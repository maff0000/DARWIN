"""SCOUT discovery domain model (PID-003 SCOUT, docs/pids/PID-003-SCOUT.md).

`external source -> SOURCE_CLAIM -> discovery`, never `external source ->
DARWIN proof` (PID-003 sec2). Nothing here evaluates, qualifies, specifies,
or promotes a discovery -- lifecycle stays `DISCOVERED` only. Never conflate
a `SourceDiscovery`/`SourceStrategyIdentity` with a DARWIN `CandidateVersion`
(PID-003 sec4) -- there is deliberately no reference from anything in this
module into `darwin.core.lifecycle`/`strategy_candidates`.

This module owns constructor-enforced invariants only (mirrors
`darwin.research_store.run_binding` -- the only supported way to build the
records below); persistence lives in `darwin.research_store`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from darwin.core.errors import DarwinError
from darwin.core.identities import new_id

# The exact, closed metric set Trader.dev (or a manual entry) may supply
# (PID-003 sec4). Never an open/arbitrary metric dict -- adding a metric is
# a deliberate schema change, not something a caller-supplied key can add.
CLAIM_METRIC_FIELDS: tuple[str, ...] = (
    "net_pnl_percent",
    "max_drawdown_percent",
    "win_rate_percent",
    "profit_factor",
    "trade_count",
    "sharpe",
    "sortino",
)


class ScoutDomainError(DarwinError):
    """Base class for SCOUT domain-invariant violations. Rejected at
    construction time, never silently stored ambiguous (same discipline as
    darwin.research_store.run_binding.RunBindingError).
    """

    code = "SCOUT_DOMAIN_ERROR"


class InvalidOriginError(ScoutDomainError):
    code = "SCOUT_INVALID_ORIGIN"


class InvalidIntakeTransitionError(ScoutDomainError):
    code = "SCOUT_INVALID_INTAKE_TRANSITION"


class RuleAvailability(StrEnum):
    """PID-003 sec4. Trader.dev's numeric summary is captured as a
    SourceClaim regardless; this enum tracks the *rule/code text*
    specifically -- Trader.dev gates that behind auth
    (`/backtest/{id}/fork.json` 401s without a key, verified live), so a
    reachable public Trader.dev record is ACCESS_RESTRICTED, never
    AVAILABLE -- SCOUT never fetches fork.json and never introduces a
    Trader.dev credential anywhere. Never inferred up to AVAILABLE.
    """

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    ACCESS_RESTRICTED = "ACCESS_RESTRICTED"
    UNKNOWN = "UNKNOWN"


class IntakeStatus(StrEnum):
    """PID-003 sec4 + Amendment 2026-09-17 (sec10 adds IN_WORKSHOP).
    Operational triage workflow only -- IN_WORKSHOP is not an evidence
    level, not a research result, not `discovery_lifecycle_state` (which
    stays DISCOVERED for every row in this PID)."""

    NEW = "NEW"
    SHORTLISTED = "SHORTLISTED"
    IN_WORKSHOP = "IN_WORKSHOP"
    READY_FOR_SPECIFICATION = "READY_FOR_SPECIFICATION"
    REJECTED = "REJECTED"


class OriginKind(StrEnum):
    """Discriminates the three honestly-distinct provenance classes
    (Amendment 2026-09-17, PID-003 sec10) -- never collapsed into one
    undifferentiated "manual" bucket."""

    ADAPTER_SOURCED = "ADAPTER_SOURCED"
    USER_DISCOVERED = "USER_DISCOVERED"
    MY_IDEA = "MY_IDEA"


class FamilyResolution(StrEnum):
    """PID-003 sec4: without deterministic evidence (an explicit
    `forkedFromStrategyId`), family is UNRESOLVED -- no fuzzy/semantic/LLM
    clustering exists anywhere in this module."""

    UNRESOLVED = "UNRESOLVED"
    FORK_LINEAGE = "FORK_LINEAGE"


class DiscoveryRunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


# Narrow, explicit allowed-transition graph (PID-003 sec6: "narrow, explicit
# allowed-transition endpoint. No generic patch-everything endpoint.").
# REJECTED -> NEW is the sole reopen path; rejection never deletes
# provenance (PID-003 sec4) but this PID does not otherwise support
# resurrecting a rejected discovery through any other state.
ALLOWED_INTAKE_TRANSITIONS: dict[IntakeStatus, frozenset[IntakeStatus]] = {
    IntakeStatus.NEW: frozenset({IntakeStatus.SHORTLISTED, IntakeStatus.REJECTED}),
    IntakeStatus.SHORTLISTED: frozenset(
        {IntakeStatus.IN_WORKSHOP, IntakeStatus.REJECTED, IntakeStatus.NEW}
    ),
    IntakeStatus.IN_WORKSHOP: frozenset(
        {IntakeStatus.READY_FOR_SPECIFICATION, IntakeStatus.REJECTED, IntakeStatus.SHORTLISTED}
    ),
    IntakeStatus.READY_FOR_SPECIFICATION: frozenset(
        {IntakeStatus.REJECTED, IntakeStatus.IN_WORKSHOP}
    ),
    IntakeStatus.REJECTED: frozenset({IntakeStatus.NEW}),
}


def validate_intake_transition(current: IntakeStatus, target: IntakeStatus) -> None:
    """The only supported way to check an intake-status transition. Rejects
    no-op (same-state) transitions explicitly -- callers must request a real
    change -- and anything not in the fixed adjacency graph above."""
    if current == target:
        raise InvalidIntakeTransitionError(
            f"{current.value} -> {target.value} is a no-op, not a transition"
        )
    allowed = ALLOWED_INTAKE_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidIntakeTransitionError(
            f"{current.value} -> {target.value} is not an allowed intake transition "
            f"(allowed from {current.value}: {sorted(a.value for a in allowed)})"
        )


@dataclass(frozen=True)
class Source:
    """PID-003 sec4: one row per governed origin -- adapter identity +
    base URL + adapter version for TRADER_DEV_PUBLIC, or a manual-entry
    origin (USER_DISCOVERED/MY_IDEA) with no adapter/base_url at all
    (Amendment 2026-09-17, sec10). Seeded by migration 0005 -- this is a
    closed, governed set, never something a caller-supplied string can
    add to (same discipline as darwin.hermes.instrument_definition's
    closed registry)."""

    id: str
    source_key: str
    origin_kind: OriginKind
    description: str
    adapter_name: str | None = None
    adapter_version: str | None = None
    base_url: str | None = None
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class SourceDiscovery:
    """The stable discovery identity (PID-003 sec4). `source_strategy_id`
    is the source's OWN identity (Trader.dev's strategy ULID) -- never
    manufactured; NULL for manual origins, which have no external identity
    to dedup against. `discovery_lifecycle_state` is always DISCOVERED in
    this PID (Amendment 2026-09-17 sec10: no PID-003 action ever produces
    SPECIFIED or a StrategyVersion).
    """

    id: str
    source_id: str
    origin_kind: OriginKind
    title: str
    source_strategy_id: str | None = None
    forked_from_source_strategy_id: str | None = None
    family_resolution: FamilyResolution = FamilyResolution.UNRESOLVED
    discovery_lifecycle_state: str = "DISCOVERED"
    intake_status: IntakeStatus = IntakeStatus.NEW
    source_symbol: str | None = None
    source_timeframe: str | None = None
    origin_description: str | None = None
    origin_url: str | None = None
    original_description: str | None = None
    pasted_rule_text: str | None = None
    personal_notes: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    last_snapshot_id: str | None = None
    latest_rule_availability: RuleAvailability | None = None
    first_seen_utc: datetime | None = None
    last_seen_utc: datetime | None = None
    created_at_utc: datetime | None = None
    updated_at_utc: datetime | None = None


@dataclass(frozen=True)
class SourceSnapshot:
    """One IMMUTABLE row per materially distinct extraction (PID-003 sec4).
    Nothing in this module ever mutates a constructed instance's fields
    after persistence -- see darwin.research_store.repositories
    .ScoutSnapshotRepository, which exposes no update method."""

    id: str
    discovery_id: str
    source_id: str
    extraction_utc: datetime
    adapter_name: str
    adapter_version: str
    rule_availability: RuleAvailability
    fingerprint_sha256: str
    source_record_id: str | None = None
    source_updated_utc: datetime | None = None
    source_url: str | None = None
    source_symbol: str | None = None
    source_timeframe: str | None = None
    raw_metadata: dict = field(default_factory=dict)
    created_at_utc: datetime | None = None


@dataclass(frozen=True)
class SourceClaim:
    """EvidenceLevel = SOURCE_CLAIM always (PID.md sec11). Every value here
    is exact Decimal, never binary float -- see `_to_exact` below. Every
    value traces to its snapshot_id + discovery_id + extraction_utc."""

    id: str
    snapshot_id: str
    discovery_id: str
    extraction_utc: datetime
    evidence_level: str = "SOURCE_CLAIM"
    net_pnl_percent: Decimal | None = None
    max_drawdown_percent: Decimal | None = None
    win_rate_percent: Decimal | None = None
    profit_factor: Decimal | None = None
    trade_count: int | None = None
    sharpe: Decimal | None = None
    sortino: Decimal | None = None
    created_at_utc: datetime | None = None

    def has_any_metric(self) -> bool:
        return any(
            getattr(self, name) is not None
            for name in CLAIM_METRIC_FIELDS
        )


@dataclass(frozen=True)
class DiscoveryRun:
    """Durable per-fetch identity (PID-003 sec4). `completed_at_utc`
    presence/absence must always agree with `status` -- enforced again at
    the DB layer (migration 0005's CHECK constraint) as defence in depth,
    same discipline as migration 0004's DIKE presence/absence CHECK."""

    id: str
    source_id: str
    adapter_name: str
    adapter_version: str
    started_at_utc: datetime
    status: DiscoveryRunStatus
    requested_filter: dict = field(default_factory=dict)
    completed_at_utc: datetime | None = None
    records_observed: int = 0
    records_accepted: int = 0
    records_unchanged: int = 0
    records_changed: int = 0
    records_rejected: int = 0
    error_summary: str | None = None
    created_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if self.status == DiscoveryRunStatus.RUNNING and self.completed_at_utc is not None:
            raise ScoutDomainError("A RUNNING DiscoveryRun must not carry completed_at_utc")
        if self.status != DiscoveryRunStatus.RUNNING and self.completed_at_utc is None:
            raise ScoutDomainError(
                f"A {self.status.value} DiscoveryRun must carry completed_at_utc"
            )


@dataclass(frozen=True)
class IntakeAuditEntry:
    id: str
    discovery_id: str
    to_status: IntakeStatus
    changed_by: str
    from_status: IntakeStatus | None = None
    reason: str | None = None
    changed_at_utc: datetime | None = None


def _to_exact(value: object) -> Decimal | None:
    """Exact float/str/int -> Decimal conversion, never routed through a
    binary-float round-trip that could silently change a claimed value
    (mirrors darwin.hermes.dataset's PRICE_SCALE exact-conversion
    discipline). `None`/missing stays `None` -- a source that omitted a
    metric is honestly recorded as omitted, never defaulted to zero."""
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass -- reject explicitly
        raise ScoutDomainError(f"Refusing to interpret boolean {value!r} as a numeric metric")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # repr() round-trips a float's actual decimal text exactly as
        # Python would display it -- str(value) can too, but repr is the
        # documented shortest-round-trip form since Python 3.1. Either way
        # this is the ONE place a float is ever seen; everything downstream
        # is Decimal.
        return Decimal(repr(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception as exc:
            raise ScoutDomainError(f"Malformed numeric metric text: {value!r}") from exc
    raise ScoutDomainError(f"Unsupported metric value type: {type(value)!r}")


def _to_exact_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ScoutDomainError(f"Refusing to interpret boolean {value!r} as trade_count")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ScoutDomainError(f"trade_count must be a whole number, got {value!r}")
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ScoutDomainError(f"Malformed trade_count text: {value!r}") from exc
    raise ScoutDomainError(f"Unsupported trade_count value type: {type(value)!r}")


def build_claim_values(raw: dict) -> dict[str, Decimal | int | None]:
    """Build the exact-typed metric dict for a SourceClaim from whichever
    of the closed metric keys `raw` actually supplies. Missing keys map to
    `None` (never fabricated as zero)."""
    values: dict[str, Decimal | int | None] = {}
    for name in CLAIM_METRIC_FIELDS:
        raw_value = raw.get(name)
        values[name] = _to_exact_int(raw_value) if name == "trade_count" else _to_exact(raw_value)
    return values


def compute_snapshot_fingerprint(*, discovery_id: str, claim_payload: dict) -> str:
    """SHA-256 over the normalized claim payload (PID-003 sec4). Normalized
    = stable key order + exact Decimal text (never float repr, which can
    legitimately differ run-to-run for the same logical value in other
    ecosystems) + explicit discovery_id binding, so an identical claim value
    for a DIFFERENT discovery never collides. `None` values are included
    explicitly (a metric going from present to absent IS a material
    change)."""
    normalized = {
        "discovery_id": str(discovery_id),
        **{
            name: (str(claim_payload.get(name)) if claim_payload.get(name) is not None else None)
            for name in CLAIM_METRIC_FIELDS
        },
    }
    canonical_json = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def build_manual_discovery(
    *,
    source_id: str,
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
    now: datetime | None = None,
) -> tuple[SourceDiscovery, SourceSnapshot | None, SourceClaim | None]:
    """The only supported way to construct a manual (USER_DISCOVERED/
    MY_IDEA) discovery (mirrors run_binding.create_research_run). Enforces,
    at construction time rather than as an assumed invariant:

    - MY_IDEA carries no origin_url and no claimed metrics at all (Amendment
      2026-09-17 sec10) -- "legitimately has NO url, NO external source, and
      NO SOURCE_CLAIM metrics at all". Never fabricates an external source
      identity for an internally-originated idea.
    - Only USER_DISCOVERED may ever produce a SourceSnapshot/SourceClaim
      pair here, and only when at least one manual field beyond the bare
      title was actually supplied -- an empty snapshot/claim row would carry
      no provenance and is never created.
    - `pasted_rule_text` is stored as inert text only. Nothing in this
      function (or anywhere in darwin.scout) ever executes, evals, or
      renders it.
    """
    if origin_kind not in (OriginKind.USER_DISCOVERED, OriginKind.MY_IDEA):
        raise InvalidOriginError(
            f"build_manual_discovery only supports USER_DISCOVERED/MY_IDEA, got {origin_kind}"
        )
    if not title or not title.strip():
        raise ScoutDomainError("A manual discovery requires a non-empty title")

    if origin_kind == OriginKind.MY_IDEA:
        if origin_url is not None:
            raise InvalidOriginError("MY_IDEA must not carry an origin_url — it has no external source")
        if claimed_metrics:
            raise InvalidOriginError(
                "MY_IDEA must not carry any claimed SOURCE_CLAIM metric — it is Matt's own "
                "hypothesis, not an external claim"
            )

    now = now or datetime.now(UTC)
    discovery_id = new_id()

    discovery = SourceDiscovery(
        id=discovery_id,
        source_id=source_id,
        origin_kind=origin_kind,
        title=title.strip(),
        source_strategy_id=None,
        forked_from_source_strategy_id=None,
        family_resolution=FamilyResolution.UNRESOLVED,
        intake_status=IntakeStatus.NEW,
        source_symbol=source_symbol,
        source_timeframe=source_timeframe,
        origin_description=origin_description,
        origin_url=origin_url,
        original_description=original_description,
        pasted_rule_text=pasted_rule_text,
        personal_notes=personal_notes,
        tags=tuple(tags),
        latest_rule_availability=None,
        first_seen_utc=now,
        last_seen_utc=now,
    )

    if origin_kind == OriginKind.MY_IDEA:
        # No external source, no metrics -- honestly zero provenance rows.
        return discovery, None, None

    has_provenance_content = bool(
        origin_description or origin_url or original_description or pasted_rule_text or claimed_metrics
    )
    if not has_provenance_content:
        return discovery, None, None

    claim_values = build_claim_values(claimed_metrics or {})
    fingerprint = compute_snapshot_fingerprint(discovery_id=discovery_id, claim_payload=claim_values)
    rule_availability = RuleAvailability.AVAILABLE if pasted_rule_text else RuleAvailability.UNAVAILABLE

    snapshot = SourceSnapshot(
        id=new_id(),
        discovery_id=discovery_id,
        source_id=source_id,
        extraction_utc=now,
        adapter_name="manual_entry",
        adapter_version="v1",
        rule_availability=rule_availability,
        fingerprint_sha256=fingerprint,
        source_record_id=None,
        source_updated_utc=None,
        source_url=origin_url,
        source_symbol=source_symbol,
        source_timeframe=source_timeframe,
        raw_metadata={
            "origin_description": origin_description,
            "original_description": original_description,
            "pasted_rule_text": pasted_rule_text,
            "personal_notes": personal_notes,
            "tags": list(tags),
        },
    )

    claim = None
    if any(v is not None for v in claim_values.values()):
        claim = SourceClaim(
            id=new_id(),
            snapshot_id=snapshot.id,
            discovery_id=discovery_id,
            extraction_utc=now,
            **claim_values,
        )

    discovery = replace(discovery, last_snapshot_id=snapshot.id, latest_rule_availability=rule_availability)
    return discovery, snapshot, claim
