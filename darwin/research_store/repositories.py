"""Explicit repository boundaries for DARWIN_sql persistence (PID-001 §26).

Plain parameterised SQL. No ORM, no `create_all` — schema exists only via
versioned migrations (migrations.py + migrations/*.sql).
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import psycopg

from darwin.core.lifecycle import PipelineStage
from darwin.research_store.models import (
    EvidenceRecord,
    MarketDatasetRecord,
    ResearchRun,
    SourceStrategy,
    StrategyCandidate,
    StrategyVersion,
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
