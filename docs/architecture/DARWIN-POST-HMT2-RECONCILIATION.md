# DARWIN — POST-HMT-2 RECONCILIATION AND APOLLO FACTUAL-BASIS CLOSURE

**Product:** DARWIN  
**Parent authority:** `PID.md`  
**Architect:** THE GOAL / DARWIN Central Architecture  
**Date:** 2026-09-28  
**Status:** ARCHITECTURALLY ACCEPTED FACTUAL BASIS — DOCUMENTATION ONLY  
**DARWIN baseline:** `a886b1b241d8eb8063db408e5dd146618af630ba`  
**HERMES baseline:** `4cece04bbc538828576b82e93fb20818b8f5b429`  
**Source work:** DARWIN POST-HMT-2 RECONCILIATION + APOLLO PID-006 FACTUAL BASIS  
**Terminal ruling:** `GREEN_DARWIN_POST_HMT2_RECONCILIATION_ARCHITECTURALLY_ACCEPTED`

---

## 1. Purpose

This record closes the factual reconciliation required after HERMES HMT-2 and before APOLLO PID-006 implementation.

It does four things:

1. records what DARWIN and HERMES actually contain at the verified baselines;
2. separates accepted evidence from agent error or overreach;
3. makes Central Architecture rulings on the unresolved design questions;
4. establishes the authoritative sequence for PID-006 APOLLO and later PID-005 ATHENA delivery.

This document does not implement APOLLO, ATHENA, GC live ingestion, DIKE evaluation, broker integration or live trading.

---

## 2. Verified programme state

At the reconciliation boundary:

- DARWIN `main` = `a886b1b241d8eb8063db408e5dd146618af630ba`;
- HERMES `main` = `4cece04bbc538828576b82e93fb20818b8f5b429`;
- DARWIN PR #16 is merged and remains the accepted ATHENA + DIKE archaeology factual basis;
- HERMES HMT-2 is CLOSED GREEN;
- the governed HMT-2 corpus contains 448 selected GC sessions and the corpus selection manifest identity is:
  `962f49c2d607d4aaad6d511314bcc47ee02491f85feb019849fc02390c2a497c`;
- DARWIN `main` currently has no GitHub branch protection. This is a governance defect, not a scientific-data defect and not a reason to bypass normal review discipline.

No implementation authority is implied by these facts.

---

## 3. HERMES research authority after HMT-2

DARWIN now recognises **two distinct governed HERMES historical authorities**.

### 3.1 Candle authority

The pre-existing canonical candle authority remains valid and useful for `XAU_USD` research:

- M1;
- M5;
- M15;
- H1;
- H4;
- D1;
- canonical unified candle view.

DARWIN's existing immutable candle `MarketDataset` remains authoritative as the DARWIN-side in-memory representation of this contract.

It is not obsolete.

### 3.2 HMT-2 event authority

HERMES now also provides governed GC event/microstructure truth based on canonical market-event contracts including:

- `MarketTradeEvent`;
- `TopOfBookEvent`;
- actual GC contract identities;
- deterministic event ordering/identity;
- partition semantic hashes;
- physical artefact hashes;
- deterministic event-set hashes;
- evidence manifests;
- lineage records;
- HMT-2 session/corpus identities.

This is a separate research authority.

It does not replace the candle contract.

DARWIN must not collapse the two into one untyped dataset merely for implementation convenience.

---

## 4. HERMES consumer boundary ruling

Existing HERMES surfaces are sufficient to begin a DARWIN read-only integration.

Useful implemented surfaces include, subject to exact version verification at implementation time:

- `market_truth.partition.PartitionReader(...).read_events(...)`;
- lineage reads and lineage indexing;
- session canonical-event loading/verification;
- frozen HMT-2 manifest and session-contract activity artefacts;
- event-set/partition/evidence identities.

### Ruling

DARWIN shall build a **DARWIN-side adapter/composition boundary first**.

HERMES is not modified merely to make DARWIN integration convenient.

