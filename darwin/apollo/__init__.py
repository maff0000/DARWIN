"""PID-006B APOLLO Candle Causal Core -- the first real APOLLO backtesting
engine vertical slice.

Scope (first supported semantic subset): XAU_USD, one timeframe, one
`MarketDataset`, ATOMIC entry composition only, LONG direction only,
single position (no pyramiding), fixed research quantity of 1 troy ounce.
Proves APOLLO mechanics, not trading edge -- performance is explicitly
not an acceptance criterion.

See:
- `darwin.apollo.plan_adapter` -- derives APOLLO's engine-native entry
  specification from the compiled `ExecutableStrategyPlan` (never from a
  raw `StrategyVersion` directly -- Central Architecture correction
  CA-006B-1), and the exhaustive supported-semantic-subset gate
  (CA-006B-4).
- `darwin.apollo.preflight` -- the mandatory, independently-re-verified
  preflight (fails closed, before a single bar is processed; re-proves
  every `ResearchConfiguration` axis binding from the actual objects
  being executed -- CA-006B-2).
- `darwin.apollo.signal` -- the engine-native entry-signal shape + the
  live per-bar decision function.
- `darwin.apollo.capability` -- the closed `ExecutionPolicyComponent`
  allowlist for this engine slice (exact full-configuration equality,
  not just id/version -- CA-006B-5).
- `darwin.apollo.economics` -- SL/TP risk-parameter resolution + cost/
  quantity component readers.
- `darwin.apollo.engine` -- the causal replay loop itself (mechanically
  re-verifies the dataset it is given against what preflight bound --
  CA-006B-3; evidence identities bind the relevant upstream identities --
  CA-006B-6).
- `darwin.apollo.persistence` -- the minimal durable `ResearchRun`/
  `EvidenceRecord` persistence this package writes.
"""
from __future__ import annotations

from darwin.apollo.engine import ApolloEngineResult, run_apollo_replay
from darwin.apollo.preflight import PreflightResult, run_preflight
from darwin.hermes.dataset import MarketDataset
from darwin.hermes.instrument_definition import InstrumentDefinition
from darwin.research_contracts.compiler import ExecutableStrategyPlan
from darwin.research_contracts.execution_policy import ExecutionPolicyVersion
from darwin.research_contracts.parameter_set import ParameterSetVersion
from darwin.research_contracts.partition_policy import ResearchPartitionPolicyVersion
from darwin.research_contracts.research_configuration import ResearchConfiguration
from darwin.specification.domain import StrategyVersion

__all__ = [
    "ApolloEngineResult",
    "PreflightResult",
    "run_apollo_candle_causal_core",
    "run_apollo_replay",
    "run_preflight",
]


def run_apollo_candle_causal_core(
    *,
    strategy_version: StrategyVersion,
    executable_plan: ExecutableStrategyPlan,
    parameter_set: ParameterSetVersion,
    execution_policy: ExecutionPolicyVersion,
    partition_policy: ResearchPartitionPolicyVersion,
    market_dataset: MarketDataset,
    research_configuration: ResearchConfiguration,
    instrument_definition: InstrumentDefinition,
) -> ApolloEngineResult:
    """Runs the mandatory preflight, then the causal replay, against the
    given (already independently constructed) configuration objects.
    Fails closed -- zero bars processed -- if preflight rejects the
    configuration; see `darwin.apollo.preflight`/`darwin.apollo.errors`.

    `executable_plan` and `partition_policy` are mandatory, explicit
    inputs (Central Architecture correction CA-006B-2) -- preflight
    independently re-proves that the EXACT objects passed here are the
    ones `research_configuration` is actually bound to; it never infers
    them from `research_configuration` alone.
    """
    preflight_result = run_preflight(
        strategy_version=strategy_version,
        executable_plan=executable_plan,
        parameter_set=parameter_set,
        execution_policy=execution_policy,
        partition_policy=partition_policy,
        market_dataset=market_dataset,
        research_configuration=research_configuration,
        instrument_definition=instrument_definition,
    )
    return run_apollo_replay(preflight_result=preflight_result, market_dataset=market_dataset)
