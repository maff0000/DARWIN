"""PID-006B required real end-to-end acceptance: load a REAL bounded
HERMES XAU_USD MarketDataset (never fabricated/mocked), replay the
APOLLO Candle Causal Core against it under BOTH ZERO_COST and a
non-zero-cost policy, and persist both as real `APOLLO_RESULT` rows.

Interval decision -- recorded here BEFORE inspecting any performance
result (this exact comment block was written before this test was ever
run against real data):

    Instrument: XAU_USD
    Timeframe:  H1
    Start:      2025-01-06T00:00:00Z
    End:        2025-02-03T00:00:00Z   (4 calendar weeks, end exclusive)

Chosen for a manageable-but-non-trivial bar count (several hundred H1
bars) comfortably inside HERMES's real available XAU_USD H1 history
without depending on the most recent (still-settling) data. The entry
threshold (2714 USD) and SL/TP distances (15/25 USD) below were set from
this window's own real average close price (queried once, before writing
any assertion in this file) purely so the fixture strategy has a
realistic chance of producing a mixed signal against real data --
NEVER tuned against, or chosen after seeing, this run's own P&L or trade
count. Performance is explicitly not an acceptance criterion here: this
test proves the engine ran correctly end-to-end against real data, not
that it found a good trade.

Skips (never fabricates a substitute dataset) if HERMES DEV is genuinely
unreachable from this host -- verified via
`darwin.hermes.reader.check_hermes_reachable`.

Persists into its OWN dedicated, freshly-created database (same
`fresh_database`-per-file pattern as
tests/integration/test_apollo_persistence.py, see that file's module
docstring for the full rationale) rather than the shared session-scoped
`pg_config` database -- this file's real HERMES XAU_USD/H1 dataset would
otherwise leak into unrelated readiness/capability assertions running
later in the same pytest session.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from darwin.apollo import run_apollo_candle_causal_core
from darwin.apollo.capability import FIXED_MECHANICAL_TEST_COST
from darwin.apollo.persistence import (
    persist_apollo_result,
    persist_research_contracts_chain,
)
from darwin.core.config import DarwinConfig, PostgresConfig
from darwin.core.dike import DikeState
from darwin.core.evidence import EvidenceLevel
from darwin.core.identities import new_id
from darwin.hermes.contract import Timeframe
from darwin.hermes.instrument_definition import get_instrument_definition
from darwin.hermes.reader import check_hermes_reachable, load_market_dataset
from darwin.research_contracts.compiler import CanonicalStrategyCompiler
from darwin.research_contracts.execution_policy import ZERO_COST
from darwin.research_contracts.input_binding import (
    research_input_binding_from_market_dataset,
)
from darwin.research_contracts.partition_policy import (
    ResearchPartitionRole,
    build_research_partition_policy_version,
)
from darwin.research_contracts.research_configuration import (
    build_research_configuration,
)
from darwin.research_store.db import connection
from darwin.research_store.migrations import run_migrations
from tests.fixtures.apollo_strategy import (
    build_apollo_parameter_set,
    build_apollo_strategy_version,
)
from tests.integration.conftest import _config_from_dsn

pytestmark = [pytest.mark.integration, pytest.mark.hermes_dev, pytest.mark.migration_authority]


def _admin_config() -> PostgresConfig:
    dsn = os.environ.get("DARWIN_TEST_PG_DSN")
    if not dsn:
        pytest.skip("DARWIN_TEST_PG_DSN not set")
    return _config_from_dsn(dsn)


@pytest.fixture(scope="module")
def pg_config():
    """A dedicated, throwaway database for this file alone -- see module
    docstring."""
    import darwin.research_store as _research_store

    admin = _admin_config()
    db_name = f"darwin_apollo_hermes_acceptance_test_{new_id().replace('-', '_')}"
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

ACCEPTANCE_INSTRUMENT = "XAU_USD"
ACCEPTANCE_TIMEFRAME = Timeframe.H1
ACCEPTANCE_START_UTC = datetime(2025, 1, 6, 0, 0, tzinfo=UTC)
ACCEPTANCE_END_UTC = datetime(2025, 2, 3, 0, 0, tzinfo=UTC)
ACCEPTANCE_ENTRY_THRESHOLD_USD = Decimal(2714)
ACCEPTANCE_STOP_LOSS_DISTANCE_USD = Decimal(15)
ACCEPTANCE_TAKE_PROFIT_DISTANCE_USD = Decimal(25)


def _load_cfg() -> DarwinConfig | None:
    try:
        return DarwinConfig.load()
    except Exception:  # noqa: BLE001 - config genuinely absent in this environment
        return None


def _build_and_run(*, market_dataset, cost_methodology):
    strategy_version = build_apollo_strategy_version("sv-apollo-hermes-acceptance")
    parameter_set = build_apollo_parameter_set(
        strategy_version, entry_threshold=ACCEPTANCE_ENTRY_THRESHOLD_USD,
        stop_loss_distance=ACCEPTANCE_STOP_LOSS_DISTANCE_USD, take_profit_distance=ACCEPTANCE_TAKE_PROFIT_DISTANCE_USD,
    )
    plan = CanonicalStrategyCompiler().compile(strategy_version)
    instrument_definition = get_instrument_definition(ACCEPTANCE_INSTRUMENT)
    binding = research_input_binding_from_market_dataset(logical_input_role="PRIMARY_MARKET_DATA", market_dataset=market_dataset)
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    from tests.fixtures.apollo_strategy import build_apollo_execution_policy

    execution_policy = build_apollo_execution_policy(cost_methodology=cost_methodology)
    research_configuration = build_research_configuration(
        strategy_version=strategy_version, executable_plan=plan, parameter_set=parameter_set,
        instrument_definition=instrument_definition, research_input_bindings=(binding,),
        partition_policy=partition_policy, execution_policy=execution_policy, dike_state=DikeState.DISABLED,
    )
    result = run_apollo_candle_causal_core(
        strategy_version=strategy_version, executable_plan=plan, parameter_set=parameter_set,
        execution_policy=execution_policy, partition_policy=partition_policy,
        market_dataset=market_dataset, research_configuration=research_configuration, instrument_definition=instrument_definition,
    )
    return strategy_version, plan, parameter_set, partition_policy, execution_policy, research_configuration, result


@pytest.fixture(scope="module")
def real_hermes_dataset():
    cfg = _load_cfg()
    if cfg is None or not check_hermes_reachable(cfg.hermes):
        pytest.skip("HERMES DEV is not reachable from this environment -- skipping real end-to-end acceptance")
    dataset = load_market_dataset(
        cfg.hermes, instrument=ACCEPTANCE_INSTRUMENT, timeframe=ACCEPTANCE_TIMEFRAME,
        start=ACCEPTANCE_START_UTC, end=ACCEPTANCE_END_UTC, adapter_build_version="pid-006b-acceptance",
    )
    if dataset.record_count == 0:
        pytest.skip("Real HERMES returned zero rows for the pre-selected acceptance window -- cannot proceed honestly")
    return cfg, dataset


def test_real_hermes_dataset_loaded_as_selected_in_advance(real_hermes_dataset) -> None:
    _cfg, dataset = real_hermes_dataset
    assert dataset.instrument == ACCEPTANCE_INSTRUMENT
    assert dataset.timeframe == ACCEPTANCE_TIMEFRAME
    assert dataset.record_count > 0
    assert dataset.actual_first_open_utc >= ACCEPTANCE_START_UTC
    assert dataset.actual_last_open_utc < ACCEPTANCE_END_UTC


def test_zero_cost_mechanical_run_completes_end_to_end_against_real_data(real_hermes_dataset, pg_config) -> None:
    _cfg, dataset = real_hermes_dataset
    _sv, plan, ps, pp, ep, rc, result = _build_and_run(market_dataset=dataset, cost_methodology=ZERO_COST)
    assert result.bars_processed == dataset.record_count
    assert result.decision_stream_hash and result.fill_trade_sequence_hash and result.economic_outcome_hash

    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=plan, parameter_set=ps, execution_policy=ep, partition_policy=pp,
            research_configuration=rc,
        )
        persisted = persist_apollo_result(
            conn, research_configuration=rc, market_dataset=dataset, engine_result=result,
            strategy_title="PID-006B real HERMES acceptance (ZERO_COST)", version_label="v1",
            build_version="pid-006b-acceptance",
        )
    with connection(pg_config) as conn, conn.cursor() as cur:
        cur.execute("SELECT result_kind FROM research_runs WHERE id = %s", (persisted.research_run.id,))
        assert cur.fetchone()["result_kind"] == EvidenceLevel.APOLLO_RESULT.value


def test_non_zero_cost_run_completes_end_to_end_against_the_same_real_data(real_hermes_dataset, pg_config) -> None:
    _cfg, dataset = real_hermes_dataset
    _sv, plan, ps, pp, ep, rc, result = _build_and_run(market_dataset=dataset, cost_methodology=FIXED_MECHANICAL_TEST_COST)
    assert result.bars_processed == dataset.record_count

    with connection(pg_config) as conn:
        persist_research_contracts_chain(
            conn, executable_plan=plan, parameter_set=ps, execution_policy=ep, partition_policy=pp,
            research_configuration=rc,
        )
        persisted = persist_apollo_result(
            conn, research_configuration=rc, market_dataset=dataset, engine_result=result,
            strategy_title="PID-006B real HERMES acceptance (FIXED_MECHANICAL_TEST_COST)", version_label="v1",
            build_version="pid-006b-acceptance",
        )
    with connection(pg_config) as conn, conn.cursor() as cur:
        cur.execute("SELECT result_kind FROM research_runs WHERE id = %s", (persisted.research_run.id,))
        assert cur.fetchone()["result_kind"] == EvidenceLevel.APOLLO_RESULT.value


def test_two_independent_runs_against_real_data_are_deterministic(real_hermes_dataset) -> None:
    """The same real dataset replayed twice (ZERO_COST) reproduces exact
    hashes -- the controlled-fixture determinism proof
    (tests/unit/test_apollo_determinism_and_perturbation.py) repeated once
    against real HERMES data, not just synthetic fixtures."""
    _cfg, dataset = real_hermes_dataset
    _sv1, *_rest1, result_a = _build_and_run(market_dataset=dataset, cost_methodology=ZERO_COST)
    _sv2, *_rest2, result_b = _build_and_run(market_dataset=dataset, cost_methodology=ZERO_COST)
    assert result_a.decision_stream_hash == result_b.decision_stream_hash
    assert result_a.fill_trade_sequence_hash == result_b.fill_trade_sequence_hash
    assert result_a.economic_outcome_hash == result_b.economic_outcome_hash
