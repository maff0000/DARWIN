-- PID-004A adversarial-audit fix #2 (database privilege separation) --
-- `darwin_app` table-level DML grants, table by table.
--
-- Run this as darwin_owner/darwin_migrator (i.e. via a connection where
-- SET ROLE darwin_owner is already in effect) AFTER all schema migrations
-- (0001-0007+) have been applied -- every table named below must already
-- exist. Used by BOTH bootstrap paths:
--   * fresh bootstrap (item 10): run once, right after the first-ever
--     `darwin migrate` -- see 01_fresh_bootstrap_roles.sql's header.
--   * existing-volume upgrade (item 11): sourced directly from
--     03_upgrade_existing_volume_to_role_separation.sql.
--
-- Deliberately NOT `GRANT ALL PRIVILEGES` and deliberately NOT
-- `ALTER DEFAULT PRIVILEGES ... ON TABLES` (which cannot express the
-- non-uniform per-table matrix below -- most tables never get UPDATE,
-- none get DELETE or TRUNCATE anywhere). Every grant here is matched
-- against what darwin/research_store/repositories.py,
-- darwin/research_store/specification_repositories.py,
-- darwin/research_store/specification_finalisation.py, and
-- darwin/scout/*.py actually execute -- nothing more. Re-running this
-- script is always safe (plain GRANT statements are idempotent).

-- --- append-only / insert-then-read tables: SELECT + INSERT only -------
-- No UPDATE, no DELETE, no TRUNCATE. strategy_versions and
-- strategy_version_data_requirements are additionally immutability-
-- trigger-protected (migration 0006) -- lacking UPDATE/DELETE privilege
-- here is now a SECOND, independent reason a raw UPDATE/DELETE against
-- them fails, not just the trigger.
GRANT SELECT, INSERT ON TABLE
    source_strategies,
    strategy_versions,
    market_datasets,
    evidence_records,
    scout_intake_audit,
    scout_snapshots,
    scout_claims,
    strategy_candidate_discovery_links,
    strategy_candidate_lineage,
    strategy_version_data_requirements,
    data_readiness_assessments,
    data_readiness_assessment_requirements,
    strategy_version_shelving_events,
    specification_validation_records
    TO darwin_app;

-- --- tables the application legitimately mutates in place --------------
-- strategy_candidates: pipeline_stage transitions (Foundation + PID-004A
--   _advance_candidate_to_specified).
-- research_runs: status/lifecycle updates (repositories.py).
-- scout_discoveries: intake-status/claim transitions (repositories.py).
-- scout_discovery_runs: run-status updates (repositories.py).
-- specification_drafts: SpecificationDraftRepository.
--   update_with_expected_revision -- the ONLY supported draft edit path,
--   still fully covered by UPDATE here (optimistic concurrency is
--   enforced by the WHERE clause in application SQL, not by withholding
--   UPDATE privilege).
GRANT SELECT, INSERT, UPDATE ON TABLE
    strategy_candidates,
    research_runs,
    scout_discoveries,
    scout_discovery_runs,
    specification_drafts
    TO darwin_app;

-- --- read-only reference/seed data --------------------------------------
-- scout_sources is seeded exclusively by migration 0005 (governed DDL/
-- seed path, darwin_owner/darwin_migrator authority) -- the application
-- only ever looks sources up, never writes to this table.
GRANT SELECT ON TABLE scout_sources TO darwin_app;

-- schema_migrations: read-only diagnostic access ONLY (adversarial-audit
-- fix #2 item 9) -- darwin.research_store.migrations.migration_state()
-- (called by darwin_core's own /api/v1/migrations and /api/v1/ready
-- endpoints using this exact darwin_app connection) only ever SELECTs;
-- creating the table and recording newly-applied versions
-- (INSERT/CREATE TABLE) stays exclusively on the governed
-- darwin_migrator/owner path (darwin.research_store.migrations.
-- run_migrations).
GRANT SELECT ON TABLE schema_migrations TO darwin_app;

-- No sequence grants: every primary key in this schema is an
-- application-generated UUID (darwin.core.identities.new_id()) or a
-- plain TEXT natural key (schema_migrations.version) -- there is no
-- SERIAL/IDENTITY column anywhere, so no nextval() privilege is ever
-- required by darwin_app.
