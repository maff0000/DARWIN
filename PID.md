# PID — DARWIN Product Constitution

**Product:** DARWIN  
**Repository:** `github.com/maff0000/DARWIN`  
**Canonical host root:** `/srv/DARWIN` on `dell-debian`  
**Owner:** THE GOAL / DARWIN Architect  
**Delivery controller:** ROGUE  
**Implementation:** FORGE, one bounded PID/work package at a time  
**Infrastructure:** HELM outside FORGE  
**Status:** APPROVED / AUTHORITATIVE  
**Version:** 0.4.0  
**Date:** 2026-09-17  
**Amendment A-001 (2026-09-17):** multi-instrument product-boundary clarification, incorporated into §1.
**Amendment A-002 (2026-09-17):** time/instrument unit semantics — see §7a.
**Amendment A-004R1 (2026-09-17):** federated execution / SOCRATES compatibility — see §22a. Central-architecture-owned; DARWIN records compatibility only, no cross-system authority.

---

## 1. Product outcome

DARWIN is a continuously operating, multi-instrument research appliance that discovers, normalises, optimises, independently proves and qualifies trading strategies for any canonical instrument made available through the governed HERMES historical contract.

DARWIN's product capability is multi-instrument. Its first programme milestone (§2) is intentionally XAUUSD-focused — XAUUSD is the first proving market, not a boundary on what DARWIN itself can do. DARWIN must never redesign its core data model, research identity, persistence or ARENA surfaces to add a new instrument; it must only need a canonical instrument identifier already present in HERMES's governed historical contract (§6, §7).

Its purpose is to turn an uncontrolled universe of external/internal strategy ideas into a governed pipeline of reproducible candidate evidence.

DARWIN does not decide what deserves live capital. It produces high-quality, independently reproduced research candidates that can later enter the governed HELIOS/CER/PLUTUS/NEO/TRON promotion chain.

DARWIN is successful when it can repeatedly take an idea from discovery through deterministic specification, authorised optimisation and independent sequential proof while preserving the complete evidence lineage required to reproduce what happened.

---

## 2. First major programme milestone

The first major milestone is:

> **At least FIVE independently promising XAUUSD strategies must be discovered, normalised, optimised and sequentially proven by DARWIN using our own canonical HERMES historical authority.**

The five strategies must be genuinely distinct strategy candidates/families, not parameter clones presented as separate discoveries.

External performance claims do not count toward the milestone.

A strategy does not count because:

- Trader.dev ranks it highly;
- a source reports high return;
- a trader describes it as profitable;
- a research paper reports an edge;
- a screenshot/backtest claims success;
- ATHENA finds an attractive numerical optimum without independent proof.

A strategy may count as `PROMISING` only after the DARWIN evidence lifecycle reaches the required internal gates, including APOLLO sequential proof.

`PROMISING` means worthy of later governed promotion work. It does not mean safe for real capital.

---

## 3. Foundational axioms

### 3.1 External sources are strategy mines, never evidence

External leaderboards, websites, traders, research papers, books, videos and other sources may tell DARWIN where to look.

They may not establish that a strategy works.

External metrics are stored as `SOURCE_CLAIM` and must never be silently presented as DARWIN-produced evidence.

### 3.2 HERMES owns market truth

HERMES DEV on `dell-debian` is DARWIN's canonical historical market-data authority.

DARWIN is a read-only consumer of the versioned HERMES historical contract.

DARWIN must not:

- create a competing canonical candle history;
- silently repair HERMES data;
- derive its own canonical H4/D1 history;
- write back into HERMES historical authority;
- depend on legacy/non-authoritative HERMES tables.

### 3.3 Memory is the strategy-computation hot path

Historical SQL is an authority and extraction surface, not the candle-by-candle execution loop.

The intended computation path is:

`HERMES canonical SQL`
→ `DARWIN read-only adapter`
→ `canonical validation`
→ `immutable MarketDataset loaded into RAM`
→ `ATHENA/APOLLO computation`
→ `DARWIN result/evidence persistence`

The appropriate dataset must be loaded/canonicalised once per research workload and reused across parameter/strategy evaluations wherever practical.

### 3.4 ATHENA optimises; APOLLO proves

ATHENA owns authorised search.

APOLLO owns independent sequential proof of frozen candidates.

ATHENA must not certify its own winner.

APOLLO must not quietly resume optimisation while proving a candidate.

