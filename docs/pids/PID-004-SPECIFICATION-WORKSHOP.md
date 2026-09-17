# PID-004 — STRATEGY SPECIFICATION + WORKSHOP

**Product:** DARWIN
**Repository:** `github.com/maff0000/DARWIN`
**Canonical starting point:** `39401321a52155357b096d708291233e326507ec`
**Owner:** THE GOAL / DARWIN Architect
**Delivery controller:** ROGUE
**Implementation:** FORGE under bounded work packages
**Infrastructure:** HELM where required
**Status:** REVISED DRAFT FOR FINAL ARCHITECT ACCEPTANCE — NOT AUTHORISED FOR IMPLEMENTATION
**Date:** 2026-09-17

---

# 0. AMENDMENT MATRIX

| Architect ruling                                   | PID-004 incorporation                                                                                                                                                                                                   |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. DARWIN → HELIOS semantic portability            | §§5A, 8A, 39A, 41A. Final StrategyVersion is canonical deterministic strategy semantic artifact; promotion must use same semantics or deterministic versioned compiler/adapter; HELIOS archaeology added.               |
| 2. Policy identity separation                      | §§5B, 17–20, 38. Explicit separation of StrategyVersion, ExecutionPolicyVersion, DIKEPolicyVersion, SizingPolicyVersion and NewsContextPolicyVersion; strategy-intrinsic exits distinguished from independent policies. |
| 3. Fingerprint separation                          | §38. `semantic_fingerprint` separated from `artifact_record_fingerprint`; provenance may differ while deterministic semantics remain identical.                                                                         |
| 4. Causal external/context fact semantics          | §§24A, 25A, 31A, 42. Event/publication/observation/effective timestamps and revisions represented; no hindsight leakage.                                                                                                |
| 5. Canonical fact vs derived fact                  | §§9A, 24, 25, 38. Explicit `CANONICAL_FACT_REFERENCE` vs `SPECIFICATION_DERIVED_FACT`; derived semantics bind algorithm/version/input/timeframe/warm-up/units.                                                          |
| 6. HELIOS composition/state compatibility fixtures | §§8A, 41A. Controlled compatibility fixtures for atomic, ALL, ANY, SEQUENCE, CONTEXT_TRIGGER and multi-timeframe context/trigger semantics.                                                                             |

Everything else in the previously reviewed PID is preserved unless explicitly refined below.

---

# 1. PURPOSE

PID-004 establishes the semantic keystone of DARWIN:

> a rigorous, instrument-generic, machine-readable Strategy Specification from which deterministic research can be performed without ATHENA, APOLLO or future HELIOS promotion interpreting prose or inventing missing trading semantics.

PID-004 then builds Strategy Workshop as the human/AI authoring experience for creating and refining that specification.

Canonical product flow:

```text
SCOUT
→ Discovery
→ Strategy Workshop
→ Specification
→ StrategyVersion
→ ATHENA
→ APOLLO
```

The architectural authority relationship is:

```text
Specification = authoritative semantic contract

Workshop = authoring/reasoning interface over that contract
```

The Workshop must conform to the Specification.

The Specification must never be shaped around limitations of the Workshop UI or Claude Code integration.

---

# 2. TWO INTERNAL ACCEPTANCE GATES

PID-004 is one product increment with two strictly ordered internal gates.

## PID-004A — SPECIFICATION CONTRACT

Establish and prove:

* canonical specification domain;
* machine-readable schema/contracts;
* deterministic rule representation;
* semantic portability toward HELIOS;
* provenance semantics;
* parameter/search-envelope semantics;
* independent policy compatibility semantics;
* data-requirement model;
* data-readiness assessment;
* canonical-vs-derived fact semantics;
* causal context/event semantics;
* validation;
* ambiguity refusal;
* StrategyVersion finalisation and immutability;
* real-SCOUT-candidate conformance;
* HSA archaeology/reuse assessment;
* HELIOS semantic-compatibility archaeology.

PID-004B may not begin until central architecture explicitly accepts PID-004A.

Expected internal gate verdict:

`GREEN_DARWIN_PID004A_SPECIFICATION_CONTRACT_ACCEPTED`

---

## PID-004B — STRATEGY WORKSHOP

Only after PID-004A is accepted:

* build ARENA Strategy Workshop;
* implement bounded Workshop workspaces;
* integrate the Claude Code specialist, working name `MENDEL`;
* persist material decision trails;
* author/refine SpecificationDraft documents;
* validate drafts against PID-004A;
* explicitly finalise immutable StrategyVersions.

Expected internal gate verdict:

`GREEN_DARWIN_PID004B_STRATEGY_WORKSHOP_ACCEPTED`

PID-004 as a whole closes only after both gates are accepted, merged and deployed.

---

# 3. NON-NEGOTIABLE AXIOM

ATHENA, APOLLO and future deterministic promotion consumers consume explicit semantics.

They must never need to answer questions such as:

* “What does the author probably mean?”
* “Does breakout mean wick or close?”
* “Which timezone did they mean?”
* “Is this parameter fixed or optimisable?”
* “How long after event A may event B occur?”
* “Does this strategy trade both directions?”
* “What happens if SL and TP touch in the same candle?”
* “Which data source should supply this fact?”
* “Can we assume this missing field is zero?”
* “Should we substitute another source because the required one is unavailable?”
* “How should HELIOS reinterpret this strategy?”
* “Which indicator formula did DARWIN intend?”

If such interpretation is required, the Specification is not ready.

When semantic ambiguity remains:

`STRATEGY_NOT_SUFFICIENTLY_DEFINED`

DARWIN does not guess.

---

# 4. STRATEGY IDENTITY MODEL

PID-004 must preserve:

```text
SourceStrategyIdentity
≠ Discovery
≠ StrategyCandidate
≠ SpecificationDraft
≠ StrategyVersion
≠ ResearchRun
```

## 4.1 Discovery

A SCOUT-originated idea with provenance.

Lifecycle:

`DISCOVERED`

No deterministic semantics implied.

## 4.2 StrategyCandidate

The durable DARWIN research identity around which one or more semantic versions may be created.

A candidate may originate from:

* one SCOUT discovery;
* a `MY_IDEA` discovery;
* a later combination/derivation of candidates;
* another governed source.

Candidate lineage must be explicit.

A candidate is not itself evidence.

## 4.3 SpecificationDraft

Mutable authoring object.

May contain:

* unresolved questions;
* incomplete semantics;
* proposed rules;
* rejected alternatives;
* provisional parameter ranges;
* unavailable-data requirements.

A SpecificationDraft is not eligible for ATHENA.

## 4.4 StrategyVersion

Created only through explicit successful finalisation of a SpecificationDraft.

