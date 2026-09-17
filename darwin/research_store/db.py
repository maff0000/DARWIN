"""DARWIN_sql (PostgreSQL) connection management.

Control/evidence/research metadata only — never the strategy-computation hot
path, never a duplicate market-history store (PID.md §14-15).
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from darwin.core.config import PostgresConfig
from darwin.core.errors import NotReadyError
from darwin.core.logging import log_event

logger = logging.getLogger(__name__)


def check_postgres_reachable(config: PostgresConfig) -> bool:
    try:
        with psycopg.connect(config.dsn(), connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except psycopg.OperationalError:
        return False


@contextmanager
def connection(config: PostgresConfig) -> Iterator[psycopg.Connection]:
    try:
        conn = psycopg.connect(config.dsn(), row_factory=dict_row, connect_timeout=5)
    except psycopg.OperationalError as exc:
        log_event(logger, logging.ERROR, "postgres_unavailable", error_class=exc.__class__.__name__)
        raise NotReadyError("DARWIN_sql is not reachable") from exc
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
