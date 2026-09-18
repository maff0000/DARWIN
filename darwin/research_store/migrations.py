"""Explicit, versioned SQL migration runner (PID-001 §27).

Deliberately not full Alembic: Foundation's schema is small and the ordering/
idempotency requirements are simple enough that a minimal, dependency-free
runner is the smaller robust choice (PID-001 §5 permits Alembic without
mandating it). Runtime application code never uses ORM `create_all` as a
migration mechanism — this module is the only schema-mutating path.

Privilege-separation note (adversarial-audit fix #2 item 9): the DDL that
creates `schema_migrations` must only ever run under governed
migration-execution authority (in production, the `darwin_migrator` role —
see `darwin/research_store/bootstrap/`), never under the ordinary
application runtime role. Accordingly this module keeps two genuinely
separate paths: `_ensure_schema_migrations_table` (DDL, called only from
`run_migrations`) and `read_applied_versions` (a plain `SELECT`, safe for
any caller, including a read-only diagnostic running under the restricted
application role — see `migration_state`, which is what `darwin_core`'s own
`/api/v1/migrations` and `/api/v1/ready` endpoints call using their ordinary
`cfg.postgres` connection). `read_applied_versions` never attempts to create
the table itself; if it is missing, that is reported as "migrations not yet
initialised", not silently papered over with a DDL statement the caller may
have no privilege to run.
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


def _schema_migrations_table_exists(conn: psycopg.Connection) -> bool:
    """Pure existence check -- a plain `SELECT`, never DDL. Safe under any
    role that has been granted `SELECT` on `schema_migrations` (the
    restricted application role included)."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM schema_migrations LIMIT 0")
        return True
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        return False


def _ensure_schema_migrations_table(conn: psycopg.Connection) -> None:
    """Governed DDL path -- in production this must only ever run under
    `darwin_migrator`/owner authority, never the ordinary application role
    (adversarial-audit fix #2 item 9). Only actually attempts `CREATE TABLE`
    when the table does not exist yet; once it exists, every subsequent
    call is just the read-only existence check above, requiring no CREATE
    privilege at all."""
    if _schema_migrations_table_exists(conn):
        return
    with conn.cursor() as cur:
        cur.execute(_CREATE_MIGRATIONS_TABLE)


def read_applied_versions(conn: psycopg.Connection) -> set[str]:
    """Pure `SELECT` -- safe under the restricted application role. Never
    creates `schema_migrations`; if it does not exist yet, returns an empty
    set (the caller is responsible for reporting that distinctly as
    "migrations not yet initialised" rather than "zero migrations
    pending" -- see `migration_state`)."""
    if not _schema_migrations_table_exists(conn):
        return set()
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}


def run_migrations(config: PostgresConfig, migrations_dir: Path) -> list[str]:
    """Apply all pending migrations in deterministic filename order.

    Returns the list of versions applied this run. Raises on the first
    failure (transaction is rolled back for that migration); does not
    continue applying subsequent files against a partially-applied schema.

    This is the ONLY function that should be called with `darwin_migrator`
    (or owner) credentials in production -- it is the governed
    migration-execution path (PID-004A adversarial-audit fix #2 item 9/10).
    """
    applied_this_run: list[str] = []
    with psycopg.connect(config.dsn(), row_factory=dict_row) as conn:
        _ensure_schema_migrations_table(conn)
        conn.commit()
        already_applied = read_applied_versions(conn)
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
    """Exposed via readiness/build diagnostics (PID-001 §27). A read-only
    diagnostic -- deliberately never performs DDL (adversarial-audit fix #2
    item 9): `darwin_core`'s own `/api/v1/migrations` and `/api/v1/ready`
    endpoints call this using the ordinary, restricted application
    connection (`cfg.postgres`), so it must work correctly under a role that
    has only been granted `SELECT` on `schema_migrations` -- and must not
    silently attempt to create that table if a genuinely fresh database has
    not been migrated yet at all.
    """
    all_versions = [p.stem for p in _migration_files(migrations_dir)]
    with psycopg.connect(config.dsn(), row_factory=dict_row) as conn:
        initialised = _schema_migrations_table_exists(conn)
        applied = read_applied_versions(conn) if initialised else set()
        conn.commit()
    pending = [v for v in all_versions if v not in applied]
    return {
        "total_migrations": len(all_versions),
        "applied": sorted(applied),
        "pending": pending,
        # A never-migrated database is reported honestly, not as "0 pending".
        "up_to_date": initialised and len(pending) == 0,
        "initialised": initialised,
    }
