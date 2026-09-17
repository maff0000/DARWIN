"""First-class data requirement model (PID-004 sec24/sec24A/sec25).

A `DataRequirement` records what evidence a strategy NEEDS. It never
records whether DARWIN currently has that evidence -- that is
`darwin.specification.readiness.DataReadinessAssessment`'s job, and the
two are deliberately never merged into one object (PID-004 sec26:
"Critical separation -- requirement vs availability").
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.specification.causal import CausalTimingPolicy
from darwin.specification.errors import SpecificationError
from darwin.specification.facts import DataAuthorityClass, FactReferenceKind
from darwin.specification.timeframe import Timeframe

# Re-exported for convenience -- DataRequirement callers commonly need both
# the fact/authority vocabulary and the causal-timing vocabulary together.
__all__ = [
    "CausalTimingPolicy",
    "DataAuthorityClass",
    "DataRequirement",
    "FactClass",
    "HistoricalDepthRequirement",
    "HistoricalDepthUnit",
]


class FactClass(StrEnum):
    """PID-004 sec24. Closed, governed extension model -- representative
    classes needed by this contract phase's fixtures, not a universal
    ontology (PID-004 sec24: "Governed schema evolution is required for
    additions.")."""

    MARKET_OHLCV = "MARKET_OHLCV"
    OPTIONS_CHAIN = "OPTIONS_CHAIN"
    IMPLIED_VOLATILITY = "IMPLIED_VOLATILITY"
    OPEN_INTEREST = "OPEN_INTEREST"
    FUTURES_CURVE = "FUTURES_CURVE"
    ORDER_BOOK = "ORDER_BOOK"
    ECONOMIC_SURPRISE = "ECONOMIC_SURPRISE"
    NEWS_CONTEXT = "NEWS_CONTEXT"
    PREDICTION_MARKET = "PREDICTION_MARKET"
    FUNDING_RATE = "FUNDING_RATE"
    ON_CHAIN = "ON_CHAIN"
    OTHER_GOVERNED_FACT = "OTHER_GOVERNED_FACT"


class HistoricalDepthUnit(StrEnum):
    BARS = "BARS"
    DAYS = "DAYS"
    YEARS = "YEARS"


@dataclass(frozen=True)
class HistoricalDepthRequirement:
    count: int
    unit: HistoricalDepthUnit

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise SpecificationError("HistoricalDepthRequirement.count must be positive")


# Fact classes for which causal publish/observe/effective timing is a real
# concern (PID-004 sec24A: "This applies especially to... news, economic
# releases, prediction markets, expectations, revised macroeconomic
# series, externally observed context."). MARKET_OHLCV and the other
# canonical-market classes are deliberately excluded -- HERMES canonical
# bars have no publication-revision concern of this kind in this contract
# phase.
CAUSALLY_SENSITIVE_FACT_CLASSES: frozenset[FactClass] = frozenset(
    {FactClass.ECONOMIC_SURPRISE, FactClass.NEWS_CONTEXT, FactClass.PREDICTION_MARKET}
)


@dataclass(frozen=True)
class DataRequirement:
    """PID-004 sec24. `fact_reference_kind` records whether the strategy's
    own reference to this requirement is canonical or specification-derived
    (see darwin.specification.facts) -- it is set once at construction from
    the actual `FactReference` the requirement backs, never independently
    guessable.

    `causal_timing_policy` is mandatory (never silently omitted) and MUST
    be `NOT_APPLICABLE` for anything outside `CAUSALLY_SENSITIVE_FACT_
    CLASSES`, and MUST NOT be `NOT_APPLICABLE` for anything inside it --
    both directions checked here so a NEWS_CONTEXT requirement can never
    quietly skip declaring its causal timing need (PID-004 sec31A).
    """

    requirement_id: str
    display_name: str
    fact_class: FactClass
    fact_reference_kind: FactReferenceKind
    authority_class: DataAuthorityClass
    instrument_applicability: tuple[str, ...]
    timeframe: Timeframe | None
    required_historical_depth: HistoricalDepthRequirement
    units: str | None
    required_fields: tuple[str, ...]
    causal_timing_policy: CausalTimingPolicy
    mandatory: bool = True

    def __post_init__(self) -> None:
        if not self.requirement_id or not self.requirement_id.strip():
            raise SpecificationError("DataRequirement requires a non-empty requirement_id")
        if not self.required_fields:
            raise SpecificationError(
                f"DataRequirement {self.requirement_id!r} requires at least one required_fields entry"
            )
        causally_sensitive = self.fact_class in CAUSALLY_SENSITIVE_FACT_CLASSES
        if causally_sensitive and self.causal_timing_policy == CausalTimingPolicy.NOT_APPLICABLE:
            raise SpecificationError(
                f"DataRequirement {self.requirement_id!r} ({self.fact_class.value}) is causally "
                f"sensitive and must declare an explicit causal_timing_policy other than "
                f"NOT_APPLICABLE (PID-004 sec24A/sec31A)"
            )
        if not causally_sensitive and self.causal_timing_policy != CausalTimingPolicy.NOT_APPLICABLE:
            raise SpecificationError(
                f"DataRequirement {self.requirement_id!r} ({self.fact_class.value}) is not "
                f"causally sensitive and must declare causal_timing_policy = NOT_APPLICABLE"
            )
