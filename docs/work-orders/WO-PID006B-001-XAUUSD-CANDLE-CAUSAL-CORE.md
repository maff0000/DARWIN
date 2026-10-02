# WO-PID006B-001 — XAUUSD CANDLE CAUSAL CORE

**Status:** RETROSPECTIVE CONSOLIDATION — implementation already underway under chat-issued Architect authority; this document converts that authority into the durable Git-tracked record the new delivery invariant requires, going forward.
**Parent PID:** `docs/pids/PID-006-APOLLO.md`, §35 gate **PID-006B — XAUUSD candle causal core**.
**Applicable amendments:** A-005 (post-HMT-2 sequencing — GC/HMT-2 deferred, not implemented here), A-006 (Market Truth Profiles — respected, not implemented here), A-007 (canonical strategy JSON — respected, not implemented here). Prerequisite correction: **SPEC-FIX-001** (malformed-composition fail-closed, `darwin/specification/composition.py`), merged to `main` before this WO's base SHA.
**Delivery controller:** ROGUE. **Implementer:** FORGE. **Owner:** THE GOAL / DARWIN Architect.
**Base SHA at WO issuance (retrospective — this is the SHA FORGE actually branched from):** `dcf5de59bc28c2454825f4a544842c5e3d9aaada`
**Branch:** `pid-006b/xauusd-candle-causal-core` · **PR:** `maff0000/DARWIN#24`

---

## 1. Honesty note on sequencing

This WO is written AFTER FORGE had already produced two implementation heads on PR #24 (`36df629...` and `a5ee3e7...`) under direct chat-issued Architect authorisation, because the Git-tracked-WO delivery invariant did not yet exist when PID-006B dispatch began. It does not claim to have preceded that work. It exists to:

1. consolidate the real authority chain that actually governed PID-006B so far into one durable Git record;
2. become the explicit WO FORGE's next (and all subsequent) PID-006B correction passes state they are implementing, per the new standing invariant.

No content below changes the meaning of any ruling already issued. Where a ruling is quoted, it is quoted for record, not reinterpreted.

---

## 2. Architect authorisation chain (verdicts actually issued, in order)

1. `GREEN_DARWIN_PID006A_PROOF_CONTRACTS_ACCEPTED` — PR #18 merged (prerequisite: shared research/proof contracts exist).
2. `GREEN_DARWIN_SPEC_FIX_001_FAIL_CLOSED_ACCEPTED` — PR #20 merged (prerequisite: malformed-composition fail-closed).
3. PID-006B dispatch explicitly authorised by Central Architecture (chat instruction, "PID-006B — XAUUSD CANDLE CAUSAL CORE... Central Architecture authorises preparation/dispatch of the bounded implementation package under these rulings").
4. First candidate (head `36df62971819264cc08ecdd1d96a8275058d0a44`) independently reviewed: causal-timing/fail-closed-preflight/determinism correct, but verdict `AMBER_DARWIN_PID006B_SEMANTIC_IDENTITY_BINDING_CORRECTION_REQUIRED` — findings CA-006B-1 through CA-006B-6 (§4 below).
5. Second candidate (head `a5ee3e7b2f802f7fd6e549bbdd7f0d9c8de5a7cd`) independently reviewed: CA-006B-1..6 "substantially and genuinely closed," but verdict `AMBER_DARWIN_PID006B_FINAL_SEMANTIC_CONFORMANCE_REQUIRED` — findings CA-006B-7 through CA-006B-9 (§5 below).
6. Correction for CA-006B-7..9 is in progress at the time this WO is issued. Its candidate head is not yet known and is not recorded here.

Expected terminal verdict once all findings close: `GREEN_DARWIN_PID006B_XAUUSD_CAUSAL_CORE_ACCEPTED`.

---

## 3. Objective

Build and prove the first real APOLLO causal backtesting vertical slice. It proves APOLLO *mechanics*, not trading edge. **Performance is explicitly not an acceptance criterion.**

---

## 4. Original scope and required behaviour (as first authorised)

### 4.1 Inputs — existing accepted contracts only

Real finalised immutable `StrategyVersion`; `CanonicalStrategyCompiler`; `ExecutableStrategyPlan`; exact `ParameterSetVersion`; exact `ExecutionPolicyVersion`; exact `ResearchPartitionPolicyVersion`; exact `ResearchConfiguration`; one governed immutable XAU_USD `MarketDataset`; `DIKE_DISABLED`. No ATHENA.

### 4.2 First supported semantic subset

XAU_USD; one timeframe; one `MarketDataset`; ATOMIC entry composition; LONG direction only; single position; fixed research quantity; no multi-leg/multi-position behaviour. `StrategyVersion` must be produced through real `finalise()`, never hand-constructed.

