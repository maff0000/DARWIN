"""Policy identity boundary (PID-004 sec5B/sec12/sec17/sec19/sec20).

Preserves the identity separation:

    StrategyVersion != ExecutionPolicyVersion != DIKEPolicyVersion
                     != SizingPolicyVersion != NewsContextPolicyVersion

`StrategyVersion` (darwin.specification.domain) never carries a field for
any frozen policy VERSION id -- there is nothing here to bind one to. What
a StrategyVersion DOES declare is *compatibility*: whether a policy class
is REQUIRED/PERMITTED/DISABLED/IRRELEVANT, and, where PERMITTED or
REQUIRED, an authorised research envelope a compatible policy's own
tunable dimensions must respect. The exact frozen policy selected for one
ResearchRun is that policy's own separately-governed concern.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.specification.errors import SpecificationError
from darwin.specification.parameters import ParameterDefinition, ParameterStatus


class PolicyClass(StrEnum):
    EXECUTION_POLICY = "EXECUTION_POLICY"
    DIKE_POLICY = "DIKE_POLICY"
    SIZING_POLICY = "SIZING_POLICY"
    NEWS_CONTEXT_POLICY = "NEWS_CONTEXT_POLICY"


class PolicyCompatibility(StrEnum):
    REQUIRED = "REQUIRED"
    PERMITTED = "PERMITTED"
    DISABLED = "DISABLED"
    IRRELEVANT = "IRRELEVANT"


@dataclass(frozen=True)
class PolicySearchAuthority:
    """One authorised, independently-tunable dimension of a compatible
    policy (e.g. stop-loss distance) -- reuses the same bounded-domain
    discipline as strategy-intrinsic parameters (PID-004 sec19: "No
    implicit feature enablement"). `parameter` must be TUNABLE with a
    bounded domain; a FIXED "search authority" would be a contradiction in
    terms."""

    dimension: str
    parameter: ParameterDefinition

    def __post_init__(self) -> None:
        if not self.dimension or not self.dimension.strip():
            raise SpecificationError("PolicySearchAuthority requires a non-empty dimension")
        if self.parameter.status != ParameterStatus.TUNABLE:
            raise SpecificationError(
                f"PolicySearchAuthority dimension {self.dimension!r} must reference a TUNABLE "
                f"parameter (a FIXED 'search authority' is a contradiction)"
            )


@dataclass(frozen=True)
class PolicyCompatibilityDeclaration:
    """One policy class's compatibility declaration on a StrategyVersion.
    `authorized_search_envelope` may only be non-empty when compatibility
    is REQUIRED or PERMITTED -- DISABLED/IRRELEVANT declaring a search
    envelope would be a contradiction (there is nothing to search if the
    policy class does not apply)."""

    policy_class: PolicyClass
    compatibility: PolicyCompatibility
    authorized_search_envelope: tuple[PolicySearchAuthority, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        if (
            self.compatibility in (PolicyCompatibility.DISABLED, PolicyCompatibility.IRRELEVANT)
            and self.authorized_search_envelope
        ):
            raise SpecificationError(
                f"{self.policy_class.value} declared {self.compatibility.value} must not carry "
                f"an authorized_search_envelope"
            )
