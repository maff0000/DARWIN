"""PID-004B Strategy Workshop persistence (migration
0009_strategy_workshop.sql).

Plain parameterised SQL, no ORM -- same discipline as
`darwin.research_store.repositories`/`.specification_repositories`. This
module is the ONLY place that translates `darwin.workshop.domain`'s
DB-agnostic dataclasses to/from Postgres rows.

Every question/decision lookup that takes a resource id ALSO takes the
`workshop_id` it must belong to, and filters `WHERE id = %s AND
workshop_id = %s` -- the structural half of PID-004B's cross-workshop
ID-substitution defence (the other half is
`darwin.workshop.service`'s explicit belongs-to check before acting).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg

from darwin.core.identities import new_id
from darwin.workshop.domain import (
    DecisionAcceptanceState,
    QuestionOrigin,
    QuestionStatus,
    StrategyWorkshop,
    WorkshopDecision,
    WorkshopQuestion,
    WorkshopStatus,
)


def candidate_exists(conn: psycopg.Connection, candidate_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM strategy_candidates WHERE id = %s", (candidate_id,))
        return cur.fetchone() is not None


def discovery_exists(conn: psycopg.Connection, discovery_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM scout_discoveries WHERE id = %s", (discovery_id,))
        return cur.fetchone() is not None


def discovery_row(conn: psycopg.Connection, discovery_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM scout_discoveries WHERE id = %s", (discovery_id,))
        row = cur.fetchone()
        return dict(row) if row else None


class WorkshopRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def get_row(self, workshop_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM strategy_workshops WHERE id = %s", (workshop_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_active_for_candidate(self, candidate_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_workshops WHERE candidate_id = %s AND status = 'ACTIVE'",
                (candidate_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def open(self, candidate_id: str) -> tuple[dict, bool]:
        """Idempotent-open (PID-004B directive): attempts to INSERT a new
        ACTIVE workshop; migration 0009's partial unique index
        (`uq_strategy_workshops_active_per_candidate`) is the real,
        structural backstop -- `ON CONFLICT ... DO NOTHING` absorbs a
        concurrent racer hitting that same index, and this method then
        re-reads and returns whichever ACTIVE row actually exists.

        Returns `(row, created)` -- `created=False` means an ACTIVE
        workshop for this candidate already existed (this call is a pure,
        side-effect-free idempotent return, never a second workshop)."""
        workshop_id = new_id()
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_workshops (id, candidate_id, status)
                VALUES (%s, %s, 'ACTIVE')
                ON CONFLICT (candidate_id) WHERE status = 'ACTIVE' DO NOTHING
                RETURNING *
                """,
                (workshop_id, candidate_id),
            )
            row = cur.fetchone()
        if row is not None:
            return dict(row), True
        existing = self.get_active_for_candidate(candidate_id)
        if existing is None:  # pragma: no cover - structurally impossible: the conflict only fires
            # because a matching ACTIVE row already exists at the moment of the INSERT.
            raise RuntimeError(
                f"strategy_workshops open() conflicted for candidate_id={candidate_id!r} but no "
                f"existing ACTIVE row could be found -- this should be structurally impossible"
            )
        return existing, False

    def link_discovery(self, workshop_id: str, discovery_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_workshop_discovery_links (id, workshop_id, discovery_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (workshop_id, discovery_id) DO NOTHING
                """,
                (new_id(), workshop_id, discovery_id),
            )

    def list_discovery_ids(self, workshop_id: str) -> list[str]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT discovery_id FROM strategy_workshop_discovery_links WHERE workshop_id = %s "
                "ORDER BY created_at_utc",
                (workshop_id,),
            )
            return [str(r["discovery_id"]) for r in cur.fetchall()]

    def set_current_draft(self, workshop_id: str, draft_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE strategy_workshops SET current_draft_id = %s, updated_at_utc = now() WHERE id = %s",
                (draft_id, workshop_id),
            )

    def mark_finalised(self, workshop_id: str, strategy_version_id: str) -> dict:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE strategy_workshops
                SET status = 'FINALISED', finalised_strategy_version_id = %s, updated_at_utc = now()
                WHERE id = %s AND status = 'ACTIVE'
                RETURNING *
                """,
                (strategy_version_id, workshop_id),
            )
            row = cur.fetchone()
        if row is None:
            # Idempotent retry against an already-FINALISED workshop -- not
            # an error (mirrors specification_finalisation's own
            # idempotent-retry discipline); return current state as-is.
            return self.get_row(workshop_id)
        return dict(row)


def workshop_row_to_domain(row: dict, discovery_ids: list[str]) -> StrategyWorkshop:
    return StrategyWorkshop(
        workshop_id=str(row["id"]),
        candidate_id=str(row["candidate_id"]),
        status=WorkshopStatus(row["status"]),
        discovery_ids=tuple(discovery_ids),
        current_draft_id=str(row["current_draft_id"]) if row.get("current_draft_id") else None,
        finalised_strategy_version_id=(
            str(row["finalised_strategy_version_id"]) if row.get("finalised_strategy_version_id") else None
        ),
        created_at_utc=row.get("created_at_utc"),
        updated_at_utc=row.get("updated_at_utc"),
    )


class WorkshopQuestionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, question: WorkshopQuestion) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workshop_questions
                    (id, workshop_id, semantic_subject, question_text, rationale, status, origin)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    question.question_id, question.workshop_id, question.semantic_subject,
                    question.question_text, question.rationale, question.status.value,
                    question.origin.value,
                ),
            )

    def get_row(self, workshop_id: str, question_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM workshop_questions WHERE id = %s AND workshop_id = %s",
                (question_id, workshop_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_for_workshop(self, workshop_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM workshop_questions WHERE workshop_id = %s ORDER BY created_at_utc",
                (workshop_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def resolve(
        self, workshop_id: str, question_id: str, *, status: QuestionStatus,
        accepted_decision_id: str | None, resolved_at_utc: datetime | None = None,
    ) -> dict | None:
        resolved_at_utc = resolved_at_utc or datetime.now(UTC)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workshop_questions
                SET status = %s, resolved_at_utc = %s, accepted_decision_id = %s
                WHERE id = %s AND workshop_id = %s AND status = 'OPEN'
                RETURNING *
                """,
                (status.value, resolved_at_utc, accepted_decision_id, question_id, workshop_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def question_row_to_domain(row: dict) -> WorkshopQuestion:
    return WorkshopQuestion(
        question_id=str(row["id"]),
        workshop_id=str(row["workshop_id"]),
        semantic_subject=row["semantic_subject"],
        question_text=row["question_text"],
        status=QuestionStatus(row["status"]),
        origin=QuestionOrigin(row["origin"]),
        rationale=row.get("rationale"),
        accepted_decision_id=str(row["accepted_decision_id"]) if row.get("accepted_decision_id") else None,
        created_at_utc=row.get("created_at_utc"),
        resolved_at_utc=row.get("resolved_at_utc"),
    )


class WorkshopDecisionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, decision: WorkshopDecision) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workshop_decisions
                    (id, workshop_id, related_question_id, affected_semantic_paths, proposed_value,
                     origin, actor, acceptance_state, rationale)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    decision.decision_id, decision.workshop_id, decision.related_question_id,
                    json.dumps(list(decision.affected_semantic_paths)),
                    json.dumps(decision.proposed_value), decision.origin.value, decision.actor,
                    decision.acceptance_state.value, decision.rationale,
                ),
            )

    def get_row(self, workshop_id: str, decision_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM workshop_decisions WHERE id = %s AND workshop_id = %s",
                (decision_id, workshop_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_for_workshop(self, workshop_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM workshop_decisions WHERE workshop_id = %s ORDER BY created_at_utc",
                (workshop_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def set_acceptance_state(
        self, workshop_id: str, decision_id: str, *, from_states: tuple[str, ...], new_state: DecisionAcceptanceState,
    ) -> dict | None:
        """Narrow accept/reject transition -- only ever moves a decision
        OUT of one of `from_states` (normally just `PROPOSED`) into
        `new_state` (`ACCEPTED`/`REJECTED`). Never used for `SUPERSEDED`
        (see `supersede`, which additionally creates the replacement row
        in the same statement group)."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workshop_decisions
                SET acceptance_state = %s
                WHERE id = %s AND workshop_id = %s AND acceptance_state = ANY(%s)
                RETURNING *
                """,
                (new_state.value, decision_id, workshop_id, list(from_states)),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def supersede(self, workshop_id: str, old_decision_id: str, new_decision: WorkshopDecision) -> dict | None:
        """Append-only supersession (PID-004B directive): inserts
        `new_decision` as a genuinely NEW row, then marks the OLD row
        SUPERSEDED with `superseded_by_decision_id` pointing at it -- the
        only two columns migration 0009's
        `trg_workshop_decisions_content_immutable` trigger ever permits an
        UPDATE to touch. Both statements run against the same `conn` the
        caller already holds inside one enclosing transaction (this method
        never commits/rolls back itself)."""
        self.create(new_decision)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workshop_decisions
                SET acceptance_state = 'SUPERSEDED', superseded_by_decision_id = %s
                WHERE id = %s AND workshop_id = %s
                RETURNING *
                """,
                (new_decision.decision_id, old_decision_id, workshop_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def decision_row_to_domain(row: dict) -> WorkshopDecision:
    from darwin.specification.provenance import RuleOrigin

    return WorkshopDecision(
        decision_id=str(row["id"]),
        workshop_id=str(row["workshop_id"]),
        proposed_value=row["proposed_value"],
        origin=RuleOrigin(row["origin"]),
        actor=row["actor"],
        acceptance_state=DecisionAcceptanceState(row["acceptance_state"]),
        affected_semantic_paths=tuple(row.get("affected_semantic_paths") or ()),
        related_question_id=str(row["related_question_id"]) if row.get("related_question_id") else None,
        rationale=row.get("rationale"),
        created_at_utc=row.get("created_at_utc"),
        superseded_by_decision_id=(
            str(row["superseded_by_decision_id"]) if row.get("superseded_by_decision_id") else None
        ),
    )