A new HERMES API is justified only if DARWIN can demonstrate a concrete consumer contract that cannot be safely constructed from the existing governed read-only surfaces.

---

## 5. Important storage correction

HMT-2 canonical storage is self-verifying through governed content identities.

It is **not** currently protected by a universal OS-level immutable-file attribute.

Therefore DARWIN must never equate:

`content-addressed / hash-verifiable`

with:

`filesystem cannot physically be modified`.

A DARWIN HMT-2 load must verify the governed identities it relies on. It must not trust a path merely because the path exists.

Scientific identity is the evidence.

The filesystem path is only a locator.

---

## 6. DARWIN post-HMT-2 capability map

### Already real

DARWIN already has:

- Product Constitution;
- Docker/PostgreSQL foundation;
- research/evidence persistence;
- HERMES candle adapter;
- immutable `MarketDataset`;
- deterministic dataset fingerprints;
- `InstrumentDefinition`;
- `ResearchRun`;
- SCOUT;
- Specification;
- immutable `StrategyVersion`;
- Strategy Workshop;
- MENDEL;
- ARENA product/UI foundation;
- DIKE identity state;
- evidence hierarchy including `ATHENA_RESULT` and `APOLLO_PROOF`.

### Genuinely missing

The following remain unimplemented at this boundary:

- `CanonicalStrategyCompiler`;
- `ExecutableStrategyPlan`;
- concrete `ParameterSetVersion`;
- concrete `ExecutionPolicyVersion`;
- protected research partition/holdout governance;
- APOLLO causal replay engine;
- APOLLO order/fill model;
- APOLLO ledger/equity engine;
- APOLLO deterministic proof evidence;
- DARWIN-side HMT-2 event-dataset binding;
- governed GC instrument/economic execution semantics;
- ATHENA engine.

The absence of these contracts is why APOLLO must not be improvised directly from legacy code.

---

## 7. ARENA clarification

The Python package boundary may contain little or no APOLLO/ATHENA-specific server implementation today.

That must not be restated as "ARENA does not exist."

ARENA is already a real first-class DARWIN product surface implemented through the existing frontend/core delivery model.

PID-005 and PID-006 extend ARENA; they do not recreate it.

---

# 8. Central Architecture rulings on the nine open decisions

## 8.1 GC long-term status

### Ruling: GC becomes a governed DARWIN research instrument family.

DARWIN is multi-instrument by constitution and HERMES now has real governed GC market truth.

However:

`GC root market identity`
≠
`actual GC futures contract`
≠
`continuous/rolled series`
≠
`execution/economic contract`.

DARWIN must preserve each separately.

The first GC work shall use **actual contract identity** and shall not pretend a bare `GC` root is a tradeable historical instrument.

A continuous roll policy is not required for the first HMT-2 scientific experiment.

---

## 8.2 Intrabar ambiguity

### Ruling: do not add `TP_FIRST` merely because legacy code supported it.

The first APOLLO candle engine uses the existing conservative doctrine:

`CONSERVATIVE_SL_FIRST`

whenever lower-resolution evidence cannot establish the order.

Where better governed evidence exists, including lower timeframe or HMT-2 event ordering, APOLLO uses the better evidence rather than invoking an arbitrary ambiguity policy.

The existing Specification field is not expanded casually.

Future alternative ambiguity treatments belong to an explicit versioned execution methodology/policy and require separate scientific justification.

---

## 8.3 GC roll doctrine

### Ruling: deferred for first HMT-2 value proof.

First GC experiments operate on actual contract/session identities.

No synthetic continuous future is required.

No front-month selector may be invented.

If a later strategy requires continuous GC, the roll derivation becomes its own governed, versioned market-data methodology with provenance back to actual contracts.

---

## 8.4 ExecutionPolicyVersion ownership

### Ruling: shared DARWIN research identity, not APOLLO-private state.

`ExecutionPolicyVersion` is:

- independent from `StrategyVersion`;
- immutable;
- versioned;
- fingerprinted;
- bound to every relevant research run;
- consumable by ATHENA and APOLLO;
- not owned semantically by either engine.

