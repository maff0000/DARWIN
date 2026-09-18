"""Deterministic, versioned, governed serialization for PID-004A persistence
(PID-004 sec37/PID-004A persistence directive item 15).

Never pickle, never Python `repr`, never `eval`/`exec` -- every document
produced here is plain JSON (`dict`/`list`/`str`/`int`/`bool`/`None`), and
every document consumed here is reconstructed through an explicit, closed
dispatch table keyed on a `__type__` discriminator string. An unrecognised
`__type__` -- or a `serialization_schema_version` this build does not
recognise -- raises explicitly (`UnknownSerializationNodeError` /
`UnsupportedSerializationSchemaVersionError`); there is no code path here
that falls back to "treat it as an inert leaf" or "look the class up by
name via getattr/importlib" (that would be its own kind of arbitrary
deserialization). Wherever a node also carries a governed operator/enum
value, decoding routes through the SAME governed constructors
`darwin.specification.expressions`/`.facts`/`.composition`/etc. already
use (e.g. `comparison_operator_from_raw`, `ComparisonOperator(...)`) --
this module never re-implements "which operators exist", it only decides
how to walk the tree.

`Decimal`/`datetime` are preserved exactly (never degraded to `float`):
a `Decimal` is tagged `{"__decimal__": "<exact text>"}` and a `datetime` is
tagged `{"__datetime__": "<isoformat with offset>"}` -- the same
exact-text discipline `darwin.specification.fingerprint.canonicalize`
already uses for hashing, extended here so it also round-trips losslessly
back into the original Python objects (canonicalize() is one-way -- it
exists only to hash, never to reconstruct).

Covers both governed persistence documents this contract phase needs:

- `serialize_strategy_version`/`deserialize_strategy_version` -- the
  immutable `StrategyVersion`'s full canonical payload (PID-004A
  persistence directive item 5: "the canonical immutable semantic
  payload... canonical provenance/artifact payload" -- both recoverable
  from ONE document, since rehydrating it and calling the rehydrated
  object's own `.semantic_payload()`/`.artifact_payload()` reproduces
  exactly what `darwin.specification.validation.finalise` fed into
  `canonical_hash` for each fingerprint).
- `serialize_specification_draft`/`deserialize_specification_draft` -- the
  mutable `SpecificationDraft`'s complete machine-readable contract (item
  4), preserving the dict-vs-tuple shape distinction between draft and
  finalised version.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from darwin.specification.applicability import (
    DstHandling,
    InstrumentApplicability,
    InstrumentApplicabilityKind,
    IntrabarAmbiguityPolicy,
    SessionSpec,
)
from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.composition import (
    AllComposition,
    AnyComposition,
    AtomicCondition,
    ComponentDirectionRelationship,
    CompositionRoot,
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
from darwin.specification.domain import SpecificationDraft, StrategyVersion
from darwin.specification.errors import SpecificationError
from darwin.specification.expressions import (
    BooleanExpression,
    Comparison,
    EventPredicate,
    Literal,
    ParameterReference,
    SessionPredicate,
    TemporalPredicate,
    UndefinedMeasurementBasis,
    boolean_operator_from_raw,
    comparison_operator_from_raw,
    session_operator_from_raw,
    temporal_operator_from_raw,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    FactReferenceKind,
    MissingInputBehavior,
    SpecificationDerivedFact,
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
)
from darwin.specification.policy import (
    PolicyClass,
    PolicyCompatibility,
    PolicyCompatibilityDeclaration,
    PolicySearchAuthority,
)
from darwin.specification.provenance import (
    ProvenanceRecord,
    RuleAcceptanceState,
    RuleOrigin,
)
from darwin.specification.timeframe import Timeframe

SERIALIZATION_SCHEMA_VERSION = "1"


class SerializationError(SpecificationError):
    code = "SPECIFICATION_SERIALIZATION_ERROR"


class UnsupportedSerializationSchemaVersionError(SerializationError):
    """Raised when a document's `serialization_schema_version` is not one
    this build knows how to decode. Never silently decoded on a best-effort
    basis (PID-004A persistence directive item 15: "REJECT unknown ...
    schema versions explicitly")."""

    code = "SPECIFICATION_UNSUPPORTED_SERIALIZATION_SCHEMA_VERSION"


class UnknownSerializationNodeError(SerializationError):
    """Raised when a `__type__` discriminator (or a scalar node shape) does
    not belong to this module's closed, explicit dispatch tables. Never a
    silent "treat as an inert leaf"."""

    code = "SPECIFICATION_UNKNOWN_SERIALIZATION_NODE"


# --- scalars: exact Decimal/datetime preservation ---------------------------


def _enc_decimal(value: Decimal) -> dict:
    return {"__decimal__": str(value)}


def _is_decimal_node(node: object) -> bool:
    return isinstance(node, dict) and set(node) == {"__decimal__"}


def _dec_decimal(node: dict) -> Decimal:
    return Decimal(node["__decimal__"])


def _enc_datetime(value: datetime) -> dict:
    return {"__datetime__": value.isoformat()}


def _is_datetime_node(node: object) -> bool:
    return isinstance(node, dict) and set(node) == {"__datetime__"}


def _dec_datetime(node: dict) -> datetime:
    return datetime.fromisoformat(node["__datetime__"])


def _enc_scalar(value: object) -> object:
    """Literal.value / ParameterDefinition.fixed_value / a derived fact's
    parameter value -- the closed `Decimal | int | bool | str` union used
    throughout this contract (PID-004A hardening item 1's closed operand
    typing). `bool` is checked before `int` since `bool` is an `int`
    subclass in Python and must never be silently widened."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return _enc_decimal(value)
    if isinstance(value, (bool, int, str)):
        return value
    raise SerializationError(f"Cannot serialize scalar value {value!r} of type {type(value)!r}")


def _dec_scalar(node: object) -> object:
    if node is None:
        return None
    if _is_decimal_node(node):
        return _dec_decimal(node)
    if isinstance(node, (bool, int, str)):
        return node
    raise UnknownSerializationNodeError(f"Unrecognised scalar node {node!r}")


def _require_type(node: object, name: str) -> dict:
    if not isinstance(node, dict) or node.get("__type__") != name:
        raise UnknownSerializationNodeError(f"Expected a {name!r} node, got {node!r}")
    return node


def _dec_optional_enum(enum_cls: type, value: object) -> object | None:
    return enum_cls(value) if value is not None else None


# --- expression tree (darwin.specification.expressions / .facts) ------------

_EXPR_LEAF_TYPES = (
    Literal,
    ParameterReference,
    UndefinedMeasurementBasis,
    CanonicalFactReference,
    SpecificationDerivedFact,
)


def _enc_expr(node: object) -> dict:
    if isinstance(node, Literal):
        return {"__type__": "Literal", "value": _enc_scalar(node.value), "unit": node.unit}
    if isinstance(node, ParameterReference):
        return {"__type__": "ParameterReference", "parameter_id": node.parameter_id}
    if isinstance(node, UndefinedMeasurementBasis):
        return {"__type__": "UndefinedMeasurementBasis", "note": node.note}
    if isinstance(node, CanonicalFactReference):
        return _enc_canonical_fact(node)
    if isinstance(node, SpecificationDerivedFact):
        return _enc_derived_fact(node)
    if isinstance(node, Comparison):
        return {
            "__type__": "Comparison",
            "operator": node.operator.value,
            "left": _enc_expr(node.left),
            "right": _enc_expr(node.right),
        }
    if isinstance(node, BooleanExpression):
        return {
            "__type__": "BooleanExpression",
            "operator": node.operator.value,
            "operands": [_enc_expr(o) for o in node.operands],
        }
    if isinstance(node, TemporalPredicate):
        return {
            "__type__": "TemporalPredicate",
            "operator": node.operator.value,
            "reference": node.reference,
            "n_bars": node.n_bars,
        }
    if isinstance(node, SessionPredicate):
        return {"__type__": "SessionPredicate", "operator": node.operator.value, "days": list(node.days)}
    if isinstance(node, EventPredicate):
        return {"__type__": "EventPredicate", "fact_requirement_id": node.fact_requirement_id}
    raise SerializationError(f"Cannot serialize expression node of type {type(node)!r}")


def _dec_expr(node: object) -> object:
    if not isinstance(node, dict) or "__type__" not in node:
        raise UnknownSerializationNodeError(f"Expected a tagged expression node, got {node!r}")
    node_type = node["__type__"]
    if node_type == "Literal":
        return Literal(value=_dec_scalar(node["value"]), unit=node.get("unit"))
    if node_type == "ParameterReference":
        return ParameterReference(parameter_id=node["parameter_id"])
    if node_type == "UndefinedMeasurementBasis":
        return UndefinedMeasurementBasis(note=node["note"])
    if node_type == "CanonicalFactReference":
        return _dec_canonical_fact(node)
    if node_type == "SpecificationDerivedFact":
        return _dec_derived_fact(node)
    if node_type == "Comparison":
        return Comparison(
            operator=comparison_operator_from_raw(node["operator"]),
            left=_dec_expr(node["left"]),
            right=_dec_expr(node["right"]),
        )
    if node_type == "BooleanExpression":
        return BooleanExpression(
            operator=boolean_operator_from_raw(node["operator"]),
            operands=tuple(_dec_expr(o) for o in node["operands"]),
        )
    if node_type == "TemporalPredicate":
        return TemporalPredicate(
            operator=temporal_operator_from_raw(node["operator"]),
            reference=node["reference"],
            n_bars=node.get("n_bars"),
        )
    if node_type == "SessionPredicate":
        return SessionPredicate(
            operator=session_operator_from_raw(node["operator"]),
            days=tuple(node.get("days", ())),
        )
    if node_type == "EventPredicate":
        return EventPredicate(fact_requirement_id=node["fact_requirement_id"])
    raise UnknownSerializationNodeError(
        f"Unknown expression node type {node_type!r} -- refusing rather than guessing"
    )


def _enc_canonical_fact(fact: CanonicalFactReference) -> dict:
    return {
        "__type__": "CanonicalFactReference",
        "fact_key": fact.fact_key,
        "fact_class": fact.fact_class.value,
        "authority_class": fact.authority_class.value,
        "unit": fact.unit,
        "timeframe": fact.timeframe.code,
        "requirement_id": fact.requirement_id,
    }


def _dec_canonical_fact(node: dict) -> CanonicalFactReference:
    return CanonicalFactReference(
        fact_key=node["fact_key"],
        fact_class=FactClass(node["fact_class"]),
        authority_class=DataAuthorityClass(node["authority_class"]),
        unit=node["unit"],
        timeframe=Timeframe(node["timeframe"]),
        requirement_id=node["requirement_id"],
    )


def _enc_derived_fact(fact: SpecificationDerivedFact) -> dict:
    return {
        "__type__": "SpecificationDerivedFact",
        "derived_fact_id": fact.derived_fact_id,
        "input_facts": [_enc_expr(i) for i in fact.input_facts],
        "algorithm_id": fact.algorithm_id,
        "algorithm_version": fact.algorithm_version,
        "parameters": [[key, _enc_scalar(value)] for key, value in fact.parameters],
        "timeframe": fact.timeframe.code,
        "warm_up_bars": fact.warm_up_bars,
        "output_unit": fact.output_unit,
        "missing_input_behavior": fact.missing_input_behavior.value,
    }


def _dec_derived_fact(node: dict) -> SpecificationDerivedFact:
    input_facts = tuple(_dec_expr(i) for i in node["input_facts"])
    for input_fact in input_facts:
        if not isinstance(input_fact, (CanonicalFactReference, SpecificationDerivedFact)):
            raise UnknownSerializationNodeError(
                "SpecificationDerivedFact.input_facts entry decoded to a non-governed fact reference"
            )
    return SpecificationDerivedFact(
        derived_fact_id=node["derived_fact_id"],
        input_facts=input_facts,
        algorithm_id=node["algorithm_id"],
        algorithm_version=node["algorithm_version"],
        parameters=tuple((key, _dec_scalar(value)) for key, value in node["parameters"]),
        timeframe=Timeframe(node["timeframe"]),
        warm_up_bars=node["warm_up_bars"],
        output_unit=node["output_unit"],
        missing_input_behavior=MissingInputBehavior(node["missing_input_behavior"]),
    )


# --- composition tree (darwin.specification.composition) --------------------


def _enc_atomic(condition: AtomicCondition) -> dict:
    return {
        "__type__": "AtomicCondition",
        "condition_id": condition.condition_id,
        "semantic_role": condition.semantic_role,
        "timeframe": condition.timeframe.code,
        "expression": _enc_expr(condition.expression),
        "direction": condition.direction.value,
    }


def _dec_atomic(node: dict) -> AtomicCondition:
    _require_type(node, "AtomicCondition")
    return AtomicCondition(
        condition_id=node["condition_id"],
        semantic_role=node["semantic_role"],
        timeframe=Timeframe(node["timeframe"]),
        expression=_dec_expr(node["expression"]),
        direction=Direction(node["direction"]),
    )


def _enc_expiry(expiry: ExpirySpec) -> dict:
    return {
        "__type__": "ExpirySpec",
        "mode": expiry.mode.value,
        "frame_count": expiry.frame_count,
        "finest_bound_timeframe": expiry.finest_bound_timeframe.code if expiry.finest_bound_timeframe else None,
        "duration_seconds": expiry.duration_seconds,
    }


def _dec_expiry(node: dict) -> ExpirySpec:
    _require_type(node, "ExpirySpec")
    finest_bound = node.get("finest_bound_timeframe")
    return ExpirySpec(
        mode=ExpiryMode(node["mode"]),
        frame_count=node.get("frame_count"),
        finest_bound_timeframe=Timeframe(finest_bound) if finest_bound else None,
        duration_seconds=node.get("duration_seconds"),
    )


def _enc_direction_relationship(value: ComponentDirectionRelationship | None) -> str | None:
    return value.value if value is not None else None


def _enc_composition(root: CompositionRoot) -> dict:
    if isinstance(root, AtomicCondition):
        return _enc_atomic(root)
    if isinstance(root, AllComposition):
        return {
            "__type__": "AllComposition",
            "composition_id": root.composition_id,
            "components": [_enc_atomic(c) for c in root.components],
            "direction_relationship": _enc_direction_relationship(root.direction_relationship),
        }
    if isinstance(root, AnyComposition):
        return {
            "__type__": "AnyComposition",
            "composition_id": root.composition_id,
            "components": [_enc_atomic(c) for c in root.components],
            "direction_relationship": _enc_direction_relationship(root.direction_relationship),
        }
    if isinstance(root, SequenceComposition):
        return {
            "__type__": "SequenceComposition",
            "composition_id": root.composition_id,
            "components": [
                {"sequence_index": c.sequence_index, "component": _enc_atomic(c.component)}
                for c in root.components
            ],
            "ordering_window_seconds": root.ordering_window_seconds,
            "tie_semantics": root.tie_semantics.value,
            "direction_relationship": _enc_direction_relationship(root.direction_relationship),
        }
    if isinstance(root, ContextTriggerComposition):
        return {
            "__type__": "ContextTriggerComposition",
            "composition_id": root.composition_id,
            "context": _enc_atomic(root.context),
            "trigger": _enc_atomic(root.trigger),
            "context_validity": _enc_expiry(root.context_validity),
            "direction_relationship": _enc_direction_relationship(root.direction_relationship),
        }
    raise SerializationError(f"Cannot serialize composition root of type {type(root)!r}")


def _dec_composition(node: object) -> CompositionRoot:
    if not isinstance(node, dict) or "__type__" not in node:
        raise UnknownSerializationNodeError(f"Expected a tagged composition node, got {node!r}")
    node_type = node["__type__"]
    if node_type == "AtomicCondition":
        return _dec_atomic(node)
    direction_relationship = _dec_optional_enum(
        ComponentDirectionRelationship, node.get("direction_relationship")
    )
    if node_type == "AllComposition":
        return AllComposition(
            composition_id=node["composition_id"],
            components=tuple(_dec_atomic(c) for c in node["components"]),
            direction_relationship=direction_relationship,
        )
    if node_type == "AnyComposition":
        return AnyComposition(
            composition_id=node["composition_id"],
            components=tuple(_dec_atomic(c) for c in node["components"]),
            direction_relationship=direction_relationship,
        )
    if node_type == "SequenceComposition":
        return SequenceComposition(
            composition_id=node["composition_id"],
            components=tuple(
                SequenceComponent(sequence_index=c["sequence_index"], component=_dec_atomic(c["component"]))
                for c in node["components"]
            ),
            ordering_window_seconds=node["ordering_window_seconds"],
            tie_semantics=SequenceTieSemantics(node["tie_semantics"]),
            direction_relationship=direction_relationship,
        )
    if node_type == "ContextTriggerComposition":
        return ContextTriggerComposition(
            composition_id=node["composition_id"],
            context=_dec_atomic(node["context"]),
            trigger=_dec_atomic(node["trigger"]),
            context_validity=_dec_expiry(node["context_validity"]),
            direction_relationship=direction_relationship,
        )
    raise UnknownSerializationNodeError(
        f"Unknown composition node type {node_type!r} -- refusing rather than guessing"
    )


# --- parameters / policy (darwin.specification.parameters / .policy) --------


def _enc_domain(domain: object | None) -> dict | None:
    if domain is None:
        return None
    if isinstance(domain, NumericRangeDomain):
        return {
            "__type__": "NumericRangeDomain",
            "minimum": _enc_scalar(domain.minimum),
            "maximum": _enc_scalar(domain.maximum),
            "step": _enc_scalar(domain.step) if domain.step is not None else None,
        }
    if isinstance(domain, IntegerRangeDomain):
        return {
            "__type__": "IntegerRangeDomain",
            "minimum": domain.minimum,
            "maximum": domain.maximum,
            "step": domain.step,
        }
    if isinstance(domain, DiscreteEnumerationDomain):
        return {"__type__": "DiscreteEnumerationDomain", "allowed_values": list(domain.allowed_values)}
    if isinstance(domain, BooleanEnumerationDomain):
        return {"__type__": "BooleanEnumerationDomain", "allowed_values": list(domain.allowed_values)}
    if isinstance(domain, DurationRangeDomain):
        return {
            "__type__": "DurationRangeDomain",
            "minimum_seconds": domain.minimum_seconds,
            "maximum_seconds": domain.maximum_seconds,
            "step_seconds": domain.step_seconds,
        }
    if isinstance(domain, UnitBearingRangeDomain):
        return {
            "__type__": "UnitBearingRangeDomain",
            "minimum": _enc_scalar(domain.minimum),
            "maximum": _enc_scalar(domain.maximum),
            "unit": domain.unit,
        }
    raise SerializationError(f"Cannot serialize parameter domain of type {type(domain)!r}")


def _dec_domain(node: dict | None) -> object | None:
    if node is None:
        return None
    node_type = node.get("__type__")
    if node_type == "NumericRangeDomain":
        return NumericRangeDomain(
            minimum=_dec_scalar(node["minimum"]),
            maximum=_dec_scalar(node["maximum"]),
            step=_dec_scalar(node["step"]) if node.get("step") is not None else None,
        )
    if node_type == "IntegerRangeDomain":
        return IntegerRangeDomain(minimum=node["minimum"], maximum=node["maximum"], step=node["step"])
    if node_type == "DiscreteEnumerationDomain":
        return DiscreteEnumerationDomain(allowed_values=tuple(node["allowed_values"]))
    if node_type == "BooleanEnumerationDomain":
        return BooleanEnumerationDomain(allowed_values=tuple(node["allowed_values"]))
    if node_type == "DurationRangeDomain":
        return DurationRangeDomain(
            minimum_seconds=node["minimum_seconds"],
            maximum_seconds=node["maximum_seconds"],
            step_seconds=node.get("step_seconds"),
        )
    if node_type == "UnitBearingRangeDomain":
        return UnitBearingRangeDomain(
            minimum=_dec_scalar(node["minimum"]), maximum=_dec_scalar(node["maximum"]), unit=node["unit"]
        )
    raise UnknownSerializationNodeError(
        f"Unknown parameter domain type {node_type!r} -- refusing rather than guessing"
    )


def _enc_parameter(parameter: ParameterDefinition) -> dict:
    return {
        "__type__": "ParameterDefinition",
        "parameter_id": parameter.parameter_id,
        "status": parameter.status.value,
        "value_type": parameter.value_type.value,
        "unit": parameter.unit,
        "fixed_value": _enc_scalar(parameter.fixed_value),
        "domain": _enc_domain(parameter.domain),
    }


def _dec_parameter(node: dict) -> ParameterDefinition:
    _require_type(node, "ParameterDefinition")
    return ParameterDefinition(
        parameter_id=node["parameter_id"],
        status=ParameterStatus(node["status"]),
        value_type=ParameterValueType(node["value_type"]),
        unit=node.get("unit"),
        fixed_value=_dec_scalar(node.get("fixed_value")),
        domain=_dec_domain(node.get("domain")),
    )


def _enc_policy_search_authority(authority: PolicySearchAuthority) -> dict:
    return {
        "__type__": "PolicySearchAuthority",
        "dimension": authority.dimension,
        "parameter": _enc_parameter(authority.parameter),
    }


def _dec_policy_search_authority(node: dict) -> PolicySearchAuthority:
    _require_type(node, "PolicySearchAuthority")
    return PolicySearchAuthority(dimension=node["dimension"], parameter=_dec_parameter(node["parameter"]))


def _enc_policy_declaration(declaration: PolicyCompatibilityDeclaration) -> dict:
    return {
        "__type__": "PolicyCompatibilityDeclaration",
        "policy_class": declaration.policy_class.value,
        "compatibility": declaration.compatibility.value,
        "authorized_search_envelope": [
            _enc_policy_search_authority(a) for a in declaration.authorized_search_envelope
        ],
        "notes": declaration.notes,
    }


def _dec_policy_declaration(node: dict) -> PolicyCompatibilityDeclaration:
    _require_type(node, "PolicyCompatibilityDeclaration")
    return PolicyCompatibilityDeclaration(
        policy_class=PolicyClass(node["policy_class"]),
        compatibility=PolicyCompatibility(node["compatibility"]),
        authorized_search_envelope=tuple(
            _dec_policy_search_authority(a) for a in node.get("authorized_search_envelope", ())
        ),
        notes=node.get("notes"),
    )


# --- data requirements (darwin.specification.data_requirements) -------------


def _enc_depth(depth: HistoricalDepthRequirement) -> dict:
    return {"__type__": "HistoricalDepthRequirement", "count": depth.count, "unit": depth.unit.value}


def _dec_depth(node: dict) -> HistoricalDepthRequirement:
    _require_type(node, "HistoricalDepthRequirement")
    return HistoricalDepthRequirement(count=node["count"], unit=HistoricalDepthUnit(node["unit"]))


def _enc_requirement(requirement: DataRequirement) -> dict:
    return {
        "__type__": "DataRequirement",
        "requirement_id": requirement.requirement_id,
        "display_name": requirement.display_name,
        "fact_class": requirement.fact_class.value,
        "fact_reference_kind": requirement.fact_reference_kind.value,
        "authority_class": requirement.authority_class.value,
        "instrument_applicability": list(requirement.instrument_applicability),
        "timeframe": requirement.timeframe.code if requirement.timeframe else None,
        "required_historical_depth": _enc_depth(requirement.required_historical_depth),
        "units": requirement.units,
        "required_fields": list(requirement.required_fields),
        "causal_timing_policy": requirement.causal_timing_policy.value,
        "mandatory": requirement.mandatory,
    }


def _dec_requirement(node: dict) -> DataRequirement:
    _require_type(node, "DataRequirement")
    timeframe = node.get("timeframe")
    return DataRequirement(
        requirement_id=node["requirement_id"],
        display_name=node["display_name"],
        fact_class=FactClass(node["fact_class"]),
        fact_reference_kind=FactReferenceKind(node["fact_reference_kind"]),
        authority_class=DataAuthorityClass(node["authority_class"]),
        instrument_applicability=tuple(node["instrument_applicability"]),
        timeframe=Timeframe(timeframe) if timeframe else None,
        required_historical_depth=_dec_depth(node["required_historical_depth"]),
        units=node.get("units"),
        required_fields=tuple(node["required_fields"]),
        causal_timing_policy=CausalTimingPolicy(node["causal_timing_policy"]),
        mandatory=node["mandatory"],
    )


# --- applicability / session (darwin.specification.applicability) ----------


def _enc_applicability(applicability: InstrumentApplicability) -> dict:
    return {
        "__type__": "InstrumentApplicability",
        "kind": applicability.kind.value,
        "instrument_ids": list(applicability.instrument_ids),
        "generic_criteria": list(applicability.generic_criteria),
    }


def _dec_applicability(node: dict) -> InstrumentApplicability:
    _require_type(node, "InstrumentApplicability")
    return InstrumentApplicability(
        kind=InstrumentApplicabilityKind(node["kind"]),
        instrument_ids=tuple(node.get("instrument_ids", ())),
        generic_criteria=tuple(node.get("generic_criteria", ())),
    )


def _enc_session(session: SessionSpec | None) -> dict | None:
    if session is None:
        return None
    return {
        "__type__": "SessionSpec",
        "iana_timezone": session.iana_timezone,
        "local_start": session.local_start,
        "local_end": session.local_end,
        "weekdays": list(session.weekdays),
        "dst_handling": session.dst_handling.value,
        "cross_midnight": session.cross_midnight,
    }


def _dec_session(node: dict | None) -> SessionSpec | None:
    if node is None:
        return None
    _require_type(node, "SessionSpec")
    return SessionSpec(
        iana_timezone=node["iana_timezone"],
        local_start=node["local_start"],
        local_end=node["local_end"],
        weekdays=tuple(node["weekdays"]),
        dst_handling=DstHandling(node["dst_handling"]),
        cross_midnight=node["cross_midnight"],
    )


# --- provenance (darwin.specification.provenance) ---------------------------


def _enc_provenance(record: ProvenanceRecord) -> dict:
    return {
        "__type__": "ProvenanceRecord",
        "provenance_id": record.provenance_id,
        "subject_ref": record.subject_ref,
        "origin": record.origin.value,
        "acceptance_state": record.acceptance_state.value,
        "material_decision_ref": record.material_decision_ref,
        "notes": record.notes,
        "recorded_at_utc": _enc_datetime(record.recorded_at_utc) if record.recorded_at_utc else None,
    }


def _dec_provenance(node: dict) -> ProvenanceRecord:
    _require_type(node, "ProvenanceRecord")
    recorded_at = node.get("recorded_at_utc")
    return ProvenanceRecord(
        provenance_id=node["provenance_id"],
        subject_ref=node["subject_ref"],
        origin=RuleOrigin(node["origin"]),
        acceptance_state=RuleAcceptanceState(node["acceptance_state"]),
        material_decision_ref=node.get("material_decision_ref"),
        notes=node.get("notes"),
        recorded_at_utc=_dec_datetime(recorded_at) if recorded_at else None,
    )


def _check_schema_version(doc: dict) -> None:
    version = doc.get("serialization_schema_version")
    if version != SERIALIZATION_SCHEMA_VERSION:
        raise UnsupportedSerializationSchemaVersionError(
            f"Unsupported serialization_schema_version {version!r}; this build only supports "
            f"{SERIALIZATION_SCHEMA_VERSION!r} -- refusing to guess how to decode an unknown "
            f"schema version"
        )


# --- top level: StrategyVersion ----------------------------------------------


def serialize_strategy_version(version: StrategyVersion) -> dict:
    """The complete, lossless, JSON-safe document for one immutable
    `StrategyVersion` -- both `semantic_payload()` and `artifact_payload()`
    are recoverable from this single document by rehydrating it
    (`deserialize_strategy_version`) and calling those methods again on the
    rehydrated object."""
    return {
        "serialization_schema_version": SERIALIZATION_SCHEMA_VERSION,
        "__type__": "StrategyVersion",
        "strategy_version_id": version.strategy_version_id,
        "candidate_id": version.candidate_id,
        "schema_semantic_version": version.schema_semantic_version,
        "title": version.title,
        "thesis": version.thesis,
        "instrument_applicability": _enc_applicability(version.instrument_applicability),
        "composition": _enc_composition(version.composition),
        "fixed_parameters": [_enc_parameter(p) for p in version.fixed_parameters],
        "tunable_parameters": [_enc_parameter(p) for p in version.tunable_parameters],
        "policy_declarations": [_enc_policy_declaration(d) for d in version.policy_declarations],
        "data_requirements": [_enc_requirement(r) for r in version.data_requirements],
        "session_spec": _enc_session(version.session_spec),
        "intrabar_ambiguity_policy": version.intrabar_ambiguity_policy.value,
        "setup_expiry": _enc_expiry(version.setup_expiry),
        "exit_rules": [_enc_atomic(e) for e in version.exit_rules],
        "provenance": [_enc_provenance(p) for p in version.provenance],
        "finalised_at_utc": _enc_datetime(version.finalised_at_utc),
        "semantic_fingerprint": version.semantic_fingerprint,
        "artifact_record_fingerprint": version.artifact_record_fingerprint,
    }


def deserialize_strategy_version(doc: dict) -> StrategyVersion:
    _check_schema_version(doc)
    if not isinstance(doc, dict) or doc.get("__type__") != "StrategyVersion":
        raise UnknownSerializationNodeError(
            f"Expected a StrategyVersion document, got __type__={doc.get('__type__') if isinstance(doc, dict) else doc!r}"
        )
    return StrategyVersion(
        strategy_version_id=doc["strategy_version_id"],
        candidate_id=doc["candidate_id"],
        schema_semantic_version=doc["schema_semantic_version"],
        title=doc["title"],
        thesis=doc["thesis"],
        instrument_applicability=_dec_applicability(doc["instrument_applicability"]),
        composition=_dec_composition(doc["composition"]),
        fixed_parameters=tuple(_dec_parameter(p) for p in doc["fixed_parameters"]),
        tunable_parameters=tuple(_dec_parameter(p) for p in doc["tunable_parameters"]),
        policy_declarations=tuple(_dec_policy_declaration(d) for d in doc["policy_declarations"]),
        data_requirements=tuple(_dec_requirement(r) for r in doc["data_requirements"]),
        session_spec=_dec_session(doc.get("session_spec")),
        intrabar_ambiguity_policy=IntrabarAmbiguityPolicy(doc["intrabar_ambiguity_policy"]),
        setup_expiry=_dec_expiry(doc["setup_expiry"]),
        exit_rules=tuple(_dec_atomic(e) for e in doc["exit_rules"]),
        provenance=tuple(_dec_provenance(p) for p in doc["provenance"]),
        finalised_at_utc=_dec_datetime(doc["finalised_at_utc"]),
        semantic_fingerprint=doc["semantic_fingerprint"],
        artifact_record_fingerprint=doc["artifact_record_fingerprint"],
    )


# --- top level: SpecificationDraft -------------------------------------------


def serialize_specification_draft(draft: SpecificationDraft) -> dict:
    """The complete, lossless, JSON-safe document for one MUTABLE
    `SpecificationDraft` (PID-004A persistence directive item 4) -- every
    dict-valued draft field round-trips back to a dict (never silently
    frozen into a tuple the way `finalise()` itself does when building a
    `StrategyVersion`)."""
    return {
        "serialization_schema_version": SERIALIZATION_SCHEMA_VERSION,
        "__type__": "SpecificationDraft",
        "draft_id": draft.draft_id,
        "candidate_id": draft.candidate_id,
        "schema_semantic_version": draft.schema_semantic_version,
        "title": draft.title,
        "thesis": draft.thesis,
        "instrument_applicability": (
            _enc_applicability(draft.instrument_applicability) if draft.instrument_applicability else None
        ),
        "composition": _enc_composition(draft.composition) if draft.composition is not None else None,
        "fixed_parameters": {k: _enc_parameter(v) for k, v in draft.fixed_parameters.items()},
        "tunable_parameters": {k: _enc_parameter(v) for k, v in draft.tunable_parameters.items()},
        "policy_declarations": [_enc_policy_declaration(v) for v in draft.policy_declarations.values()],
        "data_requirements": {k: _enc_requirement(v) for k, v in draft.data_requirements.items()},
        "session_spec": _enc_session(draft.session_spec),
        "intrabar_ambiguity_policy": (
            draft.intrabar_ambiguity_policy.value if draft.intrabar_ambiguity_policy else None
        ),
        "setup_expiry": _enc_expiry(draft.setup_expiry) if draft.setup_expiry is not None else None,
        "exit_rules": [_enc_atomic(e) for e in draft.exit_rules],
        "provenance": {k: _enc_provenance(v) for k, v in draft.provenance.items()},
        "created_at_utc": _enc_datetime(draft.created_at_utc) if draft.created_at_utc else None,
    }


def deserialize_specification_draft(doc: dict) -> SpecificationDraft:
    _check_schema_version(doc)
    if not isinstance(doc, dict) or doc.get("__type__") != "SpecificationDraft":
        raise UnknownSerializationNodeError(
            f"Expected a SpecificationDraft document, got __type__={doc.get('__type__') if isinstance(doc, dict) else doc!r}"
        )
    instrument_applicability = doc.get("instrument_applicability")
    composition = doc.get("composition")
    setup_expiry = doc.get("setup_expiry")
    created_at = doc.get("created_at_utc")
    draft = SpecificationDraft(
        draft_id=doc["draft_id"],
        candidate_id=doc["candidate_id"],
        schema_semantic_version=doc["schema_semantic_version"],
        title=doc.get("title", ""),
        thesis=doc.get("thesis", ""),
        instrument_applicability=_dec_applicability(instrument_applicability) if instrument_applicability else None,
        composition=_dec_composition(composition) if composition is not None else None,
        session_spec=_dec_session(doc.get("session_spec")),
        intrabar_ambiguity_policy=(
            IntrabarAmbiguityPolicy(doc["intrabar_ambiguity_policy"])
            if doc.get("intrabar_ambiguity_policy")
            else None
        ),
        setup_expiry=_dec_expiry(setup_expiry) if setup_expiry is not None else None,
        exit_rules=tuple(_dec_atomic(e) for e in doc.get("exit_rules", ())),
        created_at_utc=_dec_datetime(created_at) if created_at else None,
    )
    for parameter_id, node in doc.get("fixed_parameters", {}).items():
        draft.fixed_parameters[parameter_id] = _dec_parameter(node)
    for parameter_id, node in doc.get("tunable_parameters", {}).items():
        draft.tunable_parameters[parameter_id] = _dec_parameter(node)
    for node in doc.get("policy_declarations", []):
        declaration = _dec_policy_declaration(node)
        draft.policy_declarations[declaration.policy_class] = declaration
    for requirement_id, node in doc.get("data_requirements", {}).items():
        draft.data_requirements[requirement_id] = _dec_requirement(node)
    for subject_ref, node in doc.get("provenance", {}).items():
        draft.provenance[subject_ref] = _dec_provenance(node)
    return draft
