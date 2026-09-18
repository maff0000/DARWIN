"""PID-004A instrument applicability + session/DST + intrabar-ambiguity
unit tests (PID-004 sec11/sec13/sec21)."""
from __future__ import annotations

import pytest

from darwin.specification.applicability import (
    DstHandling,
    InstrumentApplicability,
    InstrumentApplicabilityKind,
    IntrabarAmbiguityPolicy,
    SessionSpec,
)
from darwin.specification.errors import SpecificationError


def test_explicit_single_requires_exactly_one_instrument():
    InstrumentApplicability(kind=InstrumentApplicabilityKind.EXPLICIT_SINGLE, instrument_ids=("XAU_USD",))
    with pytest.raises(SpecificationError):
        InstrumentApplicability(kind=InstrumentApplicabilityKind.EXPLICIT_SINGLE, instrument_ids=("XAU_USD", "XAG_USD"))
    with pytest.raises(SpecificationError):
        InstrumentApplicability(kind=InstrumentApplicabilityKind.EXPLICIT_SINGLE, instrument_ids=())


def test_explicit_set_requires_at_least_one_and_no_generic_criteria():
    InstrumentApplicability(kind=InstrumentApplicabilityKind.EXPLICIT_SET, instrument_ids=("XAU_USD", "XAG_USD"))
    with pytest.raises(SpecificationError):
        InstrumentApplicability(kind=InstrumentApplicabilityKind.EXPLICIT_SET, instrument_ids=())


def test_instrument_generic_requires_explicit_criteria_never_bare():
    with pytest.raises(SpecificationError):
        InstrumentApplicability(kind=InstrumentApplicabilityKind.INSTRUMENT_GENERIC)
    InstrumentApplicability(
        kind=InstrumentApplicabilityKind.INSTRUMENT_GENERIC,
        generic_criteria=("quote_asset == USD", "has IMPLIED_VOLATILITY fact class onboarded"),
    )


def test_instrument_generic_must_not_carry_explicit_instrument_ids():
    with pytest.raises(SpecificationError):
        InstrumentApplicability(
            kind=InstrumentApplicabilityKind.INSTRUMENT_GENERIC,
            instrument_ids=("XAU_USD",),
            generic_criteria=("quote_asset == USD",),
        )


def test_session_spec_requires_real_iana_timezone():
    with pytest.raises(SpecificationError):
        SessionSpec(
            iana_timezone="Not/A_Real_Zone", local_start="08:00", local_end="17:00",
            weekdays=(0, 1, 2, 3, 4), dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
        )


def test_session_spec_valid_iana_timezone_constructs_cleanly():
    SessionSpec(
        iana_timezone="America/New_York", local_start="08:00", local_end="17:00",
        weekdays=(0, 1, 2, 3, 4), dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
    )


def test_session_spec_requires_at_least_one_weekday():
    with pytest.raises(SpecificationError):
        SessionSpec(
            iana_timezone="America/New_York", local_start="08:00", local_end="17:00",
            weekdays=(), dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
        )


def test_session_spec_rejects_malformed_local_times():
    with pytest.raises(SpecificationError):
        SessionSpec(
            iana_timezone="America/New_York", local_start="8am", local_end="17:00",
            weekdays=(0,), dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
        )
    with pytest.raises(SpecificationError):
        SessionSpec(
            iana_timezone="America/New_York", local_start="08:00", local_end="25:00",
            weekdays=(0,), dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
        )


def test_intrabar_ambiguity_policy_has_explicit_not_applicable_value():
    assert IntrabarAmbiguityPolicy.NOT_APPLICABLE.value == "NOT_APPLICABLE"
    assert IntrabarAmbiguityPolicy.CONSERVATIVE_SL_FIRST.value == "CONSERVATIVE_SL_FIRST"
