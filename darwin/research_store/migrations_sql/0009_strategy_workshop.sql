-- PID-004B Strategy Workshop: durable Workshop identity, material
-- questions/decisions, and the SCOUT-discovery link table
-- (docs/pids/PID-004-SPECIFICATION-WORKSHOP.md sec45/sec47/sec49/sec50).
--
-- This migration ONLY adds new, additive tables -- it never rewrites
-- 0001-0008, never drops/retypes an existing column, never touches an
-- existing row. It must apply cleanly on top of either a fresh 0001-0008
-- database or (theoretically) real live 0001-0005 -- every new table here
-- is genuinely new, so there is no existence-conditional concern the way
-- 0006 had for its own tables; 02_grant_app_table_privileges.sql is
-- extended separately (existence-conditional, same discipline as before)
-- to grant darwin_app access to these new tables once they exist.
--
-- Workshop is a FOURTH, genuinely distinct identity, never collapsed with
-- Discovery/StrategyCandidate/SpecificationDraft/StrategyVersion (PID-004
-- sec4, sec49): `strategy_workshops.candidate_id` is the durable research
-- identity a Workshop operates against; `current_draft_id` names the
-- SpecificationDraft currently being authored (PID-004A's own table,
-- unmodified); `finalised_strategy_version_id` is set only once, at
-- successful finalisation, and never before.
--
-- Lifecycle (ACTIVE/FINALISED/ABANDONED) is deliberately operational-only
-- -- it is never conflated with semantic validation/readiness state, which
-- live entirely on specification_validation_records/
-- data_readiness_assessments (PID-004 sec49: "orthogonal axes").

CREATE TABLE strategy_workshops (
    id                              UUID PRIMARY KEY,
    candidate_id                    UUID NOT NULL REFERENCES strategy_candidates(id),
    current_draft_id                UUID NULL REFERENCES specification_drafts(id),
    status                          TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'FINALISED', 'ABANDONED')),
    finalised_strategy_version_id   UUID NULL REFERENCES strategy_versions(id),
    created_at_utc                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at_utc                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A FINALISED workshop must carry the StrategyVersion it produced; a
    -- non-FINALISED workshop must not claim one it never produced.
    CHECK (status = 'FINALISED' OR finalised_strategy_version_id IS NULL),
    CHECK (status <> 'FINALISED' OR finalised_strategy_version_id IS NOT NULL)
);

-- Idempotent-open invariant (PID-004 sec49), enforced structurally, not
-- merely in application code: at most one ACTIVE workshop may exist per
-- candidate at any time. FINALISED/ABANDONED rows are explicitly exempt --
-- they remain durable history forever, and a candidate may legitimately
-- accumulate several of them over time (e.g. an abandoned first attempt,
-- then a fresh ACTIVE workshop opened later).
CREATE UNIQUE INDEX uq_strategy_workshops_active_per_candidate
    ON strategy_workshops (candidate_id)
    WHERE status = 'ACTIVE';

CREATE INDEX idx_strategy_workshops_candidate_id ON strategy_workshops (candidate_id);
CREATE INDEX idx_strategy_workshops_current_draft_id ON strategy_workshops (current_draft_id);

-- Workshop <-> SCOUT Discovery, many-to-many (PID-004 sec49: "discovery/
-- candidate link" -- "may be zero/one/many"). Never a column on
-- strategy_workshops itself, and never a write path into scout_discoveries
-- (SCOUT fidelity -- PID-004 sec55: "do not silently modify SCOUT's
-- original record" -- this table only ever reads/references a
-- scout_discoveries.id, never writes to that table).
CREATE TABLE strategy_workshop_discovery_links (
    id                  UUID PRIMARY KEY,
    workshop_id         UUID NOT NULL REFERENCES strategy_workshops(id),
    discovery_id        UUID NOT NULL REFERENCES scout_discoveries(id),
    created_at_utc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workshop_id, discovery_id)
);

CREATE INDEX idx_swdl_workshop_id ON strategy_workshop_discovery_links (workshop_id);
CREATE INDEX idx_swdl_discovery_id ON strategy_workshop_discovery_links (discovery_id);

-- Material questions (PID-004 sec49/sec50). `origin` is a closed
-- vocabulary with exactly one value today ('HUMAN') -- MENDEL does not
-- exist yet in this build (PID-004 sec48: "Do not invent undocumented CLI
-- security assumptions" / sec46). The CHECK constraint below is written so
-- that adding a future 'MENDEL' value is a small, explicit, reviewed
-- migration of its own (widen the CHECK) -- never a silent schema-shape
-- change and never a free-text column pretending to be governed.
--
-- `accepted_decision_id` is added via ALTER TABLE below (after
-- workshop_decisions exists) -- the same "two tables reference each other"
-- shape 0005_scout_discovery.sql already uses for
-- scout_discoveries.last_snapshot_id -> scout_snapshots.
CREATE TABLE workshop_questions (
    id                      UUID PRIMARY KEY,
    workshop_id             UUID NOT NULL REFERENCES strategy_workshops(id),
    semantic_subject        TEXT NOT NULL,
    question_text           TEXT NOT NULL,
    rationale               TEXT NULL,
    status                  TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'RESOLVED', 'WITHDRAWN')),
    origin                  TEXT NOT NULL DEFAULT 'HUMAN'
        CHECK (origin IN ('HUMAN')),
    created_at_utc          TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at_utc         TIMESTAMPTZ NULL,

    CHECK (status = 'OPEN' OR resolved_at_utc IS NOT NULL),
    CHECK (status <> 'OPEN' OR resolved_at_utc IS NULL)
);

