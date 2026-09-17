# DARWIN — Project Memory / Architectural Index

**Status:** Active project authority index  
**Last updated:** 2026-09-17 (Amendment A-003 DIKE doctrine incorporated; additive to A-001/A-002/A-004R1)

This file records durable DARWIN architectural facts that future delivery sessions must load before changing product architecture. It is not a secret store and must never contain credentials or platform-admin secret locations.

---

## 1. Programme identity

- Product: `DARWIN`
- Canonical repository: `github.com/maff0000/DARWIN`
- Canonical development/runtime root: `/srv/DARWIN` on `dell-debian`
- DARWIN is a Docker-first, continuously operating, **multi-instrument** strategy-discovery, optimisation, sequential-proof and qualification factory. Product capability is instrument-generic; XAUUSD is the first programme milestone and initial proving market, not a product boundary (Amendment A-001, 2026-09-17).
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

## 2a. Amendment A-004R1 — federated execution / SOCRATES compatibility (2026-09-17)

Approved and locked by THE GOAL central architecture, which remains the sole cross-system authority. DARWIN is explicitly NOT given architectural authority over TRON, NEO, SOCRATES, brokers/execution infrastructure, or federation/fleet management — DARWIN records compatibility invariants only; no TRON/NEO/SOCRATES blueprint is authored here.

Canonical doctrine (central-architecture-owned):

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

Compatibility invariants DARWIN must preserve, none implemented now:

- `StrategyVersion` stays independent of broker, broker account, trader, TRON instance, deployment host, execution venue, and NEO instance — already true by construction (no such field exists on any current model).
- Instrument-specific proof is unchanged from A-001: a `StrategyVersion` proven on one `InstrumentId` is not thereby proven on any other.
- Policy identity stays separated: `StrategyVersion`, `ParameterSetVersion`, `ExecutionPolicyVersion`, `DIKEPolicyVersion`, `SizingPolicyVersion`, `NewsContextPolicyVersion`, `BrokerContract`/`AdapterVersion` are distinct future identity axes, never collapsed into one.
- A future `TronInstanceId` operational identity is reserved but never part of `StrategyVersion` identity.
- Today's identifiers must not block a future evidence envelope associating strategy/version, instrument, parameter set, execution policy, DIKE policy, sizing policy, context policy, execution-instance identity, broker/execution profile, normalized outcome, and provenance — the full envelope is not implemented now.
- Brokers are adapters beneath TRON — DARWIN never encodes broker assumptions in strategy semantics. No "Trading Cell"-style architectural wording (OANDA/Vantage/crypto) exists anywhere in DARWIN's docs or source as of this amendment; this is a standing prohibition, not a correction.
- NEO/SOCRATES are future hypothesis-producing systems only, feeding back into DARWIN for mechanical proof before governed promotion — neither is implemented.

DARWIN's current programme milestone is unchanged (§1): five independently promising XAUUSD strategies. Multi-instrument capability remains foundational (A-001); XAUUSD remains the first proving market. No current implementation scope expanded by this amendment.

---

## 2b. Amendment A-003 — DIKE deterministic capital-protection doctrine (previously issued; incorporated 2026-09-17)

Durable architectural invariant, recorded here as the project-memory authority (full doctrine: `PID.md` §5.12/§22b):

- `DIKE_DISABLED` is the scientific baseline — unguarded research is the default condition, not an error state.
- TRON's hard limits are sovereign; the stricter constraint always wins over any DARWIN research configuration.
- No direct feedback mutation — NEO/SOCRATES/any future process may only propose a new, immutable, versioned DIKE policy through the normal research/proof discipline; nothing mutates an enforced policy directly.
- Historical evidence is never rewritten — a later DIKE policy change never alters what a past `ResearchRun`'s DIKE identity meant when it ran.

Responsibility split: DARWIN researches/proves DIKE policy behaviour; TRON enforces live; NEO may learn/propose but never mutate/bypass; HELIOS remains DIKE/capital unaware; ATHENA gets authorised DIKE search only; APOLLO proves one frozen causal DIKE configuration; qualification/ARENA must distinguish DIKE-guarded from DIKE-disabled evidence explicitly, never blended.

