"""Contract tests against fixtures matching the real HERMES v1 canonical
contract (PID-001 §28). Must never depend on live HERMES.
"""
from datetime import timedelta

import pytest

from darwin.core.errors import HermesContractViolation
from darwin.hermes.contract import Timeframe
from darwin.hermes.validation import validate_rows
from tests.fixtures.hermes_rows import (
    UTC_2026_09_16_15,
    derived_d1_row,
    derived_h4_row,
    direct_h1_row,
    m15_row_with_nullable_provenance,
)


def test_direct_h1_row_accepted():
    row = direct_h1_row(UTC_2026_09_16_15)
    result = validate_rows(
        [row], instrument="XAU_USD", timeframe=Timeframe.H1,
        requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1),
    )
    assert result == [row]


def test_derived_h4_row_accepted():
    row = derived_h4_row(UTC_2026_09_16_15)
    result = validate_rows(
        [row], instrument="XAU_USD", timeframe=Timeframe.H4,
        requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=4),
    )
    assert result == [row]
    assert row.source_timeframe == "H1"


def test_derived_d1_row_accepted():
    row = derived_d1_row(UTC_2026_09_16_15)
    result = validate_rows(
        [row], instrument="XAU_USD", timeframe=Timeframe.D1,
        requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(days=1),
    )
    assert result == [row]
    assert row.source_timeframe == "H4"


def test_m15_nullable_provenance_accepted():
    row = m15_row_with_nullable_provenance(UTC_2026_09_16_15)
    assert row.derivation_generated_at_utc is None
    result = validate_rows(
        [row], instrument="XAU_USD", timeframe=Timeframe.M15,
        requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(minutes=15),
    )
    assert result == [row]


def test_malformed_row_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, high="1.00000")  # high below low/open/close
    with pytest.raises(HermesContractViolation):
        validate_rows(
            [row], instrument="XAU_USD", timeframe=Timeframe.H1,
            requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1),
        )


def test_duplicate_row_rejected():
    row = direct_h1_row(UTC_2026_09_16_15)
    with pytest.raises(HermesContractViolation):
        validate_rows(
            [row, row], instrument="XAU_USD", timeframe=Timeframe.H1,
            requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=2),
        )


def test_non_ok_row_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, status="STALE")
    with pytest.raises(HermesContractViolation):
        validate_rows(
            [row], instrument="XAU_USD", timeframe=Timeframe.H1,
            requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1),
        )


def test_non_closed_row_rejected():
    row = direct_h1_row(UTC_2026_09_16_15, is_closed=0)
    with pytest.raises(HermesContractViolation):
        validate_rows(
            [row], instrument="XAU_USD", timeframe=Timeframe.H1,
            requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=1),
        )


def test_ordering_violation_rejected():
    rows = [direct_h1_row(UTC_2026_09_16_15 + timedelta(hours=i)) for i in range(3)]
    rows[0], rows[1] = rows[1], rows[0]
    with pytest.raises(HermesContractViolation):
        validate_rows(
            rows, instrument="XAU_USD", timeframe=Timeframe.H1,
            requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=3),
        )
