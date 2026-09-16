-- DARWIN Foundation schema (PID-001 §22).
-- Control/evidence/research metadata only. DARWIN must not duplicate HERMES
-- market history here — market_datasets stores metadata/fingerprint, never
-- candle rows.

CREATE TABLE source_strategies (
    id                  UUID PRIMARY KEY,
    source_type         TEXT NOT NULL,
    source_reference    TEXT NOT NULL,
    title               TEXT NOT NULL,
    provenance          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE strategy_candidates (
    id                  UUID PRIMARY KEY,
    source_strategy_id  UUID NULL REFERENCES source_strategies(id),
    title               TEXT NOT NULL,
    pipeline_stage      TEXT NOT NULL DEFAULT 'DISCOVERED'
        CHECK (pipeline_stage IN (
            'DISCOVERED', 'SPECIFIED', 'ATHENA_TESTED',
            'ATHENA_QUALIFIED', 'APOLLO_PROVEN', 'PROMISING'
        )),
    created_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_strategy_candidates_pipeline_stage ON strategy_candidates (pipeline_stage);

CREATE TABLE strategy_versions (
    id                          UUID PRIMARY KEY,
    candidate_id                UUID NOT NULL REFERENCES strategy_candidates(id),
    version_label                TEXT NOT NULL,
    specification_fingerprint   TEXT NULL,
    is_immutable                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at_utc              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (candidate_id, version_label)
);

-- Dataset METADATA/fingerprint only. HERMES remains the sole market-history
-- authority; candle arrays are regenerable from HERMES if only this row is kept.
CREATE TABLE market_datasets (
    id                          UUID PRIMARY KEY,
    instrument                  TEXT NOT NULL,
    timeframe                   TEXT NOT NULL,
    requested_start_utc         TIMESTAMPTZ NOT NULL,
    requested_end_utc           TIMESTAMPTZ NOT NULL,
    actual_first_open_utc       TIMESTAMPTZ NULL,
    actual_last_open_utc        TIMESTAMPTZ NULL,
    record_count                INTEGER NOT NULL,
    fingerprint_sha256          TEXT NOT NULL,
    hermes_contract_version     TEXT NOT NULL,
    hermes_contract_commit      TEXT NOT NULL,
    adapter_build_version       TEXT NOT NULL,
    gap_summary                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    loaded_at_utc                TIMESTAMPTZ NOT NULL,
    created_at_utc               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_market_datasets_instrument_timeframe ON market_datasets (instrument, timeframe);
CREATE INDEX idx_market_datasets_fingerprint ON market_datasets (fingerprint_sha256);

CREATE TABLE research_runs (
    id                          UUID PRIMARY KEY,
    result_kind                 TEXT NOT NULL
        CHECK (result_kind IN ('SOURCE_CLAIM', 'ATHENA_RESULT', 'APOLLO_PROOF', 'PLUTUS_RESULT')),
    engine                      TEXT NOT NULL,
    build_version                TEXT NOT NULL,
    status                       TEXT NOT NULL,
    candidate_id                 UUID NULL REFERENCES strategy_candidates(id),
    version_id                   UUID NULL REFERENCES strategy_versions(id),
    dataset_id                   UUID NULL REFERENCES market_datasets(id),
    configuration_fingerprint    TEXT NULL,
    created_at_utc                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_research_runs_result_kind ON research_runs (result_kind);
CREATE INDEX idx_research_runs_status ON research_runs (status);

CREATE TABLE evidence_records (
    id                  UUID PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES research_runs(id),
    evidence_level      TEXT NOT NULL
        CHECK (evidence_level IN ('SOURCE_CLAIM', 'ATHENA_RESULT', 'APOLLO_PROOF', 'PLUTUS_RESULT')),
    reference           TEXT NOT NULL,
    created_at_utc       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_records_run_id ON evidence_records (run_id);