A StrategyVersion is:

* immutable;
* machine-readable;
* provenance-linked;
* deterministically validated;
* semantically complete;
* assigned a deterministic semantic fingerprint;
* assigned a separately useful artifact/record fingerprint.

Changing fixed strategy semantics creates a new StrategyVersion.

Never mutate an evidenced StrategyVersion in place.

---

# 5. STRATEGYVERSION IS NOT AN INSTRUMENT TEST

Preserve Amendments A-001/A-004R1.

StrategyVersion remains independent from:

* broker;
* account;
* trader;
* TRON instance;
* host;
* venue;
* NEO;
* SOCRATES;
* a particular ResearchRun.

It must also not automatically become synonymous with one tested instrument.

A Strategy Specification declares its **instrument applicability semantics**.

A ResearchRun later binds the exact experiment configuration.

---

# 5A. CANONICAL DARWIN → HELIOS SEMANTIC PORTABILITY

A final DARWIN StrategyVersion is the:

> **canonical deterministic strategy semantic artifact.**

Future HELIOS promotion must not require a human to independently reinterpret or rewrite the strategy.

Promotion must eventually use one of two governed mechanisms:

1. HELIOS consumes the same canonical deterministic semantic representation directly; or
2. a deterministic, versioned, tested compiler/adapter transforms the DARWIN semantic artifact into a HELIOS-compatible artifact while proving semantic equivalence.

The compiler/adapter, if required, must have:

* explicit version identity;
* deterministic transformation;
* contract tests;
* semantic-equivalence fixtures;
* failure on unsupported semantics;
* no “best effort” reinterpretation.

Unsupported semantics must later fail promotion explicitly.

Example conceptual failure:

`HELIOS_UNSUPPORTED_STRATEGY_SEMANTICS`

or equivalent.

DARWIN must not weaken or alter the StrategyVersion merely to fit a narrower future HELIOS implementation.

Likewise HELIOS must not silently approximate a DARWIN strategy.

This portability requirement concerns **strategy semantics only**.

It does not make HELIOS aware of:

* execution policy;
* sizing;
* DIKE;
* capital;
* broker/account state.

Those remain separately governed.

---

# 5B. POLICY IDENTITY SEPARATION

Preserve the identity separation:

```text
StrategyVersion
!= ExecutionPolicyVersion
!= DIKEPolicyVersion
!= SizingPolicyVersion
!= NewsContextPolicyVersion
```

A Strategy Specification may declare:

* policy compatibility requirements;
* whether a policy class is REQUIRED / PERMITTED / DISABLED / IRRELEVANT;
* authorised ATHENA search envelopes;
* constraints which a compatible policy must satisfy.

The exact frozen policy selected for a ResearchRun belongs to the experiment configuration.

Conceptually:

```text
ResearchRun
=
StrategyVersion
+ InstrumentDefinition
+ MarketDataset
+ ParameterSetVersion
+ ExecutionPolicyVersion
+ DIKEPolicyVersion
+ SizingPolicyVersion
+ NewsContextPolicyVersion
+ other governed run identities where applicable
```

A change to `DIKEPolicyVersion` must not require a new StrategyVersion merely because capital policy changed.

A change to `ExecutionPolicyVersion` must not silently mutate StrategyVersion.

A change to sizing must not create a different strategy hypothesis unless sizing is genuinely intrinsic to the strategy semantics themselves.

A future deterministic `NewsContextPolicyVersion` is reserved explicitly.

ARES supplies governed contextual facts.

News/context policy decides how those facts may participate in an experiment.

NEO remains retrospective:

> `NEO feeds back, not in.`

NEO may propose future research hypotheses but does not inject adaptive live semantics into the deterministic StrategyVersion.

---

# 6. MACHINE-READABLE CONTRACT

PID-004A shall create a canonical versioned Strategy Specification schema.

Use a structured contract, not free-form prose.

JSON-compatible representation is preferred because it supports:

* schema validation;
* deterministic hashing;
* readable evidence;
* Workshop authoring;
* API transfer;
* deterministic compiler/adapters.

Prose may accompany the contract for human explanation but is never executable strategy semantics.

---

# 7. NO ARBITRARY EXECUTABLE STRATEGY CODE

The canonical Specification must not consist of arbitrary:

* Python;
* JavaScript;
* Pine Script;
* shell;
* dynamically evaluated expressions;
* source-supplied executable code.

Source code discovered by SCOUT remains inert provenance material.

PID-004 uses a typed declarative strategy model.

The model may evolve through governed operators/fact types, but must never require executing untrusted source code.

---

# 8. TYPED STRATEGY EXPRESSION MODEL

PID-004A should define a typed declarative expression structure capable of representing strategy conditions without embedding a general-purpose programming language.

Conceptually support nodes such as:

```text
Literal
CanonicalFactReference
DerivedFactReference
ParameterReference
ArithmeticExpression
Comparison
BooleanExpression
TemporalPredicate
SessionPredicate
EventPredicate
CompositionExpression
```

and governed operators such as:

```text
AND
OR
NOT

EQ
NE
GT
GTE
LT
LTE

ADD
SUBTRACT
MULTIPLY
DIVIDE

CROSSES_ABOVE
CROSSES_BELOW

CHANGED_BY
PERCENT_CHANGE

WITHIN_N_BARS
FOR_N_CONSECUTIVE_BARS
SINCE_EVENT
BEFORE_EVENT
AFTER_EVENT

IN_SESSION
ON_DAY
```

Every supported operator must have:

* canonical identifier;
* typed operands;
* deterministic semantics;
* validation rules;
* defined handling of missing input;
* tests.

Unknown operators fail validation.

No silent fallback.

---

# 8A. HELIOS COMPOSITION / TEMPORAL COMPATIBILITY

The Specification model must be capable of representing directly, or compiling deterministically into, representative existing HELIOS semantics including:

```text
ATOMIC
ALL
ANY
SEQUENCE
CONTEXT_TRIGGER
```

The contract must preserve enough explicit state/temporal information that future promotion does not require promotion-time interpretation.

For example, `SEQUENCE` must not be reduced to a timeless `AND`.

Likewise `CONTEXT_TRIGGER` must preserve the distinction between:

* context becoming valid;
* trigger occurring;
* ordering;
* validity lifetime;
* reset/invalidation semantics where HELIOS requires them.

Multi-timeframe context/trigger relationships must be explicit.

If HELIOS normalized strategy-state semantics require additional representation such as:

* inactive;
* context-ready;
* armed;
* triggered;
* invalidated;
* expired;

or equivalent state-machine semantics, PID-004A must record those requirements deliberately.

Do not defer them as an undocumented promotion concern.

PID-004A does not implement HELIOS.

