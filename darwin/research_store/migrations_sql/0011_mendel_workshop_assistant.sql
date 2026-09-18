-- PID-004C MENDEL Workshop Assistant -- durable invocation/proposal audit
-- trail (docs/pids/PID-004C-MENDEL-WORKSHOP-ASSISTANT.md sec10), plus the
-- one narrow, separately-reviewed PID-004B schema change sec10.3 calls
-- for (widening workshop_questions.origin to add 'MENDEL').
--
-- Additive only -- this migration never rewrites 0001-0010, never drops
-- or retypes an existing column, never touches an existing row's data.
-- Both new tables here are genuinely new (mirrors migration 0009's own
-- note); 02_grant_app_table_privileges.sql is extended separately
-- (existence-conditional, same discipline as before) to grant darwin_app
-- access once they exist.

-- ============================================================================
-- 1. mendel_runs -- invocation audit (PID-004C sec10.1).
-- ============================================================================
--
-- One row per bounded MENDEL invocation. Captures reproducibility/audit
-- facts, never strategy semantics -- there is no column here that could
-- hold a proposed strategy change; that lives entirely on mendel_proposals
-- below. `status` starts 'RUNNING' (persisted BEFORE the adapter is ever
-- invoked -- darwin.workshop.mendel_service.invoke_mendel's own
-- discipline) and moves to exactly one terminal state.

CREATE TABLE mendel_runs (
    id                          UUID PRIMARY KEY,
    workshop_id                 UUID NOT NULL REFERENCES strategy_workshops(id),
    purpose                     TEXT NOT NULL
        CHECK (purpose IN (
            'ANALYSE_AMBIGUITY', 'REVIEW_DRAFT', 'SUGGEST_NEXT_QUESTIONS', 'EXPLAIN_VALIDATION',
            'PROPOSE_DATA_REQUIREMENTS', 'INTERPRET_RULE'
        )),
    focus_text                  TEXT NULL,
    context_schema_version      TEXT NOT NULL,
    context_fingerprint         TEXT NOT NULL,
    provider_identity           TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'TIMEOUT')),
    started_at_utc               TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at_utc             TIMESTAMPTZ NULL,
    error_classification         TEXT NULL,

    -- A RUNNING run must not yet claim a completion time; every terminal
    -- run must carry one (PID-004C sec10.1 / darwin.workshop.mendel_domain.
    -- MendelRun.__post_init__ enforces the identical rule in Python -- this
    -- is defence-in-depth, not the only place it is checked).
    CHECK (status = 'RUNNING' OR completed_at_utc IS NOT NULL),
    CHECK (status <> 'RUNNING' OR completed_at_utc IS NULL)
);

CREATE INDEX idx_mendel_runs_workshop_id ON mendel_runs (workshop_id);
CREATE INDEX idx_mendel_runs_status ON mendel_runs (status);

