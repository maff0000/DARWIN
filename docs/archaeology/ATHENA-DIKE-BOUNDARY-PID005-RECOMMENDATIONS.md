# ATHENA↔DIKE Boundary — PID-005 Recommendations

**Status:** archaeology synthesis only. Nothing in this document authorises implementation; it is factual/recommendatory input for Central Architecture's PID-005 authoring, per the archaeology brief's own framing. Companion documents: `ATHENA-PID005-CURRENT-STATE-LEGACY-REUSE-ASSESSMENT.md`, `DIKE-PID005-LEGACY-REUSE-ASSESSMENT.md`.

## 0. Central Architecture rulings incorporated in this revision (2026-09-19)

This document (and its two companions) were revised against `GREEN_DARWIN_ATHENA_DIKE_ARCHAEOLOGY_WITH_BOUNDED_CORRECTION_REQUIRED`, verdict head `245b8c7f459592cfb35b9e8a179e1e1e745c5b99`. No new legacy or DARWIN source was read to produce this revision — every change below is a documentation correction or an explicit ruling recorded verbatim against the existing evidence. Rulings applied:

1. DIKE has no canonical legacy source (six independent implementations) — this is a **completed** finding, not a blocked one. See companion DIKE doc's new "Canonical-source ruling" section.
2. The previously-reported `DikeState` frontend/backend naming drift is retracted as a false positive (bare enum member names vs. wire values). Only `EvidenceLevel.LIVE` remains a real drift.
3. PID-005's first milestone is **deterministic grid search only**. Legacy random/local-refinement search is a `DEFERRED_CONCEPT`.
4. The first ATHENA vertical slice is **`DIKE_DISABLED` only** — no `DIKE_GUARDED` alternative in slice one.
5. Exact `ExecutionPolicyVersion` identity binding on `ResearchRun` is **required**, separate from `StrategyVersion` identity, before PID-005 evidence is valid.
6. `SizingPolicyVersion` is **not** to be speculatively added (no DB columns, no legacy sizing port) — sizing is simply absent/not-applicable for the first slice.
7. A governed **multi-timeframe dataset-set binding** (`ResearchRunDatasetBinding`-equivalent) is a new required PID-005 consequence — a single `dataset_id`/`timeframe` pair on `ResearchRun` is insufficient for multi-timeframe `StrategyVersion`s.
8. Parameter transmission must be a **mechanically provable exact-set equality** (authorised = generated = applied = recorded), hard-failing on any mismatch, with an acceptance test recreating the legacy 8-declared/4-applied defect.
9. Sample/trade adequacy is a **hard gate**, not a scoring term; PID-005 — not this archaeology — defines the exact adequacy threshold and the single versioned objective/ranking method.
10. ATHENA does not own `StrategyVersion` semantics — a deterministic research-evaluation boundary must be built for reuse by APOLLO, so the two engines never diverge on what a strategy means.
11. Serial/parallel parity: reuse **the principle** (same inputs → same deterministic evidence regardless of execution order), not necessarily legacy source code; single-host multiprocessing only, no distributed architecture.
12. The iOS/Morpheus CDN sizing-consumption question is **out of PID-005 scope** — retained as legacy context/debt only, no Swift-side archaeology performed.
13. Remediating legacy `proteus/dike/processor.py`'s stale "canonical shared" drift is **out of DARWIN PID-005 scope** — evidentiary value only, no remediation Work Order launched from this archaeology.
14. Apollo/DIKE-execution archaeology (SL/TP ordering, wick/intrabar semantics, causal replay) remains explicitly deferred to a dedicated pre-PID-006 archaeology pass — not pulled into PID-005.
15. The first ATHENA vertical slice is revised accordingly (§5 below); a completed slice may establish `ATHENA_TESTED` semantics once PID-005 defines that lifecycle transition precisely — it does **not** establish `ATHENA_QUALIFIED` merely because configurations were ranked.

## 1. The governed ATHENA role, restated against the evidence

The brief's governed flow — `StrategyVersion + InstrumentDefinition + MarketDataset + authorised parameter/search envelopes + ExecutionPolicy compatibility + DIKE compatibility → ATHENA → bounded exploratory research → durable ATHENA evidence` — is **already fully supported by current DARWIN's data model** (see companion doc §1-4): `PolicyCompatibilityDeclaration`/`PolicySearchAuthority` already express authorised envelopes per policy class including `DIKE_POLICY`; `MarketDataset` is already the correct immutable RAM representation; `ResearchRun` already carries `dike_state`/`dike_policy_id`/`dike_policy_version`/`dike_policy_fingerprint`. **PID-005 does not need to invent this scaffolding — it needs to build the engine that consumes it**, and to extend `ResearchRun` with the execution-policy and dataset-set binding described in §4 and §5 below.

