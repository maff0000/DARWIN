"""Data readiness assessment (PID-004 sec26/sec27/sec28).

`DataReadinessAssessment` records whether DARWIN can currently satisfy a
StrategyVersion's `DataRequirement`s. It is a SEPARATE object from
`StrategyVersion` and is never threaded into semantic-fingerprint
computation (`darwin.specification.fingerprint`) -- there is no code path
in this package that hands a `DataReadinessAssessment` to a fingerprint
function; the fingerprint payload is built exclusively from
`StrategyVersion`'s own immutable fields (see darwin.specification.domain.
StrategyVersion.semantic_payload), which has no readiness field to see.
That is what makes "readiness changes do not change semantic_fingerprint"
structural rather than merely conventional.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from darwin.specification.errors import ReadinessAssessmentError


class OverallReadinessState(StrEnum):
    TESTABLE = "TESTABLE"
    DATA_BLOCKED = "DATA_BLOCKED"


class PerRequirementAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    INSUFFICIENT_RESOLUTION = "INSUFFICIENT_RESOLUTION"
    AUTHORITY_NOT_ONBOARDED = "AUTHORITY_NOT_ONBOARDED"
    CONTRACT_INCOMPATIBLE = "CONTRACT_INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RequirementReadiness:
    requirement_id: str
    availability: PerRequirementAvailability
    reason: str | None = None


@dataclass(frozen=True)
class DataReadinessAssessment:
    """One point-in-time readiness assessment against a specific
    StrategyVersion's requirement_ids. Multiple assessments may exist for
    the same `strategy_version_id` over time (PID-004 sec27/sec28:
    "reassess readiness, not rediscover/rewrite") -- each is a NEW,
    separate DataReadinessAssessment instance; none of them ever mutate
    the StrategyVersion or each other.
    """

    assessment_id: str
    strategy_version_id: str
    assessed_at_utc: datetime
    per_requirement: tuple[RequirementReadiness, ...]
    mandatory_requirement_ids: frozenset[str]

    def __post_init__(self) -> None:
        covered = {r.requirement_id for r in self.per_requirement}
        missing = self.mandatory_requirement_ids - covered
        if missing:
            raise ReadinessAssessmentError(
                f"DataReadinessAssessment {self.assessment_id!r} is missing per-requirement "
                f"readiness for mandatory requirement(s) {sorted(missing)}"
            )

    @property
    def overall_state(self) -> OverallReadinessState:
        by_id = {r.requirement_id: r for r in self.per_requirement}
        for requirement_id in self.mandatory_requirement_ids:
            if by_id[requirement_id].availability != PerRequirementAvailability.AVAILABLE:
                return OverallReadinessState.DATA_BLOCKED
        return OverallReadinessState.TESTABLE


def assess_readiness(
    *,
    assessment_id: str,
    strategy_version_id: str,
    mandatory_requirement_ids: frozenset[str] | set[str],
    per_requirement: dict[str, tuple[PerRequirementAvailability, str | None]],
    assessed_at_utc: datetime,
) -> DataReadinessAssessment:
    """The only supported way to build a DataReadinessAssessment from a
    plain `{requirement_id: (availability, reason)}` mapping -- validates
    that every mandatory requirement is covered before construction."""
    readiness_rows = tuple(
        RequirementReadiness(requirement_id=req_id, availability=availability, reason=reason)
        for req_id, (availability, reason) in per_requirement.items()
    )
    return DataReadinessAssessment(
        assessment_id=assessment_id,
        strategy_version_id=strategy_version_id,
        assessed_at_utc=assessed_at_utc,
        per_requirement=readiness_rows,
        mandatory_requirement_ids=frozenset(mandatory_requirement_ids),
    )
