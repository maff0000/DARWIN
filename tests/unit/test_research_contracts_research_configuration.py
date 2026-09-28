"""PID-006A ResearchConfiguration tests (docs/pids/PID-006-APOLLO.md sec11)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from darwin.core.dike import DikeState
from darwin.core.errors import DikePolicyBindingError
from darwin.hermes.contract import Timeframe
from darwin.hermes.dataset import build_market_dataset
from darwin.hermes.instrument_definition import get_instrument_definition
from darwin.research_contracts.compiler import CanonicalStrategyCompiler
from darwin.research_contracts.errors import (
    InvalidConfigurationError,
    ResearchConfigurationInconsistentError,
    ResearchInputBindingError,
)
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
    ExecutionPolicyComponentKind,
    build_execution_policy_version,
)
from darwin.research_contracts.input_binding import (
    ResearchInputBinding,
    ResearchInputKind,
    research_input_binding_from_market_dataset,
)
from darwin.research_contracts.parameter_set import build_parameter_set_version
from darwin.research_contracts.partition_policy import (
    ResearchPartitionRole,
    build_research_partition_policy_version,
)
from darwin.research_contracts.research_configuration import (
    build_research_configuration,
)
from darwin.specification.validation import finalise
from tests.fixtures.hermes_rows import UTC_2026_09_16_15, hourly_series
from tests.fixtures.specification_drafts import (
    minimal_valid_draft,
    simple_atomic_condition,
)


def _strategy_version(strategy_version_id: str = "sv-cfg", *, threshold: str = "4000"):
    # `threshold` varies the composition's own semantic content -- two
    # calls with different thresholds produce genuinely different
    # StrategyVersion.semantic_fingerprint values, not just different ids
    # (which alone would never change semantic identity -- PID-006A's own
    # point about excluded metadata fields).
    draft = minimal_valid_draft(
        draft_id=strategy_version_id,
        candidate_id=f"{strategy_version_id}-cand",
        composition=simple_atomic_condition(threshold=threshold),
    )
    result = finalise(draft, strategy_version_id=strategy_version_id, now=datetime(2026, 1, 1, tzinfo=UTC))
    assert result.strategy_version is not None, result.outcome
    return result.strategy_version


def _dataset(dataset_id: str = "ds-cfg"):
    rows = hourly_series(UTC_2026_09_16_15, 5)
    return build_market_dataset(
        dataset_id=dataset_id,
        instrument="XAU_USD",
        instrument_definition_id="def-v1",
        timeframe=Timeframe.H1,
        requested_start_utc=rows[0].open_time,
        requested_end_utc=rows[-1].open_time + timedelta(hours=1),
        rows=rows,
        adapter_build_version="test",
        loaded_at_utc=UTC_2026_09_16_15,
    )


def _execution_policy():
    def comp(kind, cid):
        return ExecutionPolicyComponent(kind=kind, component_id=cid, component_version="v1")

    return build_execution_policy_version(
        timing_methodology=comp(ExecutionPolicyComponentKind.TIMING_METHODOLOGY, "NEXT_BAR_OPEN"),
        price_fill_methodology=comp(ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY, "TOUCH_PRICE"),
        intrabar_resolution_methodology=comp(
            ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY, "CONSERVATIVE_SL_FIRST"
        ),
        cost_methodology=ZERO_COST,
        quantity_economic_methodology=comp(
            ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY, "FIXED_UNIT_QUANTITY"
        ),
        session_force_flat_methodology=comp(
            ExecutionPolicyComponentKind.SESSION_FORCE_FLAT_METHODOLOGY, "NO_FORCE_FLAT"
        ),
    )


def _build(strategy_version=None, dataset_id: str = "ds-cfg", **overrides):
    strategy_version = strategy_version or _strategy_version()
    plan = CanonicalStrategyCompiler().compile(strategy_version)
    parameter_set = build_parameter_set_version(strategy_version, ())
    binding = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset(dataset_id)
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    kwargs = {
        "strategy_version": strategy_version,
        "executable_plan": plan,
        "parameter_set": parameter_set,
        "instrument_definition": get_instrument_definition("XAU_USD"),
        "research_input_bindings": (binding,),
        "partition_policy": partition_policy,
        "execution_policy": _execution_policy(),
        "dike_state": DikeState.DISABLED,
    }
    kwargs.update(overrides)
    return build_research_configuration(**kwargs)


def test_material_axis_change_changes_configuration_fingerprint() -> None:
    base = _build()
    changed = _build(dataset_id="ds-different")
    assert base.fingerprint != changed.fingerprint


def test_strategy_axis_change_changes_fingerprint_independent_of_others() -> None:
    base = _build()
    other_strategy = _strategy_version("sv-cfg-2", threshold="4500")
    changed = _build(strategy_version=other_strategy)
    assert base.fingerprint != changed.fingerprint
    assert base.execution_policy_fingerprint == changed.execution_policy_fingerprint  # untouched axis unaffected


def test_axes_are_independent_changing_one_never_changes_anothers_recorded_identity() -> None:
    base = _build()
    changed = _build(dataset_id="ds-different")
    # Only the partition-policy/input-binding axis actually changed.
    assert base.strategy_semantic_fingerprint == changed.strategy_semantic_fingerprint
    assert base.parameter_set_fingerprint == changed.parameter_set_fingerprint
    assert base.execution_policy_fingerprint == changed.execution_policy_fingerprint
    assert base.research_partition_policy_fingerprint != changed.research_partition_policy_fingerprint


def test_inconsistent_parameter_set_binding_rejected() -> None:
    strategy_a = _strategy_version("sv-cfg-a", threshold="4000")
    strategy_b = _strategy_version("sv-cfg-b", threshold="4700")
    plan = CanonicalStrategyCompiler().compile(strategy_a)
    mismatched_parameter_set = build_parameter_set_version(strategy_b, ())
    binding = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset()
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    with pytest.raises(ResearchConfigurationInconsistentError):
        build_research_configuration(
            strategy_version=strategy_a,
            executable_plan=plan,
            parameter_set=mismatched_parameter_set,
            instrument_definition=get_instrument_definition("XAU_USD"),
            research_input_bindings=(binding,),
            partition_policy=partition_policy,
            execution_policy=_execution_policy(),
            dike_state=DikeState.DISABLED,
        )


def test_inconsistent_plan_binding_rejected() -> None:
    strategy_a = _strategy_version("sv-cfg-c", threshold="4000")
    strategy_b = _strategy_version("sv-cfg-d", threshold="4800")
    mismatched_plan = CanonicalStrategyCompiler().compile(strategy_b)
    parameter_set = build_parameter_set_version(strategy_a, ())
    binding = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset()
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    with pytest.raises(ResearchConfigurationInconsistentError):
        build_research_configuration(
            strategy_version=strategy_a,
            executable_plan=mismatched_plan,
            parameter_set=parameter_set,
            instrument_definition=get_instrument_definition("XAU_USD"),
            research_input_bindings=(binding,),
            partition_policy=partition_policy,
            execution_policy=_execution_policy(),
            dike_state=DikeState.DISABLED,
        )


def test_dike_disabled_must_carry_no_policy_identity() -> None:
    with pytest.raises(DikePolicyBindingError):
        _build(dike_state=DikeState.DISABLED, dike_policy_fingerprint="some-fingerprint")


def test_dike_guarded_requires_policy_identity() -> None:
    with pytest.raises(DikePolicyBindingError):
        _build(dike_state=DikeState.GUARDED, dike_policy_fingerprint=None)


def test_dike_guarded_with_fingerprint_succeeds() -> None:
    config = _build(dike_state=DikeState.GUARDED, dike_policy_fingerprint="policy-fp-1")
    assert config.dike_state == DikeState.GUARDED
    assert config.dike_policy_fingerprint == "policy-fp-1"


def test_equivalent_canonical_ordering_yields_same_fingerprint() -> None:
    strategy_version = _strategy_version("sv-cfg-order")
    plan = CanonicalStrategyCompiler().compile(strategy_version)
    parameter_set = build_parameter_set_version(strategy_version, ())
    binding_a = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset("ds-order-a")
    )
    binding_b = research_input_binding_from_market_dataset(
        logical_input_role="SECONDARY_CONTEXT", market_dataset=_dataset("ds-order-b")
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding_a)
    execution_policy = _execution_policy()

    first = build_research_configuration(
        strategy_version=strategy_version,
        executable_plan=plan,
        parameter_set=parameter_set,
        instrument_definition=get_instrument_definition("XAU_USD"),
        research_input_bindings=(binding_a, binding_b),
        partition_policy=partition_policy,
        execution_policy=execution_policy,
        dike_state=DikeState.DISABLED,
    )
    second = build_research_configuration(
        strategy_version=strategy_version,
        executable_plan=plan,
        parameter_set=parameter_set,
        instrument_definition=get_instrument_definition("XAU_USD"),
        research_input_bindings=(binding_b, binding_a),  # reversed order
        partition_policy=partition_policy,
        execution_policy=execution_policy,
        dike_state=DikeState.DISABLED,
    )
    assert first.fingerprint == second.fingerprint


def test_requires_at_least_one_input_binding() -> None:
    strategy_version = _strategy_version("sv-cfg-empty")
    plan = CanonicalStrategyCompiler().compile(strategy_version)
    parameter_set = build_parameter_set_version(strategy_version, ())
    binding = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset()
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    with pytest.raises(InvalidConfigurationError):
        build_research_configuration(
            strategy_version=strategy_version,
            executable_plan=plan,
            parameter_set=parameter_set,
            instrument_definition=get_instrument_definition("XAU_USD"),
            research_input_bindings=(),
            partition_policy=partition_policy,
            execution_policy=_execution_policy(),
            dike_state=DikeState.DISABLED,
        )


# --- CA-1 (adversarial-audit follow-up, PR #18): ResearchConfiguration must
# bind its partition policy to its actual declared input set
# ------------------------------------------------------------------------------


def test_partition_policy_bound_to_declared_dataset_succeeds() -> None:
    """Baseline positive control for CA-1: a partition policy bound to
    Dataset A, in a configuration whose research_input_bindings also
    declares Dataset A, succeeds."""
    binding = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset("ds-ca1-a")
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    strategy_version = _strategy_version("sv-ca1-positive")
    config = build_research_configuration(
        strategy_version=strategy_version,
        executable_plan=CanonicalStrategyCompiler().compile(strategy_version),
        parameter_set=build_parameter_set_version(strategy_version, ()),
        instrument_definition=get_instrument_definition("XAU_USD"),
        research_input_bindings=(binding,),
        partition_policy=partition_policy,
        execution_policy=_execution_policy(),
        dike_state=DikeState.DISABLED,
    )
    assert config.research_partition_policy_fingerprint == partition_policy.fingerprint


def test_partition_policy_bound_to_undeclared_dataset_rejected() -> None:
    """CA-1 core case: a partition policy bound to Dataset B, in a
    configuration whose research_input_bindings only declares Dataset A,
    is a structurally contradictory configuration and must be rejected."""
    binding_a = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset("ds-ca1-only-a")
    )
    binding_b = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset("ds-ca1-unrelated-b")
    )
    partition_policy_for_b = build_research_partition_policy_version(
        role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding_b
    )
    strategy_version = _strategy_version("sv-ca1-negative")
    with pytest.raises(ResearchConfigurationInconsistentError):
        build_research_configuration(
            strategy_version=strategy_version,
            executable_plan=CanonicalStrategyCompiler().compile(strategy_version),
            parameter_set=build_parameter_set_version(strategy_version, ()),
            instrument_definition=get_instrument_definition("XAU_USD"),
            research_input_bindings=(binding_a,),  # only Dataset A declared
            partition_policy=partition_policy_for_b,  # but policy governs Dataset B
            execution_policy=_execution_policy(),
            dike_state=DikeState.DISABLED,
        )


def test_duplicate_binding_fingerprint_rejected() -> None:
    """CA-1 item 3: the identical ResearchInputBinding must not be
    declared twice in one configuration's research_input_bindings."""
    binding = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset("ds-ca1-dup")
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding)
    strategy_version = _strategy_version("sv-ca1-dup-fp")
    with pytest.raises(ResearchConfigurationInconsistentError):
        build_research_configuration(
            strategy_version=strategy_version,
            executable_plan=CanonicalStrategyCompiler().compile(strategy_version),
            parameter_set=build_parameter_set_version(strategy_version, ()),
            instrument_definition=get_instrument_definition("XAU_USD"),
            research_input_bindings=(binding, binding),  # same binding twice
            partition_policy=partition_policy,
            execution_policy=_execution_policy(),
            dike_state=DikeState.DISABLED,
        )


