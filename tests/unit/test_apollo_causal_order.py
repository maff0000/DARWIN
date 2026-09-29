"""PID-006B causal per-bar order tests -- falsification tests 1-5, plus
the no-pyramiding invariant and the same-bar-exit-then-new-entry allowance
the spec explicitly carves out.

All fixtures here use `ZERO_COST` so fill prices are exactly the bar's raw
open/SL/TP price with no cost adjustment -- isolating causal-timing/
intrabar-resolution behaviour from cost mechanics (which
tests/unit/test_apollo_economics.py and the cost-perturbation case in
tests/unit/test_apollo_determinism_and_perturbation.py cover separately).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from darwin.apollo import run_apollo_candle_causal_core
from darwin.hermes.dataset import to_fixed_point
from tests.fixtures.apollo_strategy import apollo_row, build_apollo_fixture_bundle

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _run(rows, **overrides):
    bundle = build_apollo_fixture_bundle(dataset_id=overrides.pop("dataset_id", "ds-causal"), rows=rows, **overrides)
    return run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    ), bundle


# ---- falsification test 2 + 3: signal bar cannot fill itself; next-bar-open exact ----


def test_falsification2_and_3_entry_fills_at_next_bar_open_never_signal_bar() -> None:
    """Bar 1 closes above threshold (signal fires). If the engine
    incorrectly filled on the SIGNAL bar itself, the fill price would be
    bar 1's own open (3990). The correct behaviour fills at bar 2's real
    open (4006) -- a materially different, exact price, proving both (a)
    no same-bar fill and (b) the fill price is genuinely the next bar's
    real open, not an approximation of it."""
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "3990"),                # bar0: no signal (close 3990 < 4000)
        apollo_row(UTC_START + timedelta(hours=1), "3990", "4010", "3988", "4005"),  # bar1: close 4005 > 4000 -> signal
        apollo_row(UTC_START + timedelta(hours=2), "4006", "4040", "3960", "4020"),  # bar2: real next-bar open = 4006
        apollo_row(UTC_START + timedelta(hours=3), "4020", "4050", "4000", "4030"),
    ]
    # Wide SL/TP so no exit is triggered within this small dataset -- isolates
    # the entry-timing proof from intrabar exit/re-entry behaviour (covered
    # separately below).
    result, _ = _run(rows, dataset_id="ds-causal-23", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    entry_fills = [f for f in result.fills if f.role == "ENTRY"]
    assert len(entry_fills) == 1
    entry_fill = entry_fills[0]
    # Filled on bar index 2 (the bar AFTER the signal bar, index 1) -- never on the signal bar itself (index 1).
    assert entry_fill.bar_index == 2
    order = result.order_stream[0]
    assert order.created_at_bar_index == 1
    assert entry_fill.bar_index != order.created_at_bar_index
    # Exact next-bar-open price, ZERO_COST so no adjustment: 4006, never bar1's own open (3990).
    assert entry_fill.fill_price_fp == to_fixed_point(Decimal(4006))
    assert entry_fill.fill_price_fp != to_fixed_point(Decimal(3990))


def test_falsification1_future_data_cannot_affect_earlier_decisions() -> None:
    """Behavioural causal-clock proof: replaying only the first K bars of
    a dataset produces IDENTICAL decisions for bars 0..K-2 as replaying
    the full dataset -- if any decision secretly depended on a bar beyond
    its own close, truncating the dataset would change an earlier
    decision. (The last decision, K-1, legitimately differs across the
    two runs only in whether its resulting order can still fill --
    compared separately below.)"""
    rows = [
        apollo_row(UTC_START + timedelta(hours=i), "3990", "4010", "3985", str(3990 + i * 20))
        for i in range(6)
    ]
    full_result, _ = _run(rows, dataset_id="ds-causal-1-full")
    truncated_result, _ = _run(rows[:4], dataset_id="ds-causal-1-trunc")

    for i in range(3):  # bars 0..2 -- neither run's decision for these could see bar 3+
        full_decision = full_result.decision_stream[i]
        trunc_decision = truncated_result.decision_stream[i]
        assert full_decision.signal_fired == trunc_decision.signal_fired
        assert full_decision.position_open_at_decision == trunc_decision.position_open_at_decision
        assert full_decision.order_created == trunc_decision.order_created

    # Structural half of the same proof: the live decision function's
    # signature makes this impossible to violate even in principle -- see
    # tests/unit/test_apollo_signal.py::test_evaluate_entry_signal_signature_has_no_array_or_index_parameter.


# ---- falsification test 4: same-bar SL+TP resolves SL-first ------------


def test_falsification4_same_bar_sl_and_tp_touch_resolves_sl_first() -> None:
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),  # signal at close
        apollo_row(UTC_START + timedelta(hours=1), "4000", "4001", "3999", "4000"),  # entry fills at open=4000; sl=3995 tp=4010 (thresholds below)
        apollo_row(UTC_START + timedelta(hours=2), "4000", "4015", "3990", "4000"),  # both SL (3995) and TP (4010) touched this bar
        apollo_row(UTC_START + timedelta(hours=3), "4000", "4001", "3999", "4000"),
    ]
    result, _ = _run(rows, dataset_id="ds-causal-4", stop_loss_distance=Decimal(5), take_profit_distance=Decimal(10))
    assert len(result.trades) >= 1
    trade = result.trades[0]
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.exit_bar_index == 2
    # SL price (entry 4000 - 5 = 3995), never the TP price (4010).
    assert trade.exit_fill_price_fp == to_fixed_point(Decimal(3995))


def test_falsification4_naive_tp_first_would_have_disagreed() -> None:
    """Demonstrates the SL-first proof actually bites: an intentionally
    WRONG "TP-first" resolution of the exact same bar would report
    TAKE_PROFIT, not STOP_LOSS -- so the assertion above is genuinely
    discriminating, not vacuously true regardless of resolution order."""
    sl_fp, tp_fp = to_fixed_point(Decimal(3995)), to_fixed_point(Decimal(4010))
    bar_high_fp, bar_low_fp = to_fixed_point(Decimal(4015)), to_fixed_point(Decimal(3990))
    sl_touched = bar_low_fp <= sl_fp
    tp_touched = bar_high_fp >= tp_fp
    assert sl_touched and tp_touched  # the ambiguous case genuinely exists in this fixture
    naive_tp_first_reason = "TAKE_PROFIT" if tp_touched else ("STOP_LOSS" if sl_touched else None)
    conservative_sl_first_reason = "STOP_LOSS" if sl_touched else ("TAKE_PROFIT" if tp_touched else None)
    assert naive_tp_first_reason != conservative_sl_first_reason


# ---- falsification test 5: wick touches use high/low, not close --------


def test_falsification5_wick_low_triggers_sl_even_though_close_did_not() -> None:
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),
        apollo_row(UTC_START + timedelta(hours=1), "4000", "4001", "3999", "4000"),  # entry at open=4000, sl=3995
        # Close (4002) alone never touches SL (3995) -- but the LOW (3994) does.
        apollo_row(UTC_START + timedelta(hours=2), "4000", "4008", "3994", "4002"),
        apollo_row(UTC_START + timedelta(hours=3), "4002", "4010", "4000", "4005"),
    ]
    result, _ = _run(rows, dataset_id="ds-causal-5", stop_loss_distance=Decimal(5), take_profit_distance=Decimal(100))
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "STOP_LOSS"
    assert trade.exit_bar_index == 2
    # Proves the discriminating power: close-only would have MISSED this touch.
    close_fp = to_fixed_point(Decimal(4002))
    sl_fp = to_fixed_point(Decimal(3995))
    assert close_fp > sl_fp  # close never breaches SL
    low_fp = to_fixed_point(Decimal(3994))
    assert low_fp <= sl_fp  # but the wick low does


def test_falsification5_wick_high_triggers_tp_even_though_close_did_not() -> None:
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),
        apollo_row(UTC_START + timedelta(hours=1), "4000", "4001", "3999", "4000"),  # entry at open=4000, tp=4010
        apollo_row(UTC_START + timedelta(hours=2), "4000", "4012", "3998", "4001"),  # close never reaches TP, high does
        apollo_row(UTC_START + timedelta(hours=3), "4001", "4010", "3999", "4005"),
    ]
    result, _ = _run(rows, dataset_id="ds-causal-5b", stop_loss_distance=Decimal(100), take_profit_distance=Decimal(10))
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "TAKE_PROFIT"
    close_fp = to_fixed_point(Decimal(4001))
    tp_fp = to_fixed_point(Decimal(4010))
    assert close_fp < tp_fp
    high_fp = to_fixed_point(Decimal(4012))
    assert high_fp >= tp_fp


# ---- no-pyramiding + same-bar re-entry allowance ------------------------


def test_no_pyramiding_blocks_new_entry_while_position_open() -> None:
    """close stays above threshold for every bar after entry, but no
    second entry order is ever created while the first position remains
    open."""
    rows = [
        apollo_row(UTC_START + timedelta(hours=i), "4000", "4001", "3999", "4005")
        for i in range(6)
    ]
    result, _ = _run(rows, dataset_id="ds-nopyr", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    entry_fills = [f for f in result.fills if f.role == "ENTRY"]
    assert len(entry_fills) == 1  # never pyramided into a second position
    for decision in result.decision_stream:
        if decision.position_open_at_decision:
            assert decision.order_created is False


def test_same_bar_exit_then_close_evaluation_may_create_a_new_order() -> None:
    """PID-006B explicit allowance: if intrabar SL/TP makes the position
    flat again within the same bar the entry filled on, that bar's
    close-time evaluation may still create a NEW order for the next bar."""
    # Deliberately only TWO bars: bar1 is the last bar in this dataset, so
    # the new order bar1's close-time evaluation creates has nowhere left
    # to fill (UNFILLED_END_OF_DATA) -- isolating the "may still create a
    # new order" proof from any further exit/re-entry cascade.
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),
        # bar1: entry fills at open=4000 (sl=3995,tp=4999); intrabar SL touch (low 3990) AND close still > threshold.
        apollo_row(UTC_START + timedelta(hours=1), "4000", "4006", "3990", "4006"),
    ]
    result, _ = _run(rows, dataset_id="ds-samebar-reentry", stop_loss_distance=Decimal(5), take_profit_distance=Decimal(999))
    bar1_decision = result.decision_stream[1]
    assert bar1_decision.position_open_at_decision is False  # position was closed intrabar before close-time eval
    assert bar1_decision.order_created is True  # a NEW order was created for the next bar
    assert len(result.trades) == 1
    assert result.trades[0].exit_bar_index == 1
    second_order = next(o for o in result.order_stream if o.created_at_bar_index == 1)
    assert second_order.eligible_from_bar_index is None
    assert second_order.status == "UNFILLED_END_OF_DATA"
