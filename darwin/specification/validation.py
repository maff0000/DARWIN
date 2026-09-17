"""Deterministic validation pipeline + finalisation gate (PID-004
sec32/sec33/sec34/sec42).

`validate_draft` never raises for a materially incomplete specification.
It always returns a `ValidationOutcome` -- `VALID` or
`STRATEGY_NOT_SUFFICIENTLY_DEFINED` -- because a refusal is a governed,
successful outcome (HSA doctrine, deliberately reused; see
`darwin.specification.errors` module docstring). `finalise` only raises
`FinalisationError` for genuine programmer mistakes; an incomplete draft
produces a `FinalisationResult` with `strategy_version=None` and the same
`STRATEGY_NOT_SUFFICIENTLY_DEFINED` outcome, never an exception.

Missing DATA (readiness) never appears anywhere in this module -- only
missing/incomplete SEMANTICS can produce a finding here (PID-004 sec32:
"Missing historical data must not cause a semantically complete
specification to be called ambiguous."). `finalise` succeeds even when the
strategy will turn out to be DATA_BLOCKED (PID-004 sec34) -- readiness is
assessed afterwards, separately, by `darwin.specification.readiness`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from darwin.specification.applicability import InstrumentApplicabilityKind
from darwin.specification.composition import (
    CompositionRoot,
    ContextTriggerComposition,
    ExpiryMode,
    all_leaf_conditions,
    finest_bound_timeframe_of,
)
from darwin.specification.data_requirements import CAUSALLY_SENSITIVE_FACT_CLASSES
from darwin.specification.domain import (
    SEMANTIC_FIELD_NAMES,
    SpecificationDraft,
    StrategyVersion,
)
from darwin.specification.errors import (
    FinalisationError,
    ParameterDomainViolationError,
    UnrecognisedExpressionNodeError,
)
from darwin.specification.expressions import (
    BooleanExpression,
    Comparison,
    EventPredicate,
    Literal,
    ParameterReference,
    SessionPredicate,
    TemporalPredicate,
    UndefinedMeasurementBasis,
)
from darwin.specification.facts import (
    CanonicalFactReference,
    FactReferenceKind,
    SpecificationDerivedFact,
    fact_key_semantic_field,
)
from darwin.specification.fingerprint import canonical_hash
from darwin.specification.parameters import ParameterStatus, validate_parameter_value


class ValidationOutcomeStatus(StrEnum):
    VALID = "VALID"
    STRATEGY_NOT_SUFFICIENTLY_DEFINED = "STRATEGY_NOT_SUFFICIENTLY_DEFINED"


@dataclass(frozen=True)
class ValidationFinding:
    stage: str
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class ValidationOutcome:
    status: ValidationOutcomeStatus
    findings: tuple[ValidationFinding, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationOutcomeStatus.VALID


_GOVERNED_LEAF_NODE_TYPES: tuple[type, ...] = (
    Literal,
    ParameterReference,
    CanonicalFactReference,
    TemporalPredicate,
    SessionPredicate,
    EventPredicate,
    UndefinedMeasurementBasis,
)


def _iter_expression_nodes(node: object):
    """Recursively walks an expression tree, yielding every node reached.
    PID-004A hardening item 1: this walk must never silently skip/ignore a
    node type it does not recognise -- every node is either a known
    recursive container (Comparison/BooleanExpression/
    SpecificationDerivedFact), a known governed leaf type, or an explicit
    `UnrecognisedExpressionNodeError`. There is no implicit "anything else
    is treated as an inert leaf" fallback. In practice every governed
    dataclass already rejects an ungoverned child at construction time
    (see expressions.py/facts.py/composition.py __post_init__ checks); this
    walk is defense-in-depth against a node that bypassed those checks
    (e.g. via `object.__setattr__` on a frozen dataclass)."""
    yield node
    if isinstance(node, Comparison):
        yield from _iter_expression_nodes(node.left)
        yield from _iter_expression_nodes(node.right)
    elif isinstance(node, BooleanExpression):
        for operand in node.operands:
            yield from _iter_expression_nodes(operand)
    elif isinstance(node, SpecificationDerivedFact):
        for input_fact in node.input_facts:
            yield from _iter_expression_nodes(input_fact)
    elif isinstance(node, _GOVERNED_LEAF_NODE_TYPES):
        pass  # governed leaf types -- nothing further to recurse into
    else:
        raise UnrecognisedExpressionNodeError(
            f"Expression tree walk encountered an unrecognised node {node!r} (type "
            f"{type(node)!r}) -- refusing explicitly rather than silently treating it as an "
            f"inert leaf (PID-004A hardening item 1)"
        )


def _validate_composition(
    root: CompositionRoot | None, *, findings: list[ValidationFinding]
) -> None:
    if root is None:
        findings.append(
            ValidationFinding(
                stage="composition",
                code="MISSING_COMPOSITION",
                message="A SpecificationDraft requires a composition (ATOMIC/ALL/ANY/SEQUENCE/CONTEXT_TRIGGER)",
            )
        )
        return

    leaves = all_leaf_conditions(root)
    for leaf in leaves:
        for node in _iter_expression_nodes(leaf.expression):
            if isinstance(node, UndefinedMeasurementBasis):
                findings.append(
                    ValidationFinding(
                        stage="ambiguity",
                        code="UNDEFINED_MEASUREMENT_BASIS",
                        message=f"{leaf.condition_id}: {node.note}",
                        path=leaf.condition_id,
                    )
                )

    if isinstance(root, ContextTriggerComposition) and root.context_validity.mode == ExpiryMode.FRAMES:
        actual_finest = finest_bound_timeframe_of((root.context, root.trigger))
        if root.context_validity.finest_bound_timeframe != actual_finest:
            findings.append(
                ValidationFinding(
                    stage="composition",
                    code="FRAMES_EXPIRY_TIMEFRAME_MISMATCH",
                    message=(
                        f"CONTEXT_TRIGGER {root.composition_id}: context_validity declares "
                        f"finest_bound_timeframe={root.context_validity.finest_bound_timeframe}, "
                        f"actual finest bound timeframe is {actual_finest}"
                    ),
                    path=root.composition_id,
                )
            )


def _validate_parameters(draft: SpecificationDraft, *, findings: list[ValidationFinding]) -> None:
    all_params = {**draft.fixed_parameters, **draft.tunable_parameters}
    for parameter_id, definition in all_params.items():
        if definition.status == ParameterStatus.FIXED:
            try:
                validate_parameter_value(definition, definition.fixed_value)
            except ParameterDomainViolationError as exc:  # pragma: no cover - defensive, ParameterDefinition already enforces this
                findings.append(
                    ValidationFinding(
                        stage="parameters", code="FIXED_PARAMETER_INVALID", message=str(exc), path=parameter_id
                    )
                )

    referenced: set[str] = set()
    if draft.composition is not None:
        for leaf in all_leaf_conditions(draft.composition):
            for node in _iter_expression_nodes(leaf.expression):
                if isinstance(node, ParameterReference):
                    referenced.add(node.parameter_id)
    for exit_rule in draft.exit_rules:
        for node in _iter_expression_nodes(exit_rule.expression):
            if isinstance(node, ParameterReference):
                referenced.add(node.parameter_id)

    missing = referenced - set(all_params.keys())
    for parameter_id in sorted(missing):
        findings.append(
            ValidationFinding(
                stage="parameters",
                code="UNDECLARED_PARAMETER_REFERENCE",
                message=f"ParameterReference to {parameter_id!r} has no matching declared parameter",
                path=parameter_id,
            )
        )


def _validate_data_requirements(draft: SpecificationDraft, *, findings: list[ValidationFinding]) -> None:
    referenced: set[str] = set()
    if draft.composition is not None:
        for leaf in all_leaf_conditions(draft.composition):
            for node in _iter_expression_nodes(leaf.expression):
                if isinstance(node, EventPredicate):
                    referenced.add(node.fact_requirement_id)
    for exit_rule in draft.exit_rules:
        for node in _iter_expression_nodes(exit_rule.expression):
            if isinstance(node, EventPredicate):
                referenced.add(node.fact_requirement_id)
    missing = referenced - set(draft.data_requirements.keys())
    for requirement_id in sorted(missing):
        findings.append(
            ValidationFinding(
                stage="data_requirements",
                code="UNDECLARED_DATA_REQUIREMENT_REFERENCE",
                message=f"EventPredicate references undeclared DataRequirement {requirement_id!r}",
                path=requirement_id,
            )
        )
    # PID-004A hardening item 5: an EventPredicate must reference an
    # appropriate governed event/context requirement -- not merely any
    # arbitrary requirement id that happens to be declared. Reuses the same
    # governed CAUSALLY_SENSITIVE_FACT_CLASSES vocabulary
    # darwin.specification.data_requirements already defines for exactly
    # this "is this an event/context fact class" question.
    for requirement_id in sorted(referenced - missing):
        requirement = draft.data_requirements[requirement_id]
        if requirement.fact_class not in CAUSALLY_SENSITIVE_FACT_CLASSES:
            findings.append(
                ValidationFinding(
                    stage="data_requirements",
                    code="EVENT_PREDICATE_REQUIREMENT_NOT_EVENT",
                    message=(
                        f"EventPredicate references DataRequirement {requirement_id!r} whose "
                        f"fact_class {requirement.fact_class.value!r} is not a governed "
                        f"event/context class "
                        f"({sorted(c.value for c in CAUSALLY_SENSITIVE_FACT_CLASSES)}) -- "
                        f"EventPredicate must never be pointed at plain market data or any other "
                        f"non-event requirement"
                    ),
                    path=requirement_id,
                )
            )


def _all_leaves(draft: SpecificationDraft) -> list:
    """Every AtomicCondition leaf reachable from `draft` -- composition
    leaves plus exit_rules -- as one flat list. Shared by the PID-004A
    hardening validators below to avoid re-deriving this same "leaves =
    composition leaves + exit_rules" shape four separate ways."""
    leaves = list(all_leaf_conditions(draft.composition)) if draft.composition is not None else []
    leaves.extend(draft.exit_rules)
    return leaves


