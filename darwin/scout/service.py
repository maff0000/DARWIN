"""SCOUT orchestration: turns Trader.dev adapter records (or Matt's manual
entry) into persisted discoveries/snapshots/claims, with durable per-run
provenance (PID-003 SCOUT sec4).

This is the ONLY place a `DiscoveryRun` is driven end-to-end -- darwin.app's
endpoints call into this module, never into the adapter or repositories
directly, so idempotency/dedup/run-bookkeeping logic exists in exactly one
place.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime

import psycopg

from darwin.core.identities import new_id
from darwin.core.logging import log_event
from darwin.research_store.repositories import (
    ScoutClaimRepository,
    ScoutDiscoveryRepository,
    ScoutDiscoveryRunRepository,
    ScoutSnapshotRepository,
    ScoutSourceRepository,
)
from darwin.scout.domain import (
    DiscoveryRun,
    DiscoveryRunStatus,
    FamilyResolution,
    OriginKind,
    ScoutDomainError,
    SourceClaim,
    SourceDiscovery,
    SourceSnapshot,
    build_claim_values,
    build_manual_discovery,
    compute_snapshot_fingerprint,
)
from darwin.scout.trader_dev_adapter import (
    ADAPTER_NAME,
    ADAPTER_VERSION,
    ALLOWED_SORTS,
    NormalizedRecord,
    ScoutSourceError,
    TraderDevAdapter,
)

logger = logging.getLogger(__name__)

MAX_RECORDS_PER_RUN = 200  # hard ceiling regardless of what the caller asks for
DEFAULT_MAX_RECORDS_PER_RUN = 25


class ScoutRequestError(ScoutDomainError):
    """A caller-supplied /scout request parameter is out of the bounded,
    sensible range this endpoint accepts. Never a raw URL parameter exists
    here or anywhere in SCOUT (PID-003 sec5/sec6)."""

    code = "SCOUT_INVALID_REQUEST"


def _require_source(conn: psycopg.Connection, source_key: str) -> dict:
    source = ScoutSourceRepository(conn).get_by_key(source_key)
    if source is None:  # pragma: no cover - only possible if migration 0005 seed rows are missing
        raise ScoutDomainError(f"SCOUT source {source_key!r} is not seeded — migrations pending?")
    return source


def run_discovery(
    conn: psycopg.Connection,
    *,
    symbol: str | None,
    max_records: int = DEFAULT_MAX_RECORDS_PER_RUN,
    sort: str = "recent",
    adapter: TraderDevAdapter | None = None,
) -> dict:
    """Run exactly ONE bounded, synchronous, on-demand discovery pass
    against Trader.dev (PID-003 sec6: "no scheduler, no continuous
    crawling"). Always produces a durable DiscoveryRun row, win or lose --
    "no silent success" (PID-003 sec4).

    Records already known (same source_id + source_strategy_id) whose
    latest claim payload is byte-identical are counted `unchanged` and
    create no new snapshot. A materially different claim payload creates a
    new immutable snapshot+claim and counts as `changed`. A genuinely new
    source_strategy_id counts as `accepted`. A per-record parse failure
    counts as `rejected` and does not abort the run -- explicit, bounded
    partial-ingestion support (PID-003 sec4): the run's own `status`
    becomes PARTIAL, never a silently-reported SUCCEEDED.
    """
    if max_records < 1 or max_records > MAX_RECORDS_PER_RUN:
        raise ScoutRequestError(
            f"max_records must be between 1 and {MAX_RECORDS_PER_RUN}, got {max_records}"
        )
    if sort not in ALLOWED_SORTS:
        raise ScoutRequestError(f"sort {sort!r} is not one of the allowed sort values: {sorted(ALLOWED_SORTS)}")

    source = _require_source(conn, "TRADER_DEV_PUBLIC")
    source_id = source["id"]

    run_id = new_id()
    started_at = datetime.now(UTC)
    requested_filter = {"symbol": symbol, "max_records": max_records, "sort": sort}
    run_repo = ScoutDiscoveryRunRepository(conn)
    run_repo.create(
        DiscoveryRun(
            id=run_id,
            source_id=source_id,
            adapter_name=ADAPTER_NAME,
            adapter_version=ADAPTER_VERSION,
            started_at_utc=started_at,
            status=DiscoveryRunStatus.RUNNING,
            requested_filter=requested_filter,
        )
    )
    conn.commit()  # the RUNNING row is durable evidence a run started, independent of the outcome below

    owns_adapter = adapter is None
    adapter = adapter or TraderDevAdapter()
    observed = accepted = unchanged = changed = rejected = 0
    error_summary: str | None = None
    try:
        try:
            records, parse_errors = adapter.iter_public_records(symbol=symbol, max_records=max_records, sort=sort)
        except ScoutSourceError as exc:
            # Total failure before a single record was fetched -- no
            # partial writes were made, so FAILED (not PARTIAL) is honest.
            error_summary = f"{exc.__class__.__name__}: {exc}"
            run_repo.complete(
                run_id, status=DiscoveryRunStatus.FAILED.value, completed_at_utc=datetime.now(UTC),
                records_observed=0, records_accepted=0, records_unchanged=0, records_changed=0,
                records_rejected=0, error_summary=error_summary,
            )
            conn.commit()
            log_event(logger, logging.WARNING, "scout_discovery_run_failed", run_id=run_id, error=error_summary)
            return run_repo.get(run_id)

        observed += len(parse_errors)
        rejected += len(parse_errors)
        for record in records:
            observed += 1
            try:
                outcome = _ingest_record(conn, source_id=source_id, record=record)
            except ScoutDomainError as exc:
                rejected += 1
                log_event(
                    logger, logging.WARNING, "scout_record_rejected",
                    run_id=run_id, source_strategy_id=getattr(record, "source_strategy_id", None),
                    error=str(exc),
                )
                continue
            if outcome == "accepted":
                accepted += 1
            elif outcome == "changed":
                changed += 1
            else:
                unchanged += 1

        conn.commit()
        error_detail = "; ".join(parse_errors[:5]) if parse_errors else None
        if rejected and (accepted or changed or unchanged):
            status = DiscoveryRunStatus.PARTIAL
            error_summary = f"{rejected} of {observed} records could not be ingested" + (
                f" ({error_detail})" if error_detail else ""
            )
        elif rejected and not (accepted or changed or unchanged):
            status = DiscoveryRunStatus.FAILED
            error_summary = f"All {rejected} observed records failed to ingest" + (
                f" ({error_detail})" if error_detail else ""
            )
        else:
            status = DiscoveryRunStatus.SUCCEEDED

        run_repo.complete(
            run_id, status=status.value, completed_at_utc=datetime.now(UTC),
            records_observed=observed, records_accepted=accepted, records_unchanged=unchanged,
            records_changed=changed, records_rejected=rejected, error_summary=error_summary,
        )
        conn.commit()
        log_event(
            logger, logging.INFO, "scout_discovery_run_completed", run_id=run_id, status=status.value,
            observed=observed, accepted=accepted, unchanged=unchanged, changed=changed, rejected=rejected,
        )
        return run_repo.get(run_id)
    finally:
        if owns_adapter:
            adapter.close()


def _ingest_record(conn: psycopg.Connection, *, source_id: str, record: NormalizedRecord) -> str:
    """Idempotency/dedup core (PID-003 sec4). Returns "accepted" | "changed"
    | "unchanged". Raises ScoutDomainError for a malformed record — callers
    count that as `rejected` and continue the run.
    """
    discovery_repo = ScoutDiscoveryRepository(conn)
    snapshot_repo = ScoutSnapshotRepository(conn)
    claim_repo = ScoutClaimRepository(conn)

    now = datetime.now(UTC)
    existing = discovery_repo.get_by_source_identity(source_id, record.source_strategy_id)

    claim_values = build_claim_values(record.claim_payload)

    if existing is None:
        discovery_id = new_id()
        family_resolution = (
            FamilyResolution.FORK_LINEAGE if record.forked_from_source_strategy_id else FamilyResolution.UNRESOLVED
        )
        discovery = SourceDiscovery(
            id=discovery_id,
            source_id=source_id,
            origin_kind=OriginKind.ADAPTER_SOURCED,
            title=record.name or record.source_strategy_id,
            source_strategy_id=record.source_strategy_id,
            forked_from_source_strategy_id=record.forked_from_source_strategy_id,
            family_resolution=family_resolution,
            source_symbol=record.symbol,
            source_timeframe=record.timeframe,
            first_seen_utc=now,
            last_seen_utc=now,
        )
        discovery_repo.create(discovery)
    else:
        discovery_id = str(existing["id"])  # psycopg returns UUID columns as uuid.UUID, not str

    fingerprint = compute_snapshot_fingerprint(discovery_id=discovery_id, claim_payload=claim_values)
    duplicate = snapshot_repo.find_by_fingerprint(discovery_id, fingerprint)
    if duplicate is not None:
        # Idempotent repeat -- no new snapshot row, but we DID just see it
        # again: last_seen_utc still advances (PID-003 acceptance sec: "run
        # it twice, prove no second snapshot was created" — last_seen_utc
        # moving is how the second run is honestly distinguishable from a
        # no-op).
        discovery_repo.record_extraction_seen(discovery_id, last_seen_utc=now)
        return "accepted" if existing is None else "unchanged"

    snapshot = SourceSnapshot(
        id=new_id(),
        discovery_id=discovery_id,
        source_id=source_id,
        extraction_utc=now,
        adapter_name=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        rule_availability=record.rule_availability,
        fingerprint_sha256=fingerprint,
        source_record_id=record.result_id,
        source_updated_utc=record.strategy_updated_at_utc,
        source_url=record.view_url,
        source_symbol=record.symbol,
        source_timeframe=record.timeframe,
        raw_metadata=record.raw_metadata,
    )
    snapshot_repo.create(snapshot)

    if any(v is not None for v in claim_values.values()):
        claim_repo.create(
            SourceClaim(
                id=new_id(),
                snapshot_id=snapshot.id,
                discovery_id=discovery_id,
                extraction_utc=now,
                **claim_values,
            )
        )

    discovery_repo.record_extraction_seen(
        discovery_id,
        last_seen_utc=now,
        new_snapshot_id=snapshot.id,
        latest_rule_availability=record.rule_availability.value,
        source_symbol=record.symbol,
        source_timeframe=record.timeframe,
    )
    return "accepted" if existing is None else "changed"


def create_manual_discovery(
    conn: psycopg.Connection,
    *,
    origin_kind: OriginKind,
    title: str,
    origin_description: str | None = None,
    origin_url: str | None = None,
    source_symbol: str | None = None,
    source_timeframe: str | None = None,
    original_description: str | None = None,
    pasted_rule_text: str | None = None,
    personal_notes: str | None = None,
    tags: tuple[str, ...] = (),
    claimed_metrics: dict | None = None,
) -> dict:
    """PID-003 Amendment 2026-09-17 sec10: Matt adding a strategy he found
    himself, or a hypothesis of his own -- never touches the Trader.dev
    adapter, never triggers a fetch of anything."""
    source_key = origin_kind.value  # 'USER_DISCOVERED' | 'MY_IDEA' -- same string by construction
    source = _require_source(conn, source_key)

    discovery, snapshot, claim = build_manual_discovery(
        source_id=source["id"],
        origin_kind=origin_kind,
        title=title,
        origin_description=origin_description,
        origin_url=origin_url,
        source_symbol=source_symbol,
        source_timeframe=source_timeframe,
        original_description=original_description,
        pasted_rule_text=pasted_rule_text,
        personal_notes=personal_notes,
        tags=tags,
        claimed_metrics=claimed_metrics,
    )

    discovery_repo = ScoutDiscoveryRepository(conn)
    # Insert the discovery WITHOUT its last_snapshot_id forward-reference
    # first -- scout_discoveries.last_snapshot_id is FK'd to scout_snapshots
    # (migration 0005), so inserting the fully-populated discovery (which
    # already points at `snapshot.id`) before that snapshot row exists
    # would violate the constraint. Snapshot+claim go in next, then the
    # discovery's last_snapshot_id/latest_rule_availability are set via the
    # same record_extraction_seen() update path _ingest_record uses.
    bare_discovery = replace(discovery, last_snapshot_id=None, latest_rule_availability=None)
    discovery_repo.create(bare_discovery)
    if snapshot is not None:
        ScoutSnapshotRepository(conn).create(snapshot)
    if claim is not None:
        ScoutClaimRepository(conn).create(claim)
    if snapshot is not None:
        discovery_repo.record_extraction_seen(
            discovery.id,
            last_seen_utc=discovery.last_seen_utc,
            new_snapshot_id=snapshot.id,
            latest_rule_availability=(
                discovery.latest_rule_availability.value if discovery.latest_rule_availability else None
            ),
            source_symbol=discovery.source_symbol,
            source_timeframe=discovery.source_timeframe,
        )
    conn.commit()
    log_event(
        logger, logging.INFO, "scout_manual_discovery_created",
        discovery_id=discovery.id, origin_kind=origin_kind.value,
    )
    return discovery_repo.get(discovery.id)


def scout_status(conn: psycopg.Connection | None, *, adapter: TraderDevAdapter | None = None) -> dict:
    """GET /api/v1/scout/status body (PID-003 sec6). Always answers -- a
    Trader.dev outage or a not-yet-migrated database degrades the fields
    that depend on them, never raises, and never affects DARWIN readiness
    (see darwin.app: this function is never consulted by `_readiness`).
    """
    owns_adapter = adapter is None
    adapter = adapter or TraderDevAdapter()
    try:
        reachable = adapter.check_reachable()
    finally:
        if owns_adapter:
            adapter.close()

    result: dict = {
        "trader_dev_public": {"reachable": reachable},
        "last_discovery_run": None,
        "sources": [],
    }
    if conn is None:
        return result
    try:
        result["last_discovery_run"] = ScoutDiscoveryRunRepository(conn).get_latest()
        result["sources"] = ScoutSourceRepository(conn).list()
    except Exception as exc:  # noqa: BLE001 - status must never 500 on a DB hiccup
        log_event(logger, logging.WARNING, "scout_status_db_check_failed", error=str(exc))
    return result
