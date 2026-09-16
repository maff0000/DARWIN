# DARWIN — Project Memory / Architectural Index

**Status:** Active project authority index  
**Last updated:** 2026-09-16

This file records durable DARWIN architectural facts that future delivery sessions must load before changing product architecture. It is not a secret store and must never contain credentials or platform-admin secret locations.

---

## 1. Programme identity

- Product: `DARWIN`
- Canonical repository: `github.com/maff0000/DARWIN`
- Canonical development/runtime root: `/srv/DARWIN` on `dell-debian`
- DARWIN is a Docker-first, continuously operating XAUUSD strategy-discovery, optimisation, sequential-proof and qualification factory.
- DARWIN is a research/incubation side-chain and is not part of the live capital-control path.
- First major milestone: at least **FIVE** independently promising XAUUSD strategies discovered, normalised, optimised and sequentially proven by DARWIN using canonical HERMES historical authority.
- External leaderboard/source claims never count as DARWIN proof.

---

## 2. Delivery authority

- **THE GOAL / DARWIN Architect** owns product architecture, system boundaries, PIDs, sequencing, acceptance gates and cross-system rulings.
- **ROGUE** controls FORGE for DARWIN and dispatches bounded FORGE PL sessions.
- **FORGE** implements only Architect-authorised work packages/PIDs and must not invent ambiguous product or trading semantics.
- **HELM** owns host/infrastructure work outside FORGE.
- Git/GitHub is the durable shared coordination/evidence surface where appropriate.

---

## 3. CD-0 archaeology — CLOSED GREEN

CD-0 legacy archaeology is complete. Do not repeat it without a specific later need.

### ATHENA

Ruling: `REUSE_WITH_ADAPTATION`.

- Legacy ATHENA is principally a parameter-search/optimisation layer.
- It delegates strategy execution/simulation rather than owning an independent market replay engine.
- DARWIN should preserve useful parameter-space generation, search, ranking/aggregation and concurrency mechanics where they remain sound.
- DARWIN ATHENA must ultimately depend on DARWIN-owned simulation/proof contracts rather than legacy Zeus/tradingProteus coupling.

### APOLLO

Ruling: `REUSE_COMPONENTS / REBUILD_BOUNDARY`.

- Legacy Apollo/ApolloV4 contains useful sequential replay, in-memory loading, position, ledger, balance/equity and execution-simulation concepts.
- Legacy Apollo is not DARWIN APOLLO as-is because its historical architecture executes external ZeusV4 decisions rather than proving a self-contained frozen DARWIN candidate.
- ZeusV4 is not part of the canonical DARWIN proof path.
- Continuous ledger is the DARWIN default; legacy day-bounded/FORCE_FLAT semantics are optional explicit policy, not global doctrine.
- Generic break-even, partial-exit and trailing-stop primitives require deliberate DARWIN design rather than strategy-specific hacks.

### HSA

Ruling: strong reuse.

- Reuse as-is where practical: strategy identity/versioning, immutable lineage, ambiguity refusal, deterministic specification doctrine and compatible contracts.
- Reuse with adaptation: timeframe/composition semantics, parameter definitions and test requirements.
- DARWIN `specification` must extend HSA by distinguishing fixed strategy semantics from the authorised parameter/search envelope.
- Standalone HSA is not retired until DARWIN proves full replacement of required capability and central architecture explicitly closes it.

---

## 4. HERMES historical authority

**Status:** `GREEN / COMPLETE — 2026-09-16`

Canonical HERMES repository:

`github.com/maff0000/hermes`

Canonical historical-contract commit:

`3f90e640c9c9c1f4a22ba4ac586a1d478f35a997`

Merged PR:

`maff0000/hermes#166`

HERMES DEV on `dell-debian` is DARWIN's canonical historical market-data authority.

Canonical SQL objects:

