-- PID-004B Strategy Workshop UI enablement: an explicit, structural
-- Discovery -> StrategyCandidate origin link.
--
-- Genuine backend gap found while building the ARENA Workshop UI (not part
-- of the original PID-004B backend contract, which never needed to CREATE
-- a StrategyCandidate via API at all -- every existing test/fixture builds
-- one directly through StrategyCandidateRepository): before this
-- migration there was NO REST endpoint anywhere in DARWIN_core capable of
-- creating a strategy_candidates row, which means ARENA's "Open Workshop"
-- button (PID-004B directive: "call POST /api/v1/workshops... idempotent
-- per-candidate") had no candidate_id to open a Workshop against at all.
--
-- This migration only ADDS a nullable column + a partial unique index to
-- the EXISTING strategy_candidates table (migration 0001) -- it never
-- rewrites 0001-0009, never drops/retypes an existing column, never
-- touches an existing row. `origin_discovery_id` is optional (a candidate
-- may still be created with no discovery origin, e.g. a future
-- combination/derivation candidate per PID-004 sec4.2) -- the partial
-- unique index only constrains rows that DO carry one, giving the new
-- `POST /api/v1/candidates` endpoint (darwin/app.py) real, DB-backed
-- idempotent get-or-create semantics per discovery -- the exact same
-- `ON CONFLICT ... DO NOTHING RETURNING *` idiom migration 0009's own
-- `WorkshopRepository.open` already uses for idempotent-open-per-candidate.

ALTER TABLE strategy_candidates
    ADD COLUMN origin_discovery_id UUID NULL REFERENCES scout_discoveries(id);

CREATE UNIQUE INDEX uq_strategy_candidates_origin_discovery
    ON strategy_candidates (origin_discovery_id)
    WHERE origin_discovery_id IS NOT NULL;

CREATE INDEX idx_strategy_candidates_origin_discovery_id
    ON strategy_candidates (origin_discovery_id);
