"""PID-006B engine-native entry-signal shape + the live per-bar decision
function.

Central Architecture correction CA-006B-1: this module no longer derives
`EntrySignalSpec` from a raw `StrategyVersion` -- that responsibility now
belongs exclusively to `darwin.apollo.plan_adapter.check_plan_capability`,
which reads the compiled `ExecutableStrategyPlan.semantic_payload`
instead. This module keeps only the engine-native `EntrySignalSpec` shape
(a plain, already-validated data carrier) and the pure per-bar evaluator
-- neither of which cares where the spec came from.

`evaluate_entry_signal` is deliberately kept a narrow, pure function of
exactly one already-closed bar's four scalar fixed-point OHLC values (plus
the already-resolved parameter values). It has no array/index/dataset
parameter, so it is structurally impossible for it to read any bar other
than the one it was called with -- see
tests/unit/test_apollo_causal_order.py's causal-clock proof. It has no
MAE/MFE-shaped parameter and returns a single `bool`, so it is equally
structurally impossible for it to reference retrospective excursion data
-- see tests/unit/test_apollo_mae_mfe_retrospective.py's structural proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from darwin.apollo.errors import EngineDefectError
from darwin.hermes.dataset import to_fixed_point
from darwin.specification.expressions import ComparisonOperator
from darwin.specification.facts import HermesMarketField

#: PID-006B v1 supports exactly these deterministic comparison operators.
#: CROSSES_ABOVE/CROSSES_BELOW require previous-bar state -- a capability
#: this v1 slice does not implement (never silently approximated). Plain
#: strings compare/hash equal to the matching `ComparisonOperator`
#: members (it is a `StrEnum`), so this set is usable against either the
#: typed enum or the plain string read back out of a compiled plan's
#: canonicalized payload.
SUPPORTED_OPERATORS: frozenset[str] = frozenset(
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
    """The validated, engine-native shape of a compiled plan's entry
    condition -- resolved once at preflight by
    `darwin.apollo.plan_adapter.check_plan_capability`, then passed
    unchanged to `evaluate_entry_signal` for every bar. `operator` is
    stored as a plain string (the exact value read back out of a
    compiled plan's canonicalized payload) -- it compares/hashes equal to
    the matching `ComparisonOperator` member either way."""

    condition_id: str
    field: str  # one of SUPPORTED_FIELDS
    operator: str
    right_kind: str  # "LITERAL" | "PARAMETER"
    right_literal: Decimal | None
    right_parameter_id: str | None


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
    except KeyError as exc:  # pragma: no cover - unreachable after check_plan_capability
        raise EngineDefectError(
            f"evaluate_entry_signal: operator {spec.operator!r} has no evaluator despite passing "
            f"check_plan_capability -- this is an engine defect, never a losing trade"
        ) from exc
