"""PID-006B plan-adapter tests (Central Architecture correction
CA-006B-1/CA-006B-4): `darwin.apollo.plan_adapter.check_plan_capability`
derives APOLLO's engine-native entry specification from the compiled
`ExecutableStrategyPlan.semantic_payload` -- never from a raw
`StrategyVersion` directly. Every adversarial case here mutates the
PLAN's own canonical payload dict, not the `StrategyVersion` -- mutating
`StrategyVersion` alone would no longer affect what this module reads.
"""
from __future__ import annotations

import dataclasses

import pytest

from darwin.apollo.errors import (
    CapabilityBlockReason,
    EngineCapabilityBlockedError,
    InvalidConfigurationError,
)
from darwin.apollo.plan_adapter import (
    check_plan_capability,
    plan_condition_timeframe_code,
)
from darwin.research_contracts.compiler import CanonicalStrategyCompiler
from tests.fixtures.apollo_strategy import build_apollo_strategy_version


def _plan(strategy_version=None):
    sv = strategy_version or build_apollo_strategy_version()
    return CanonicalStrategyCompiler().compile(sv)


def _mutate_payload(plan, **overrides):
    return dataclasses.replace(plan, semantic_payload={**plan.semantic_payload, **overrides})


def test_supported_plan_resolves_to_entry_signal_spec() -> None:
    plan = _plan()
    spec = check_plan_capability(plan)
    assert spec.field == "CLOSE"
    assert spec.operator == "GT"
    assert spec.right_kind == "PARAMETER"
    assert spec.right_parameter_id == "entry_threshold_usd"
    assert plan_condition_timeframe_code(plan) == "H1"


def test_non_atomic_composition_is_capability_blocked() -> None:
    plan = _plan()
    bogus_composition = {"__type__": "AllComposition", "composition_id": "all-1"}
    mutated = _mutate_payload(plan, composition=bogus_composition)
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_COMPOSITION_SHAPE


def test_short_direction_is_capability_blocked() -> None:
    plan = _plan()
    composition = dict(plan.semantic_payload["composition"])
    composition["direction"] = "SHORT"
    mutated = _mutate_payload(plan, composition=composition)
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_DIRECTION


def test_nonempty_exit_rules_is_capability_blocked() -> None:
    plan = _plan()
    mutated = _mutate_payload(plan, exit_rules=[{"__type__": "AtomicCondition"}])
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_EXIT_RULES


def test_crosses_above_operator_is_capability_blocked() -> None:
    """CROSSES_ABOVE/CROSSES_BELOW require previous-bar state -- explicitly
    not implemented in this v1 slice."""
    plan = _plan()
    composition = dict(plan.semantic_payload["composition"])
    expression = dict(composition["expression"])
    expression["operator"] = "CROSSES_ABOVE"
    composition["expression"] = expression
    mutated = _mutate_payload(plan, composition=composition)
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_EXPRESSION_SHAPE


def test_boolean_expression_root_is_capability_blocked() -> None:
    plan = _plan()
    composition = dict(plan.semantic_payload["composition"])
    composition["expression"] = {"__type__": "BooleanExpression", "operator": "AND", "operands": []}
    mutated = _mutate_payload(plan, composition=composition)
    with pytest.raises(EngineCapabilityBlockedError):
        check_plan_capability(mutated)


def test_volume_field_is_not_supported() -> None:
    """VOLUME is not a price -- excluded from the supported OHLCV field set."""
    plan = _plan()
    composition = dict(plan.semantic_payload["composition"])
    expression = dict(composition["expression"])
    left = dict(expression["left"])
    left["fact_key"] = "OHLCV.VOLUME"
    expression["left"] = left
    composition["expression"] = expression
    mutated = _mutate_payload(plan, composition=composition)
    with pytest.raises(EngineCapabilityBlockedError):
        check_plan_capability(mutated)


def test_instrument_generic_is_capability_blocked() -> None:
    plan = _plan()
    mutated = _mutate_payload(
        plan,
        instrument_applicability={"__type__": "InstrumentApplicability", "kind": "INSTRUMENT_GENERIC", "instrument_ids": [], "generic_criteria": ["x"]},
    )
    with pytest.raises(EngineCapabilityBlockedError):
        check_plan_capability(mutated)


