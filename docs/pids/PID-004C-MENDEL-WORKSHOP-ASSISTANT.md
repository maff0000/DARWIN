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
DARWIN-owned transaction  (see §7.3)
        ↓
SpecificationDraft new revision   ← only for a category-C (draft-mutating) proposal, §6.2
        ↓
deterministic validation
        ↓
human finalisation
        ↓
immutable StrategyVersion
```

This chain shows the category-C (draft-mutating) path. A category-A (`ASK_QUESTION`) or category-B
(`MATERIAL_CONCERN`) acceptance ends at the DARWIN-owned transaction step and does **not** produce a new
`SpecificationDraft` revision — see §6.2 for the exact, mechanically distinct behaviour of each category.

MENDEL never directly mutates canonical `SpecificationDraft` state, in any category. MENDEL submits
proposals; DARWIN applies accepted proposals.

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

## 6.2 Proposal-class acceptance semantics — three behavioural categories

It is **not true** that every accepted proposal mutates `SpecificationDraft`. Acceptance behaviour is
mechanically explicit and falls into exactly one of three categories, determined by the proposal's class
(§6.4):

```text
MENDEL creates proposal
        ↓
proposal persists as PROPOSED
        ↓
human reviews
        ↓
ACCEPTED or REJECTED
```

If **REJECTED**, uniformly across all three categories: the proposal remains historical; `SpecificationDraft`
never changes; no draft revision increment occurs; no `WorkshopQuestion`/`WorkshopDecision` is created.

If **ACCEPTED**, the resulting behaviour depends on category:

### A. QUESTION (`ASK_QUESTION`)

```text
MendelProposal
→ human accepts
→ DARWIN creates WorkshopQuestion
→ QuestionOrigin.MENDEL
→ proposal ACCEPTED
```

No `SpecificationDraft` mutation. No draft revision increment. Existing deterministic validation may be
displayed/refreshed for context, but semantic state has not changed merely because a question was created.

### B. ADVISORY (`MATERIAL_CONCERN`)

Acceptance means the human acknowledges/accepts the concern into Workshop history. It may create the
appropriate governed `WorkshopDecision`/audit record. It **must not** itself mutate `SpecificationDraft`. It
**must not** increment draft revision. It **must not** change validation merely by being acknowledged. If
resolving the concern requires changing semantics, MENDEL must make a separate, distinct, typed
draft-mutating proposal (category C) — acknowledging an advisory concern is never itself treated as
authorising a semantic change.

### C. DRAFT-MUTATING

`SEMANTIC_CHANGE`, `PARAMETER_CHANGE`, `DATA_REQUIREMENT`, `THESIS_CHANGE`, `POLICY_CLASSIFICATION`,
`INSTRUMENT_CLARIFICATION`, `TIMEFRAME_CLARIFICATION`:

```text
proposal ACCEPT
→ DARWIN-owned transaction
→ WorkshopDecision origin WORKSHOP_PROPOSAL
→ typed SpecificationDraft mutation
→ revision increment
→ deterministic validation
→ proposal ACCEPTED
```

MENDEL itself never performs any of these mutations, for any category — DARWIN alone applies an accepted
proposal (§7.3).

There is no generic "all non-question proposals mutate the draft" rule. §7.3 and §10 define the exact,
category-specific transaction and persistence shape; §15's acceptance proofs must exercise all three
categories, not only category C.

## 6.3 Provenance

An accepted category-C (draft-mutating) proposal's resulting `WorkshopDecision.origin` must be
`RuleOrigin.WORKSHOP_PROPOSAL` — already a member of the existing closed vocabulary
(`darwin/specification/provenance.py`), requiring no change. Human acceptance must **never** transform this
into `RuleOrigin.USER_CLARIFICATION` merely because the human clicked Accept:

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

A MENDEL-raised **question** (category A) is a genuinely new case, and its exact vocabulary is locked now
rather than left as an implementation-time decision. Today `WorkshopQuestion.origin` is `QuestionOrigin`, a
deliberately closed vocabulary holding exactly one value, `HUMAN` — the code's own comment names this as the
seam a MENDEL integration would extend. PID-004C locks the new member's name as:

```text
QuestionOrigin.HUMAN     (existing)
QuestionOrigin.MENDEL    (new — locked by this PID)
```

Human acceptance of a MENDEL-proposed question authorises its **creation**; it must **never** rewrite the
question's historical origin to `HUMAN`. Two distinct truths are preserved through separate fields, never
collapsed into one: the human **authorised creation** (recorded via the existing accepted-by/decision actor
field the Workshop boundary already provides); MENDEL **originated** the question's content (recorded as
`origin = QuestionOrigin.MENDEL`, permanently). Widening the vocabulary is the one narrow, separately
reviewed migration described in §10.3; it does not touch anything else migration 0009 governs.

## 6.4 Bounded proposal vocabulary

A small, closed set of proposal classes, extensible only by explicit code/version change — never dozens of
types — each mapped to exactly one of the three §6.2 behavioural categories:

| Proposal class | Category |
|---|---|
| `ASK_QUESTION` | A — QUESTION |
| `MATERIAL_CONCERN` | B — ADVISORY |
| `SEMANTIC_CHANGE` | C — DRAFT-MUTATING |
| `PARAMETER_CHANGE` | C — DRAFT-MUTATING |
| `DATA_REQUIREMENT` | C — DRAFT-MUTATING |
| `THESIS_CHANGE` | C — DRAFT-MUTATING |
| `POLICY_CLASSIFICATION` | C — DRAFT-MUTATING |
| `INSTRUMENT_CLARIFICATION` | C — DRAFT-MUTATING |
| `TIMEFRAME_CLARIFICATION` | C — DRAFT-MUTATING |

This mapping is itself part of the closed contract (§10) — a proposal's category is never inferred at
runtime from its payload shape; it is fixed by its class.

## 6.5 Structured, typed proposals — not prose-scraping

MENDEL's output must be machine-parseable through a closed, typed contract. The human-readable
rationale/explanation can be rich prose; the actionable proposal structure (class, affected semantic
path(s), proposed value, draft revision it was generated against) must be typed and schema-validated before
DARWIN ever acts on it. There is no code path where free-form Markdown is scraped or regexed to decide what
database field to alter.

## 6.6 `affected_semantic_paths` is audit metadata, never a mutation mechanism

This is important enough to state explicitly. `affected_semantic_paths` (§10.2) is **audit / presentation
metadata only** — it tells a human reviewer what area of the strategy a proposal concerns. It **must not**
become an executable generic mutation mechanism, for example:

```text
path = "anything.the.model.outputs"
value = arbitrary JSON
```

followed by a generic setter. There is no generic path-based patch engine anywhere in PID-004C.

Each category-C (draft-mutating) proposal class has a **closed, typed** actionable payload, understood by an
explicit DARWIN application handler for that class. The principle is fixed:

```text
MENDEL emits a typed proposal
DARWIN selects the known proposal handler for that proposal's class
the handler constructs canonical PID-004A domain objects
existing typed deserialisation/validation (PID-004A) remains authoritative
```

Never:

```text
MENDEL emits JSONPath + arbitrary value
a generic patch engine mutates the draft
```

There is no `eval`. There is no dynamic attribute setter keyed off `affected_semantic_paths`. There is no
arbitrary JSON Patch engine. A complex composition change (e.g. restructuring an `ALL`/`ANY`/`SEQUENCE`
subtree) may legitimately propose a typed canonical subtree/document fragment, provided that fragment is
constructed and applied through the same closed PID-004A constructors/deserialiser every other authoring
path already uses — never through a bespoke generic mutation path invented for MENDEL.

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

## 7.3 Acceptance transaction — one shape per behavioural category

### 7.3.0 The acceptance boundary — mechanically enforceable human authority

Proposal acceptance is exposed **only** through DARWIN's existing human-operator acceptance boundary (the
same Workshop API surface a human already uses for every other Workshop action). The `MendelAdapter`
(§11.4) has no capability, credential, callback, tool, or internal method that can invoke proposal
acceptance. This is the invariant PID-004C actually guarantees:

```text
MENDEL cannot accept
MENDEL cannot call acceptance
MENDEL cannot obtain acceptance authority
```

PID-004C does **not** claim that acceptance cryptographically proves the accepting actor is "a genuine
human" — that is stronger than the architecture currently proves unless DARWIN has an authoritative
authentication/identity mechanism specifically capable of making that assertion, and PID-004C does not
invent an authentication/IAM programme. Where an authenticated DARWIN operator identity is already
available, it is persisted with the acceptance. Where the current deployment does not provide cryptographic
operator identity, the acceptance transaction records the bounded operator actor already supplied by the
existing Workshop boundary, and this PID does not claim cryptographic proof of humanness beyond that.

### 7.3.1 QUESTION-class acceptance (category A — `ASK_QUESTION`)

```text
verify proposal / current revision
→ create WorkshopQuestion (origin = QuestionOrigin.MENDEL)
→ mark proposal ACCEPTED
```

Must be transactionally coherent: no `WorkshopQuestion` may exist for an accepted proposal that failed to
commit, and no proposal may show ACCEPTED while its `WorkshopQuestion` failed to persist.

### 7.3.2 ADVISORY-class acceptance (category B — `MATERIAL_CONCERN`)

```text
record governed acknowledgement / decision
→ mark proposal ACCEPTED
```

Must be transactionally coherent, on the same terms as above. No `SpecificationDraft` mutation and no draft
revision increment occurs in this transaction (§6.2.B).

### 7.3.3 DRAFT-MUTATING-class acceptance (category C)

```text
verify Workshop is ACTIVE
→ verify proposal is still applicable/current (not STALE — see §7.5)
→ construct the canonical typed draft mutation via the closed proposal-class handler (§6.6) —
  never a generic path/value setter
