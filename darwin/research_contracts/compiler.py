"""`CanonicalStrategyCompiler` -- deterministic, versioned, side-effect-free
translation of an immutable `darwin.specification.domain.StrategyVersion`
into an immutable `ExecutableStrategyPlan` (PID-006A sec2/sec3).

Hard prohibitions (PID-006A sec2, tested in
tests/architecture/test_research_contracts_layering.py and
tests/unit/test_research_contracts_compiler.py): this module never
touches HERMES, SQL, market data, historical replay, simulation, ranking,
a broker, the network, an LLM, or `eval`/`exec`/arbitrary plugin
execution. It translates already-finalised deterministic semantics; it
never reinterprets them. There is no `evaluate()`/`run()`/`replay()`
function anywhere in this module.

Reuse, don't reinvent (PID-006A sec2): every semantic field is carried
over through `darwin.specification.fingerprint.canonicalize()`/
`canonical_hash()` -- the exact discipline
`darwin.specification.domain.StrategyVersion.semantic_fingerprint` itself
already uses. This module does not hand-write a second serialisation
convention for the composition/expression tree; it reuses the generic one
verbatim.

Judgment call (flagged for the Architect/auditor -- PID-006A delivery
discipline item 5): v1 fully, deterministically represents ATOMIC/ALL/ANY
composition -- every field of `AtomicCondition`/`AllComposition`/
`AnyComposition` is carried over unchanged, including nested canonical/
derived fact references, parameters, sessions, expiry, etc. A `SEQUENCE`
or `CONTEXT_TRIGGER` node -- anywhere in the composition tree, not only
at its root (including nested inside an `AllComposition`/
`AnyComposition`'s `components`) -- is capability-blocked
(`ENGINE_CAPABILITY_BLOCKED`, reason `UNSUPPORTED_COMPOSITION_PRIMITIVE`),
NOT because their data cannot be copied into a dict (it trivially can),
but because `SequenceComposition.ordering_window_seconds`/`tie_semantics`
and `ContextTriggerComposition.context_validity`/timeframe-coherence rule
are HELIOS-side TEMPORAL/ORDERING semantics -- carrying them into
`ExecutableStrategyPlan` as inert copied data, with no corresponding
executable temporal-evaluation contract, would silently commit this PID
to an evaluation semantics it never authorises (PID-006A sec13: "a valid
StrategyVersion may require a feature the compiler doesn't yet support --
that doesn't make the StrategyVersion invalid"). This is exactly that
case, made explicit rather than silently resolved either way.
"""
from __future__ import annotations

from dataclasses import dataclass

from darwin.core.identities import new_id
from darwin.research_contracts.errors import (
    CapabilityBlockContext,
    CapabilityBlockReason,
    EngineCapabilityBlockedError,
)
from darwin.specification.composition import (
    AllComposition,
    AnyComposition,
    AtomicCondition,
    ContextTriggerComposition,
    SequenceComposition,
)
from darwin.specification.domain import SEMANTIC_FIELD_NAMES, StrategyVersion
from darwin.specification.fingerprint import canonical_hash, canonicalize

#: Stable identity of this compiler implementation. Bound into every
#: `ExecutableStrategyPlan.fingerprint` (PID-006A sec5) so a future
#: compiler upgrade never silently produces a plan indistinguishable from
#: one compiled by an earlier, less-capable implementation.
COMPILER_ID = "darwin.research_contracts.compiler.CanonicalStrategyCompiler"
COMPILER_VERSION = "1.0.0"

