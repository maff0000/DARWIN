# DARWIN AMENDMENT A-006 — MARKET TRUTH PROFILES AND INSTRUMENT-SPECIFIC RESEARCH CAPABILITIES

**Parent authority:** `PID.md`  
**Product:** DARWIN  
**Date:** 2026-09-29  
**Status:** ARCHITECT AMENDMENT — LOCKED  
**DARWIN baseline observed:** `b0ff8b0e24d5c6a669403117f4f1cb33c6b094c3`

---

## A-006.1 Decision

DARWIN remains **one instrument-generic research/proof platform**.

DARWIN will **not**:

- create a separate research system merely because another instrument lacks GC-style information;
- make COMEX GC/HMT-2 a universal DARWIN dependency;
- weaken the GOLD research stack merely to make every edge portable;
- pretend that every instrument has an equivalent source of centralised microstructure truth.

Instead, instrument-specific research capability is governed through a **Market Truth Profile** concept (name may later be implemented exactly or by a semantically equivalent immutable contract).

The platform is generic.  
The available truth is market-specific.  
Strategies declare what truth they require.

---

## A-006.2 Market Truth Profile

A Market Truth Profile describes the governed research truth/capabilities available for a specific traded instrument or research market.

Conceptually it may identify:

- execution/traded instrument identity;
- native canonical candles;
- native tick/bid-ask evidence;
- native venue/order-book evidence where available;
- cross-market contextual inputs;
- event/microstructure datasets;
- supported research capability identifiers;
- exact dataset/authority identities and fingerprints required for reproducibility.

This amendment defines the architectural concept, not a new implementation package. Do not add a `MarketTruthProfile` class merely to satisfy this document before a concrete consumer requires it.

---

## A-006.3 Strategy applicability is capability-aware

A strategy or research configuration may require market-truth capabilities in addition to ordinary instrument applicability.

Examples of capability classes include:

- canonical candle causal replay;
- native tick/bid-ask replay;
- central-limit-order-book context;
- event-level sequencing;
- order-flow imbalance;
- auction/microstructure context.

A strategy requiring capability `X` is applicable only where the selected governed Market Truth Profile supplies capability `X`.

If a capability is unavailable:

> fail closed as not applicable / capability unavailable.

Never:

- fabricate an equivalent;
- silently substitute a weaker data source;
- degrade to candles without recording a methodology change;
- claim portability because the ticker or asset class looks similar.

---

## A-006.4 Three distinct truth relationships

DARWIN must distinguish:

### 1. Native-market truth

Truth belonging directly to the traded/researched instrument.

For `XAU_USD`, examples include governed XAUUSD candles, broker/OTC ticks and bid/ask where separately authorised.

### 2. Cross-market contextual truth

Truth from a different but related market used as explanatory/context evidence.

For the GOLD programme:

`COMEX GC -> contextual evidence for XAUUSD`

is allowed only when explicitly bound and tested.

Context truth is never silently promoted into execution truth.

### 3. Venue-specific microstructure truth

Centralised event/order-book evidence belonging to an actual venue/instrument contract.

HMT-2 GC MBP-1 belongs here for GC research.

These categories may coexist in one research configuration, but their identities and roles must remain explicit.

---

## A-006.5 GC / XAUUSD boundary

COMEX GC futures and OTC `XAU_USD` remain distinct market and execution identities, preserving Amendment A-005.

For GOLD:

```text
XAUUSD execution/traded market
        +
GC / COMEX centralised futures context
```

may become a powerful specialist research profile.

However:

- GC event truth is not XAUUSD execution truth;
- GC prices/fills may not be substituted for XAUUSD prices/fills;
- GC contract economics are not XAUUSD broker economics;
- any GC->XAUUSD contextual use must be explicitly declared as cross-market context;
- proof must identify exactly which XAUUSD and GC evidence was consumed.

---

## A-006.6 Portability is not a success criterion for an edge

DARWIN itself remains reusable across instruments.

A profitable/robust strategy family does **not** have to be reusable across instruments.

If a strategy's edge materially depends on GC microstructure, it may legitimately be:

> GOLD/XAUUSD specialist only.

Do not damage a proven specialist edge in pursuit of artificial instrument symmetry.

Likewise, another market may later require a completely different profile:

- crypto exchange order-book truth;
- equity exchange/venue truth;
- FX OTC/native broker truth;
- futures-specific contract/order-book truth.

Those become additional governed profiles/capabilities within DARWIN, not separate DARWIN systems.

---

## A-006.7 Evidence before live infrastructure

HMT-LIVE remains deferred until historical evidence demonstrates value.

The research sequence remains:

```text
XAUUSD candle causal core
        ↓
HMT-2 data usability
        ↓
governed actual-GC semantics/economics
        ↓
controlled GC event/microstructure value experiment
        ↓
if justified: GC-as-context contribution to XAUUSD
        ↓
only then reconsider HMT-LIVE
```

The controlled GC experiment must not confuse a cross-market difference with microstructure value. First establish event/microstructure value against the same governed GC contract/economics as required by A-005. Cross-market GC->XAUUSD contextual value is a later, separate experiment.

Negative evidence is a valid result.

If historical work shows little or no material value, do not build HMT-LIVE merely because HMT-2 exists.

---

## A-006.8 GOLD specialisation is explicitly permitted

If GC-enhanced GOLD research proves materially and robustly valuable, THE GOAL may deliberately prioritise or even restrict a strategy family to GOLD/XAUUSD.

That is not a failure of DARWIN's multi-instrument architecture.

The distinction is:

```text
DARWIN platform capability = multi-instrument
strategy/profile applicability = may be instrument-specific
```

A small number of deeply advantaged specialist strategies is preferable to forcing the same information architecture onto markets where the required truth does not exist.

---

## A-006.9 No second system

Adding a new instrument must not require a parallel research platform.

The intended architecture is:

```text
DARWIN
  |
  +-- shared strategy semantics / research contracts
  +-- APOLLO independent proof
  +-- ATHENA exploration/search
  |
  +-- Market Truth Profiles
        |
        +-- XAUUSD
        |     +-- native XAUUSD truth
        |     +-- optional GC contextual truth
        |
        +-- future instrument A
        |     +-- its own governed truth/capabilities
        |
        +-- future instrument B
              +-- its own governed truth/capabilities
```

Market-specific data adapters and capability implementations are permitted behind governed contracts.

A second DARWIN architecture is not.

---

## A-006.10 Research identity consequence

Research evidence must remain reproducible with enough identity to answer:

- which traded/researched instrument?
- which Market Truth Profile/capability set?
- which native input bindings?
- which contextual input bindings?
- which role did each input play?
- which exact dataset fingerprints/authority versions?
- which strategy, parameter set and execution policy?
- which engine/methodology versions?

Existing `ResearchInputBinding` / `ResearchConfiguration` work is directionally compatible: logical input roles and exact governed dataset fingerprints remain the foundation. A-006 does not require an immediate schema migration.

---

## A-006.11 Programme consequence

The first major DARWIN milestone remains unchanged:

> at least five independently promising XAUUSD strategies proven from DARWIN evidence.

A-006 changes the interpretation of multi-instrument architecture:

- **platform genericity is mandatory;**
- **edge portability is not.**

GC is a high-value candidate input for GOLD, not a template that other instruments must imitate.

No implementation work, migration or new class/package is authorised by A-006 itself.
