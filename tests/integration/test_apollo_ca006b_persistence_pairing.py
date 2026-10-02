"""Central Architecture correction CA-006B adversarial test 14: persistence
refuses to pair an `ApolloEngineResult` with a different
`ResearchConfiguration`/`MarketDataset` than the one that actually
produced it.

Uses its own dedicated, freshly-created database -- same rationale as
tests/integration/test_apollo_persistence.py's module docstring.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from darwin.apollo import run_apollo_candle_causal_core
from darwin.apollo.errors import InvalidConfigurationError
from darwin.apollo.persistence import (
    persist_apollo_result,
    persist_research_contracts_chain,
)
from darwin.core.config import PostgresConfig
from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.migrations import run_migrations
from tests.fixtures.apollo_strategy import apollo_row, build_apollo_fixture_bundle
from tests.integration.conftest import _config_from_dsn

pytestmark = [pytest.mark.integration, pytest.mark.migration_authority]

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _rows(n: int = 4):
    return [
        apollo_row(UTC_START + timedelta(hours=i), "3990", "3995", "3985", "3990" if i == 0 else "4005")
        for i in range(n)
    ]


def _admin_config() -> PostgresConfig:
    dsn = os.environ.get("DARWIN_TEST_PG_DSN")
    if not dsn:
        pytest.skip("DARWIN_TEST_PG_DSN not set")
    return _config_from_dsn(dsn)


@pytest.fixture(scope="module")
def pg_config():
    import darwin.research_store as _research_store

    admin = _admin_config()
    db_name = f"darwin_apollo_ca006b_pairing_test_{new_id().replace('-', '_')}"
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


def _run(bundle):
    return run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, execution_policy=bundle.execution_policy,
        partition_policy=bundle.partition_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    )


def test_ca006b_14_persistence_refuses_a_result_paired_with_a_different_dataset(pg_config) -> None:
    bundle_a = build_apollo_fixture_bundle(dataset_id=new_id(), rows=_rows(), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    bundle_b = build_apollo_fixture_bundle(dataset_id=new_id(), rows=_rows(n=6), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    result_a = _run(bundle_a)

    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=bundle_a.executable_plan, parameter_set=bundle_a.parameter_set,
            execution_policy=bundle_a.execution_policy, partition_policy=bundle_a.partition_policy,
            research_configuration=bundle_a.research_configuration,
        )
        with pytest.raises(InvalidConfigurationError):
            persist_apollo_result(
                conn, research_configuration=bundle_a.research_configuration, market_dataset=bundle_b.market_dataset,
                engine_result=result_a, strategy_title="CA-006B-14 mismatched dataset", version_label="v1",
                build_version="ca-006b-test",
            )


def test_ca006b_14_persistence_refuses_a_result_paired_with_a_different_research_configuration(pg_config) -> None:
    bundle_a = build_apollo_fixture_bundle(dataset_id=new_id(), rows=_rows(), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    bundle_b = build_apollo_fixture_bundle(dataset_id=new_id(), rows=_rows(), entry_threshold=Decimal(9999), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    result_a = _run(bundle_a)

    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=bundle_b.executable_plan, parameter_set=bundle_b.parameter_set,
            execution_policy=bundle_b.execution_policy, partition_policy=bundle_b.partition_policy,
            research_configuration=bundle_b.research_configuration,
        )
        with pytest.raises(InvalidConfigurationError):
            persist_apollo_result(
                conn, research_configuration=bundle_b.research_configuration, market_dataset=bundle_a.market_dataset,
                engine_result=result_a, strategy_title="CA-006B-14 mismatched configuration", version_label="v1",
                build_version="ca-006b-test",
            )


def test_ca006b_14_persistence_still_accepts_the_correctly_paired_result(pg_config) -> None:
    bundle = build_apollo_fixture_bundle(dataset_id=new_id(), rows=_rows(), stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    result = _run(bundle)
    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=bundle.executable_plan, parameter_set=bundle.parameter_set,
            execution_policy=bundle.execution_policy, partition_policy=bundle.partition_policy,
            research_configuration=bundle.research_configuration,
        )
        persisted = persist_apollo_result(
            conn, research_configuration=bundle.research_configuration, market_dataset=bundle.market_dataset,
            engine_result=result, strategy_title="CA-006B-14 correctly paired", version_label="v1",
            build_version="ca-006b-test",
        )
    assert persisted.research_run.configuration_fingerprint == bundle.research_configuration.fingerprint
