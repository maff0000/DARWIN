# HELIOS Archaeology — PID-004A Semantic Compatibility

**HELIOS commit inspected:** `7f7193d55475e40583892b94dd461b1b64d6f1ef` (branch `main`, dell-debian `/srv/HELIOS`)
**Inspected:** read-only. No files were edited, staged or committed in `/srv/HELIOS`; no git-state-changing command was run. `git -C /srv/HELIOS status --porcelain` returned empty both before and after this inspection, and `HEAD` was re-checked at the end and is unchanged.

---

## Summary table

| # | Concept | Classification | Key evidence |
|---|---|---|---|
| 1 | Atomic strategy semantics | `DIRECTLY_COMPATIBLE` (as a concept) / `COMPILABLE_WITH_VERSIONED_ADAPTER` (as code) | `docs/ATOMS.md` §1; `helios/strategies/base.py`; package format `helios/spec/model.py::StrategyPackage` (`kind: ATOMIC`) |
| 2 | `ALL` | `DIRECTLY_COMPATIBLE` | `helios/composition/primitives.py::_evaluate_all` — every component must hold, no ordering, no timing |
| 3 | `ANY` | `DIRECTLY_COMPATIBLE` | `helios/composition/primitives.py::_evaluate_any` — at least one holds; non-holding components are not failures |
| 4 | `SEQUENCE` | `COMPILABLE_WITH_VERSIONED_ADAPTER` | `helios/composition/primitives.py::_evaluate_sequence`; `sequence_index` + `ordering_window_seconds`; ordering keyed on `first_matched_at_utc`, inclusive window |
| 5 | `CONTEXT_TRIGGER` | `COMPILABLE_WITH_VERSIONED_ADAPTER` | `helios/composition/primitives.py::_evaluate_context_trigger`; genuinely distinct rule set (§ below), not sugar over `ALL`/`SEQUENCE` |
| 6 | Timeframe/context semantics, multi-timeframe composition | `DARWIN_MODEL_MUST_EXPLICITLY_REPRESENT` | `helios/spec/model.py::InputRequirement` (`role`, `timeframe` pair, per-package, no global map); `docs/CONTRACTS.md` §1.1 |
| 7 | Normalized strategy states | `DIRECTLY_COMPATIBLE` | `helios/contracts/state.py::StrategyState` (7 states) + `LEGAL_TRANSITIONS` table |
| 8 | Reset/expiry/invalidation semantics | `DARWIN_MODEL_MUST_EXPLICITLY_REPRESENT` | `helios/spec/model.py::ExpirySpec` (`NEVER/FRAMES/DURATION`); `docs/COMPOSITION.md` §6, §8; rearm-only-via-`DORMANT` rule |
| 9 | Strategy identity/config contracts | `DIRECTLY_COMPATIBLE` | `helios/contracts/identity.py` (`strategy_id`, `strategy_version`, immutable promoted pair); `definition_fingerprint()` |
| 10 | State outputs consumed downstream | `DIRECTLY_COMPATIBLE` (schema is stable and documented) | `helios/contracts/output.py::StrategyStateEnvelope`; `helios/publish/sink.py` (FILE/STREAM/MEMORY, no socket) |
| 11 | Explicit temporal ordering / windows beyond SEQUENCE | `HELIOS_CURRENTLY_UNSUPPORTED` (for anything beyond the two shipped primitives) | `docs/COMPOSITION.md` §1.1 "no chain of chains"; only `SEQUENCE`'s `ordering_window_seconds` and `CONTEXT_TRIGGER`'s validity check exist — no generic "N bars/minutes between any two arbitrary events" primitive |
| 12 | Multi-timeframe context/trigger behavior, traced example | `DEFER` (behavior is clear; classification depends on whether DARWIN needs *identical* re-evaluation cadence semantics) | `docs/FIXTURES.md` §5.5 vertical-slice table; `fixtures/hsa/handoff/gold_context_trigger.chain.yaml` |

---

## Detailed findings

### 1. Atomic strategy semantics

An atomic strategy in HELIOS is one Python module implementing the `StrategyEvaluator` protocol (`helios/protocols.py`), bound to exactly one declarative `StrategyPackage` of `kind: ATOMIC` via `helios/strategies/registry.py`. Per `docs/ATOMS.md` §1.2, **a package declares exactly one semantic-role input** ("the registry refuses more"). The evaluation is a pure fold: `evaluate(context: EvaluationContext) -> StrategyStateEnvelope`, where `EvaluationContext` carries only `instrument`, `evaluated_at_utc`, `windows` (keyed by role), `parameters`, `freshness_policy`, and `previous` (its own last envelope) — nothing else, which is what makes execution-blindness structural (`docs/CONTRACTS.md` §6).

