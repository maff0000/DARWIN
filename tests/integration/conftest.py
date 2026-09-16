import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

from darwin.core.config import PostgresConfig
from darwin.research_store.migrations import run_migrations

import darwin.research_store as _rs; MIGRATIONS_DIR = Path(_rs.__file__).resolve().parent / "migrations_sql"


def _config_from_dsn(dsn: str) -> PostgresConfig:
    parsed = urlparse(dsn)
    return PostgresConfig(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database=(parsed.path or "/darwin").lstrip("/"),
        user=parsed.username or "darwin_test",
        password=parsed.password or "",
    )


@pytest.fixture(scope="session")
def pg_config() -> PostgresConfig:
    dsn = os.environ.get("DARWIN_TEST_PG_DSN")
    if not dsn:
        pytest.skip("DARWIN_TEST_PG_DSN not set — integration tests require a disposable PostgreSQL")
    cfg = _config_from_dsn(dsn)
    run_migrations(cfg, MIGRATIONS_DIR)
    return cfg
