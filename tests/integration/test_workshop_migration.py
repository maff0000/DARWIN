"""PID-004B migration 0009 -- clean-path and upgrade-path proofs.

Clean-path (0001 -> 0009 on a brand-new database) is already proven by
every OTHER integration test in this session via the shared `pg_config`
fixture (`tests/integration/conftest.py`), which runs `run_migrations`
against the full, current `migrations_sql/` directory before any test
executes -- if 0009 did not apply cleanly on top of a fresh database, no
integration test in this whole suite would run at all.

This file additionally proves the UPGRADE path: an existing database
already migrated only through 0008, carrying real pre-existing
candidate/discovery/version data, gains 0009 cleanly on a SECOND
`run_migrations` call, with that pre-existing data completely unaffected.
Requires DB-admin-scoped authority (`CREATE DATABASE`) -- marked
`migration_authority` per the existing convention in pyproject.toml.
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
from darwin.research_store.models import StrategyCandidate
from darwin.research_store.repositories import StrategyCandidateRepository
from darwin.research_store.specification_finalisation import (
    finalise_specification_draft,
)
from darwin.research_store.specification_repositories import (
    SpecificationDraftRepository,
)
from tests.fixtures.specification_drafts import minimal_valid_draft
from tests.fixtures.workshops import new_user_discovered_discovery
from tests.integration.conftest import _config_from_dsn

pytestmark = [pytest.mark.integration, pytest.mark.migration_authority]

MIGRATIONS_DIR = Path(_research_store.__file__).resolve().parent / "migrations_sql"


def _admin_config() -> PostgresConfig | None:
    import os

    dsn = os.environ.get("DARWIN_TEST_PG_DSN")
    if not dsn:
        pytest.skip("DARWIN_TEST_PG_DSN not set")
    return _config_from_dsn(dsn)


@pytest.fixture
def fresh_database():
    """Creates a brand-new, throwaway database on the SAME disposable
    Postgres instance `DARWIN_TEST_PG_DSN` already points at (requires
    CREATE DATABASE authority), and drops it afterwards."""
    admin = _admin_config()
    db_name = f"darwin_upgrade_test_{new_id().replace('-', '_')}"
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
    """A temp copy of migrations_sql/ containing only files strictly
    before `version_prefix_exclusive` in filename order -- lets
    `run_migrations` be pointed at "only 0001-0008" without touching the
    real migrations_sql/ directory at all."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="darwin_migrations_subset_"))
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name < version_prefix_exclusive:
            shutil.copy(path, tmp_dir / path.name)
    return tmp_dir


def test_0009_upgrade_path_applies_cleanly_and_preserves_existing_data(fresh_database):
    old_migrations_dir = _migrations_dir_up_to("0009")
    try:
        applied = run_migrations(fresh_database, old_migrations_dir)
        assert "0008_strategy_version_draft_origin_integrity" in applied
        assert not any(v.startswith("0009") for v in applied)
    finally:
        shutil.rmtree(old_migrations_dir, ignore_errors=True)

    # Seed representative pre-existing data through the OLD (0001-0008)
    # schema shape -- a candidate, a discovery, a draft, and a finalised
    # StrategyVersion, exactly like a real pre-0009 deployment would carry.
    with connection(fresh_database) as conn:
        candidate_id = new_id()
        StrategyCandidateRepository(conn).create(
            StrategyCandidate(id=candidate_id, title="Pre-existing candidate")
        )
        discovery_id = new_user_discovered_discovery(conn, source_symbol="XAUUSD")
        draft = minimal_valid_draft(candidate_id=candidate_id)
        draft.draft_id = new_id()
        SpecificationDraftRepository(conn).create(draft)
        outcome = finalise_specification_draft(conn, draft_id=draft.draft_id, expected_revision=1)
        assert outcome.strategy_version is not None
        strategy_version_id = outcome.strategy_version.strategy_version_id

    # Now apply 0009 on top, using the REAL, full migrations directory --
    # only 0009 should be newly applied.
    applied_now = run_migrations(fresh_database, MIGRATIONS_DIR)
    assert applied_now == ["0009_strategy_workshop"]
    state = migration_state(fresh_database, MIGRATIONS_DIR)
    assert state["up_to_date"] is True

    # Pre-existing data is completely unaffected.
    with connection(fresh_database) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT title FROM strategy_candidates WHERE id = %s", (candidate_id,))
            assert cur.fetchone()["title"] == "Pre-existing candidate"
            cur.execute("SELECT source_symbol FROM scout_discoveries WHERE id = %s", (discovery_id,))
            assert cur.fetchone()["source_symbol"] == "XAUUSD"
            cur.execute("SELECT id FROM strategy_versions WHERE id = %s", (strategy_version_id,))
            assert cur.fetchone() is not None

        # And the new PID-004B tables/objects exist and are immediately
        # usable against this upgraded database.
        from darwin.workshop import service

        workshop = service.open_workshop(conn, candidate_id=candidate_id, discovery_ids=(discovery_id,))
        assert workshop.candidate_id == candidate_id


def test_0009_is_idempotent_on_a_database_that_already_has_it(fresh_database):
    run_migrations(fresh_database, MIGRATIONS_DIR)
    applied_again = run_migrations(fresh_database, MIGRATIONS_DIR)
    assert applied_again == []
