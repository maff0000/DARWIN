"""PID-004C migration 0011 -- clean-path, upgrade-path, structural CHECK,
and content-immutability proofs.

Clean-path (0001 -> 0011 on a brand-new database) is already proven by
every OTHER integration test in this session via the shared `pg_config`
fixture (mirrors tests/integration/test_workshop_migration.py's own
reasoning for migration 0009). This file additionally proves: the UPGRADE
path (an existing database already migrated only through 0010, carrying
real pre-existing Workshop data, gains 0011 cleanly on a second
`run_migrations` call, with that pre-existing data completely unaffected);
the structural class<->category CHECK constraint (a raw SQL INSERT); the
widened `workshop_questions.origin` CHECK; the
`trg_mendel_proposals_content_immutable` trigger; and (PID-004C closure
hardening item 3 / Auditor Finding B fix) the
`trg_workshop_questions_content_immutable` trigger -- these structural
proofs run under the ordinary `pg_config` test role; the REAL restricted
`darwin_app` role proof (the Auditor's own reproduction, under the actual
production-shaped privilege boundary) lives in
tests/integration/test_workshop_questions_immutability.py.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import psycopg
import pytest

import darwin.research_store as _research_store
from darwin.core.config import PostgresConfig
from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.migrations import migration_state, run_migrations
from darwin.specification.provenance import RuleOrigin
from darwin.workshop import mendel_service, service
from darwin.workshop.domain import QuestionStatus
from darwin.workshop.mendel_adapter import (
    DeterministicTestMendelAdapter,
    MendelInvocationResult,
)
from darwin.workshop.mendel_domain import InvocationPurpose
from tests.fixtures.mendel import ask_question_proposal, open_workshop_with_draft
from tests.fixtures.workshops import new_candidate, new_user_discovered_discovery
from tests.integration.conftest import _config_from_dsn

pytestmark = [pytest.mark.integration, pytest.mark.migration_authority]

MIGRATIONS_DIR = Path(_research_store.__file__).resolve().parent / "migrations_sql"


def _admin_config() -> PostgresConfig:
    import os

    dsn = os.environ.get("DARWIN_TEST_PG_DSN")
    if not dsn:
        pytest.skip("DARWIN_TEST_PG_DSN not set")
    return _config_from_dsn(dsn)


@pytest.fixture
def fresh_database():
    admin = _admin_config()
    db_name = f"darwin_mendel_upgrade_test_{new_id().replace('-', '_')}"
    with psycopg.connect(admin.dsn(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{db_name}"')
    try:
        yield PostgresConfig(
            host=admin.host, port=admin.port, database=db_name, user=admin.user, password=admin.password,
        )
    finally:
        with psycopg.connect(admin.dsn(), autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


def _migrations_dir_up_to(version_prefix_exclusive: str) -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="darwin_mendel_migrations_subset_"))
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name < version_prefix_exclusive:
            shutil.copy(path, tmp_dir / path.name)
    return tmp_dir


def test_0011_upgrade_path_applies_cleanly_and_preserves_existing_workshop_data(fresh_database):
    old_migrations_dir = _migrations_dir_up_to("0011")
    try:
        applied = run_migrations(fresh_database, old_migrations_dir)
        assert "0010_strategy_candidate_origin_discovery" in applied
        assert not any(v.startswith("0011") for v in applied)
    finally:
        shutil.rmtree(old_migrations_dir, ignore_errors=True)

    # Seed representative pre-existing PID-004B Workshop data through the
    # OLD (0001-0010) schema shape.
    with connection(fresh_database) as conn:
        candidate_id = new_candidate(conn)
        discovery_id = new_user_discovered_discovery(conn, source_symbol="XAUUSD")
        workshop = service.open_workshop(conn, candidate_id=candidate_id, discovery_ids=(discovery_id,))
        question = service.create_question(
            conn, workshop.workshop_id, semantic_subject="exit", question_text="what closes the trade?"
        )

    applied_now = run_migrations(fresh_database, MIGRATIONS_DIR)
    assert applied_now == ["0011_mendel_workshop_assistant"]
    state = migration_state(fresh_database, MIGRATIONS_DIR)
    assert state["up_to_date"] is True

    with connection(fresh_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM strategy_candidates WHERE id = %s", (candidate_id,))
            assert cur.fetchone()["title"] is not None
            cur.execute("SELECT status FROM strategy_workshops WHERE id = %s", (workshop.workshop_id,))
            assert cur.fetchone()["status"] == "ACTIVE"
            cur.execute("SELECT origin, status FROM workshop_questions WHERE id = %s", (question.question_id,))
            row = cur.fetchone()
            assert row["origin"] == "HUMAN"
            assert row["status"] == "OPEN"

        # And the new PID-004C tables/objects exist and are immediately usable.
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(proposals=(ask_question_proposal(),), reasoning_summary="upgrade smoke")
        )
        run = mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        assert run.status.value == "SUCCEEDED"
        proposals = mendel_service.list_proposals(conn, workshop.workshop_id)
        assert len(proposals) == 1

        # And a MENDEL-originated question really can be created now (the
        # one narrow PID-004B schema change this migration makes).
        accepted = mendel_service.accept_proposal(conn, workshop.workshop_id, proposals[0].proposal_id, actor="matt")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT origin FROM workshop_questions WHERE id = %s", (accepted.resulting_question_id,)
            )
            assert cur.fetchone()["origin"] == "MENDEL"


def test_0011_is_idempotent_on_a_database_that_already_has_it(fresh_database):
    run_migrations(fresh_database, MIGRATIONS_DIR)
    applied_again = run_migrations(fresh_database, MIGRATIONS_DIR)
    assert applied_again == []


# ============================================================================
# Structural CHECK constraint proofs -- raw SQL, independent of any Python
# guard (PID-004C sec6.4).
# ============================================================================


def test_class_category_mismatch_rejected_by_database_check_constraint(pg_config):
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(proposals=(), reasoning_summary="setup")
        )
        run = mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        with pytest.raises(psycopg.errors.CheckViolation), conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mendel_proposals
                    (id, run_id, workshop_id, proposal_class, proposal_category, proposal_schema_version,
                     payload, rationale, generated_against_draft_revision, generated_against_no_draft_yet)
                VALUES (%s, %s, %s, 'ASK_QUESTION', 'ADVISORY', 'MENDEL_PROPOSAL_V1', '{}', 'bad pair',
                        1, FALSE)
                """,
                (new_id(), run.run_id, workshop.workshop_id),
            )
        conn.rollback()


