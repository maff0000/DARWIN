"""PID-004A Specification Contract persistence integration tests, against a
real, disposable PostgreSQL (PID-001 sec28 discipline, same pattern as
tests/integration/test_postgres_repositories.py and
tests/integration/test_scout_persistence.py). Skipped automatically unless
DARWIN_TEST_PG_DSN is set.

Every StrategyVersion persisted here is either a controlled architectural
conformance fixture (mirroring tests/contract/test_specification_fixtures.py,
clearly labelled below) or synthetic test data built for this file alone --
never presented as real discovered/proven strategy evidence (PID-004
sec20/sec30/sec41). No SCOUT-derived candidate is fabricated anywhere in
this file (PID-004A persistence directive item 21) -- SCOUT stays entirely
out of scope for this persistence proof.
"""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse

import psycopg
import pytest

from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.migrations import migration_state, run_migrations
from darwin.research_store.models import StrategyCandidate
from darwin.research_store.repositories import StrategyCandidateRepository
from darwin.research_store.specification_finalisation import (
    SpecificationDraftRevisionAlreadyFinalisedConflictError,
    finalise_specification_draft,
)
from darwin.research_store.specification_repositories import (
    DataReadinessAssessmentRepository,
    DataRequirementProjectionRepository,
    ShelvingRepository,
    SpecificationDraftRepository,
    SpecificationVersionRepository,
    StaleRevisionError,
    ValidationRecordRepository,
)
from darwin.specification.applicability import IntrabarAmbiguityPolicy
from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.composition import (
    AllComposition,
    AnyComposition,
    AtomicCondition,
    ContextTriggerComposition,
    Direction,
    ExpiryMode,
    ExpirySpec,
    SequenceComponent,
    SequenceComposition,
    SequenceTieSemantics,
)
from darwin.specification.data_requirements import (
    DataAuthorityClass,
    DataRequirement,
    FactClass,
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.domain import SpecificationDraft, StrategyVersion
from darwin.specification.expressions import (
    Comparison,
    ComparisonOperator,
    EventPredicate,
    Literal,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    FactReferenceKind,
    MissingInputBehavior,
    SpecificationDerivedFact,
)
from darwin.specification.fingerprint import canonical_hash
from darwin.specification.readiness import (
    OverallReadinessState,
    PerRequirementAvailability,
    assess_readiness,
)
from darwin.specification.serialization import (
    deserialize_strategy_version,
)
from darwin.specification.timeframe import Timeframe
from darwin.specification.validation import (
    ValidationOutcomeStatus,
    finalise,
)
from tests.fixtures.specification_drafts import (
    XAU_USD_APPLICABILITY,
    accepted_provenance,
    h1_close_reference,
    h1_high_reference,
    hermes_ohlcv_requirement,
    minimal_valid_draft,
    simple_atomic_condition,
)

pytestmark = pytest.mark.integration


# --- shared helpers -----------------------------------------------------------


def _new_candidate(conn, *, title: str = "Persistence test candidate") -> str:
    candidate_id = new_id()
    StrategyCandidateRepository(conn).create(StrategyCandidate(id=candidate_id, title=title))
    return candidate_id


def _house_under_real_candidate(conn, draft: SpecificationDraft, *, candidate_id: str | None = None) -> str:
    """Fixture/synthetic drafts use plain governed string ids (e.g.
    "fixture-01") that are legitimate at the domain layer but are not
    themselves database identity decisions (see migration 0006's header
    comment) -- this re-houses a draft under a real UUID draft_id/
    candidate_id before it is persisted. Mutating `candidate_id` here is
    always safe: it is explicitly EXCLUDED from `semantic_fingerprint`
    (darwin.specification.domain._EXCLUDED_FROM_SEMANTIC_FINGERPRINT), so
    this never changes the semantic identity of what gets finalised --
    only `artifact_record_fingerprint` (computed fresh, AFTER this swap,
    by `finalise()`) is candidate_id-sensitive, and it is always computed
    consistently against whichever candidate_id is in place at finalise()
    time.
    """
    candidate_id = candidate_id or _new_candidate(conn)
    draft.draft_id = new_id()
    draft.candidate_id = candidate_id
    return candidate_id


def _persist_draft(conn, draft: SpecificationDraft) -> None:
    SpecificationDraftRepository(conn).create(draft)


# ============================================================================
# Migration state + existing-data safety (PID-004A persistence directive
# item 17)
# ============================================================================


def test_migration_0006_is_applied_and_up_to_date(pg_config):
    from tests.integration.conftest import MIGRATIONS_DIR

    state = migration_state(pg_config, MIGRATIONS_DIR)
    assert state["up_to_date"] is True
    assert "0006_strategy_specification" in state["applied"]
    for earlier in (
        "0001_foundation",
        "0002_research_run_instrument_binding",
        "0003_instrument_definition_binding",
        "0004_dike_policy_binding",
        "0005_scout_discovery",
    ):
        assert earlier in state["applied"]


def test_migration_runner_is_idempotent_running_twice(pg_config):
    from tests.integration.conftest import MIGRATIONS_DIR

    applied_again = run_migrations(pg_config, MIGRATIONS_DIR)
    assert applied_again == []  # nothing re-applied, no error


def test_0006_applies_cleanly_after_0001_through_0005_and_preexisting_rows_survive():
    """A from-scratch proof, deliberately NOT using the shared session
    `pg_config` fixture (which already applies every migration including
    0006 before any test runs) -- this test needs a database that starts
    at exactly 0001-0005, has real Foundation + SCOUT rows inserted, and
    THEN has 0006 applied, to prove 0006 (a) applies cleanly on top of
    0001-0005 and (b) never touches/truncates/recreates pre-existing rows.
    """
    import os
    import shutil
    import tempfile
    from pathlib import Path

    import darwin.research_store as _research_store
    from darwin.core.config import PostgresConfig

    dsn = os.environ.get("DARWIN_TEST_PG_DSN")
    if not dsn:
        pytest.skip("DARWIN_TEST_PG_DSN not set")
    parsed = urlparse(dsn)
    admin_cfg = PostgresConfig(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database=(parsed.path or "/darwin").lstrip("/"),
        user=parsed.username or "darwin_test",
        password=parsed.password or "",
    )
    fresh_db_name = f"darwin_0006_safety_{new_id().replace('-', '_')}"
    with psycopg.connect(admin_cfg.dsn(), autocommit=True) as admin_conn, admin_conn.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{fresh_db_name}"')
    fresh_cfg = PostgresConfig(
        host=admin_cfg.host, port=admin_cfg.port, database=fresh_db_name,
        user=admin_cfg.user, password=admin_cfg.password,
    )
    try:
        migrations_dir = Path(_research_store.__file__).resolve().parent / "migrations_sql"
        all_files = sorted(migrations_dir.glob("*.sql"), key=lambda p: p.name)
        pre_0006_files = [p for p in all_files if p.name < "0006"]
        assert pre_0006_files, "expected at least one pre-0006 migration file"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            for f in pre_0006_files:
                shutil.copy(f, tmp_dir / f.name)
            applied_pre = run_migrations(fresh_cfg, tmp_dir)
            assert "0006_strategy_specification" not in applied_pre

        # Insert real pre-existing Foundation + SCOUT rows before 0006 exists.
        from darwin.research_store.models import SourceStrategy
        from darwin.research_store.repositories import (
            ScoutSourceRepository,
            SourceStrategyRepository,
        )

        with connection(fresh_cfg) as conn:
            SourceStrategyRepository(conn).create(
                SourceStrategy(id=new_id(), source_type="TEST", source_reference="ref", title="Pre-0006 source")
            )
            candidate_id = _new_candidate(conn, title="Pre-0006 candidate")
            trader_dev_source = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")
            assert trader_dev_source is not None

        # Now apply the FULL migration set (includes 0006) on top.
        applied_full = run_migrations(fresh_cfg, migrations_dir)
        assert "0006_strategy_specification" in applied_full

        state = migration_state(fresh_cfg, migrations_dir)
        assert state["up_to_date"] is True

        with connection(fresh_cfg) as conn:
            assert SourceStrategyRepository(conn).count() == 1
            assert StrategyCandidateRepository(conn).count() == 1
            sources = ScoutSourceRepository(conn).list()
            assert {s["source_key"] for s in sources} == {"TRADER_DEV_PUBLIC", "USER_DISCOVERED", "MY_IDEA"}

            # New PID-004A tables exist and are empty, not error-raising.
            assert SpecificationDraftRepository(conn).list_for_candidate(candidate_id) == []
    finally:
        with psycopg.connect(admin_cfg.dsn(), autocommit=True) as admin_conn, admin_conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s",
                (fresh_db_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{fresh_db_name}"')


# ============================================================================
# Drafts (PID-004A persistence directive item 19 "Drafts")
# ============================================================================


def test_draft_create_and_read_round_trips(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)

        rehydrated = SpecificationDraftRepository(conn).get(draft.draft_id)
        assert rehydrated is not None
        assert rehydrated.draft_id == draft.draft_id
        assert rehydrated.candidate_id == candidate_id
        assert rehydrated.title == draft.title
        assert rehydrated.composition.condition_id == draft.composition.condition_id
        assert set(rehydrated.data_requirements) == set(draft.data_requirements)

        row = SpecificationDraftRepository(conn).get_row(draft.draft_id)
        assert row["revision"] == 1


def test_draft_update_with_expected_revision_succeeds(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)

        draft.title = "Updated title"
        new_revision = SpecificationDraftRepository(conn).update_with_expected_revision(draft.draft_id, 1, draft)
        assert new_revision == 2

        rehydrated = SpecificationDraftRepository(conn).get(draft.draft_id)
        assert rehydrated.title == "Updated title"
        row = SpecificationDraftRepository(conn).get_row(draft.draft_id)
        assert row["revision"] == 2


def test_draft_update_with_stale_revision_is_refused(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)

        draft.title = "First edit"
        SpecificationDraftRepository(conn).update_with_expected_revision(draft.draft_id, 1, draft)

        draft.title = "Stale edit -- should be refused"
        with pytest.raises(StaleRevisionError):
            SpecificationDraftRepository(conn).update_with_expected_revision(draft.draft_id, 1, draft)

        # Refused write never landed -- title is still the first edit.
        rehydrated = SpecificationDraftRepository(conn).get(draft.draft_id)
        assert rehydrated.title == "First edit"


def test_incomplete_draft_can_persist(pg_config):
    """A materially incomplete SpecificationDraft (no composition at all)
    is perfectly legitimate authoring-in-progress state (PID-004 sec4.3)
    and must persist without any validation being applied at the
    persistence layer -- validation is a separate, explicit step."""
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        bare = SpecificationDraft(
            draft_id=new_id(), candidate_id=candidate_id, schema_semantic_version="1.0.0", title="Barely started",
        )
        SpecificationDraftRepository(conn).create(bare)
        rehydrated = SpecificationDraftRepository(conn).get(bare.draft_id)
        assert rehydrated is not None
        assert rehydrated.composition is None
        assert rehydrated.instrument_applicability is None


def test_persisting_or_updating_a_draft_never_creates_a_strategy_version(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)
        draft.title = "Edited, still just a draft"
        SpecificationDraftRepository(conn).update_with_expected_revision(draft.draft_id, 1, draft)

        assert SpecificationVersionRepository(conn).list_for_candidate(candidate_id) == []


# ============================================================================
# Finalisation (item 19 "Finalisation") -- uses controlled fixture-01
# (tests/fixtures/specification_drafts.minimal_valid_draft), clearly an
# architecture-proof fixture, never real SCOUT-derived evidence (item 21).
# ============================================================================


def test_valid_draft_finalises_atomically_and_candidate_becomes_specified(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)

        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        assert outcome.outcome.status == ValidationOutcomeStatus.VALID
        assert outcome.strategy_version is not None
        assert outcome.candidate_advanced is True

        version_row = SpecificationVersionRepository(conn).get_row(outcome.strategy_version.strategy_version_id)
        assert version_row is not None
        requirement_rows = DataRequirementProjectionRepository(conn).list_for_strategy_version(
            outcome.strategy_version.strategy_version_id
        )
        assert len(requirement_rows) == len(outcome.strategy_version.data_requirements)

        with conn.cursor() as cur:
            cur.execute("SELECT pipeline_stage FROM strategy_candidates WHERE id = %s", (candidate_id,))
            assert cur.fetchone()["pipeline_stage"] == "SPECIFIED"

        validation_rows = ValidationRecordRepository(conn).list_for_draft(draft.draft_id)
        assert len(validation_rows) == 1
        assert validation_rows[0]["status"] == "VALID"
        assert str(validation_rows[0]["strategy_version_id"]) == outcome.strategy_version.strategy_version_id


def test_invalid_draft_persists_refusal_and_creates_no_strategy_version(pg_config):
    """Fixture-12 equivalent (tests/contract/test_specification_fixtures.py
    test_fixture_12): a deliberately ambiguous condition --
    STRATEGY_NOT_SUFFICIENTLY_DEFINED."""
    from darwin.specification.expressions import UndefinedMeasurementBasis

    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        ambiguous = AtomicCondition(
            condition_id="near_the_iv_wall", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
            expression=Comparison(
                operator=ComparisonOperator.LT, left=h1_close_reference(),
                right=UndefinedMeasurementBasis(note="'near an IV wall' names no wall definition"),
            ),
            direction=Direction.SHORT,
        )
        draft = SpecificationDraft(
            draft_id=new_id(), candidate_id=candidate_id, schema_semantic_version="1.0.0",
            title="Deliberately insufficient", instrument_applicability=XAU_USD_APPLICABILITY, composition=ambiguous,
            intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
            setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
        )
        draft.set_provenance(accepted_provenance("near_the_iv_wall"))
        _persist_draft(conn, draft)

        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        assert outcome.outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
        assert outcome.strategy_version is None
        assert outcome.candidate_advanced is False

        assert SpecificationVersionRepository(conn).list_for_candidate(candidate_id) == []
        with conn.cursor() as cur:
            cur.execute("SELECT pipeline_stage FROM strategy_candidates WHERE id = %s", (candidate_id,))
            assert cur.fetchone()["pipeline_stage"] == "DISCOVERED"

        validation_rows = ValidationRecordRepository(conn).list_for_draft(draft.draft_id)
        assert len(validation_rows) == 1
        assert validation_rows[0]["status"] == "STRATEGY_NOT_SUFFICIENTLY_DEFINED"
        assert validation_rows[0]["strategy_version_id"] is None
        assert len(validation_rows[0]["findings"]) >= 1


def test_finalisation_round_trip_exact_and_fingerprints_match(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        original = outcome.strategy_version

        rehydrated = SpecificationVersionRepository(conn).get(original.strategy_version_id)
        assert rehydrated is not None
        assert rehydrated == original  # exact dataclass equality -- lossless round trip

        assert canonical_hash(rehydrated.semantic_payload()) == original.semantic_fingerprint
        assert canonical_hash(rehydrated.artifact_payload()) == original.artifact_record_fingerprint

        row = SpecificationVersionRepository(conn).get_row(original.strategy_version_id)
        assert row["semantic_fingerprint"] == original.semantic_fingerprint
        assert row["artifact_record_fingerprint"] == original.artifact_record_fingerprint


def test_data_blocked_strategy_still_finalises_and_candidate_still_advances(pg_config):
    """PID-004 sec34: finalisation never requires TESTABLE."""
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        iv_requirement = DataRequirement(
            requirement_id="xau_iv_surface", display_name="XAU_USD implied volatility surface",
            fact_class=FactClass.IMPLIED_VOLATILITY, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
            timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(3, HistoricalDepthUnit.YEARS),
            units="IV_PERCENT", required_fields=("strike", "expiry", "implied_volatility"),
            causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
        )
        iv_wall_fact = CanonicalFactReference(
            fact_key="OPTIONS.IMPLIED_VOLATILITY", fact_class=FactClass.IMPLIED_VOLATILITY,
            authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, unit="IV_PERCENT", timeframe=Timeframe("D1"),
            requirement_id="xau_iv_surface",
        )
        wall_exit = AtomicCondition(
            condition_id="iv_wall_context", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
            expression=Comparison(operator=ComparisonOperator.GT, left=iv_wall_fact, right=Literal(Decimal(0), unit="IV_PERCENT")),
            direction=Direction.BOTH,
        )
        trigger = simple_atomic_condition("price_approaches_iv_wall", threshold="4000")
        draft = SpecificationDraft(
            draft_id=new_id(), candidate_id=candidate_id, schema_semantic_version="1.0.0",
            title="IV-wall data-blocked fixture", instrument_applicability=XAU_USD_APPLICABILITY, composition=trigger,
            intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
            setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
        )
        draft.exit_rules = (wall_exit,)
        draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
        draft.set_data_requirement(iv_requirement)
        draft.set_provenance(accepted_provenance("price_approaches_iv_wall"))
        draft.set_provenance(accepted_provenance("iv_wall_context"))
        _persist_draft(conn, draft)

        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        assert outcome.outcome.status == ValidationOutcomeStatus.VALID
        assert outcome.candidate_advanced is True
        version = outcome.strategy_version

        readiness = assess_readiness(
            assessment_id=new_id(), strategy_version_id=version.strategy_version_id,
            mandatory_requirement_ids={r.requirement_id for r in version.data_requirements},
            per_requirement={
                "hermes_xau_usd_h1_ohlcv": (PerRequirementAvailability.AVAILABLE, None),
                "xau_iv_surface": (PerRequirementAvailability.AUTHORITY_NOT_ONBOARDED, "not onboarded"),
            },
            assessed_at_utc=datetime.now(UTC),
        )
        assert readiness.overall_state == OverallReadinessState.DATA_BLOCKED
        DataReadinessAssessmentRepository(conn).create(readiness)


# ============================================================================
# Finalisation idempotency (adversarial-audit fix #1): a particular
# (draft_id, draft_revision) pair may create AT MOST ONE StrategyVersion.
# ============================================================================


def test_sequential_duplicate_finalisation_retry_is_idempotent_not_a_second_version(pg_config):
    """A non-concurrent, retried call (same draft_id/expected_revision)
    must return the SAME StrategyVersion, never mint a second one or write
    a second VALID validation record."""
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)

        first = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        assert first.strategy_version is not None

    with connection(pg_config) as conn:
        second = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)

    assert second.strategy_version is not None
    assert second.strategy_version.strategy_version_id == first.strategy_version.strategy_version_id
    assert second.validation_record_id == first.validation_record_id
    assert second.candidate_advanced is False  # nothing new was advanced on the retry

    with connection(pg_config) as conn:
        rows = SpecificationVersionRepository(conn).list_for_candidate(candidate_id)
        assert len(rows) == 1

        valid_records = [
            r for r in ValidationRecordRepository(conn).list_for_draft(draft.draft_id) if r["status"] == "VALID"
        ]
        assert len(valid_records) == 1


def test_finalising_a_new_revision_after_an_edit_creates_a_genuinely_new_strategy_version(pg_config):
    """Finalising does not advance `revision` -- only an explicit edit
    does. Once the draft is genuinely edited to revision 2, finalising
    revision 2 must create a brand new, distinct StrategyVersion (not be
    treated as a duplicate of revision 1's)."""
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)

        outcome_a = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        version_a = outcome_a.strategy_version
        assert version_a is not None

        # Finalisation must never itself have bumped the draft's revision.
        draft_row = SpecificationDraftRepository(conn).get_row(draft.draft_id)
        assert int(draft_row["revision"]) == 1

        draft.title = "Simple close-above-level long -- edited"
        new_revision = SpecificationDraftRepository(conn).update_with_expected_revision(draft.draft_id, 1, draft)
        assert new_revision == 2

        outcome_b = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=2)
        version_b = outcome_b.strategy_version
        assert version_b is not None
        assert version_b.strategy_version_id != version_a.strategy_version_id
        assert version_b.title != version_a.title

        rows = SpecificationVersionRepository(conn).list_for_candidate(candidate_id)
        assert len(rows) == 2


