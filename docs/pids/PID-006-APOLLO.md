# PID-006 — APOLLO INDEPENDENT CAUSAL PROOF ENGINE

**Parent authority:** `PID.md` + Amendment A-005  
**Product:** DARWIN  
**Module:** APOLLO  
**Owner:** THE GOAL / DARWIN Architect  
**Delivery controller:** ROGUE  
**Implementation:** FORGE under bounded work packages  
**Infrastructure:** HELM where required  
**Date:** 2026-09-28  
**Status:** ARCHITECT DEFINITION FOR REVIEW — NO IMPLEMENTATION AUTHORITY UNTIL ACCEPTED  
**Canonical definition baseline:** `a886b1b241d8eb8063db408e5dd146618af630ba`  
**HERMES factual baseline:** `4cece04bbc538828576b82e93fb20818b8f5b429`

---

# 1. Purpose

APOLLO is DARWIN's independent deterministic causal historical proof engine.

It answers:

> Given one frozen strategy meaning, one exact parameter set, exact governed historical inputs, one exact execution/economic policy and explicit research-partition identity, what would have happened under causal sequential replay?

APOLLO produces:

`APOLLO_PROOF`

only when its evidence contract and methodology requirements are satisfied.

APOLLO does not optimise.

APOLLO does not place live trades.

APOLLO does not mutate `StrategyVersion`.

APOLLO does not own market truth.

---

# 2. Why APOLLO lands before ATHENA engine

Amendment A-005 deliberately changes implementation order while preserving PID numbering.

Reason:

ATHENA is useful only if the strategy evaluation/proof substrate is scientifically trustworthy.

HMT-2 also creates an urgent economic question:

> Does event/microstructure truth improve trading research enough to justify further engineering?

Therefore APOLLO's causal/evidence core is established before ATHENA's optimiser.

---

# 3. Proof independence

Permanent invariant:

> Share semantic truth, not the backtest engine.

Correct boundary:

```text
StrategyVersion
      ↓
CanonicalStrategyCompiler
      ↓
ExecutableStrategyPlan
      ├─────────────────────────┐
      ↓                         ↓
ATHENA evaluator            APOLLO engine
exploration                 independent proof
```

APOLLO may consume the same compiled semantic meaning as ATHENA.

APOLLO must have its own:

- causal clock;
- replay loop;
- order/fill mechanics;
- position state;
- SL/TP/BE/trailing implementation;
- ledger;
- accounting;
- ambiguity accounting;
- proof evidence.

Legacy architecture in which ATHENA directly drove Apollo is explicitly rejected.

---

# 4. APOLLO proof identity

Every proof binds at minimum:

- `StrategyVersion`;
- `CanonicalStrategyCompiler` version;
- `ExecutableStrategyPlan` fingerprint;
- exact `ParameterSetVersion`;
- `InstrumentDefinition`;
- exact dataset binding set;
- exact `ResearchPartitionPolicyVersion` and data role;
- exact `ExecutionPolicyVersion`;
- DIKE state/policy identity;
- derived-fact algorithm identities where used;
- APOLLO engine/build version;
- causal/alignment methodology version;
- cost/economic methodology identity;
- deterministic configuration fingerprint.

If any identity needed to reproduce the proof is missing, durable `APOLLO_PROOF` evidence is not created.

---

# 5. Shared research contracts introduced before the engine

PID-006's first gate establishes shared DARWIN research contracts.

These contracts are not APOLLO-private semantics.

## 5.1 CanonicalStrategyCompiler

Deterministic.

Versioned.

Side-effect free.

No market queries.

No trade simulation.

No ranking.

No broker calls.

No arbitrary Python/eval/plugin execution.

Input:

`StrategyVersion`

Output:

`ExecutableStrategyPlan`.

## 5.2 ExecutableStrategyPlan

Governed immutable data representing the exact machine meaning of a StrategyVersion.

Preserves at least:

- ATOMIC/ALL/ANY/SEQUENCE/CONTEXT_TRIGGER composition;
- direction;
- timeframe bindings;
- conditions;
- parameter references;
- derived-fact identities;
- sessions;
- expiry;
- intrinsic exits;
- instrument applicability;
- declared ambiguity requirements.

ATHENA and APOLLO may not reinterpret it differently.

## 5.3 ParameterSetVersion

Immutable exact parameter assignment.

Required even when every parameter is fixed.

No hidden mutable dictionary becomes proof identity.

## 5.4 ExecutionPolicyVersion

Shared immutable execution/economic research policy.

Separate from StrategyVersion.

## 5.5 ResearchPartitionPolicyVersion

