"""Focused regression test for the live-compatibility hotfix to
darwin/research_store/migrations.py (backport of PID-004A adversarial-audit
fix #2 item 9).

The pre-fix `migration_state()` (the function backing `/api/v1/migrations`
and `/api/v1/ready`) unconditionally ran
`CREATE TABLE IF NOT EXISTS schema_migrations` on every call, even though it
is meant to be a read-only diagnostic. That meant a restricted database role
without schema CREATE privilege could not call it at all -- blocking the
planned `darwin_app` least-privilege role from running the live application.

This test proves the fix using a REAL restricted PostgreSQL role (not a
superuser standing in for one): `migration_state()` must succeed under a
role with SELECT-only access to `schema_migrations` and CRUD-only access to
the application's own tables, with schema CREATE privilege explicitly
absent and proven absent.

Skipped automatically unless DARWIN_TEST_PG_DSN is set -- same discipline as
the rest of tests/integration/.
"""
from __future__ import annotations

import uuid

import psycopg
import pytest

from darwin.core.config import PostgresConfig
from darwin.research_store.migrations import migration_state, run_migrations

pytestmark = pytest.mark.integration

_APP_TABLES = [
    "source_strategies",
    "strategy_candidates",
    "strategy_versions",
    "market_datasets",
    "research_runs",
    "evidence_records",
    "scout_sources",
    "scout_discoveries",
    "scout_snapshots",
    "scout_claims",
    "scout_discovery_runs",
    "scout_intake_audit",
]

_EXPECTED_LIVE_ERA_VERSIONS = [
    "0001_foundation",
    "0002_research_run_instrument_binding",
    "0003_instrument_definition_binding",
    "0004_dike_policy_binding",
    "0005_scout_discovery",
]


def _config_for(base: PostgresConfig, *, user: str, password: str, database: str | None = None) -> PostgresConfig:
    return PostgresConfig(
        host=base.host,
        port=base.port,
        database=database or base.database,
        user=user,
        password=password,
    )


@pytest.fixture
def restricted_role(pg_config):
    """A genuinely restricted PostgreSQL role scoped to the (already
    migrated, 0001-0005) test database: CONNECT + schema USAGE + SELECT on
    `schema_migrations` + ordinary CRUD on the application's own data
    tables -- mirroring the least-privilege `darwin_app` role this hotfix
    exists to unblock. Schema CREATE is deliberately never granted, and is
    explicitly revoked in case the server's defaults ever changed.
    """
    role = f"darwin_app_test_{uuid.uuid4().hex[:8]}"
    password = uuid.uuid4().hex

    with psycopg.connect(pg_config.dsn(), autocommit=True) as conn:
        with conn.cursor() as cur:
            # CREATE ROLE does not support server-side parameter binding for
            # its PASSWORD clause -- the password is our own freshly
            # generated uuid4().hex (fixed-length lowercase hex, never
            # user-supplied), so safe to interpolate directly.
            cur.execute(f"CREATE ROLE \"{role}\" LOGIN PASSWORD '{password}' NOCREATEDB NOCREATEROLE NOSUPERUSER")
            cur.execute(f'GRANT CONNECT ON DATABASE "{pg_config.database}" TO "{role}"')
            cur.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            cur.execute(f'REVOKE CREATE ON SCHEMA public FROM "{role}"')
            cur.execute(f'REVOKE CREATE ON DATABASE "{pg_config.database}" FROM "{role}"')
            cur.execute(f'GRANT SELECT ON schema_migrations TO "{role}"')
            for table in _APP_TABLES:
                cur.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role}"')
        try:
            yield role, password
        finally:
            with conn.cursor() as cur:
                cur.execute(f'DROP OWNED BY "{role}"')
                cur.execute(f'DROP ROLE "{role}"')


def test_restricted_role_genuinely_has_no_create_privilege(pg_config, restricted_role):
    """Negative control: prove the role really cannot CREATE anything --
    the precondition that makes the positive assertion below meaningful.
    """
    role, password = restricted_role
    restricted_dsn = _config_for(pg_config, user=role, password=password).dsn()
    with (
        psycopg.connect(restricted_dsn, autocommit=True) as conn,
        conn.cursor() as cur,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        cur.execute("CREATE TABLE hotfix_probe_should_never_exist (id INT)")


def test_migration_state_succeeds_under_restricted_no_create_role(pg_config, restricted_role):
    """The actual defect + fix, proven under a real restricted role.

    Pre-fix, this call would raise psycopg.errors.InsufficientPrivilege
    because `applied_versions()` unconditionally ran
    `CREATE TABLE IF NOT EXISTS schema_migrations` first. Post-fix,
    `migration_state()` never attempts DDL -- and since the role above has
    been proven (in the sibling test) to hold zero CREATE privilege
    anywhere, a successful call here is itself proof that no DDL was
    executed: a role with no CREATE grant cannot have performed any.
    """
    from tests.integration.conftest import MIGRATIONS_DIR

    role, password = restricted_role
    restricted_config = _config_for(pg_config, user=role, password=password)

    state = migration_state(restricted_config, MIGRATIONS_DIR)

    assert state["initialised"] is True
    assert state["applied"] == _EXPECTED_LIVE_ERA_VERSIONS
    assert state["pending"] == []
    assert state["up_to_date"] is True
    assert state["total_migrations"] == len(_EXPECTED_LIVE_ERA_VERSIONS)


def test_run_migrations_still_performs_real_ddl_under_genuine_privilege(pg_config):
    """Governed-path sanity check on a brand-new database: `run_migrations`
    (the ONLY function meant to run under migrator/owner authority in
    production) must still genuinely create `schema_migrations` from
    scratch and apply every migration when given real privilege -- proving
    the privilege-separation split did not quietly break the one path that
    is supposed to perform DDL.
    """
    from tests.integration.conftest import MIGRATIONS_DIR

    fresh_db = f"darwin_fresh_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(pg_config.dsn(), autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(f'CREATE DATABASE "{fresh_db}"')

    try:
        fresh_config = _config_for(pg_config, user=pg_config.user, password=pg_config.password, database=fresh_db)

        applied = run_migrations(fresh_config, MIGRATIONS_DIR)
        assert applied == _EXPECTED_LIVE_ERA_VERSIONS

        state = migration_state(fresh_config, MIGRATIONS_DIR)
        assert state["initialised"] is True
        assert state["up_to_date"] is True
        assert state["pending"] == []
        assert state["applied"] == _EXPECTED_LIVE_ERA_VERSIONS

        # Re-running is idempotent and requires no further DDL for
        # already-applied versions.
        assert run_migrations(fresh_config, MIGRATIONS_DIR) == []
    finally:
        with psycopg.connect(pg_config.dsn(), autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (fresh_db,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{fresh_db}"')