def _validate_fact_requirement_coverage(draft: SpecificationDraft, *, findings: list[ValidationFinding]) -> None:
    """PID-004A hardening item 2/3: every canonical fact a strategy
    consumes -- via entry/composition rules, exit rules, or a derived-fact
    chain's transitive canonical leaves (the recursive `_iter_expression_nodes`
    walk below already descends into `SpecificationDerivedFact.input_facts`,
    so a derived fact's canonical inputs are found automatically, however
    deep the derivation chain) -- must be deterministically backed by a
    declared `DataRequirement`. A valid final StrategyVersion must never be
    constructible while consuming a canonical fact readiness doesn't know
    about.

    Each `CanonicalFactReference.requirement_id` names the DataRequirement
    it is drawn from; this validator cross-checks requirement identity,
    fact/reference kind, fact_class, authority_class, timeframe, units,
    the semantic field named by `fact_key`, and (where the draft's
    instrument_applicability is explicit) instrument applicability.
    """
    for leaf in _all_leaves(draft):
        for node in _iter_expression_nodes(leaf.expression):
            if not isinstance(node, CanonicalFactReference):
                continue
            requirement = draft.data_requirements.get(node.requirement_id)
            if requirement is None:
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="MISSING_DATA_REQUIREMENT_FOR_CANONICAL_FACT",
                        message=(
                            f"CanonicalFactReference {node.fact_key!r} (on {leaf.condition_id!r}) "
                            f"names requirement_id={node.requirement_id!r}, which has no matching "
                            f"declared DataRequirement on this draft"
                        ),
                        path=node.requirement_id,
                    )
                )
                continue
            if requirement.fact_reference_kind != FactReferenceKind.CANONICAL_FACT_REFERENCE:
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="DATA_REQUIREMENT_KIND_MISMATCH",
                        message=(
                            f"DataRequirement {node.requirement_id!r} declares "
                            f"fact_reference_kind={requirement.fact_reference_kind.value!r}, but "
                            f"{node.fact_key!r} is a CANONICAL_FACT_REFERENCE"
                        ),
                        path=node.requirement_id,
                    )
                )
            if requirement.fact_class != node.fact_class:
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="DATA_REQUIREMENT_FACT_CLASS_MISMATCH",
                        message=(
                            f"DataRequirement {node.requirement_id!r} fact_class="
                            f"{requirement.fact_class.value!r} does not match CanonicalFactReference "
                            f"{node.fact_key!r} fact_class={node.fact_class.value!r}"
                        ),
                        path=node.requirement_id,
                    )
                )
            if requirement.authority_class != node.authority_class:
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="DATA_REQUIREMENT_AUTHORITY_CLASS_MISMATCH",
                        message=(
                            f"DataRequirement {node.requirement_id!r} authority_class="
                            f"{requirement.authority_class.value!r} does not match "
                            f"CanonicalFactReference {node.fact_key!r} authority_class="
                            f"{node.authority_class.value!r}"
                        ),
                        path=node.requirement_id,
                    )
                )
            if requirement.timeframe is not None and requirement.timeframe != node.timeframe:
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="DATA_REQUIREMENT_TIMEFRAME_MISMATCH",
                        message=(
                            f"DataRequirement {node.requirement_id!r} timeframe="
                            f"{requirement.timeframe.code!r} does not match CanonicalFactReference "
                            f"{node.fact_key!r} timeframe={node.timeframe.code!r}"
                        ),
                        path=node.requirement_id,
                    )
                )
            if requirement.units is not None and requirement.units != node.unit:
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="DATA_REQUIREMENT_UNIT_MISMATCH",
                        message=(
                            f"DataRequirement {node.requirement_id!r} units={requirement.units!r} "
                            f"does not match CanonicalFactReference {node.fact_key!r} unit="
                            f"{node.unit!r}"
                        ),
                        path=node.requirement_id,
                    )
                )
            field_name = fact_key_semantic_field(node.fact_key)
            if field_name.upper() not in {f.upper() for f in requirement.required_fields}:
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="DATA_REQUIREMENT_FIELD_MISMATCH",
                        message=(
                            f"CanonicalFactReference {node.fact_key!r} names semantic field "
                            f"{field_name!r}, which is not in DataRequirement "
                            f"{node.requirement_id!r}.required_fields={requirement.required_fields!r}"
                        ),
                        path=node.requirement_id,
                    )
                )
            instrument_applicability = draft.instrument_applicability
            if (
                instrument_applicability is not None
                and instrument_applicability.kind
                in (InstrumentApplicabilityKind.EXPLICIT_SINGLE, InstrumentApplicabilityKind.EXPLICIT_SET)
                and requirement.instrument_applicability
                and not set(instrument_applicability.instrument_ids).issubset(
                    set(requirement.instrument_applicability)
                )
            ):
                findings.append(
                    ValidationFinding(
                        stage="data_requirements",
                        code="DATA_REQUIREMENT_INSTRUMENT_MISMATCH",
                        message=(
                            f"DataRequirement {node.requirement_id!r} instrument_applicability="
                            f"{requirement.instrument_applicability!r} does not cover the draft's "
                            f"own instrument_applicability.instrument_ids="
                            f"{instrument_applicability.instrument_ids!r}"
                        ),
                        path=node.requirement_id,
                    )
                )


