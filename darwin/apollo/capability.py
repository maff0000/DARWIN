"""PID-006B closed, explicit `ExecutionPolicyComponent` capability allowlist.

The engine supports exactly one component per axis, except
`COST_METHODOLOGY`, which supports exactly two (`ZERO_COST` for the
mechanical/development acceptance run, and `FIXED_MECHANICAL_TEST_COST`
for the cost-participates-in-arithmetic proof). Every component below is
a real, ordinary `ExecutionPolicyComponent` -- never a magic sentinel --
selected explicitly by whoever builds the `ExecutionPolicyVersion`, mirroring
`darwin.research_contracts.execution_policy.ZERO_COST`'s own discipline.

An `ExecutionPolicyVersion` containing any component/version pair not in
this allowlist is `ENGINE_CAPABILITY_BLOCKED` at preflight, before a
single bar is processed -- see `darwin.apollo.preflight`.
"""
from __future__ import annotations

from decimal import Decimal

from darwin.apollo.errors import (
    CapabilityBlockContext,
    CapabilityBlockReason,
    EngineCapabilityBlockedError,
)
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
    ExecutionPolicyComponentKind,
    ExecutionPolicyVersion,
)

#: PID-006B timing methodology: a signal is evaluated only when its source
#: candle has closed; a close-time decision creates an order eligible at
#: the next canonical bar's open, on the SAME timeframe. No M1
#: disambiguation.
TIMING_CLOSE_TO_NEXT_BAR_OPEN = ExecutionPolicyComponent(
    kind=ExecutionPolicyComponentKind.TIMING_METHODOLOGY,
    component_id="CLOSE_TO_NEXT_BAR_OPEN_SAME_TIMEFRAME",
    component_version="v1",
)

#: PID-006B price-fill methodology: the fill price used is genuinely the
#: eligible bar's real open -- never an approximation, never the signal
#: bar's own close.
PRICE_FILL_NEXT_BAR_OPEN = ExecutionPolicyComponent(
    kind=ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY,
    component_id="NEXT_BAR_OPEN",
    component_version="v1",
)

#: PID-006B intrabar resolution: if both SL and TP are touched within the
#: same bar, SL wins (`IntrabarAmbiguityPolicy.CONSERVATIVE_SL_FIRST`'s
#: execution-mechanics counterpart). `TP_FIRST` is not authorised and has
#: no component here.
INTRABAR_CONSERVATIVE_SL_FIRST = ExecutionPolicyComponent(
    kind=ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY,
    component_id="CONSERVATIVE_SL_FIRST",
    component_version="v1",
)

#: PID-006B session force-flat: out of scope for this engine slice -- no
#: session-based forced flattening is implemented. Recorded explicitly as
#: "no force-flat rule applies", never a silent omission of the mandatory
#: axis.
SESSION_NO_FORCE_FLAT = ExecutionPolicyComponent(
    kind=ExecutionPolicyComponentKind.SESSION_FORCE_FLAT_METHODOLOGY,
    component_id="NO_FORCE_FLAT",
    component_version="v1",
)

#: PID-006B quantity/economics: fixed research quantity of exactly 1 troy
#: ounce, always, USD account currency, explicit starting capital. 100,000
#: USD is a clean, round, clearly-documented research starting balance --
#: large enough that a single XAU_USD position's mark-to-market swings
#: never drive the account negative within this v1 slice's controlled
#: fixtures/real-data acceptance window, never intended as a realistic
#: account-sizing claim.
QUANTITY_FIXED_ONE_TROY_OUNCE = ExecutionPolicyComponent(
    kind=ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY,
    component_id="FIXED_ONE_TROY_OUNCE_USD_ACCOUNT",
    component_version="v1",
    configuration=(
        ("quantity", Decimal(1)),
        ("quantity_unit", "TROY_OUNCE"),
        ("starting_capital_usd", Decimal(100000)),
        ("account_currency", "USD"),
    ),
)

