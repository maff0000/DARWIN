"""PID-006A ParameterSetVersion tests (docs/pids/PID-006-APOLLO.md sec6)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.research_contracts.errors import ParameterSetBindingError
from darwin.research_contracts.parameter_set import build_parameter_set_version
from darwin.specification.domain import StrategyVersion
from darwin.specification.errors import ParameterDomainViolationError
from darwin.specification.parameters import (
    IntegerRangeDomain,
    NumericRangeDomain,
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
)
from darwin.specification.validation import finalise
from tests.fixtures.specification_drafts import minimal_valid_draft


def _finalised_with_parameters(**draft_kwargs) -> StrategyVersion:
    draft = minimal_valid_draft(**draft_kwargs)
    draft.set_parameter(
        ParameterDefinition(
            parameter_id="fixed_lookback",
            status=ParameterStatus.FIXED,
            value_type=ParameterValueType.INTEGER,
            fixed_value=20,
        )
    )
    draft.set_parameter(
        ParameterDefinition(
            parameter_id="ema_period",
            status=ParameterStatus.TUNABLE,
            value_type=ParameterValueType.INTEGER,
            domain=IntegerRangeDomain(minimum=5, maximum=50),
        )
    )
    draft.set_parameter(
        ParameterDefinition(
            parameter_id="stop_distance",
            status=ParameterStatus.TUNABLE,
            value_type=ParameterValueType.DECIMAL,
            unit="USD_PER_TROY_OUNCE",
            domain=NumericRangeDomain(minimum=Decimal("1.0"), maximum=Decimal("50.0")),
        )
    )
    result = finalise(draft, strategy_version_id=draft_kwargs.get("draft_id", "sv-params"), now=datetime(2026, 1, 1, tzinfo=UTC))
    assert result.strategy_version is not None, result.outcome
    return result.strategy_version


_VALID_ASSIGNMENTS = (
    ("fixed_lookback", 20),
    ("ema_period", 12),
    ("stop_distance", Decimal("5.5")),
)


def test_unordered_input_produces_same_fingerprint_as_ordered_input() -> None:
    version = _finalised_with_parameters()
    ordered = build_parameter_set_version(version, _VALID_ASSIGNMENTS)
    shuffled = build_parameter_set_version(version, tuple(reversed(_VALID_ASSIGNMENTS)))
    assert ordered.fingerprint == shuffled.fingerprint
    assert ordered.assignments == shuffled.assignments  # canonical order regardless of input order


def test_changed_value_produces_different_fingerprint() -> None:
    version = _finalised_with_parameters()
    base = build_parameter_set_version(version, _VALID_ASSIGNMENTS)
    changed = build_parameter_set_version(
        version, (("fixed_lookback", 20), ("ema_period", 13), ("stop_distance", Decimal("5.5")))
    )
    assert base.fingerprint != changed.fingerprint


def test_binds_source_strategy_version_semantic_identity() -> None:
    version = _finalised_with_parameters()
    parameter_set = build_parameter_set_version(version, _VALID_ASSIGNMENTS)
    assert parameter_set.source_semantic_fingerprint == version.semantic_fingerprint


def test_missing_required_parameter_rejected() -> None:
    version = _finalised_with_parameters()
    with pytest.raises(ParameterSetBindingError):
        build_parameter_set_version(version, (("fixed_lookback", 20), ("ema_period", 12)))  # stop_distance missing


def test_unknown_extra_parameter_rejected() -> None:
    version = _finalised_with_parameters()
    with pytest.raises(ParameterSetBindingError):
        build_parameter_set_version(version, (*_VALID_ASSIGNMENTS, ("not_a_real_parameter", 1)))


def test_duplicate_assignment_rejected() -> None:
    version = _finalised_with_parameters()
    with pytest.raises(ParameterSetBindingError):
        build_parameter_set_version(version, (*_VALID_ASSIGNMENTS, ("ema_period", 99)))


def test_wrong_type_rejected() -> None:
    version = _finalised_with_parameters()
    with pytest.raises(ParameterSetBindingError):
        build_parameter_set_version(
            version, (("fixed_lookback", 20), ("ema_period", "twelve"), ("stop_distance", Decimal("5.5")))
        )


def test_bool_is_never_accepted_for_integer_parameter() -> None:
    version = _finalised_with_parameters()
    with pytest.raises(ParameterSetBindingError):
        build_parameter_set_version(
            version, (("fixed_lookback", 20), ("ema_period", True), ("stop_distance", Decimal("5.5")))
        )


def test_fixed_parameter_override_attempt_rejected() -> None:
    """Reuses darwin.specification.parameters.validate_parameter_value
    directly (PID-006A sec6) -- the error type is specification's own
    ParameterDomainViolationError, never re-wrapped."""
    version = _finalised_with_parameters()
    with pytest.raises(ParameterDomainViolationError):
        build_parameter_set_version(
            version, (("fixed_lookback", 21), ("ema_period", 12), ("stop_distance", Decimal("5.5")))
        )


def test_tunable_out_of_domain_value_rejected() -> None:
    version = _finalised_with_parameters()
    with pytest.raises(ParameterDomainViolationError):
        build_parameter_set_version(
            version, (("fixed_lookback", 20), ("ema_period", 999), ("stop_distance", Decimal("5.5")))
        )
