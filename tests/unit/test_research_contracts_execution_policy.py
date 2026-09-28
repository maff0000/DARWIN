"""PID-006A ExecutionPolicyVersion / ZERO_COST tests
(docs/pids/PID-006-APOLLO.md sec7/sec8)."""
from __future__ import annotations

import pytest

from darwin.research_contracts.errors import (
    ExecutionPolicyIncompleteError,
    InvalidConfigurationError,
)
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
    ExecutionPolicyComponentKind,
    build_execution_policy_version,
)


def _component(kind: ExecutionPolicyComponentKind, component_id: str, version: str = "v1") -> ExecutionPolicyComponent:
    return ExecutionPolicyComponent(kind=kind, component_id=component_id, component_version=version)


def _all_axes(**overrides) -> dict:
    base = {
        "timing_methodology": _component(ExecutionPolicyComponentKind.TIMING_METHODOLOGY, "NEXT_BAR_OPEN"),
        "price_fill_methodology": _component(ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY, "TOUCH_PRICE"),
        "intrabar_resolution_methodology": _component(
            ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY, "CONSERVATIVE_SL_FIRST"
        ),
        "cost_methodology": ZERO_COST,
        "quantity_economic_methodology": _component(
            ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY, "FIXED_UNIT_QUANTITY"
        ),
        "session_force_flat_methodology": _component(
            ExecutionPolicyComponentKind.SESSION_FORCE_FLAT_METHODOLOGY, "NO_FORCE_FLAT"
        ),
    }
    base.update(overrides)
    return base


def test_missing_mandatory_component_rejected() -> None:
    axes = _all_axes()
    axes["cost_methodology"] = None
    with pytest.raises(ExecutionPolicyIncompleteError):
        build_execution_policy_version(**axes)


def test_all_six_axes_are_individually_mandatory() -> None:
    for axis in _all_axes():
        axes = _all_axes()
        axes[axis] = None
        with pytest.raises(ExecutionPolicyIncompleteError):
            build_execution_policy_version(**axes)


def test_wrong_component_kind_for_axis_rejected() -> None:
    axes = _all_axes()
    axes["cost_methodology"] = _component(ExecutionPolicyComponentKind.TIMING_METHODOLOGY, "NEXT_BAR_OPEN")
    with pytest.raises(InvalidConfigurationError):
        build_execution_policy_version(**axes)


def test_zero_cost_succeeds_explicitly() -> None:
    policy = build_execution_policy_version(**_all_axes(cost_methodology=ZERO_COST))
    assert policy.cost_methodology == ZERO_COST


def test_material_component_change_changes_fingerprint() -> None:
    base = build_execution_policy_version(**_all_axes())
    changed = build_execution_policy_version(
        **_all_axes(
            price_fill_methodology=_component(ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY, "NEXT_OPEN_PRICE")
        )
    )
    assert base.fingerprint != changed.fingerprint


def test_component_version_change_changes_fingerprint() -> None:
    base = build_execution_policy_version(**_all_axes())
    changed = build_execution_policy_version(
        **_all_axes(
            timing_methodology=_component(ExecutionPolicyComponentKind.TIMING_METHODOLOGY, "NEXT_BAR_OPEN", "v2")
        )
    )
    assert base.fingerprint != changed.fingerprint


def test_component_configuration_change_changes_fingerprint() -> None:
    base_component = ExecutionPolicyComponent(
        kind=ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY,
        component_id="CONSERVATIVE_SL_FIRST",
        component_version="v1",
        configuration=(("tie_break", "SL_FIRST"),),
    )
    other_component = ExecutionPolicyComponent(
        kind=ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY,
        component_id="CONSERVATIVE_SL_FIRST",
        component_version="v1",
        configuration=(("tie_break", "TP_FIRST"),),
    )
    base = build_execution_policy_version(**_all_axes(intrabar_resolution_methodology=base_component))
    changed = build_execution_policy_version(**_all_axes(intrabar_resolution_methodology=other_component))
    assert base.fingerprint != changed.fingerprint


def test_omitted_cost_methodology_never_silently_becomes_zero_cost() -> None:
    axes = _all_axes()
    axes["cost_methodology"] = None
    with pytest.raises(ExecutionPolicyIncompleteError):
        build_execution_policy_version(**axes)
    # ZERO_COST must be the caller's deliberate, explicit choice -- there
    # is no default anywhere `build_execution_policy_version` could take.
    policy = build_execution_policy_version(**_all_axes(cost_methodology=ZERO_COST))
    assert policy.cost_methodology.component_id == "ZERO_COST"


def test_empty_component_id_rejected() -> None:
    with pytest.raises(InvalidConfigurationError):
        ExecutionPolicyComponent(
            kind=ExecutionPolicyComponentKind.COST_METHODOLOGY, component_id="", component_version="v1"
        )
