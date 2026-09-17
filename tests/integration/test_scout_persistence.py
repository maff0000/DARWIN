"""PID-003 SCOUT integration tests against a real, disposable PostgreSQL
(PID-001 §28 discipline). Skipped automatically unless DARWIN_TEST_PG_DSN is
set -- same pattern as tests/integration/test_postgres_repositories.py.
"""
from __future__ import annotations

from datetime import UTC, datetime

import httpx
import psycopg
import pytest

from darwin.research_store.db import connection
from darwin.research_store.repositories import (
    ScoutClaimRepository,
    ScoutDiscoveryRepository,
    ScoutDiscoveryRunRepository,
    ScoutSnapshotRepository,
    ScoutSourceRepository,
)
from darwin.scout import service as scout_service
from darwin.scout.domain import (
    FamilyResolution,
    IntakeStatus,
    InvalidIntakeTransitionError,
    OriginKind,
    RuleAvailability,
)
from darwin.scout.trader_dev_adapter import NormalizedRecord, TraderDevAdapter

pytestmark = pytest.mark.integration


def _record(
    *, source_strategy_id: str, result_id: str, symbol: str = "XAUUSD", timeframe: str = "60",
    net_pnl_percent: float = 10.0, forked_from: str | None = None,
) -> NormalizedRecord:
    return NormalizedRecord(
        source_strategy_id=source_strategy_id, result_id=result_id, name="Test strategy",
        symbol=symbol, timeframe=timeframe, forked_from_source_strategy_id=forked_from,
        strategy_updated_at_utc=datetime.now(UTC), view_url=f"https://mcp-api.trader.dev/backtest/{result_id}",
        claim_payload={"net_pnl_percent": net_pnl_percent, "trade_count": 100},
        rule_availability=RuleAvailability.ACCESS_RESTRICTED,
        raw_metadata={"search_hit": {"id": source_strategy_id}, "backtest_result_detail": {"id": result_id}},
    )


# --- migration seed data ------------------------------------------------------

def test_migration_seeds_exactly_the_three_governed_sources(pg_config):
    with connection(pg_config) as conn:
        sources = ScoutSourceRepository(conn).list()
    keys = {s["source_key"] for s in sources}
    assert keys == {"TRADER_DEV_PUBLIC", "USER_DISCOVERED", "MY_IDEA"}
    by_key = {s["source_key"]: s for s in sources}
    assert by_key["TRADER_DEV_PUBLIC"]["origin_kind"] == "ADAPTER_SOURCED"
    assert by_key["TRADER_DEV_PUBLIC"]["base_url"] == "https://mcp-api.trader.dev"
    assert by_key["MY_IDEA"]["base_url"] is None
    assert by_key["USER_DISCOVERED"]["adapter_name"] is None


# --- adapter-sourced ingest: dedup / idempotency / changed-snapshot ----------

def test_first_ingest_creates_a_new_discovery_and_snapshot(pg_config):
    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        record = _record(source_strategy_id="strat-first-" + str(datetime.now(UTC).timestamp()), result_id="res-1")
        outcome = scout_service._ingest_record(conn, source_id=source_id, record=record)
        conn.commit()
        assert outcome == "accepted"
        discovery = ScoutDiscoveryRepository(conn).get_by_source_identity(source_id, record.source_strategy_id)
        assert discovery is not None
        assert discovery["origin_kind"] == "ADAPTER_SOURCED"
        assert discovery["source_symbol"] == "XAUUSD"
        assert discovery["first_seen_utc"] is not None
        assert discovery["last_seen_utc"] is not None
        snapshots = ScoutSnapshotRepository(conn).list_for_discovery(discovery["id"])
        assert len(snapshots) == 1


def test_identical_repeated_extraction_is_idempotent_no_second_snapshot(pg_config):
    strategy_id = "strat-idempotent-" + str(datetime.now(UTC).timestamp())
    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        record = _record(source_strategy_id=strategy_id, result_id="res-idem-1")
        scout_service._ingest_record(conn, source_id=source_id, record=record)
        conn.commit()
        discovery = ScoutDiscoveryRepository(conn).get_by_source_identity(source_id, strategy_id)
        first_last_seen = discovery["last_seen_utc"]

        outcome = scout_service._ingest_record(conn, source_id=source_id, record=record)
        conn.commit()
        assert outcome == "unchanged"

        snapshots = ScoutSnapshotRepository(conn).list_for_discovery(discovery["id"])
        assert len(snapshots) == 1  # still exactly one -- no duplicate row

        refreshed = ScoutDiscoveryRepository(conn).get(discovery["id"])
        assert refreshed["last_seen_utc"] >= first_last_seen  # last_seen still advances