def test_duplicate_logical_input_role_rejected() -> None:
    """CA-1 item 4: two DIFFERENT datasets both claiming the same
    logical_input_role in one configuration is ambiguous and must never
    be silently accepted."""
    binding_a = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA", market_dataset=_dataset("ds-ca1-role-a")
    )
    binding_b = research_input_binding_from_market_dataset(
        logical_input_role="PRIMARY_MARKET_DATA",  # same role, different dataset
        market_dataset=_dataset("ds-ca1-role-b"),
    )
    partition_policy = build_research_partition_policy_version(role=ResearchPartitionRole.DEVELOPMENT, input_binding=binding_a)
    strategy_version = _strategy_version("sv-ca1-dup-role")
    with pytest.raises(ResearchConfigurationInconsistentError):
        build_research_configuration(
            strategy_version=strategy_version,
            executable_plan=CanonicalStrategyCompiler().compile(strategy_version),
            parameter_set=build_parameter_set_version(strategy_version, ()),
            instrument_definition=get_instrument_definition("XAU_USD"),
            research_input_bindings=(binding_a, binding_b),
            partition_policy=partition_policy,
            execution_policy=_execution_policy(),
            dike_state=DikeState.DISABLED,
        )


# --- CA-2 item 5 (adversarial-audit follow-up, PR #18) ----------------------


