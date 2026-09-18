"""PID-004C MENDEL Workshop Assistant -- DB-agnostic domain types.

Mirrors `darwin.workshop.domain`'s discipline exactly: this module never
imports psycopg or anything SQL-specific -- `darwin.research_store.
mendel_repositories` is the only place that translates these objects
to/from Postgres rows.

Two genuinely distinct concerns (PID-004C sec6):

- `MendelRun` -- one bounded invocation of the MENDEL specialist against
  one Workshop (audit/reproducibility record -- never strategy
  semantics).
- `MendelProposal` -- the PROPOSED-state staging record MENDEL produces.
  NOT a `WorkshopQuestion`/`WorkshopDecision` -- only human acceptance
  causes DARWIN to create one of those existing, already-governed
  records (PID-004C sec6.1).

The `ProposalClass -> ProposalCategory` mapping (PID-004C sec6.4) is the
single source of truth this module, the migration's CHECK constraint, and
`darwin.workshop.mendel_service`'s acceptance dispatch must all agree
with -- never re-derived ad hoc in more than one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Self

from darwin.workshop.mendel_errors import (
    MendelProposalClassCategoryMismatchError,
    MendelRunError,
)


class ProposalClass(StrEnum):
    """Closed vocabulary (PID-004C sec6.4) -- extensible only by explicit
    code/version change, never a free-text value."""

    ASK_QUESTION = "ASK_QUESTION"
    SEMANTIC_CHANGE = "SEMANTIC_CHANGE"
    PARAMETER_CHANGE = "PARAMETER_CHANGE"
    DATA_REQUIREMENT = "DATA_REQUIREMENT"
    THESIS_CHANGE = "THESIS_CHANGE"
    POLICY_CLASSIFICATION = "POLICY_CLASSIFICATION"
    INSTRUMENT_CLARIFICATION = "INSTRUMENT_CLARIFICATION"
    TIMEFRAME_CLARIFICATION = "TIMEFRAME_CLARIFICATION"
    MATERIAL_CONCERN = "MATERIAL_CONCERN"


class ProposalCategory(StrEnum):
    """The three behavioural categories (PID-004C sec6.2)."""

    QUESTION = "QUESTION"
    ADVISORY = "ADVISORY"
    DRAFT_MUTATING = "DRAFT_MUTATING"


# The single, fixed source of truth for PID-004C sec6.4's table. The
# migration's structural CHECK constraint (0011_mendel_workshop_assistant.sql)
# is hand-written to mirror this EXACT mapping -- see
# tests/integration/test_mendel_migration.py's negative-test proof that the
# database itself refuses any other pairing, independent of this dict.
PROPOSAL_CLASS_CATEGORY: dict[ProposalClass, ProposalCategory] = {
    ProposalClass.ASK_QUESTION: ProposalCategory.QUESTION,
    ProposalClass.MATERIAL_CONCERN: ProposalCategory.ADVISORY,
    ProposalClass.SEMANTIC_CHANGE: ProposalCategory.DRAFT_MUTATING,
    ProposalClass.PARAMETER_CHANGE: ProposalCategory.DRAFT_MUTATING,
    ProposalClass.DATA_REQUIREMENT: ProposalCategory.DRAFT_MUTATING,
    ProposalClass.THESIS_CHANGE: ProposalCategory.DRAFT_MUTATING,
    ProposalClass.POLICY_CLASSIFICATION: ProposalCategory.DRAFT_MUTATING,
    ProposalClass.INSTRUMENT_CLARIFICATION: ProposalCategory.DRAFT_MUTATING,
    ProposalClass.TIMEFRAME_CLARIFICATION: ProposalCategory.DRAFT_MUTATING,
}

assert set(PROPOSAL_CLASS_CATEGORY) == set(ProposalClass), (
    "PROPOSAL_CLASS_CATEGORY must cover every ProposalClass member -- a class with no "
    "category mapping is a structural bug, never a legitimate 'undecided' state"
)


def category_for_class(proposal_class: ProposalClass) -> ProposalCategory:
    return PROPOSAL_CLASS_CATEGORY[proposal_class]


class ProposalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class InvocationPurpose(StrEnum):
    """Closed, versioned bounded-task vocabulary (PID-004C sec11.1.1).
    Never a generic free-text prompt -- an addition here is a deliberate
    code/version change."""

    ANALYSE_AMBIGUITY = "ANALYSE_AMBIGUITY"
    REVIEW_DRAFT = "REVIEW_DRAFT"
    SUGGEST_NEXT_QUESTIONS = "SUGGEST_NEXT_QUESTIONS"
    EXPLAIN_VALIDATION = "EXPLAIN_VALIDATION"
    PROPOSE_DATA_REQUIREMENTS = "PROPOSE_DATA_REQUIREMENTS"
    INTERPRET_RULE = "INTERPRET_RULE"


class _NoDraftYetType:
    """A dedicated, typed sentinel (PID-004C sec7.5) -- deliberately its
    own class (not `None`, not `0`, not a string) so it can never collide
    with a genuine integer draft revision or be silently coerced into one
    by `==`/truthiness/`json.dumps`. Singleton by construction (`__new__`
    always returns the same instance) purely so `NO_DRAFT_YET is
    NO_DRAFT_YET` holds everywhere -- equality below does not depend on
    identity, only on type, so a second accidental instantiation (there is
    no code path that does this, but defence in depth) would still compare
    equal.
    """

    _instance: Self | None = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NO_DRAFT_YET"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _NoDraftYetType)

    def __hash__(self) -> int:
        return hash("darwin.workshop.mendel_domain.NO_DRAFT_YET")


#: The one canonical sentinel instance -- imported everywhere a
#: `generated_against_draft_revision`/current-draft-binding value is
#: produced or consumed. Never re-instantiated ad hoc.
NO_DRAFT_YET = _NoDraftYetType()

#: A draft-revision binding is either a real, positive revision number or
#: the explicit `NO_DRAFT_YET` sentinel -- never an ambiguous `None`/`0`.
DraftRevisionBinding = int | _NoDraftYetType


def is_stale_binding(
    generated_against: DraftRevisionBinding, current_binding: DraftRevisionBinding
) -> bool:
    """PID-004C sec7.5's simple bound-to-revision staleness rule, applied
    uniformly across all three behavioural categories (PID-004C sec7.5's
    directive that even a QUESTION/ADVISORY proposal generated before any
    draft existed must be checked the same way): a proposal is stale
    exactly when the binding it was generated against no longer matches
    the Workshop's current binding -- comparing `NO_DRAFT_YET` to
    `NO_DRAFT_YET` is never stale; comparing `NO_DRAFT_YET` to any real
    revision (a draft has since been created) is always stale; comparing
    two real revisions uses ordinary integer equality."""
    return generated_against != current_binding


@dataclass(frozen=True)
class MendelRun:
    """One bounded MENDEL invocation (PID-004C sec10.1). `completed_at_utc`
    is `None` iff `status == RUNNING` -- enforced below so a terminal run
    can never be missing its completion timestamp and a still-RUNNING run
    can never claim one prematurely."""

    run_id: str
    workshop_id: str
    purpose: InvocationPurpose
    focus_text: str | None
    context_schema_version: str
    context_fingerprint: str
    provider_identity: str
    status: RunStatus
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    error_classification: str | None = None

    def __post_init__(self) -> None:
        if not self.run_id or not self.run_id.strip():
            raise MendelRunError("MendelRun requires a non-empty run_id")
        if not self.workshop_id or not self.workshop_id.strip():
            raise MendelRunError("MendelRun requires a non-empty workshop_id")
        if not self.context_schema_version or not self.context_schema_version.strip():
            raise MendelRunError("MendelRun requires a non-empty context_schema_version")
        if not self.context_fingerprint or not self.context_fingerprint.strip():
            raise MendelRunError("MendelRun requires a non-empty context_fingerprint")
        if not self.provider_identity or not self.provider_identity.strip():
            raise MendelRunError("MendelRun requires a non-empty provider_identity")
        if self.status == RunStatus.RUNNING and self.completed_at_utc is not None:
            raise MendelRunError("A RUNNING MendelRun must not carry completed_at_utc")
        if self.status != RunStatus.RUNNING and self.completed_at_utc is None:
            raise MendelRunError(f"A {self.status.value} MendelRun must carry completed_at_utc")

    @property
    def is_terminal(self) -> bool:
        return self.status != RunStatus.RUNNING


@dataclass(frozen=True)
class MendelProposal:
    """One PROPOSED-state staging record (PID-004C sec6.1/sec10.2).
    `proposal_category` is persisted explicitly (never re-derived at read
    time) but is validated here to agree with `PROPOSAL_CLASS_CATEGORY`
    for `proposal_class` -- constructing a `MendelProposal` with a
    disagreeing pair is a construction-time error, never silently
    accepted (PID-004C sec6.4: "never inferred at runtime from its payload
    shape; it is fixed by its class")."""

    proposal_id: str
    run_id: str
    workshop_id: str
    proposal_class: ProposalClass
    proposal_category: ProposalCategory
    proposal_schema_version: str
    payload: dict
    rationale: str
    affected_semantic_paths: tuple[str, ...]
    generated_against_draft_revision: DraftRevisionBinding
    status: ProposalStatus = ProposalStatus.PROPOSED
    created_at_utc: datetime | None = None
    resolved_at_utc: datetime | None = None
    resulting_question_id: str | None = None
    resulting_decision_id: str | None = None

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.proposal_id.strip():
            raise MendelRunError("MendelProposal requires a non-empty proposal_id")
        if not self.run_id or not self.run_id.strip():
            raise MendelRunError("MendelProposal requires a non-empty run_id")
        if not self.workshop_id or not self.workshop_id.strip():
            raise MendelRunError("MendelProposal requires a non-empty workshop_id")
        if not self.proposal_schema_version or not self.proposal_schema_version.strip():
            raise MendelRunError("MendelProposal requires a non-empty proposal_schema_version")
        if not self.rationale or not self.rationale.strip():
            raise MendelRunError("MendelProposal requires a non-empty rationale")
        expected_category = PROPOSAL_CLASS_CATEGORY[self.proposal_class]
        if self.proposal_category != expected_category:
            raise MendelProposalClassCategoryMismatchError(
                f"proposal_class={self.proposal_class.value!r} must carry "
                f"proposal_category={expected_category.value!r}, got {self.proposal_category.value!r}"
            )
        if self.status == ProposalStatus.PROPOSED and self.resolved_at_utc is not None:
            raise MendelRunError("A PROPOSED MendelProposal must not carry resolved_at_utc")
        if self.status != ProposalStatus.PROPOSED and self.resolved_at_utc is None:
            raise MendelRunError(f"A {self.status.value} MendelProposal must carry resolved_at_utc")
        if self.resulting_question_id is not None and self.proposal_category != ProposalCategory.QUESTION:
            raise MendelRunError("resulting_question_id may only be set for a QUESTION-category proposal")
        if self.resulting_decision_id is not None and self.proposal_category == ProposalCategory.QUESTION:
            raise MendelRunError("resulting_decision_id may never be set for a QUESTION-category proposal")
