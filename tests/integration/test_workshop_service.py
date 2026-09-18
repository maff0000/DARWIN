"""PID-004B Strategy Workshop service/repository integration tests against
a real, disposable PostgreSQL (docs/pids/PID-004-SPECIFICATION-WORKSHOP.md
sec56). Mirrors tests/integration/test_specification_persistence.py's
style: direct calls into darwin.workshop.service (never through HTTP --
see tests/integration/test_workshop_api.py for the thin HTTP-wiring
proofs) against `pg_config`.
"""
from __future__ import annotations

import hashlib
import json

import psycopg
import pytest

from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.specification_repositories import (
    DataReadinessAssessmentRepository,
    StaleRevisionError,
)
from darwin.specification.applicability import (
    InstrumentApplicability,
    InstrumentApplicabilityKind,
)
from darwin.specification.provenance import RuleOrigin
from darwin.specification.readiness import PerRequirementAvailability, assess_readiness
from darwin.specification.serialization import serialize_specification_draft
from darwin.specification.validation import ValidationOutcomeStatus
from darwin.workshop import service
from darwin.workshop.domain import QuestionStatus, WorkshopStatus
from darwin.workshop.errors import (
    CrossWorkshopReferenceError,
    InvalidWorkshopReferenceError,
    WorkshopHasNoDraftError,
    WorkshopNotFoundError,
)
from tests.fixtures.specification_drafts import minimal_valid_draft
from tests.fixtures.workshops import (
    new_candidate,
    new_my_idea_discovery,
    new_user_discovered_discovery,
)

pytestmark = pytest.mark.integration


