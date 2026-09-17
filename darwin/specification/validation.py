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

from darwin.specification.composition import (
    CompositionRoot,
    ContextTriggerComposition,
    ExpiryMode,
    all_leaf_conditions,
    finest_bound_timeframe_of,
)
from darwin.specification.domain import (
    SEMANTIC_FIELD_NAMES,
    SpecificationDraft,
    StrategyVersion,
)
from darwin.specification.errors import FinalisationError, ParameterDomainViolationError
from darwin.specification.expressions import (
    BooleanExpression,
    Comparison,
    EventPredicate,
    ParameterReference,
    UndefinedMeasurementBasis,
)
from darwin.specification.facts import SpecificationDerivedFact
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


def _iter_expression_nodes(node: object):
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
    # Literal, ParameterReference, CanonicalFactReference,
    # TemporalPredicate, SessionPredicate, EventPredicate,
    # UndefinedMeasurementBasis are leaves w.r.t. this walk.


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
