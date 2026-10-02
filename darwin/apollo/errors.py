"""PID-006B APOLLO Candle Causal Core -- error hierarchy.

Mirrors `darwin.research_contracts.errors`'s own discipline exactly (that
module's docstring is the canonical explanation, reused here rather than
re-derived): every domain-invariant violation is a typed, code-bearing
`DarwinError` subclass, never silently accepted or reported as
unstructured prose.

The same structural distinction PID-006A drew is preserved here:
`EngineCapabilityBlockedError` is NOT a domain-validation failure -- a
`ResearchConfiguration`/`ExecutionPolicyVersion` that is fully valid but
requires a semantic this v1 engine slice does not yet implement is not
invalid, only not-yet-supported. `InvalidConfigurationError` is reserved
for genuine domain-validation failures (mismatched binding, wrong
instrument, inconsistent identity, ...).

`EngineDefectError` is the third, deliberately distinct case this package
adds: an internal bug/exception inside the engine's own replay loop must
surface as an explicit, typed engine failure -- never as a losing trade,
never as silently-wrong P&L (PID-006B causal-order requirement: "Never
encode an engine defect as a losing trade").
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.core.errors import DarwinError


class ApolloError(DarwinError):
    """Base class for all PID-006B APOLLO domain errors."""

    code = "APOLLO_ERROR"


class InvalidConfigurationError(ApolloError):
    """An ordinary domain-validation failure discovered at preflight --
    e.g. a dataset/instrument mismatch, a parameter-set/strategy
    mismatch, or a DIKE state other than DISABLED. Never raised for a
    capability gap -- see `EngineCapabilityBlockedError` for that."""

    code = "APOLLO_INVALID_CONFIGURATION"


class CapabilityBlockReason(StrEnum):
    """Closed, governed vocabulary of reasons preflight can fail closed
    rather than silently misrepresent an unsupported semantic. Extending
    this is a deliberate, reviewed product decision -- never inferred from
    a caught exception's message text."""

    UNSUPPORTED_EXECUTION_POLICY_COMPONENT = "UNSUPPORTED_EXECUTION_POLICY_COMPONENT"
    UNSUPPORTED_COMPOSITION_SHAPE = "UNSUPPORTED_COMPOSITION_SHAPE"
    UNSUPPORTED_DIRECTION = "UNSUPPORTED_DIRECTION"
    UNSUPPORTED_EXPRESSION_SHAPE = "UNSUPPORTED_EXPRESSION_SHAPE"
    UNSUPPORTED_EXIT_RULES = "UNSUPPORTED_EXIT_RULES"
    UNSUPPORTED_TIMEFRAME_MISMATCH = "UNSUPPORTED_TIMEFRAME_MISMATCH"
    #: CA-006B-4 exhaustive supported-semantic-subset gate -- one reason
    #: per StrategyVersion/ExecutableStrategyPlan semantic field this
    #: engine slice does not implement, so a capability-block result
    #: always names exactly which field tripped it, never a generic
    #: "unsupported" bucket.
    UNSUPPORTED_SESSION_SPEC = "UNSUPPORTED_SESSION_SPEC"
    UNSUPPORTED_SETUP_EXPIRY = "UNSUPPORTED_SETUP_EXPIRY"
    UNSUPPORTED_INTRABAR_AMBIGUITY_POLICY = "UNSUPPORTED_INTRABAR_AMBIGUITY_POLICY"
    UNSUPPORTED_DATA_REQUIREMENT = "UNSUPPORTED_DATA_REQUIREMENT"
    UNSUPPORTED_POLICY_DECLARATION = "UNSUPPORTED_POLICY_DECLARATION"
    MISSING_RISK_PARAMETER_DECLARATION = "MISSING_RISK_PARAMETER_DECLARATION"


@dataclass(frozen=True)
class CapabilityBlockContext:
    """Structured, machine-readable context for one
    `EngineCapabilityBlockedError` -- never free text the caller has to
    parse. Mirrors `darwin.research_contracts.errors.CapabilityBlockContext`
    exactly."""

    reason: CapabilityBlockReason
    subject_ref: str
    detail: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict:
        return {
            "reason": self.reason.value,
            "subject_ref": self.subject_ref,
            "detail": dict(self.detail),
        }


class EngineCapabilityBlockedError(ApolloError):
    """A fully-valid `ResearchConfiguration`/`StrategyVersion`/
    `ExecutionPolicyVersion` requires a semantic this v1 engine slice does
    not implement (PID-006B "first supported semantic subset"). Raised
    ONLY at preflight, before a single bar is processed -- never mid-replay.
    Distinguished by construction from `InvalidConfigurationError`: never
    raised because the input is wrong, only because this engine's current
    capability envelope does not yet cover it.
    """

    code = "APOLLO_ENGINE_CAPABILITY_BLOCKED"

    def __init__(self, message: str, *, context: CapabilityBlockContext) -> None:
        super().__init__(message)
        self.context = context


class EngineDefectError(ApolloError):
    """An internal bug/exception was caught inside the engine's own replay
    loop. Never encoded as a losing trade or silently-wrong P&L -- the
    replay is aborted and this is raised instead, carrying the bar index
    at which the defect was detected."""

    code = "APOLLO_ENGINE_DEFECT"


class PersistedFingerprintMismatchError(ApolloError):
    """A row read back from `darwin.research_store` carried a recomputed
    fingerprint that does not match its own stored fingerprint column --
    mirrors `darwin.research_contracts.errors.PersistedFingerprintMismatchError`."""

    code = "APOLLO_PERSISTED_FINGERPRINT_MISMATCH"