It proves contract compatibility.

---

# 9. DERIVED MARKET FACTS / INDICATORS

Indicators and other deterministic derived facts must be explicit.

Examples include:

```text
SMA
EMA
ATR
RSI
highest
lowest
range
returns
volatility
```

where implemented.

An indicator reference must preserve:

* input fact;
* timeframe role;
* algorithm identifier;
* algorithm version where relevant;
* parameters;
* warm-up requirement;
* output units.

Do not accept ambiguous names such as:

`ATR = 14`

without defining exact input/timeframe/formula semantics.

PID-004A does not need every indicator ever invented.

It needs:

1. a governed extension model;
2. representative primitives sufficient to prove architecture.

Unsupported but fully specified semantics fail explicitly rather than being approximated.

---

# 9A. CANONICAL FACT VS SPECIFICATION-DERIVED FACT

DARWIN must distinguish:

```text
CANONICAL_FACT_REFERENCE
```

from:

```text
SPECIFICATION_DERIVED_FACT
```

A canonical fact reference points to facts owned by a governed authority.

Examples:

* HERMES OHLCV;
* ARES governed event/context fact;
* future options-chain authority.

A specification-derived fact is a deterministic transformation performed for research semantics.

A `SPECIFICATION_DERIVED_FACT` must bind:

* source/input fact reference(s);
* algorithm identifier;
* algorithm version;
* exact parameters;
* timeframe/resolution;
* warm-up;
* output unit/type;
* missing-input behaviour.

A derived value must never masquerade as a HERMES canonical fact.

HERMES remains canonical market-history authority.

DARWIN may derive research facts from HERMES data, but those facts remain DARWIN-derived semantics.

Future HELIOS/live promotion must prove that equivalent deterministic derived semantics are available live.

No formula drift is permitted between:

```text
DARWIN research
```

and:

```text
future deterministic live evaluation
```

If a future live system implements ATR/EMA/etc differently, equivalence must fail rather than silently diverge.

---

# 10. SPECIFICATION TOP-LEVEL SEMANTICS

A final Specification must be able to represent, where applicable:

## Identity

* candidate ID;
* specification schema version;
* StrategyVersion ID after finalisation;
* parent/derived candidate references;
* semantic fingerprint;
* artifact/record fingerprint.

## Human context

* title;
* thesis;
* mechanism/hypothesis.

The thesis explains the strategy but does not substitute for deterministic rules.

## Provenance

* linked SCOUT discovery/discoveries;
* source material references;
* source strategy identity;
* material Workshop decisions.

## Applicability

* instrument applicability;
* direction applicability;
* required market-unit semantics;
* other applicability constraints.

## Timeframe roles

Named roles such as:

* context;
* signal;
* entry;
* management;
* confirmation.

No implicit “main timeframe”.

## Required facts

* canonical market facts;
* specification-derived facts;
* external/context facts;
* authority requirements.

## Trading semantics

* entry;
* no-entry;
* direction;
* invalidation;
* exits;
* temporal/composition semantics;
* session/day restrictions.

## Parameters

* fixed;
* tunable;
* type;
* unit;
* allowed domain.

## Search authority

* ATHENA-authorised parameter envelopes;
* execution-policy search authority;
* DIKE-policy search authority;
* sizing-policy compatibility/search authority where later governed;
* NewsContextPolicy compatibility/search authority where later governed.

## Time semantics

* timezone;
* DST rule;
* session resolution into UTC.

## Intrabar semantics

* wick/close semantics;
* price-touch behaviour;
* ambiguity handling.

## Data requirements

Exact historical evidence required for testing.

## Validation contract

Deterministic conditions required before finalisation.

---

# 11. INSTRUMENT APPLICABILITY

Do not force every StrategyVersion to hardcode `XAU_USD`.

Support:

### Explicit instrument applicability

Example:

```text
XAU_USD only
```

### Explicit instrument set

Example:

```text
XAU_USD
XAG_USD
```

### Instrument-generic applicability

Where genuinely semantic:

```text
any instrument satisfying explicitly declared market/unit/fact capabilities
```

Instrument-generic does not mean “all tickers probably work”.

Applicability criteria must be explicit.

No instrument may be inferred by parsing source ticker text.

---

# 12. TIMEFRAME ROLES

Multiple-timeframe strategies must be first-class.

Represent roles, not merely an unordered timeframe list.

Example:

```text
context_timeframe = H4
signal_timeframe  = H1
entry_timeframe   = M15
```

Rules reference roles explicitly.

A strategy using one timeframe need not declare unused roles.

Cross-timeframe alignment semantics must be deterministic and causal.

No look-ahead.

---

# 13. SESSION / TIMEZONE / DST

If session semantics affect strategy behaviour, declare them explicitly.

Examples:

* IANA timezone;
* local start/end;
* DST handling;
* weekdays;
* holiday/session exceptions where required;
* session-cross-midnight semantics.

The evaluator resolves these onto the canonical UTC timeline.

No host-local assumptions.

A strategy not dependent on sessions does not need a session block.

---

# 14. PRICE / UNIT SEMANTICS

All price/value-bearing rules and parameters must preserve meaningful units.

Do not confuse:

* storage precision;
* tick size;
* pip;
* quote currency;
* base quantity;
* contract multiplier;
* lot size.

Foundation InstrumentDefinition remains authoritative for market-price meaning.

Future APOLLO execution contracts remain authoritative for position economics.

Specification declares semantic requirements without inventing broker conventions.

---

# 15. ENTRY SEMANTICS

A strategy may define one or more entry setups.

Each must be capable of declaring:

* direction: LONG / SHORT / BOTH where appropriate;
* enabling conditions;
* trigger conditions;
* confirmation conditions;
* no-entry conditions;
* temporal ordering;
* validity duration;
* entry timing semantics.

The contract must distinguish:

```text
close above level
```

from:

```text
high touches level
```

from:

```text
crosses above and closes above
```

These are not interchangeable.

---

# 16. INVALIDATION / NO-ENTRY

Invalidation and no-entry semantics are first-class.

Examples:

* setup expires after N candles;
* do not enter after session boundary;
* do not enter if volatility exceeds threshold;
* setup invalidated if opposite level touched first;
* context expires before trigger.

Absence of an invalidation rule must not silently become one.

---

# 17. STRATEGY-INTRINSIC EXIT SEMANTICS VS EXECUTION POLICY

PID-004 must distinguish:

```text
strategy-intrinsic exit semantics
```

from:

```text
independently versioned execution mechanics
```

## Strategy-intrinsic exit semantics

A rule belongs in StrategyVersion when changing it changes the actual trading hypothesis.

Example:

> “Exit when RSI crosses back below 50.”

That is semantic strategy logic.

