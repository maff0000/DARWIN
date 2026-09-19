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

import dataclasses
import logging
from datetime import UTC, datetime
from decimal import InvalidOperation

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
    _dec_decimal,
    _is_decimal_node,
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
    succeeded_run = run_row_to_domain(row) if row else run
    # PID-004C sec13/sec13.1: attach the adapter's bounded reasoning
    # summary onto THIS synchronous response only -- never persisted
    # (see MendelRun.reasoning_summary's own docstring). `dataclasses.
    # replace` never mutates the DB-rehydrated `succeeded_run` in place.
    return dataclasses.replace(succeeded_run, reasoning_summary=result.reasoning_summary)


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


def _validated_parameter_change_fixed_value(value_type: ParameterValueType, fixed_value: object) -> object:
    """PID-004C closure-hardening (Architect-directed real-defect fix,
    2026-09-19): `PARAMETER_CHANGE`'s declared `value_type` must agree
    EXACTLY with `fixed_value`'s actual shape, checked here -- BEFORE
    `_apply_parameter_change` (below) ever constructs a
    `ParameterDefinition`, whose own `__post_init__`
    (`darwin.specification.parameters`) performs no such cross-check and
    is deliberately left untouched by this fix (that is a separate,
    broader, pre-existing PID-004A gap -- see this work package's final
    report).

    Mirrors `darwin.specification.serialization._enc_scalar`'s own closed
    `Decimal | int | bool | str` discipline exactly, including checking
    `bool` before/separately from `int` since `bool` is an `int` subclass
    in Python and must never be silently treated as one.

    Returns the value to actually store as `ParameterDefinition.
    fixed_value`: for DECIMAL this is the DECODED `Decimal` (this
    codebase's own canonical wire representation for a Decimal scalar is
    `{"__decimal__": "<string>"}` -- see `darwin.specification.
    serialization._enc_decimal`/`_dec_decimal`/`_is_decimal_node`, reused
    directly here rather than inventing a second representation); for
    every other value_type the payload's `fixed_value` is already the
    correct native Python scalar and is returned unchanged.
    """
    if value_type == ParameterValueType.BOOLEAN:
        if not isinstance(fixed_value, bool):
            raise MendelOutputValidationError(
                f"PARAMETER_CHANGE value_type=BOOLEAN requires a genuine bool fixed_value, got "
                f"{fixed_value!r} of type {type(fixed_value).__name__!r}"
            )
        return fixed_value
    if value_type in (ParameterValueType.INTEGER, ParameterValueType.DURATION_SECONDS):
        # bool excluded FIRST and explicitly -- bool is an int subclass in
        # Python, and a bool fixed_value must never be silently accepted
        # as a genuine INTEGER/DURATION_SECONDS value.
        if isinstance(fixed_value, bool) or not isinstance(fixed_value, int):
            raise MendelOutputValidationError(
                f"PARAMETER_CHANGE value_type={value_type.value} requires a genuine int fixed_value "
                f"(bool explicitly excluded), got {fixed_value!r} of type {type(fixed_value).__name__!r}"
            )
        return fixed_value
    if value_type == ParameterValueType.STRING:
        if not isinstance(fixed_value, str):
            raise MendelOutputValidationError(
                f"PARAMETER_CHANGE value_type=STRING requires a genuine str fixed_value, got "
                f"{fixed_value!r} of type {type(fixed_value).__name__!r}"
            )
        return fixed_value
    if value_type == ParameterValueType.DECIMAL:
        # Accept ONLY this codebase's own canonical lossless wire shape
        # ({"__decimal__": "<string>"}, with the wrapped value itself
        # required to be a JSON string) -- never a raw JSON number, and
        # never silently coerced from a binary float (a raw JSON float
        # inside the wrapper would itself construct a lossy Decimal, so
        # it is rejected here too, not just a bare float fixed_value).
        if not _is_decimal_node(fixed_value) or not isinstance(fixed_value["__decimal__"], str):
            raise MendelOutputValidationError(
                "PARAMETER_CHANGE value_type=DECIMAL requires fixed_value in this codebase's own "
                "canonical lossless wire representation {'__decimal__': '<string>'} (darwin."
                f"specification.serialization's own contract) -- got {fixed_value!r}"
            )
        try:
            decoded = _dec_decimal(fixed_value)
        except InvalidOperation as exc:
            raise MendelOutputValidationError(
                f"PARAMETER_CHANGE value_type=DECIMAL fixed_value {fixed_value!r} is not a valid "
                f"Decimal string: {exc}"
            ) from exc
        # PID-004C closure hardening (Architect-directed, 2026-09-19, closing
        # a real Auditor-found gap): `Decimal("NaN")`/`Decimal("sNaN")`/
        # `Decimal("Infinity")`/`Decimal("-Infinity")` are all valid Python
        # Decimal constructions and therefore never raise `InvalidOperation`
        # above -- a non-finite value would otherwise sail through
        # undetected and reach persistence. A strategy parameter's fixed
        # value must always be a genuine, finite number; never silently
        # normalised, never left for a later validation stage to discover.
        if not decoded.is_finite():
            raise MendelOutputValidationError(
                f"PARAMETER_CHANGE value_type=DECIMAL fixed_value {fixed_value!r} decodes to a "
                f"non-finite Decimal ({decoded!r}) -- NaN/sNaN/Infinity/-Infinity are never a valid "
                f"fixed parameter value"
            )
        return decoded
    raise MendelOutputValidationError(  # pragma: no cover -- closed enum, every member handled above
        f"Unhandled ParameterValueType {value_type!r}"
    )


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
    # PID-004C closure-hardening (2026-09-19): explicit, non-coercive
    # value_type/fixed_value shape check -- BEFORE ParameterDefinition is
    # ever constructed -- so a mismatched proposal fails HERE, during
    # invoke_mendel's own dry-run of this exact handler
    # (_validate_payload_shape), never merely later at accept time.
    fixed_value = _validated_parameter_change_fixed_value(value_type, fixed_value)
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