def _discovery_fingerprint(conn: psycopg.Connection, discovery_id: str) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM scout_discoveries WHERE id = %s", (discovery_id,))
        row = dict(cur.fetchone())
    return hashlib.sha256(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()


def _empty_draft_document(candidate_id: str, draft_id: str = "placeholder") -> dict:
    from darwin.specification.domain import SpecificationDraft

    draft = SpecificationDraft(draft_id=draft_id, candidate_id=candidate_id, schema_semantic_version="1.0.0")
    return serialize_specification_draft(draft)


# ============================================================================
# Idempotent open
# ============================================================================


def test_open_workshop_is_idempotent_per_active_candidate(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        first = service.open_workshop(conn, candidate_id=candidate_id)
        second = service.open_workshop(conn, candidate_id=candidate_id)
        assert first.workshop_id == second.workshop_id

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM strategy_workshops WHERE candidate_id = %s AND status = 'ACTIVE'",
                (candidate_id,),
            )
            assert cur.fetchone()["n"] == 1


def test_open_workshop_rejects_invalid_candidate_id(pg_config):
    with connection(pg_config) as conn, pytest.raises(InvalidWorkshopReferenceError):
        service.open_workshop(conn, candidate_id=new_id())


def test_open_workshop_rejects_invalid_discovery_id(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        with pytest.raises(InvalidWorkshopReferenceError):
            service.open_workshop(conn, candidate_id=candidate_id, discovery_ids=(new_id(),))
        # Refusing must not leave an orphaned workshop behind.
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM strategy_workshops WHERE candidate_id = %s", (candidate_id,))
            assert cur.fetchone()["n"] == 0


def test_open_workshop_links_a_real_discovery(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        discovery_id = new_user_discovered_discovery(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id, discovery_ids=(discovery_id,))
        assert workshop.discovery_ids == (discovery_id,)


def test_open_workshop_with_zero_discoveries_is_legitimate(pg_config):
    """PID-004B directive: a Workshop opened from a controlled fixture with
    no real Discovery is legitimate."""
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        assert workshop.discovery_ids == ()


def test_open_workshop_with_my_idea_discovery(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        discovery_id = new_my_idea_discovery(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id, discovery_ids=(discovery_id,))
        assert workshop.discovery_ids == (discovery_id,)


def test_a_new_active_workshop_may_be_opened_after_the_previous_one_is_finalised(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        first = service.open_workshop(conn, candidate_id=candidate_id)
        service.update_draft(
            conn, first.workshop_id, expected_revision=0,
            draft_document=serialize_specification_draft(minimal_valid_draft(candidate_id=candidate_id)),
        )
        outcome = service.finalise_workshop(conn, first.workshop_id, expected_revision=1)
        assert outcome.strategy_version is not None

        second = service.open_workshop(conn, candidate_id=candidate_id)
    assert second.workshop_id != first.workshop_id
    assert second.status == WorkshopStatus.ACTIVE


# ============================================================================
# SCOUT / Discovery fidelity -- discovery row is byte-identical before/after
# every Workshop operation.
# ============================================================================


def test_scout_discovery_row_is_byte_identical_before_and_after_every_workshop_operation(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        discovery_id = new_user_discovered_discovery(conn, source_symbol="XAUUSD")
        before = _discovery_fingerprint(conn, discovery_id)

        workshop = service.open_workshop(conn, candidate_id=candidate_id, discovery_ids=(discovery_id,))
        assert _discovery_fingerprint(conn, discovery_id) == before

        question = service.create_question(
            conn, workshop.workshop_id, semantic_subject="composition", question_text="what triggers entry?",
        )
        assert _discovery_fingerprint(conn, discovery_id) == before

        decision = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"note": "use H1 close"},
            origin=RuleOrigin.USER_CLARIFICATION, actor="matt", related_question_id=question.question_id,
        )
        assert _discovery_fingerprint(conn, discovery_id) == before

        service.resolve_question(
            conn, workshop.workshop_id, question.question_id, resolution=QuestionStatus.RESOLVED,
            accepted_decision_id=decision.decision_id,
        )
        assert _discovery_fingerprint(conn, discovery_id) == before

        service.accept_decision(conn, workshop.workshop_id, decision.decision_id)
        assert _discovery_fingerprint(conn, discovery_id) == before

        service.supersede_decision(
            conn, workshop.workshop_id, decision.decision_id, proposed_value={"note": "use H4 close instead"},
            actor="matt",
        )
        assert _discovery_fingerprint(conn, discovery_id) == before

        _draft, revision = service.update_draft(
            conn, workshop.workshop_id, expected_revision=0,
            draft_document=serialize_specification_draft(minimal_valid_draft(candidate_id=candidate_id)),
        )
        assert _discovery_fingerprint(conn, discovery_id) == before

        service.validate_workshop_draft(conn, workshop.workshop_id)
        assert _discovery_fingerprint(conn, discovery_id) == before

        outcome = service.finalise_workshop(conn, workshop.workshop_id, expected_revision=revision)
        assert outcome.strategy_version is not None
        assert _discovery_fingerprint(conn, discovery_id) == before


# ============================================================================
# Questions
# ============================================================================


def test_question_create_list_resolve(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        question = service.create_question(
            conn, workshop.workshop_id, semantic_subject="exit", question_text="what closes the trade?",
            rationale="source text is ambiguous",
        )
        listed = service.list_questions(conn, workshop.workshop_id)
        assert [q.question_id for q in listed] == [question.question_id]
        assert listed[0].status == QuestionStatus.OPEN

        resolved = service.resolve_question(
            conn, workshop.workshop_id, question.question_id, resolution=QuestionStatus.WITHDRAWN,
        )
        assert resolved.status == QuestionStatus.WITHDRAWN
        assert resolved.resolved_at_utc is not None


def test_resolve_question_rejects_cross_workshop_accepted_decision_id(pg_config):
    with connection(pg_config) as conn:
        candidate_a = new_candidate(conn)
        candidate_b = new_candidate(conn)
        workshop_a = service.open_workshop(conn, candidate_id=candidate_a)
        workshop_b = service.open_workshop(conn, candidate_id=candidate_b)
        question_a = service.create_question(
            conn, workshop_a.workshop_id, semantic_subject="x", question_text="y?"
        )
        decision_b = service.create_decision(
            conn, workshop_b.workshop_id, proposed_value={"x": 1}, origin=RuleOrigin.WORKSHOP_PROPOSAL,
            actor="matt",
        )
        with pytest.raises(CrossWorkshopReferenceError):
            service.resolve_question(
                conn, workshop_a.workshop_id, question_a.question_id, resolution=QuestionStatus.RESOLVED,
                accepted_decision_id=decision_b.decision_id,
            )


def test_resolve_question_rejects_a_question_id_belonging_to_another_workshop(pg_config):
    with connection(pg_config) as conn:
        candidate_a = new_candidate(conn)
        candidate_b = new_candidate(conn)
        workshop_a = service.open_workshop(conn, candidate_id=candidate_a)
        workshop_b = service.open_workshop(conn, candidate_id=candidate_b)
        question_b = service.create_question(
            conn, workshop_b.workshop_id, semantic_subject="x", question_text="y?"
        )
        with pytest.raises(CrossWorkshopReferenceError):
            service.resolve_question(
                conn, workshop_a.workshop_id, question_b.question_id, resolution=QuestionStatus.RESOLVED,
            )


# ============================================================================
# Decisions
# ============================================================================


def test_decision_create_accept_reject(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)

        accepted = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"a": 1}, origin=RuleOrigin.SOURCE_RULE, actor="matt",
        )
        accepted = service.accept_decision(conn, workshop.workshop_id, accepted.decision_id)
        assert accepted.acceptance_state.value == "ACCEPTED"

        rejected = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"b": 2}, origin=RuleOrigin.WORKSHOP_PROPOSAL,
            actor="matt",
        )
        rejected = service.reject_decision(conn, workshop.workshop_id, rejected.decision_id, rationale="no")
        assert rejected.acceptance_state.value == "REJECTED"

        listed = {d.decision_id: d for d in service.list_decisions(conn, workshop.workshop_id)}
        assert listed[accepted.decision_id].acceptance_state.value == "ACCEPTED"
        assert listed[rejected.decision_id].acceptance_state.value == "REJECTED"


def test_decision_supersede_preserves_history(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        original = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"threshold": 4000}, origin=RuleOrigin.SOURCE_RULE,
            actor="matt",
        )
        replacement = service.supersede_decision(
            conn, workshop.workshop_id, original.decision_id, proposed_value={"threshold": 4200},
            actor="matt", rationale="source re-read more carefully",
        )
        all_decisions = {d.decision_id: d for d in service.list_decisions(conn, workshop.workshop_id)}
        old = all_decisions[original.decision_id]
        assert old.acceptance_state.value == "SUPERSEDED"
        assert old.superseded_by_decision_id == replacement.decision_id
        assert old.proposed_value == {"threshold": 4000}  # never rewritten
        new = all_decisions[replacement.decision_id]
        assert new.proposed_value == {"threshold": 4200}
        assert new.origin == original.origin  # origin travels forward unchanged


