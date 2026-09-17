"""Fixtures matching the real HERMES v1 canonical contract, for contract/unit
tests that must never depend on live HERMES (PID-001 §28).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from darwin.hermes.validation import RawCanonicalRow


def direct_h1_row(
    open_time: datetime,
    *,
    instrument: str = "XAU_USD",
    timeframe: str = "H1",
    source_timeframe: str | None = None,
    open_: str = "4344.52500",
    high: str = "4361.00000",
    low: str = "4343.03500",
    close: str = "4352.62500",
    volume: int = 5483,
    is_closed: int | None = 1,
    status: str | None = "OK",
    source_coverage: str | None = "1.0000",
    gap_state: str | None = "NONE",
    derivation_generated_at_utc: datetime | None = None,
) -> RawCanonicalRow:
    return RawCanonicalRow(
        instrument=instrument,
        timeframe=timeframe,
        open_time=open_time,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        is_closed=is_closed,
        status=status,
        source_timeframe=source_timeframe if source_timeframe is not None else timeframe,
        derivation_policy="NONE_DIRECT",
        source_policy_epoch="DIRECT_NATIVE_V1",
        source_count=1,
        expected_source_count=1,
        source_coverage=Decimal(source_coverage) if source_coverage is not None else None,
        gap_state=gap_state,
        derivation_run_id=f"DIRECT_{timeframe}:{int(open_time.timestamp())}",
        derivation_generated_at_utc=derivation_generated_at_utc,
        created_at=open_time,
    )


def derived_h4_row(open_time: datetime, **overrides) -> RawCanonicalRow:
    base = {"timeframe": "H4", "source_timeframe": "H1"}
    base.update(overrides)
    return direct_h1_row(open_time, **base)


def derived_d1_row(open_time: datetime, **overrides) -> RawCanonicalRow:
    base = {"timeframe": "D1", "source_timeframe": "H4"}
    base.update(overrides)
    return direct_h1_row(open_time, **base)


def m15_row_with_nullable_provenance(open_time: datetime, **overrides) -> RawCanonicalRow:
    """M15 rows may legitimately have a null derivation_generated_at_utc — this
    must never be incorrectly rejected as a missing required field.
    """
    base = {"timeframe": "M15", "source_timeframe": "M15", "derivation_generated_at_utc": None}
    base.update(overrides)
    return direct_h1_row(open_time, **base)


def hourly_series(start: datetime, count: int, **overrides) -> list[RawCanonicalRow]:
    return [direct_h1_row(start + timedelta(hours=i), **overrides) for i in range(count)]


UTC_2026_09_16_15 = datetime(2026, 9, 16, 15, 0, 0, tzinfo=UTC)
