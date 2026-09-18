"""Pure, no-Postgres-required tests for darwin.specification.serialization
(PID-004A persistence directive item 15). Round-trip correctness against
real domain objects, plus the three explicit-refusal cases: unknown
node type, unknown governed operator, and unknown/unsupported
serialization schema version.
"""
from __future__ import annotations

import copy
from datetime import datetime
from decimal import Decimal

import pytest

from darwin.specification.composition import (
    AllComposition,
    AtomicCondition,
    Direction,
)
from darwin.specification.domain import SpecificationDraft
from darwin.specification.errors import UnknownOperatorError
from darwin.specification.expressions import Comparison, ComparisonOperator, Literal
from darwin.specification.facts import MissingInputBehavior, SpecificationDerivedFact
from darwin.specification.parameters import (
    NumericRangeDomain,
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
)
from darwin.specification.serialization import (
    SERIALIZATION_SCHEMA_VERSION,
    UnknownSerializationNodeError,
    UnsupportedSerializationSchemaVersionError,
    deserialize_specification_draft,
    deserialize_strategy_version,
    serialize_specification_draft,
    serialize_strategy_version,
)
from darwin.specification.timeframe import Timeframe
from darwin.specification.validation import finalise
from tests.fixtures.specification_drafts import (
    accepted_provenance,
    h1_close_reference,
    h1_high_reference,
    hermes_ohlcv_requirement,
    minimal_valid_draft,
)


def test_strategy_version_round_trips_exactly():
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-serialization-test").strategy_version
    doc = serialize_strategy_version(version)
    rehydrated = deserialize_strategy_version(doc)
    assert rehydrated == version


def test_strategy_version_document_is_plain_json_safe():
    """Never pickle/repr -- the document must be json.dumps-able as-is."""
    import json

    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-json-safe-test").strategy_version
    doc = serialize_strategy_version(version)
    json.dumps(doc)  # must not raise


def test_decimal_and_datetime_preserved_exactly_not_degraded_to_float():
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-decimal-test").strategy_version
    doc = serialize_strategy_version(version)
    rehydrated = deserialize_strategy_version(doc)

    threshold = rehydrated.composition.expression.right
    assert isinstance(threshold, Literal)
    assert isinstance(threshold.value, Decimal)
    assert threshold.value == Decimal(4000)
    assert isinstance(rehydrated.finalised_at_utc, datetime)
    assert rehydrated.finalised_at_utc == version.finalised_at_utc


def test_composition_all_and_derived_fact_chain_round_trip():
    ema = SpecificationDerivedFact(
        derived_fact_id="ema_50", input_facts=(h1_close_reference(),), algorithm_id="EMA", algorithm_version="v1",
        parameters=(("period", 50), ("scale", Decimal("1.5"))), timeframe=Timeframe("H1"), warm_up_bars=50,
        output_unit="USD_PER_TROY_OUNCE", missing_input_behavior=MissingInputBehavior.FAIL_EVALUATION,
    )
    condition = AtomicCondition(
        condition_id="close_crosses_ema", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
        expression=Comparison(operator=ComparisonOperator.CROSSES_ABOVE, left=h1_close_reference(), right=ema),
        direction=Direction.LONG,
    )
    all_comp = AllComposition(
        composition_id="all_x", components=(
            condition,
            AtomicCondition(
                condition_id="high_above", semantic_role="TRIGGER", timeframe=Timeframe("H1"),
                expression=Comparison(operator=ComparisonOperator.GT, left=h1_high_reference("H1"), right=Literal(Decimal(4010), unit="USD_PER_TROY_OUNCE")),
                direction=Direction.LONG,
            ),
        ),
    )
    from darwin.specification.applicability import IntrabarAmbiguityPolicy
    from darwin.specification.composition import (
        ExpiryMode,
        ExpirySpec,
        all_leaf_conditions,
    )
    from tests.fixtures.specification_drafts import XAU_USD_APPLICABILITY

    draft = SpecificationDraft(
        draft_id="draft-all-derived", candidate_id="candidate-all-derived", schema_semantic_version="1.0.0",
        instrument_applicability=XAU_USD_APPLICABILITY, composition=all_comp,
        intrabar_ambiguity_policy=IntrabarAmbiguityPolicy.NOT_APPLICABLE, setup_expiry=ExpirySpec(mode=ExpiryMode.NOT_APPLICABLE),
    )
    draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    for leaf in all_leaf_conditions(all_comp):
        draft.set_provenance(accepted_provenance(leaf.condition_id))

    version = finalise(draft, strategy_version_id="sv-all-derived-test").strategy_version
    doc = serialize_strategy_version(version)
    rehydrated = deserialize_strategy_version(doc)
    assert rehydrated == version
    assert rehydrated.composition.primitive.value == "ALL"
    right = rehydrated.composition.components[0].expression.right
    assert isinstance(right, SpecificationDerivedFact)
    assert right.parameters == (("period", 50), ("scale", Decimal("1.5")))


