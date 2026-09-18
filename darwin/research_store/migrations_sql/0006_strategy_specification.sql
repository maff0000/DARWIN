-- PID-004A Specification Contract: durable persistence for the already-
-- accepted, already-hardened in-memory domain model in darwin.specification
-- (docs/pids/PID-004-SPECIFICATION-WORKSHOP.md sec2/PID-004A). This is a
-- PERSISTENCE-ONLY migration -- it never redesigns the domain model.
--
-- Architect ruling (verbatim, item 1): do NOT create competing tables like
-- `spec_strategy_versions`. Evolve `strategy_candidates`/`strategy_versions`
-- into the canonical Specification persistence model. One identity system.
-- Accordingly this migration ALTERs the existing 0001_foundation.sql tables
-- (adds nullable columns only -- no existing column is dropped/retyped, no
-- existing row is touched) and adds new, genuinely separate tables for
-- concerns that were never modelled at all before now: draft authoring,
-- candidate lineage/discovery provenance, the DataRequirement projection,
-- readiness assessments, shelving events, and validation records.
--
-- No persistent DARWIN deployment has ever existed on this host (same
-- reasoning already relied on by migrations 0002-0005), so this migration
-- is written to be safe regardless -- every new column on an existing
-- table is nullable (no backfill required), every new table is additive,
-- and nothing here truncates, drops, or retypes any existing object.
--
-- Identity-model judgment call (flagged for the Architect, not silently
-- resolved): `strategy_candidates.id`/`strategy_versions.id` remain UUID
-- (unchanged) -- real candidates/versions created by
-- darwin.research_store.specification_finalisation always mint a real
-- UUID (darwin.core.identities.new_id()) for both. darwin.specification's
-- own domain dataclasses only require a non-empty governed string id
-- (tests/contract's 14 fixtures use plain strings like "fixture-01"),
-- which is legitimate domain modelling but not itself a database identity
-- decision -- when those fixtures are run through real persistence
-- (architecture-proof only, PID-004 sec21/sec30), the persistence layer
-- substitutes fresh UUIDs for candidate_id/strategy_version_id before
-- INSERT. This is always safe: candidate_id and strategy_version_id are
-- both explicitly EXCLUDED from `semantic_fingerprint`
-- (darwin.specification.domain._EXCLUDED_FROM_SEMANTIC_FINGERPRINT), so
-- substituting them changes neither the domain object's semantic identity
-- nor its semantic_fingerprint -- only artifact_record_fingerprint (which
-- is explicitly allowed, indeed expected, to differ per persisted record).

-- ---------------------------------------------------------------------------
-- 1. Evolve strategy_candidates / strategy_versions (item 1/item 3/item 5).
-- ---------------------------------------------------------------------------

-- strategy_candidates.pipeline_stage already permits 'SPECIFIED' since
-- 0001_foundation.sql -- no ALTER needed there. Candidate derivation
-- lineage and discovery provenance are modelled as new join tables (item
-- 3: "NOT collapsed into the old nullable source_strategy_id column, and
-- NOT one overloaded nullable column").

CREATE TABLE strategy_candidate_discovery_links (
    id                  UUID PRIMARY KEY,
    candidate_id        UUID NOT NULL REFERENCES strategy_candidates(id),
    discovery_id        UUID NOT NULL REFERENCES scout_discoveries(id),
    created_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, discovery_id)
);

CREATE INDEX idx_scdl_candidate_id ON strategy_candidate_discovery_links (candidate_id);
CREATE INDEX idx_scdl_discovery_id ON strategy_candidate_discovery_links (discovery_id);

CREATE TABLE strategy_candidate_lineage (
    id                      UUID PRIMARY KEY,
    child_candidate_id      UUID NOT NULL REFERENCES strategy_candidates(id),
    parent_candidate_id     UUID NOT NULL REFERENCES strategy_candidates(id),
    created_at_utc          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (child_candidate_id, parent_candidate_id),
    CHECK (child_candidate_id <> parent_candidate_id)
);

CREATE INDEX idx_scl_child_candidate_id ON strategy_candidate_lineage (child_candidate_id);
CREATE INDEX idx_scl_parent_candidate_id ON strategy_candidate_lineage (parent_candidate_id);

-- SpecificationDraft persistence (item 4): mutable authoring object, full
-- lossless serialized payload (darwin.specification.serialization), and
-- explicit optimistic-concurrency `revision`. A draft revision is NOT a
-- StrategyVersion (item 4) -- this table has no fingerprint/immutability
-- columns at all; those belong exclusively to strategy_versions below.
CREATE TABLE specification_drafts (
    id                              UUID PRIMARY KEY,
    candidate_id                    UUID NOT NULL REFERENCES strategy_candidates(id),
    schema_semantic_version         TEXT NOT NULL,
    revision                        INTEGER NOT NULL DEFAULT 1,
    draft_payload                   JSONB NOT NULL,
    serialization_schema_version    TEXT NOT NULL,
    created_at_utc                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (revision >= 1)
);

CREATE INDEX idx_specification_drafts_candidate_id ON specification_drafts (candidate_id);

-- Evolve strategy_versions (item 5/item 6/item 7): nullable additive
-- columns only. `full_payload` is the complete losslessly-serialized
-- StrategyVersion (darwin.specification.serialization.
-- serialize_strategy_version) -- both the canonical immutable semantic
-- payload AND the canonical provenance/artifact payload are recoverable
-- from this single document by rehydrating it
-- (darwin.specification.serialization.deserialize_strategy_version) and
-- calling the rehydrated object's own .semantic_payload()/.artifact_
-- payload() methods -- never persisting only the two hashes while
-- discarding the semantics that produced them.
ALTER TABLE strategy_versions
    ADD COLUMN title                         TEXT,
    ADD COLUMN thesis                        TEXT,
    ADD COLUMN schema_semantic_version        TEXT,
    ADD COLUMN semantic_fingerprint           TEXT,
    ADD COLUMN artifact_record_fingerprint    TEXT,
    ADD COLUMN full_payload                   JSONB,
    ADD COLUMN serialization_schema_version   TEXT,
    ADD COLUMN source_draft_id                UUID REFERENCES specification_drafts(id),
    ADD COLUMN finalised_at_utc                TIMESTAMPTZ;

-- Item 6: semantic_fingerprint deliberately carries NO uniqueness
-- constraint -- two independent candidates producing semantically
-- identical strategies is explicitly valid (same semantic_fingerprint,
-- different StrategyVersion identity, different artifact_record_
-- fingerprint). Indexed (not unique) purely for the "which other
-- StrategyVersions share this semantic_fingerprint" query.
CREATE INDEX idx_strategy_versions_semantic_fingerprint ON strategy_versions (semantic_fingerprint);

-- artifact_record_fingerprint MAY be uniquely constrained (item 6: "your
-- call, justify it"). Justification: artifact_record_fingerprint binds
-- strategy_version_id + provenance + finalised_at_utc (PID-004 sec38) --
-- for it to collide across two rows, a second finalisation would have to
-- reproduce not only the identical semantics but the identical
-- strategy_version_id, provenance, and finalisation instant of an
-- existing row, which never happens under normal operation (each
-- finalisation mints a fresh strategy_version_id). A genuine collision
-- can only mean an accidental duplicate INSERT of the exact same record --
-- exactly the case a UNIQUE constraint should catch as a safety net,
-- never a legitimate second research record. Multiple NULLs (rows written
-- by the pre-existing narrow StrategyVersionRepository, which never
-- populates this column) remain permitted -- Postgres UNIQUE treats NULL
-- as distinct from NULL.
ALTER TABLE strategy_versions
    ADD CONSTRAINT uq_strategy_versions_artifact_record_fingerprint UNIQUE (artifact_record_fingerprint);

-- Item 7: REAL immutability enforcement, not just an unread BOOLEAN flag.
-- Once a strategy_versions row is inserted, no UPDATE or DELETE against
-- it may succeed, from any caller -- application code, another persona's
-- ad hoc SQL, or a future forgetful repository method -- not just because
-- no repository method here exposes one. Migration/admin paths remain
-- possible only through separately-governed DB migration mechanics
-- (a superuser could still `ALTER TABLE ... DISABLE TRIGGER`), which is
-- exactly the carve-out PID-004A's own persistence directive item 7
-- anticipates ("Migration/admin paths may still exist through
-- separately-governed DB migration mechanics -- ordinary application
-- operation must not be able to bypass this").
CREATE OR REPLACE FUNCTION reject_strategy_version_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'strategy_versions rows are immutable once inserted (PID-004 sec4.4/sec33): % on id=%',
        TG_OP, OLD.id
        USING ERRCODE = 'raise_exception';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_strategy_versions_immutable
    BEFORE UPDATE OR DELETE ON strategy_versions
    FOR EACH ROW EXECUTE FUNCTION reject_strategy_version_mutation();

-- ---------------------------------------------------------------------------
-- 2. Data requirement projection (item 8): derived transactionally at
--    finalisation time, FK'd back to the StrategyVersion, never
--    independently editable. Immutability enforced the same real way as
--    strategy_versions (item 7's discipline applied here too, since item 8
--    demands "never independently editable" as a hard invariant, not a
--    convention).
-- ---------------------------------------------------------------------------

CREATE TABLE strategy_version_data_requirements (
    id                          UUID PRIMARY KEY,
    strategy_version_id         UUID NOT NULL REFERENCES strategy_versions(id),
    requirement_id              TEXT NOT NULL,
    display_name                TEXT NOT NULL,
    fact_class                  TEXT NOT NULL
        CHECK (fact_class IN (
            'MARKET_OHLCV', 'OPTIONS_CHAIN', 'IMPLIED_VOLATILITY', 'OPEN_INTEREST',
            'FUTURES_CURVE', 'ORDER_BOOK', 'ECONOMIC_SURPRISE', 'NEWS_CONTEXT',
            'PREDICTION_MARKET', 'FUNDING_RATE', 'ON_CHAIN', 'OTHER_GOVERNED_FACT'
        )),
    fact_reference_kind         TEXT NOT NULL
        CHECK (fact_reference_kind IN ('CANONICAL_FACT_REFERENCE', 'SPECIFICATION_DERIVED_FACT')),
    authority_class             TEXT NOT NULL
        CHECK (authority_class IN (
            'HERMES_CANONICAL_MARKET', 'ARES_GOVERNED_CONTEXT', 'OPTIONS_AUTHORITY',
            'FUTURES_AUTHORITY', 'OTHER_GOVERNED_AUTHORITY'
        )),
    instrument_applicability    JSONB NOT NULL DEFAULT '[]'::jsonb,
    timeframe_code               TEXT NULL,
    historical_depth_count        INTEGER NOT NULL,
    historical_depth_unit           TEXT NOT NULL CHECK (historical_depth_unit IN ('BARS', 'DAYS', 'YEARS')),
    units                             TEXT NULL,
    required_fields                    JSONB NOT NULL,
    causal_timing_policy                  TEXT NOT NULL
        CHECK (causal_timing_policy IN (
            'NOT_APPLICABLE', 'ORIGINAL_PUBLISHED_VALUE_ONLY', 'LATEST_CAUSALLY_AVAILABLE_REVISION'
        )),
    mandatory                              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at_utc                           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- requirement_id is unique WITHIN one StrategyVersion (item 16); the
    -- same requirement_id spelling may legitimately recur across
    -- different StrategyVersions.
    UNIQUE (strategy_version_id, requirement_id)
);

CREATE INDEX idx_svdr_strategy_version_id ON strategy_version_data_requirements (strategy_version_id);
CREATE INDEX idx_svdr_fact_class ON strategy_version_data_requirements (fact_class);
CREATE INDEX idx_svdr_authority_class ON strategy_version_data_requirements (authority_class);

CREATE OR REPLACE FUNCTION reject_data_requirement_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'strategy_version_data_requirements rows are never independently editable (PID-004 sec8): % on id=%',
        TG_OP, OLD.id
        USING ERRCODE = 'raise_exception';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_svdr_immutable
    BEFORE UPDATE OR DELETE ON strategy_version_data_requirements
    FOR EACH ROW EXECUTE FUNCTION reject_data_requirement_mutation();

-- ---------------------------------------------------------------------------
-- 3. Data readiness assessments (item 9): append-only, multiple per
--    StrategyVersion allowed. Per-requirement rows must FK to genuine
--    requirements belonging to THAT StrategyVersion -- enforced here with
--    a real composite-key constraint, not just application-level care.
-- ---------------------------------------------------------------------------

CREATE TABLE data_readiness_assessments (
    id                          UUID PRIMARY KEY,
    strategy_version_id         UUID NOT NULL REFERENCES strategy_versions(id),
    assessed_at_utc              TIMESTAMPTZ NOT NULL,
    overall_state                 TEXT NOT NULL CHECK (overall_state IN ('TESTABLE', 'DATA_BLOCKED')),
    mandatory_requirement_ids       JSONB NOT NULL,
    created_at_utc                    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Composite unique target so a per-requirement row (below) can be
    -- FK-pinned to (this exact assessment, this exact strategy_version_id)
    -- at once -- never just the assessment id alone.
    UNIQUE (id, strategy_version_id)
);

CREATE INDEX idx_dra_strategy_version_id ON data_readiness_assessments (strategy_version_id);

CREATE TABLE data_readiness_assessment_requirements (
    id                          UUID PRIMARY KEY,
    assessment_id                UUID NOT NULL,
    strategy_version_id           UUID NOT NULL,
    requirement_id                  TEXT NOT NULL,
    availability                      TEXT NOT NULL
        CHECK (availability IN (
            'AVAILABLE', 'UNAVAILABLE', 'INSUFFICIENT_HISTORY', 'INSUFFICIENT_RESOLUTION',
            'AUTHORITY_NOT_ONBOARDED', 'CONTRACT_INCOMPATIBLE', 'UNKNOWN'
        )),
    reason                              TEXT NULL,
    created_at_utc                        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- (assessment_id, strategy_version_id) must be a genuine assessment row.
    FOREIGN KEY (assessment_id, strategy_version_id)
        REFERENCES data_readiness_assessments (id, strategy_version_id),
    -- (strategy_version_id, requirement_id) must be a genuine requirement
    -- belonging to THAT SAME StrategyVersion. Together these two composite
    -- FKs make it structurally impossible to record readiness for a
    -- requirement that belongs to a different StrategyVersion than the
    -- one this row's own assessment is against -- there is no path that
    -- lets strategy_version_id disagree between the two FK targets while
    -- both still resolve.
    FOREIGN KEY (strategy_version_id, requirement_id)
        REFERENCES strategy_version_data_requirements (strategy_version_id, requirement_id),
    UNIQUE (assessment_id, requirement_id)
);

CREATE INDEX idx_drar_assessment_id ON data_readiness_assessment_requirements (assessment_id);
CREATE INDEX idx_drar_strategy_version_id ON data_readiness_assessment_requirements (strategy_version_id);

-- ---------------------------------------------------------------------------
-- 4. Shelving (item 10): auditable append-only event/history table,
--    entirely separate from strategy_versions/fingerprints/DataRequirements
--    -- structurally incapable of touching any of them (no FK/trigger
--    anywhere links this table's rows back into mutating those tables; it
--    only ever reads a strategy_version_id to attach to).
-- ---------------------------------------------------------------------------

CREATE TABLE strategy_version_shelving_events (
    id                          UUID PRIMARY KEY,
    strategy_version_id         UUID NOT NULL REFERENCES strategy_versions(id),
    state                        TEXT NOT NULL CHECK (state IN ('SHELVED', 'UNSHELVED')),
    reason                        TEXT NULL,
    actor                           TEXT NULL,
    occurred_at_utc                   TIMESTAMPTZ NOT NULL,
    created_at_utc                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_svse_strategy_version_id ON strategy_version_shelving_events (strategy_version_id);

-- ---------------------------------------------------------------------------
-- 5. Validation records (item 11): a refused draft is durably
--    representable and creates NO StrategyVersion -- enforced here with a
--    real CHECK, not just application discipline.
-- ---------------------------------------------------------------------------

CREATE TABLE specification_validation_records (
    id                          UUID PRIMARY KEY,
    draft_id                     UUID NOT NULL REFERENCES specification_drafts(id),
    draft_revision                 INTEGER NOT NULL,
    assessed_at_utc                  TIMESTAMPTZ NOT NULL,
    status                             TEXT NOT NULL CHECK (status IN ('VALID', 'STRATEGY_NOT_SUFFICIENTLY_DEFINED')),
    findings                             JSONB NOT NULL DEFAULT '[]'::jsonb,
    strategy_version_id                    UUID NULL REFERENCES strategy_versions(id),
    created_at_utc                           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A refused draft creates NO StrategyVersion (PID-004 sec33/sec35 --
    -- this is the direction that is always safe to enforce at the DB
    -- layer; a VALID validate_draft() outcome may legitimately exist
    -- without a StrategyVersion yet if a caller only validated without
    -- finalising, so the reverse direction is deliberately NOT enforced
    -- here).
    CHECK (status <> 'STRATEGY_NOT_SUFFICIENTLY_DEFINED' OR strategy_version_id IS NULL)
);

CREATE INDEX idx_svr_draft_id ON specification_validation_records (draft_id);
CREATE INDEX idx_svr_strategy_version_id ON specification_validation_records (strategy_version_id);