def _validate_session_predicates(draft: SpecificationDraft, *, findings: list[ValidationFinding]) -> None:
    """PID-004A hardening item 5: a strategy must not finalise with an
    IN_SESSION/ON_DAY-style SessionPredicate but no declared, compatible
    SessionSpec on the draft."""
    uses_session = any(
        isinstance(node, SessionPredicate)
        for leaf in _all_leaves(draft)
        for node in _iter_expression_nodes(leaf.expression)
    )
    if uses_session and draft.session_spec is None:
        findings.append(
            ValidationFinding(
                stage="applicability",
                code="MISSING_SESSION_SPEC",
                message=(
                    "A SessionPredicate is used in composition/exit rules, but no SessionSpec is "
                    "declared on the draft"
                ),
            )
        )


def _validate_temporal_predicate_references(draft: SpecificationDraft, *, findings: list[ValidationFinding]) -> None:
    """PID-004A hardening item 5: whatever condition/event a
    TemporalPredicate references must resolve to an existing governed
    semantic reference within the same specification -- either another
    AtomicCondition.condition_id (composition leaf or exit rule) or a
    declared DataRequirement.requirement_id (for an external-event
    reference). No arbitrary dangling string reference may finalise."""
    leaves = _all_leaves(draft)
    valid_references = {leaf.condition_id for leaf in leaves} | set(draft.data_requirements.keys())
    for leaf in leaves:
        for node in _iter_expression_nodes(leaf.expression):
            if isinstance(node, TemporalPredicate) and node.reference not in valid_references:
                findings.append(
                    ValidationFinding(
                        stage="composition",
                        code="DANGLING_TEMPORAL_PREDICATE_REFERENCE",
                        message=(
                            f"TemporalPredicate.reference {node.reference!r} (on "
                            f"{leaf.condition_id!r}) does not resolve to any declared "
                            f"AtomicCondition.condition_id or DataRequirement.requirement_id on "
                            f"this draft"
                        ),
                        path=leaf.condition_id,
                    )
                )