def test_workshop_decision_content_immutable_trigger_rejects_direct_update(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        decision = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"a": 1}, origin=RuleOrigin.SOURCE_RULE, actor="matt",
        )
    with connection(pg_config) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE workshop_decisions SET proposed_value = %s WHERE id = %s",
                    (json.dumps({"a": 999}), decision.decision_id),
                )
        except psycopg.errors.RaiseException:
            conn.rollback()
        else:
            conn.rollback()
            pytest.fail("expected RaiseException from trg_workshop_decisions_content_immutable")


def test_workshop_decision_content_immutable_trigger_rejects_delete(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        decision = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"a": 1}, origin=RuleOrigin.SOURCE_RULE, actor="matt",
        )
    with connection(pg_config) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM workshop_decisions WHERE id = %s", (decision.decision_id,))
        except psycopg.errors.RaiseException:
            conn.rollback()
        else:
            conn.rollback()
            pytest.fail("expected RaiseException from trg_workshop_decisions_content_immutable")


def test_workshop_decision_acceptance_state_update_is_permitted_by_the_trigger(pg_config):
    """The trigger permits acceptance_state/superseded_by_decision_id
    updates -- proved directly at the raw-SQL layer, not only through
    service.accept_decision."""
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        decision = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"a": 1}, origin=RuleOrigin.SOURCE_RULE, actor="matt",
        )
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE workshop_decisions SET acceptance_state = 'ACCEPTED' WHERE id = %s",
                (decision.decision_id,),
            )
            affected = cur.rowcount
        assert affected == 1