Removing/replacing it creates a new StrategyVersion.

## Execution policy

A rule belongs in `ExecutionPolicyVersion` when the strategy allows independently governed execution mechanics to be selected/tested.

Examples may include:

* a generic stop distance chosen from an authorised range;
* trailing-stop policy;
* break-even policy;
* partial-exit mechanics;
* time-stop mechanics;

where these are not intrinsic to the underlying strategy thesis.

Specification declares compatibility and authorised search boundaries.

The frozen execution policy belongs to the ResearchRun.

Changing only `ExecutionPolicyVersion` does not silently rewrite StrategyVersion.

---

# 18. FIXED VS TUNABLE PARAMETERS

Every strategy parameter has explicit status.

Conceptually:

```text
FIXED
TUNABLE
```

A tunable parameter requires an authorised bounded domain such as:

```text
integer range
decimal range
enumerated values
boolean alternatives
duration range
price/unit-bearing range
```

No:

`ATHENA may try whatever it wants`.

Changing a strategy-intrinsic authorised search envelope creates a new StrategyVersion where it changes the research hypothesis/authority.

---

# 19. EXECUTION-POLICY SEARCH AUTHORITY

Specification may authorise ATHENA to search selected independently versioned execution-policy dimensions.

Example conceptual declaration:

```text
execution_policy:
  stop_loss:
    compatibility: PERMITTED
    search_authority: TUNABLE
    range: ...
```

or:

```text
execution_policy:
  stop_loss:
    compatibility: DISABLED
```

The final exact choice belongs to `ExecutionPolicyVersion`, not StrategyVersion.

No implicit feature enablement.

---

# 20. DIKE / SIZING / NEWS-CONTEXT POLICY COMPATIBILITY

Preserve A-003.

Specification may declare:

* DIKE compatibility;
* fixed constraints;
* disabled/permitted/required behaviour;
* authorised research envelope.

The exact frozen DIKE configuration belongs to `DIKEPolicyVersion`.

The exact sizing policy belongs to `SizingPolicyVersion`.

A future context policy belongs to `NewsContextPolicyVersion`.

Changing those independently governed policies does not create a new StrategyVersion unless the strategy's own deterministic semantics changed.

ARES supplies governed contextual facts.

A deterministic NewsContextPolicy may later define how those facts participate in experiments.

NEO remains retrospective:

`NEO feeds back, not in.`

TRON remains live DIKE/risk enforcement authority.

HELIOS remains capital/account unaware.

---

# 21. INTRABAR / WICK SEMANTICS

Where active price-touch behaviour matters, Specification must explicitly reference appropriate OHLC facts.

Do not silently substitute close-only logic.

Preserve resolution hierarchy:

1. canonical lower-timeframe evidence where available and semantically sufficient;
2. otherwise register intrabar ambiguity;
3. apply exact experiment ambiguity policy.

For specifications capable of same-candle ordering ambiguity, required ambiguity-policy semantics must be explicit.

Existing initial policy:

`CONSERVATIVE_SL_FIRST`

may be selected explicitly where appropriate.

Do not hide it as evaluator default.

---

# 22. SOURCE VS WORKSHOP PROVENANCE

Every material semantic rule must be traceable to how it entered the Specification.

Preserve distinctions equivalent to:

* `SOURCE_RULE`
* `USER_CLARIFICATION`
* `WORKSHOP_PROPOSAL`
* `ACCEPTED_SPECIFICATION_RULE`

Recommended model:

### Origin

```text
SOURCE_RULE
USER_CLARIFICATION
WORKSHOP_PROPOSAL
```

### Acceptance state

```text
PROPOSED
ACCEPTED_SPECIFICATION_RULE
REJECTED
SUPERSEDED
```

This avoids pretending `ACCEPTED_SPECIFICATION_RULE` is an origin.

A Workshop proposal accepted by Matt remains:

`origin = WORKSHOP_PROPOSAL`

and:

`acceptance = ACCEPTED_SPECIFICATION_RULE`

Claude must never invent a rule and label it `SOURCE_RULE`.

---

# 23. MATERIAL DECISION REFERENCES

Specification semantic nodes introduced or changed during Workshop should reference material decisions where appropriate.

Finalised StrategyVersion need not contain every chat token.

It must retain enough lineage to answer:

> Why does this rule mean this?

and:

> Did the source say this, did Matt clarify it, or did MENDEL propose it?

---

# 24. DATA REQUIREMENT MODEL

Data requirements are first-class specification semantics.

A `DataRequirement` should preserve:

* semantic requirement ID;
* human-readable semantic name;
* fact class;
* fact-reference kind;
* required authority/source class;
* instrument applicability;
* timeframe/resolution;
* required historical depth/window;
* units;
* temporal alignment requirements;
* required fields;
* whether derived from another governed input;
* optional/mandatory semantics where meaningful.

Examples of fact classes:

```text
MARKET_OHLCV
OPTIONS_CHAIN
IMPLIED_VOLATILITY
OPEN_INTEREST
FUTURES_CURVE
ORDER_BOOK
ECONOMIC_SURPRISE
NEWS_CONTEXT
PREDICTION_MARKET
FUNDING_RATE
ON_CHAIN
OTHER_GOVERNED_FACT
```

Governed schema evolution is required for additions.

---

# 24A. CAUSAL EXTERNAL / CONTEXT FACT SEMANTICS

Historical evaluation may consume only information that was available at that historical instant.

External/context facts must preserve causal availability metadata where relevant.

Support fields equivalent to:

```text
event_time
published_at_utc
observed_at_utc
effective_at_utc
revision
version
```

Semantics:

### `event_time`

When the underlying real-world event occurred or is defined to occur.

### `published_at_utc`

When an authority published the information.

### `observed_at_utc`

When the governed system first observed/ingested it.

### `effective_at_utc`

The earliest canonical instant at which a historical evaluator is permitted to consume that fact.

### `revision/version`

Identity of the source revision/value version.

The invariant is:

> Historical evaluation may consume only information available at that historical instant.

A later-revised number must never leak backward.

A later article must never inform an earlier decision.

A prediction-market probability observed after an event may not be projected into the pre-event timeline.

An economic release revision may not replace the original released value in a backtest unless the strategy explicitly consumes revisions causally after they become available.

This applies especially to:

* ARES;
* news;
* economic releases;
* prediction markets;
* expectations;
* revised macroeconomic series;
* externally observed context.

---

# 25. DATA AUTHORITY

Each required input declares required authority class.

Examples:

```text
HERMES_CANONICAL_MARKET
ARES_GOVERNED_CONTEXT
OPTIONS_AUTHORITY
FUTURES_AUTHORITY
OTHER_GOVERNED_AUTHORITY
```

