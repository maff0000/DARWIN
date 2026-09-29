# DARWIN AMENDMENT A-007 — CANONICAL STRATEGY DEFINITION & SERIALIZATION DOCTRINE

**Parent authority:** `PID.md`  
**Product:** DARWIN  
**Date:** 2026-09-29  
**Status:** ARCHITECT AMENDMENT — LOCKED  
**Relationship:** Additive to A-001 through A-006

---

## A-007.1 Decision

Every DARWIN strategy must have **one canonical, versioned, machine-readable representation** before it may enter research, proof, qualification, or promotion.

JSON is the standard durable interchange/serialization format.

The JSON document itself is **not** the ultimate semantic authority.

The semantic authority remains DARWIN's governed typed Specification model and immutable `StrategyVersion`.

The invariant is:

```text
human / AI / external idea
        ↓
canonical strategy JSON
        ↓
schema validation
        ↓
typed DARWIN Specification model
        ↓
semantic validation / finalise()
        ↓
immutable StrategyVersion
        ↓
CanonicalStrategyCompiler
        ↓
ExecutableStrategyPlan
```

No strategy may bypass this route.

---

## A-007.2 Why this is required

Without a canonical strategy contract, meaning can drift between:

- human descriptions;
- transcripts and source material;
- Strategy Workshop;
- MENDEL / AI-assisted reasoning;
- Python objects;
- ATHENA;
- APOLLO;
- HELIOS;
- ARENA;
- future NEO/SOCRATES proposals;
- exported/imported research artifacts.

DARWIN must never have multiple informal definitions of "the same strategy".

A strategy becomes a DARWIN strategy only after its semantics have been represented in the canonical schema and successfully finalised into an immutable `StrategyVersion`.

---

## A-007.3 JSON is the canonical interchange format

The standard durable interchange representation is JSON.

Reasons:

- language-independent;
- stable for APIs and files;
- easy to validate;
- easy to diff;
- AI-friendly;
- GUI-friendly;
- suitable for import/export;
- reproducible;
- can be fingerprinted after canonicalisation.

JSON formatting is not semantic.

Whitespace, property ordering and other presentation differences must not change strategy meaning.

Where fingerprints are derived from serialized form, DARWIN must use deterministic canonicalisation rather than raw file bytes.

---

## A-007.4 Schema authority

Every canonical strategy JSON document must declare an explicit schema version.

Conceptually:

```json
{
  "schema_version": "1.0",
  "strategy_id": "xau-example-001",
  "strategy_version": "1",
  "name": "Example Strategy",
  "thesis": "Human-readable explanation only",
  "instrument_applicability": {},
  "required_market_capabilities": [],
  "composition": {},
  "data_requirements": [],
  "fixed_parameters": {},
  "tunable_parameters": {},
  "entry_semantics": {},
  "exit_rules": [],
  "session_spec": {},
  "setup_expiry": {},
  "intrabar_ambiguity_policy": "CONSERVATIVE_SL_FIRST",
  "provenance": {}
}
```

The exact production schema must be generated from or rigorously aligned with DARWIN's existing Specification/`StrategyVersion` semantics.

This amendment does **not** authorise inventing a second, competing strategy model.

The schema is a serialization contract for the authoritative domain model.

---

## A-007.5 Structural validation and semantic validation are different gates

JSON Schema (or exact equivalent) validates document structure.

It may enforce, for example:

- required fields;
- allowed primitive names;
- field types;
- closed enumerations;
- shape of parameter definitions;
- shape of composition nodes;
- schema version.

But JSON Schema alone cannot determine that a strategy is semantically valid.

Semantic authority remains DARWIN Specification validation.

Therefore:

```text
JSON structurally valid
        ≠
Strategy semantically valid
```

A structurally valid JSON strategy may still fail with governed domain outcomes such as:

`STRATEGY_NOT_SUFFICIENTLY_DEFINED`

or another explicit Specification error.

---

## A-007.6 No executable meaning may hide only in prose

Human-readable fields are permitted and encouraged, including:

- name;
- thesis;
- rationale;
- source narrative;
- examples;
- research notes;
- citations/provenance.

But prose is never executable strategy meaning.

For example:

```text
"Enter when price looks strong after breaking resistance"
```

may be retained as narrative, but it is not a valid executable rule.

Executable meaning must resolve into governed DARWIN semantics such as:

- `AtomicCondition`;
- `Comparison`;
- `CanonicalFactReference`;
- `ParameterReference`;
- `TemporalPredicate`;
- `SessionPredicate`;
- `EventPredicate`;
- `ALL`;
- `ANY`;
- `SEQUENCE`;
- `CONTEXT_TRIGGER`;
- explicit exit/invalidation/session semantics;
- explicit parameter domains.

If the strategy cannot yet be represented unambiguously, DARWIN must refuse to finalise it rather than interpret prose dynamically at runtime.

---

## A-007.7 One route into research

All strategy origins converge on the same canonical route.

Examples:

- SCOUT-discovered strategy;
- manually entered strategy;
- trader transcript;
- Strategy Workshop output;
- MENDEL/AI proposal;
- future NEO/SOCRATES hypothesis;
- imported external strategy document.

All must become:

```text
canonical strategy document
        ↓
SpecificationDraft / governed typed model
        ↓
finalise()
        ↓
StrategyVersion
```

before ATHENA or APOLLO may consume them.

ATHENA and APOLLO must never execute arbitrary strategy JSON directly.

They consume governed typed/compiled strategy identity.

---

## A-007.8 Immutable StrategyVersion remains semantic identity

The canonical JSON strategy document is an interchange representation.

`StrategyVersion` remains the immutable semantic identity used by DARWIN.

