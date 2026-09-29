"""PID-006B mandatory preflight -- independently re-verified BEFORE a
single bar is replayed. Fails closed with a governed
`InvalidConfigurationError`/`EngineCapabilityBlockedError` (never a bare
crash mid-replay) the instant any check fails; a mismatch here means
`bars_processed == 0`.

Deliberately re-derives every check independently rather than trusting
that `ResearchConfiguration`/`ParameterSetVersion` were constructed
correctly once upstream -- the engine must never trust a configuration
blindly just because it was constructed correctly once (PID-006B
"Mandatory preflight" section, item 7's own instruction, generalised to
every check here).
"""
from __future__ import annotations

from dataclasses import dataclass

from darwin.apollo.capability import check_execution_policy_capability
from darwin.apollo.economics import (
    CostModel,
    QuantityEconomics,
    RiskParameters,
    read_cost_model,
    read_quantity_economics,
    resolve_risk_parameters,
)
from darwin.apollo.errors import InvalidConfigurationError
from darwin.apollo.signal import EntrySignalSpec, check_strategy_capability
from darwin.core.dike import DikeState
from darwin.hermes.dataset import MarketDataset, compute_fingerprint
from darwin.hermes.instrument_definition import InstrumentDefinition
from darwin.research_contracts.execution_policy import ExecutionPolicyVersion
from darwin.research_contracts.input_binding import (
    verify_research_input_binding_fingerprint,
)
from darwin.research_contracts.parameter_set import ParameterSetVersion
from darwin.research_contracts.research_configuration import ResearchConfiguration
from darwin.specification.applicability import InstrumentApplicabilityKind
from darwin.specification.domain import StrategyVersion

#: PID-006B scope: XAU_USD, one timeframe, one MarketDataset -- this engine
#: slice's ONLY supported instrument in v1.
SUPPORTED_INSTRUMENT = "XAU_USD"


@dataclass(frozen=True)
class PreflightResult:
    """Everything the replay loop needs, resolved exactly once, before any
    bar is touched."""

    entry_signal_spec: EntrySignalSpec
    parameter_values: dict[str, object]
    risk_parameters: RiskParameters
    quantity_economics: QuantityEconomics
    cost_model: CostModel


def _check_instrument_applicability(strategy_version: StrategyVersion) -> None:
    """Preflight check #1."""
    applicability = strategy_version.instrument_applicability
    if applicability.kind == InstrumentApplicabilityKind.INSTRUMENT_GENERIC:
        from darwin.apollo.errors import (
            CapabilityBlockContext,
            CapabilityBlockReason,
            EngineCapabilityBlockedError,
        )

        raise EngineCapabilityBlockedError(
            "APOLLO Candle Causal Core v1 supports EXPLICIT_SINGLE/EXPLICIT_SET instrument "
            "applicability only -- INSTRUMENT_GENERIC strategies are not yet evaluable by this "
            "engine slice",
            context=CapabilityBlockContext(
                reason=CapabilityBlockReason.UNSUPPORTED_COMPOSITION_SHAPE,
                subject_ref=strategy_version.strategy_version_id,
                detail=(("instrument_applicability_kind", applicability.kind.value),),
            ),
        )
    if SUPPORTED_INSTRUMENT not in applicability.instrument_ids:
        raise InvalidConfigurationError(
            f"StrategyVersion {strategy_version.strategy_version_id!r} instrument_applicability "
            f"{applicability.instrument_ids!r} does not include {SUPPORTED_INSTRUMENT!r} -- "
            f"this replay request is for an instrument the strategy does not declare itself "
            f"applicable to"
        )


def _check_configuration_instrument(research_configuration: ResearchConfiguration) -> None:
    """Preflight check #2."""
    if research_configuration.instrument_definition_id != SUPPORTED_INSTRUMENT:
        raise InvalidConfigurationError(
            f"ResearchConfiguration.instrument_definition_id "
            f"{research_configuration.instrument_definition_id!r} != {SUPPORTED_INSTRUMENT!r}"
        )