def test_conflicting_explicit_strategy_version_id_on_retry_raises_typed_conflict_error(pg_config):
    """A retry that supplies an EXPLICIT strategy_version_id that
    disagrees with the one already finalised for this exact draft
    revision must be refused with a typed conflict error -- never silently
    accepted, never silently ignored."""
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)

    with pytest.raises(SpecificationDraftRevisionAlreadyFinalisedConflictError) as excinfo, connection(
        pg_config
    ) as conn:
        finalise_specification_draft(
            conn, draft_id=draft.draft_id, expected_revision=1, strategy_version_id=new_id(),
        )
    assert excinfo.value.code == "SPECIFICATION_DRAFT_REVISION_ALREADY_FINALISED_CONFLICT"

    with connection(pg_config) as conn:
        rows = SpecificationVersionRepository(conn).list_for_candidate(candidate_id)
        assert len(rows) == 1  # the conflicting retry created nothing


def test_concurrent_finalisation_of_the_same_draft_revision_creates_exactly_one_strategy_version(pg_config):
    """The adversarial audit's required proof: two independent DB
    connections, two real threads, synchronised to start together, both
    finalising the SAME (draft_id, expected_revision). After both
    complete: exactly one StrategyVersion, exactly one VALID validation
    record, both callers agree on the same logical result (or one got the
    idempotent existing result), the candidate reached SPECIFIED exactly
    once, the data-requirement projection exists exactly once, and no
    error/orphaned state is left behind."""
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
    draft_id = draft.draft_id

    barrier = threading.Barrier(2)
    results: list = []
    errors: list = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait(timeout=10)
        try:
            with connection(pg_config) as thread_conn:
                outcome = finalise_specification_draft(
                    thread_conn, draft_id=draft_id, expected_revision=1
                )
            with lock:
                results.append(outcome)
        except Exception as exc:  # noqa: BLE001 -- captured for the assertion below, not swallowed
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"unexpected errors from concurrent finalisation: {errors!r}"
    assert len(results) == 2

    version_ids = {outcome.strategy_version.strategy_version_id for outcome in results}
    assert len(version_ids) == 1, "both concurrent callers must agree on exactly one StrategyVersion"
    (strategy_version_id,) = version_ids

    with connection(pg_config) as conn:
        version_rows = SpecificationVersionRepository(conn).list_for_candidate(candidate_id)
        assert len(version_rows) == 1
        assert str(version_rows[0]["id"]) == strategy_version_id

        valid_records = [
            r for r in ValidationRecordRepository(conn).list_for_draft(draft_id) if r["status"] == "VALID"
        ]
        assert len(valid_records) == 1

        with conn.cursor() as cur:
            cur.execute("SELECT pipeline_stage FROM strategy_candidates WHERE id = %s", (candidate_id,))
            assert cur.fetchone()["pipeline_stage"] == "SPECIFIED"

        requirement_rows = DataRequirementProjectionRepository(conn).list_for_strategy_version(
            strategy_version_id
        )
        assert len(requirement_rows) == 1  # minimal_valid_draft declares exactly one requirement


