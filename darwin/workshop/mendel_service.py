"""PID-004C MENDEL Workshop Assistant orchestration -- the acceptance
transactions (sec7.3), the invocation pipeline (sec11/sec18), and the
closed, per-class draft-mutation handlers (sec6.6).

Layering mirrors `darwin.workshop.service` exactly: `darwin.workshop.api`
calls into this module, never into `darwin.research_store.
mendel_repositories` directly. One `conn: psycopg.Connection` threaded
through every call; the caller's enclosing `darwin.research_store.db.
connection(...)` context manager commits/rolls back -- this module never
calls `commit()`/`rollback()` itself.

Every draft-mutating handler below is a NARROW, EXPLICIT, per-class
function -- there is no generic path/value setter anywhere in this module
(PID-004C sec6.6). `affected_semantic_paths` is read from a proposal only
as audit metadata (passed straight through onto the resulting
`WorkshopDecision`), never used to decide what to mutate or how.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import psycopg

from darwin.core.identities import new_id
from darwin.research_store.mendel_repositories import (
    MendelProposalRepository,
    MendelRunRepository,
    proposal_row_to_domain,
    run_row_to_domain,
)
from darwin.research_store.specification_repositories import StaleRevisionError
from darwin.specification.applicability import (
    DstHandling,
    InstrumentApplicability,
    InstrumentApplicabilityKind,
    SessionSpec,
)
from darwin.specification.data_requirements import (
    CausalTimingPolicy,
    DataAuthorityClass,
    DataRequirement,
    FactClass,
    HistoricalDepthRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.domain import SpecificationDraft
from darwin.specification.errors import SpecificationError
from darwin.specification.facts import FactReferenceKind
from darwin.specification.parameters import (
    ParameterDefinition,
    ParameterStatus,
    ParameterValueType,
)
from darwin.specification.policy import (
    PolicyClass,
    PolicyCompatibility,
    PolicyCompatibilityDeclaration,
)
from darwin.specification.provenance import RuleOrigin
from darwin.specification.serialization import (
    SerializationError,
    deserialize_specification_draft,
    serialize_specification_draft,
)
from darwin.specification.timeframe import Timeframe
from darwin.workshop import service
from darwin.workshop.domain import QuestionOrigin
from darwin.workshop.errors import WorkshopNotActiveError
from darwin.workshop.mendel_adapter import MendelAdapter, RawMendelProposal
from darwin.workshop.mendel_context import build_bounded_context
from darwin.workshop.mendel_domain import (
    NO_DRAFT_YET,
    PROPOSAL_CLASS_CATEGORY,
    DraftRevisionBinding,
    InvocationPurpose,
    MendelProposal,
    MendelRun,
    ProposalCategory,
    ProposalClass,
    ProposalStatus,
    RunStatus,
    category_for_class,
    is_stale_binding,
)
from darwin.workshop.mendel_errors import (
    MendelAdapterTimeoutError,
    MendelOutputValidationError,
    MendelProposalNotApplicableError,
    MendelProposalNotFoundError,
    MendelProposalStaleError,
    MendelRunNotFoundError,
)

logger = logging.getLogger(__name__)

#: The proposal-schema version this build's validation pipeline and
#: handlers understand (PID-004C sec10.2/sec18). A future schema bump is a
#: deliberate code change, never a silent shape drift.
PROPOSAL_SCHEMA_VERSION = "MENDEL_PROPOSAL_V1"


# ============================================================================
# invoke_mendel -- PID-004C sec11/sec18.
# ============================================================================


def _current_binding(conn: psycopg.Connection, workshop_id: str) -> DraftRevisionBinding:
    _, revision = service.get_draft(conn, workshop_id)
    return revision if revision is not None else NO_DRAFT_YET


def _validate_raw_proposal(
    raw: RawMendelProposal, *, run_id: str, workshop_id: str, binding: DraftRevisionBinding
) -> MendelProposal:
    """PID-004C sec18's output-validation pipeline, per proposal: parse
    against the exact declared `proposal_schema_version` -> validate
    closed class/category agreement -> validate workshop/run binding ->
    validate the typed payload shape for its class. Only construction of
    the real, typed `MendelProposal` -- which itself re-checks class/
    category agreement (`darwin.workshop.mendel_domain.MendelProposal.
    __post_init__`) -- ever happens; nothing is persisted here."""
    if raw.proposal_schema_version != PROPOSAL_SCHEMA_VERSION:
        raise MendelOutputValidationError(
            f"unsupported proposal_schema_version {raw.proposal_schema_version!r}; this build only "
            f"understands {PROPOSAL_SCHEMA_VERSION!r}"
        )
    try:
        proposal_class = ProposalClass(raw.proposal_class)
    except ValueError as exc:
        raise MendelOutputValidationError(
            f"proposal_class {raw.proposal_class!r} is not in the closed PID-004C sec6.4 vocabulary"
        ) from exc
    category = category_for_class(proposal_class)
    _validate_payload_shape(proposal_class, raw.payload)
    if not raw.rationale or not raw.rationale.strip():
        raise MendelOutputValidationError("a MendelProposal requires a non-empty rationale")
    return MendelProposal(
        proposal_id=new_id(),
        run_id=run_id,
        workshop_id=workshop_id,
        proposal_class=proposal_class,
        proposal_category=category,
        proposal_schema_version=raw.proposal_schema_version,
        payload=raw.payload,
        rationale=raw.rationale,
        affected_semantic_paths=tuple(raw.affected_semantic_paths),
        generated_against_draft_revision=binding,
    )


def invoke_mendel(
    conn: psycopg.Connection, workshop_id: str, *, purpose: InvocationPurpose, focus_text: str | None,
    adapter: MendelAdapter,
) -> MendelRun:
    """PID-004C sec7.3.0/sec11/sec17: persists a `RUNNING` `mendel_runs`
    row BEFORE calling the adapter, then EITHER persists `SUCCEEDED` +
    every validated proposal atomically, OR persists `FAILED`/`TIMEOUT`
    with an error classification and ZERO proposal rows -- never a
    partial proposal set, and never an exception that could damage
    `SpecificationDraft`/`WorkshopQuestion`/`WorkshopDecision` state (this
    function never touches those tables at all)."""
    workshop = service.get_workshop(conn, workshop_id)
    if not workshop.is_active:
        raise WorkshopNotActiveError(f"Workshop {workshop_id!r} is {workshop.status.value}, not ACTIVE")

    context = build_bounded_context(conn, workshop_id, focus_text=focus_text)
    binding = _current_binding(conn, workshop_id)
    run_id = new_id()
    started_at = datetime.now(UTC)
    run = MendelRun(
        run_id=run_id, workshop_id=workshop_id, purpose=purpose, focus_text=focus_text,
        context_schema_version=context.schema_version, context_fingerprint=context.fingerprint,
        provider_identity=adapter.provider_identity, status=RunStatus.RUNNING, started_at_utc=started_at,
    )
    MendelRunRepository(conn).create(run)

    try:
        result = adapter.invoke(context=context, purpose=purpose, focus_text=focus_text)
    except MendelAdapterTimeoutError as exc:
        row = MendelRunRepository(conn).mark_terminal(
            workshop_id, run_id, status=RunStatus.TIMEOUT, completed_at_utc=datetime.now(UTC),
            error_classification=str(exc),
        )
        return run_row_to_domain(row) if row else run
    except Exception as exc:  # noqa: BLE001 -- any adapter failure is a governed FAILED run, never a leak
        row = MendelRunRepository(conn).mark_terminal(
            workshop_id, run_id, status=RunStatus.FAILED, completed_at_utc=datetime.now(UTC),
            error_classification=f"adapter_invocation_error: {exc}",
        )
        return run_row_to_domain(row) if row else run

    try:
        validated = [
            _validate_raw_proposal(raw, run_id=run_id, workshop_id=workshop_id, binding=binding)
            for raw in result.proposals
        ]
    except MendelOutputValidationError as exc:
        row = MendelRunRepository(conn).mark_terminal(
            workshop_id, run_id, status=RunStatus.FAILED, completed_at_utc=datetime.now(UTC),
            error_classification=str(exc),
        )
        return run_row_to_domain(row) if row else run

    row = MendelRunRepository(conn).mark_terminal(
        workshop_id, run_id, status=RunStatus.SUCCEEDED, completed_at_utc=datetime.now(UTC),
    )
    proposal_repo = MendelProposalRepository(conn)
    for proposal in validated:
        proposal_repo.create(proposal)
    return run_row_to_domain(row) if row else run


def get_run(conn: psycopg.Connection, workshop_id: str, run_id: str) -> MendelRun:
    service.get_workshop(conn, workshop_id)
    row = MendelRunRepository(conn).get_row(workshop_id, run_id)
    if row is None:
        raise MendelRunNotFoundError(f"run_id={run_id!r} does not belong to workshop_id={workshop_id!r}")
    return run_row_to_domain(row)


def list_runs(conn: psycopg.Connection, workshop_id: str) -> list[MendelRun]:
    service.get_workshop(conn, workshop_id)
    rows = MendelRunRepository(conn).list_for_workshop(workshop_id)
    return [run_row_to_domain(r) for r in rows]


def list_proposals(
    conn: psycopg.Connection, workshop_id: str, *, status: ProposalStatus | None = None
) -> list[MendelProposal]:
    service.get_workshop(conn, workshop_id)
    rows = MendelProposalRepository(conn).list_for_workshop(workshop_id, status=status)
    return [proposal_row_to_domain(r) for r in rows]


# ============================================================================
# Closed, per-class draft-mutation handlers -- PID-004C sec6.6.
#
# Every handler here takes the CURRENT SpecificationDraft + the proposal's
# own typed payload and returns the NEXT SpecificationDraft -- constructed
# exclusively through darwin.specification's own existing, closed
# constructors/deserialiser. None of them accept a caller-supplied
# path/key to decide what to touch; each is hardcoded to exactly one
# field. See this work package's final report for which of these are a
# FULL handler versus a documented, narrower first-pass handler.
# ============================================================================


def _apply_parameter_change(draft: SpecificationDraft, payload: dict) -> SpecificationDraft:
    """FULL handler for PARAMETER_CHANGE, WP1 scope: creates or replaces a
    FIXED parameter's value via the existing `ParameterDefinition`
    constructor + `SpecificationDraft.set_parameter`. Does NOT support
    mutating a TUNABLE parameter's domain (a TUNABLE parameter has no
    single "value" to change) -- a payload naming an existing TUNABLE
    parameter, or omitting `fixed_value`, is refused rather than guessed."""
    try:
        parameter_id = payload["parameter_id"]
        value_type = ParameterValueType(payload["value_type"])
        fixed_value = payload["fixed_value"]
    except (KeyError, ValueError) as exc:
        raise MendelOutputValidationError(f"malformed PARAMETER_CHANGE payload: {exc}") from exc
    if fixed_value is None:
        raise MendelOutputValidationError(
            "PARAMETER_CHANGE (WP1 full-handler scope) requires a non-null fixed_value -- TUNABLE "
            "domain mutation is not supported by this handler"
        )
    existing = draft.tunable_parameters.get(parameter_id)
    if existing is not None:
        raise MendelOutputValidationError(
            f"parameter_id={parameter_id!r} is currently TUNABLE -- this handler only changes an "
            f"existing/new FIXED parameter's value, never a TUNABLE parameter's domain"
        )
    try:
        definition = ParameterDefinition(
            parameter_id=parameter_id, status=ParameterStatus.FIXED, value_type=value_type,
            unit=payload.get("unit"), fixed_value=fixed_value,
        )
    except SpecificationError as exc:
        raise MendelOutputValidationError(f"malformed PARAMETER_CHANGE payload: {exc}") from exc
    draft.set_parameter(definition)
    return draft


def _apply_data_requirement(draft: SpecificationDraft, payload: dict) -> SpecificationDraft:
    """FULL handler for DATA_REQUIREMENT, WP1 scope: adds a new typed
    `DataRequirement` via the existing PID-004A typed constructors."""
    try:
        depth_node = payload["required_historical_depth"]
        depth = HistoricalDepthRequirement(
            count=int(depth_node["count"]), unit=HistoricalDepthUnit(depth_node["unit"])
        )
        timeframe_code = payload.get("timeframe")
        requirement = DataRequirement(
            requirement_id=payload["requirement_id"],
            display_name=payload["display_name"],
            fact_class=FactClass(payload["fact_class"]),
            fact_reference_kind=FactReferenceKind(payload["fact_reference_kind"]),
            authority_class=DataAuthorityClass(payload["authority_class"]),
            instrument_applicability=tuple(payload["instrument_applicability"]),
            timeframe=Timeframe(timeframe_code) if timeframe_code else None,
            required_historical_depth=depth,
            units=payload.get("units"),
            required_fields=tuple(payload["required_fields"]),
            causal_timing_policy=CausalTimingPolicy(payload["causal_timing_policy"]),
            mandatory=bool(payload.get("mandatory", True)),
        )
    except (KeyError, ValueError, TypeError, SpecificationError) as exc:
        raise MendelOutputValidationError(f"malformed DATA_REQUIREMENT payload: {exc}") from exc
    draft.set_data_requirement(requirement)
    return draft


def _apply_thesis_change(draft: SpecificationDraft, payload: dict) -> SpecificationDraft:
    """FULL handler for THESIS_CHANGE, WP1 scope: replaces `draft.thesis`
    -- a plain, non-empty string field with no further internal structure
    to validate beyond that."""
    try:
        new_thesis = payload["new_thesis"]
    except KeyError as exc:
        raise MendelOutputValidationError("malformed THESIS_CHANGE payload: missing 'new_thesis'") from exc
    if not isinstance(new_thesis, str) or not new_thesis.strip():
        raise MendelOutputValidationError("THESIS_CHANGE payload 'new_thesis' must be a non-empty string")
    draft.thesis = new_thesis
    return draft


def _apply_instrument_clarification(draft: SpecificationDraft, payload: dict) -> SpecificationDraft:
    """FULL handler for INSTRUMENT_CLARIFICATION, WP1 scope: replaces
    `draft.instrument_applicability` via the existing `InstrumentApplicability`
    constructor (which itself enforces PID-004 sec11's own kind-specific
    shape rules)."""
    try:
        applicability = InstrumentApplicability(
            kind=InstrumentApplicabilityKind(payload["kind"]),
            instrument_ids=tuple(payload.get("instrument_ids", ())),
            generic_criteria=tuple(payload.get("generic_criteria", ())),
        )
    except (KeyError, ValueError, SpecificationError) as exc:
        raise MendelOutputValidationError(f"malformed INSTRUMENT_CLARIFICATION payload: {exc}") from exc
    draft.instrument_applicability = applicability
    return draft


def _apply_policy_classification(draft: SpecificationDraft, payload: dict) -> SpecificationDraft:
    """NARROWER first-pass handler for POLICY_CLASSIFICATION, WP1 scope:
    supports a bare compatibility declaration (`PolicyClass` +
    `PolicyCompatibility` + optional notes) via the existing
    `PolicyCompatibilityDeclaration` constructor. Does NOT support
    declaring an `authorized_search_envelope` (which itself requires
    constructing a nested TUNABLE `ParameterDefinition` per authorised
    search dimension) -- a payload naming one is refused rather than
    guessed at."""
    if payload.get("authorized_search_envelope"):
        raise MendelOutputValidationError(
            "POLICY_CLASSIFICATION (WP1 narrower first-pass) does not support "
            "authorized_search_envelope -- only a bare compatibility declaration"
        )
    try:
        declaration = PolicyCompatibilityDeclaration(
            policy_class=PolicyClass(payload["policy_class"]),
            compatibility=PolicyCompatibility(payload["compatibility"]),
            notes=payload.get("notes"),
        )
    except (KeyError, ValueError, SpecificationError) as exc:
        raise MendelOutputValidationError(f"malformed POLICY_CLASSIFICATION payload: {exc}") from exc
    draft.set_policy_declaration(declaration)
    return draft


def _apply_timeframe_clarification(draft: SpecificationDraft, payload: dict) -> SpecificationDraft:
    """NARROWER first-pass handler for TIMEFRAME_CLARIFICATION, WP1 scope:
    supports only replacing the Workshop's `SessionSpec` (timezone/session
    window/weekdays/DST/cross-midnight) via the existing `SessionSpec`
    constructor. Does NOT support per-atomic-condition timeframe-role
    reassignment inside the composition tree (PID-004 sec6's genuinely
    separate "timeframe role per component" concept) -- that is deferred
    to a later work package, never guessed at here."""
    try:
        session = SessionSpec(
            iana_timezone=payload["iana_timezone"], local_start=payload["local_start"],
            local_end=payload["local_end"], weekdays=tuple(payload["weekdays"]),
            dst_handling=DstHandling.FOLLOW_IANA_TIMEZONE_RULES,
            cross_midnight=bool(payload.get("cross_midnight", False)),
        )
    except (KeyError, ValueError, TypeError, SpecificationError) as exc:
        raise MendelOutputValidationError(f"malformed TIMEFRAME_CLARIFICATION payload: {exc}") from exc
    draft.session_spec = session
    return draft


def _apply_semantic_change(draft: SpecificationDraft, payload: dict) -> SpecificationDraft:
    """NARROWER first-pass handler for SEMANTIC_CHANGE, WP1 scope:
    supports wholesale replacement of the entire `composition` subtree,
    supplied as an already-serialised `CompositionRoot` document (exactly
    the shape `darwin.specification.serialization`'s own encoder produces)
    -- applied by round-tripping the WHOLE draft through the existing,
    closed `deserialize_specification_draft` (never a hand-rolled partial
    tree edit, never a bespoke composition constructor of this module's
    own invention). Does NOT support a targeted/partial edit of one
    nested condition without restating the entire composition document --
    that finer-grained capability is deferred."""
    composition_document = payload.get("composition")
    if not isinstance(composition_document, dict):
        raise MendelOutputValidationError(
            "SEMANTIC_CHANGE (WP1 narrower first-pass) requires a 'composition' key holding a "
            "complete serialised CompositionRoot document"
        )
    document = serialize_specification_draft(draft)
    document["composition"] = composition_document
    try:
        return deserialize_specification_draft(document)
    except (SerializationError, SpecificationError) as exc:
        raise MendelOutputValidationError(f"malformed SEMANTIC_CHANGE payload: {exc}") from exc


_DRAFT_MUTATION_HANDLERS = {
    ProposalClass.SEMANTIC_CHANGE: _apply_semantic_change,
    ProposalClass.PARAMETER_CHANGE: _apply_parameter_change,
    ProposalClass.DATA_REQUIREMENT: _apply_data_requirement,
    ProposalClass.THESIS_CHANGE: _apply_thesis_change,
    ProposalClass.POLICY_CLASSIFICATION: _apply_policy_classification,
    ProposalClass.INSTRUMENT_CLARIFICATION: _apply_instrument_clarification,
    ProposalClass.TIMEFRAME_CLARIFICATION: _apply_timeframe_clarification,
}

assert set(_DRAFT_MUTATION_HANDLERS) == {
    proposal_class
    for proposal_class, category in PROPOSAL_CLASS_CATEGORY.items()
    if category == ProposalCategory.DRAFT_MUTATING
}, "every DRAFT_MUTATING ProposalClass must have exactly one registered handler"


def _validate_payload_shape(proposal_class: ProposalClass, payload: dict) -> None:
    """PID-004C sec18's "validate the typed payload shape for its class"
    step, run BEFORE persistence at invoke_mendel time (not just at
    acceptance time) -- so a malformed proposal is refused up front,
    never merely discovered later when a human tries to accept it. For
    DRAFT_MUTATING classes this dry-runs the real handler against a
    disposable, minimal in-memory draft; a payload that fails construction
    fails validation identically to a payload that would fail at
    acceptance time -- there is exactly one shape-checking code path, not
    two that could drift apart.
    """
    if not isinstance(payload, dict):
        raise MendelOutputValidationError(f"payload for {proposal_class.value} must be a JSON object")
    category = category_for_class(proposal_class)
    if category != ProposalCategory.DRAFT_MUTATING:
        return
    handler = _DRAFT_MUTATION_HANDLERS[proposal_class]
    probe_draft = SpecificationDraft(draft_id=new_id(), candidate_id=new_id(), schema_semantic_version="1.0.0")
    handler(probe_draft, payload)


# ============================================================================
# accept_proposal / reject_proposal -- PID-004C sec7.3, sec7.5.
# ============================================================================


def _get_proposal_or_raise(conn: psycopg.Connection, workshop_id: str, proposal_id: str) -> MendelProposal:
    row = MendelProposalRepository(conn).get_row(workshop_id, proposal_id)
    if row is None:
        raise MendelProposalNotFoundError(
            f"proposal_id={proposal_id!r} does not belong to workshop_id={workshop_id!r}"
        )
    return proposal_row_to_domain(row)


def accept_proposal(
    conn: psycopg.Connection, workshop_id: str, proposal_id: str, *, actor: str
) -> MendelProposal:
    """PID-004C sec7.3.1-sec7.3.3: dispatches by `proposal_category`.
    Staleness (sec7.5) is checked FIRST, uniformly across all three
    categories (per PID-004C's own directive that even a QUESTION/ADVISORY
    proposal generated before any draft existed must be checked the same
    way) -- a proposal discovered stale here is marked `STALE` and
    returned as-is (never raised as an exception from mid-transaction,
    which would roll back the STALE marking itself); a proposal that is
    ALREADY `STALE` (or otherwise not `PROPOSED`) is refused up front via
    a typed error, with no write attempted at all."""
    workshop = service.get_workshop(conn, workshop_id)
    if not workshop.is_active:
        raise WorkshopNotActiveError(f"Workshop {workshop_id!r} is {workshop.status.value}, not ACTIVE")

    proposal = _get_proposal_or_raise(conn, workshop_id, proposal_id)
    if proposal.status != ProposalStatus.PROPOSED:
        if proposal.status == ProposalStatus.STALE:
            raise MendelProposalStaleError(f"proposal_id={proposal_id!r} is already STALE")
        raise MendelProposalNotApplicableError(
            f"proposal_id={proposal_id!r} is {proposal.status.value}, not PROPOSED"
        )

    current_binding = _current_binding(conn, workshop_id)
    if is_stale_binding(proposal.generated_against_draft_revision, current_binding):
        row = MendelProposalRepository(conn).mark_stale(
            workshop_id, proposal_id, resolved_at_utc=datetime.now(UTC)
        )
        return proposal_row_to_domain(row) if row else proposal

    if proposal.proposal_category == ProposalCategory.QUESTION:
        question = service.create_question(
            conn, workshop_id, semantic_subject=_question_subject(proposal),
            question_text=_question_text(proposal), rationale=proposal.rationale,
            origin=QuestionOrigin.MENDEL,
        )
        row = MendelProposalRepository(conn).mark_accepted(
            workshop_id, proposal_id, resolved_at_utc=datetime.now(UTC),
            resulting_question_id=question.question_id,
        )
        return proposal_row_to_domain(row) if row else proposal

    if proposal.proposal_category == ProposalCategory.ADVISORY:
        decision = service.create_decision(
            conn, workshop_id, proposed_value=proposal.payload, origin=RuleOrigin.WORKSHOP_PROPOSAL,
            actor=actor, affected_semantic_paths=proposal.affected_semantic_paths,
            rationale=proposal.rationale,
        )
        row = MendelProposalRepository(conn).mark_accepted(
            workshop_id, proposal_id, resolved_at_utc=datetime.now(UTC),
            resulting_decision_id=decision.decision_id,
        )
        return proposal_row_to_domain(row) if row else proposal

    # DRAFT_MUTATING (PID-004C sec7.3.3).
    draft, revision = service.get_draft(conn, workshop_id)
    if draft is None:  # pragma: no cover -- structurally excluded by the staleness check above
        raise MendelProposalNotApplicableError(
            f"proposal_id={proposal_id!r} is DRAFT_MUTATING but Workshop {workshop_id!r} has no draft"
        )
    # The payload was already validated at invoke_mendel time -- a
    # MendelOutputValidationError here should be structurally unreachable,
    # but is deliberately left to propagate (never silently swallowed) if
    # it somehow occurs.
    handler = _DRAFT_MUTATION_HANDLERS[proposal.proposal_class]
    mutated_draft = handler(draft, proposal.payload)
    document = serialize_specification_draft(mutated_draft)
    try:
        service.update_draft(conn, workshop_id, expected_revision=revision, draft_document=document)
    except StaleRevisionError:
        row = MendelProposalRepository(conn).mark_stale(
            workshop_id, proposal_id, resolved_at_utc=datetime.now(UTC)
        )
        return proposal_row_to_domain(row) if row else proposal

    decision = service.create_decision(
        conn, workshop_id, proposed_value=proposal.payload, origin=RuleOrigin.WORKSHOP_PROPOSAL,
        actor=actor, affected_semantic_paths=proposal.affected_semantic_paths, rationale=proposal.rationale,
    )
    row = MendelProposalRepository(conn).mark_accepted(
        workshop_id, proposal_id, resolved_at_utc=datetime.now(UTC),
        resulting_decision_id=decision.decision_id,
    )
    # PID-004C sec6.2.C/sec7.3.3: deterministic validation reruns after
    # every accepted DRAFT_MUTATING proposal. Read-only (darwin.workshop.
    # service.validate_workshop_draft writes nothing) -- called here,
    # inside the same transaction, purely so it demonstrably happens as
    # part of acceptance, not left to an API caller who might forget.
    service.validate_workshop_draft(conn, workshop_id)
    return proposal_row_to_domain(row) if row else proposal


def _question_subject(proposal: MendelProposal) -> str:
    subject = proposal.payload.get("semantic_subject") if isinstance(proposal.payload, dict) else None
    return subject or "MENDEL-raised question"


def _question_text(proposal: MendelProposal) -> str:
    text = proposal.payload.get("question_text") if isinstance(proposal.payload, dict) else None
    return text or proposal.rationale


def reject_proposal(
    conn: psycopg.Connection, workshop_id: str, proposal_id: str, *, reason: str | None = None
) -> MendelProposal:
    """PID-004C sec7.4: rejected proposals remain historical, never
    deleted, never touch `SpecificationDraft`. `reason` is accepted for
    audit but not currently persisted as its own column -- WP1 records it
    only in the returned/observed API response body; a future work
    package may add a durable `rejection_reason` column if that proves
    necessary (recorded honestly as a known limitation, not hidden)."""
    workshop = service.get_workshop(conn, workshop_id)
    if not workshop.is_active:
        raise WorkshopNotActiveError(f"Workshop {workshop_id!r} is {workshop.status.value}, not ACTIVE")
    proposal = _get_proposal_or_raise(conn, workshop_id, proposal_id)
    if proposal.status != ProposalStatus.PROPOSED:
        raise MendelProposalNotApplicableError(
            f"proposal_id={proposal_id!r} is {proposal.status.value}, not PROPOSED"
        )
    row = MendelProposalRepository(conn).mark_rejected(
        workshop_id, proposal_id, resolved_at_utc=datetime.now(UTC)
    )
    return proposal_row_to_domain(row) if row else proposal
