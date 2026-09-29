"""PID-006B falsification test 13, against a real, disposable PostgreSQL
(same pattern as tests/integration/test_research_contracts_persistence.py):
the ZERO_COST mechanical run and the non-zero-cost run BOTH persist as
`EvidenceLevel.APOLLO_RESULT` -- never `APOLLO_PROOF` -- verified by
querying the REAL persisted `ResearchRun.result_kind` row back out of
Postgres, never merely asserting an in-memory object's field.

Deliberately uses its OWN dedicated, freshly-created database (the same
`fresh_database`-per-file pattern tests/integration/test_mendel_migration.py
and tests/integration/test_workshop_migration.py already establish) rather
than the shared session-scoped `pg_config` database every OTHER
integration test file writes into: this file persists real
`market_datasets` rows for XAU_USD/H1 (the one instrument/timeframe this
engine slice supports) as a genuine, expected side effect of exercising
`persist_apollo_result` -- and several *other* integration tests
(tests/integration/test_workshop_ui_enablement.py,
tests/integration/test_mendel_api.py) assert readiness/capability state
that would be silently corrupted by an unrelated XAU_USD/H1 dataset row
leaking into the SAME shared database earlier in the same pytest session
(`darwin.workshop.service.assess_workshop_readiness` scans up to 500 most
recent `market_datasets` rows session-wide, with no per-test scoping of
its own). Isolating this file's writes to its own throwaway database is
the narrow, correct fix -- not a workaround for a bug in those other
tests, which never expected a second, real-data-backed engine slice to
exist in this codebase at all until PID-006B."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest

from darwin.apollo import run_apollo_candle_causal_core
from darwin.apollo.capability import FIXED_MECHANICAL_TEST_COST
from darwin.apollo.persistence import (
    persist_apollo_result,
    persist_research_contracts_chain,
)
from darwin.core.config import PostgresConfig
from darwin.core.evidence import EvidenceLevel
from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.migrations import migration_state, run_migrations
from tests.fixtures.apollo_strategy import apollo_row, build_apollo_fixture_bundle
from tests.integration.conftest import _config_from_dsn

pytestmark = [pytest.mark.integration, pytest.mark.migration_authority]

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _admin_config() -> PostgresConfig:
    dsn = os.environ.get("DARWIN_TEST_PG_DSN")
    if not dsn:
        pytest.skip("DARWIN_TEST_PG_DSN not set")
    return _config_from_dsn(dsn)


@pytest.fixture(scope="module")
def pg_config():
    """A dedicated, throwaway database for this file alone -- see module
    docstring. Migrated once, dropped at the end of the module."""
    from pathlib import Path

    import darwin.research_store as _research_store

    admin = _admin_config()
    db_name = f"darwin_apollo_persistence_test_{new_id().replace('-', '_')}"
    with psycopg.connect(admin.dsn(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{db_name}"')
    cfg = PostgresConfig(host=admin.host, port=admin.port, database=db_name, user=admin.user, password=admin.password)
    try:
        migrations_dir = Path(_research_store.__file__).resolve().parent / "migrations_sql"
        run_migrations(cfg, migrations_dir)
        yield cfg
    finally:
        with psycopg.connect(admin.dsn(), autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')


def _rows(n: int = 5):
    out = []
    for i in range(n):
        base = 3990 + (i % 3) * 15
        close = base + (5 if i % 2 else -3)
        out.append(apollo_row(UTC_START + timedelta(hours=i), str(base), str(base + 15), str(base - 15), str(close)))
    return out


def test_migration_0013_widens_the_evidence_level_check_constraints(pg_config) -> None:
    from pathlib import Path

    import darwin.research_store as _research_store

    migrations_dir = Path(_research_store.__file__).resolve().parent / "migrations_sql"
    state = migration_state(pg_config, migrations_dir)
    assert "0013_apollo_result_evidence_level" in state["applied"]

    with connection(pg_config) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conname = %s",
            ("research_runs_result_kind_check",),
        )
        assert "APOLLO_RESULT" in cur.fetchone()["def"]
        cur.execute(
            "SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conname = %s",
            ("evidence_records_evidence_level_check",),
        )
        assert "APOLLO_RESULT" in cur.fetchone()["def"]


def _persist_one_run(pg_config, *, dataset_id: str, cost_methodology) -> str:
    bundle = build_apollo_fixture_bundle(
        dataset_id=dataset_id, rows=_rows(), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000),
        cost_methodology=cost_methodology,
    )
    result = run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    )
    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=bundle.executable_plan, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, partition_policy=bundle.partition_policy,
            research_configuration=bundle.research_configuration,
        )
        persisted = persist_apollo_result(
            conn, research_configuration=bundle.research_configuration, market_dataset=bundle.market_dataset,
            engine_result=result, strategy_title="PID-006B persistence test fixture", version_label="v1",
            build_version="test-pid006b",
        )
    return persisted.research_run.id


def test_zero_cost_run_persists_as_apollo_result_never_apollo_proof(pg_config) -> None:
    from darwin.research_contracts.execution_policy import ZERO_COST

    run_id = _persist_one_run(pg_config, dataset_id=new_id(), cost_methodology=ZERO_COST)
    with connection(pg_config) as conn, conn.cursor() as cur:
        cur.execute("SELECT result_kind FROM research_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
    assert row["result_kind"] == EvidenceLevel.APOLLO_RESULT.value
    assert row["result_kind"] != EvidenceLevel.APOLLO_PROOF.value


def test_non_zero_cost_run_also_persists_as_apollo_result_never_apollo_proof(pg_config) -> None:
    run_id = _persist_one_run(pg_config, dataset_id=new_id(), cost_methodology=FIXED_MECHANICAL_TEST_COST)
    with connection(pg_config) as conn, conn.cursor() as cur:
        cur.execute("SELECT result_kind FROM research_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
    assert row["result_kind"] == EvidenceLevel.APOLLO_RESULT.value
    assert row["result_kind"] != EvidenceLevel.APOLLO_PROOF.value


def test_persisted_run_binds_configuration_fingerprint_and_evidence_summary(pg_config) -> None:
    bundle = build_apollo_fixture_bundle(
        dataset_id=new_id(), rows=_rows(), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000),
    )
    result = run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    )
    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=bundle.executable_plan, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, partition_policy=bundle.partition_policy,
            research_configuration=bundle.research_configuration,
        )
        persisted = persist_apollo_result(
            conn, research_configuration=bundle.research_configuration, market_dataset=bundle.market_dataset,
            engine_result=result, strategy_title="PID-006B evidence test fixture", version_label="v1",
            build_version="test-pid006b",
        )

    with connection(pg_config) as conn, conn.cursor() as cur:
        cur.execute("SELECT configuration_fingerprint, dataset_id FROM research_runs WHERE id = %s", (persisted.research_run.id,))
        run_row = cur.fetchone()
        cur.execute("SELECT reference, evidence_level FROM evidence_records WHERE run_id = %s", (persisted.research_run.id,))
        evidence_rows = cur.fetchall()

    assert run_row["configuration_fingerprint"] == bundle.research_configuration.fingerprint
    assert str(run_row["dataset_id"]) == bundle.market_dataset.dataset_id
    assert len(evidence_rows) == 1
    assert evidence_rows[0]["evidence_level"] == EvidenceLevel.APOLLO_RESULT.value
    import json

    summary = json.loads(evidence_rows[0]["reference"])
    assert summary["decision_stream_hash"] == result.decision_stream_hash
    assert summary["fill_trade_sequence_hash"] == result.fill_trade_sequence_hash
    assert summary["economic_outcome_hash"] == result.economic_outcome_hash
    assert summary["research_configuration_fingerprint"] == bundle.research_configuration.fingerprint


def test_persist_research_contracts_chain_is_idempotent(pg_config) -> None:
    """Calling the chain-persistence helper twice for the identical
    configuration is a safe no-op (PID-006A ON CONFLICT DO NOTHING
    discipline, reused verbatim)."""
    bundle = build_apollo_fixture_bundle(
        dataset_id="ds-persist-idempotent", rows=_rows(), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000),
    )
    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=bundle.executable_plan, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, partition_policy=bundle.partition_policy,
            research_configuration=bundle.research_configuration,
        )
        persist_research_contracts_chain(
            conn, executable_plan=bundle.executable_plan, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, partition_policy=bundle.partition_policy,
            research_configuration=bundle.research_configuration,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM research_configurations WHERE fingerprint = %s",
                (bundle.research_configuration.fingerprint,),
            )
            assert cur.fetchone()["n"] == 1
