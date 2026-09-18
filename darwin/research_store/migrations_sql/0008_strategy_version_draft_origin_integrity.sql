-- PID-004A Specification Contract persistence closure: source-draft
-- identity integrity for `strategy_versions.source_draft_id` /
-- `.source_draft_revision` (both added by 0006/0007).
--
-- Today the two columns can independently be NULL/non-NULL in any
-- combination -- nothing at the database layer enforces that they always
-- travel together. This migration constrains them to exactly:
--
--   (source_draft_id IS NULL AND source_draft_revision IS NULL)
--       -- legacy/Foundation rows, created outside the PID-004A draft/
--       -- finalisation flow entirely.
--   OR
--   (source_draft_id IS NOT NULL AND source_draft_revision IS NOT NULL
--    AND source_draft_revision >= 1)
--       -- PID-004A rows, created by
--       -- darwin.research_store.specification_finalisation, which always
--       -- supplies both together (see
--       -- darwin.research_store.specification_repositories.
--       -- SpecificationVersionRepository.create()'s own
--       -- `_validate_draft_origin_pair` guard -- the same invariant
--       -- enforced there, in application code, BEFORE any row reaches
--       -- this constraint at all -- defence in depth, not a substitute
--       -- for it).
--
-- Deliberately NOT a rewrite of 0007's already-accepted partial unique
-- index (`uq_strategy_versions_source_draft_revision`) -- this is an
-- independent, additive CHECK constraint over the pairing of the two
-- columns; 0007's index still separately enforces that a given
-- (source_draft_id, source_draft_revision) pair identifies at most one
-- row.
--
-- ---------------------------------------------------------------------------
-- Forward-safety: this migration must remain safe to apply to a database
-- that already ran 0006/0007 and contains `strategy_versions` rows
-- created by the OLD, pre-remediation finalisation code -- rows that
-- legitimately have `source_draft_id IS NOT NULL` while
-- `source_draft_revision IS NULL` (the idempotency column did not exist
-- yet when those rows were inserted, if any such rows exist at all: this
-- host has never had a persistent DARWIN deployment reach 0006/0007
-- through the old code, so in practice this block is a no-op every time
-- it runs here -- but it must still be correct against a hypothetical
-- environment where it is not).
--
-- Before the CHECK constraint is added, BACKFILL `source_draft_revision`
-- for every such row -- but ONLY when the correct value can be
-- deterministically established: look up `specification_validation_
-- records` for a row with the SAME `strategy_version_id` (via its own FK
-- to `strategy_versions(id)`) AND the SAME `draft_id` (matching this
-- row's `source_draft_id`), with `status = 'VALID'`. If EXACTLY ONE such
-- record exists, backfill its `draft_revision`. If zero or more than one
-- candidate exists (ambiguous -- there is no single correct answer to
-- guess), this migration FAILS LOUDLY (raises, aborting the whole
-- migration transaction -- `darwin.research_store.migrations.
-- run_migrations` rolls back on any exception) rather than guessing or
-- leaving the row unconstrained. Only once every affected row has been
-- either successfully backfilled or the migration has already aborted
-- does the CHECK constraint get added.
--
-- The backfill UPDATE below is, itself, a real mutation of an
-- already-inserted `strategy_versions` row -- which 0006's own
-- `trg_strategy_versions_immutable` trigger exists specifically to
-- reject, from ANY caller, including this one. 0006's header comment
-- already anticipated exactly this carve-out ("Migration/admin paths may
-- still exist through separately-governed DB migration mechanics ...
-- ordinary application operation must not be able to bypass this") --
-- this migration only ever runs under governed migrator/owner authority
-- (`darwin.research_store.migrations.run_migrations`), never under the
-- restricted application role, so temporarily disabling the trigger here
-- is exactly that anticipated, governed path, not a weakening of it.
-- `ALTER TABLE ... {DIS,EN}ABLE TRIGGER` is itself transactional DDL: if
-- the backfill loop below raises (the ambiguous-data case), the whole
-- migration -- including the DISABLE -- rolls back together, so a failed
-- attempt never leaves the trigger disabled.
-- ---------------------------------------------------------------------------

ALTER TABLE strategy_versions DISABLE TRIGGER trg_strategy_versions_immutable;

DO $$
DECLARE
    affected_row       RECORD;
    candidate_count     INTEGER;
    backfill_revision    INTEGER;
BEGIN
    FOR affected_row IN
        SELECT id, source_draft_id
        FROM strategy_versions
        WHERE source_draft_id IS NOT NULL AND source_draft_revision IS NULL
        ORDER BY id
    LOOP
        SELECT count(*), max(draft_revision)
          INTO candidate_count, backfill_revision
          FROM specification_validation_records
          WHERE strategy_version_id = affected_row.id
            AND draft_id = affected_row.source_draft_id
            AND status = 'VALID';

        IF candidate_count <> 1 THEN
            RAISE EXCEPTION
                'migration 0008: cannot deterministically backfill '
                'strategy_versions.source_draft_revision for id=% '
                '(source_draft_id=%) -- found % candidate VALID '
                'specification_validation_records for (strategy_version_id, '
                'draft_id), expected exactly 1; refusing to guess',
                affected_row.id, affected_row.source_draft_id, candidate_count
                USING ERRCODE = 'raise_exception';
        END IF;

        UPDATE strategy_versions
        SET source_draft_revision = backfill_revision
        WHERE id = affected_row.id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Only reached once the DO block above completed without raising --
-- restore real immutability enforcement before this migration finishes.
ALTER TABLE strategy_versions ENABLE TRIGGER trg_strategy_versions_immutable;

-- Only reached once every affected row above was either successfully
-- backfilled, or the DO block already raised and aborted the migration.
ALTER TABLE strategy_versions
    ADD CONSTRAINT ck_strategy_versions_draft_origin_integrity
    CHECK (
        (source_draft_id IS NULL AND source_draft_revision IS NULL)
        OR
        (source_draft_id IS NOT NULL AND source_draft_revision IS NOT NULL
         AND source_draft_revision >= 1)
    );
