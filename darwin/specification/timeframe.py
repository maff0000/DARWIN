"""Instrument-generic, closed timeframe representation (PID-004 sec6/sec12).

A timeframe is a regex-typed code (the same discipline the HSA archaeology
flags as its strongest, most portable finding --
`docs/archaeology/HSA-PID004A-REUSE-ASSESSMENT.md` #8 -- though HSA's own
code spells its regex NUMBER-then-UNIT, e.g. ``5M``/``4H``. This module
deliberately uses UNIT-then-NUMBER instead -- ``H4``, ``H1``, ``M15``,
``M5``, ``D1`` -- to match PID-004 sec12's own worked example verbatim
("context_timeframe = H4", "signal_timeframe = H1", "entry_timeframe =
M15") and the HELIOS archaeology's own predominant spelling. This is a
deliberate, documented divergence from HSA's literal regex, not an
accidental mismatch.

Semantic ROLE is a fully decoupled concept declared per atomic condition /
chain component (see `darwin.specification.composition`) -- never a
single ambient strategy-level timeframe (PID-004 sec6, HELIOS archaeology
finding #6). Nothing in this module names GOLD, XAU or any other
instrument-specific role/timeframe pairing -- that only ever appears as
example fixture data (tests/contract).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from darwin.specification.errors import SpecificationError

_CODE_PATTERN = re.compile(r"^(M|H|D|W)[1-9][0-9]*$")

_UNIT_MINUTES = {
    "M": 1,
    "H": 60,
    "D": 60 * 24,
    "W": 60 * 24 * 7,
}


class InvalidTimeframeError(SpecificationError):
    code = "SPECIFICATION_INVALID_TIMEFRAME"


@dataclass(frozen=True)
class Timeframe:
    """A single governed timeframe code, e.g. ``M5``, ``H1``, ``H4``,
    ``D1``, ``W1``. Deliberately just a validated code + a derived minute
    duration -- no HERMES-specific string mapping lives here (that
    conversion, if ever needed, belongs to a HERMES-boundary adapter, not
    this instrument-generic contract).
    """

    code: str

    def __post_init__(self) -> None:
        if not _CODE_PATTERN.match(self.code):
            raise InvalidTimeframeError(
                f"Invalid timeframe code {self.code!r}; expected e.g. 'M5', 'H1', 'H4', 'D1', 'W1'"
            )

    @property
    def minutes(self) -> int:
        unit = self.code[0]
        count = int(self.code[1:])
        return count * _UNIT_MINUTES[unit]

    def is_finer_than(self, other: Timeframe) -> bool:
        return self.minutes < other.minutes

    def is_coarser_than(self, other: Timeframe) -> bool:
        return self.minutes > other.minutes


def finest(timeframes: list[Timeframe] | tuple[Timeframe, ...]) -> Timeframe:
    """The finest (shortest-duration) timeframe among `timeframes`. Used to
    resolve HELIOS's real "FRAMES expiry counts frames of the finest bound
    timeframe" rule (HELIOS archaeology finding #8) -- never left for a
    caller to compute ad hoc and potentially disagree on.
    """
    if not timeframes:
        raise InvalidTimeframeError("Cannot compute the finest timeframe of an empty collection")
    return min(timeframes, key=lambda tf: tf.minutes)
