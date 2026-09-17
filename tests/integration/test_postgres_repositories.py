"""Integration tests against a real, disposable PostgreSQL (PID-001 §28).
Skipped automatically unless DARWIN_TEST_PG_DSN is set — never a CI dependency
on live HERMES, and this file never touches HERMES at all.
"""
from datetime import UTC, datetime

import pytest

from darwin.core.evidence import EvidenceLevel
from darwin.core.identities import new_id
from darwin.core.lifecycle import PipelineStage
from darwin.research_store.db import connection
from darwin.research_store.models import (
    MarketDatasetRecord,
    SourceStrategy,
    StrategyCandidate,
)
from darwin.research_store.repositories import (
    MarketDatasetRepository,
    ResearchRunRepository,
    SourceStrategyRepository,
    StrategyCandidateRepository,
)
from darwin.research_store.run_binding import create_research_run

pytestmark = pytest.mark.integration


def test_migrations_applied_cleanly(pg_config):
    from darwin.research_store.migrations import migration_state
    from tests.integration.conftest import MIGRATIONS_DIR

    state = migration_state(pg_config, MIGRATIONS_DIR)
    assert state["up_to_date"] is True
    assert "0001_foundation" in state["applied"]


def test_source_strategy_roundtrip(pg_config):
    with connection(pg_config) as conn:
        repo = SourceStrategyRepository(conn)
        before = repo.count()
        repo.create(
            SourceStrategy(
                id=new_id(), source_type="TRADER_DEV", source_reference="https://example.invalid/s/1",
                title="Example source strategy",
            )
        )
        assert repo.count() == before + 1


def test_candidate_pipeline_stage_counts(pg_config):
    with connection(pg_config) as conn:
        repo = StrategyCandidateRepository(conn)
        before = repo.counts_by_stage()
        repo.create(StrategyCandidate(id=new_id(), title="Candidate A", pipeline_stage=PipelineStage.DISCOVERED))
        after = repo.counts_by_stage()
        assert after[PipelineStage.DISCOVERED.value] == before[PipelineStage.DISCOVERED.value] + 1


def test_market_dataset_metadata_persists_and_reads_back(pg_config):
    with connection(pg_config) as conn:
        repo = MarketDatasetRepository(conn)
        dataset_id = new_id()
        record = MarketDatasetRecord(
            id=dataset_id,
            instrument="XAU_USD",
            timeframe="H1",
            requested_start_utc=datetime(2026, 9, 16, 15, tzinfo=UTC),
            requested_end_utc=datetime(2026, 9, 16, 18, tzinfo=UTC),
            actual_first_open_utc=datetime(2026, 9, 16, 15, tzinfo=UTC),
            actual_last_open_utc=datetime(2026, 9, 16, 17, tzinfo=UTC),
            record_count=3,
            fingerprint_sha256="a" * 64,
            hermes_contract_version="v1",
            hermes_contract_commit="3f90e640c9c9c1f4a22ba4ac586a1d478f35a997",
            adapter_build_version="test",
            gap_summary={"expected_count": 3, "actual_count": 3, "missing_count": 0,
                         "missing_open_times_utc": [], "truncated": False},
            loaded_at_utc=datetime.now(UTC),
        )
        repo.create(record)
        fetched = repo.get(dataset_id)
        assert fetched is not None
        assert fetched["fingerprint_sha256"] == "a" * 64
        assert fetched["record_count"] == 3
        # Never a duplicate of HERMES candle history — no per-candle columns exist here.
        assert "high" not in fetched and "close" not in fetched


def test_research_run_lifecycle(pg_config):
    with connection(pg_config) as conn:
        repo = ResearchRunRepository(conn)
        run = create_research_run(
            result_kind=EvidenceLevel.ATHENA_RESULT, engine="foundation-proof",
            build_version="test", status="RUNNING", instrument="XAU_USD", timeframe="H1",
            run_type="ATHENA", strategy_title="Foundation proof strategy", version_label="v1",
        )
        repo.create(run)
        repo.update_status(run.id, "COMPLETE")
        fetched = repo.get(run.id)
        assert fetched["status"] == "COMPLETE"
        assert fetched["result_kind"] == "ATHENA_RESULT"


def test_research_run_instrument_timeframe_title_persist_and_read_back(pg_config):
    """Amendment A-001 item D: run/API representation (this is exactly the dict
    darwin.app's /runs and /runs/{id} return -- SELECT * FROM research_runs) must
    contain instrument, timeframe, result kind, and the human-readable title.
    """
    with connection(pg_config) as conn:
        repo = ResearchRunRepository(conn)
        run = create_research_run(
            result_kind=EvidenceLevel.APOLLO_PROOF, engine="apollo-proof", build_version="test",
            status="COMPLETE", instrument="EUR_USD", timeframe="M15", run_type="APOLLO",
            strategy_title="Mean Reversion", version_label="v7",
        )
        repo.create(run)
        fetched = repo.get(run.id)
        assert fetched["instrument"] == "EUR_USD"
        assert fetched["timeframe"] == "M15"
        assert fetched["result_kind"] == "APOLLO_PROOF"
        assert fetched["display_title"] == "<EUR_USD · M15> Mean Reversion v7 — APOLLO"