# ============================================================================
# PID-004C CLOSURE HARDENING item 2 (Auditor Finding A fix): the exact,
# closed top-level payload key set for EVERY one of the nine ProposalClass
# members -- ASK_QUESTION and MATERIAL_CONCERN included, not only the seven
# DRAFT_MUTATING classes that already had a dry-run handler check. A
# payload key outside its class's set is refused BEFORE persistence
# (`_validate_payload_shape` below), never silently ignored by a handler
# that only ever read its own named keys.
#
# Each set below mirrors EXACTLY what that class's current handler (or, for
# ASK_QUESTION, `_question_subject`/`_question_text`) already legitimately
# reads -- this is closure of the "reject anything else" gap, never an
# addition or removal of functional capability. Mirrors
# `PROPOSAL_CLASS_CATEGORY`'s own "single source of truth, asserted
# exhaustive" discipline (mendel_domain.py).
# ============================================================================

PROPOSAL_CLASS_ALLOWED_PAYLOAD_KEYS: dict[ProposalClass, frozenset[str]] = {
    # QUESTION category -- darwin.workshop.mendel_service._question_subject/
    # _question_text's own current `payload.get(...)` reads.
    ProposalClass.ASK_QUESTION: frozenset({"semantic_subject", "question_text"}),
    # ADVISORY category -- nothing currently reads MATERIAL_CONCERN's
    # payload by key (it is persisted whole as a WorkshopDecision's
    # proposed_value), so this defines the minimal sensible schema already
    # illustrated by darwin.workshop.api._E2E_FIXTURE_PROPOSALS and
    # tests/fixtures/mendel.py's material_concern_proposal().
    ProposalClass.MATERIAL_CONCERN: frozenset({"concern"}),
    # DRAFT_MUTATING -- one entry per _DRAFT_MUTATION_HANDLERS handler,
    # matching its exact current payload[...]/payload.get(...) reads.
    ProposalClass.SEMANTIC_CHANGE: frozenset({"composition"}),
    ProposalClass.PARAMETER_CHANGE: frozenset({"parameter_id", "value_type", "unit", "fixed_value"}),
    ProposalClass.DATA_REQUIREMENT: frozenset({
        "requirement_id", "display_name", "fact_class", "fact_reference_kind", "authority_class",
        "instrument_applicability", "timeframe", "required_historical_depth", "units",
        "required_fields", "causal_timing_policy", "mandatory",
    }),
    ProposalClass.THESIS_CHANGE: frozenset({"new_thesis"}),
    # `authorized_search_envelope` IS one of this handler's current reads
    # (`payload.get("authorized_search_envelope")`) -- it exists solely so
    # the handler can explicitly refuse a truthy value with its own
    # narrower-first-pass message; excluding it here would just replace
    # that specific, informative message with the generic "unrecognised
    # key" one for no functional gain, so it stays in the allowed set.
    ProposalClass.POLICY_CLASSIFICATION: frozenset(
        {"policy_class", "compatibility", "notes", "authorized_search_envelope"}
    ),
    ProposalClass.INSTRUMENT_CLARIFICATION: frozenset({"kind", "instrument_ids", "generic_criteria"}),
    ProposalClass.TIMEFRAME_CLARIFICATION: frozenset(
        {"iana_timezone", "local_start", "local_end", "weekdays", "cross_midnight"}
    ),
}