def test_changed_metric_creates_new_snapshot_old_remains_readable(pg_config):
    strategy_id = "strat-changed-" + str(datetime.now(UTC).timestamp())
    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        first = _record(source_strategy_id=strategy_id, result_id="res-changed-1", net_pnl_percent=10.0)
        scout_service._ingest_record(conn, source_id=source_id, record=first)
        conn.commit()
        discovery = ScoutDiscoveryRepository(conn).get_by_source_identity(source_id, strategy_id)
        first_snapshot_id = discovery["last_snapshot_id"]

        second = _record(source_strategy_id=strategy_id, result_id="res-changed-1", net_pnl_percent=99.0)
        outcome = scout_service._ingest_record(conn, source_id=source_id, record=second)
        conn.commit()
        assert outcome == "changed"

        snapshots = ScoutSnapshotRepository(conn).list_for_discovery(discovery["id"])
        assert len(snapshots) == 2
        old_snapshot = next(s for s in snapshots if s["id"] == first_snapshot_id)
        assert old_snapshot is not None  # still readable
        old_claim = ScoutClaimRepository(conn).get_for_snapshot(first_snapshot_id)
        assert old_claim["net_pnl_percent"] == 10  # unchanged, immutable

        refreshed = ScoutDiscoveryRepository(conn).get(discovery["id"])
        new_claim = ScoutClaimRepository(conn).get_for_snapshot(refreshed["last_snapshot_id"])
        assert new_claim["net_pnl_percent"] == 99


def test_explicit_fork_lineage_is_preserved(pg_config):
    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        record = _record(
            source_strategy_id="strat-fork-" + str(datetime.now(UTC).timestamp()), result_id="res-fork-1",
            forked_from="parent-strategy-id",
        )
        scout_service._ingest_record(conn, source_id=source_id, record=record)
        conn.commit()
        discovery = ScoutDiscoveryRepository(conn).get_by_source_identity(source_id, record.source_strategy_id)
        assert discovery["forked_from_source_strategy_id"] == "parent-strategy-id"
        assert discovery["family_resolution"] == FamilyResolution.FORK_LINEAGE.value


def test_no_fork_lineage_stays_unresolved(pg_config):
    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        record = _record(source_strategy_id="strat-nofork-" + str(datetime.now(UTC).timestamp()), result_id="res-nf-1")
        scout_service._ingest_record(conn, source_id=source_id, record=record)
        conn.commit()
        discovery = ScoutDiscoveryRepository(conn).get_by_source_identity(source_id, record.source_strategy_id)
        assert discovery["family_resolution"] == FamilyResolution.UNRESOLVED.value


# --- manual discovery (Amendment 2026-09-17 sec10) ---------------------------

def test_manual_user_discovered_persists_with_snapshot_and_claim(pg_config):
    with connection(pg_config) as conn:
        discovery = scout_service.create_manual_discovery(
            conn, origin_kind=OriginKind.USER_DISCOVERED, title="Found on a forum",
            origin_description="r/algotrading post", origin_url="https://reddit.example.invalid/x",
            claimed_metrics={"net_pnl_percent": 33.3},
        )
        assert discovery["origin_kind"] == "USER_DISCOVERED"
        snapshots = ScoutSnapshotRepository(conn).list_for_discovery(discovery["id"])
        assert len(snapshots) == 1
        claim = ScoutClaimRepository(conn).get_for_snapshot(snapshots[0]["id"])
        assert claim["net_pnl_percent"] == 33.3 or float(claim["net_pnl_percent"]) == 33.3


def test_manual_my_idea_persists_with_zero_snapshots(pg_config):
    with connection(pg_config) as conn:
        discovery = scout_service.create_manual_discovery(
            conn, origin_kind=OriginKind.MY_IDEA, title="Matt's own hypothesis about gold seasonality",
        )
        assert discovery["origin_kind"] == "MY_IDEA"
        assert discovery["source_strategy_id"] is None
        assert discovery["origin_url"] is None
        snapshots = ScoutSnapshotRepository(conn).list_for_discovery(discovery["id"])
        assert snapshots == []  # legitimately zero SOURCE_CLAIM provenance