def _check_input_bindings_match_dataset(
    research_configuration: ResearchConfiguration, market_dataset: MarketDataset
) -> None:
    """Preflight check #3. This engine slice replays against exactly ONE
    `MarketDataset` (PID-006B scope) -- `research_configuration` must
    declare exactly one `ResearchInputBinding`, and it must genuinely
    identify the exact loaded `market_dataset` about to be replayed."""
    bindings = research_configuration.research_input_bindings
    if len(bindings) != 1:
        raise InvalidConfigurationError(
            f"APOLLO Candle Causal Core v1 supports exactly one ResearchInputBinding (one "
            f"MarketDataset), got {len(bindings)}"
        )
    binding = bindings[0]
    # Never trust a stored/passed fingerprint at face value -- recompute
    # and compare against the binding's own raw fields first (PID-006A
    # CA-2 discipline, reused here at the APOLLO boundary).
    verify_research_input_binding_fingerprint(binding)
    if binding.governed_dataset_id != market_dataset.dataset_id:
        raise InvalidConfigurationError(
            f"ResearchInputBinding.governed_dataset_id {binding.governed_dataset_id!r} != the "
            f"loaded MarketDataset.dataset_id {market_dataset.dataset_id!r} -- refusing to "
            f"replay against a dataset the configuration never declared as its input"
        )
    if binding.dataset_semantic_fingerprint != market_dataset.fingerprint_sha256:
        raise InvalidConfigurationError(
            f"ResearchInputBinding.dataset_semantic_fingerprint "
            f"{binding.dataset_semantic_fingerprint!r} != the loaded MarketDataset's own "
            f"fingerprint_sha256 {market_dataset.fingerprint_sha256!r}"
        )


def _check_dataset_fingerprint_recomputes(market_dataset: MarketDataset) -> None:
    """Preflight check #4. Independently recomputes the dataset's own
    content fingerprint from its raw arrays via
    `darwin.hermes.dataset.compute_fingerprint` (the exact function
    `build_market_dataset` itself uses) and compares against the stored
    value -- never trusts `fingerprint_sha256` merely because it is
    present."""
    recomputed = compute_fingerprint(
        instrument=market_dataset.instrument,
        instrument_definition_id=market_dataset.instrument_definition_id,
        timeframe=market_dataset.timeframe,
        open_time_epoch_s=market_dataset.open_time_epoch_s,
        open_fp=market_dataset.open_fp,
        high_fp=market_dataset.high_fp,
        low_fp=market_dataset.low_fp,
        close_fp=market_dataset.close_fp,
        volume=market_dataset.volume,
    )
    if recomputed != market_dataset.fingerprint_sha256:
        raise InvalidConfigurationError(
            f"MarketDataset {market_dataset.dataset_id!r} fingerprint_sha256 "
            f"{market_dataset.fingerprint_sha256!r} does not match the fingerprint recomputed "
            f"from its own raw arrays ({recomputed!r}) -- refusing to replay against an "
            f"internally-inconsistent dataset"
        )


def _check_instrument_definition_agreement(
    market_dataset: MarketDataset,
    instrument_definition: InstrumentDefinition,
    research_configuration: ResearchConfiguration,
) -> None:
    """Preflight check #5 -- the documented gotcha: `MarketDataset.
    instrument_definition_id` stores `InstrumentDefinition.fingerprint` (a
    hash), NOT the bare instrument id; `ResearchConfiguration.
    instrument_definition_id` stores the bare id (e.g. "XAU_USD"). Two
    genuinely different comparisons, never conflated."""
    if market_dataset.instrument_definition_id != instrument_definition.fingerprint:
        raise InvalidConfigurationError(
            f"MarketDataset.instrument_definition_id {market_dataset.instrument_definition_id!r} "
            f"!= InstrumentDefinition({instrument_definition.instrument_id!r}).fingerprint "
            f"{instrument_definition.fingerprint!r}"
        )
    if market_dataset.instrument != research_configuration.instrument_definition_id:
        raise InvalidConfigurationError(
            f"MarketDataset.instrument {market_dataset.instrument!r} != "
            f"ResearchConfiguration.instrument_definition_id "
            f"{research_configuration.instrument_definition_id!r}"
        )


