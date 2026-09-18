"""PID-004A Specification Contract persistence (DARWIN_sql / migration
0006_strategy_specification.sql).

Plain parameterised SQL, no ORM -- same discipline as
`darwin.research_store.repositories`. This module is the ONLY place that
translates between `darwin.specification`'s DB-agnostic domain objects
(`SpecificationDraft`, `StrategyVersion`, `DataRequirement`,
`DataReadinessAssessment`) and Postgres rows -- `darwin.specification`
itself never imports psycopg or anything SQL-specific (PID-004A
persistence directive item 14, mirroring how `darwin.scout.domain` stays
DB-agnostic while `darwin.research_store.repositories` does the SQL work
for SCOUT).

Foundation's own narrow `StrategyCandidateRepository`/
`StrategyVersionRepository` (`darwin.research_store.repositories`) are
untouched -- they still create/count `strategy_candidates`/
`strategy_versions` rows using exactly the columns migration
0001_foundation.sql defined. The repositories here evolve the SAME two
tables (migration 0006 only ADDs nullable columns) with the richer
PID-004A persistence those narrow repositories never needed.
"""
from __future__ import annotations

import json
from datetime import datetime

import psycopg

from darwin.core.errors import DarwinError
from darwin.core.identities import new_id
from darwin.specification.domain import SpecificationDraft, StrategyVersion
from darwin.specification.readiness import DataReadinessAssessment
from darwin.specification.serialization import (
    SERIALIZATION_SCHEMA_VERSION,
    deserialize_specification_draft,
    deserialize_strategy_version,
    serialize_specification_draft,
    serialize_strategy_version,
)


class SpecificationPersistenceError(DarwinError):
    code = "SPECIFICATION_PERSISTENCE_ERROR"


class StaleRevisionError(SpecificationPersistenceError):
    """Raised when a `SpecificationDraft` update/finalisation is attempted
    against a revision that is no longer current (classic optimistic-
    concurrency refusal -- PID-004A persistence directive item 4). The
    caller must re-read the draft and retry; this module never silently
    applies a stale write."""

    code = "SPECIFICATION_STALE_REVISION"


# --- candidate lineage / discovery provenance (item 3) ----------------------


