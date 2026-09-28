# PID-005 — ATHENA DETERMINISTIC EXPLORATORY RESEARCH

**Parent authority:** `PID.md` + Amendment A-005  
**Product:** DARWIN  
**Module:** ATHENA  
**Owner:** THE GOAL / DARWIN Architect  
**Delivery controller:** ROGUE  
**Implementation:** FORGE under bounded work packages  
**Date:** 2026-09-28  
**Status:** ARCHITECT DEFINITION — IMPLEMENTATION DEFERRED UNTIL PID-006 CORE GATE  
**Canonical definition baseline:** `a886b1b241d8eb8063db408e5dd146618af630ba`

---

# 1. Purpose

ATHENA is DARWIN's deterministic exploratory research engine.

Its job is to search **explicitly authorised** strategy parameter space against governed historical data and preserve the complete resulting research surface.

ATHENA answers:

> Which bounded configurations and regions deserve later independent APOLLO proof?

ATHENA does not answer:

> Has this strategy been independently proven?

That belongs to APOLLO.

---

# 2. Programme position

Canonical research flow:

```text
Discovery
  ↓
Strategy Workshop / MENDEL
  ↓
immutable StrategyVersion
  ↓
ATHENA
  ↓
ATHENA_RESULT
  ↓
candidate/configuration selection
  ↓
APOLLO
  ↓
APOLLO_PROOF
  ↓
Qualification
```

Because of Amendment A-005, APOLLO core is implemented before the ATHENA engine even though ATHENA retains PID number 005.

PID numbering is historical identity, not current implementation order.

---

# 3. Permanent doctrine

## 3.1 Intelligence backward, mechanics forward

MENDEL may reason during authoring.

From an immutable `StrategyVersion` onward, deterministic engines consume explicit governed semantics.

ATHENA contains no LLM strategy interpretation.

## 3.2 Optimisation is not proof

`ATHENA_RESULT` is not DARWIN proof.

`APOLLO_PROOF` is DARWIN proof.

ATHENA never promotes its own highest-scoring result directly to proof.

## 3.3 Shared semantics, independent engines

ATHENA consumes:

`StrategyVersion -> CanonicalStrategyCompiler -> ExecutableStrategyPlan`

The compiler/plan is shared semantic truth.

ATHENA must not use APOLLO's replay engine.

APOLLO must not use ATHENA's replay engine.

## 3.4 Full research surface matters

ATHENA is not:

`max(score) wins`.

Every valid cell remains durable evidence so later robustness/neighbourhood analysis can distinguish broad stable regions from isolated peaks.

---

# 4. Inputs

A real ATHENA experiment binds at minimum:

- immutable `StrategyVersion`;
- compiler version and `ExecutableStrategyPlan` identity;
- exact `InstrumentDefinition`;
- exact dataset binding(s);
- exact `ResearchPartitionPolicyVersion` and data role;
- exact parameter-search plan;
- exact pinned parameter assignments;
- exact `ExecutionPolicyVersion`;
- DIKE state/policy identity;
- derived-fact algorithm/version identities;
- ATHENA engine build/version;
- methodology/objective version;
- adequacy-rule version.

No input may be silently defaulted after the experiment identity is created.

---

# 5. ParameterSetVersion

ATHENA requires a concrete immutable `ParameterSetVersion` contract.

Each evaluated cell binds one exact set of parameter values.

A `ParameterSetVersion` must have:

- strategy version identity;
- canonical ordered parameter assignments;
- value types/units;
- deterministic fingerprint;
- creation provenance;
- explicit relationship to the ATHENA search plan.

Changing any value produces a different identity.

---

# 6. Parameter-transmission invariant

Permanent acceptance invariant:

```text
AUTHORISED
=
GENERATED
=
APPLIED
=
RECORDED
```

for every relevant parameter dimension.

Mismatch is a hard failure.

It is never a warning and never converted into a poor score.

PID-005 acceptance must recreate the legacy failure class in which eight parameters were declared/recorded but only four affected evaluation, and prove modern DARWIN rejects it structurally.

---

# 7. Search method V1

V1 search is:

`DETERMINISTIC_GRID_V1`

No random optimiser.

No local random refinement.

No falsely labelled "Bayesian" optimiser.

More sophisticated methods require separate evidence that deterministic exhaustive search is no longer sufficient.

---

# 8. Search-domain enumeration

Supported V1 grid domains must be finitely and exactly enumerable.

Rules:

- integer range requires explicit positive step;
- decimal/numeric range requires explicit positive step represented without float drift;
- duration range requires explicit positive step;
- discrete enumeration enumerates exact members;
- boolean enumeration enumerates exact members;
- a unit-bearing range without an explicit step is not silently discretised.

Failure:

`SEARCH_DOMAIN_NOT_GRID_ENUMERABLE`

ATHENA never invents a step size.

Decimal stepping uses exact decimal arithmetic.

---

# 9. Search plan

Before execution ATHENA materialises an immutable search plan containing:

- searched dimensions;
- pinned tunables;
- canonical ordered values per dimension;
- exact cell cardinality;
- maximum permitted cardinality;
- deterministic grid fingerprint;
- methodology version.

