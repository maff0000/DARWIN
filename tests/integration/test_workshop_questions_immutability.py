"""PID-004C CLOSURE HARDENING item 3 (Auditor Finding B fix) --
`workshop_questions` content-immutability proof against a real, disposable
PostgreSQL taken through the FULL role-separation bootstrap, exactly like
`tests/integration/test_mendel_privilege_separation.py`:

  01_fresh_bootstrap_roles.sql (as postgres superuser)
    -> migrate 0001-0011 (as darwin_migrator)
    -> 02_grant_app_table_privileges.sql (as darwin_migrator/superuser)
    -> connect as the RESTRICTED darwin_app role for every attempt below.

An independent Auditor confirmed, with real evidence, that a raw
`UPDATE workshop_questions SET origin='HUMAN' WHERE origin='MENDEL'`
succeeded with no error against the pre-fix schema. This file proves the
NEW `trg_workshop_questions_content_immutable` trigger (migration 0011)
refuses that exact statement, and every other substantive-column rewrite,
UNDER THE REAL RESTRICTED ROLE -- never merely under a superuser-equivalent
test role, and never by narrowing/widening darwin_app's own GRANTs (the
trigger itself is what refuses it, independent of role privilege level).

  DARWIN_PRIVSEP_APP_DSN -- the RESTRICTED darwin_app role, post-bootstrap.

Deliberately its own file (not appended to test_mendel_privilege_
separation.py) since it targets workshop_questions, not the mendel_* pair
that file already covers -- same "avoid unrelated cross-file coupling"
reasoning test_mendel_privilege_separation.py's own docstring gives.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import psycopg
import pytest

from darwin.core.config import PostgresConfig
from darwin.research_store.db import connection
from darwin.specification.provenance import RuleOrigin
from darwin.workshop import mendel_service, service
from darwin.workshop.domain import QuestionStatus
from darwin.workshop.mendel_adapter import (
    DeterministicTestMendelAdapter,
    MendelInvocationResult,
)
from darwin.workshop.mendel_domain import InvocationPurpose
from tests.fixtures.mendel import ask_question_proposal, open_workshop_with_draft

pytestmark = pytest.mark.integration


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
            "DARWIN_PRIVSEP_APP_DSN not set -- workshop_questions immutability tests require a "
            "disposable PostgreSQL already taken through the role-separation bootstrap"
        )
    return _config_from_dsn(dsn, default_user="darwin_app")


def _seed_mendel_question(conn) -> tuple:
    """A real MENDEL-origin WorkshopQuestion, created via the actual
    accept_proposal path -- exactly the row shape the Auditor's own
    reproduction targeted, never a hand-rolled INSERT."""
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
    conn.commit()
    return workshop, question


def _expect_refused(conn, sql: str, params: tuple) -> str:
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    except psycopg.errors.RaiseException as exc:
        message = str(exc)
        conn.rollback()
        return message
    else:
        conn.rollback()
        pytest.fail(f"expected the trigger to refuse this UPDATE, nothing was raised: {sql}")


def test_real_restricted_role_cannot_launder_mendel_origin_to_human(app_pg_config):
    """The EXACT statement the Auditor's own reproduction used."""
    with connection(app_pg_config) as conn:
        _workshop, question = _seed_mendel_question(conn)
        message = _expect_refused(
            conn, "UPDATE workshop_questions SET origin='HUMAN' WHERE origin='MENDEL' AND id = %s",
            (question.question_id,),
        )
        assert "immutable" in message.lower()

        # And genuinely unchanged afterward.
        with connection(app_pg_config) as verify_conn:
            questions = service.list_questions(verify_conn, _workshop.workshop_id)
        still = next(q for q in questions if q.question_id == question.question_id)
        assert still.origin.value == "MENDEL"


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("question_text", "'hacked?'"),
        ("semantic_subject", "'hacked'"),
        ("rationale", "'hacked rationale'"),
        ("created_at_utc", "now()"),
    ],
)
def test_real_restricted_role_cannot_rewrite_substantive_columns(app_pg_config, column, value):
    with connection(app_pg_config) as conn:
        _workshop, question = _seed_mendel_question(conn)
        message = _expect_refused(
            conn, f"UPDATE workshop_questions SET {column} = {value} WHERE id = %s", (question.question_id,)
        )
        assert "immutable" in message.lower()


def test_real_restricted_role_cannot_rewrite_workshop_id(app_pg_config):
    with connection(app_pg_config) as conn:
        _workshop_a, question = _seed_mendel_question(conn)
        workshop_b, _ = open_workshop_with_draft(conn)
        conn.commit()
        message = _expect_refused(
            conn, "UPDATE workshop_questions SET workshop_id = %s WHERE id = %s",
            (workshop_b.workshop_id, question.question_id),
        )
        assert "immutable" in message.lower()


def test_real_restricted_role_cannot_delete(app_pg_config):
    """Two independent layers refuse this, same defence-in-depth shape as
    workshop_decisions/mendel_proposals (02_grant_app_table_privileges.sql's
    own comment): darwin_app is never GRANTed DELETE on workshop_questions
    at all (grant-layer denial, InsufficientPrivilege -- what this test
    observes), and even a role that DID have DELETE granted would still be
    refused by trg_workshop_questions_content_immutable's own explicit
    DELETE rejection (proven under the ordinary `pg_config` role in
    tests/integration/test_mendel_migration.py::
    test_workshop_questions_content_immutability_trigger_rejects_delete,
    which is NOT grant-restricted and so genuinely exercises the trigger
    itself, independent of any GRANT)."""
    with connection(app_pg_config) as conn:
        _workshop, question = _seed_mendel_question(conn)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.cursor() as cur:
            cur.execute("DELETE FROM workshop_questions WHERE id = %s", (question.question_id,))
        conn.rollback()


def test_real_restricted_role_legitimate_resolution_still_succeeds(app_pg_config):
    """Positive control: the real resolve_question lifecycle transition
    (OPEN -> RESOLVED, resolved_at_utc + accepted_decision_id set) must
    still succeed, under the REAL restricted role, exactly as before the
    trigger was added."""
    with connection(app_pg_config) as conn:
        workshop, question = _seed_mendel_question(conn)
        decision = service.create_decision(
            conn, workshop.workshop_id, proposed_value={"note": "resolved via privsep test"},
            origin=RuleOrigin.USER_CLARIFICATION, actor="matt",
            rationale="Resolving the MENDEL-raised question under the restricted role.",
        )
        resolved = service.resolve_question(
            conn, workshop.workshop_id, question.question_id,
            resolution=QuestionStatus.RESOLVED, accepted_decision_id=decision.decision_id,
        )
        assert resolved.status == QuestionStatus.RESOLVED
        assert resolved.resolved_at_utc is not None
        assert resolved.accepted_decision_id == decision.decision_id
        assert resolved.origin.value == "MENDEL"
        assert resolved.question_text == question.question_text
        conn.commit()
