# HSA Archaeology — PID-004A Reuse Assessment

**HSA commit inspected:** `279ec181b5cd78df953671e087e01b7c1190ff96` (branch `main`, dell-debian `/srv/HSA`), confirmed via `git rev-parse HEAD` immediately before this report was written, and unchanged from the commit named in the brief.

**Inspected:** read-only. No file in `/srv/HSA` was edited, staged, committed, checked out, or otherwise mutated. `git -C /srv/HSA status --porcelain` returned empty both before and after inspection. All work was `cat`/`grep`/`find`/`git rev-parse`/`git status` over SSH to `root@192.168.11.10`.

## Summary table

| # | Concept | Classification | Key evidence |
|---|---|---|---|
| 1 | StrategyCandidate identity | REUSE_WITH_ADAPTATION | `hsa/versioning.py:identity_of()` — identity is always `(strategy_id, strategy_version)`; HSA has **no separate "candidate" identity type** — a candidate is a `strategy_package` document whose `lifecycle.status == "CANDIDATE"`. |
| 2 | StrategyVersion identity | REUSE_WITH_ADAPTATION | Same `identity_of()`; `contracts/common.defs.json#/$defs/strategy_id` + `semver`; one identity model spans the whole lifecycle, distinguished only by `lifecycle.status`, not by a second type. |
| 3 | Immutable version semantics | REUSE | `hsa/versioning.py:refuse_in_place_mutation`, `describe_in_place_mutation`, `PromotedVersionImmutableError` — real diff-based enforcement with captured, tested error text in `docs/VERSIONING.md` §4, not a naming convention. |
| 4 | Ambiguity refusal | REUSE_WITH_ADAPTATION | `hsa/intake/analyser.py` + `hsa/intake/documents.py:build_not_sufficiently_defined` — a genuinely working, deterministic, five-audit-hardened refusal engine, not a stub. |
| 5 | Deterministic decomposition | REIMPLEMENT_FROM_DOCTRINE | No code decomposes a description into atomics/chain. `hsa/intake/documents.py:NOT_YET_SPECIFIED` lists `atomic_strategies`, `chain`, `timeframe_roles`, etc. as fields intake **cannot** supply. Decomposition is a doctrine-guided human/AI step (`docs/HSA-ROLE.md` §4 steps 5-8), not deterministic code. |
| 6 | Atomic conditions | DO_NOT_REUSE | No typed single-condition primitive exists anywhere. `catalogue/atomic/*.json` encode logic as prose (`direction_rule`, `description`) pinned only by `deterministic_test_cases`, e.g. `golden_cross.json`'s `direction_rule`: *"LONG on the bar where ma.fast crosses from at or below ma.slow to above it…"* — a string, not an AST. |
| 7 | Condition typing | DO_NOT_REUSE (with one exception) | No closed operator/condition vocabulary for strategy logic. The one exception: `common.defs.json#/$defs/criterion` has a genuine typed `comparator` enum (`>=,<=,>,<,==,!=`) — but it's used for evidence acceptance/rejection thresholds, not for strategy rule logic. |
| 8 | Timeframe semantics | REUSE | `common.defs.json#/$defs/timeframe` (`^[1-9][0-9]*(M\|H\|D\|W)$`), `#/$defs/timeframe_role` (`CONTEXT/LOCATION/CONFIRMATION/TRIGGER`), `chain.schema.json#/timeframe_roles`, `hsa/semantics.py:_check_context_trigger_timeframes` (CONTEXT must be strictly higher than TRIGGER). Roles are canonical; the timeframe each maps to is per-strategy — enforced, not just documented. |
| 9 | Fixed vs tunable parameters | REUSE_WITH_ADAPTATION | `common.defs.json#/$defs/parameter` — every declared parameter has type, default, units, and exactly one of `allowed_range`/`allowed_values`. But "fixed" is achieved by **omission** (a fixed value simply isn't declared as a parameter) — there's no explicit field marking a value as fixed-by-identity vs tunable. |
| 10 | Tuning/search envelopes | REUSE | `parameter.allowed_range {minimum, maximum, step}` or `allowed_values` (enum). Simple, bounded, mechanically checkable; `oneOf` in the schema forces every parameter to declare one. |
| 11 | Lineage | REUSE_WITH_ADAPTATION | `hsa/versioning.py:derive_candidate`, `lineage()`, `lifecycle.supersedes {strategy_id, strategy_version, rationale}`, `VERSION_LINEAGE` CER reference type. Working code, but reference-type carry-forward rules (`CARRIED_FORWARD_REFERENCE_TYPES` vs `GATE_VERDICT_REFERENCE_TYPES`) are keyed to HSA/CER's own vocabulary. |
| 12 | Validation | REUSE | `hsa/contracts.py:validate_document` (JSON Schema Draft 2020-12, offline `$ref` resolution via a local store) + `hsa/semantics.py` (cross-field `Finding`-based checks). Fully deterministic, dependency-light (`jsonschema` only), no LLM in the loop. |
| 13 | Schema/contracts | REUSE_WITH_ADAPTATION | `contracts/*.schema.json` — real JSON Schema, `additionalProperties: false` everywhere, structural prohibitions by construction (e.g. `atomic_strategy.schema.json` has no property that could name a peer strategy). Discipline is portable; trading-specific vocabulary (HERMES fields, LONG/SHORT, GOLD timeframes) is not. |
| 14 | Unsupported/ambiguous handling | REUSE_WITH_ADAPTATION | `hsa/intake/documents.py:build_draft` / `build_not_sufficiently_defined` — a refusal is a validated, first-class **document**, never an exception (`hsa/intake/errors.py` docstring is explicit about this). No silent guessing found anywhere in the codebase (confirmed by grep, see below). |

## Detailed findings

### 1–2. StrategyCandidate / StrategyVersion identity

HSA does not model "candidate" and "version" as two different identity types. There is exactly one identity pair, `(strategy_id, strategy_version)`, defined once in `contracts/common.defs.json`:

```json
"strategy_id": { "type": "string", "pattern": "^[a-z][a-z0-9_]{2,63}$" }
"semver":      { "type": "string", "pattern": "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$" }
```

`hsa/versioning.py:identity_of()` is the single place that reads this pair off a document, and it refuses to guess: it raises `VersioningError` if either half is missing or malformed. What makes something a "candidate" rather than a "version" is purely `lifecycle.status` (`CANDIDATE | PROMOTED | DORMANT | RETIRED`) on the *same* schema, `contracts/strategy_package.schema.json`. There is no separate, lighter-weight "candidate" document shape — a candidate is a full `strategy_package` with every field the mature contract requires, just not yet gated.

This is a real design decision worth naming for DARWIN's architect explicitly: **HSA chose one schema across the whole lifecycle, distinguished by a status enum, rather than two schemas (a mutable pre-final "candidate" type and a frozen "version" type)**. If DARWIN's model genuinely wants two separate typed objects (`StrategyCandidate` vs `StrategyVersion`), HSA's identity *tuple* (`id` + strict semver) is directly reusable, but the *split into two types* is DARWIN's own design work — HSA offers no code for it, only a single-schema-with-status-field alternative to react to.

### 3. Immutable version semantics — real enforcement, not convention

This is enforced code, not a naming convention. `hsa/versioning.py` distinguishes two questions that are easy to conflate and states why conflating them was a real, closed bug:

- `is_frozen(package)` — may this version's *content* still be edited? (derived from `status_of()` against `IMMUTABLE_STATUSES = (PROMOTED, DORMANT, RETIRED)`)
- `is_promoted(package)` — has this version *actually been through* promotion? (derived from history: some frozen statuses prove it by construction — `DORMANT` is reachable only from `PROMOTED` — others, notably `RETIRED`, prove nothing on their own because `CANDIDATE -> RETIRED` is a legitimate gate-free transition, so a `PROMOTION_EVIDENCE` CER reference anchored to that exact version is required)

`refuse_in_place_mutation()` computes a full structural diff (`_diff`, JSON-path based) between a promoted document and a proposed one, and raises `PromotedVersionImmutableError` naming every changed path with before/after values, unless the only difference is a permitted `lifecycle.status` transition. `docs/VERSIONING.md` §4 captures the literal exception text and a test (`tests/test_criterion_13_inventory.py`) regenerates and asserts it matches, so the documentation cannot drift from the code. This is a mature, tested implementation of "promoted versions are immutable," not a comment saying so.

### 4 & 14. Ambiguity refusal / unsupported-strategy handling

This is the strongest single piece of engineering in the repository, and it is real. The ambiguity boundary itself is a crisp, generalizable test stated in `docs/AMBIGUITY-POLICY.md`:

> Parameterise a term whose **measurement basis is known** but whose **threshold is unset**. Refuse a term whose **measurement basis is itself undefined**.

The engine that applies it (`hsa/intake/analyser.py`, ~1100 lines; `hsa/intake/lexicon.py`; `hsa/intake/documents.py`) is a deterministic, regex/pattern-based scanner over a declarative JSON lexicon (`hsa/intake/lexicon.json`), not an LLM call and not free-form NLP — the module docstring is explicit: *"WHAT THIS IS NOT: an LLM call, or anything that understands English."* Its own history, recorded in the docstrings, is unusually candid: five separate audits found five separate silent paths by which a discretionary phrase like "near resistance" could vanish without a refusal (overlap-vs-coverage confusion, sentence-boundary swallowing, wildcard-slot content, contested matches, re-basing by context) — and the fixes for all five are still present as both code and an explicit runtime invariant: every recognized lexicon match is written into a ledger and `UnreportedMatchError` is raised if a match ever reaches the end of a scan unaccounted for (`hsa/intake/errors.py`).

The refusal itself is a first-class governed **outcome**, not an exception:

```python
# hsa/intake/errors.py
"""Note what is deliberately NOT here: there is no exception for the
STRATEGY_NOT_SUFFICIENTLY_DEFINED outcome. A refusal is a successful,
governed result of intake ... not a failure, so it is returned as a
document rather than raised."""
```

`build_not_sufficiently_defined()` constructs and *validates* the refusal against `contracts/not_sufficiently_defined.schema.json` before returning it — a malformed refusal is treated as worse than no refusal. The schema itself enforces the shape of a *good* refusal: every `unresolved_items[]` entry requires verbatim `source_language`, a `why_unresolved` specific to that phrase, `blocks[]` (which parts of strategy engineering it stops), and `resolution_needed {kind, description, responsible}` naming who must resolve it — and, deliberately, there is no `chosen`/`selected` field on offered `candidate_definitions`, so "here are some options" can never silently become "here is the answer."

**Adaptation needed for DARWIN**: the *lexicon content* (`lexicon.json`) is entirely HSA/trading-domain vocabulary ("large wick," "near resistance," etc.) and is not portable as data. The *engine* (declarative term/marker/qualifier model, coverage-not-overlap suppression rule, ledger invariant) is a strong, domain-agnostic pattern DARWIN could adopt if and only if DARWIN needs to parse free-text rule descriptions at all — if DARWIN's Specification objects are always authored as structured input rather than prose, this ~1500 lines of machinery is not worth porting.

### 5. Deterministic decomposition

No code in HSA takes a raw description and produces atomic strategies or a chain. `hsa/intake/documents.py:NOT_YET_SPECIFIED` is explicit and enumerates exactly what intake cannot supply:

```python
NOT_YET_SPECIFIED: tuple[tuple[str, str], ...] = (
    ("atomic_strategies", "Atomic decomposition of the measurable logic (PID line 133)."),
    ("chain", "Chain composition using ALL / ANY / SEQUENCE / CONTEXT_TRIGGER (PID line 135)."),
    ...
)
```

The module docstring states the reason directly: *"Intake cannot supply those from a raw description without inventing trading logic, which PID lines 39 and 148 forbid."* Decomposition into atomics is described as a doctrine-guided step an HSA session (human or AI) performs by hand, following `docs/HELIOS-STRATEGY-BLUEPRINT.md` §1 (the seven atomicity properties) and `docs/COMPOSITION-DOCTRINE.md` — not something the repository automates. What *is* automated is checking a human-produced decomposition afterward (schema + `hsa/semantics.py`), which is concept #12, not this one.

### 6–7. Atomic conditions / condition typing

There is no typed single-condition model comparable to "RSI < 30" anywhere in HSA. An "atomic strategy" in this codebase is a whole self-contained governed unit (`contracts/atomic_strategy.schema.json`) with `parameters`, `output_contract`, `deterministic_test_cases`, `doctrine_assertions` — considerably heavier than a single comparison. The actual comparison logic is carried as free-text prose fields (`description`, `thesis`, `direction_semantics.direction_rule`) and is *pinned*, not *expressed*, by `deterministic_test_cases` (fixed HERMES facts and their exact expected output). E.g. `catalogue/atomic/golden_cross.json`:

```json
"direction_rule": "LONG on the bar where ma.fast crosses from at or below ma.slow to above it; SHORT on the bar where ma.fast crosses from at or above ma.slow to below it."
```

This is a human/FORGE-readable sentence, not machine-evaluable structure — FORGE (HSA's downstream implementer) is trusted to turn the prose plus the test cases into real code. The one place a genuinely typed, closed comparator vocabulary exists is `common.defs.json#/$defs/criterion` (`metric`, `comparator` enum, `threshold`), but that's used for acceptance/rejection evidence gates, not for expressing the strategy's own trigger/entry logic. **This is a real gap**: DARWIN, if it wants typed atomic conditions as first-class objects, gets no working implementation from HSA to import — only the observation that HSA solved the "how do we know the logic is right" problem via pinned test cases instead of via a typed expression language.

### 8. Timeframe semantics

This is one of HSA's strongest, most portable pieces. Timeframe strings are regex-typed (`^[1-9][0-9]*(M|H|D|W)$`, `common.defs.json`), and — separately — four semantic *roles* are a closed enum (`CONTEXT`, `LOCATION`, `CONFIRMATION`, `TRIGGER`) that are explicitly decoupled from any concrete timeframe: *"The roles are canonical; the timeframe each role maps to is not"* (`docs/HELIOS-STRATEGY-BLUEPRINT.md` §2.2). A chain declares its own `timeframe_roles` mapping (e.g. `{"CONTEXT": "4H", "TRIGGER": "5M"}`), and `hsa/semantics.py:_check_timeframe_roles` / `_check_context_trigger_timeframes` mechanically enforce that (a) every input's declared role/timeframe pair agrees with the chain's own mapping and (b) for the `CONTEXT_TRIGGER` primitive, the `CONTEXT` timeframe is *strictly* higher than the `TRIGGER` timeframe — a real, tested cross-field check, not just a schema-level enum.

### 9–10. Fixed vs tunable parameters / search envelopes

`common.defs.json#/$defs/parameter` requires `name`, `description`, `type`, `default`, `units`, and exactly one of `allowed_range {minimum, maximum, step}` or `allowed_values` (enforced by a schema `oneOf`). Every declared parameter is therefore bounded by construction — this is a clean, directly reusable envelope shape for a first specification-contract phase.

What HSA does **not** have is an explicit "fixed-by-identity" marker. A value that must not vary (e.g. the instrument list, or a hardcoded constant baked into `description`/`direction_rule` prose) is simply never declared in the `parameters` array — fixed-ness is achieved by omission, not by a field that says `tunable: false`. For DARWIN's stated need to *distinguish* fixed-by-identity parameters from tunable ones inside one typed object, HSA's schema would need an added discriminator; the bounded-range/enum shape itself needs no change.

### 11. Lineage

Real, working code: `hsa/versioning.py:derive_candidate()` produces a new candidate document (never mutates its input — `copy.deepcopy` throughout), bumps semver, sets `lifecycle.supersedes {strategy_id, strategy_version, rationale}` (rationale is mandatory — refused if blank), and selectively carries forward CER references:

```python
CARRIED_FORWARD_REFERENCE_TYPES = ("SOURCE_ANALYSIS", "STRATEGY_HYPOTHESIS", "RESEARCH_FINDING", "VERSION_LINEAGE")
GATE_VERDICT_REFERENCE_TYPES   = ("PROMOTION_EVIDENCE", "REVISION_EVIDENCE", "REJECTION_EVIDENCE")
```

— provenance/hypothesis references survive onto a new candidate; gate *verdicts* never do, because PID doctrine requires a candidate to "pass the governed evidence gates again," and carrying a parent's promotion evidence forward would let a modification inherit an approval it never earned. `lineage()` orders a strategy's packages by semver and reports each version's status/supersession/rationale. The algorithm shape (candidate derivation with mandatory rationale; asymmetric evidence carry-forward; refusing to derive from a version that was never actually promoted, checked via reachability in the status-transition graph rather than the current status alone) is a mature pattern worth porting; the specific `reference_type` vocabulary is HSA/CER-specific and would need renaming to DARWIN's own evidence taxonomy.

### 12. Validation

Two independent, composable layers, both fully deterministic:

1. **Structural** — `hsa/contracts.py:validate_document()`, built on `jsonschema`'s `Draft202012Validator`. Every schema in `contracts/` is loaded into one local store keyed by `$id` and handed to a `RefResolver`, so cross-file `$ref`s resolve **entirely offline** — no network fetch, ever. `detect_kind()` reads the `$hsa_kind` discriminator and explicitly refuses to guess a kind (`MissingDiscriminatorError`) rather than trying schemas until one fits.
2. **Semantic** — `hsa/semantics.py`, a library of cross-field checks (package/chain agreement, HERMES-field coverage, reason-field attribution, `SEQUENCE` index contiguity, `CONTEXT_TRIGGER` role-exclusivity) that JSON Schema structurally cannot express. Findings share the exact same `{path, message, schema_path}` shape as structural failures (`Finding.as_failure()`), so a caller never branches on which kind of problem it hit.

Both are cheaply portable: the only runtime dependency is `jsonschema` (per `README.md`/`PID.md` explicit "keep the implementation lightweight" rule), and neither module has any HSA-specific side effects — they operate purely on the document passed in plus an optional catalogue.

### 13. Schema/contracts

`contracts/` is real, disciplined JSON Schema (Draft 2020-12), not prose dressed as schema: `atomic_strategy.schema.json`, `chain.schema.json`, `strategy_package.schema.json`, `cer_reference.schema.json`, `not_sufficiently_defined.schema.json`, plus shared `common.defs.json`. Every object sets `additionalProperties: false`. The most notable technique — worth naming for DARWIN explicitly — is **structural prohibition by omission**: `atomic_strategy.schema.json`'s own description states it deliberately, *"there is no `depends_on`, no `requires_strategy`, no `inputs`, no `components`... The only `strategy_id` in an atomic document is the document's OWN identity."* Combined with `additionalProperties: false`, this makes an atomic strategy unable to acquire a dependency on a peer *even by accident* — enforced by the shape of the document, not by review discipline. `chain.schema.json` uses the same technique to make chain-of-chain recursion structurally unrepresentable (no self-`$ref`, no `chain_id` inside an `atomic_input`), rather than merely discouraged by convention.

Note the schema set's own honesty about the limits of this technique: `docs/COMPOSITION-DOCTRINE.md` §1 records that the open `deterministic_test_cases` objects *can* still smuggle a planted peer `strategy_id` past the schema, and the actual closure is a full-document walk in `tests/test_catalogue.py::test_entry_references_no_other_strategy` — i.e., schema-level prohibition-by-omission is necessary but was explicitly proven insufficient on its own, and the gap was closed by a test, not by tightening the schema further. That is a valuable, transferable lesson about the limits of "no such field exists" as an enforcement strategy.

### Confirmed: no arbitrary code execution anywhere

Per the task's explicit instruction to flag this loudly if found: `grep -rnE 'eval\(|exec\(|subprocess|os\.system|__import__' /srv/HSA/hsa /srv/HSA/tests` found **no** `eval`/`exec`/`os.system`/`__import__` anywhere in the codebase. The only `subprocess` usages are in the test suite (`tests/test_cli.py`, `tests/test_semantic_cli.py`, `tests/test_acceptance_example_b.py`, `tests/test_boot.py`), and all of them invoke HSA's own `hsa` CLI as a black box to test its process-level behaviour (exit codes, stdout), not to execute strategy logic. Strategy "logic" in HSA is never executed at all — it is represented as prose plus pinned test cases and handed to FORGE for implementation elsewhere. This is a clean, honest negative finding: HSA gives DARWIN nothing to be worried about on this front.

## Doctrine worth preserving

- **The parameterise/refuse boundary test**: *"can the quantity be named without choosing between constructions that disagree on real data? If yes, parameterise. If no, refuse."* (`docs/AMBIGUITY-POLICY.md`) — a crisp, domain-general test for any system that must decide when a rule is "sufficiently defined," independent of HSA's specific trading vocabulary.
- **A refusal is a governed, successful outcome — never an exception.** Modelling "I can't fully specify this" as a validated document rather than an error is a strong pattern for any typed, machine-consumable contract system that must sometimes say "not yet."
- **Two different questions, not one**: "may this be edited?" (`is_frozen`, derived from current status) vs. "was this actually gated?" (`is_promoted`, derived from *history*, because some statuses are reachable without ever passing a gate). Conflating them was a real, closed defect in HSA's own history — worth remembering as a specific trap, not just an abstract warning.
- **Semantic roles are canonical; the concrete mapping is not.** Decoupling a role vocabulary (`CONTEXT`/`TRIGGER`/etc.) from any specific timeframe/value keeps a specification portable across instruments and strategies without hard-coding an example into doctrine.
- **"As applicable" read narrowly**: every field in the governed contract is `required`; "as applicable" is honoured by allowing *structurally empty* content, never by allowing the field to be *absent* — because a missing section is indistinguishable from an overlooked one. Directly applicable to any "complete specification" contract DARWIN designs.
- **Structural prohibition by omission, with its limits stated honestly.** Removing the only field that could express a forbidden relationship is strong, cheap, and provably necessary — but not provably sufficient on its own; open/free-form sub-objects need an explicit walking test as well.
- **The evidence "seam" pattern**: one function (`open_evidence_reader()`) is the entire boundary between "evidence system is not live yet" and "evidence system is live," with an explicit list of the only three things that change when it goes live, and an explicit, tested guarantee that the not-yet-live adapter has no write path at all. Reusable as a general pattern for any DARWIN dependency (e.g. a not-yet-live backtest/evidence authority) that isn't ready yet.
- **A candidate must earn its own gate; it does not inherit a parent's verdict, but it does inherit the parent's provenance/hypothesis.** The asymmetric carry-forward rule (provenance survives, verdicts don't) is a specific, well-reasoned answer to "what does a new version keep from the old one," worth adopting even without the code.

## Implementation worth reusing

- `hsa/contracts.py` — `validate_document()`, `detect_kind()`, and the offline multi-file `$ref` resolution pattern (local store keyed by `$id`, no network fetch ever). Small, dependency-light (`jsonschema` only), directly adaptable to DARWIN's own kinds/schemas.
- `hsa/semantics.py` — the `Finding` dataclass and `check_document`/`check_chain`/`check_package` dispatch pattern for cross-field checks JSON Schema cannot express, sharing one failure shape with structural errors.
- `hsa/versioning.py` — `derive_candidate`, `refuse_in_place_mutation`/`describe_in_place_mutation`, the `is_frozen`/`is_promoted` split, and the `_statuses_reachable_without_promotion()` technique of deriving a promotion-proof status set from the transition graph rather than hand-maintaining it.
- `contracts/common.defs.json`'s generic definitions — `utc_timestamp`, `semver`, `non_empty_string`, `provenance`, `parameter` (bounded range/enum), `criterion` (typed comparator) — these are domain-agnostic building blocks, close to verbatim-portable.
- The ambiguity-analyser's *engine* pattern (declarative lexicon data + deterministic scanner + a runtime "every recognized match must be accounted for" invariant that raises loudly on a new silent path) — **only** if DARWIN needs to ingest free-text rule descriptions; not worth porting for a purely structured-input specification pipeline.

## Implementation that should NOT be imported into DARWIN

- `hsa/intake/lexicon.json` and its GOLD/wick/breakout-specific term set — entirely HSA-domain vocabulary; would need to be authored from scratch for DARWIN's own domain even if the engine around it were reused.
- The GOLD-specific `4H/1H/15M/5M` example mapping in `docs/HELIOS-STRATEGY-BLUEPRINT.md` §2 — explicitly labelled by HSA's own doctrine as "a hypothesis structure to be empirically validated, not doctrine that guarantees edge" (PID line 97). Should not be carried into DARWIN as if it were a canonical default.
- `contracts/fixtures/cer/*` — placeholder evidence documents standing in for a CER system that is not live. These are contract-shape proof only ("no evidence claim anywhere in this repository has been checked against reality" — `docs/CER-CONTRACT.md` §5); importing them into DARWIN would import fake data that could be mistaken for real evidence.
- The ~1,100-line `hsa/intake/analyser.py` machinery wholesale, if DARWIN does not actually need free-text intake. It is well-built for what it does but is a large amount of hardened, subtle regex/sentence-boundary logic to inherit and maintain for a capability DARWIN may not need in a first specification-contract phase.

## Gaps DARWIN must solve itself

- **No typed atomic-condition/expression model.** HSA never represents "RSI < 30"-style logic as structured data — only as prose pinned by test cases. If DARWIN's Specification objects must be machine-evaluable (not just machine-validated-for-shape), this is entirely new design work; HSA's `criterion` def (metric/comparator/threshold) is the only close analogue, and it's scoped to evidence gates, not to entry/exit logic.
- **No automated decomposition.** Turning a raw idea into atomics + a chain is explicitly left to a human/AI following doctrine (`docs/HSA-ROLE.md`, `docs/HELIOS-STRATEGY-BLUEPRINT.md`), not to code. If DARWIN wants any deterministic decomposition assistance, HSA provides doctrine to follow, not an algorithm to call.
- **No explicit fixed-vs-tunable discriminator field.** HSA achieves "fixed" only by *not* declaring something as a parameter; DARWIN's stated need for a first-class distinction between identity-fixed and tunable parameters requires a new field, not an existing one.
- **No StrategyCandidate/StrategyVersion type split.** HSA uses one schema plus a status enum across the whole lifecycle. If DARWIN genuinely wants two separate typed objects, that split has to be designed from scratch; HSA offers the single-schema alternative as something to explicitly diverge from, not something to extend.
- **No richer parameter search-space model.** Only bounded numeric ranges (with optional step) or closed enumerations — no distributions, priors, or conditional/interacting parameter spaces. Fine for a first phase; DARWIN should not assume it needs nothing more later.
- **No live evidence backend, anywhere in the ecosystem as inspected.** CER is fixture-only in HSA; DARWIN will face the identical "what does a live evidence/backtest authority actually look like" problem HSA has deliberately deferred (correctly, per its own PID's non-goals) rather than solved.
- **No arbitrary-execution risk found** (confirmed by grep — see above) — stated here as a gap-check that came back clean, not as something DARWIN needs to solve. Good news, not a finding to act on.

## Cross-reference note for the HELIOS archaeology pass

`docs/HELIOS-STRATEGY-BLUEPRINT.md` §4 draws the path a governed HSA package takes to reach HELIOS explicitly as:

```
source idea -> HSA -> governed specification -> FORGE -> HELIOS
                                                   ^
                                          (builds)  (runs it)
```

Points worth reconciling against whatever the independent HELIOS-side archaeology finds, stated only as things to check, not as conclusions about HELIOS itself:

- **HSA's output never reaches HELIOS directly.** The strategy_package JSON document is consumed by **FORGE**, a separate implementer, which is trusted to turn HSA's prose-plus-test-cases (`direction_rule`, `description`, `deterministic_test_cases`) into whatever HELIOS actually runs. HSA's own doctrine states the acceptance bar for this handoff explicitly: *"could a competent engineer who knows no trading implement exactly this, with no decision left to them?"* (§3.1). Worth checking on the HELIOS side: does HELIOS (or FORGE's actual output) have **any** artifact that still carries `strategy_id` + `strategy_version`, `reason_field`, or the `signal_type: BOOLEAN|STATE|SCORE` distinction — or does that vocabulary stop at FORGE and never reach HELIOS's own internal representation at all?
- **HSA explicitly forbids embedding runtime/account/broker state into what reaches HELIOS** (§4.2, PID line 156). Worth checking: does HELIOS's actual strategy-runtime interface have any notion of account/broker state leaking into what a "strategy" is allowed to know, which would mean the HSA-side doctrine and the HELIOS-side reality have already diverged?
- **The return path is doctrine, not observed behaviour from this side**: *"if implementation exposes ambiguity, the strategy returns to HSA rather than FORGE guessing"* (§4.3) — this is HSA's stated expectation of FORGE/HELIOS's behaviour, not something HSA's own code enforces or can enforce (HSA has no visibility into FORGE or HELIOS at all). Worth checking whether anything on the HELIOS/FORGE side actually implements a "send it back rather than guess" path, or whether that guarantee currently exists only as HSA-side aspiration.
- **The multi-timeframe role model (`CONTEXT/LOCATION/CONFIRMATION/TRIGGER`) and the four composition primitives (`ALL/ANY/SEQUENCE/CONTEXT_TRIGGER`) are HSA/specification-side vocabulary.** Worth checking whether HELIOS's actual runtime strategy engine has matching (or differently-named, or absent) concepts for timeframe roles and composition — if HELIOS has its own, differently-shaped composition model, that is a real semantic-portability gap between the two systems that DARWIN's architect will want reconciled explicitly rather than assumed away.
- **Evidence/CER identities are named in the strategy_package (`cer_references`) but CER is not live anywhere in this ecosystem as inspected.** If the HELIOS-side archaeology finds any actual evidence/backtest recording mechanism in HELIOS or FORGE, it is worth checking whether it lines up with CER's stated identity model (`strategy_id`/`strategy_version`/`experiment_id`/`run_id`/`evidence_id`/`artifact_id`) or is a wholly separate, unreconciled evidence path.
