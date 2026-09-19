"""PID-004C MENDEL Workshop Assistant persistence (migration
0011_mendel_workshop_assistant.sql).

Plain parameterised SQL, no ORM -- same discipline as
`darwin.research_store.workshop_repositories`. This module is the ONLY
place that translates `darwin.workshop.mendel_domain`'s DB-agnostic
dataclasses to/from Postgres rows.

`MendelProposalRepository.get_row` (and every other proposal lookup that
takes a `proposal_id`) ALSO takes the `workshop_id` it must belong to and
filters `WHERE id = %s AND workshop_id = %s` -- the exact same
cross-workshop ID-substitution defence `darwin.research_store.
workshop_repositories` already established for questions/decisions
(PID-004C sec14: "no cross-Workshop access").
"""
from __future__ import annotations

import json
from datetime import datetime

import psycopg

from darwin.workshop.mendel_domain import (
    NO_DRAFT_YET,
    DraftRevisionBinding,
    InvocationPurpose,
    MendelProposal,
    MendelRun,
    ProposalCategory,
    ProposalClass,
    ProposalStatus,
    RunStatus,
)


def _binding_to_columns(binding: DraftRevisionBinding) -> tuple[int | None, bool]:
    if binding is NO_DRAFT_YET:
        return None, True
    return int(binding), False  # type: ignore[arg-type]


def _columns_to_binding(revision: int | None, no_draft_yet: bool) -> DraftRevisionBinding:
    if no_draft_yet:
        return NO_DRAFT_YET
    assert revision is not None  # guaranteed by the migration's own CHECK constraint
    return int(revision)


class MendelRunRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, run: MendelRun) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mendel_runs
                    (id, workshop_id, purpose, focus_text, context_schema_version, context_fingerprint,
                     provider_identity, status, started_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run.run_id, run.workshop_id, run.purpose.value, run.focus_text,
                    run.context_schema_version, run.context_fingerprint, run.provider_identity,
                    run.status.value, run.started_at_utc,
                ),
            )

    def get_row(self, workshop_id: str, run_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM mendel_runs WHERE id = %s AND workshop_id = %s", (run_id, workshop_id)
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_for_workshop(self, workshop_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM mendel_runs WHERE workshop_id = %s ORDER BY started_at_utc", (workshop_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def mark_terminal(
        self, workshop_id: str, run_id: str, *, status: RunStatus, completed_at_utc: datetime,
        error_classification: str | None = None,
    ) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE mendel_runs
                SET status = %s, completed_at_utc = %s, error_classification = %s
                WHERE id = %s AND workshop_id = %s AND status = 'RUNNING'
                RETURNING *
                """,
                (status.value, completed_at_utc, error_classification, run_id, workshop_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def run_row_to_domain(row: dict) -> MendelRun:
    return MendelRun(
        run_id=str(row["id"]),
        workshop_id=str(row["workshop_id"]),
        purpose=InvocationPurpose(row["purpose"]),
        focus_text=row.get("focus_text"),
        context_schema_version=row["context_schema_version"],
        context_fingerprint=row["context_fingerprint"],
        provider_identity=row["provider_identity"],
        status=RunStatus(row["status"]),
        started_at_utc=row["started_at_utc"],
        completed_at_utc=row.get("completed_at_utc"),
        error_classification=row.get("error_classification"),
    )


class MendelProposalRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, proposal: MendelProposal) -> None:
        revision, no_draft_yet = _binding_to_columns(proposal.generated_against_draft_revision)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mendel_proposals
                    (id, run_id, workshop_id, proposal_class, proposal_category, proposal_schema_version,
                     payload, rationale, affected_semantic_paths, generated_against_draft_revision,
                     generated_against_no_draft_yet, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    proposal.proposal_id, proposal.run_id, proposal.workshop_id,
                    proposal.proposal_class.value, proposal.proposal_category.value,
                    proposal.proposal_schema_version, json.dumps(proposal.payload), proposal.rationale,
                    json.dumps(list(proposal.affected_semantic_paths)), revision, no_draft_yet,
                    proposal.status.value,
                ),
            )

    def get_row(self, workshop_id: str, proposal_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM mendel_proposals WHERE id = %s AND workshop_id = %s",
                (proposal_id, workshop_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_for_workshop(self, workshop_id: str, *, status: ProposalStatus | None = None) -> list[dict]:
        with self._conn.cursor() as cur:
            if status is None:
                cur.execute(
                    "SELECT * FROM mendel_proposals WHERE workshop_id = %s ORDER BY created_at_utc",
                    (workshop_id,),
                )
            else:
                cur.execute(
                    "SELECT * FROM mendel_proposals WHERE workshop_id = %s AND status = %s "
                    "ORDER BY created_at_utc",
                    (workshop_id, status.value),
                )
            return [dict(r) for r in cur.fetchall()]

    def _set_status(
        self, workshop_id: str, proposal_id: str, *, new_status: ProposalStatus,
        resolved_at_utc: datetime, resulting_question_id: str | None = None,
        resulting_decision_id: str | None = None,
    ) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE mendel_proposals
                SET status = %s, resolved_at_utc = %s, resulting_question_id = %s,
                    resulting_decision_id = %s
                WHERE id = %s AND workshop_id = %s AND status = 'PROPOSED'
                RETURNING *
                """,
                (
                    new_status.value, resolved_at_utc, resulting_question_id, resulting_decision_id,
                    proposal_id, workshop_id,
                ),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def mark_stale(self, workshop_id: str, proposal_id: str, *, resolved_at_utc: datetime) -> dict | None:
        return self._set_status(
            workshop_id, proposal_id, new_status=ProposalStatus.STALE, resolved_at_utc=resolved_at_utc
        )

    def mark_accepted(
        self, workshop_id: str, proposal_id: str, *, resolved_at_utc: datetime,
        resulting_question_id: str | None = None, resulting_decision_id: str | None = None,
    ) -> dict | None:
        return self._set_status(
            workshop_id, proposal_id, new_status=ProposalStatus.ACCEPTED, resolved_at_utc=resolved_at_utc,
            resulting_question_id=resulting_question_id, resulting_decision_id=resulting_decision_id,
        )

    def mark_rejected(self, workshop_id: str, proposal_id: str, *, resolved_at_utc: datetime) -> dict | None:
        return self._set_status(
            workshop_id, proposal_id, new_status=ProposalStatus.REJECTED, resolved_at_utc=resolved_at_utc
        )


def proposal_row_to_domain(row: dict) -> MendelProposal:
    return MendelProposal(
        proposal_id=str(row["id"]),
        run_id=str(row["run_id"]),
        workshop_id=str(row["workshop_id"]),
        proposal_class=ProposalClass(row["proposal_class"]),
        proposal_category=ProposalCategory(row["proposal_category"]),
        proposal_schema_version=row["proposal_schema_version"],
        payload=row["payload"],
        rationale=row["rationale"],
        affected_semantic_paths=tuple(row.get("affected_semantic_paths") or ()),
        generated_against_draft_revision=_columns_to_binding(
            row.get("generated_against_draft_revision"), bool(row["generated_against_no_draft_yet"])
        ),
        status=ProposalStatus(row["status"]),
        created_at_utc=row.get("created_at_utc"),
        resolved_at_utc=row.get("resolved_at_utc"),
        resulting_question_id=(
            str(row["resulting_question_id"]) if row.get("resulting_question_id") else None
        ),
        resulting_decision_id=(
            str(row["resulting_decision_id"]) if row.get("resulting_decision_id") else None
        ),
    )
