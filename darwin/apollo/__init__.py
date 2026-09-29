"""PID-006B APOLLO Candle Causal Core -- the first real APOLLO backtesting
engine vertical slice.

Scope (first supported semantic subset): XAU_USD, one timeframe, one
`MarketDataset`, ATOMIC entry composition only, LONG direction only,
single position (no pyramiding), fixed research quantity of 1 troy ounce.
Proves APOLLO mechanics, not trading edge -- performance is explicitly
not an acceptance criterion.

See:
- `darwin.apollo.preflight` -- the mandatory, independently-re-verified
  preflight (fails closed, before a single bar is processed).
- `darwin.apollo.signal` -- the entry-signal capability check + the live
  per-bar decision function.
- `darwin.apollo.capability` -- the closed `ExecutionPolicyComponent`
  allowlist for this engine slice.
- `darwin.apollo.economics` -- SL/TP risk-parameter resolution + cost/
  quantity component readers.
- `darwin.apollo.engine` -- the causal replay loop itself.
- `darwin.apollo.persistence` -- the minimal durable `ResearchRun`/
  `EvidenceRecord` persistence this package writes.
"""
from __future__ import annotations

from darwin.apollo.engine import ApolloEngineResult, run_apollo_replay
from darwin.apollo.preflight import PreflightResult, run_preflight
from darwin.hermes.dataset import MarketDataset
from darwin.hermes.instrument_definition import InstrumentDefinition
from darwin.research_contracts.execution_policy import ExecutionPolicyVersion
from darwin.research_contracts.parameter_set import ParameterSetVersion
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
    parameter_set: ParameterSetVersion,
    execution_policy: ExecutionPolicyVersion,
    market_dataset: MarketDataset,
    research_configuration: ResearchConfiguration,
    instrument_definition: InstrumentDefinition,
) -> ApolloEngineResult:
    """Runs the mandatory preflight, then the causal replay, against the
    given (already independently constructed) configuration objects.
    Fails closed -- zero bars processed -- if preflight rejects the
    configuration; see `darwin.apollo.preflight`/`darwin.apollo.errors`.
    """
    preflight_result = run_preflight(
        strategy_version=strategy_version,
        parameter_set=parameter_set,
        execution_policy=execution_policy,
        market_dataset=market_dataset,
        research_configuration=research_configuration,
        instrument_definition=instrument_definition,
    )
    return run_apollo_replay(preflight_result=preflight_result, market_dataset=market_dataset)
