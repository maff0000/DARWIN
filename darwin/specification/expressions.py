"""Typed declarative strategy expression model (PID-004 sec7/sec8).

No eval, no exec, no arbitrary source-supplied executable code anywhere in
this module or this package. A strategy condition is always a closed tree
of the typed nodes below -- never a string, never a Python/JS/Pine
Script/shell fragment (PID-004 sec7). Source code discovered by SCOUT
remains inert provenance material; nothing in `darwin.specification` ever
executes it.

Every governed operator below has a canonical identifier, typed operands,
and construction-time validation. An operator string outside the closed
enum raises `UnknownOperatorError` immediately -- there is no silent
fallback, and no generic "evaluate whatever operator string you got" path
exists anywhere in this module (PID-004 sec8).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Union

from darwin.specification.errors import (
    InvalidOperandError,
    SpecificationError,
    UnknownOperatorError,
)


class ExpressionKind(StrEnum):
    """Closed discriminator mirroring PID-004 sec8's conceptual node list.
    Carried as a fixed, non-settable class attribute on every node type
    below (never a caller-supplied flag) purely to make canonical
    serialisation/fingerprinting self-describing; the real type safety
    comes from Python's own `isinstance`/dataclass typing, not from this
    string."""

    LITERAL = "LITERAL"
    PARAMETER_REFERENCE = "PARAMETER_REFERENCE"
    COMPARISON = "COMPARISON"
    BOOLEAN_EXPRESSION = "BOOLEAN_EXPRESSION"
    TEMPORAL_PREDICATE = "TEMPORAL_PREDICATE"
    SESSION_PREDICATE = "SESSION_PREDICATE"
    EVENT_PREDICATE = "EVENT_PREDICATE"
    UNDEFINED_MEASUREMENT_BASIS = "UNDEFINED_MEASUREMENT_BASIS"
    # Fact-reference node kinds are defined on darwin.specification.facts,
    # not here, but share this same discriminator vocabulary so a generic
    # tree-walker (see darwin.specification.composition._walk) can dispatch
    # uniformly without importing facts.py and creating a cycle.
    CANONICAL_FACT_REFERENCE = "CANONICAL_FACT_REFERENCE"
    SPECIFICATION_DERIVED_FACT = "SPECIFICATION_DERIVED_FACT"


class ComparisonOperator(StrEnum):
    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    CROSSES_ABOVE = "CROSSES_ABOVE"
    CROSSES_BELOW = "CROSSES_BELOW"


class BooleanOperator(StrEnum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class TemporalOperator(StrEnum):
    WITHIN_N_BARS = "WITHIN_N_BARS"
    FOR_N_CONSECUTIVE_BARS = "FOR_N_CONSECUTIVE_BARS"
    SINCE_EVENT = "SINCE_EVENT"
    BEFORE_EVENT = "BEFORE_EVENT"
    AFTER_EVENT = "AFTER_EVENT"


class SessionOperator(StrEnum):
    IN_SESSION = "IN_SESSION"
    ON_DAY = "ON_DAY"


def comparison_operator_from_raw(raw: object) -> ComparisonOperator:
    """The only supported way to turn caller-supplied raw operator text
    (e.g. Workshop JSON input, once PID-004B exists) into a governed
    `ComparisonOperator`. Raises `UnknownOperatorError` explicitly for
    anything outside the closed vocabulary -- never returns a best guess."""
    try:
        return ComparisonOperator(raw)
    except ValueError as exc:
        raise UnknownOperatorError(
            f"Unknown comparison operator {raw!r}; governed set is "
            f"{sorted(op.value for op in ComparisonOperator)}"
        ) from exc


def boolean_operator_from_raw(raw: object) -> BooleanOperator:
    try:
        return BooleanOperator(raw)
    except ValueError as exc:
        raise UnknownOperatorError(
            f"Unknown boolean operator {raw!r}; governed set is "
            f"{sorted(op.value for op in BooleanOperator)}"
        ) from exc


def temporal_operator_from_raw(raw: object) -> TemporalOperator:
    try:
        return TemporalOperator(raw)
    except ValueError as exc:
        raise UnknownOperatorError(
            f"Unknown temporal operator {raw!r}; governed set is "
            f"{sorted(op.value for op in TemporalOperator)}"
        ) from exc


def session_operator_from_raw(raw: object) -> SessionOperator:
    try:
        return SessionOperator(raw)
    except ValueError as exc:
        raise UnknownOperatorError(
            f"Unknown session operator {raw!r}; governed set is "
            f"{sorted(op.value for op in SessionOperator)}"
        ) from exc


@dataclass(frozen=True)
class Literal:
    """A bare typed constant. `unit` is optional but, once declared, is
    checked for consistency by `Comparison` (PID-004 sec14: never confuse
    storage precision/units)."""

    value: Decimal | int | bool | str
    unit: str | None = None
    kind: ExpressionKind = ExpressionKind.LITERAL


@dataclass(frozen=True)
class ParameterReference:
    """A reference to a `ParameterDefinition` declared elsewhere on the same
    SpecificationDraft/StrategyVersion (FIXED or TUNABLE -- this node does
    not care which; that distinction is validated separately, see
    darwin.specification.validation)."""

    parameter_id: str
    kind: ExpressionKind = ExpressionKind.PARAMETER_REFERENCE

    def __post_init__(self) -> None:
        if not self.parameter_id or not self.parameter_id.strip():
            raise SpecificationError("ParameterReference requires a non-empty parameter_id")


@dataclass(frozen=True)
class UndefinedMeasurementBasis:
    """Explicit structural marker: the author has not said what this
    expression measures against, and it is not being offered as a TUNABLE
    parameter either (PID-004 sec3/sec18/sec31, HSA doctrine: "parameterise
    when the measurement basis is known but the threshold is unset; refuse
    when the measurement basis itself is undefined").

    This node is never silently treated as a value. Its sole purpose is to
    be found by `darwin.specification.validation.validate_draft`, which
    must return `STRATEGY_NOT_SUFFICIENTLY_DEFINED` whenever one appears
    anywhere in a composition tree. There is no `default_value` field here
    on purpose -- a strategy this ambiguous does not get a guessed number.
    """

    note: str
    kind: ExpressionKind = ExpressionKind.UNDEFINED_MEASUREMENT_BASIS


# Forward reference union -- FactReference lives in darwin.specification.facts
# and is imported lazily by type checkers only, to avoid a circular import
# (facts.py never needs expressions.py's concrete Comparison/Boolean nodes).
#
# This is the closed VALUE-operand union -- what a `Comparison.left`/
# `.right` may be. It deliberately excludes `Comparison`/`BooleanExpression`
# themselves (PID-004A hardening item 1: comparisons compare values, not
# truth values -- a nested Comparison/BooleanExpression is never a valid
# Comparison operand; combine truth values with `BooleanExpression`
# instead). `_governed_comparison_operand_types()` below is the real,
# runtime-enforced source of truth this type alias mirrors for readers/
# type-checkers only.
Operand = Union[
    Literal,
    ParameterReference,
    UndefinedMeasurementBasis,
    "darwin.specification.facts.CanonicalFactReference",  # noqa: F821
    "darwin.specification.facts.SpecificationDerivedFact",  # noqa: F821
]


def _governed_comparison_operand_types() -> tuple[type, ...]:
    """The closed set of types a `Comparison` operand may be (PID-004A
    hardening item 1). Resolved lazily, inside a function rather than at
    module import time, because `CanonicalFactReference`/
    `SpecificationDerivedFact` live in `darwin.specification.facts`, which
    itself imports THIS module (`ExpressionKind`) -- a module-level import
    here would be circular. By the time any `Comparison` is actually
    constructed, both modules have finished importing, so the deferred
    import below is safe."""
    from darwin.specification.facts import (
        CanonicalFactReference,
        SpecificationDerivedFact,
    )

    return (
        Literal,
        ParameterReference,
        UndefinedMeasurementBasis,
        CanonicalFactReference,
        SpecificationDerivedFact,
    )


@dataclass(frozen=True)
class Comparison:
    """A single typed comparison, e.g. `close GT ema_50`. `left`/`right`
    must each be a governed VALUE operand -- `Literal`, `ParameterReference`,
    `UndefinedMeasurementBasis`, `CanonicalFactReference`, or
    `SpecificationDerivedFact`. A nested Comparison/BooleanExpression is
    intentionally NOT allowed (comparisons compare values, not truth
    values; combine truth values with `BooleanExpression` instead), and
    neither is a raw string, an arbitrary object, or any other unsupported
    type (PID-004A hardening item 1: the expression tree is closed and
    this is enforced at runtime, not merely by a type hint)."""

    operator: ComparisonOperator
    left: object
    right: object
    kind: ExpressionKind = ExpressionKind.COMPARISON

    def __post_init__(self) -> None:
        if not isinstance(self.operator, ComparisonOperator):
            raise UnknownOperatorError(
                f"Comparison.operator must be a ComparisonOperator, got {self.operator!r}"
            )
        governed_types = _governed_comparison_operand_types()
        for side, operand in (("left", self.left), ("right", self.right)):
            if not isinstance(operand, governed_types):
                raise InvalidOperandError(
                    f"Comparison.{side} must be a governed value operand "
                    f"(Literal/ParameterReference/UndefinedMeasurementBasis/CanonicalFactReference/"
                    f"SpecificationDerivedFact), got {operand!r} (type {type(operand)!r})"
                )
        left_unit = getattr(self.left, "unit", None)
        right_unit = getattr(self.right, "unit", None)
        if left_unit is not None and right_unit is not None and left_unit != right_unit:
            raise SpecificationError(
                f"Comparison unit mismatch: left unit {left_unit!r} != right unit {right_unit!r}"
            )


@dataclass(frozen=True)
class BooleanExpression:
    """AND/OR combine two-or-more operands; NOT takes exactly one. Operands
    must be governed CONDITION-typed nodes -- `Comparison`,
    `BooleanExpression` (nested), `TemporalPredicate`, `SessionPredicate`,
    `EventPredicate`, or `UndefinedMeasurementBasis` -- never a bare
    `Literal` (a boolean combination of constants is not a strategy
    condition), a raw string, or any other unsupported type (PID-004A
    hardening item 1: enforced at runtime, not merely by a type hint)."""

    operator: BooleanOperator
    operands: tuple[object, ...]
    kind: ExpressionKind = ExpressionKind.BOOLEAN_EXPRESSION

    def __post_init__(self) -> None:
        if not isinstance(self.operator, BooleanOperator):
            raise UnknownOperatorError(
                f"BooleanExpression.operator must be a BooleanOperator, got {self.operator!r}"
            )
        governed_types = (
            Comparison,
            BooleanExpression,
            TemporalPredicate,
            SessionPredicate,
            EventPredicate,
            UndefinedMeasurementBasis,
        )
        for index, operand in enumerate(self.operands):
            if not isinstance(operand, governed_types):
                raise InvalidOperandError(
                    f"BooleanExpression operand[{index}] must be a governed condition node "
                    f"(Comparison/BooleanExpression/TemporalPredicate/SessionPredicate/"
                    f"EventPredicate/UndefinedMeasurementBasis), got {operand!r} "
                    f"(type {type(operand)!r})"
                )
        if self.operator == BooleanOperator.NOT:
            if len(self.operands) != 1:
                raise SpecificationError("NOT requires exactly one operand")
        else:
            if len(self.operands) < 2:
                raise SpecificationError(f"{self.operator.value} requires at least two operands")


@dataclass(frozen=True)
class TemporalPredicate:
    """A temporal relationship over other expressions/events, e.g.
    `WITHIN_N_BARS(event=setup_formed, n=5)`. `reference` names the
    event/condition this predicate is measured against; `n_bars` is
    required for WITHIN_N_BARS/FOR_N_CONSECUTIVE_BARS and must be absent
    (None) for SINCE_EVENT/BEFORE_EVENT/AFTER_EVENT (which are purely
    ordering predicates with no bar count)."""

    operator: TemporalOperator
    reference: str
    n_bars: int | None = None
    kind: ExpressionKind = ExpressionKind.TEMPORAL_PREDICATE

    def __post_init__(self) -> None:
        if not isinstance(self.operator, TemporalOperator):
            raise UnknownOperatorError(
                f"TemporalPredicate.operator must be a TemporalOperator, got {self.operator!r}"
            )
        needs_n_bars = self.operator in (
            TemporalOperator.WITHIN_N_BARS,
            TemporalOperator.FOR_N_CONSECUTIVE_BARS,
        )
        if needs_n_bars and (self.n_bars is None or self.n_bars <= 0):
            raise SpecificationError(f"{self.operator.value} requires a positive n_bars")
        if not needs_n_bars and self.n_bars is not None:
            raise SpecificationError(f"{self.operator.value} must not carry n_bars")


@dataclass(frozen=True)
class SessionPredicate:
    """IN_SESSION/ON_DAY resolve against the strategy's own declared
    `SessionSpec` (darwin.specification.applicability) -- this node never
    carries its own ad hoc timezone; there is exactly one governed session
    declaration per StrategyVersion (PID-004 sec13)."""

    operator: SessionOperator
    days: tuple[int, ...] = ()
    kind: ExpressionKind = ExpressionKind.SESSION_PREDICATE

    def __post_init__(self) -> None:
        if not isinstance(self.operator, SessionOperator):
            raise UnknownOperatorError(
                f"SessionPredicate.operator must be a SessionOperator, got {self.operator!r}"
            )
        if self.operator == SessionOperator.ON_DAY and not self.days:
            raise SpecificationError("ON_DAY requires at least one weekday (0=Mon..6=Sun)")
        for day in self.days:
            if not (0 <= day <= 6):
                raise SpecificationError(f"Invalid weekday {day!r}; must be 0..6")


@dataclass(frozen=True)
class EventPredicate:
    """A reference to an external/context event fact
    (`darwin.specification.facts.CanonicalFactReference` of a NEWS_CONTEXT/
    ECONOMIC_SURPRISE/PREDICTION_MARKET fact class) plus the causal
    ordering required against it. This node never carries a concrete
    historical timestamp -- causal timing REQUIREMENTS live on the bound
    `DataRequirement` (darwin.specification.data_requirements); actual
    per-observation timestamps live on
    `darwin.specification.causal.ExternalFactObservation`, which this
    package never fabricates."""

    fact_requirement_id: str
    kind: ExpressionKind = ExpressionKind.EVENT_PREDICATE

    def __post_init__(self) -> None:
        if not self.fact_requirement_id or not self.fact_requirement_id.strip():
            raise SpecificationError("EventPredicate requires a non-empty fact_requirement_id")
