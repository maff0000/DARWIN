"""`ResearchConfiguration` -- the shared, immutable binding of an exact
pre-execution research configuration (PID-006A sec11). Replaces what an
earlier draft called "APOLLO proof identity" -- APOLLO does not exist yet,
and this object makes no claim that any engine has proved anything. Its
fingerprint answers exactly one question: *what exact governed
experiment/proof configuration was requested?* -- never "APOLLO proved
this" (that is a future, separately-governed proof-RESULT concern,
entirely outside this work package).

Shared by design: both a future ATHENA and a future APOLLO consume the
same `ResearchConfiguration` shape; neither is referenced by name in this
module beyond this docstring.
"""
from __future__ import annotations

from dataclasses import dataclass

from darwin.core.dike import DikeState
from darwin.core.errors import DikePolicyBindingError
from darwin.core.identities import new_id
from darwin.hermes.instrument_definition import InstrumentDefinition
from darwin.research_contracts.compiler import ExecutableStrategyPlan
from darwin.research_contracts.errors import (
    InvalidConfigurationError,
    ResearchConfigurationInconsistentError,
)
from darwin.research_contracts.execution_policy import ExecutionPolicyVersion
from darwin.research_contracts.input_binding import ResearchInputBinding
from darwin.research_contracts.parameter_set import ParameterSetVersion
from darwin.research_contracts.partition_policy import ResearchPartitionPolicyVersion
from darwin.specification.domain import StrategyVersion
from darwin.specification.fingerprint import canonical_hash

#: PID-006A sec11 -- bumped whenever the *shape* of ResearchConfiguration's
#: own binding changes, independent of any one axis's own schema version.
CONFIGURATION_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class ResearchConfiguration:
    """Immutable, deterministically fingerprinted research-configuration
    identity (PID-006A sec11). Binds, as independent axes: `StrategyVersion`
    semantic identity, `ExecutableStrategyPlan` identity,
    `ParameterSetVersion`, `InstrumentDefinition` identity,
    `ResearchInputBinding` set, `ResearchPartitionPolicyVersion`,
    `ExecutionPolicyVersion`, DIKE identity/state, and any required
    derived-algorithm identities.

    Each axis's own fingerprint is recorded verbatim -- changing any ONE
    axis never silently changes another axis's own recorded identity
    (Required tests: "strategy/parameter/policy/partition/input identities
    remain independent axes").

    `research_configuration_id` is an opaque application-generated
    identity, excluded from `fingerprint`.
    """

    research_configuration_id: str
    configuration_schema_version: str
    strategy_semantic_fingerprint: str
    executable_strategy_plan_fingerprint: str
    parameter_set_fingerprint: str
    instrument_definition_id: str
    instrument_definition_fingerprint: str
    research_input_bindings: tuple[ResearchInputBinding, ...]
    research_partition_policy_fingerprint: str
    execution_policy_fingerprint: str
    dike_state: DikeState
    dike_policy_fingerprint: str | None
    required_derived_algorithm_identities: tuple[tuple[str, str], ...]
    fingerprint: str


def _fingerprint_payload(
    *,
    configuration_schema_version: str,
    strategy_semantic_fingerprint: str,
    executable_strategy_plan_fingerprint: str,
    parameter_set_fingerprint: str,
    instrument_definition_id: str,
    instrument_definition_fingerprint: str,
    research_input_bindings: tuple[ResearchInputBinding, ...],
    research_partition_policy_fingerprint: str,
    execution_policy_fingerprint: str,
    dike_state: DikeState,
    dike_policy_fingerprint: str | None,
    required_derived_algorithm_identities: tuple[tuple[str, str], ...],
) -> dict:
    # research_input_bindings is sorted by its own fingerprint before
    # hashing -- deterministic regardless of the order the caller happened
    # to pass them in (Required tests: "equivalent canonical ordering
    # yields the same fingerprint").
    sorted_bindings = tuple(sorted(research_input_bindings, key=lambda b: b.fingerprint))
    return {
        "configuration_schema_version": configuration_schema_version,
        "strategy_semantic_fingerprint": strategy_semantic_fingerprint,
        "executable_strategy_plan_fingerprint": executable_strategy_plan_fingerprint,
        "parameter_set_fingerprint": parameter_set_fingerprint,
        "instrument_definition_id": instrument_definition_id,
        "instrument_definition_fingerprint": instrument_definition_fingerprint,
        "research_input_binding_fingerprints": [b.fingerprint for b in sorted_bindings],
        "research_partition_policy_fingerprint": research_partition_policy_fingerprint,
        "execution_policy_fingerprint": execution_policy_fingerprint,
        "dike_state": dike_state.value,
        "dike_policy_fingerprint": dike_policy_fingerprint,
        "required_derived_algorithm_identities": sorted(required_derived_algorithm_identities),
    }