def _check_timeframe_agreement(market_dataset: MarketDataset, entry_signal_spec_timeframe: str) -> None:
    """Preflight check #6. This engine slice supports exactly one
    timeframe -- a straightforward equality check, never a capability
    negotiation."""
    if market_dataset.timeframe.value != entry_signal_spec_timeframe:
        raise InvalidConfigurationError(
            f"MarketDataset.timeframe {market_dataset.timeframe.value!r} does not match the "
            f"entry condition's own bound timeframe {entry_signal_spec_timeframe!r} -- APOLLO "
            f"Candle Causal Core v1 supports exactly one timeframe per replay"
        )
    if market_dataset.instrument != SUPPORTED_INSTRUMENT:
        raise InvalidConfigurationError(
            f"MarketDataset.instrument {market_dataset.instrument!r} != {SUPPORTED_INSTRUMENT!r}"
        )


def _check_parameter_set_binding(strategy_version: StrategyVersion, parameter_set: ParameterSetVersion) -> None:
    """Preflight check #7. Independently re-verified here even though
    `build_research_configuration` already enforces this once at
    construction time -- the engine never trusts a configuration blindly
    just because it was constructed correctly once upstream."""
    if parameter_set.source_semantic_fingerprint != strategy_version.semantic_fingerprint:
        raise InvalidConfigurationError(
            f"ParameterSetVersion.source_semantic_fingerprint "
            f"{parameter_set.source_semantic_fingerprint!r} != "
            f"StrategyVersion.semantic_fingerprint {strategy_version.semantic_fingerprint!r}"
        )


def _check_dike_disabled(research_configuration: ResearchConfiguration) -> None:
    """Preflight check #9. `DIKE_GUARDED` is rejected outright for this
    engine slice."""
    if research_configuration.dike_state != DikeState.DISABLED:
        raise InvalidConfigurationError(
            f"APOLLO Candle Causal Core v1 requires dike_state == DIKE_DISABLED, got "
            f"{research_configuration.dike_state.value!r}"
        )


def run_preflight(
    *,
    strategy_version: StrategyVersion,
    parameter_set: ParameterSetVersion,
    execution_policy: ExecutionPolicyVersion,
    market_dataset: MarketDataset,
    research_configuration: ResearchConfiguration,
    instrument_definition: InstrumentDefinition,
) -> PreflightResult:
    """Runs every PID-006B mandatory preflight check, in order, raising on
    the first failure -- BEFORE touching a single bar. Returns the
    resolved `PreflightResult` the replay loop needs on success."""
    entry_signal_spec = check_strategy_capability(strategy_version)  # capability check (composition shape)

    _check_instrument_applicability(strategy_version)  # check #1
    _check_configuration_instrument(research_configuration)  # check #2
    _check_input_bindings_match_dataset(research_configuration, market_dataset)  # check #3
    _check_dataset_fingerprint_recomputes(market_dataset)  # check #4
    _check_instrument_definition_agreement(market_dataset, instrument_definition, research_configuration)  # check #5
    _check_timeframe_agreement(market_dataset, entry_signal_spec_timeframe=_entry_condition_timeframe(strategy_version))  # check #6
    _check_parameter_set_binding(strategy_version, parameter_set)  # check #7
    check_execution_policy_capability(execution_policy)  # check #8 (capability)
    _check_dike_disabled(research_configuration)  # check #9

    parameter_values: dict[str, object] = dict(parameter_set.assignments)
    risk_parameters = resolve_risk_parameters(parameter_values)
    quantity_economics = read_quantity_economics(execution_policy.quantity_economic_methodology)
    cost_model = read_cost_model(execution_policy.cost_methodology)

    return PreflightResult(
        entry_signal_spec=entry_signal_spec,
        parameter_values=parameter_values,
        risk_parameters=risk_parameters,
        quantity_economics=quantity_economics,
        cost_model=cost_model,
    )


def _entry_condition_timeframe(strategy_version: StrategyVersion) -> str:
    """`strategy_version.composition` has already been proven (by
    `check_strategy_capability`, called before this helper is ever
    reached in `run_preflight`) to be a bare `AtomicCondition` -- reads
    its bound timeframe code (e.g. "H1") directly."""
    return strategy_version.composition.timeframe.code
