"""PID-004A StrategyCandidate/SpecificationDraft/StrategyVersion +
finalisation-gate unit tests (PID-004 sec4/sec17/sec19/sec32-34/sec42)."""
from __future__ import annotations

import dataclasses

import pytest

from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.composition import Direction
from darwin.specification.data_requirements import (
    DataAuthorityClass,
    DataRequirement,
    FactClass,
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.domain import (
    StrategyCandidate,
    StrategyVersion,
    strategy_version_field_names,
)
from darwin.specification.errors import FinalisationError, SpecificationError
from darwin.specification.expressions import (
    Comparison,
    ComparisonOperator,
    EventPredicate,
    ParameterReference,
    UndefinedMeasurementBasis,
)
from darwin.specification.facts import FactReferenceKind
from darwin.specification.parameters import (
    IntegerRangeDomain,
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
from darwin.specification.readiness import PerRequirementAvailability, assess_readiness
from darwin.specification.timeframe import Timeframe
from darwin.specification.validation import (
    ValidationOutcomeStatus,
    finalise,
    validate_draft,
)
from tests.fixtures.specification_drafts import (
    accepted_provenance,
    minimal_valid_draft,
    now_utc,
    simple_atomic_condition,
)

# --- StrategyCandidate ----------------------------------------------------------

def test_strategy_candidate_requires_non_empty_id_and_title():
    with pytest.raises(SpecificationError):
        StrategyCandidate(candidate_id="", title="x")
    with pytest.raises(SpecificationError):
        StrategyCandidate(candidate_id="c1", title="")


def test_strategy_candidate_carries_lineage():
    candidate = StrategyCandidate(
        candidate_id="c3", title="Combined idea", origin_discovery_ids=("disc-1",), parent_candidate_ids=("c1", "c2")
    )
    assert candidate.parent_candidate_ids == ("c1", "c2")


# --- SpecificationDraft is genuinely mutable -------------------------------------

def test_specification_draft_is_mutable():
    draft = minimal_valid_draft()
    draft.title = "Updated title"
    assert draft.title == "Updated title"
    param = ParameterDefinition(
        parameter_id="ema_period", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.INTEGER,
        domain=IntegerRangeDomain(minimum=10, maximum=200),
    )
    draft.set_parameter(param)
    assert draft.tunable_parameters["ema_period"] is param


def test_specification_draft_has_no_status_or_is_finalised_field():
    """PID-004 sec19: finalisation state must never live as a flag on the
    draft itself."""
    field_names = {f.name for f in dataclasses.fields(minimal_valid_draft())}
    assert "status" not in field_names
    assert "is_finalised" not in field_names


# --- StrategyVersion is genuinely immutable --------------------------------------

def test_strategy_version_is_frozen():
    result = finalise(minimal_valid_draft(), strategy_version_id="sv-1")
    version = result.strategy_version
    assert version is not None
    with pytest.raises(dataclasses.FrozenInstanceError):
        version.title = "hacked"  # type: ignore[misc]


def test_finalise_never_mutates_the_draft():
    draft = minimal_valid_draft()
    title_before = draft.title
    finalise(draft, strategy_version_id="sv-1")
    assert draft.title == title_before
    field_names = {f.name for f in dataclasses.fields(draft)}
    assert "status" not in field_names  # still no such field after finalisation


def test_finalise_produces_a_genuinely_distinct_object_and_type_from_the_draft():
    draft = minimal_valid_draft()
    result = finalise(draft, strategy_version_id="sv-1")
    version = result.strategy_version
    assert version is not None
    assert type(version) is not type(draft)
    assert version is not draft
    assert isinstance(version, StrategyVersion)


def test_finalise_requires_non_empty_strategy_version_id():
    with pytest.raises(FinalisationError):
        finalise(minimal_valid_draft(), strategy_version_id="")


def test_semantic_and_artifact_payload_round_trip_to_the_same_stored_fingerprints():
    """Recomputing canonical_hash() from the finished StrategyVersion's OWN
    semantic_payload()/artifact_payload() must reproduce the exact
    fingerprints stored at finalisation time -- proving the fingerprint
    fields are not independently-set metadata that could drift from the
    object's real content."""
    from darwin.specification.fingerprint import canonical_hash

    version = finalise(minimal_valid_draft(), strategy_version_id="sv-roundtrip").strategy_version
    assert canonical_hash(version.semantic_payload()) == version.semantic_fingerprint
    assert canonical_hash(version.artifact_payload()) == version.artifact_record_fingerprint


# --- STRATEGY_NOT_SUFFICIENTLY_DEFINED is a returned outcome, never a raise ------

def test_undefined_measurement_basis_produces_governed_refusal_not_an_exception():
    condition = simple_atomic_condition("ambiguous_wall_proximity")
    condition = dataclasses.replace(
        condition,
        expression=Comparison(
            operator=ComparisonOperator.LT,
            left=condition.expression.left,
            right=UndefinedMeasurementBasis(note="author never defined what 'near the wall' means"),
        ),
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)  # must not raise
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "UNDEFINED_MEASUREMENT_BASIS" for f in outcome.findings)

    result = finalise(draft, strategy_version_id="sv-should-not-exist")  # must not raise either
    assert result.strategy_version is None
    assert result.outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED


def test_missing_provenance_blocks_finalisation():
    draft = minimal_valid_draft()
    draft.provenance.clear()
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "MISSING_PROVENANCE" for f in outcome.findings)