def test_create_decision_rejects_related_question_from_another_workshop(pg_config):
    with connection(pg_config) as conn:
        candidate_a = new_candidate(conn)
        candidate_b = new_candidate(conn)
        workshop_a = service.open_workshop(conn, candidate_id=candidate_a)
        workshop_b = service.open_workshop(conn, candidate_id=candidate_b)
        question_b = service.create_question(
            conn, workshop_b.workshop_id, semantic_subject="x", question_text="y?"
        )
        with pytest.raises(CrossWorkshopReferenceError):
            service.create_decision(
                conn, workshop_a.workshop_id, proposed_value={"x": 1}, origin=RuleOrigin.WORKSHOP_PROPOSAL,
                actor="matt", related_question_id=question_b.question_id,
            )


def test_accept_decision_rejects_a_decision_id_belonging_to_another_workshop(pg_config):
    with connection(pg_config) as conn:
        candidate_a = new_candidate(conn)
        candidate_b = new_candidate(conn)
        workshop_a = service.open_workshop(conn, candidate_id=candidate_a)
        workshop_b = service.open_workshop(conn, candidate_id=candidate_b)
        decision_b = service.create_decision(
            conn, workshop_b.workshop_id, proposed_value={"x": 1}, origin=RuleOrigin.WORKSHOP_PROPOSAL,
            actor="matt",
        )
        with pytest.raises(CrossWorkshopReferenceError):
            service.accept_decision(conn, workshop_a.workshop_id, decision_b.decision_id)


# ============================================================================
# Draft authoring
# ============================================================================


def test_draft_create_then_update_with_expected_revision(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        draft, revision = service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=_empty_draft_document(candidate_id),
        )
        assert revision == 1
        assert draft.candidate_id == candidate_id

        edited = minimal_valid_draft(candidate_id=candidate_id)
        draft2, revision2 = service.update_draft(
            conn, workshop.workshop_id, expected_revision=1,
            draft_document=serialize_specification_draft(edited),
        )
        assert revision2 == 2
        assert draft2.composition is not None


def test_draft_update_with_stale_revision_is_rejected_explicitly(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=_empty_draft_document(candidate_id),
        )
        with pytest.raises(StaleRevisionError):
            service.update_draft(
                conn, workshop.workshop_id, expected_revision=0,
                draft_document=_empty_draft_document(candidate_id),
            )


def test_draft_update_never_trusts_caller_supplied_candidate_or_draft_id(pg_config):
    """A caller cannot point one Workshop's draft edit at another
    candidate/draft by putting a different id inside the document body --
    the service always forces draft_id/candidate_id to the Workshop's own
    identity before deserializing."""
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        other_candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        document = _empty_draft_document(other_candidate_id, draft_id="attacker-supplied-id")
        draft, _ = service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=document,
        )
        assert draft.candidate_id == candidate_id
        assert draft.draft_id != "attacker-supplied-id"