### 3.5 Reproducibility is mandatory

A serious DARWIN result must be reproducible from at least:

- strategy/candidate identity;
- candidate version;
- deterministic specification;
- authorised parameter values;
- execution-policy values;
- HERMES dataset identity/fingerprint;
- bounded market interval;
- engine/code version;
- configuration version;
- stochastic seed where any stochastic process is explicitly authorised.

An attractive numerical output without reproducible input identity is not durable evidence.

### 3.6 DARWIN is execution-blind to live capital

DARWIN does not place live trades and is not in the live capital-control path.

Failure of DARWIN, ARENA, SCOUT, ATHENA, APOLLO, its database or its scheduler must not interrupt an already-promoted HELIOS strategy or live trading.

---

## 4. Authority and governance

### 4.1 THE GOAL / DARWIN Architect

Owns:

- product mission;
- system boundaries;
- PIDs;
- architecture;
- sequencing;
- acceptance gates;
- cross-system integration decisions;
- promotion boundary definitions;
- interpretation of product ambiguity.

### 4.2 ROGUE

Owns:

- controlling FORGE for DARWIN;
- dispatching one bounded FORGE PL session per authorised package;
- enforcing PID scope;
- receiving implementation evidence;
- escalating architectural ambiguity rather than letting FORGE invent product policy.

### 4.3 FORGE

Owns:

- implementation of the authorised PID/work package;
- code;
- tests;
- migrations;
- container build;
- runtime proof;
- implementation-level engineering decisions inside clear product boundaries.

FORGE must not invent trading semantics, evidence policy or cross-system authority.

### 4.4 HELM

Owns host/infrastructure responsibilities outside FORGE, including deployment plumbing, storage, permissions, external services, networking and secret placement.

### 4.5 Git authority

Durable DARWIN product doctrine must live in Git/GitHub rather than only in chat or agent memory.

`PID.md` is the master constitution.

Module PIDs are subordinate to it and may refine but not contradict it without an explicit architectural amendment.

---

## 5. Application architecture

DARWIN is one organised product/repository with explicit internal modules.

Conceptual module layout:

```text
DARWIN
├── core/
├── scout/
├── specification/
├── athena/
├── apollo/
├── qualification/
├── arena/
├── research_store/
├── hermes/
├── scheduler/
└── integrations/
```

These names define responsibility boundaries. They do not automatically imply independent network services.

Container/process separation must be driven by operational need, not module naming.

### 5.1 `core`

Owns shared product concepts:

- canonical DARWIN identities;
- lifecycle;
- evidence-level/result-kind semantics;
- configuration foundation;
- common validation;
- reproducibility metadata;
- shared API error conventions;
- health/readiness aggregation.

`core` must remain small. It must not become a dumping ground for all business logic.

### 5.2 `scout`

Owns strategy discovery and source provenance.

Initial external source is Trader.dev.

SCOUT must model:

- source identity;
- source strategy identity;
- source URL/reference;
- extraction timestamp;
- source-claimed metrics;
- rule availability;
- strategy-family identity/clustering;
- deduplication;
- candidate intake status.

SCOUT may prioritise based on source claims, but cannot convert those claims into DARWIN proof.

### 5.3 `specification`

Owns deterministic candidate specification.

It must eventually absorb the useful HSA strategy-definition responsibility, subject to proven compatibility/replacement.

It owns:

- candidate identity/version;
- source provenance;
- trading thesis/mechanism;
- required market facts;
- timeframe semantics;
- entry rules;
- exit rules;
- invalidation;
- fixed rules;
- tunable parameters;
- authorised parameter ranges;
- execution-policy search ranges;
- deterministic tests;
- evidence requirements;
- structured ambiguity refusal.

Material ambiguity produces:

`STRATEGY_NOT_SUFFICIENTLY_DEFINED`

DARWIN must not guess.

### 5.4 `athena`

Owns optimisation/search over specification-authorised dimensions.

ATHENA may search:

- strategy parameters;
- stop-loss;
- take-profit;
- break-even;
- partial exits;
- trailing activation/distance/reference;
- session filters;
- confirmation thresholds;
- other dimensions explicitly authorised by the candidate specification.

ATHENA must prefer stable parameter regions/plateaus over blindly treating the single highest historical return as inherently superior.

ATHENA produces `ATHENA_RESULT`.

Legacy ATHENA is classified `REUSE_WITH_ADAPTATION`; useful engineering must be inspected/reused rather than discarded.

