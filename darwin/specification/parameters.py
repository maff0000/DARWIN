"""Fixed vs tunable parameter semantics (PID-004 sec18).

Every meaningful parameter has explicit FIXED/TUNABLE status. A TUNABLE
parameter requires a closed, bounded, authorised domain -- constructing
one without a domain is a construction-time error
(`UnboundedTunableParameterError`), never a silently-accepted "ATHENA may
try whatever it wants" (PID-004 sec18).

Reuses the HSA archaeology's one directly-portable parameter shape
(bounded numeric range / discrete enumeration) but adds the explicit
FIXED/TUNABLE discriminator field HSA never had (`docs/archaeology/
HSA-PID004A-REUSE-ASSESSMENT.md` #9: "HSA achieves 'fixed' only by *not*
declaring something as a parameter... DARWIN's stated need for a
first-class distinction... requires a new field, not an existing one.").
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from darwin.specification.errors import (
    ParameterDomainViolationError,
    UnboundedTunableParameterError,
)


class ParameterStatus(StrEnum):
    FIXED = "FIXED"
    TUNABLE = "TUNABLE"


class ParameterValueType(StrEnum):
    DECIMAL = "DECIMAL"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    STRING = "STRING"
    DURATION_SECONDS = "DURATION_SECONDS"


@dataclass(frozen=True)
class NumericRangeDomain:
    minimum: Decimal
    maximum: Decimal
    step: Decimal | None = None

    def __post_init__(self) -> None:
        if self.minimum > self.maximum:
            raise ParameterDomainViolationError(
                f"NumericRangeDomain minimum {self.minimum} > maximum {self.maximum}"
            )

    def contains(self, value: Decimal) -> bool:
        return self.minimum <= value <= self.maximum


@dataclass(frozen=True)
class IntegerRangeDomain:
    minimum: int
    maximum: int
    step: int = 1

    def __post_init__(self) -> None:
        if self.minimum > self.maximum:
            raise ParameterDomainViolationError(
                f"IntegerRangeDomain minimum {self.minimum} > maximum {self.maximum}"
            )
        if self.step <= 0:
            raise ParameterDomainViolationError("IntegerRangeDomain.step must be positive")

    def contains(self, value: int) -> bool:
        return self.minimum <= value <= self.maximum


@dataclass(frozen=True)
class DiscreteEnumerationDomain:
    allowed_values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.allowed_values:
            raise ParameterDomainViolationError("DiscreteEnumerationDomain requires at least one allowed value")

    def contains(self, value: str) -> bool:
        return value in self.allowed_values


@dataclass(frozen=True)
class BooleanEnumerationDomain:
    allowed_values: tuple[bool, ...] = (True, False)

    def contains(self, value: bool) -> bool:
        return value in self.allowed_values


@dataclass(frozen=True)
class DurationRangeDomain:
    minimum_seconds: int
    maximum_seconds: int
    step_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.minimum_seconds > self.maximum_seconds:
            raise ParameterDomainViolationError("DurationRangeDomain minimum > maximum")
        if self.minimum_seconds < 0:
            raise ParameterDomainViolationError("DurationRangeDomain.minimum_seconds must be >= 0")

    def contains(self, value: int) -> bool:
        return self.minimum_seconds <= value <= self.maximum_seconds


@dataclass(frozen=True)
class UnitBearingRangeDomain:
    minimum: Decimal
    maximum: Decimal
    unit: str

    def __post_init__(self) -> None:
        if self.minimum > self.maximum:
            raise ParameterDomainViolationError("UnitBearingRangeDomain minimum > maximum")
        if not self.unit:
            raise ParameterDomainViolationError("UnitBearingRangeDomain requires a unit")

    def contains(self, value: Decimal) -> bool:
        return self.minimum <= value <= self.maximum


ParameterDomain = (
    NumericRangeDomain
    | IntegerRangeDomain
    | DiscreteEnumerationDomain
    | BooleanEnumerationDomain
    | DurationRangeDomain
    | UnitBearingRangeDomain
)


@dataclass(frozen=True)
class ParameterDefinition:
    """A single strategy parameter, always exactly FIXED or TUNABLE. FIXED
    requires `fixed_value` and forbids `domain`; TUNABLE requires a bounded
    `domain` and forbids `fixed_value` -- both directions enforced in
    `__post_init__`, so neither state can be constructed ambiguously."""

    parameter_id: str
    status: ParameterStatus
    value_type: ParameterValueType
    unit: str | None = None
    fixed_value: object = None
    domain: ParameterDomain | None = None

    def __post_init__(self) -> None:
        if not self.parameter_id or not self.parameter_id.strip():
            raise ParameterDomainViolationError("ParameterDefinition requires a non-empty parameter_id")
        if self.status == ParameterStatus.FIXED:
            if self.fixed_value is None:
                raise ParameterDomainViolationError(
                    f"FIXED parameter {self.parameter_id!r} requires a fixed_value"
                )
            if self.domain is not None:
                raise ParameterDomainViolationError(
                    f"FIXED parameter {self.parameter_id!r} must not carry a tunable domain"
                )
        elif self.status == ParameterStatus.TUNABLE:
            if self.domain is None:
                raise UnboundedTunableParameterError(
                    f"TUNABLE parameter {self.parameter_id!r} requires a closed, bounded domain "
                    f"(PID-004 sec18: no unbounded search space)"
                )
            if self.fixed_value is not None:
                raise ParameterDomainViolationError(
                    f"TUNABLE parameter {self.parameter_id!r} must not carry a fixed_value"
                )
        else:
            raise ParameterDomainViolationError(f"Unknown ParameterStatus: {self.status!r}")


def validate_parameter_value(parameter: ParameterDefinition, value: object) -> None:
    """Raises `ParameterDomainViolationError` if `value` is out of a
    TUNABLE parameter's declared domain, or does not equal a FIXED
    parameter's declared value. Used by validation.py's parameter stage
    (PID-004 sec42 critical case: "out-of-domain parameter rejected")."""
    if parameter.status == ParameterStatus.FIXED:
        if value != parameter.fixed_value:
            raise ParameterDomainViolationError(
                f"FIXED parameter {parameter.parameter_id!r} must equal {parameter.fixed_value!r}, got {value!r}"
            )
        return
    domain = parameter.domain
    assert domain is not None  # guaranteed by ParameterDefinition.__post_init__
    if not domain.contains(value):  # type: ignore[arg-type]
        raise ParameterDomainViolationError(
            f"Value {value!r} is out of domain for TUNABLE parameter {parameter.parameter_id!r}"
        )
