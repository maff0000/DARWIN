"""PID-004A "Specification Contract" hardening pass -- negative-test suite
(Architect-directed bounded hardening, 2026-09-17).

Closes four real semantic-integrity gaps in code that already exists and
was already tested:

1. the expression tree was not actually closed at runtime (`object`-typed
   fields accepted anything);
2. a canonical fact could be consumed by a strategy with no declared
   `DataRequirement` backing it;
3. `CanonicalFactReference.fact_key` was a free, merely-non-empty string
   even for the currently-governed HERMES market namespace;
5. dangling/inconsistent SessionPredicate/TemporalPredicate/cross-timeframe
   references could survive into a finalised StrategyVersion.

Every test below proves a REJECTION -- a governed construction-time error,
or a `STRATEGY_NOT_SUFFICIENTLY_DEFINED` validation finding with a specific
code -- for something the pre-hardening contract would have silently
accepted. (Item numbers above match the Architect's directive; item 4 is
covered separately by the real-SCOUT-fitness harness, not here, and item 6
is a doctrine/comment-only fix with no runtime behaviour to test.)
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.composition import AllComposition, AtomicCondition, Direction
from darwin.specification.data_requirements import (
    DataAuthorityClass,
    DataRequirement,
    FactClass,
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.errors import (
    InvalidOperandError,
    SpecificationError,
    UngovernedFactKeyError,
    UnrecognisedExpressionNodeError,
)
from darwin.specification.expressions import (
    BooleanExpression,
    BooleanOperator,
    Comparison,
    ComparisonOperator,
    EventPredicate,
    Literal,
    SessionOperator,
    SessionPredicate,
    TemporalOperator,
    TemporalPredicate,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    FactReferenceKind,
    MissingInputBehavior,
    SpecificationDerivedFact,
)
from darwin.specification.timeframe import Timeframe
from darwin.specification.validation import (
    ValidationOutcomeStatus,
    _iter_expression_nodes,
    finalise,
    validate_draft,
)
from tests.fixtures.specification_drafts import (
    accepted_provenance,
    h1_close_reference,
    hermes_ohlcv_requirement,
    hermes_ohlcv_requirement_id,
    minimal_valid_draft,
    new_york_session,
    simple_atomic_condition,
)

# === Item 1: the expression tree is closed ======================================

def test_comparison_rejects_a_raw_string_operand():
    with pytest.raises(SpecificationError):
        Comparison(operator=ComparisonOperator.GT, left="close", right=Literal(Decimal(1)))


def test_comparison_rejects_an_arbitrary_unrelated_object():
    with pytest.raises(SpecificationError):
        Comparison(operator=ComparisonOperator.GT, left=object(), right=Literal(Decimal(1)))


def test_comparison_rejects_an_unsupported_dataclass():
    @dataclasses.dataclass(frozen=True)
    class _NotAGovernedOperand:
        value: int

    with pytest.raises(InvalidOperandError):
        Comparison(operator=ComparisonOperator.GT, left=_NotAGovernedOperand(value=1), right=Literal(Decimal(1)))


def test_comparison_rejects_a_nested_comparison_as_an_operand():
    """Comparisons compare VALUES, not truth values -- a nested
    Comparison/BooleanExpression must never be accepted as an operand."""
    inner = Comparison(operator=ComparisonOperator.GT, left=Literal(Decimal(1)), right=Literal(Decimal(0)))
    with pytest.raises(InvalidOperandError):
        Comparison(operator=ComparisonOperator.GT, left=inner, right=Literal(Decimal(1)))


def test_boolean_expression_rejects_a_bare_literal_operand():
    with pytest.raises(InvalidOperandError):
        BooleanExpression(operator=BooleanOperator.AND, operands=(Literal(Decimal(1)), Literal(Decimal(2))))


def test_boolean_expression_rejects_a_raw_string_operand():
    comparison = Comparison(operator=ComparisonOperator.GT, left=Literal(Decimal(1)), right=Literal(Decimal(0)))
    with pytest.raises(InvalidOperandError):
        BooleanExpression(operator=BooleanOperator.AND, operands=(comparison, "not-a-real-condition"))


def test_atomic_condition_rejects_a_raw_string_expression():
    with pytest.raises(InvalidOperandError):
        AtomicCondition(
            condition_id="bad_expression_type",
            semantic_role="TRIGGER",
            timeframe=Timeframe("H1"),
            expression="close > 4000",
            direction=Direction.LONG,
        )


def test_derived_fact_rejects_a_raw_string_input():
    with pytest.raises(SpecificationError):
        SpecificationDerivedFact(
            derived_fact_id="bad_ema_string_input", input_facts=("close",), algorithm_id="EMA", algorithm_version="v1",
            parameters=(("period", 50),), timeframe=Timeframe("H1"), warm_up_bars=50, output_unit="USD",
            missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
        )


def test_derived_fact_rejects_an_arbitrary_unrelated_object_as_input():
    with pytest.raises(SpecificationError):
        SpecificationDerivedFact(
            derived_fact_id="bad_ema_object_input", input_facts=(object(),), algorithm_id="EMA", algorithm_version="v1",
            parameters=(), timeframe=Timeframe("H1"), warm_up_bars=1, output_unit="USD",
            missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
        )


def test_tree_walker_fails_explicitly_on_a_node_it_could_not_have_been_constructed_with():
    """Defense in depth: even if a node bypasses every constructor check
    (here, via the frozen-dataclass escape hatch `object.__setattr__`),
    the recursive tree walker itself must refuse to silently treat it as
    an inert leaf -- it must fail explicitly (PID-004A hardening item 1)."""
    comparison = Comparison(operator=ComparisonOperator.GT, left=Literal(Decimal(1)), right=Literal(Decimal(0)))
    object.__setattr__(comparison, "left", "sneaky-bypass-string")
    with pytest.raises(UnrecognisedExpressionNodeError):
        list(_iter_expression_nodes(comparison))


# === Item 3: fact_key is governed for the currently-onboarded HERMES namespace ===

def test_hermes_market_fact_key_with_unknown_field_is_rejected_at_construction():
    with pytest.raises(UngovernedFactKeyError):
        CanonicalFactReference(
            fact_key="OHLCV.BOGUS", fact_class=FactClass.MARKET_OHLCV,
            authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
            unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H1"), requirement_id="whatever",
        )


def test_hermes_market_fact_key_with_wrong_namespace_is_rejected_at_construction():
    with pytest.raises(UngovernedFactKeyError):
        CanonicalFactReference(
            fact_key="BARS.CLOSE", fact_class=FactClass.MARKET_OHLCV,
            authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
            unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H1"), requirement_id="whatever",
        )


def test_not_yet_onboarded_fact_class_may_still_describe_a_free_text_semantic_fact():
    """PID-004A hardening item 3: DARWIN must still be able to specify a
    future DATA_BLOCKED strategy whose eventual data authority is not
    onboarded yet -- only the CURRENTLY governed HERMES market namespace
    enforces a closed field vocabulary; this must NOT raise."""
    ref = CanonicalFactReference(
        fact_key="OPTIONS.IMPLIED_VOLATILITY", fact_class=FactClass.IMPLIED_VOLATILITY,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, unit="IV_PERCENT", timeframe=Timeframe("D1"),
        requirement_id="xau_iv_surface",
    )
    assert ref.fact_key == "OPTIONS.IMPLIED_VOLATILITY"


# === Item 2: every consumed canonical fact must bind to a real DataRequirement ===

def test_canonical_fact_with_no_matching_requirement_at_all_is_refused():
    orphan_ref = CanonicalFactReference(
        fact_key="OHLCV.CLOSE", fact_class=FactClass.MARKET_OHLCV, authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H1"), requirement_id="nonexistent_requirement",
    )
    condition = AtomicCondition(
        condition_id="orphan_fact_condition", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=orphan_ref, right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "MISSING_DATA_REQUIREMENT_FOR_CANONICAL_FACT" for f in outcome.findings)

    result = finalise(draft, strategy_version_id="sv-should-not-exist-orphan-fact")
    assert result.strategy_version is None


def test_canonical_fact_requirement_authority_class_mismatch_is_refused():
    ref = CanonicalFactReference(
        fact_key="OHLCV.CLOSE", fact_class=FactClass.MARKET_OHLCV,
        authority_class=DataAuthorityClass.OTHER_GOVERNED_AUTHORITY,  # real requirement below is HERMES_CANONICAL_MARKET
        unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H1"),
        requirement_id=hermes_ohlcv_requirement_id(timeframe="H1"),
    )
    condition = AtomicCondition(
        condition_id="authority_mismatch_condition", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=ref, right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "DATA_REQUIREMENT_AUTHORITY_CLASS_MISMATCH" for f in outcome.findings)


def test_canonical_fact_requirement_timeframe_mismatch_is_refused():
    ref = CanonicalFactReference(
        fact_key="OHLCV.CLOSE", fact_class=FactClass.MARKET_OHLCV, authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H4"),  # real requirement below is H1
        requirement_id=hermes_ohlcv_requirement_id(timeframe="H1"),
    )
    condition = AtomicCondition(
        condition_id="timeframe_mismatch_condition", semantic_role="TRIGGER", timeframe=Timeframe("H4"),
        expression=Comparison(operator=ComparisonOperator.GT, left=ref, right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "DATA_REQUIREMENT_TIMEFRAME_MISMATCH" for f in outcome.findings)


def test_canonical_fact_requirement_unit_mismatch_is_refused():
    ref = CanonicalFactReference(
        fact_key="OHLCV.CLOSE", fact_class=FactClass.MARKET_OHLCV, authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="EUR_PER_TROY_OUNCE",  # real requirement below is USD_PER_TROY_OUNCE
        timeframe=Timeframe("H1"), requirement_id=hermes_ohlcv_requirement_id(timeframe="H1"),
    )
    condition = AtomicCondition(
        condition_id="unit_mismatch_condition", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=ref, right=Literal(Decimal(4000), unit="EUR_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "DATA_REQUIREMENT_UNIT_MISMATCH" for f in outcome.findings)


def test_canonical_fact_requirement_field_mismatch_is_refused():
    restricted_requirement = DataRequirement(
        requirement_id="xau_h1_close_only", display_name="XAU_USD H1 close-only bars",
        fact_class=FactClass.MARKET_OHLCV, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET, instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("H1"), required_historical_depth=HistoricalDepthRequirement(count=200, unit=HistoricalDepthUnit.BARS),
        units="USD_PER_TROY_OUNCE", required_fields=("CLOSE",), causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )
    ref = CanonicalFactReference(
        fact_key="OHLCV.VOLUME",  # not in restricted_requirement.required_fields
        fact_class=FactClass.MARKET_OHLCV, authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H1"), requirement_id="xau_h1_close_only",
    )
    condition = AtomicCondition(
        condition_id="field_mismatch_condition", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=ref, right=Literal(Decimal(1000), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    draft.set_data_requirement(restricted_requirement)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "DATA_REQUIREMENT_FIELD_MISMATCH" for f in outcome.findings)


def test_derived_fact_with_canonical_input_lacking_a_requirement_is_refused():
    """Derived facts must recursively terminate in COVERED canonical
    requirements -- a derived fact whose canonical input has no matching
    DataRequirement must be refused, discovered by walking `input_facts`
    transitively (the same `_iter_expression_nodes` recursion used
    everywhere else in this module)."""
    orphan_input = CanonicalFactReference(
        fact_key="OHLCV.CLOSE", fact_class=FactClass.MARKET_OHLCV, authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H1"), requirement_id="nonexistent_requirement_for_derived_input",
    )
    ema = SpecificationDerivedFact(
        derived_fact_id="ema_50_orphan_input", input_facts=(orphan_input,), algorithm_id="EMA", algorithm_version="v1",
        parameters=(("period", 50),), timeframe=Timeframe("H1"), warm_up_bars=50, output_unit="USD_PER_TROY_OUNCE",
        missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
    )
    condition = AtomicCondition(
        condition_id="derived_orphan_condition", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.CROSSES_ABOVE, left=h1_close_reference(), right=ema),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "MISSING_DATA_REQUIREMENT_FOR_CANONICAL_FACT" for f in outcome.findings)


def test_event_predicate_referencing_a_plain_market_data_requirement_is_refused():
    """PID-004A hardening item 5: EventPredicate must reference an
    appropriate governed event/context requirement -- not merely any
    arbitrary requirement id typed in, including a plain market-data one."""
    ohlcv_requirement = hermes_ohlcv_requirement(timeframe="D1")
    condition = AtomicCondition(
        condition_id="misused_event_predicate", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
        expression=EventPredicate(fact_requirement_id=ohlcv_requirement.requirement_id), direction=Direction.BOTH,
    )
    draft = minimal_valid_draft()
    draft.exit_rules = (condition,)
    draft.set_data_requirement(ohlcv_requirement)
    draft.set_provenance(accepted_provenance("misused_event_predicate"))
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "EVENT_PREDICATE_REQUIREMENT_NOT_EVENT" for f in outcome.findings)


# === Item 5: reference completeness (no dangling references) ===================

def test_session_predicate_without_a_declared_session_spec_is_refused():
    condition = AtomicCondition(
        condition_id="session_no_spec", semantic_role="TRIGGER", timeframe=Timeframe("M15"),
        expression=SessionPredicate(operator=SessionOperator.IN_SESSION), direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    assert draft.session_spec is None
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "MISSING_SESSION_SPEC" for f in outcome.findings)

    result = finalise(draft, strategy_version_id="sv-should-not-exist-session")
    assert result.strategy_version is None


def test_session_predicate_with_a_declared_session_spec_is_accepted():
    condition = AtomicCondition(
        condition_id="session_with_spec", semantic_role="TRIGGER", timeframe=Timeframe("M15"),
        expression=SessionPredicate(operator=SessionOperator.IN_SESSION), direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    draft.session_spec = new_york_session()
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.VALID


def test_temporal_predicate_with_a_dangling_reference_is_refused():
    condition = AtomicCondition(
        condition_id="temporal_dangling", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=TemporalPredicate(operator=TemporalOperator.SINCE_EVENT, reference="a_condition_that_does_not_exist"),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "DANGLING_TEMPORAL_PREDICATE_REFERENCE" for f in outcome.findings)

    result = finalise(draft, strategy_version_id="sv-should-not-exist-temporal")
    assert result.strategy_version is None


def test_temporal_predicate_referencing_a_real_condition_id_is_accepted():
    referenced = simple_atomic_condition("setup_formed")
    temporal_leaf = AtomicCondition(
        condition_id="within_bars_of_setup", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=TemporalPredicate(operator=TemporalOperator.WITHIN_N_BARS, reference="setup_formed", n_bars=5),
        direction=Direction.LONG,
    )
    composition = AllComposition(composition_id="all_setup_and_within", components=(referenced, temporal_leaf))
    draft = minimal_valid_draft(composition=composition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.VALID


def test_atomic_condition_referencing_a_different_timeframe_fact_with_no_composition_relationship_is_refused():
    """An H1-bound AtomicCondition must never silently reference an H4
    fact -- that belongs to explicit composition (CONTEXT_TRIGGER), never
    a single atomic condition."""
    mismatched_ref = CanonicalFactReference(
        fact_key="OHLCV.CLOSE", fact_class=FactClass.MARKET_OHLCV, authority_class=DataAuthorityClass.HERMES_CANONICAL_MARKET,
        unit="USD_PER_TROY_OUNCE", timeframe=Timeframe("H4"), requirement_id=hermes_ohlcv_requirement_id(timeframe="H4"),
    )
    condition = AtomicCondition(
        condition_id="h1_leaf_smuggling_h4_fact", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=mismatched_ref, right=Literal(Decimal(4000), unit="USD_PER_TROY_OUNCE")),
        direction=Direction.LONG,
    )
    draft = minimal_valid_draft(composition=condition)
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H4"))
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "ATOMIC_CONDITION_TIMEFRAME_MISMATCH" for f in outcome.findings)

    result = finalise(draft, strategy_version_id="sv-should-not-exist-atomic-timeframe")
    assert result.strategy_version is None