def test_no_draft_yet_binding_pair_check_rejects_both_set(pg_config):
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(proposals=(), reasoning_summary="setup")
        )
        run = mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        with pytest.raises(psycopg.errors.CheckViolation), conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mendel_proposals
                    (id, run_id, workshop_id, proposal_class, proposal_category, proposal_schema_version,
                     payload, rationale, generated_against_draft_revision, generated_against_no_draft_yet)
                VALUES (%s, %s, %s, 'ASK_QUESTION', 'QUESTION', 'MENDEL_PROPOSAL_V1', '{}', 'bad binding',
                        1, TRUE)
                """,
                (new_id(), run.run_id, workshop.workshop_id),
            )
        conn.rollback()


def test_workshop_questions_origin_check_accepts_mendel_and_rejects_other_values(pg_config):
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workshop_questions (id, workshop_id, semantic_subject, question_text, origin) "
                "VALUES (%s, %s, 'x', 'y?', 'MENDEL')",
                (new_id(), workshop.workshop_id),
            )
        conn.rollback()  # this test only proves acceptance, not durable insertion

    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        with pytest.raises(psycopg.errors.CheckViolation), conn.cursor() as cur:
            cur.execute(
                "INSERT INTO workshop_questions (id, workshop_id, semantic_subject, question_text, origin) "
                "VALUES (%s, %s, 'x', 'y?', 'SOME_OTHER_ORIGIN')",
                (new_id(), workshop.workshop_id),
            )
        conn.rollback()


# ============================================================================
# Content-immutability trigger (mirrors migration 0009's workshop_decisions
# trigger, against mendel_proposals).
# ============================================================================


def test_mendel_proposals_content_immutability_trigger_rejects_delete(pg_config):
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(proposals=(ask_question_proposal(),), reasoning_summary="x")
        )
        mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        proposal = mendel_service.list_proposals(conn, workshop.workshop_id)[0]
        with pytest.raises(psycopg.errors.RaiseException), conn.cursor() as cur:
            cur.execute("DELETE FROM mendel_proposals WHERE id = %s", (proposal.proposal_id,))
        conn.rollback()


def test_mendel_proposals_content_immutability_trigger_rejects_payload_rewrite(pg_config):
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(proposals=(ask_question_proposal(),), reasoning_summary="x")
        )
        mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        proposal = mendel_service.list_proposals(conn, workshop.workshop_id)[0]
        with pytest.raises(psycopg.errors.RaiseException), conn.cursor() as cur:
            cur.execute(
                "UPDATE mendel_proposals SET payload = '{\"hacked\": true}' WHERE id = %s",
                (proposal.proposal_id,),
            )
        conn.rollback()


def test_mendel_proposals_content_immutability_trigger_permits_status_transition(pg_config):
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(proposals=(ask_question_proposal(),), reasoning_summary="x")
        )
        mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        proposal = mendel_service.list_proposals(conn, workshop.workshop_id)[0]
        accepted = mendel_service.accept_proposal(conn, workshop.workshop_id, proposal.proposal_id, actor="matt")
        assert accepted.status.value == "ACCEPTED"


# ============================================================================
# PID-004C closure hardening item 3 (Auditor Finding B fix):
# trg_workshop_questions_content_immutable -- structural proofs under the
# ordinary `pg_config` role. The REAL restricted darwin_app role proof
# (the Auditor's own reproduction) lives in
# tests/integration/test_workshop_questions_immutability.py.
# ============================================================================


def _seed_mendel_question(conn) -> tuple:
    """A real MENDEL-origin WorkshopQuestion, created via the actual
    accept_proposal path (never a hand-rolled INSERT) -- the same
    origin='MENDEL' row the Auditor's own reproduction targeted."""
    workshop, _ = open_workshop_with_draft(conn)
    adapter = DeterministicTestMendelAdapter(
        result=MendelInvocationResult(proposals=(ask_question_proposal(),), reasoning_summary="x")
    )
    mendel_service.invoke_mendel(
        conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
    )
    proposal = mendel_service.list_proposals(conn, workshop.workshop_id)[0]
    accepted = mendel_service.accept_proposal(conn, workshop.workshop_id, proposal.proposal_id, actor="matt")
    questions = service.list_questions(conn, workshop.workshop_id)
    question = next(q for q in questions if q.question_id == accepted.resulting_question_id)
    assert question.origin.value == "MENDEL"
    return workshop, question