#: PID-006B cost methodology #2: a deliberately simple, deterministic,
#: NON-zero mechanical TEST fixture -- never a real XAU broker cost
#: calibration claim. Applied as: buy fills at (open + half_spread +
#: slippage), sell fills at (open - half_spread - slippage), plus a flat
#: per-trade fee charged on exit. Values are plain, labelled test
#: constants.
FIXED_MECHANICAL_TEST_COST = ExecutionPolicyComponent(
    kind=ExecutionPolicyComponentKind.COST_METHODOLOGY,
    component_id="FIXED_MECHANICAL_TEST_COST",
    component_version="v1",
    configuration=(
        ("spread_usd", Decimal("1.00")),
        ("slippage_usd", Decimal("0.20")),
        ("fee_usd_per_trade", Decimal("0.50")),
    ),
)

#: The closed allowlist itself: axis -> {(component_id, component_version)}.
_SUPPORTED: dict[ExecutionPolicyComponentKind, frozenset[tuple[str, str]]] = {
    ExecutionPolicyComponentKind.TIMING_METHODOLOGY: frozenset(
        {(TIMING_CLOSE_TO_NEXT_BAR_OPEN.component_id, TIMING_CLOSE_TO_NEXT_BAR_OPEN.component_version)}
    ),
    ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY: frozenset(
        {(PRICE_FILL_NEXT_BAR_OPEN.component_id, PRICE_FILL_NEXT_BAR_OPEN.component_version)}
    ),
    ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY: frozenset(
        {(INTRABAR_CONSERVATIVE_SL_FIRST.component_id, INTRABAR_CONSERVATIVE_SL_FIRST.component_version)}
    ),
    ExecutionPolicyComponentKind.COST_METHODOLOGY: frozenset(
        {
            (ZERO_COST.component_id, ZERO_COST.component_version),
            (FIXED_MECHANICAL_TEST_COST.component_id, FIXED_MECHANICAL_TEST_COST.component_version),
        }
    ),
    ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY: frozenset(
        {(QUANTITY_FIXED_ONE_TROY_OUNCE.component_id, QUANTITY_FIXED_ONE_TROY_OUNCE.component_version)}
    ),
    ExecutionPolicyComponentKind.SESSION_FORCE_FLAT_METHODOLOGY: frozenset(
        {(SESSION_NO_FORCE_FLAT.component_id, SESSION_NO_FORCE_FLAT.component_version)}
    ),
}

_AXIS_FIELDS: tuple[str, ...] = (
    "timing_methodology",
    "price_fill_methodology",
    "intrabar_resolution_methodology",
    "cost_methodology",
    "quantity_economic_methodology",
    "session_force_flat_methodology",
)


def check_execution_policy_capability(execution_policy: ExecutionPolicyVersion) -> None:
    """PID-006B preflight check #8: `ExecutionPolicyVersion` must contain
    ONLY components this engine slice actually supports. Raises
    `EngineCapabilityBlockedError` (never a bare crash mid-replay -- this
    always runs before any bar is touched) the instant any axis carries a
    component/version pair outside `_SUPPORTED`.
    """
    for axis in _AXIS_FIELDS:
        component: ExecutionPolicyComponent = getattr(execution_policy, axis)
        allowed = _SUPPORTED[component.kind]
        key = (component.component_id, component.component_version)
        if key not in allowed:
            raise EngineCapabilityBlockedError(
                f"ExecutionPolicyVersion axis {component.kind.value} selects "
                f"{component.component_id!r}/{component.component_version!r}, which this "
                f"APOLLO Candle Causal Core (v1) does not support. Supported for this axis: "
                f"{sorted(allowed)}",
                context=CapabilityBlockContext(
                    reason=CapabilityBlockReason.UNSUPPORTED_EXECUTION_POLICY_COMPONENT,
                    subject_ref=f"{component.kind.value}:{component.component_id}/{component.component_version}",
                    detail=(("axis", component.kind.value),),
                ),
            )
