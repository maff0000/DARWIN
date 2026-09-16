from datetime import timedelta
from decimal import Decimal

import pytest

from darwin.hermes.contract import Timeframe
from darwin.hermes.dataset import build_market_dataset
from tests.fixtures.hermes_rows import UTC_2026_09_16_15, hourly_series


def _dataset(rows=None):
    rows = rows if rows is not None else hourly_series(UTC_2026_09_16_15, 5)
    start = rows[0].open_time
    end = rows[-1].open_time + timedelta(hours=1)
    return build_market_dataset(
        dataset_id="ds-1",
        instrument="XAU_USD",
        timeframe=Timeframe.H1,
        requested_start_utc=start,
        requested_end_utc=end,
        rows=rows,
        adapter_build_version="test",
        loaded_at_utc=UTC_2026_09_16_15,
    )


def test_fingerprint_deterministic_for_identical_input():
    rows = hourly_series(UTC_2026_09_16_15, 5)
    ds1 = _dataset(rows)
    ds2 = _dataset(hourly_series(UTC_2026_09_16_15, 5))  # independent second load
    assert ds1.fingerprint_sha256 == ds2.fingerprint_sha256
    assert ds1.fingerprint_sha256 != ""


def test_fingerprint_changes_when_a_price_changes():
    rows_a = hourly_series(UTC_2026_09_16_15, 3)
    rows_b = hourly_series(UTC_2026_09_16_15, 3)
    rows_b[1] = rows_b[1].__class__(**{**rows_b[1].__dict__, "close": Decimal("1.00000")})
    ds_a = _dataset(rows_a)
    ds_b = _dataset(rows_b)
    assert ds_a.fingerprint_sha256 != ds_b.fingerprint_sha256


def test_fingerprint_independent_of_load_timestamp():
    rows = hourly_series(UTC_2026_09_16_15, 3)
    ds1 = _dataset(rows)
    ds2 = build_market_dataset(
        dataset_id="different-id",
        instrument="XAU_USD",
        timeframe=Timeframe.H1,
        requested_start_utc=rows[0].open_time,
        requested_end_utc=rows[-1].open_time + timedelta(hours=1),
        rows=rows,
        adapter_build_version="test",
        loaded_at_utc=UTC_2026_09_16_15 + timedelta(days=30),  # different load time
    )
    assert ds1.fingerprint_sha256 == ds2.fingerprint_sha256
    assert ds1.dataset_id != ds2.dataset_id  # identity differs, fingerprint does not


def test_wick_high_low_preserved_exactly():
    rows = hourly_series(UTC_2026_09_16_15, 1, high="4361.00000", low="4343.03500")
    ds = _dataset(rows)
    high, low = ds.high_low_at(0)
    assert high == Decimal("4361.00000")
    assert low == Decimal("4343.03500")


def test_dataset_immutable():
    ds = _dataset()
    with pytest.raises(ValueError):
        ds.open_fp[0] = 0
    with pytest.raises(ValueError):
        ds.high_fp[:] = 0


def test_gap_detection_finds_missing_hour():
    rows = hourly_series(UTC_2026_09_16_15, 3)
    del rows[1]  # remove the middle hour -> one missing expected open
    start = rows[0].open_time
    end = rows[-1].open_time + timedelta(hours=1)
    ds = build_market_dataset(
        dataset_id="ds-gap",
        instrument="XAU_USD",
        timeframe=Timeframe.H1,
        requested_start_utc=start,
        requested_end_utc=end,
        rows=rows,
        adapter_build_version="test",
        loaded_at_utc=UTC_2026_09_16_15,
    )
    assert ds.gap_summary.missing_count == 1
    assert ds.record_count == 2


def test_gap_detection_never_fabricates_rows():
    rows = hourly_series(UTC_2026_09_16_15, 3)
    del rows[1]
    ds = _dataset(rows)
    # record_count reflects only rows actually returned by HERMES, never a
    # fabricated/forward-filled/interpolated value.
    assert ds.record_count == len(rows)


def test_empty_dataset_has_stable_fingerprint_and_no_crash():
    ds = build_market_dataset(
        dataset_id="ds-empty",
        instrument="XAU_USD",
        timeframe=Timeframe.H1,
        requested_start_utc=UTC_2026_09_16_15,
        requested_end_utc=UTC_2026_09_16_15 + timedelta(hours=1),
        rows=[],
        adapter_build_version="test",
        loaded_at_utc=UTC_2026_09_16_15,
    )
    assert ds.record_count == 0
    assert ds.fingerprint_sha256
    assert ds.actual_first_open_utc is None
