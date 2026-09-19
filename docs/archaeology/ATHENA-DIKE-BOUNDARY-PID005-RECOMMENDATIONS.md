# ATHENA↔DIKE Boundary — PID-005 Recommendations

**Status:** archaeology synthesis only. Nothing in this document authorises implementation; it is factual/recommendatory input for Central Architecture's PID-005 authoring, per the archaeology brief's own framing. Companion documents: `ATHENA-PID005-CURRENT-STATE-LEGACY-REUSE-ASSESSMENT.md`, `DIKE-PID005-LEGACY-REUSE-ASSESSMENT.md`.

## 1. The governed ATHENA role, restated against the evidence

The brief's governed flow — `StrategyVersion + InstrumentDefinition + MarketDataset + authorised parameter/search envelopes + ExecutionPolicy compatibility + DIKE compatibility → ATHENA → bounded exploratory research → durable ATHENA evidence` — is **already fully supported by current DARWIN's data model** (see companion doc §1-4): `PolicyCompatibilityDeclaration`/`PolicySearchAuthority` already express authorised envelopes per policy class including `DIKE_POLICY`; `MarketDataset` is already the correct immutable RAM representation; `ResearchRun` already carries `dike_state`/`dike_policy_id`/`dike_policy_version`/`dike_policy_fingerprint`. **PID-005 does not need to invent this scaffolding — it needs to build the engine that consumes it.**

## 2. What ATHENA should adopt from legacy, and from where specifically

- **Search mechanics**: adopt `run_nowic_sweep.py`'s lineage (deterministic grid + hash-pipeline serial/parallel parity proof + per-worker DB plan isolation) as the primary architectural reference, not `optimizer.py`'s. `optimizer.py`'s random/local-perturbation stage is worth keeping as a *concept* (a second, explicitly-labelled "local random refinement" search mode, never described as Bayesian), but only once re-seeded for reproducibility.
- **Parameter transmission**: build the config-override/parameter-transmission path so it is *mechanically derived* from the authorised `PolicySearchAuthority`/tunable-parameter declarations on the `StrategyVersion`, never a hand-maintained allowlist. This directly closes the legacy "silent parameter drop" defect (companion doc §9) at the architecture level rather than by code review discipline alone.
- **Scoring/ranking**: build one objective function (not four independent, undocumented ones), with a mandatory, non-optional minimum-sample-size gate, and make the risk-regime (guarded vs. disabled) under which each candidate's metrics were observed a first-class, queryable field of its evidence — not an invisible precondition the way legacy's DIKE-disabled wide search was.
- **DIKE gating logic**: reuse the *shape* of `apollov4`/`tyche`'s `check_gate()` (regime-aware position caps, daily/session/streak/burst/profit-lock checks, DB-driven fail-loud config, zero self-adaptation) as the closest legacy analogue for a future `DIKEPolicyVersion`'s evaluation semantics — but only the gating half. Never adopt any of the four found `get_lot_size()`/`adjust_position_size()` methods, the dormant sizing-shaped DB columns, or the `StreakRules.loss_streak_action` field's sizing-action values.
- **Process pattern for DIKE_DISABLED-equivalent research**: the `WO-DIKE-DISCOVERY-MODE-0001` → `WO-DIKE-MATURE-0001` pairing (paper-scoped throttle relaxation → evidence-based restoration, human-approved, documented rollback) is a strong template for how a DARWIN ATHENA research cycle that authorises a `DIKE_DISABLED` baseline should be structured and later reconciled against a `DIKE_GUARDED` re-run.

## 3. What must explicitly NOT cross the boundary

