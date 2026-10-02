"""PID-006B APOLLO Candle Causal Core -- the replay engine itself.

Exact per-bar causal order (PID-006B spec, non-negotiable):

    BAR OPEN
      -> fill eligible pending entry order (if any) at this bar's open price
      -> evaluate active SL/TP against THIS bar's high/low
      -> mark position/equity at this bar
    BAR CLOSE
      -> evaluate strategy against this now-closed bar
      -> possibly create an order eligible at the NEXT bar's open

A signal is evaluated only when its source candle has closed; a
close-time decision creates an order eligible at the next canonical
bar's open, on the SAME timeframe -- never same-bar. Same-bar SL+TP
resolves `CONSERVATIVE_SL_FIRST`. One position only, no pyramiding: while
a position is open, no new entry order may be created even if the
close-time evaluation would otherwise fire. An unfilled order at
end-of-data is a valid terminal outcome, never an error.

MAE/MFE are computed in a wholly separate, retrospective pass
(`_compute_retrospective_mae_mfe`), AFTER the causal replay loop has
already finished -- never inside it, never visible to
`darwin.apollo.signal.evaluate_entry_signal` (see that module's
docstring and tests/unit/test_apollo_mae_mfe_retrospective.py for the
structural proof).

An internal engine defect is never encoded as a losing trade: unexpected
exceptions raised while processing bar `i` are caught and re-raised as a
typed `EngineDefectError` naming that bar index, aborting the replay --
this module's own `ApolloError` subclasses (raised deliberately, e.g. by
`evaluate_entry_signal`) are never re-wrapped.

Central Architecture correction CA-006B-3: this function no longer merely
trusts the caller to pass the SAME `MarketDataset` that was preflighted
-- it mechanically re-verifies `market_dataset.dataset_id`/
`.fingerprint_sha256` against the exact identities `PreflightResult`
carries (`bound_dataset_id`/`bound_dataset_fingerprint`) BEFORE touching
bar 0, raising a governed `InvalidConfigurationError` on any mismatch.

Central Architecture correction CA-006B-6: the three evidence identities
below each bind the relevant upstream identity -- `decision_stream_hash`
binds engine methodology + the compiled plan's own fingerprint +
`ParameterSetVersion.fingerprint` + the dataset's own content fingerprint
(deliberately NOT the execution/cost policy -- decision identity stays
cost-independent); `fill_trade_sequence_hash` additionally binds
`decision_stream_hash` + `ExecutionPolicyVersion.fingerprint`;
`economic_outcome_hash` additionally binds `fill_trade_sequence_hash` AND
the MAE/MFE excursion evidence (CA-006B-9). A fourth,
`evidence_envelope_hash`, binds `ResearchConfiguration.fingerprint` +
the research-partition identity + engine methodology + all three output
identities together, so a change to ANY upstream identity remains
scientifically distinguishable even on the rare occasion the numeric
replay output happens to come out identical.

Central Architecture correction CA-006B-9 (MAE/MFE candle-resolution
governance): at OHLC resolution, exact intrabar ordering is unknowable --
presenting a completed trade's full exit-bar high/low as if it were
certain, exact excursion would silently present ambiguous data as exact
fact (extrema on the exit bar can occur AFTER the position has already
closed within that same bar). This module adopts ONE coherent, documented,
asymmetric methodology (`MAE_MFE_METHODOLOGY_ID = "CONSERVATIVE_EXCURSION_V1"`),
chosen deliberately to never understate risk and never overstate reward:

- MAE (adverse excursion) always uses the FULL raw low across the whole
  entry-to-exit bar range, INCLUDING the exit bar itself -- any adverse
  price action on the exit bar is credited as real risk exposure even if
  its exact timing (before/after the trigger) is unknowable, because a
  risk measure must never hide a real adverse print behind an ambiguity
  excuse.
- MFE (favourable excursion) uses the full raw high across every bar
  STRICTLY BEFORE the exit bar (unambiguous -- the trade was definitely
  open the whole bar), but caps the exit bar's own contribution at the
  CERTAIN evidence only: if the trade exited via TAKE_PROFIT, the exit
  bar is known to have reached at least the TP trigger price (that is
  why it exited) -- that certain level is credited, and nothing further,
  even if the raw bar high is higher (consistent with the same
  CONSERVATIVE_SL_FIRST discipline already governing the exit itself: SL
  wins when ambiguous, so any further favourable excursion on that bar
  is deliberately never credited beyond the trigger that actually
  realised it). If it exited via STOP_LOSS, the exit bar's own high is
  EXCLUDED entirely from MFE -- a same-bar favourable print on a
  stop-out bar is exactly the ambiguous, possibly-post-exit case this
  correction exists to stop presenting as fact. A still-OPEN position
  (never exited) has no exit-bar ambiguity at all and keeps the full raw
  high/low across its entire range unchanged.

Every `MaeMfeRecord` explicitly states its own `methodology_id` and
measurement interval (`measurement_start_bar_index`/
`measurement_end_bar_index`), plus a human-readable `mae_resolution`/
`mfe_resolution` note naming exactly how the exit bar was handled -- this
evidence is never a bare, falsely-precise number with no stated
provenance. The MAE/MFE records themselves are bound into
`economic_outcome_hash` (via `_economic_payload`), so a change to this
excursion-resolution methodology changes the governed economic evidence
identity even when every other recorded figure is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from darwin.apollo.economics import RiskParameters
from darwin.apollo.errors import (
    ApolloError,
    EngineDefectError,
    InvalidConfigurationError,
)
from darwin.apollo.preflight import PreflightResult
from darwin.apollo.signal import evaluate_entry_signal
from darwin.hermes.dataset import MarketDataset, from_fixed_point
from darwin.specification.fingerprint import canonical_hash, canonicalize

#: Stable identity of this engine implementation -- bound into
#: `decision_stream_hash`/`evidence_envelope_hash` (CA-006B-6) so a
#: future engine upgrade never silently produces evidence
#: indistinguishable from an earlier, differently-behaved implementation.
ENGINE_ID = "darwin.apollo.engine.ApolloCandleCausalCore"
ENGINE_VERSION = "1.0.0"

#: CA-006B-9: the one governed MAE/MFE candle-resolution methodology this
#: engine implements -- see module docstring for the full rationale.
#: Bound into every `MaeMfeRecord` and, transitively, into
#: `economic_outcome_hash`.
MAE_MFE_METHODOLOGY_ID = "CONSERVATIVE_EXCURSION_V1"


@dataclass(frozen=True)
class DecisionRecord:
    """One row of the decision stream -- purely signal-derived, never
    touched by cost/fill mechanics (so a cost-policy change can never
    change `decision_stream_hash`)."""

    bar_index: int
    open_time_epoch_s: int
    signal_fired: bool
    position_open_at_decision: bool
    order_created: bool


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    created_at_bar_index: int
    eligible_from_bar_index: int | None  # None iff status == UNFILLED_END_OF_DATA
    direction: str
    quantity: str  # Decimal, stringified for a stable hash-independent repr
    status: str  # "FILLED" | "UNFILLED_END_OF_DATA"


@dataclass(frozen=True)
class FillRecord:
    order_id: str
    bar_index: int
    fill_price_fp: int
    quantity: str
    role: str  # "ENTRY" | "EXIT"


@dataclass(frozen=True)
class TradeRecord:
    """A COMPLETED (entry + exit) trade only -- an open position at the
    end of the dataset is recorded separately, in
    `ApolloEngineResult.open_position`, never as a completed trade with a
    fabricated exit."""

    trade_id: str
    entry_order_id: str
    entry_bar_index: int
    entry_fill_price_fp: int
    exit_bar_index: int
    exit_fill_price_fp: int
    exit_reason: str  # "STOP_LOSS" | "TAKE_PROFIT"
    quantity: str
    realized_pnl_usd: str
    fee_usd: str


@dataclass(frozen=True)
class OpenPositionState:
    trade_id: str
    entry_bar_index: int
    entry_fill_price_fp: int
    quantity: str
    mark_price_fp: int
    unrealized_pnl_usd: str


@dataclass(frozen=True)
class EquityPoint:
    bar_index: int
    open_time_epoch_s: int
    balance_usd: str
    unrealized_pnl_usd: str
    equity_usd: str
    position_open: bool


@dataclass(frozen=True)
class MaeMfeRecord:
    """Retrospective-only excursion evidence, computed once per completed
    trade (or still-open position) AFTER the causal replay loop has
    finished -- see module docstring for the full CA-006B-9 methodology.
    Never a bare number: `methodology_id` + the measurement interval +
    an explicit per-side resolution note are always carried alongside the
    USD figures, so this evidence can never be mistaken for a
    falsely-precise single number with no stated provenance."""

    trade_id: str
    mae_usd: str
    mfe_usd: str
    methodology_id: str
    measurement_start_bar_index: int
    measurement_end_bar_index: int
    mae_resolution: str
    mfe_resolution: str


@dataclass(frozen=True)
class ApolloEngineResult:
    bars_processed: int
    decision_stream: tuple[DecisionRecord, ...]
    order_stream: tuple[OrderRecord, ...]
    fills: tuple[FillRecord, ...]
    trades: tuple[TradeRecord, ...]
    mae_mfe: tuple[MaeMfeRecord, ...]
    equity_curve: tuple[EquityPoint, ...]
    open_position: OpenPositionState | None
    terminal_position_state: str  # "FLAT" | "OPEN"
    starting_capital_usd: str
    final_balance_usd: str
    final_equity_usd: str
    peak_equity_usd: str
    max_drawdown_usd: str
    decision_stream_hash: str
    fill_trade_sequence_hash: str
    economic_outcome_hash: str
    #: CA-006B-3/CA-006B-6: the exact bound identities this result was
    #: produced against -- `darwin.apollo.persistence` independently
    #: re-verifies these before pairing this result with a
    #: `ResearchConfiguration`/`MarketDataset` row.
    bound_dataset_id: str
    bound_dataset_fingerprint: str
    bound_research_configuration_fingerprint: str
    #: CA-006B-6: binds ResearchConfiguration + partition + engine
    #: methodology + all three output identities together.
    evidence_envelope_hash: str


def _decision_payload(
    decisions: tuple[DecisionRecord, ...],
    *,
    executable_strategy_plan_fingerprint: str,
    parameter_set_fingerprint: str,
    dataset_fingerprint: str,
) -> dict:
    """CA-006B-6: binds engine methodology + the compiled plan's own
    fingerprint + ParameterSetVersion's fingerprint + the dataset's
    content fingerprint -- deliberately NEVER the execution/cost policy
    (decision identity stays cost-independent, proven by
    tests/unit/test_apollo_determinism_and_perturbation.py)."""
    return {
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "executable_strategy_plan_fingerprint": executable_strategy_plan_fingerprint,
        "parameter_set_fingerprint": parameter_set_fingerprint,
        "dataset_fingerprint": dataset_fingerprint,
        "decisions": [canonicalize(d) for d in decisions],
    }


def _fill_trade_payload(
    orders: tuple[OrderRecord, ...],
    fills: tuple[FillRecord, ...],
    trades: tuple[TradeRecord, ...],
    *,
    decision_stream_hash: str,
    execution_policy_fingerprint: str,
) -> dict:
    """CA-006B-6: binds `decision_stream_hash` (so fill/trade identity is
    traceably downstream of decision identity) plus
    `ExecutionPolicyVersion.fingerprint` (every execution axis, including
    cost -- fill prices themselves embed cost mechanics)."""
    return {
        "decision_stream_hash": decision_stream_hash,
        "execution_policy_fingerprint": execution_policy_fingerprint,
        "orders": [canonicalize(o) for o in orders],
        "fills": [canonicalize(f) for f in fills],
        "trades": [canonicalize(t) for t in trades],
    }


def _economic_payload(
    trades: tuple[TradeRecord, ...],
    equity_curve: tuple[EquityPoint, ...],
    *,
    fill_trade_sequence_hash: str,
    mae_mfe: tuple[MaeMfeRecord, ...],
    starting_capital_usd: str,
    final_balance_usd: str,
    final_equity_usd: str,
    peak_equity_usd: str,
    max_drawdown_usd: str,
) -> dict:
    """CA-006B-6: binds `fill_trade_sequence_hash` (which already carries
    the execution-policy/cost identity transitively) plus the economic
    outcome payload itself. CA-006B-9: also binds the full `mae_mfe`
    excursion evidence (including its `methodology_id`/measurement
    interval/resolution notes) -- a change to the excursion-resolution
    methodology, or to any excursion value it produces, changes this
    hash even when every other recorded economic figure is unchanged."""
    return {
        "fill_trade_sequence_hash": fill_trade_sequence_hash,
        "starting_capital_usd": starting_capital_usd,
        "trade_pnls": [t.realized_pnl_usd for t in trades],
        "equity_curve": [canonicalize(e) for e in equity_curve],
        "mae_mfe": [canonicalize(m) for m in mae_mfe],
        "final_balance_usd": final_balance_usd,
        "final_equity_usd": final_equity_usd,
        "peak_equity_usd": peak_equity_usd,
        "max_drawdown_usd": max_drawdown_usd,
    }


def _evidence_envelope_payload(
    *,
    research_configuration_fingerprint: str,
    research_partition_policy_fingerprint: str,
    decision_stream_hash: str,
    fill_trade_sequence_hash: str,
    economic_outcome_hash: str,
) -> dict:
    """CA-006B-6: the explicit evidence-envelope identity binding
    `ResearchConfiguration.fingerprint` + research-partition identity +
    engine/methodology identity + the three output identities together."""
    return {
        "engine_id": ENGINE_ID,
        "engine_version": ENGINE_VERSION,
        "research_configuration_fingerprint": research_configuration_fingerprint,
        "research_partition_policy_fingerprint": research_partition_policy_fingerprint,
        "decision_stream_hash": decision_stream_hash,
        "fill_trade_sequence_hash": fill_trade_sequence_hash,
        "economic_outcome_hash": economic_outcome_hash,
    }


def _compute_retrospective_mae_mfe(
    *,
    trades: tuple[TradeRecord, ...],
    open_position: OpenPositionState | None,
    market_dataset: MarketDataset,
    quantity: Decimal,
    risk: RiskParameters,
) -> tuple[MaeMfeRecord, ...]:
    """Wholly separate from, and called strictly AFTER, the causal replay
    loop. Reads the FULL `high_fp`/`low_fp` arrays -- deliberately a
    different function, with a different signature, from
    `darwin.apollo.signal.evaluate_entry_signal`, which never receives an
    array at all. See the module docstring (CA-006B-9) for the full,
    governed, asymmetric `CONSERVATIVE_EXCURSION_V1` methodology this
    implements: MAE always uses the complete raw low across the whole
    range (including the exit bar -- never understate risk); MFE excludes
    or caps the exit bar's own contribution at the certain trigger
    evidence only (never overstate reward from an ambiguous, possibly
    post-exit print). A still-open position has no exit-bar ambiguity at
    all and keeps the full raw range for both sides, unchanged.
    """
    high_fp = market_dataset.high_fp
    low_fp = market_dataset.low_fp
    records: list[MaeMfeRecord] = []

    def _mae_usd(entry_fp: int, start: int, end: int) -> Decimal:
        worst_low = int(np.min(low_fp[start : end + 1]))
        mae_fp = max(0, entry_fp - worst_low)
        return from_fixed_point(mae_fp) * quantity

    def _mfe_usd_full_range(entry_fp: int, start: int, end: int) -> Decimal:
        best_high = int(np.max(high_fp[start : end + 1]))
        mfe_fp = max(0, best_high - entry_fp)
        return from_fixed_point(mfe_fp) * quantity

    for trade in trades:
        entry_fp = trade.entry_fill_price_fp
        start, end = trade.entry_bar_index, trade.exit_bar_index
        mae_usd = _mae_usd(entry_fp, start, end)

        if end > start:
            # Bars strictly BEFORE the exit bar: unambiguous, the position
            # was definitely open for the whole bar.
            prior_high_fp = int(np.max(high_fp[start:end]))
        else:
            # Same-bar exit: no prior bars exist at all.
            prior_high_fp = entry_fp

        if trade.exit_reason == "TAKE_PROFIT":
            tp_price_fp = entry_fp + risk.take_profit_distance_fp
            best_high_certain_fp = max(prior_high_fp, tp_price_fp)
            mfe_resolution = "CAPPED_AT_TAKE_PROFIT_TRIGGER_EXIT_BAR_BEYOND_TRIGGER_EXCLUDED"
        else:  # STOP_LOSS
            best_high_certain_fp = prior_high_fp
            mfe_resolution = "EXIT_BAR_EXCLUDED_STOP_LOSS_AMBIGUITY"
        mfe_fp = max(0, best_high_certain_fp - entry_fp)
        mfe_usd = from_fixed_point(mfe_fp) * quantity

        records.append(
            MaeMfeRecord(
                trade_id=trade.trade_id, mae_usd=str(mae_usd), mfe_usd=str(mfe_usd),
                methodology_id=MAE_MFE_METHODOLOGY_ID, measurement_start_bar_index=start, measurement_end_bar_index=end,
                mae_resolution="FULL_RANGE_INCLUSIVE_OF_EXIT_BAR", mfe_resolution=mfe_resolution,
            )
        )

    if open_position is not None:
        last_bar = market_dataset.record_count - 1
        entry_fp = open_position.entry_fill_price_fp
        mae_usd = _mae_usd(entry_fp, open_position.entry_bar_index, last_bar)
        mfe_usd = _mfe_usd_full_range(entry_fp, open_position.entry_bar_index, last_bar)
        records.append(
            MaeMfeRecord(
                trade_id=open_position.trade_id, mae_usd=str(mae_usd), mfe_usd=str(mfe_usd),
                methodology_id=MAE_MFE_METHODOLOGY_ID, measurement_start_bar_index=open_position.entry_bar_index,
                measurement_end_bar_index=last_bar, mae_resolution="FULL_RANGE_POSITION_STILL_OPEN",
                mfe_resolution="FULL_RANGE_POSITION_STILL_OPEN",
            )
        )

    return tuple(records)


def run_apollo_replay(*, preflight_result: PreflightResult, market_dataset: MarketDataset) -> ApolloEngineResult:
    """Runs the causal candle replay against an already-preflighted
    configuration (see `darwin.apollo.preflight.run_preflight`). Assumes
    preflight has already passed. Unlike earlier revisions of this
    module, it no longer merely TRUSTS that `market_dataset` is the same
    one `run_preflight` was given -- see the mechanical check immediately
    below (CA-006B-3).
    """
    if market_dataset.dataset_id != preflight_result.bound_dataset_id:
        raise InvalidConfigurationError(
            f"run_apollo_replay was given MarketDataset.dataset_id {market_dataset.dataset_id!r}, "
            f"which does not match the dataset preflight actually bound "
            f"({preflight_result.bound_dataset_id!r}) -- refusing to replay against a dataset "
            f"that was never preflighted, before touching a single bar"
        )
    if market_dataset.fingerprint_sha256 != preflight_result.bound_dataset_fingerprint:
        raise InvalidConfigurationError(
            f"run_apollo_replay was given a MarketDataset whose fingerprint_sha256 "
            f"({market_dataset.fingerprint_sha256!r}) does not match the dataset preflight "
            f"actually bound ({preflight_result.bound_dataset_fingerprint!r}) -- refusing to "
            f"replay against content that was never preflighted, before touching a single bar"
        )

    spec = preflight_result.entry_signal_spec
    risk = preflight_result.risk_parameters
    qty_econ = preflight_result.quantity_economics
    cost = preflight_result.cost_model
    quantity = qty_econ.quantity
    parameter_values = preflight_result.parameter_values

    n = market_dataset.record_count
    open_fp = market_dataset.open_fp
    high_fp = market_dataset.high_fp
    low_fp = market_dataset.low_fp
    close_fp = market_dataset.close_fp
    open_time = market_dataset.open_time_epoch_s

    decisions: list[DecisionRecord] = []
    orders: list[OrderRecord] = []
    fills: list[FillRecord] = []
    trades: list[TradeRecord] = []
    equity_curve: list[EquityPoint] = []

    balance = qty_econ.starting_capital_usd
    peak_equity = balance
    max_dd = Decimal(0)

    pending_order: dict | None = None
    position: dict | None = None
    order_counter = 0
    trade_counter = 0

    try:
        for i in range(n):
            # ---- BAR OPEN --------------------------------------------------
            if pending_order is not None and pending_order["eligible_from_bar_index"] == i:
                base_price_fp = int(open_fp[i])
                fill_price_fp = cost.buy_fill_price_fp(base_price_fp)
                entry_order_id = pending_order["order_id"]
                fills.append(
                    FillRecord(
                        order_id=entry_order_id, bar_index=i, fill_price_fp=fill_price_fp,
                        quantity=str(quantity), role="ENTRY",
                    )
                )
                trade_counter += 1
                position = {
                    "trade_id": f"trade-{trade_counter}",
                    "entry_order_id": entry_order_id,
                    "entry_bar_index": i,
                    "entry_fill_price_fp": fill_price_fp,
                    "sl_price_fp": fill_price_fp - risk.stop_loss_distance_fp,
                    "tp_price_fp": fill_price_fp + risk.take_profit_distance_fp,
                }
                pending_order = None

            if position is not None:
                bar_high_fp = int(high_fp[i])
                bar_low_fp = int(low_fp[i])
                sl_touched = bar_low_fp <= position["sl_price_fp"]
                tp_touched = bar_high_fp >= position["tp_price_fp"]
                exit_reason: str | None = None
                exit_base_fp: int | None = None
                if sl_touched:  # CONSERVATIVE_SL_FIRST: SL wins if both touched
                    exit_reason, exit_base_fp = "STOP_LOSS", position["sl_price_fp"]
                elif tp_touched:
                    exit_reason, exit_base_fp = "TAKE_PROFIT", position["tp_price_fp"]

                if exit_reason is not None:
                    exit_fill_price_fp = cost.sell_fill_price_fp(exit_base_fp)
                    fills.append(
                        FillRecord(
                            order_id=position["entry_order_id"], bar_index=i, fill_price_fp=exit_fill_price_fp,
                            quantity=str(quantity), role="EXIT",
                        )
                    )
                    gross_pnl = from_fixed_point(exit_fill_price_fp - position["entry_fill_price_fp"]) * quantity
                    realized_pnl = gross_pnl - cost.fee_usd
                    balance += realized_pnl
                    trades.append(
                        TradeRecord(
                            trade_id=position["trade_id"],
                            entry_order_id=position["entry_order_id"],
                            entry_bar_index=position["entry_bar_index"],
                            entry_fill_price_fp=position["entry_fill_price_fp"],
                            exit_bar_index=i,
                            exit_fill_price_fp=exit_fill_price_fp,
                            exit_reason=exit_reason,
                            quantity=str(quantity),
                            realized_pnl_usd=str(realized_pnl),
                            fee_usd=str(cost.fee_usd),
                        )
                    )
                    position = None

            # ---- mark position/equity at this bar ---------------------------
            if position is not None:
                mark_price_fp = int(close_fp[i])
                unrealized = from_fixed_point(mark_price_fp - position["entry_fill_price_fp"]) * quantity
            else:
                unrealized = Decimal(0)
            equity = balance + unrealized
            peak_equity = max(peak_equity, equity)
            max_dd = max(max_dd, peak_equity - equity)
            equity_curve.append(
                EquityPoint(
                    bar_index=i, open_time_epoch_s=int(open_time[i]), balance_usd=str(balance),
                    unrealized_pnl_usd=str(unrealized), equity_usd=str(equity), position_open=position is not None,
                )
            )

            # ---- BAR CLOSE ---------------------------------------------------
            signal_fired = evaluate_entry_signal(
                spec,
                parameter_values=parameter_values,
                open_fp=int(open_fp[i]),
                high_fp=int(high_fp[i]),
                low_fp=int(low_fp[i]),
                close_fp=int(close_fp[i]),
            )
            position_open_at_decision = position is not None
            order_created = False
            if signal_fired and not position_open_at_decision:
                if pending_order is not None:  # pragma: no cover - structurally unreachable, defensive
                    raise EngineDefectError(
                        f"bar {i}: a new entry order would be created while another order is "
                        f"already pending -- this violates the engine's own single-pending-order "
                        f"invariant and must never be silently allowed to double-order"
                    )
                order_counter += 1
                order_id = f"order-{order_counter}"
                if i + 1 < n:
                    orders.append(
                        OrderRecord(
                            order_id=order_id, created_at_bar_index=i, eligible_from_bar_index=i + 1,
                            direction="LONG", quantity=str(quantity), status="FILLED",
                        )
                    )
                    pending_order = {"order_id": order_id, "eligible_from_bar_index": i + 1}
                else:
                    orders.append(
                        OrderRecord(
                            order_id=order_id, created_at_bar_index=i, eligible_from_bar_index=None,
                            direction="LONG", quantity=str(quantity), status="UNFILLED_END_OF_DATA",
                        )
                    )
                order_created = True

            decisions.append(
                DecisionRecord(
                    bar_index=i, open_time_epoch_s=int(open_time[i]), signal_fired=signal_fired,
                    position_open_at_decision=position_open_at_decision, order_created=order_created,
                )
            )
    except ApolloError:
        raise
    except Exception as exc:
        raise EngineDefectError(
            f"APOLLO Candle Causal Core: internal defect while processing bar (engine state "
            f"corrupted) -- {exc.__class__.__name__}: {exc}"
        ) from exc

    open_position: OpenPositionState | None = None
    if position is not None:
        mark_price_fp = int(close_fp[n - 1])
        unrealized = from_fixed_point(mark_price_fp - position["entry_fill_price_fp"]) * quantity
        open_position = OpenPositionState(
            trade_id=position["trade_id"], entry_bar_index=position["entry_bar_index"],
            entry_fill_price_fp=position["entry_fill_price_fp"], quantity=str(quantity),
            mark_price_fp=mark_price_fp, unrealized_pnl_usd=str(unrealized),
        )

    final_equity = equity_curve[-1].equity_usd if equity_curve else str(balance)
    mae_mfe = _compute_retrospective_mae_mfe(
        trades=tuple(trades), open_position=open_position, market_dataset=market_dataset, quantity=quantity, risk=risk
    )

    decision_stream_hash = canonical_hash(
        _decision_payload(
            tuple(decisions),
            executable_strategy_plan_fingerprint=preflight_result.executable_strategy_plan_fingerprint,
            parameter_set_fingerprint=preflight_result.parameter_set_fingerprint,
            dataset_fingerprint=preflight_result.bound_dataset_fingerprint,
        )
    )
    fill_trade_sequence_hash = canonical_hash(
        _fill_trade_payload(
            tuple(orders), tuple(fills), tuple(trades),
            decision_stream_hash=decision_stream_hash,
            execution_policy_fingerprint=preflight_result.execution_policy_fingerprint,
        )
    )
    economic_outcome_hash = canonical_hash(
        _economic_payload(
            tuple(trades), tuple(equity_curve), fill_trade_sequence_hash=fill_trade_sequence_hash, mae_mfe=mae_mfe,
            starting_capital_usd=str(qty_econ.starting_capital_usd),
            final_balance_usd=str(balance), final_equity_usd=str(final_equity), peak_equity_usd=str(peak_equity),
            max_drawdown_usd=str(max_dd),
        )
    )
    evidence_envelope_hash = canonical_hash(
        _evidence_envelope_payload(
            research_configuration_fingerprint=preflight_result.research_configuration_fingerprint,
            research_partition_policy_fingerprint=preflight_result.research_partition_policy_fingerprint,
            decision_stream_hash=decision_stream_hash,
            fill_trade_sequence_hash=fill_trade_sequence_hash,
            economic_outcome_hash=economic_outcome_hash,
        )
    )

    return ApolloEngineResult(
        bars_processed=n,
        decision_stream=tuple(decisions),
        order_stream=tuple(orders),
        fills=tuple(fills),
        trades=tuple(trades),
        mae_mfe=mae_mfe,
        equity_curve=tuple(equity_curve),
        open_position=open_position,
        terminal_position_state="OPEN" if position is not None else "FLAT",
        starting_capital_usd=str(qty_econ.starting_capital_usd),
        final_balance_usd=str(balance),
        final_equity_usd=str(final_equity),
        peak_equity_usd=str(peak_equity),
        max_drawdown_usd=str(max_dd),
        decision_stream_hash=decision_stream_hash,
        fill_trade_sequence_hash=fill_trade_sequence_hash,
        economic_outcome_hash=economic_outcome_hash,
        bound_dataset_id=preflight_result.bound_dataset_id,
        bound_dataset_fingerprint=preflight_result.bound_dataset_fingerprint,
        bound_research_configuration_fingerprint=preflight_result.research_configuration_fingerprint,
        evidence_envelope_hash=evidence_envelope_hash,
    )
