"""PID-004A controlled contract fixtures (PID-004 sec20/sec30/sec41/sec41A).

Fourteen architectural conformance fixtures proving contract expressiveness.
Every fixture here is clearly-labelled TEST fixture data -- none of it is
presented as a real discovered/proven strategy (PID-004 sec30: "Controlled
fixture only. Never present it as real discovered/proven evidence.").
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from darwin.specification.applicability import (
    DstHandling,
    IntrabarAmbiguityPolicy,
    SessionSpec,
)
from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.composition import (
    AllComposition,
    AnyComposition,
    AtomicCondition,
    ContextTriggerComposition,
    Direction,
    ExpiryMode,
    ExpirySpec,
    SequenceComponent,
    SequenceComposition,
    SequenceTieSemantics,
)
from darwin.specification.data_requirements import (
    DataAuthorityClass,
    DataRequirement,
    FactClass,
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.domain import SpecificationDraft
from darwin.specification.expressions import (
    BooleanExpression,
    BooleanOperator,
    Comparison,
    ComparisonOperator,
    EventPredicate,
    Literal,
    ParameterReference,
    SessionOperator,
    SessionPredicate,
    UndefinedMeasurementBasis,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    FactReferenceKind,
    MissingInputBehavior,
    SpecificationDerivedFact,
)
from darwin.specification.parameters import (
    IntegerRangeDomain,
    NumericRangeDomain,
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
)
from darwin.specification.policy import (
    PolicyClass,
    PolicyCompatibility,
    PolicyCompatibilityDeclaration,
    PolicySearchAuthority,
)
from darwin.specification.readiness import (
    OverallReadinessState,
    PerRequirementAvailability,
    assess_readiness,
)
from darwin.specification.timeframe import Timeframe
from darwin.specification.validation import (
    ValidationOutcomeStatus,
    finalise,
    validate_draft,
)
from tests.fixtures.specification_drafts import (
    XAU_USD_APPLICABILITY,
    accepted_provenance,
    h1_close_reference,
    h1_high_reference,
    hermes_ohlcv_requirement,
    minimal_valid_draft,
    simple_atomic_condition,
)


def _bare_draft(draft_id: str, composition) -> SpecificationDraft:
    return SpecificationDraft(
        draft_id=draft_id,
        candidate_id=f"candidate-{draft_id}",
        schema_semantic_version="1.0.0",
        title=f"Contract fixture: {draft_id}",
        thesis="Controlled architectural conformance fixture -- not a real trading hypothesis.",
        instrument_applicability=XAU_USD_APPLICABILITY,
        composition=composition,
        intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE,
        setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
    )


def _with_provenance(draft: SpecificationDraft) -> SpecificationDraft:
    from darwin.specification.composition import all_leaf_conditions

    for leaf in all_leaf_conditions(draft.composition):
        draft.set_provenance(accepted_provenance(leaf.condition_id))
    for exit_rule in draft.exit_rules:
        draft.set_provenance(accepted_provenance(exit_rule.condition_id))
    return draft


# --- 1. Simple single-timeframe atomic strategy (PID-004 sec41.A) --------------

def test_fixture_01_simple_atomic_ohlcv_strategy():
    draft = minimal_valid_draft()
    result = finalise(draft, strategy_version_id="fixture-01")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    assert result.strategy_version is not None


# --- 2. ALL ---------------------------------------------------------------------

def test_fixture_02_all_composition():
    all_comp = AllComposition(
        composition_id="all_close_and_high",
        components=(
            simple_atomic_condition("close_above_4000", threshold="4000"),
            AtomicCondition(
                condition_id="high_above_4010",
                semantic_role="TRIGGER",
                timeframe=Timeframe("H1"),
                expression=Comparison(
                    operator=ComparisonOperator.GT,
                    left=h1_high_reference("H1"),
                    right=Literal(Decimal(4010), unit="USD_PER_TROY_OUNCE"),
                ),
                direction=Direction.LONG,
            ),
        ),
    )
    draft = _with_provenance(_bare_draft("fixture-02", all_comp))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    result = finalise(draft, strategy_version_id="fixture-02")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    assert result.strategy_version.composition.primitive.value == "ALL"


# --- 3. ANY -----------------------------------------------------------------------

def test_fixture_03_any_composition():
    any_comp = AnyComposition(
        composition_id="any_close_or_high",
        components=(
            simple_atomic_condition("close_above_4000", threshold="4000"),
            AtomicCondition(
                condition_id="high_above_4050",
                semantic_role="TRIGGER",
                timeframe=Timeframe("H1"),
                expression=Comparison(
                    operator=ComparisonOperator.GT,
                    left=h1_high_reference("H1"),
                    right=Literal(Decimal(4050), unit="USD_PER_TROY_OUNCE"),
                ),
                direction=Direction.LONG,
            ),
        ),
    )
    draft = _with_provenance(_bare_draft("fixture-03", any_comp))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    result = finalise(draft, strategy_version_id="fixture-03")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    assert result.strategy_version.composition.primitive.value == "ANY"


# --- 4. SEQUENCE -- never reduced to AND ----------------------------------------

def test_fixture_04_sequence_composition_distinct_from_all():
    sequence = SequenceComposition(
        composition_id="seq_breakout_then_retest",
        components=(
            SequenceComponent(0, simple_atomic_condition("breaks_above_4000", threshold="4000")),
            SequenceComponent(
                1,
                AtomicCondition(
                    condition_id="retests_4000",
                    semantic_role="CONFIRMATION",
                    timeframe=Timeframe("H1"),
                    expression=Comparison(
                        operator=ComparisonOperator.LTE, left=h1_close_reference(), right=Literal(Decimal(4005), unit="USD_PER_TROY_OUNCE")
                    ),
                    direction=Direction.LONG,
                ),
            ),
        ),
        ordering_window_seconds=4 * 3600,
        tie_semantics=SequenceTieSemantics.TIES_PERMITTED,
    )
    draft = _with_provenance(_bare_draft("fixture-04", sequence))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    result = finalise(draft, strategy_version_id="fixture-04")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version = result.strategy_version
    assert version.composition.primitive.value == "SEQUENCE"
    # structurally distinct from AllComposition -- has fields ALL cannot declare:
    assert hasattr(version.composition, "ordering_window_seconds")
    assert hasattr(version.composition, "tie_semantics")


# --- 5. CONTEXT_TRIGGER ----------------------------------------------------------

def test_fixture_05_context_trigger_composition():
    context = AtomicCondition(
        condition_id="h4_uptrend_context",
        semantic_role="CONTEXT",
        timeframe=Timeframe("H4"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("H4"), right=Literal(Decimal(3900), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    trigger = AtomicCondition(
        condition_id="m5_breakout_trigger",
        semantic_role="TRIGGER",
        timeframe=Timeframe("M5"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M5"), right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    ct = ContextTriggerComposition(
        composition_id="ct_gold_context_trigger",
        context=context,
        trigger=trigger,
        context_validity=ExpirySpec(mode=ExpiryMode.DURATION, duration_seconds=4 * 3600),
    )
    draft = _with_provenance(_bare_draft("fixture-05", ct))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H4"))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="M5"))
    result = finalise(draft, strategy_version_id="fixture-05")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version = result.strategy_version
    assert version.composition.primitive.value == "CONTEXT_TRIGGER"
    # never a bare 2-item SEQUENCE:
    assert not hasattr(version.composition, "sequence_index")
    assert version.composition.context.timeframe.is_coarser_than(version.composition.trigger.timeframe)


# --- 6. Multi-timeframe context/trigger with causal, no-look-ahead alignment ---

def test_fixture_06_multi_timeframe_context_trigger_causal_alignment():
    """PID-004 sec12: 'Cross-timeframe alignment semantics must be
    deterministic and causal. No look-ahead.' Modelled here by the
    FRAMES expiry explicitly naming the finest bound timeframe (M5),
    matching HELIOS's real rule (HELIOS archaeology finding #8) rather
    than an ambiguous 'N frames' with no stated timeframe."""
    context = AtomicCondition(
        condition_id="h1_context",
        semantic_role="CONTEXT",
        timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("H1"), right=Literal(Decimal(3950), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    trigger = AtomicCondition(
        condition_id="m5_trigger",
        semantic_role="TRIGGER",
        timeframe=Timeframe("M5"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M5"), right=Literal(Decimal(3980), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    ct = ContextTriggerComposition(
        composition_id="ct_multi_timeframe",
        context=context,
        trigger=trigger,
        context_validity=ExpirySpec(mode=ExpiryMode.FRAMES, frame_count=48, finest_bound_timeframe=Timeframe("M5")),
    )
    draft = _with_provenance(_bare_draft("fixture-06", ct))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="M5"))
    result = finalise(draft, strategy_version_id="fixture-06")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version = result.strategy_version
    assert version.composition.context_validity.finest_bound_timeframe == Timeframe("M5")


def test_fixture_06_frames_expiry_naming_the_wrong_finest_timeframe_is_refused():
    """A validation-level cross-check, not just a constructor check: an
    author who names H1 (the CONTEXT leg) as the 'finest bound timeframe'
    when the actual finest is M5 must be caught before finalisation."""
    context = AtomicCondition(
        condition_id="h1_context", semantic_role="CONTEXT", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("H1"), right=Literal(Decimal(3950), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    trigger = AtomicCondition(
        condition_id="m5_trigger", semantic_role="TRIGGER", timeframe=Timeframe("M5"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M5"), right=Literal(Decimal(3980), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    ct = ContextTriggerComposition(
        composition_id="ct_wrong_finest", context=context, trigger=trigger,
        context_validity=ExpirySpec(mode=ExpiryMode.FRAMES, frame_count=48, finest_bound_timeframe=Timeframe("H1")),
    )
    draft = _with_provenance(_bare_draft("fixture-06b", ct))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="M5"))
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "FRAMES_EXPIRY_TIMEFRAME_MISMATCH" for f in outcome.findings)


# --- 7. Session/timezone/DST strategy --------------------------------------------

def test_fixture_07_session_timezone_dst_strategy():
    condition = AtomicCondition(
        condition_id="ny_session_breakout",
        semantic_role="TRIGGER",
        timeframe=Timeframe("M15"),
        expression=BooleanExpression(
            operator=BooleanOperator.AND,
            operands=(
                Comparison(operator=ComparisonOperator.GT, left=h1_close_reference("M15"), right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
                SessionPredicate(operator=SessionOperator.IN_SESSION),
            ),
        ),
        direction=Direction.LONG,
    )
    draft = _with_provenance(_bare_draft("fixture-07", condition))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="M15"))
    draft.session_spec = SessionSpec(
        iana_timezone="America/New_York", local_start="08:00", local_end="17:00",
        weekdays=(0, 1, 2, 3, 4), dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
    )
    result = finalise(draft, strategy_version_id="fixture-07")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    assert result.strategy_version.session_spec.iana_timezone == "America/New_York"


# --- 8. Wick/touch strategy -------------------------------------------------------

def test_fixture_08_wick_touch_strategy_distinguishes_high_from_close():
    """PID-004 sec15/sec21: 'high touches level' is not interchangeable
    with 'close above level'. This fixture references OHLCV.HIGH
    explicitly and declares CONSERVATIVE_SL_FIRST rather than silently
    defaulting to close-only logic."""
    wick_touch = AtomicCondition(
        condition_id="high_touches_4050_resistance",
        semantic_role="TRIGGER",
        timeframe=Timeframe("H1"),
        expression=Comparison(
            operator=ComparisonOperator.CROSSES_ABOVE,
            left=h1_high_reference("H1"),
            right=Literal(Decimal(4050), unit="USD_PER_TROY_OUNCE"),
        ),
        direction=Direction.SHORT,
    )
    draft = _with_provenance(_bare_draft("fixture-08", wick_touch))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    draft.intrabar_ambiguity_policy = IntrabarAmbiguityPolicy.CONSERVATIVE_SL_FIRST
    result = finalise(draft, strategy_version_id="fixture-08")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    assert result.strategy_version.intrabar_ambiguity_policy == IntrabarAmbiguityPolicy.CONSERVATIVE_SL_FIRST


# --- 9. Fixed + tunable parameter strategy ---------------------------------------

def test_fixture_09_fixed_and_tunable_parameter_strategy():
    condition = AtomicCondition(
        condition_id="close_above_tunable_threshold",
        semantic_role="TRIGGER",
        timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=h1_close_reference(), right=ParameterReference(parameter_id="breakout_threshold")),
        direction=Direction.LONG,
    )
    draft = _with_provenance(_bare_draft("fixture-09", condition))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    draft.set_parameter(
        ParameterDefinition(
            parameter_id="breakout_threshold", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.DECIMAL,
            unit="USD_PER_TROY_OUNCE", domain=NumericRangeDomain(minimum=Decimal(3800), maximum=Decimal(4200)),
        )
    )
    draft.set_parameter(
        ParameterDefinition(
            parameter_id="trade_both_directions", status=ParameterStatus.FIXED, value_type=ParameterValueType.BOOLEAN, fixed_value=False,
        )
    )
    result = finalise(draft, strategy_version_id="fixture-09")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version = result.strategy_version
    assert {p.parameter_id for p in version.tunable_parameters} == {"breakout_threshold"}
    assert {p.parameter_id for p in version.fixed_parameters} == {"trade_both_directions"}


# --- 10. DIKE-compatible strategy (policy boundary in practice) -----------------

def test_fixture_10_dike_compatibility_declared_without_embedding_a_policy_version():
    draft = minimal_valid_draft(draft_id="fixture-10", candidate_id="candidate-fixture-10")
    draft.set_policy_declaration(
        PolicyCompatibilityDeclaration(policy_class=PolicyClass.EXECUTION_POLICY, compatibility=PolicyCompatibility.DISABLED)
    )
    draft.set_policy_declaration(
        PolicyCompatibilityDeclaration(
            policy_class=PolicyClass.DIKE_POLICY,
            compatibility=PolicyCompatibility.PERMITTED,
            authorized_search_envelope=(
                PolicySearchAuthority(
                    dimension="max_leverage",
                    parameter=ParameterDefinition(
                        parameter_id="max_leverage", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.INTEGER,
                        domain=IntegerRangeDomain(minimum=1, maximum=10),
                    ),
                ),
            ),
        )
    )
    result = finalise(draft, strategy_version_id="fixture-10")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version = result.strategy_version
    dike_decl = next(d for d in version.policy_declarations if d.policy_class == PolicyClass.DIKE_POLICY)
    assert dike_decl.compatibility == PolicyCompatibility.PERMITTED
    # no field anywhere on StrategyVersion names a frozen DIKEPolicyVersion id:
    from darwin.specification.domain import strategy_version_field_names

    assert "dike_policy_version_id" not in strategy_version_field_names()


# --- 11. IV-wall DATA_BLOCKED fixture (PID-004 sec30) ----------------------------

def test_fixture_11_iv_wall_data_blocked():
    iv_requirement = DataRequirement(
        requirement_id="xau_iv_surface", display_name="XAU_USD implied volatility surface",
        fact_class=FactClass.IMPLIED_VOLATILITY, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(count=3, unit=HistoricalDepthUnit.YEARS),
        units="IV_PERCENT", required_fields=("strike", "expiry", "implied_volatility"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )
    oi_requirement = DataRequirement(
        requirement_id="xau_open_interest", display_name="XAU_USD options open interest",
        fact_class=FactClass.OPEN_INTEREST, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(count=3, unit=HistoricalDepthUnit.YEARS),
        units="CONTRACTS", required_fields=("strike", "expiry", "open_interest"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )
    # PID-004A hardening item 5: EventPredicate is reserved for governed
    # event/context fact classes (NEWS_CONTEXT/ECONOMIC_SURPRISE/
    # PREDICTION_MARKET -- see darwin.specification.data_requirements.
    # CAUSALLY_SENSITIVE_FACT_CLASSES). An implied-volatility "wall" is
    # continuously-observed market-derived data, not a discrete external
    # event, so it is modelled here as a genuine CanonicalFactReference
    # value compared against a level -- never smuggled through
    # EventPredicate merely because both concepts involve "context".
    iv_wall_fact = CanonicalFactReference(
        fact_key="OPTIONS.IMPLIED_VOLATILITY", fact_class=FactClass.IMPLIED_VOLATILITY,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, unit="IV_PERCENT", timeframe=Timeframe("D1"),
        requirement_id="xau_iv_surface",
    )
    wall_exit = AtomicCondition(
        condition_id="iv_wall_context", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=iv_wall_fact, right=Literal(Decimal(0), unit="IV_PERCENT")),
        direction=Direction.BOTH,
    )
    trigger = simple_atomic_condition("price_approaches_iv_wall", threshold="4000")
    draft = _with_provenance(_bare_draft("fixture-11", trigger))
    draft.exit_rules = (wall_exit,)
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    draft.set_data_requirement(iv_requirement)
    draft.set_data_requirement(oi_requirement)
    draft.set_provenance(accepted_provenance("iv_wall_context"))

    result = finalise(draft, strategy_version_id="fixture-11")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version = result.strategy_version

    readiness = assess_readiness(
        assessment_id="fixture-11-readiness", strategy_version_id=version.strategy_version_id,
        mandatory_requirement_ids={r.requirement_id for r in version.data_requirements},
        per_requirement={
            "hermes_xau_usd_h1_ohlcv": (PerRequirementAvailability.AVAILABLE, None),
            "xau_iv_surface": (PerRequirementAvailability.AUTHORITY_NOT_ONBOARDED, "options authority not yet onboarded"),
            "xau_open_interest": (PerRequirementAvailability.AUTHORITY_NOT_ONBOARDED, "options authority not yet onboarded"),
        },
        assessed_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert readiness.overall_state == OverallReadinessState.DATA_BLOCKED
    # StrategyVersion itself remains untouched/valid regardless:
    assert version.strategy_version_id == "fixture-11"


# --- 12. Deliberately insufficient strategy --------------------------------------

def test_fixture_12_deliberately_insufficient_strategy_refused():
    ambiguous = AtomicCondition(
        condition_id="near_the_iv_wall",
        semantic_role="TRIGGER",
        timeframe=Timeframe("H1"),
        expression=Comparison(
            operator=ComparisonOperator.LT, left=h1_close_reference(),
            right=UndefinedMeasurementBasis(note="'near an IV wall' names no wall definition, expiry, distance, or trigger"),
        ),
        direction=Direction.SHORT,
    )
    draft = _with_provenance(_bare_draft("fixture-12", ambiguous))
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED

    result = finalise(draft, strategy_version_id="fixture-12-should-not-exist")
    assert result.strategy_version is None
    assert result.outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED


# --- 13. Causal external-context strategy ----------------------------------------

def test_fixture_13_causal_external_context_strategy():
    cpi_requirement = DataRequirement(
        requirement_id="cpi_yoy_surprise", display_name="US CPI YoY surprise",
        fact_class=FactClass.ECONOMIC_SURPRISE, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.ARES_GOVERNED_CONTEXT, instrument_applicability=("XAU_USD",),
        timeframe=None, required_historical_depth=HistoricalDepthRequirement(count=10, unit=HistoricalDepthUnit.YEARS),
        units=None, required_fields=("consensus", "actual", "surprise"),
        causal_timing_policy=CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY,
    )
    context = AtomicCondition(
        condition_id="cpi_beat_context", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
        expression=EventPredicate(fact_requirement_id="cpi_yoy_surprise"), direction=Direction.BOTH,
    )
    trigger = simple_atomic_condition("gold_reaction_trigger", threshold="4000")
    draft = _with_provenance(_bare_draft("fixture-13", trigger))
    draft.exit_rules = (context,)
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    draft.set_data_requirement(cpi_requirement)
    draft.set_provenance(accepted_provenance("cpi_beat_context"))

    result = finalise(draft, strategy_version_id="fixture-13")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version = result.strategy_version
    cpi_req = next(r for r in version.data_requirements if r.requirement_id == "cpi_yoy_surprise")
    assert cpi_req.causal_timing_policy == CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY

    # prove the no-leak invariant using the same causal machinery as
    # test_specification_facts_and_causal.py:
    from darwin.specification.causal import (
        ExternalFactObservation,
        select_causally_available_revision,
    )

    original = ExternalFactObservation(
        fact_requirement_id="cpi_yoy_surprise", event_time=datetime(2025, 12, 10, tzinfo=UTC),
        published_at_utc=datetime(2025, 12, 10, 13, 30, tzinfo=UTC), observed_at_utc=datetime(2025, 12, 10, 13, 30, tzinfo=UTC),
        effective_at_utc=datetime(2025, 12, 10, 13, 30, tzinfo=UTC), revision="original", value=Decimal("0.3"),
    )
    revised = ExternalFactObservation(
        fact_requirement_id="cpi_yoy_surprise", event_time=datetime(2025, 12, 10, tzinfo=UTC),
        published_at_utc=datetime(2026, 1, 10, tzinfo=UTC), observed_at_utc=datetime(2026, 1, 10, tzinfo=UTC),
        effective_at_utc=datetime(2026, 1, 10, tzinfo=UTC), revision="revised", value=Decimal("0.5"),
    )
    at_release = select_causally_available_revision([original, revised], decision_instant_utc=original.effective_at_utc)
    assert at_release.value == Decimal("0.3")


# --- 14. Deterministic derived-fact strategy (EMA) -------------------------------

def test_fixture_14_deterministic_derived_fact_strategy():
    ema_50 = SpecificationDerivedFact(
        derived_fact_id="ema_50_h1", input_facts=(h1_close_reference(),), algorithm_id="EMA", algorithm_version="v1",
        parameters=(("period", 50),), timeframe=Timeframe("H1"), warm_up_bars=50, output_unit="USD_PER_TROY_OUNCE",
        missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
    )
    condition = AtomicCondition(
        condition_id="close_crosses_above_ema50", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.CROSSES_ABOVE, left=h1_close_reference(), right=ema_50),
        direction=Direction.LONG,
    )
    draft = _with_provenance(_bare_draft("fixture-14", condition))
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    result = finalise(draft, strategy_version_id="fixture-14")
    assert result.outcome.status == ValidationOutcomeStatus.VALID
    version_v1 = result.strategy_version

    # changing the derived fact's algorithm_version changes semantic_fingerprint:
    ema_50_v2 = SpecificationDerivedFact(
        derived_fact_id="ema_50_h1", input_facts=(h1_close_reference(),), algorithm_id="EMA", algorithm_version="v2",
        parameters=(("period", 50),), timeframe=Timeframe("H1"), warm_up_bars=50, output_unit="USD_PER_TROY_OUNCE",
        missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
    )
    condition_v2 = AtomicCondition(
        condition_id="close_crosses_above_ema50", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.CROSSES_ABOVE, left=h1_close_reference(), right=ema_50_v2),
        direction=Direction.LONG,
    )
    draft_v2 = _with_provenance(_bare_draft("fixture-14-v2", condition_v2))
    draft_v2.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    version_v2 = finalise(draft_v2, strategy_version_id="fixture-14-v2").strategy_version

    assert version_v1.semantic_fingerprint != version_v2.semantic_fingerprint

    # the derived fact never masquerades as canonical HERMES authority:
    from darwin.specification.facts import FactReferenceKindError, require_canonical

    right_operand = version_v1.composition.expression.right
    assert isinstance(right_operand, SpecificationDerivedFact)
    with pytest.raises(FactReferenceKindError):
        require_canonical(right_operand)
