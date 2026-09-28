"""`ParameterSetVersion` -- an immutable parameter assignment validated
AGAINST the exact source `StrategyVersion` it belongs to (PID-006A sec6).

Stronger than fingerprinting an arbitrary dict: every assignment is
checked structurally (no missing parameter, no unknown parameter, no
duplicate assignment, exact type match) and then semantically via
`darwin.specification.parameters.validate_parameter_value` -- reused
directly, not re-derived, exactly as PID-006A sec6 requires ("Use this
directly against each of the StrategyVersion's fixed_parameters/
tunable_parameters, rather than re-deriving the check").
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from darwin.core.identities import new_id
from darwin.research_contracts.errors import ParameterSetBindingError
from darwin.specification.domain import StrategyVersion
from darwin.specification.fingerprint import canonical_hash, canonicalize
from darwin.specification.parameters import (
    ParameterDefinition,
    ParameterValueType,
    validate_parameter_value,
)

#: The Python type(s) each governed `ParameterValueType` must exactly
#: match. `bool` is deliberately excluded from the INTEGER/DURATION_SECONDS
#: check below (Python's `bool` is a subclass of `int`, and a boolean value
#: silently satisfying an INTEGER parameter would be a real, if subtle,
#: type-confusion bug).
_EXPECTED_PYTHON_TYPE: dict[ParameterValueType, type] = {
    ParameterValueType.DECIMAL: Decimal,
    ParameterValueType.INTEGER: int,
    ParameterValueType.BOOLEAN: bool,
    ParameterValueType.STRING: str,
    ParameterValueType.DURATION_SECONDS: int,
}


def _check_exact_type(definition: ParameterDefinition, value: object) -> None:
    expected = _EXPECTED_PYTHON_TYPE[definition.value_type]
    if expected is int and isinstance(value, bool):
        raise ParameterSetBindingError(
            f"Parameter {definition.parameter_id!r} requires {definition.value_type.value} "
            f"(python int), got bool {value!r}"
        )
    if not isinstance(value, expected):
        raise ParameterSetBindingError(
            f"Parameter {definition.parameter_id!r} requires {definition.value_type.value} "
            f"(python {expected.__name__}), got {type(value).__name__} {value!r}"
        )


@dataclass(frozen=True)
class ParameterSetVersion:
    """Immutable, deterministically fingerprinted parameter assignment
    (PID-006A sec6). `parameter_set_id` is an opaque application-generated
    identity, excluded from `fingerprint` (same discipline as
    `ExecutableStrategyPlan.plan_id`). `source_strategy_version_id` is
    carried for traceability only; the actual bound identity is
    `source_semantic_fingerprint` (PID-006A sec6: "must bind the source
    StrategyVersion's semantic identity... into its own fingerprint").

    `assignments` is always stored pre-sorted by `parameter_id` --
    canonical ordering independent of caller/dict input order (PID-006A
    sec6/Required tests: "unordered input dict produces the same
    fingerprint as ordered input").
    """

    parameter_set_id: str
    source_strategy_version_id: str
    source_semantic_fingerprint: str
    assignments: tuple[tuple[str, object], ...]
    fingerprint: str


def _fingerprint_payload(*, source_semantic_fingerprint: str, assignments: tuple[tuple[str, object], ...]) -> dict:
    return {
        "source_semantic_fingerprint": source_semantic_fingerprint,
        "assignments": canonicalize(list(assignments)),
    }


def compute_parameter_set_fingerprint(
    *, source_semantic_fingerprint: str, assignments: tuple[tuple[str, object], ...]
) -> str:
    """Recomputable independently of a live `ParameterSetVersion` instance
    -- used both by `build_parameter_set_version` and by
    `darwin.research_store`'s persistence layer on reconstruction."""
    return canonical_hash(
        _fingerprint_payload(source_semantic_fingerprint=source_semantic_fingerprint, assignments=assignments)
    )


def build_parameter_set_version(
    strategy_version: StrategyVersion, assignments: Iterable[tuple[str, object]]
) -> ParameterSetVersion:
    """The only supported way to construct a `ParameterSetVersion`
    (PID-006A sec6). `assignments` is an iterable of `(parameter_id,
    value)` pairs -- deliberately not a `dict` on this public seam, so a
    caller-supplied duplicate `parameter_id` is observable and rejected
    here rather than silently collapsed by dict construction before this
    function ever sees it.

    Raises `ParameterSetBindingError` for every structural violation
    (missing parameter, unknown parameter, duplicate assignment, wrong
    type) and lets
    `darwin.specification.parameters.validate_parameter_value`'s own
    `ParameterDomainViolationError` propagate unchanged for a FIXED-value
    mismatch or an out-of-domain TUNABLE value (reuse, don't reinvent --
    PID-006A sec6).
    """
    seen: dict[str, object] = {}
    for parameter_id, value in assignments:
        if parameter_id in seen:
            raise ParameterSetBindingError(f"Duplicate assignment for parameter {parameter_id!r}")
        seen[parameter_id] = value

    all_parameters: dict[str, ParameterDefinition] = {
        definition.parameter_id: definition
        for definition in (*strategy_version.fixed_parameters, *strategy_version.tunable_parameters)
    }

    missing = sorted(set(all_parameters) - set(seen))
    if missing:
        raise ParameterSetBindingError(
            f"ParameterSetVersion missing required parameter(s): {missing} "
            f"(StrategyVersion {strategy_version.strategy_version_id!r})"
        )
    unknown = sorted(set(seen) - set(all_parameters))
    if unknown:
        raise ParameterSetBindingError(
            f"ParameterSetVersion references unknown parameter(s): {unknown} "
            f"(not declared on StrategyVersion {strategy_version.strategy_version_id!r})"
        )

    for parameter_id, value in seen.items():
        definition = all_parameters[parameter_id]
        _check_exact_type(definition, value)
        # Reused directly, not re-derived (PID-006A sec6): rejects a
        # FIXED-value mismatch or an out-of-domain TUNABLE value with
        # ParameterDomainViolationError, propagated unchanged.
        validate_parameter_value(definition, value)

    resolved = tuple(sorted(seen.items(), key=lambda kv: kv[0]))
    fingerprint = compute_parameter_set_fingerprint(
        source_semantic_fingerprint=strategy_version.semantic_fingerprint, assignments=resolved
    )
    return ParameterSetVersion(
        parameter_set_id=new_id(),
        source_strategy_version_id=strategy_version.strategy_version_id,
        source_semantic_fingerprint=strategy_version.semantic_fingerprint,
        assignments=resolved,
        fingerprint=fingerprint,
    )
