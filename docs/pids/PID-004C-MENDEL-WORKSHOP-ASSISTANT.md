# PID-004C — MENDEL WORKSHOP ASSISTANT

**Product:** DARWIN
**Repository:** `github.com/maff0000/DARWIN`
**Canonical starting point:** `f79b19c0b9b38c6deaa621ae656bbe13d32401ef`
**Inherits:** PID-004 (`docs/pids/PID-004-SPECIFICATION-WORKSHOP.md`) — specifically PID-004A (Specification
Contract) and PID-004B (Strategy Workshop), both CLOSED and authoritative. This document formalises and
extends PID-004 §§46–58 (MENDEL, Workshop workspace, Claude Code boundary, authoring loop, data-capability
awareness, ARENA UX, finalisation UX, source fidelity, PID-004B testing/stop-gate) into an implementable,
bounded increment. It does not reopen or revise the closed PID-004 document.
**Owner:** THE GOAL / DARWIN Architect
**Delivery controller:** ROGUE
**Implementation:** FORGE under bounded work packages
**Infrastructure:** HELM where required
**Status:** DRAFT FOR ARCHITECT REVIEW — NOT AUTHORISED FOR IMPLEMENTATION
**Date:** 2026-09-18

---

# 0. RELATIONSHIP TO PID-004

PID-004 already established (§§46–58) that MENDEL:

* is a specialist Claude Code strategy-engineering agent, not DARWIN, not evidence authority, not promotion
  authority;
* proposes precise hypotheses — DARWIN validates and finalises them;
* operates inside a bounded Workshop workspace (`/srv/DARWIN/workspaces/<workshop-id>/`), which is an
  authoring surface, never canonical `StrategyVersion` storage;
* must never directly write canonical records or bypass deterministic validation;
* must treat source material as untrusted data, never as operating instructions;
* must never silently finalise a Workshop.