def compute_research_configuration_fingerprint(
    *,
    configuration_schema_version: str,
    strategy_semantic_fingerprint: str,
    executable_strategy_plan_fingerprint: str,
    parameter_set_fingerprint: str,
    instrument_definition_id: str,
    instrument_definition_fingerprint: str,
    research_input_bindings: tuple[ResearchInputBinding, ...],
    research_partition_policy_fingerprint: str,
    execution_policy_fingerprint: str,
    dike_state: DikeState,
    dike_policy_fingerprint: str | None,
    required_derived_algorithm_identities: tuple[tuple[str, str], ...],
) -> str:
    """Recomputable independently of a live `ResearchConfiguration`
    instance -- used both by `build_research_configuration` and by
    `darwin.research_store`'s persistence layer on reconstruction."""
    return canonical_hash(
        _fingerprint_payload(
            configuration_schema_version=configuration_schema_version,
            strategy_semantic_fingerprint=strategy_semantic_fingerprint,
            executable_strategy_plan_fingerprint=executable_strategy_plan_fingerprint,
            parameter_set_fingerprint=parameter_set_fingerprint,
            instrument_definition_id=instrument_definition_id,
            instrument_definition_fingerprint=instrument_definition_fingerprint,
            research_input_bindings=research_input_bindings,
            research_partition_policy_fingerprint=research_partition_policy_fingerprint,
            execution_policy_fingerprint=execution_policy_fingerprint,
            dike_state=dike_state,
            dike_policy_fingerprint=dike_policy_fingerprint,
            required_derived_algorithm_identities=required_derived_algorithm_identities,
        )
    )


def build_research_configuration(
    *,
    strategy_version: StrategyVersion,
    executable_plan: ExecutableStrategyPlan,
    parameter_set: ParameterSetVersion,
    instrument_definition: InstrumentDefinition,
    research_input_bindings: tuple[ResearchInputBinding, ...],
    partition_policy: ResearchPartitionPolicyVersion,
    execution_policy: ExecutionPolicyVersion,
    dike_state: DikeState,
    dike_policy_fingerprint: str | None = None,
    required_derived_algorithm_identities: tuple[tuple[str, str], ...] = (),
) -> ResearchConfiguration:
    """The only supported way to construct a `ResearchConfiguration`
    (PID-006A sec11). Detects and rejects an inconsistent binding before
    computing any fingerprint:

    - `executable_plan` must have been compiled from the SAME
      `strategy_version` (by semantic fingerprint).
    - `parameter_set` must have been built against the SAME
      `strategy_version` (by semantic fingerprint) -- the exact example
      PID-006A sec11 names explicitly.
    - `dike_state`/`dike_policy_fingerprint` must agree exactly as
      `darwin.core.errors.DikePolicyBindingError` already governs
      elsewhere in DARWIN (DISABLED carries no policy identity; GUARDED
      requires one) -- reused directly, not re-derived.
    """
    if executable_plan.source_semantic_fingerprint != strategy_version.semantic_fingerprint:
        raise ResearchConfigurationInconsistentError(
            "ExecutableStrategyPlan was compiled from a different StrategyVersion "
            f"(plan source_semantic_fingerprint={executable_plan.source_semantic_fingerprint!r}, "
            f"expected {strategy_version.semantic_fingerprint!r})"
        )
    if parameter_set.source_semantic_fingerprint != strategy_version.semantic_fingerprint:
        raise ResearchConfigurationInconsistentError(
            "ParameterSetVersion was built against a different StrategyVersion "
            f"(parameter_set source_semantic_fingerprint={parameter_set.source_semantic_fingerprint!r}, "
            f"expected {strategy_version.semantic_fingerprint!r})"
        )
    if not isinstance(dike_state, DikeState):
        raise InvalidConfigurationError(f"ResearchConfiguration requires a governed DikeState, got {dike_state!r}")
    if dike_state == DikeState.DISABLED and dike_policy_fingerprint is not None:
        raise DikePolicyBindingError("DIKE_DISABLED must carry no DIKE policy identity")
    if dike_state == DikeState.GUARDED and dike_policy_fingerprint is None:
        raise DikePolicyBindingError("DIKE_GUARDED requires a DIKE policy fingerprint")
    if not research_input_bindings:
        raise InvalidConfigurationError("ResearchConfiguration requires at least one ResearchInputBinding")

    fingerprint = compute_research_configuration_fingerprint(
        configuration_schema_version=CONFIGURATION_SCHEMA_VERSION,
        strategy_semantic_fingerprint=strategy_version.semantic_fingerprint,
        executable_strategy_plan_fingerprint=executable_plan.fingerprint,
        parameter_set_fingerprint=parameter_set.fingerprint,
        instrument_definition_id=instrument_definition.instrument_id,
        instrument_definition_fingerprint=instrument_definition.fingerprint,
        research_input_bindings=research_input_bindings,
        research_partition_policy_fingerprint=partition_policy.fingerprint,
        execution_policy_fingerprint=execution_policy.fingerprint,
        dike_state=dike_state,
        dike_policy_fingerprint=dike_policy_fingerprint,
        required_derived_algorithm_identities=required_derived_algorithm_identities,
    )
    return ResearchConfiguration(
        research_configuration_id=new_id(),
        configuration_schema_version=CONFIGURATION_SCHEMA_VERSION,
        strategy_semantic_fingerprint=strategy_version.semantic_fingerprint,
        executable_strategy_plan_fingerprint=executable_plan.fingerprint,
        parameter_set_fingerprint=parameter_set.fingerprint,
        instrument_definition_id=instrument_definition.instrument_id,
        instrument_definition_fingerprint=instrument_definition.fingerprint,
        research_input_bindings=tuple(research_input_bindings),
        research_partition_policy_fingerprint=partition_policy.fingerprint,
        execution_policy_fingerprint=execution_policy.fingerprint,
        dike_state=dike_state,
        dike_policy_fingerprint=dike_policy_fingerprint,
        required_derived_algorithm_identities=tuple(required_derived_algorithm_identities),
        fingerprint=fingerprint,
    )
