"""E2E fixture seed — uses the REAL repository classes (the exact path the
real API reads from), not a frontend mock. Deliberately includes a second,
non-XAU instrument (EUR_USD) built directly via the repository — the same
technique the A-001 backend contract tests already use — to prove ARENA's
UI is genuinely instrument-generic, not merely coded to look that way.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

from darwin.core.dike import DikeState
from darwin.core.evidence import EvidenceLevel
from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.models import MarketDatasetRecord, ResearchRun
from darwin.research_store.repositories import (
    MarketDatasetRepository,
    ResearchRunRepository,
    ScoutClaimRepository,
    ScoutDiscoveryRepository,
    ScoutDiscoveryRunRepository,
    ScoutSnapshotRepository,
    ScoutSourceRepository,
)
from darwin.research_store.run_binding import build_run_title
from darwin.scout.domain import (
    DiscoveryRun,
    DiscoveryRunStatus,
    IntakeStatus,
    OriginKind,
    RuleAvailability,
    SourceClaim,
    SourceDiscovery,
    SourceSnapshot,
    build_claim_values,
    build_manual_discovery,
    compute_snapshot_fingerprint,
)

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

    # --- PID-003 SCOUT fixtures -----------------------------------------
    # Real rows via the real repository/domain classes (same discipline as
    # the datasets/runs fixtures above) -- never a frontend mock. Covers:
    # an ADAPTER_SOURCED discovery left NEW (for the live shortlist E2E
    # action), one with a thin claimed trade sample, one with NO claim at
    # all (honest missing-metric rendering), a USER_DISCOVERED entry walked
    # through real intake transitions to READY_FOR_SPECIFICATION, a MY_IDEA
    # entry with no external source/metrics at all, and a REJECTED entry --
    # exercising all five intake states and all three origin kinds.
    discovery_repo = ScoutDiscoveryRepository(conn)
    snapshot_repo = ScoutSnapshotRepository(conn)
    claim_repo = ScoutClaimRepository(conn)
    source_repo = ScoutSourceRepository(conn)
    run_repo = ScoutDiscoveryRunRepository(conn)
    now = datetime.now(UTC)

    def make_adapter_discovery(
        *, title, source_strategy_id, symbol, timeframe, metrics, rule_availability
    ):
        """Mirrors darwin.scout.service._ingest_record's construction for an
        ADAPTER_SOURCED record — the only origin kind build_manual_discovery
        does not cover."""
        source = source_repo.get_by_key("TRADER_DEV_PUBLIC")
        discovery = SourceDiscovery(
            id=new_id(),
            source_id=source["id"],
            origin_kind=OriginKind.ADAPTER_SOURCED,
            title=title,
            source_strategy_id=source_strategy_id,
            source_symbol=symbol,
            source_timeframe=timeframe,
            first_seen_utc=now,
            last_seen_utc=now,
        )
        claim_values = build_claim_values(metrics or {})
        fingerprint = compute_snapshot_fingerprint(discovery_id=discovery.id, claim_payload=claim_values)
        snapshot = SourceSnapshot(
            id=new_id(),
            discovery_id=discovery.id,
            source_id=source["id"],
            source_record_id=source_strategy_id,
            extraction_utc=now,
            adapter_name="trader_dev_public_adapter",
            adapter_version="v1",
            rule_availability=rule_availability,
            fingerprint_sha256=fingerprint,
            source_url=f"https://mcp-api.trader.dev/strategy/{source_strategy_id}",
            source_symbol=symbol,
            source_timeframe=timeframe,
            raw_metadata={"e2e_fixture": True},
        )
        claim = (
            SourceClaim(id=new_id(), snapshot_id=snapshot.id, discovery_id=discovery.id, extraction_utc=now, **claim_values)
            if metrics
            else None
        )
        # Insert order respects the FK from scout_discoveries.last_snapshot_id
        # -> scout_snapshots(id) (migration 0005): bare discovery first, then
        # snapshot/claim, then record_extraction_seen sets the forward
        # reference -- same ordering darwin.scout.service uses.
        discovery_repo.create(discovery)
        snapshot_repo.create(snapshot)
        if claim is not None:
            claim_repo.create(claim)
        discovery_repo.record_extraction_seen(
            discovery.id,
            last_seen_utc=now,
            new_snapshot_id=snapshot.id,
            latest_rule_availability=rule_availability.value,
            source_symbol=symbol,
            source_timeframe=timeframe,
        )
        return discovery

    def make_manual_discovery(**kwargs):
        discovery, snapshot, claim = build_manual_discovery(now=now, **kwargs)
        bare = replace(discovery, last_snapshot_id=None, latest_rule_availability=None)
        discovery_repo.create(bare)
        if snapshot is not None:
            snapshot_repo.create(snapshot)
        if claim is not None:
            claim_repo.create(claim)
        if snapshot is not None:
            discovery_repo.record_extraction_seen(
                discovery.id,
                last_seen_utc=now,
                new_snapshot_id=snapshot.id,
                latest_rule_availability=(
                    discovery.latest_rule_availability.value if discovery.latest_rule_availability else None
                ),
                source_symbol=discovery.source_symbol,
                source_timeframe=discovery.source_timeframe,
            )
        return discovery

    disc_new = make_adapter_discovery(
        title="XAUUSD London Session Breakout",
        source_strategy_id="e2e-trader-dev-001",
        symbol="XAUUSD",
        timeframe="1h",
        metrics={
            "net_pnl_percent": "42.50", "max_drawdown_percent": "18.30", "win_rate_percent": "55.00",
            "profit_factor": "1.80", "trade_count": 340, "sharpe": "1.20", "sortino": "1.60",
        },
        rule_availability=RuleAvailability.ACCESS_RESTRICTED,
    )  # left NEW — the live "shortlist" E2E action targets this one

    disc_shortlisted = make_adapter_discovery(
        title="Gold Momentum Scalper",
        source_strategy_id="e2e-trader-dev-002",
        symbol="XAUUSD",
        timeframe="15m",
        metrics={
            "net_pnl_percent": "120.00", "max_drawdown_percent": "45.00", "win_rate_percent": "38.00",
            "profit_factor": "1.10", "trade_count": 15, "sharpe": "0.40", "sortino": "0.50",
        },
        rule_availability=RuleAvailability.ACCESS_RESTRICTED,
    )  # trade_count=15 < the UI's 30-trade low-sample threshold, deliberately

    disc_no_metrics = make_adapter_discovery(
        title="Unlabeled EA Import",
        source_strategy_id="e2e-trader-dev-003",
        symbol="XAUUSD",
        timeframe="4h",
        metrics=None,
        rule_availability=RuleAvailability.UNAVAILABLE,
    )  # no claim row at all — proves the UI never fabricates a metric

    disc_user = make_manual_discovery(
        source_id=source_repo.get_by_key("USER_DISCOVERED")["id"],
        origin_kind=OriginKind.USER_DISCOVERED,
        title="London Range Break (Reddit)",
        origin_description="Reddit r/algotrading post",
        origin_url="https://www.reddit.com/r/algotrading/e2e_fixture_example",
        source_symbol="XAUUSD",
        source_timeframe="1h",
        original_description="Trade the London open range break with 1% risk per trade.",
        pasted_rule_text="IF close > londonRangeHigh THEN buy\nIF close < londonRangeLow THEN sell",
        personal_notes="Found during Matt's Sunday research pass — worth a look.",
        tags=("breakout", "session"),
        claimed_metrics={"net_pnl_percent": "30", "max_drawdown_percent": "12", "trade_count": 80, "profit_factor": "2.1"},
    )

    disc_my_idea = make_manual_discovery(
        source_id=source_repo.get_by_key("MY_IDEA")["id"],
        origin_kind=OriginKind.MY_IDEA,
        title="VWAP Reversion Idea",
        personal_notes="Matt's own hypothesis: fade extreme VWAP deviation intraday.",
        tags=("my-idea", "vwap"),
    )

    disc_rejected = make_manual_discovery(
        source_id=source_repo.get_by_key("MY_IDEA")["id"],
        origin_kind=OriginKind.MY_IDEA,
        title="Fib Cluster Reversal Idea (superseded)",
        personal_notes="An earlier idea, superseded by the VWAP reversion idea above.",
    )
    conn.commit()

    # Real, validated intake-status transitions (darwin.research_store
    # .repositories.ScoutDiscoveryRepository.set_intake_status) — builds a
    # genuine audit trail exactly the way ARENA's own controls will,
    # exercising SHORTLISTED, IN_WORKSHOP, READY_FOR_SPECIFICATION and
    # REJECTED (disc_new/disc_no_metrics stay NEW).
    discovery_repo.set_intake_status(disc_shortlisted.id, IntakeStatus.SHORTLISTED, changed_by="matt-fixture", reason="High claimed PF, worth a look")

    discovery_repo.set_intake_status(disc_user.id, IntakeStatus.SHORTLISTED, changed_by="matt-fixture", reason="Clear rules, plausible claim")
    discovery_repo.set_intake_status(disc_user.id, IntakeStatus.IN_WORKSHOP, changed_by="matt-fixture", reason="Starting specification prep")
    discovery_repo.set_intake_status(disc_user.id, IntakeStatus.READY_FOR_SPECIFICATION, changed_by="matt-fixture", reason="Ambiguities resolved enough to specify")

    discovery_repo.set_intake_status(disc_my_idea.id, IntakeStatus.SHORTLISTED, changed_by="matt-fixture", reason="Worth prototyping")
    discovery_repo.set_intake_status(disc_my_idea.id, IntakeStatus.IN_WORKSHOP, changed_by="matt-fixture", reason="Moved into workshop triage")

    discovery_repo.set_intake_status(disc_rejected.id, IntakeStatus.SHORTLISTED, changed_by="matt-fixture", reason="Initial triage")
    discovery_repo.set_intake_status(disc_rejected.id, IntakeStatus.REJECTED, changed_by="matt-fixture", reason="Superseded by the VWAP reversion idea")
    conn.commit()

    # A completed DiscoveryRun so /scout/status.last_discovery_run and
    # /scout/discovery-runs have real data to render, not just null.
    trader_dev_source = source_repo.get_by_key("TRADER_DEV_PUBLIC")
    discovery_run = DiscoveryRun(
        id=new_id(),
        source_id=trader_dev_source["id"],
        adapter_name="trader_dev_public_adapter",
        adapter_version="v1",
        started_at_utc=now,
        status=DiscoveryRunStatus.SUCCEEDED,
        requested_filter={"symbol": "XAUUSD", "max_records": 3, "sort": "recent"},
        completed_at_utc=now,
        records_observed=3,
        records_accepted=3,
        records_unchanged=0,
        records_changed=0,
        records_rejected=0,
    )
    run_repo.create(discovery_run)
    conn.commit()

print(json.dumps({
    "seeded": True,
    "xau_dataset_id": xau_dataset.id,
    "eur_dataset_id": eur_dataset.id,
    "run_ids": [r.id for r in runs],
    "scout_discovery_ids": {
        "new": disc_new.id,
        "shortlisted": disc_shortlisted.id,
        "no_metrics": disc_no_metrics.id,
        "user_discovered": disc_user.id,
        "my_idea": disc_my_idea.id,
        "rejected": disc_rejected.id,
    },
}))
