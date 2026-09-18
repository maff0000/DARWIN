"""Instrument applicability, session/timezone/DST, and intrabar-ambiguity
semantics (PID-004 sec11/sec13/sec21).

Instrument-generic by construction: nothing here hardcodes `XAU_USD` as a
type-level concept -- an instrument id is just a plain governed string
(validated elsewhere against `darwin.hermes.instrument_definition`'s
closed registry when/if a StrategyVersion is bound to real market data;
this contract phase does not require that binding to exist yet).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.specification.errors import SpecificationError


class InstrumentApplicabilityKind(StrEnum):
    EXPLICIT_SINGLE = "EXPLICIT_SINGLE"
    EXPLICIT_SET = "EXPLICIT_SET"
    INSTRUMENT_GENERIC = "INSTRUMENT_GENERIC"


@dataclass(frozen=True)
class InstrumentApplicability:
    """PID-004 sec11. `INSTRUMENT_GENERIC` requires explicit
    `generic_criteria` (e.g. "quote_asset == USD", "has IMPLIED_VOLATILITY
    fact class onboarded") -- "instrument-generic does not mean all
    tickers probably work"; no instrument is ever inferred by parsing a
    source ticker string anywhere in this package.
    """

    kind: InstrumentApplicabilityKind
    instrument_ids: tuple[str, ...] = ()
    generic_criteria: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind == InstrumentApplicabilityKind.EXPLICIT_SINGLE:
            if len(self.instrument_ids) != 1:
                raise SpecificationError("EXPLICIT_SINGLE requires exactly one instrument_id")
            if self.generic_criteria:
                raise SpecificationError("EXPLICIT_SINGLE must not carry generic_criteria")
        elif self.kind == InstrumentApplicabilityKind.EXPLICIT_SET:
            if len(self.instrument_ids) < 1:
                raise SpecificationError("EXPLICIT_SET requires at least one instrument_id")
            if self.generic_criteria:
                raise SpecificationError("EXPLICIT_SET must not carry generic_criteria")
        elif self.kind == InstrumentApplicabilityKind.INSTRUMENT_GENERIC:
            if self.instrument_ids:
                raise SpecificationError("INSTRUMENT_GENERIC must not carry an explicit instrument_ids list")
            if not self.generic_criteria:
                raise SpecificationError(
                    "INSTRUMENT_GENERIC requires explicit generic_criteria -- 'any instrument "
                    "probably works' is never a valid declaration (PID-004 sec11)"
                )
        else:
            raise SpecificationError(f"Unknown InstrumentApplicabilityKind: {self.kind!r}")


class DstHandling(StrEnum):
    """PID-004 sec13. Only one governed value in this contract phase --
    session resolution defers entirely to the named IANA timezone's own
    DST rules, never a hand-rolled offset table."""

    FOLLOW_IANA_TIMEZONE_RULES = "FOLLOW_IANA_TIMEZONE_RULES"


@dataclass(frozen=True)
class SessionSpec:
    """PID-004 sec13. `iana_timezone` must be a real IANA zone name (e.g.
    ``America/New_York``) -- validated via the stdlib `zoneinfo` database,
    never a bare UTC-offset guess. `weekdays` uses 0=Mon..6=Sun. The
    evaluator (not built in this phase) resolves this onto the canonical
    UTC timeline; nothing here assumes a host-local clock.
    """

    iana_timezone: str
    local_start: str
    local_end: str
    weekdays: tuple[int, ...]
    dst_handling: DstHandling
    cross_midnight: bool = False

    def __post_init__(self) -> None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(self.iana_timezone)
        except ZoneInfoNotFoundError as exc:
            raise SpecificationError(f"Not a real IANA timezone: {self.iana_timezone!r}") from exc
        for day in self.weekdays:
            if not (0 <= day <= 6):
                raise SpecificationError(f"Invalid weekday {day!r}; must be 0..6")
        if not self.weekdays:
            raise SpecificationError("SessionSpec requires at least one weekday")
        for label, value in (("local_start", self.local_start), ("local_end", self.local_end)):
            parts = value.split(":")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                raise SpecificationError(f"SessionSpec.{label} must be 'HH:MM', got {value!r}")
            hour, minute = int(parts[0]), int(parts[1])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise SpecificationError(f"SessionSpec.{label} out of range: {value!r}")


class IntrabarAmbiguityPolicy(StrEnum):
    """PID-004 sec21. `NOT_APPLICABLE` is the required explicit value for
    a strategy with no active price-touch/same-candle-ordering ambiguity
    concern -- never silently omitted (PID-004 sec33)."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONSERVATIVE_SL_FIRST = "CONSERVATIVE_SL_FIRST"
