-- PID-006A Shared Research/Proof Contracts -- durable persistence for the
-- immutable configuration/governance artifacts modelled in
-- darwin.research_contracts (docs/pids/PID-006-APOLLO.md sec5/sec35).
--
-- Additive only -- this migration never rewrites 0001-0011, never drops
-- or retypes an existing column, never touches an existing row's data.
-- All five tables below are genuinely new (mirrors migration 0009/0011's
-- own note); 02_grant_app_table_privileges.sql is extended separately
-- (existence-conditional, same discipline as before) to grant darwin_app
-- access once they exist.
--
-- Scope boundary (PID-006A sec12/sec14, load-bearing): this migration
-- does NOT touch `research_runs` or any other existing table -- Foundation's
-- ResearchRun remains entirely untouched, and none of the five tables
-- below is wired into it (that integration is PID-006B's job). This
-- migration does NOT add any APOLLO trade table, proof-result table,
-- order/fill/position/ledger/equity table, HMT-2 table, or ATHENA
-- experiment/cell table -- every table here records IDENTITY only:
-- exactly the immutable configuration under which a future proof would be
-- requested, never a result, a trade, or a replay.
--
-- Identity-model judgment call (flagged for the Architect/auditor, not
-- silently resolved -- mirrors the identical judgment call migration 0006
-- already recorded for strategy_candidates.id/strategy_versions.id):
-- `source_strategy_version_id` below is plain TEXT, deliberately NOT a
-- foreign key to strategy_versions(id). darwin.specification's own
-- StrategyVersion domain objects only require a non-empty governed string
-- id (tests/contract fixtures use plain strings like "fixture-01"), and
-- PID-006A's own required tests exercise ExecutableStrategyPlan/
-- ParameterSetVersion/ResearchConfiguration against such fixtures without
-- ever requiring the source StrategyVersion to already be a persisted
-- database row. The REAL bound identity everywhere in this migration is
-- always the semantic/content FINGERPRINT column (TEXT, never null),
-- never the source id -- an FK here would wrongly force every research
-- contract in this schema to first persist a real strategy_versions row,
-- which this work package does not require and does not implement.
--
-- Immutability discipline (PID-006A sec15): every table below is a named
-- **Version** artifact for a reason -- persistence never offers an
-- ordinary "edit this version in place" path. Two independent layers of
-- defence, both applied to every table:
--   1. 02_grant_app_table_privileges.sql grants darwin_app only SELECT,
--      INSERT -- no UPDATE, no DELETE.
--   2. The shared `reject_research_contract_mutation()` trigger function
--      below rejects every UPDATE/DELETE outright, independent of grants
--      -- mirrors migration 0011's `trg_mendel_proposals_content_immutable`
--      precedent, simplified to a blanket reject (these records have no
--      legitimate mutable lifecycle column at all, unlike mendel_proposals'
--      status/resolved_at_utc).
--
-- Duplicate-identity insert behaviour (Required tests: "duplicate-identity
-- insert behaviour is deterministic/idempotent"): every table's own
-- content-addressed `fingerprint` column is UNIQUE, and
-- darwin.research_store.research_contracts_repositories' create() methods
-- use `INSERT ... ON CONFLICT (fingerprint) DO NOTHING RETURNING *` (the
-- same idiom migration 0010's StrategyCandidateRepository.
-- get_or_create_for_discovery already established), falling back to a
-- plain SELECT by fingerprint when the row already existed -- a repeated
-- create() of an identical artifact is a deterministic no-op that returns
-- the existing row, never a duplicate, never an error.

-- ============================================================================
-- 1. compiled_strategy_plans -- ExecutableStrategyPlan (PID-006A sec3/sec5).
-- ============================================================================
--
-- Derived evidence, not new authority (PID-006A sec16): `source_semantic_
-- fingerprint` is always StrategyVersion.semantic_fingerprint, so a
-- persisted plan can never outlive or contradict the StrategyVersion it
-- was compiled from -- StrategyVersion remains the canonical strategy
-- semantic authority everywhere in DARWIN.

CREATE TABLE compiled_strategy_plans (
    id                              UUID PRIMARY KEY,
    source_strategy_version_id      TEXT NOT NULL,
    source_semantic_fingerprint     TEXT NOT NULL,
    compiler_id                     TEXT NOT NULL,
    compiler_version                TEXT NOT NULL,
    plan_schema_version             TEXT NOT NULL,
    semantic_payload                JSONB NOT NULL,
    fingerprint                     TEXT NOT NULL,
    created_at_utc                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (fingerprint)
);

CREATE INDEX idx_compiled_strategy_plans_source_fingerprint
    ON compiled_strategy_plans (source_semantic_fingerprint);

-- ============================================================================
-- 2. parameter_set_versions -- ParameterSetVersion (PID-006A sec6).
-- ============================================================================

CREATE TABLE parameter_set_versions (
    id                              UUID PRIMARY KEY,
    source_strategy_version_id      TEXT NOT NULL,
    source_semantic_fingerprint     TEXT NOT NULL,
    assignments                     JSONB NOT NULL,
    fingerprint                     TEXT NOT NULL,
    created_at_utc                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (fingerprint)
);

CREATE INDEX idx_parameter_set_versions_source_fingerprint
    ON parameter_set_versions (source_semantic_fingerprint);

-- ============================================================================
-- 3. execution_policy_versions -- ExecutionPolicyVersion (PID-006A sec7/sec8).
-- ============================================================================
--
-- Every one of the six mandatory identity axes is its own NOT NULL JSONB
-- column -- there is no nullable axis column anywhere on this table,
-- which is itself a second, independent (database-level) enforcement of
-- "absence never means a default" alongside the Python-level
-- ExecutionPolicyIncompleteError check in
-- darwin.research_contracts.execution_policy.build_execution_policy_version.

CREATE TABLE execution_policy_versions (
    id                                      UUID PRIMARY KEY,
    timing_methodology                      JSONB NOT NULL,
    price_fill_methodology                  JSONB NOT NULL,
    intrabar_resolution_methodology         JSONB NOT NULL,
    cost_methodology                        JSONB NOT NULL,
    quantity_economic_methodology           JSONB NOT NULL,
    session_force_flat_methodology          JSONB NOT NULL,
    fingerprint                             TEXT NOT NULL,
    created_at_utc                          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (fingerprint)
);

-- ============================================================================
-- 4. research_partition_policy_versions -- ResearchPartitionPolicyVersion
--    (PID-006A sec9).
-- ============================================================================
--
-- `input_binding` stores the FULL ResearchInputBinding payload (role,
-- kind, governed dataset identity, dataset fingerprint, its own
-- fingerprint) inline as JSONB, rather than a separate join table --
-- PID-006A sec9/sec10 requires only that a partition role bind to a
-- specific governed input identity, never that the binding be
-- independently queryable/reusable across multiple partition policies in
-- this work package; a separate `research_input_bindings` table is not
-- required by any of PID-006A's expected durable concepts and was not
-- added (kept close to the exact five expected table names PID-006A
-- sec14 lists).

CREATE TABLE research_partition_policy_versions (
    id                              UUID PRIMARY KEY,
    role                             TEXT NOT NULL
        CHECK (role IN ('DEVELOPMENT', 'VALIDATION', 'PROTECTED_HOLDOUT')),
    input_binding                   JSONB NOT NULL,
    fingerprint                     TEXT NOT NULL,
    created_at_utc                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (fingerprint)
);

CREATE INDEX idx_research_partition_policy_versions_role
    ON research_partition_policy_versions (role);

-- ============================================================================
-- 5. research_configurations -- ResearchConfiguration (PID-006A sec11).
-- ============================================================================
--
-- Every axis is recorded by its OWN fingerprint column (never a single
-- opaque blob) so "strategy/parameter/policy/partition/input identities
-- remain independent axes" (Required tests) is true at the persistence
-- layer too, not only in the in-memory dataclass. `research_input_
-- bindings` is the JSONB array of bound input fingerprints (sorted, same
-- canonical ordering the in-memory fingerprint computation uses).
--
-- DIKE identity binding mirrors the EXISTING research_runs discipline
-- (migration 0004_dike_policy_binding.sql) exactly: DIKE_DISABLED carries
-- no policy identity, DIKE_GUARDED must carry one -- enforced here at the
-- database level too, independent of
-- darwin.research_contracts.research_configuration.build_research_configuration's
-- own Python-level DikePolicyBindingError check.

CREATE TABLE research_configurations (
    id                                          UUID PRIMARY KEY,
    configuration_schema_version                TEXT NOT NULL,
    strategy_semantic_fingerprint                TEXT NOT NULL,
    executable_strategy_plan_fingerprint         TEXT NOT NULL,
    parameter_set_fingerprint                    TEXT NOT NULL,
    instrument_definition_id                     TEXT NOT NULL,
    instrument_definition_fingerprint            TEXT NOT NULL,
    research_input_bindings                      JSONB NOT NULL,
    research_partition_policy_fingerprint        TEXT NOT NULL,
    execution_policy_fingerprint                  TEXT NOT NULL,
    dike_state                                    TEXT NOT NULL
        CHECK (dike_state IN ('DIKE_DISABLED', 'DIKE_GUARDED')),
    dike_policy_fingerprint                       TEXT NULL,
    required_derived_algorithm_identities         JSONB NOT NULL DEFAULT '[]'::jsonb,
    fingerprint                                   TEXT NOT NULL,
    created_at_utc                                 TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (fingerprint),
    CHECK (
        (dike_state = 'DIKE_DISABLED' AND dike_policy_fingerprint IS NULL)
        OR (dike_state = 'DIKE_GUARDED' AND dike_policy_fingerprint IS NOT NULL)
    )
);

CREATE INDEX idx_research_configurations_strategy_fingerprint
    ON research_configurations (strategy_semantic_fingerprint);

-- ============================================================================
-- 6. Immutability backstop -- one shared trigger function, five triggers.
-- ============================================================================
--
-- None of these five tables has any legitimate mutable lifecycle column
-- (unlike, e.g., migration 0011's mendel_runs/mendel_proposals, which
-- legitimately transition status in place) -- every column on every one
-- of these rows is fixed at insert time. The backstop is therefore a flat
-- reject of both UPDATE and DELETE, not a column-by-column comparison.

CREATE OR REPLACE FUNCTION reject_research_contract_mutation() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            '% rows are immutable Version records (PID-006A): DELETE on id=% is not permitted',
            TG_TABLE_NAME, OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;

    RAISE EXCEPTION
        '% rows are immutable Version records (PID-006A): UPDATE on id=% is not permitted -- '
        'a material change must create a new row with a new fingerprint, never rewrite this one',
        TG_TABLE_NAME, OLD.id
        USING ERRCODE = 'raise_exception';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_compiled_strategy_plans_immutable
    BEFORE UPDATE OR DELETE ON compiled_strategy_plans
    FOR EACH ROW EXECUTE FUNCTION reject_research_contract_mutation();

CREATE TRIGGER trg_parameter_set_versions_immutable
    BEFORE UPDATE OR DELETE ON parameter_set_versions
    FOR EACH ROW EXECUTE FUNCTION reject_research_contract_mutation();

CREATE TRIGGER trg_execution_policy_versions_immutable
    BEFORE UPDATE OR DELETE ON execution_policy_versions
    FOR EACH ROW EXECUTE FUNCTION reject_research_contract_mutation();

CREATE TRIGGER trg_research_partition_policy_versions_immutable
    BEFORE UPDATE OR DELETE ON research_partition_policy_versions
    FOR EACH ROW EXECUTE FUNCTION reject_research_contract_mutation();

CREATE TRIGGER trg_research_configurations_immutable
    BEFORE UPDATE OR DELETE ON research_configurations
    FOR EACH ROW EXECUTE FUNCTION reject_research_contract_mutation();