def test_get_draft_before_any_draft_exists_returns_none(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        draft, revision = service.get_draft(conn, workshop.workshop_id)
        assert draft is None
        assert revision is None


def test_validate_before_any_draft_exists_raises_explicitly(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        with pytest.raises(WorkshopHasNoDraftError):
            service.validate_workshop_draft(conn, workshop.workshop_id)


# ============================================================================
# Validation / finalisation
# ============================================================================


def test_validate_calls_the_real_validator_and_reports_incomplete_draft(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=_empty_draft_document(candidate_id),
        )
        outcome = service.validate_workshop_draft(conn, workshop.workshop_id)
        assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
        codes = {f.code for f in outcome.findings}
        assert "MISSING_INSTRUMENT_APPLICABILITY" in codes
        assert "MISSING_COMPOSITION" in codes


def test_finalise_is_refused_for_an_incomplete_draft(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=_empty_draft_document(candidate_id),
        )
        outcome = service.finalise_workshop(conn, workshop.workshop_id, expected_revision=1)
        assert outcome.strategy_version is None
        assert outcome.outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
        workshop_after = service.get_workshop(conn, workshop.workshop_id)
        assert workshop_after.status == WorkshopStatus.ACTIVE  # never advanced


def test_finalise_succeeds_for_a_valid_draft_and_advances_the_workshop(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        _draft, revision = service.update_draft(
            conn, workshop.workshop_id, expected_revision=0,
            draft_document=serialize_specification_draft(minimal_valid_draft(candidate_id=candidate_id)),
        )
        outcome = service.finalise_workshop(conn, workshop.workshop_id, expected_revision=revision)
        assert outcome.strategy_version is not None
        assert outcome.candidate_advanced is True

        workshop_after = service.get_workshop(conn, workshop.workshop_id)
        assert workshop_after.status == WorkshopStatus.FINALISED
        assert workshop_after.finalised_strategy_version_id == outcome.strategy_version.strategy_version_id

        with conn.cursor() as cur:
            cur.execute("SELECT pipeline_stage FROM strategy_candidates WHERE id = %s", (candidate_id,))
            assert cur.fetchone()["pipeline_stage"] == "SPECIFIED"


def test_a_data_blocked_strategy_may_still_finalise(pg_config):
    """PID-004 sec34/sec54: finalisation is gated on semantic VALIDITY
    only -- a strategy that is semantically complete but DATA_BLOCKED
    finalises exactly the same way. Readiness is assessed AFTER
    finalisation, separately, and never blocks it."""
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        draft = minimal_valid_draft(candidate_id=candidate_id)
        _, revision = service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=serialize_specification_draft(draft),
        )
        outcome = service.finalise_workshop(conn, workshop.workshop_id, expected_revision=revision)
        version = outcome.strategy_version
        assert version is not None

        requirement_id = next(iter(draft.data_requirements))
        assessment = assess_readiness(
            assessment_id=new_id(), strategy_version_id=version.strategy_version_id,
            mandatory_requirement_ids={requirement_id},
            per_requirement={requirement_id: (PerRequirementAvailability.UNAVAILABLE, "HERMES gap")},
            assessed_at_utc=version.finalised_at_utc,
        )
        assert assessment.overall_state.value == "DATA_BLOCKED"
        DataReadinessAssessmentRepository(conn).create(assessment)

        workshop_after = service.get_workshop(conn, workshop.workshop_id)
        assert workshop_after.status == WorkshopStatus.FINALISED
        assert workshop_after.finalised_strategy_version_id == version.strategy_version_id


def test_finalise_is_idempotent_on_retry(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        _draft, revision = service.update_draft(
            conn, workshop.workshop_id, expected_revision=0,
            draft_document=serialize_specification_draft(minimal_valid_draft(candidate_id=candidate_id)),
        )
        first = service.finalise_workshop(conn, workshop.workshop_id, expected_revision=revision)
        second = service.finalise_workshop(conn, workshop.workshop_id, expected_revision=revision)
        assert first.strategy_version.strategy_version_id == second.strategy_version.strategy_version_id

        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM strategy_versions WHERE candidate_id = %s", (candidate_id,)
            )
            assert cur.fetchone()["n"] == 1


def test_finalising_one_workshop_never_affects_another_workshop(pg_config):
    with connection(pg_config) as conn:
        candidate_a = new_candidate(conn)
        candidate_b = new_candidate(conn)
        workshop_a = service.open_workshop(conn, candidate_id=candidate_a)
        workshop_b = service.open_workshop(conn, candidate_id=candidate_b)
        _, revision_a = service.update_draft(
            conn, workshop_a.workshop_id, expected_revision=0,
            draft_document=serialize_specification_draft(minimal_valid_draft(candidate_id=candidate_a)),
        )
        service.finalise_workshop(conn, workshop_a.workshop_id, expected_revision=revision_a)

        workshop_b_after = service.get_workshop(conn, workshop_b.workshop_id)
        assert workshop_b_after.status == WorkshopStatus.ACTIVE
        assert workshop_b_after.finalised_strategy_version_id is None


# ============================================================================
# Instrument-mapping rule -- no automatic ticker inference (PID-004B)
# ============================================================================


def test_no_automatic_instrument_inference_from_raw_source_symbol(pg_config):
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        discovery_id = new_user_discovered_discovery(conn, source_symbol="XAUUSD")
        before = _discovery_fingerprint(conn, discovery_id)
        workshop = service.open_workshop(conn, candidate_id=candidate_id, discovery_ids=(discovery_id,))

        empty_document = _empty_draft_document(candidate_id)
        draft, revision = service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=empty_document,
        )
        assert draft.instrument_applicability is None  # never auto-inferred from "XAUUSD"

        outcome = service.validate_workshop_draft(conn, workshop.workshop_id)
        codes = {f.code for f in outcome.findings}
        assert "MISSING_INSTRUMENT_APPLICABILITY" in codes
        assert "MISSING_COMPOSITION" in codes

        # An explicit user clarification is recorded distinctly (never a
        # SCOUT-row rewrite) -- but recording/accepting the decision alone
        # does not itself mutate the draft; that still requires the
        # explicit draft-authoring call below (never MENDEL/Workshop
        # writing the canonical draft directly).
        decision = service.create_decision(
            conn, workshop.workshop_id,
            proposed_value={"instrument_applicability": {"kind": "EXPLICIT_SINGLE", "instrument_ids": ["XAU_USD"]}},
            origin=RuleOrigin.USER_CLARIFICATION, actor="matt",
            rationale="Matt confirmed XAUUSD means canonical XAU_USD",
        )
        service.accept_decision(conn, workshop.workshop_id, decision.decision_id)
        assert _discovery_fingerprint(conn, discovery_id) == before  # still untouched

        draft.instrument_applicability = InstrumentApplicability(
            kind=InstrumentApplicabilityKind.EXPLICIT_SINGLE, instrument_ids=("XAU_USD",)
        )
        draft2, _revision2 = service.update_draft(
            conn, workshop.workshop_id, expected_revision=revision,
            draft_document=serialize_specification_draft(draft),
        )
        assert draft2.instrument_applicability.instrument_ids == ("XAU_USD",)
        assert _discovery_fingerprint(conn, discovery_id) == before  # STILL untouched

        outcome2 = service.validate_workshop_draft(conn, workshop.workshop_id)
        codes2 = {f.code for f in outcome2.findings}
        assert "MISSING_INSTRUMENT_APPLICABILITY" not in codes2  # resolved
        assert "MISSING_COMPOSITION" in codes2  # composition was never touched


# ============================================================================
# Deleted workspace directory does not lose canonical state
# ============================================================================


def test_deleted_workspace_directory_does_not_lose_canonical_state(pg_config, tmp_path, monkeypatch):
    monkeypatch.setenv("DARWIN_WORKSPACES_ROOT", str(tmp_path))
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        workshop = service.open_workshop(conn, candidate_id=candidate_id)
        service.create_question(conn, workshop.workshop_id, semantic_subject="x", question_text="y?")
        service.update_draft(
            conn, workshop.workshop_id, expected_revision=0, draft_document=_empty_draft_document(candidate_id),
        )

        from darwin.workshop import workspace as workspace_module

        assert workspace_module.workspace_exists(workshop.workshop_id)
        workspace_module.delete_workspace(workshop.workshop_id)
        assert not workspace_module.workspace_exists(workshop.workshop_id)

        # The database alone must still answer "what is this Workshop's
        # current state" completely and correctly.
        reloaded = service.get_workshop(conn, workshop.workshop_id)
        assert reloaded.candidate_id == candidate_id
        assert reloaded.current_draft_id is not None
        questions = service.list_questions(conn, workshop.workshop_id)
        assert len(questions) == 1
        draft, revision = service.get_draft(conn, workshop.workshop_id)
        assert draft is not None
        assert revision == 1

        # A further mutating operation transparently regenerates the
        # workspace from canonical state.
        service.create_question(conn, workshop.workshop_id, semantic_subject="z", question_text="w?")
        assert workspace_module.workspace_exists(workshop.workshop_id)


def test_get_workshop_raises_not_found_for_unknown_id(pg_config):
    with connection(pg_config) as conn, pytest.raises(WorkshopNotFoundError):
        service.get_workshop(conn, new_id())
