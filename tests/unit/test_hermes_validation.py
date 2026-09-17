from datetime import timedelta

import pytest

from darwin.core.errors import HermesContractViolation
from darwin.hermes.contract import Timeframe
from darwin.hermes.validation import validate_rows
from tests.fixtures.hermes_rows import UTC_2026_09_16_15, direct_h1_row, hourly_series


def _bounds(rows):
    return rows[0].open_time, rows[-1].open_time + timedelta(hours=1)


def test_valid_series_passes_unchanged():
    rows = hourly_series(UTC_2026_09_16_15, 3)
    start, end = _bounds(rows)
    result = validate_rows(rows, instrument="XAU_USD", timeframe=Timeframe.H1, requested_start=start, requested_end=end)
    assert result == rows


def test_wrong_instrument_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, instrument="EUR_USD")
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_wrong_timeframe_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, timeframe="H4")
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_non_closed_row_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, is_closed=0)
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_non_ok_status_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, status="PENDING")
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_incomplete_source_coverage_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, source_coverage="0.5000")
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_non_none_gap_state_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, gap_state="PARTIAL")
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_duplicate_rows_rejected():
    row = direct_h1_row(UTC_2026_09_16_15)
    with pytest.raises(HermesContractViolation):
        validate_rows([row, row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=2))


def test_non_monotonic_timestamps_rejected():
    rows = hourly_series(UTC_2026_09_16_15, 3)
    rows[1], rows[2] = rows[2], rows[1]  # break ascending order
    start, end = UTC_2026_09_16_15, UTC_2026_09_16_15 + timedelta(hours=3)
    with pytest.raises(HermesContractViolation):
        validate_rows(rows, instrument="XAU_USD", timeframe=Timeframe.H1, requested_start=start, requested_end=end)


def test_timestamp_outside_requested_bounds_rejected():
    row = direct_h1_row(UTC_2026_09_16_15)
    with pytest.raises(HermesContractViolation):
        validate_rows(
            [row], instrument="XAU_USD", timeframe=Timeframe.H1,
            requested_start=UTC_2026_09_16_15 + timedelta(hours=1),
            requested_end=UTC_2026_09_16_15 + timedelta(hours=2),
        )


def test_malformed_ohlc_null_field_rejected():
    row = direct_h1_row(UTC_2026_09_16_15)
    row = row.__class__(**{**row.__dict__, "high": None})
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_high_less_than_low_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, high="4340.00000", low="4343.03500")
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_negative_volume_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, volume=-1)
    with pytest.raises(HermesContractViolation):
        validate_rows([row], instrument="XAU_USD", timeframe=Timeframe.H1,
                      requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1))


def test_m15_nullable_derivation_timestamp_not_incorrectly_rejected():
    from tests.fixtures.hermes_rows import m15_row_with_nullable_provenance

    row = m15_row_with_nullable_provenance(UTC_2026_09_16_15)
    result = validate_rows(
        [row], instrument="XAU_USD", timeframe=Timeframe.M15,
        requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(minutes=15),
    )
    assert result == [row]