Shared immutable governance of data roles and protected holdout.

These shared contracts should live in a neutral DARWIN domain, not inside ATHENA or APOLLO implementation internals.

---

# 6. Data boundaries

## 6.1 Candle data

Existing immutable `MarketDataset` is retained.

It remains the first APOLLO market-data input.

APOLLO consumes it in memory.

APOLLO never queries HERMES SQL candle-by-candle.

## 6.2 Event data

HMT-2 does not get forced into `MarketDataset`.

Introduce a typed immutable binding equivalent to:

`MarketEventDataset`

or an Architect-approved typed `ResearchDataset` family.

It binds scientific identity, not arbitrary filesystem paths.

At minimum preserve:

- HERMES commit/contract identity;
- HMT-2 manifest/session identity;
- actual contract identity;
- event families;
- time coverage;
- event-set hash;
- partition semantic hashes;
- evidence/lineage identity;
- deterministic ordering methodology.

DARWIN remains a read-only consumer.

## 6.3 Mixed inputs

A future APOLLO run may bind multiple typed datasets, for example:

- H1 candle strategy input;
- M1 disambiguation input;
- GC event context input.

Every input is explicit in proof identity.

---

# 7. GC / XAUUSD boundary

APOLLO must never equate COMEX GC futures with OTC `XAU_USD`.

For GC research preserve:

```text
GC market family
≠ actual GC contract
≠ continuous GC derivation
≠ execution/economic contract
```

The first GC scientific programme uses actual contracts.

No front-month or roll policy is invented.

A continuous future is introduced only as a separately versioned derived methodology if later research requires it.

---

# 8. ExecutionPolicyVersion minimum contract

A proof policy must make relevant assumptions explicit.

Minimum conceptual fields include:

### Timing
- signal availability rule;
- decision timestamp rule;
- order eligibility timestamp;
- fill timing rule;
- next-bar/open semantics where supported;
- same-event eligibility.

### Price/fill
- market/limit/stop behaviour supported by the slice;
- entry price rule;
- exit price rule;
- spread model;
- slippage model;
- commission/fee model.

### Ambiguity
- lower-resolution disambiguation hierarchy;
- conservative fallback policy;
- unsupported ambiguity behaviour.

### Economics
- quantity unit;
- fixed research quantity or separately governed sizing-policy identity;
- multiplier/contract semantics where applicable;
- account currency/conversion where applicable;
- starting capital if equity/drawdown are monetary.

### Session
- session boundary behaviour;
- optional force-flat behaviour when explicitly enabled.

No hidden default may alter proof economics.

---

# 9. First-slice quantity/sizing ruling

PID-006 V1 does not import a legacy percent-risk sizing function merely because it exists.

First proof uses an explicit fixed research quantity/economic normalisation.

This avoids mixing:

- strategy edge;
- sizing policy;
- account risk model.

`SizingPolicyVersion` remains a distinct future axis.

If later evidence needs risk-based sizing, it is introduced explicitly and versioned.

---

# 10. Cost doctrine

Costs are mandatory policy identity.

Allowed:

- an explicit named `ZERO_COST` policy for mechanical/determinism acceptance;
- explicit idealised research labelled as such.

Not allowed:

- omitted costs silently meaning zero;
- report-time cost overlays that do not participate in fills/economics;
- real-world proof claims under an accidental zero-cost model.

A real `APOLLO_PROOF` performance claim binds an economically defensible cost policy.

---

# 11. Causal clock

At proof time `T`, APOLLO may observe only information available at `T`.

Mechanically test at least:

- candle close visibility;
- higher-timeframe close visibility;
- lower-timeframe visibility;
- derived-fact warm-up/availability;
- external/context observation time;
- HMT-2 event ordering;
- contract/session facts;
- roll/continuous-series facts if ever used;
- future highs/lows;
- retrospective metrics such as MFE/MAE.

MFE/MAE can be calculated after-the-fact for evidence.

They must never be available to the live decision path.

---

# 12. Candle replay

The APOLLO candle loop iterates the governed candle timeline.

It must not be keyed only to rows where a signal already exists.

Doing so would skip market time and weaken causal reasoning.

The engine advances causally over every required market interval/event needed by the plan.

---

# 13. Wick / intrabar doctrine

OHLC high/low are first-class touch evidence.

A level touched by high/low counts as touched according to the frozen execution policy.

Resolution hierarchy:

1. better governed temporal evidence, e.g. lower timeframe, if available;
2. event-level evidence, where the same tested market genuinely supplies it;
3. otherwise classify ambiguity;
4. apply the explicit deterministic fallback.

