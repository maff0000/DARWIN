"""PID-006B falsification test 9: open-position unrealised P&L affects
bar equity/drawdown -- mark-to-market, not just realised P&L at trade
close."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from darwin.apollo import run_apollo_candle_causal_core
from tests.fixtures.apollo_strategy import apollo_row, build_apollo_fixture_bundle

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _run(rows, **overrides):
    bundle = build_apollo_fixture_bundle(dataset_id=overrides.pop("dataset_id", "ds-mtm"), rows=rows, **overrides)
    return run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    ), bundle


def test_equity_moves_with_unrealized_pnl_while_position_still_open() -> None:
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),  # signal
        apollo_row(UTC_START + timedelta(hours=1), "4000", "4001", "3999", "4020"),  # entry fills at 4000; close 4020 (favourable, unrealised)
        apollo_row(UTC_START + timedelta(hours=2), "4020", "4021", "4019", "3990"),  # close 3990 (adverse, unrealised)
        apollo_row(UTC_START + timedelta(hours=3), "3990", "3991", "3989", "3990"),
    ]
    result, _bundle = _run(rows, dataset_id="ds-mtm-1", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    assert result.terminal_position_state == "OPEN"  # SL/TP never touched -- position genuinely still open
    assert len(result.trades) == 0  # no COMPLETED trade -- nothing was realised

    equity_bar1 = result.equity_curve[1]
    equity_bar2 = result.equity_curve[2]
    assert equity_bar1.position_open is True
    assert Decimal(equity_bar1.unrealized_pnl_usd) == Decimal(20)  # 4020 - 4000
    assert Decimal(equity_bar2.unrealized_pnl_usd) == Decimal(-10)  # 3990 - 4000

    starting_capital = Decimal(result.starting_capital_usd)
    # Balance (realised only) is unchanged while the position is open -- the
    # entire equity swing bar-to-bar comes from mark-to-market unrealised P&L.
    assert Decimal(equity_bar1.balance_usd) == starting_capital
    assert Decimal(equity_bar2.balance_usd) == starting_capital
    assert Decimal(equity_bar1.equity_usd) == starting_capital + Decimal(20)
    assert Decimal(equity_bar2.equity_usd) == starting_capital - Decimal(10)
    assert Decimal(equity_bar2.equity_usd) < Decimal(equity_bar1.equity_usd)


def test_running_max_drawdown_reflects_unrealized_equity_dip() -> None:
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),
        apollo_row(UTC_START + timedelta(hours=1), "4000", "4001", "3999", "4050"),  # +50 unrealised
        apollo_row(UTC_START + timedelta(hours=2), "4050", "4051", "4049", "3970"),  # equity dips relative to peak
        apollo_row(UTC_START + timedelta(hours=3), "3970", "3971", "3969", "3970"),
    ]
    result, _ = _run(rows, dataset_id="ds-mtm-2", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    max_dd = Decimal(result.max_drawdown_usd)
    # Peak equity was starting_capital+50 (bar1); bar2 equity is starting_capital-30 -- an 80 USD
    # drawdown driven entirely by mark-to-market, never touched by a completed trade.
    assert max_dd == Decimal(80)
    assert len(result.trades) == 0