An authority class may exist semantically before a concrete provider is onboarded.

Do not substitute an unrelated convenient source merely because the intended authority is unavailable.

HERMES remains canonical market-history authority.

ARES remains governed news/context authority.

DARWIN consumes governed fact contracts.

It does not manufacture missing canonical truth.

---

# 25A. FACT AUTHORITY + DERIVATION CHAIN

Every fact used by strategy semantics must be attributable as either:

```text
CANONICAL_FACT_REFERENCE
```

or:

```text
SPECIFICATION_DERIVED_FACT
```

For derived facts, the complete deterministic derivation chain must remain reproducible.

Example:

```text
HERMES H1 close
→ EMA algorithm v1
→ period 50
→ warm-up 50 closed bars
→ output USD_PER_TROY_OUNCE
```

The resulting EMA is a DARWIN-derived fact.

It is not relabelled as HERMES data.

Future promotion/live evaluation must either reuse the same deterministic derivation semantics or prove equivalent compilation.

---

# 26. CRITICAL SEPARATION — REQUIREMENT VS AVAILABILITY

The immutable Strategy Specification records:

> what evidence the strategy requires.

A separate `DataReadinessAssessment` records:

> whether DARWIN can satisfy those requirements now.

Current availability must not participate in StrategyVersion semantic identity.

Conceptually:

```text
StrategyVersion
    └── DataRequirement[]
```

separate from:

```text
DataReadinessAssessment
    ├── strategy_version_id
    ├── assessed_at_utc
    ├── authority contract versions
    ├── per-requirement availability
    ├── missing reason
    └── overall readiness
```

Readiness may be reassessed later without modifying StrategyVersion.

---

# 27. DATA READINESS STATES

At minimum:

```text
TESTABLE
DATA_BLOCKED
```

Per requirement, useful states such as:

```text
AVAILABLE
UNAVAILABLE
INSUFFICIENT_HISTORY
INSUFFICIENT_RESOLUTION
AUTHORITY_NOT_ONBOARDED
CONTRACT_INCOMPATIBLE
UNKNOWN
```

Exact names may be refined.

The invariant:

```text
SPECIFIED + DATA_BLOCKED
```

is valid.

Data blocked does not mean:

* strategy failed;
* strategy rejected;
* strategy invalid;
* evidence is poor.

It means required historical facts are unavailable.

---

# 28. DATA_BLOCKED / SHELVED

Support non-destructive shelving.

Operationally:

```text
SPECIFIED
+
DATA_BLOCKED
+
SHELVED
```

Shelving preserves:

* StrategyVersion;
* specification;
* source lineage;
* rationale;
* all DataRequirements;
* readiness assessment;
* exact blockers.

When capability becomes available:

```text
reassess readiness
```

not:

```text
rediscover
rewrite
```

No new StrategyVersion merely because infrastructure improved.

---

# 29. STRATEGY-DEMAND SIGNAL

DARWIN should later be able to aggregate blockers such as:

```text
17 candidates require historical implied volatility
9 require historical options OI
31 require ARES event context
4 require futures curves
```

PID-004A need only preserve the model/queryability needed to support this.

Do not automatically modify HERMES/ARES or launch infrastructure work.

---

# 30. IV-WALL DESIGN TEST

PID-004A must include an architectural conformance fixture for an XAUUSD implied-volatility-wall reversal hypothesis.

It should be capable of requiring:

* canonical `XAU_USD` price history;
* historical options expiry;
* strikes;
* historical implied volatility;
* historical open interest;
* contract/chain observation timestamps;
* explicitly defined derived options-exposure fact where required.

The fixture must prove:

1. schema represents the hypothesis;
2. unavailable options history does not corrupt semantics;
3. StrategyVersion remains valid;
4. DataReadiness reports `DATA_BLOCKED`;
5. missing capabilities are explicit/queryable.

Controlled fixture only.

Never present it as real discovered/proven evidence.

---

# 31. SEMANTIC AMBIGUITY VS DATA BLOCK

Keep these separate.

### Ambiguous

> “Trade near an IV wall.”

Unknown:

* wall definition;
* expiry selection;
* distance;
* direction;
* trigger;
* exit.

Result:

`STRATEGY_NOT_SUFFICIENTLY_DEFINED`

No finalisation.

### Fully specified but unavailable data

Exact IV-wall construction and trade semantics exist, but historical option-chain/OI evidence is unavailable.

Result:

```text
SPECIFIED
DATA_BLOCKED
```

---

# 31A. SEMANTIC AMBIGUITY VS CAUSAL UNAVAILABILITY

Also distinguish:

### Semantic ambiguity

The strategy does not say what event/value it needs.

### Causal-data defect

The strategy is explicit, but the dataset lacks trustworthy historical publication/observation timing required to prevent hindsight.

Example:

> Strategy uses consensus CPI surprise available at release time.

If DARWIN has final revised CPI values but lacks the originally published value/timestamp history, the strategy may be semantically valid yet:

`DATA_BLOCKED`

because causal evidence is insufficient.

DARWIN must not substitute revised hindsight data.

---

# 32. VALIDATION PIPELINE

PID-004A implements deterministic validation stages.

Conceptually:

```text
schema validation
→ reference validation
→ fact-kind/authority validation
→ type/unit validation
→ semantic completeness
→ provenance validation
→ parameter/search-envelope validation
→ temporal/timeframe validation
→ composition/state validation
→ causal-context validation
→ ambiguity validation
→ finalisation eligibility
```

Data availability is assessed separately after semantic finalisation eligibility.

Missing historical data must not cause a semantically complete specification to be called ambiguous.

---

# 33. FINALISATION GATE

A SpecificationDraft may finalise only when:

* schema valid;
* required semantics complete;
* no unresolved material ambiguity;
* all referenced facts/operators known;
* parameter types/units valid;
* tunable parameters have bounded domains;
* Workshop-introduced rules have accepted provenance;
* timeframe/session semantics deterministic where applicable;
* composition/temporal semantics deterministic;
* causal external-fact requirements explicit where applicable;
* DataRequirements explicit;
* no implicit evaluator defaults remain which could materially alter results.

Then DARWIN atomically creates immutable:

`StrategyVersion`

and advances:

`DISCOVERED → SPECIFIED`

where lineage supports the transition.

---

# 34. FINALISATION DOES NOT REQUIRE DATA AVAILABILITY

A semantically valid strategy can finalise when required data is unavailable.

Finalisation creates StrategyVersion.

DataReadinessAssessment may mark:

`DATA_BLOCKED`.

This is intentional.

---

# 35. REJECTION

Rejection is an explicit operational/product decision, not failed evidence.

Reasons may include:

* unsuitable mechanism;
* user chooses not to pursue;
* source unsuitable;
* duplicate concept with no useful differentiation;
* research cost unjustified.

Record:

* reason code;
* notes;
* UTC timestamp;
* actor.

Do not delete provenance.

Do not manufacture StrategyVersion merely to record rejection.

---

# 36. STRATEGY COMPOSITION FUTURE COMPATIBILITY

Do not implement a composition engine in PID-004.

However candidate lineage must support:

```text
Candidate C derived from Candidate A + Candidate B + Context Rule X
```

C is a NEW candidate.

It receives:

* its own Specification;
* StrategyVersion(s);
* ATHENA work;
* APOLLO proof.

Success of A/B does not prove C.

---

# 37. PERSISTENCE

Use `DARWIN_sql`.

No new database.

No Redis.

No standalone Specification service.

PID-004A likely needs durable entities equivalent to:

* strategy candidates/lineage where Foundation concepts need refinement;
* specification drafts;
* immutable strategy versions/specification documents;
* rule provenance references;
* data requirements;
* data readiness assessments;
* validation records.

Do not duplicate Foundation concepts without first proving why existing contracts cannot evolve safely.

Migration design must be reviewed against `0001–0005`.

---

# 38. FINGERPRINT SEPARATION

PID-004A shall explicitly separate at least two fingerprints.

## `semantic_fingerprint`

Binds deterministic strategy semantics only.

It must include all semantics capable of changing strategy behaviour, such as:

* schema semantic version;
* typed strategy rules;
* composition/temporal semantics;
* fixed strategy parameters;
* strategy-intrinsic tunable domains;
* session/time semantics;
* fact references;
* specification-derived fact algorithms/versions;
* data semantic requirements;
* intrinsic ambiguity semantics;
* strategy applicability.

It must not unnecessarily bind:

* SCOUT URL;
* source title;
* discovery ID;
* provenance note wording;
* Workshop commentary;
* current data readiness;
* HERMES uptime;
* current policy versions;
* current ResearchRun configuration.

Therefore two independent discoveries may produce StrategyVersions with:

```text
same semantic_fingerprint
```

while retaining completely separate provenance chains.

That allows DARWIN to recognise:

> these are semantically the same strategy hypothesis

without erasing where each came from.

## `artifact_record_fingerprint`

Binds the durable finalised artifact/record.

It may additionally include:

* StrategyVersion record identity;
* provenance references;
* material decision references;
* source lineage;
* schema/artifact metadata.

Two StrategyVersion records may therefore have:

```text
same semantic_fingerprint
different artifact_record_fingerprint
```

This is valid.

Semantic equality must not collapse provenance records automatically.

Deduplication/promotion policy is separately governed.

Neither fingerprint binds current DataReadinessAssessment.

Neither binds independently selected:

* ExecutionPolicyVersion;
* DIKEPolicyVersion;
* SizingPolicyVersion;
* NewsContextPolicyVersion.

---

# 39. PID-004A — HSA ARCHAEOLOGY

Before implementing overlapping Specification capability, perform bounded archaeology of standalone HSA.

Classify relevant areas:

```text
REUSE
REUSE_WITH_ADAPTATION
REIMPLEMENT_FROM_DOCTRINE
DO_NOT_REUSE
DEFER
```

Inspect especially:

* candidate identity/versioning;
* ambiguity refusal;
* atomic condition representation;
* deterministic decomposition;
* timeframe semantics;
* fixed/tunable parameter distinction;
* authorised tuning ranges;
* validation;
* lineage;
* schema contracts.

Do not copy blindly.

Do not modify/retire HSA.

Produce:

`docs/archaeology/HSA-PID004A-REUSE-ASSESSMENT.md`

Standalone HSA retirement remains separately authorised.

---

# 39A. PID-004A — HELIOS SEMANTIC-COMPATIBILITY ARCHAEOLOGY

Perform bounded read-only archaeology of current canonical HELIOS.

Do not modify HELIOS.

Inspect only what is necessary to understand deterministic strategy semantic compatibility, particularly:

* atomic/condition semantics;
* `ALL`;
* `ANY`;
* `SEQUENCE`;
* `CONTEXT_TRIGGER`;
* normalized strategy-state semantics;
* timeframe semantics;
* strategy identity/config contracts;
* state transition/reset/expiry behaviour where relevant;
* input/output contract shape required by HELIOS/FALCON boundary.

Classify compatibility findings as:

```text
DIRECTLY_COMPATIBLE
COMPILABLE_WITH_VERSIONED_ADAPTER
DARWIN_MODEL_MUST_EXPLICITLY_REPRESENT
HELIOS_CURRENTLY_UNSUPPORTED
DEFER
```

Produce:

`docs/archaeology/HELIOS-PID004A-SEMANTIC-COMPATIBILITY.md`

The assessment must answer:

1. Which DARWIN semantics could HELIOS eventually consume directly?
2. Which require a deterministic compiler/adapter?
3. Which current HELIOS concepts need explicit representation in the DARWIN contract?
4. Which DARWIN semantics are expected to fail future HELIOS promotion until HELIOS evolves?
5. Are there any existing HELIOS normalized states/temporal semantics which would otherwise be lost?

No HELIOS changes are authorised.

---

# 40. PID-004A REAL-WORLD FITNESS TEST

Test architecture against genuine current SCOUT discoveries.

Use a representative bounded sample of real XAUUSD discoveries from PID-003.

Do not rewrite source descriptions to make them fit.

For each selected discovery:

1. preserve exact SCOUT provenance;
2. attempt structured specification;
3. identify unresolved semantics;
4. identify DataRequirements;
5. validate;
6. classify truthful outcome.

Possible outcomes include:

```text
SUFFICIENTLY_DEFINED / TESTABLE

STRATEGY_NOT_SUFFICIENTLY_DEFINED

SUFFICIENTLY_DEFINED / DATA_BLOCKED

REJECTED
```

Do not manufacture outcome diversity.

If all current Trader.dev candidates are inaccessible/insufficiently defined, report exactly that.

That is evidence about source quality, not PID failure.

---

# 41. CONTROLLED CONTRACT FIXTURES

Controlled fixtures must prove architecture breadth.

Clearly label them test fixtures.

At minimum:

### A. Simple single-timeframe atomic strategy

OHLCV-only, testable.

### B. Multi-timeframe strategy

Explicit context/signal/entry roles.

### C. Session strategy

Explicit IANA timezone/DST.

### D. Wick/touch strategy

Explicit high/low semantics and ambiguity policy.

### E. Tunable strategy

Fixed/tunable parameters with bounded envelopes.

### F. DIKE-compatible strategy

Explicit DIKE disabled/fixed/search compatibility semantics without embedding DIKEPolicyVersion.

