"""PID-006B quantity/cost-methodology component readers + SL/TP risk-parameter
resolution.

Quantity/economics and cost mechanics are read from the
`ExecutionPolicyVersion`'s own component `configuration` payload (the
governed components in `darwin.apollo.capability`) -- never hardcoded a
second time here, so the policy's own fingerprint genuinely binds every
number the engine actually uses (PID-006B "Quantity/economics" +
"Costs" sections).

SL/TP distances are read from the StrategyVersion's own declared
parameters via the already-resolved `ParameterSetVersion` assignments --
fixed research risk, no percent-risk sizing, no partial exits, no
trailing stops, no break-even (all explicitly out of scope for this
package).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from darwin.apollo.errors import InvalidConfigurationError
from darwin.hermes.dataset import to_fixed_point
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
)

#: PID-006B engine-defined parameter_id convention: a StrategyVersion
#: compatible with this engine slice must declare exactly these two
#: parameters (FIXED or TUNABLE, DECIMAL, unit=USD_PER_TROY_OUNCE, always
#: positive). A strategy that omits either simply never told this engine
#: how to manage risk -- an ordinary configuration problem (there is no
#: implicit "no stop"/"no target"), never a capability gap.
STOP_LOSS_PARAMETER_ID = "stop_loss_distance_usd"
TAKE_PROFIT_PARAMETER_ID = "take_profit_distance_usd"


@dataclass(frozen=True)
class RiskParameters:
    """Resolved, fixed-point SL/TP distances for one replay -- read once
    at preflight, never re-read mid-replay."""

    stop_loss_distance_fp: int
    take_profit_distance_fp: int


def resolve_risk_parameters(parameter_values: dict[str, object]) -> RiskParameters:
    """Reads the two mandatory SL/TP distance parameters out of the
    already-resolved `ParameterSetVersion` assignments (see
    `darwin.apollo.preflight.resolve_parameter_values`). Raises
    `InvalidConfigurationError` if either is missing or not a positive
    `Decimal`."""
    resolved: dict[str, int] = {}
    for field_name, parameter_id in (
        ("stop_loss_distance_fp", STOP_LOSS_PARAMETER_ID),
        ("take_profit_distance_fp", TAKE_PROFIT_PARAMETER_ID),
    ):
        value = parameter_values.get(parameter_id)
        if not isinstance(value, Decimal) or value <= 0:
            raise InvalidConfigurationError(
                f"APOLLO Candle Causal Core v1 requires a positive Decimal parameter "
                f"{parameter_id!r} (stop-loss/take-profit distance, USD_PER_TROY_OUNCE) on the "
                f"StrategyVersion/ParameterSetVersion -- got {value!r}"
            )
        resolved[field_name] = to_fixed_point(value)
    return RiskParameters(**resolved)


@dataclass(frozen=True)
class QuantityEconomics:
    """Resolved quantity/starting-capital economics for one replay, read
    from the `quantity_economic_methodology` component's own
    `configuration` payload."""

    quantity: Decimal
    quantity_unit: str
    starting_capital_usd: Decimal
    account_currency: str


_QUANTITY_REQUIRED_KEYS = ("quantity", "quantity_unit", "starting_capital_usd", "account_currency")


def read_quantity_economics(component: ExecutionPolicyComponent) -> QuantityEconomics:
    config = dict(component.configuration)
    missing = [key for key in _QUANTITY_REQUIRED_KEYS if key not in config]
    if missing:
        raise InvalidConfigurationError(
            f"quantity_economic_methodology component {component.component_id!r}/"
            f"{component.component_version!r} is missing required configuration key(s): {missing}"
        )
    quantity = config["quantity"]
    starting_capital_usd = config["starting_capital_usd"]
    if not isinstance(quantity, Decimal) or quantity <= 0:
        raise InvalidConfigurationError(
            f"quantity_economic_methodology component {component.component_id!r} 'quantity' must "
            f"be a positive Decimal, got {quantity!r}"
        )
    if not isinstance(starting_capital_usd, Decimal) or starting_capital_usd <= 0:
        raise InvalidConfigurationError(
            f"quantity_economic_methodology component {component.component_id!r} "
            f"'starting_capital_usd' must be a positive Decimal, got {starting_capital_usd!r}"
        )
    return QuantityEconomics(
        quantity=quantity,
        quantity_unit=str(config["quantity_unit"]),
        starting_capital_usd=starting_capital_usd,
        account_currency=str(config["account_currency"]),
    )


@dataclass(frozen=True)
class CostModel:
    """Resolved, engine-native cost mechanics for one `COST_METHODOLOGY`
    component. `half_spread_fp`/`slippage_fp` are applied symmetrically
    against the direction of trade: a BUY (entry) fill is pushed
    price-adverse (higher); a SELL (exit) fill is pushed price-adverse
    (lower). `fee_usd` is a flat fee charged once per completed
    (round-trip) trade, on exit, against account balance."""

    half_spread_fp: int
    slippage_fp: int
    fee_usd: Decimal

    def buy_fill_price_fp(self, base_price_fp: int) -> int:
        return base_price_fp + self.half_spread_fp + self.slippage_fp

    def sell_fill_price_fp(self, base_price_fp: int) -> int:
        return base_price_fp - self.half_spread_fp - self.slippage_fp


_COST_REQUIRED_KEYS = ("spread_usd", "slippage_usd", "fee_usd_per_trade")


def read_cost_model(component: ExecutionPolicyComponent) -> CostModel:
    """`ZERO_COST` resolves to an inert, zero-friction model (fills at the
    bare base price, no fee) -- the exact same component, never a
    special-cased alternate code path beyond this dispatch. Any other
    component (in practice, only `FIXED_MECHANICAL_TEST_COST` -- preflight
    has already rejected everything else) is read from its own
    `configuration` payload."""
    if (
        component.component_id == ZERO_COST.component_id
        and component.component_version == ZERO_COST.component_version
    ):
        return CostModel(half_spread_fp=0, slippage_fp=0, fee_usd=Decimal(0))

    config = dict(component.configuration)
    missing = [key for key in _COST_REQUIRED_KEYS if key not in config]
    if missing:
        raise InvalidConfigurationError(
            f"cost_methodology component {component.component_id!r}/{component.component_version!r} "
            f"is missing required configuration key(s): {missing}"
        )
    spread_usd, slippage_usd, fee_usd = (config[k] for k in _COST_REQUIRED_KEYS)
    for label, value in (("spread_usd", spread_usd), ("slippage_usd", slippage_usd), ("fee_usd_per_trade", fee_usd)):
        if not isinstance(value, Decimal) or value < 0:
            raise InvalidConfigurationError(
                f"cost_methodology component {component.component_id!r} {label!r} must be a "
                f"non-negative Decimal, got {value!r}"
            )
    return CostModel(
        half_spread_fp=to_fixed_point(spread_usd / 2),
        slippage_fp=to_fixed_point(slippage_usd),
        fee_usd=fee_usd,
    )
