"""`ResearchPartitionPolicyVersion` -- a closed role vocabulary
(DEVELOPMENT/VALIDATION/PROTECTED_HOLDOUT) bound to a SPECIFIC governed
research input identity (PID-006A sec9).

Deliberately NOT a bare enum wrapper: a protected holdout must be
distinguishable by BOTH role AND exact data identity -- never by the word
`PROTECTED_HOLDOUT` alone (PID-006A sec9). Binding is expressed via
`ResearchInputBinding` (see `darwin.research_contracts.input_binding`),
never hardcoded to `MarketDataset` directly, so a future typed HMT-2 event
dataset can participate without redefining what a partition role means.

No statistical machinery lives here -- this module records WHICH role was
assigned to WHICH governed input, nothing about how partitions are
constructed, sized, or evaluated.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.core.identities import new_id
from darwin.research_contracts.errors import InvalidConfigurationError
from darwin.research_contracts.input_binding import ResearchInputBinding
from darwin.specification.fingerprint import canonical_hash


class ResearchPartitionRole(StrEnum):
    """Closed role vocabulary (PID-006A sec9). No statistical machinery --
    purely an identity label bound to a governed input."""

    DEVELOPMENT = "DEVELOPMENT"
    VALIDATION = "VALIDATION"
    PROTECTED_HOLDOUT = "PROTECTED_HOLDOUT"


@dataclass(frozen=True)
class ResearchPartitionPolicyVersion:
    """Immutable, deterministically fingerprinted binding of one
    `ResearchPartitionRole` to one `ResearchInputBinding` (PID-006A sec9).
    `partition_policy_id` is an opaque application-generated identity,
    excluded from `fingerprint`.
    """

    partition_policy_id: str
    role: ResearchPartitionRole
    input_binding: ResearchInputBinding
    fingerprint: str


def _fingerprint_payload(*, role: ResearchPartitionRole, input_binding: ResearchInputBinding) -> dict:
    # Deliberately binds the input binding's OWN fingerprint plus its
    # governed identity/kind -- never just role.value alone (PID-006A
    # sec9: "never by the word PROTECTED_HOLDOUT alone").
    return {
        "role": role.value,
        "input_binding_fingerprint": input_binding.fingerprint,
        "input_binding_kind": input_binding.input_kind.value,
        "input_binding_logical_role": input_binding.logical_input_role,
    }


def compute_research_partition_policy_fingerprint(
    *, role: ResearchPartitionRole, input_binding: ResearchInputBinding
) -> str:
    """Recomputable independently of a live
    `ResearchPartitionPolicyVersion` instance -- used both by
    `build_research_partition_policy_version` and by
    `darwin.research_store`'s persistence layer on reconstruction."""
    return canonical_hash(_fingerprint_payload(role=role, input_binding=input_binding))


def build_research_partition_policy_version(
    *, role: ResearchPartitionRole, input_binding: ResearchInputBinding
) -> ResearchPartitionPolicyVersion:
    """The only supported way to construct a
    `ResearchPartitionPolicyVersion` (PID-006A sec9). Deterministic
    regardless of how `input_binding` itself was assembled -- the
    fingerprint depends only on `role` and `input_binding`'s own already-
    canonical identity fields, never on incidental construction-argument
    ordering."""
    if not isinstance(role, ResearchPartitionRole):
        raise InvalidConfigurationError(f"ResearchPartitionPolicyVersion requires a governed ResearchPartitionRole, got {role!r}")
    if not isinstance(input_binding, ResearchInputBinding):
        raise InvalidConfigurationError(
            f"ResearchPartitionPolicyVersion requires a ResearchInputBinding, got {type(input_binding)!r}"
        )
    fingerprint = compute_research_partition_policy_fingerprint(role=role, input_binding=input_binding)
    return ResearchPartitionPolicyVersion(
        partition_policy_id=new_id(),
        role=role,
        input_binding=input_binding,
        fingerprint=fingerprint,
    )
