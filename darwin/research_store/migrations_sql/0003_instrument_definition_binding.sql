-- Amendment A-002: time/instrument unit semantics (PID-001 §1b/§16/§22).
-- market_datasets and research_runs must carry instrument_definition_id as
-- an explicit durable fact -- the InstrumentDefinition identity under which
-- a dataset's/run's prices are interpreted, not merely the bare instrument
-- string. No persistent DARWIN deployment has ever existed (confirmed: no
-- persistent darwin_core/darwin_sql containers exist on this host, and PR #2
-- is unmerged), so both tables are guaranteed empty at this point and
-- NOT NULL can be added directly without a backfill step, same reasoning as
-- migration 0002.

ALTER TABLE market_datasets
    ADD COLUMN instrument_definition_id TEXT;

ALTER TABLE market_datasets
    ALTER COLUMN instrument_definition_id SET NOT NULL;

ALTER TABLE research_runs
    ADD COLUMN instrument_definition_id TEXT;

ALTER TABLE research_runs
    ALTER COLUMN instrument_definition_id SET NOT NULL;