### 5.5 `apollo`

Owns independent sequential proof of frozen candidates.

APOLLO must process market history causally and in chronological order.

It owns proof-time execution semantics, including where applicable:

- position lifecycle;
- exposure;
- stop-loss;
- take-profit;
- break-even;
- partial exits;
- trailing stops;
- realised/unrealised P&L;
- balance;
- equity;
- trade ledger;
- intrabar ambiguity accounting.

APOLLO produces `APOLLO_PROOF`.

Legacy Apollo/ApolloV4 is classified `REUSE_COMPONENTS / REBUILD_BOUNDARY`.

ZeusV4 is not part of the canonical DARWIN proof architecture.

### 5.6 `qualification`

Owns explicit evidence gates and candidate status transitions.

It does not alter strategy semantics.

It evaluates evidence against configured gates such as:

- minimum useful trade count;
- profit factor;
- positive expectancy;
- drawdown;
- payoff;
- concentration;
- parameter stability;
- robustness;
- other empirically justified dimensions.

Thresholds must be configurable/visible and must not be hidden constants scattered through code.

### 5.7 `arena`

ARENA is the first-class DARWIN GUI/control surface.

It begins early rather than being attached after the research engines exist.

ARENA must expose where applicable:

- system health;
- pipeline counts;
- discovered candidates;
- source claims;
- provenance;
- active/recent jobs;
- ATHENA runs;
- APOLLO proofs;
- qualification state;
- promising candidates;
- evidence lineage.

Later it should expose:

- return;
- PF;
- drawdown;
- trade count;
- win rate;
- expectancy;
- Sharpe/Sortino where mathematically valid;
- equity curves;
- drawdown curves;
- optimisation surfaces;
- heatmaps;
- trailing/execution-policy comparisons;
- APOLLO ledgers;
- trade drilldown;
- parameter stability.

Every headline metric must disclose evidence level/result kind.

### 5.8 `research_store`

Owns DARWIN persistence abstractions.

It must distinguish durable product truth from regenerable scratch.

It must not become a second market-history authority.

### 5.9 `hermes`

Owns the DARWIN-side read-only HERMES adapter and MarketDataset construction.

It does not own HERMES itself.

### 5.10 `scheduler`

Owns later continuous-factory scheduling and work dispatch.

It is not required to become a generic orchestration platform.

### 5.11 `integrations`

Owns later controlled promotion/feedback boundaries such as CER, HELIOS and PLUTUS.

These are deliberately deferred until DARWIN has first proven its own research pipeline and reached the initial five-strategy milestone threshold for promotion work.

---

## 6. HERMES historical contract

HERMES historical authority status is `GREEN / COMPLETE — 2026-09-16`.

Canonical HERMES repository:

`github.com/maff0000/hermes`

Canonical historical-contract commit:

`3f90e640c9c9c1f4a22ba4ac586a1d478f35a997`

Merged PR:

`maff0000/hermes#166`

Canonical SQL objects available to DARWIN:

- `canonical_candles_m1`
- `canonical_candles_m5`
- `canonical_candles_m15`
- `canonical_candles_h1`
- `canonical_candles_h4`
- `canonical_candles_d1`
- unified `canonical_candles`

DARWIN uses principal `darwin_ro`, proven SELECT-only on the seven canonical objects, with mutations and legacy/base-table access denied.

The adapter should prefer per-timeframe canonical objects when the timeframe is known, while treating the versioned HERMES SQL contract—not its current physical backing—as authority.

Breaking HERMES contract changes require a versioned new contract; DARWIN must not silently adapt to incompatible semantic changes.

---

## 7. MarketDataset

`MarketDataset` is the immutable in-memory market-data boundary consumed by research engines.

At minimum it contains or identifies:

- instrument;
- timeframe;
- requested start inclusive;
- requested end exclusive;
- actual first/last candle;
- record count;
- exact chronological open timestamps;
- exact OHLC values;
- volume;
- canonical HERMES provenance fields required for validation/audit;
- canonical contract version/reference;
- dataset fingerprint;
- load timestamp;
- adapter/code version sufficient to reproduce loading.

It must preserve **high and low** exactly enough for deterministic price-touch testing.

A dataset is invalid if canonical row invariants are violated, including malformed identity/timeframe/order, non-closed/non-OK rows, duplicates or other contract violations.

Gaps must be represented honestly. DARWIN must not fabricate missing candles.