Every tunable parameter relevant to the run is explicitly either:

`SEARCHED`

or:

`PINNED_FOR_THIS_EXPERIMENT`.

Nothing is implicitly omitted.

If grid cardinality exceeds the configured limit:

`SEARCH_SPACE_TOO_LARGE`

The experiment fails preflight before historical computation begins.

---

# 10. Dataset bindings

ATHENA must support an exact set of historical inputs, not only one timeframe.

Conceptually:

```text
AthenaExperiment
  ├── H4 -> MarketDataset A
  ├── H1 -> MarketDataset B
  └── M15 -> MarketDataset C
```

and, after HMT-2 integration where relevant, typed event/context dataset bindings.

Each binding carries its scientific identity/fingerprint.

Physical paths are not scientific identity.

ATHENA must not query HERMES/SQL inside the per-candle/per-cell inner loop.

---

# 11. Historical visibility and no-lookahead

At evaluation time `T`, only information actually available by `T` may be visible.

For candle facts:

- an unclosed higher-timeframe candle is not visible;
- future high/low/close is not visible;
- derived facts obey explicit warm-up and close/availability semantics.

For event/context facts:

- causal observation/availability timestamp is explicit;
- revisions are handled by their versioned causal semantics;
- future events never leak backwards.

Temporal alignment methodology is versioned and participates in experiment identity.

---

# 12. DerivedFactAlgorithmRegistry

ATHENA consumes only explicitly implemented, versioned derived algorithms.

Exact resolution key:

```text
algorithm_id
+
algorithm_version
```

No `latest`.

No fuzzy alias.

No "whatever the indicator library currently does."

If the StrategyVersion requires an unavailable algorithm/version:

`ENGINE_CAPABILITY_BLOCKED`

The StrategyVersion remains valid; the engine is not capable of evaluating it yet.

---

# 13. ExecutionPolicyVersion

ATHENA binds one exact immutable `ExecutionPolicyVersion` for an experiment.

ATHENA V1 does not optimise execution policy.

Execution policy identity includes the execution assumptions actually required by the evaluator, such as:

- signal availability/fill timing;
- entry/exit price rule;
- spread/cost methodology;
- slippage methodology;
- same-bar/event ambiguity treatment;
- quantity/economic normalisation where relevant.

Execution policy is a shared DARWIN research contract, not ATHENA-private configuration.

---

# 14. DIKE

First ATHENA implementation uses:

`DIKE_DISABLED`

only.

This is a scientific baseline.

It does not mean a strategy is suitable for live unguarded trading.

Guarded DIKE research requires a separately implemented and versioned DIKE evaluator/policy and is outside the first ATHENA slice.

---

# 15. Research partition / holdout governance

ATHENA obeys the shared `ResearchPartitionPolicyVersion`.

ATHENA may evaluate authorised:

- `DEVELOPMENT`;
- `VALIDATION`.

ATHENA must not consume:

`PROTECTED_HOLDOUT`

reserved for independent APOLLO proof.

The engine must fail closed if a search plan attempts to include a protected holdout.

Selection decisions and dataset exposure are evidence events.

---

# 16. Experiment and cell model

One full grid is an `AthenaExperiment`.

Each exact parameter configuration is a distinct trial/ResearchRun-equivalent evidence unit.

Experiment states:

- `PLANNED`;
- `RUNNING`;
- `SUCCEEDED`;
- `FAILED`;
- `CANCELLED`.

Cell states:

- `PENDING`;
- `RUNNING`;
- `SUCCEEDED`;
- `DISQUALIFIED`;
- `FAILED`.

`FAILED` = system/evaluation failure.

`DISQUALIFIED` = scientifically valid result failing adequacy/eligibility.

Exceptions are never encoded as magic poor scores.

---

# 17. Adequacy

Adequacy is a hard eligibility gate evaluated before ranking.

Use an immutable/versioned `AdequacyRuleVersion`.

V1 may include:

- minimum completed trades;
- minimum temporal coverage.

A cell failing adequacy is `DISQUALIFIED`.

It is not merely given a weaker score.

Old evidence always records which adequacy rule judged it.

---

# 18. V1 cell objective

Initial transparent objective:

`ATHENA_CELL_OBJECTIVE_EXPECTANCY_V1`

Primary value:

mean net trade return under the frozen execution/economic policy.

Rationale:

- transparent;
- deterministic;
- avoids legacy zero-loss Profit Factor sentinels;
- avoids divide-by-near-zero drawdown explosions;
- directly interpretable.

This objective helps order cells.

It does not create `ATHENA_QUALIFIED`.

---

# 19. Minimum cell evidence

V1 records at least:

- completed trades;
- wins;
- losses;
- net return;
- mean trade return/expectancy;
- median trade return;
- maximum drawdown;
- exposure;
- temporal coverage;
- Profit Factor with honest undefined/infinite state representation;
- decision hash;
- trade-sequence hash;
- economic-result hash;
- parameter-set fingerprint;
- dataset fingerprints;
- execution-policy fingerprint;
- engine/methodology versions.

