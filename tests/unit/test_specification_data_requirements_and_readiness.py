"""PID-004A data requirement + readiness unit tests (PID-004
sec24/sec24A/sec26/sec27/sec28)."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.data_requirements import (
    DataAuthorityClass,
    DataRequirement,
    FactClass,
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.errors import ReadinessAssessmentError, SpecificationError
from darwin.specification.facts import FactReferenceKind
from darwin.specification.readiness import (
    OverallReadinessState,
    PerRequirementAvailability,
    assess_readiness,
)
from darwin.specification.timeframe import Timeframe


def _ohlcv_requirement(requirement_id: str = "xau_h1_ohlcv") -> DataRequirement:
    return DataRequirement(
        requirement_id=requirement_id,
        display_name="XAU_USD H1 OHLCV",
        fact_class=FactClass.MARKET_OHLCV,
        fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("H1"),
        required_historical_depth=HistoricalDepthRequirement(count=500, unit=HistoricalDepthUnit.BARS),
        units="USD_PER_TROY_OUNCE",
        required_fields=("open", "high", "low", "close"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )


def _news_requirement(requirement_id: str = "cpi_yoy") -> DataRequirement:
    return DataRequirement(
        requirement_id=requirement_id,
        display_name="US CPI YoY surprise",
        fact_class=FactClass.ECONOMIC_SURPRISE,
        fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.ARES_GOVERNED_CONTEXT,
        instrument_applicability=("XAU_USD",),
        timeframe=None,
        required_historical_depth=HistoricalDepthRequirement(count=5, unit=HistoricalDepthUnit.YEARS),
        units=None,
        required_fields=("consensus", "actual", "surprise"),
        causal_timing_policy=CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY,
    )


# --- causal-sensitivity discipline is bidirectional -----------------------------

def test_causally_sensitive_fact_class_requires_explicit_causal_timing_policy():
    with pytest.raises(SpecificationError):
        DataRequirement(
            requirement_id="cpi_yoy",
            display_name="US CPI YoY",
            fact_class=FactClass.ECONOMIC_SURPRISE,
            fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.ARES_GOVERNED_CONTEXT,
            instrument_applicability=("XAU_USD",),
            timeframe=None,
            required_historical_depth=HistoricalDepthRequirement(count=5, unit=HistoricalDepthUnit.YEARS),
            units=None,
            required_fields=("actual",),
            causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
        )


def test_non_causally_sensitive_fact_class_must_declare_not_applicable():
    with pytest.raises(SpecificationError):
        DataRequirement(
            requirement_id="xau_h1_ohlcv",
            display_name="XAU H1 OHLCV",
            fact_class=FactClass.MARKET_OHLCV,
            fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
            instrument_applicability=("XAU_USD",),
            timeframe=Timeframe("H1"),
            required_historical_depth=HistoricalDepthRequirement(count=500, unit=HistoricalDepthUnit.BARS),
            units="USD_PER_TROY_OUNCE",
            required_fields=("close",),
            causal_timing_policy=CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY,
        )


def test_representative_fact_classes_for_fixtures_all_exist():
    for name in (
        "MARKET_OHLCV", "OPTIONS_CHAIN", "IMPLIED_VOLATILITY", "OPEN_INTEREST",
        "NEWS_CONTEXT", "ECONOMIC_SURPRISE", "PREDICTION_MARKET",
    ):
        assert name in {c.value for c in FactClass}


def test_requirement_requires_at_least_one_required_field():
    with pytest.raises(SpecificationError):
        DataRequirement(
            requirement_id="x", display_name="x", fact_class=FactClass.MARKET_OHLCV,
            fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
            authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
            instrument_applicability=("XAU_USD",), timeframe=Timeframe("H1"),
            required_historical_depth=HistoricalDepthRequirement(count=1, unit=HistoricalDepthUnit.BARS),
            units="USD", required_fields=(), causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
        )


# --- readiness: separate object, TESTABLE/DATA_BLOCKED, per-requirement states -

def test_all_available_is_testable():
    requirement = _ohlcv_requirement()
    assessment = assess_readiness(
        assessment_id="a1", strategy_version_id="sv1",
        mandatory_requirement_ids={requirement.requirement_id},
        per_requirement={requirement.requirement_id: (PerRequirementAvailability.AVAILABLE, None)},
        assessed_at_utc=datetime.now(UTC),
    )
    assert assessment.overall_state == OverallReadinessState.TESTABLE


def test_one_unavailable_mandatory_requirement_is_data_blocked():
    requirement = _news_requirement()
    assessment = assess_readiness(
        assessment_id="a1", strategy_version_id="sv1",
        mandatory_requirement_ids={requirement.requirement_id},
        per_requirement={
            requirement.requirement_id: (PerRequirementAvailability.AUTHORITY_NOT_ONBOARDED, "ARES options authority not onboarded"),
        },
        assessed_at_utc=datetime.now(UTC),
    )
    assert assessment.overall_state == OverallReadinessState.DATA_BLOCKED


def test_assessment_missing_a_mandatory_requirement_is_rejected():
    with pytest.raises(ReadinessAssessmentError):
        assess_readiness(
            assessment_id="a1", strategy_version_id="sv1",
            mandatory_requirement_ids={"req_a", "req_b"},
            per_requirement={"req_a": (PerRequirementAvailability.AVAILABLE, None)},
            assessed_at_utc=datetime.now(UTC),
        )


def test_data_blocked_to_testable_is_a_new_assessment_same_strategy_version():
    """PID-004 sec27/sec28 critical case: later availability moves
    DATA_BLOCKED -> TESTABLE via a NEW readiness assessment attached to
    the SAME strategy_version_id -- no new StrategyVersion involved."""
    requirement = _news_requirement()
    blocked = assess_readiness(
        assessment_id="a1", strategy_version_id="sv-fixed",
        mandatory_requirement_ids={requirement.requirement_id},
        per_requirement={requirement.requirement_id: (PerRequirementAvailability.UNAVAILABLE, "not yet onboarded")},
        assessed_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert blocked.overall_state == OverallReadinessState.DATA_BLOCKED

    later = assess_readiness(
        assessment_id="a2", strategy_version_id="sv-fixed",
        mandatory_requirement_ids={requirement.requirement_id},
        per_requirement={requirement.requirement_id: (PerRequirementAvailability.AVAILABLE, None)},
        assessed_at_utc=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert later.overall_state == OverallReadinessState.TESTABLE
    assert blocked.strategy_version_id == later.strategy_version_id == "sv-fixed"
    assert blocked.assessment_id != later.assessment_id


def test_all_per_requirement_availability_states_exist():
    assert {a.value for a in PerRequirementAvailability} == {
        "AVAILABLE", "UNAVAILABLE", "INSUFFICIENT_HISTORY", "INSUFFICIENT_RESOLUTION",
        "AUTHORITY_NOT_ONBOARDED", "CONTRACT_INCOMPATIBLE", "UNKNOWN",
    }