The implementation may live in a neutral shared DARWIN domain such as `core` or another Architect-approved research-contract module.

It must not be buried inside APOLLO so ATHENA later has to import APOLLO internals.

---

## 8.5 NEXT_M1_OPEN semantics

### Ruling: true next-bar-open or fail closed.

Silent fallback from `NEXT_M1_OPEN` to close is prohibited.

The first APOLLO slice does not need M1 disambiguation and therefore does not implement this behaviour.

When introduced, it must use the actual next eligible canonical bar open under explicit causal/session rules.

Until then, a strategy or execution policy requiring it is:

`ENGINE_CAPABILITY_BLOCKED`

not silently approximated.

---

## 8.6 Costs

### Ruling: explicit policy always; omission never.

A named `ZERO_COST` execution policy may be used for:

- engine determinism tests;
- mechanical acceptance fixtures;
- deliberately idealised research explicitly labelled as such.

It must never arise through omission/default accident.

A real strategy-performance claim intended to become `APOLLO_PROOF` must bind an explicit economically justified cost policy appropriate to the tested market/execution model.

---

## 8.7 Partial exits and multi-leg positions

### Ruling: true position reduction is a first-class capability.

A partial exit reduces an existing position quantity through an explicit fill/ledger event.

It is not represented as a fake second whole position merely to emulate reduction.

Separately valid strategy legs may still be separate positions when the strategy semantics genuinely define them as such.

"Multi-leg strategy" and "partial exit" are not synonyms.

---

## 8.8 Holdout / validation ownership

### Ruling: shared DARWIN research-governance contract.

Train/development/validation/protected-holdout identity is not owned by ATHENA or APOLLO.

Introduce a versioned shared concept equivalent to:

`ResearchPartitionPolicyVersion`

and explicit dataset/run roles such as:

- `DEVELOPMENT`;
- `VALIDATION`;
- `PROTECTED_HOLDOUT`.

ATHENA may search development and authorised validation data.

ATHENA must not consume protected APOLLO holdout data.

APOLLO access to a protected holdout is an evidence event and must be recorded so repeated proof attempts cannot masquerade as pristine independent tests.

Repeated holdout use degrades evidentiary independence and must be visible.

---

## 8.9 Branch protection

### Ruling: separate governance remediation.

DARWIN `main` being unprotected is a real control gap.

It does not block documentation authoring or architecture review.

It does require a separately authorised governance remediation.

A denied GitHub administrative action must not be bypassed through an alternate mechanism.

---

# 9. Shared semantics vs independent proof

This is a permanent DARWIN invariant.

Correct architecture:

```text
StrategyVersion
      ↓
CanonicalStrategyCompiler
      ↓
ExecutableStrategyPlan
      ├───────────────────────┐
      ↓                       ↓
ATHENA evaluator          APOLLO engine
exploration               independent causal proof
```

Shared:

- strategy meaning;
- composition;
- timeframes;
- directions;
- parameter references;
- derived-fact references;
- session semantics;
- intrinsic exits;
- instrument applicability.

Independent:

- replay engine;
- causal clock;
- order/fill processing;
- position state;
- same-bar/event resolution mechanics;
- trade ledger;
- economics;
- proof evidence.

Legacy ATHENA's direct driving of legacy Apollo is a documented anti-pattern and shall not be recreated.

---

# 10. Research sequencing amendment

PID numbers remain historical identities:

- PID-005 = ATHENA;
- PID-006 = APOLLO.

Implementation order changes deliberately:

```text
HMT-2 CLOSED GREEN
        ↓
post-HMT-2 reconciliation
        ↓
PID-006 definition
        ↓
APOLLO shared research contracts
        ↓
APOLLO XAUUSD candle causal core
        ↓
HMT-2 event-dataset usability proof
        ↓
GC governed research onboarding
        ↓
HMT-2 trading-value experiment
        ↓
PID-005 implementation
        ↓
APOLLO independent proof of ATHENA-selected candidates
        ↓
Qualification
```