def test_hand_constructed_binding_with_invalid_fingerprint_rejected_by_configuration() -> None:
    """CA-2 item 5: a ResearchInputBinding with an outright invalid
    fingerprint, presented directly to ResearchConfiguration construction
    (bypassing build_research_input_binding), must be rejected -- never
    silently trusted as semantic input."""
    forged = ResearchInputBinding(
        input_binding_id="forged-cfg-1",
        logical_input_role="PRIMARY_MARKET_DATA",
        input_kind=ResearchInputKind.MARKET_CANDLE_DATASET,
        governed_dataset_id="ds-forged-cfg",
        dataset_semantic_fingerprint="1" * 64,
        fingerprint="not-a-real-fingerprint",
    )
    legit_binding = research_input_binding_from_market_dataset(
        logical_input_role="SECONDARY_CONTEXT", market_dataset=_dataset("ds-ca2-legit")
    )
    partition_policy = build_research_partition_policy_version(
        role=ResearchPartitionRole.DEVELOPMENT, input_binding=legit_binding
    )
    strategy_version = _strategy_version("sv-ca2-forged")
    with pytest.raises(ResearchInputBindingError):
        build_research_configuration(
            strategy_version=strategy_version,
            executable_plan=CanonicalStrategyCompiler().compile(strategy_version),
            parameter_set=build_parameter_set_version(strategy_version, ()),
            instrument_definition=get_instrument_definition("XAU_USD"),
            research_input_bindings=(legit_binding, forged),
            partition_policy=partition_policy,
            execution_policy=_execution_policy(),
            dike_state=DikeState.DISABLED,
        )

