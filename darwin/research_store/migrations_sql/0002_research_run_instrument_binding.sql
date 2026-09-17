-- Amendment A-001: multi-instrument substrate (PID-001 §1a/§22).
-- research_runs must carry instrument/timeframe as explicit durable facts,
-- not only reachable via a join to market_datasets, plus an immutable
-- human-readable display_title. research_runs is guaranteed empty at this
-- point (no run-creation code path existed before this migration/before
-- darwin.research_store.run_binding), so NOT NULL can be added directly
-- without a backfill step.

ALTER TABLE research_runs
    ADD COLUMN instrument     TEXT,
    ADD COLUMN timeframe      TEXT,
    ADD COLUMN display_title  TEXT;

ALTER TABLE research_runs
    ALTER COLUMN instrument    SET NOT NULL,
    ALTER COLUMN timeframe     SET NOT NULL,
    ALTER COLUMN display_title SET NOT NULL;

CREATE INDEX idx_research_runs_instrument_timeframe ON research_runs (instrument, timeframe);