The loader may detect/report expected-grid gaps, but Foundation must not invent a universal policy that all strategies require gap-free data; later experiments/specifications decide whether a particular gap pattern invalidates a test.

---

## 7a. Amendment A-002 — time/instrument unit semantics (2026-09-17)

A numeric OHLC price without instrument semantics is insufficient: `XAU_USD = 4300.00000` must be interpretable as `4300 USD per troy ounce of gold`, not merely `4300`. Foundation therefore owns enough instrument semantics to make market data unambiguous — nothing more:

```text
Market identity + Market units + UTC time semantics  ≠  Broker/execution contract
```

DARWIN owns the left side. Future APOLLO owns the explicit execution economics (contract multiplier, lot size, minimum trade quantity, tick value, commission, margin, etc.) required to turn market movement into monetary trade results. DARWIN must never assume a broker-lot convention (e.g. "1 lot XAUUSD = 100 ounces") unless a future, explicit, separately governed execution contract says so.

A minimal, instrument-generic `InstrumentDefinition` concept (instrument_id, base_asset, quote_asset, base_quantity_unit, price_unit, definition_version/fingerprint) supplies this semantic layer. The ticker (`InstrumentId`) is identity; the `InstrumentDefinition` supplies meaning. It is never inferred dynamically by parsing the ticker string.

`MarketDataset` binds, directly or by immutable reference/fingerprint, the `InstrumentDefinition` under which its prices are interpreted — not merely the bare instrument identifier — and the dataset fingerprint binds that identity too, so a later semantic change cannot silently make old research mean something different. `ResearchRun` inherits the same instrument-definition identity used by its bound `MarketDataset`, so historical evidence can always answer both "what instrument was this?" and "what did one unit of that instrument mean when this test was run?"

UTC remains canonical throughout (§3.3): HERMES `open_time` is UTC by contract, all persisted research timestamps and `MarketDataset` timestamps are UTC, requested dataset boundaries are timezone-aware and normalised to UTC, dataset fingerprints are timezone-stable, and no host-local timezone may affect computation. A future strategy session may describe an explicit IANA timezone/DST rule (e.g. a London or New York session) — that resolves to the canonical UTC timeline before ATHENA/APOLLO evaluation, and belongs to SPECIFICATION, not Foundation.

Storage precision must never be confused with market economics: `PRICE_SCALE` (§7) is a lossless numerical encoding property only — it is not tick size, pip size, contract size, minimum price increment, or position multiplier.

DARWIN remains multi-instrument (§1, Amendment A-001); `InstrumentDefinition` is never an XAU-specific object — contract fixtures prove at least two coexisting definitions (e.g. XAU_USD: XAU/USD/TROY_OUNCE/USD_PER_TROY_OUNCE, and EUR_USD: EUR/USD/EURO/USD_PER_EUR) without pretending EUR_USD is currently available from the real canonical HERMES surface.

**Architect ruling on the A-001 second-real-instrument proof item:** the absence of a second real HERMES instrument is **not a PID-001 merge blocker**. Foundation's multi-instrument structure is proven with controlled contract fixtures; the first programme milestone remains XAUUSD; modifying HERMES purely to satisfy a Foundation test would violate the system boundary. That A-001 acceptance item is reclassified `DEFERRED_EXTERNAL_PROOF` — before DARWIN claims real multi-instrument *operational* capability, HERMES must onboard at least one additional canonical instrument and DARWIN must prove a real load against it, as a later cross-system acceptance gate, not Foundation scope.

---

## 8. Wick and intrabar execution doctrine

Candle open/high/low/close are execution facts.

Wick high/low must be used for all active price-touch rules such as:

- SL;
- TP;
- break-even stop;
- partial exit levels;
- trailing stop contact;
- other stop/target thresholds.

Close-only approximations are forbidden where a wick can change the result.

OHLC can establish contact but may not establish the ordering of multiple contacts inside the same candle.

Resolution hierarchy:

1. use canonical lower-timeframe HERMES evidence where available and semantically sufficient;
2. otherwise record an intrabar ambiguity;
3. apply the experiment's deterministic ambiguity policy.

Initial default policy:

`CONSERVATIVE_SL_FIRST`

The applied ambiguity policy must be part of reproducibility metadata/evidence.

---

## 9. Strategy lifecycle

Initial internal lifecycle:

```text
DISCOVERED
→ SPECIFIED
→ ATHENA_TESTED
→ ATHENA_QUALIFIED
→ APOLLO_PROVEN
→ PROMISING
```

### 9.1 `DISCOVERED`

A source strategy/idea has been captured with provenance.

No claim of correctness or profitability.

### 9.2 `SPECIFIED`

A deterministic candidate version exists with enough precision to implement/test without inventing trading semantics.

### 9.3 `ATHENA_TESTED`

At least one authorised optimisation/search experiment completed.

### 9.4 `ATHENA_QUALIFIED`

ATHENA evidence passes the configured optimisation-side qualification gate, including stability/robustness requirements where applicable.

This is not independent proof.

### 9.5 `APOLLO_PROVEN`

The frozen candidate has completed independent sequential proof under the required APOLLO experiment contract.

The term `PROVEN` means proven to have produced the recorded evidence under the specified historical experiment—not proven profitable forever or safe for live capital.

### 9.6 `PROMISING`

APOLLO evidence and qualification rules justify later governed promotion consideration.

This is the first programme-milestone counting state.

No direct live-trading implication exists.

### 9.7 Transition governance

Lifecycle transitions must be explicit, auditable and evidence-linked.

A later modification of a strategy creates a new candidate/version. It does not mutate a previously evidenced version in place.

---

## 10. Strategy identity/versioning

DARWIN should reuse compatible HSA identity/version doctrine.

At minimum:

- source strategy identity is distinct from DARWIN candidate identity;
- a candidate has an immutable version;
- parameterised experimental runs reference the exact candidate version;
- changing fixed strategy semantics creates a new version;
- optimisation does not silently rewrite the fixed semantic specification;
- promoted/evidenced versions remain immutable.

Parameter search values belong to experiments/results, while the specification declares the authorised search envelope.

---

## 11. Research evidence hierarchy

At minimum DARWIN recognises:

### `SOURCE_CLAIM`

External evidence/claim imported for discovery/prioritisation.

Examples:

- reported return;
- reported PF;
- reported win rate;
- leaderboard rank.

Never represented as a DARWIN result.

### `ATHENA_RESULT`

A result produced by DARWIN optimisation/search.

It must reference:

- candidate version;
- parameter/execution-policy values;
- MarketDataset fingerprint;
- engine version;
- run identity;
- metrics;
- search context.

ATHENA results are not independent proof.

### `APOLLO_PROOF`

Independent sequential proof of an exact frozen candidate/configuration.

It must preserve or reference:

- MarketDataset identity;
- exact candidate/config;
- ambiguity policy;
- ledger;
- trades;
- balance/equity;
- summary metrics;
- engine version;
- deterministic replay evidence where required.

### `PLUTUS_RESULT`

Future forward/demo execution evidence. Not part of the initial DARWIN milestone implementation.

Evidence levels must never be silently blended into one metric.

ARENA must label them explicitly.

---

## 12. Qualification doctrine

Headline return is insufficient.

Qualification should eventually consider:

- adequate trade count;
- profit factor;
- expectancy;
- drawdown;
- payoff;
- concentration;
- robustness across neighbouring parameter values;
- parameter stability/plateaus;
- exposure characteristics;
- regime concentration where evidence exists;
- sensitivity to execution-policy assumptions.

Exact production thresholds are empirical configuration, not permanent guesses embedded in source.

Qualification configuration/version must be attached to every qualification decision.

---

## 13. Execution-policy doctrine

Execution policy is separate from strategy semantics where practical.

Generic execution-policy primitives should eventually represent:

- stop loss;
- take profit;
- break-even;
- partial exits;
- trailing stops;
- optional session-close behaviour.

A strategy specification declares:

- fixed execution rules;
- tunable execution dimensions;
- allowed ranges/options.

ATHENA may search only authorised dimensions.

APOLLO proves the frozen resulting policy.

Continuous ledger is the canonical default.

Session-bounded/FORCE_FLAT behaviour must be explicit when a strategy genuinely requires it.

---

## 14. Persistence classes

DARWIN distinguishes persistence by value and regenerability.

### Class A — canonical DARWIN control metadata

Durable.

Examples:

- source records;
- candidate/version identities;
- lifecycle state;
- run identities;
- configuration versions;
- evidence references;
- qualification decisions.

Initial home: `DARWIN_sql`.

### Class B — durable finalist/proof evidence

Durable and recoverable/backed up.

Examples:

- APOLLO proof ledgers;
- candidate proof summaries;
- reproducibility manifests;
- evidence needed for later promotion.

Initial metadata/indexing home: `DARWIN_sql`; larger artefact representation may evolve based on measured need.

### Class C — optimisation research results

Potentially high-volume and partly regenerable.

Do not assume all ATHENA scratch output deserves the durability/latency characteristics of Class A/B.

Foundation may store modest initial results in SQL, but architecture must leave room for a measured later representation if actual volumes justify it.

### Class D — ephemeral runtime state

Examples:

- transient progress;
- temporary files;
- worker scratch;
- caches.

May be discarded/reconstructed.

Redis must not be introduced merely for Class D without a proven requirement.

### Market history

Not a DARWIN persistence class.

HERMES owns it.

---

## 15. Database and storage doctrine

Foundation uses a relational SQL store for product/control/evidence metadata.

Initial Foundation decision:

**PostgreSQL** in container `DARWIN_sql`.

Rationale:

- small operational surface;
- mature transactions;
- migrations;
- JSON support where needed;
- suitable for control/evidence records and ARENA read models;
- no evidence yet justifies distributed analytics infrastructure.

This decision does not force future high-volume ATHENA scratch results into PostgreSQL forever.

No ClickHouse, Kafka, Elasticsearch or similar infrastructure is authorised without measured workload evidence.

---

## 16. Container and deployment model

DARWIN is Docker-first from its first implementation commit.

Initial persistent runtime:

```text
DARWIN_core
DARWIN_sql
```

`DARWIN_redis` is absent from Foundation.

Redis may be introduced by a later PID only if a concrete requirement is demonstrated.

DARWIN conceptual modules initially reside inside the `DARWIN_core` application/container.

The system must not be developed host-native first and containerised later.

### Deployment workflow

Preferred:

branch
→ tests/CI
→ disposable Docker validation
→ independent audit where appropriate
→ merge
→ build/tag exact tested image
→ deploy exact tested image
→ runtime proof
→ rollback if required

There is one persistent DARWIN environment on `dell-debian`, not a permanent DEV/PROD pair.

Application source must not hard-code `dell-debian`, HERMES IP addresses or `/srv/DARWIN` as semantic dependencies.

Deployment wiring is external.

---

## 17. Failure isolation

DARWIN is not a dependency of live trading.

Required failure property:

`DARWIN unavailable`
→ no effect on HERMES operation
→ no effect on HELIOS
→ no effect on live execution
→ no mutation of authoritative historical data.

The HERMES adapter is read-only by principal and by product contract.

Research database failure may prevent new DARWIN work but must not affect market-data production or live trading.

ARENA failure must not corrupt research engines or evidence.

---

## 18. Security doctrine

### 18.1 Secrets

No credentials in:

- Git;
- Docker images;
- committed Compose files;
- MEMORY.md;
- test fixtures;
- logs;
- error responses.

Runtime secrets are external.

DARWIN may reference its own `darwin_ro` secret mechanism/path through deployment configuration, but platform root/admin access remains HELM authority and must not be recorded in general DARWIN project memory.

### 18.2 Least privilege

- HERMES access uses `darwin_ro`.
- HERMES writes are forbidden.
- DARWIN SQL application credentials should be scoped to required DARWIN schema/database rights.
- Administrative migration credentials, if separate, must not be used by normal runtime where avoidable.

### 18.3 External inputs

SCOUT/source content is untrusted input.

Strategy prose, URLs, identifiers and source metrics must be validated/sanitised before storage/display.

### 18.4 Network exposure

Only interfaces required for operation should be exposed.

Internal database ports should not be treated as public APIs.

ARENA/API exposure policy is defined by its PID/deployment configuration.

### 18.5 Supply chain

Dependencies should be pinned/locked sufficiently for reproducible builds.

CI should include at least secret scanning and dependency/test gates appropriate to the implementation.

---

## 19. Observability doctrine

DARWIN must be observable before the strategy engines are complete.

At minimum operational observability should cover:

- build/version;
- service health/readiness;
- SQL connectivity;
- HERMES adapter readiness;
- job/run counts;
- error counts;
- dataset-load metrics;
- later ATHENA/APOLLO progress;
- lifecycle counts.

Structured logging should include correlation/run IDs where relevant.

Logs must not contain secrets.

ARENA is the product-level observability surface; logs/metrics are engineering-level surfaces.

