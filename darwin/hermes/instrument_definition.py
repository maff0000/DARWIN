"""Instrument-generic market-unit semantics (Amendment A-002, PID.md §7a,
PID-001 §1b, docs/architecture/market-dataset.md).

A numeric OHLC price has no meaning without instrument semantics --
`XAU_USD = 4300.00000` means `4300 USD per troy ounce of gold`, not merely
`4300`. `InstrumentDefinition` supplies that meaning; the ticker
(`InstrumentId`, a bare string here) remains identity. Never inferred
dynamically by parsing the ticker -- only ever looked up from the closed,
governed registry below.

This is market-data interpretation only. It does NOT define broker lot
size, contract multiplier, tick size, or any other execution/economics
concept -- those are explicitly reserved for a future, separately governed
APOLLO execution contract (PID-001 §1b "Market semantics vs execution
economics").
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from darwin.core.errors import DarwinError


class UnknownInstrumentDefinitionError(DarwinError):
    """No governed InstrumentDefinition exists for the requested instrument_id."""

    code = "UNKNOWN_INSTRUMENT_DEFINITION"


@dataclass(frozen=True)
class InstrumentDefinition:
    """Minimal, instrument-generic market-unit semantics. Never XAU-specific
    as a type -- see the two-definition contract-fixture proof in
    tests/unit/test_instrument_definition.py.
    """

    instrument_id: str
    base_asset: str
    quote_asset: str
    base_quantity_unit: str
    price_unit: str
    definition_version: str

    @property
    def fingerprint(self) -> str:
        """Deterministic identity for this exact definition. Changes if and only
        if any semantic field changes -- binding this into a MarketDataset's
        fingerprint (PID-001 §1b/§17) means a later semantic redefinition can
        never silently make old research mean something different.
        """
        hasher = hashlib.sha256()
        for field_value in (
            self.instrument_id,
            self.base_asset,
            self.quote_asset,
            self.base_quantity_unit,
            self.price_unit,
            self.definition_version,
        ):
            hasher.update(field_value.encode("utf-8"))
            hasher.update(b"\x00")
        return hasher.hexdigest()


# The governed, closed registry of real DARWIN instrument definitions.
# Extending this is a product/data decision (mirrors what HERMES's canonical
# surface + the Architect's ruling actually support), never something a
# caller-supplied string can add to or infer.
_REGISTRY: dict[str, InstrumentDefinition] = {
    "XAU_USD": InstrumentDefinition(
        instrument_id="XAU_USD",
        base_asset="XAU",
        quote_asset="USD",
        base_quantity_unit="TROY_OUNCE",
        price_unit="USD_PER_TROY_OUNCE",
        definition_version="v1",
    ),
}


def list_instrument_definitions() -> list[InstrumentDefinition]:
    """All governed definitions, for read-only ARENA browsing (PID-002 sec12)."""
    return list(_REGISTRY.values())


def get_instrument_definition(instrument_id: str) -> InstrumentDefinition:
    """The only supported way to obtain a governed InstrumentDefinition.
    Raises for anything not in the closed registry -- never fabricates or
    infers one from the instrument_id string.
    """
    try:
        return _REGISTRY[instrument_id]
    except KeyError as exc:
        raise UnknownInstrumentDefinitionError(
            f"No governed InstrumentDefinition for instrument_id {instrument_id!r}"
        ) from exc
