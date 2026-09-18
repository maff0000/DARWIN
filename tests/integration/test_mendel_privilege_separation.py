"""PID-004C MENDEL Workshop Assistant database-privilege-separation proofs
-- against a real, disposable PostgreSQL already taken through the
role-separation bootstrap (see `darwin/research_store/bootstrap/`),
exactly like tests/integration/test_privilege_separation.py. Deliberately
its own file/role connection rather than reusing that file's fixtures
directly, for the same reason that file gives for not sharing the plain
`pg_config` role.

  DARWIN_PRIVSEP_APP_DSN       -- the RESTRICTED darwin_app role, post-upgrade.

Proves darwin_app CAN do the ordinary MENDEL read/write flow end-to-end
(SELECT/INSERT/UPDATE on mendel_runs/mendel_proposals) and CANNOT
TRUNCATE/DROP/CREATE against either table.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import psycopg
import pytest

from darwin.core.config import PostgresConfig
from darwin.research_store.db import connection
from darwin.workshop import mendel_service
from darwin.workshop.mendel_adapter import (
    DeterministicTestMendelAdapter,
    MendelInvocationResult,
)
from darwin.workshop.mendel_domain import InvocationPurpose
from tests.fixtures.mendel import (
    ask_question_proposal,
    open_workshop_with_draft,
    parameter_change_proposal,
)

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
            "DARWIN_PRIVSEP_APP_DSN not set -- MENDEL privilege-boundary tests require a disposable "
            "PostgreSQL already taken through the role-separation upgrade"
        )
    return _config_from_dsn(dsn, default_user="darwin_app")


def _expect_rejected(conn, exc_type, sql: str, params: tuple = ()) -> str:
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


def _assert_denied(message: str) -> None:
    lowered = message.lower()
    assert "permission denied" in lowered or "must be owner" in lowered, message


def test_ordinary_mendel_flow_succeeds_end_to_end_through_the_restricted_app_role(app_pg_config):
    with connection(app_pg_config) as conn:
        workshop, _revision = open_workshop_with_draft(conn)
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(
                proposals=(ask_question_proposal(), parameter_change_proposal(fixed_value=9)),
                reasoning_summary="privilege-separation smoke",
            )
        )
        run = mendel_service.invoke_mendel(
            conn, workshop.workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        assert run.status.value == "SUCCEEDED"
        proposals = mendel_service.list_proposals(conn, workshop.workshop_id)
        assert len(proposals) == 2

        question_proposal = next(p for p in proposals if p.proposal_class.value == "ASK_QUESTION")
        accepted = mendel_service.accept_proposal(
            conn, workshop.workshop_id, question_proposal.proposal_id, actor="privsep-test"
        )
        assert accepted.status.value == "ACCEPTED"


def test_darwin_app_cannot_truncate_or_drop_or_create_on_mendel_tables(app_pg_config):
    with connection(app_pg_config) as conn:
        for table in ("mendel_runs", "mendel_proposals"):
            _assert_denied(
                _expect_rejected(conn, psycopg.errors.InsufficientPrivilege, f"TRUNCATE TABLE {table}")
            )
            _assert_denied(
                _expect_rejected(conn, psycopg.errors.InsufficientPrivilege, f"DROP TABLE {table}")
            )
        _assert_denied(
            _expect_rejected(
                conn, psycopg.errors.InsufficientPrivilege,
                "CREATE TABLE mendel_privsep_test_table (id UUID PRIMARY KEY)",
            )
        )
