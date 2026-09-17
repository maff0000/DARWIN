"""PID-004A typed expression model + timeframe unit tests
(docs/pids/PID-004-SPECIFICATION-WORKSHOP.md sec6/sec7/sec8)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from darwin.specification.errors import SpecificationError, UnknownOperatorError
from darwin.specification.expressions import (
    BooleanExpression,
    BooleanOperator,
    Comparison,
    ComparisonOperator,
    Literal,
    ParameterReference,
    SessionOperator,
    SessionPredicate,
    TemporalOperator,
    TemporalPredicate,
    UndefinedMeasurementBasis,
    boolean_operator_from_raw,
    comparison_operator_from_raw,
    session_operator_from_raw,
    temporal_operator_from_raw,
)
from darwin.specification.timeframe import InvalidTimeframeError, Timeframe, finest

# --- timeframe ----------------------------------------------------------------

def test_valid_timeframe_codes_construct_cleanly():
    for code in ("M5", "H1", "H4", "D1", "W1"):
        Timeframe(code)


def test_invalid_timeframe_code_rejected():
    with pytest.raises(InvalidTimeframeError):
        Timeframe("5M")  # wrong order -- this module is unit-then-number
    with pytest.raises(InvalidTimeframeError):
        Timeframe("H0")  # zero count
    with pytest.raises(InvalidTimeframeError):
        Timeframe("XAU_USD")  # not a timeframe at all


def test_timeframe_minutes_and_ordering():
    m5, h1, h4, d1 = Timeframe("M5"), Timeframe("H1"), Timeframe("H4"), Timeframe("D1")
    assert m5.minutes == 5
    assert h1.minutes == 60
    assert h4.minutes == 240
    assert d1.minutes == 1440
    assert m5.is_finer_than(h1)
    assert h4.is_coarser_than(h1)
    assert finest([h4, h1, m5]) == m5


def test_finest_of_empty_raises():
    with pytest.raises(InvalidTimeframeError):
        finest([])


# --- governed operator vocabulary: unknown operators fail explicitly ----------

def test_unknown_comparison_operator_raises_typed_error():
    with pytest.raises(UnknownOperatorError):
        comparison_operator_from_raw("APPROXIMATELY_EQUALS")


def test_unknown_boolean_operator_raises_typed_error():
    with pytest.raises(UnknownOperatorError):
        boolean_operator_from_raw("XOR")


def test_unknown_temporal_operator_raises_typed_error():
    with pytest.raises(UnknownOperatorError):
        temporal_operator_from_raw("EVENTUALLY")


def test_unknown_session_operator_raises_typed_error():
    with pytest.raises(UnknownOperatorError):
        session_operator_from_raw("ON_HOLIDAY")


def test_governed_operator_from_raw_accepts_real_members():
    assert comparison_operator_from_raw("GT") is ComparisonOperator.GT
    assert boolean_operator_from_raw("AND") is BooleanOperator.AND
    assert temporal_operator_from_raw("WITHIN_N_BARS") is TemporalOperator.WITHIN_N_BARS
    assert session_operator_from_raw("IN_SESSION") is SessionOperator.IN_SESSION


def test_comparison_rejects_non_enum_operator_even_when_constructed_directly():
    with pytest.raises(UnknownOperatorError):
        Comparison(operator="GT", left=Literal(Decimal(1)), right=Literal(Decimal(0)))  # type: ignore[arg-type]


# --- Comparison / unit mismatch -----------------------------------------------

def test_comparison_unit_mismatch_rejected():
    with pytest.raises(SpecificationError):
        Comparison(
            operator=ComparisonOperator.GT,
            left=Literal(Decimal(100), unit="USD_PER_TROY_OUNCE"),
            right=Literal(Decimal(100), unit="USD"),
        )


def test_comparison_same_unit_constructs_cleanly():
    Comparison(
        operator=ComparisonOperator.GT,
        left=Literal(Decimal(100), unit="USD"),
        right=Literal(Decimal(50), unit="USD"),
    )


# --- BooleanExpression arity ---------------------------------------------------

def test_not_requires_exactly_one_operand():
    comparison = Comparison(operator=ComparisonOperator.GT, left=Literal(Decimal(1)), right=Literal(Decimal(0)))
    BooleanExpression(operator=BooleanOperator.NOT, operands=(comparison,))
    with pytest.raises(SpecificationError):
        BooleanExpression(operator=BooleanOperator.NOT, operands=(comparison, comparison))


def test_and_or_require_at_least_two_operands():
    comparison = Comparison(operator=ComparisonOperator.GT, left=Literal(Decimal(1)), right=Literal(Decimal(0)))
    with pytest.raises(SpecificationError):
        BooleanExpression(operator=BooleanOperator.AND, operands=(comparison,))


# --- TemporalPredicate n_bars discipline ---------------------------------------

def test_within_n_bars_requires_positive_n_bars():
    TemporalPredicate(operator=TemporalOperator.WITHIN_N_BARS, reference="setup", n_bars=5)
    with pytest.raises(SpecificationError):
        TemporalPredicate(operator=TemporalOperator.WITHIN_N_BARS, reference="setup", n_bars=None)
    with pytest.raises(SpecificationError):
        TemporalPredicate(operator=TemporalOperator.WITHIN_N_BARS, reference="setup", n_bars=0)


def test_since_event_must_not_carry_n_bars():
    TemporalPredicate(operator=TemporalOperator.SINCE_EVENT, reference="news_release")
    with pytest.raises(SpecificationError):
        TemporalPredicate(operator=TemporalOperator.SINCE_EVENT, reference="news_release", n_bars=3)


# --- SessionPredicate -----------------------------------------------------------

def test_on_day_requires_at_least_one_weekday():
    with pytest.raises(SpecificationError):
        SessionPredicate(operator=SessionOperator.ON_DAY, days=())


def test_on_day_rejects_invalid_weekday():
    with pytest.raises(SpecificationError):
        SessionPredicate(operator=SessionOperator.ON_DAY, days=(7,))


def test_in_session_needs_no_days():
    SessionPredicate(operator=SessionOperator.IN_SESSION)


# --- ambiguity marker & ParameterReference -------------------------------------

def test_undefined_measurement_basis_is_a_distinct_leaf_node():
    node = UndefinedMeasurementBasis(note="author never said what 'near resistance' means")
    assert node.note
    with pytest.raises(SpecificationError):
        ParameterReference(parameter_id="   ")
