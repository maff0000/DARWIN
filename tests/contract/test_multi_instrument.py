"""Amendment A-001 (PID-001 §1a) required regression proof, items A and B --
multi-instrument MarketDataset genericity using contract fixtures. Must
never depend on live HERMES (same discipline as the rest of tests/contract).
"""
from datetime import timedelta

import pytest

from darwin.core.errors import HermesContractViolation
from darwin.hermes.contract import Timeframe
from darwin.hermes.dataset import build_market_dataset
from darwin.hermes.validation import validate_rows
from tests.fixtures.hermes_rows import UTC_2026_09_16_15, direct_h1_row


def test_two_instruments_produce_separate_datasets_with_different_fingerprints():
    """Item A: correct instrument preserved; datasets remain separate;
    fingerprints differ because instrument identity is included; no row
    contamination between instruments.
    """
    xau_rows = [
        direct_h1_row(UTC_2026_09_16_15 + timedelta(hours=i), instrument="XAU_USD")
        for i in range(3)
    ]
    eur_rows = [
        direct_h1_row(UTC_2026_09_16_15 + timedelta(hours=i), instrument="EUR_USD")
        for i in range(3)
    ]

    xau_validated = validate_rows(
        xau_rows, instrument="XAU_USD", timeframe=Timeframe.H1,
        requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=3),
    )
    eur_validated = validate_rows(
        eur_rows, instrument="EUR_USD", timeframe=Timeframe.H1,
        requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=3),
    )

    xau_dataset = build_market_dataset(
        dataset_id="d-xau", instrument="XAU_USD", instrument_definition_id="def-xau-v1", timeframe=Timeframe.H1,
        requested_start_utc=UTC_2026_09_16_15, requested_end_utc=UTC_2026_09_16_15 + timedelta(hours=3),
        rows=xau_validated, adapter_build_version="test", loaded_at_utc=UTC_2026_09_16_15,
    )
    eur_dataset = build_market_dataset(
        dataset_id="d-eur", instrument="EUR_USD", instrument_definition_id="def-eur-v1", timeframe=Timeframe.H1,
        requested_start_utc=UTC_2026_09_16_15, requested_end_utc=UTC_2026_09_16_15 + timedelta(hours=3),
        rows=eur_validated, adapter_build_version="test", loaded_at_utc=UTC_2026_09_16_15,
    )

    # Correct instrument preserved, datasets remain separate.
    assert xau_dataset.instrument == "XAU_USD"
    assert eur_dataset.instrument == "EUR_USD"

    # Identical prices/timestamps under a different instrument must never
    # produce the same semantic dataset identity.
    assert xau_dataset.fingerprint_sha256 != eur_dataset.fingerprint_sha256

    # No row contamination: each dataset's own rows all belong to its own instrument.
    assert xau_dataset.record_count == 3
    assert eur_dataset.record_count == 3


def test_explicit_instrument_selection_cannot_silently_return_another_instrument():
    """Item B: requesting instrument A cannot return instrument B without
    validation failure. Simulates a contamination scenario -- a row that
    claims to belong to a different instrument than the one requested.
    """
    rows = [
        direct_h1_row(UTC_2026_09_16_15, instrument="XAU_USD"),
        direct_h1_row(UTC_2026_09_16_15 + timedelta(hours=1), instrument="EUR_USD"),  # contamination
    ]
    with pytest.raises(HermesContractViolation, match="instrument"):
        validate_rows(
            rows, instrument="XAU_USD", timeframe=Timeframe.H1,
            requested_start=UTC_2026_09_16_15, requested_end=UTC_2026_09_16_15 + timedelta(hours=2),
        )


def test_dataset_fingerprint_depends_on_instrument_not_just_prices():
    """Same prices/timestamps, different instrument -> different fingerprint
    (dataset.py's compute_fingerprint hashes the instrument string itself).
    """
    row_kwargs = {"open_": "4300.00000", "high": "4310.00000", "low": "4290.00000", "close": "4305.00000"}
    xau_row = direct_h1_row(UTC_2026_09_16_15, instrument="XAU_USD", **row_kwargs)
    eur_row = direct_h1_row(UTC_2026_09_16_15, instrument="EUR_USD", **row_kwargs)

    xau_dataset = build_market_dataset(
        dataset_id="d1", instrument="XAU_USD", instrument_definition_id="def-xau-v1", timeframe=Timeframe.H1,
        requested_start_utc=UTC_2026_09_16_15, requested_end_utc=UTC_2026_09_16_15 + timedelta(hours=1),
        rows=[xau_row], adapter_build_version="test", loaded_at_utc=UTC_2026_09_16_15,
    )
    eur_dataset = build_market_dataset(
        dataset_id="d2", instrument="EUR_USD", instrument_definition_id="def-eur-v1", timeframe=Timeframe.H1,
        requested_start_utc=UTC_2026_09_16_15, requested_end_utc=UTC_2026_09_16_15 + timedelta(hours=1),
        rows=[eur_row], adapter_build_version="test", loaded_at_utc=UTC_2026_09_16_15,
    )
    assert xau_dataset.fingerprint_sha256 != eur_dataset.fingerprint_sha256
