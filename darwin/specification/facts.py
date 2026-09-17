"""Canonical vs specification-derived fact model (PID-004 sec9/sec9A/sec25A).

Two genuinely distinct dataclass TYPES, never one object with a
`is_canonical` flag a caller could set inconsistently:

- `CanonicalFactReference` -- points at a fact owned by a governed
  authority (HERMES OHLCV, a future ARES/options authority, ...).
- `SpecificationDerivedFact` -- a deterministic DARWIN-side transformation
  (EMA, ATR, ...) with its own algorithm identity/version/parameters.

`fact_reference_kind()` is the ONLY way to ask which kind a `FactReference`
is, and it dispatches purely on `isinstance` -- there is no boolean/enum
field on either dataclass that a caller could flip to make a derived fact
masquerade as canonical HERMES authority (PID-004 sec9A). That is what
makes this a structural, type-level impossibility rather than a naming
convention (contrast with the HSA archaeology's own honest gap report,
`docs/archaeology/HSA-PID004A-REUSE-ASSESSMENT.md` "Gaps DARWIN must solve
itself").
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.specification.errors import FactReferenceKindError, SpecificationError
from darwin.specification.expressions import ExpressionKind
from darwin.specification.timeframe import Timeframe


class DataAuthorityClass(StrEnum):
    """PID-004 sec25. An authority class may exist semantically before a
    concrete provider is onboarded -- DARWIN never substitutes an
    unrelated convenient source merely because the intended authority is
    unavailable; see darwin.specification.readiness for how "authority not
    onboarded" is represented as a readiness state, never as a semantic
    substitution."""

    HERMES_CANONICAL_MARKET = "HERMES_CANONICAL_MARKET"
    ARES_GOVERNED_CONTEXT = "ARES_GOVERNED_CONTEXT"
    OPTIONS_AUTHORITY = "OPTIONS_AUTHORITY"
    FUTURES_AUTHORITY = "FUTURES_AUTHORITY"
    OTHER_GOVERNED_AUTHORITY = "OTHER_GOVERNED_AUTHORITY"


class FactReferenceKind(StrEnum):
    CANONICAL_FACT_REFERENCE = "CANONICAL_FACT_REFERENCE"
    SPECIFICATION_DERIVED_FACT = "SPECIFICATION_DERIVED_FACT"


class MissingInputBehavior(StrEnum):
    """PID-004 sec9: a SPECIFICATION_DERIVED_FACT must bind explicit
    missing-input behaviour -- never an implicit "treat as zero"."""

    FAIL_EVALUATION = "FAIL_EVALUATION"
    PROPAGATE_UNKNOWN = "PROPAGATE_UNKNOWN"


@dataclass(frozen=True)
class CanonicalFactReference:
    """Points at a fact owned by a governed authority (PID-004 sec9A).
    `fact_key` is a governed identifier (e.g. ``OHLCV.CLOSE``,
    ``ARES.ECONOMIC_RELEASE.CPI_YOY``) -- never invented/inferred by this
    package; the closed vocabulary of real fact_keys this contract phase
    actually exercises lives in `darwin.specification.data_requirements`'s
    fixtures, not as a hardcoded enum here (PID-004 sec9: "PID-004A does
    not need every indicator ever invented... a governed extension
    model.")."""

    fact_key: str
    authority_class: DataAuthorityClass
    unit: str
    timeframe: Timeframe
    kind: FactReferenceKind = FactReferenceKind.CANONICAL_FACT_REFERENCE

    def __post_init__(self) -> None:
        if not self.fact_key or not self.fact_key.strip():
            raise SpecificationError("CanonicalFactReference requires a non-empty fact_key")
        if self.kind != FactReferenceKind.CANONICAL_FACT_REFERENCE:
            raise FactReferenceKindError(
                "CanonicalFactReference.kind is fixed; it may never be constructed as anything "
                "other than CANONICAL_FACT_REFERENCE"
            )


@dataclass(frozen=True)
class SpecificationDerivedFact:
    """A deterministic DARWIN research-side transformation (PID-004
    sec9/sec9A/sec25A). `input_facts` may reference canonical facts or
    other derived facts (a derivation chain), but the chain always
    terminates in canonical references -- there is no way to construct an
    input-less derived fact, which would have nothing to derive from.

    Changing `algorithm_id`/`algorithm_version`/`parameters` for a
    behaviourally-used derived fact changes the owning StrategyVersion's
    `semantic_fingerprint` (see darwin.specification.domain and the Case B
    fingerprint test) -- the fingerprint payload walks this dataclass's
    own fields, so there is nothing additional to wire up by hand.
    """

    derived_fact_id: str
    input_facts: tuple[CanonicalFactReference | SpecificationDerivedFact, ...]
    algorithm_id: str
    algorithm_version: str
    parameters: tuple[tuple[str, object], ...]
    timeframe: Timeframe
    warm_up_bars: int
    output_unit: str
    missing_input_behavior: MissingInputBehavior
    kind: FactReferenceKind = FactReferenceKind.SPECIFICATION_DERIVED_FACT

    def __post_init__(self) -> None:
        if not self.derived_fact_id or not self.derived_fact_id.strip():
            raise SpecificationError("SpecificationDerivedFact requires a non-empty derived_fact_id")
        if not self.input_facts:
            raise SpecificationError(
                f"SpecificationDerivedFact {self.derived_fact_id!r} must declare at least one input fact"
            )
        if not self.algorithm_id or not self.algorithm_version:
            raise SpecificationError(
                f"SpecificationDerivedFact {self.derived_fact_id!r} requires algorithm_id and algorithm_version"
            )
        if self.warm_up_bars < 0:
            raise SpecificationError("warm_up_bars must be >= 0")
        if not isinstance(self.missing_input_behavior, MissingInputBehavior):
            raise SpecificationError(
                f"missing_input_behavior must be a MissingInputBehavior, got {self.missing_input_behavior!r}"
            )
        if self.kind != FactReferenceKind.SPECIFICATION_DERIVED_FACT:
            raise FactReferenceKindError(
                "SpecificationDerivedFact.kind is fixed; it may never be constructed as anything "
                "other than SPECIFICATION_DERIVED_FACT"
            )


FactReference = CanonicalFactReference | SpecificationDerivedFact


def fact_reference_kind(reference: FactReference) -> FactReferenceKind:
    """The only supported way to ask which kind a FactReference is.
    Dispatches purely on isinstance -- there is no shared mutable field to
    misreport (PID-004 sec9A)."""
    if isinstance(reference, CanonicalFactReference):
        return FactReferenceKind.CANONICAL_FACT_REFERENCE
    if isinstance(reference, SpecificationDerivedFact):
        return FactReferenceKind.SPECIFICATION_DERIVED_FACT
    raise FactReferenceKindError(f"Not a governed FactReference: {type(reference)!r}")


def require_canonical(reference: FactReference) -> CanonicalFactReference:
    """Raises unless `reference` is genuinely a CanonicalFactReference.
    Used anywhere DARWIN must prove a fact is HERMES-canonical (or another
    governed authority) rather than a DARWIN-derived research value."""
    if not isinstance(reference, CanonicalFactReference):
        raise FactReferenceKindError(
            f"Expected a CanonicalFactReference (governed authority data), got "
            f"{fact_reference_kind(reference).value} -- a derived fact must never be used "
            f"where canonical authority is required"
        )
    return reference


def derivation_chain_algorithms(reference: FactReference) -> tuple[tuple[str, str], ...]:
    """Every (algorithm_id, algorithm_version) pair in `reference`'s
    derivation chain, canonical-fact leaves excluded. Used by the semantic
    fingerprint payload (indirectly, via the whole dataclass tree) and
    directly by tests proving an algorithm/version change is visible."""
    if isinstance(reference, CanonicalFactReference):
        return ()
    pairs: list[tuple[str, str]] = [(reference.algorithm_id, reference.algorithm_version)]
    for input_fact in reference.input_facts:
        pairs.extend(derivation_chain_algorithms(input_fact))
    return tuple(pairs)


# ExpressionKind values reused above for a uniform tree-walk discriminator
# across expressions.py and facts.py -- confirmed identical members exist
# on both enums for the two fact-reference kinds (see
# darwin.specification.composition._walk).
assert ExpressionKind.CANONICAL_FACT_REFERENCE.value == FactReferenceKind.CANONICAL_FACT_REFERENCE.value
assert (
    ExpressionKind.SPECIFICATION_DERIVED_FACT.value == FactReferenceKind.SPECIFICATION_DERIVED_FACT.value
)
