"""E2E fixture seed — uses the REAL repository classes (the exact path the
real API reads from), not a frontend mock. Deliberately includes a second,
non-XAU instrument (EUR_USD) built directly via the repository — the same
technique the A-001 backend contract tests already use — to prove ARENA's
UI is genuinely instrument-generic, not merely coded to look that way.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from darwin.core.dike import DikeState
from darwin.core.evidence import EvidenceLevel
from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.models import MarketDatasetRecord, ResearchRun
from darwin.research_store.repositories import MarketDatasetRepository, ResearchRunRepository
from darwin.research_store.run_binding import build_run_title

from darwin.core.config import DarwinConfig

cfg = DarwinConfig.load()

XAU_DEF_ID = "99287b05c6b9478eb1185bfcd32121431254903e79ccd736410d509034cf51b6"
EUR_DEF_ID = "e2e-synthetic-eur-usd-definition-fixture-only"

xau_dataset = MarketDatasetRecord(
    id=new_id(),
    instrument="XAU_USD",
    instrument_definition_id=XAU_DEF_ID,
    timeframe="H1",
    requested_start_utc=datetime(2026, 9, 1, tzinfo=UTC),
    requested_end_utc=datetime(2026, 9, 2, tzinfo=UTC),
    actual_first_open_utc=datetime(2026, 9, 1, 0, tzinfo=UTC),
    actual_last_open_utc=datetime(2026, 9, 1, 23, tzinfo=UTC),
    record_count=24,
    fingerprint_sha256="e2e" + "0" * 61,
    hermes_contract_version="v1",
    hermes_contract_commit="3f90e640c9c9c1f4a22ba4ac586a1d478f35a997",
    adapter_build_version="0.1.0",
    gap_summary={"missing": 0},
    loaded_at_utc=datetime.now(UTC),
)

eur_dataset = MarketDatasetRecord(
    id=new_id(),
    instrument="EUR_USD",
    instrument_definition_id=EUR_DEF_ID,
    timeframe="M15",
    requested_start_utc=datetime(2026, 9, 1, tzinfo=UTC),
    requested_end_utc=datetime(2026, 9, 1, 6, tzinfo=UTC),
    actual_first_open_utc=datetime(2026, 9, 1, 0, tzinfo=UTC),
    actual_last_open_utc=datetime(2026, 9, 1, 5, 45, tzinfo=UTC),
    record_count=24,
    fingerprint_sha256="e2e" + "1" * 61,
    hermes_contract_version="v1",
    hermes_contract_commit="3f90e640c9c9c1f4a22ba4ac586a1d478f35a997",
    adapter_build_version="0.1.0",
    gap_summary={"missing": 0, "note": "synthetic E2E fixture, not a real HERMES load"},
    loaded_at_utc=datetime.now(UTC),
)

with connection(cfg.postgres) as conn:
    MarketDatasetRepository(conn).create(xau_dataset)
    MarketDatasetRepository(conn).create(eur_dataset)
    conn.commit()

    runs = [
        ResearchRun(
            id=new_id(),
            result_kind=EvidenceLevel.SOURCE_CLAIM,
            engine="scout-fixture",
            build_version="0.1.0",
            status="RECORDED",
            instrument="XAU_USD",
            instrument_definition_id=XAU_DEF_ID,
            timeframe="H1",
            display_title=build_run_title(
                instrument="XAU_USD", timeframe="H1", run_type="SOURCE_CLAIM",
                strategy_title="External London Breakout claim",
            ),
            dike_state=DikeState.DISABLED,
        ),
        ResearchRun(
            id=new_id(),
            result_kind=EvidenceLevel.ATHENA_RESULT,
            engine="athena-fixture",
            build_version="0.1.0",
            status="COMPLETED",
            instrument="XAU_USD",
            instrument_definition_id=XAU_DEF_ID,
            timeframe="H1",
            display_title=build_run_title(
                instrument="XAU_USD", timeframe="H1", run_type="ATHENA",
                strategy_title="London Breakout", version_label="v1",
            ),
            dataset_id=xau_dataset.id,
            dike_state=DikeState.DISABLED,
        ),
        ResearchRun(
            id=new_id(),
            result_kind=EvidenceLevel.APOLLO_PROOF,
            engine="apollo-fixture",
            build_version="0.1.0",
            status="PROVEN",
            instrument="XAU_USD",
            instrument_definition_id=XAU_DEF_ID,
            timeframe="H1",
            display_title=build_run_title(
                instrument="XAU_USD", timeframe="H1", run_type="APOLLO",
                strategy_title="London Breakout", version_label="v1",
            ),
            dataset_id=xau_dataset.id,
            dike_state=DikeState.GUARDED,
            dike_policy_id="e2e-synthetic-conservative-policy",
            dike_policy_version="v0-e2e",
            dike_policy_fingerprint="e2e" + "2" * 61,
        ),
        ResearchRun(
            id=new_id(),
            result_kind=EvidenceLevel.ATHENA_RESULT,
            engine="athena-fixture",
            build_version="0.1.0",
            status="COMPLETED",
            instrument="EUR_USD",
            instrument_definition_id=EUR_DEF_ID,
            timeframe="M15",
            display_title=build_run_title(
                instrument="EUR_USD", timeframe="M15", run_type="ATHENA",
                strategy_title="Mean Reversion", version_label="v7",
            ),
            dataset_id=eur_dataset.id,
            dike_state=DikeState.DISABLED,
        ),
    ]
    repo = ResearchRunRepository(conn)
    for r in runs:
        repo.create(r)
    conn.commit()

print(json.dumps({
    "seeded": True,
    "xau_dataset_id": xau_dataset.id,
    "eur_dataset_id": eur_dataset.id,
    "run_ids": [r.id for r in runs],
}))
