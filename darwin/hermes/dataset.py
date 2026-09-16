"""The immutable in-memory MarketDataset (PID.md §7, PID-001 §15-19).

Exact fixed-point representation of HERMES DECIMAL(12,5) OHLC as int64, so
wick highs/lows remain exact and deterministic rather than subtly changed by
binary floating point. Immutable to consumers. Deterministic SHA-256
fingerprint for identical canonical input. Never fabricates missing candles.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import numpy as np

from darwin.core.errors import HermesContractViolation
from darwin.hermes.contract import Timeframe
from darwin.hermes.validation import RawCanonicalRow

# HERMES canonical price columns are DECIMAL(12,5) — five decimal places.
# Scaling by 10**5 gives an exact integer representation with no binary
# floating-point rounding of a canonical market fact.
PRICE_SCALE = 100_000

TIMEFRAME_STEP_SECONDS: dict[Timeframe, int] = {
    Timeframe.M1: 60,
    Timeframe.M5: 300,
    Timeframe.M15: 900,
    Timeframe.H1: 3_600,
    Timeframe.H4: 14_400,
    Timeframe.D1: 86_400,
}

_MAX_REPORTED_GAPS = 50


def to_fixed_point(value: Decimal) -> int:
    """Exact DECIMAL(12,5) -> int64 conversion. Never routes through float."""
    scaled = (value * PRICE_SCALE).to_integral_exact()
    return int(scaled)


def from_fixed_point(value: int) -> Decimal:
    return Decimal(value) / PRICE_SCALE


def _epoch_seconds_utc(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return int(dt.timestamp())


@dataclass(frozen=True)
class GapSummary:
    expected_count: int
    actual_count: int
    missing_count: int
    missing_open_times_utc: tuple[str, ...]  # ISO-8601, capped at _MAX_REPORTED_GAPS
    truncated: bool

    def as_dict(self) -> dict:
        return {
            "expected_count": self.expected_count,
            "actual_count": self.actual_count,
            "missing_count": self.missing_count,
            "missing_open_times_utc": list(self.missing_open_times_utc),
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class MarketDataset:
    """Immutable in-memory market-data boundary. ATHENA/APOLLO consume this and
    must never know or depend on HERMES's physical storage layout.
    """

    dataset_id: str
    instrument: str
    timeframe: Timeframe
    requested_start_utc: datetime
    requested_end_utc: datetime
    hermes_contract_version: str
    hermes_contract_commit: str
    adapter_build_version: str
    loaded_at_utc: datetime
    fingerprint_sha256: str
    gap_summary: GapSummary

    open_time_epoch_s: np.ndarray  # int64, ascending, UTC epoch seconds
    open_fp: np.ndarray  # int64 fixed-point (PRICE_SCALE)
    high_fp: np.ndarray
    low_fp: np.ndarray
    close_fp: np.ndarray
    volume: np.ndarray  # int64

    def __post_init__(self) -> None:
        for arr in (
            self.open_time_epoch_s,
            self.open_fp,
            self.high_fp,
            self.low_fp,
            self.close_fp,
            self.volume,
        ):
            arr.flags.writeable = False

    @property
    def record_count(self) -> int:
        return int(self.open_time_epoch_s.shape[0])

    @property
    def actual_first_open_utc(self) -> datetime | None:
        if self.record_count == 0:
            return None
        return datetime.fromtimestamp(int(self.open_time_epoch_s[0]), tz=UTC)

    @property
    def actual_last_open_utc(self) -> datetime | None:
        if self.record_count == 0:
            return None
        return datetime.fromtimestamp(int(self.open_time_epoch_s[-1]), tz=UTC)

    def high_low_at(self, index: int) -> tuple[Decimal, Decimal]:
        """Exact wick high/low at a row index, recovered losslessly from fixed-point."""
        return from_fixed_point(int(self.high_fp[index])), from_fixed_point(int(self.low_fp[index]))

    def as_metadata_dict(self) -> dict:
        """Metadata only — never the candle arrays themselves (PostgreSQL persists
        metadata/fingerprint, not a duplicate of HERMES market history).
        """
        return {
            "dataset_id": self.dataset_id,
            "instrument": self.instrument,
            "timeframe": self.timeframe.value,
            "requested_start_utc": self.requested_start_utc.isoformat(),
            "requested_end_utc": self.requested_end_utc.isoformat(),
            "actual_first_open_utc": (
                self.actual_first_open_utc.isoformat() if self.actual_first_open_utc else None
            ),
            "actual_last_open_utc": (
                self.actual_last_open_utc.isoformat() if self.actual_last_open_utc else None
            ),
            "record_count": self.record_count,
            "hermes_contract_version": self.hermes_contract_version,
            "hermes_contract_commit": self.hermes_contract_commit,
            "adapter_build_version": self.adapter_build_version,
            "loaded_at_utc": self.loaded_at_utc.isoformat(),
            "fingerprint_sha256": self.fingerprint_sha256,
            "gap_summary": self.gap_summary.as_dict(),
        }


def compute_fingerprint(
    *,
    instrument: str,
    timeframe: Timeframe,
    open_time_epoch_s: np.ndarray,
    open_fp: np.ndarray,
    high_fp: np.ndarray,
    low_fp: np.ndarray,
    close_fp: np.ndarray,
    volume: np.ndarray,
) -> str:
    """Deterministic SHA-256 over canonical semantic content only.

    Explicitly excludes: load timestamp, Python object identity, DB row
    surrogate IDs, derivation_run_id, and machine/host — two independent loads
    of unchanged HERMES rows for the same range must produce the same value.

    Serialisation: `instrument` UTF-8, NUL, `timeframe` UTF-8, NUL, then for
    each row in ascending open_time order: open_time_epoch_s (int64 big-endian),
    open/high/low/close (int64 big-endian fixed-point), volume (int64 big-endian).
    """
    hasher = hashlib.sha256()
    hasher.update(instrument.encode("utf-8"))
    hasher.update(b"\x00")
    hasher.update(timeframe.value.encode("utf-8"))
    hasher.update(b"\x00")

    n = open_time_epoch_s.shape[0]
    for i in range(n):
        hasher.update(
            struct.pack(
                ">qqqqqq",
                int(open_time_epoch_s[i]),
                int(open_fp[i]),
                int(high_fp[i]),
                int(low_fp[i]),
                int(close_fp[i]),
                int(volume[i]),
            )
        )
    return hasher.hexdigest()


def compute_gap_summary(
    *,
    timeframe: Timeframe,
    requested_start_utc: datetime,
    requested_end_utc: datetime,
    open_time_epoch_s: np.ndarray,
) -> GapSummary:
    """Raw fixed-step expected-grid gap detection. Never fabricates, never
    forward-fills, never interpolates, never invents a trading-calendar
    doctrine — see PID-001 §18.
    """
    step = TIMEFRAME_STEP_SECONDS[timeframe]
    start_epoch = _epoch_seconds_utc(requested_start_utc)
    end_epoch = _epoch_seconds_utc(requested_end_utc)

    expected = set(range(start_epoch, end_epoch, step))
    actual = {int(v) for v in open_time_epoch_s.tolist()}
    missing = sorted(expected - actual)

    missing_iso = tuple(
        datetime.fromtimestamp(ts, tz=UTC).isoformat() for ts in missing[:_MAX_REPORTED_GAPS]
    )
    return GapSummary(
        expected_count=len(expected),
        actual_count=len(actual),
        missing_count=len(missing),
        missing_open_times_utc=missing_iso,
        truncated=len(missing) > _MAX_REPORTED_GAPS,
    )


def build_market_dataset(
    *,
    dataset_id: str,
    instrument: str,
    timeframe: Timeframe,
    requested_start_utc: datetime,
    requested_end_utc: datetime,
    rows: list[RawCanonicalRow],
    adapter_build_version: str,
    loaded_at_utc: datetime,
) -> MarketDataset:
    """Construct the immutable MarketDataset from already-validated rows.

    Rows must already have passed `darwin.hermes.validation.validate_rows` —
    this function does not re-validate contract semantics, only converts and
    freezes.
    """
    if not rows:
        empty = np.array([], dtype=np.int64)
        fingerprint = compute_fingerprint(
            instrument=instrument,
            timeframe=timeframe,
            open_time_epoch_s=empty,
            open_fp=empty,
            high_fp=empty,
            low_fp=empty,
            close_fp=empty,
            volume=empty,
        )
        gap_summary = compute_gap_summary(
            timeframe=timeframe,
            requested_start_utc=requested_start_utc,
            requested_end_utc=requested_end_utc,
            open_time_epoch_s=empty,
        )
        return MarketDataset(
            dataset_id=dataset_id,
            instrument=instrument,
            timeframe=timeframe,
            requested_start_utc=requested_start_utc,
            requested_end_utc=requested_end_utc,
            hermes_contract_version="v1",
            hermes_contract_commit="",
            adapter_build_version=adapter_build_version,
            loaded_at_utc=loaded_at_utc,
            fingerprint_sha256=fingerprint,
            gap_summary=gap_summary,
            open_time_epoch_s=empty,
            open_fp=empty,
            high_fp=empty,
            low_fp=empty,
            close_fp=empty,
            volume=empty,
        )

    from darwin.hermes.contract import HERMES_CONTRACT_COMMIT, HERMES_CONTRACT_VERSION

    n = len(rows)
    open_time_epoch_s = np.empty(n, dtype=np.int64)
    open_fp = np.empty(n, dtype=np.int64)
    high_fp = np.empty(n, dtype=np.int64)
    low_fp = np.empty(n, dtype=np.int64)
    close_fp = np.empty(n, dtype=np.int64)
    volume = np.empty(n, dtype=np.int64)

    for i, row in enumerate(rows):
        open_time_epoch_s[i] = _epoch_seconds_utc(row.open_time)
        open_fp[i] = to_fixed_point(row.open)
        high_fp[i] = to_fixed_point(row.high)
        low_fp[i] = to_fixed_point(row.low)
        close_fp[i] = to_fixed_point(row.close)
        volume[i] = int(row.volume) if row.volume is not None else 0

    if not np.all(np.diff(open_time_epoch_s) > 0):
        raise HermesContractViolation("Rows are not strictly ascending by open_time")

    fingerprint = compute_fingerprint(
        instrument=instrument,
        timeframe=timeframe,
        open_time_epoch_s=open_time_epoch_s,
        open_fp=open_fp,
        high_fp=high_fp,
        low_fp=low_fp,
        close_fp=close_fp,
        volume=volume,
    )
    gap_summary = compute_gap_summary(
        timeframe=timeframe,
        requested_start_utc=requested_start_utc,
        requested_end_utc=requested_end_utc,
        open_time_epoch_s=open_time_epoch_s,
    )

    return MarketDataset(
        dataset_id=dataset_id,
        instrument=instrument,
        timeframe=timeframe,
        requested_start_utc=requested_start_utc,
        requested_end_utc=requested_end_utc,
        hermes_contract_version=HERMES_CONTRACT_VERSION,
        hermes_contract_commit=HERMES_CONTRACT_COMMIT,
        adapter_build_version=adapter_build_version,
        loaded_at_utc=loaded_at_utc,
        fingerprint_sha256=fingerprint,
        gap_summary=gap_summary,
        open_time_epoch_s=open_time_epoch_s,
        open_fp=open_fp,
        high_fp=high_fp,
        low_fp=low_fp,
        close_fp=close_fp,
        volume=volume,
    )
