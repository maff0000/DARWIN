"""Causal external/context fact semantics (PID-004 sec10/sec24A/sec31A).

The invariant this module exists to enforce:

    Historical evaluation may consume only information available at that
    historical instant. A later-revised number must never leak backward.
    A later article must never inform an earlier decision.

Two separate things live here, and they are kept deliberately separate:

1. `CausalTimingPolicy` -- what a `DataRequirement` (darwin.specification.
   data_requirements) REQUIRES of an external/context fact's causal
   timing. This is specification-time semantics -- part of what the
   strategy needs, never touched by actual historical availability.
2. `ExternalFactObservation` + `select_causally_available_revision` --
   a small, deterministic causal-selection function proving the invariant
   above is structurally enforceable. This is NOT a historical data
   store, NOT ARES, and NOT an evaluation engine -- it exists purely so
   the causal invariant can be tested in-memory (PID-004 sec42's required
   causal-event tests) without building any of those things.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from darwin.specification.errors import CausalTimingViolationError, SpecificationError


class CausalTimingPolicy(StrEnum):
    """PID-004 sec10: the specification records what causal timing is
    REQUIRED; no implicit default (PID-004 sec33) -- `NOT_APPLICABLE` is
    the explicit value for a DataRequirement that has no causal-timing
    concern (e.g. MARKET_OHLCV), never a silently-omitted field."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    ORIGINAL_PUBLISHED_VALUE_ONLY = "ORIGINAL_PUBLISHED_VALUE_ONLY"
    LATEST_CAUSALLY_AVAILABLE_REVISION = "LATEST_CAUSALLY_AVAILABLE_REVISION"


@dataclass(frozen=True)
class ExternalFactObservation:
    """One concrete historical observation of an external/context fact
    (PID-004 sec24A). Never fabricated as "real" evidence by this
    package -- every field here is caller-supplied, and this dataclass is
    used only by controlled fixtures/tests in this contract phase (there
    is no ARES/news ingestion anywhere in `darwin.specification`).

    - `event_time`: when the underlying real-world event occurred/is
      defined to occur.
    - `published_at_utc`: when the authority published the information.
    - `observed_at_utc`: when a governed system first observed/ingested it.
    - `effective_at_utc`: the earliest canonical instant at which a
      historical evaluator is permitted to consume this fact. Must never
      be earlier than `published_at_utc` (an evaluator cannot become
      permitted to know something before it was even published).
    - `revision`: identity of this source revision/value version.
    """

    fact_requirement_id: str
    event_time: datetime
    published_at_utc: datetime
    observed_at_utc: datetime
    effective_at_utc: datetime
    revision: str
    value: object

    def __post_init__(self) -> None:
        if self.effective_at_utc < self.published_at_utc:
            raise CausalTimingViolationError(
                f"ExternalFactObservation revision {self.revision!r}: effective_at_utc "
                f"({self.effective_at_utc.isoformat()}) precedes published_at_utc "
                f"({self.published_at_utc.isoformat()}) -- a fact cannot become causally "
                f"available before it was published"
            )
        if self.observed_at_utc < self.published_at_utc:
            raise CausalTimingViolationError(
                f"ExternalFactObservation revision {self.revision!r}: observed_at_utc "
                f"({self.observed_at_utc.isoformat()}) precedes published_at_utc "
                f"({self.published_at_utc.isoformat()}) -- a governed system cannot observe "
                f"a fact before its authority published it"
            )


def is_causally_available(observation: ExternalFactObservation, *, decision_instant_utc: datetime) -> bool:
    """The one required check: an observation is usable at `decision_instant_utc`
    if and only if its `effective_at_utc` is not later than the decision
    instant. This is the entire "no hindsight leakage" rule, expressed as
    one comparison rather than left implicit anywhere else."""
    return observation.effective_at_utc <= decision_instant_utc


def select_causally_available_revision(
    observations: list[ExternalFactObservation] | tuple[ExternalFactObservation, ...],
    *,
    decision_instant_utc: datetime,
) -> ExternalFactObservation | None:
    """Among possibly-multiple revisions of the SAME fact, return the
    latest one that was causally available at `decision_instant_utc`, or
    `None` if none were. This makes "request a later revision than what
    was causally available at this instant" structurally impossible: the
    filter (`is_causally_available`) is applied before any selection by
    recency ever happens -- there is no code path that picks a revision
    first and checks availability second.
    """
    if not observations:
        raise SpecificationError("select_causally_available_revision requires at least one observation")
    fact_ids = {obs.fact_requirement_id for obs in observations}
    if len(fact_ids) != 1:
        raise SpecificationError(
            f"select_causally_available_revision requires observations of exactly one fact, got {fact_ids}"
        )
    available = [obs for obs in observations if is_causally_available(obs, decision_instant_utc=decision_instant_utc)]
    if not available:
        return None
    return max(available, key=lambda obs: obs.effective_at_utc)