- `canonical_candles_m1`
- `canonical_candles_m5`
- `canonical_candles_m15`
- `canonical_candles_h1`
- `canonical_candles_h4`
- `canonical_candles_d1`
- `canonical_candles`

H4 and D1 are governed HERMES-owned durable derivations. DARWIN must never introduce a competing historical market-data authority or independently derive canonical H4/D1 history.

DARWIN historical access principal:

`darwin_ro`

Authority is proven as:

- SELECT-only on the seven canonical objects;
- mutation denied;
- legacy/base candle access denied.

DARWIN historical database credentials are external secrets. DARWIN may reference its own runtime credential mechanism/path through deployment configuration, but this project memory must never record MariaDB root/admin secret locations or platform-admin credentials.

Execution/data boundary:

`HERMES canonical history`
→ `DARWIN read-only adapter`
→ `immutable MarketDataset in RAM`
→ `ATHENA / APOLLO`
→ `DARWIN research/evidence persistence`

SQL must not become the strategy-evaluation inner loop. Load/canonicalise the appropriate historical dataset once per research workload and reuse it across parameter/strategy evaluations wherever practical.

---

## 5. MarketDataset doctrine

`MarketDataset` is the immutable in-memory boundary between HERMES market truth and DARWIN research engines.

At minimum it preserves:

- instrument;
- timeframe;
- bounded start/end interval;
- record count;
- candle open timestamp;
- open;
- high;
- low;
- close;
- volume;
- HERMES provenance/derivation facts required by the canonical contract;
- a reproducible dataset fingerprint/hash;
- load metadata sufficient to reproduce the research input.

ATHENA and APOLLO consume `MarketDataset`; they must not know or depend upon HERMES's physical database layout.

---

## 6. APOLLO wick / intrabar invariant

Candle OHLC, including wick **high** and **low**, are first-class execution facts.

APOLLO must use candle high/low for all price-touch mechanics including:

- stop-loss;
- take-profit;
- break-even;
- trailing stop;
- partial exits;
- any other level-touch execution behaviour.

A touched active price level counts as contact according to the configured execution policy.

OHLC can prove that multiple levels were touched but may not prove their intrabar ordering.

Resolution hierarchy:

1. use lower-timeframe canonical HERMES evidence where sufficient to resolve ordering;
2. otherwise classify the event as intrabar ambiguous;
3. apply the configured deterministic ambiguity policy.

Initial conservative ambiguity policy:

`CONSERVATIVE_SL_FIRST`

ATHENA must never substitute close-only approximations where wick behaviour changes strategy/execution outcome.

---

## 7. Evidence hierarchy

DARWIN must preserve evidence class explicitly. At minimum:

- `SOURCE_CLAIM`
- `ATHENA_RESULT`
- `APOLLO_PROOF`
- later `PLUTUS_RESULT`

External-source metrics are discovery/prioritisation inputs only. They are never promoted or displayed as DARWIN-owned proof.

ATHENA optimises. APOLLO independently proves frozen candidates. APOLLO must not quietly resume optimisation during proof.

---

## 8. Container/runtime doctrine

DARWIN is containerised from the first implementation commit.

Initial expected runtime:

- `DARWIN_core`
- `DARWIN_sql`

`DARWIN_redis` is optional and must not be introduced without a demonstrated requirement.

Do not split conceptual modules into microservices merely because they have names. Strong internal boundaries come first; process/container separation follows measured operational need.

---

## 9. Persistence doctrine

Persistence optimises durability/research access; memory optimises strategy computation.

DARWIN SQL stores control/evidence/research metadata and suitable durable results. It is not canonical market history and must not sit inside the candle-by-candle hot path.

Do not select distributed/high-volume research infrastructure before real ATHENA workloads demonstrate the need.

---

## 10. Open-blocker status

`EXT-HERMES-001` is **CLOSED GREEN**.

There is no remaining HERMES discovery or access blocker for DARWIN Foundation.

Do not modify HERMES as part of DARWIN Foundation work.