### G. Data-blocked IV-wall strategy

Fully specified semantics requiring historical options/IV/OI.

### H. Insufficiently defined discovery

Fails:

`STRATEGY_NOT_SUFFICIENTLY_DEFINED`

### I. Causal context strategy

Consumes an external/event fact with publication/observation/effective timing and proves later revisions cannot leak backward.

### J. Derived-fact strategy

Uses a `SPECIFICATION_DERIVED_FACT` such as a versioned EMA and proves it remains distinct from the underlying canonical HERMES fact.

---

# 41A. HELIOS COMPOSITION / STATE COMPATIBILITY FIXTURES

PID-004A must add controlled compatibility fixtures for representative HELIOS semantics.

At minimum:

### H1. Atomic

One deterministic atomic condition.

### H2. ALL

Multiple conditions all required.

### H3. ANY

At least one condition sufficient.

### H4. SEQUENCE

A deterministic ordered sequence where:

```text
A then B
```

is semantically different from:

```text
A AND B
```

### H5. CONTEXT_TRIGGER

Context must become valid before trigger semantics may activate.

### H6. Multi-timeframe context/trigger

Example:

```text
H4 context
→ H1 trigger
```

with deterministic causal alignment and no look-ahead.

For each fixture prove one of:

```text
direct semantic representation
```

or:

```text
deterministic versioned compile target
```

with expected normalized-state meaning documented.

If exact semantic parity cannot be represented, PID-004A must fail that compatibility fixture and record the missing contract capability.

Do not approximate it.

---

# 42. PID-004A TESTING

Add comprehensive:

* JSON/schema contract tests;
* domain tests;
* deterministic serialisation tests;
* semantic fingerprint tests;
* artifact fingerprint tests;
* DB constraint/integration tests;
* validation tests;
* version immutability tests;
* provenance tests;
* policy-identity separation tests;
* data-requirement tests;
* readiness tests;
* canonical-vs-derived-fact tests;
* causal-event tests;
* HELIOS compatibility fixture tests;
* real-SCOUT conformance tests.

Critical cases:

* unknown operator rejected;
* unknown fact rejected;
* unit mismatch rejected;
* missing timeframe role rejected where referenced;
* omitted irrelevant semantics allowed;
* materially required absent semantics rejected;
* tunable parameter without bounded domain rejected;
* out-of-domain parameter rejected;
* Workshop proposal cannot masquerade as source rule;
* unresolved ambiguity blocks finalisation;
* unavailable data does not block semantic finalisation;
* readiness changes do not change semantic fingerprint;
* later availability moves DATA_BLOCKED → TESTABLE without new StrategyVersion;
* semantic edit creates new semantic fingerprint;
* provenance-only change may preserve semantic fingerprint while changing artifact fingerprint;
* different source records with identical deterministic semantics can be recognised as semantically equal;
* changing ExecutionPolicyVersion does not change StrategyVersion semantic fingerprint;
* changing DIKEPolicyVersion does not change StrategyVersion semantic fingerprint;
* causal external fact cannot be read before `effective_at_utc`;
* revised external value does not leak backward;
* derived fact cannot claim canonical HERMES authority;
* changed derived algorithm version changes semantic fingerprint where used;
* atomic/ALL/ANY/SEQUENCE/CONTEXT_TRIGGER semantics are distinguishable;
* multi-timeframe context/trigger alignment remains causal.

---

# 43. PID-004A ARENA SURFACE

PID-004A may add restrained Specification inspection/readiness UI if useful for proving the contract.

Do not build full Workshop yet.

Useful presentation may include:

* candidate;
* semantic validation status;
* specification status;
* semantic fingerprint;
* testability/readiness;
* required facts;
* canonical vs derived facts;
* missing capabilities;
* exact validation errors;
* StrategyVersion identity;
* HELIOS compatibility status where deterministically assessable.

No fake MENDEL/Workshop chat.

No Claude Code integration.

---

# 44. PID-004A STOP GATE

When PID-004A implementation is complete:

ROGUE must STOP.

Return for Architect review with:

* exact commit;
* HSA archaeology;
* HELIOS semantic-compatibility archaeology;
* final specification schema;
* typed expression/operator/composition model;
* provenance model;
* policy-identity model;
* semantic/artifact fingerprint model;
* canonical/derived fact model;
* causal external-fact model;
* data-requirement model;
* readiness model;
* migration/schema;
* validation outcomes;
* real SCOUT candidate classifications;
* controlled fixture classifications;
* HELIOS compatibility fixture results;
* test totals;
* CI;
* Auditor verdict;
* known limitations.

Expected verdict request:

`GREEN_DARWIN_PID004A_SPECIFICATION_CONTRACT_READY_FOR_ARCHITECT_REVIEW`

Do not start PID-004B before explicit acceptance.

---

# 45. PID-004B — STRATEGY WORKSHOP PURPOSE

After PID-004A acceptance, Strategy Workshop becomes the ARENA authoring environment for turning Discovery into an accepted SpecificationDraft.

Workshop helps resolve:

* trading mechanism;
* ambiguity;
* timeframe semantics;
* temporal/composition semantics;
* sessions;
* entry/exit rules;
* data requirements;
* parameter ranges;
* execution-policy compatibility;
* DIKE compatibility;
* sizing/context compatibility.

It does not replace deterministic validation.

---

# 46. MENDEL

Working name:

`MENDEL`

MENDEL is a specialist Claude Code strategy-engineering agent.

MENDEL is not DARWIN.

MENDEL is not:

* evidence authority;
* promotion authority;
* ATHENA;
* APOLLO;
* QUALIFICATION;
* NEO;
* live trading intelligence.

MENDEL proposes precise hypotheses.

DARWIN validates and finalises them.

---

# 47. WORKSHOP WORKSPACE

Initial PID-004B integration uses a bounded workspace:

```text
/srv/DARWIN/workspaces/<workshop-id>/
```

with equivalents of:

```text
DISCOVERY.json
SOURCE_MATERIAL/
CONTEXT.md
QUESTIONS.md
DECISIONS.jsonl
SPECIFICATION_DRAFT.json
VALIDATION.json
```

Exact layout may be refined.

The workspace is an authoring surface.

It is not canonical StrategyVersion storage.

Canonical truth remains DARWIN persistence.

---

# 48. CLAUDE CODE BOUNDARY

Do not give FastAPI a generic:

```text
run arbitrary Claude command
```

capability.

PID-004B must establish a controlled mechanism whereby MENDEL:

* operates against one bounded Workshop;
* receives governed doctrine/schema;
* receives only relevant SCOUT/source context;
* receives relevant data-capability/readiness information;
* edits draft/workspace material;
* cannot directly write canonical StrategyVersion records;
* cannot bypass deterministic validation.