---

## 20. ARENA GUI doctrine

ARENA is first-class scope.

It starts immediately after Foundation.

It should make the factory understandable while it is being built.

Design goals:

- clear top-level navigation;
- near-real-time operational state where useful;
- provenance always visible;
- evidence level always visible;
- no marketing-style blending of source claims and DARWIN results;
- drill-down from headline result to run/config/dataset/evidence;
- polished enough to become the normal operator/research interface.

A chart or metric without provenance/evidence classification is incomplete.

---

## 21. Recovery doctrine

Hardware must be replaceable.

Durable truth must live in recoverable sources:

- Git/GitHub;
- external deployment configuration;
- external secrets management/location under platform authority;
- PostgreSQL backups for durable DARWIN state;
- durable finalist/proof artefacts where required;
- HERMES references/fingerprints for market datasets.

Do not back up millions of regenerable scratch results with the same priority as proof ledgers and candidate identity.

A fresh host should be able to restore DARWIN without relying on undocumented local state.

---

## 22. Promotion boundaries

Promotion integrations are deliberately later.

### CER

CER is not DARWIN's optimisation database.

Later, serious finalists crossing the promotion threshold may register formal evidence/identity in CER.

Normal ATHENA losers do not need CER packages.

### HELIOS

HELIOS is not an early DARWIN dependency.

DARWIN must never mutate a running HELIOS strategy directly.

Promotion creates/uses governed immutable strategy versions through a later explicit contract.

### PLUTUS / NEO / TRON

Future forward/demo/live-adjacent evidence may feed DARWIN research.

No downstream system may silently rewrite an existing promoted strategy through DARWIN.

New evidence may justify a new candidate version.

---

## 22a. Amendment A-004R1 — federated execution / SOCRATES compatibility (2026-09-17)

**Authority note:** `A-004R1` is approved and locked by THE GOAL central architecture, which remains the cross-system authority. DARWIN is NOT given architectural authority over TRON, NEO, SOCRATES, brokers/execution infrastructure, or federation/fleet management by this section. DARWIN's task is only to remain permanently compatible with the approved future architecture. This section does not author a definitive TRON/NEO/SOCRATES programme blueprint — central architecture issues those authoritative PIDs/blueprints separately when their delivery waves begin. DARWIN records only the interfaces and invariants it must preserve today.

### Canonical programme doctrine (central-architecture-owned, recorded here for DARWIN's compatibility)

```text
DARWIN proves strategies against instruments.
HELIOS evaluates them deterministically.
TRON executes approved configurations.
Brokers are adapters.
NEO learns locally and feeds back, not in.
SOCRATES learns globally.
DARWIN proves what NEO and SOCRATES think they have learned.

Mechanical going forward. Intelligent looking backward.
```

### Strategy identity

`StrategyVersion` is, and must remain, independent of: broker; broker account; trader; TRON instance; deployment host; execution venue; NEO instance. The same immutable `StrategyVersion` may be tested, and eventually deployed, in multiple independent execution environments. DARWIN's current identity model (§10, §20) already satisfies this by construction — no broker/account/TRON/venue field exists anywhere on `StrategyCandidate`, `StrategyVersion`, or `ResearchRun`.

### Instrument-specific proof

Unchanged from Amendment A-001, restated for emphasis: `StrategyVersion != proof on every instrument`. A strategy must be independently tested against each canonical `InstrumentId`. A strategy proven on `XAU_USD` is not thereby proven on `EUR_USD`, `BTC_USD`, `USD_JPY`, or any other instrument. A-001 remains authoritative.

### Policy identity separation

DARWIN must not design so that future deployment configuration collapses into `StrategyVersion` identity. Independent future identities are reserved (not implemented in PID-001): `StrategyVersion`; `ParameterSetVersion`; `ExecutionPolicyVersion`; `DIKEPolicyVersion`; `SizingPolicyVersion`; `NewsContextPolicyVersion` where applicable; `BrokerContract`/`AdapterVersion`. Each is a distinct future axis of identity, not a field folded into another.

### Future execution-instance compatibility

Compatibility with a future operational identity such as `TronInstanceId` is reserved. TRON and fleet management are NOT implemented now. `TronInstanceId` must never become part of `StrategyVersion` identity — an execution instance is where/how a proven strategy runs, never what makes the strategy itself immutable.

### Evidence compatibility

