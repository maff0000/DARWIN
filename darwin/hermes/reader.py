"""Read-only HERMES historical adapter (PID-001 §11-13).

One bounded bulk/range query per load, never candle-by-candle. No writes are
possible from this module — it contains no INSERT/UPDATE/DELETE statement,
and the `darwin_ro` principal it connects as is independently proven
SELECT-only at the database layer (see docs/architecture/market-dataset.md).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import pymysql
import pymysql.cursors

from darwin.core.config import HermesConfig
from darwin.core.errors import HermesUnavailableError, InvalidRequestError
from darwin.core.logging import log_event
from darwin.hermes.contract import ALLOWED_INSTRUMENTS, Timeframe, canonical_object_for
from darwin.hermes.instrument_definition import get_instrument_definition
from darwin.hermes.validation import RawCanonicalRow, validate_rows

logger = logging.getLogger(__name__)

_SELECT_TEMPLATE = """
SELECT
    instrument, timeframe, open_time, open, high, low, close, volume,
    is_closed, status, source_timeframe, derivation_policy, source_policy_epoch,
    source_count, expected_source_count, source_coverage, gap_state,
    derivation_run_id, derivation_generated_at_utc, created_at
FROM {table}
WHERE instrument = %s
  AND open_time >= %s
  AND open_time < %s
ORDER BY open_time ASC
"""


def _connect(config: HermesConfig) -> pymysql.connections.Connection:
    try:
        return pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=30,
        )
    except pymysql.MySQLError as exc:
        raise HermesUnavailableError(f"Could not connect to HERMES: {exc.__class__.__name__}") from exc


def check_hermes_reachable(config: HermesConfig) -> bool:
    """Lightweight readiness probe. Must never run a large historical query."""
    try:
        conn = _connect(config)
    except HermesUnavailableError:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except pymysql.MySQLError:
        return False
    finally:
        conn.close()


def normalize_utc_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """The single place request-boundary UTC normalisation happens (Amendment
    A-002, PID-001 §1b items 6-8). Rejects naive datetimes at the public
    HERMES-read boundary; normalises any timezone-aware instant to UTC, so
    equivalent instants expressed in different UTC offsets always normalise
    identically -- never silently assume UTC for a value that wasn't
    explicitly timezone-aware.
    """
    if start.tzinfo is None or end.tzinfo is None:
        raise InvalidRequestError("start/end must be timezone-aware UTC datetimes")
    if start >= end:
        raise InvalidRequestError("start must be strictly before end (end exclusive)")
    return start.astimezone(UTC), end.astimezone(UTC)


def fetch_canonical_rows(
    config: HermesConfig,
    *,
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> list[RawCanonicalRow]:
    """One bulk, parameterised, ascending-ordered range query. The table
    identifier comes only from the fixed internal contract mapping — never
    from caller input.
    """
    if instrument not in ALLOWED_INSTRUMENTS:
        raise InvalidRequestError(f"Instrument {instrument!r} is not in the DARWIN allowlist")

    # Amendment A-002: naive-rejection + UTC normalisation happen BEFORE any
    # connection attempt -- proven in tests/unit/test_utc_semantics.py by
    # pointing at an unreachable host and confirming InvalidRequestError,
    # never HermesUnavailableError, is what's raised.
    start_utc, end_utc = normalize_utc_range(start, end)

    table = canonical_object_for(timeframe)  # closed mapping only, see contract.py
    query = _SELECT_TEMPLATE.format(table=table)

    conn = _connect(config)
    try:
        with conn.cursor() as cur:
            # MariaDB DATETIME columns are naive-by-storage, UTC-by-contract —
            # strip tzinfo for the parameter bind, interpret explicitly as UTC
            # on the way back out. No local-time conversion anywhere.
            cur.execute(
                query,
                (instrument, start_utc.replace(tzinfo=None), end_utc.replace(tzinfo=None)),
            )
            raw_rows = cur.fetchall()
    except pymysql.MySQLError as exc:
        raise HermesUnavailableError(f"HERMES query failed: {exc.__class__.__name__}") from exc
    finally:
        conn.close()

    rows = [
        RawCanonicalRow(
            instrument=r["instrument"],
            timeframe=r["timeframe"],
            open_time=r["open_time"].replace(tzinfo=UTC),
            open=r["open"],
            high=r["high"],
            low=r["low"],
            close=r["close"],
            volume=r["volume"],
            is_closed=r["is_closed"],
            status=r["status"],
            source_timeframe=r["source_timeframe"],
            derivation_policy=r["derivation_policy"],
            source_policy_epoch=r["source_policy_epoch"],
            source_count=r["source_count"],
            expected_source_count=r["expected_source_count"],
            source_coverage=r["source_coverage"],
            gap_state=r["gap_state"],
            derivation_run_id=r["derivation_run_id"],
            derivation_generated_at_utc=(
                r["derivation_generated_at_utc"].replace(tzinfo=UTC)
                if r["derivation_generated_at_utc"] is not None
                else None
            ),
            created_at=(
                r["created_at"].replace(tzinfo=UTC) if r["created_at"] is not None else None
            ),
        )
        for r in raw_rows
    ]

    log_event(
        logger,
        logging.INFO,
        "hermes_rows_fetched",
        instrument=instrument,
        timeframe=timeframe.value,
        table=table,
        row_count=len(rows),
    )

    return validate_rows(
        rows,
        instrument=instrument,
        timeframe=timeframe,
        requested_start=start_utc,
        requested_end=end_utc,
    )


def load_market_dataset(
    config: HermesConfig,
    *,
    instrument: str,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
    adapter_build_version: str,
):
    """Public Foundation entry point matching PID-001 §12's conceptual signature.

    Fetches once, validates, and freezes into one immutable MarketDataset.
    Callers (and later ATHENA/APOLLO) must never call this per-candle — the
    whole point of MarketDataset is that this is the only HERMES query for
    the entire requested workload.
    """
    from darwin.core.identities import new_id
    from darwin.hermes.dataset import build_market_dataset

    # Amendment A-002: resolve the governed InstrumentDefinition BEFORE the
    # HERMES query — an instrument with no governed semantics must never
    # reach a dataset build, even if HERMES itself would answer for it.
    instrument_definition = get_instrument_definition(instrument)

    requested_start_utc, requested_end_utc = normalize_utc_range(start, end)
    rows = fetch_canonical_rows(
        config, instrument=instrument, timeframe=timeframe, start=start, end=end
    )
    return build_market_dataset(
        dataset_id=new_id(),
        instrument=instrument,
        instrument_definition_id=instrument_definition.fingerprint,
        timeframe=timeframe,
        requested_start_utc=requested_start_utc,
        requested_end_utc=requested_end_utc,
        rows=rows,
        adapter_build_version=adapter_build_version,
        loaded_at_utc=datetime.now(UTC),
    )