No magic 99/999 sentinels.

---

# 20. Complete surface preservation

Every terminal cell is retained.

Negative/disqualified results are evidence.

Non-winning cells are evidence.

ATHENA must preserve enough topology to support future:

- neighbourhood stability;
- plateau/region analysis;
- parameter sensitivity;
- robustness comparisons.

V1 does not need a sophisticated plateau detector.

---

# 21. Determinism

Provide:

- serial reference evaluation;
- single-host multiprocessing evaluation.

For identical experiment identity:

```text
serial evidence
==
parallel evidence
```

after deterministic result ordering, irrespective of worker completion order.

No distributed architecture in V1.

---

# 22. Checkpoint/resume

Persist per-cell completion durably.

On resume:

- validate exact experiment identity;
- identify terminal cells;
- do not rerun terminal cells;
- queue only incomplete/retriable cells;
- never duplicate evidence.

Idempotency is structural/persistence-enforced.

---

# 23. Performance model

Doctrine:

> Persistence optimises durability and research access. Memory optimises computation.

Historical datasets are loaded once per suitable workload and reused across cells.

Derived caches are allowed only under deterministic identity and never become evidence authority.

No SQL/HERMES call inside the candle/event hot loop.

---

# 24. Lifecycle

PID-005 first engine implements:

```text
SPECIFIED
→ ATHENA_TESTED
```

Meaning:

> a complete valid ATHENA experiment was performed.

It does not mean:

> the strategy is good.

Even if every cell is disqualified, a complete valid experiment can still be `ATHENA_TESTED`.

`ATHENA_QUALIFIED` is not implemented until a robust-region/selection methodology is separately defined and accepted.

---

# 25. ARENA

ATHENA becomes a first-class ARENA workflow.

Expose:

- StrategyVersion and semantic fingerprint;
- instrument;
- research partition/data role;
- required datasets;
- execution policy;
- DIKE state;
- search dimensions;
- exact grid size;
- progress;
- eligible/disqualified/failed counts;
- complete cell table;
- methodology identities;
- fingerprints.

For two-dimensional searches, a heatmap is appropriate.

For higher dimensions, use slices/selectors and tables.

Do not design around a giant "winner" card.

---

# 26. First ATHENA vertical slice

Only after the required APOLLO/shared-contract gate is accepted:

```text
one real immutable StrategyVersion
+
XAU_USD
+
governed candle MarketDataset binding
+
2–3 searched parameters
+
one frozen ExecutionPolicyVersion
+
one ResearchPartitionPolicyVersion
+
DIKE_DISABLED
+
DETERMINISTIC_GRID_V1
+
one AdequacyRuleVersion
+
ATHENA_CELL_OBJECTIVE_EXPECTANCY_V1
+
complete durable cell surface
+
parameter-transmission equality proof
+
serial/parallel parity
        ↓
ATHENA_RESULT
        ↓
ATHENA_TESTED
```

---

# 27. Out of scope for first implementation

- random optimisation;
- "Bayesian" optimisation;
- DIKE_GUARDED;
- sizing-policy search;
- execution-policy search;
- HMT-LIVE;
- distributed execution;
- APOLLO proof;
- ATHENA_QUALIFIED;
- live trading;
- broker integration;
- self-promotion to HELIOS.

---

# 28. Internal delivery gates

## PID-005A — ATHENA contracts/search plan

Consumes already accepted shared contracts from the APOLLO-first programme and implements:

- AthenaExperiment;
- search plan;
- deterministic grid enumeration;
- parameter transmission integrity;
- adequacy/objective identities;
- cell evidence identity.

No historical grid engine yet.

Expected verdict:

`GREEN_DARWIN_PID005A_ATHENA_CONTRACTS_ACCEPTED`

## PID-005B — deterministic engine

Implements:

- serial evaluator;
- multiprocessing evaluator;
- complete cell persistence;
- checkpoint/resume;
- metrics;
- adequacy;
- parity.

Expected verdict:

`GREEN_DARWIN_PID005B_ATHENA_ENGINE_ACCEPTED`

## PID-005C — real XAUUSD vertical slice + ARENA

Proves the first real governed experiment and lifecycle transition.

Expected verdict:

`GREEN_DARWIN_PID005C_REAL_VERTICAL_SLICE_ACCEPTED`

---

# 29. Acceptance invariants

PID-005 cannot close unless independently reproduced evidence proves:

1. all searched/pinned parameters are applied exactly;
2. the legacy 8-declared/4-applied defect is rejected;
3. grid order/cardinality is deterministic;
4. serial/parallel evidence matches exactly;
5. incomplete work resumes without duplicate evidence;
6. protected holdout cannot enter ATHENA search;
7. no future data is visible;
8. every terminal cell is retained;
9. engine failures are not converted into scores;
10. `ATHENA_RESULT` is still not DARWIN proof.

---

# 30. Implementation authority

This document defines ATHENA.

It does not currently authorise ATHENA implementation.

Implementation remains deferred until Central Architecture accepts the required PID-006 shared-contract/APOLLO-core gate under Amendment A-005.