#: `ExecutableStrategyPlan`'s own payload schema version (PID-006A sec5).
#: Bumped whenever the *shape* of the compiled payload changes, independent
#: of `COMPILER_VERSION` (which tracks the compiler's own behaviour/
#: capability envelope).
PLAN_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class ExecutableStrategyPlan:
    """Immutable, deterministically fingerprinted compiled strategy
    (PID-006A sec3). NOT a backtest: no mutable market state, no order/
    position/P&L object appears anywhere on this class or in any field it
    carries -- see tests/architecture/test_research_contracts_layering.py
    for the automated proof.

    `plan_id` is an application-generated opaque identity (PID-001 sec21
    style, via `darwin.core.identities.new_id()`) -- excluded from
    `fingerprint`, exactly as `StrategyVersion.strategy_version_id` is
    excluded from `semantic_fingerprint`. Two independent compilations of
    the same `StrategyVersion` with the same compiler produce two
    `ExecutableStrategyPlan` instances with different `plan_id`s but an
    identical `fingerprint` (PID-006A sec3/sec5: "same StrategyVersion ->
    bit/semantic-identical plan and fingerprint across independent
    runs").

    `source_strategy_version_id` is carried for traceability only (a
    plain string, never itself bound into `fingerprint` -- mirrors
    `StrategyVersion`'s own `_EXCLUDED_FROM_SEMANTIC_FINGERPRINT`
    discipline for non-semantic identity fields). The actual bound
    identity is `source_semantic_fingerprint`.
    """

    plan_id: str
    source_strategy_version_id: str
    source_semantic_fingerprint: str
    compiler_id: str
    compiler_version: str
    plan_schema_version: str
    semantic_payload: dict
    fingerprint: str


def _identity_payload(
    *,
    source_semantic_fingerprint: str,
    compiler_id: str,
    compiler_version: str,
    plan_schema_version: str,
    semantic_payload: dict,
) -> dict:
    """The exact structure `ExecutableStrategyPlan.fingerprint` is computed
    from (PID-006A sec5: "must bind at least: source StrategyVersion.
    semantic_fingerprint, compiler identity/version, the canonical plan
    payload, and a plan schema version"). Kept as one explicit function so
    a reconstruction from storage can recompute the identical fingerprint
    (PID-006A sec15) without duplicating this shape by hand.
    """
    return {
        "source_semantic_fingerprint": source_semantic_fingerprint,
        "compiler_id": compiler_id,
        "compiler_version": compiler_version,
        "plan_schema_version": plan_schema_version,
        "semantic_payload": semantic_payload,
    }


def compute_plan_fingerprint(
    *,
    source_semantic_fingerprint: str,
    compiler_id: str,
    compiler_version: str,
    plan_schema_version: str,
    semantic_payload: dict,
) -> str:
    """Recomputable independently of any live `ExecutableStrategyPlan`
    instance -- used both by `CanonicalStrategyCompiler.compile` and by
    `darwin.research_store`'s persistence layer on reconstruction (PID-006A
    sec15: "recompute the fingerprint from the reconstructed payload and
    compare against the stored fingerprint")."""
    return canonical_hash(
        _identity_payload(
            source_semantic_fingerprint=source_semantic_fingerprint,
            compiler_id=compiler_id,
            compiler_version=compiler_version,
            plan_schema_version=plan_schema_version,
            semantic_payload=semantic_payload,
        )
    )


def _walk_composition_capability(node: object, *, root_id: str) -> None:
    """Recursively walk every composition node reachable from `node` --
    not just the root -- and fail closed the instant any node ANYWHERE in
    the tree is a SEQUENCE/CONTEXT_TRIGGER primitive, or any node type
    this compiler does not explicitly recognise (PID-006A sec4/sec13).

    This exists because `AllComposition`/`AnyComposition.components` is
    typed as `tuple[AtomicCondition, ...]` but that is a type HINT, not a
    runtime guarantee -- nothing in `darwin.specification.composition`
    enforces it at construction time (`AllComposition.__post_init__` only
    checks `len(components) >= 2`). A component slot can be populated
    with any object, including a composition primitive this compiler does
    not support (e.g. a `SequenceComposition` smuggled inside an
    `AllComposition`'s `components` tuple, bypassing `finalise()`).
    Checking only `strategy_version.composition`'s own top-level type --
    as an earlier version of this function did -- silently carried such a
    smuggled node through as inert `canonicalize()`d data instead of
    capability-blocking it, which is exactly the "semantic field silently
    dropped" failure PID-006A sec4 forbids (found by independent adversarial
    review; see PR #18 follow-up commit).
    """
    if isinstance(node, (SequenceComposition, ContextTriggerComposition)):
        raise EngineCapabilityBlockedError(
            f"CanonicalStrategyCompiler {COMPILER_VERSION} cannot yet compile "
            f"composition primitive {node.primitive.value} "
            f"(composition_id={node.composition_id!r}, found while walking the composition "
            f"tree rooted at {root_id!r}) -- SEQUENCE/CONTEXT_TRIGGER temporal-ordering "
            f"semantics are not yet representable in ExecutableStrategyPlan "
            f"(PID-006A sec13/sec2 judgment call)",
            context=CapabilityBlockContext(
                reason=CapabilityBlockReason.UNSUPPORTED_COMPOSITION_PRIMITIVE,
                subject_ref=node.composition_id,
                detail=(("primitive", node.primitive.value), ("root_composition_id", root_id)),
            ),
        )
    if isinstance(node, AtomicCondition):
        return  # leaf -- nothing further to walk for composition-primitive capability purposes
    if isinstance(node, (AllComposition, AnyComposition)):
        for component in node.components:
            _walk_composition_capability(component, root_id=root_id)
        return
    # Any other node type is one this compiler does not explicitly
    # recognise at all -- fail closed rather than silently canonicalize()
    # it as inert data (PID-006A sec13: no third state where a semantic
    # field is silently dropped).
    raise EngineCapabilityBlockedError(
        f"CanonicalStrategyCompiler {COMPILER_VERSION} encountered an unrecognised "
        f"composition node type {type(node).__name__!r} while walking the composition tree "
        f"rooted at {root_id!r} -- refusing to silently carry it over as inert data",
        context=CapabilityBlockContext(
            reason=CapabilityBlockReason.UNSUPPORTED_COMPOSITION_PRIMITIVE,
            subject_ref=getattr(node, "composition_id", getattr(node, "condition_id", root_id)),
            detail=(("node_type", type(node).__name__), ("root_composition_id", root_id)),
        ),
    )


