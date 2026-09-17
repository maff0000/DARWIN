-- PID-003 SCOUT: discovery/provenance substrate (docs/pids/PID-003-SCOUT.md).
--
-- Deliberately a NEW, self-contained set of tables rather than reusing
-- source_strategies/strategy_candidates (0001_foundation.sql): PID-003 §4
-- is explicit that "SourceStrategyIdentity != DARWIN CandidateVersion" --
-- a SCOUT discovery is provenance-only (DISCOVERED, never transitions in
-- this PID) and must never be silently conflated with the generic
-- Foundation pipeline_stage lifecycle that a future Specification PID
-- (PID-004) will actually drive. No FK from scout_* into
-- strategy_candidates/source_strategies exists anywhere in this migration.
--
-- No persistent DARWIN deployment exists yet (same reasoning already
-- relied on by migrations 0002-0004), so every NOT NULL below is safe to
-- add directly with no backfill step.

-- Closed, governed set of discovery origins (Amendment 2026-09-17,
-- docs/pids/PID-003-SCOUT.md §10): one adapter-sourced origin
-- (TRADER_DEV_PUBLIC) plus two manual-entry origins that are honestly
-- distinct from it and from each other -- USER_DISCOVERED (an idea found
-- outside SCOUT's automated adapter, with an external source) and
-- MY_IDEA (Matt's own hypothesis, no external source at all). Seeded here
-- as data rows, not as a Python-side registry, because "which sources
-- exist" is DARWIN_sql's own durable fact, read by every scout_discoveries
-- row via source_id.
CREATE TABLE scout_sources (
    id                  UUID PRIMARY KEY,
    source_key          TEXT NOT NULL UNIQUE
        CHECK (source_key IN ('TRADER_DEV_PUBLIC', 'USER_DISCOVERED', 'MY_IDEA')),
    origin_kind         TEXT NOT NULL
        CHECK (origin_kind IN ('ADAPTER_SOURCED', 'USER_DISCOVERED', 'MY_IDEA')),
    adapter_name        TEXT NULL,
    adapter_version     TEXT NULL,
    base_url            TEXT NULL,
    description         TEXT NOT NULL,
    created_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO scout_sources (id, source_key, origin_kind, adapter_name, adapter_version, base_url, description) VALUES
    (gen_random_uuid(), 'TRADER_DEV_PUBLIC', 'ADAPTER_SOURCED', 'trader_dev_public_adapter', 'v1',
     'https://mcp-api.trader.dev',
     'Trader.dev public, unauthenticated strategy/backtest browse surface (see docs/pids/PID-003-SCOUT.md sec3).'),
    (gen_random_uuid(), 'USER_DISCOVERED', 'USER_DISCOVERED', NULL, NULL, NULL,
     'A strategy idea Matt found outside SCOUT''s automated adapter (a website, TradingView, Reddit, YouTube, a paper, a forum, a trader, etc.) and entered manually.'),
    (gen_random_uuid(), 'MY_IDEA', 'MY_IDEA', NULL, NULL, NULL,
     'A hypothesis that originated with Matt, not any external source -- legitimately carries no URL, no external source, and no SOURCE_CLAIM metrics.');

-- SourceDiscovery: the stable discovery identity (PID-003 sec4). Keyed on the
-- strongest stable identity the source itself supplies (Trader.dev's own
-- strategy ULID `id`) -- never manufactured. Manual origins have no such
-- external key, so source_strategy_id is NULL for them and dedup simply
-- does not apply (each manual entry is its own row).
CREATE TABLE scout_discoveries (
    id                          UUID PRIMARY KEY,
    source_id                   UUID NOT NULL REFERENCES scout_sources(id),
    origin_kind                 TEXT NOT NULL
        CHECK (origin_kind IN ('ADAPTER_SOURCED', 'USER_DISCOVERED', 'MY_IDEA')),
    source_strategy_id          TEXT NULL,
    forked_from_source_strategy_id TEXT NULL,
    family_resolution           TEXT NOT NULL DEFAULT 'UNRESOLVED'
        CHECK (family_resolution IN ('UNRESOLVED', 'FORK_LINEAGE')),
    discovery_lifecycle_state   TEXT NOT NULL DEFAULT 'DISCOVERED'
        CHECK (discovery_lifecycle_state = 'DISCOVERED'),
    intake_status                TEXT NOT NULL DEFAULT 'NEW'
        CHECK (intake_status IN ('NEW', 'SHORTLISTED', 'IN_WORKSHOP', 'READY_FOR_SPECIFICATION', 'REJECTED')),
    title                        TEXT NOT NULL,
    source_symbol                TEXT NULL,
    source_timeframe             TEXT NULL,
    origin_description           TEXT NULL,
    origin_url                   TEXT NULL,
    original_description         TEXT NULL,
    pasted_rule_text              TEXT NULL,
    personal_notes                TEXT NULL,
    tags                          JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_snapshot_id               UUID NULL,
    latest_rule_availability       TEXT NULL
        CHECK (latest_rule_availability IN ('AVAILABLE', 'PARTIAL', 'UNAVAILABLE', 'ACCESS_RESTRICTED', 'UNKNOWN')),
    first_seen_utc                  TIMESTAMPTZ NOT NULL,
    last_seen_utc                   TIMESTAMPTZ NOT NULL,
    created_at_utc                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc                   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- MY_IDEA legitimately has no external source at all (PID-003 sec10):
    -- no source_strategy_id, no origin_url. Defence in depth alongside the
    -- application-layer constructor (darwin.scout.domain.build_manual_discovery).
    CHECK (origin_kind <> 'MY_IDEA' OR (source_strategy_id IS NULL AND origin_url IS NULL)),
    -- Only an adapter-sourced discovery carries a source_strategy_id/fork
    -- lineage -- manual entries (both kinds) never fabricate one.
    CHECK (origin_kind = 'ADAPTER_SOURCED' OR (source_strategy_id IS NULL AND forked_from_source_strategy_id IS NULL)),
    CHECK (forked_from_source_strategy_id IS NULL OR family_resolution = 'FORK_LINEAGE')
);

-- Stable dedup identity (PID-003 sec4): exact source identity dedups to the
-- SAME discovery row. NULLs (manual origins) are never considered equal to
-- each other by Postgres UNIQUE semantics, so this never collides across
-- manual entries.
CREATE UNIQUE INDEX idx_scout_discoveries_source_identity
    ON scout_discoveries (source_id, source_strategy_id)
    WHERE source_strategy_id IS NOT NULL;

CREATE INDEX idx_scout_discoveries_intake_status ON scout_discoveries (intake_status);
CREATE INDEX idx_scout_discoveries_source_symbol ON scout_discoveries (source_symbol);
CREATE INDEX idx_scout_discoveries_origin_kind ON scout_discoveries (origin_kind);

-- SourceSnapshot: one IMMUTABLE row per materially distinct extraction
-- (PID-003 sec4). No UPDATE statement is ever issued against this table by
-- application code (darwin.research_store.repositories.ScoutSnapshotRepository
-- exposes create()/get()/list_for_discovery() only -- no update method
-- exists). The fingerprint uniqueness below is what makes repeated
-- identical extraction idempotent.
CREATE TABLE scout_snapshots (
    id                      UUID PRIMARY KEY,
    discovery_id            UUID NOT NULL REFERENCES scout_discoveries(id),
    source_id               UUID NOT NULL REFERENCES scout_sources(id),
    source_record_id        TEXT NULL,
    extraction_utc           TIMESTAMPTZ NOT NULL,
    source_updated_utc       TIMESTAMPTZ NULL,
    adapter_name              TEXT NOT NULL,
    adapter_version           TEXT NOT NULL,
    source_url                 TEXT NULL,
    source_symbol               TEXT NULL,
    source_timeframe            TEXT NULL,
    raw_metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    rule_availability              TEXT NOT NULL
        CHECK (rule_availability IN ('AVAILABLE', 'PARTIAL', 'UNAVAILABLE', 'ACCESS_RESTRICTED', 'UNKNOWN')),
    fingerprint_sha256               TEXT NOT NULL,
    created_at_utc                     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Idempotency + immutability (PID-003 sec4): identical repeated
    -- extraction of a discovery never creates a second row for the same
    -- normalized claim payload.
    UNIQUE (discovery_id, fingerprint_sha256)
);

CREATE INDEX idx_scout_snapshots_discovery_id ON scout_snapshots (discovery_id);
CREATE INDEX idx_scout_snapshots_extraction_utc ON scout_snapshots (extraction_utc);

ALTER TABLE scout_discoveries
    ADD CONSTRAINT fk_scout_discoveries_last_snapshot
    FOREIGN KEY (last_snapshot_id) REFERENCES scout_snapshots(id);

-- SourceClaim: EvidenceLevel = SOURCE_CLAIM always (PID.md sec11), exact
-- NUMERIC never binary float. One row per snapshot -- the closed, bounded
-- metric set PID-003 sec4 names, never an open/arbitrary metric dict.
-- Foreign-keyed to a real snapshot AND a real discovery, per PID-003's
-- persistence requirement that every claim traces to both.
CREATE TABLE scout_claims (
    id                      UUID PRIMARY KEY,
    snapshot_id              UUID NOT NULL UNIQUE REFERENCES scout_snapshots(id),
    discovery_id              UUID NOT NULL REFERENCES scout_discoveries(id),
    evidence_level             TEXT NOT NULL CHECK (evidence_level = 'SOURCE_CLAIM'),
    net_pnl_percent              NUMERIC NULL,
    max_drawdown_percent          NUMERIC NULL,
    win_rate_percent                NUMERIC NULL,
    profit_factor                     NUMERIC NULL,
    trade_count                         INTEGER NULL,
    sharpe                                NUMERIC NULL,
    sortino                                 NUMERIC NULL,
    extraction_utc                            TIMESTAMPTZ NOT NULL,
    created_at_utc                              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scout_claims_discovery_id ON scout_claims (discovery_id);

-- DiscoveryRun: durable per-fetch identity (PID-003 sec4). completed_at_utc
-- presence/absence is tied to status by CHECK, so a run can never be read
-- back in an ambiguous "finished but still shows RUNNING" or "still running
-- but has a completion time" state.
CREATE TABLE scout_discovery_runs (
    id                          UUID PRIMARY KEY,
    source_id                    UUID NOT NULL REFERENCES scout_sources(id),
    requested_filter               JSONB NOT NULL DEFAULT '{}'::jsonb,
    adapter_name                     TEXT NOT NULL,
    adapter_version                    TEXT NOT NULL,
    status                               TEXT NOT NULL
        CHECK (status IN ('RUNNING', 'SUCCEEDED', 'PARTIAL', 'FAILED')),
    started_at_utc                         TIMESTAMPTZ NOT NULL,
    completed_at_utc                         TIMESTAMPTZ NULL,
    records_observed                           INTEGER NOT NULL DEFAULT 0,
    records_accepted                             INTEGER NOT NULL DEFAULT 0,
    records_unchanged                              INTEGER NOT NULL DEFAULT 0,
    records_changed                                  INTEGER NOT NULL DEFAULT 0,
    records_rejected                                   INTEGER NOT NULL DEFAULT 0,
    error_summary                                        TEXT NULL,
    created_at_utc                                         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (
        (status = 'RUNNING' AND completed_at_utc IS NULL)
        OR (status IN ('SUCCEEDED', 'PARTIAL', 'FAILED') AND completed_at_utc IS NOT NULL)
    )
);

CREATE INDEX idx_scout_discovery_runs_started_at ON scout_discovery_runs (started_at_utc DESC);
CREATE INDEX idx_scout_discovery_runs_status ON scout_discovery_runs (status);

-- Intake audit trail (PID-003 sec4: "auditable, never deletes provenance").
-- Only ever appended to -- no update/delete path exists in the repository.
CREATE TABLE scout_intake_audit (
    id                      UUID PRIMARY KEY,
    discovery_id             UUID NOT NULL REFERENCES scout_discoveries(id),
    from_status               TEXT NULL
        CHECK (from_status IS NULL OR from_status IN ('NEW', 'SHORTLISTED', 'IN_WORKSHOP', 'READY_FOR_SPECIFICATION', 'REJECTED')),
    to_status                  TEXT NOT NULL
        CHECK (to_status IN ('NEW', 'SHORTLISTED', 'IN_WORKSHOP', 'READY_FOR_SPECIFICATION', 'REJECTED')),
    changed_by                   TEXT NOT NULL,
    reason                         TEXT NULL,
    changed_at_utc                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scout_intake_audit_discovery_id ON scout_intake_audit (discovery_id);