Initial fallback:

`CONSERVATIVE_SL_FIRST`.

Do not add `TP_FIRST` merely to mimic legacy code.

---

# 14. NEXT_M1_OPEN

No silent fallback.

If an execution policy requests `NEXT_M1_OPEN`, the engine must either:

- fill at the actual next eligible canonical M1 open under explicit rules; or
- fail preflight/capability assessment.

First vertical slice does not require this capability.

---

# 15. Order -> fill model

APOLLO has an explicit lifecycle:

```text
strategy decision
    ↓
order intent
    ↓
eligibility/validation
    ↓
fill
    ↓
position/ledger mutation
```

A decision never jumps directly to an open position.

Each fill records:

- timestamp;
- side;
- quantity;
- raw market price reference;
- execution price;
- spread/slippage;
- fees;
- originating order/decision identity;
- execution-policy identity.

Unsupported order types fail closed.

---

# 16. Position model

Position state is derived from immutable fill/adjustment events.

At minimum support the first-slice single-position lifecycle:

- open;
- active;
- close.

Later capability adds:

- partial reduction;
- stop adjustment/break-even;
- trailing stop;
- multiple legitimate positions/strategy legs.

A partial exit is a true quantity reduction.

It is not emulated by inventing extra whole positions.

---

# 17. SL / TP

SL and TP evaluation is extracted into deterministic engine primitives.

No strategy-specific god-object owns generic exit mechanics.

Rules are driven by:

- ExecutableStrategyPlan's intrinsic exit semantics;
- ExecutionPolicyVersion mechanics;
- current position state;
- causal market evidence.

---

# 18. Break-even

Break-even is a generic governed stop-adjustment primitive.

It must not inherit one legacy strategy's two-leg implementation.

A break-even adjustment is itself an evidence event with time, trigger and resulting stop state.

---

# 19. Partial exits

True reduction:

```text
position quantity Q
      ↓ exit fill q < Q
remaining quantity Q-q
```

Ledger economics and MAE/MFE continue correctly across the remaining exposure.

This capability is outside the first minimal slice but its data model must not make it impossible.

---

# 20. Trailing stops

Built fresh as a generic primitive.

Trailing policy records:

- trigger;
- reference;
- distance/algorithm;
- update frequency;
- monotonicity rule;
- causal stop-state history.

No implementation is inferred from legacy because none exists to reuse safely.

---

# 21. Ledger and equity

APOLLO requires a deterministic continuous ledger.

At minimum preserve:

- order intents;
- fills;
- position state transitions;
- realised P&L;
- unrealised P&L;
- fees/costs;
- balance;
- equity;
- peak equity;
- drawdown;
- exposure;
- trade completion;
- exit reason.

The equity curve updates causally while positions are open.

Trade-close-only equity is insufficient.

---

# 22. MAE / MFE

For each completed trade APOLLO records:

- MAE;
- MFE;
- causal interval over which each was measured;
- price/economic representation used.

They are retrospective evidence only.

No strategy condition can access its own future MAE/MFE.

---

# 23. Deterministic proof hashes

APOLLO emits independent deterministic identities for at least:

1. decision stream;
2. trade/fill sequence;
3. economic outcome.

A proof envelope also fingerprints:

- plan/compiler;
- parameter set;
- data;
- execution policy;
- research partition;
- engine/methodology.

Two identical runs must produce identical deterministic evidence.

Wall-clock audit timestamps are metadata, not semantic hash input.

---

# 24. Research partition / holdout governance

APOLLO consumes explicit data roles.

For protected holdout:

- access is deliberate;
- access is recorded;
- exact strategy/configuration tested is recorded;
- repeated holdout proof attempts remain visible;
- a candidate cannot be repeatedly tuned after holdout observation and still be described as pristine independent proof.

The first mechanical engine acceptance may use development data.

The first programme-level independent proof must use an explicitly governed proof partition.

---

# 25. Failure semantics

Never turn engine defects into performance.

Examples:

- missing algorithm/version;
- unsupported fill mode;
- inconsistent dataset binding;
- future-data exposure;
- parameter mismatch;
- corrupt HERMES hash;
- impossible order state;
- economic contract missing.

These produce explicit engine/preflight failures.

They do not produce a losing trade or a `-999999` score.

---

# 26. APOLLO evidence vs proof eligibility

Not every successful engine run automatically becomes durable independent proof.

A run can be mechanically valid while failing proof-governance requirements, e.g.:

- development partition rather than holdout;
- explicit idealised zero-cost policy;
- synthetic fixture;
- insufficient temporal/trade coverage.

