-- Amendment A-003: DIKE deterministic capital-protection identity substrate
-- (PID.md sec5.12/sec22b, PID-001 sec1d). research_runs must carry an
-- explicit DIKE state plus policy identity -- present only when guarded,
-- absent only when disabled, never ambiguous. No persistent DARWIN
-- deployment has ever existed (confirmed: no persistent darwin_core/
-- darwin_sql containers exist on this host, and PR #2 is unmerged), so
-- research_runs is guaranteed empty at this point and NOT NULL can be
-- added directly for dike_state without a backfill step, same reasoning
-- as migrations 0002/0003. dike_policy_id/version/fingerprint stay
-- nullable at the column level -- the absence/presence invariant is
-- enforced by application code (darwin.research_store.run_binding.
-- create_research_run) and reinforced here by a CHECK constraint as
-- defence in depth, rather than a NOT NULL that would forbid the
-- DIKE_DISABLED case entirely.

ALTER TABLE research_runs
    ADD COLUMN dike_state TEXT,
    ADD COLUMN dike_policy_id TEXT,
    ADD COLUMN dike_policy_version TEXT,
    ADD COLUMN dike_policy_fingerprint TEXT;

ALTER TABLE research_runs
    ALTER COLUMN dike_state SET NOT NULL;

ALTER TABLE research_runs
    ADD CONSTRAINT dike_policy_identity_presence_matches_state CHECK (
        (dike_state = 'DIKE_DISABLED'
            AND dike_policy_id IS NULL
            AND dike_policy_version IS NULL
            AND dike_policy_fingerprint IS NULL)
        OR
        (dike_state = 'DIKE_GUARDED'
            AND dike_policy_id IS NOT NULL
            AND dike_policy_version IS NOT NULL
            AND dike_policy_fingerprint IS NOT NULL)
    );