### 4.3 Mandatory preflight (original)

Before replay, independently verify: `StrategyVersion` instrument applicability includes XAU_USD; `ResearchConfiguration` instrument identity is XAU_USD; `ResearchInputBinding` identifies the exact loaded `MarketDataset`; dataset fingerprint recomputes/matches; `MarketDataset` instrument and `InstrumentDefinition` agree with configuration; timeframe/data requirement is supported; `ParameterSetVersion` exactly matches strategy definitions; `ExecutionPolicyVersion` contains only components supported by this engine slice; DIKE state is exactly `DISABLED`. Mismatch fails before replay with a governed invalid-configuration/capability outcome. Never encode an engine defect as a losing trade.

### 4.4 Causal timing (original, permanent, unchanged by any correction)

Signal evaluated only when the source candle has closed. A close-time decision creates an order eligible at the next canonical bar open of the SAME timeframe. No same-bar close fill. Not `NEXT_M1_OPEN`. No next bar inside the bounded dataset ⇒ order remains unfilled/end-of-data.

### 4.5 Per-bar causal order (original, permanent, unchanged by any correction)

```
BAR OPEN → fill eligible pending entry → evaluate active SL/TP against that bar's high/low
  → mark position/equity → BAR CLOSE → evaluate strategy → possibly create next-bar order
```
One position only; no pyramiding. An intrabar exit making the position flat may still generate the next bar's order from the same bar's close-time evaluation.

### 4.6 Intrabar policy

High/low are first-class touch evidence. Both SL and TP touched with no better temporal evidence: `CONSERVATIVE_SL_FIRST`. No `TP_FIRST`.

### 4.7 Quantity/economics

Fixed research quantity: `1 TROY_OUNCE`. No broker lot assumption, no percent-risk sizing. Explicit deterministic research starting capital and USD account currency.

### 4.8 Costs

`ZERO_COST/v1` permitted for end-to-end mechanical acceptance — not proof-eligible. A separate deterministic non-zero-cost methodology must also be tested so spread/slippage/fees genuinely participate in fill/P&L arithmetic. No "realistic" XAU broker cost calibration.

### 4.9 Evidence classification

New authorised value `APOLLO_RESULT` (`EVIDENCE_LEVEL_IS_DARWIN_PROOF[APOLLO_RESULT] = False`); `APOLLO_PROOF` (`= True`) unchanged. Every PID-006B run — `ZERO_COST` or non-zero-cost — is `APOLLO_RESULT`, never `APOLLO_PROOF`. Only the narrow enum/schema/API/frontend compatibility changes required for this value are authorised.

### 4.10 ResearchRun

Use the existing `ResearchRun` model via `configuration_fingerprint`. No second APOLLO run model. No multi-input `ResearchRun` remodel in this WO.

### 4.11 Engine evidence

Deterministically: decision stream; order stream; fill sequence; position lifecycle; completed trade ledger; terminal position state; realised/unrealised P&L; balance/equity by bar; peak equity/drawdown; MAE/MFE (retrospective only, structurally inaccessible to the live decision path); exit reasons; decision-stream/fill-trade-sequence/economic-outcome SHA-256 identities.

### 4.12 Persistence

Minimal. `ResearchRun` + existing `evidence_records` table. No generic event store, competing market store, or broad APOLLO analytics schema. A genuinely unavoidable excess requirement must be escalated, never silently designed around.

---

## 5. Corrections issued and their disposition

### 5.1 CA-006B-1 through CA-006B-6 (issued against head `36df629...`, closed at head `a5ee3e7...`)

