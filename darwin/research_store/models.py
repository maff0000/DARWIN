"""Plain domain records for DARWIN_sql — no ORM session leakage into business
logic (PID-001 §26). Repositories translate to/from these explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from darwin.core.dike import DikeState
from darwin.core.evidence import EvidenceLevel
from darwin.core.lifecycle import PipelineStage


@dataclass(frozen=True)
class SourceStrategy:
    id: str
    source_type: str
    source_reference: str
    title: str
    provenance: dict = field(default_factory=dict)
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


@dataclass(frozen=True)
class StrategyCandidate:
    id: str
    title: str
    source_strategy_id: str | None = None
    pipeline_stage: PipelineStage = PipelineStage.DISCOVERED
    # PID-004B Workshop UI enablement (migration 0010): the SCOUT
    # scout_discoveries.id this candidate originated from, if any -- optional,
    # since a candidate may still originate with no discovery (PID-004
    # sec4.2: "a later combination/derivation of candidates; another
    # governed source"). See StrategyCandidateRepository.get_or_create_for_discovery
    # for the idempotent-per-discovery creation path this backs.
    origin_discovery_id: str | None = None
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


@dataclass(frozen=True)
class StrategyVersion:
    id: str
    candidate_id: str
    version_label: str
    specification_fingerprint: str | None = None
    is_immutable: bool = True
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class MarketDatasetRecord:
    """Persisted MarketDataset metadata/fingerprint — never candle rows themselves.

    `instrument_definition_id` (Amendment A-002) is the InstrumentDefinition
    identity under which this dataset's prices are interpreted -- see
    darwin.hermes.instrument_definition.
    """

    id: str
    instrument: str
    instrument_definition_id: str
    timeframe: str
    requested_start_utc: datetime
    requested_end_utc: datetime
    actual_first_open_utc: datetime | None
    actual_last_open_utc: datetime | None
    record_count: int
    fingerprint_sha256: str
    hermes_contract_version: str
    hermes_contract_commit: str
    adapter_build_version: str
    gap_summary: dict
    loaded_at_utc: datetime
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class ResearchRun:
    """The concrete test instance (Amendment A-001, PID-001 §1a): a
    StrategyCandidate/StrategyVersion tested against one InstrumentId +
    Timeframe + MarketDataset. instrument/timeframe/display_title are
    explicit durable facts here, not only reachable via a join to
    market_datasets -- see darwin.research_store.run_binding.create_research_run,
    which is the only supported way to construct one (it enforces the
    instrument/timeframe agreement with the bound dataset).

    `instrument_definition_id` (Amendment A-002, PID-001 §1b) is inherited
    from the bound MarketDataset -- historical evidence must always be able
    to answer what an instrument's price meant when the run was executed,
    even if InstrumentDefinition is redefined later.

    `dike_state`/`dike_policy_id`/`dike_policy_version`/`dike_policy_fingerprint`
    (Amendment A-003, PID-001 §1d) are identity binding only -- Foundation
    never evaluates or enforces a DIKE policy. DIKE_DISABLED must carry no
    policy identity; DIKE_GUARDED must carry all three -- no null/absence
    ambiguity, enforced in darwin.research_store.run_binding.create_research_run.
    """

    id: str
    result_kind: EvidenceLevel
    engine: str
    build_version: str
    status: str
    instrument: str
    instrument_definition_id: str
    timeframe: str
    display_title: str
    candidate_id: str | None = None
    version_id: str | None = None
    dataset_id: str | None = None
    configuration_fingerprint: str | None = None
    dike_state: DikeState = DikeState.DISABLED
    dike_policy_id: str | None = None
    dike_policy_version: str | None = None
    dike_policy_fingerprint: str | None = None
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    run_id: str
    evidence_level: EvidenceLevel
    reference: str
    created_at_utc: datetime | None = None
