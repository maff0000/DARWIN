-- PID-006B XAUUSD Candle Causal Core -- adds the new APOLLO_RESULT
-- evidence level to the closed CHECK-constraint vocabularies on
-- research_runs.result_kind and evidence_records.evidence_level
-- (both originally defined in 0001_foundation.sql).
--
-- Narrow, explicitly authorised schema change (Architect's own words:
-- "Make only the narrow enum/schema/API/frontend compatibility changes
-- required for this new evidence value"). Never touches existing row
-- data, never rewrites APOLLO_PROOF's own meaning, never adds a new
-- table -- purely widens two existing CHECK constraints to also accept
-- 'APOLLO_RESULT'.
--
-- Postgres has no ALTER TABLE ... ALTER CONSTRAINT for a CHECK's own
-- expression -- the constraint must be dropped and re-added. Both
-- constraints here were created inline (unnamed) by 0001_foundation.sql,
-- so Postgres assigned them its own default names
-- (<table>_<column>_check) -- those are the exact names dropped below.

ALTER TABLE research_runs
    DROP CONSTRAINT research_runs_result_kind_check;

ALTER TABLE research_runs
    ADD CONSTRAINT research_runs_result_kind_check
    CHECK (result_kind IN ('SOURCE_CLAIM', 'ATHENA_RESULT', 'APOLLO_PROOF', 'APOLLO_RESULT', 'PLUTUS_RESULT'));

ALTER TABLE evidence_records
    DROP CONSTRAINT evidence_records_evidence_level_check;

ALTER TABLE evidence_records
    ADD CONSTRAINT evidence_records_evidence_level_check
    CHECK (evidence_level IN ('SOURCE_CLAIM', 'ATHENA_RESULT', 'APOLLO_PROOF', 'APOLLO_RESULT', 'PLUTUS_RESULT'));
