"""PID-004B Strategy Workshop orchestration (docs/pids/
PID-004-SPECIFICATION-WORKSHOP.md sec45-sec56).

Mirrors `darwin.scout.service`'s layering: `darwin.app`'s endpoints call
into this module, never into the repositories or `darwin.specification`/
`darwin.research_store.specification_finalisation` directly, so every
Workshop invariant (idempotent open, cross-workshop scoping, SCOUT
fidelity, the finalisation boundary) lives in exactly one place.

MENDEL seam (PID-004 sec46/sec48), without building MENDEL: every
question/decision creation function below takes an explicit `origin`
(`QuestionOrigin`/`darwin.specification.provenance.RuleOrigin`) and
`actor` parameter -- a future MENDEL adapter could call these same
functions with a new origin value and its own actor identity. Nothing here
is coupled to a Claude SDK, a subprocess, or a generic command surface --
there is no function anywhere in this module (or `darwin.workshop.api`)
that accepts a caller-supplied filesystem path or shell command.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import psycopg

from darwin.core.identities import new_id
from darwin.research_store.repositories import MarketDatasetRepository
from darwin.research_store.specification_finalisation import (
    FinalisationOutcome,
    finalise_specification_draft,
)
from darwin.research_store.specification_repositories import (
    DataReadinessAssessmentRepository,
    SpecificationDraftRepository,
    SpecificationVersionRepository,
)
from darwin.research_store.workshop_repositories import (
    WorkshopDecisionRepository,
    WorkshopQuestionRepository,
    WorkshopRepository,
    candidate_exists,
    decision_row_to_domain,
    discovery_exists,
    discovery_row,
    question_row_to_domain,
    workshop_row_to_domain,
)
from darwin.specification.data_requirements import (
    DataAuthorityClass,
    DataRequirement,
    HistoricalDepthUnit,
)
from darwin.specification.domain import SpecificationDraft
from darwin.specification.provenance import RuleOrigin
from darwin.specification.readiness import PerRequirementAvailability, assess_readiness
from darwin.specification.serialization import (
    deserialize_specification_draft,
    deserialize_strategy_version,
)
from darwin.specification.validation import ValidationOutcome, validate_draft
from darwin.workshop import workspace
from darwin.workshop.domain import (
    DecisionAcceptanceState,
    QuestionOrigin,
    QuestionStatus,
    StrategyWorkshop,
    WorkshopDecision,
    WorkshopQuestion,
    WorkshopStatus,
)
from darwin.workshop.errors import (
    CrossWorkshopReferenceError,
    InvalidWorkshopReferenceError,
    WorkshopHasNoDraftError,
    WorkshopNotActiveError,
    WorkshopNotFoundError,
)

logger = logging.getLogger(__name__)


def _sync_workspace_best_effort(conn: psycopg.Connection, workshop_id: str) -> None:
    """Regenerates the Workshop's authoring workspace from canonical
    Postgres state (PID-004 sec49). Deliberately best-effort: the
    workspace is an authoring surface, never canonical storage (PID-004
    sec47) -- a filesystem problem here (disk full, permissions, the
    directory having been deleted out-of-band) must never fail an
    otherwise-successful, already-committed API call."""
    try:
        row = WorkshopRepository(conn).get_row(workshop_id)
        if row is None:
            return
        discovery_ids = WorkshopRepository(conn).list_discovery_ids(workshop_id)
        discoveries = [discovery_row(conn, d) for d in discovery_ids]
        questions = WorkshopQuestionRepository(conn).list_for_workshop(workshop_id)
        decisions = WorkshopDecisionRepository(conn).list_for_workshop(workshop_id)
        draft_payload = None
        if row.get("current_draft_id"):
            draft_row = SpecificationDraftRepository(conn).get_row(str(row["current_draft_id"]))
            draft_payload = draft_row["draft_payload"] if draft_row else None
        workspace.sync_workspace_from_db(
            workshop=row, discoveries=[d for d in discoveries if d], questions=questions,
            decisions=decisions, draft_payload=draft_payload, validation=None,
        )
    except Exception:
        logger.warning("workshop_workspace_sync_failed", extra={"workshop_id": workshop_id}, exc_info=True)


def open_workshop(
    conn: psycopg.Connection, *, candidate_id: str, discovery_ids: tuple[str, ...] = ()
) -> StrategyWorkshop:
    """Idempotent open (PID-004B directive): at most one ACTIVE Workshop
    per candidate. Refuses an invalid `candidate_id`/`discovery_id`
    outright -- never creates an orphaned Workshop."""
    if not candidate_exists(conn, candidate_id):
        raise InvalidWorkshopReferenceError(f"No strategy_candidates row with id={candidate_id!r}")
    for discovery_id in discovery_ids:
        if not discovery_exists(conn, discovery_id):
            raise InvalidWorkshopReferenceError(f"No scout_discoveries row with id={discovery_id!r}")

    repo = WorkshopRepository(conn)
    row, created = repo.open(candidate_id)
    if created:
        for discovery_id in discovery_ids:
            repo.link_discovery(row["id"], discovery_id)
    resolved_discovery_ids = repo.list_discovery_ids(str(row["id"]))
    _sync_workspace_best_effort(conn, str(row["id"]))
    return workshop_row_to_domain(row, resolved_discovery_ids)


def get_workshop(conn: psycopg.Connection, workshop_id: str) -> StrategyWorkshop:
    repo = WorkshopRepository(conn)
    row = repo.get_row(workshop_id)
    if row is None:
        raise WorkshopNotFoundError(f"No strategy_workshops row with id={workshop_id!r}")
    return workshop_row_to_domain(row, repo.list_discovery_ids(workshop_id))


def _require_active(workshop: StrategyWorkshop) -> None:
    if not workshop.is_active:
        raise WorkshopNotActiveError(
            f"Workshop {workshop.workshop_id!r} is {workshop.status.value}, not ACTIVE"
        )


# --- questions ---------------------------------------------------------------


def create_question(
    conn: psycopg.Connection, workshop_id: str, *, semantic_subject: str, question_text: str,
    rationale: str | None = None, origin: QuestionOrigin = QuestionOrigin.HUMAN,
) -> WorkshopQuestion:
    workshop = get_workshop(conn, workshop_id)
    _require_active(workshop)
    question = WorkshopQuestion(
        question_id=new_id(), workshop_id=workshop_id, semantic_subject=semantic_subject,
        question_text=question_text, rationale=rationale, origin=origin,
    )
    WorkshopQuestionRepository(conn).create(question)
    _sync_workspace_best_effort(conn, workshop_id)
    return question


def list_questions(conn: psycopg.Connection, workshop_id: str) -> list[WorkshopQuestion]:
    get_workshop(conn, workshop_id)  # 404s if the workshop itself does not exist
    rows = WorkshopQuestionRepository(conn).list_for_workshop(workshop_id)
    return [question_row_to_domain(r) for r in rows]


def resolve_question(
    conn: psycopg.Connection, workshop_id: str, question_id: str, *,
    resolution: QuestionStatus, accepted_decision_id: str | None = None,
) -> WorkshopQuestion:
    if resolution not in (QuestionStatus.RESOLVED, QuestionStatus.WITHDRAWN):
        raise WorkshopNotActiveError(f"resolution must be RESOLVED or WITHDRAWN, got {resolution!r}")
    workshop = get_workshop(conn, workshop_id)
    _require_active(workshop)
    question_repo = WorkshopQuestionRepository(conn)
    existing = question_repo.get_row(workshop_id, question_id)
    if existing is None:
        raise CrossWorkshopReferenceError(
            f"question_id={question_id!r} does not belong to workshop_id={workshop_id!r}"
        )
    if accepted_decision_id is not None:
        decision = WorkshopDecisionRepository(conn).get_row(workshop_id, accepted_decision_id)
        if decision is None:
            raise CrossWorkshopReferenceError(
                f"accepted_decision_id={accepted_decision_id!r} does not belong to "
                f"workshop_id={workshop_id!r}"
            )
    row = question_repo.resolve(
        workshop_id, question_id, status=resolution, accepted_decision_id=accepted_decision_id,
        resolved_at_utc=datetime.now(UTC),
    )
    if row is None:
        raise WorkshopNotActiveError(f"question_id={question_id!r} is not OPEN")
    _sync_workspace_best_effort(conn, workshop_id)
    return question_row_to_domain(row)


# --- decisions ----------------------------------------------------------------


def create_decision(
    conn: psycopg.Connection, workshop_id: str, *, proposed_value: object, origin: RuleOrigin,
    actor: str, affected_semantic_paths: tuple[str, ...] = (), related_question_id: str | None = None,
    rationale: str | None = None,
) -> WorkshopDecision:
    workshop = get_workshop(conn, workshop_id)
    _require_active(workshop)
    if (
        related_question_id is not None
        and WorkshopQuestionRepository(conn).get_row(workshop_id, related_question_id) is None
    ):
        raise CrossWorkshopReferenceError(
            f"related_question_id={related_question_id!r} does not belong to "
            f"workshop_id={workshop_id!r}"
        )
    decision = WorkshopDecision(
        decision_id=new_id(), workshop_id=workshop_id, proposed_value=proposed_value, origin=origin,
        actor=actor, affected_semantic_paths=tuple(affected_semantic_paths),
        related_question_id=related_question_id, rationale=rationale,
    )
    WorkshopDecisionRepository(conn).create(decision)
    _sync_workspace_best_effort(conn, workshop_id)
    return decision


def list_decisions(conn: psycopg.Connection, workshop_id: str) -> list[WorkshopDecision]:
    get_workshop(conn, workshop_id)
    rows = WorkshopDecisionRepository(conn).list_for_workshop(workshop_id)
    return [decision_row_to_domain(r) for r in rows]


def _get_decision_or_raise(conn: psycopg.Connection, workshop_id: str, decision_id: str) -> dict:
    row = WorkshopDecisionRepository(conn).get_row(workshop_id, decision_id)
    if row is None:
        raise CrossWorkshopReferenceError(
            f"decision_id={decision_id!r} does not belong to workshop_id={workshop_id!r}"
        )
    return row


def accept_decision(conn: psycopg.Connection, workshop_id: str, decision_id: str) -> WorkshopDecision:
    workshop = get_workshop(conn, workshop_id)
    _require_active(workshop)
    _get_decision_or_raise(conn, workshop_id, decision_id)
    row = WorkshopDecisionRepository(conn).set_acceptance_state(
        workshop_id, decision_id, from_states=("PROPOSED",), new_state=DecisionAcceptanceState.ACCEPTED,
    )
    if row is None:
        raise WorkshopNotActiveError(f"decision_id={decision_id!r} is not PROPOSED")
    _sync_workspace_best_effort(conn, workshop_id)
    return decision_row_to_domain(row)


def reject_decision(
    conn: psycopg.Connection, workshop_id: str, decision_id: str, *, rationale: str | None = None
) -> WorkshopDecision:
    workshop = get_workshop(conn, workshop_id)
    _require_active(workshop)
    _get_decision_or_raise(conn, workshop_id, decision_id)
    row = WorkshopDecisionRepository(conn).set_acceptance_state(
        workshop_id, decision_id, from_states=("PROPOSED",), new_state=DecisionAcceptanceState.REJECTED,
    )
    if row is None:
        raise WorkshopNotActiveError(f"decision_id={decision_id!r} is not PROPOSED")
    _sync_workspace_best_effort(conn, workshop_id)
    return decision_row_to_domain(row)


def supersede_decision(
    conn: psycopg.Connection, workshop_id: str, decision_id: str, *, proposed_value: object, actor: str,
    affected_semantic_paths: tuple[str, ...] | None = None, rationale: str | None = None,
) -> WorkshopDecision:
    workshop = get_workshop(conn, workshop_id)
    _require_active(workshop)
    old_row = _get_decision_or_raise(conn, workshop_id, decision_id)
    new_decision = WorkshopDecision(
        decision_id=new_id(), workshop_id=workshop_id, proposed_value=proposed_value,
        origin=RuleOrigin(old_row["origin"]), actor=actor,
        affected_semantic_paths=tuple(affected_semantic_paths or old_row.get("affected_semantic_paths") or ()),
        related_question_id=str(old_row["related_question_id"]) if old_row.get("related_question_id") else None,
        rationale=rationale,
    )
    WorkshopDecisionRepository(conn).supersede(workshop_id, decision_id, new_decision)
    _sync_workspace_best_effort(conn, workshop_id)
    return new_decision


# --- draft --------------------------------------------------------------------


def get_draft(conn: psycopg.Connection, workshop_id: str) -> tuple[SpecificationDraft | None, int | None]:
    workshop = get_workshop(conn, workshop_id)
    if workshop.current_draft_id is None:
        return None, None
    row = SpecificationDraftRepository(conn).get_row(workshop.current_draft_id)
    if row is None:  # pragma: no cover - defensive; FK guarantees the draft row exists
        return None, None
    return deserialize_specification_draft(row["draft_payload"]), int(row["revision"])


def update_draft(
    conn: psycopg.Connection, workshop_id: str, *, expected_revision: int, draft_document: dict,
    schema_semantic_version: str | None = None,
) -> tuple[SpecificationDraft, int]:
    """Creates (expected_revision == 0, no draft yet) or updates (>=1, an
    existing draft at exactly that revision) the Workshop's current
    SpecificationDraft. Deliberately NEVER trusts a caller-supplied
    `draft_id`/`candidate_id` inside `draft_document` -- both are always
    forced to the Workshop's own identity before deserialization, so a
    caller cannot point one Workshop's draft edit at another Workshop's
    (or another candidate's) draft by ID substitution. Deserialization
    stays entirely within `darwin.specification.serialization`'s existing
    closed typed model -- an unrecognised node/operator/schema-version
    raises the same typed error it always would."""
    workshop = get_workshop(conn, workshop_id)
    _require_active(workshop)
    repo = SpecificationDraftRepository(conn)

    if workshop.current_draft_id is None:
        if expected_revision != 0:
            raise WorkshopHasNoDraftError(
                f"Workshop {workshop_id!r} has no draft yet -- expected_revision must be 0 to create one, "
                f"got {expected_revision!r}"
            )
        draft_id = new_id()
        document = dict(draft_document)
        document["draft_id"] = draft_id
        document["candidate_id"] = workshop.candidate_id
        if schema_semantic_version:
            document["schema_semantic_version"] = schema_semantic_version
        draft = deserialize_specification_draft(document)
        repo.create(draft)
        WorkshopRepository(conn).set_current_draft(workshop_id, draft_id)
        _sync_workspace_best_effort(conn, workshop_id)
        return draft, 1

    document = dict(draft_document)
    document["draft_id"] = workshop.current_draft_id
    document["candidate_id"] = workshop.candidate_id
    draft = deserialize_specification_draft(document)
    new_revision = repo.update_with_expected_revision(workshop.current_draft_id, expected_revision, draft)
    _sync_workspace_best_effort(conn, workshop_id)
    return draft, new_revision


def validate_workshop_draft(conn: psycopg.Connection, workshop_id: str) -> ValidationOutcome:
    """Calls `darwin.specification.validation.validate_draft` directly --
    never reimplements validation logic (PID-004B directive). Read-only:
    does not write a `specification_validation_records` row (that
    durable record is written by the finalisation transaction itself,
    which this Workshop layer never duplicates before an actual
    finalisation attempt)."""
    draft, _ = get_draft(conn, workshop_id)
    if draft is None:
        raise WorkshopHasNoDraftError(f"Workshop {workshop_id!r} has no draft to validate yet")
    return validate_draft(draft)


# --- finalisation -------------------------------------------------------------


def finalise_workshop(
    conn: psycopg.Connection, workshop_id: str, *, expected_revision: int,
    strategy_version_id: str | None = None, version_label: str | None = None,
) -> FinalisationOutcome:
    """The Workshop-layer finalisation boundary. Calls the EXISTING, already
    governed `darwin.research_store.specification_finalisation.
    finalise_specification_draft` transaction boundary -- never
    reimplements validation/finalisation. On a VALID outcome, additionally
    marks the Workshop FINALISED with its `finalised_strategy_version_id`
    set, using the SAME `conn`/transaction -- the caller's enclosing
    `darwin.research_store.db.connection(...)` context manager is what
    commits both writes atomically or rolls back both together on any
    exception (mirrors `finalise_specification_draft`'s own discipline of
    never calling commit/rollback itself)."""
    workshop = get_workshop(conn, workshop_id)
    if workshop.status == WorkshopStatus.FINALISED:
        # Idempotent retry: re-run the (also idempotent)
        # finalise_specification_draft against the same draft/revision and
        # return its result as-is -- never a second Workshop-level side
        # effect, never an error for a genuine repeat of an
        # already-successful finalisation.
        if workshop.current_draft_id is None:  # pragma: no cover - defensive
            raise WorkshopHasNoDraftError(f"Workshop {workshop_id!r} is FINALISED but has no current_draft_id")
        return finalise_specification_draft(
            conn, draft_id=workshop.current_draft_id, expected_revision=expected_revision,
            strategy_version_id=strategy_version_id, version_label=version_label,
        )
    _require_active(workshop)
    if workshop.current_draft_id is None:
        raise WorkshopHasNoDraftError(f"Workshop {workshop_id!r} has no draft to finalise yet")

    outcome = finalise_specification_draft(
        conn, draft_id=workshop.current_draft_id, expected_revision=expected_revision,
        strategy_version_id=strategy_version_id, version_label=version_label,
    )
    if outcome.strategy_version is not None:
        WorkshopRepository(conn).mark_finalised(workshop_id, outcome.strategy_version.strategy_version_id)
    _sync_workspace_best_effort(conn, workshop_id)
    return outcome


# --- readiness (PID-004 sec26-sec28; Workshop UI enablement) -----------------
#
# Genuine gap found while building ARENA's Workshop Readiness panel: PID-004A
# already defines `DataReadinessAssessment`/`DataReadinessAssessmentRepository`
# in full (`darwin.specification.readiness` / `.research_store.
# specification_repositories`), but nothing anywhere -- not PID-004B's own
# workshop routes, not `darwin.app` -- ever exposed them over HTTP or ever
# called `assess_readiness` outside tests/fixtures. Deliberately narrow: one
# read (what is the latest assessment, if any), one deliberate write action
# (assess now) -- never automatic, never run inside finalise_workshop's own
# transaction (mirrors `darwin.research_store.specification_finalisation`'s
# own documented separation: "readiness is assessed afterwards,
# separately").


def get_readiness(conn: psycopg.Connection, workshop_id: str) -> dict:
    """The latest `DataReadinessAssessment` for this Workshop's finalised
    StrategyVersion, or an honest `UNASSESSED` state -- never fabricated.
    `UNASSESSED` is the correct, structural answer (not a placeholder) for
    every ACTIVE Workshop: `DataReadinessAssessment` is defined against a
    `strategy_version_id` only (PID-004 sec26), and no StrategyVersion
    exists before finalisation."""
    workshop = get_workshop(conn, workshop_id)
    if workshop.finalised_strategy_version_id is None:
        return {"state": "UNASSESSED", "assessed_at_utc": None, "requirements": ()}
    assessment_repo = DataReadinessAssessmentRepository(conn)
    assessments = assessment_repo.list_for_strategy_version(workshop.finalised_strategy_version_id)
    if not assessments:
        return {"state": "UNASSESSED", "assessed_at_utc": None, "requirements": ()}
    latest = assessments[-1]  # list_for_strategy_version orders oldest-first; last is most recent
    per_requirement = assessment_repo.list_per_requirement(str(latest["id"]))
    return {
        "state": latest["overall_state"],
        "assessed_at_utc": latest["assessed_at_utc"],
        "requirements": tuple(
            {
                "requirement_id": r["requirement_id"],
                "availability": r["availability"],
                "reason": r.get("reason"),
            }
            for r in per_requirement
        ),
    }


def evaluate_data_requirement_availability(
    requirement: DataRequirement, datasets: list[dict]
) -> tuple[PerRequirementAvailability, str | None]:
    """The one, shared, genuinely-computed-from-real-state per-requirement
    availability check (PID-004 sec26-28) -- extracted so it can be reused
    by BOTH `assess_workshop_readiness` (below, against a FINALISED
    StrategyVersion's requirements) AND PID-004C's `DraftCapabilityView`
    (`darwin.workshop.mendel_context`, against a pre-finalisation DRAFT's
    requirements) without either duplicating the HERMES/`MarketDataset`
    lookup logic (PID-004C sec8.3: "reuse them through the same bounded
    context builder... do not build a new, separate capability registry").

    * a `HERMES_CANONICAL_MARKET` requirement is AVAILABLE if a real
      `MarketDataset` row exists for one of the requirement's applicable
      instruments, at its timeframe, with at least its required historical
      depth (bar count) -- else UNAVAILABLE with the honest reason.
    * any OTHER `authority_class` (e.g. `OPTIONS_AUTHORITY`) is
      `AUTHORITY_NOT_ONBOARDED` -- truthfully: this DARWIN build has no
      data-authority integration for anything beyond HERMES's own
      canonical market data today.
    """
    if requirement.authority_class != DataAuthorityClass.HERMES_CANONICAL_MARKET:
        return (
            PerRequirementAvailability.AUTHORITY_NOT_ONBOARDED,
            (
                f"no data authority integration exists for {requirement.authority_class.value} "
                f"in this DARWIN build"
            ),
        )
    depth = requirement.required_historical_depth
    for dataset in datasets:
        if dataset["instrument"] not in requirement.instrument_applicability:
            continue
        if requirement.timeframe is not None and dataset["timeframe"] != requirement.timeframe.code:
            continue
        if depth.unit == HistoricalDepthUnit.BARS and int(dataset["record_count"]) < depth.count:
            continue
        return (PerRequirementAvailability.AVAILABLE, None)
    return (
        PerRequirementAvailability.UNAVAILABLE,
        (
            f"no MarketDataset found covering {list(requirement.instrument_applicability)} at "
            f"{requirement.timeframe.code if requirement.timeframe else 'any timeframe'} with "
            f"sufficient depth"
        ),
    )


def assess_workshop_readiness(conn: psycopg.Connection, workshop_id: str) -> dict:
    """Deliberate, explicit readiness assessment against a FINALISED
    Workshop's StrategyVersion -- a human-triggered action, never automatic.
    Genuinely computed from real DARWIN state, never fabricated for
    display (see `evaluate_data_requirement_availability` above for the
    actual per-requirement logic).

    Writes one new, append-only `DataReadinessAssessment` (PID-004
    sec27/sec28: "reassess readiness, not rediscover/rewrite" -- never
    updates a prior assessment in place) and returns `get_readiness`'s own
    dict shape."""
    workshop = get_workshop(conn, workshop_id)
    if workshop.finalised_strategy_version_id is None:
        raise WorkshopHasNoDraftError(
            f"Workshop {workshop_id!r} has no finalised StrategyVersion to assess readiness against yet"
        )
    version_row = SpecificationVersionRepository(conn).get_row(workshop.finalised_strategy_version_id)
    version = deserialize_strategy_version(version_row["full_payload"])
    dataset_repo = MarketDatasetRepository(conn)
    datasets = dataset_repo.list(limit=500)

    per_requirement: dict[str, tuple[PerRequirementAvailability, str | None]] = {
        requirement.requirement_id: evaluate_data_requirement_availability(requirement, datasets)
        for requirement in version.data_requirements
    }

    assessment = assess_readiness(
        assessment_id=new_id(),
        strategy_version_id=version.strategy_version_id,
        mandatory_requirement_ids={r.requirement_id for r in version.data_requirements if r.mandatory},
        per_requirement=per_requirement,
        assessed_at_utc=datetime.now(UTC),
    )
    DataReadinessAssessmentRepository(conn).create(assessment)
    return get_readiness(conn, workshop_id)
