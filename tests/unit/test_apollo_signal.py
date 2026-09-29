"""PID-006B entry-signal capability check + live decision function tests."""
from __future__ import annotations

import dataclasses
import inspect
from decimal import Decimal

import pytest

from darwin.apollo.errors import CapabilityBlockReason, EngineCapabilityBlockedError
from darwin.apollo.signal import (
    EntrySignalSpec,
    check_strategy_capability,
    evaluate_entry_signal,
)
from darwin.hermes.dataset import to_fixed_point
from darwin.specification.composition import (
    AllComposition,
    Direction,
)
from darwin.specification.expressions import (
    BooleanExpression,
    BooleanOperator,
    ComparisonOperator,
)
from tests.fixtures.apollo_strategy import (
    apollo_entry_condition,
    build_apollo_strategy_version,
)
from tests.fixtures.specification_drafts import simple_atomic_condition


def test_supported_strategy_resolves_to_entry_signal_spec() -> None:
    sv = build_apollo_strategy_version()
    spec = check_strategy_capability(sv)
    assert spec.field == "CLOSE"
    assert spec.operator == ComparisonOperator.GT
    assert spec.right_kind == "PARAMETER"
    assert spec.right_parameter_id == "entry_threshold_usd"


def test_non_atomic_composition_is_capability_blocked() -> None:
    sv = build_apollo_strategy_version()
    all_composition = AllComposition(
        composition_id="all-1",
        components=(apollo_entry_condition("leg_0"), simple_atomic_condition("leg_1")),
    )
    mutated = dataclasses.replace(sv, composition=all_composition)
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_strategy_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_COMPOSITION_SHAPE


def test_short_direction_is_capability_blocked() -> None:
    sv = build_apollo_strategy_version()
    short_condition = apollo_entry_condition(direction=Direction.SHORT)
    mutated = dataclasses.replace(sv, composition=short_condition)
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_strategy_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_DIRECTION


def test_nonempty_exit_rules_is_capability_blocked() -> None:
    sv = build_apollo_strategy_version()
    mutated = dataclasses.replace(sv, exit_rules=(simple_atomic_condition("exit_1"),))
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_strategy_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_EXIT_RULES


def test_crosses_above_operator_is_capability_blocked() -> None:
    """CROSSES_ABOVE/CROSSES_BELOW require previous-bar state -- explicitly
    not implemented in this v1 slice."""
    sv = build_apollo_strategy_version()
    condition = sv.composition
    mutated_expression = dataclasses.replace(condition.expression, operator=ComparisonOperator.CROSSES_ABOVE)
    mutated_condition = dataclasses.replace(condition, expression=mutated_expression)
    mutated = dataclasses.replace(sv, composition=mutated_condition)
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_strategy_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE


def test_boolean_expression_root_is_capability_blocked() -> None:
    sv = build_apollo_strategy_version()
    condition = sv.composition
    boolean_expr = BooleanExpression(
        operator=BooleanOperator.AND,
        operands=(condition.expression, condition.expression),
    )
    mutated_condition = dataclasses.replace(condition, expression=boolean_expr)
    mutated = dataclasses.replace(sv, composition=mutated_condition)
    with pytest.raises(EngineCapabilityBlockedError):
        check_strategy_capability(mutated)


def test_volume_field_is_not_supported() -> None:
    """VOLUME is not a price -- excluded from the supported OHLCV field set."""
    sv = build_apollo_strategy_version()
    condition = sv.composition
    from darwin.specification.data_requirements import FactClass
    from darwin.specification.facts import CanonicalFactReference, DataAuthorityClass
    from darwin.specification.timeframe import Timeframe

    volume_ref = CanonicalFactReference(
        fact_key="OHLCV.VOLUME", fact_class=FactClass.MARKET_OHLCV,
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET, unit="USD_PER_TROY_OUNCE",
        timeframe=Timeframe("H1"), requirement_id="hermes_xau_usd_h1_ohlcv",
    )
    mutated_expression = dataclasses.replace(condition.expression, left=volume_ref)
    mutated_condition = dataclasses.replace(condition, expression=mutated_expression)
    mutated = dataclasses.replace(sv, composition=mutated_condition)
    with pytest.raises(EngineCapabilityBlockedError):
        check_strategy_capability(mutated)


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