def test_instrument_not_xau_usd_is_invalid_configuration() -> None:
    plan = _plan()
    mutated = _mutate_payload(
        plan,
        instrument_applicability={"__type__": "InstrumentApplicability", "kind": "EXPLICIT_SINGLE", "instrument_ids": ["EUR_USD"], "generic_criteria": []},
    )
    with pytest.raises(InvalidConfigurationError):
        check_plan_capability(mutated)


def test_missing_stop_loss_parameter_declaration_is_capability_blocked() -> None:
    plan = _plan()
    tunable = [p for p in plan.semantic_payload["tunable_parameters"] if p["parameter_id"] != "stop_loss_distance_usd"]
    mutated = _mutate_payload(plan, tunable_parameters=tunable)
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.MISSING_RISK_PARAMETER_DECLARATION


def test_session_spec_present_is_capability_blocked() -> None:
    """CA-006B-4 adversarial test 7: a valid StrategyVersion declaring a
    real (non-null) session restriction must never silently run as if
    APOLLO honoured it -- it does not implement session filtering at all."""
    plan = _plan()
    mutated = _mutate_payload(
        plan,
        session_spec={
            "__type__": "SessionSpec", "iana_timezone": "America/New_York", "local_start": "08:00",
            "local_end": "17:00", "weekdays": [0, 1, 2, 3, 4], "dst_handling": "FOLLOW_IANA_TIMEZONE_RULES",
            "cross_midnight": False,
        },
    )
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_SESSION_SPEC


def test_setup_expiry_frames_is_capability_blocked() -> None:
    """CA-006B-4 adversarial test 8."""
    plan = _plan()
    mutated = _mutate_payload(
        plan,
        setup_expiry={"__type__": "ExpirySpec", "mode": "FRAMES", "frame_count": 5, "finest_bound_timeframe": "H1", "duration_seconds": None},
    )
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_SETUP_EXPIRY


def test_additional_data_requirement_is_capability_blocked() -> None:
    """CA-006B-4 adversarial test 9: a second, unsupported data
    requirement (e.g. news/IV data this engine never supplies) must never
    be silently ignored."""
    plan = _plan()
    extra_requirement = {
        "__type__": "DataRequirement", "requirement_id": "ares_news_sentiment", "display_name": "News sentiment",
        "fact_class": "NEWS_CONTEXT", "fact_reference_kind": "CANONICAL_FACT_REFERENCE",
        "authority_class": "ARES_GOVERNED_CONTEXT", "instrument_applicability": ["XAU_USD"],
        "timeframe": None, "required_historical_depth": {"__type__": "HistoricalDepthRequirement", "count": 1, "unit": "BARS"},
        "units": None, "required_fields": ["SENTIMENT_SCORE"], "causal_timing_policy": "AS_OF_PUBLISH_TIME", "mandatory": True,
    }
    mutated = _mutate_payload(plan, data_requirements=[*plan.semantic_payload["data_requirements"], extra_requirement])
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_DATA_REQUIREMENT


def test_intrabar_ambiguity_policy_not_applicable_is_capability_blocked() -> None:
    """CA-006B-4 adversarial test 10: APOLLO always applies
    CONSERVATIVE_SL_FIRST -- a strategy declaring NOT_APPLICABLE would
    misrepresent the real mechanics this engine applies."""
    plan = _plan()
    mutated = _mutate_payload(plan, intrabar_ambiguity_policy="NOT_APPLICABLE")
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_INTRABAR_AMBIGUITY_POLICY


def test_policy_declaration_execution_policy_disabled_is_blocked() -> None:
    plan = _plan()
    mutated = _mutate_payload(
        plan,
        policy_declarations=[{"__type__": "PolicyCompatibilityDeclaration", "policy_class": "EXECUTION_POLICY", "compatibility": "DISABLED", "authorized_search_envelope": [], "notes": None}],
    )
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_POLICY_DECLARATION


@pytest.mark.parametrize("policy_class", ["DIKE_POLICY", "SIZING_POLICY", "NEWS_CONTEXT_POLICY"])
def test_policy_declaration_required_for_unhonoured_class_is_blocked(policy_class) -> None:
    plan = _plan()
    mutated = _mutate_payload(
        plan,
        policy_declarations=[{"__type__": "PolicyCompatibilityDeclaration", "policy_class": policy_class, "compatibility": "REQUIRED", "authorized_search_envelope": [], "notes": None}],
    )
    with pytest.raises(EngineCapabilityBlockedError) as exc_info:
        check_plan_capability(mutated)
    assert exc_info.value.context.reason == CapabilityBlockReason.UNSUPPORTED_POLICY_DECLARATION
