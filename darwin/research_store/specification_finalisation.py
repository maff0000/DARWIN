"""PID-004A finalisation transaction boundary (PID-004 sec33/sec34,
PID-004A persistence directive item 12).

One governed function, one transaction: load draft (locking the row so a
concurrent finalisation attempt cannot race past the revision check) ->
validate exact revision -> finalise in the domain
(`darwin.specification.validation.finalise`, never reimplemented here) ->
persist the validation outcome -> on success, INSERT the immutable
`StrategyVersion` + its `DataRequirement` projection -> advance the
candidate `DISCOVERED -> SPECIFIED` -> return. Any exception raised from
here propagates to the caller's `darwin.research_store.db.connection`
context manager, which rolls back the whole transaction -- there is no
partial-commit path anywhere in this module.

A semantically-complete-but-`DATA_BLOCKED` strategy finalises exactly the
same way a `TESTABLE` one does (PID-004 sec34) -- this module never
touches readiness at all; readiness is assessed afterwards, separately,
via `DataReadinessAssessmentRepository`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import psycopg

from darwin.core.identities import new_id
from darwin.research_store.specification_repositories import (
    DataRequirementProjectionRepository,
    SpecificationPersistenceError,
    SpecificationVersionRepository,
    StaleRevisionError,
    ValidationRecordRepository,
)
from darwin.specification.domain import StrategyVersion
from darwin.specification.serialization import deserialize_specification_draft
from darwin.specification.validation import (
    FinalisationResult,
    ValidationOutcome,
    finalise,
)


class DraftNotFoundError(SpecificationPersistenceError):
    code = "SPECIFICATION_DRAFT_NOT_FOUND"


@dataclass(frozen=True)
class FinalisationOutcome:
    """What actually happened, for a caller that needs more than the bare
    domain `FinalisationResult` -- e.g. which validation record was
    written, and whether the candidate was actually advanced (it is a
    no-op, not an error, if the candidate was already past DISCOVERED --
    see `_advance_candidate_to_specified`)."""

    result: FinalisationResult
    validation_record_id: str
    candidate_advanced: bool

    @property
    def outcome(self) -> ValidationOutcome:
        return self.result.outcome

    @property
    def strategy_version(self) -> StrategyVersion | None:
        return self.result.strategy_version


def _advance_candidate_to_specified(conn: psycopg.Connection, candidate_id: str) -> bool:
    """PID-004A persistence directive item 13: only `DISCOVERED ->
    SPECIFIED` from this phase. A no-op (not an error) if the candidate is
    not currently `DISCOVERED` -- e.g. a second StrategyVersion finalised
    under an already-SPECIFIED candidate. Never advances to
    ATHENA_TESTED/ATHENA_QUALIFIED/APOLLO_PROVEN/PROMISING -- this
    function's own UPDATE statement never writes any value other than the
    literal string 'SPECIFIED'."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE strategy_candidates
            SET pipeline_stage = 'SPECIFIED', updated_at_utc = now()
            WHERE id = %s AND pipeline_stage = 'DISCOVERED'
            """,
            (candidate_id,),
        )
        return cur.rowcount > 0


def finalise_specification_draft(
    conn: psycopg.Connection,
    *,
    draft_id: str,
    expected_revision: int,
    strategy_version_id: str | None = None,
    version_label: str | None = None,
    now: datetime | None = None,
) -> FinalisationOutcome:
    """The one governed finalisation transaction boundary. Everything
    below runs against the SAME `conn` the caller obtained from
    `darwin.research_store.db.connection(config)` -- that context manager
    commits on normal return and rolls back on any exception, so this
    function itself never calls `conn.commit()`/`conn.rollback()`
    directly; raising is sufficient to undo everything already written in
    this call.
    """
    now = now or datetime.now(UTC)

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM specification_drafts WHERE id = %s FOR UPDATE", (draft_id,))
        row = cur.fetchone()
    if row is None:
        raise DraftNotFoundError(f"No specification_drafts row with id={draft_id!r}")
    if int(row["revision"]) != expected_revision:
        raise StaleRevisionError(
            f"specification_drafts {draft_id!r} is at revision {row['revision']}, expected "
            f"{expected_revision!r} -- re-read and retry"
        )

    draft = deserialize_specification_draft(row["draft_payload"])

    result = finalise(draft, strategy_version_id=strategy_version_id or new_id(), now=now)

    findings_payload = [
        {"stage": f.stage, "code": f.code, "message": f.message, "path": f.path}
        for f in result.outcome.findings
    ]

    if result.strategy_version is None:
        # STRATEGY_NOT_SUFFICIENTLY_DEFINED (PID-004 sec33/sec35): record
        # the refusal. No StrategyVersion, no candidate advancement, draft
        # untouched.
        validation_record_id = ValidationRecordRepository(conn).create(
            draft_id=draft_id, draft_revision=expected_revision, assessed_at_utc=now,
            status=result.outcome.status.value, findings=findings_payload, strategy_version_id=None,
        )
        return FinalisationOutcome(result=result, validation_record_id=validation_record_id, candidate_advanced=False)

    # VALID: the StrategyVersion row + its DataRequirement projection MUST
    # exist before the validation record's FK to strategy_versions(id) can
    # be satisfied -- insert them first, in this order, all still inside
    # the same transaction.
    version = result.strategy_version
    SpecificationVersionRepository(conn).create(version, version_label=version_label, source_draft_id=draft_id)
    DataRequirementProjectionRepository(conn).create_many(version.strategy_version_id, version.data_requirements)
    candidate_advanced = _advance_candidate_to_specified(conn, version.candidate_id)

    validation_record_id = ValidationRecordRepository(conn).create(
        draft_id=draft_id, draft_revision=expected_revision, assessed_at_utc=now,
        status=result.outcome.status.value, findings=findings_payload,
        strategy_version_id=version.strategy_version_id,
    )

    return FinalisationOutcome(
        result=result, validation_record_id=validation_record_id, candidate_advanced=candidate_advanced
    )
