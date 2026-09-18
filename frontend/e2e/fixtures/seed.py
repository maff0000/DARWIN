"""E2E fixture seed — uses the REAL repository classes (the exact path the
real API reads from), not a frontend mock. Deliberately includes a second,
non-XAU instrument (EUR_USD) built directly via the repository — the same
technique the A-001 backend contract tests already use — to prove ARENA's
UI is genuinely instrument-generic, not merely coded to look that way.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

# PID-004B Workshop fixtures below reuse the SAME controlled draft builders
# tests/contract already relies on (tests/fixtures/specification_drafts.py)
# -- never a second, divergent copy of "what a minimal valid draft looks
# like". `tests` is not an installed package (pyproject.toml only packages
# `darwin*`), and this script's own directory (frontend/e2e/fixtures/) is
# what ends up on sys.path[0] when run as `python frontend/e2e/fixtures/
# seed.py` -- so the repo root is added explicitly here, once, before any
# `tests.fixtures...` import below.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

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

    # --- PID-004B Strategy Workshop fixtures -----------------------------
    # Real Workshop state via the real `darwin.workshop.service` functions
    # (the exact path the real API calls) -- never a hand-rolled INSERT
    # bypassing the governed domain model, same discipline as the SCOUT
    # fixtures above.
    from darwin.core.lifecycle import PipelineStage
    from darwin.research_store.models import StrategyCandidate as FoundationStrategyCandidate
    from darwin.research_store.repositories import StrategyCandidateRepository
    from darwin.specification.provenance import RuleOrigin
    from darwin.workshop import service as workshop_service

    candidate_repo = StrategyCandidateRepository(conn)

    # 1) SCOUT flow fixture: only a real, dedicated XAUUSD discovery is
    # seeded here -- the Workshop itself (candidate + workshop) is created
    # LIVE during e2e/workshop.spec.ts's own "Open Workshop" click, through
    # the real POST /api/v1/candidates + POST /api/v1/workshops endpoints
    # (PID-004B directive: "never construct Workshop state client-side").
    # Deliberately its OWN discovery, never one of the discoveries above
    # that e2e/discovery.spec.ts's own mutating-actions block changes --
    # different spec files can run in different Playwright workers
    # concurrently (no `fullyParallel` override forces file-level
    # serialisation), so sharing a row across files would be a real race.
    disc_workshop_scout_flow = make_manual_discovery(
        source_id=source_repo.get_by_key("USER_DISCOVERED")["id"],
        origin_kind=OriginKind.USER_DISCOVERED,
        title="E2E Workshop Source — XAUUSD Session Breakout",
        origin_description="Seeded exclusively for e2e/workshop.spec.ts's real-SCOUT-flow proof",
        origin_url="https://example.invalid/e2e-workshop-source",
        source_symbol="XAUUSD",
        source_timeframe="1h",
        original_description="Break of the prior session's high/low range.",
        pasted_rule_text="IF close > priorSessionHigh THEN buy\nIF close < priorSessionLow THEN sell",
    )
    conn.commit()

    # 2) Controlled COMPLETE fixture: a fully valid draft, ready to
    # finalise live during the test (PID-004B directive scenario 2).
    from tests.fixtures.specification_drafts import minimal_valid_draft
    from darwin.specification.serialization import serialize_specification_draft

    candidate_complete_id = new_id()
    candidate_repo.create(
        FoundationStrategyCandidate(
            id=candidate_complete_id, title="E2E Complete Fixture — Close Above Level",
            pipeline_stage=PipelineStage.DISCOVERED,
        )
    )
    workshop_complete = workshop_service.open_workshop(conn, candidate_id=candidate_complete_id)
    complete_draft = minimal_valid_draft(candidate_id=candidate_complete_id)
    workshop_service.update_draft(
        conn, workshop_complete.workshop_id, expected_revision=0,
        draft_document=serialize_specification_draft(complete_draft),
        schema_semantic_version=complete_draft.schema_semantic_version,
    )
    # A material USER_CLARIFICATION decision, ACCEPTED -- so the Decisions
    # panel/finalisation summary has real provenance to show.
    complete_decision = workshop_service.create_decision(
        conn, workshop_complete.workshop_id,
        proposed_value={"instrument_id": "XAU_USD"}, origin=RuleOrigin.USER_CLARIFICATION,
        actor="matt-fixture", rationale="Confirmed canonical instrument for this fixture.",
    )
    workshop_service.accept_decision(conn, workshop_complete.workshop_id, complete_decision.decision_id)
    conn.commit()

    # 3) Controlled DATA_BLOCKED-shaped fixture (IV-wall pattern, mirrors
    # tests/contract/test_specification_fixtures.py::test_fixture_11_iv_wall_data_blocked):
    # a VALID draft whose mandatory DataRequirements include one HERMES
    # OHLCV requirement (satisfiable) and two OPTIONS_AUTHORITY
    # requirements DARWIN genuinely has no adapter for -- so
    # `assess_workshop_readiness` (darwin/workshop/service.py) will
    # honestly report DATA_BLOCKED after finalisation, never fabricated.
    from decimal import Decimal
    from darwin.specification.composition import AtomicCondition, Direction
    from darwin.specification.data_requirements import (
        DataAuthorityClass, DataRequirement, FactClass, HistoricalDepthRequirement, HistoricalDepthUnit,
    )
    from darwin.specification.expressions import Comparison, ComparisonOperator, Literal
    from darwin.specification.facts import CanonicalFactReference, FactReferenceKind
    from darwin.specification.causal import CausalTimingPolicy
    from darwin.specification.timeframe import Timeframe
    from tests.fixtures.specification_drafts import accepted_provenance, hermes_ohlcv_requirement, simple_atomic_condition

    candidate_blocked_id = new_id()
    candidate_repo.create(
        FoundationStrategyCandidate(
            id=candidate_blocked_id, title="E2E DATA_BLOCKED Fixture — IV Wall Context",
            pipeline_stage=PipelineStage.DISCOVERED,
        )
    )
    workshop_blocked = workshop_service.open_workshop(conn, candidate_id=candidate_blocked_id)

    iv_requirement = DataRequirement(
        requirement_id="xau_iv_surface", display_name="XAU_USD implied volatility surface",
        fact_class=FactClass.IMPLIED_VOLATILITY, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(count=3, unit=HistoricalDepthUnit.YEARS),
        units="IV_PERCENT", required_fields=("strike", "expiry", "implied_volatility"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )
    oi_requirement = DataRequirement(
        requirement_id="xau_open_interest", display_name="XAU_USD options open interest",
        fact_class=FactClass.OPEN_INTEREST, fact_reference_kind=FactReferenceKind.CANONICAL_FACT_REFERENCE,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, instrument_applicability=("XAU_USD",),
        timeframe=Timeframe("D1"), required_historical_depth=HistoricalDepthRequirement(count=3, unit=HistoricalDepthUnit.YEARS),
        units="CONTRACTS", required_fields=("strike", "expiry", "open_interest"),
        causal_timing_policy=CausalTimingPolicy.NOT_APPLICABLE,
    )
    iv_wall_fact = CanonicalFactReference(
        fact_key="OPTIONS.IMPLIED_VOLATILITY", fact_class=FactClass.IMPLIED_VOLATILITY,
        authority_class=DataAuthorityClass.OPTIONS_AUTHORITY, unit="IV_PERCENT", timeframe=Timeframe("D1"),
        requirement_id="xau_iv_surface",
    )
    wall_exit = AtomicCondition(
        condition_id="iv_wall_context", semantic_role="CONTEXT", timeframe=Timeframe("D1"),
        expression=Comparison(operator=ComparisonOperator.GT, left=iv_wall_fact, right=Literal(Decimal(0), unit="IV_PERCENT")),
        direction=Direction.BOTH,
    )
    trigger = simple_atomic_condition("price_approaches_iv_wall", threshold="4000")
    blocked_draft = minimal_valid_draft(
        draft_id="e2e-iv-wall-draft", candidate_id=candidate_blocked_id, composition=trigger,
    )
    blocked_draft.exit_rules = (wall_exit,)
    blocked_draft.set_data_requirement(hermes_ohlcv_requirement(timeframe="H1"))
    blocked_draft.set_data_requirement(iv_requirement)
    blocked_draft.set_data_requirement(oi_requirement)
    blocked_draft.set_provenance(accepted_provenance("iv_wall_context"))
    workshop_service.update_draft(
        conn, workshop_blocked.workshop_id, expected_revision=0,
        draft_document=serialize_specification_draft(blocked_draft),
        schema_semantic_version=blocked_draft.schema_semantic_version,
    )
    conn.commit()

    # 4) Stale-edit fixture: an ACTIVE Workshop with a real draft at
    # revision 1 -- two Playwright browser contexts both load this SAME
    # revision, one saves, the other's save must be refused as stale
    # (PID-004B directive scenario 4).
    candidate_stale_id = new_id()
    candidate_repo.create(
        FoundationStrategyCandidate(
            id=candidate_stale_id, title="E2E Stale-Edit Fixture", pipeline_stage=PipelineStage.DISCOVERED,
        )
    )
    workshop_stale = workshop_service.open_workshop(conn, candidate_id=candidate_stale_id)
    stale_draft = minimal_valid_draft(candidate_id=candidate_stale_id)
    workshop_service.update_draft(
        conn, workshop_stale.workshop_id, expected_revision=0,
        draft_document=serialize_specification_draft(stale_draft),
        schema_semantic_version=stale_draft.schema_semantic_version,
    )
    conn.commit()

    # 5) PID-004C WP3 MENDEL fixture: a dedicated ACTIVE Workshop with a
    # real, validation-clean draft at revision 1 -- e2e/mendel.spec.ts's
    # own Workshop, never shared with any of the fixtures above (same
    # "no cross-file row sharing" discipline this script's own comments
    # already establish for scenario 1's dedicated discovery). The real
    # MENDEL invocation itself happens LIVE during the test, through the
    # real UI + the real POST .../mendel/invoke endpoint -- this only
    # seeds the Workshop/draft the test opens (PID-004B/PID-004C
    # directive: never construct Workshop/MENDEL state client-side).
    candidate_mendel_id = new_id()
    candidate_repo.create(
        FoundationStrategyCandidate(
            id=candidate_mendel_id, title="E2E MENDEL Fixture — Session Breakout",
            pipeline_stage=PipelineStage.DISCOVERED,
        )
    )
    workshop_mendel = workshop_service.open_workshop(conn, candidate_id=candidate_mendel_id)
    mendel_draft = minimal_valid_draft(candidate_id=candidate_mendel_id)
    workshop_service.update_draft(
        conn, workshop_mendel.workshop_id, expected_revision=0,
        draft_document=serialize_specification_draft(mendel_draft),
        schema_semantic_version=mendel_draft.schema_semantic_version,
    )
    conn.commit()

_OUTPUT = {
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
    "workshop_fixture_ids": {
        "scout_flow_discovery_id": disc_workshop_scout_flow.id,
        "complete_candidate_id": candidate_complete_id,
        "complete_workshop_id": workshop_complete.workshop_id,
        "data_blocked_candidate_id": candidate_blocked_id,
        "data_blocked_workshop_id": workshop_blocked.workshop_id,
        "stale_edit_candidate_id": candidate_stale_id,
        "stale_edit_workshop_id": workshop_stale.workshop_id,
        "mendel_candidate_id": candidate_mendel_id,
        "mendel_workshop_id": workshop_mendel.workshop_id,
    },
}
print(json.dumps(_OUTPUT))

# Also written to a fixed, well-known file (in addition to stdout) so CI
# steps AFTER this one -- which run natively on the runner, not inside this
# throwaway container, and whose own stdout capture would otherwise be
# mixed with pip/darwin-migrate log noise -- can cleanly read these ids
# (e.g. to target a specific seeded Workshop for the workspace-loss E2E
# proof) without re-parsing this script's combined console output.
(_REPO_ROOT / "frontend" / "e2e" / "fixtures" / ".seed_output.json").write_text(json.dumps(_OUTPUT, indent=2))