def _check_composition_capability(strategy_version: StrategyVersion) -> None:
    """Fail closed on the one deliberate v1 capability gap (module
    docstring), across the ENTIRE composition tree -- not just its root
    (see `_walk_composition_capability`). Raised before any payload is
    built -- a capability-blocked StrategyVersion never produces a
    partial/best-effort plan."""
    composition = strategy_version.composition
    root_id = getattr(composition, "composition_id", getattr(composition, "condition_id", "<root>"))
    _walk_composition_capability(composition, root_id=root_id)


class CanonicalStrategyCompiler:
    """Deterministic, versioned, side-effect-free compiler (PID-006A
    sec2). Holds no mutable state across calls -- `compile()` is a pure
    function of its `strategy_version` argument plus the module-level
    `COMPILER_ID`/`COMPILER_VERSION`/`PLAN_SCHEMA_VERSION` constants.
    """

    compiler_id = COMPILER_ID
    compiler_version = COMPILER_VERSION
    plan_schema_version = PLAN_SCHEMA_VERSION

    def compile(self, strategy_version: StrategyVersion) -> ExecutableStrategyPlan:
        """Translate `strategy_version` into an `ExecutableStrategyPlan`,
        or raise `EngineCapabilityBlockedError` if a semantic it requires
        is not yet supported (PID-006A sec4/sec13). Never mutates
        `strategy_version`; never touches anything outside the object
        graph it was given.
        """
        _check_composition_capability(strategy_version)

        # Every SEMANTIC_FIELD_NAMES entry is SUPPORTED in v1 once the
        # composition-primitive capability check above has passed --
        # carried over via the exact same canonicalize() discipline
        # StrategyVersion.semantic_fingerprint itself is built on (PID-006A
        # sec2: "reuse, don't reinvent"). No field is silently dropped --
        # see tests/unit/test_research_contracts_compiler.py's coverage
        # test, which walks SEMANTIC_FIELD_NAMES itself rather than a
        # hand-maintained copy of it.
        semantic_payload = {
            name: canonicalize(getattr(strategy_version, name)) for name in SEMANTIC_FIELD_NAMES
        }

        fingerprint = compute_plan_fingerprint(
            source_semantic_fingerprint=strategy_version.semantic_fingerprint,
            compiler_id=self.compiler_id,
            compiler_version=self.compiler_version,
            plan_schema_version=self.plan_schema_version,
            semantic_payload=semantic_payload,
        )

        return ExecutableStrategyPlan(
            plan_id=new_id(),
            source_strategy_version_id=strategy_version.strategy_version_id,
            source_semantic_fingerprint=strategy_version.semantic_fingerprint,
            compiler_id=self.compiler_id,
            compiler_version=self.compiler_version,
            plan_schema_version=self.plan_schema_version,
            semantic_payload=semantic_payload,
            fingerprint=fingerprint,
        )
