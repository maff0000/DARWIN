"""PID-004A fixed/tunable parameter + policy-identity-boundary unit tests
(PID-004 sec5B/sec12/sec18/sec19/sec20)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from darwin.specification.errors import (
    ParameterDomainViolationError,
    SpecificationError,
    UnboundedTunableParameterError,
)
from darwin.specification.parameters import (
    BooleanEnumerationDomain,
    DiscreteEnumerationDomain,
    DurationRangeDomain,
    IntegerRangeDomain,
    NumericRangeDomain,
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
    UnitBearingRangeDomain,
    validate_parameter_value,
)
from darwin.specification.policy import (
    PolicyClass,
    PolicyCompatibility,
    PolicyCompatibilityDeclaration,
    PolicySearchAuthority,
)

# --- FIXED vs TUNABLE construction-time discipline -----------------------------

def test_fixed_parameter_requires_a_fixed_value():
    with pytest.raises(ParameterDomainViolationError):
        ParameterDefinition(parameter_id="p1", status=ParameterStatus.FIXED, value_type=ParameterValueType.INTEGER)


def test_fixed_parameter_must_not_carry_a_domain():
    with pytest.raises(ParameterDomainViolationError):
        ParameterDefinition(
            parameter_id="p1",
            status=ParameterStatus.FIXED,
            value_type=ParameterValueType.INTEGER,
            fixed_value=5,
            domain=IntegerRangeDomain(minimum=1, maximum=10),
        )


def test_tunable_parameter_without_domain_is_a_construction_time_error():
    """PID-004 sec18: 'No: ATHENA may try whatever it wants.' -- an
    unbounded TUNABLE parameter is refused at construction, not accepted
    and left to ATHENA's discretion."""
    with pytest.raises(UnboundedTunableParameterError):
        ParameterDefinition(parameter_id="p1", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.INTEGER)


def test_tunable_parameter_must_not_carry_a_fixed_value():
    with pytest.raises(ParameterDomainViolationError):
        ParameterDefinition(
            parameter_id="p1",
            status=ParameterStatus.TUNABLE,
            value_type=ParameterValueType.INTEGER,
            fixed_value=5,
            domain=IntegerRangeDomain(minimum=1, maximum=10),
        )


def test_tunable_parameter_with_bounded_domain_constructs_cleanly():
    ParameterDefinition(
        parameter_id="ema_period",
        status=ParameterStatus.TUNABLE,
        value_type=ParameterValueType.INTEGER,
        domain=IntegerRangeDomain(minimum=10, maximum=200),
    )


# --- every closed domain kind ---------------------------------------------------

def test_numeric_range_domain_contains():
    domain = NumericRangeDomain(minimum=Decimal(0), maximum=Decimal(1))
    assert domain.contains(Decimal("0.5"))
    assert not domain.contains(Decimal("1.5"))
    with pytest.raises(ParameterDomainViolationError):
        NumericRangeDomain(minimum=Decimal(1), maximum=Decimal(0))


def test_integer_range_domain_contains():
    domain = IntegerRangeDomain(minimum=10, maximum=200)
    assert domain.contains(50)
    assert not domain.contains(500)


def test_discrete_enumeration_domain_requires_nonempty_and_contains():
    with pytest.raises(ParameterDomainViolationError):
        DiscreteEnumerationDomain(allowed_values=())
    domain = DiscreteEnumerationDomain(allowed_values=("EMA", "SMA"))
    assert domain.contains("EMA")
    assert not domain.contains("WMA")


def test_boolean_enumeration_domain_contains():
    domain = BooleanEnumerationDomain()
    assert domain.contains(True)
    assert domain.contains(False)


def test_duration_range_domain_contains():
    domain = DurationRangeDomain(minimum_seconds=60, maximum_seconds=3600)
    assert domain.contains(1800)
    assert not domain.contains(10)
    with pytest.raises(ParameterDomainViolationError):
        DurationRangeDomain(minimum_seconds=-1, maximum_seconds=10)


def test_unit_bearing_range_domain_requires_unit_and_contains():
    with pytest.raises(ParameterDomainViolationError):
        UnitBearingRangeDomain(minimum=Decimal(0), maximum=Decimal(10), unit="")
    domain = UnitBearingRangeDomain(minimum=Decimal(0), maximum=Decimal(50), unit="USD_PER_TROY_OUNCE")
    assert domain.contains(Decimal(25))
    assert not domain.contains(Decimal(100))


# --- out-of-domain value rejection (PID-004 sec42 critical case) --------------

def test_out_of_domain_tunable_value_is_rejected():
    param = ParameterDefinition(
        parameter_id="ema_period",
        status=ParameterStatus.TUNABLE,
        value_type=ParameterValueType.INTEGER,
        domain=IntegerRangeDomain(minimum=10, maximum=200),
    )
    validate_parameter_value(param, 50)  # in-domain: no raise
    with pytest.raises(ParameterDomainViolationError):
        validate_parameter_value(param, 5000)


def test_fixed_value_mismatch_is_rejected():
    param = ParameterDefinition(
        parameter_id="risk_pct", status=ParameterStatus.FIXED, value_type=ParameterValueType.DECIMAL, fixed_value=Decimal("1.0")
    )
    validate_parameter_value(param, Decimal("1.0"))
    with pytest.raises(ParameterDomainViolationError):
        validate_parameter_value(param, Decimal("2.0"))


# --- strategy-intrinsic exit vs execution-policy boundary (PID-004 sec17/sec42) -

def test_execution_policy_search_authority_requires_a_tunable_parameter():
    with pytest.raises(SpecificationError):
        PolicySearchAuthority(
            dimension="stop_loss_distance",
            parameter=ParameterDefinition(
                parameter_id="sl", status=ParameterStatus.FIXED, value_type=ParameterValueType.DECIMAL,
                fixed_value=Decimal(10),
            ),
        )


def test_policy_compatibility_declaration_disabled_must_not_carry_search_envelope():
    with pytest.raises(SpecificationError):
        PolicyCompatibilityDeclaration(
            policy_class=PolicyClass.EXECUTION_POLICY,
            compatibility=PolicyCompatibility.DISABLED,
            authorized_search_envelope=(
                PolicySearchAuthority(
                    dimension="stop_loss_distance",
                    parameter=ParameterDefinition(
                        parameter_id="sl", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.DECIMAL,
                        domain=NumericRangeDomain(minimum=Decimal(1), maximum=Decimal(50)),
                    ),
                ),
            ),
        )


def test_permitted_execution_policy_may_declare_a_bounded_search_envelope():
    declaration = PolicyCompatibilityDeclaration(
        policy_class=PolicyClass.EXECUTION_POLICY,
        compatibility=PolicyCompatibility.PERMITTED,
        authorized_search_envelope=(
            PolicySearchAuthority(
                dimension="stop_loss_distance",
                parameter=ParameterDefinition(
                    parameter_id="sl", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.DECIMAL,
                    domain=NumericRangeDomain(minimum=Decimal(1), maximum=Decimal(50)),
                ),
            ),
        ),
    )
    assert declaration.compatibility == PolicyCompatibility.PERMITTED
    assert len(declaration.authorized_search_envelope) == 1


def test_all_four_policy_classes_and_compatibility_values_exist():
    assert {c.value for c in PolicyClass} == {
        "EXECUTION_POLICY", "DIKE_POLICY", "SIZING_POLICY", "NEWS_CONTEXT_POLICY",
    }
    assert {c.value for c in PolicyCompatibility} == {"REQUIRED", "PERMITTED", "DISABLED", "IRRELEVANT"}
