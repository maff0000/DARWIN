"""PID-004B Strategy Workshop -- DB-agnostic domain types (docs/pids/
PID-004-SPECIFICATION-WORKSHOP.md sec45/sec49/sec50).

Four genuinely distinct concerns, never collapsed into one status-flagged
object (the same discipline `darwin.specification.domain` already applies
to StrategyCandidate/SpecificationDraft/StrategyVersion, extended here one
layer up):

- `StrategyWorkshop` -- the durable Workshop identity/lifecycle binding
  (never itself a SpecificationDraft/StrategyVersion).
- `WorkshopQuestion` -- unresolved ambiguity raised against a Workshop.
- `WorkshopDecision` -- a material, provenance-tagged resolution proposed
  against a Workshop -- NOT a `darwin.specification.provenance.
  ProvenanceRecord` (a decision only becomes one once its effect is
  actually applied to a SpecificationDraft through the existing
  draft-authoring API/repository).

This module never imports psycopg or anything SQL-specific --
`darwin.research_store.workshop_repositories` is the only place that
translates these objects to/from Postgres rows (mirrors
`darwin.specification`/`darwin.research_store.specification_repositories`'s
own layering).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from darwin.specification.provenance import RuleOrigin
from darwin.workshop.errors import WorkshopError


class WorkshopStatus(StrEnum):
    """Operational lifecycle ONLY (PID-004 sec49) -- never conflated with
    semantic validation/readiness. A Workshop may legitimately be ACTIVE
    while its current draft is STRATEGY_NOT_SUFFICIENTLY_DEFINED, or ACTIVE
    while VALID-but-DATA_BLOCKED; those are orthogonal axes recorded
    elsewhere (specification_validation_records / data_readiness_
    assessments), never folded into this enum."""

    ACTIVE = "ACTIVE"
    FINALISED = "FINALISED"
    ABANDONED = "ABANDONED"


class QuestionStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    WITHDRAWN = "WITHDRAWN"


class QuestionOrigin(StrEnum):
    """Closed vocabulary, deliberately holding exactly one value today.
    PID-004B does not build MENDEL (PID-004 sec46/sec48) -- this enum is
    the forward seam a future MENDEL integration would extend (add a new
    member + widen migration 0009's CHECK constraint in its own reviewed
    migration), never a free-text column standing in for a real
    vocabulary."""

    HUMAN = "HUMAN"


class DecisionAcceptanceState(StrEnum):
    """A Workshop decision's OWN acceptance state -- deliberately a
    separate closed vocabulary from `darwin.specification.provenance.
    RuleAcceptanceState` (PROPOSED/ACCEPTED_SPECIFICATION_RULE/REJECTED/
    SUPERSEDED). A WorkshopDecision is not a ProvenanceRecord; it only
    becomes the origin of one once a human explicitly applies its effect
    to a SpecificationDraft (which mints its own ProvenanceRecord there,
    still carrying the same `origin` this decision recorded)."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class StrategyWorkshop:
    """The durable Workshop identity (PID-004 sec49). `discovery_ids` is
    the Workshop's own resolved view of `strategy_workshop_discovery_links`
    -- zero, one, or many real SCOUT `scout_discoveries.id` values, or
    empty for a Workshop opened against a controlled fixture with no real
    Discovery (legitimate -- PID-004B directive)."""

    workshop_id: str
    candidate_id: str
    status: WorkshopStatus
    discovery_ids: tuple[str, ...] = ()
    current_draft_id: str | None = None
    finalised_strategy_version_id: str | None = None
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.workshop_id or not self.workshop_id.strip():
            raise WorkshopError("StrategyWorkshop requires a non-empty workshop_id")
        if not self.candidate_id or not self.candidate_id.strip():
            raise WorkshopError("StrategyWorkshop requires a non-empty candidate_id")
        if self.status == WorkshopStatus.FINALISED and not self.finalised_strategy_version_id:
            raise WorkshopError("A FINALISED StrategyWorkshop must carry finalised_strategy_version_id")
        if self.status != WorkshopStatus.FINALISED and self.finalised_strategy_version_id:
            raise WorkshopError(
                f"A {self.status.value} StrategyWorkshop must not carry finalised_strategy_version_id"
            )

    @property
    def is_active(self) -> bool:
        return self.status == WorkshopStatus.ACTIVE


@dataclass(frozen=True)
class WorkshopQuestion:
    """Unresolved ambiguity raised against a Workshop (PID-004 sec50).
    `origin` is deliberately narrower than `WorkshopDecision.origin` --
    today only a human raises a question (see `QuestionOrigin`)."""

    question_id: str
    workshop_id: str
    semantic_subject: str
    question_text: str
    status: QuestionStatus = QuestionStatus.OPEN
    origin: QuestionOrigin = QuestionOrigin.HUMAN
    rationale: str | None = None
    accepted_decision_id: str | None = None
    created_at_utc: datetime | None = None
    resolved_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.question_id or not self.question_id.strip():
            raise WorkshopError("WorkshopQuestion requires a non-empty question_id")
        if not self.workshop_id or not self.workshop_id.strip():
            raise WorkshopError("WorkshopQuestion requires a non-empty workshop_id")
        if not self.question_text or not self.question_text.strip():
            raise WorkshopError("WorkshopQuestion requires non-empty question_text")
        if not self.semantic_subject or not self.semantic_subject.strip():
            raise WorkshopError("WorkshopQuestion requires a non-empty semantic_subject")
        if self.status == QuestionStatus.OPEN and self.resolved_at_utc is not None:
            raise WorkshopError("An OPEN WorkshopQuestion must not carry resolved_at_utc")
        if self.status != QuestionStatus.OPEN and self.resolved_at_utc is None:
            raise WorkshopError(f"A {self.status.value} WorkshopQuestion must carry resolved_at_utc")


@dataclass(frozen=True)
class WorkshopDecision:
    """A material, provenance-tagged Workshop decision (PID-004 sec50).
    `origin` reuses `darwin.specification.provenance.RuleOrigin` EXACTLY
    (PID-004B directive: "reuse the exact same closed vocabulary PID-004A's
    provenance model already defines, don't invent a second one").
    Append-only: a changed decision is a NEW `WorkshopDecision` instance
    whose `superseded_by_decision_id`-pointing predecessor is never
    mutated in place -- see `darwin.research_store.workshop_repositories.
    WorkshopDecisionRepository.supersede`, and migration 0009's own
    `trg_workshop_decisions_content_immutable` DB trigger, which enforces
    this even if application code somehow tried to bypass it."""

    decision_id: str
    workshop_id: str
    proposed_value: object
    origin: RuleOrigin
    actor: str
    acceptance_state: DecisionAcceptanceState = DecisionAcceptanceState.PROPOSED
    affected_semantic_paths: tuple[str, ...] = ()
    related_question_id: str | None = None
    rationale: str | None = None
    created_at_utc: datetime | None = None
    superseded_by_decision_id: str | None = None

    def __post_init__(self) -> None:
        if not self.decision_id or not self.decision_id.strip():
            raise WorkshopError("WorkshopDecision requires a non-empty decision_id")
        if not self.workshop_id or not self.workshop_id.strip():
            raise WorkshopError("WorkshopDecision requires a non-empty workshop_id")
        if not self.actor or not self.actor.strip():
            raise WorkshopError("WorkshopDecision requires a non-empty actor")
        if (
            self.superseded_by_decision_id is not None
            and self.acceptance_state != DecisionAcceptanceState.SUPERSEDED
        ):
            raise WorkshopError(
                "A WorkshopDecision with superseded_by_decision_id set must have "
                "acceptance_state == SUPERSEDED"
            )