def _validate_atomic_condition_timeframe_consistency(
    draft: SpecificationDraft, *, findings: list[ValidationFinding]
) -> None:
    """PID-004A hardening item 5: the fact/timeframe semantics an
    AtomicCondition consumes must be consistent with that condition's own
    explicit (semantic_role, timeframe) binding. An H1-bound condition must
    never silently reference an H4 fact -- that kind of multi-timeframe
    relationship belongs to explicit composition (CONTEXT_TRIGGER), never
    smuggled through a single atomic condition's own expression tree. This
    check is per-leaf and applies uniformly whether the leaf is a bare
    ATOMIC composition, an ALL/ANY/SEQUENCE component, or a CONTEXT_TRIGGER
    context/trigger leg -- CONTEXT_TRIGGER's own cross-timeframe allowance
    is a relationship BETWEEN two AtomicCondition legs (already validated
    at construction time in composition.py), never a licence for a single
    leaf's own facts to disagree with its own declared timeframe.
    """
    for leaf in _all_leaves(draft):
        for node in _iter_expression_nodes(leaf.expression):
            if isinstance(node, (CanonicalFactReference, SpecificationDerivedFact)) and node.timeframe != leaf.timeframe:
                findings.append(
                    ValidationFinding(
                        stage="composition",
                        code="ATOMIC_CONDITION_TIMEFRAME_MISMATCH",
                        message=(
                            f"AtomicCondition {leaf.condition_id!r} is bound to timeframe "
                            f"{leaf.timeframe.code!r} but its expression references a fact at "
                            f"timeframe {node.timeframe.code!r} with no declared cross-timeframe "
                            f"composition relationship (use CONTEXT_TRIGGER for that)"
                        ),
                        path=leaf.condition_id,
                    )
                )