This is not a renumbering.

It is a roadmap amendment.

---

# 11. HMT-2 value programme — three separate questions

The programme must not collapse these into one claim.

## HMT2-DATA

Can DARWIN read the governed HMT-2 corpus, verify its identities and reproduce deterministic event input?

This is a **data-usability** question.

No trading edge is implied.

## HMT2-GC-PROOF

After GC research/execution semantics are explicitly governed, does APOLLO produce reproducible causal strategy evidence on actual GC contracts?

This is a **trading research** question.

## HMT2-INCREMENTAL-VALUE

For controlled, same-semantics experiments, what does event-level truth change relative to a deliberately coarser representation of the same underlying market evidence?

Measure at least:

- ambiguous-exit resolution;
- entry/fill timing;
- stop/target ordering;
- trade sequence;
- MAE/MFE;
- expectancy;
- drawdown;
- economic result;
- robustness.

Only this third question measures HMT-2's incremental value.

---

# 12. First HMT-2 comparison design

The preferred first trading-value experiment is GC-native and **actual-contract based**.

It must not compare OTC XAUUSD execution against COMEX GC execution and attribute the difference to market-data resolution.

A valid design keeps constant:

- actual GC contract/session;
- frozen strategy semantics;
- parameter set;
- execution policy;
- quantity/economic model;
- cost policy;
- research partition role.

Then compare:

1. event-aware causal resolution; versus
2. an explicitly defined coarse control representation of the same underlying GC evidence.

If a coarse control representation is not a governed HERMES product, it must be explicitly labelled an experimental projection and must never be persisted/presented as canonical market truth.

---

# 13. Legacy reuse rulings

Accepted factual direction:

| Area | Ruling |
|---|---|
| causal replay clock | REBUILD |
| existing causal external-fact timing primitive | REUSE_AS_IS narrowly |
| position lifecycle patterns | REUSE_WITH_ADAPTATION |
| order -> fill lifecycle | REBUILD |
| wick SL/TP principles | REUSE_WITH_ADAPTATION |
| break-even | REBUILD generic primitive |
| partial exits | REBUILD true reduction |
| trailing stops | REBUILD |
| hard-coded same-bar collision handling | REJECT |
| wick touch semantics | REUSE_AS_IS as principle |
| lower-timeframe disambiguation | REUSE_WITH_ADAPTATION |
| same-bar close fill assumption | REJECT |
| optional/report-only costs | REJECT as proof model |
| continuous ledger pattern | REUSE_WITH_ADAPTATION |
| ATHENA-named force-flat coupling | REJECT naming/coupling |
| realised P&L patterns | REUSE_WITH_ADAPTATION |
| missing unrealised P&L/equity | REBUILD |
| drawdown formula | REUSE_WITH_ADAPTATION |
| retrospective MAE/MFE discipline | REUSE_WITH_ADAPTATION |
| three-layer deterministic hash concept | REUSE_AS_IS conceptually; relocate into governed DARWIN proof domain |

"Reuse" never means copying a legacy module without checking its dependencies and invariants.

---

# 14. Documentation consequences

The following are now authoritative companion documents:

- `docs/architecture/AMENDMENT-A005-POST-HMT2-RESEARCH-SEQUENCING.md`;
- `docs/pids/PID-005-ATHENA.md`;
- `docs/pids/PID-006-APOLLO.md`.

`PID.md` and `MEMORY.md` must be updated in the docs-only merge to point at this reconciliation and Amendment A-005.

---

# 15. Closure

The factual-basis investigation is complete enough to author PID-006.

No additional broad APOLLO archaeology is authorised.

Future source investigation must be tied to a specific unresolved implementation question.

**Verdict:**

`GREEN_DARWIN_POST_HMT2_RECONCILIATION_ARCHITECTURALLY_ACCEPTED`

**Next gate:**

`GREEN_DARWIN_PID006_DEFINITION_ACCEPTED`

Only after PID-006 definition acceptance may the first APOLLO implementation work package be dispatched.
