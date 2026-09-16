"""Canonical row validation against the HERMES contract (PID-001 §14).

Rejects malformed/non-canonical input. Missing expected candle timestamps are
gaps, not malformed rows — gap detection is handled separately (dataset.py),
never conflated with row rejection here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from darwin.core.errors import HermesContractViolation
from darwin.hermes.contract import Timeframe


@dataclass(frozen=True)
class RawCanonicalRow:
    """One row exactly as returned by a canonical HERMES object, before validation."""

    instrument: str
    timeframe: str
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    is_closed: int | None
    status: str | None
    source_timeframe: str | None
    derivation_policy: str | None
    source_policy_epoch: str | None
    source_count: int | None
    expected_source_count: int | None
    source_coverage: Decimal | None
    gap_state: str | None
    derivation_run_id: str | None
    derivation_generated_at_utc: datetime | None
    created_at: datetime | None


def validate_rows(
    rows: list[RawCanonicalRow],
    *,
    instrument: str,
    timeframe: Timeframe,
    requested_start: datetime,
    requested_end: datetime,
) -> list[RawCanonicalRow]:
    """Validate a bulk-loaded row set. Raises HermesContractViolation on the first
    contract breach found; returns the same rows unchanged (validation only —
    no repair, no silent coercion) when everything holds.
    """
    previous_open_time: datetime | None = None
    seen: set[tuple[str, str, datetime]] = set()

    for row in rows:
        if row.instrument != instrument:
            raise HermesContractViolation(
                f"Row instrument {row.instrument!r} does not match requested {instrument!r}"
            )
        if row.timeframe != timeframe.value:
            raise HermesContractViolation(
                f"Row timeframe {row.timeframe!r} does not match requested {timeframe.value!r}"
            )
        if row.is_closed is not None and row.is_closed != 1:
            raise HermesContractViolation(
                f"Non-closed row at {row.open_time.isoformat()} — Foundation only consumes closed candles"
            )
        if row.status is not None and row.status != "OK":
            raise HermesContractViolation(
                f"Non-OK status {row.status!r} at {row.open_time.isoformat()}"
            )
        if row.source_coverage is not None and row.source_coverage != Decimal("1.0000"):
            raise HermesContractViolation(
                f"source_coverage {row.source_coverage} != 1.0000 at {row.open_time.isoformat()}"
            )
        if row.gap_state is not None and row.gap_state != "NONE":
            raise HermesContractViolation(
                f"gap_state {row.gap_state!r} != NONE on an exposed row at {row.open_time.isoformat()}"
            )
        if row.open_time < requested_start or row.open_time >= requested_end:
            raise HermesContractViolation(
                f"Row open_time {row.open_time.isoformat()} outside requested bounds "
                f"[{requested_start.isoformat()}, {requested_end.isoformat()})"
            )

        key = (row.instrument, row.timeframe, row.open_time)
        if key in seen:
            raise HermesContractViolation(f"Duplicate row for {key}")
        seen.add(key)

        if previous_open_time is not None and row.open_time <= previous_open_time:
            raise HermesContractViolation(
                f"Non-monotonic timestamps: {row.open_time.isoformat()} does not follow "
                f"{previous_open_time.isoformat()}"
            )
        previous_open_time = row.open_time

        _validate_ohlc(row)

        if row.volume is not None and row.volume < 0:
            raise HermesContractViolation(f"Negative volume at {row.open_time.isoformat()}")

        # created_at is a required semantic field; derivation_generated_at_utc is
        # HERMES-contract-documented nullable provenance (e.g. some M15 rows) and
        # must NOT be incorrectly rejected as missing.
        if row.created_at is None:
            raise HermesContractViolation(
                f"Missing required created_at at {row.open_time.isoformat()}"
            )

    return rows


def _validate_ohlc(row: RawCanonicalRow) -> None:
    for field_name in ("open", "high", "low", "close"):
        value = getattr(row, field_name)
        if value is None:
            raise HermesContractViolation(
                f"Malformed OHLC: {field_name} is null at {row.open_time.isoformat()}"
            )
        try:
            Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise HermesContractViolation(
                f"Malformed OHLC: {field_name} is not a valid decimal at {row.open_time.isoformat()}"
            ) from exc

    if row.high < row.low:
        raise HermesContractViolation(
            f"Impossible OHLC: high < low at {row.open_time.isoformat()}"
        )
    if row.high < row.open or row.high < row.close:
        raise HermesContractViolation(
            f"Impossible OHLC: high < open/close at {row.open_time.isoformat()}"
        )
    if row.low > row.open or row.low > row.close:
        raise HermesContractViolation(
            f"Impossible OHLC: low > open/close at {row.open_time.isoformat()}"
        )
