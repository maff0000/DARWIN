"""Amendment A-002 (PID-001 §1b) items 6, 7, 8 -- UTC canonical request
boundaries. Must never depend on live HERMES (same discipline as the rest
of tests/unit): every case here is proven WITHOUT a real connection, by
pointing at a host that cannot resolve and confirming the naive/ordering
checks raise InvalidRequestError before any connection is ever attempted --
if the check happened after connecting, a DNS/connection failure would
raise HermesUnavailableError instead, which none of these do.
"""
from datetime import UTC, datetime, timedelta, timezone

import pytest

from darwin.core.config import HermesConfig
from darwin.core.errors import InvalidRequestError
from darwin.hermes.contract import Timeframe
from darwin.hermes.reader import (
    fetch_canonical_rows,
    load_market_dataset,
    normalize_utc_range,
)

_UNREACHABLE_CONFIG = HermesConfig(
    host="host.invalid.never-resolves.example",
    port=3307,
    database="tradingSignals",
    user="darwin_ro",
    password="unused",
)


def test_naive_start_rejected_at_public_boundary_before_any_connection():
    """Item 8: naive user/request datetimes are rejected at the public
    HERMES-read boundary -- never silently defaulted to UTC.
    """
    naive_start = datetime(2026, 9, 16, 15)  # noqa: DTZ001 -- intentionally naive, proving rejection
    aware_end = datetime(2026, 9, 16, 16, tzinfo=UTC)
    with pytest.raises(InvalidRequestError, match="timezone-aware"):
        fetch_canonical_rows(
            _UNREACHABLE_CONFIG, instrument="XAU_USD", timeframe=Timeframe.H1,
            start=naive_start, end=aware_end,
        )


def test_naive_end_rejected_at_public_boundary_before_any_connection():
    aware_start = datetime(2026, 9, 16, 15, tzinfo=UTC)
    naive_end = datetime(2026, 9, 16, 16)  # noqa: DTZ001 -- intentionally naive, proving rejection
    with pytest.raises(InvalidRequestError, match="timezone-aware"):
        fetch_canonical_rows(
            _UNREACHABLE_CONFIG, instrument="XAU_USD", timeframe=Timeframe.H1,
            start=aware_start, end=naive_end,
        )


def test_naive_datetime_rejected_via_the_top_level_load_market_dataset_entry_point():
    """Item 8, at the actual public Foundation entry point (PID-001 §12),
    not just the lower-level fetch function.
    """
    naive_start = datetime(2026, 9, 16, 15)  # noqa: DTZ001 -- intentionally naive, proving rejection
    aware_end = datetime(2026, 9, 16, 16, tzinfo=UTC)
    with pytest.raises(InvalidRequestError, match="timezone-aware"):
        load_market_dataset(
            _UNREACHABLE_CONFIG, instrument="XAU_USD", timeframe=Timeframe.H1,
            start=naive_start, end=aware_end, adapter_build_version="test",
        )


def test_equivalent_instants_in_different_utc_offsets_normalize_identically():
    """Item 7: equivalent instants expressed in different UTC offsets
    normalise to the same canonical UTC range.
    """
    instant_utc = datetime(2026, 9, 16, 15, 0, 0, tzinfo=UTC)
    # Same instant, expressed with a +02:00 offset instead of UTC.
    instant_plus2 = instant_utc.astimezone(timezone(timedelta(hours=2)))
    assert instant_utc != instant_plus2 or instant_utc.utcoffset() != instant_plus2.utcoffset()
    assert instant_utc == instant_plus2  # same instant, different offset representation

    end_utc = instant_utc + timedelta(hours=1)
    end_plus2 = end_utc.astimezone(timezone(timedelta(hours=2)))

    start_a, end_a = normalize_utc_range(instant_utc, end_utc)
    start_b, end_b = normalize_utc_range(instant_plus2, end_plus2)

    assert start_a == start_b
    assert end_a == end_b
    assert start_a.utcoffset() == timedelta(0)
    assert start_b.utcoffset() == timedelta(0)


def test_normalize_utc_range_rejects_non_strictly_ascending_bounds():
    """Item 6: UTC-aware boundaries remain mandatory, and the range itself
    must still be well-formed once normalised.
    """
    t = datetime(2026, 9, 16, 15, tzinfo=UTC)
    with pytest.raises(InvalidRequestError):
        normalize_utc_range(t, t)
