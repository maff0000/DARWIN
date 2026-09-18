-- PID-004A adversarial-audit fix #1: finalisation idempotency per
-- (draft_id, draft_revision).
--
-- The bug: `finalise_specification_draft` (darwin.research_store.
-- specification_finalisation) row-locks the SpecificationDraft, checks
-- `revision == expected_revision`, and on success inserts a
-- StrategyVersion -- but nothing anywhere records that THIS EXACT draft
-- revision was already successfully finalised. A second caller with the
-- same draft_id/expected_revision (a concurrent request, or a retried/
-- double-submitted one) could create a SECOND StrategyVersion for the
-- same logical finalisation event.
--
-- Deliberately NOT fixed by bumping specification_drafts.revision on
-- finalisation: revision means authoring/content revision (PID-004A
-- persistence directive item 4). Finalising does not change the draft's
-- content, so it must not look like it did -- editing the draft's
-- content is what legitimately advances revision (1->2), and revision 2
-- must remain free to finalise into a genuinely NEW StrategyVersion.
--
-- Required invariant enforced here at the DATABASE layer (the real
-- backstop, not just application-level care -- see
-- darwin.research_store.specification_finalisation for the
-- check-then-act application logic this constraint backs up): a
-- particular (draft_id, draft_revision) pair may create AT MOST ONE
-- StrategyVersion. A later, genuinely edited revision may create
-- another.

-- source_draft_revision travels alongside the existing source_draft_id
-- column (added by 0006) -- nullable for the same reason source_draft_id
-- itself is nullable (legacy/Foundation StrategyVersion rows created
-- outside the PID-004A draft/finalisation flow have no draft origin at
-- all, and must stay unconstrained).
ALTER TABLE strategy_versions
    ADD COLUMN source_draft_revision INTEGER NULL;

-- Partial unique index: only enforced when source_draft_id IS NOT NULL.
-- Legacy/Foundation rows (source_draft_id NULL, source_draft_revision
-- NULL) are explicitly exempt -- Postgres would treat every NULL as
-- distinct under a plain UNIQUE constraint anyway, but the explicit WHERE
-- clause makes the intent unambiguous and matches the same discipline
-- already used for artifact_record_fingerprint in 0006.
CREATE UNIQUE INDEX uq_strategy_versions_source_draft_revision
    ON strategy_versions (source_draft_id, source_draft_revision)
    WHERE source_draft_id IS NOT NULL;