def test_workshop_questions_content_immutability_trigger_rejects_origin_laundering(pg_config):
    with connection(pg_config) as conn:
        _workshop, question = _seed_mendel_question(conn)
        with pytest.raises(psycopg.errors.RaiseException), conn.cursor() as cur:
            cur.execute(
                "UPDATE workshop_questions SET origin = 'HUMAN' WHERE id = %s", (question.question_id,)
            )
        conn.rollback()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("question_text", "'hacked?'"),
        ("semantic_subject", "'hacked'"),
        ("rationale", "'hacked rationale'"),
    ],
)
def test_workshop_questions_content_immutability_trigger_rejects_substantive_rewrite(pg_config, column, value):
    with connection(pg_config) as conn:
        _workshop, question = _seed_mendel_question(conn)
        with pytest.raises(psycopg.errors.RaiseException), conn.cursor() as cur:
            cur.execute(
                f"UPDATE workshop_questions SET {column} = {value} WHERE id = %s", (question.question_id,)
            )
        conn.rollback()


def test_workshop_questions_content_immutability_trigger_rejects_delete(pg_config):
    with connection(pg_config) as conn:
        _workshop, question = _seed_mendel_question(conn)
        with pytest.raises(psycopg.errors.RaiseException), conn.cursor() as cur:
            cur.execute("DELETE FROM workshop_questions WHERE id = %s", (question.question_id,))
        conn.rollback()


def test_workshop_questions_content_immutability_trigger_permits_legitimate_resolution(pg_config):
    """Positive control: the real resolve_question lifecycle transition
    (OPEN -> RESOLVED, resolved_at_utc + accepted_decision_id set) must
    still succeed exactly as before the trigger was added."""
    with connection(pg_config) as conn:
        workshop, question = _seed_mendel_question(conn)
        decision = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"note": "resolved via test"},
            origin=RuleOrigin.USER_CLARIFICATION,
            actor="matt", rationale="Resolving the MENDEL-raised question.",
        )
        resolved = service.resolve_question(
            conn, workshop.workshop_id, question.question_id,
            resolution=QuestionStatus.RESOLVED, accepted_decision_id=decision.decision_id,
        )
        assert resolved.status == QuestionStatus.RESOLVED
        assert resolved.resolved_at_utc is not None
        assert resolved.accepted_decision_id == decision.decision_id
        # And origin/content survived untouched.
        assert resolved.origin.value == "MENDEL"
        assert resolved.question_text == question.question_text
