-- PID-004A adversarial-audit fix #2 (database privilege separation) --
-- `darwin_app` table-level DML grants, table by table.
--
-- Run this as darwin_owner/darwin_migrator (i.e. via a connection where
-- SET ROLE darwin_owner is already in effect) -- used by BOTH bootstrap
-- paths:
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
--
-- --- Persistence-contract closure gap 2: existence-conditional grants ---
--
-- Real production right now has only migrations 0001-0005 applied.
-- Tables introduced by 0006+ (specification_drafts,
-- strategy_version_data_requirements, data_readiness_assessments,
-- data_readiness_assessment_requirements, strategy_version_
-- shelving_events, specification_validation_records,
-- strategy_candidate_discovery_links, strategy_candidate_lineage) do not
-- exist there yet -- a plain `GRANT ... ON TABLE <name> TO darwin_app`
-- against a table that does not exist fails outright, which would make
-- this script (and 03_upgrade_existing_volume_to_role_separation.sql,
-- which sources it unconditionally) unusable against the REAL current
-- live schema shape.
--
-- Fix: every GRANT below is wrapped in an explicit `to_regclass(...) IS
-- NOT NULL` existence check and skips cleanly (no error) when the table
-- does not exist yet -- this is NOT a relaxation of governance. The
-- allowlist itself is unchanged: every table name and its exact
-- privilege set is still spelled out literally below, still reviewed the
-- same way, still nowhere near `GRANT ALL` or "whatever happens to
-- exist" -- this conditional only ever changes whether an ALREADY-
-- GOVERNED grant statement executes against a schema that has not
-- reached that migration yet. When a future migration adds a new table
-- that darwin_app needs to touch, a human/FORGE must still deliberately
-- add a new entry here -- this mechanism does not do that automatically
-- and does not attempt to.
--
-- This lets the SAME script correctly serve: real live 0001-0005 today,
-- a disposable 0001-0007/0008 environment, and any future migration
-- state, without ever granting more than the literal, explicit list
-- below allows for whichever tables happen to already exist.

-- --- append-only / insert-then-read tables: SELECT + INSERT only -------
-- No UPDATE, no DELETE, no TRUNCATE. strategy_versions and
-- strategy_version_data_requirements are additionally immutability-
-- trigger-protected (migration 0006) -- lacking UPDATE/DELETE privilege
-- here is now a SECOND, independent reason a raw UPDATE/DELETE against
-- them fails, not just the trigger.
DO $$ BEGIN IF to_regclass('public.source_strategies') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE source_strategies TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.strategy_versions') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE strategy_versions TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.market_datasets') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE market_datasets TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.evidence_records') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE evidence_records TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.scout_intake_audit') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE scout_intake_audit TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.scout_snapshots') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE scout_snapshots TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.scout_claims') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE scout_claims TO darwin_app;
END IF; END $$;

-- The following six tables do not exist at all against real live
-- 0001-0005 -- these DO blocks skip cleanly there and only ever GRANT
-- once 0006 (or later) has actually been applied.
DO $$ BEGIN IF to_regclass('public.strategy_candidate_discovery_links') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE strategy_candidate_discovery_links TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.strategy_candidate_lineage') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE strategy_candidate_lineage TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.strategy_version_data_requirements') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE strategy_version_data_requirements TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.data_readiness_assessments') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE data_readiness_assessments TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.data_readiness_assessment_requirements') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE data_readiness_assessment_requirements TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.strategy_version_shelving_events') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE strategy_version_shelving_events TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.specification_validation_records') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE specification_validation_records TO darwin_app;
END IF; END $$;

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
DO $$ BEGIN IF to_regclass('public.strategy_candidates') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE strategy_candidates TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.research_runs') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE research_runs TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.scout_discoveries') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE scout_discoveries TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.scout_discovery_runs') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE scout_discovery_runs TO darwin_app;
END IF; END $$;

-- specification_drafts does not exist at real live 0001-0005 -- skips
-- cleanly there, same as the six PID-004A-only tables above.
DO $$ BEGIN IF to_regclass('public.specification_drafts') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE specification_drafts TO darwin_app;
END IF; END $$;