DIKE policy identity is immutable/versioned (`dike_policy_id`/`dike_policy_version`/`dike_policy_fingerprint`), same discipline as `StrategyVersion` and `InstrumentDefinition`.

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

## 5a. Instrument definition / unit semantics (Amendment A-002, 2026-09-17)

A numeric OHLC price has no meaning without instrument semantics. DARWIN's `InstrumentDefinition` (instrument-generic, never inferred by parsing the ticker) supplies: base/quote asset, base quantity unit, price unit, and a definition version/fingerprint. `MarketDataset` binds this identity (not just the bare `instrument` string), and the dataset fingerprint includes it, so a later semantic redefinition cannot silently change what old research meant. `ResearchRun` inherits the same instrument-definition identity as its bound dataset.

**XAUUSD unit invariant:** for `XAU_USD`, canonical market price is USD per troy ounce of gold. This is market-data interpretation only — it does NOT define broker lot size or contract multiplier. Later APOLLO monetary P&L must combine price movement × explicit traded quantity in governed quantity units × explicit execution/contract semantics where required. Never derive monetary P&L from price change alone without unit-aware quantity semantics.

`PRICE_SCALE` (the fixed-point encoding factor, §5) is a lossless numerical encoding property only — never tick size, pip size, contract size, minimum price increment, or position multiplier. Those belong to a future, separately governed APOLLO execution contract (venue/execution instrument, quantity unit, contract multiplier, lot size, minimum trade quantity, tick value, spread, commission, margin, etc.), explicitly reserved and not implemented in PID-001.

Distinction to preserve everywhere:

```text
Market identity + Market units + UTC time semantics  ≠  Broker/execution contract
```

DARWIN Foundation owns the left side only.

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

**ARENA visual durability (PID-002):** these evidence classes must carry stable, unmistakably different visual/semantic treatment in ARENA across every later expansion -- no single generic "performance" badge may make a SOURCE_CLAIM look equivalent to APOLLO_PROOF. A user must be able to answer "where did this number come from?" from the UI alone.

---

## 7a. ARENA doctrine (PID-002, 2026-09-17)

ARENA is DARWIN's first-class, permanent visual operating surface -- not a temporary admin page. Durable architectural commitments, not implementation detail (kept in `docs/pids/PID-002-ARENA.md`):

- Served as a static production bundle packaged into the `DARWIN_core` image and served by the existing FastAPI product -- no Node runtime/container in production, no separate ARENA container without a separately Architect-approved requirement. Runtime remains exactly `DARWIN_core` + `DARWIN_sql`, no Redis.
- Left-hand rail is the primary navigation; the top bar is global/utility only (health, build, environment, Account affordance) -- this split must survive every later module landing (SCOUT/ATHENA/APOLLO/QUALIFICATION) without a shell redesign.
- ARENA reads Foundation's existing `/api/v1/...` APIs and real persistence only; the browser never talks to PostgreSQL or HERMES directly. Narrow read-only API additions are permitted when a real requirement can't be served by existing endpoints -- never generic mutation APIs.
- DIKE state/policy identity is displayed as immutable identity only -- ARENA must never imply Foundation evaluates DIKE (PID-001 §1d).
- No fabricated/demo data of any kind may appear in the production build. Empty states are designed deliberately, never filled with sample data.

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

---

## 11. SCOUT vs Strategy Workshop vs Specification (2026-09-17)

`SCOUT` (PID-003) captures external `SOURCE_CLAIM` discovery provenance only — adapter-
sourced (Trader.dev) and manual (`USER_DISCOVERED`/`MY_IDEA`) — and never decides
ambiguous trading semantics or produces a `StrategyVersion`. A future `Strategy Workshop`
(part of PID-004, bundled with `Specification`) is where ambiguity gets resolved into a
deterministic specification; SCOUT and Workshop/Specification are never the same module.

Revised canonical PID sequence: PID-002 ARENA → PID-003 SCOUT → PID-004 Strategy
Workshop + Specification → PID-005 ATHENA → PID-006 APOLLO → PID-007 Qualification →
PID-008 Continuous Factory. This is a sequencing/scope clarification only — the
programme's first milestone (§1: five independently promising XAUUSD strategies) is
unchanged.
