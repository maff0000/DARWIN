"""PID-006A Research Contracts -- error hierarchy.

Mirrors `darwin.specification.errors`'s own discipline exactly: every
domain-invariant violation is rejected at construction time as a typed,
code-bearing `DarwinError` subclass, never silently accepted, swallowed,
or reported as unstructured prose.

The one deliberate structural distinction this module exists to carry
(PID-006A sec13): `EngineCapabilityBlockedError` is NOT a domain-validation
failure. A `StrategyVersion` that fails `darwin.specification.validation`
is genuinely invalid. A `StrategyVersion` that is fully valid but requires
a semantic this compiler does not yet implement is not invalid at all --
the compiler is simply not (yet) capable of representing it. Conflating
the two would make a future capability upgrade look like a bug fix for a
previously-"invalid" input, when nothing about the input's validity ever
changed. `InvalidConfigurationError` and its siblings below are for
genuine domain-validation failures (wrong type, missing field, mismatched
binding, ...); `EngineCapabilityBlockedError` is reserved exclusively for
"this input is valid; this engine cannot evaluate it yet".
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.core.errors import DarwinError


class ResearchContractsError(DarwinError):
    """Base class for all PID-006A research-contracts domain errors."""

    code = "RESEARCH_CONTRACTS_ERROR"


class InvalidConfigurationError(ResearchContractsError):
    """An ordinary domain-validation failure: a value, type, or structural
    invariant was violated at construction time. Never raised for a
    capability gap -- see `EngineCapabilityBlockedError` for that."""

    code = "RESEARCH_CONTRACTS_INVALID_CONFIGURATION"


class CapabilityBlockReason(StrEnum):
    """Closed, governed vocabulary of reasons a compilation/construction
    can fail closed rather than silently drop or misrepresent a semantic.
    Extending this is a deliberate, reviewed product decision each time --
    never inferred from a caught exception's message text."""

    UNSUPPORTED_COMPOSITION_PRIMITIVE = "UNSUPPORTED_COMPOSITION_PRIMITIVE"


@dataclass(frozen=True)
class CapabilityBlockContext:
    """Structured, machine-readable context for one `EngineCapabilityBlockedError`
    -- never free text the caller has to parse. `subject_ref` names the
    specific semantic element that could not be compiled (e.g. a
    `composition_id`); `detail` carries a small number of additional
    plain key/value facts (e.g. the unsupported primitive's own name)."""

    reason: CapabilityBlockReason
    subject_ref: str
    detail: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict:
        return {
            "reason": self.reason.value,
            "subject_ref": self.subject_ref,
            "detail": dict(self.detail),
        }


class EngineCapabilityBlockedError(ResearchContractsError):
    """A fully-valid input requires a semantic this engine does not yet
    implement (PID-006A sec13). Distinguished by construction from
    `InvalidConfigurationError`: this is never raised because the input
    was wrong, only because this engine's current capability envelope
    does not yet cover it. Carries a typed, structured
    `CapabilityBlockContext` -- never only a prose message -- so a caller
    can branch on `reason` without parsing text.
    """

    code = "RESEARCH_CONTRACTS_ENGINE_CAPABILITY_BLOCKED"

    def __init__(self, message: str, *, context: CapabilityBlockContext) -> None:
        super().__init__(message)
        self.context = context


class ParameterSetBindingError(InvalidConfigurationError):
    """A `ParameterSetVersion` was constructed with assignments that do not
    exactly match its source `StrategyVersion`'s declared parameters --
    missing, unknown, duplicate, or wrong-type. Out-of-domain/fixed-value
    mismatches are raised directly by
    `darwin.specification.parameters.validate_parameter_value` as
    `ParameterDomainViolationError` and are never re-wrapped here (reuse,
    don't reinvent)."""

    code = "RESEARCH_CONTRACTS_PARAMETER_SET_BINDING_ERROR"


class ExecutionPolicyIncompleteError(InvalidConfigurationError):
    """An `ExecutionPolicyVersion` was constructed missing one or more of
    its mandatory identity axes (PID-006A sec7: "absence never means a
    default"). Never raised for `ZERO_COST` itself, which is a fully
    explicit, valid selection -- only for a genuinely omitted axis."""

    code = "RESEARCH_CONTRACTS_EXECUTION_POLICY_INCOMPLETE"


class ResearchInputBindingError(InvalidConfigurationError):
    """A `ResearchInputBinding` was constructed with an inconsistent or
    incomplete identity (e.g. an empty governed dataset identity, or an
    `input_kind` that does not match the concrete identity supplied)."""

    code = "RESEARCH_CONTRACTS_RESEARCH_INPUT_BINDING_ERROR"


class ResearchConfigurationInconsistentError(InvalidConfigurationError):
    """A `ResearchConfiguration` was asked to bind axes that do not
    actually agree with each other -- e.g. a `ParameterSetVersion` or
    `ExecutableStrategyPlan` built against a different `StrategyVersion`
    than the one directly referenced, or a DIKE state/policy-fingerprint
    pairing that violates the existing `DikePolicyBindingError` invariant
    (PID-006A sec11: "Construction must detect and reject an inconsistent
    binding")."""

    code = "RESEARCH_CONTRACTS_CONFIGURATION_INCONSISTENT"


class PersistedFingerprintMismatchError(ResearchContractsError):
    """A row read back from `darwin.research_store` carried a recomputed
    fingerprint that does not match its own stored fingerprint column
    (PID-006A sec15: "recompute the fingerprint from the reconstructed
    payload and compare against the stored fingerprint -- do not merely
    trust the stored value"). This is a data-integrity finding, never
    silently ignored."""

    code = "RESEARCH_CONTRACTS_PERSISTED_FINGERPRINT_MISMATCH"