| # | Finding | Disposition at `a5ee3e7...` |
|---|---|---|
| CA-006B-1 | `ExecutableStrategyPlan` must be load-bearing, not ceremonial — APOLLO must derive execution meaning from the compiled plan's `semantic_payload`, never reinterpret raw `StrategyVersion` | CLOSED — `darwin/apollo/plan_adapter.py` added; `darwin/research_contracts/compiler.py` untouched |
| CA-006B-2 | Reverify the full `ResearchConfiguration` axis binding (plan/parameter-set/execution-policy/partition-policy/instrument-definition fingerprints, and the configuration's own fingerprint) independently at preflight, never trusting stored values | CLOSED — five `compute_*_fingerprint` recomputations wired into `preflight.py` |
| CA-006B-3 | Bind `PreflightResult` mechanically to the exact dataset/configuration it was computed against; replay must reject a different dataset before bar 0 | CLOSED — `PreflightResult.bound_dataset_id`/`bound_dataset_fingerprint`, checked as the first statement of `run_apollo_replay` |
| CA-006B-4 | Exhaustive supported-semantic-subset gate — every `StrategyVersion.SEMANTIC_FIELD_NAMES` field actively supported or explicitly capability-blocked, never silently passed through | CLOSED — `plan_adapter.py` accounts for all 11 fields |
| CA-006B-5 | Exact `ExecutionPolicyComponent` semantics — match by full structural equality (kind+id+version+configuration), not `(id, version)` alone | CLOSED — `capability.py` uses genuine frozen-dataclass `==` |
| CA-006B-6 | Evidence identities must bind the relevant upstream identity so numerically identical output under a different upstream identity remains scientifically distinguishable | CLOSED — new `evidence_envelope_hash`; decision/fill/economic hashes re-scoped |

Independently re-audited clean (`AUDIT PASS — CA-006B-1 through CA-006B-6 all genuinely closed, no new defect found`) before Architect re-review.

### 5.2 CA-006B-7 through CA-006B-9 (issued against head `a5ee3e7...`, correction in progress)

| # | Finding | Status |
|---|---|---|
| CA-006B-7 | Prove `ExecutableStrategyPlan.semantic_payload` is exactly the canonical payload for the supplied `StrategyVersion` — not merely that `source_semantic_fingerprint` matches and the plan's own `fingerprint` recomputes (a payload can be forged and self-consistently fingerprinted while `source_*` fields still agree) | IN PROGRESS |
| CA-006B-8 | Finish the narrow supported-semantic gate: unknown schema_semantic_version, unused declared parameters, wrong SL/TP/entry-threshold units, data-requirement/historical-depth honoured (BARS only, dataset must contain ≥N bars), unsupported policy/search declarations — all must capability-block, never "recorded but ignored" | IN PROGRESS |
| CA-006B-9 | Govern MAE/MFE candle-resolution semantics for the ambiguous exit bar — current implementation can include extrema occurring after the trade already exited within that bar; must state its measurement interval/methodology, respect `CONSERVATIVE_SL_FIRST` where that resolves the same-bar conflict, and participate in the relevant deterministic evidence identity | IN PROGRESS |

Explicitly excluded from CA-006B-7..9's fix: `darwin/research_contracts/compiler.py` (CA-006B-7 forbids touching it), M1/HMT-2 disambiguation (CA-006B-9 forbids it).

---

## 6. Allowed production scope (cumulative, all correction rounds)

- `darwin/apollo/` — the real engine package (new code home).
- `darwin/core/evidence.py` — exactly one new `EvidenceLevel.APOLLO_RESULT` value + its `EVIDENCE_LEVEL_IS_DARWIN_PROOF` entry. `APOLLO_PROOF` unchanged.
- `darwin/research_store/migrations_sql/0013_apollo_result_evidence_level.sql` — exactly one migration, narrowing two existing CHECK constraints to include `APOLLO_RESULT`. No further migration without explicit escalation.
- `frontend/src/api/types.ts`, `frontend/src/components/EvidenceBadge.tsx` (+ narrow supporting style tokens) — the narrow `APOLLO_RESULT` type/badge addition only.
- Test files under `tests/unit/`, `tests/contract/`, `tests/architecture/`, `tests/integration/` as required to prove the above.

**Never in scope for this WO:** `darwin/research_contracts/` (any file — the shared PID-006A contracts, explicitly including `compiler.py`), `darwin/apollo`/`darwin/athena` package boundary violations, HERMES source, `ResearchRun`/`research_runs` remodel, any migration beyond `0013`, broad ARENA expansion.

---

## 7. Explicit exclusions (standing, cumulative across all rounds)

GC; HMT-2; `MarketTruthProfile` implementation (Amendment A-006 is respected, not implemented); canonical strategy JSON/JSON Schema implementation (Amendment A-007 is respected, not implemented); continuous futures; roll policy; `DIKE_GUARDED`; ATHENA; optimisation; break-even; partial exits; trailing stops; multiple positions; M1 disambiguation; `NEXT_M1_OPEN`; risk-based sizing; broker/live execution; real broker cost calibration; broad ARENA expansion; any PID-006C feature.

---

## 8. Migration authority

Exactly one migration is authorised under this WO: `0013_apollo_result_evidence_level.sql`. Any further migration requirement discovered during a correction round must be escalated to Central Architecture before being added — it is not pre-authorised by this WO.

---

## 9. Required tests / falsification attacks (cumulative)

### 9.1 Original 13 (§9 of the first dispatch, all currently passing, unchanged by any correction)

Future-data-blind decisions; signal bar cannot fill itself; exact next-bar-open timing; same-bar SL+TP resolves SL-first; wick touches use high/low; dataset/instrument mismatch blocks before replay; parameter mismatch blocks before replay; unsupported policy capability blocks before replay; open-position unrealised P&L affects bar equity/drawdown; MAE/MFE remain retrospective; two independent identical runs reproduce exact hashes/ledger/equity; controlled parameter/data/policy changes perturb the appropriate identities/results; `ZERO_COST`/development mechanical run persists as `APOLLO_RESULT`, never `APOLLO_PROOF`.

### 9.2 CA-006B-1..6 (14 tests, all currently passing — §"Required new adversarial tests" of the CA-006B-1..6 correction)

ParameterSet A↔B same StrategyVersion fails before replay; ExecutionPolicy A↔B fails before replay; instrument-definition fingerprint-differs-while-bare-id-agrees fails; compiled-plan fingerprint mismatch fails; tampered/stale `ResearchConfiguration.fingerprint` fails; preflight Dataset A → replay Dataset B fails before bar 0; non-null session semantics capability-blocked; unsupported setup-expiry capability-blocked; extra unsupported data requirement capability-blocked; inconsistent ambiguity policy capability-blocked; counterfeit quantity-component configuration blocked; counterfeit cost-component configuration blocked; identical decisions under different plan/parameter/data identity remain distinguishable via evidence identity; persistence refuses mismatched `(engine_result, research_configuration, market_dataset)` triples.

### 9.3 CA-006B-7..9 (in progress — required, not yet all delivered)

Forged plan payload with valid recomputed plan/config fingerprints rejected; unknown Strategy schema semantic version capability-blocked; unused extra strategy parameter capability-blocked; wrong SL/TP unit capability-blocked; wrong entry-threshold unit (parameterised and literal) capability-blocked; insufficient dataset bar-count vs. required historical depth fails before replay; unsupported policy/search declaration capability-blocked; exit-bar MAE/MFE contamination case correctly excluded; MAE/MFE-methodology mutation changes the relevant deterministic evidence identity.

### 9.4 Real end-to-end acceptance

At least one real bounded HERMES XAU_USD `MarketDataset`, interval selected and recorded before inspecting performance. Performance is not an acceptance criterion. (Interval used so far: XAU_USD/H1, `2025-01-06T00:00:00Z`–`2025-02-03T00:00:00Z`.)

---

## 10. Audit requirements

A fresh, independent, adversarial audit (fresh context, no access to the implementing agent's own claims beyond the PR itself) is required before every Architect re-review, covering at minimum the findings open at that round. Audits performed so far: initial candidate (causal-timing/determinism/fail-closed, `AUDIT PASS`); CA-006B-1..6 correction (`AUDIT PASS — all genuinely closed, no new defect found`); CA-006B-7..9 correction audit — pending.

---

## 11. PR lineage (Git-tracked record)

| Head SHA | Event |
|---|---|
| `36df62971819264cc08ecdd1d96a8275058d0a44` | First candidate. CI green. Independent audit: causal/determinism/fail-closed `AUDIT PASS`. Architect verdict: `AMBER_DARWIN_PID006B_SEMANTIC_IDENTITY_BINDING_CORRECTION_REQUIRED` (CA-006B-1..6). |
| `a5ee3e7b2f802f7fd6e549bbdd7f0d9c8de5a7cd` | CA-006B-1..6 correction. CI green. Independent audit: `AUDIT PASS`. Architect verdict: `AMBER_DARWIN_PID006B_FINAL_SEMANTIC_CONFORMANCE_REQUIRED` (CA-006B-7..9). |
| *(pending)* | CA-006B-7..9 correction — in progress at WO issuance. |

---

## 12. Expected terminal state

`GREEN_DARWIN_PID006B_XAUUSD_CAUSAL_CORE_ACCEPTED`, once CA-006B-7..9 close and a fresh independent audit confirms no new defect. Until then: `READY_FOR_DARWIN_ARCHITECT_PID006B_FINAL_REACCEPTANCE`.

---

## 13. Permanent delivery invariant this WO establishes going forward

```text
Architect decision → PID / Amendment → Git → ROGUE Work Order → Git
    → FORGE → implementation/tests → independent audit → PR
    → Architect acceptance → merge → closure
```

FORGE must not begin or continue a DARWIN implementation package unless it can name the exact Git-tracked parent PID and the exact Git-tracked bounded Work Order authorising it. From PID-006C onward, no FORGE dispatch occurs before its Work Order exists in Git. A Work Order may operationalise an Architect-approved PID; it may never invent product semantics, architecture, evidence policy, or cross-system authority — any such ambiguity returns to Central Architecture before FORGE proceeds.
