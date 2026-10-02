"""PID-006B falsification tests 11 and 12: two independent identical runs
reproduce exact hashes/ledger/equity; controlled parameter/data/policy
changes perturb the appropriate identities and no others (the three axes
-- decision, fill/trade, economic -- are genuinely independent, not
accidentally coupled)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from darwin.apollo import run_apollo_candle_causal_core
from darwin.apollo.capability import FIXED_MECHANICAL_TEST_COST
from tests.fixtures.apollo_strategy import apollo_row, build_apollo_fixture_bundle

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def _rows(n: int = 8, *, seed_high: int = 4020, close_shift: int = 0):
    out = []
    for i in range(n):
        base = 3990 + (i % 3) * 15
        close = base + (5 if i % 2 else -3) + close_shift
        out.append(apollo_row(UTC_START + timedelta(hours=i), str(base), str(seed_high + i), str(base - 10), str(close)))
    return out


def _run(rows, **overrides):
    dataset_id = overrides.pop("dataset_id", "ds-perturb")
    bundle = build_apollo_fixture_bundle(dataset_id=dataset_id, rows=rows, **overrides)
    result = run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, executable_plan=bundle.executable_plan,
        parameter_set=bundle.parameter_set, execution_policy=bundle.execution_policy,
        partition_policy=bundle.partition_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    )
    return result, bundle


def test_falsification11_two_independent_identical_runs_reproduce_exact_hashes() -> None:
    rows = _rows()
    result_a, _ = _run(rows, dataset_id="ds-determinism-a")
    result_b, _ = _run(rows, dataset_id="ds-determinism-a")  # same dataset_id -> identical MarketDataset content/identity too
    assert result_a.decision_stream_hash == result_b.decision_stream_hash
    assert result_a.fill_trade_sequence_hash == result_b.fill_trade_sequence_hash
    assert result_a.economic_outcome_hash == result_b.economic_outcome_hash
    assert result_a.trades == result_b.trades
    assert result_a.equity_curve == result_b.equity_curve
    assert result_a.decision_stream == result_b.decision_stream


def test_falsification12_parameter_change_perturbs_decision_and_downstream_hashes() -> None:
    """Changing entry_threshold_usd changes WHICH bars signal -> changes
    decision_stream_hash, and (since the resulting trades differ)
    fill_trade_sequence_hash and economic_outcome_hash too."""
    rows = _rows()
    low_threshold, _ = _run(rows, dataset_id="ds-perturb-param", entry_threshold=Decimal(3990))
    high_threshold, _ = _run(rows, dataset_id="ds-perturb-param", entry_threshold=Decimal(4025))
    assert low_threshold.decision_stream_hash != high_threshold.decision_stream_hash
    assert low_threshold.fill_trade_sequence_hash != high_threshold.fill_trade_sequence_hash
    assert low_threshold.economic_outcome_hash != high_threshold.economic_outcome_hash


def test_falsification12_cost_policy_change_perturbs_economic_hash_but_never_decision_hash() -> None:
    """The exact axis-independence proof PID-006B names explicitly: change
    ONLY the cost policy -- decision_stream_hash (purely signal-derived)
    must be IDENTICAL; fill_trade_sequence_hash (fill prices embed cost)
    and economic_outcome_hash (P&L embeds cost) must both DIFFER.

    Uses deliberately wide SL/TP distances so no exit is ever triggered in
    either run -- isolating the proof from the (separate, legitimate)
    fact that a cost-shifted fill price also shifts absolute SL/TP levels
    and could otherwise change exit TIMING (see the risk-parameter test
    below, which does not make this "decision hash unaffected" claim)."""
    rows = _rows()
    zero_cost_result, _ = _run(
        rows, dataset_id="ds-perturb-cost", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000)
    )
    real_cost_result, _ = _run(
        rows, dataset_id="ds-perturb-cost", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000),
        cost_methodology=FIXED_MECHANICAL_TEST_COST,
    )

    assert zero_cost_result.decision_stream_hash == real_cost_result.decision_stream_hash
    assert zero_cost_result.decision_stream == real_cost_result.decision_stream
    assert zero_cost_result.fill_trade_sequence_hash != real_cost_result.fill_trade_sequence_hash
    assert zero_cost_result.economic_outcome_hash != real_cost_result.economic_outcome_hash
    # The same entry bar/order happened in both runs (decision-independent
    # of cost) -- only the economics of that exact same fill differ: the
    # cost-shifted entry price changes the running mark-to-market
    # unrealised P&L, hence final equity.
    assert len(zero_cost_result.order_stream) == len(real_cost_result.order_stream) == 1
    assert zero_cost_result.order_stream[0].created_at_bar_index == real_cost_result.order_stream[0].created_at_bar_index
    assert zero_cost_result.fills[0].fill_price_fp != real_cost_result.fills[0].fill_price_fp
    assert zero_cost_result.final_equity_usd != real_cost_result.final_equity_usd


def test_falsification12_dataset_change_perturbs_decision_hash() -> None:
    """A +50 close-price shift flips `signal_fired` on several bars that
    were sitting just below the (unchanged) entry_threshold_usd -- a
    genuinely different market history, never merely a different
    dataset_id/label. Wide SL/TP isolates this from any exit-timing
    interaction, so the ONLY thing that can differ is which bars signal."""
    rows_a = _rows(close_shift=0)
    rows_b = _rows(close_shift=50)
    result_a, _ = _run(rows_a, dataset_id="ds-perturb-data-a", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    result_b, _ = _run(rows_b, dataset_id="ds-perturb-data-b", stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(1000))
    assert [d.signal_fired for d in result_a.decision_stream] != [d.signal_fired for d in result_b.decision_stream]
    assert result_a.decision_stream_hash != result_b.decision_stream_hash


def test_falsification12_risk_parameter_change_perturbs_fill_and_economic_hash() -> None:
    """SL/TP distances change where/whether a position exits, which
    changes fill/trade and economic identities. (Note: because an
    earlier/later exit also changes how soon the position frees up for a
    new entry, this MAY also change decision_stream_hash for this
    fixture's multi-signal dataset -- unlike the cost-policy case above,
    SL/TP genuinely does participate in the causal position-open/closed
    state the decision stream records, so no claim is made here about
    decision_stream_hash either way.)"""
    rows = _rows()
    tight, _ = _run(rows, dataset_id="ds-perturb-risk", stop_loss_distance=Decimal(2), take_profit_distance=Decimal(3))
    wide, _ = _run(rows, dataset_id="ds-perturb-risk", stop_loss_distance=Decimal(500), take_profit_distance=Decimal(500))
    assert tight.fill_trade_sequence_hash != wide.fill_trade_sequence_hash
    assert tight.economic_outcome_hash != wide.economic_outcome_hash