1. Any of the four legacy sizing methods (`get_lot_size()` × 3, `adjust_position_size()` × 1) or the dormant sizing-shaped DB columns — these belong, if anywhere, to a future `SizingPolicyVersion`, and PID-005 should not give ATHENA any authority to search or apply them under the `DIKE_POLICY` compatibility class.
2. `proteus/dike/processor.py`'s "canonical shared" claim — it is a documented isolation-doctrine violation and a stale drift artifact, not an architectural precedent to follow for how DARWIN's own DIKE-policy code should be organised across services.
3. The label "Bayesian" for any DARWIN search technique that is, in fact, unseeded local random perturbation — naming must be accurate from the start.
4. EPIC-DIKE-001's confidence/streak/recovery multiplicative sizing formula — it was never implemented in legacy and must not be resurrected inside DARWIN's DIKE policy semantics; if PID-005/a future SizingPolicyVersion wants this concept, it should be designed fresh against DARWIN's own StrategyVersion/SizingPolicyVersion separation, not ported from an abandoned proposal.
5. Legacy's invisible drawdown-blindness coupling (scoring on drawdown produced under an artificially-unconstrained `DIKE_DISABLED` regime without labelling it as such).

## 4. Recommended ATHENA evidence shape for PID-005 (not finalised — a recommendation)

Per WO §16, at minimum a DARWIN `ResearchRun`/evidence record should carry (fields already present on `darwin.research_store.models.ResearchRun` marked ✅; new fields this archaeology recommends marked ➕):

