"""PID-004A Specification Contract -- error hierarchy.

Mirrors `darwin.scout.domain`'s discipline: every domain-invariant violation
is rejected at construction time as a typed, code-bearing `DarwinError`
subclass, never silently accepted or swallowed. `STRATEGY_NOT_SUFFICIENTLY_
DEFINED` is deliberately NOT modelled as an exception anywhere in this
package -- per the HSA archaeology (`docs/archaeology/HSA-PID004A-REUSE-
ASSESSMENT.md` #4/#14), a refusal is a governed, successful validation
*outcome* (see `darwin.specification.validation.ValidationOutcome`), not a
failure a caller must catch.
"""
from __future__ import annotations

from darwin.core.errors import DarwinError


class SpecificationError(DarwinError):
    """Base class for all PID-004A specification-contract domain errors."""

    code = "SPECIFICATION_ERROR"


class UnknownOperatorError(SpecificationError):
    """A raw operator string does not belong to a governed, closed operator
    vocabulary (PID-004 sec8: "Unknown operators fail validation. No silent
    fallback."). Raised at construction time -- never at evaluation time,
    because nothing in this package evaluates strategy logic.
    """

    code = "SPECIFICATION_UNKNOWN_OPERATOR"


class UnboundedTunableParameterError(SpecificationError):
    """A TUNABLE parameter was constructed without a closed, bounded domain
    (PID-004 sec18: "No: ATHENA may try whatever it wants.")."""

    code = "SPECIFICATION_UNBOUNDED_TUNABLE_PARAMETER"


class ParameterDomainViolationError(SpecificationError):
    """A concrete value was rejected by a parameter's own bounded domain."""

    code = "SPECIFICATION_PARAMETER_DOMAIN_VIOLATION"


class InvalidCompositionError(SpecificationError):
    """A composition primitive was constructed in a way that violates its
    own structural rules (e.g. a SEQUENCE with non-contiguous indices, a
    CONTEXT_TRIGGER missing a context validity declaration)."""

    code = "SPECIFICATION_INVALID_COMPOSITION"


class InvalidExpirySpecError(SpecificationError):
    """An ExpirySpec was constructed with a mode/value combination that is
    not self-consistent (PID-004 sec8: no implicit defaults; FRAMES must
    name which timeframe's frames are being counted)."""

    code = "SPECIFICATION_INVALID_EXPIRY_SPEC"


class CausalTimingViolationError(SpecificationError):
    """A causal external-fact construct would let a later revision or a
    later-observed value leak backward across its own required instant
    (PID-004 sec24A/sec31A)."""

    code = "SPECIFICATION_CAUSAL_TIMING_VIOLATION"


class FactReferenceKindError(SpecificationError):
    """A caller attempted to treat a SPECIFICATION_DERIVED_FACT as if it
    were CANONICAL_FACT_REFERENCE authority, or vice-versa (PID-004 sec9A:
    "A derived value must never masquerade as a HERMES canonical fact.")."""

    code = "SPECIFICATION_FACT_REFERENCE_KIND_ERROR"


class ProvenanceError(SpecificationError):
    """A provenance/rule-origin operation violated the origin-is-permanent
    invariant (PID-004 sec22)."""

    code = "SPECIFICATION_PROVENANCE_ERROR"


class ReadinessAssessmentError(SpecificationError):
    """A DataReadinessAssessment was constructed against requirement IDs
    that do not match its StrategyVersion's own DataRequirements."""

    code = "SPECIFICATION_READINESS_ASSESSMENT_ERROR"


class FinalisationError(SpecificationError):
    """Raised only for a programmer-error call into `finalise()` (e.g. a
    draft belonging to a different schema). Never raised for a materially
    incomplete specification -- that produces a
    `STRATEGY_NOT_SUFFICIENTLY_DEFINED` ValidationOutcome instead, returned
    to the caller, not thrown at them (see module docstring)."""

    code = "SPECIFICATION_FINALISATION_ERROR"


class InvalidOperandError(SpecificationError):
    """A `Comparison`/`BooleanExpression`/`AtomicCondition`/
    `SpecificationDerivedFact` was constructed with an operand/expression/
    input outside its own closed, governed type vocabulary (PID-004A
    hardening item 1: the expression tree must be closed -- a raw string,
    an arbitrary object, or an unsupported dataclass must never survive
    into a valid StrategyVersion)."""

    code = "SPECIFICATION_INVALID_OPERAND"


class UnrecognisedExpressionNodeError(SpecificationError):
    """A recursive expression-tree walk (see
    `darwin.specification.validation._iter_expression_nodes`) encountered a
    node type it does not recognise. Raised explicitly rather than
    silently treating the node as an inert leaf -- defense-in-depth
    alongside the construction-time `InvalidOperandError` checks (PID-004A
    hardening item 1)."""

    code = "SPECIFICATION_UNRECOGNISED_EXPRESSION_NODE"


class UngovernedFactKeyError(SpecificationError):
    """A `CanonicalFactReference` was constructed with a `fact_key` that
    does not belong to its declared `fact_class`'s governed semantic
    vocabulary, for a fact_class this contract phase currently governs
    (e.g. HERMES `MARKET_OHLCV`). A free, merely-non-empty `fact_key`
    string is never sufficient to confer canonical-fact status within a
    currently-governed namespace (PID-004A hardening item 3). Fact classes
    belonging to a not-yet-onboarded authority remain free-text -- this
    error is never raised for those."""

    code = "SPECIFICATION_UNGOVERNED_FACT_KEY"
