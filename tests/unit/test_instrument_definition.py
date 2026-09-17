"""Amendment A-002 (PID-001 §1b) items 1, 4, 5 -- InstrumentDefinition:
market-unit semantics, instrument-generic coexistence, and the
PRICE_SCALE-vs-market-economics boundary.
"""
import dataclasses
from datetime import timedelta

import pytest

from darwin.hermes.contract import Timeframe
from darwin.hermes.dataset import PRICE_SCALE, build_market_dataset
from darwin.hermes.instrument_definition import (
    InstrumentDefinition,
    UnknownInstrumentDefinitionError,
    get_instrument_definition,
)
from tests.fixtures.hermes_rows import UTC_2026_09_16_15, hourly_series


def test_xau_usd_resolves_to_governed_troy_ounce_semantics():
    """Item 1: XAU_USD resolves to the governed XAU/USD/troy-ounce price
    semantics -- never inferred by parsing the ticker string.
    """
    definition = get_instrument_definition("XAU_USD")
    assert definition.instrument_id == "XAU_USD"
    assert definition.base_asset == "XAU"
    assert definition.quote_asset == "USD"
    assert definition.base_quantity_unit == "TROY_OUNCE"
    assert definition.price_unit == "USD_PER_TROY_OUNCE"
    assert definition.definition_version


def test_unknown_instrument_is_not_fabricated():
    """The ticker is identity; the definition supplies semantics -- an
    instrument with no governed definition must raise, never silently
    synthesize one by parsing the string.
    """
    with pytest.raises(UnknownInstrumentDefinitionError):
        get_instrument_definition("NOT_A_REAL_INSTRUMENT")


def test_fingerprint_is_deterministic_and_field_sensitive():
    d1 = InstrumentDefinition(
        instrument_id="XAU_USD", base_asset="XAU", quote_asset="USD",
        base_quantity_unit="TROY_OUNCE", price_unit="USD_PER_TROY_OUNCE",
        definition_version="v1",
    )
    d2 = InstrumentDefinition(
        instrument_id="XAU_USD", base_asset="XAU", quote_asset="USD",
        base_quantity_unit="TROY_OUNCE", price_unit="USD_PER_TROY_OUNCE",
        definition_version="v1",
    )
    d3 = dataclasses.replace(d1, definition_version="v2")
    assert d1.fingerprint == d2.fingerprint  # same fields -> same identity
    assert d1.fingerprint != d3.fingerprint  # any field change -> different identity


def test_synthetic_second_instrument_definition_coexists_without_xau_assumptions():
    """Item 4: a synthetic second-instrument definition coexists alongside
    XAU_USD, proving InstrumentDefinition is genuinely instrument-generic --
    not by touching HERMES or the real ALLOWED_INSTRUMENTS query allowlist,
    purely as a contract-fixture-level type proof. EUR_USD is NOT registered
    in the governed production registry (it is not a real HERMES instrument
    today) -- constructing it directly here is exactly what proves the type
    itself carries no XAU-specific assumption.
    """
    xau = get_instrument_definition("XAU_USD")
    eur = InstrumentDefinition(
        instrument_id="EUR_USD", base_asset="EUR", quote_asset="USD",
        base_quantity_unit="EURO", price_unit="USD_PER_EUR",
        definition_version="v1",
    )
    assert xau.instrument_id != eur.instrument_id
    assert xau.fingerprint != eur.fingerprint
    # EUR_USD is deliberately not in the real governed registry (see
    # instrument_definition.py's docstring / PID-001 §1a item E,
    # DEFERRED_EXTERNAL_PROOF) -- this is not an oversight, it is the point.
    with pytest.raises(UnknownInstrumentDefinitionError):
        get_instrument_definition("EUR_USD")


def test_market_dataset_preserves_and_binds_instrument_definition_identity():
    """Item 2: MarketDataset preserves/binds the instrument-definition
    identity -- both as a first-class attribute and in its metadata dict
    (the shape persisted/exposed via the API), not merely the bare
    `instrument` string.
    """
    definition = get_instrument_definition("XAU_USD")
    rows = hourly_series(UTC_2026_09_16_15, 2)
    ds = build_market_dataset(
        dataset_id="ds-def-1",
        instrument="XAU_USD",
        instrument_definition_id=definition.fingerprint,
        timeframe=Timeframe.H1,
        requested_start_utc=rows[0].open_time,
        requested_end_utc=rows[-1].open_time + timedelta(hours=1),
        rows=rows,
        adapter_build_version="test",
        loaded_at_utc=UTC_2026_09_16_15,
    )
    assert ds.instrument_definition_id == definition.fingerprint
    assert ds.as_metadata_dict()["instrument_definition_id"] == definition.fingerprint


def test_price_scale_carries_no_tick_pip_or_contract_semantics():
    """Item 5: no code interprets PRICE_SCALE as tick/pip/contract semantics.
    Structural proof: PRICE_SCALE is a bare decimal-scaling integer with no
    tick/pip/contract attribute anywhere near it, and InstrumentDefinition
    -- the type that DOES carry market-unit semantics -- has no tick/pip/
    contract/multiplier field at all (those are explicitly reserved for a
    future, separately governed APOLLO execution contract, PID-001 §1b).
    """
    assert PRICE_SCALE == 100_000
    assert isinstance(PRICE_SCALE, int)

    definition_fields = {f.name for f in dataclasses.fields(InstrumentDefinition)}
    forbidden_execution_concepts = {
        "tick_size", "pip_size", "contract_size", "contract_multiplier",
        "lot_size", "minimum_price_increment", "position_multiplier",
        "tick_value", "minimum_trade_quantity",
    }
    assert definition_fields.isdisjoint(forbidden_execution_concepts)