def test_db_unique_index_backstops_a_missed_application_level_idempotency_check(pg_config, monkeypatch):
    """Direct proof of the crux of the fix: even when the application-level
    check-then-act is bypassed/missed (simulated here by monkeypatching the
    internal lookup helper to miss on its first call, exactly as a genuine
    race between the check and the INSERT could), migration 0007's partial
    unique index on strategy_versions(source_draft_id,
    source_draft_revision) is the real backstop -- the duplicate INSERT
    fails at the database, and finalise_specification_draft recovers to the
    pre-existing result instead of raising a surprise integrity error."""
    import darwin.research_store.specification_finalisation as finalisation_module

    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)

        # Simulate "a finalisation for this exact draft/revision already
        # committed" by inserting the StrategyVersion directly through the
        # repository -- entirely bypassing finalise_specification_draft's
        # own idempotency check, exactly the race window the DB constraint
        # exists to backstop.
        rogue_version_id = new_id()
        precomputed = finalise(draft, strategy_version_id=rogue_version_id)
        assert precomputed.strategy_version is not None
        SpecificationVersionRepository(conn).create(
            precomputed.strategy_version, source_draft_id=draft.draft_id, source_draft_revision=1,
        )
        DataRequirementProjectionRepository(conn).create_many(
            rogue_version_id, precomputed.strategy_version.data_requirements
        )
        ValidationRecordRepository(conn).create(
            draft_id=draft.draft_id, draft_revision=1, assessed_at_utc=datetime.now(UTC),
            status="VALID", findings=[], strategy_version_id=rogue_version_id,
        )

    real_check = finalisation_module._load_existing_finalisation
    call_count = {"n": 0}

    def blind_on_first_call(conn, *, draft_id, draft_revision):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None, None  # simulate the application-level check missing the race
        return real_check(conn, draft_id=draft_id, draft_revision=draft_revision)

    monkeypatch.setattr(finalisation_module, "_load_existing_finalisation", blind_on_first_call)

    with connection(pg_config) as conn:
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)

    assert call_count["n"] == 2  # the blind pre-check, then the post-conflict recovery
    assert outcome.strategy_version is not None
    assert outcome.strategy_version.strategy_version_id == rogue_version_id

    with connection(pg_config) as conn:
        rows = SpecificationVersionRepository(conn).list_for_candidate(candidate_id)
        assert len(rows) == 1  # never a second row despite the missed application-level check

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM strategy_version_data_requirements WHERE strategy_version_id = %s",
                (rogue_version_id,),
            )
            assert cur.fetchone()["n"] == 1  # the failed insert attempt left no partial data behind