def test_undeclared_parameter_reference_blocks_finalisation():
    condition = simple_atomic_condition("uses_undeclared_param")
    condition = dataclasses.replace(
        condition,
        expression=Comparison(
            operator=ComparisonOperator.GT, left=condition.expression.left, right=ParameterReference(parameter_id="ghost_param")
        ),
    )
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "UNDECLARED_PARAMETER_REFERENCE" for f in outcome.findings)


def test_undeclared_data_requirement_reference_blocks_finalisation():
    """PID-004 sec42 critical case: an EventPredicate naming a fact
    requirement that was never declared on the draft must be rejected --
    the DARWIN analogue of 'unknown fact rejected'."""
    condition = simple_atomic_condition("references_undeclared_requirement")
    condition = dataclasses.replace(condition, expression=EventPredicate(fact_requirement_id="ghost_requirement"))
    draft = minimal_valid_draft(composition=condition)
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "UNDECLARED_DATA_REQUIREMENT_REFERENCE" for f in outcome.findings)


def test_missing_top_level_completeness_fields_blocks_finalisation():
    draft = minimal_valid_draft()
    draft.intrabar_ambiguity_policy = None
    outcome = validate_draft(draft)
    assert outcome.status == ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED
    assert any(f.code == "MISSING_INTRABAR_AMBIGUITY_POLICY" for f in outcome.findings)


# --- finalisation succeeds even when data will be DATA_BLOCKED (sec34) ----------

def test_finalisation_succeeds_when_semantics_complete_even_if_data_will_be_blocked():
    requirement = DataRequirement(
        requirement_id="cpi_yoy",
        display_name="US CPI YoY surprise",
        fact_class=FactClass.ECONOMIC_SURPRISE,
        fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.ARES_GOVERNED_CONTEXT,
        instrument_applicability=("XAU_USD",),
        timeframe=None,
        required_historical_depth=HistoricalDepthRequirement(count=5, unit=HistoricalDepthUnit.YEARS),
        units=None,
        required_fields=("actual", "consensus"),
        causal_timing_policy=CausalTimingPolicy.ORIGINAL_PUBLISHED_VALUE_ONLY,
    )
    condition = simple_atomic_condition("cpi_beat_trigger")
    condition = dataclasses.replace(
        condition,
        expression=Comparison(
            operator=ComparisonOperator.GT,
            left=condition.expression.left,
            right=condition.expression.right,
        ),
    )
    draft = minimal_valid_draft(composition=condition)
    draft.set_data_requirement(requirement)
    # reference the requirement via an EventPredicate somewhere reachable --
    # attach it as a second exit rule condition to keep the fixture small.
    from darwin.specification.composition import AtomicCondition

    event_condition = AtomicCondition(
        condition_id="cpi_context",
        semantic_role="CONTEXT",
        timeframe=Timeframe("D1"),
        expression=EventPredicate(fact_requirement_id="cpi_yoy"),
        direction=Direction.BOTH,
    )
    draft.exit_rules = (event_condition,)
    draft.set_provenance(accepted_provenance("cpi_context"))

    result = finalise(draft, strategy_version_id="sv-iv-wall-like")
    assert result.outcome.is_valid
    version = result.strategy_version
    assert version is not None

    readiness = assess_readiness(
        assessment_id="a1", strategy_version_id=version.strategy_version_id,
        mandatory_requirement_ids={r.requirement_id for r in version.data_requirements},
        per_requirement={"cpi_yoy": (PerRequirementAvailability.AUTHORITY_NOT_ONBOARDED, "ARES economic-surprise history not onboarded")},
        assessed_at_utc=now_utc(),
    )
    from darwin.specification.readiness import OverallReadinessState

    assert readiness.overall_state == OverallReadinessState.DATA_BLOCKED
    # SPECIFIED + DATA_BLOCKED is valid and real -- the StrategyVersion is untouched.
    assert version.strategy_version_id == "sv-iv-wall-like"