class CandidateLineageRepository:
    """`StrategyCandidate <-> SCOUT Discovery` provenance and
    `child StrategyCandidate <-> parent StrategyCandidate` lineage, each as
    a real join table -- never collapsed into `strategy_candidates`'s old
    nullable `source_strategy_id` column (PID-004A persistence directive
    item 3)."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def link_discovery(self, candidate_id: str, discovery_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_candidate_discovery_links (id, candidate_id, discovery_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (candidate_id, discovery_id) DO NOTHING
                """,
                (new_id(), candidate_id, discovery_id),
            )

    def link_parent(self, child_candidate_id: str, parent_candidate_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_candidate_lineage (id, child_candidate_id, parent_candidate_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (child_candidate_id, parent_candidate_id) DO NOTHING
                """,
                (new_id(), child_candidate_id, parent_candidate_id),
            )

    def discoveries_for_candidate(self, candidate_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_candidate_discovery_links WHERE candidate_id = %s ORDER BY created_at_utc",
                (candidate_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def parents_for_candidate(self, child_candidate_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_candidate_lineage WHERE child_candidate_id = %s ORDER BY created_at_utc",
                (child_candidate_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def children_for_candidate(self, parent_candidate_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_candidate_lineage WHERE parent_candidate_id = %s ORDER BY created_at_utc",
                (parent_candidate_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# --- SpecificationDraft persistence (item 4) ---------------------------------


class SpecificationDraftRepository:
    """MUTABLE `SpecificationDraft` persistence with explicit optimistic
    concurrency (`revision`). A draft revision is NEVER a StrategyVersion
    (PID-004 sec4.3/PID-004A persistence directive item 4) -- this table
    has no fingerprint/immutability column at all."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, draft: SpecificationDraft) -> None:
        payload = serialize_specification_draft(draft)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO specification_drafts
                    (id, candidate_id, schema_semantic_version, revision, draft_payload,
                     serialization_schema_version)
                VALUES (%s, %s, %s, 1, %s, %s)
                """,
                (
                    draft.draft_id,
                    draft.candidate_id,
                    draft.schema_semantic_version,
                    json.dumps(payload),
                    SERIALIZATION_SCHEMA_VERSION,
                ),
            )

    def get_row(self, draft_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM specification_drafts WHERE id = %s", (draft_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get(self, draft_id: str) -> SpecificationDraft | None:
        row = self.get_row(draft_id)
        if row is None:
            return None
        return deserialize_specification_draft(row["draft_payload"])

    def update_with_expected_revision(
        self, draft_id: str, expected_revision: int, draft: SpecificationDraft
    ) -> int:
        """The only supported way to persist an edit to an existing draft.
        Atomically increments `revision` ONLY when the row is still at
        `expected_revision` -- a stale write (someone else's edit already
        landed) touches zero rows and raises `StaleRevisionError`, never
        silently overwrites. Returns the new revision on success."""
        payload = serialize_specification_draft(draft)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE specification_drafts
                SET draft_payload = %s, revision = revision + 1, updated_at_utc = now()
                WHERE id = %s AND revision = %s
                RETURNING revision
                """,
                (json.dumps(payload), draft_id, expected_revision),
            )
            row = cur.fetchone()
        if row is None:
            raise StaleRevisionError(
                f"specification_drafts {draft_id!r} is not at the expected revision "
                f"{expected_revision!r} -- re-read and retry"
            )
        return int(row["revision"])

    def list_for_candidate(self, candidate_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM specification_drafts WHERE candidate_id = %s ORDER BY created_at_utc",
                (candidate_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# --- canonical StrategyVersion persistence (item 5/6/7) ----------------------


class SpecificationVersionRepository:
    """Canonical, immutable `StrategyVersion` persistence -- evolves the
    Foundation `strategy_versions` table (migration 0001) rather than
    creating a competing table (PID-004A persistence directive item 1).

    Exposes ONLY insert + read/list -- there is no `update`/`delete`
    method anywhere on this class (item 7: "your repository must expose
    only INSERT + read/list"). Real immutability enforcement is at the
    Postgres layer (migration 0006's `trg_strategy_versions_immutable`
    trigger) -- see `tests/integration/test_specification_persistence.py`
    for the direct raw-SQL proof.
    """

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(
        self,
        version: StrategyVersion,
        *,
        version_label: str | None = None,
        source_draft_id: str | None = None,
        source_draft_revision: int | None = None,
    ) -> None:
        label = version_label or version.strategy_version_id
        full_payload = serialize_strategy_version(version)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_versions
                    (id, candidate_id, version_label, specification_fingerprint, is_immutable,
                     title, thesis, schema_semantic_version, semantic_fingerprint,
                     artifact_record_fingerprint, full_payload, serialization_schema_version,
                     source_draft_id, source_draft_revision, finalised_at_utc)
                VALUES (%s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    version.strategy_version_id,
                    version.candidate_id,
                    label,
                    version.semantic_fingerprint,
                    version.title,
                    version.thesis,
                    version.schema_semantic_version,
                    version.semantic_fingerprint,
                    version.artifact_record_fingerprint,
                    json.dumps(full_payload),
                    SERIALIZATION_SCHEMA_VERSION,
                    source_draft_id,
                    source_draft_revision,
                    version.finalised_at_utc,
                ),
            )

    def get_row(self, strategy_version_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM strategy_versions WHERE id = %s", (strategy_version_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get(self, strategy_version_id: str) -> StrategyVersion | None:
        row = self.get_row(strategy_version_id)
        if row is None or row.get("full_payload") is None:
            return None
        return deserialize_strategy_version(row["full_payload"])

    def list_for_candidate(self, candidate_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_versions WHERE candidate_id = %s ORDER BY created_at_utc",
                (candidate_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_by_semantic_fingerprint(self, semantic_fingerprint: str) -> list[dict]:
        """PID-004A persistence directive item 6: `semantic_fingerprint` is
        NOT unique identity -- multiple rows may legitimately share one."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_versions WHERE semantic_fingerprint = %s ORDER BY created_at_utc",
                (semantic_fingerprint,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_row_by_draft_and_revision(
        self, source_draft_id: str, source_draft_revision: int
    ) -> dict | None:
        """Adversarial-audit fix #1 (finalisation idempotency): the
        read half of the `(source_draft_id, source_draft_revision)`
        uniqueness invariant enforced by migration 0007's partial unique
        index -- used by
        `darwin.research_store.specification_finalisation` to detect that
        this exact draft revision has already been finalised, before
        (and, as a DB-level backstop, after) attempting a new INSERT."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_versions WHERE source_draft_id = %s AND source_draft_revision = %s",
                (source_draft_id, source_draft_revision),
            )
            row = cur.fetchone()
            return dict(row) if row else None


# --- data requirement projection (item 8) ------------------------------------


class DataRequirementProjectionRepository:
    """Relational, queryable projection of a StrategyVersion's
    `DataRequirement`s -- derived transactionally at finalisation time,
    FK'd back to the StrategyVersion, never independently editable
    (real DB trigger, migration 0006). The canonical semantic truth
    remains `strategy_versions.full_payload`; this table exists purely to
    answer aggregate/filter queries efficiently (PID-004 sec29)."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create_many(self, strategy_version_id: str, requirements) -> None:
        with self._conn.cursor() as cur:
            for requirement in requirements:
                cur.execute(
                    """
                    INSERT INTO strategy_version_data_requirements
                        (id, strategy_version_id, requirement_id, display_name, fact_class,
                         fact_reference_kind, authority_class, instrument_applicability,
                         timeframe_code, historical_depth_count, historical_depth_unit, units,
                         required_fields, causal_timing_policy, mandatory)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        new_id(),
                        strategy_version_id,
                        requirement.requirement_id,
                        requirement.display_name,
                        requirement.fact_class.value,
                        requirement.fact_reference_kind.value,
                        requirement.authority_class.value,
                        json.dumps(list(requirement.instrument_applicability)),
                        requirement.timeframe.code if requirement.timeframe else None,
                        requirement.required_historical_depth.count,
                        requirement.required_historical_depth.unit.value,
                        requirement.units,
                        json.dumps(list(requirement.required_fields)),
                        requirement.causal_timing_policy.value,
                        requirement.mandatory,
                    ),
                )

    def list_for_strategy_version(self, strategy_version_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_version_data_requirements WHERE strategy_version_id = %s "
                "ORDER BY requirement_id",
                (strategy_version_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def query(self, *, fact_class: str | None = None, authority_class: str | None = None) -> list[dict]:
        """Answers PID-004 sec29's aggregate-demand question: which
        StrategyVersions need `fact_class` (e.g. IMPLIED_VOLATILITY /
        OPEN_INTEREST) and/or ARES (`ARES_GOVERNED_CONTEXT`) context? Which
        are missing a given authority?"""
        clauses: list[str] = []
        params: list[object] = []
        if fact_class is not None:
            clauses.append("fact_class = %s")
            params.append(fact_class)
        if authority_class is not None:
            clauses.append("authority_class = %s")
            params.append(authority_class)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM strategy_version_data_requirements {where} ORDER BY strategy_version_id",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def distinct_strategy_version_ids(
        self, *, fact_class: str | None = None, authority_class: str | None = None
    ) -> list[str]:
        rows = self.query(fact_class=fact_class, authority_class=authority_class)
        seen: list[str] = []
        for row in rows:
            value = str(row["strategy_version_id"])
            if value not in seen:
                seen.append(value)
        return seen


# --- data readiness assessments (item 9) -------------------------------------


class DataReadinessAssessmentRepository:
    """Append-only `DataReadinessAssessment` persistence -- multiple
    assessments per StrategyVersion are expected (PID-004 sec27/sec28),
    never mutated/rewritten. No update/delete method exists anywhere on
    this class. Per-requirement rows are protected by migration 0006's
    composite FK discipline: it is structurally impossible to persist a
    per-requirement readiness row whose requirement belongs to a different
    StrategyVersion than the assessment it is filed under -- see
    `tests/integration/test_specification_persistence.py`."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, assessment: DataReadinessAssessment) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO data_readiness_assessments
                    (id, strategy_version_id, assessed_at_utc, overall_state, mandatory_requirement_ids)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    assessment.assessment_id,
                    assessment.strategy_version_id,
                    assessment.assessed_at_utc,
                    assessment.overall_state.value,
                    json.dumps(sorted(assessment.mandatory_requirement_ids)),
                ),
            )
            for per_requirement in assessment.per_requirement:
                cur.execute(
                    """
                    INSERT INTO data_readiness_assessment_requirements
                        (id, assessment_id, strategy_version_id, requirement_id, availability, reason)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        new_id(),
                        assessment.assessment_id,
                        assessment.strategy_version_id,
                        per_requirement.requirement_id,
                        per_requirement.availability.value,
                        per_requirement.reason,
                    ),
                )

    def get_header(self, assessment_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM data_readiness_assessments WHERE id = %s", (assessment_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_per_requirement(self, assessment_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM data_readiness_assessment_requirements WHERE assessment_id = %s "
                "ORDER BY requirement_id",
                (assessment_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def list_for_strategy_version(self, strategy_version_id: str) -> list[dict]:
        """Full history, oldest first -- every assessment ever taken
        against this StrategyVersion, none of them rewritten."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM data_readiness_assessments WHERE strategy_version_id = %s "
                "ORDER BY assessed_at_utc ASC",
                (strategy_version_id,),
            )
            return [dict(r) for r in cur.fetchall()]


# --- shelving (item 10) -------------------------------------------------------


class ShelvingRepository:
    """Non-destructive operational shelving as an auditable append-only
    event/history table (PID-004 sec28) -- structurally incapable of
    touching `strategy_versions`/either fingerprint/DataRequirements: this
    table only ever reads a `strategy_version_id` to attach an event to,
    never writes to any other table."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create_event(
        self,
        strategy_version_id: str,
        *,
        state: str,
        occurred_at_utc: datetime,
        reason: str | None = None,
        actor: str | None = None,
    ) -> str:
        event_id = new_id()
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_version_shelving_events
                    (id, strategy_version_id, state, reason, actor, occurred_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (event_id, strategy_version_id, state, reason, actor, occurred_at_utc),
            )
        return event_id

    def list_for_strategy_version(self, strategy_version_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM strategy_version_shelving_events WHERE strategy_version_id = %s "
                "ORDER BY occurred_at_utc ASC",
                (strategy_version_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def current_state(self, strategy_version_id: str) -> str | None:
        events = self.list_for_strategy_version(strategy_version_id)
        return events[-1]["state"] if events else None


# --- validation records (item 11) --------------------------------------------


class ValidationRecordRepository:
    """Deterministic validation outcomes (PID-004 sec33/sec35): a refused
    draft (`STRATEGY_NOT_SUFFICIENTLY_DEFINED`) is durably representable
    and creates no StrategyVersion -- enforced at the DB layer by migration
    0006's CHECK constraint, not merely by this repository's own care."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        draft_id: str,
        draft_revision: int,
        assessed_at_utc: datetime,
        status: str,
        findings: list[dict],
        strategy_version_id: str | None = None,
    ) -> str:
        record_id = new_id()
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO specification_validation_records
                    (id, draft_id, draft_revision, assessed_at_utc, status, findings, strategy_version_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record_id,
                    draft_id,
                    draft_revision,
                    assessed_at_utc,
                    status,
                    json.dumps(findings),
                    strategy_version_id,
                ),
            )
        return record_id

    def list_for_draft(self, draft_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM specification_validation_records WHERE draft_id = %s ORDER BY created_at_utc",
                (draft_id,),
            )
            return [dict(r) for r in cur.fetchall()]