A finalised strategy must preserve:

- semantic fingerprint;
- schema semantic version;
- composition semantics;
- data requirements;
- instrument applicability;
- parameter definitions;
- session semantics;
- expiry/invalidation semantics;
- exit semantics;
- all other governed StrategyVersion fields.

Non-semantic narrative metadata must not alter `StrategyVersion.semantic_fingerprint`.

---

## A-007.9 Market Truth Profile / A-006 integration

A-007 incorporates Amendment A-006 directly into strategy description.

A strategy may explicitly declare required market capabilities.

Conceptually:

```json
{
  "instrument_applicability": {
    "instruments": ["XAU_USD"]
  },
  "required_market_capabilities": [
    "CANONICAL_CANDLES",
    "GC_ORDER_FLOW_CONTEXT",
    "GC_AUCTION_CONTEXT"
  ]
}
```

The capability names above are illustrative until their governed vocabulary is implemented.

The invariant is architectural:

```text
Strategy required capabilities
        ↓
selected Market Truth Profile
        ↓
satisfied / not satisfied
```

If required truth is unavailable, the strategy is not applicable to that profile.

No hidden knowledge such as "this strategy needs the GC data" may exist only in a human note, agent memory, source code comment, or prompt.

---

## A-007.10 Import/export doctrine

DARWIN should ultimately support lossless strategy import/export through the canonical JSON representation.

Required properties:

- versioned schema;
- deterministic validation;
- no silent field dropping;
- no silent default insertion where semantics would change;
- unknown semantic fields fail closed unless explicitly governed by a compatible schema version;
- export followed by import must preserve semantic identity;
- canonicalisation followed by fingerprinting must be deterministic;
- old documents remain interpretable according to their recorded schema version or fail explicitly as unsupported.

Schema migration must be explicit and versioned.

---

## A-007.11 AI doctrine

AI may help produce or transform a canonical strategy document.

AI may not bypass Specification validation.

An AI-generated strategy is still only a proposal until:

1. its JSON is structurally valid;
2. it maps into the governed DARWIN domain;
3. semantic validation succeeds;
4. an immutable `StrategyVersion` is produced.

No LLM interpretation is allowed inside APOLLO's or ATHENA's causal execution path.

Research execution must remain deterministic.

---

## A-007.12 HELIOS / promotion consequence

The same frozen strategy semantics proven by DARWIN must be the semantics promoted toward HELIOS.

The intended chain remains:

```text
Canonical Strategy JSON
        ↓
StrategyVersion
        ↓
CanonicalStrategyCompiler
        ↓
ExecutableStrategyPlan
        ├─────────────┐
        ↓             ↓
     ATHENA         APOLLO
```

A later HELIOS promotion compiler/adapter must consume the same governed semantic identity.

DARWIN must never prove one interpretation while HELIOS trades another.

---

## A-007.13 Minimum canonical strategy content

The exact schema is implementation-owned by the existing Specification model, but every finalised strategy representation must be able to preserve or reference, where applicable:

- schema version;
- strategy identity/version;
- human-readable name/thesis;
- source/provenance;
- instrument applicability;
- required market capabilities;
- composition primitive and component semantics;
- governed facts/data requirements;
- timeframes;
- direction semantics;
- fixed parameters;
- tunable parameters and allowed domains;
- entry semantics;
- exit semantics;
- invalidation semantics;
- session semantics;
- setup expiry;
- intrabar ambiguity declaration;
- policy compatibility declarations;
- deterministic test/evidence requirements where part of Specification;
- semantic fingerprint after finalisation.

No new semantic field should be added merely because JSON can carry it.

The typed DARWIN domain remains authoritative.

---

## A-007.14 Implementation timing

A-007 is architecture doctrine.

It does not require immediate implementation before SPEC-FIX-001 closure or PID-006B unless PID-006B needs a concrete serialization boundary.

Do not prematurely build:

- a second strategy model;
- a generic schema platform;
- a strategy DSL unrelated to current Specification semantics;
- arbitrary plugin execution;
- an LLM interpreter at runtime.

When implementation is required, prefer a narrow JSON Schema + serializer/deserializer around the existing Specification domain.

---

## A-007.15 Acceptance invariants for future implementation

When the canonical JSON contract is implemented, acceptance must prove at minimum:

1. valid strategy JSON -> governed typed Specification -> finalised `StrategyVersion`;
2. malformed JSON structure -> governed schema failure;
3. structurally valid but semantically ambiguous/invalid JSON -> governed Specification failure;
4. JSON round-trip preserves semantic identity;
5. JSON property ordering/whitespace does not alter semantic identity;
6. unknown unsupported semantic fields fail closed;
7. valid ATOMIC/ALL/ANY/SEQUENCE/CONTEXT_TRIGGER semantics round-trip correctly;
8. required market capabilities round-trip correctly;
9. prose fields cannot create executable behaviour;
10. ATHENA/APOLLO consume finalised/compiled identity, not arbitrary JSON;
11. deterministic canonicalisation/fingerprinting is proven;
12. no broker/live execution assumptions leak into strategy semantics.

---

## A-007.16 Programme consequence

The permanent doctrine is:

> **Every DARWIN strategy has one versioned, schema-valid, canonical machine-readable representation. JSON is the standard durable interchange representation. No strategy may enter ATHENA, APOLLO, Qualification or promotion until it has resolved successfully into the governed typed Specification model and immutable StrategyVersion.**

And, in combination with A-006:

> **Required market capabilities are explicit strategy semantics, never hidden operational knowledge.**

This amendment prevents semantic drift while keeping DARWIN deterministic, reproducible, AI-friendly and portable across systems.
