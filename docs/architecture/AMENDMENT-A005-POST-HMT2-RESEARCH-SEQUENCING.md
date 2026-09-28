# DARWIN AMENDMENT A-005 — POST-HMT-2 RESEARCH SEQUENCING AND PROOF ARCHITECTURE

**Parent authority:** `PID.md`  
**Product:** DARWIN  
**Date:** 2026-09-28  
**Status:** ARCHITECT AMENDMENT — TO BE INCORPORATED INTO THE PRODUCT CONSTITUTION  
**DARWIN baseline:** `a886b1b241d8eb8063db408e5dd146618af630ba`  
**HERMES baseline:** `4cece04bbc538828576b82e93fb20818b8f5b429`

---

## A-005.1 Purpose

HERMES HMT-2 materially expands the historical research authority available to DARWIN.

This amendment reconciles that change without resetting DARWIN or invalidating the existing candle foundation.

---

## A-005.2 HERMES authority now has two distinct historical surfaces

DARWIN recognises:

1. governed canonical candle history, consumed through `MarketDataset`; and
2. governed HMT-2 GC market-event/microstructure history.

Neither automatically replaces the other.

DARWIN remains read-only with respect to both.

DARWIN must not become a second canonical market-data authority.

---

## A-005.3 Historical proof before HMT-LIVE

HMT-LIVE is deferred.

The immediate economic question is whether HMT-2 produces measurable research value.

Therefore:

```text
HMT-2 historical authority
        ↓
DARWIN APOLLO proof capability
        ↓
HMT-2 historical value experiments
        ↓
only then reconsider HMT-LIVE
```

---

## A-005.4 PID numbering vs implementation order

Historical PID identities remain:

- PID-005 — ATHENA;
- PID-006 — APOLLO.

Implementation order is amended:

- PID-006 APOLLO core is implemented before PID-005 ATHENA engine;
- PID-005 is not renumbered;
- ATHENA implementation resumes only after APOLLO's core causal/evidence contracts are proven.

---

## A-005.5 Shared semantic truth, independent engines

ATHENA and APOLLO consume the same governed strategy meaning through a deterministic semantic compilation boundary.

They do not share a historical simulation engine.

```text
StrategyVersion
      ↓
CanonicalStrategyCompiler
      ↓
ExecutableStrategyPlan
      ├───────────────────┐
      ↓                   ↓
ATHENA engine         APOLLO engine
exploration           independent proof
```

This is required so APOLLO can falsify an ATHENA result rather than reproduce an ATHENA engine defect.

---

## A-005.6 Shared research identities

The following are independent versioned axes and may not be collapsed into `StrategyVersion`:

- `ParameterSetVersion`;
- `ExecutionPolicyVersion`;
- `ResearchPartitionPolicyVersion`;
- `DIKEPolicyVersion`;
- later `SizingPolicyVersion`;
- later context/news policy identities;
- dataset binding identities;
- engine/compiler/methodology identities.

These are shared DARWIN research contracts, not private implementation state of ATHENA or APOLLO.

---

## A-005.7 GC and XAUUSD are not equivalent

COMEX GC futures and OTC `XAU_USD` are distinct market/execution identities.

HMT-2 event truth must never be presented as XAUUSD execution truth.

GC research requires explicit governed identity for:

- GC market family;
- actual futures contract;
- event dataset/session;
- execution/economic semantics where economic results are claimed.

Continuous/rolled GC is a derived methodology and is deferred until a strategy genuinely requires it.

---

## A-005.8 Holdout governance becomes first-class

DARWIN must explicitly govern development/validation/protected-holdout roles.

ATHENA may not optimise on protected APOLLO holdout data.

APOLLO holdout access must be recorded.

Repeated use must remain visible because repeated exposure weakens independent evidentiary value.

---

## A-005.9 Cost and approximation doctrine

No hidden zero-cost default.

No silent approximation of unsupported fill timing.

No silent fallback from a requested execution semantic to another one.

Explicit idealised policies are allowed for engine tests but must be labelled as such.

Unsupported semantics fail closed as engine capability gaps.

---

## A-005.10 Programme consequence

The Product Constitution remains otherwise unchanged.

The first major milestone remains at least five independently promising XAUUSD strategies proven from DARWIN evidence.

HMT-2 adds a new research programme; it does not rewrite completed Foundation, ARENA, SCOUT, Specification, Workshop or MENDEL work.
