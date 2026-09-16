"""Explicit, versioned SQL migration runner (PID-001 §27).

Deliberately not full Alembic: Foundation's schema is small and the ordering/
idempotency requirements are simple enough that a minimal, dependency-free
runner is the smaller robust choice (PID-001 §5 permits Alembic without
mandating it). Runtime application code never uses ORM `create_all` as a
migration mechanism — this module is the only schema-mutating path.
"""
from __future__ import annotations

import logging
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from darwin.core.config import PostgresConfig
from darwin.core.logging import log_event

logger = logging.getLogger(__name__)

_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at_utc TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"), key=lambda p: p.name)


def applied_versions(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(_CREATE_MIGRATIONS_TABLE)
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}


def run_migrations(config: PostgresConfig, migrations_dir: Path) -> list[str]:
    """Apply all pending migrations in deterministic filename order.

    Returns the list of versions applied this run. Raises on the first
    failure (transaction is rolled back for that migration); does not
    continue applying subsequent files against a partially-applied schema.
    """
    applied_this_run: list[str] = []
    with psycopg.connect(config.dsn(), row_factory=dict_row) as conn:
        already_applied = applied_versions(conn)
        conn.commit()

        for path in _migration_files(migrations_dir):
            version = path.stem
            if version in already_applied:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                log_event(logger, logging.ERROR, "migration_failed", version=version)
                raise
            applied_this_run.append(version)
            log_event(logger, logging.INFO, "migration_applied", version=version)

    return applied_this_run


def migration_state(config: PostgresConfig, migrations_dir: Path) -> dict:
    """Exposed via readiness/build diagnostics (PID-001 §27)."""
    all_versions = [p.stem for p in _migration_files(migrations_dir)]
    with psycopg.connect(config.dsn(), row_factory=dict_row) as conn:
        applied = applied_versions(conn)
        conn.commit()
    pending = [v for v in all_versions if v not in applied]
    return {
        "total_migrations": len(all_versions),
        "applied": sorted(applied),
        "pending": pending,
        "up_to_date": len(pending) == 0,
    }
