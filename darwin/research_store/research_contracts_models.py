"""Plain persisted records for the PID-006A research-contracts tables
(migration 0012) -- mirrors the existing `darwin.research_store.models`
discipline exactly ("Plain domain records for DARWIN_sql -- no ORM
session leakage into business logic"): these are row-shaped, JSON-safe
dataclasses, deliberately distinct from the richer runtime dataclasses in
`darwin.research_contracts` (`ExecutableStrategyPlan`, `ParameterSetVersion`,
`ExecutionPolicyVersion`, `ResearchPartitionPolicyVersion`,
`ResearchConfiguration`) -- the same "persisted metadata record vs rich
in-memory object" split `MarketDatasetRecord` already draws against
`darwin.hermes.dataset.MarketDataset`.

`darwin.research_store.research_contracts_repositories` is the only place
that translates between these records and Postgres rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CompiledStrategyPlanRecord:
    id: str
    source_strategy_version_id: str
    source_semantic_fingerprint: str
    compiler_id: str
    compiler_version: str
    plan_schema_version: str
    semantic_payload: dict
    fingerprint: str
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class ParameterSetVersionRecord:
    id: str
    source_strategy_version_id: str
    source_semantic_fingerprint: str
    assignments: list = field(default_factory=list)
    fingerprint: str = ""
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class ExecutionPolicyVersionRecord:
    id: str
    timing_methodology: dict
    price_fill_methodology: dict
    intrabar_resolution_methodology: dict
    cost_methodology: dict
    quantity_economic_methodology: dict
    session_force_flat_methodology: dict
    fingerprint: str
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class ResearchPartitionPolicyVersionRecord:
    id: str
    role: str
    input_binding: dict
    fingerprint: str
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class ResearchConfigurationRecord:
    id: str
    configuration_schema_version: str
    strategy_semantic_fingerprint: str
    executable_strategy_plan_fingerprint: str
    parameter_set_fingerprint: str
    instrument_definition_id: str
    instrument_definition_fingerprint: str
    research_input_bindings: list
    research_partition_policy_fingerprint: str
    execution_policy_fingerprint: str
    dike_state: str
    dike_policy_fingerprint: str | None
    required_derived_algorithm_identities: list
    fingerprint: str
    created_at_utc: datetime | None = None
