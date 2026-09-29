"""PID-006B quantity/cost component readers + SL/TP risk-parameter
resolution tests. Proves BOTH cost policies -- ZERO_COST and
FIXED_MECHANICAL_TEST_COST -- and that cost genuinely participates in
fill-price arithmetic (falsification-relevant: "used in a separate test
proving costs genuinely participate in fill/P&L arithmetic")."""
from __future__ import annotations

from decimal import Decimal

import pytest

from darwin.apollo.capability import (
    FIXED_MECHANICAL_TEST_COST,
    QUANTITY_FIXED_ONE_TROY_OUNCE,
)
from darwin.apollo.economics import (
    read_cost_model,
    read_quantity_economics,
    resolve_risk_parameters,
)
from darwin.apollo.errors import InvalidConfigurationError
from darwin.hermes.dataset import to_fixed_point
from darwin.research_contracts.execution_policy import (
    ZERO_COST,
    ExecutionPolicyComponent,
    ExecutionPolicyComponentKind,
)


def test_zero_cost_model_is_inert() -> None:
    model = read_cost_model(ZERO_COST)
    base = to_fixed_point(Decimal(4000))
    assert model.buy_fill_price_fp(base) == base
    assert model.sell_fill_price_fp(base) == base
    assert model.fee_usd == Decimal(0)


def test_fixed_mechanical_cost_model_pushes_fills_price_adverse() -> None:
    """A BUY (entry) fills HIGHER than the base price; a SELL (exit) fills
    LOWER -- both directions are adverse to the trader, exactly as real
    spread/slippage cost mechanics must be, and genuinely change the
    numeric fill price (never a no-op)."""
    model = read_cost_model(FIXED_MECHANICAL_TEST_COST)
    base = to_fixed_point(Decimal(4000))
    buy_price = model.buy_fill_price_fp(base)
    sell_price = model.sell_fill_price_fp(base)
    assert buy_price > base
    assert sell_price < base
    assert model.fee_usd > Decimal(0)
    # Exact numbers, not just direction: spread_usd=1.00 (half=0.50) + slippage_usd=0.20 = 0.70 adverse.
    assert buy_price - base == to_fixed_point(Decimal("0.70"))
    assert base - sell_price == to_fixed_point(Decimal("0.70"))


def test_cost_model_missing_configuration_key_is_invalid_configuration() -> None:
    broken = ExecutionPolicyComponent(
        kind=ExecutionPolicyComponentKind.COST_METHODOLOGY, component_id="FIXED_MECHANICAL_TEST_COST",
        component_version="v1", configuration=(("spread_usd", Decimal(1)),),  # missing slippage/fee
    )
    with pytest.raises(InvalidConfigurationError):
        read_cost_model(broken)


def test_quantity_economics_reads_component_configuration() -> None:
    econ = read_quantity_economics(QUANTITY_FIXED_ONE_TROY_OUNCE)
    assert econ.quantity == Decimal(1)
    assert econ.quantity_unit == "TROY_OUNCE"
    assert econ.starting_capital_usd == Decimal(100000)
    assert econ.account_currency == "USD"


def test_quantity_economics_missing_key_is_invalid_configuration() -> None:
    broken = ExecutionPolicyComponent(
        kind=ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY, component_id="X", component_version="v1",
        configuration=(("quantity", Decimal(1)),),
    )
    with pytest.raises(InvalidConfigurationError):
        read_quantity_economics(broken)


def test_resolve_risk_parameters_requires_both_positive_decimals() -> None:
    params = resolve_risk_parameters(
        {"stop_loss_distance_usd": Decimal(5), "take_profit_distance_usd": Decimal(10)}
    )
    assert params.stop_loss_distance_fp == to_fixed_point(Decimal(5))
    assert params.take_profit_distance_fp == to_fixed_point(Decimal(10))


@pytest.mark.parametrize(
    "values",
    [
        {"take_profit_distance_usd": Decimal(10)},  # missing SL
        {"stop_loss_distance_usd": Decimal(5)},  # missing TP
        {"stop_loss_distance_usd": Decimal(-5), "take_profit_distance_usd": Decimal(10)},  # negative
        {"stop_loss_distance_usd": Decimal(0), "take_profit_distance_usd": Decimal(10)},  # zero
        {"stop_loss_distance_usd": "5", "take_profit_distance_usd": Decimal(10)},  # wrong type
    ],
)
def test_resolve_risk_parameters_rejects_missing_or_invalid(values) -> None:
    with pytest.raises(InvalidConfigurationError):
        resolve_risk_parameters(values)