# --- policy identity boundary (sec12) --------------------------------------------

def test_strategy_version_has_no_field_for_any_frozen_policy_version_id():
    names = strategy_version_field_names()
    for forbidden in ("execution_policy_version_id", "dike_policy_version_id", "sizing_policy_version_id", "news_context_policy_version_id",
                      "execution_policy_version", "dike_policy_version", "sizing_policy_version", "news_context_policy_version"):
        assert forbidden not in names


def test_strategy_version_has_no_data_readiness_field():
    names = strategy_version_field_names()
    assert "data_readiness" not in names
    assert "readiness" not in names
    assert "data_readiness_assessment" not in names


# --- strategy-intrinsic exit vs execution-policy boundary (sec17/sec42) ---------

def test_intrinsic_exit_and_execution_policy_search_authority_live_in_different_places():
    """'Exit when RSI crosses back below 50' is strategy-intrinsic and
    belongs on exit_rules; 'a stop-loss chosen from an authorised range'
    is execution-policy search authority and belongs on
    policy_declarations. This test proves they are genuinely different
    buckets on the finished StrategyVersion, not one undifferentiated
    'exit rules' collection."""
    rsi_below_50_exit = simple_atomic_condition("rsi_cross_below_50", semantic_role="MANAGEMENT")
    draft = minimal_valid_draft()
    draft.exit_rules = (rsi_below_50_exit,)
    draft.set_provenance(accepted_provenance("rsi_cross_below_50"))

    stop_loss_param = ParameterDefinition(
        parameter_id="stop_loss_distance", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.DECIMAL,
        domain=IntegerRangeDomain(minimum=5, maximum=50),
    )
    draft.set_policy_declaration(
        PolicyCompatibilityDeclaration(
            policy_class=PolicyClass.EXECUTION_POLICY,
            compatibility=PolicyCompatibility.PERMITTED,
            authorized_search_envelope=(PolicySearchAuthority(dimension="stop_loss_distance", parameter=stop_loss_param),),
        )
    )

    result = finalise(draft, strategy_version_id="sv-exit-vs-policy")
    version = result.strategy_version
    assert version is not None

    exit_condition_ids = {c.condition_id for c in version.exit_rules}
    assert "rsi_cross_below_50" in exit_condition_ids

    execution_declaration = next(d for d in version.policy_declarations if d.policy_class == PolicyClass.EXECUTION_POLICY)
    search_dimensions = {a.dimension for a in execution_declaration.authorized_search_envelope}
    assert "stop_loss_distance" in search_dimensions
    # the two buckets do not overlap:
    assert "stop_loss_distance" not in exit_condition_ids
    assert "rsi_cross_below_50" not in search_dimensions


# --- FinalisationResult self-consistency ----------------------------------------

def test_finalisation_result_invariants():
    from darwin.specification.validation import FinalisationResult, ValidationOutcome

    valid_outcome = ValidationOutcome(status=ValidationOutcomeStatus.VALID)
    with pytest.raises(FinalisationError):
        FinalisationResult(outcome=valid_outcome, strategy_version=None)

    blocked_outcome = ValidationOutcome(status=ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED)
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-x").strategy_version
    with pytest.raises(FinalisationError):
        FinalisationResult(outcome=blocked_outcome, strategy_version=version)