- ✅ `id`, `candidate_id`, `version_id` (StrategyVersion identity)
- ✅ `instrument`, `instrument_definition_id`, `timeframe`
- ✅ `dataset_id` (→ `MarketDatasetRecord`, itself carrying `hermes_contract_version`/`hermes_contract_commit`/`fingerprint_sha256` — full HERMES/dataset provenance already modelled)
- ✅ `configuration_fingerprint`
- ✅ `dike_state`, `dike_policy_id`, `dike_policy_version`, `dike_policy_fingerprint`
- ➕ exact `ExecutionPolicyVersion` id/config (not yet a field on `ResearchRun` — currently only DIKE policy identity is bound; execution-policy identity binding should be added symmetrically before PID-005 ships)
- ➕ exact `SizingPolicyVersion` id/config, when applicable (none exists yet at all — correctly, since sizing is not yet a governed concept; the field should be added as nullable/absent until that policy class is real)
- ➕ engine build/version (which ATHENA code build produced this evidence — legacy has no equivalent; DARWIN should version its own engine explicitly, unlike any legacy component read)
- ➕ search methodology + methodology version (grid vs. random vs. local-refinement, and which version of that method — closest legacy analogue: `sweep_core.py`'s `combo_id`/`grid_hash`, generalised)
- ➕ objective/metric definition actually used to score this run (not just the resulting metrics) — legacy's mistake was letting scoring formulas proliferate undocumented; DARWIN should persist which objective was applied, versioned
- ✅-ish `sample counts`/`trade counts` should exist and be a **hard gate**, not merely stored (legacy stored trade counts in several places but never gated on them)
- ➕ drawdown/risk-regime label (guarded vs. disabled) attached directly to the evidence, addressing the drawdown-blindness finding
- ➕ temporal coverage (exact date range replayed) — legacy passes this to Apollo but ATHENA's own evidence records should also persist it directly, not rely on reconstructing it from the Apollo call
- ➕ rejection/failure reason, for candidates ATHENA explicitly disqualifies (e.g., failing the minimum-sample-size gate) rather than merely omitting them
- ➕ reproducibility metadata: random seed (if any stochastic search stage is used), and ideally the same serial/parallel parity-hash concept `hash_pipeline.py` already proves for legacy — this is the single strongest piece of legacy engineering worth deliberately carrying forward almost as-is

This is a recommended shape, not a contract — PID-005 authoring should finalise it.

## 5. Recommended first ATHENA vertical slice (WO §23)

Smallest slice consistent with both the archaeology and current doctrine:
- One real, already-finalised, immutable `StrategyVersion` (not a placeholder)
- Instrument: `XAU_USD` (current milestone), loaded via one canonical HERMES `MarketDataset` (already buildable today via `darwin/hermes/dataset.py::build_market_dataset()`)
- A small, explicitly authorised parameter envelope (2-3 tunable dimensions, closed bounded domains, drawn from that StrategyVersion's own `tunable_parameters`/`policy_declarations` — not a hand-picked convenience set)
- `DIKE_DISABLED` baseline run, **explicitly labelled as such in the evidence** (closing the drawdown-blindness gap directly in the vertical slice, not deferred)
- One additional, bounded `DIKE_GUARDED` alternative if the StrategyVersion's own policy compatibility declares `DIKE_POLICY` as REQUIRED/PERMITTED with a non-empty search envelope — using the `apollov4`/`tyche` `check_gate()` shape (gating concepts only, no sizing) as the closest legacy reference for what a first real `DIKEPolicyVersion`'s evaluation semantics might check
- A single, explicit, versioned objective function with a hard minimum-trade-count gate
- Full reproducibility metadata (seed, if any stochastic stage is used) and a serial-vs-parallel parity proof modelled on `hash_pipeline.py`, even at small scale
- Output: durable `ResearchRun` + `EvidenceRecord` rows using the fields in §4 above (as many of the ➕ fields as PID-005 chooses to add)
- **Then STOP** — no APOLLO invocation, no lifecycle-stage transition beyond what this slice's own evidence justifies, no qualification claim.

## 6. Relationship to APOLLO (WO §24) — reconfirmed, not reopened

Current DARWIN already encodes this correctly at the type level (`EVIDENCE_LEVEL_IS_DARWIN_PROOF[ATHENA_RESULT] = False`, `[APOLLO_PROOF] = True`). ATHENA answers "which bounded configurations appear worthy of exact proof?"; APOLLO (PID-006, per `docs/pids/PID-003-SCOUT.md:209`) answers "does this exact configuration survive rigorous causal historical evaluation?" This archaeology found nothing in legacy ATHENA that should change this doctrine — if anything, the legacy scoring formulas' demonstrated fragility (no trade-count guard, four undocumented formulas, drawdown blindness) is a direct argument *for* keeping ATHENA_QUALIFIED strictly short of a DARWIN proof, exactly as current doctrine already requires.

## 7. Open architectural questions for Central Architecture (not resolved by this archaeology, by design)

1. **ExecutionPolicyVersion/SizingPolicyVersion binding on `ResearchRun`**: only DIKE policy identity is currently bound (§4 above). Should PID-005 extend `ResearchRun` symmetrically before ATHENA ships, or is DIKE-only binding intentional for the first milestone?
2. **iOS CDN sizing payload's true consumption model** (companion DIKE doc §15) — unresolved from backend code alone; needs either a Swift-side read or an explicit decision that it is out of scope for DARWIN entirely (it is a live-trading concern, likely TRON/Morpheus's, not ATHENA/DIKE research's).
3. **SL/TP intrabar resolution semantics** (WO §18/§19) — confirmed to live entirely inside Apollo (`apollo/replay_engine.py`/`apollov4/engine.py`), not ATHENA, and neither file was read in this pass (explicitly out of the `athena/`-scoped archaeology). A dedicated Apollo-focused archaeology pass, feeding PID-006, is needed before PID-006 authoring — this document cannot answer WO §18/§19 definitively, only confirm ATHENA itself carries no conflicting assumption.
4. **Frontend/backend enum drift** (`EvidenceLevel.LIVE`, `DikeState` prefix inconsistency) — a reconciliation decision needed during PID-005/PID-002 delivery, not an archaeological question, but flagged here so it isn't lost.
5. **Whether DARWIN wants a second, explicitly-labelled "local random refinement" search mode at all**, given legacy's version of it was mislabelled "Bayesian" and never validated against real overfitting risk — or whether PID-005's first milestone should ship grid-only and defer any refinement stage.
6. **Whether `proteus/dike/processor.py`'s existence (a documented isolation-doctrine violation with two production-ish claimed consumers) needs a remediation Work Order of its own in the legacy codebase**, independent of DARWIN — flagged for Central Architecture to decide whether that belongs in this programme's scope at all, since it is a tradingProteus-side defect, not a DARWIN one.

## 8. Confirmation

No implementation occurred as part of producing this document or its two companions: no ATHENA engine code, no optimisation libraries, no DIKE code changes, no migrations, no ARENA changes, no API endpoints, no deployment, no HERMES/HELIOS/TRON changes, no lifecycle state changes, no research run was executed, and no strategy was marked ATHENA_TESTED/ATHENA_QUALIFIED anywhere in DARWIN or any other system.