assert set(PROPOSAL_CLASS_ALLOWED_PAYLOAD_KEYS) == set(ProposalClass), (
    "PROPOSAL_CLASS_ALLOWED_PAYLOAD_KEYS must cover every ProposalClass member -- a class with no "
    "closed key set is a structural bug, never a legitimate 'unrestricted' state (PID-004C closure "
    "hardening item 2)"
)


def _validate_payload_shape(proposal_class: ProposalClass, payload: dict) -> None:
    """PID-004C sec18's "validate the typed payload shape for its class"
    step, run BEFORE persistence at invoke_mendel time (not just at
    acceptance time) -- so a malformed proposal is refused up front,
    never merely discovered later when a human tries to accept it.

    Two checks, in order, for EVERY class (not only DRAFT_MUTATING ones):
    1. Closed top-level key set (PID-004C closure hardening item 2 /
       Auditor Finding A): any key outside `PROPOSAL_CLASS_ALLOWED_
       PAYLOAD_KEYS[proposal_class]` fails validation immediately, with
       the unrecognised key(s) named in the error -- never silently
       dropped, never preserved as inert extra JSON, never passed through
       to a handler that would just ignore it.
    2. For DRAFT_MUTATING classes only, dry-runs the real handler against
       a disposable, minimal in-memory draft; a payload that fails
       construction fails validation identically to a payload that would
       fail at acceptance time -- there is exactly one shape-checking code
       path, not two that could drift apart.
    """
    if not isinstance(payload, dict):
        raise MendelOutputValidationError(f"payload for {proposal_class.value} must be a JSON object")
    allowed_keys = PROPOSAL_CLASS_ALLOWED_PAYLOAD_KEYS[proposal_class]
    unrecognised = set(payload) - allowed_keys
    if unrecognised:
        raise MendelOutputValidationError(
            f"payload for {proposal_class.value} contains unrecognised key(s) "
            f"{sorted(unrecognised)!r} -- only {sorted(allowed_keys)!r} are accepted for this class "
            f"(closed payload shape, PID-004C closure hardening item 2: unknown fields fail closed)"
        )
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
    # MendelOutputValidationError here should be structurally unreachable
    # for a proposal that went through the normal invoke_mendel pipeline.
    #
    # Defence-in-depth ONLY (PID-004C closure-hardening, 2026-09-19,
    # re-audit-found gap closed): this narrow except exists solely to turn
    # a hypothetical malformed row (e.g. one inserted directly via
    # MendelProposalRepository/raw SQL, bypassing invoke_mendel's gate
    # entirely) into a governed MendelProposalNotApplicableError instead of
    # an uncaught internal exception escaping this boundary.
    # `MendelOutputValidationError` is explicitly included alongside
    # `SerializationError`/`SpecificationError` -- it is exactly what
    # `_validated_parameter_change_fixed_value` (called again here via
    # `_apply_parameter_change`) raises for a type-mismatched fixed_value,
    # and omitting it left precisely that bypass path leaking an uncaught
    # MendelOutputValidationError instead of the promised governed
    # refusal. Still only these three specific, narrow exception types --
    # never a bare Exception, so a genuine programming bug elsewhere is
    # not masked. Nothing has been written yet at this point (no draft/
    # decision/proposal-status write has happened), so the proposal is
    # left exactly PROPOSED -- never marked ACCEPTED, never orphaning a
    # decision, transaction stays coherent.
    handler = _DRAFT_MUTATION_HANDLERS[proposal.proposal_class]
    try:
        mutated_draft = handler(draft, proposal.payload)
        document = serialize_specification_draft(mutated_draft)
    except (MendelOutputValidationError, SerializationError, SpecificationError) as exc:
        raise MendelProposalNotApplicableError(
            f"proposal_id={proposal_id!r} payload is malformed for its proposal_class "
            f"{proposal.proposal_class.value!r} and cannot be applied: {exc}"
        ) from exc
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