-- --- read-only reference/seed data --------------------------------------
-- scout_sources is seeded exclusively by migration 0005 (governed DDL/
-- seed path, darwin_owner/darwin_migrator authority) -- the application
-- only ever looks sources up, never writes to this table.
DO $$ BEGIN IF to_regclass('public.scout_sources') IS NOT NULL THEN
    GRANT SELECT ON TABLE scout_sources TO darwin_app;
END IF; END $$;

-- schema_migrations: read-only diagnostic access ONLY (adversarial-audit
-- fix #2 item 9) -- darwin.research_store.migrations.migration_state()
-- (called by darwin_core's own /api/v1/migrations and /api/v1/ready
-- endpoints using this exact darwin_app connection) only ever SELECTs;
-- creating the table and recording newly-applied versions
-- (INSERT/CREATE TABLE) stays exclusively on the governed
-- darwin_migrator/owner path (darwin.research_store.migrations.
-- run_migrations). Exists as soon as any migration has ever been run
-- (created by run_migrations itself, at every migration_state level
-- including bare 0001-0005) -- the existence check here is still
-- correct defence for the theoretical case of a database that has never
-- been migrated at all.
DO $$ BEGIN IF to_regclass('public.schema_migrations') IS NOT NULL THEN
    GRANT SELECT ON TABLE schema_migrations TO darwin_app;
END IF; END $$;

-- --- PID-004B Strategy Workshop (migration 0009) -----------------------
-- strategy_workshops/workshop_questions: the application legitimately
--   mutates these in place (status transitions, current_draft_id,
--   finalised_strategy_version_id, question resolve/withdraw) -- UPDATE is
--   granted, DELETE is not (Workshops/questions are durable history, never
--   deleted -- PID-004B: "FINALISED/ABANDONED Workshops remain durable
--   history").
-- workshop_decisions: append-only (PID-004B) -- UPDATE is granted ONLY
--   because acceptance_state/superseded_by_decision_id legitimately change
--   post-insert (the cross-reference bookkeeping a supersession performs);
--   migration 0009's own `trg_workshop_decisions_content_immutable`
--   trigger is the real backstop against a rewrite of substantive content
--   even though UPDATE privilege is granted -- same defence-in-depth shape
--   as strategy_versions' immutability trigger, just with a narrower
--   trigger (some columns updatable) rather than a blanket reject. No
--   DELETE anywhere.
-- strategy_workshop_discovery_links: append-only many-to-many -- SELECT +
--   INSERT only, same as strategy_candidate_discovery_links above.
DO $$ BEGIN IF to_regclass('public.strategy_workshops') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE strategy_workshops TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.strategy_workshop_discovery_links') IS NOT NULL THEN
    GRANT SELECT, INSERT ON TABLE strategy_workshop_discovery_links TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.workshop_questions') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE workshop_questions TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.workshop_decisions') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE workshop_decisions TO darwin_app;
END IF; END $$;

-- --- PID-004C MENDEL Workshop Assistant (migration 0011) ----------------
-- mendel_runs: the application mutates status/completed_at_utc/
--   error_classification in place (invoke_mendel's RUNNING -> terminal
--   transition) -- UPDATE is granted, DELETE is not (run history is
--   durable audit, never deleted).
-- mendel_proposals: append-only (PID-004C) -- UPDATE is granted ONLY
--   because status/resolved_at_utc/resulting_question_id/
--   resulting_decision_id legitimately change post-insert (accept/reject/
--   stale transitions); migration 0011's own
--   `trg_mendel_proposals_content_immutable` trigger is the real backstop
--   against a rewrite of substantive proposal content even though UPDATE
--   privilege is granted -- same defence-in-depth shape as
--   workshop_decisions above. No DELETE anywhere.
DO $$ BEGIN IF to_regclass('public.mendel_runs') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE mendel_runs TO darwin_app;
END IF; END $$;

DO $$ BEGIN IF to_regclass('public.mendel_proposals') IS NOT NULL THEN
    GRANT SELECT, INSERT, UPDATE ON TABLE mendel_proposals TO darwin_app;
END IF; END $$;

-- No sequence grants: every primary key in this schema is an
-- application-generated UUID (darwin.core.identities.new_id()) or a
-- plain TEXT natural key (schema_migrations.version) -- there is no
-- SERIAL/IDENTITY column anywhere, so no nextval() privilege is ever
-- required by darwin_app.