Today's identifiers must not prevent a future evidence envelope from associating: strategy/version; instrument; parameter set; execution policy; DIKE policy; sizing policy; context policy; execution-instance identity; broker/execution profile; normalized outcome; provenance. The complete future evidence envelope is explicitly NOT implemented during PID-001 — today's `ResearchRun`/`ATHENA_RESULT`/`APOLLO_PROOF` model (§11, §9) must simply not close off room for these associations later.

### Broker abstraction

Canonical principle: **brokers are adapters beneath TRON.** DARWIN must not encode broker assumptions in strategy semantics. Any wording implying an architectural concept such as an "OANDA Trading Cell," "Vantage Trading Cell," or "crypto Trading Cell" is superseded — those are execution resources/endpoints, not architectural identities. (Verified 2026-09-17: no such wording exists anywhere in DARWIN's current product-authority documents or source; this paragraph is a standing prohibition against introducing it, not a correction of an existing defect.)

### NEO / SOCRATES compatibility doctrine (recorded, not implemented)

NEO is future local analytical intelligence; NEO feeds back, not in; NEO produces hypotheses, not live discretionary decisions. SOCRATES is future population-level intelligence across multiple execution environments; SOCRATES also produces hypotheses only. Hypotheses from either return to DARWIN; DARWIN mechanically tests them before governed promotion — DARWIN proves what NEO and SOCRATES think they have learned. Neither NEO nor SOCRATES is implemented by this amendment.

### Milestone unaffected

This amendment does not change DARWIN's current programme milestone (§2): at least five independently promising XAUUSD strategies discovered, normalised, optimised and sequentially proven using canonical HERMES history. Multi-instrument capability remains foundational (Amendment A-001); XAUUSD remains the first proving market. This amendment expands no current implementation scope — it records compatibility invariants only.

---

## 23. Explicit non-goals

DARWIN initial programme does not build:

- broker/live execution;
- a replacement HERMES historical database;
- a generic market-data platform;
- a generic orchestration platform;
- a second CER evidence database;
- HELIOS strategy runtime;
- NEO/TRON live decision/control;
- speculative distributed analytics infrastructure;
- independent canonical H4/D1 candle derivation;
- strategy semantics invented to fill ambiguous source gaps;
- microservices for every conceptual module.

---

## 24. Delivery sequence

Current expected sequence:

1. `PID.md`
2. `PID-001-FOUNDATION.md`
3. Foundation implementation and proof
4. `PID-002-ARENA.md`
5. ARENA operational shell
6. `PID-003-SCOUT.md`
7. Trader.dev intake
8. `PID-004-SPECIFICATION.md`
9. use completed ATHENA archaeology/rulings to finalise `PID-005-ATHENA.md`
10. use completed APOLLO archaeology/rulings to finalise `PID-006-APOLLO.md`
11. `PID-007-QUALIFICATION.md`
12. `PID-008-CONTINUOUS-FACTORY.md`
13. scale until five genuinely promising XAUUSD candidates exist
14. only then prioritise later CER/HELIOS/PLUTUS promotion/feedback PIDs.

CD-0 archaeology is already CLOSED GREEN and must not be repeated merely because PID-005/006 have not yet been written.

---

## 25. Module PID standard

Every module PID must specify:

- purpose;
- authority/boundaries;
- inputs;
- outputs;
- contracts;
- persistence;
- failure semantics;
- security;
- observability;
- GUI representation;
- tests;
- runtime proof;
- explicit non-goals;
- acceptance gate.

Do not implement multiple major modules merely because their PIDs exist.

---

## 26. First milestone acceptance

The programme reaches its first major stopping point only when:

- DARWIN runs continuously;
- ARENA shows live factory state;
- SCOUT discovery operates;
- strategy specification is deterministic;
- HERMES historical authority is consumed through the governed read-only boundary;
- ATHENA performs real optimisation from in-memory MarketDataset inputs;
- APOLLO independently proves frozen candidates sequentially;
- evidence provenance is clear;
- qualification is operational;
- at least five distinct XAUUSD strategies are `PROMISING` with credible DARWIN/APOLLO evidence.

This milestone does not authorise real capital.

---

## 27. Architectural amendment rule

A later implementation finding may require this constitution to change.

If so:

- state the evidence;
- state the affected invariant/boundary;
- obtain DARWIN Architect approval;
- version/update `PID.md`;
- then update subordinate PIDs.

Do not silently change product doctrine inside implementation commits.