# --- intake status transitions + audit ---------------------------------------

def test_valid_intake_transition_persists_and_audits(pg_config):
    with connection(pg_config) as conn:
        discovery = scout_service.create_manual_discovery(
            conn, origin_kind=OriginKind.MY_IDEA, title="Intake transition test idea",
        )
        repo = ScoutDiscoveryRepository(conn)
        updated = repo.set_intake_status(
            discovery["id"], IntakeStatus.SHORTLISTED, changed_by="matt", reason="looks promising"
        )
        conn.commit()
        assert updated["intake_status"] == "SHORTLISTED"
        audit = repo.list_intake_audit(discovery["id"])
        assert len(audit) == 1
        assert audit[0]["from_status"] == "NEW"
        assert audit[0]["to_status"] == "SHORTLISTED"
        assert audit[0]["changed_by"] == "matt"


def test_invalid_intake_transition_is_rejected_and_state_unchanged(pg_config):
    with connection(pg_config) as conn:
        discovery = scout_service.create_manual_discovery(
            conn, origin_kind=OriginKind.MY_IDEA, title="Invalid transition test idea",
        )
        repo = ScoutDiscoveryRepository(conn)
        with pytest.raises(InvalidIntakeTransitionError):
            repo.set_intake_status(discovery["id"], IntakeStatus.READY_FOR_SPECIFICATION, changed_by="matt")
        conn.rollback()
    with connection(pg_config) as conn:
        refreshed = ScoutDiscoveryRepository(conn).get(discovery["id"])
        assert refreshed["intake_status"] == "NEW"  # unchanged
        assert ScoutDiscoveryRepository(conn).list_intake_audit(discovery["id"]) == []


def test_rejection_never_deletes_provenance(pg_config):
    with connection(pg_config) as conn:
        discovery = scout_service.create_manual_discovery(
            conn, origin_kind=OriginKind.MY_IDEA, title="Rejected idea stays readable",
        )
        repo = ScoutDiscoveryRepository(conn)
        repo.set_intake_status(discovery["id"], IntakeStatus.REJECTED, changed_by="matt", reason="not worth pursuing")
        conn.commit()
        still_there = repo.get(discovery["id"])
        assert still_there is not None
        assert still_there["intake_status"] == "REJECTED"
        assert still_there["discovery_lifecycle_state"] == "DISCOVERED"  # never SPECIFIED


# --- DB-layer defence in depth -----------------------------------------------

def _expect_and_absorb(conn: psycopg.Connection, exc_type, sql: str, params: tuple) -> None:
    """Run one deliberately-invalid statement, assert it raises `exc_type`,
    and roll back explicitly -- never relies on PostgreSQL's implicit
    COMMIT-in-aborted-transaction-means-ROLLBACK behaviour, so the
    connection is left in a clean, known state for connection()'s own
    commit-on-exit."""
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    except exc_type:
        conn.rollback()
    else:
        conn.rollback()
        pytest.fail(f"expected {exc_type.__name__}, nothing was raised")


def test_db_rejects_duplicate_source_identity_directly(pg_config):
    from darwin.core.identities import new_id

    strategy_id = "strat-dup-" + str(datetime.now(UTC).timestamp())
    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        record = _record(source_strategy_id=strategy_id, result_id="res-dup-1")
        scout_service._ingest_record(conn, source_id=source_id, record=record)
        conn.commit()

    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        _expect_and_absorb(
            conn, psycopg.errors.UniqueViolation,
            """
            INSERT INTO scout_discoveries
                (id, source_id, origin_kind, source_strategy_id, title, first_seen_utc, last_seen_utc)
            VALUES (%s, %s, 'ADAPTER_SOURCED', %s, 'dup', now(), now())
            """,
            (new_id(), source_id, strategy_id),
        )


def test_db_rejects_inconsistent_discovery_run_status_directly(pg_config):
    from darwin.core.identities import new_id

    with connection(pg_config) as conn:
        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        _expect_and_absorb(
            conn, psycopg.errors.CheckViolation,
            """
            INSERT INTO scout_discovery_runs
                (id, source_id, adapter_name, adapter_version, status, started_at_utc, completed_at_utc)
            VALUES (%s, %s, 'a', 'v1', 'SUCCEEDED', now(), NULL)
            """,
            (new_id(), source_id),
        )


