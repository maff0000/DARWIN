"""PID-006B entry-signal capability check + the live per-bar decision
function.

"First supported semantic subset" (PID-006B scope): ATOMIC entry
composition only, LONG direction only, a single `Comparison` of one OHLCV
`CanonicalFactReference` against a `Literal` or `ParameterReference`,
using a deterministic (non-crossing) operator. `check_strategy_capability`
is the ONE place this shape is validated -- resolved once at preflight
into an `EntrySignalSpec`, never re-derived mid-replay.

`evaluate_entry_signal` is deliberately kept a narrow, pure function of
exactly one already-closed bar's four scalar fixed-point OHLC values (plus
the already-resolved parameter values). It has no array/index/dataset
parameter, so it is structurally impossible for it to read any bar other
than the one it was called with -- see
tests/unit/test_apollo_engine_causal_timing.py's causal-clock proof. It
has no MAE/MFE-shaped parameter and returns a single `bool`, so it is
equally structurally impossible for it to reference retrospective
excursion data -- see
tests/unit/test_apollo_mae_mfe_retrospective.py's structural proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from darwin.apollo.errors import (
    CapabilityBlockContext,
    CapabilityBlockReason,
    EngineCapabilityBlockedError,
    EngineDefectError,
)
from darwin.hermes.dataset import to_fixed_point
from darwin.specification.composition import AtomicCondition, Direction
from darwin.specification.domain import StrategyVersion
from darwin.specification.expressions import (
    Comparison,
    ComparisonOperator,
    Literal,
    ParameterReference,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    FactClass,
    HermesMarketField,
)

#: PID-006B v1 supports exactly these deterministic comparison operators.
#: CROSSES_ABOVE/CROSSES_BELOW require previous-bar state -- a capability
#: this v1 slice does not implement (never silently approximated).
SUPPORTED_OPERATORS: frozenset[ComparisonOperator] = frozenset(
    {
        ComparisonOperator.GT,
        ComparisonOperator.GTE,
        ComparisonOperator.LT,
        ComparisonOperator.LTE,
        ComparisonOperator.EQ,
        ComparisonOperator.NE,
    }
)

#: The OHLCV field vocabulary this v1 slice's entry signal may compare --
#: every one of these is already fully known the instant the bar closes
#: (never VOLUME, which is not a price and not needed for this slice).
SUPPORTED_FIELDS: frozenset[str] = frozenset(
    {
        HermesMarketField.OPEN.value,
        HermesMarketField.HIGH.value,
        HermesMarketField.LOW.value,
        HermesMarketField.CLOSE.value,
    }
)

_FIELD_VALUE_FN = {
    HermesMarketField.OPEN.value: lambda o, h, l, c: o,
    HermesMarketField.HIGH.value: lambda o, h, l, c: h,
    HermesMarketField.LOW.value: lambda o, h, l, c: l,
    HermesMarketField.CLOSE.value: lambda o, h, l, c: c,
}

_OPERATOR_FN = {
    ComparisonOperator.GT: lambda a, b: a > b,
    ComparisonOperator.GTE: lambda a, b: a >= b,
    ComparisonOperator.LT: lambda a, b: a < b,
    ComparisonOperator.LTE: lambda a, b: a <= b,
    ComparisonOperator.EQ: lambda a, b: a == b,
    ComparisonOperator.NE: lambda a, b: a != b,
}


@dataclass(frozen=True)
class EntrySignalSpec:
    """The validated, engine-native shape of `StrategyVersion.composition`
    -- resolved once at preflight by `check_strategy_capability`, then
    passed unchanged to `evaluate_entry_signal` for every bar."""

    condition_id: str
    field: str  # one of SUPPORTED_FIELDS
    operator: ComparisonOperator
    right_kind: str  # "LITERAL" | "PARAMETER"
    right_literal: Decimal | None
    right_parameter_id: str | None


def _blocked(message: str, *, reason: CapabilityBlockReason, subject_ref: str, **detail: str) -> EngineCapabilityBlockedError:
    return EngineCapabilityBlockedError(
        message,
        context=CapabilityBlockContext(reason=reason, subject_ref=subject_ref, detail=tuple(detail.items())),
    )


def check_strategy_capability(strategy_version: StrategyVersion) -> EntrySignalSpec:
    """PID-006B preflight check #8 (strategy-shape half): validates
    `strategy_version.composition`/`exit_rules` against the engine's
    closed "first supported semantic subset" and returns the resolved
    `EntrySignalSpec` on success. Raises `EngineCapabilityBlockedError` --
    never a bare crash -- for anything outside this shape, before a
    single bar is ever processed.
    """
    composition = strategy_version.composition
    if not isinstance(composition, AtomicCondition):
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports ATOMIC entry composition only, got "
            f"{type(composition).__name__}",
            reason=CapabilityBlockReason.UNSUPPORTED_COMPOSITION_SHAPE,
            subject_ref=getattr(composition, "composition_id", "<root>"),
            composition_type=type(composition).__name__,
        )
    if composition.direction != Direction.LONG:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports LONG direction only, got "
            f"{composition.direction.value} (condition_id={composition.condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_DIRECTION,
            subject_ref=composition.condition_id,
            direction=composition.direction.value,
        )
    if strategy_version.exit_rules:
        raise _blocked(
            "APOLLO Candle Causal Core v1 supports no StrategyVersion-level exit_rules -- "
            "position exit is via SL/TP parameters only (see darwin.apollo.economics)",
            reason=CapabilityBlockReason.UNSUPPORTED_EXIT_RULES,
            subject_ref=strategy_version.strategy_version_id,
            exit_rules_count=str(len(strategy_version.exit_rules)),
        )

    expression = composition.expression
    if not isinstance(expression, Comparison):
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports a single Comparison expression only, got "
            f"{type(expression).__name__} (condition_id={composition.condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE,
            subject_ref=composition.condition_id,
            expression_type=type(expression).__name__,
        )
    if expression.operator not in SUPPORTED_OPERATORS:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 does not support comparison operator "
            f"{expression.operator.value} (condition_id={composition.condition_id!r}) -- "
            f"CROSSES_ABOVE/CROSSES_BELOW require previous-bar state, not implemented in v1",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE,
            subject_ref=composition.condition_id,
            operator=expression.operator.value,
        )

    left = expression.left
    if not isinstance(left, CanonicalFactReference) or left.fact_class != FactClass.MARKET_OHLCV:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 requires Comparison.left to be a MARKET_OHLCV "
            f"CanonicalFactReference (condition_id={composition.condition_id!r}), got {left!r}",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE,
            subject_ref=composition.condition_id,
            left_type=type(left).__name__,
        )
    _namespace, _dot, field = left.fact_key.partition(".")
    if field not in SUPPORTED_FIELDS:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports OHLCV fields {sorted(SUPPORTED_FIELDS)} only, "
            f"got {left.fact_key!r} (condition_id={composition.condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE,
            subject_ref=composition.condition_id,
            fact_key=left.fact_key,
        )

    right = expression.right
    if isinstance(right, Literal):
        if not isinstance(right.value, Decimal):
            raise _blocked(
                f"APOLLO Candle Causal Core v1 requires a Decimal Literal on the right-hand side "
                f"of the entry comparison (condition_id={composition.condition_id!r}), got "
                f"{type(right.value).__name__}",
                reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE,
                subject_ref=composition.condition_id,
                literal_value_type=type(right.value).__name__,
            )
        right_kind, right_literal, right_parameter_id = "LITERAL", right.value, None
    elif isinstance(right, ParameterReference):
        right_kind, right_literal, right_parameter_id = "PARAMETER", None, right.parameter_id
    else:
        raise _blocked(
            f"APOLLO Candle Causal Core v1 supports Literal or ParameterReference on the "
            f"right-hand side of the entry comparison only, got {type(right).__name__} "
            f"(condition_id={composition.condition_id!r})",
            reason=CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE,
            subject_ref=composition.condition_id,
            right_type=type(right).__name__,
        )

    return EntrySignalSpec(
        condition_id=composition.condition_id,
        field=field,
        operator=expression.operator,
        right_kind=right_kind,
        right_literal=right_literal,
        right_parameter_id=right_parameter_id,
    )


def evaluate_entry_signal(
    spec: EntrySignalSpec,
    *,
    parameter_values: dict[str, Decimal],
    open_fp: int,
    high_fp: int,
    low_fp: int,
    close_fp: int,
) -> bool:
    """THE live per-bar decision function. Pure function of exactly one
    already-closed bar's four scalar fixed-point OHLC values plus the
    already-resolved parameter values -- see module docstring for the two
    structural proofs this narrow signature enables."""
    left_value = _FIELD_VALUE_FN[spec.field](open_fp, high_fp, low_fp, close_fp)

    if spec.right_kind == "LITERAL":
        right_value = to_fixed_point(spec.right_literal)
    else:
        raw = parameter_values.get(spec.right_parameter_id)
        if not isinstance(raw, Decimal):
            raise EngineDefectError(
                f"evaluate_entry_signal: parameter {spec.right_parameter_id!r} resolved to "
                f"{raw!r} (expected Decimal) -- this indicates a defect upstream of the "
                f"engine's own replay loop, never encoded as a losing trade"
            )
        right_value = to_fixed_point(raw)

    try:
        return _OPERATOR_FN[spec.operator](left_value, right_value)
    except KeyError as exc:  # pragma: no cover - unreachable after check_strategy_capability
        raise EngineDefectError(
            f"evaluate_entry_signal: operator {spec.operator!r} has no evaluator despite passing "
            f"check_strategy_capability -- this is an engine defect, never a losing trade"
        ) from exc