Six reference atoms exist (`helios/strategies/atoms/*.py`): `golden_cross`, `range_breakout`, `swing_proximity`, `rejection_wick`, `no_wick_candle`, `momentum_volatility`. All are explicitly declared non-production ("None of them is production alpha" — `docs/ATOMS.md` header).

A DARWIN atomic strategy concept maps reasonably naturally onto this ("one condition, one declared timeframe role, one set of typed parameters, one direction, one strength measure") — hence `DIRECTLY_COMPATIBLE` as a *concept*. But actually producing a runnable HELIOS atom from a DARWIN specification would require generating or hand-writing a Python evaluator module (the condition logic itself is not declarative — only its binding metadata is), so at the *code* level this is `COMPILABLE_WITH_VERSIONED_ADAPTER` at best, and for genuinely novel conditions may require new HELIOS-side code (`HELIOS_CURRENTLY_UNSUPPORTED` until a human/FORGE writes the atom). The **package wrapper** (identity, inputs, parameters, direction, timing, persistence, expiry) is fully declarative and directly compatible; the **condition body** is not.

### 2. `ALL`

`helios/composition/primitives.py::_evaluate_all`:
```python
def _evaluate_all(outcomes: Sequence[ComponentOutcome]) -> PrimitiveResult:
    satisfied = all(outcome.satisfied for outcome in outcomes)
```
No ordering, no timing relationship — the package schema itself refuses an `ALL` chain that declares `sequence_index` (`helios/spec/model.py::ChainSpec._primitive_rules_hold`, `else: if indexed: raise StrategySpecError("only a SEQUENCE chain may declare sequence_index", ...)`). This is genuinely just "every component holds," structurally distinct from `ANY` and `SEQUENCE`. `DIRECTLY_COMPATIBLE`.

### 3. `ANY`

`_evaluate_any` — satisfied when at least one component holds; a non-holding component is not a chain failure, only contributes nothing, and its own reason is still published. Chain `strength` (`docs/COMPOSITION.md` §7) is "share of declared components that hold," so `ANY` with 2-of-3 publishes a materially different `strength` (0.6667) than `ANY` with 3-of-3 (1.0). `DIRECTLY_COMPATIBLE`.

### 4. `SEQUENCE`

Real, non-trivial temporal logic (`_evaluate_sequence`):
- Order is established by each component's `first_matched_at_utc` (occurrence start), **not** `last_matched_at_utc` (which keeps advancing while a component stays live) — this distinction matters and is easy for a naive compiler to get wrong.
- Ties (identical match instants across components) are legal — because a 4H close is also a 5M close.
- A **strictly earlier** later-component match instant is what breaks order (`OUT_OF_DECLARED_ORDER`); HELIOS never reorders to make a fit.
- `ordering_window_seconds` is checked **inclusively** across `min`..`max` matched instant, and a lapsed window is reported chain-level (not attributed to any one component).
- Schema-level: `sequence_index` values must be unique and contiguous from 0 (`ChainSpec._primitive_rules_hold`), and a `SEQUENCE` chain *must* declare `ordering_window_seconds` — refused otherwise, no default.

This is real enough (instant-based, tie-tolerant, window-inclusive, chain-vs-component-level reason separation) that a DARWIN-to-HELIOS compiler translating an abstract "ordered composition" concept into this exact semantics is a well-defined, deterministic, testable problem — but it is *not* trivial 1:1 translation. `COMPILABLE_WITH_VERSIONED_ADAPTER`.

### 5. `CONTEXT_TRIGGER`

Genuinely structurally distinct from both `ALL` and `SEQUENCE` — confirmed by reading `_evaluate_context_trigger` in full:

1. exactly one `CONTEXT` and one `TRIGGER` component are guaranteed by the package schema (`ChainSpec._primitive_rules_hold`: `role_names.count(required) != 1` raised for either role);
2. the context's `matched_at_utc` must not be **later than** the trigger's (`CONTEXT_NOT_ESTABLISHED_FIRST`) — simultaneous is fine;
3. if the context publishes its own `valid_until_utc`, the trigger's match instant must not be after it (`CONTEXT_VALIDITY_LAPSED`);
4. **at spec-construction time** (not runtime), if both roles bind to timeframes and `CONTEXT` is *finer* than `TRIGGER`, the engine refuses the chain with `StrategySpecError` — "a context cannot frame something slower than itself." This is a structural, definition-time rule with no `SEQUENCE` equivalent.