CREATE INDEX idx_workshop_questions_workshop_id ON workshop_questions (workshop_id);
CREATE INDEX idx_workshop_questions_status ON workshop_questions (status);

-- Material decisions (PID-004 sec50). `origin` reuses the EXACT closed
-- vocabulary darwin.specification.provenance.RuleOrigin already defines
-- (SOURCE_RULE / USER_CLARIFICATION / WORKSHOP_PROPOSAL) -- never a second,
-- competing origin vocabulary. `acceptance_state` is deliberately its own
-- separate closed vocabulary (PROPOSED/ACCEPTED/REJECTED/SUPERSEDED),
-- distinct from darwin.specification.provenance.RuleAcceptanceState
-- (PROPOSED/ACCEPTED_SPECIFICATION_RULE/REJECTED/SUPERSEDED) -- a Workshop
-- decision is not itself a ProvenanceRecord; a decision only becomes a
-- ProvenanceRecord once its effect is actually applied to a
-- SpecificationDraft via the existing draft-authoring API.
--
-- Append-only (PID-004B directive): a changed decision creates a NEW row
-- referencing the old one via `superseded_by_decision_id`; the substantive
-- content columns of an existing row (proposed_value, origin, actor,
-- rationale, workshop_id, related_question_id, created_at_utc) are never
-- rewritten in place -- enforced for real below by
-- `trg_workshop_decisions_content_immutable`, mirroring migration 0006's
-- `trg_strategy_versions_immutable` pattern. Only `acceptance_state` and
-- `superseded_by_decision_id` may ever be updated on an existing row (the
-- cross-reference bookkeeping the same transaction that supersedes a
-- decision performs) -- the trigger explicitly permits exactly those two
-- columns to change and rejects any other change or any DELETE.
CREATE TABLE workshop_decisions (
    id                          UUID PRIMARY KEY,
    workshop_id                 UUID NOT NULL REFERENCES strategy_workshops(id),
    related_question_id         UUID NULL REFERENCES workshop_questions(id),
    affected_semantic_paths     JSONB NOT NULL DEFAULT '[]'::jsonb,
    proposed_value              JSONB NOT NULL,
    origin                      TEXT NOT NULL
        CHECK (origin IN ('SOURCE_RULE', 'USER_CLARIFICATION', 'WORKSHOP_PROPOSAL')),
    actor                       TEXT NOT NULL,
    acceptance_state            TEXT NOT NULL DEFAULT 'PROPOSED'
        CHECK (acceptance_state IN ('PROPOSED', 'ACCEPTED', 'REJECTED', 'SUPERSEDED')),
    rationale                   TEXT NULL,
    created_at_utc               TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by_decision_id    UUID NULL REFERENCES workshop_decisions(id),

    CHECK (superseded_by_decision_id IS NULL OR acceptance_state = 'SUPERSEDED')
);

CREATE INDEX idx_workshop_decisions_workshop_id ON workshop_decisions (workshop_id);
CREATE INDEX idx_workshop_decisions_related_question_id ON workshop_decisions (related_question_id);
CREATE INDEX idx_workshop_decisions_acceptance_state ON workshop_decisions (acceptance_state);

CREATE OR REPLACE FUNCTION reject_workshop_decision_content_mutation() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'workshop_decisions rows are append-only (PID-004B): DELETE on id=%',
            OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;

    -- UPDATE: only acceptance_state and superseded_by_decision_id may ever
    -- change. Any other column disagreeing between OLD and NEW is a
    -- rewrite of substantive decision content, which never happens on an
    -- existing row (PID-004B: "a changed decision creates a NEW row").
    IF OLD.workshop_id IS DISTINCT FROM NEW.workshop_id
        OR OLD.related_question_id IS DISTINCT FROM NEW.related_question_id
        OR OLD.affected_semantic_paths IS DISTINCT FROM NEW.affected_semantic_paths
        OR OLD.proposed_value IS DISTINCT FROM NEW.proposed_value
        OR OLD.origin IS DISTINCT FROM NEW.origin
        OR OLD.actor IS DISTINCT FROM NEW.actor
        OR OLD.rationale IS DISTINCT FROM NEW.rationale
        OR OLD.created_at_utc IS DISTINCT FROM NEW.created_at_utc
    THEN
        RAISE EXCEPTION
            'workshop_decisions content is immutable once inserted (PID-004B): only '
            'acceptance_state/superseded_by_decision_id may change, on id=%',
            OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_workshop_decisions_content_immutable
    BEFORE UPDATE OR DELETE ON workshop_decisions
    FOR EACH ROW EXECUTE FUNCTION reject_workshop_decision_content_mutation();

-- workshop_questions.accepted_decision_id -> workshop_decisions(id), added
-- now that workshop_decisions exists (same ordering discipline
-- 0005_scout_discovery.sql already uses for last_snapshot_id).
ALTER TABLE workshop_questions
    ADD COLUMN accepted_decision_id UUID NULL REFERENCES workshop_decisions(id);

CREATE INDEX idx_workshop_questions_accepted_decision_id ON workshop_questions (accepted_decision_id);