def _validate_top_level_completeness(draft: SpecificationDraft, *, findings: list[ValidationFinding]) -> None:
    if draft.instrument_applicability is None:
        findings.append(
            ValidationFinding(
                stage="schema", code="MISSING_INSTRUMENT_APPLICABILITY", message="instrument_applicability is required"
            )
        )
    if draft.intrabar_ambiguity_policy is None:
        findings.append(
            ValidationFinding(
                stage="schema",
                code="MISSING_INTRABAR_AMBIGUITY_POLICY",
                message="intrabar_ambiguity_policy is required (use NOT_APPLICABLE if genuinely irrelevant)",
            )
        )
    if draft.setup_expiry is None:
        findings.append(
            ValidationFinding(
                stage="schema",
                code="MISSING_SETUP_EXPIRY",
                message="setup_expiry is required (use ExpiryMode.NOT_APPLICABLE if genuinely irrelevant)",
            )
        )


def _validate_provenance(draft: SpecificationDraft, *, findings: list[ValidationFinding]) -> None:
    from darwin.specification.provenance import RuleAcceptanceState

    leaves = list(all_leaf_conditions(draft.composition)) if draft.composition is not None else []
    leaves.extend(draft.exit_rules)
    for leaf in leaves:
        record = draft.provenance.get(leaf.condition_id)
        if record is None:
            findings.append(
                ValidationFinding(
                    stage="provenance",
                    code="MISSING_PROVENANCE",
                    message=f"AtomicCondition {leaf.condition_id!r} has no ProvenanceRecord",
                    path=leaf.condition_id,
                )
            )
        elif record.acceptance_state not in (
            RuleAcceptanceState.ACCEPTED_SPECIFICATION_RULE,
        ):
            findings.append(
                ValidationFinding(
                    stage="provenance",
                    code="RULE_NOT_ACCEPTED",
                    message=(
                        f"AtomicCondition {leaf.condition_id!r} provenance is "
                        f"{record.acceptance_state.value}, not ACCEPTED_SPECIFICATION_RULE"
                    ),
                    path=leaf.condition_id,
                )
            )


def validate_draft(draft: SpecificationDraft) -> ValidationOutcome:
    """Runs the deterministic validation pipeline (PID-004 sec32) against
    `draft`. Never mutates `draft`. Never raises for material
    incompleteness -- always returns a governed `ValidationOutcome`."""
    findings: list[ValidationFinding] = []
    _validate_top_level_completeness(draft, findings=findings)
    _validate_composition(draft.composition, findings=findings)
    _validate_parameters(draft, findings=findings)
    _validate_data_requirements(draft, findings=findings)
    _validate_fact_requirement_coverage(draft, findings=findings)
    _validate_session_predicates(draft, findings=findings)
    _validate_temporal_predicate_references(draft, findings=findings)
    _validate_atomic_condition_timeframe_consistency(draft, findings=findings)
    _validate_provenance(draft, findings=findings)

    if findings:
        return ValidationOutcome(
            status=ValidationOutcomeStatus.STRATEGY_NOT_SUFFICIENTLY_DEFINED, findings=tuple(findings)
        )
    return ValidationOutcome(status=ValidationOutcomeStatus.VALID)