-- ============================================================================
-- 2. mendel_proposals -- the MendelProposal record (PID-004C sec6.1/sec10.2).
-- ============================================================================
--
-- `generated_against_draft_revision` binding representation (PID-004C
-- sec7.5's NO_DRAFT_YET sentinel): a nullable INTEGER revision column PLUS
-- a NOT NULL boolean flag, with a CHECK constraint enforcing that exactly
-- one of "a real revision" / "the NO_DRAFT_YET sentinel" holds at all
-- times -- deliberately never an overloaded NULL/0 read two different ways
-- by different code paths. darwin.research_store.mendel_repositories'
-- `_binding_to_columns`/`_columns_to_binding` are the only translation
-- point between this pair of columns and
-- darwin.workshop.mendel_domain.NO_DRAFT_YET / a real int.

CREATE TABLE mendel_proposals (
    id                                  UUID PRIMARY KEY,
    run_id                               UUID NOT NULL REFERENCES mendel_runs(id),
    workshop_id                          UUID NOT NULL REFERENCES strategy_workshops(id),
    proposal_class                       TEXT NOT NULL
        CHECK (proposal_class IN (
            'ASK_QUESTION', 'SEMANTIC_CHANGE', 'PARAMETER_CHANGE', 'DATA_REQUIREMENT',
            'THESIS_CHANGE', 'POLICY_CLASSIFICATION', 'INSTRUMENT_CLARIFICATION',
            'TIMEFRAME_CLARIFICATION', 'MATERIAL_CONCERN'
        )),
    proposal_category                    TEXT NOT NULL
        CHECK (proposal_category IN ('QUESTION', 'ADVISORY', 'DRAFT_MUTATING')),
    proposal_schema_version               TEXT NOT NULL,
    payload                              JSONB NOT NULL,
    rationale                            TEXT NOT NULL,
    affected_semantic_paths              JSONB NOT NULL DEFAULT '[]'::jsonb,
    generated_against_draft_revision     INTEGER NULL,
    generated_against_no_draft_yet       BOOLEAN NOT NULL DEFAULT FALSE,
    status                               TEXT NOT NULL DEFAULT 'PROPOSED'
        CHECK (status IN ('PROPOSED', 'ACCEPTED', 'REJECTED', 'STALE')),
    created_at_utc                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at_utc                       TIMESTAMPTZ NULL,
    resulting_question_id                 UUID NULL REFERENCES workshop_questions(id),
    resulting_decision_id                 UUID NULL REFERENCES workshop_decisions(id),

    -- --- THE structural class<->category CHECK constraint (PID-004C
    -- sec6.4) -- mirrors darwin.workshop.mendel_domain.
    -- PROPOSAL_CLASS_CATEGORY EXACTLY. It is structurally impossible to
    -- persist any other pairing, independent of any Python-level guard --
    -- tests/integration/test_mendel_migration.py proves this with a raw
    -- SQL INSERT attempting a mismatched pair.
    CHECK (
        (proposal_class = 'ASK_QUESTION' AND proposal_category = 'QUESTION')
        OR (proposal_class = 'MATERIAL_CONCERN' AND proposal_category = 'ADVISORY')
        OR (
            proposal_class IN (
                'SEMANTIC_CHANGE', 'PARAMETER_CHANGE', 'DATA_REQUIREMENT', 'THESIS_CHANGE',
                'POLICY_CLASSIFICATION', 'INSTRUMENT_CLARIFICATION', 'TIMEFRAME_CLARIFICATION'
            )
            AND proposal_category = 'DRAFT_MUTATING'
        )
    ),

    -- Exactly one of "a real draft revision" / "the NO_DRAFT_YET sentinel"
    -- may hold -- never both, never neither.
    CHECK (
        (generated_against_draft_revision IS NOT NULL AND generated_against_no_draft_yet = FALSE)
        OR (generated_against_draft_revision IS NULL AND generated_against_no_draft_yet = TRUE)
    ),

    -- A PROPOSED proposal has not yet been resolved; every non-PROPOSED
    -- (ACCEPTED/REJECTED/STALE) proposal must carry a resolution time.
    CHECK (status = 'PROPOSED' OR resolved_at_utc IS NOT NULL),
    CHECK (status <> 'PROPOSED' OR resolved_at_utc IS NULL),

    -- A resulting_question_id may only ever be set for a QUESTION-category
    -- proposal (PID-004C sec10.2); a resulting_decision_id is set for
    -- ADVISORY or DRAFT_MUTATING acceptance, never QUESTION (PID-004C
    -- sec7.3.1/sec7.3.2/sec7.3.3).
    CHECK (resulting_question_id IS NULL OR proposal_category = 'QUESTION'),
    CHECK (resulting_decision_id IS NULL OR proposal_category <> 'QUESTION')
);

CREATE INDEX idx_mendel_proposals_workshop_id ON mendel_proposals (workshop_id);
CREATE INDEX idx_mendel_proposals_run_id ON mendel_proposals (run_id);
CREATE INDEX idx_mendel_proposals_status ON mendel_proposals (status);

-- Content-immutability (PID-004C sec10.2/sec6.1 -- "Proposal history is
-- durable and auditable... a rejected or superseded proposal is never
-- deleted"): only status/resolved_at_utc/resulting_question_id/
-- resulting_decision_id may ever change after insert -- mirrors migration
-- 0009's trg_workshop_decisions_content_immutable pattern exactly, just
-- against mendel_proposals' own column set. DELETE is rejected outright.

CREATE OR REPLACE FUNCTION reject_mendel_proposal_content_mutation() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'mendel_proposals rows are append-only (PID-004C): DELETE on id=%',
            OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;

    IF OLD.run_id IS DISTINCT FROM NEW.run_id
        OR OLD.workshop_id IS DISTINCT FROM NEW.workshop_id
        OR OLD.proposal_class IS DISTINCT FROM NEW.proposal_class
        OR OLD.proposal_category IS DISTINCT FROM NEW.proposal_category
        OR OLD.proposal_schema_version IS DISTINCT FROM NEW.proposal_schema_version
        OR OLD.payload IS DISTINCT FROM NEW.payload
        OR OLD.rationale IS DISTINCT FROM NEW.rationale
        OR OLD.affected_semantic_paths IS DISTINCT FROM NEW.affected_semantic_paths
        OR OLD.generated_against_draft_revision IS DISTINCT FROM NEW.generated_against_draft_revision
        OR OLD.generated_against_no_draft_yet IS DISTINCT FROM NEW.generated_against_no_draft_yet
        OR OLD.created_at_utc IS DISTINCT FROM NEW.created_at_utc
    THEN
        RAISE EXCEPTION
            'mendel_proposals content is immutable once inserted (PID-004C): only status/'
            'resolved_at_utc/resulting_question_id/resulting_decision_id may change, on id=%',
            OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_mendel_proposals_content_immutable
    BEFORE UPDATE OR DELETE ON mendel_proposals
    FOR EACH ROW EXECUTE FUNCTION reject_mendel_proposal_content_mutation();

-- ============================================================================
-- 3. The one narrow PID-004B schema change (PID-004C sec10.3): widen
--    workshop_questions.origin to add 'MENDEL' alongside the existing
--    'HUMAN'. No other PID-004B table/trigger/constraint changes.
-- ============================================================================
--
-- Migration 0009 declared this CHECK inline on the column
-- (`origin TEXT ... CHECK (origin IN ('HUMAN'))`), so Postgres assigned it
-- an auto-generated name rather than one this migration can assume by
-- convention. Found and dropped by inspecting pg_constraint directly
-- (never guessed), then replaced with an explicitly-named, widened
-- constraint so any FUTURE widening has an obvious, stable name to target.

DO $$
DECLARE
    existing_constraint_name TEXT;
BEGIN
    SELECT con.conname INTO existing_constraint_name
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE rel.relname = 'workshop_questions'
      AND nsp.nspname = 'public'
      AND con.contype = 'c'
      AND pg_get_constraintdef(con.oid) = 'CHECK ((origin = ''HUMAN''::text))';

    IF existing_constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE workshop_questions DROP CONSTRAINT %I', existing_constraint_name);
    ELSE
        RAISE EXCEPTION
            'Could not find migration 0009''s original workshop_questions.origin CHECK constraint '
            '(expected exactly one, defining origin IN (''HUMAN'')) -- refusing to guess; a prior '
            'migration or manual change may have already altered it';
    END IF;
END $$;

ALTER TABLE workshop_questions
    ADD CONSTRAINT workshop_questions_origin_check CHECK (origin IN ('HUMAN', 'MENDEL'));
