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
        # SPEC-FIX-001: the `tuple[AtomicCondition, ...]` type hint above is
        # not a runtime guarantee -- nothing stops a caller (e.g. via
        # `dataclasses.replace()`) from substituting a different
        # composition type into `components`. This contract phase forbids
        # nesting (see module docstring); a non-AtomicCondition member must
        # fail closed here, at construction, rather than surface later as a
        # bare AttributeError/TypeError wherever a leaf's AtomicCondition-
        # only attributes (e.g. `.expression`) are first dereferenced.
        for component in self.components:
            if not isinstance(component, AtomicCondition):
                raise InvalidCompositionError(
                    f"AllComposition {self.composition_id!r} components must all be "
                    f"AtomicCondition leaves (nesting is not supported in this contract "
                    f"phase), got {component!r} (type {type(component)!r})"
                )
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
        # SPEC-FIX-001: same rationale as AllComposition above -- the type
        # hint alone does not stop a malformed element (e.g. a nested
        # composition) from being substituted in; fail closed here rather
        # than let it surface later as a bare AttributeError/TypeError.
        for component in self.components:
            if not isinstance(component, AtomicCondition):
                raise InvalidCompositionError(
                    f"AnyComposition {self.composition_id!r} components must all be "
                    f"AtomicCondition leaves (nesting is not supported in this contract "
                    f"phase), got {component!r} (type {type(component)!r})"
                )
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
        # SPEC-FIX-001: `component: AtomicCondition` is a type hint, not a
        # runtime guarantee -- fail closed rather than let a malformed
        # `.component` surface as a bare attribute error downstream.
        if not isinstance(self.component, AtomicCondition):
            raise InvalidCompositionError(
                f"SequenceComponent (sequence_index={self.sequence_index!r}).component must be "
                f"an AtomicCondition leaf (nesting is not supported in this contract phase), "
                f"got {self.component!r} (type {type(self.component)!r})"
            )
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
        # SPEC-FIX-001: this type check MUST run before the `c.sequence_index`
        # access immediately below -- a non-SequenceComponent element (e.g.
        # a nested composition substituted in via `dataclasses.replace()`)
        # would otherwise crash there with a bare AttributeError before this
        # method ever gets a chance to raise the governed
        # InvalidCompositionError.
        for component in self.components:
            if not isinstance(component, SequenceComponent):
                raise InvalidCompositionError(
                    f"SequenceComposition {self.composition_id!r} components must all be "
                    f"SequenceComponent instances, got {component!r} (type {type(component)!r})"
                )
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
        # SPEC-FIX-001: these type checks MUST run before the
        # `self.context.timeframe`/`self.trigger.timeframe` access
        # immediately below -- a malformed `context`/`trigger` (e.g. a
        # nested composition substituted in via `dataclasses.replace()`)
        # would otherwise crash there with a bare AttributeError before
        # this method ever gets a chance to raise the governed
        # InvalidCompositionError.
        if not isinstance(self.context, AtomicCondition):
            raise InvalidCompositionError(
                f"ContextTriggerComposition {self.composition_id!r}.context must be an "
                f"AtomicCondition leaf (nesting is not supported in this contract phase), "
                f"got {self.context!r} (type {type(self.context)!r})"
            )
        if not isinstance(self.trigger, AtomicCondition):
            raise InvalidCompositionError(
                f"ContextTriggerComposition {self.composition_id!r}.trigger must be an "
                f"AtomicCondition leaf (nesting is not supported in this contract phase), "
                f"got {self.trigger!r} (type {type(self.trigger)!r})"
            )
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
    is a one-level unwrap, not a recursive tree walk.

    SPEC-FIX-001 defence-in-depth: every `__post_init__` above already
    rejects a malformed leaf at construction time. This function re-checks
    anyway, structurally, before returning -- because `__post_init__` only
    runs once, at construction, and a frozen dataclass's field can still be
    mutated afterwards via `object.__setattr__` (never via
    `dataclasses.replace()`, which DOES re-invoke `__post_init__` on the
    new instance and is therefore already caught above). If malformed
    state ever reaches this function despite the constructor checks, it
    must fail closed here rather than hand a non-AtomicCondition leaf to a
    caller that will blindly dereference AtomicCondition-only attributes
    (e.g. `.expression`) on it.
    """
    if isinstance(root, AtomicCondition):
        leaves: tuple[AtomicCondition, ...] = (root,)
    elif isinstance(root, (AllComposition, AnyComposition)):
        leaves = root.components
    elif isinstance(root, SequenceComposition):
        # `ordered_components()` itself dereferences `c.sequence_index` for
        # every `c` in `root.components` -- guard that here too, so an
        # `object.__setattr__`-corrupted `components` tuple fails closed
        # with InvalidCompositionError rather than a bare AttributeError
        # inside `ordered_components()` before this function's own
        # leaf-type assertion below ever runs.
        for component in root.components:
            if not isinstance(component, SequenceComponent):
                raise InvalidCompositionError(
                    f"all_leaf_conditions() found a non-SequenceComponent element "
                    f"{component!r} (type {type(component)!r}) in SequenceComposition "
                    f"{root.composition_id!r}.components -- malformed composition state "
                    f"reached the leaf-extraction boundary despite constructor checks"
                )
        leaves = root.ordered_components()
    elif isinstance(root, ContextTriggerComposition):
        leaves = (root.context, root.trigger)
    else:
        raise InvalidCompositionError(f"Unrecognised composition root type: {type(root)!r}")

    for leaf in leaves:
        if not isinstance(leaf, AtomicCondition):
            raise InvalidCompositionError(
                f"all_leaf_conditions() resolved a non-AtomicCondition leaf {leaf!r} "
                f"(type {type(leaf)!r}) from root {root!r} -- malformed composition state "
                f"reached the leaf-extraction boundary despite constructor checks (e.g. via "
                f"object.__setattr__ on an already-constructed frozen dataclass)"
            )
    return tuple(leaves)


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
