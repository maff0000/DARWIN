"""`ResearchInputBinding` -- a neutral, immutable identity object answering:
exactly which governed historical input did this configuration intend to
consume, and for what role? (PID-006A sec10).

Never binds scientific identity to an absolute filesystem path -- only to
a governed dataset's own opaque identity (`governed_dataset_id`) and
content fingerprint (`dataset_semantic_fingerprint`). The first concrete
`input_kind`, `MARKET_CANDLE_DATASET`, binds the EXISTING
`darwin.hermes.dataset.MarketDataset` (its `dataset_id` +
`fingerprint_sha256` -- read directly from that module rather than
guessed). `ResearchInputKind` is a discriminated, extensible enum
specifically so a later `MARKET_EVENT_DATASET` kind (a future typed HMT-2
event dataset) can participate without redefining what a partition role
binds to (see `darwin.research_contracts.partition_policy`) -- this
module implements no HMT-2 loading of any kind.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from darwin.core.identities import new_id
from darwin.hermes.dataset import MarketDataset
from darwin.research_contracts.errors import ResearchInputBindingError
from darwin.specification.fingerprint import canonical_hash


class ResearchInputKind(StrEnum):
    """Discriminated, closed-but-extensible vocabulary of governed
    research input kinds (PID-006A sec10). Only `MARKET_CANDLE_DATASET`
    is implemented in this work package -- adding a future
    `MARKET_EVENT_DATASET` member is a deliberate, reviewed extension of
    this enum, never a structural rewrite of `ResearchInputBinding`
    itself."""

    MARKET_CANDLE_DATASET = "MARKET_CANDLE_DATASET"


@dataclass(frozen=True)
class ResearchInputBinding:
    """PID-006A sec10 minimum conceptual identity: logical input role,
    dataset/input kind, governed dataset identity, semantic fingerprint/
    hash. `input_binding_id` is an opaque application-generated identity,
    excluded from `fingerprint` (same discipline as
    `ExecutableStrategyPlan.plan_id`).
    """

    input_binding_id: str
    logical_input_role: str
    input_kind: ResearchInputKind
    governed_dataset_id: str
    dataset_semantic_fingerprint: str
    fingerprint: str


def _fingerprint_payload(
    *,
    logical_input_role: str,
    input_kind: ResearchInputKind,
    governed_dataset_id: str,
    dataset_semantic_fingerprint: str,
) -> dict:
    return {
        "logical_input_role": logical_input_role,
        "input_kind": input_kind.value,
        "governed_dataset_id": governed_dataset_id,
        "dataset_semantic_fingerprint": dataset_semantic_fingerprint,
    }


def compute_research_input_binding_fingerprint(
    *,
    logical_input_role: str,
    input_kind: ResearchInputKind,
    governed_dataset_id: str,
    dataset_semantic_fingerprint: str,
) -> str:
    """Recomputable independently of a live `ResearchInputBinding`
    instance -- used both by `build_research_input_binding` and by
    `darwin.research_store`'s persistence layer on reconstruction."""
    return canonical_hash(
        _fingerprint_payload(
            logical_input_role=logical_input_role,
            input_kind=input_kind,
            governed_dataset_id=governed_dataset_id,
            dataset_semantic_fingerprint=dataset_semantic_fingerprint,
        )
    )


def build_research_input_binding(
    *,
    logical_input_role: str,
    input_kind: ResearchInputKind,
    governed_dataset_id: str,
    dataset_semantic_fingerprint: str,
) -> ResearchInputBinding:
    """The only supported way to construct a `ResearchInputBinding`
    directly from its raw identity fields. Prefer
    `research_input_binding_from_market_dataset` when binding an existing
    in-memory `MarketDataset`.
    """
    if not logical_input_role or not logical_input_role.strip():
        raise ResearchInputBindingError("ResearchInputBinding requires a non-empty logical_input_role")
    if not isinstance(input_kind, ResearchInputKind):
        raise ResearchInputBindingError(f"ResearchInputBinding requires a governed ResearchInputKind, got {input_kind!r}")
    if not governed_dataset_id or not governed_dataset_id.strip():
        raise ResearchInputBindingError("ResearchInputBinding requires a non-empty governed_dataset_id")
    if not dataset_semantic_fingerprint or not dataset_semantic_fingerprint.strip():
        raise ResearchInputBindingError("ResearchInputBinding requires a non-empty dataset_semantic_fingerprint")

    fingerprint = compute_research_input_binding_fingerprint(
        logical_input_role=logical_input_role,
        input_kind=input_kind,
        governed_dataset_id=governed_dataset_id,
        dataset_semantic_fingerprint=dataset_semantic_fingerprint,
    )
    return ResearchInputBinding(
        input_binding_id=new_id(),
        logical_input_role=logical_input_role,
        input_kind=input_kind,
        governed_dataset_id=governed_dataset_id,
        dataset_semantic_fingerprint=dataset_semantic_fingerprint,
        fingerprint=fingerprint,
    )


def research_input_binding_from_market_dataset(
    *, logical_input_role: str, market_dataset: MarketDataset
) -> ResearchInputBinding:
    """The one concrete, implemented `ResearchInputBinding` constructor
    for today's candle world (PID-006A sec10). Binds
    `MarketDataset.dataset_id` (governed identity) and
    `MarketDataset.fingerprint_sha256` (content fingerprint) -- never the
    dataset's candle arrays, and never any filesystem path."""
    return build_research_input_binding(
        logical_input_role=logical_input_role,
        input_kind=ResearchInputKind.MARKET_CANDLE_DATASET,
        governed_dataset_id=market_dataset.dataset_id,
        dataset_semantic_fingerprint=market_dataset.fingerprint_sha256,
    )