Persist the run honestly.

Only label `APOLLO_PROOF` when the configured proof-evidence gate is satisfied.

If current `EvidenceLevel` granularity cannot express useful pre-proof APOLLO runs without confusion, PID-006 implementation must introduce a non-proof run/status distinction without weakening `APOLLO_PROOF`.

---

# 27. First APOLLO vertical slice — XAUUSD candle core

The first implementation proves APOLLO itself, not HMT-2.

Use:

- one genuine immutable DARWIN `StrategyVersion`;
- one simple supported semantic form;
- `XAU_USD`;
- one bounded governed `MarketDataset`;
- one exact `ParameterSetVersion`;
- one frozen `ExecutionPolicyVersion`;
- fixed research quantity;
- explicit cost policy;
- `DIKE_DISABLED`;
- no ATHENA;
- no optimisation.

Minimum mechanics:

- semantic compilation;
- sequential causal candle loop;
- explicit order -> fill;
- entry range validation;
- wick SL/TP;
- conservative same-bar fallback;
- single position;
- deterministic realised/unrealised P&L;
- bar-by-bar equity/drawdown;
- trade ledger;
- MAE/MFE;
- proof hashes.

Acceptance:

run independently at least twice and reproduce exact semantic evidence.

---

# 28. First-slice exclusions

Not required in the first XAUUSD core slice:

- GC;
- HMT-2 event data;
- continuous futures;
- roll policy;
- DIKE_GUARDED;
- trailing stops;
- partial exits;
- break-even;
- multiple simultaneous strategy legs;
- M1 ambiguity disambiguation;
- `NEXT_M1_OPEN`;
- risk-based sizing;
- broker/live execution;
- ATHENA.

These are later gates, not forgotten requirements.

---

# 29. HMT-2 Gate 1 — data usability

After APOLLO candle core:

DARWIN proves it can bind and consume HMT-2 event truth read-only.

This gate establishes:

- exact HERMES/HMT-2 identity;
- 448-session manifest consumption;
- session/actual-contract identity;
- event-family loading;
- semantic hash verification;
- deterministic event ordering;
- repeatable input fingerprint.

No trading edge claim.

No GC P&L claim.

Expected verdict:

`GREEN_DARWIN_PID006_HMT2_DATA_USABILITY_ACCEPTED`

---

# 30. HMT-2 Gate 2 — GC research onboarding

Before a GC economic/trading proof, establish governed GC research semantics.

At minimum:

- GC market-family `InstrumentDefinition`-equivalent;
- actual contract identity binding;
- quantity/price units;
- minimum price increment/tick semantics;
- contract multiplier/economic conversion where monetary P&L is claimed;
- cost policy;
- fixed research quantity;
- session semantics.

No continuous roll is required for the first experiment.

Use actual contracts.

All externally sourced exchange/economic facts require evidence and versioned definition identity.

---

# 31. HMT-2 Gate 3 — incremental value experiment

After GC onboarding:

Use the same actual contract/session and frozen strategy/configuration.

Compare:

- full event-aware causal resolution; versus
- deliberately coarser controlled representation of the same underlying GC evidence.

Do not compare GC to XAUUSD and call the difference HMT-2 value.

Measure at least:

- ambiguous event count;
- resolved event count;
- entry/fill timing;
- SL/TP ordering;
- trade sequence;
- trade count;
- MAE/MFE;
- expectancy;
- drawdown;
- economic result.

Negative result is valid.

If HMT-2 adds little measurable value, record that.

Do not protect sunk engineering investment by manufacturing a positive conclusion.

---

# 32. Cross-market GC -> XAUUSD context

This is a later experiment class.

GC order-flow facts used in an XAUUSD strategy are **context**, not XAUUSD execution truth.

Requirements include:

- explicit cross-instrument dependency;
- causal observation timestamp;
- context algorithm/version;
- no future leakage;
- independent XAUUSD execution data.

Do not mix this with the first GC-native event-resolution experiment.

---

# 33. DIKE

First APOLLO slice binds:

`DIKE_DISABLED`

and proves that identity is present.

No DIKE evaluator is built in the core slice.

Later DIKE proof requires one frozen `DIKEPolicyVersion`.

TRON remains sovereign for live hard limits.

---

# 34. ARENA

APOLLO becomes first-class in ARENA.

Minimum run detail:

- StrategyVersion;
- compiler/plan fingerprint;
- instrument;
- dataset bindings/provenance;
- research-partition role;
- parameter set;
- execution policy;
- DIKE state;
- engine/methodology versions;
- run state;
- trade count;
- costs;
- return/expectancy;
- balance/equity curve;
- drawdown;
- MAE/MFE;
- ambiguity events;
- trade/fill ledger;
- proof hashes;
- proof-eligibility status.

