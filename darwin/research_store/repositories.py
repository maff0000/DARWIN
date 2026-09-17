"""Explicit repository boundaries for DARWIN_sql persistence (PID-001 §26).

Plain parameterised SQL. No ORM, no `create_all` — schema exists only via
versioned migrations (migrations.py + migrations/*.sql).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg

from darwin.core.identities import new_id
from darwin.core.lifecycle import PipelineStage
from darwin.research_store.models import (
    EvidenceRecord,
    MarketDatasetRecord,
    ResearchRun,
    SourceStrategy,
    StrategyCandidate,
    StrategyVersion,
)
from darwin.scout.domain import (
    DiscoveryRun,
    IntakeStatus,
    ScoutDomainError,
    SourceClaim,
    SourceDiscovery,
    SourceSnapshot,
    validate_intake_transition,
)


class SourceStrategyRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, s: SourceStrategy) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_strategies
                    (id, source_type, source_reference, title, provenance)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (s.id, s.source_type, s.source_reference, s.title, json.dumps(s.provenance)),
            )

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM source_strategies")
            return int(cur.fetchone()["n"])


class StrategyCandidateRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, c: StrategyCandidate) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_candidates
                    (id, source_strategy_id, title, pipeline_stage)
                VALUES (%s, %s, %s, %s)
                """,
                (c.id, c.source_strategy_id, c.title, c.pipeline_stage.value),
            )

    def counts_by_stage(self) -> dict[str, int]:
        counts = {stage.value: 0 for stage in PipelineStage}
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT pipeline_stage, COUNT(*) AS n FROM strategy_candidates GROUP BY pipeline_stage"
            )
            for row in cur.fetchall():
                counts[row["pipeline_stage"]] = int(row["n"])
        return counts

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM strategy_candidates")
            return int(cur.fetchone()["n"])


class StrategyVersionRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, v: StrategyVersion) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO strategy_versions
                    (id, candidate_id, version_label, specification_fingerprint, is_immutable)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (v.id, v.candidate_id, v.version_label, v.specification_fingerprint, v.is_immutable),
            )

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM strategy_versions")
            return int(cur.fetchone()["n"])


class MarketDatasetRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, d: MarketDatasetRecord) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO market_datasets
                    (id, instrument, instrument_definition_id, timeframe,
                     requested_start_utc, requested_end_utc,
                     actual_first_open_utc, actual_last_open_utc, record_count,
                     fingerprint_sha256, hermes_contract_version, hermes_contract_commit,
                     adapter_build_version, gap_summary, loaded_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    d.id,
                    d.instrument,
                    d.instrument_definition_id,
                    d.timeframe,
                    d.requested_start_utc,
                    d.requested_end_utc,
                    d.actual_first_open_utc,
                    d.actual_last_open_utc,
                    d.record_count,
                    d.fingerprint_sha256,
                    d.hermes_contract_version,
                    d.hermes_contract_commit,
                    d.adapter_build_version,
                    json.dumps(d.gap_summary),
                    d.loaded_at_utc,
                ),
            )

    def get(self, dataset_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM market_datasets WHERE id = %s", (dataset_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM market_datasets ORDER BY loaded_at_utc DESC LIMIT %s", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM market_datasets")
            return int(cur.fetchone()["n"])


class ResearchRunRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, r: ResearchRun) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_runs
                    (id, result_kind, engine, build_version, status,
                     instrument, instrument_definition_id, timeframe, display_title,
                     candidate_id, version_id, dataset_id, configuration_fingerprint,
                     dike_state, dike_policy_id, dike_policy_version, dike_policy_fingerprint)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    r.id,
                    r.result_kind.value,
                    r.engine,
                    r.build_version,
                    r.status,
                    r.instrument,
                    r.instrument_definition_id,
                    r.timeframe,
                    r.display_title,
                    r.candidate_id,
                    r.version_id,
                    r.dataset_id,
                    r.configuration_fingerprint,
                    r.dike_state.value,
                    r.dike_policy_id,
                    r.dike_policy_version,
                    r.dike_policy_fingerprint,
                ),
            )

    def update_status(self, run_id: str, status: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE research_runs SET status = %s, updated_at_utc = %s WHERE id = %s",
                (status, datetime.now(UTC), run_id),
            )

    def get(self, run_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM research_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM research_runs ORDER BY created_at_utc DESC LIMIT %s", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM research_runs")
            return int(cur.fetchone()["n"])


class EvidenceRecordRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, e: EvidenceRecord) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evidence_records (id, run_id, evidence_level, reference)
                VALUES (%s, %s, %s, %s)
                """,
                (e.id, e.run_id, e.evidence_level.value, e.reference),
            )

    def list_for_run(self, run_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM evidence_records WHERE run_id = %s", (run_id,))
            return [dict(r) for r in cur.fetchall()]


# --- PID-003 SCOUT: discovery/provenance persistence ------------------------
#
# Deliberately separate tables from source_strategies/strategy_candidates
# above -- see migration 0005_scout_discovery.sql's header comment.
# SourceDiscovery/SourceSnapshot/SourceClaim/DiscoveryRun/Source live in
# darwin.scout.domain (constructor-enforced invariants, mirroring
# darwin.research_store.run_binding's role for ResearchRun) -- repositories
# here only translate to/from DARWIN_sql, same discipline as every
# repository above.

# Fixed allowlist of GET /api/v1/scout/discoveries sort values -> SQL ORDER
# BY fragments. Never string-interpolate a caller-supplied sort value
# directly -- only a value already present as a dict key here is ever used.
_DISCOVERY_SORTS: dict[str, str] = {
    "recent": "d.last_seen_utc DESC",
    "net_pnl_percent": "c.net_pnl_percent DESC NULLS LAST",
    "profit_factor": "c.profit_factor DESC NULLS LAST",
    "sharpe": "c.sharpe DESC NULLS LAST",
    "sortino": "c.sortino DESC NULLS LAST",
    "max_drawdown_percent": "c.max_drawdown_percent ASC NULLS LAST",
    "trade_count": "c.trade_count DESC NULLS LAST",
}

DISCOVERY_SORT_VALUES: tuple[str, ...] = tuple(_DISCOVERY_SORTS)

_DISCOVERY_LEADERBOARD_SELECT = """
    SELECT d.*,
           c.net_pnl_percent, c.max_drawdown_percent, c.win_rate_percent,
           c.profit_factor, c.trade_count, c.sharpe, c.sortino
    FROM scout_discoveries d
    LEFT JOIN scout_claims c ON c.snapshot_id = d.last_snapshot_id