## 2. What ATHENA should adopt from legacy, and from where specifically

- **Search mechanics — grid only for PID-005's first milestone.** Adopt `run_nowic_sweep.py`'s lineage (deterministic grid + hash-pipeline serial/parallel parity proof + per-worker DB plan isolation) as the sole architectural reference for the first implementation slice. `optimizer.py`'s random/local-perturbation stage is `DEFERRED_CONCEPT` — not part of PID-005's first slice. It may be reconsidered later only with an explicit seed, genuine reproducibility, real evidence it adds value over grid search, correct naming (never "Bayesian" — legacy's own use of that label was inaccurate; there is no surrogate model or acquisition function anywhere in the source), and explicit overfitting controls.
- **Parameter transmission**: build the config-override/parameter-transmission path so it is *mechanically derived* from the authorised `PolicySearchAuthority`/tunable-parameter declarations on the `StrategyVersion` — and make the resulting equality mechanically provable end-to-end (§4 below), not merely "derived" as a one-time code-review discipline. This directly closes the legacy "silent parameter drop" defect (companion doc §9).
- **Scoring/ranking**: build one objective function (not four independent, undocumented ones), with sample/trade adequacy enforced as a hard gate ahead of scoring (§4), and make the risk-regime (guarded vs. disabled) under which each candidate's metrics were observed a first-class, queryable field of its evidence — not an invisible precondition the way legacy's DIKE-disabled wide search was.
- **DIKE gating logic (future increment, not PID-005's first slice)**: the *shape* of `apollov4`/`tyche`'s `check_gate()` (regime-aware position caps, daily/session/streak/burst/profit-lock checks, DB-driven fail-loud config, zero self-adaptation) is the closest legacy analogue for a future `DIKEPolicyVersion`'s evaluation semantics — but only the gating half, and only once a canonical DARWIN `DIKEPolicyVersion` domain contract/evaluator is separately governed (§5). Never adopt any of the four found `get_lot_size()`/`adjust_position_size()` methods, the dormant sizing-shaped DB columns, or the `StreakRules.loss_streak_action` field's sizing-action values.
- **Process pattern for `DIKE_DISABLED`-equivalent research**: the `WO-DIKE-DISCOVERY-MODE-0001` → `WO-DIKE-MATURE-0001` pairing (paper-scoped throttle relaxation → evidence-based restoration, human-approved, documented rollback) is a strong template for how a DARWIN ATHENA research cycle that authorises a `DIKE_DISABLED` baseline should be structured and later reconciled against a `DIKE_GUARDED` re-run — once that later increment exists.

## 3. What must explicitly NOT cross the boundary

1. Any of the four legacy sizing methods (`get_lot_size()` × 3, `adjust_position_size()` × 1), the dormant sizing-shaped DB columns, or the iOS CDN sizing payload (`dike/ios_publisher.py`) — sizing is out of scope entirely for PID-005's first slice, not merely deferred to a symmetric future field. Do not add speculative `SizingPolicyVersion` columns "for symmetry"; sizing is simply absent/not-applicable until a governed `SizingPolicyVersion` contract exists.
2. `proteus/dike/processor.py`'s "canonical shared" claim — it is a documented isolation-doctrine violation and a stale drift artifact, not an architectural precedent to follow for how DARWIN's own DIKE-policy code should be organised across services. Remediating it is a `tradingProteus`-side concern, out of DARWIN PID-005's scope.
3. The label "Bayesian" for any DARWIN search technique that is, in fact, unseeded local random perturbation — naming must be accurate from the start. This entire search mode is `DEFERRED_CONCEPT` for PID-005's first milestone regardless of naming.
4. EPIC-DIKE-001's confidence/streak/recovery multiplicative sizing formula — it was never implemented in legacy (zero repo hits for `confidence_factor`) and must not be resurrected inside DARWIN's DIKE policy semantics now or speculatively.
5. Legacy's invisible drawdown-blindness coupling (scoring on drawdown produced under an artificially-unconstrained `DIKE_DISABLED` regime without labelling it as such).
6. `DIKE_GUARDED` research runs — out of PID-005's first vertical slice entirely (§5). DARWIN does not yet possess a canonical `DIKEPolicyVersion` domain contract/evaluator; inventing one implicitly while simultaneously proving ATHENA's fundamental engine would conflate two separate governance decisions.
7. Any DIKE-execution-layer question (SL/TP same-bar ordering, wick/intrabar semantics, causal replay correctness) — these belong entirely to a dedicated Apollo+DIKE archaeology pass ahead of PID-006, not to PID-005.

## 4. Required ATHENA evidence shape for PID-005

Per the brief's evidence-shape requirement, a DARWIN `ResearchRun`/evidence record must carry (fields already present on `darwin.research_store.models.ResearchRun` marked ✅; fields this document requires PID-005 to add marked **REQUIRED**; fields explicitly NOT to be added yet marked **NOT YET**):

- ✅ `id`, `candidate_id`, `version_id` (StrategyVersion identity)
- ✅ `instrument`, `instrument_definition_id`, `timeframe`
- ✅ `dataset_id` (→ `MarketDatasetRecord`, carrying `hermes_contract_version`/`hermes_contract_commit`/`fingerprint_sha256`)
- ✅ `configuration_fingerprint`
- ✅ `dike_state`, `dike_policy_id`, `dike_policy_version`, `dike_policy_fingerprint`
- **REQUIRED** — exact `ExecutionPolicyVersion` identity/configuration, bound to the run **separately from `StrategyVersion` identity** (never collapsed into it). Research evidence must always be able to answer, with no invisible assumption: what spread, slippage, fill rule, execution delay, and fee/commission model produced these fills/results? This is not optional or deferrable the way sizing is — every `ResearchRun` has *some* execution assumption whether recorded or not, so PID-005 must record it explicitly rather than leave it implicit.
- **NOT YET** — no `SizingPolicyVersion` field, no sizing-shaped DB columns, added now. Sizing is not a governed concept yet; the first ATHENA slice does not need it, and speculative symmetry is not a reason to add schema ahead of the governed contract existing. When sizing becomes real, `ResearchRun` evidence must eventually bind it separately, at that time.
- **REQUIRED** — a governed exact input-dataset-**set** binding (not a single `dataset_id`/`timeframe` pair), because canonical `StrategyVersion` semantics already permit atomic components to bind different explicit timeframes (e.g. `CONTEXT H4` + `TRIGGER H1`), and a single-dataset identity is insufficient permanent evidence for such a run. Conceptually:
  ```text
  ResearchRun
    ↓
  ResearchRunDatasetBinding*        (exact naming is PID-005's to decide)
    ├── timeframe H1 → MarketDataset A
    └── timeframe H4 → MarketDataset B
  ```
  Requirements on this binding: every bound dataset carries its own immutable fingerprint/provenance; all datasets belong to the governed instrument definition the run requires; every timeframe the `StrategyVersion` actually requires is covered by the binding; no unbound/unexpected dataset may silently influence evaluation; and the run's overall evidence fingerprint/identity must include the exact dataset **set**, not just one dataset. The first vertical slice may use a single H1 dataset, but the engine must not be designed so that exactly one dataset is a permanent assumption.
- engine build/version (which ATHENA code build produced this evidence — legacy has no equivalent; DARWIN should version its own engine explicitly)
- search methodology + methodology version — for PID-005's first slice this is simply "deterministic grid, version N"; the field must still exist so a later `DEFERRED_CONCEPT` search mode has somewhere to be recorded once it is real
- the single objective/metric definition actually applied to score this run, itself versioned — never four undocumented competing formulas
- **REQUIRED as a hard gate, not merely a stored count** — sample/trade adequacy. A candidate failing the gate is explicitly disqualified with a recorded reason and *retained* in evidence (not silently omitted); PID-005 defines and versions the exact adequacy rule, not this archaeology.
- drawdown/risk-regime label (guarded vs. disabled) attached directly to the evidence, addressing the drawdown-blindness finding
- exact temporal coverage (date range replayed), persisted directly on the evidence rather than reconstructed from an Apollo call
- reproducibility metadata: random seed (only relevant once/if a stochastic search stage becomes real) and a serial/parallel determinism parity proof (§6), modelled on `hash_pipeline.py`'s principle
- **REQUIRED as a mechanically checked invariant, not a recommendation**: authorised search dimensions = generated config dimensions = applied evaluator config dimensions = recorded evidence config dimensions, subject only to explicitly FIXED/non-search parameters outside that set. If ATHENA records a dimension as varied but the evaluator never consumed it: hard failure. If the evaluator receives an undeclared search dimension: hard failure. PID-005 must include an acceptance test that deliberately recreates the legacy 8-declared/4-applied defect (companion ATHENA doc §9) and proves DARWIN refuses it.

This is a required shape, not yet a finalised schema — PID-005 authoring finalises field names/types.

## 5. Required first ATHENA vertical slice (Central Architecture ruling — supersedes any prior recommendation)

```text
one real immutable StrategyVersion
+
XAU_USD
+
exact required MarketDataset set (single timeframe acceptable for first fixture)
+
small 2–3 dimension authorised closed parameter envelope
  (drawn from that StrategyVersion's own tunable_parameters/policy_declarations,
   not a hand-picked convenience set)
+
one explicit versioned ExecutionPolicy
+
DIKE_DISABLED only, explicitly labelled as such in the evidence
+
deterministic GRID search only
+
hard sample-adequacy gate
+
one explicit versioned ATHENA objective/methodology
+
exact parameter-transmission equality proof (§4)
+
serial/parallel deterministic parity proof (§6)
        ↓
durable ATHENA_RESULT evidence
```

**Then STOP.** The first slice does **not** require: `DIKE_GUARDED`; random search; local refinement; anything resembling Bayesian optimisation; sizing of any kind; APOLLO invocation; or an `ATHENA_QUALIFIED` claim. A successfully completed slice may establish `ATHENA_TESTED` semantics once PID-005 defines that lifecycle transition precisely — ranking a set of configurations is not, by itself, grounds for `ATHENA_QUALIFIED`.

## 6. Determinism: reuse the principle, not necessarily the code

Retain the hash-pipeline finding, but state the reuse boundary precisely: DARWIN reuses **the principle** `hash_pipeline.py` proves, not necessarily its source. PID-005 must prove that identical (`StrategyVersion`, dataset set, execution policy, DIKE state/policy, exact configuration, methodology) inputs produce the *same deterministic result/evidence* whether the evaluation runs serially or in parallel — provided the evaluation itself is deterministic. Parallel completion order must never affect evidence identity or ranking (the legacy `imap_unordered` + explicit re-sort-by-`combo_id` pattern is the correct shape for this). Single-host multiprocessing is the only architecture in scope; no distributed execution model is being considered at this stage.

## 7. ATHENA does not own StrategyVersion semantics

ATHENA controls which authorised configuration to test, search ordering/method, objective/ranking, and the resulting research evidence. It must **not** develop an independent interpretation of what a `StrategyVersion`'s rules mean. PID-005 must establish one deterministic research-evaluation boundary/mechanism that consumes canonical `StrategyVersion` semantics — and that same mechanism (or a directly compatible successor) should be reusable by APOLLO (PID-006), so ATHENA and APOLLO never develop two different meanings for the same `StrategyVersion`. APOLLO may apply a stricter proof procedure or an exact frozen configuration on top of that shared evaluation boundary; it must not reinterpret the strategy itself. This also preserves eventual HELIOS semantic portability, since a single, shared interpretation layer is easier to port than two independently-evolved ones.

## 8. Relationship to APOLLO — reconfirmed, not reopened

Current DARWIN already encodes this correctly at the type level (`EVIDENCE_LEVEL_IS_DARWIN_PROOF[ATHENA_RESULT] = False`, `[APOLLO_PROOF] = True`). ATHENA answers "which bounded configurations appear worthy of exact proof?"; APOLLO (PID-006, per `docs/pids/PID-003-SCOUT.md:209`) answers "does this exact configuration survive rigorous causal historical evaluation?" This archaeology found nothing in legacy ATHENA that should change this doctrine — if anything, the legacy scoring formulas' demonstrated fragility (no trade-count guard, four undocumented formulas, drawdown blindness) is a direct argument *for* keeping `ATHENA_QUALIFIED` strictly short of a DARWIN proof, exactly as current doctrine already requires. SL/TP same-bar ordering, wick/intrabar semantics, and causal replay correctness remain entirely out of this document's scope — they require a dedicated Apollo+DIKE archaeology pass before PID-006 authoring, not before PID-005.

## 9. Open architectural questions remaining for Central Architecture

Most prior open questions in this section were resolved by the rulings recorded in §0 and are no longer open (execution/sizing policy binding → §4; iOS CDN payload → out of scope §12/§0.12; local random refinement → deferred §0.3; `proteus/dike/processor.py` remediation → out of scope §0.13). What remains genuinely open:

1. **SL/TP intrabar resolution semantics and causal replay correctness** — confirmed to live entirely inside Apollo (`apollo/replay_engine.py`/`apollov4/engine.py`), neither file read in this archaeology (explicitly out of the `athena/`-scoped work). A dedicated Apollo-focused archaeology pass, feeding PID-006, is needed before PID-006 authoring.
2. **`EvidenceLevel.LIVE`** (frontend-only enum member with no backend equivalent) — a reconciliation decision needed during PID-005/PID-002 delivery; not an archaeological question, flagged here so it isn't lost.
3. **Exact naming and schema** for the `ResearchRunDatasetBinding`-equivalent (§4) and for the adequacy-gate threshold (§4/§9 of the companion ATHENA document) — both explicitly left to PID-005 authoring, not resolved here.

## 10. Confirmation

No implementation occurred as part of producing this document or its two companions, nor as part of this revision: no ATHENA engine code, no optimisation libraries, no DIKE code changes, no migrations, no ARENA changes, no API endpoints, no deployment, no HERMES/HELIOS/TRON changes, no lifecycle state changes, no research run was executed, and no strategy was marked `ATHENA_TESTED`/`ATHENA_QUALIFIED` anywhere in DARWIN or any other system. This revision changed only the three archaeology documents themselves.