No fabricated/demo evidence in production.

A human must be able to answer:

> What exact assumptions and data created this result?

from ARENA alone.

---

# 35. Internal delivery gates

## PID-006A — shared research/proof contracts

Build/prove:

- `CanonicalStrategyCompiler`;
- `ExecutableStrategyPlan`;
- `ParameterSetVersion`;
- `ExecutionPolicyVersion`;
- `ResearchPartitionPolicyVersion`;
- APOLLO proof/run identity;
- capability/preflight model;
- evidence fingerprints.

No historical trade engine yet.

Expected:

`GREEN_DARWIN_PID006A_PROOF_CONTRACTS_ACCEPTED`

## PID-006B — XAUUSD candle causal core

Build/prove the first bounded vertical slice in §27.

Expected:

`GREEN_DARWIN_PID006B_XAUUSD_CAUSAL_CORE_ACCEPTED`

This gate is the minimum prerequisite for resuming ATHENA engine implementation.

## PID-006C — execution completeness

Add, under separate bounded work packages:

- true partial reductions;
- break-even;
- trailing;
- M1 disambiguation;
- true `NEXT_M1_OPEN`;
- richer order types only when strategy requirements justify them.

Do not expand mechanically just to imitate a broker.

Expected:

`GREEN_DARWIN_PID006C_EXECUTION_PRIMITIVES_ACCEPTED`

## PID-006D — HMT-2 data usability

Implement §29.

Expected:

`GREEN_DARWIN_PID006D_HMT2_DATA_USABILITY_ACCEPTED`

## PID-006E — GC research semantics + first HMT-2 value experiment

Implement §§30–31.

Expected:

`GREEN_DARWIN_PID006E_HMT2_VALUE_EXPERIMENT_ACCEPTED`

## PID-006F — ARENA / operational evidence surface

Expose APOLLO evidence and run drilldown without changing proof semantics.

Expected:

`GREEN_DARWIN_PID006F_ARENA_ACCEPTED`

---

# 36. Acceptance attack matrix

Independent audit must attempt to falsify at least:

1. same inputs -> different result;
2. different parameter value recorded but not applied;
3. unclosed higher-timeframe data leak;
4. future candle high/low visible early;
5. retrospective MAE/MFE influencing decisions;
6. order jumping directly to a fill/position;
7. fill outside permitted price/time range;
8. same-bar SL/TP order changing without evidence/policy identity change;
9. cost omission silently becoming zero;
10. dataset path changed while hash identity is trusted incorrectly;
11. corrupted HMT-2 partition accepted without hash failure;
12. GC treated as XAUUSD;
13. bare GC root accepted where actual contract identity is required;
14. protected holdout passed into ATHENA search;
15. repeated APOLLO holdout use hidden;
16. engine exception converted into performance;
17. wall-clock/process scheduling changing proof hash;
18. APOLLO importing ATHENA simulation code or ATHENA importing APOLLO simulation code.

---

# 37. Explicit prohibitions

APOLLO must not:

- optimise parameters;
- reinterpret prose;
- use an LLM in the proof path;
- call a broker;
- place live trades;
- own HERMES truth;
- silently repair market data;
- invent GC roll/front-month rules;
- infer economics from ticker strings;
- hide costs;
- silently approximate unsupported execution;
- expose future data;
- use ATHENA's replay engine;
- become a distributed platform before evidence requires it.

---

# 38. Documentation / evidence required per gate

Every implementation gate must return:

- exact branch/head SHA;
- exact changed files;
- compare/diff summary;
- test evidence;
- independent adversarial audit;
- exact CI associated with the candidate head;
- migrations/schema impact;
- deployment impact;
- known debt;
- explicit non-goals;
- rollback/compatibility notes where relevant.

Merge is not deployment.

Source acceptance is not deployment.

No new migration is applied to a live runtime without separate deployment authority.

---

# 39. Definition acceptance gate

Before FORGE receives PID-006A implementation authority, Central Architecture must verify the docs-only PID PR against:

- Product Constitution;
- post-HMT-2 reconciliation;
- current source;
- HERMES HMT-2 contracts;
- ATHENA archaeology;
- no hidden GC/XAU equivalence;
- no shared ATHENA/APOLLO simulation engine;
- no live/deployment scope creep.

Expected definition verdict:

`GREEN_DARWIN_PID006_DEFINITION_ACCEPTED`

Only then may ROGUE dispatch PID-006A.
