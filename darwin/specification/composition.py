"""HELIOS-compatible composition semantics (PID-004 sec5A/sec8A/sec41A).

Models ATOMIC/ALL/ANY/SEQUENCE/CONTEXT_TRIGGER as five genuinely distinct
dataclass TYPES -- never one generic "composition node" with a
discriminator field that erases the distinctions (PID-004 sec8A: "SEQUENCE
must not be reduced to a timeless AND"; CONTEXT_TRIGGER must preserve
context-established-before-trigger ordering, validity lifetime and
reset/invalidation semantics, and must never be modelled as a bare
2-item SEQUENCE).

This module does NOT implement HELIOS. It does not evaluate anything --
there is no `evaluate()` function anywhere in this package. What it
represents is the semantic RULE SET a future deterministic HELIOS
promotion/compiler needs to see explicitly (per the HELIOS archaeology,
`docs/archaeology/HELIOS-PID004A-SEMANTIC-COMPATIBILITY.md`, answer to
question 3): explicit per-component (semantic_role, timeframe) binding,
explicit governed expiry mode + value, and the two primitives
(SEQUENCE/CONTEXT_TRIGGER) that a compiler -- not this package -- would
eventually have to translate into HELIOS's own instant-based, tie-tolerant
temporal semantics.

Deliberate scope decision (flagged for the Architect, not silently
resolved): composition COMPONENTS in this contract phase are always
`AtomicCondition` leaves. Nesting one composition inside another
("chain-of-chains") is not implemented here.

Doctrine (PID-004A hardening item 6 -- corrects an earlier, wrong framing
of this exact decision): DARWIN is canonical. PID-004A does not implement
nested composition because it is outside the authorised scope. Future
DARWIN semantic extensions may exceed current HELIOS capability;
unsupported promotion must fail explicitly until a versioned equivalent
compiler/HELIOS capability exists. This is a scope boundary DARWIN itself
drew, not a limitation borrowed from what today's HELIOS happens to be
able to execute (real current HELIOS also structurally refuses
chain-of-chain composition today -- HELIOS archaeology finding #11,
`docs/COMPOSITION.md` sec1.1: "Recursive chain-of-chain composition
requires explicit architecture authority" -- but that fact is
corroborating context, never the reason for DARWIN's own decision).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.specification.errors import (
    InvalidCompositionError,
    InvalidExpirySpecError,
    InvalidOperandError,
)
from darwin.specification.expressions import (
    BooleanExpression,
    Comparison,
    EventPredicate,
    SessionPredicate,
    TemporalPredicate,
    UndefinedMeasurementBasis,
)
from darwin.specification.timeframe import Timeframe, finest


class CompositionPrimitive(StrEnum):
    """Closed, four-primitive vocabulary (PID-004 sec8A) plus ATOMIC as the
    leaf kind. Fixed on each dataclass below purely as a self-describing
    discriminator for canonical serialisation -- the actual type safety
    comes from five distinct dataclasses, not from switching on this
    value (PID-004 sec8A: never one generic node)."""

    ATOMIC = "ATOMIC"
    ALL = "ALL"
    ANY = "ANY"
    SEQUENCE = "SEQUENCE"
    CONTEXT_TRIGGER = "CONTEXT_TRIGGER"


class Direction(StrEnum):
    """PID-004 sec15. Deliberately does NOT include HELIOS's runtime-only
    NEUTRAL/NONE output distinction (HELIOS archaeology answer 5) -- that
    is an evaluation-TIME output concept a future HELIOS runtime produces,
    not a specification-TIME declaration a StrategyVersion makes. Recorded
    here as a known, deliberate scope boundary, not silently elided."""

    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class ComponentDirectionRelationship(StrEnum):
    """HELIOS archaeology answer 3(c): an explicit direction relationship
    between chain components, checked for internal contradiction at
    bind-time. `None` on a composition (see below) means "not declared" --
    structurally distinct from declaring ANY."""

    SAME = "SAME"
    OPPOSITE = "OPPOSITE"
    ANY = "ANY"


Expression = (
    Comparison
    | BooleanExpression
    | TemporalPredicate
    | SessionPredicate
    | EventPredicate
    | UndefinedMeasurementBasis
)


@dataclass(frozen=True)
class AtomicCondition:
    """The leaf composition primitive -- HELIOS ATOMIC (HELIOS archaeology
    finding #1: "a package declares exactly one semantic-role input").
    Exactly one explicit `(semantic_role, timeframe)` binding; the whole
    `expression` tree is evaluated entirely within that single role/
    timeframe context. `semantic_role` is a plain governed-but-open string
    (never GOLD's CONTEXT/LOCATION/CONFIRMATION/TRIGGER baked in as
    anything but example fixture data, per PID-004 sec6) -- CONTEXT_TRIGGER
    below names its two roles via dedicated typed fields, not by matching
    this string, so no strategy-generic code path depends on any
    particular role spelling.
    """

    condition_id: str
    semantic_role: str
    timeframe: Timeframe
    expression: object
    direction: Direction
    primitive: CompositionPrimitive = CompositionPrimitive.ATOMIC

    def __post_init__(self) -> None:
        if not self.condition_id or not self.condition_id.strip():
            raise InvalidCompositionError("AtomicCondition requires a non-empty condition_id")
        if not self.semantic_role or not self.semantic_role.strip():
            raise InvalidCompositionError(
                f"AtomicCondition {self.condition_id!r} requires a non-empty semantic_role "
                f"(PID-004 sec6: no ambient/implicit timeframe role)"
            )
        if not isinstance(
            self.expression,
            (Comparison, BooleanExpression, TemporalPredicate, SessionPredicate, EventPredicate, UndefinedMeasurementBasis),
        ):
            raise InvalidOperandError(
                f"AtomicCondition {self.condition_id!r}.expression must be a governed Expression "
                f"node (Comparison/BooleanExpression/TemporalPredicate/SessionPredicate/"
                f"EventPredicate/UndefinedMeasurementBasis), got {self.expression!r} "
                f"(type {type(self.expression)!r}) -- PID-004A hardening item 1: the expression "
                f"tree is closed"
            )
        if self.primitive != CompositionPrimitive.ATOMIC:
            raise InvalidCompositionError("AtomicCondition.primitive is fixed to ATOMIC")


@dataclass(frozen=True)
class AllComposition:
    """ALL -- every component must hold. No ordering, no timing (HELIOS
    archaeology finding #2: "No ordering, no timing relationship... the
    package schema itself refuses an ALL chain that declares
    sequence_index"). Mirrored here by `AllComposition` simply having no
    `sequence_index`/`ordering_window` field to declare at all -- there is
    nothing to accidentally set."""

    composition_id: str
    components: tuple[AtomicCondition, ...]
    direction_relationship: ComponentDirectionRelationship | None = None
    primitive: CompositionPrimitive = CompositionPrimitive.ALL

    def __post_init__(self) -> None:
        if len(self.components) < 2:
            raise InvalidCompositionError("ALL requires at least two components")
        if self.primitive != CompositionPrimitive.ALL:
            raise InvalidCompositionError("AllComposition.primitive is fixed to ALL")


@dataclass(frozen=True)
class AnyComposition:
    """ANY -- at least one component holds; a non-holding component is not
    a failure (HELIOS archaeology finding #3). Same "no ordering field
    exists" discipline as AllComposition."""

    composition_id: str
    components: tuple[AtomicCondition, ...]
    direction_relationship: ComponentDirectionRelationship | None = None
    primitive: CompositionPrimitive = CompositionPrimitive.ANY

    def __post_init__(self) -> None:
        if len(self.components) < 2:
            raise InvalidCompositionError("ANY requires at least two components")
        if self.primitive != CompositionPrimitive.ANY:
            raise InvalidCompositionError("AnyComposition.primitive is fixed to ANY")


class SequenceTieSemantics(StrEnum):
    """HELIOS archaeology finding #4: ties (identical match instants across
    components) are legal because e.g. a 4H close is also a 5M close.
    Explicit, governed, no implicit default (PID-004 sec33)."""

    TIES_PERMITTED = "TIES_PERMITTED"
    TIES_BREAK_ORDER = "TIES_BREAK_ORDER"


@dataclass(frozen=True)
class SequenceComponent:
    """One ordered slot in a SEQUENCE. `sequence_index` values across a
    SequenceComposition must be unique and contiguous from 0 (HELIOS
    archaeology finding #4) -- checked at the composition level, not per
    component, because contiguity is a property of the whole ordered set."""

    sequence_index: int
    component: AtomicCondition

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise InvalidCompositionError("sequence_index must be >= 0")


@dataclass(frozen=True)
class SequenceComposition:
    """SEQUENCE -- `A then B` is semantically different from `A AND B`
    (PID-004 sec8A). Never reduced to AND: this type mandatorily carries
    an explicit ordering (`sequence_index` per component, contiguous from
    0) and an explicit, non-optional `ordering_window` (HELIOS archaeology
    finding #4: "a SEQUENCE chain *must* declare ordering_window_seconds --
    refused otherwise, no default"). `tie_semantics` makes the "ties are
    legal" rule an explicit governed choice rather than an implicit
    evaluator behaviour PID-004 sec33 would otherwise forbid at
    finalisation.
    """

    composition_id: str
    components: tuple[SequenceComponent, ...]
    ordering_window_seconds: int
    tie_semantics: SequenceTieSemantics
    direction_relationship: ComponentDirectionRelationship | None = None
    primitive: CompositionPrimitive = CompositionPrimitive.SEQUENCE

    def __post_init__(self) -> None:
        if self.primitive != CompositionPrimitive.SEQUENCE:
            raise InvalidCompositionError("SequenceComposition.primitive is fixed to SEQUENCE")
        if len(self.components) < 2:
            raise InvalidCompositionError("SEQUENCE requires at least two components")
        indices = sorted(c.sequence_index for c in self.components)
        if indices != list(range(len(indices))):
            raise InvalidCompositionError(
                f"SEQUENCE sequence_index values must be unique and contiguous from 0, got {indices}"
            )
        if self.ordering_window_seconds <= 0:
            raise InvalidCompositionError("SEQUENCE requires a positive ordering_window_seconds")
        if not isinstance(self.tie_semantics, SequenceTieSemantics):
            raise InvalidCompositionError("SEQUENCE requires an explicit SequenceTieSemantics")

    def ordered_components(self) -> tuple[AtomicCondition, ...]:
        return tuple(c.component for c, _ in sorted(
            ((c, c.sequence_index) for c in self.components), key=lambda pair: pair[1]
        ))


class ExpiryMode(StrEnum):
    """PID-004 sec8. `NOT_APPLICABLE` is the required explicit value when
    expiry is genuinely irrelevant to a strategy shape (PID-004 sec8: "no
    implicit defaults... must be an explicit 'not applicable' value,
    never silently omitted/assumed")."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEVER = "NEVER"
    FRAMES = "FRAMES"
    DURATION = "DURATION"


@dataclass(frozen=True)
class ExpirySpec:
    """Explicit governed expiry (PID-004 sec8). FRAMES must deterministically
    name which timeframe's frames are being counted (HELIOS's own real
    rule: frames of the *finest bound timeframe* -- HELIOS archaeology
    finding #8) -- `finest_bound_timeframe` is mandatory for FRAMES, never
    left implicit, and `darwin.specification.validation` cross-checks it
    against the composition's own actual finest bound timeframe rather
    than trusting a caller-supplied value blindly."""

    mode: ExpiryMode
    frame_count: int | None = None
    finest_bound_timeframe: Timeframe | None = None
    duration_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.mode == ExpiryMode.FRAMES:
            if self.frame_count is None or self.frame_count <= 0:
                raise InvalidExpirySpecError("FRAMES expiry requires a positive frame_count")
            if self.finest_bound_timeframe is None:
                raise InvalidExpirySpecError(
                    "FRAMES expiry requires finest_bound_timeframe (HELIOS counts frames of the "
                    "finest bound timeframe, not an unnamed one)"
                )
        else:
            if self.frame_count is not None or self.finest_bound_timeframe is not None:
                raise InvalidExpirySpecError(f"{self.mode.value} expiry must not carry FRAMES fields")
        if self.mode == ExpiryMode.DURATION:
            if self.duration_seconds is None or self.duration_seconds <= 0:
                raise InvalidExpirySpecError("DURATION expiry requires a positive duration_seconds")
        else:
            if self.duration_seconds is not None:
                raise InvalidExpirySpecError(f"{self.mode.value} expiry must not carry duration_seconds")


def finest_bound_timeframe_of(components: tuple[AtomicCondition, ...]) -> Timeframe:
    """The finest timeframe actually bound across `components` -- used to
    validate a FRAMES ExpirySpec's declared `finest_bound_timeframe`
    against reality rather than trusting it blindly."""
    return finest([c.timeframe for c in components])


@dataclass(frozen=True)
class ContextTriggerComposition:
    """CONTEXT_TRIGGER -- genuinely distinct from a 2-item SEQUENCE (PID-004
    sec8A, HELIOS archaeology finding #5). Modelled with dedicated typed
    `context`/`trigger` fields (never a string role match against a
    generic components list) so "exactly one CONTEXT and one TRIGGER" is
    true by construction, not by a runtime count check. Preserves,
    explicitly, the three rules real HELIOS enforces that SEQUENCE has no
    equivalent of:

    1. context-established-before-trigger ordering (`context` must not
       resolve later than `trigger` -- validated at draft-validation time,
       not here, since this dataclass has no notion of "resolves at");
    2. an explicit `context_validity` (`ExpirySpec`) -- the context's OWN
       declared validity lifetime, checked against the trigger's match
       instant, never omitted (PID-004 sec33: no implicit evaluator
       default);
    3. a bind-time timeframe-coherence rule -- `context.timeframe` must
       not be finer than `trigger.timeframe` (HELIOS archaeology finding
       #5 point 4: "a context cannot frame something slower than
       itself"), enforced right here at construction.
    """

    composition_id: str
    context: AtomicCondition
    trigger: AtomicCondition
    context_validity: ExpirySpec
    direction_relationship: ComponentDirectionRelationship | None = None
    primitive: CompositionPrimitive = CompositionPrimitive.CONTEXT_TRIGGER

    def __post_init__(self) -> None:
        if self.primitive != CompositionPrimitive.CONTEXT_TRIGGER:
            raise InvalidCompositionError("ContextTriggerComposition.primitive is fixed to CONTEXT_TRIGGER")
        if self.context.timeframe.is_finer_than(self.trigger.timeframe):
            raise InvalidCompositionError(
                f"CONTEXT_TRIGGER timeframe-coherence violation: context timeframe "
                f"{self.context.timeframe.code} is finer than trigger timeframe "
                f"{self.trigger.timeframe.code} -- a context cannot frame something slower "
                f"than itself"
            )
        if self.context_validity.mode == ExpiryMode.NOT_APPLICABLE:
            raise InvalidCompositionError(
                "CONTEXT_TRIGGER requires an explicit context_validity (NEVER/FRAMES/DURATION) -- "
                "NOT_APPLICABLE would silently drop the context's own validity-lapse rule"
            )


CompositionRoot = AtomicCondition | AllComposition | AnyComposition | SequenceComposition | ContextTriggerComposition


def all_leaf_conditions(root: CompositionRoot) -> tuple[AtomicCondition, ...]:
    """Every AtomicCondition leaf reachable from `root`. Since this
    contract phase forbids nesting compositions inside one another, this
    is a one-level unwrap, not a recursive tree walk."""
    if isinstance(root, AtomicCondition):
        return (root,)
    if isinstance(root, (AllComposition, AnyComposition)):
        return root.components
    if isinstance(root, SequenceComposition):
        return root.ordered_components()
    if isinstance(root, ContextTriggerComposition):
        return (root.context, root.trigger)
    raise InvalidCompositionError(f"Unrecognised composition root type: {type(root)!r}")


# --- normalized state semantics (PID-004 sec7) ------------------------------
#
# IMPORTANT DISTINCTION (the one the Architect specifically flagged as easy
# to get wrong): the vocabulary and transition table below are semantic
# RULES governing validity/expiry/invalidation/re-arm behaviour that a
# StrategyVersion's composition must remain compatible with -- input
# semantics for a future HELIOS-side runtime. They are NOT a runtime state
# machine DARWIN itself executes. There is no `transition()` function, no
# mutable state instance, and no evaluator anywhere in this module or this
# package. `NormalizedStrategyState` exists purely as reference/documentation
# data so a future compiler knows exactly which HELIOS states DARWIN's own
# expiry/invalidation declarations must remain expressible against.


class NormalizedStrategyState(StrEnum):
    """Verbatim HELIOS vocabulary (HELIOS archaeology finding #7). DARWIN
    never instantiates or transitions one of these -- see module-level note
    above."""

    DORMANT = "DORMANT"
    FORMING = "FORMING"
    MATCHED = "MATCHED"
    ACTIVE = "ACTIVE"
    WEAKENING = "WEAKENING"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"


# Reference-only legal-transition table (HELIOS archaeology finding #7).
# Never consumed by an evaluator in this package -- kept here solely so a
# future DARWIN->HELIOS compiler and this package's own tests can assert
# that DARWIN's expiry/invalidation declarations remain compatible with it,
# without DARWIN ever walking it at runtime.
NORMALIZED_STATE_LEGAL_TRANSITIONS: dict[NormalizedStrategyState, frozenset[NormalizedStrategyState]] = {
    NormalizedStrategyState.DORMANT: frozenset(
        {NormalizedStrategyState.FORMING, NormalizedStrategyState.MATCHED, NormalizedStrategyState.INVALID}
    ),
    NormalizedStrategyState.FORMING: frozenset(
        {NormalizedStrategyState.MATCHED, NormalizedStrategyState.INVALID, NormalizedStrategyState.EXPIRED}
    ),
    NormalizedStrategyState.MATCHED: frozenset(
        {NormalizedStrategyState.ACTIVE, NormalizedStrategyState.INVALID, NormalizedStrategyState.EXPIRED}
    ),
    NormalizedStrategyState.ACTIVE: frozenset(
        {NormalizedStrategyState.WEAKENING, NormalizedStrategyState.INVALID, NormalizedStrategyState.EXPIRED}
    ),
    NormalizedStrategyState.WEAKENING: frozenset(
        {NormalizedStrategyState.ACTIVE, NormalizedStrategyState.INVALID, NormalizedStrategyState.EXPIRED}
    ),
    NormalizedStrategyState.INVALID: frozenset({NormalizedStrategyState.DORMANT}),
    NormalizedStrategyState.EXPIRED: frozenset({NormalizedStrategyState.DORMANT}),
}


class RearmPolicy(StrEnum):
    """HELIOS archaeology finding #7/#8: a resolved INVALID/EXPIRED
    occurrence rearms only by passing back through DORMANT -- there is no
    "instant re-arm on invalidation" in real HELIOS. DARWIN records this as
    the one governed rearm policy its composition semantics must remain
    compatible with; it is not itself enforced by any runtime here."""

    REARM_ONLY_VIA_DORMANT = "REARM_ONLY_VIA_DORMANT"