→ optimistic-concurrency check against the current draft revision
→ create the next draft revision (existing PID-004A draft-authoring API)
→ record the decision/provenance (WorkshopDecision, origin = RuleOrigin.WORKSHOP_PROPOSAL)
→ mark the MendelProposal ACCEPTED
→ run deterministic validation
```

Must be atomic: a failure partway through must leave neither an ACCEPTED-but-unapplied proposal nor a draft
mutation without its provenance record. No ACCEPTED proposal of any category may exist claiming a resulting
object/mutation that failed to commit; no resulting canonical change may commit while its proposal still
shows merely PROPOSED due to a partial failure.

In every category, MENDEL does not participate inside the acceptance transaction — it has already returned
by the time a human triggers it, and the acceptance boundary (§7.3.0) makes that structural, not just
procedural.

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

A proposal generated **before** any `SpecificationDraft` yet exists for the candidate (e.g. an early
`ASK_QUESTION` or `THESIS_CHANGE` proposal raised before the first draft revision is authored) does not fall
back to an ambiguous `NULL`/`0` "no revision" value treated inconsistently by different code paths. It
records an explicit, closed sentinel binding state — `generated_against_draft_revision = NO_DRAFT_YET` (or
equivalent explicit, typed sentinel; exact representation is an implementation-time decision within this
invariant) — distinct from any real integer revision. Acceptance of such a proposal is evaluated against
"does a `SpecificationDraft` exist yet for this candidate" using that same explicit sentinel, never against
an untyped absence. This PID does not implement path-level conflict resolution (§19); it keeps the
no-draft-yet case simple and deterministic rather than silently overloading `NULL`/`0`.

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

### 8.3.1 `DraftCapabilityView` — a bounded, derived, pre-finalisation view

MENDEL operates on `SpecificationDraft` state, **before** finalisation. A persisted `DataReadinessAssessment`
does not necessarily exist for a draft — `DataReadinessAssessment` and this view are correctly separated
concepts and must not be conflated. PID-004C defines a bounded concept — named `DraftCapabilityView` here
(the name may be refined at implementation time; the semantics below are fixed) — computed from
authoritative existing DARWIN truth, including as applicable:

* canonical instrument support;
* timeframe support;
* governed fact classes;
* existing `MarketDataset` state;
* historical depth;
* known external/context authorities;
* `DataRequirement`s in the current draft;
* an existing `DataReadinessAssessment`, where one legitimately already exists for this candidate.

`DraftCapabilityView` is: derived; non-semantic; never `StrategyVersion` identity; never a new independent
capability registry; safe to recompute at any time; supplied to MENDEL only as part of its bounded context
(§8.1). It allows MENDEL, before finalisation, to distinguish per data need:

* `SUPPORTED_AND_AVAILABLE`
* `SUPPORTED_BUT_NOT_AVAILABLE`
* `UNSUPPORTED_OR_AUTHORITY_MISSING`
* `UNKNOWN`

(or an equivalent existing-domain-aligned set of meanings — exact naming is an implementation-time decision
within this invariant). PID-004C never invents availability simply because HERMES exists as a system; a
data need is only `SUPPORTED_AND_AVAILABLE` when the existing authoritative contracts above actually say so.
A persisted `DataReadinessAssessment`, where one exists, remains governed entirely by its existing PID-004A
semantics — `DraftCapabilityView` reuses it, never redefines or duplicates it.

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
* the bounded task purpose that triggered the invocation, from the closed vocabulary defined in §11.1.1
  (e.g. `REVIEW_DRAFT`, `EXPLAIN_VALIDATION`), plus any bounded human focus/context text supplied;
* `context_schema_version` — the declared schema version of the bounded input context (§8.1) assembled for
  this run;
* `context_fingerprint` — computed from a deterministic/canonical serialisation of the bounded context
  under its declared `context_schema_version` (§10.5) — never incidental JSON dictionary ordering or
  volatile UI state;
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
* `proposal_category` (`QUESTION` / `ADVISORY` / `DRAFT_MUTATING` — the §6.2/§6.4 mapping, persisted
  explicitly rather than re-derived, so audit tooling need not hardcode the class→category table);
* `proposal_schema_version` — the declared schema version of the typed payload contract this proposal was
  emitted under;
* typed payload (structure varies by class, itself schema-validated against `proposal_schema_version`; a
  closed, class-specific shape per §6.6 — never a generic path/value structure);
* `rationale`;
* `affected_semantic_paths` — audit/presentation metadata only (§6.6), never itself executable;
* `generated_against_draft_revision` (or the explicit `NO_DRAFT_YET` sentinel — §7.5);
* `status` (`PROPOSED` / `ACCEPTED` / `REJECTED` / `STALE`);
* `created_at_utc` / `resolved_at_utc`;
* `resulting_question_id` (nullable FK to `workshop_questions`, set only once accepted for an
  `ASK_QUESTION`-class proposal);
* `resulting_decision_id` (nullable FK to `workshop_decisions`, set only once accepted for a category-B
  (`MATERIAL_CONCERN`) or category-C (draft-mutating) proposal).

## 10.3 The one narrow PID-004B schema change

Widen `QuestionOrigin` (currently the single value `HUMAN`) with one new, locked member —
`QuestionOrigin.MENDEL` (§6.3) — representing a MENDEL-originated question, via a new, separately reviewed
migration that widens migration 0009's `trg_workshop_decisions_content_immutable`-adjacent `CHECK`
constraint on `workshop_questions.origin`. This is exactly the forward seam the existing code comment names,
exercised narrowly: no other PID-004B table, trigger, or constraint changes.

## 10.4 Model identity vs semantic identity

MENDEL's model/runtime identity, `context_schema_version`, and `proposal_schema_version` all belong in
`mendel_runs`/`mendel_proposals` invocation provenance — **never** in `StrategyVersion` semantic identity.
The same strategy semantics produced through different MENDEL versions, or different schema versions, must
remain semantically identical whenever the canonical `SpecificationDraft` content is identical. This mirrors
PID-004's own existing separation of `semantic_fingerprint` from `artifact_record_fingerprint`.

## 10.5 Context fingerprint

`mendel_runs.context_fingerprint` gives auditability: an audit target must be able to state, precisely,
*"proposal P was generated from context schema V, context fingerprint C, draft revision N, provider/model
M, proposal schema Q."* The fingerprint is computed from a deterministic, canonical serialisation of the
bounded, assembled input context (§8.1) **under its declared `context_schema_version`** — never from
incidental JSON dictionary key ordering or irrelevant volatile UI state.

---

# 11. EXECUTION MODEL

## 11.1 Bounded, single-invocation model

A MENDEL invocation operates on exactly one Workshop, one explicit bounded task, and one bounded context.
There is no unconstrained autonomous loop.

### 11.1.1 Bounded task vocabulary — closed, not a generic prompt

The `task` a MENDEL invocation performs is never an implicit generic-agent prompt. It is drawn from a small,
closed, versioned invocation-purpose vocabulary, for example:

* `ANALYSE_AMBIGUITY`
* `REVIEW_DRAFT`
* `SUGGEST_NEXT_QUESTIONS`
* `EXPLAIN_VALIDATION`
* `PROPOSE_DATA_REQUIREMENTS`
* `INTERPRET_RULE`

(exact naming may be refined at implementation time; the set must remain small, closed, and versioned — an
addition is a code/version change, never a free-text value). The human may supply bounded focus/context
text alongside a chosen task (e.g. which rule, which validation finding). That text narrows what MENDEL
reasons about; it never expands MENDEL's authority or tool surface (§11.3). PID-004C explicitly does not
create a generic invocation surface such as:

```text
POST /mendel
{ "prompt": "do anything..." }
```

§12's API already states no endpoint accepts free-form instructions bypassing this bounded task/context
model; this section fixes the closed vocabulary that statement depends on.

## 11.2 No agent swarm — completion-budget protection

Still explicitly excluded from PID-004C, protecting the completion budget (§21) and the roadmap sequencing
(§2):

* autonomous research;
* browser research (unless separately authorised in a future PID);
* agent swarm (multiple cooperating MENDEL agents);
* multi-agent collaboration;
* recursive Claude (recursive subagents spawned by MENDEL's own invocation);
* persistent conversational memory (beyond one bounded task per invocation — §19);
* multi-model routing;
* ATHENA calls (autonomous or otherwise);
* APOLLO calls;
* HELIOS changes;
* DIKE control;
* generic agent framework;
* autonomous strategy-portfolio generation.

One bounded specialist, invoked one bounded task at a time, is sufficient.

## 11.3 Model-exposed tool surface: zero, for PID-004C

For the PID-004C vertical slice, MENDEL receives a complete bounded context (§8.1, §10.5's
`context_schema_version`) assembled entirely by DARWIN before invocation. MENDEL therefore requires **no
model-exposed tools at all**. Specifically, MENDEL is given no:

* shell;
* filesystem browser or arbitrary file read/write;
* SQL;
* Docker;
* Git;
* browser;
* arbitrary HTTP/network access;
* subprocess/process execution;
* DARWIN mutation tool of any kind;
* proposal-acceptance tool (§7.3.0 — MENDEL cannot accept its own proposal, structurally).

The model transport/provider (whatever mechanism the `MendelAdapter`, §11.4, uses to communicate with the
configured Claude service) is not itself a model-exposed research/network tool — it is the fixed
bounded-context-in/typed-proposals-out channel, not a capability MENDEL can direct. Where Claude Code is
the provider, the adapter/provider must be configured so that Claude Code cannot autonomously invoke its
own normal general-purpose tools (shell, file, web, etc.) during a MENDEL invocation.

MENDEL's input is exactly:

```text
bounded typed context
+
bounded task (§11.1.1)
```

MENDEL's output is exactly:

```text
typed proposal set
+
bounded reasoning summary
```

Nothing else. The existing Workshop filesystem workspace (§11.5) may be used by DARWIN **when assembling
context** — MENDEL itself does not need, and does not receive, direct filesystem authority for PID-004C.
This materially strengthens prompt-injection containment (§14): there is no tool for injected source content
to persuade MENDEL to invoke.

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
* no acceptance spoofing: acceptance is exposed only through DARWIN's human-operator acceptance boundary
  (§7.3.0); this PID does not claim cryptographic proof of humanness, only that MENDEL has no capability,
  credential, callback, tool, or internal method able to invoke acceptance itself;
* MENDEL cannot self-accept its own proposal (structurally — §7.3.0, §11.3);
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

This vertical-slice proof must be exercised against all three behavioural categories (§6.2), not only a
draft-mutating (category C) proposal: a category-A `ASK_QUESTION` acceptance must be proven to create a
`WorkshopQuestion` with `origin = QuestionOrigin.MENDEL` and leave `SpecificationDraft` and its revision
untouched; a category-B `MATERIAL_CONCERN` acceptance must be proven to record its acknowledgement/decision
and leave `SpecificationDraft` and its revision untouched; a category-C proposal (e.g. `SEMANTIC_CHANGE`)
must be proven to increment the draft revision and change the relevant validation finding, exactly as
described above.

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
* accepted proposals are applied by DARWIN, never by MENDEL, through the governed, category-specific
  acceptance transaction (§7.3), and only a category-C (draft-mutating) acceptance mutates
  `SpecificationDraft` (§6.2);
* deterministic validation reruns after every accepted category-C (draft-mutating) proposal (§6.2.C, §7.3.3)
  — never merely because a question was created (category A) or a concern was acknowledged (category B);
* proposal history (`mendel_proposals`, `mendel_runs`) is durable and auditable (§10), including
  `proposal_category`, `context_schema_version`, and `proposal_schema_version`;
* all proofs in §15 are green, including the three-category vertical-slice proof (§15.1) and the
  prompt-injection proof (§15.5).

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

# 25. AMENDMENT — BOUNDED HARDENING PASS (2026-09-18)

Following Architect verdict `GREEN_DARWIN_PID004C_DEFINITION_WITH_BOUNDED_HARDENING_REQUIRED` on the
original draft (head `359d836a2002a17e462763f51b5a4605cd1d9f06`), this document was corrected in place —
no reopening or expansion of the accepted architecture — to:

1. replace vague "all non-question proposals mutate the draft" language with three explicit behavioural
   categories — QUESTION, ADVISORY, DRAFT-MUTATING — each with its own acceptance flow (§6.2, §6.4);
2. lock `QuestionOrigin.MENDEL` as the exact new enum member now, rather than leaving it an
   implementation-time decision (§6.3, §10.3);
3. state explicitly that `affected_semantic_paths` is audit/presentation metadata only, never an executable
   generic mutation mechanism, and that every draft-mutating proposal class is applied through a closed,
   typed, class-specific DARWIN handler — never a generic path/value patch engine (§6.6);
4. replace the unprovable "verifies the actor is a genuine human" claim with the mechanically enforceable
   invariant that MENDEL has no capability, credential, callback, tool, or method able to invoke acceptance
   itself (§7.3.0, §14);
5. define a bounded, derived `DraftCapabilityView` distinguishing `SUPPORTED_AND_AVAILABLE` /
   `SUPPORTED_BUT_NOT_AVAILABLE` / `UNSUPPORTED_OR_AUTHORITY_MISSING` / `UNKNOWN`, correctly separated from
   `DataReadinessAssessment` (§8.3.1);
6. tighten the tool boundary to zero model-exposed tools for this slice, with an explicit forbidden list and
   a statement that the model transport is not itself a tool (§11.3);
7. define a small, closed, versioned bounded task vocabulary, ruling out a generic free-form prompt
   endpoint (§11.1.1);
8. add `context_schema_version` / `proposal_schema_version` to the machine contracts, and tie the context
   fingerprint to a deterministic serialisation under its declared schema version (§10.1, §10.2, §10.5);
9. correct §7.3's atomicity requirement to match each behavioural category exactly, rather than a single
   generic transaction shape (§7.3.0–§7.3.3);
10. define an explicit `NO_DRAFT_YET` sentinel for a proposal generated before any draft exists, rather than
    an ambiguous `NULL`/`0` (§7.5);
11. made the completion-budget exclusion list in §11.2 explicit and exhaustive per the Architect's own
    wording, and propagated the three-category correction into §4's authority-chain diagram and §21's
    completion criteria for internal consistency;
12. no change required — HELM's original authorship of the reviewed artefact stands; ROGUE holds
    architecture/delivery-control review going forward.

No implementation, migration, dependency, or Workshop/product code changed. Only this file changed.

---

# EXPECTED NEXT VERDICT REQUEST

`GREEN_DARWIN_PID004C_DEFINITION_HARDENED_READY_FOR_ARCHITECT_ACCEPTANCE`