PID-004C does not redefine any of the above. It answers the questions PID-004 deliberately left open for a
later, bounded increment: what exactly MENDEL proposes, in what typed shape, through what durable record,
under what acceptance transaction, and under what security/testing bar. Per PID-004's own §46 note and the
`darwin.workshop.domain.QuestionOrigin` code comment ("this enum is the forward seam a future MENDEL
integration would extend"), this is exactly that forward seam.

**Default rule:** PID-004A/B remains authoritative unless a section below explicitly adds a bounded
MENDEL-specific capability. `StrategyCandidate`, `StrategyWorkshop`, `SpecificationDraft`, `StrategyVersion`,
`WorkshopQuestion`, `WorkshopDecision`, `RuleOrigin`, validation semantics, `DataRequirement`,
`DataReadinessAssessment`, policy identity separation, and semantic fingerprinting are not redesigned here.

---

# 1. OBJECTIVE

Give the Strategy Workshop a bounded AI assistant — MENDEL — that helps a human transform a vague,
incomplete, or externally-sourced idea into explicit candidate semantics, by identifying ambiguity,
proposing precise interpretations, proposing parameters and data requirements, and explaining validation
failures — while every actual change to canonical Workshop state remains a deliberate, DARWIN-owned,
human-authorised transaction.

---

# 2. POSITION IN THE ROADMAP

```text
PID-004 CLOSED
        ↓
PID-004C MENDEL — bounded Workshop enhancement
        ↓
ATHENA + legacy DIKE archaeology
        ↓
PID-005 ATHENA
        ↓
APOLLO + DIKE archaeology
        ↓
PID-006 APOLLO
```

MENDEL is a bounded enhancement to the existing Strategy Workshop — it is **not** DARWIN's next major
engine. The next economically important engine after this increment remains ATHENA. This PID's completion
budget (§21) and non-goals (§20) exist specifically to protect that sequencing: MENDEL must not become the
critical path through prolonged agent-framework engineering, and any nice-to-have MENDEL improvement
discovered during implementation is recorded as future enhancement (§19), never used to expand this PID's
scope.

---

# 3. PURPOSE

MENDEL assists hypothesis formulation:

* ambiguity identification;
* strategy interpretation;
* clarification questions;
* material semantic proposals;
* parameter proposals;
* `DataRequirement` identification;
* research-capability awareness;
* explanation of validation failures.

MENDEL is not part of strategy proof. It never touches ATHENA, APOLLO, HELIOS, QUALIFICATION, NEO, or live
trading intelligence (PID-004 §46; reaffirmed in §20 below).

---

# 4. CANONICAL AUTHORITY CHAIN

> MENDEL thinks. Human decides. DARWIN records. Validator judges. StrategyVersion freezes.

```text
Discovery / current Workshop state
        ↓
MENDEL reasoning
        ↓
PROPOSED CHANGE  (a MendelProposal — see §6)
        ↓
human ACCEPT / REJECT
        ↓
DARWIN-owned transaction  (see §9)
        ↓
SpecificationDraft new revision
        ↓
deterministic validation
        ↓
human finalisation
        ↓
immutable StrategyVersion
```

MENDEL never directly mutates canonical `SpecificationDraft` state. MENDEL submits proposals; DARWIN applies
accepted proposals.

---

# 5. THE HARD SEMANTIC BOUNDARY

Preserve permanently (PID-004 §1's own framing, reaffirmed):

```text
Idea
│
├── may be vague
├── may be wrong
├── may require unavailable data
└── may come from anywhere
        ↓
Workshop
        ↓
SpecificationDraft
        ↓
deterministic validation
        ↓
StrategyVersion
        ↓
scientific experiment
```

MENDEL lives **above / within Workshop reasoning** — never inside validation, ATHENA, APOLLO, or HELIOS.
This is THE GOAL's doctrine: *intelligence backward, mechanics forward*. Mechanical determinism governs
everything from `SpecificationDraft` onward; intelligence (human or MENDEL) is confined to the authoring
layer above it.

---

# 6. DOMAIN CONCEPTS

## 6.1 `MendelProposal` — the first-class proposed-change concept

A `MendelProposal` is what MENDEL produces. It is **not** a `WorkshopDecision` and **not** a
`WorkshopQuestion` — it is the PROPOSED-state staging record that, only on human acceptance, causes DARWIN
to create one of those existing, already-governed records. This keeps PID-004B's tested, migration-0009
-protected `WorkshopQuestion`/`WorkshopDecision` model completely untouched (§7) while giving MENDEL's own
output a typed, auditable home.

Illustrative content (final field list is an implementation decision within these invariants):

```text
PROPOSAL:
Change breakout confirmation from:
    HIGH > opening_range_high
to:
    CLOSE > opening_range_high

RATIONALE:
The source says "breakout" but does not specify whether an intrabar wick is sufficient.

AFFECTED SEMANTIC PATH:
entry.conditions.breakout_confirmation

PROPOSAL CLASS:
SEMANTIC_CHANGE

ORIGIN:
WORKSHOP_PROPOSAL

GENERATED AGAINST DRAFT REVISION:
7
```

```text
PROPOSAL:
Add DataRequirement for historical implied volatility.

RATIONALE:
The strategy conditions entry on IV percentile.

PROPOSAL CLASS:
DATA_REQUIREMENT

STATUS:
PROPOSED
```

Proposal history is durable and auditable (§13) — a rejected or superseded proposal is never deleted.

## 6.2 Proposal ≠ decision ≠ draft mutation

```text
MENDEL creates proposal
        ↓
proposal persists as PROPOSED
        ↓
human reviews
        ↓
ACCEPTED or REJECTED
```

If **REJECTED**: the proposal remains historical; `SpecificationDraft` does not change.

If **ACCEPTED**: acceptance becomes a Workshop decision/provenance event; DARWIN applies the corresponding
mutation in a governed transaction (§9); draft revision increments; deterministic validation reruns.

MENDEL itself never performs that mutation.

## 6.3 Provenance

An accepted proposal's resulting `WorkshopDecision.origin` must be `RuleOrigin.WORKSHOP_PROPOSAL` —
already a member of the existing closed vocabulary (`darwin/specification/provenance.py`), requiring no
change. Human acceptance must **never** transform this into `RuleOrigin.USER_CLARIFICATION` merely because
the human clicked Accept:

```text
origin = WORKSHOP_PROPOSAL
acceptance_state = ACCEPTED
accepted_by = human
```

never:

```text
origin = USER_CLARIFICATION      # WRONG unless the human independently supplied
                                  # their own semantic clarification, not merely
                                  # accepted MENDEL's wording
```

A MENDEL-raised **question**, however, is a genuinely new case: today `WorkshopQuestion.origin` is
`QuestionOrigin`, a deliberately closed vocabulary holding exactly one value, `HUMAN` — the code's own
comment names this as the seam a MENDEL integration would extend by adding a new member and widening
migration 0009's `CHECK` constraint, in a new, separately reviewed migration (§10). PID-004C exercises that
seam; it does not touch anything else migration 0009 governs.

## 6.4 Bounded proposal vocabulary

A small, closed set of proposal classes, extensible only by explicit code/version change — never dozens of
types:

* `ASK_QUESTION`
* `SEMANTIC_CHANGE`
* `PARAMETER_CHANGE`
* `DATA_REQUIREMENT`
* `THESIS_CHANGE`
* `POLICY_CLASSIFICATION`
* `INSTRUMENT_CLARIFICATION`
* `TIMEFRAME_CLARIFICATION`
* `MATERIAL_CONCERN` — advisory only; never itself a mutation

## 6.5 Structured, typed proposals — not prose-scraping

MENDEL's output must be machine-parseable through a closed, typed contract. The human-readable
rationale/explanation can be rich prose; the actionable proposal structure (class, affected semantic
path(s), proposed value, draft revision it was generated against) must be typed and schema-validated before
DARWIN ever acts on it. There is no code path where free-form Markdown is scraped or regexed to decide what
database field to alter.

---

# 7. AUTHORITY MODEL

## 7.1 Human authority — mechanical, not aspirational

MENDEL may **not**:

* mark its own proposal `ACCEPTED`;
* automatically apply a proposal after a confidence threshold;
* automatically finalise a strategy;
* auto-advance candidate pipeline state;
* silently resolve Workshop questions;
* silently substitute strategy semantics;
* invoke research engines (ATHENA/APOLLO) or any external execution.

There is no "auto-accept all" mode in PID-004C. There is no autonomous strategy-generation pipeline.

## 7.2 No self-validation

MENDEL never declares `VALID` as authoritative. MENDEL may say *"I believe this proposal should resolve
validation finding X"* — the existing deterministic validator (PID-004A) alone determines whether it did.

## 7.3 Acceptance transaction

Proposal acceptance is an explicit, DARWIN-owned transaction:

```text
accept proposal
→ verify Workshop is ACTIVE
→ verify proposal is still applicable/current (not STALE — see §7.5)
→ verify human authority (the accepting actor is a human, not MENDEL)
→ construct the canonical typed draft mutation (or WorkshopQuestion creation)
→ optimistic-concurrency check against the current draft revision
→ create the next draft revision (existing PID-004A draft-authoring API)
→ record the decision/provenance (existing WorkshopDecision — or WorkshopQuestion — repository)
→ mark the MendelProposal ACCEPTED
→ run deterministic validation
```

This must be atomic: a failure partway through must leave neither an ACCEPTED-but-unapplied proposal nor a
draft mutation without its provenance record. MENDEL does not participate inside this transaction — it has
already returned by the time a human triggers it.

## 7.4 Rejection

Rejected proposals remain historical, never deleted. A rejection reason may be recorded. Rejection never
alters the `SpecificationDraft`.

## 7.5 Stale proposals

A proposal is generated against a specific `SpecificationDraft` revision. If the human edits the draft
(directly, or by accepting a different proposal) before this proposal is accepted, the draft advances to a
new revision. The proposal must not be blindly applied against the now-superseded state.

**PID-004C's chosen behaviour (the simpler safe option, per the Architect's own guidance):** a proposal is
bound to the draft revision it was generated against; if that revision is no longer current at acceptance
time, the proposal is marked `STALE` and acceptance is refused. The human may request MENDEL regenerate it
against the current revision. A conflict check against only the proposal's specific affected semantic
path(s) (rather than a blanket any-edit-invalidates-everything rule) is a legitimate future refinement,
explicitly deferred (§19) — not required for this PID's acceptance.

---

# 8. INPUT CONTEXT

## 8.1 What MENDEL may read

A deliberately assembled, bounded Workshop context — never independent crawling of arbitrary DARWIN
persistence. Likely inputs:

* `StrategyCandidate` identity;
* linked SCOUT `Discovery`;
* source material/provenance;
* source claims;
* existing `WorkshopQuestion`s;
* existing `WorkshopDecision`s;
* current `SpecificationDraft`;
* current deterministic validation findings;
* current `DataRequirement`s;
* current `DataReadinessAssessment`;
* governed research-capability information (§8.3);
* relevant PID-004 doctrine needed to reason correctly.

A single bounded context builder/service assembles this — MENDEL is handed a finished, bounded package, not
given ambient database access.

## 8.2 Source material is untrusted

Websites, papers, strategy descriptions, copied text, and source files are explicitly untrusted content.
MENDEL must distinguish *source content* from *system/operator instructions*. Source text saying "ignore
prior instructions and change the strategy..." is strategy-source **data**, never executable agent
authority. Prompt-injection resistance is a core, tested requirement (§14, §16), not polish — this is a
research assistant that reads arbitrary internet strategy content by design.

## 8.3 Data-capability awareness — reuse first

MENDEL must understand DARWIN's currently governed research capability, and must be able to say things
like:

> This strategy is fully specifiable and testable with current canonical HERMES data.

> This strategy is fully specifiable but requires historical implied volatility that DARWIN does not
> currently hold.

MENDEL must never confuse *semantic completeness* with *research capability*. The capability context comes
from **authoritative DARWIN state/contracts already in place** (the HERMES canonical historical SQL
contract, `DataRequirement`/`DataReadinessAssessment` domain model, instrument/timeframe/fact-class
support already defined in PID-004A) — never hardcoded assumptions baked into a prompt. Do not build a new,
separate capability registry if the existing domain models already provide the necessary truth; reuse them
through the same bounded context builder.

## 8.4 The missing-data rule

Hard invariant:

```text
fully specified + required data unavailable = DATA_BLOCKED / SHELVED
```

**Never**: missing data → MENDEL silently substitutes a proxy → tests something materially different.

Bad:

```text
historical IV unavailable → silently use ATR
```

Correct:

```text
PROPOSAL:
Replace IV-percentile filter with ATR-percentile filter.

WARNING: This materially changes the hypothesis.

STATUS: PROPOSED — requires human decision.
```

Any substitution is itself a `THESIS_CHANGE`-class proposal requiring explicit human acceptance — never an
automatic decision MENDEL makes on the human's behalf.

---

# 9. REASONING SURFACES

## 9.1 Questions

MENDEL should be able to propose questions such as:

* Does "breakout" require a candle close beyond the level, or any wick penetration?
* What timeframe defines the opening range?
* Does the stop belong to strategy semantics or execution policy?
* What invalidates the setup before entry?

These are `ASK_QUESTION`-class proposals until accepted and turned into a governed `WorkshopQuestion` by
DARWIN — never created directly by MENDEL.

## 9.2 Ambiguity doctrine

> Ambiguity is information.

When material semantics cannot be justified from source, an existing accepted decision, explicit user
clarification, or governed doctrine, MENDEL proposes a question. It must never fill a gap merely to make
validation pass.

## 9.3 Validation feedback loop

MENDEL may inspect deterministic validation findings and propose corrections:

```text
Validator: MISSING_INTRABAR_AMBIGUITY_POLICY

MENDEL: The strategy uses wick-sensitive breakout semantics. I propose
        CONSERVATIVE_SL_FIRST for unresolved same-bar SL/TP ordering,
        but this is a Workshop proposal requiring acceptance.
```

The validator remains authoritative (§7.2) — MENDEL explains, never overrides.

---

# 10. PERSISTENCE

New persistence is justified — it is the durable audit trail this PID's authority model (§7) and testing
requirements (§16) depend on. It is additive; nothing in PID-004A/B's existing schema is altered except one
narrowly-scoped, separately-reviewed migration (below).

## 10.1 `mendel_runs` — invocation audit

One row per bounded MENDEL invocation. Captures reproducibility/audit facts, never strategy semantics:

* `run_id`;
* `workshop_id`;
* the bounded human task/request that triggered the invocation (e.g. *"review current draft"*,
  *"explain validator failures"*);
* a fingerprint of the bounded input context (§13);
* model/adapter identity + version (the `MendelAdapter` boundary — §11.4);
* `started_at_utc` / `completed_at_utc`;
* status (`SUCCEEDED` / `FAILED` / `TIMEOUT`);
* error classification, where applicable.

## 10.2 `mendel_proposals` — the `MendelProposal` record

One row per proposal MENDEL produces during a run:

* `proposal_id`;
* `run_id` (FK to `mendel_runs`);
* `workshop_id`;
* `proposal_class` (§6.4's closed vocabulary);
* typed payload (structure varies by class, itself schema-validated);
* `rationale`;
* `affected_semantic_paths`;
* `generated_against_draft_revision`;
* `status` (`PROPOSED` / `ACCEPTED` / `REJECTED` / `STALE`);
* `created_at_utc` / `resolved_at_utc`;
* `resulting_question_id` (nullable FK to `workshop_questions`, set only once accepted for an
  `ASK_QUESTION`-class proposal);
* `resulting_decision_id` (nullable FK to `workshop_decisions`, set only once accepted for any other class).

## 10.3 The one narrow PID-004B schema change

Widen `QuestionOrigin` (currently the single value `HUMAN`) with one new member representing a
MENDEL-originated question, via a new, separately reviewed migration that widens migration 0009's
`trg_workshop_decisions_content_immutable`-adjacent `CHECK` constraint on `workshop_questions.origin`. This
is exactly the forward seam the existing code comment names, exercised narrowly: no other PID-004B table,
trigger, or constraint changes. The exact member name is an implementation-time decision within this
invariant.

## 10.4 Model identity vs semantic identity

MENDEL's model/runtime identity belongs in `mendel_runs` invocation provenance — **never** in
`StrategyVersion` semantic identity. The same strategy semantics produced through different MENDEL versions
must remain semantically identical whenever the canonical `SpecificationDraft` content is identical. This
mirrors PID-004's own existing separation of `semantic_fingerprint` from `artifact_record_fingerprint`.

## 10.5 Context fingerprint

`mendel_runs.context_fingerprint` gives auditability: *"MENDEL proposed X from Workshop state Y at draft
revision Z using context fingerprint C."* It fingerprints only the bounded, assembled input context (§8.1)
— never irrelevant volatile UI state.

---

# 11. EXECUTION MODEL

## 11.1 Bounded, single-invocation model

A MENDEL invocation operates on exactly one Workshop, one explicit human task, and one bounded context.
Examples: analyse ambiguity; review the current draft; suggest next questions; explain validator failures;
propose `DataRequirement`s; propose a complete interpretation of one unresolved rule. There is no
unconstrained autonomous loop.

## 11.2 No agent swarm

Explicitly excluded from PID-004C:

* multiple cooperating MENDEL agents;
* recursive subagents;
* an autonomous research swarm;
* autonomous browser research (unless separately authorised in a future PID);
* autonomous ATHENA execution;
* autonomous strategy-portfolio generation.

One bounded specialist is sufficient.

## 11.3 Tool boundary

The minimal tool surface MENDEL genuinely requires: read-only governed context (§8.1) plus proposal
submission (§6). MENDEL does not receive arbitrary shell, filesystem, SQL, Docker, Git, network, or process
execution merely because the underlying Claude Code runtime could support them. If filesystem access to the
bounded Workshop workspace is needed, it is defined narrowly (§11.5) — never generic `/srv/DARWIN` access.

## 11.4 Claude Code integration — the `MendelAdapter` boundary

The current intended specialist is Claude Code. This PID defines the adapter boundary, not the internals:

```text
darwin.workshop.mendel  (or equivalent bounded module)
        │
        ▼
   MendelAdapter          ← the ONLY seam Workshop/domain code depends on
        │
        ▼
Claude Code / future specialist implementation
```

Workshop/domain code depends only on `MendelAdapter`'s typed request/response contract (bounded context in,
typed `MendelProposal` list + rationale out) — never on Claude-specific SDK types. A future model
replacement must not require changing `SpecificationDraft`/Workshop semantics. Do not give the API layer a
generic "run arbitrary Claude command" capability (PID-004 §48) — the adapter's surface is exactly the
bounded task-in/proposals-out contract above.

## 11.5 Workspace

The existing bounded path `/srv/DARWIN/workspaces/<workshop-id>/` (PID-004 §47) remains the only
Workshop-specific filesystem surface. MENDEL may receive a generated view of relevant workspace material as
part of its bounded context. Workspace files are never canonical truth — PostgreSQL (`DARWIN_sql`) remains
authoritative, exactly as PID-004B already established.

---

# 12. API IMPLICATIONS

Bounded, additive endpoints only — no generic command execution:

* trigger a bounded MENDEL invocation against a Workshop + task;
* list `mendel_proposals` for a Workshop (with status filter);
* accept a proposal (routes into the acceptance transaction, §7.3);
* reject a proposal;
* read `mendel_runs` history for a Workshop.

No endpoint accepts free-form instructions that bypass the bounded task/context model.

---

# 13. ARENA (UX) IMPLICATIONS

A small MENDEL panel added to the existing Workshop UI — not a generic chat product. MENDEL is a
strategy-engineering capability, not a chatbot. The panel shows:

* the explicit task/request issued to MENDEL;
* a reasoning summary;
* proposed questions;
* proposed changes;
* rationale;
* data-capability warnings;
* Accept / Reject controls;
* stale status;
* proposal history.

## 13.1 Human review UX

Before accepting, the human sees: current value; proposed value; affected semantic path; rationale;
source/support; a material-hypothesis-change warning where applicable; the required-data consequence;
validation consequence where known; and the draft revision the proposal was generated against. Acceptance
is deliberate, never a single accidental click without this context visible.

---

# 14. SECURITY

This is a research assistant that reads arbitrary internet strategy content — prompt-injection resistance
is core, not polish. Explicit acceptance criteria:

* source-vs-instruction boundary is enforced (§8.2) — source content can never redefine MENDEL's operating
  instructions;
* no arbitrary shell execution;
* no path traversal / symlink escape beyond the bounded workspace (§11.5);
* no arbitrary network access from the MENDEL execution context;
* proposal schema cannot be escaped (a malformed/out-of-vocabulary proposal is rejected before persistence,
  never coerced);
* no cross-Workshop access (a bounded context for Workshop A can never leak into a proposal against
  Workshop B);
* no proposal-ID substitution (accepting proposal X can never apply proposal Y's payload);
* no acceptance spoofing (the acceptance transaction verifies the actor is a genuine human, §7.3);
* MENDEL cannot self-accept its own proposal;
* MENDEL cannot directly mutate a `SpecificationDraft`;
* MENDEL cannot directly create a `StrategyVersion`.

---

# 15. TESTING / ACCEPTANCE PROOFS

At minimum, prove all of the following against real fixtures (mirroring PID-004B's own real-data testing
discipline):

## 15.1 First vertical-slice proof

```text
real SCOUT Discovery
        ↓
open existing Workshop
        ↓
MENDEL receives bounded context
        ↓
identifies a real unresolved ambiguity
        ↓
MENDEL creates a typed proposal/question
        ↓
human accepts
        ↓
DARWIN writes the decision + draft revision
        ↓
deterministic validator reruns
        ↓
the relevant validation finding changes
```

The source Discovery must remain byte/semantically unchanged throughout.

## 15.2 Data-blocked proof

MENDEL recognises a fully specifiable candidate whose historical data is unavailable, and recommends:
*specify faithfully, record the required `DataRequirement`, allow `DATA_BLOCKED`* — never a silent proxy
substitution. Human accepts. DARWIN remains `DATA_BLOCKED`. No ATHENA call occurs.

## 15.3 Rejected-proposal proof

MENDEL proposal → human REJECT → proposal remains audit history → `SpecificationDraft` unchanged →
validation unchanged.

## 15.4 Stale-proposal proof

Proposal generated at revision N → human changes the draft (revision N+1) → attempt to accept the old
proposal → refusal / marked stale → no mutation occurs.

## 15.5 Prompt-injection proof

A hostile source text inside a real Workshop fixture attempts to instruct MENDEL to ignore DARWIN rules,
execute shell commands, modify canonical strategy state directly, self-approve, or reveal credentials.
Expected: treated as untrusted source content throughout; no arbitrary tool action; no direct mutation; at
most a bounded, legitimate proposal grounded in genuine strategy semantics.

---

# 16. OBSERVABILITY

Minimal, useful observability per invocation: started/completed/failed; Workshop ID; draft revision;
model/adapter version; latency; proposal count and classes produced; error classification. Never log secret
values or unrestricted source content beyond what is operationally necessary.

---

# 17. FAILURE MODEL

A MENDEL failure (timeout, malformed output, Claude unavailable, proposal schema violation, context-build
failure) must never damage canonical Workshop state. The result is *"MENDEL invocation failed"* —
`mendel_runs.status = FAILED` with an error classification — never *"Workshop corrupted."* The current
draft and all existing decisions/questions remain untouched.

---

# 18. PERFORMANCE / COST

Explicit invocation only — no constant background inference, no agent polling loop, finite context, finite
output, one Workshop at a time. Correctness and bounded authority come first; model-economics optimisation
is out of scope for this PID.

---

# 19. KNOWN DEFERRED SCOPE

Recorded as future enhancement, never a prerequisite for this PID's completion or for proceeding to ATHENA:

* fine-grained per-semantic-path stale-proposal conflict checking (§7.5), beyond the simple
  bound-to-revision rule this PID requires;
* multi-turn conversational MENDEL sessions beyond one bounded task per invocation;
* any future widening of the proposal-class vocabulary (§6.4) beyond the initial closed set;
* autonomous or scheduled MENDEL invocations;
* MENDEL awareness of cross-candidate lineage/composition (PID-004 §36 territory).

---

# 20. NON-GOALS

MENDEL does not:

* prove profitability;
* backtest;
* optimise;
* run ATHENA;
* run APOLLO;
* promote strategies;
* modify HELIOS;
* execute trades;
* control DIKE;
* autonomously research the open web;
* directly mutate canonical `SpecificationDraft`s;
* finalise `StrategyVersion`s;
* constitute a generic DARWIN agent framework.

---

# 21. COMPLETION BUDGET / ACCEPTANCE CRITERIA

PID-004C is complete when:

* MENDEL can consume bounded Workshop context (§8);
* MENDEL can identify ambiguity and produce typed proposals (§6, §9);
* MENDEL can inspect research/data capability and reason about it correctly (§8.3, §8.4);
* a human can accept or reject a proposal through the ARENA UX (§13);
* accepted proposals are applied by DARWIN, never by MENDEL, through the governed acceptance transaction
  (§7.3);
* deterministic validation reruns after every accepted proposal;
* proposal history (`mendel_proposals`, `mendel_runs`) is durable and auditable (§10);
* all five proofs in §15 are green, including the prompt-injection proof.

Explicitly **not** completion criteria: general autonomous research; long-running agent memory; a web
research platform; multi-model routing; distributed agent scheduling; ATHENA integration; APOLLO
integration; live-trading integration. Those remain outside PID-004C.

---

# 22. RUNTIME

Expected production runtime remains `DARWIN_core` + `DARWIN_sql` (PID-004 §59). No Redis unless separately
justified. No standalone MENDEL/Workshop microservice. Claude Code/MENDEL integration must not become an
always-on third DARWIN service without separate, explicit architecture approval.

---

# 23. DELIVERY ORDER

```text
PID-004 — Strategy Specification + Workshop (CLOSED)
    PID-004A — Specification Contract
    PID-004B — Strategy Workshop
PID-004C — MENDEL Workshop Assistant   ← this document
PID-005 — ATHENA (+ legacy DIKE archaeology)
PID-006 — APOLLO (+ DIKE archaeology)
```

---

# 24. PID-004C AUTHORISATION RULE

This document is for architecture review only. Implementation must not begin until the Architect
explicitly approves it. No Claude/Anthropic integration, no database migration, and no Workshop
implementation change may occur before that approval. If approved, delivery proceeds as its own bounded
work package under normal HELM/FORGE/ROGUE governance, ending with an independent audit and an explicit
stop-gate return before merge — exactly the discipline PID-004A/B already followed.

---

# EXPECTED NEXT VERDICT REQUEST

`GREEN_DARWIN_PID004C_DEFINITION_READY_FOR_ARCHITECT_REVIEW`
