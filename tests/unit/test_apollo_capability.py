"""PID-006B ExecutionPolicyVersion capability-allowlist tests (falsification
test 8's capability half -- see tests/unit/test_apollo_preflight.py for the
full "blocks before replay, zero bars processed" proof)."""
from __future__ import annotations

import pytest

from darwin.apollo.capability import (
    FIXED_MECHANICAL_TEST_COST,
    INTRABAR_CONSERVATIVE_SL_FIRST,
    PRICE_FILL_NEXT_BAR_OPEN,
    QUANTITY_FIXED_ONE_TROY_OUNCE,
    SESSION_NO_FORCE_FLAT,
    TIMING_CLOSE_TO_NEXT_BAR_OPEN,
    check_execution_policy_capability,
)
from darwin.apollo.errors import CapabilityBlockReason, EngineCapabilityBlockedError
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
    ExecutionPolicyComponentKind,
    build_execution_policy_version,
)


def _policy(**overrides):
    defaults = {
        "timing_methodology": TIMING_CLOSE_TO_NEXT_BAR_OPEN,
        "price_fill_methodology": PRICE_FILL_NEXT_BAR_OPEN,
        "intrabar_resolution_methodology": INTRABAR_CONSERVATIVE_SL_FIRST,
        "cost_methodology": ZERO_COST,
        "quantity_economic_methodology": QUANTITY_FIXED_ONE_TROY_OUNCE,
        "session_force_flat_methodology": SESSION_NO_FORCE_FLAT,
    }
    defaults.update(overrides)
    return build_execution_policy_version(**defaults)


def test_governed_zero_cost_policy_is_supported() -> None:
    check_execution_policy_capability(_policy())  # must not raise


def test_governed_fixed_mechanical_cost_policy_is_supported() -> None:
    check_execution_policy_capability(_policy(cost_methodology=FIXED_MECHANICAL_TEST_COST))  # must not raise


@pytest.mark.parametrize(
    "axis,bogus",
    [
        (
            "timing_methodology",
            ExecutionPolicyComponent(kind=ExecutionPolicyComponentKind.TIMING_METHODOLOGY, component_id="BOGUS", component_version="v1"),
        ),
        (
            "price_fill_methodology",
            ExecutionPolicyComponent(kind=ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY, component_id="TOUCH_PRICE", component_version="v1"),
        ),
        (
            "intrabar_resolution_methodology",
            ExecutionPolicyComponent(kind=ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY, component_id="TP_FIRST", component_version="v1"),
        ),
        (
            "cost_methodology",
            ExecutionPolicyComponent(kind=ExecutionPolicyComponentKind.COST_METHODOLOGY, component_id="REALISTIC_BROKER_COST", component_version="v1"),
        ),
        (
            "quantity_economic_methodology",
            ExecutionPolicyComponent(kind=ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY, component_id="PERCENT_RISK_SIZING", component_version="v1"),
        ),
        (
            "session_force_flat_methodology",
            ExecutionPolicyComponent(kind=ExecutionPolicyComponentKind.SESSION_FORCE_FLAT_METHODOLOGY, component_id="FORCE_FLAT_AT_NY_CLOSE", component_version="v1"),
        ),
    ],
    ids=["timing", "price_fill", "intrabar", "cost", "quantity", "session"],
)
def test_every_axis_independently_rejects_an_unsupported_component(axis, bogus) -> None:
    """`TP_FIRST` in particular is explicitly not authorised (PID-006B
    Intrabar policy: "Do not implement TP_FIRST") -- proven here as an
    ordinary capability-block case like any other unsupported component."""
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_execution_policy_capability(_policy(**{axis: bogus}))
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_EXECUTION_POLICY_COMPONENT


def test_unsupported_version_of_an_otherwise_supported_component_is_also_blocked() -> None:
    """Not just an unknown component_id -- an unrecognised component_version
    of an otherwise-supported id is equally rejected (no implicit
    forward-compatibility)."""
    stale = ExecutionPolicyComponent(
        kind=ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY,
        component_id=PRICE_FILL_NEXT_BAR_OPEN.component_id,
        component_version="v0-legacy",
    )
    with pytest.raises(EngineCapabilityBlockedError):
        check_execution_policy_capability(_policy(price_fill_methodology=stale))


def test_capability_blocked_is_not_invalid_configuration() -> None:
    """Mirrors PID-006A sec13's own structural distinction: a capability
    gap is never catchable as an ordinary configuration error."""
    from darwin.apollo.errors import InvalidConfigurationError

    assert not issubclass(EngineCapabilityBlockedError, InvalidConfigurationError)
    assert not issubclass(InvalidConfigurationError, EngineCapabilityBlockedError)
