"""Plain domain records for DARWIN_sql — no ORM session leakage into business
logic (PID-001 §26). Repositories translate to/from these explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

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
    """Persisted MarketDataset metadata/fingerprint — never candle rows themselves."""

    id: str
    instrument: str
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
    id: str
    result_kind: EvidenceLevel
    engine: str
    build_version: str
    status: str
    candidate_id: str | None = None
    version_id: str | None = None
    dataset_id: str | None = None
    configuration_fingerprint: str | None = None
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    run_id: str
    evidence_level: EvidenceLevel
    reference: str
    created_at_utc: datetime | None = None
