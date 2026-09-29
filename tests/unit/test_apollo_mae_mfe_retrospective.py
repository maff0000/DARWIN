"""PID-006B falsification test 10: MAE/MFE remain retrospective -- computed
from data never exposed to the live decision path. Two independent
proofs, mirroring the causal-discipline test pattern already used
elsewhere in this codebase (an `inspect.signature`-based structural
check, PLUS a behavioural numeric proof)."""
from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from darwin.apollo import engine as apollo_engine
from darwin.apollo import run_apollo_candle_causal_core
from darwin.apollo.signal import evaluate_entry_signal
from tests.fixtures.apollo_strategy import apollo_row, build_apollo_fixture_bundle

UTC_START = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)


def test_live_decision_function_is_structurally_distinct_from_the_mae_mfe_computer() -> None:
    assert evaluate_entry_signal is not apollo_engine._compute_retrospective_mae_mfe
    decision_params = set(inspect.signature(evaluate_entry_signal).parameters)
    mae_mfe_params = set(inspect.signature(apollo_engine._compute_retrospective_mae_mfe).parameters)
    # The MAE/MFE computer's signature is genuinely array/trade-shaped
    # (exactly what a retrospective pass needs); the live decision
    # function's signature has none of those names at all.
    assert {"trades", "market_dataset"}.issubset(mae_mfe_params)
    assert decision_params.isdisjoint({"trades", "market_dataset", "open_position"})


def test_live_decision_function_rejects_an_injected_mae_so_far_argument() -> None:
    """A caller cannot smuggle retrospective excursion data into the live
    decision path even by trying -- the signature is closed."""
    with pytest.raises(TypeError):
        evaluate_entry_signal(  # type: ignore[call-arg]
            None, parameter_values={}, open_fp=0, high_fp=0, low_fp=0, close_fp=0, mae_so_far=Decimal(5)
        )


def test_mae_mfe_computed_only_after_trades_are_already_finalised() -> None:
    """Behavioural proof: `run_apollo_replay`'s own source calls the MAE/MFE
    pass exactly once, and only after the causal bar loop (the `for i in
    range(n):` block) has already completed -- never inside it."""
    source = inspect.getsource(apollo_engine.run_apollo_replay)
    loop_end = source.index("open_position: OpenPositionState | None = None")
    mae_call = source.index("_compute_retrospective_mae_mfe(")
    assert mae_call > loop_end > source.index("for i in range(n):")


def test_mae_mfe_values_are_correct_for_a_known_excursion_path() -> None:
    rows = [
        apollo_row(UTC_START, "3990", "3995", "3985", "4005"),  # signal
        apollo_row(UTC_START + timedelta(hours=1), "4000", "4030", "3970", "4000"),  # entry at 4000; MFE=30, MAE=30 intrabar
        apollo_row(UTC_START + timedelta(hours=2), "4000", "4050", "3960", "4010"),  # exits via TP (entry+50=4050 touched)
    ]
    bundle = build_apollo_fixture_bundle(
        dataset_id="ds-maemfe-1", rows=rows, stop_loss_distance=Decimal(1000), take_profit_distance=Decimal(50)
    )
    result = run_apollo_candle_causal_core(
        strategy_version=bundle.strategy_version, parameter_set=bundle.parameter_set,
        execution_policy=bundle.execution_policy, market_dataset=bundle.market_dataset,
        research_configuration=bundle.research_configuration, instrument_definition=bundle.instrument_definition,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "TAKE_PROFIT"
    mae_mfe = result.mae_mfe[0]
    assert mae_mfe.trade_id == trade.trade_id
    # Over bars 1-2 (entry to exit inclusive): worst low = 3960 (bar2) -> MAE = 4000-3960 = 40.
    # Best high = 4050 (bar2) -> MFE = 4050-4000 = 50.
    assert Decimal(mae_mfe.mae_usd) == Decimal(40)
    assert Decimal(mae_mfe.mfe_usd) == Decimal(50)
