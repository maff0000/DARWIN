# DARWIN — Project Memory / Architectural Index

**Status:** Active project authority index  
**Last updated:** 2026-09-29 (Amendment A-007 canonical strategy definition incorporated; additive to A-001/A-002/A-003/A-004R1/A-005/A-006)

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

---

## 12. Post-HMT-2 research restart (Amendment A-005, 2026-09-28)

- Verified DARWIN factual-restart `main`: `a886b1b241d8eb8063db408e5dd146618af630ba` (PR #16, ATHENA + DIKE archaeology, merged).
- Verified HERMES HMT-2 `main`: `4cece04bbc538828576b82e93fb20818b8f5b429`. HMT-2 selection manifest holds 448 governed GC sessions; DARWIN consumes HERMES read-only and must verify scientific hashes/lineage, never trust a filesystem path as authority on its own.
- HERMES now provides two distinct governed historical authorities: the existing canonical candle authority (§4-§6, unchanged) and the additional GC HMT-2 event/microstructure corpus. Neither replaces the other.
- Post-HMT-2 reconciliation verdict: `GREEN_DARWIN_POST_HMT2_RECONCILIATION_ARCHITECTURALLY_ACCEPTED`.
- Amendment A-005 preserves PID numbering (`PID-005` ATHENA, `PID-006` APOLLO) but changes implementation order: APOLLO core first, ATHENA engine afterward.
- Permanent architecture: `StrategyVersion -> CanonicalStrategyCompiler -> ExecutableStrategyPlan`. ATHENA and APOLLO share semantic truth only; they never share a replay/simulation engine.
- First APOLLO implementation slice: a bounded real `XAU_USD` candle causal proof engine. HMT-2 follows in sequence: event-dataset usability -> governed GC research semantics -> GC actual-contract incremental-value experiment.
- COMEX GC and OTC `XAU_USD` are never interchangeable. First GC research uses actual contract identities; continuous/roll doctrine is deferred until genuinely required.
- `ExecutionPolicyVersion`, `ParameterSetVersion` and `ResearchPartitionPolicyVersion` are shared immutable DARWIN research identities — never private ATHENA/APOLLO state.
- Protected holdout is first-class research governance: ATHENA cannot search it; APOLLO access is recorded so repeated holdout use stays visible.
- DARWIN `main` branch protection was verified disabled at this checkpoint (`gh api .../branches/main/protection` → 404 "Branch not protected"). Separate governance debt; do not bypass a denied GitHub admin action through an alternate mechanism.

Authoritative detail:
- `docs/architecture/DARWIN-POST-HMT2-RECONCILIATION.md`
- `docs/architecture/AMENDMENT-A005-POST-HMT2-RESEARCH-SEQUENCING.md`
- `docs/pids/PID-005-ATHENA.md`
- `docs/pids/PID-006-APOLLO.md`

---

## 13. PID-006A closure — Shared Research/Proof Contracts (2026-09-28)

- Verdict: `GREEN_DARWIN_PID006A_PROOF_CONTRACTS_ACCEPTED`. Merged `main` @ `87e1fe699bbee986db85ede96a239f43ae094570` (PR #18, merge-commit, first parent `56d37a490efef33d853d43c66c72013add4f9ff5`, second parent `50cb839e9c417dc5982622ad456ec97249220e59`).
- New package `darwin/research_contracts/` — `CanonicalStrategyCompiler`→`ExecutableStrategyPlan`, `ParameterSetVersion`, `ExecutionPolicyVersion`, `ResearchPartitionPolicyVersion`/`ResearchInputBinding`, `ResearchConfiguration`. Immutable, deterministically fingerprinted, shared by future ATHENA and APOLLO — `darwin/specification` has zero dependency on it (one-directional, `ast`-proven). No historical replay/order/fill/position/P&L code exists anywhere in this package.
- Persistence: migration `0012_research_contracts.sql`, 5 tables, all `UNIQUE(fingerprint)`, immutable (trigger-enforced, `SELECT, INSERT`-only grants). **Source accepted only — not applied to any deployed runtime.**
- Went through two Architect-authorised adversarial-audit correction rounds before acceptance: a non-recursive composition-capability check (could let a hand-constructed, non-`finalise()` composition smuggle unsupported temporal semantics past capability-blocking) and two configuration-integrity gaps (a `ResearchConfiguration` could bind a partition policy to an undeclared input; a nested `ResearchInputBinding`'s fingerprint was trusted rather than independently re-verified on reconstruction) — all closed and re-audited clean.
- Known non-blocking test debt (recorded, not reopened for): the persistence test suite doesn't include a raw-SQL nested-JSON-tamper regression test for the fix above, though the underlying code was proven correct against exactly that attack during the final audit.
- `darwin/apollo`, `darwin/athena`, `ResearchRun`/`research_runs`: untouched by this work.
- Next: `SPEC-FIX-001` (pre-existing, unrelated `darwin/specification/validation.py` malformed-composition defect) before `PID-006B — XAUUSD Candle Causal Core`.

Authoritative detail: `docs/pids/PID-006-APOLLO.md` §5/§35, PR `maff0000/DARWIN#18`.

---

## 14. Amendment A-006 — Market Truth Profiles and instrument-specific research capabilities (2026-09-29)

- Locked doctrine: `GREEN_DARWIN_A006_MARKET_TRUTH_PROFILE_DOCTRINE_LOCKED`. DARWIN remains one instrument-generic research/proof platform; GC/HMT-2 is not, and must never become, a universal DARWIN dependency.
- Instrument-specific research capability is governed through a **Market Truth Profile** concept (or exact semantic equivalent) — an architectural concept only; no `MarketTruthProfile` class is authorised until a concrete consumer contract requires one.
- Strategy applicability is capability-aware: a strategy/research configuration may require market-truth capabilities beyond ordinary instrument identity (native tick/bid-ask replay, order-book context, event-level sequencing, etc.). Missing required capability → fail closed/not-applicable, never a fabricated equivalent or silent degrade.
- Three distinct, non-blurring truth relationships: native-market truth, cross-market contextual truth (never silently promoted into execution truth), venue-specific microstructure truth (HMT-2 GC MBP-1 belongs here).
- GC ≠ XAUUSD, reaffirmed (Amendment A-005): GC event truth is never XAUUSD execution truth; any GC→XAUUSD contextual use must be explicit, never silent.
- **Platform genericity is mandatory; edge portability is not.** A GC-dependent edge may legitimately remain GOLD/XAUUSD-only — that is not a failure of DARWIN's multi-instrument architecture. A future instrument (crypto/equity/FX/futures) gets its own governed Market Truth Profile, never a second DARWIN.
- Research sequence reaffirmed: XAUUSD candle causal core → HMT-2 data usability → governed actual-GC semantics/economics → controlled same-contract GC microstructure-value experiment → (if justified) separate GC-context-for-XAUUSD experiment → only then reconsider HMT-LIVE. The controlled same-contract experiment must never be confused with the later cross-market experiment.
- `ResearchInputBinding`/`ResearchConfiguration` (PID-006A) are directionally compatible with A-006; no immediate schema migration required.
- Documentation only — no implementation, migration, or new class/package authorised by A-006 itself.

Authoritative detail: `docs/architecture/AMENDMENT-A006-MARKET-TRUTH-PROFILES.md`.

---

## 15. Amendment A-007 — canonical strategy definition & serialization doctrine (2026-09-29)

- Locked doctrine: `GREEN_DARWIN_A007_CANONICAL_STRATEGY_CONTRACT_DOCTRINE_LOCKED`. Every DARWIN strategy has one canonical, versioned, machine-readable representation before it may enter research, proof, qualification or promotion.
- Required route: `human/AI/external idea → canonical strategy JSON → schema validation → typed Specification model → finalise() → immutable StrategyVersion → CanonicalStrategyCompiler → ExecutableStrategyPlan`. No strategy may bypass this route.
- JSON is the standard durable interchange/serialization format — it is never the semantic authority. The semantic authority remains DARWIN's governed typed Specification model and immutable `StrategyVersion`.
- Structural (schema) validation and semantic (Specification) validation are separate gates: `JSON structurally valid ≠ Strategy semantically valid`.
- Human-readable thesis/rationale/provenance is permitted but is never executable meaning; ambiguous prose must produce a governed refusal, never runtime interpretation.
- Deterministic canonicalisation is required for fingerprints — JSON formatting/property order must never affect semantic identity. Unknown/unsupported semantic fields fail closed.
- AI may propose/generate strategy JSON but may never bypass Specification validation; no LLM interpretation is permitted inside APOLLO's or ATHENA's causal execution path. ATHENA/APOLLO consume governed typed/compiled strategy identity only, never arbitrary JSON.
- A-006 integration (§14): required market capabilities are explicit strategy semantics (`required_market_capabilities`), never hidden agent memory or a human note. Invariant: `strategy requirements → MarketTruthProfile capabilities → compatible/not compatible`.
- Do not create a second competing strategy model or a new DSL merely because A-007 exists. `StrategyVersion` remains the immutable semantic authority. Documentation only — no JSON Schema, serializer, migration or new strategy class authorised by A-007 itself; implementation is deferred until a concrete consumer requires it, and must wrap the existing Specification domain.

Authoritative detail: `docs/architecture/AMENDMENT-A007-CANONICAL-STRATEGY-DEFINITION.md`.

---

## 16. SPEC-FIX-001 closure + A-006/A-007 durable lock (2026-09-29)

- `SPEC-FIX-001 = CLOSED GREEN` (`GREEN_DARWIN_SPEC_FIX_001_FAIL_CLOSED_ACCEPTED`). Merged `main` via PR #20 at `35100934356abae1c580a77b4dd9440ad9fb808a` (first parent `b0ff8b0e24d5c6a669403117f4f1cb33c6b094c3`, second parent `bdba1eeada600bb9230cb98fbec0f497367c9396`). `darwin/specification/composition.py`'s five composition constructors now fail closed (`InvalidCompositionError`) on malformed nested state instead of leaking a bare `AttributeError`; `all_leaf_conditions()` carries an independent defence-in-depth check. The PID-006A adversarial compiler test was adapted (not retired) per Architect ruling to use `object.__setattr__` invariant-bypass instead of direct construction, preserving its original proof that `CanonicalStrategyCompiler` independently fails closed too.
- `A-006 = DURABLY LOCKED` (`GREEN_DARWIN_A006_MARKET_TRUTH_PROFILE_DOC_ACCEPTED`). Merged via PR #21 at `a9267b2d4013129784f388c75001a7047d5da595` (first parent `35100934356abae1c580a77b4dd9440ad9fb808a`, second parent `f6c5c45fc528caf25db6570affe9135d5001a83f`).
- `A-007 = DURABLY LOCKED` (`GREEN_DARWIN_A007_CANONICAL_STRATEGY_DOC_ACCEPTED`). Merged via PR #22 at `0936d07fb18215c701ed6d8123a1320b3c796d5d` (first parent `a9267b2d4013129784f388c75001a7047d5da595`, second parent `0b8ecdcca660b57db61496ffbf5630a1bd467c89`).
- Final reconciled `main`: `0936d07fb18215c701ed6d8123a1320b3c796d5d`.

---

## 17. PID-006B closure — XAUUSD Candle Causal Core (2026-10-02)

- Verdict: `GREEN_DARWIN_PID006B_XAUUSD_CAUSAL_CORE_ACCEPTED`. Implements `docs/work-orders/WO-PID006B-001-XAUUSD-CANDLE-CAUSAL-CORE.md` (first Git-tracked Work Order under the new PID→WO→FORGE delivery invariant).
- Merged via two PRs, in order: PR #25 (WO doc) at `ccac72dde1a84589beb88b5818fc0335d4d4d2fc` (first parent `dcf5de59bc28c2454825f4a544842c5e3d9aaada`, second parent `0ef0a3c1cc1e48949cb7bb497c2b08e37136fd73`); PR #24 (implementation) at `ae820221640a1116bb983b3077cc6e7dd977b70e` (first parent `ccac72dde1a84589beb88b5818fc0335d4d4d2fc`, second parent `9451561b0e4c0a0a00d95cdce927a4314ee37c54`).
- First real APOLLO causal backtesting engine (`darwin/apollo/`): exact next-bar-open causal timing, SL-first same-bar resolution, wick-based touch detection, single-position mark-to-market equity/drawdown, governed exit-bar MAE/MFE resolution (`CONSERVATIVE_EXCURSION_V1`), three bound deterministic evidence hashes plus an `evidence_envelope_hash`. New `EvidenceLevel.APOLLO_RESULT` (migration `0013`) — `APOLLO_PROOF` unchanged; every PID-006B run persists as `APOLLO_RESULT`.
- Went through three Architect-authorised adversarial-audit correction rounds (CA-006B-1..6: load-bearing `ExecutableStrategyPlan`, full `ResearchConfiguration` axis reverification, mechanical dataset binding, exhaustive semantic-field gate, exact `ExecutionPolicyComponent` structural equality, evidence-identity binding; CA-006B-7..9: forged-plan-payload detection, narrow schema/unit/data-requirement/depth/policy gate, governed exit-bar MAE/MFE resolution) — all independently re-audited clean before each re-acceptance.
- Real HERMES DEV end-to-end acceptance: XAU_USD/H1, `2025-01-06T00:00:00Z`–`2025-02-03T00:00:00Z`, selected before inspecting performance (not an acceptance criterion).
- **`darwin_ro` credential rotated 2026-10-02T10:51:23Z** (HELM-scoped hygiene action, triggered by the PID-006B audit disclosing the secret value into a transient agent tool transcript — no source-code leak, but treated as disclosed per Central Architecture policy). Rotation also surfaced and fixed a real, independent, pre-existing operational defect: the live `darwin-darwin_core-1` container had been running against a stale pre-rotation copy of the credential (two divergent secret-file copies existed; `hermes_adapter` reported `DEGRADED`/unreachable in `/api/v1/ready` before rotation). Both copies now hold the identical rotated value; live container restarted and reverified `hermes_adapter: OK`. Secret value never recorded here or anywhere durable — only this fact and timestamp.
- `darwin/research_contracts/` and `darwin/specification/` untouched by this work.
- Next gate: PID-006C (per the standing invariant, no FORGE dispatch before its Work Order exists in Git).
