"""PID-004A finalisation transaction boundary (PID-004 sec33/sec34,
PID-004A persistence directive item 12).

One governed function, one transaction: load draft (locking the row so a
concurrent finalisation attempt cannot race past the revision check) ->
validate exact revision -> check finalisation idempotency for THIS EXACT
(draft_id, draft_revision) -> finalise in the domain
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

Idempotency (adversarial-audit fix #1): a particular `(draft_id,
draft_revision)` pair may create AT MOST ONE `StrategyVersion` -- a second
caller finalising the exact same draft revision (a concurrent request, or
a retried/double-submitted one) must get the SAME logical result back, not
a second `StrategyVersion`. This is deliberately NOT implemented by
bumping `specification_drafts.revision` on finalisation -- `revision`
means authoring/content revision (persistence directive item 4);
finalising does not change the draft's content, so it must not look like
it did. Editing the draft's content is what legitimately advances revision
(1 -> 2), and a later revision remains free to finalise into a genuinely
NEW `StrategyVersion` (see `test_finalising_a_new_revision_after_an_edit_
creates_a_genuinely_new_strategy_version`).

Two layers enforce the invariant:

1. Application-level check-then-act, right after the draft row lock is
   acquired and `expected_revision` is confirmed
   (`_load_existing_finalisation`): if this exact (draft_id, revision) has
   already produced a `StrategyVersion`, return it idempotently instead of
   re-finalising. The `SELECT ... FOR UPDATE` above already serialises
   concurrent callers against the SAME draft_id, so in practice this check
   is what a second, lock-released caller sees.
2. A real database backstop: migration 0007's partial unique index on
   `strategy_versions (source_draft_id, source_draft_revision)`. Even if
   some future code path reaches the INSERT below without having safely
   serialised against another caller, the SECOND insert for the same
   (draft_id, revision) fails at the database -- caught here specifically
   (by constraint name, not by broad exception class) and recovered by
   re-reading and returning the now-existing result, never raised to the
   caller as a surprise integrity error.
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
from darwin.specification.serialization import (
    deserialize_specification_draft,
    deserialize_strategy_version,
)
from darwin.specification.validation import (
    FinalisationResult,
    ValidationOutcome,
    ValidationOutcomeStatus,
    finalise,
)

# Must match the index name in
# darwin/research_store/migrations_sql/0007_finalisation_idempotency.sql
# exactly -- this is how the UniqueViolation catch below distinguishes
# "the finalisation-idempotency backstop fired" from any other unrelated
# unique-constraint violation (e.g. artifact_record_fingerprint).
_SOURCE_DRAFT_REVISION_UNIQUE_INDEX = "uq_strategy_versions_source_draft_revision"


class DraftNotFoundError(SpecificationPersistenceError):
    code = "SPECIFICATION_DRAFT_NOT_FOUND"


class SpecificationDraftRevisionAlreadyFinalisedConflictError(SpecificationPersistenceError):
    """Raised only when a caller's EXPLICIT `strategy_version_id`/
    `version_label` request conflicts with the StrategyVersion that
    already exists for this exact (draft_id, draft_revision) -- a normal
    identical retry (no explicit id/label, or ones that match) is never an
    error; see `_load_existing_finalisation`/`finalise_specification_draft`."""

    code = "SPECIFICATION_DRAFT_REVISION_ALREADY_FINALISED_CONFLICT"


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


def _load_existing_finalisation(
    conn: psycopg.Connection, *, draft_id: str, draft_revision: int
) -> tuple[dict | None, FinalisationOutcome | None]:
    """Looks up whether `(draft_id, draft_revision)` has already produced a
    `StrategyVersion` (migration 0007's partial unique index is the
    structural guarantee that at most one such row can ever exist).
    Returns `(None, None)` if not; otherwise `(existing_row,
    idempotent_outcome)` -- `existing_row` is the raw `strategy_versions`
    row dict (used by the caller for the explicit-id/label conflict check),
    `idempotent_outcome` is the `FinalisationOutcome` to hand back as-is.

    Reconstructs a `FinalisationResult`/`ValidationOutcome` rather than
    re-deriving them from `darwin.specification.validation.finalise` --
    re-running `finalise` would be redundant (the outcome is already
    durably VALID, by construction of how a `strategy_versions` row with a
    non-null `source_draft_id`/`source_draft_revision` comes to exist at
    all) and would require re-fetching/re-deserializing the draft payload
    for no benefit.
    """
    existing_row = SpecificationVersionRepository(conn).get_row_by_draft_and_revision(
        draft_id, draft_revision
    )
    if existing_row is None:
        return None, None

    existing_version = deserialize_strategy_version(existing_row["full_payload"])

    matching_records = [
        record
        for record in ValidationRecordRepository(conn).list_for_draft(draft_id)
        if record["status"] == "VALID"
        and int(record["draft_revision"]) == draft_revision
        and record["strategy_version_id"] is not None
        and str(record["strategy_version_id"]) == str(existing_row["id"])
    ]
    # Exactly one is expected here -- the same transaction that ever
    # inserted this strategy_versions row also inserted its VALID
    # validation record (see the end of finalise_specification_draft).
    # There is no code path that writes one without the other.
    validation_record_id = (
        str(matching_records[-1]["id"]) if matching_records else str(existing_row["id"])
    )

    outcome = FinalisationOutcome(
        result=FinalisationResult(
            outcome=ValidationOutcome(status=ValidationOutcomeStatus.VALID, findings=()),
            strategy_version=existing_version,
        ),
        validation_record_id=validation_record_id,
        candidate_advanced=False,
    )
    return existing_row, outcome


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

    # Idempotency guard (adversarial-audit fix #1): this exact (draft_id,
    # expected_revision) pair may already have produced a StrategyVersion
    # -- a concurrent caller that queued behind the FOR UPDATE lock above,
    # or a retried/double-submitted request. Never mint a second one.
    existing_row, existing_outcome = _load_existing_finalisation(
        conn, draft_id=draft_id, draft_revision=expected_revision
    )
    if existing_outcome is not None:
        existing_version = existing_outcome.strategy_version
        conflicting_id = strategy_version_id is not None and strategy_version_id != existing_row["id"]
        conflicting_label = version_label is not None and version_label != existing_row["version_label"]
        if conflicting_id or conflicting_label:
            raise SpecificationDraftRevisionAlreadyFinalisedConflictError(
                f"specification_drafts {draft_id!r} revision {expected_revision!r} was already "
                f"finalised as StrategyVersion {existing_version.strategy_version_id!r} "
                f"(version_label={existing_row['version_label']!r}); the caller's request "
                f"(strategy_version_id={strategy_version_id!r}, version_label={version_label!r}) "
                f"conflicts with that existing finalisation"
            )
        return existing_outcome

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

    # DB-level backstop for the idempotency invariant (the crux of
    # adversarial-audit fix #1): a SAVEPOINT around just the StrategyVersion
    # INSERT lets us catch ONLY a violation of migration 0007's partial
    # unique index on (source_draft_id, source_draft_revision) -- by
    # constraint name, not by broad exception class, so an unrelated
    # UniqueViolation (e.g. artifact_record_fingerprint) still propagates
    # normally -- roll back to before the failed INSERT (otherwise the
    # whole enclosing transaction would be left aborted), and recover by
    # returning the finalisation that already exists for this exact
    # (draft_id, revision) instead of raising a surprise integrity error to
    # the caller. In ordinary operation the FOR UPDATE lock + the
    # application-level check above already prevent this from firing; this
    # is defence-in-depth for any path that reaches here without that
    # serialisation.
    with conn.cursor() as cur:
        cur.execute("SAVEPOINT finalise_strategy_version_insert")
    try:
        SpecificationVersionRepository(conn).create(
            version,
            version_label=version_label,
            source_draft_id=draft_id,
            source_draft_revision=expected_revision,
        )
    except psycopg.errors.UniqueViolation as exc:
        constraint_name = getattr(exc.diag, "constraint_name", None)
        if constraint_name != _SOURCE_DRAFT_REVISION_UNIQUE_INDEX:
            raise
        with conn.cursor() as cur:
            cur.execute("ROLLBACK TO SAVEPOINT finalise_strategy_version_insert")
        _, recovered_outcome = _load_existing_finalisation(
            conn, draft_id=draft_id, draft_revision=expected_revision
        )
        if recovered_outcome is None:
            # Should be structurally impossible (the constraint only ever
            # fires because a matching row already exists) -- but never
            # swallow silently if it somehow happens.
            raise
        return recovered_outcome
    else:
        with conn.cursor() as cur:
            cur.execute("RELEASE SAVEPOINT finalise_strategy_version_insert")

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
