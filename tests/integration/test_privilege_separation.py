"""PID-004A adversarial-audit fix #2 (database privilege separation)
integration tests -- against a real, disposable PostgreSQL that has
already been taken through the role-separation upgrade
(`darwin/research_store/bootstrap/03_upgrade_existing_volume_to_role_
separation.sql`, sourcing `02_grant_app_table_privileges.sql`) or the
fresh-bootstrap path (`01_fresh_bootstrap_roles.sql` +
`02_grant_app_table_privileges.sql`).

Deliberately NOT using the shared `pg_config` fixture from
tests/integration/conftest.py -- that fixture's underlying role is shared
by every OTHER integration test file in this session and must stay a
straightforward superuser-equivalent test role throughout (changing its
privileges mid-session would make test order load-bearing for unrelated
files, which is exactly the kind of fragile coupling this suite avoids
elsewhere). This file's Postgres role state is provisioned entirely
externally (a separate disposable postgres:16-alpine container, taken
through the upgrade SQL) and handed in via its own env vars:

  DARWIN_PRIVSEP_APP_DSN       -- the RESTRICTED darwin_app role, post-upgrade.
  DARWIN_PRIVSEP_MIGRATOR_DSN  -- the darwin_migrator role (optional -- only
                                  the "governed migrations still work"
                                  test needs it; skipped on its own if unset).

Both connection strings point at a database that already has migrations
0001-0007 applied and the 3-role model in place -- this file only proves
the PRIVILEGE BOUNDARY, not the upgrade procedure itself (see this
session's verification notes / the agent's final report for the
existing-volume-upgrade proof, which additionally seeds and checks
representative data survival).
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest

import darwin.research_store as _research_store
from darwin.core.config import PostgresConfig
from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.migrations import migration_state, run_migrations
from darwin.research_store.models import StrategyCandidate
from darwin.research_store.repositories import StrategyCandidateRepository
from darwin.research_store.specification_finalisation import (
    finalise_specification_draft,
)
from darwin.research_store.specification_repositories import (
    DataRequirementProjectionRepository,
    SpecificationDraftRepository,
    SpecificationVersionRepository,
    ValidationRecordRepository,
)
from darwin.specification.provenance import RuleOrigin
from darwin.workshop.domain import QuestionStatus
from tests.fixtures.specification_drafts import minimal_valid_draft

pytestmark = pytest.mark.integration

MIGRATIONS_DIR = Path(_research_store.__file__).resolve().parent / "migrations_sql"


def _config_from_dsn(dsn: str, *, default_user: str) -> PostgresConfig:
    parsed = urlparse(dsn)
    return PostgresConfig(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database=(parsed.path or "/darwin").lstrip("/"),
        user=parsed.username or default_user,
        password=parsed.password or "",
    )


@pytest.fixture(scope="session")
def app_pg_config() -> PostgresConfig:
    dsn = os.environ.get("DARWIN_PRIVSEP_APP_DSN")
    if not dsn:
        pytest.skip(
            "DARWIN_PRIVSEP_APP_DSN not set -- privilege-boundary tests require a disposable "
            "PostgreSQL already taken through the role-separation upgrade (see "
            "darwin/research_store/bootstrap/)"
        )
    return _config_from_dsn(dsn, default_user="darwin_app")


@pytest.fixture(scope="session")
def migrator_pg_config() -> PostgresConfig | None:
    dsn = os.environ.get("DARWIN_PRIVSEP_MIGRATOR_DSN")
    if not dsn:
        return None
    return _config_from_dsn(dsn, default_user="darwin_migrator")


def _new_candidate(conn, *, title: str = "Privilege-separation test candidate") -> str:
    candidate_id = new_id()
    StrategyCandidateRepository(conn).create(StrategyCandidate(id=candidate_id, title=title))
    return candidate_id


def _assert_denied(message: str) -> None:
    """Postgres phrases InsufficientPrivilege two ways depending on the
    operation: a plain GRANT-based denial says "permission denied for
    table X", while an owner-only DDL operation (DISABLE TRIGGER, DROP
    TABLE, ADD COLUMN, ...) says "must be owner of table X" instead --
    darwin_app owns nothing, so both phrasings are equally valid proof
    that the operation was refused for lack of privilege."""
    lowered = message.lower()
    assert "permission denied" in lowered or "must be owner" in lowered, message


def _expect_rejected(conn, exc_type, sql: str, params: tuple = ()) -> str:
    """Runs `sql` expecting it to fail with `exc_type`; rolls back
    afterwards either way (a failed statement aborts the transaction) and
    returns the stringified error for the caller to assert message
    content on."""
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    except exc_type as exc:
        message = str(exc)
        conn.rollback()
        return message
    else:
        conn.rollback()
        pytest.fail(f"expected {exc_type.__name__}, nothing was raised")


# ============================================================================
# Must succeed through the restricted darwin_app role -- the main proof
# that privilege separation has not broken ordinary application operation.
# The full existing persistence integration suite is additionally run
# against this exact role as a separate verification pass (see the
# session's final report) -- this test is a self-contained, in-repo smoke
# proof of the same claim for the primary finalisation path.
# ============================================================================


def test_ordinary_finalisation_flow_succeeds_end_to_end_through_the_restricted_app_role(app_pg_config):
    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)

        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        assert outcome.strategy_version is not None
        assert outcome.candidate_advanced is True

        version_row = SpecificationVersionRepository(conn).get_row(outcome.strategy_version.strategy_version_id)
        assert version_row is not None
        requirement_rows = DataRequirementProjectionRepository(conn).list_for_strategy_version(
            outcome.strategy_version.strategy_version_id
        )
        assert len(requirement_rows) == len(outcome.strategy_version.data_requirements)

        validation_rows = ValidationRecordRepository(conn).list_for_draft(draft.draft_id)
        assert len(validation_rows) == 1
        assert validation_rows[0]["status"] == "VALID"

        with conn.cursor() as cur:
            cur.execute("SELECT pipeline_stage FROM strategy_candidates WHERE id = %s", (candidate_id,))
            assert cur.fetchone()["pipeline_stage"] == "SPECIFIED"


def test_migration_state_readonly_diagnostic_works_through_the_restricted_app_role(app_pg_config):
    """Adversarial-audit fix #2 item 9's direct proof: the read-only
    migration-state diagnostic (exactly what darwin_core's own
    /api/v1/migrations and /api/v1/ready endpoints call, using the
    ordinary application connection) must work correctly under a role
    that has ONLY been granted SELECT on schema_migrations -- it must
    never attempt to CREATE TABLE schema_migrations itself."""
    state = migration_state(app_pg_config, MIGRATIONS_DIR)
    assert state["initialised"] is True
    assert state["up_to_date"] is True
    assert "0007_finalisation_idempotency" in state["applied"]


def test_run_migrations_is_a_safe_no_op_through_the_restricted_app_role_when_nothing_is_pending(app_pg_config):
    """`run_migrations` itself must not require DDL privilege when there
    is genuinely nothing to apply -- it should never even attempt `CREATE
    TABLE schema_migrations` once that table already exists (see
    `darwin.research_store.migrations._ensure_schema_migrations_table`).
    This is what lets a test/diagnostic harness call `run_migrations`
    defensively without needing migrator/owner authority, while a
    genuinely NEW pending migration still requires it (proved separately
    below via `migrator_pg_config`)."""
    applied = run_migrations(app_pg_config, MIGRATIONS_DIR)
    assert applied == []


def test_governed_migrations_still_run_through_darwin_migrator(migrator_pg_config):
    if migrator_pg_config is None:
        pytest.skip("DARWIN_PRIVSEP_MIGRATOR_DSN not set")
    applied = run_migrations(migrator_pg_config, MIGRATIONS_DIR)
    assert applied == []  # already up to date -- this proves connectivity + authority, not re-application
    state = migration_state(migrator_pg_config, MIGRATIONS_DIR)
    assert state["up_to_date"] is True


# ============================================================================
# Must FAIL through the restricted darwin_app role.
# ============================================================================


def test_truncate_strategy_versions_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(conn, psycopg.errors.InsufficientPrivilege, "TRUNCATE strategy_versions")
    _assert_denied(message)


def test_truncate_strategy_versions_cascade_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege, "TRUNCATE strategy_versions CASCADE"
        )
    _assert_denied(message)


def test_disable_trigger_on_strategy_versions_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege, "ALTER TABLE strategy_versions DISABLE TRIGGER ALL"
        )
    _assert_denied(message)


def test_drop_table_strategy_versions_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(conn, psycopg.errors.InsufficientPrivilege, "DROP TABLE strategy_versions")
    _assert_denied(message)


def test_add_column_to_strategy_versions_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege,
            "ALTER TABLE strategy_versions ADD COLUMN whatever TEXT",
        )
    _assert_denied(message)


def test_create_table_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege, "CREATE TABLE whatever (id UUID PRIMARY KEY)"
        )
    _assert_denied(message)


def test_set_role_darwin_owner_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(conn, psycopg.errors.InsufficientPrivilege, "SET ROLE darwin_owner")
    _assert_denied(message)


def test_set_role_darwin_migrator_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(conn, psycopg.errors.InsufficientPrivilege, "SET ROLE darwin_migrator")
    _assert_denied(message)


def test_direct_update_against_a_finalised_strategy_version_fails_through_the_restricted_role(app_pg_config):
    """Must fail for TWO independent reasons now: the immutability
    trigger (migration 0006) AND lack of UPDATE privilege (this fix) --
    this test only asserts that it fails, not which reason fired first
    (Postgres checks privilege before executing the statement, so in
    practice InsufficientPrivilege fires; either failure mode is a pass
    for this test)."""
    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        version_id = outcome.strategy_version.strategy_version_id

    with connection(app_pg_config) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE strategy_versions SET title = 'HACKED' WHERE id = %s", (version_id,))
        except (psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException) as exc:
            conn.rollback()
            message = str(exc).lower()
            assert "permission denied" in message or "immutable" in message
        else:
            conn.rollback()
            pytest.fail("expected UPDATE against a finalised strategy_versions row to fail")

    with connection(app_pg_config) as conn:
        row = SpecificationVersionRepository(conn).get_row(version_id)
        assert row["title"] != "HACKED"


def test_delete_against_a_finalised_strategy_version_fails_through_the_restricted_role(app_pg_config):
    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        version_id = outcome.strategy_version.strategy_version_id

    with connection(app_pg_config) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM strategy_versions WHERE id = %s", (version_id,))
        except (psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException) as exc:
            conn.rollback()
            message = str(exc).lower()
            assert "permission denied" in message or "immutable" in message
        else:
            conn.rollback()
            pytest.fail("expected DELETE against a finalised strategy_versions row to fail")

    with connection(app_pg_config) as conn:
        assert SpecificationVersionRepository(conn).get_row(version_id) is not None


def _new_workshop(conn, candidate_id: str) -> str:
    from darwin.workshop import service as workshop_service

    return workshop_service.open_workshop(conn, candidate_id=candidate_id).workshop_id


# ============================================================================
# PID-004B Strategy Workshop (migration 0009) -- same restricted-role proof
# extended to the new tables.
# ============================================================================


def test_workshop_ordinary_lifecycle_succeeds_through_the_restricted_app_role(app_pg_config):
    from darwin.specification.serialization import serialize_specification_draft
    from darwin.workshop import service as workshop_service
    from tests.fixtures.specification_drafts import minimal_valid_draft

    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        workshop_id = _new_workshop(conn, candidate_id)
        question = workshop_service.create_question(
            conn, workshop_id, semantic_subject="x", question_text="y?"
        )
        decision = workshop_service.create_decision(
            conn, workshop_id, proposed_value={"a": 1}, origin=RuleOrigin.SOURCE_RULE, actor="matt",
        )
        workshop_service.accept_decision(conn, workshop_id, decision.decision_id)
        workshop_service.resolve_question(
            conn, workshop_id, question.question_id, resolution=QuestionStatus.RESOLVED,
            accepted_decision_id=decision.decision_id,
        )
        _draft, revision = workshop_service.update_draft(
            conn, workshop_id, expected_revision=0,
            draft_document=serialize_specification_draft(minimal_valid_draft(candidate_id=candidate_id)),
        )
        outcome = workshop_service.finalise_workshop(conn, workshop_id, expected_revision=revision)
        assert outcome.strategy_version is not None
        workshop_after = workshop_service.get_workshop(conn, workshop_id)
        assert workshop_after.status.value == "FINALISED"


def test_truncate_workshop_decisions_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        message = _expect_rejected(conn, psycopg.errors.InsufficientPrivilege, "TRUNCATE workshop_decisions")
    _assert_denied(message)


def test_delete_workshop_decisions_row_is_refused_for_two_independent_reasons(app_pg_config):
    """No DELETE privilege at all (this fix) AND migration 0009's own
    trg_workshop_decisions_content_immutable trigger both refuse a DELETE
    -- this test only asserts that it fails, either failure mode is a
    pass (Postgres checks privilege first in practice)."""
    from darwin.workshop import service as workshop_service

    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        workshop_id = _new_workshop(conn, candidate_id)
        decision = workshop_service.create_decision(
            conn, workshop_id, proposed_value={"a": 1}, origin=RuleOrigin.SOURCE_RULE, actor="matt",
        )

    with connection(app_pg_config) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM workshop_decisions WHERE id = %s", (decision.decision_id,))
        except (psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException) as exc:
            conn.rollback()
            message = str(exc).lower()
            assert "permission denied" in message or "append-only" in message
        else:
            conn.rollback()
            pytest.fail("expected DELETE against workshop_decisions to fail")


def test_delete_workshop_questions_row_is_refused(app_pg_config):
    from darwin.workshop import service as workshop_service

    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        workshop_id = _new_workshop(conn, candidate_id)
        question = workshop_service.create_question(
            conn, workshop_id, semantic_subject="x", question_text="y?"
        )

    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege,
            "DELETE FROM workshop_questions WHERE id = %s", (question.question_id,),
        )
    _assert_denied(message)


def test_delete_strategy_workshops_row_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        workshop_id = _new_workshop(conn, candidate_id)

    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege,
            "DELETE FROM strategy_workshops WHERE id = %s", (workshop_id,),
        )
    _assert_denied(message)


def test_delete_strategy_workshop_discovery_link_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        discovery_id = _new_discovery(conn)
        workshop_id = _new_workshop_with_discovery(conn, candidate_id, discovery_id)

    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege,
            "DELETE FROM strategy_workshop_discovery_links WHERE workshop_id = %s", (workshop_id,),
        )
    _assert_denied(message)


def test_update_strategy_workshop_discovery_link_is_refused(app_pg_config):
    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        discovery_id = _new_discovery(conn)
        workshop_id = _new_workshop_with_discovery(conn, candidate_id, discovery_id)

    with connection(app_pg_config) as conn:
        message = _expect_rejected(
            conn, psycopg.errors.InsufficientPrivilege,
            "UPDATE strategy_workshop_discovery_links SET discovery_id = discovery_id WHERE workshop_id = %s",
            (workshop_id,),
        )
    _assert_denied(message)


def _new_discovery(conn) -> str:
    from tests.fixtures.workshops import new_user_discovered_discovery

    return new_user_discovered_discovery(conn)


def _new_workshop_with_discovery(conn, candidate_id: str, discovery_id: str) -> str:
    from darwin.workshop import service as workshop_service

    return workshop_service.open_workshop(
        conn, candidate_id=candidate_id, discovery_ids=(discovery_id,)
    ).workshop_id


def test_mutation_of_the_data_requirement_projection_fails_through_the_restricted_role(app_pg_config):
    """`strategy_version_data_requirements` is never independently
    editable (migration 0006's trigger) -- darwin_app additionally has no
    UPDATE/DELETE privilege on it at all (this fix)."""
    with connection(app_pg_config) as conn:
        candidate_id = _new_candidate(conn)
        draft = minimal_valid_draft()
        draft.draft_id = new_id()
        draft.candidate_id = candidate_id
        SpecificationDraftRepository(conn).create(draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        requirement_row = DataRequirementProjectionRepository(conn).list_for_strategy_version(
            outcome.strategy_version.strategy_version_id
        )[0]

    with connection(app_pg_config) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE strategy_version_data_requirements SET display_name = 'HACKED' WHERE id = %s",
                    (requirement_row["id"],),
                )
        except (psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException) as exc:
            conn.rollback()
            message = str(exc).lower()
            assert "permission denied" in message or "editable" in message
        else:
            conn.rollback()
            pytest.fail("expected UPDATE against strategy_version_data_requirements to fail")

    with connection(app_pg_config) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM strategy_version_data_requirements WHERE id = %s", (requirement_row["id"],)
                )
        except (psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException) as exc:
            conn.rollback()
            message = str(exc).lower()
            assert "permission denied" in message or "editable" in message
        else:
            conn.rollback()
            pytest.fail("expected DELETE against strategy_version_data_requirements to fail")