So `CONTEXT_TRIGGER` is not literally `SEQUENCE` with two indices and a window: it has its own asymmetric validity-lapse check tied to the *context's own declared expiry*, and its own timeframe-coherence rule enforced at bind time. It does collapse to something *conceptually adjacent* to a 2-component `SEQUENCE` (both use `first_matched_at_utc` ordering and tie-tolerance), but the validity-window check against the context's own `valid_until_utc` and the H-timeframe-coherence check are genuinely CONTEXT_TRIGGER-only rules absent from `SEQUENCE`. `COMPILABLE_WITH_VERSIONED_ADAPTER`.

### 6. Timeframe/context semantics; multi-timeframe composition

**HELIOS composition contains no hardcoded concrete timeframe assignment/value such as H4/M5 or HERMES timeframe-code policy. Timeframe is carried as typed package/input binding data. The composition engine must not own a global role→timeframe mapping.** Confirmed at the code level: `docs/COMPOSITION.md` §1.2 states "Nothing in `helios/composition/` names a timeframe..."; `tests/test_chain_multi_timeframe.py::test_no_timeframe_code_appears_anywhere_in_the_composition_engine` asserts this mechanically by scanning for the exact *value* tokens of every `Timeframe.code`/`hermes_code` and asserting none appear anywhere under `helios/composition/` — this is a check against hardcoded timeframe *values*, not against the `Timeframe` *type* itself (the type is of course referenced, e.g. `composition/engine.py`'s `_role_timeframes: Mapping[str, Timeframe]`, to carry exactly the per-package binding data this invariant requires). The PID's GOLD template (`CONTEXT`→4H, `LOCATION`→1H, `CONFIRMATION`→15M, `TRIGGER`→5M) is *per-package configuration* declared in each package's `inputs` block (`helios/spec/model.py::InputRequirement`, one `(role, timeframe)` binding per input) — never a HELIOS constant.

The engine names exactly two role tokens structurally (`CONTEXT`, `TRIGGER` — required by the `CONTEXT_TRIGGER` primitive itself); `LOCATION` and `CONFIRMATION` are plain data as far as HELIOS is concerned and asserted to appear nowhere in the engine source.

**Implication for DARWIN:** if DARWIN's own Specification model represents timeframe as a global/implicit property (e.g., "this is a daily-timeframe strategy") rather than an explicit per-condition `(semantic_role, timeframe)` binding carried on each atomic condition and each chain component, a future compiler could not recover which HELIOS package `inputs[]` binding to emit. This is why `DARWIN_MODEL_MUST_EXPLICITLY_REPRESENT`: DARWIN must carry an explicit role/timeframe pair per atomic leaf and per chain component, not a single ambient timeframe for the whole strategy.

### 7. Normalized strategy states

Seven states, exactly as the PID names them, adopted verbatim (`helios/contracts/state.py::StrategyState`): `DORMANT, FORMING, MATCHED, ACTIVE, WEAKENING, INVALID, EXPIRED`. The legal transition table (`LEGAL_TRANSITIONS`) is real and enforced everywhere via `helios.contracts.state.transition()` — both atomic evaluation and chain evaluation route every proposed transition through this one table (`docs/COMPOSITION.md` §6 end: "Every published transition is validated against `helios.contracts.state.LEGAL_TRANSITIONS`... so the engine cannot emit a sequence the documented state model forbids"). Key non-obvious rules actually present in code (`helios/contracts/state.py::_transitions`):
- `DORMANT -> MATCHED` is legal (no forced forming phase);
- a live state (`MATCHED/ACTIVE/WEAKENING`) can never fall back to `DORMANT`/`FORMING` — must resolve via `INVALID` or `EXPIRED`;
- `WEAKENING -> ACTIVE` legal, `WEAKENING -> MATCHED` illegal (never re-fires the match edge);
- `INVALID`/`EXPIRED` rearm **only** via `DORMANT`;
- every state can reach `INVALID` (including `DORMANT` and `EXPIRED` — used for evaluation-failure containment, `helios/strategies/evaluation.py`).

This state machine is fully explicit, testable, and directly reusable as a target vocabulary. `DIRECTLY_COMPATIBLE`.

### 8. Reset/expiry/invalidation semantics

Configurable per package, not hardcoded, via `helios/spec/model.py::ExpirySpec` — three modes: `NEVER` (open-ended), `FRAMES` (count of the **finest bound timeframe** — a genuinely non-obvious rule documented in `docs/COMPOSITION.md` §8: "HELIOS counts frames of the finest one, because that is the resolution at which a chain concludes"), `DURATION` (wall-clock seconds from `first_matched_at_utc`). Invalidation is atom/chain-specific logic (e.g. "the averages crossed back" for `golden_cross`, "the close returned inside the level" for `range_breakout`) — not a generic framework rule; each atom declares its own hard-invalidation condition in code.

The rearm-only-via-`DORMANT` rule (§7 above) is itself a form of reset semantics: an occurrence that resolves (`INVALID`/`EXPIRED`) cannot re-match until the underlying condition actually clears and a fresh `DORMANT` cycle begins — this is a subtle, load-bearing behavioral rule (`docs/ATOMS.md` §4.2: "a strategy that is invalidated on one bar cannot publish MATCHED on the next; the earliest is the bar after").

This is exactly the kind of thing DARWIN must capture explicitly: **which** expiry mode, **what value**, and (implicitly) that a DARWIN strategy relying on "instant re-arm on invalidation" is not expressible — HELIOS enforces a mandatory one-cycle-through-DORMANT delay. `DARWIN_MODEL_MUST_EXPLICITLY_REPRESENT`.

### 9. Strategy identity/config contracts

`helios/contracts/identity.py`: `strategy_id` (`^[a-z][a-z0-9_]{2,63}$`), `strategy_version` (strict `major.minor.patch`, no leading zeros, no pre-release suffixes). `ChainId` is a structurally distinct type from `StrategyId`. **A promoted `(strategy_id, strategy_version)` pair is immutable** — `assert_promotion_immutable()` / `assert_version_immutable()` raise if a changed definition reuses a version, and equally if an unchanged definition bumps one, via `definition_fingerprint(package)` — a deterministic hash over declared *behavior* (inputs, parameters, direction, timing, persistence, expiry, chain composition), explicitly excluding `metadata` and the version field itself. There is **no parameter-override facility at runtime** (`docs/ATOMS.md` §2: "A different parameter value is a different definition, and therefore a new version rather than a runtime argument").

This is directly compatible with a DARWIN `StrategyVersion` concept as long as DARWIN also treats a promoted version as immutable-by-content — which appears to be the design intent already. `DIRECTLY_COMPATIBLE`.

### 10. State outputs consumed downstream

One uniform envelope (`helios/contracts/output.py::StrategyStateEnvelope`, schema `helios.strategy_state/1.0.0`) for atomic strategies **and** chains alike. Full field list (all always present, `null` preserved rather than omitted): `schema_version, kind, strategy_id, strategy_version, chain_id, chain_version, instrument, timeframe, semantic_role, state, direction, strength, evidence, explanation, first_matched_at_utc, last_matched_at_utc, active_since_utc, last_evaluated_at_utc, validity{valid_from_utc,valid_until_utc,reason}, components[], inputs[]`.

Destination: **no network, no listening socket, no state service** — `helios/publish/sink.py` explicitly forbids it ("There is no network sink, and no state service... `tests/test_execution_blind` enforces that no module under `helios/` may even import a networking library"). Three sinks only: `FILE` (append JSON Lines, flushed per record), `STREAM` (`STDOUT`/`STDERR`), `MEMORY` (tests/dry-run). A downstream consumer (FALCON) reads a file or a stream — there is no HELIOS API, queue, or Redis integration at all today. This is an important, possibly surprising, finding: **HELIOS publishes nowhere HERMES/Redis-like; it is file/stream-only.**

Schema-version negotiation is strict allow-list based (`docs/INTEGRATION.md` §1.5): a consumer declares the exact set of versions it accepts; anything else is refused before the payload is even parsed — no "same major is fine" leniency. `DIRECTLY_COMPATIBLE` as a target schema for DARWIN to be aware of, though DARWIN itself doesn't produce this envelope (HELIOS does, at runtime) — the relevant point for DARWIN is that its own eventual "expected result" schema should map cleanly onto this if backtested-equivalence checking against real HELIOS runs is ever wanted.

### 11. Explicit temporal ordering beyond SEQUENCE

No generic "event A must occur within N bars/minutes of event B" primitive exists beyond what `SEQUENCE` (`ordering_window_seconds`, order + span across *all* declared components) and `CONTEXT_TRIGGER` (context validity-lapse check, a pairwise not-later-than + not-after-context-expiry check) already provide. There is **no chain-of-chains** and **no arbitrary pairwise temporal-window primitive independent of the two shipped structures** — confirmed by `docs/COMPOSITION.md` §1.1 ("A component must be an `ATOMIC` envelope... Recursive chain-of-chain composition requires explicit architecture authority per the PID, and is refused at both levels") and by the fact that `ChainPrimitive` is a closed 4-member enum (`ALL, ANY, SEQUENCE, CONTEXT_TRIGGER` — `helios/spec/model.py`). A DARWIN strategy requiring e.g. "any of these 3 conditions occurring within a rolling 2-hour window, in no particular order, at most once per condition" has no direct HELIOS primitive today. `HELIOS_CURRENTLY_UNSUPPORTED` for anything beyond the two shipped temporal shapes; the two that do exist are `COMPILABLE_WITH_VERSIONED_ADAPTER` (see #4, #5).

### 12. Multi-timeframe context/trigger behavior — traced example

Traced end-to-end via `docs/FIXTURES.md` §5 (the vertical-slice scenario) and the shipped `gold_context_trigger@1.0.0` package (`fixtures/hsa/handoff/gold_context_trigger.chain.yaml`, `CONTEXT`→H4/`golden_cross`, `TRIGGER`→M5/`range_breakout`, `expiry.mode: DURATION, duration_seconds: 14400`).

Concretely, from the vertical-slice state table (`docs/FIXTURES.md` §5.5), evaluation happens **every 5 minutes** (every M5 bar close + 60s), i.e. HELIOS re-evaluates the *entire chain*, including the H4 context leg, on every 5-minute tick — **not** only once per H4 bar close. The H4 `golden_cross` atom's own state (`DORMANT→MATCHED→ACTIVE...`) only actually *changes* when a new H4 bar closes, but the chain engine still re-reads and re-checks that (unchanged) component state on every M5 evaluation cycle. So: **a coarser-timeframe context does NOT get "frozen" or evaluated once-per-day and cached** — the runtime polls continuously at the finest cadence in the feed (here M5, every 5 min) and simply re-observes whatever the coarser component's *last published envelope* currently says. This is confirmed structurally too: `docs/RUNTIME.md`'s "continuous concurrent evaluation" and `docs/COMPOSITION.md` §1 ("One evaluation is a pure function of (package, component envelopes, evaluation instant, previous chain envelope). The engine holds no state between calls").

The trace itself: context (`golden_cross`) reaches `MATCHED` at 12:01, `ACTIVE` from 13:01 on; trigger (`range_breakout`) reaches `MATCHED` at 14:01 — chain state at 14:01 becomes `MATCHED LONG`, strength `1.0000`. The `CONTEXT_TRIGGER` chain's own `DURATION` expiry (14400s = 4h from `first_matched_at_utc` 14:01) fires `EXPIRED` at 15:06 (per the table) — nothing about the underlying condition broke; time simply ran out on the chain's *own* declared validity window, distinct from the component-level validity of either leg. This demonstrates the timeframe-coherence rule from #5 concretely: `CONTEXT` (H4) is coarser than `TRIGGER` (M5), which is legal; had the package tried to bind `CONTEXT` finer than `TRIGGER` it would have been refused at construction (`StrategySpecError`), never at runtime.

---

## Answers to the required explicit questions

**1. Which semantics DARWIN can model in a form HELIOS could eventually consume directly?**
The state vocabulary (`DORMANT/FORMING/MATCHED/ACTIVE/WEAKENING/INVALID/EXPIRED` + the legal transition table), the identity/versioning model (`strategy_id@strategy_version`, immutable-by-content promotion), the `ALL`/`ANY` composition primitives, and the declarative package "envelope" fields (parameters with typed min/max, direction mode, persistence, per-input freshness override) are all direct, low-friction targets. If DARWIN's Specification model expresses these using the same vocabulary and the same closed enums, no real translation logic is needed beyond serialization format.

**2. Which require a deterministic versioned compiler/adapter?**
`SEQUENCE` and `CONTEXT_TRIGGER` composition (temporal-instant semantics, tie-tolerance, inclusive windows, context-validity-lapse checks, timeframe-coherence bind-time checks) and the atomic-condition *body* itself (DARWIN's condition logic would need to be compiled into, or matched against, an actual Python `StrategyEvaluator` implementation registered in `helios/strategies/registry.py` — packages carry only binding metadata, never executable logic).

**3. Which HELIOS concepts must DARWIN explicitly encode now to avoid future reinterpretation?**
(a) An explicit, per-leaf-condition and per-chain-component `(semantic_role, timeframe)` binding — never an ambient/implicit strategy-level timeframe (§6). (b) Explicit expiry mode + value per strategy/chain (`NEVER`/`FRAMES`/`DURATION`, with `FRAMES` meaning frames of the *finest bound timeframe*) (§8). (c) Explicit direction relationship per chain component (`SAME`/`OPPOSITE`/`ANY`) and package-level `component_relationship`, since these are checked for internal contradiction at bind time. (d) For any `SEQUENCE`-like DARWIN construct: an explicit `sequence_index` per component and an explicit `ordering_window_seconds`. (e) The persistence/`min_matched_frames` concept if DARWIN ever wants to require a condition to hold for N consecutive evaluations before counting as matched — this is a real HELIOS field, not free.

**4. Which valid future DARWIN semantics would currently be unsupported by HELIOS?**
Chain-of-chains / hierarchical composition (structurally refused, `ChainComponent` has no chain field). Any composition primitive beyond the closed four-member enum (e.g. "N-of-M", weighted voting, a generic rolling temporal window across unordered conditions, "NOT" / negation of a component). Runtime parameter overrides (a new parameter value is by definition a new version — there is no "same strategy, different knob" concept at runtime). Multiple semantic-role inputs on one atomic strategy (an atom is capped at exactly one declared input by the registry).

**5. Which normalized HELIOS states or temporal semantics would otherwise be lost if DARWIN's model doesn't capture them?**
The `INVALID` vs `EXPIRED` distinction ("something broke" vs "time simply ran out") — if DARWIN's model only has a binary matched/not-matched, this semantically important distinction (and its differing rearm/latching behavior — both resolve only via `DORMANT`, but a resolved `EXPIRED` occurrence stays expired while its own condition still holds, whereas `INVALID` rearms as soon as the next evaluation runs) is unrecoverable later. Also the `NEUTRAL` vs `NONE` direction distinction (direction-aware-but-currently-unbiased vs not-directional-at-all) — collapsing these loses information a chain's anchor-resolution logic depends on.

**6. Are ATOMIC/ALL/ANY/SEQUENCE/CONTEXT_TRIGGER genuinely semantically distinct in current HELIOS, and exactly how (or where do they collapse into each other)?**
Yes, all five are genuinely distinct in the actual code, not just by name:
- `ATOMIC` is a leaf evaluator with its own condition logic and state machine; `ALL`/`ANY`/`SEQUENCE`/`CONTEXT_TRIGGER` are all pure functions over *already-published* atomic (or, in principle, only-atomic-for-now) envelopes and never touch market facts directly.
- `ALL` vs `ANY`: complementary boolean logic over the same unordered component set, no ordering, no timing — verified in `_evaluate_all`/`_evaluate_any`, ~10 lines each, no shared special-casing.
- `SEQUENCE` vs `ALL`/`ANY`: adds an ordering (`sequence_index`) and a window (`ordering_window_seconds`) neither of the other two can even declare (refused by schema if they try).
- `CONTEXT_TRIGGER` vs `SEQUENCE`: does **not** use `sequence_index` at all (schema forbids it for this primitive); instead uses named roles (`CONTEXT`/`TRIGGER`) with an asymmetric not-later-than check plus a check against the *context's own* declared `valid_until_utc` — a rule `SEQUENCE` has no equivalent of — and a bind-time timeframe-coherence check (context must not be finer than trigger) that no other primitive performs.
None of the four collapses into another; each has code paths, refusal rules, and test files (`tests/test_chain_*.py`) that would fail if collapsed.

**7. How do multi-timeframe context/trigger semantics behave today, concretely?**
See detailed finding #12: evaluation is continuous at the cadence of the fastest timeframe the runtime feed supplies (in the shipped scenario, every 5 minutes); every component — including coarse-timeframe ones — is re-checked on every tick against its own *last-published* envelope, not re-computed from scratch and not cached/frozen for a day. A coarse-timeframe leg's *state* only changes when its own underlying timeframe's bar actually closes and a new atomic evaluation runs and republishes; the chain layer itself has no timeframe-aware caching or throttling — it is handed whatever component envelopes the runtime last produced, at every chain evaluation tick, and reasons purely from their published `state`/`matched_at_utc`/`validity` fields.

---

## Current real HSA<->HELIOS contract (from `test_contract_hsa.py` and `fixtures/hsa`)

This is ground truth for today's actual, working integration surface:

- **Unit of exchange:** a "handoff" — a directory of declarative package files (JSON or YAML), each either `kind: ATOMIC` or `kind: CHAIN`, schema `helios.strategy_package/1.0.0`. Loaded via `helios.integration.hsa_boundary.load_handoff(directory)`.
- **Two-phase acceptance:** (1) each package is validated *individually* on load (schema version, closed key set, known HERMES fact names, parameter range coherence, chain-primitive-specific rules); (2) the **whole handoff is then resolved as a set** — every chain component must reference a package *actually present in the same handoff*, at the *exact* version named. `tests/test_contract_hsa.py::test_every_chain_component_resolves_to_an_atomic_package_that_is_present` and `test_a_missing_component_names_the_chain_that_needed_it` confirm this is enforced, not advisory.
- **No version leniency whatsoever.** `test_a_version_mismatch_says_what_helios_actually_holds`: a chain naming `golden_cross@2.0.0` when the handoff holds only `1.0.0` is refused outright — `"will not substitute a different version"`. This is possibly the single most important thing for a DARWIN architect to internalize: **HELIOS treats an exact-version chain reference as non-negotiable identity, not a dependency range.** Any DARWIN promotion/versioning scheme must produce exact-version-pinned chain definitions, never floating/latest references.
- **No chain-of-chains**, enforced at the handoff-resolution level too (`test_a_chain_naming_another_chain_is_refused`, `"chain-of-chain composition needs explicit architecture authority"`) — refused even though the individual chain package would otherwise parse fine.
- **Everything unresolved is reported in one pass**, not one-at-a-time (`test_every_unresolved_reference_is_reported_at_once`) — a deliberate usability property, but also evidence that HELIOS validates a whole handoff transactionally, not incrementally.
- **Duplicate identity claims are refused** (`test_two_definitions_claiming_one_promoted_version_are_refused`) — two files both claiming `golden_cross@1.0.0` is an error, not "last one wins."
- **A realistic, currently-working example handoff** (`fixtures/hsa/handoff/`) is 4 atomics (`golden_cross`, `range_breakout`, `rejection_wick`, `swing_proximity`) + 2 chains: one `SEQUENCE` (`gold_staged_sequence@1.0.0`, all four GOLD template stages H4/H1/M15/M5) and one `CONTEXT_TRIGGER` (`gold_context_trigger@1.0.0`, H4 context + M5 trigger only, skipping the two middle stages). This proves HELIOS supports chains using *fewer* than all four semantic stages, and that `CONTEXT_TRIGGER` intermediate components (if any) are optional (the PID allows "any intermediate components in declared order" but the shipped example has none).
- **Refusal is precise, not generic**: `tests/test_contract_hsa.py::UNDERSPECIFIED_CASES` shows HELIOS naming the exact offending file and the exact missing concept — e.g. `requires_unpublished_fact.atomic.yaml` fails with the unresolved fact name (`ema_100`) *and* the full list of facts HELIOS does know (`known=[...]`) in structured `context`, which is directly machine-parseable by a future DARWIN-side validator wanting to pre-flight-check a spec before attempting a real HELIOS handoff.
- **What HELIOS reports back on success** (`describe_handoff(bundle)`): the accepted package schema version, every atomic identity string, and per-chain `primitive`, ordered `components` list (canonical order, not declaration order), and `role_timeframes` dict — this is the acknowledgment contract a DARWIN-side "did my compiled output actually get accepted" check would consume.

This handoff-level contract (individual validation → whole-set resolution → exact-version pinning → single-pass error reporting → structured acknowledgment) is the most mature, testable, and directly reusable piece of the entire HELIOS surface for reconciliation against the DARWIN PID — it is real code, not aspirational documentation, and it is exercised by 20+ passing tests in `tests/test_contract_hsa.py` at the inspected commit.