@dataclass(frozen=True)
class FinalisationResult:
    outcome: ValidationOutcome
    strategy_version: StrategyVersion | None

    def __post_init__(self) -> None:
        if self.outcome.is_valid and self.strategy_version is None:
            raise FinalisationError("A VALID outcome must carry a StrategyVersion")
        if not self.outcome.is_valid and self.strategy_version is not None:
            raise FinalisationError("A non-VALID outcome must not carry a StrategyVersion")


def finalise(draft: SpecificationDraft, *, strategy_version_id: str, now: datetime | None = None) -> FinalisationResult:
    """The ONLY supported way to produce a `StrategyVersion`. Validates
    `draft` (PID-004 sec33); on any finding, returns a
    `FinalisationResult` with `strategy_version=None` and the governed
    `STRATEGY_NOT_SUFFICIENTLY_DEFINED` outcome -- `draft` itself is never
    mutated either way (PID-004 sec19: "never mutate a draft in place into
    a frozen version"). On success, constructs a brand NEW, immutable
    `StrategyVersion` object -- never the same object as `draft`, never a
    mutated `draft` with a status flag flipped.
    """
    outcome = validate_draft(draft)
    if not outcome.is_valid:
        return FinalisationResult(outcome=outcome, strategy_version=None)

    if not strategy_version_id or not strategy_version_id.strip():
        raise FinalisationError("finalise requires a non-empty strategy_version_id")

    now = now or datetime.now(UTC)

    semantic_fields = {name: getattr(draft, name) for name in SEMANTIC_FIELD_NAMES}
    # dict-valued draft fields (fixed_parameters, tunable_parameters,
    # policy_declarations, data_requirements) are frozen into tuples here --
    # this is also the exact shape StrategyVersion itself stores them in,
    # so semantic_payload() on the finished object reproduces this same
    # dict deterministically via canonicalize()'s sorted-key dict handling.
    semantic_fields["fixed_parameters"] = tuple(sorted(draft.fixed_parameters.values(), key=lambda p: p.parameter_id))
    semantic_fields["tunable_parameters"] = tuple(
        sorted(draft.tunable_parameters.values(), key=lambda p: p.parameter_id)
    )
    semantic_fields["policy_declarations"] = tuple(
        sorted(draft.policy_declarations.values(), key=lambda d: d.policy_class.value)
    )
    semantic_fields["data_requirements"] = tuple(
        sorted(draft.data_requirements.values(), key=lambda r: r.requirement_id)
    )

    semantic_fingerprint = canonical_hash(semantic_fields)

    provenance_tuple = tuple(sorted(draft.provenance.values(), key=lambda p: p.provenance_id))
    artifact_fields = {
        "semantic_fingerprint": semantic_fingerprint,
        "strategy_version_id": strategy_version_id,
        "candidate_id": draft.candidate_id,
        "title": draft.title,
        "provenance": provenance_tuple,
        "finalised_at_utc": now,
    }
    artifact_record_fingerprint = canonical_hash(artifact_fields)

    version = StrategyVersion(
        strategy_version_id=strategy_version_id,
        candidate_id=draft.candidate_id,
        schema_semantic_version=draft.schema_semantic_version,
        title=draft.title,
        thesis=draft.thesis,
        instrument_applicability=semantic_fields["instrument_applicability"],
        composition=semantic_fields["composition"],
        fixed_parameters=semantic_fields["fixed_parameters"],
        tunable_parameters=semantic_fields["tunable_parameters"],
        policy_declarations=semantic_fields["policy_declarations"],
        data_requirements=semantic_fields["data_requirements"],
        session_spec=semantic_fields["session_spec"],
        intrabar_ambiguity_policy=semantic_fields["intrabar_ambiguity_policy"],
        setup_expiry=semantic_fields["setup_expiry"],
        exit_rules=semantic_fields["exit_rules"],
        provenance=provenance_tuple,
        finalised_at_utc=now,
        semantic_fingerprint=semantic_fingerprint,
        artifact_record_fingerprint=artifact_record_fingerprint,
    )
    return FinalisationResult(outcome=outcome, strategy_version=version)