Prefer verifiable OS/Claude Code permission boundaries.

Do not invent undocumented CLI security assumptions.

---

# 49. WORKSHOP CANONICAL STATE

Workshop durable state should include equivalents of:

* workshop ID;
* discovery/candidate link;
* status;
* unresolved questions;
* material decisions;
* current draft identity;
* validation results;
* timestamps;
* user acceptance decisions.

Filesystem workspace is not the only copy of critical decision truth.

---

# 50. MATERIAL DECISION TRAIL

Persist material decisions, not every conversational token.

A decision can record:

* question/ambiguity;
* proposed resolution;
* origin;
* accepted/rejected state;
* rationale/notes;
* user/agent attribution;
* UTC timestamp;
* affected specification semantic references.

Source provenance and accepted semantics remain distinguishable.

---

# 51. WORKSHOP AUTHORING LOOP

Conceptually:

```text
Discovery
→ Open Workshop
→ inspect source material
→ identify ambiguities
→ MENDEL proposes precise alternatives
→ user accepts/clarifies/rejects
→ SpecificationDraft updated
→ DARWIN validation
→ remaining questions
→ repeat
→ explicit finalisation
```

MENDEL never silently finalises.

---

# 52. WORKSHOP DATA-CAPABILITY AWARENESS

MENDEL receives current DARWIN data-capability/readiness information.

It may say:

> This hypothesis is fully definable, but requires historical options open interest which DARWIN does not currently have.

It must not solve missing data by quietly replacing the hypothesis with a convenient substitute.

Any substitution is a material Workshop proposal requiring explicit acceptance.

---

# 53. WORKSHOP ARENA UX

ARENA should support progression:

```text
Discovery
→ source/provenance
→ Open Workshop
→ questions
→ material decisions
→ specification draft
→ validation
→ data requirements/readiness
→ finalise StrategyVersion
```

Useful panels:

### Source

What was actually discovered.

### Hypothesis

Human-readable mechanism.

### Rules

Machine-readable semantics.

### Questions

Unresolved ambiguity.

### Decisions

Accepted/rejected material decisions.

### Parameters

Fixed/tunable and search authority.

### Policy compatibility

Execution/DIKE/sizing/news-context compatibility and permitted research envelope.

### Data requirements

Available/missing facts.

### Validation

Errors/warnings/readiness.

### Finalise

Explicit user action only.

---

# 54. FINALISATION UX

Make consequence clear:

> Finalising creates an immutable StrategyVersion.

Before finalisation show:

* unresolved-question count;
* semantic validation;
* missing data requirements;
* semantic fingerprint preview where practical;
* explicit TESTABLE vs DATA_BLOCKED;
* policy compatibility declarations;
* source/Workshop provenance summary.

A DATA_BLOCKED strategy may still finalise when semantically complete.

---

# 55. WORKSHOP SAFETY / SOURCE FIDELITY

Source material is untrusted.

MENDEL and ARENA treat source content as data.

Do not allow source text to redefine MENDEL's operating instructions.

Do not execute source code.

Do not silently modify SCOUT's original record.

Workshop interpretation is a separate layer with explicit provenance.

---

# 56. PID-004B TESTING

At minimum prove:

* Workshop created from real Discovery;
* original source remains unchanged;
* bounded workspace created correctly;
* MENDEL/draft edits cannot mutate canonical StrategyVersion directly;
* material decision trail persists;
* source rule/user clarification/workshop proposal remain distinguishable;
* accepted rules feed SpecificationDraft;
* unresolved ambiguity blocks finalisation;
* deterministic validation controls finalisation;
* DATA_BLOCKED strategy may finalise;
* finalisation creates immutable StrategyVersion;
* semantic edit after finalisation requires new StrategyVersion;
* policy-only experiment changes do not rewrite StrategyVersion;
* Workspace deletion does not erase canonical StrategyVersion/decision evidence;
* no arbitrary command endpoint exists.

Real-browser proof required.

---

# 57. PID-004B STOP GATE

After Workshop implementation and independent Audit:

Return:

`GREEN_DARWIN_PID004_SPECIFICATION_WORKSHOP_READY_FOR_ARCHITECT_REVIEW`

Do not merge without Architect authorisation.

---

# 58. EXPLICIT PID-004 EXCLUSIONS

PID-004 does NOT implement:

* ATHENA optimisation;
* APOLLO proof engine;
* qualification;
* continuous factory;
* live trading;
* broker integration;
* TRON;
* NEO;
* SOCRATES;
* PLUTUS;
* automatic HERMES expansion;
* automatic ARES expansion;
* options-data platform;
* strategy-composition engine;
* HELIOS implementation/modification;
* HELIOS promotion compiler beyond bounded compatibility architecture/testing required by PID-004A;
* external-performance validation;
* fuzzy proof transfer between related strategies.

No strategy becomes promising in PID-004.

---

# 59. RUNTIME

Expected production runtime remains:

```text
DARWIN_core
DARWIN_sql
```

No Redis unless separately justified.

No Specification microservice.

No Workshop microservice merely because Workshop has distinct product identity.

Claude Code/MENDEL integration must not accidentally become an always-on third DARWIN service without explicit architecture approval.

---

# 60. CURRENT PROGRAMME MILESTONE

Unchanged:

> At least FIVE independently promising XAUUSD strategies discovered, specified, optimised and sequentially proven using canonical HERMES historical authority.

PID-004 advances candidates only as far as:

`SPECIFIED`

with operational readiness:

`TESTABLE`

or:

`DATA_BLOCKED`

where appropriate.

No PID-004 result counts as `PROMISING`.

---

# 61. DELIVERY ORDER

Canonical programme sequence remains:

```text
PID-002 — ARENA
PID-003 — SCOUT / Discovery
PID-004 — Strategy Specification + Workshop
    PID-004A — Specification Contract
    PID-004B — Strategy Workshop
PID-005 — ATHENA
PID-006 — APOLLO
PID-007 — Qualification
PID-008 — Continuous Factory
```

---

# 62. PID-004 AUTHORISATION RULE

This document is for final architectural acceptance only.

Implementation must not begin until the Architect explicitly approves it.

If approved:

1. implement PID-004A only;
2. STOP;
3. obtain explicit PID-004A acceptance;
4. then implement PID-004B;
5. STOP for full PID-004 review.

No Claude Code/MENDEL implementation may begin before PID-004A is accepted.

---

# EXPECTED NEXT VERDICT REQUEST

`GREEN_DARWIN_PID004_SPECIFICATION_WORKSHOP_READY_FOR_FINAL_ARCHITECT_ACCEPTANCE`

