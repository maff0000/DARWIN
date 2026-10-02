"""PID-006B mandatory preflight -- independently re-verified BEFORE a
single bar is replayed. Fails closed with a governed
`InvalidConfigurationError`/`PersistedFingerprintMismatchError`/
`EngineCapabilityBlockedError` (never a bare crash mid-replay) the
instant any check fails; a mismatch here means `bars_processed == 0`.

Central Architecture correction CA-006B-2: this module never trusts that
a `ResearchConfiguration` was constructed correctly once upstream, nor
that any of its bound objects (`StrategyVersion`, `ExecutableStrategyPlan`,
`ParameterSetVersion`, `ExecutionPolicyVersion`,
`ResearchPartitionPolicyVersion`) are internally self-consistent merely
because they were handed to this function together. Every one of
`ResearchConfiguration`'s own recorded axis fingerprints is independently
RECOMPUTED from the actual object being executed and compared against
the stored value -- the same "recompute, never trust the stored
fingerprint" discipline `darwin.research_contracts` itself already uses
throughout (see e.g.
`darwin.research_store.research_contracts_repositories`'s own
`get_by_fingerprint` methods). This is what makes it impossible to build
a `ResearchConfiguration` against `ParameterSet A` and then execute it
against `ParameterSet B` merely because both happen to belong to the same
`StrategyVersion` -- same for every other axis.
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
from darwin.apollo.errors import (
    InvalidConfigurationError,
    PersistedFingerprintMismatchError,
)
from darwin.apollo.plan_adapter import (
    check_plan_capability,
    plan_condition_timeframe_code,
)
from darwin.apollo.signal import EntrySignalSpec
from darwin.core.dike import DikeState
from darwin.hermes.dataset import MarketDataset, compute_fingerprint
from darwin.hermes.instrument_definition import InstrumentDefinition
from darwin.research_contracts.compiler import (
    ExecutableStrategyPlan,
    compute_plan_fingerprint,
)
from darwin.research_contracts.execution_policy import (
    ExecutionPolicyVersion,
    compute_execution_policy_fingerprint,
)
from darwin.research_contracts.input_binding import (
    verify_research_input_binding_fingerprint,
)
from darwin.research_contracts.parameter_set import (
    ParameterSetVersion,
    compute_parameter_set_fingerprint,
)
from darwin.research_contracts.partition_policy import (
    ResearchPartitionPolicyVersion,
    compute_research_partition_policy_fingerprint,
)
from darwin.research_contracts.research_configuration import (
    ResearchConfiguration,
    compute_research_configuration_fingerprint,
)
from darwin.specification.domain import SEMANTIC_FIELD_NAMES, StrategyVersion
from darwin.specification.fingerprint import canonical_hash, canonicalize

#: PID-006B scope: XAU_USD, one timeframe, one MarketDataset -- this engine
#: slice's ONLY supported instrument in v1.
SUPPORTED_INSTRUMENT = "XAU_USD"

_EXECUTION_POLICY_AXES: tuple[str, ...] = (
    "timing_methodology",
    "price_fill_methodology",
    "intrabar_resolution_methodology",
    "cost_methodology",
    "quantity_economic_methodology",
    "session_force_flat_methodology",
)


@dataclass(frozen=True)
class PreflightResult:
    """Everything the replay loop needs, resolved exactly once, before any
    bar is touched.

    CA-006B-3/CA-006B-6: carries the EXACT bound identities preflight
    independently proved to agree with each other -- `market_dataset`
    passed to `darwin.apollo.engine.run_apollo_replay` is mechanically
    checked against `bound_dataset_id`/`bound_dataset_fingerprint` before
    bar 0, and every fingerprint below is embedded into the engine's own
    evidence hashes so a change to any upstream identity remains
    scientifically distinguishable even when the numeric replay output
    happens to come out identical.
    """

    entry_signal_spec: EntrySignalSpec
    parameter_values: dict[str, object]
    risk_parameters: RiskParameters
    quantity_economics: QuantityEconomics
    cost_model: CostModel
    bound_dataset_id: str
    bound_dataset_fingerprint: str
    research_configuration_fingerprint: str
    strategy_semantic_fingerprint: str
    executable_strategy_plan_fingerprint: str
    parameter_set_fingerprint: str
    execution_policy_fingerprint: str
    research_partition_policy_fingerprint: str
    instrument_definition_fingerprint: str


def _recompute_strategy_semantic_fingerprint(strategy_version: StrategyVersion) -> str:
    """Independently recomputes `StrategyVersion.semantic_fingerprint`
    from the object's own current field values, via the exact same
    `semantic_payload()` + `canonical_hash` discipline `finalise()` itself
    used to produce it originally -- never trusts the stored
    `.semantic_fingerprint` field at face value."""
    return canonical_hash(strategy_version.semantic_payload())


def _check_configuration_instrument(
    research_configuration: ResearchConfiguration, instrument_definition: InstrumentDefinition
) -> None:
    """Preflight check #2, widened per CA-006B-2 bullets 4/5: the
    configuration's recorded instrument identity must agree with BOTH the
    fixed engine constant AND the actual `InstrumentDefinition` object
    being executed against."""
    if research_configuration.instrument_definition_id != SUPPORTED_INSTRUMENT:
        raise InvalidConfigurationError(
            f"ResearchConfiguration.instrument_definition_id "
            f"{research_configuration.instrument_definition_id!r} != {SUPPORTED_INSTRUMENT!r}"
        )
    if research_configuration.instrument_definition_id != instrument_definition.instrument_id:
        raise InvalidConfigurationError(
            f"ResearchConfiguration.instrument_definition_id "
            f"{research_configuration.instrument_definition_id!r} != the actual "
            f"InstrumentDefinition.instrument_id {instrument_definition.instrument_id!r} being executed"
        )
    if research_configuration.instrument_definition_fingerprint != instrument_definition.fingerprint:
        raise InvalidConfigurationError(
            f"ResearchConfiguration.instrument_definition_fingerprint "
            f"{research_configuration.instrument_definition_fingerprint!r} != the actual "
            f"InstrumentDefinition.fingerprint {instrument_definition.fingerprint!r} being executed"
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
        raise PersistedFingerprintMismatchError(
            f"MarketDataset {market_dataset.dataset_id!r} fingerprint_sha256 "
            f"{market_dataset.fingerprint_sha256!r} does not match the fingerprint recomputed "
            f"from its own raw arrays ({recomputed!r}) -- refusing to replay against an "
            f"internally-inconsistent dataset"
        )


def _check_instrument_definition_agreement(
    market_dataset: MarketDataset, instrument_definition: InstrumentDefinition
) -> None:
    """Preflight check #5 -- the documented gotcha: `MarketDataset.
    instrument_definition_id` stores `InstrumentDefinition.fingerprint` (a
    hash), NOT the bare instrument id. A genuinely different comparison
    from `_check_configuration_instrument` above, never conflated."""
    if market_dataset.instrument_definition_id != instrument_definition.fingerprint:
        raise InvalidConfigurationError(
            f"MarketDataset.instrument_definition_id {market_dataset.instrument_definition_id!r} "
            f"!= InstrumentDefinition({instrument_definition.instrument_id!r}).fingerprint "
            f"{instrument_definition.fingerprint!r}"
        )
    if market_dataset.instrument != SUPPORTED_INSTRUMENT:
        raise InvalidConfigurationError(
            f"MarketDataset.instrument {market_dataset.instrument!r} != {SUPPORTED_INSTRUMENT!r}"
        )


def _check_timeframe_agreement(market_dataset: MarketDataset, condition_timeframe_code: str) -> None:
    """Preflight check #6. This engine slice supports exactly one
    timeframe -- a straightforward equality check, never a capability
    negotiation. `condition_timeframe_code` is read from the COMPILED
    PLAN (via `plan_adapter.plan_condition_timeframe_code`), never from
    the raw `StrategyVersion` (CA-006B-1)."""
    if market_dataset.timeframe.value != condition_timeframe_code:
        raise InvalidConfigurationError(
            f"MarketDataset.timeframe {market_dataset.timeframe.value!r} does not match the "
            f"compiled plan's own bound timeframe {condition_timeframe_code!r} -- APOLLO Candle "
            f"Causal Core v1 supports exactly one timeframe per replay"
        )


def _check_dike_disabled(research_configuration: ResearchConfiguration) -> None:
    """Preflight check #9. `DIKE_GUARDED` is rejected outright for this
    engine slice."""
    if research_configuration.dike_state != DikeState.DISABLED:
        raise InvalidConfigurationError(
            f"APOLLO Candle Causal Core v1 requires dike_state == DIKE_DISABLED, got "
            f"{research_configuration.dike_state.value!r}"
        )


def _check_strategy_plan_provenance(strategy_version: StrategyVersion, executable_plan: ExecutableStrategyPlan, *, strategy_semantic_fingerprint: str) -> None:
    """CA-006B-1: `StrategyVersion` is supplied alongside the plan ONLY
    for this provenance/integrity cross-check -- never as the source of
    executable meaning. `strategy_semantic_fingerprint` is the
    INDEPENDENTLY RECOMPUTED value (see `_recompute_strategy_semantic_fingerprint`),
    not the possibly-tampered stored field."""
    if executable_plan.source_strategy_version_id != strategy_version.strategy_version_id:
        raise InvalidConfigurationError(
            f"ExecutableStrategyPlan.source_strategy_version_id "
            f"{executable_plan.source_strategy_version_id!r} != "
            f"StrategyVersion.strategy_version_id {strategy_version.strategy_version_id!r}"
        )
    if executable_plan.source_semantic_fingerprint != strategy_semantic_fingerprint:
        raise InvalidConfigurationError(
            f"ExecutableStrategyPlan.source_semantic_fingerprint "
            f"{executable_plan.source_semantic_fingerprint!r} != the independently-recomputed "
            f"StrategyVersion.semantic_fingerprint {strategy_semantic_fingerprint!r}"
        )


def _check_plan_payload_matches_strategy_version(
    strategy_version: StrategyVersion, executable_plan: ExecutableStrategyPlan
) -> None:
    """CA-006B-7: proving `source_semantic_fingerprint` and `fingerprint`
    both "match" is NOT sufficient -- a caller can construct a plan whose
    `semantic_payload` has been altered and then correctly recompute
    `fingerprint` over that ALTERED payload (`compute_plan_fingerprint`
    just hashes whatever payload it is handed). This independently
    recomputes the EXACT canonical semantic payload
    `CanonicalStrategyCompiler.compile()` itself would have produced from
    `strategy_version` -- via the same `SEMANTIC_FIELD_NAMES`/
    `canonicalize` construction, reused verbatim, never a second
    compiler -- and compares it field-for-field against the plan's own
    `semantic_payload`. `darwin/research_contracts/compiler.py` is never
    touched or re-implemented; this only reads `StrategyVersion` and the
    plan's already-produced payload."""
    recomputed_payload = {name: canonicalize(getattr(strategy_version, name)) for name in SEMANTIC_FIELD_NAMES}
    if recomputed_payload != executable_plan.semantic_payload:
        mismatched_fields = sorted(
            name for name in SEMANTIC_FIELD_NAMES if recomputed_payload.get(name) != executable_plan.semantic_payload.get(name)
        )
        raise InvalidConfigurationError(
            f"ExecutableStrategyPlan.semantic_payload does not match the canonical semantic "
            f"payload independently recomputed from the supplied StrategyVersion -- mismatched "
            f"field(s): {mismatched_fields} -- the plan's source-identity fields may agree while "
            f"its actual compiled content has been altered; APOLLO never executes a plan whose "
            f"payload cannot be reproduced from the StrategyVersion it claims to come from"
        )


def _check_historical_depth(market_dataset: MarketDataset, *, required_historical_depth_bars: int) -> None:
    """CA-006B-8: mandatory historical depth is honoured before replay --
    PID-006B supports `BARS` depth units only (enforced in
    `plan_adapter._check_data_requirements`, which also returns the
    required count read from the plan); here, independently, the
    supplied `MarketDataset` must actually contain at least that many
    governed bars, or replay fails closed before bar 0."""
    if market_dataset.record_count < required_historical_depth_bars:
        raise InvalidConfigurationError(
            f"StrategyVersion's data requirement needs at least {required_historical_depth_bars} "
            f"bars of historical depth, but the supplied MarketDataset only has "
            f"{market_dataset.record_count} -- refusing to replay against an insufficient dataset"
        )


def _recompute_and_check_plan_fingerprint(
    executable_plan: ExecutableStrategyPlan, *, strategy_semantic_fingerprint: str, research_configuration: ResearchConfiguration
) -> str:
    """CA-006B-2 bullet 2: recomputes `ExecutableStrategyPlan.fingerprint`
    via `compute_plan_fingerprint` -- both a self-consistency check
    (the plan's own stored fingerprint must match a recompute from its
    own fields) and an axis-binding check (that recomputed value must
    match what `research_configuration` claims to be bound to). Returns
    the recomputed fingerprint for downstream re-use (e.g. the research-
    configuration self-consistency recompute)."""
    recomputed = compute_plan_fingerprint(
        source_semantic_fingerprint=strategy_semantic_fingerprint,
        compiler_id=executable_plan.compiler_id,
        compiler_version=executable_plan.compiler_version,
        plan_schema_version=executable_plan.plan_schema_version,
        semantic_payload=executable_plan.semantic_payload,
    )
    if recomputed != executable_plan.fingerprint:
        raise PersistedFingerprintMismatchError(
            f"ExecutableStrategyPlan.fingerprint {executable_plan.fingerprint!r} does not match "
            f"the fingerprint recomputed from its own fields ({recomputed!r})"
        )
    if recomputed != research_configuration.executable_strategy_plan_fingerprint:
        raise InvalidConfigurationError(
            f"The ExecutableStrategyPlan actually being executed has fingerprint {recomputed!r}, "
            f"which does not match ResearchConfiguration.executable_strategy_plan_fingerprint "
            f"{research_configuration.executable_strategy_plan_fingerprint!r} -- this "
            f"configuration was never bound to this plan"
        )
    return recomputed


def _recompute_and_check_parameter_set_fingerprint(
    parameter_set: ParameterSetVersion, *, strategy_semantic_fingerprint: str, research_configuration: ResearchConfiguration
) -> str:
    """CA-006B-2 bullet 3 / adversarial test 1: `ResearchConfiguration`
    built with ParameterSet A must never be executable with ParameterSet
    B, merely because both belong to the same `StrategyVersion`."""
    if parameter_set.source_semantic_fingerprint != strategy_semantic_fingerprint:
        raise InvalidConfigurationError(
            f"ParameterSetVersion.source_semantic_fingerprint "
            f"{parameter_set.source_semantic_fingerprint!r} != the independently-recomputed "
            f"StrategyVersion.semantic_fingerprint {strategy_semantic_fingerprint!r}"
        )
    recomputed = compute_parameter_set_fingerprint(
        source_semantic_fingerprint=strategy_semantic_fingerprint, assignments=parameter_set.assignments
    )
    if recomputed != parameter_set.fingerprint:
        raise PersistedFingerprintMismatchError(
            f"ParameterSetVersion.fingerprint {parameter_set.fingerprint!r} does not match the "
            f"fingerprint recomputed from its own fields ({recomputed!r})"
        )
    if recomputed != research_configuration.parameter_set_fingerprint:
        raise InvalidConfigurationError(
            f"The ParameterSetVersion actually being executed has fingerprint {recomputed!r}, "
            f"which does not match ResearchConfiguration.parameter_set_fingerprint "
            f"{research_configuration.parameter_set_fingerprint!r} -- this configuration was "
            f"never bound to this exact parameter set (ParameterSet A/B substitution)"
        )
    return recomputed


def _recompute_and_check_execution_policy_fingerprint(
    execution_policy: ExecutionPolicyVersion, *, research_configuration: ResearchConfiguration
) -> str:
    """CA-006B-2 bullet 7 / adversarial test 2: same discipline as
    parameter sets, for the execution policy axis."""
    axes = {axis: getattr(execution_policy, axis) for axis in _EXECUTION_POLICY_AXES}
    recomputed = compute_execution_policy_fingerprint(**axes)
    if recomputed != execution_policy.fingerprint:
        raise PersistedFingerprintMismatchError(
            f"ExecutionPolicyVersion.fingerprint {execution_policy.fingerprint!r} does not match "
            f"the fingerprint recomputed from its own fields ({recomputed!r})"
        )
    if recomputed != research_configuration.execution_policy_fingerprint:
        raise InvalidConfigurationError(
            f"The ExecutionPolicyVersion actually being executed has fingerprint {recomputed!r}, "
            f"which does not match ResearchConfiguration.execution_policy_fingerprint "
            f"{research_configuration.execution_policy_fingerprint!r} -- this configuration was "
            f"never bound to this exact execution policy"
        )
    return recomputed


def _recompute_and_check_partition_policy_fingerprint(
    partition_policy: ResearchPartitionPolicyVersion, *, research_configuration: ResearchConfiguration
) -> str:
    """CA-006B-2 bullet 8."""
    verify_research_input_binding_fingerprint(partition_policy.input_binding)
    recomputed = compute_research_partition_policy_fingerprint(
        role=partition_policy.role, input_binding=partition_policy.input_binding
    )
    if recomputed != partition_policy.fingerprint:
        raise PersistedFingerprintMismatchError(
            f"ResearchPartitionPolicyVersion.fingerprint {partition_policy.fingerprint!r} does "
            f"not match the fingerprint recomputed from its own fields ({recomputed!r})"
        )
    if recomputed != research_configuration.research_partition_policy_fingerprint:
        raise InvalidConfigurationError(
            f"The ResearchPartitionPolicyVersion actually being executed has fingerprint "
            f"{recomputed!r}, which does not match "
            f"ResearchConfiguration.research_partition_policy_fingerprint "
            f"{research_configuration.research_partition_policy_fingerprint!r}"
        )
    bound_fingerprints = {binding.fingerprint for binding in research_configuration.research_input_bindings}
    if partition_policy.input_binding.fingerprint not in bound_fingerprints:
        raise InvalidConfigurationError(
            "ResearchPartitionPolicyVersion.input_binding is not one of "
            "ResearchConfiguration.research_input_bindings"
        )
    return recomputed


def _check_research_configuration_self_consistency(
    research_configuration: ResearchConfiguration,
    *,
    strategy_semantic_fingerprint: str,
    executable_strategy_plan_fingerprint: str,
    parameter_set_fingerprint: str,
    execution_policy_fingerprint: str,
    research_partition_policy_fingerprint: str,
) -> None:
    """CA-006B-2 final bullet / adversarial test 5: independently
    recomputes `ResearchConfiguration.fingerprint` itself from its own
    raw, STORED axis fields via `compute_research_configuration_fingerprint`
    and rejects if it does not match the stored value -- catches a
    stale/tampered `ResearchConfiguration.fingerprint`. This is deliberately
    SEPARATE from (and in addition to) the axis-by-axis cross-checks
    above, each of which instead compares a freshly-recomputed fingerprint
    from the ACTUAL object being executed against what
    `research_configuration` claims (already performed by the `_recompute_and_check_*`
    helpers above, whose arguments are passed in here purely for the
    direct equality assertions against `research_configuration`'s own
    stored fields -- defence in depth, not a redundant no-op)."""
    recomputed_self = compute_research_configuration_fingerprint(
        configuration_schema_version=research_configuration.configuration_schema_version,
        strategy_semantic_fingerprint=research_configuration.strategy_semantic_fingerprint,
        executable_strategy_plan_fingerprint=research_configuration.executable_strategy_plan_fingerprint,
        parameter_set_fingerprint=research_configuration.parameter_set_fingerprint,
        instrument_definition_id=research_configuration.instrument_definition_id,
        instrument_definition_fingerprint=research_configuration.instrument_definition_fingerprint,
        research_input_bindings=research_configuration.research_input_bindings,
        research_partition_policy_fingerprint=research_configuration.research_partition_policy_fingerprint,
        execution_policy_fingerprint=research_configuration.execution_policy_fingerprint,
        dike_state=research_configuration.dike_state,
        dike_policy_fingerprint=research_configuration.dike_policy_fingerprint,
        required_derived_algorithm_identities=research_configuration.required_derived_algorithm_identities,
    )
    if recomputed_self != research_configuration.fingerprint:
        raise PersistedFingerprintMismatchError(
            f"ResearchConfiguration.fingerprint {research_configuration.fingerprint!r} does not "
            f"match the fingerprint recomputed from its own stored axis fields "
            f"({recomputed_self!r}) -- refusing to trust a stale/tampered configuration"
        )

    # Defence in depth: the axis-by-axis checks above already compared
    # each FRESH recompute (from the actual object being executed)
    # against research_configuration's stored field; re-assert the same
    # equalities here as one explicit, auditable block.
    if research_configuration.strategy_semantic_fingerprint != strategy_semantic_fingerprint:
        raise InvalidConfigurationError("ResearchConfiguration.strategy_semantic_fingerprint axis mismatch")
    if research_configuration.executable_strategy_plan_fingerprint != executable_strategy_plan_fingerprint:
        raise InvalidConfigurationError("ResearchConfiguration.executable_strategy_plan_fingerprint axis mismatch")
    if research_configuration.parameter_set_fingerprint != parameter_set_fingerprint:
        raise InvalidConfigurationError("ResearchConfiguration.parameter_set_fingerprint axis mismatch")
    if research_configuration.execution_policy_fingerprint != execution_policy_fingerprint:
        raise InvalidConfigurationError("ResearchConfiguration.execution_policy_fingerprint axis mismatch")
    if research_configuration.research_partition_policy_fingerprint != research_partition_policy_fingerprint:
        raise InvalidConfigurationError("ResearchConfiguration.research_partition_policy_fingerprint axis mismatch")


def run_preflight(
    *,
    strategy_version: StrategyVersion,
    executable_plan: ExecutableStrategyPlan,
    parameter_set: ParameterSetVersion,
    execution_policy: ExecutionPolicyVersion,
    partition_policy: ResearchPartitionPolicyVersion,
    market_dataset: MarketDataset,
    research_configuration: ResearchConfiguration,
    instrument_definition: InstrumentDefinition,
) -> PreflightResult:
    """Runs every PID-006B mandatory preflight check, in order, raising on
    the first failure -- BEFORE touching a single bar. Returns the
    resolved `PreflightResult` the replay loop needs on success.

    `executable_plan` and `partition_policy` are now mandatory explicit
    inputs (CA-006B-2): the exact objects claimed by
    `research_configuration` must be independently reproven, never merely
    assumed from `research_configuration` alone.
    """
    # CA-006B-1: the entry specification is derived EXCLUSIVELY from the
    # compiled plan's own semantic_payload (capability check #8, strategy-shape half).
    resolved_plan_capability = check_plan_capability(executable_plan)
    entry_signal_spec = resolved_plan_capability.entry_signal_spec
    condition_timeframe_code = plan_condition_timeframe_code(executable_plan)

    # Independently recompute StrategyVersion's own semantic identity --
    # never trust the stored .semantic_fingerprint field at face value.
    strategy_semantic_fingerprint = _recompute_strategy_semantic_fingerprint(strategy_version)
    _check_strategy_plan_provenance(strategy_version, executable_plan, strategy_semantic_fingerprint=strategy_semantic_fingerprint)
    # CA-006B-7: source-identity agreement alone is insufficient -- prove
    # the plan's ACTUAL semantic_payload content matches what compiling
    # strategy_version would really produce, not merely that its
    # source-identity fields and self-consistent fingerprint agree.
    _check_plan_payload_matches_strategy_version(strategy_version, executable_plan)

    _check_configuration_instrument(research_configuration, instrument_definition)  # check #2 (+ CA-006B-2 bullets 4/5)
    _check_input_bindings_match_dataset(research_configuration, market_dataset)  # check #3
    _check_dataset_fingerprint_recomputes(market_dataset)  # check #4
    _check_instrument_definition_agreement(market_dataset, instrument_definition)  # check #5
    _check_timeframe_agreement(market_dataset, condition_timeframe_code)  # check #6
    _check_historical_depth(market_dataset, required_historical_depth_bars=resolved_plan_capability.required_historical_depth_bars)  # CA-006B-8

    executable_strategy_plan_fingerprint = _recompute_and_check_plan_fingerprint(
        executable_plan, strategy_semantic_fingerprint=strategy_semantic_fingerprint, research_configuration=research_configuration
    )
    parameter_set_fingerprint = _recompute_and_check_parameter_set_fingerprint(
        parameter_set, strategy_semantic_fingerprint=strategy_semantic_fingerprint, research_configuration=research_configuration
    )  # check #7 + CA-006B-2 bullet 3 / adversarial test 1
    execution_policy_fingerprint = _recompute_and_check_execution_policy_fingerprint(
        execution_policy, research_configuration=research_configuration
    )  # CA-006B-2 bullet 7 / adversarial test 2
    research_partition_policy_fingerprint = _recompute_and_check_partition_policy_fingerprint(
        partition_policy, research_configuration=research_configuration
    )  # CA-006B-2 bullet 8

    check_execution_policy_capability(execution_policy)  # check #8 (capability, exact-configuration per CA-006B-5)

    _check_research_configuration_self_consistency(
        research_configuration,
        strategy_semantic_fingerprint=strategy_semantic_fingerprint,
        executable_strategy_plan_fingerprint=executable_strategy_plan_fingerprint,
        parameter_set_fingerprint=parameter_set_fingerprint,
        execution_policy_fingerprint=execution_policy_fingerprint,
        research_partition_policy_fingerprint=research_partition_policy_fingerprint,
    )  # CA-006B-2 final bullet / adversarial test 5

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
        bound_dataset_id=market_dataset.dataset_id,
        bound_dataset_fingerprint=market_dataset.fingerprint_sha256,
        research_configuration_fingerprint=research_configuration.fingerprint,
        strategy_semantic_fingerprint=strategy_semantic_fingerprint,
        executable_strategy_plan_fingerprint=executable_strategy_plan_fingerprint,
        parameter_set_fingerprint=parameter_set_fingerprint,
        execution_policy_fingerprint=execution_policy_fingerprint,
        research_partition_policy_fingerprint=research_partition_policy_fingerprint,
        instrument_definition_fingerprint=instrument_definition.fingerprint,
    )