# ============================================================================
# Immutability (item 19 "Immutability" / item 7)
# ============================================================================


def test_strategy_version_repository_exposes_no_update_or_delete_method():
    repo_methods = {name for name in dir(SpecificationVersionRepository) if not name.startswith("_")}
    assert "update" not in repo_methods
    assert "delete" not in repo_methods
    assert repo_methods == {
        "create", "get_row", "get", "list_for_candidate", "list_by_semantic_fingerprint",
        "get_row_by_draft_and_revision",
    }


def test_db_refuses_raw_update_against_a_finalised_strategy_version(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        version_id = outcome.strategy_version.strategy_version_id

    # Two independent reasons this must fail as of the PID-004A
    # adversarial-audit privilege-separation fix: the immutability trigger
    # (migration 0006) fires under a role still privileged enough to reach
    # it (e.g. this file's own shared superuser-equivalent test role), OR
    # lack of UPDATE privilege fires first under the restricted darwin_app
    # role (see tests/integration/test_privilege_separation.py, which
    # proves this exact statement against the real restricted role) --
    # either is an acceptable proof that the mutation was refused.
    with connection(pg_config) as conn:
        with pytest.raises(
            (psycopg.errors.RaiseException, psycopg.errors.InsufficientPrivilege)
        ) as excinfo, conn.cursor() as cur:
            cur.execute("UPDATE strategy_versions SET title = 'HACKED' WHERE id = %s", (version_id,))
        message = str(excinfo.value).lower()
        assert "immutable" in message or "permission denied" in message
        conn.rollback()

    with connection(pg_config) as conn:
        row = SpecificationVersionRepository(conn).get_row(version_id)
        assert row["title"] != "HACKED"


def test_db_refuses_raw_delete_against_a_finalised_strategy_version(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        version_id = outcome.strategy_version.strategy_version_id

    # See the comment in test_db_refuses_raw_update_against_a_finalised_
    # strategy_version above -- two independent, equally valid failure
    # reasons as of the privilege-separation fix.
    with connection(pg_config) as conn:
        with pytest.raises(
            (psycopg.errors.RaiseException, psycopg.errors.InsufficientPrivilege)
        ) as excinfo, conn.cursor() as cur:
            cur.execute("DELETE FROM strategy_versions WHERE id = %s", (version_id,))
        message = str(excinfo.value).lower()
        assert "immutable" in message or "permission denied" in message
        conn.rollback()

    with connection(pg_config) as conn:
        assert SpecificationVersionRepository(conn).get_row(version_id) is not None


def test_db_refuses_raw_update_and_delete_against_the_data_requirement_projection(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        rows = DataRequirementProjectionRepository(conn).list_for_strategy_version(
            outcome.strategy_version.strategy_version_id
        )
        requirement_row_id = rows[0]["id"]

    # See the comment in test_db_refuses_raw_update_against_a_finalised_
    # strategy_version above -- two independent, equally valid failure
    # reasons as of the privilege-separation fix.
    with connection(pg_config) as conn:
        with pytest.raises(
            (psycopg.errors.RaiseException, psycopg.errors.InsufficientPrivilege)
        ), conn.cursor() as cur:
            cur.execute(
                "UPDATE strategy_version_data_requirements SET display_name = 'HACKED' WHERE id = %s",
                (requirement_row_id,),
            )
        conn.rollback()
    with connection(pg_config) as conn:
        with pytest.raises(
            (psycopg.errors.RaiseException, psycopg.errors.InsufficientPrivilege)
        ), conn.cursor() as cur:
            cur.execute("DELETE FROM strategy_version_data_requirements WHERE id = %s", (requirement_row_id,))
        conn.rollback()


# ============================================================================
# Semantic equality (item 19 "Semantic equality" / item 6)
# ============================================================================


def test_two_distinct_candidates_identical_semantics_both_survive_same_semantic_fingerprint(pg_config):
    with connection(pg_config) as conn:
        candidate_a = _new_candidate(conn, title="Candidate A")
        candidate_b = _new_candidate(conn, title="Candidate B")

        draft_a = minimal_valid_draft()
        draft_a.draft_id = new_id()
        draft_a.candidate_id = candidate_a
        draft_b = minimal_valid_draft()
        draft_b.draft_id = new_id()
        draft_b.candidate_id = candidate_b

        _persist_draft(conn, draft_a)
        _persist_draft(conn, draft_b)

        outcome_a = finalise_specification_draft(conn, draft_id=draft_a.draft_id, expected_revision=1)
        outcome_b = finalise_specification_draft(conn, draft_id=draft_b.draft_id, expected_revision=1)

        version_a, version_b = outcome_a.strategy_version, outcome_b.strategy_version
        assert version_a.strategy_version_id != version_b.strategy_version_id
        assert version_a.semantic_fingerprint == version_b.semantic_fingerprint
        assert version_a.artifact_record_fingerprint != version_b.artifact_record_fingerprint

        # Both rows genuinely survive -- neither was merged/deduped away.
        assert SpecificationVersionRepository(conn).get_row(version_a.strategy_version_id) is not None
        assert SpecificationVersionRepository(conn).get_row(version_b.strategy_version_id) is not None
        matches = SpecificationVersionRepository(conn).list_by_semantic_fingerprint(version_a.semantic_fingerprint)
        assert {str(row["id"]) for row in matches} >= {version_a.strategy_version_id, version_b.strategy_version_id}


# ============================================================================
# Data requirements (item 19 "Data requirements" / item 8)
# ============================================================================


def test_data_requirement_projection_matches_canonical_payload(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        version = outcome.strategy_version

        projected = {
            row["requirement_id"]: row
            for row in DataRequirementProjectionRepository(conn).list_for_strategy_version(version.strategy_version_id)
        }
        assert set(projected) == {r.requirement_id for r in version.data_requirements}
        for requirement in version.data_requirements:
            row = projected[requirement.requirement_id]
            assert row["fact_class"] == requirement.fact_class.value
            assert row["authority_class"] == requirement.authority_class.value
            assert row["units"] == requirement.units
            assert set(row["required_fields"]) == set(requirement.required_fields)


def test_orphan_data_readiness_requirement_reference_is_refused_by_the_database(pg_config):
    """A readiness per-requirement row must never be able to reference a
    requirement belonging to a DIFFERENT StrategyVersion (PID-004A
    persistence directive item 9) -- proven here with a direct, deliberate
    raw-SQL attempt, not just application-level care."""
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft_1 = minimal_valid_draft()
        _house_under_real_candidate(conn, draft_1, candidate_id=candidate_id)
        _persist_draft(conn, draft_1)
        version_1 = finalise_specification_draft(conn, draft_id=draft_1.draft_id, expected_revision=1).strategy_version

        candidate_2 = _new_candidate(conn)
        draft_2 = minimal_valid_draft()
        _house_under_real_candidate(conn, draft_2, candidate_id=candidate_2)
        # A requirement genuinely unique to draft_2 -- minimal_valid_draft()'s
        # default HERMES H1 OHLCV requirement id is identical across every
        # draft built from it, so it alone would NOT prove cross-version
        # isolation (it would legitimately also exist under version_1).
        unique_requirement = DataRequirement(
            requirement_id="unique_to_version_2_only", display_name="Unique to version 2",
            fact_class=FactClass.MARKET_OHLCV, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET, instrument_applicability=("XAU_USD",),
            timeframe=Timeframe("H4"), required_historical_depth=HistoricalDepthRequirement(200, HistoricalDepthUnit.BARS),
            units="USD_PER_TROY_OUNCE", required_fields=("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"),
            causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE, mandatory=False,
        )
        draft_2.set_data_requirement(unique_requirement)
        _persist_draft(conn, draft_2)
        version_2 = finalise_specification_draft(conn, draft_id=draft_2.draft_id, expected_revision=1).strategy_version

        assessment_id = new_id()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_readiness_assessments
                    (id, strategy_version_id, assessed_at_utc, overall_state, mandatory_requirement_ids)
                VALUES (%s, %s, now(), 'TESTABLE', '[]'::jsonb)
                """,
                (assessment_id, version_1.strategy_version_id),
            )
        conn.commit()

        # version_2's own requirement_id genuinely exists -- but NOT under version_1.
        real_requirement_id_of_version_2 = "unique_to_version_2_only"
        assert real_requirement_id_of_version_2 in {r.requirement_id for r in version_2.data_requirements}
        assert real_requirement_id_of_version_2 not in {r.requirement_id for r in version_1.data_requirements}
        with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_readiness_assessment_requirements
                    (id, assessment_id, strategy_version_id, requirement_id, availability)
                VALUES (%s, %s, %s, %s, 'AVAILABLE')
                """,
                (new_id(), assessment_id, version_1.strategy_version_id, real_requirement_id_of_version_2),
            )
        conn.rollback()


def test_query_data_requirements_by_fact_class_and_authority_class(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        iv_requirement = DataRequirement(
            requirement_id="xau_iv_surface", display_name="XAU_USD implied volatility surface",
            fact_class=FactClass.IMPLIED_VOLATILITY, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
            timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(3, HistoricalDepthUnit.YEARS),
            units="IV_PERCENT", required_fields=("strike", "expiry", "implied_volatility"),
            causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
        )
        iv_wall_fact = CanonicalFactReference(
            fact_key="OPTIONS.IMPLIED_VOLATILITY", fact_class=FactClass.IMPLIED_VOLATILITY,
            authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, unit="IV_PERCENT", timeframe=Timeframe("D1"),
            requirement_id="xau_iv_surface",
        )
        wall_exit = AtomicCondition(
            condition_id="iv_wall_context_q", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
            expression=Comparison(operator=ComparisonOperator.GT, left=iv_wall_fact, right=Literal(Decimal(0), unit="IV_PERCENT")),
            direction=Direction.BOTH,
        )
        trigger = simple_atomic_condition("price_query_trigger", threshold="4000")
        draft = SpecificationDraft(
            draft_id=new_id(), candidate_id=candidate_id, schema_semantic_version="1.0.0",
            title="Query-by-fact-class fixture", instrument_applicability=XAU_USD_APPLICABILITY, composition=trigger,
            intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
            setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
        )
        draft.exit_rules = (wall_exit,)
        draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
        draft.set_data_requirement(iv_requirement)
        draft.set_provenance(accepted_provenance("price_query_trigger"))
        draft.set_provenance(accepted_provenance("iv_wall_context_q"))
        _persist_draft(conn, draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        version_id = outcome.strategy_version.strategy_version_id

        proj_repo = DataRequirementProjectionRepository(conn)
        iv_matches = proj_repo.query(fact_class="IMPLIED_VOLATILITY")
        assert any(str(r["strategy_version_id"]) == version_id and r["requirement_id"] == "xau_iv_surface" for r in iv_matches)

        options_authority_matches = proj_repo.distinct_strategy_version_ids(authority_class="OPTIONS_AUTHORITY")
        assert version_id in options_authority_matches

        hermes_only = proj_repo.distinct_strategy_version_ids(authority_class="HERMES_CANONICAL_MARKET")
        assert version_id in hermes_only  # also requires HERMES OHLCV


# ============================================================================
# Readiness (item 19 "Readiness")
# ============================================================================


def test_data_blocked_then_testable_readiness_both_retained_in_history_same_version(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        version = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1).strategy_version

        mandatory_ids = {r.requirement_id for r in version.data_requirements}
        blocked = assess_readiness(
            assessment_id=new_id(), strategy_version_id=version.strategy_version_id,
            mandatory_requirement_ids=mandatory_ids,
            per_requirement={rid: (PerRequirementAvailability.UNAVAILABLE, "not yet loaded") for rid in mandatory_ids},
            assessed_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert blocked.overall_state == OverallReadinessState.DATA_BLOCKED
        DataReadinessAssessmentRepository(conn).create(blocked)

        testable = assess_readiness(
            assessment_id=new_id(), strategy_version_id=version.strategy_version_id,
            mandatory_requirement_ids=mandatory_ids,
            per_requirement={rid: (PerRequirementAvailability.AVAILABLE, None) for rid in mandatory_ids},
            assessed_at_utc=datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert testable.overall_state == OverallReadinessState.TESTABLE
        DataReadinessAssessmentRepository(conn).create(testable)

        history = DataReadinessAssessmentRepository(conn).list_for_strategy_version(version.strategy_version_id)
        assert len(history) == 2
        assert history[0]["overall_state"] == "DATA_BLOCKED"
        assert history[1]["overall_state"] == "TESTABLE"
        assert str(history[0]["strategy_version_id"]) == str(history[1]["strategy_version_id"]) == version.strategy_version_id

        # Readiness changes never touch the StrategyVersion or its
        # fingerprint (PID-004 sec26).
        row = SpecificationVersionRepository(conn).get_row(version.strategy_version_id)
        assert row["semantic_fingerprint"] == version.semantic_fingerprint


# ============================================================================
# Shelving (item 19 "Shelving" / item 10)
# ============================================================================


def test_shelving_a_data_blocked_version_never_mutates_the_version_and_history_is_preserved(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        version = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1).strategy_version

        before = SpecificationVersionRepository(conn).get_row(version.strategy_version_id)

        shelving_repo = ShelvingRepository(conn)
        shelving_repo.create_event(
            version.strategy_version_id, state="SHELVED", reason="required data unavailable",
            actor="matt", occurred_at_utc=datetime(2026, 3, 1, tzinfo=UTC),
        )
        assert shelving_repo.current_state(version.strategy_version_id) == "SHELVED"

        after = SpecificationVersionRepository(conn).get_row(version.strategy_version_id)
        assert after["semantic_fingerprint"] == before["semantic_fingerprint"]
        assert after["artifact_record_fingerprint"] == before["artifact_record_fingerprint"]
        assert after["full_payload"] == before["full_payload"]

        # A later readiness reassessment does not rewrite shelving history,
        # and shelving does not rewrite readiness history either.
        mandatory_ids = {r.requirement_id for r in version.data_requirements}
        reassessed = assess_readiness(
            assessment_id=new_id(), strategy_version_id=version.strategy_version_id,
            mandatory_requirement_ids=mandatory_ids,
            per_requirement={rid: (PerRequirementAvailability.AVAILABLE, None) for rid in mandatory_ids},
            assessed_at_utc=datetime(2026, 4, 1, tzinfo=UTC),
        )
        DataReadinessAssessmentRepository(conn).create(reassessed)
        events = shelving_repo.list_for_strategy_version(version.strategy_version_id)
        assert len(events) == 1
        assert events[0]["state"] == "SHELVED"

        shelving_repo.create_event(
            version.strategy_version_id, state="UNSHELVED", reason="data now available",
            actor="matt", occurred_at_utc=datetime(2026, 4, 2, tzinfo=UTC),
        )
        events = shelving_repo.list_for_strategy_version(version.strategy_version_id)
        assert [e["state"] for e in events] == ["SHELVED", "UNSHELVED"]  # history preserved, never rewritten


# ============================================================================
# Causality (item 19 "Causality") -- round-trips the causal timing policy
# of an external/context DataRequirement (fixture-13 equivalent).
# ============================================================================


def test_causal_external_context_requirement_round_trips_losslessly(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        cpi_requirement = DataRequirement(
            requirement_id="cpi_yoy_surprise", display_name="US CPI YoY surprise",
            fact_class=FactClass.ECONOMIC_SURPRISE, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.ARES_GOVERNED_CONTEXT, instrument_applicability=("XAU_USD",),
            timeframe=None, required_historical_depth=HistoricalDepthRequirement(10, HistoricalDepthUnit.YEARS),
            units=None, required_fields=("consensus", "actual", "surprise"),
            causal_timing_policy=CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY,
        )
        context = AtomicCondition(
            condition_id="cpi_beat_context", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
            expression=EventPredicate(fact_requirement_id="cpi_yoy_surprise"), direction=Direction.BOTH,
        )
        trigger = simple_atomic_condition("gold_reaction_trigger_causal", threshold="4000")
        draft = SpecificationDraft(
            draft_id=new_id(), candidate_id=candidate_id, schema_semantic_version="1.0.0",
            title="Causal fixture", instrument_applicability=XAU_USD_APPLICABILITY, composition=trigger,
            intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
            setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
        )
        draft.exit_rules = (context,)
        draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
        draft.set_data_requirement(cpi_requirement)
        draft.set_provenance(accepted_provenance("gold_reaction_trigger_causal"))
        draft.set_provenance(accepted_provenance("cpi_beat_context"))
        _persist_draft(conn, draft)
        version = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1).strategy_version

        rehydrated = SpecificationVersionRepository(conn).get(version.strategy_version_id)
        cpi_req = next(r for r in rehydrated.data_requirements if r.requirement_id == "cpi_yoy_surprise")
        assert cpi_req.causal_timing_policy == CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY

        projection_row = next(
            r for r in DataRequirementProjectionRepository(conn).list_for_strategy_version(version.strategy_version_id)
            if r["requirement_id"] == "cpi_yoy_surprise"
        )
        assert projection_row["causal_timing_policy"] == "ORIGINAL_PUBLISHED_VALUE_ONLY"


# ============================================================================
# Composition round trip (item 19 "Composition") -- ATOMIC/ALL/ANY/
# SEQUENCE/CONTEXT_TRIGGER/multi-timeframe, mirroring
# tests/contract/test_specification_fixtures.py fixtures 1-6.
# ============================================================================


def _finalise_bare(conn, candidate_id: str, composition, *, exit_rules=(), extra_requirements=()) -> StrategyVersion:
    draft = SpecificationDraft(
        draft_id=new_id(), candidate_id=candidate_id, schema_semantic_version="1.0.0",
        title="Composition round-trip fixture", instrument_applicability=XAU_USD_APPLICABILITY, composition=composition,
        intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
        setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
    )
    draft.exit_rules = exit_rules
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H4"))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="M5"))
    for req in extra_requirements:
        draft.set_data_requirement(req)
    from darwin.specification.composition import all_leaf_conditions

    for leaf in all_leaf_conditions(composition):
        draft.set_provenance(accepted_provenance(leaf.condition_id))
    for exit_rule in exit_rules:
        draft.set_provenance(accepted_provenance(exit_rule.condition_id))
    _persist_draft(conn, draft)
    outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
    assert outcome.outcome.status == ValidationOutcomeStatus.VALID, outcome.outcome.findings
    return outcome.strategy_version


def test_composition_round_trip_all_any_sequence_context_trigger(pg_config):
    with connection(pg_config) as conn:
        # ATOMIC
        atomic_candidate = _new_candidate(conn)
        atomic_version = _finalise_bare(conn, atomic_candidate, simple_atomic_condition("atomic_close_above"))
        assert (
            SpecificationVersionRepository(conn).get(atomic_version.strategy_version_id).composition.primitive.value
            == "ATOMIC"
        )

        # ALL
        all_candidate = _new_candidate(conn)
        all_comp = AllComposition(
            composition_id="all_rt", components=(
                simple_atomic_condition("all_close_above_rt", threshold="4000"),
                AtomicCondition(
                    condition_id="all_high_above_rt", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
                    expression=Comparison(operator=ComparisonOperator.GT, left=h1_high_reference("H1"), right=Literal(Decimal(4010), unit="USD_PER_TROY_OUNCE")),
                    direction=Direction.LONG,
                ),
            ),
        )
        all_version = _finalise_bare(conn, all_candidate, all_comp)
        rehydrated_all = SpecificationVersionRepository(conn).get(all_version.strategy_version_id)
        assert rehydrated_all.composition.primitive.value == "ALL"
        assert len(rehydrated_all.composition.components) == 2

        # ANY
        any_candidate = _new_candidate(conn)
        any_comp = AnyComposition(
            composition_id="any_rt", components=(
                simple_atomic_condition("any_close_above_rt", threshold="4000"),
                AtomicCondition(
                    condition_id="any_high_above_rt", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
                    expression=Comparison(operator=ComparisonOperator.GT, left=h1_high_reference("H1"), right=Literal(Decimal(4050), unit="USD_PER_TROY_OUNCE")),
                    direction=Direction.LONG,
                ),
            ),
        )
        any_version = _finalise_bare(conn, any_candidate, any_comp)
        rehydrated_any = SpecificationVersionRepository(conn).get(any_version.strategy_version_id)
        assert rehydrated_any.composition.primitive.value == "ANY"

        # SEQUENCE -- structurally distinct from ALL (has ordering_window_seconds/tie_semantics)
        seq_candidate = _new_candidate(conn)
        sequence = SequenceComposition(
            composition_id="seq_rt", components=(
                SequenceComponent(0, simple_atomic_condition("seq_breaks_above_rt", threshold="4000")),
                SequenceComponent(1, AtomicCondition(
                    condition_id="seq_retests_rt", semantic_role="CONFIRMATION", timeframe=Timeframe("H1"),
                    expression=Comparison(operator=ComparisonOperator.LTE, left=h1_close_reference(), right=Literal(Decimal(4005), unit="USD_PER_TROY_OUNCE")),
                    direction=Direction.LONG,
                )),
            ),
            ordering_window_seconds=4 * 3600, tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
        )
        seq_version = _finalise_bare(conn, seq_candidate, sequence)
        rehydrated_seq = SpecificationVersionRepository(conn).get(seq_version.strategy_version_id)
        assert rehydrated_seq.composition.primitive.value == "SEQUENCE"
        assert rehydrated_seq.composition.ordering_window_seconds == 4 * 3600
        assert rehydrated_seq.composition.tie_semantics == SequenceTieSemantics.TIES_PERMITTED

        # CONTEXT_TRIGGER (multi-timeframe, causal alignment via FRAMES expiry
        # naming the finest bound timeframe -- HELIOS archaeology finding #8)
        ct_candidate = _new_candidate(conn)
        context = AtomicCondition(
            condition_id="ct_h1_context_rt", semantic_role="CONTEXT", timeframe=Timeframe("H1"),
            expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("H1"), right=Literal(Decimal(3950), unit="USD_PER_TROY_OUNCE")),
            direction=Direction.LONG,
        )
        trigger = AtomicCondition(
            condition_id="ct_m5_trigger_rt", semantic_role="TRIGGER", timeframe=Timeframe("M5"),
            expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M5"), right=Literal(Decimal(3980), unit="USD_PER_TROY_OUNCE")),
            direction=Direction.LONG,
        )
        ct = ContextTriggerComposition(
            composition_id="ct_rt", context=context, trigger=trigger,
            context_validity=ExpirySpec(mode=ExpiryMode.FRAMES, frame_count=48, finest_bound_timeframe=Timeframe("M5")),
        )
        ct_version = _finalise_bare(conn, ct_candidate, ct)
        rehydrated_ct = SpecificationVersionRepository(conn).get(ct_version.strategy_version_id)
        assert rehydrated_ct.composition.primitive.value == "CONTEXT_TRIGGER"
        assert not hasattr(rehydrated_ct.composition, "sequence_index")
        assert rehydrated_ct.composition.context.timeframe.is_coarser_than(rehydrated_ct.composition.trigger.timeframe)
        assert rehydrated_ct.composition.context_validity.finest_bound_timeframe == Timeframe("M5")


# ============================================================================
# Facts round trip (item 19 "Facts") -- canonical HERMES fact, derived
# chain (EMA), and a DATA_BLOCKED future fact class (IV surface).
# ============================================================================


def test_facts_round_trip_canonical_derived_chain_and_data_blocked_future_class(pg_config):
    with connection(pg_config) as conn:
        # Canonical HERMES fact (already exercised throughout, re-asserted
        # explicitly here) + derived-fact chain (EMA over HERMES close).
        candidate_id = _new_candidate(conn)
        ema_50 = SpecificationDerivedFact(
            derived_fact_id="ema_50_h1_rt", input_facts=(h1_close_reference(),), algorithm_id="EMA", algorithm_version="v1",
            parameters=(("period", 50),), timeframe=Timeframe("H1"), warm_up_bars=50, output_unit="USD_PER_TROY_OUNCE",
            missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
        )
        condition = AtomicCondition(
            condition_id="close_crosses_above_ema50_rt", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
            expression=Comparison(operator=ComparisonOperator.CROSSES_ABOVE, left=h1_close_reference(), right=ema_50),
            direction=Direction.LONG,
        )
        version = _finalise_bare(conn, candidate_id, condition)
        rehydrated = SpecificationVersionRepository(conn).get(version.strategy_version_id)
        right_operand = rehydrated.composition.expression.right
        assert isinstance(right_operand, SpecificationDerivedFact)
        assert right_operand.algorithm_id == "EMA"
        assert right_operand.algorithm_version == "v1"
        assert isinstance(right_operand.input_facts[0], CanonicalFactReference)

        from darwin.specification.facts import FactReferenceKindError, require_canonical

        with pytest.raises(FactReferenceKindError):
            require_canonical(right_operand)  # never masquerades as canonical HERMES authority

        # DATA_BLOCKED future fact class: IMPLIED_VOLATILITY under
        # OPTIONS_AUTHORITY, not yet onboarded (fixture-11 equivalent),
        # round-tripped through the projection AND the full canonical
        # payload.
        blocked_candidate = _new_candidate(conn)
        iv_requirement = DataRequirement(
            requirement_id="xau_iv_surface_facts_rt", display_name="XAU_USD implied volatility surface",
            fact_class=FactClass.IMPLIED_VOLATILITY, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
            timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(3, HistoricalDepthUnit.YEARS),
            units="IV_PERCENT", required_fields=("strike", "expiry", "implied_volatility"),
            causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
        )
        iv_wall_fact = CanonicalFactReference(
            fact_key="OPTIONS.IMPLIED_VOLATILITY", fact_class=FactClass.IMPLIED_VOLATILITY,
            authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, unit="IV_PERCENT", timeframe=Timeframe("D1"),
            requirement_id="xau_iv_surface_facts_rt",
        )
        wall_exit = AtomicCondition(
            condition_id="iv_wall_context_facts_rt", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
            expression=Comparison(operator=ComparisonOperator.GT, left=iv_wall_fact, right=Literal(Decimal(0), unit="IV_PERCENT")),
            direction=Direction.BOTH,
        )
        trigger = simple_atomic_condition("price_approaches_iv_wall_facts_rt", threshold="4000")
        blocked_version = _finalise_bare(
            conn, blocked_candidate, trigger, exit_rules=(wall_exit,), extra_requirements=(iv_requirement,)
        )
        rehydrated_blocked = SpecificationVersionRepository(conn).get(blocked_version.strategy_version_id)
        iv_req = next(r for r in rehydrated_blocked.data_requirements if r.requirement_id == "xau_iv_surface_facts_rt")
        assert iv_req.fact_class == FactClass.IMPLIED_VOLATILITY
        assert iv_req.authority_class == DataAuthorityClass.OPTIONS_AUTHORITY


# ============================================================================
# All 14 controlled contract fixtures round-tripped through disposable
# PostgreSQL with EXACT semantic-fingerprint preservation (PID-004A
# persistence directive item 20). Mirrors
# tests/contract/test_specification_fixtures.py exactly -- clearly
# architecture-proof only, never presented as real discovered/proven
# evidence (PID-004 sec20/sec30).
# ============================================================================


def _fixture_versions() -> list[tuple[str, StrategyVersion, StrategyVersion]]:
    """Returns `(name, reference_version, db_version)` triples.
    `reference_version` finalises the fixture draft EXACTLY as
    tests/contract/test_specification_fixtures.py does (same plain-string
    draft/candidate/version ids) -- its `semantic_fingerprint` is the
    ground truth already proved there. `db_version` re-finalises the SAME
    draft object (never mutated by `finalise()`, so this is safe) after
    swapping `candidate_id` to a real UUID and using a real UUID
    `strategy_version_id`, ready to satisfy `strategy_versions`' UUID
    columns -- proving in the same breath that this swap never changes
    `semantic_fingerprint` (candidate_id/strategy_version_id are both
    excluded from it)."""
    from tests.contract import test_specification_fixtures as fx

    versions: list[tuple[str, StrategyVersion, StrategyVersion]] = []

    def _finalise(name: str, draft, **kwargs):
        reference = finalise(draft, strategy_version_id=f"persist-{name}", **kwargs)
        assert reference.outcome.status == ValidationOutcomeStatus.VALID, (name, reference.outcome.findings)
        draft.candidate_id = new_id()
        db = finalise(draft, strategy_version_id=new_id(), **kwargs)
        assert db.outcome.status == ValidationOutcomeStatus.VALID, (name, db.outcome.findings)
        assert db.strategy_version.semantic_fingerprint == reference.strategy_version.semantic_fingerprint
        versions.append((name, reference.strategy_version, db.strategy_version))

    _finalise("01", minimal_valid_draft())

    all_comp = AllComposition(
        composition_id="all_close_and_high_p", components=(
            simple_atomic_condition("close_above_4000_p", threshold="4000"),
            AtomicCondition(
                condition_id="high_above_4010_p", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
                expression=Comparison(operator=ComparisonOperator.GT, left=h1_high_reference("H1"), right=Literal(Decimal(4010), unit="USD_PER_TROY_OUNCE")),
                direction=Direction.LONG,
            ),
        ),
    )
    d02 = fx._with_provenance(fx._bare_draft("p02", all_comp))
    d02.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    _finalise("02", d02)

    any_comp = AnyComposition(
        composition_id="any_close_or_high_p", components=(
            simple_atomic_condition("close_above_4000_p2", threshold="4000"),
            AtomicCondition(
                condition_id="high_above_4050_p", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
                expression=Comparison(operator=ComparisonOperator.GT, left=h1_high_reference("H1"), right=Literal(Decimal(4050), unit="USD_PER_TROY_OUNCE")),
                direction=Direction.LONG,
            ),
        ),
    )
    d03 = fx._with_provenance(fx._bare_draft("p03", any_comp))
    d03.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    _finalise("03", d03)

    sequence = SequenceComposition(
        composition_id="seq_breakout_then_retest_p", components=(
            SequenceComponent(0, simple_atomic_condition("breaks_above_4000_p", threshold="4000")),
            SequenceComponent(1, AtomicCondition(
                condition_id="retests_4000_p", semantic_role="CONFIRMATION", timeframe=Timeframe("H1"),
                expression=Comparison(operator=ComparisonOperator.LTE, left=h1_close_reference(), right=Literal(Decimal(4005), unit="USD_PER_TROY_OUNCE")),
                direction=Direction.LONG,
            )),
        ),
        ordering_window_seconds=4 * 3600, tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
    )
    d04 = fx._with_provenance(fx._bare_draft("p04", sequence))
    d04.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    _finalise("04", d04)

    context = AtomicCondition(
        condition_id="h4_uptrend_context_p", semantic_role="CONTEXT", timeframe=Timeframe("H4"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("H4"), right=Literal(Decimal(3900), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    trigger = AtomicCondition(
        condition_id="m5_breakout_trigger_p", semantic_role="TRIGGER", timeframe=Timeframe("M5"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M5"), right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    ct = ContextTriggerComposition(
        composition_id="ct_gold_context_trigger_p", context=context, trigger=trigger,
        context_validity=ExpirySpec(mode=ExpiryMode.DURATION, duration_seconds=4 * 3600),
    )
    d05 = fx._with_provenance(fx._bare_draft("p05", ct))
    d05.set_data_requirement(hermes_ohlcv_requirement(timeframe="H4"))
    d05.set_data_requirement(hermes_ohlcv_requirement(timeframe="M5"))
    _finalise("05", d05)

    context6 = AtomicCondition(
        condition_id="h1_context_p", semantic_role="CONTEXT", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("H1"), right=Literal(Decimal(3950), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    trigger6 = AtomicCondition(
        condition_id="m5_trigger_p", semantic_role="TRIGGER", timeframe=Timeframe("M5"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M5"), right=Literal(Decimal(3980), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    ct6 = ContextTriggerComposition(
        composition_id="ct_multi_timeframe_p", context=context6, trigger=trigger6,
        context_validity=ExpirySpec(mode=ExpiryMode.FRAMES, frame_count=48, finest_bound_timeframe=Timeframe("M5")),
    )
    d06 = fx._with_provenance(fx._bare_draft("p06", ct6))
    d06.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    d06.set_data_requirement(hermes_ohlcv_requirement(timeframe="M5"))
    _finalise("06", d06)

    from darwin.specification.applicability import DstHandling, SessionSpec
    from darwin.specification.expressions import (
        BooleanExpression,
        BooleanOperator,
        SessionOperator,
        SessionPredicate,
    )

    condition7 = AtomicCondition(
        condition_id="ny_session_breakout_p", semantic_role="TRIGGER", timeframe=Timeframe("M15"),
        expression=BooleanExpression(
            operator=BooleanOperator.AND,
            operands=(
                Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M15"), right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
                SessionPredicate(operator=SessionOperator.IN_SESSION),
            ),
        ),
        direction=Direction.LONG,
    )
    d07 = fx._with_provenance(fx._bare_draft("p07", condition7))
    d07.set_data_requirement(hermes_ohlcv_requirement(timeframe="M15"))
    d07.session_spec = SessionSpec(
        iana_timezone="America/New_York", local_start="08:00", local_end="17:00",
        weekdays=(0, 1, 2, 3, 4), dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
    )
    _finalise("07", d07)

    wick_touch = AtomicCondition(
        condition_id="high_touches_4050_resistance_p", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.CROSSES_ABOVE, left=h1_high_reference("H1"), right=Literal(Decimal(4050), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.SHORT,
    )
    d08 = fx._with_provenance(fx._bare_draft("p08", wick_touch))
    d08.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    d08.intrabar_ambiguity_policy = IntrabarAmbiguityPolicy.CONSERVATIVE_SL_FIRST
    _finalise("08", d08)

    from darwin.specification.expressions import ParameterReference
    from darwin.specification.parameters import (
        NumericRangeDomain,
        ParameterDefinition,
        ParameterStatus,
        ParameterValueType,
    )

    condition9 = AtomicCondition(
        condition_id="close_above_tunable_threshold_p", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference(), right=ParameterReference(parameter_id="breakout_threshold")),
        direction=Direction.LONG,
    )
    d09 = fx._with_provenance(fx._bare_draft("p09", condition9))
    d09.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    d09.set_parameter(ParameterDefinition(
        parameter_id="breakout_threshold", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.DECIMAL,
        unit="USD_PER_TROY_OUNCE", domain=NumericRangeDomain(minimum=Decimal(3800), maximum=Decimal(4200)),
    ))
    d09.set_parameter(ParameterDefinition(
        parameter_id="trade_both_directions", status=ParameterStatus.FIXED, value_type=ParameterValueType.BOOLEAN, fixed_value=False,
    ))
    _finalise("09", d09)

    from darwin.specification.parameters import IntegerRangeDomain
    from darwin.specification.policy import (
        PolicyClass,
        PolicyCompatibility,
        PolicyCompatibilityDeclaration,
        PolicySearchAuthority,
    )

    d10 = minimal_valid_draft(draft_id="p10", candidate_id="candidate-p10")
    d10.set_policy_declaration(PolicyCompatibilityDeclaration(policy_class=PolicyClass.EXECUTION_POLICY, compatibility=PolicyCompatibility.DISABLED))
    d10.set_policy_declaration(PolicyCompatibilityDeclaration(
        policy_class=PolicyClass.DIKE_POLICY, compatibility=PolicyCompatibility.PERMITTED,
        authorized_search_envelope=(
            PolicySearchAuthority(dimension="max_leverage", parameter=ParameterDefinition(
                parameter_id="max_leverage", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.INTEGER,
                domain=IntegerRangeDomain(minimum=1, maximum=10),
            )),
        ),
    ))
    _finalise("10", d10)

    iv_requirement = DataRequirement(
        requirement_id="xau_iv_surface_p", display_name="XAU_USD implied volatility surface",
        fact_class=FactClass.IMPLIED_VOLATILITY, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(3, HistoricalDepthUnit.YEARS),
        units="IV_PERCENT", required_fields=("strike", "expiry", "implied_volatility"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )
    oi_requirement = DataRequirement(
        requirement_id="xau_open_interest_p", display_name="XAU_USD options open interest",
        fact_class=FactClass.OPEN_INTEREST, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(3, HistoricalDepthUnit.YEARS),
        units="CONTRACTS", required_fields=("strike", "expiry", "open_interest"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )
    iv_wall_fact = CanonicalFactReference(
        fact_key="OPTIONS.IMPLIED_VOLATILITY", fact_class=FactClass.IMPLIED_VOLATILITY,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, unit="IV_PERCENT", timeframe=Timeframe("D1"),
        requirement_id="xau_iv_surface_p",
    )
    wall_exit = AtomicCondition(
        condition_id="iv_wall_context_p", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=iv_wall_fact, right=Literal(Decimal(0), unit="IV_PERCENT")),
        direction=Direction.BOTH,
    )
    trigger11 = simple_atomic_condition("price_approaches_iv_wall_p", threshold="4000")
    d11 = fx._with_provenance(fx._bare_draft("p11", trigger11))
    d11.exit_rules = (wall_exit,)
    d11.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    d11.set_data_requirement(iv_requirement)
    d11.set_data_requirement(oi_requirement)
    d11.set_provenance(accepted_provenance("iv_wall_context_p"))
    _finalise("11", d11)
    # 12 (STRATEGY_NOT_SUFFICIENTLY_DEFINED) is deliberately excluded --
    # it never produces a StrategyVersion, so there is nothing to persist.

    cpi_requirement = DataRequirement(
        requirement_id="cpi_yoy_surprise_p", display_name="US CPI YoY surprise",
        fact_class=FactClass.ECONOMIC_SURPRISE, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.ARES_GOVERNED_CONTEXT, instrument_applicability=("XAU_USD",),
        timeframe=None, required_historical_depth=HistoricalDepthRequirement(10, HistoricalDepthUnit.YEARS),
        units=None, required_fields=("consensus", "actual", "surprise"),
        causal_timing_policy=CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY,
    )
    context13 = AtomicCondition(
        condition_id="cpi_beat_context_p", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
        expression=EventPredicate(fact_requirement_id="cpi_yoy_surprise_p"), direction=Direction.BOTH,
    )
    trigger13 = simple_atomic_condition("gold_reaction_trigger_p", threshold="4000")
    d13 = fx._with_provenance(fx._bare_draft("p13", trigger13))
    d13.exit_rules = (context13,)
    d13.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    d13.set_data_requirement(cpi_requirement)
    d13.set_provenance(accepted_provenance("cpi_beat_context_p"))
    _finalise("13", d13)

    ema_50 = SpecificationDerivedFact(
        derived_fact_id="ema_50_h1_p", input_facts=(h1_close_reference(),), algorithm_id="EMA", algorithm_version="v1",
        parameters=(("period", 50),), timeframe=Timeframe("H1"), warm_up_bars=50, output_unit="USD_PER_TROY_OUNCE",
        missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
    )
    condition14 = AtomicCondition(
        condition_id="close_crosses_above_ema50_p", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.CROSSES_ABOVE, left=h1_close_reference(), right=ema_50),
        direction=Direction.LONG,
    )
    d14 = fx._with_provenance(fx._bare_draft("p14", condition14))
    d14.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    _finalise("14", d14)

    return versions


def test_all_controlled_fixtures_round_trip_through_postgres_with_exact_semantic_fingerprints(pg_config):
    """PID-004A persistence directive item 20: fixture 12
    (STRATEGY_NOT_SUFFICIENTLY_DEFINED) never produces a StrategyVersion,
    so 13 of the 14 fixtures are persisted here -- the 14th is proven
    separately by `test_invalid_draft_persists_refusal_and_creates_no_strategy_version`
    above, which IS fixture-12's exact refusal shape."""
    with connection(pg_config) as conn:
        for name, reference_version, db_version in _fixture_versions():
            # `_fixture_versions()` already proved db_version.semantic_fingerprint
            # == reference_version.semantic_fingerprint (candidate_id/
            # strategy_version_id swap does not affect semantic identity).
            StrategyCandidateRepository(conn).create(
                StrategyCandidate(id=db_version.candidate_id, title=f"Fixture {name} persistence proof")
            )

            SpecificationVersionRepository(conn).create(db_version)
            DataRequirementProjectionRepository(conn).create_many(
                db_version.strategy_version_id, db_version.data_requirements
            )

            rehydrated = SpecificationVersionRepository(conn).get(db_version.strategy_version_id)
            assert rehydrated == db_version
            assert canonical_hash(rehydrated.semantic_payload()) == reference_version.semantic_fingerprint, name
            assert canonical_hash(rehydrated.artifact_payload()) == db_version.artifact_record_fingerprint, name


# ============================================================================
# Serialization schema/version governance (item 15) -- DB-adjacent proof
# that a document actually read back from Postgres round-trips; the pure,
# no-DB-required unknown-node/operator/schema-version rejection tests live
# in tests/unit/test_specification_serialization.py.
# ============================================================================


def test_full_payload_read_back_from_postgres_deserializes_exactly(pg_config):
    with connection(pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        _house_under_real_candidate(conn, draft, candidate_id=candidate_id)
        _persist_draft(conn, draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        row = SpecificationVersionRepository(conn).get_row(outcome.strategy_version.strategy_version_id)
        rehydrated = deserialize_strategy_version(row["full_payload"])
        assert rehydrated == outcome.strategy_version
