"""`ExecutionPolicyVersion` -- shared DARWIN research execution-POLICY
IDENTITY (PID-006A sec7). Not APOLLO-private, not ATHENA-private, not part
of `StrategyVersion` -- mirrors the identity separation
`darwin.specification.policy` already documents:

    StrategyVersion != ExecutionPolicyVersion != DIKEPolicyVersion != ...

PID-006A scope rule (sec7, load-bearing): this module defines policy
IDENTITY, not execution mechanics. There is no order/fill/simulation
function anywhere here. Each mandatory axis is represented by an explicit,
versioned `ExecutionPolicyComponent` REFERENCE (kind + component_id +
component_version + a small configuration payload) rather than embedded
executable/simulation code -- exactly the "prefer explicit versioned
policy-component references" instruction. A future APOLLO/ATHENA runtime
resolves a `component_id`/`component_version` pair to real mechanics; this
package only ever records which one was selected.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.core.identities import new_id
from darwin.research_contracts.errors import (
    ExecutionPolicyIncompleteError,
    InvalidConfigurationError,
)
from darwin.specification.fingerprint import canonical_hash, canonicalize


class ExecutionPolicyComponentKind(StrEnum):
    """The six mandatory identity axes PID-006A sec7 requires to be
    explicit. Closed vocabulary -- extending it is a deliberate, reviewed
    product decision, never inferred from a caller-supplied string."""

    TIMING_METHODOLOGY = "TIMING_METHODOLOGY"
    PRICE_FILL_METHODOLOGY = "PRICE_FILL_METHODOLOGY"
    INTRABAR_RESOLUTION_METHODOLOGY = "INTRABAR_RESOLUTION_METHODOLOGY"
    COST_METHODOLOGY = "COST_METHODOLOGY"
    QUANTITY_ECONOMIC_METHODOLOGY = "QUANTITY_ECONOMIC_METHODOLOGY"
    SESSION_FORCE_FLAT_METHODOLOGY = "SESSION_FORCE_FLAT_METHODOLOGY"


@dataclass(frozen=True)
class ExecutionPolicyComponent:
    """One explicit, versioned policy-component reference (PID-006A
    sec7). `configuration` is a small closed set of plain, canonicalisable
    key/value facts about this exact component selection (e.g. a fixed
    slippage-model parameter) -- never executable code, never a plugin
    reference, never a callable. Two components are semantically identical
    if and only if `kind`, `component_id`, `component_version`, and
    `configuration` all agree.
    """

    kind: ExecutionPolicyComponentKind
    component_id: str
    component_version: str
    configuration: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.component_id or not self.component_id.strip():
            raise InvalidConfigurationError(
                f"ExecutionPolicyComponent ({self.kind.value if isinstance(self.kind, ExecutionPolicyComponentKind) else self.kind!r}) "
                f"requires a non-empty component_id"
            )
        if not self.component_version or not self.component_version.strip():
            raise InvalidConfigurationError(
                f"ExecutionPolicyComponent {self.component_id!r} requires a non-empty component_version"
            )


#: PID-006A sec8 -- `ZERO_COST` is LOCKED: an explicit, named, versioned,
#: fingerprinted cost-methodology value, permitted for mechanical/
#: determinism tests only, and must be deliberately selected -- it is a
#: real, ordinary `ExecutionPolicyComponent`, never a magic sentinel and
#: never the default `ExecutionPolicyVersion.cost_methodology` takes on if
#: omitted (there is no default -- see `build_execution_policy_version`).
ZERO_COST_COMPONENT_ID = "ZERO_COST"
ZERO_COST_COMPONENT_VERSION = "v1"
ZERO_COST = ExecutionPolicyComponent(
    kind=ExecutionPolicyComponentKind.COST_METHODOLOGY,
    component_id=ZERO_COST_COMPONENT_ID,
    component_version=ZERO_COST_COMPONENT_VERSION,
    configuration=(),
)


@dataclass(frozen=True)
class ExecutionPolicyVersion:
    """Immutable, versioned, fingerprinted execution-policy identity
    (PID-006A sec7). Every axis is mandatory -- a `None` axis is rejected
    at construction (`build_execution_policy_version`) with
    `ExecutionPolicyIncompleteError`, never silently defaulted (PID-006A
    sec8: "A missing cost-methodology field must be a construction-time
    rejection, never silently interpreted as zero cost" -- generalised
    here to every axis, not only cost).
    """

    execution_policy_id: str
    timing_methodology: ExecutionPolicyComponent
    price_fill_methodology: ExecutionPolicyComponent
    intrabar_resolution_methodology: ExecutionPolicyComponent
    cost_methodology: ExecutionPolicyComponent
    quantity_economic_methodology: ExecutionPolicyComponent
    session_force_flat_methodology: ExecutionPolicyComponent
    fingerprint: str


_AXIS_FIELDS: tuple[str, ...] = (
    "timing_methodology",
    "price_fill_methodology",
    "intrabar_resolution_methodology",
    "cost_methodology",
    "quantity_economic_methodology",
    "session_force_flat_methodology",
)

_AXIS_TO_KIND: dict[str, ExecutionPolicyComponentKind] = {
    "timing_methodology": ExecutionPolicyComponentKind.TIMING_METHODOLOGY,
    "price_fill_methodology": ExecutionPolicyComponentKind.PRICE_FILL_METHODOLOGY,
    "intrabar_resolution_methodology": ExecutionPolicyComponentKind.INTRABAR_RESOLUTION_METHODOLOGY,
    "cost_methodology": ExecutionPolicyComponentKind.COST_METHODOLOGY,
    "quantity_economic_methodology": ExecutionPolicyComponentKind.QUANTITY_ECONOMIC_METHODOLOGY,
    "session_force_flat_methodology": ExecutionPolicyComponentKind.SESSION_FORCE_FLAT_METHODOLOGY,
}


def _fingerprint_payload(components: dict[str, ExecutionPolicyComponent]) -> dict:
    return {axis: canonicalize(components[axis]) for axis in _AXIS_FIELDS}


def compute_execution_policy_fingerprint(**components: ExecutionPolicyComponent) -> str:
    """Recomputable independently of a live `ExecutionPolicyVersion`
    instance -- used both by `build_execution_policy_version` and by
    `darwin.research_store`'s persistence layer on reconstruction.
    Accepts the six axes by keyword (same names as `_AXIS_FIELDS`)."""
    return canonical_hash(_fingerprint_payload(components))


def build_execution_policy_version(
    *,
    timing_methodology: ExecutionPolicyComponent | None,
    price_fill_methodology: ExecutionPolicyComponent | None,
    intrabar_resolution_methodology: ExecutionPolicyComponent | None,
    cost_methodology: ExecutionPolicyComponent | None,
    quantity_economic_methodology: ExecutionPolicyComponent | None,
    session_force_flat_methodology: ExecutionPolicyComponent | None,
) -> ExecutionPolicyVersion:
    """The only supported way to construct an `ExecutionPolicyVersion`
    (PID-006A sec7). Every axis is a required keyword argument with no
    default -- a caller must pass `cost_methodology=ZERO_COST` explicitly
    to select it; there is no way to "leave it out and get ZERO_COST".

    Raises `ExecutionPolicyIncompleteError` if any axis is `None` or not
    an `ExecutionPolicyComponent` of the matching
    `ExecutionPolicyComponentKind`.
    """
    components = {
        "timing_methodology": timing_methodology,
        "price_fill_methodology": price_fill_methodology,
        "intrabar_resolution_methodology": intrabar_resolution_methodology,
        "cost_methodology": cost_methodology,
        "quantity_economic_methodology": quantity_economic_methodology,
        "session_force_flat_methodology": session_force_flat_methodology,
    }
    for axis, component in components.items():
        expected_kind = _AXIS_TO_KIND[axis]
        if component is None:
            raise ExecutionPolicyIncompleteError(
                f"ExecutionPolicyVersion missing mandatory component for axis "
                f"{expected_kind.value} -- absence never means a default (PID-006A sec7)"
            )
        if not isinstance(component, ExecutionPolicyComponent):
            raise InvalidConfigurationError(
                f"ExecutionPolicyVersion axis {expected_kind.value} requires an "
                f"ExecutionPolicyComponent, got {type(component)!r}"
            )
        if component.kind != expected_kind:
            raise InvalidConfigurationError(
                f"ExecutionPolicyVersion axis {expected_kind.value} was given a component of "
                f"kind {component.kind.value} instead"
            )

    fingerprint = compute_execution_policy_fingerprint(**components)
    return ExecutionPolicyVersion(
        execution_policy_id=new_id(),
        fingerprint=fingerprint,
        **components,
    )