def test_tunable_parameter_domain_round_trips():
    param = ParameterDefinition(
        parameter_id="threshold", status=ParameterStatus.TUNABLE, value_type=ParameterValueType.DECIMAL,
        unit="USD_PER_TROY_OUNCE", domain=NumericRangeDomain(minimum=Decimal("3800.5"), maximum=Decimal("4200.25")),
    )
    draft = minimal_valid_draft()
    draft.set_parameter(param)
    version = finalise(draft, strategy_version_id="sv-param-test").strategy_version
    doc = serialize_strategy_version(version)
    rehydrated = deserialize_strategy_version(doc)
    rt_param = next(p for p in rehydrated.tunable_parameters if p.parameter_id == "threshold")
    assert rt_param.domain.minimum == Decimal("3800.5")
    assert rt_param.domain.maximum == Decimal("4200.25")


def test_specification_draft_round_trips_including_dict_shape():
    draft = minimal_valid_draft()
    doc = serialize_specification_draft(draft)
    rehydrated = deserialize_specification_draft(doc)
    assert rehydrated.draft_id == draft.draft_id
    assert rehydrated.candidate_id == draft.candidate_id
    assert isinstance(rehydrated.fixed_parameters, dict)
    assert isinstance(rehydrated.data_requirements, dict)
    assert set(rehydrated.data_requirements) == set(draft.data_requirements)
    assert rehydrated.composition.condition_id == draft.composition.condition_id


def test_incomplete_draft_with_no_composition_round_trips():
    draft = SpecificationDraft(draft_id="d1", candidate_id="c1", schema_semantic_version="1.0.0")
    doc = serialize_specification_draft(draft)
    rehydrated = deserialize_specification_draft(doc)
    assert rehydrated.composition is None
    assert rehydrated.instrument_applicability is None
    assert rehydrated.setup_expiry is None


# --- explicit refusal cases (item 15) ---------------------------------------


def test_unsupported_schema_version_is_rejected_explicitly():
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-schema-version-test").strategy_version
    doc = serialize_strategy_version(version)
    assert doc["serialization_schema_version"] == SERIALIZATION_SCHEMA_VERSION
    doc["serialization_schema_version"] = "999-does-not-exist"
    with pytest.raises(UnsupportedSerializationSchemaVersionError):
        deserialize_strategy_version(doc)


def test_unknown_node_type_is_rejected_explicitly_not_skipped():
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-unknown-node-test").strategy_version
    doc = serialize_strategy_version(version)
    corrupted = copy.deepcopy(doc)
    # Corrupt the comparison's right operand into a node type that does not
    # exist in the closed dispatch table.
    corrupted["composition"]["expression"]["right"] = {"__type__": "TotallyMadeUpNode", "value": "anything"}
    with pytest.raises(UnknownSerializationNodeError):
        deserialize_strategy_version(corrupted)


def test_unknown_comparison_operator_is_rejected_via_the_governed_constructor():
    """Decoding never re-implements 'which operators are known' -- it
    routes through the SAME governed constructor darwin.specification.
    expressions already uses, so an unknown operator raises the domain's
    own UnknownOperatorError, not a separate serialization-only check."""
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-unknown-operator-test").strategy_version
    doc = serialize_strategy_version(version)
    corrupted = copy.deepcopy(doc)
    corrupted["composition"]["expression"]["operator"] = "BOGUS_OPERATOR_DOES_NOT_EXIST"
    with pytest.raises(UnknownOperatorError):
        deserialize_strategy_version(corrupted)


def test_unknown_composition_root_type_is_rejected():
    draft = minimal_valid_draft()
    version = finalise(draft, strategy_version_id="sv-unknown-root-test").strategy_version
    doc = serialize_strategy_version(version)
    corrupted = copy.deepcopy(doc)
    corrupted["composition"] = {"__type__": "NotARealCompositionType", "composition_id": "x"}
    with pytest.raises(UnknownSerializationNodeError):
        deserialize_strategy_version(corrupted)


def test_malformed_document_missing_type_tag_is_rejected():
    with pytest.raises(UnknownSerializationNodeError):
        deserialize_strategy_version({"serialization_schema_version": SERIALIZATION_SCHEMA_VERSION})