"""


class ScoutSourceRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def get_by_key(self, source_key: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM scout_sources WHERE source_key = %s", (source_key,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get(self, source_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM scout_sources WHERE id = %s", (source_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list(self) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM scout_sources ORDER BY source_key")
            return [dict(r) for r in cur.fetchall()]


class ScoutDiscoveryRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, d: SourceDiscovery) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scout_discoveries
                    (id, source_id, origin_kind, source_strategy_id, forked_from_source_strategy_id,
                     family_resolution, discovery_lifecycle_state, intake_status, title,
                     source_symbol, source_timeframe, origin_description, origin_url,
                     original_description, pasted_rule_text, personal_notes, tags,
                     last_snapshot_id, latest_rule_availability, first_seen_utc, last_seen_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    d.id, d.source_id, d.origin_kind.value, d.source_strategy_id,
                    d.forked_from_source_strategy_id, d.family_resolution.value,
                    d.discovery_lifecycle_state, d.intake_status.value, d.title,
                    d.source_symbol, d.source_timeframe, d.origin_description, d.origin_url,
                    d.original_description, d.pasted_rule_text, d.personal_notes,
                    json.dumps(list(d.tags)), d.last_snapshot_id,
                    d.latest_rule_availability.value if d.latest_rule_availability else None,
                    d.first_seen_utc, d.last_seen_utc,
                ),
            )

    def get(self, discovery_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(f"{_DISCOVERY_LEADERBOARD_SELECT} WHERE d.id = %s", (discovery_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_by_source_identity(self, source_id: str, source_strategy_id: str) -> dict | None:
        """The dedup lookup (PID-003 sec4): exact source identity dedups to
        the same discovery row. Never used for manual origins, which carry
        no source_strategy_id."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM scout_discoveries WHERE source_id = %s AND source_strategy_id = %s",
                (source_id, source_strategy_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list(
        self,
        *,
        symbol: str | None = None,
        intake_status: str | None = None,
        origin_kind: str | None = None,
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        if sort not in _DISCOVERY_SORTS:
            raise ScoutDomainError(f"Unsupported discovery sort {sort!r}; allowed: {sorted(_DISCOVERY_SORTS)}")
        clauses: list[str] = []
        params: list[object] = []
        if symbol:
            clauses.append("d.source_symbol = %s")
            params.append(symbol)
        if intake_status:
            clauses.append("d.intake_status = %s")
            params.append(intake_status)
        if origin_kind:
            clauses.append("d.origin_kind = %s")
            params.append(origin_kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        with self._conn.cursor() as cur:
            cur.execute(
                f"{_DISCOVERY_LEADERBOARD_SELECT} {where} ORDER BY {_DISCOVERY_SORTS[sort]} LIMIT %s OFFSET %s",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM scout_discoveries")
            return int(cur.fetchone()["n"])

    def counts_by_intake_status(self) -> dict[str, int]:
        counts = {status.value: 0 for status in IntakeStatus}
        with self._conn.cursor() as cur:
            cur.execute("SELECT intake_status, COUNT(*) AS n FROM scout_discoveries GROUP BY intake_status")
            for row in cur.fetchall():
                counts[row["intake_status"]] = int(row["n"])
        return counts

    def record_extraction_seen(
        self,
        discovery_id: str,
        *,
        last_seen_utc: datetime,
        new_snapshot_id: str | None = None,
        latest_rule_availability: str | None = None,
        source_symbol: str | None = None,
        source_timeframe: str | None = None,
    ) -> None:
        """Called on EVERY extraction of an existing discovery, whether the
        snapshot content is identical (idempotent — no new row) or changed
        (a new snapshot row was just created). `last_seen_utc` always
        advances; `last_snapshot_id`/`latest_rule_availability`/symbol/
        timeframe are only overwritten when a genuinely new snapshot was
        taken (`new_snapshot_id` given) -- an idempotent repeat updates
        `last_seen_utc` only, never manufactures a fake "changed" signal.
        """
        if new_snapshot_id is not None:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE scout_discoveries
                    SET last_seen_utc = %s, last_snapshot_id = %s, latest_rule_availability = %s,
                        source_symbol = COALESCE(%s, source_symbol),
                        source_timeframe = COALESCE(%s, source_timeframe),
                        updated_at_utc = %s
                    WHERE id = %s
                    """,
                    (last_seen_utc, new_snapshot_id, latest_rule_availability,
                     source_symbol, source_timeframe, datetime.now(UTC), discovery_id),
                )
        else:
            with self._conn.cursor() as cur:
                cur.execute(
                    "UPDATE scout_discoveries SET last_seen_utc = %s WHERE id = %s",
                    (last_seen_utc, discovery_id),
                )

    def set_intake_status(
        self,
        discovery_id: str,
        target_status: IntakeStatus,
        *,
        changed_by: str,
        reason: str | None = None,
    ) -> dict:
        """The only supported way to change intake status (PID-003 sec6:
        "narrow, explicit allowed-transition endpoint"). Validates the
        transition via darwin.scout.domain.validate_intake_transition,
        updates the discovery, and appends an audit row -- all inside the
        caller's existing transaction (darwin.research_store.db.connection
        commits/rolls back the whole request atomically), so a rejected
        transition never partially applies.
        """
        current = self.get(discovery_id)
        if current is None:
            raise ScoutDomainError(f"No discovery with id {discovery_id!r}")
        current_status = IntakeStatus(current["intake_status"])
        validate_intake_transition(current_status, target_status)

        now = datetime.now(UTC)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE scout_discoveries SET intake_status = %s, updated_at_utc = %s WHERE id = %s",
                (target_status.value, now, discovery_id),
            )
            cur.execute(
                """
                INSERT INTO scout_intake_audit (id, discovery_id, from_status, to_status, changed_by, reason, changed_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (new_id(), discovery_id, current_status.value, target_status.value, changed_by, reason, now),
            )
        return self.get(discovery_id)

    def list_intake_audit(self, discovery_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM scout_intake_audit WHERE discovery_id = %s ORDER BY changed_at_utc ASC",
                (discovery_id,),
            )
            return [dict(r) for r in cur.fetchall()]


class ScoutSnapshotRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, s: SourceSnapshot) -> None:
        """INSERT only -- no update method exists on this repository. The
        table's own UNIQUE(discovery_id, fingerprint_sha256) constraint
        (migration 0005) is what makes an identical repeated extraction
        idempotent; callers must check for an existing fingerprint match
        (`find_by_fingerprint`) before calling this, rather than relying on
        this method to silently no-op on conflict.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scout_snapshots
                    (id, discovery_id, source_id, source_record_id, extraction_utc, source_updated_utc,
                     adapter_name, adapter_version, source_url, source_symbol, source_timeframe,
                     raw_metadata, rule_availability, fingerprint_sha256)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    s.id, s.discovery_id, s.source_id, s.source_record_id, s.extraction_utc,
                    s.source_updated_utc, s.adapter_name, s.adapter_version, s.source_url,
                    s.source_symbol, s.source_timeframe, json.dumps(s.raw_metadata, default=str),
                    s.rule_availability.value, s.fingerprint_sha256,
                ),
            )

    def find_by_fingerprint(self, discovery_id: str, fingerprint_sha256: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM scout_snapshots WHERE discovery_id = %s AND fingerprint_sha256 = %s",
                (discovery_id, fingerprint_sha256),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get(self, snapshot_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM scout_snapshots WHERE id = %s", (snapshot_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_for_discovery(self, discovery_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM scout_snapshots WHERE discovery_id = %s ORDER BY extraction_utc ASC",
                (discovery_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM scout_snapshots")
            return int(cur.fetchone()["n"])


class ScoutClaimRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, c: SourceClaim) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scout_claims
                    (id, snapshot_id, discovery_id, evidence_level, net_pnl_percent,
                     max_drawdown_percent, win_rate_percent, profit_factor, trade_count,
                     sharpe, sortino, extraction_utc)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    c.id, c.snapshot_id, c.discovery_id, c.evidence_level, c.net_pnl_percent,
                    c.max_drawdown_percent, c.win_rate_percent, c.profit_factor, c.trade_count,
                    c.sharpe, c.sortino, c.extraction_utc,
                ),
            )

    def get_for_snapshot(self, snapshot_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM scout_claims WHERE snapshot_id = %s", (snapshot_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_for_discovery(self, discovery_id: str) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM scout_claims WHERE discovery_id = %s ORDER BY extraction_utc ASC",
                (discovery_id,),
            )
            return [dict(r) for r in cur.fetchall()]


class ScoutDiscoveryRunRepository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def create(self, r: DiscoveryRun) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scout_discovery_runs
                    (id, source_id, requested_filter, adapter_name, adapter_version, status,
                     started_at_utc, completed_at_utc, records_observed, records_accepted,
                     records_unchanged, records_changed, records_rejected, error_summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    r.id, r.source_id, json.dumps(r.requested_filter, default=str), r.adapter_name,
                    r.adapter_version, r.status.value, r.started_at_utc, r.completed_at_utc,
                    r.records_observed, r.records_accepted, r.records_unchanged,
                    r.records_changed, r.records_rejected, r.error_summary,
                ),
            )

    def complete(
        self,
        run_id: str,
        *,
        status: str,
        completed_at_utc: datetime,
        records_observed: int,
        records_accepted: int,
        records_unchanged: int,
        records_changed: int,
        records_rejected: int,
        error_summary: str | None,
    ) -> None:
        """The only update path for a DiscoveryRun -- moves it from RUNNING
        to a terminal status with its final counts, all at once, so no
        caller can ever observe a run that is "terminal but still has
        completed_at_utc = NULL" or vice versa (migration 0005's CHECK
        constraint also enforces this at the DB layer)."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE scout_discovery_runs
                SET status = %s, completed_at_utc = %s, records_observed = %s, records_accepted = %s,
                    records_unchanged = %s, records_changed = %s, records_rejected = %s, error_summary = %s
                WHERE id = %s
                """,
                (status, completed_at_utc, records_observed, records_accepted, records_unchanged,
                 records_changed, records_rejected, error_summary, run_id),
            )

    def get(self, run_id: str) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM scout_discovery_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM scout_discovery_runs ORDER BY started_at_utc DESC LIMIT %s", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_latest(self) -> dict | None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM scout_discovery_runs ORDER BY started_at_utc DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None

    def count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM scout_discovery_runs")
            return int(cur.fetchone()["n"])