def test_db_rejects_my_idea_with_a_source_strategy_id_directly(pg_config):
    """Defence in depth beyond the application constructor
    (darwin.scout.domain.build_manual_discovery) -- migration 0005's CHECK
    constraint on origin_kind='MY_IDEA' rejects it at the DB layer too."""
    from darwin.core.identities import new_id

    with connection(pg_config) as conn:
        my_idea_source_id = ScoutSourceRepository(conn).get_by_key("MY_IDEA")["id"]
        _expect_and_absorb(
            conn, psycopg.errors.CheckViolation,
            """
            INSERT INTO scout_discoveries
                (id, source_id, origin_kind, source_strategy_id, title, first_seen_utc, last_seen_utc)
            VALUES (%s, %s, 'MY_IDEA', 'some-external-id', 'bad', now(), now())
            """,
            (new_id(), my_idea_source_id),
        )


# --- end-to-end run_discovery against a mocked Trader.dev -------------------

def test_run_discovery_end_to_end_against_a_mocked_source_is_idempotent(pg_config):
    import json

    strategy_id = "strat-e2e-" + str(datetime.now(UTC).timestamp())
    hit = {
        "id": strategy_id, "name": "E2E test strategy", "symbol": "XAUUSD", "timeframe": "60",
        "forkedFromStrategyId": None, "updatedAt": 1789668702591,
        "result": {"resultId": "res-e2e-1", "viewUrl": "https://mcp-api.trader.dev/backtest/res-e2e-1"},
    }
    detail = {
        "id": "res-e2e-1", "visibility": "public", "netProfitPct": 5.5, "maxDrawdownPct": 3.3,
        "winRatePct": 60.0, "profitFactor": 1.8, "totalTrades": 42, "sharpeRatio": 1.1, "sortinoRatio": 1.4,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/strategies/search" in url:
            body = {"results": [hit], "limit": 50, "offset": 0, "hasMore": False, "sort": "recent"}
        else:
            body = detail
        return httpx.Response(200, content=json.dumps(body).encode("utf-8"),
                               headers={"content-type": "application/json"})

    with connection(pg_config) as conn:
        with TraderDevAdapter(transport=httpx.MockTransport(handler)) as adapter:
            run1 = scout_service.run_discovery(conn, symbol="XAUUSD", max_records=5, adapter=adapter)
        assert run1["status"] == "SUCCEEDED"
        assert run1["records_accepted"] == 1

        source_id = ScoutSourceRepository(conn).get_by_key("TRADER_DEV_PUBLIC")["id"]
        discovery = ScoutDiscoveryRepository(conn).get_by_source_identity(source_id, strategy_id)
        assert discovery is not None
        snapshot_count_after_first = len(ScoutSnapshotRepository(conn).list_for_discovery(discovery["id"]))
        assert snapshot_count_after_first == 1

        with TraderDevAdapter(transport=httpx.MockTransport(handler)) as adapter:
            run2 = scout_service.run_discovery(conn, symbol="XAUUSD", max_records=5, adapter=adapter)
        assert run2["status"] == "SUCCEEDED"
        assert run2["records_unchanged"] == 1
        assert run2["id"] != run1["id"]  # a genuinely new DiscoveryRun row each time

        snapshot_count_after_second = len(ScoutSnapshotRepository(conn).list_for_discovery(discovery["id"]))
        assert snapshot_count_after_second == 1  # still exactly one -- idempotent


def test_run_discovery_records_a_failed_run_when_source_totally_unreachable(pg_config, monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated total outage")

    with connection(pg_config) as conn, TraderDevAdapter(transport=httpx.MockTransport(handler)) as adapter:
        run = scout_service.run_discovery(conn, symbol="XAUUSD", max_records=5, adapter=adapter)
    assert run["status"] == "FAILED"
    assert run["completed_at_utc"] is not None
    assert run["records_observed"] == 0
    assert run["error_summary"]


def test_discovery_run_repository_get_latest_reflects_most_recent(pg_config):
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated")

    with connection(pg_config) as conn:
        with TraderDevAdapter(transport=httpx.MockTransport(handler)) as adapter:
            run = scout_service.run_discovery(conn, symbol="XAUUSD", max_records=1, adapter=adapter)
        latest = ScoutDiscoveryRunRepository(conn).get_latest()
    assert latest["id"] == run["id"]
