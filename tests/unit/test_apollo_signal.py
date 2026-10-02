"""PID-006B engine-native entry-signal shape + live decision function
tests. The capability-gate tests (which derive `EntrySignalSpec` from a
compiled `ExecutableStrategyPlan`) now live in
tests/unit/test_apollo_plan_adapter.py (Central Architecture correction
CA-006B-1) -- this file is purely about the already-resolved
`EntrySignalSpec` shape and the pure per-bar evaluator."""
from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from darwin.apollo.signal import EntrySignalSpec, evaluate_entry_signal
from darwin.hermes.dataset import to_fixed_point
from darwin.specification.expressions import ComparisonOperator


@pytest.mark.parametrize(
    "operator,left,right,expected",
    [
        (ComparisonOperator.GT, "4005", "4000", True),
        (ComparisonOperator.GT, "3999", "4000", False),
        (ComparisonOperator.GTE, "4000", "4000", True),
        (ComparisonOperator.LT, "3999", "4000", True),
        (ComparisonOperator.LTE, "4000", "4000", True),
        (ComparisonOperator.EQ, "4000", "4000", True),
        (ComparisonOperator.NE, "4000", "4000", False),
    ],
)
def test_evaluate_entry_signal_operators(operator, left, right, expected) -> None:
    spec = EntrySignalSpec(
        condition_id="c", field="CLOSE", operator=operator, right_kind="LITERAL",
        right_literal=Decimal(right), right_parameter_id=None,
    )
    result = evaluate_entry_signal(
        spec, parameter_values={}, open_fp=to_fixed_point(Decimal(left)),
        high_fp=to_fixed_point(Decimal(left)), low_fp=to_fixed_point(Decimal(left)),
        close_fp=to_fixed_point(Decimal(left)),
    )
    assert result is expected


def test_evaluate_entry_signal_reads_only_the_field_it_was_told_to() -> None:
    """OPEN/HIGH/LOW/CLOSE are genuinely independent -- a spec bound to
    CLOSE never accidentally reads HIGH etc."""
    spec = EntrySignalSpec(
        condition_id="c", field="CLOSE", operator=ComparisonOperator.GT, right_kind="LITERAL",
        right_literal=Decimal(4000), right_parameter_id=None,
    )
    # HIGH is far above threshold, but CLOSE is below it -- must be False.
    result = evaluate_entry_signal(
        spec, parameter_values={}, open_fp=to_fixed_point(Decimal(3990)),
        high_fp=to_fixed_point(Decimal(9999)), low_fp=to_fixed_point(Decimal(3980)),
        close_fp=to_fixed_point(Decimal(3995)),
    )
    assert result is False


def test_evaluate_entry_signal_resolves_parameter_reference() -> None:
    spec = EntrySignalSpec(
        condition_id="c", field="CLOSE", operator=ComparisonOperator.GT, right_kind="PARAMETER",
        right_literal=None, right_parameter_id="entry_threshold_usd",
    )
    result = evaluate_entry_signal(
        spec, parameter_values={"entry_threshold_usd": Decimal(4000)},
        open_fp=0, high_fp=0, low_fp=0, close_fp=to_fixed_point(Decimal(4001)),
    )
    assert result is True


def test_evaluate_entry_signal_signature_has_no_array_or_index_parameter() -> None:
    """PID-006B causal-clock structural proof (falsification test 1, signal
    half): the live decision function's own signature makes it impossible
    to pass it anything but four scalar values for ONE bar -- there is no
    array, dataset, or bar-index parameter it could use to read another
    bar."""
    params = set(inspect.signature(evaluate_entry_signal).parameters)
    assert params == {"spec", "parameter_values", "open_fp", "high_fp", "low_fp", "close_fp"}
    for forbidden in ("dataset", "market_dataset", "index", "bar_index", "future", "array"):
        assert forbidden not in params


def test_evaluate_entry_signal_signature_has_no_mae_mfe_parameter() -> None:
    """PID-006B MAE/MFE-retrospective structural proof (falsification test
    10, signal half): no parameter here could ever carry an excursion
    figure, and the function returns a single bool."""
    signature = inspect.signature(evaluate_entry_signal)
    for forbidden in ("mae", "mfe", "excursion", "adverse", "favorable", "favourable"):
        assert forbidden not in signature.parameters
    assert signature.return_annotation in (bool, inspect.Signature.empty) or "bool" in str(signature.return_annotation)
