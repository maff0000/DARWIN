"""The versioned canonical HERMES historical contract DARWIN is authorised to consume.

PID.md §6 / PID-001 §11: fixed, internal timeframe -> object mapping. No
runtime-supplied arbitrary table name is ever permitted — this module is the
only place table identifiers are chosen, and the mapping is exhaustive and closed.
"""
from __future__ import annotations

from enum import StrEnum

# Canonical HERMES repository + contract commit DARWIN is built against.
# A breaking HERMES contract change requires a new versioned reference here,
# reviewed explicitly — DARWIN must not silently adapt to incompatible changes.
HERMES_REPOSITORY = "github.com/maff0000/hermes"
HERMES_CONTRACT_COMMIT = "3f90e640c9c9c1f4a22ba4ac586a1d478f35a997"
HERMES_CONTRACT_VERSION = "v1"

# Defence-in-depth allowlist of instrument values DARWIN will query HERMES
# for -- an explicit, closed set, never inferred from a caller-supplied
# string. This is NOT a product-boundary decision (Amendment A-001, PID.md
# §1: DARWIN's product capability is multi-instrument) -- it currently
# mirrors HERMES's own canonical historical surface, which as of 2026-09-17
# contains exactly one instrument. Every code path that consumes an
# instrument (validate_rows, MarketDataset, fingerprinting, ResearchRun
# binding) is already instrument-generic; extending this set is purely a
# data-availability fact tied to HERMES onboarding a new instrument, not an
# architecture change here.
ALLOWED_INSTRUMENTS: frozenset[str] = frozenset({"XAU_USD"})


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"


# Fixed, closed mapping — the ONLY source of truth for which physical object a
# timeframe reads from. Never interpolate a table name from user input.
TIMEFRAME_TO_CANONICAL_OBJECT: dict[Timeframe, str] = {
    Timeframe.M1: "canonical_candles_m1",
    Timeframe.M5: "canonical_candles_m5",
    Timeframe.M15: "canonical_candles_m15",
    Timeframe.H1: "canonical_candles_h1",
    Timeframe.H4: "canonical_candles_h4",
    Timeframe.D1: "canonical_candles_d1",
}

UNIFIED_CANONICAL_OBJECT = "canonical_candles"

CANONICAL_COLUMNS: tuple[str, ...] = (
    "instrument",
    "timeframe",
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "is_closed",
    "status",
    "source_timeframe",
    "derivation_policy",
    "source_policy_epoch",
    "source_count",
    "expected_source_count",
    "source_coverage",
    "gap_state",
    "derivation_run_id",
    "derivation_generated_at_utc",
    "created_at",
)


def canonical_object_for(timeframe: Timeframe) -> str:
    """The only function allowed to choose a physical object name. Closed mapping only."""
    try:
        return TIMEFRAME_TO_CANONICAL_OBJECT[timeframe]
    except KeyError as exc:  # pragma: no cover - Timeframe enum makes this unreachable
        raise ValueError(f"No canonical object mapped for timeframe {timeframe!r}") from exc
