"""PID-006B minimal durable persistence.

Deliberately narrow (Architect's own instruction, "keep this genuinely
minimal"): one `ResearchRun` row per engine execution
(`result_kind=APOLLO_RESULT`, ALWAYS -- both the ZERO_COST mechanical run
and the non-zero-cost run), bound to the exact persisted
`ResearchConfiguration` via `configuration_fingerprint`, plus durable
identity/summary evidence via the EXISTING `evidence_records` table. No
bar-by-bar row, no new event store, no competing market-data store, no
broad APOLLO analytics schema.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import psycopg

from darwin.apollo.engine import ApolloEngineResult
from darwin.apollo.errors import InvalidConfigurationError
from darwin.core.dike import DikeState
from darwin.core.evidence import EvidenceLevel
from darwin.core.identities import new_id
from darwin.hermes.dataset import MarketDataset
from darwin.research_contracts.compiler import ExecutableStrategyPlan
from darwin.research_contracts.execution_policy import ExecutionPolicyVersion
from darwin.research_contracts.parameter_set import ParameterSetVersion
from darwin.research_contracts.partition_policy import ResearchPartitionPolicyVersion
from darwin.research_contracts.research_configuration import ResearchConfiguration
from darwin.research_store.models import (
    EvidenceRecord,
    MarketDatasetRecord,
    ResearchRun,
)
from darwin.research_store.repositories import (
    EvidenceRecordRepository,
    MarketDatasetRepository,
    ResearchRunRepository,
)
from darwin.research_store.research_contracts_repositories import (
    CompiledStrategyPlanRepository,
    ExecutionPolicyVersionRepository,
    ParameterSetVersionRepository,
    ResearchConfigurationRepository,
    ResearchPartitionPolicyVersionRepository,
)
from darwin.research_store.run_binding import create_research_run


@dataclass(frozen=True)
class PersistedApolloRun:
    research_run: ResearchRun
    evidence_records: tuple[EvidenceRecord, ...]


def persist_research_contracts_chain(
    conn: psycopg.Connection,
    *,
    executable_plan: ExecutableStrategyPlan,
    parameter_set: ParameterSetVersion,
    execution_policy: ExecutionPolicyVersion,
    partition_policy: ResearchPartitionPolicyVersion,
    research_configuration: ResearchConfiguration,
) -> None:
    """Persists the full PID-006A research-contracts identity chain this
    run's `configuration_fingerprint` points at. Every repository here
    uses `ON CONFLICT (fingerprint) DO NOTHING` (PID-006A migration 0012),
    so calling this twice for the identical configuration is a safe,
    idempotent no-op -- never a duplicate, never an error."""
    CompiledStrategyPlanRepository(conn).create(executable_plan)
    ParameterSetVersionRepository(conn).create(parameter_set)
    ExecutionPolicyVersionRepository(conn).create(execution_policy)
    ResearchPartitionPolicyVersionRepository(conn).create(partition_policy)
    ResearchConfigurationRepository(conn).create(research_configuration)


def persist_market_dataset_if_absent(conn: psycopg.Connection, market_dataset: MarketDataset) -> None:
    if MarketDatasetRepository(conn).get(market_dataset.dataset_id) is not None:
        return
    MarketDatasetRepository(conn).create(
        MarketDatasetRecord(
            id=market_dataset.dataset_id,
            instrument=market_dataset.instrument,
            instrument_definition_id=market_dataset.instrument_definition_id,
            timeframe=market_dataset.timeframe.value,
            requested_start_utc=market_dataset.requested_start_utc,
            requested_end_utc=market_dataset.requested_end_utc,
            actual_first_open_utc=market_dataset.actual_first_open_utc,
            actual_last_open_utc=market_dataset.actual_last_open_utc,
            record_count=market_dataset.record_count,
            fingerprint_sha256=market_dataset.fingerprint_sha256,
            hermes_contract_version=market_dataset.hermes_contract_version,
            hermes_contract_commit=market_dataset.hermes_contract_commit,
            adapter_build_version=market_dataset.adapter_build_version,
            gap_summary=market_dataset.gap_summary.as_dict(),
            loaded_at_utc=market_dataset.loaded_at_utc,
        )
    )


def persist_apollo_result(
    conn: psycopg.Connection,
    *,
    research_configuration: ResearchConfiguration,
    market_dataset: MarketDataset,
    engine_result: ApolloEngineResult,
    strategy_title: str,
    version_label: str,
    build_version: str,
) -> PersistedApolloRun:
    """Persists one `ResearchRun` (`result_kind=EvidenceLevel.APOLLO_RESULT`
    -- never `APOLLO_PROOF`, regardless of which cost policy was used;
    this package implements no proof-eligibility gating) plus one
    `EvidenceRecord` carrying the three SHA-256 identities and a compact
    result summary as JSON in `reference`, following the same convention
    `darwin.research_store.repositories.EvidenceRecordRepository.create`
    already uses for every other evidence row in this schema.

    CA-006B adversarial test 14: refuses to pair `engine_result` with a
    `research_configuration`/`market_dataset` other than the ones that
    actually produced it -- `engine_result.bound_*` identities (set by
    `darwin.apollo.engine.run_apollo_replay` from the exact
    `PreflightResult` it ran against) must agree with the objects passed
    to THIS call.
    """
    if engine_result.bound_dataset_id != market_dataset.dataset_id:
        raise InvalidConfigurationError(
            f"ApolloEngineResult was produced against MarketDataset.dataset_id "
            f"{engine_result.bound_dataset_id!r}, not the one passed to persist_apollo_result "
            f"({market_dataset.dataset_id!r}) -- refusing to persist a mismatched pairing"
        )
    if engine_result.bound_dataset_fingerprint != market_dataset.fingerprint_sha256:
        raise InvalidConfigurationError(
            "ApolloEngineResult was produced against a MarketDataset with a different content "
            "fingerprint than the one passed to persist_apollo_result -- refusing to persist a "
            "mismatched pairing"
        )
    if engine_result.bound_research_configuration_fingerprint != research_configuration.fingerprint:
        raise InvalidConfigurationError(
            f"ApolloEngineResult was produced against ResearchConfiguration.fingerprint "
            f"{engine_result.bound_research_configuration_fingerprint!r}, not the one passed to "
            f"persist_apollo_result ({research_configuration.fingerprint!r}) -- refusing to "
            f"persist a mismatched pairing"
        )

    persist_market_dataset_if_absent(conn, market_dataset)

    run = create_research_run(
        result_kind=EvidenceLevel.APOLLO_RESULT,
        engine="APOLLO_CANDLE_CAUSAL_CORE",
        build_version=build_version,
        status="COMPLETED",
        instrument=market_dataset.instrument,
        instrument_definition_id=market_dataset.instrument_definition_id,
        timeframe=market_dataset.timeframe,
        run_type="APOLLO_CANDLE_CAUSAL_REPLAY",
        strategy_title=strategy_title,
        version_label=version_label,
        dataset_id=market_dataset.dataset_id,
        dataset_instrument=market_dataset.instrument,
        dataset_timeframe=market_dataset.timeframe,
        dataset_instrument_definition_id=market_dataset.instrument_definition_id,
        configuration_fingerprint=research_configuration.fingerprint,
        dike_state=DikeState.DISABLED,
    )
    ResearchRunRepository(conn).create(run)

    summary = {
        "bars_processed": engine_result.bars_processed,
        "trade_count": len(engine_result.trades),
        "terminal_position_state": engine_result.terminal_position_state,
        "starting_capital_usd": engine_result.starting_capital_usd,
        "final_balance_usd": engine_result.final_balance_usd,
        "final_equity_usd": engine_result.final_equity_usd,
        "peak_equity_usd": engine_result.peak_equity_usd,
        "max_drawdown_usd": engine_result.max_drawdown_usd,
        "decision_stream_hash": engine_result.decision_stream_hash,
        "fill_trade_sequence_hash": engine_result.fill_trade_sequence_hash,
        "economic_outcome_hash": engine_result.economic_outcome_hash,
        "evidence_envelope_hash": engine_result.evidence_envelope_hash,
        "research_configuration_fingerprint": research_configuration.fingerprint,
    }
    record = EvidenceRecord(
        id=new_id(),
        run_id=run.id,
        evidence_level=EvidenceLevel.APOLLO_RESULT,
        reference=json.dumps(summary, sort_keys=True),
    )
    EvidenceRecordRepository(conn).create(record)

    return PersistedApolloRun(research_run=run, evidence_records=(record,))
