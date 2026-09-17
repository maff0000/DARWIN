# PID-002 — DARWIN ARENA

**Parent authority:** `PID.md`, closed PID-001 Foundation (`docs/pids/PID-001-FOUNDATION.md`), Amendments A-001/A-002/A-003/A-004R1  
**Product:** DARWIN  
**Module/work package:** ARENA (application shell + Foundation read surface)  
**Status:** APPROVED FOR IMPLEMENTATION  
**Version:** 0.1.0  
**Date:** 2026-09-17  
**Implementation owner:** FORGE under ROGUE  
**Infrastructure owner:** HELM outside FORGE  
**Canonical starting point:** `main = 8f1d74018328369c1deb45b4ca883a51fa97ea3a`  
**Presentation target:** `PRESENTATION_POLISHED` — this PID declares a first-class institutional research application, not merely a usable interface. Forge's mandatory real-browser verification gate applies in full; source-only review is never sufficient for acceptance.

---

## 1. Purpose

ARENA is DARWIN's first-class visual operating surface — not a temporary admin page. It is the GUI spine into which later DARWIN capabilities progressively land:

```text
ARENA → SCOUT → SPECIFICATION → ATHENA(+DIKE) → APOLLO(+DIKE) → QUALIFICATION → CONTINUOUS FACTORY
```

PID-002 establishes a professional, coherent, extensible application shell and exposes the real Foundation state already available. The first release is primarily **READ / OBSERVE / DRILL DOWN**, not mutation/control.

A human must be able to open DARWIN in a browser and immediately understand: what build is running; whether DARWIN itself is healthy; whether PostgreSQL/migrations are healthy; whether HERMES historical access is healthy/degraded; what datasets DARWIN knows about; what research runs exist; what instrument/timeframe each belongs to; what the market units mean; what evidence class a result belongs to; whether DIKE was disabled or guarded; what pipeline state currently exists; what is degraded or wrong. No SSH or SQL should be required for ordinary operational inspection.

Foundation does not implement strategy discovery, strategy logic, optimisation, or sequential trade proof (PID-001 §1) — ARENA does not implement or imply any of that either.

---

## 2. Non-goals — explicit

PID-002 does NOT:

- place trades;
- mutate HERMES;
- implement SCOUT, ATHENA, APOLLO, DIKE evaluation, qualification, TRON, NEO, or SOCRATES;
- implement account/broker execution or authentication (unless an existing authoritative mechanism already exists, which it does not);
- expose secrets, DB connection information, or secret filesystem paths;
- add unnecessary write endpoints — read-only, narrowly-justified additions only;
- alter PID-001 Foundation semantics;
- fabricate/mock data of any kind in the production build or in browser acceptance tests;
- present empty SCOUT/ATHENA/APOLLO/QUALIFICATION pages merely because they will exist later.

No production secret value may enter the frontend bundle.

---

## 3. Build capabilities

Before implementation, use the strongest available capabilities for product design, frontend architecture (React + TypeScript), responsive web design, UI/UX, accessibility, semantic HTML, browser automation, Playwright/E2E testing, visual/screenshot review, frontend performance, and secure frontend/API integration. This is a product-design deliverable, not backend engineering styling a few HTML tables. The Claude Code `frontend-design` skill's guidance (design plan → critique against the brief → build → self-critique with screenshots) governs the visual design process — see §4.

The design receives an explicit visual-quality review (§19) before Auditor acceptance.

---

## 4. Visual / product character

**Institutional research application.** Modern, dark-first, precise, calm, high information density without clutter, excellent typography, strong hierarchy, professional, research/operations oriented.

Avoid: generic Bootstrap admin appearance; giant empty cards; excessive gradients; neon crypto-casino styling; decorative charts with no real data; fake financial metrics; meaningless animations; dashboard clutter for its own sake; the generic AI-design tells (warm cream + terracotta, near-black + single acid accent, broadsheet hairlines, identical SaaS cards with one shadow/radius everywhere, tracked-out ALL-CAPS eyebrows, middle-dot metadata strings, `→` on every link). Use animation only when it improves comprehension — one deliberate moment beats scattered hover/fade effects everywhere.

Fingerprints, SHAs, IDs, and timestamps: abbreviated for scanning, full value accessible, copy action where useful, monospace where appropriate. All times shown by ARENA are explicitly UTC unless a later governed domain object explicitly defines another timezone.

The implementer must run the frontend-design skill's two-pass process: (1) a compact token system (color: 4–6 named hex values; type: typefaces and roles; layout: concept + ASCII wireframes + alignment guidance; principles) reviewed against this brief for genericness before any code is written, then (2) build, screenshotting and self-critiquing along the way.

---

## 5. Frontend architecture

React + TypeScript + Vite (or an equivalent lightweight production build), accessible component primitives, a small coherent DARWIN design system.

```text
frontend source
    ↓ build-time
static production bundle
    ↓
packaged into DARWIN_core image
    ↓
served by existing FastAPI product
```

Node/tooling exists at build time only — **no Node runtime/container in production.** Persistent services remain exactly `DARWIN_core` + `DARWIN_sql`, no Redis, no separate ARENA container unless real evidence demonstrates a requirement and the Architect approves it separately (not authorised by this PID).

API remains under `/api/v1/...`. ARENA is served from `/` (chosen deliberately over a `/arena` sub-route, since ARENA is the whole application shell, not one feature within a larger product at this stage) — document this choice in `docs/architecture/`.

---

## 6. Application shell

### Left-hand primary navigation

Persistent, collapsible left rail on desktop. This is the core application navigation, not the top bar. Initial structure:

```text
Core
  Overview
Market Data
  Datasets
Research
  Research Runs
  Evidence
Pipeline
  Pipeline
System
  System Status
  HERMES
  Migrations
```

Do not expose empty SCOUT/ATHENA/APOLLO/QUALIFICATION pages now. The navigation architecture must let those sections (eventually: `Overview, SCOUT, Specification, Datasets, ATHENA, APOLLO, Qualification, Evidence, Pipeline, System`) land later without redesigning the shell.

### Top utility bar

Not primary navigation — a restrained global/utility area: current environment, global DARWIN health indicator, build/version, short commit SHA, repository/docs links where appropriate, Account/Profile, appearance/theme control if worthwhile. Include a **View Account** affordance — but since no real account/profile authority exists yet, its unavailable/not-configured state must be explicit rather than a fabricated user profile. No authentication is implemented by this PID.

---

## 7. Overview page

Landing page answers: "What is DARWIN doing and is it healthy?" Real data only.

- **System summary:** build/version, commit SHA, runtime status, PostgreSQL state, migration state, HERMES adapter state.
- **Operational state:** clear OK/DEGRADED/DOWN semantics, a prominent degraded-state banner where appropriate, component-specific explanation rather than a generic red light.
- **Foundation counts:** real current counts of source strategies, strategy candidates, strategy versions, MarketDatasets, ResearchRuns. Zero is valid — show `0`, never manufacture activity.
- **Recent activity:** recent datasets and ResearchRuns where real data exists; a deliberately designed, useful empty state otherwise.

---

## 8. Market dataset browser

Datasets are first-class objects. List/table supports scanning/filtering by instrument, timeframe, date/range, record count, gap state where available, loaded time. Every row exposes: dataset identity, instrument, timeframe, bounded interval, record count, fingerprint, instrument-definition identity, HERMES provenance, load time. Clicking a row opens a detail view.

**Dataset detail** exposes real Foundation facts: Dataset ID; `InstrumentId`; the governed `InstrumentDefinition` (base asset, quote asset, base quantity unit, price unit, definition version/fingerprint); timeframe; requested interval; actual first/last candle; record count; dataset fingerprint; HERMES contract/version/commit; adapter/build identity; gaps; loaded timestamp.

For `XAU_USD` the UI must make `XAU_USD price → USD per troy ounce` understandable — sourced from the governed `InstrumentDefinition` model, never an XAU-specific frontend constant. A-001 remains authoritative; the GUI stays instrument-generic.

---

## 9. ResearchRun / evidence browser

`ResearchRun` is a first-class object. List/table supports filtering by instrument, timeframe, status, ResultKind/EvidenceLevel, engine, DIKE state, date. Shows at minimum: display title, run ID, candidate/version where present, instrument, timeframe, ResultKind/EvidenceLevel, engine, status, DIKE state, created timestamp.

**Run detail** exposes: full run identity; candidate/version; bound `MarketDataset` with drill-through; instrument; `InstrumentDefinition` identity; timeframe; engine; build version; configuration fingerprint; ResultKind/EvidenceLevel; status; timestamps.

**DIKE panel:** clearly distinguishes `DIKE_DISABLED` from `DIKE_GUARDED`. Guarded runs show policy id, policy version, policy fingerprint. Never imply Foundation is evaluating DIKE — ARENA displays immutable run identity only (PID-001 §1d).

### Evidence language — durable design requirement

The evidence vocabulary must not let later modules visually blur fundamentally different evidence classes. Canonical hierarchy and required visual/semantic treatment, stable across every later ARENA expansion:

- **`SOURCE_CLAIM`** — external claim, not DARWIN proof. Must be unmistakable (e.g. "External claim" / "Source claim — not independently proven by DARWIN").
- **`ATHENA_RESULT`** — historical optimisation/search result, not independent proof.
- **`APOLLO_PROOF`** — independent sequential proof of a frozen candidate.
- **`PLUTUS_RESULT`** — future forward/demo evidence.
- **`LIVE`** — future real-world/live evidence.

No single generic "performance" badge may make a source leaderboard metric look equivalent to APOLLO evidence. A user looking at a metric must be able to answer "where did this number come from?" without opening source code.

---

## 10. Pipeline page

Real `pipeline/summary` counts by canonical stage (`DISCOVERED → SPECIFIED → ATHENA_TESTED → ATHENA_QUALIFIED → APOLLO_PROVEN → PROMISING`). Zero counts are fine — do not invent progress. The GUI must not imply `PROMISING` means approved for live capital (PID.md §9.6).

---

## 11. System area

- **System Status:** build, process health, readiness, component states, record counts.
- **HERMES:** DARWIN's adapter/dependency view only — reachable/degraded, the read-only historical-authority relationship, canonical contract identity where available. Not a HERMES administration panel. No HERMES mutations.
- **Migrations:** read-only state answering current migrations, applied, pending, up-to-date. If Foundation lacks a safe read API for exact migration state, add the narrowest read-only API necessary (§12). No migration-execution button in ARENA v1.

---

## 12. API rule

Use real DARWIN APIs and real persistence only. Foundation already exposes `/api/v1/health`, `/ready`, `/buildinfo`, `/system/summary`, `/pipeline/summary`, `/datasets`, `/datasets/{id}`, `/runs`, `/runs/{id}` — reuse them; do not create duplicate frontend-specific business truth. The browser must never connect directly to PostgreSQL or HERMES.

Narrow read-only API additions are authorised only when the real ARENA requirement cannot be served correctly by existing Foundation APIs. Likely justified: a full migration-state read model; a governed `InstrumentDefinition` read model. No generic mutation APIs.

---

## 13. Real data only

No fake/demo strategy results, no mocked leaderboard, no fake equity curve, no fake APOLLO proof, no synthetic P&L cards, no screenshot-only prototype presented as acceptance. Production ARENA displays only real Foundation API/persistence state. Automated tests may construct isolated fixtures in disposable infrastructure, but browser acceptance exercises the real FastAPI/API/repository path — never frontend-mocked API responses.

---

## 14. Empty and degraded states

Empty states (zero source strategies, zero candidates, zero ATHENA runs, zero APOLLO proofs) must look intentional — explain what the object is and why nothing exists yet. Do not populate with sample financial data to avoid whitespace.

Degraded/error behaviour matters as much as the happy path. Prove visually and behaviourally: HERMES degraded; PostgreSQL unavailable; migrations pending/degraded; API unavailable; empty data; missing dataset/run; unknown/error response. The GUI must remain understandable, identify the affected dependency, distinguish blocking vs non-blocking degradation, avoid raw stack traces, and avoid a misleading stale "green" state. HERMES-degraded must reflect Foundation's own established semantics: DARWIN's control plane may remain `READY` while historical work is `DEGRADED` (PID-001 §10, the readiness-defect fix).

---

## 15. Responsiveness / accessibility

Desktop is the primary operational target — design for a serious workstation display around 1280–1920px width, with sensible behaviour at narrower widths. Required: keyboard navigability; logical focus states; semantic tables/forms; accessible labels; accessible status communication; sufficient contrast; no meaning conveyed by colour alone; reduced-motion respect where relevant. Aim at WCAG AA quality.

---

## 16. Quality and testing

Frontend unit/component tests where valuable; real API contract tests; browser E2E tests (Playwright or equivalent). Acceptance browser tests run against the real ARENA bundle → real `DARWIN_core` → real API → disposable PostgreSQL, never mocked HTTP responses. At minimum prove:

1. ARENA loads.
2. Build SHA shown correctly.
3. System health/readiness shown correctly.
4. HERMES degraded state renders correctly.
5. Dataset list renders a real persisted dataset.
6. Dataset detail renders instrument/timeframe/unit semantics/fingerprint.
7. ResearchRun list renders a real persisted run.
8. Run detail renders evidence level.
9. `DIKE_DISABLED` renders correctly.
10. `DIKE_GUARDED` renders policy identity correctly.
11. Instrument/timeframe filters do not assume XAUUSD.
12. Evidence classes are visually/semantically distinct.
13. Empty states are correct.
14. API failure produces controlled UI.
15. Primary left navigation works.
16. Top utility navigation works.

Screenshot/visual inspection of all primary routes is required. Tests passing does not constitute acceptance on its own — the GUI must actually be looked at (§19).

---

## 17. Design review gate

Before Auditor acceptance, Rogue conducts a visual/product review at minimum desktop widths, asking: does this look like a serious research product; is hierarchy immediately obvious; is the left navigation excellent; is the top utility bar restrained; can the system be understood in five seconds; is any screen pretending data exists when it does not; can `SOURCE_CLAIM` be distinguished from DARWIN-produced evidence instantly; are long SHAs/fingerprints handled elegantly; are tables readable; are detail pages information-rich without looking like JSON dumps; does degraded state look intentionally designed; will ATHENA/APOLLO fit naturally into this shell later. A materially "no" on any of these means refine before audit.

---

## 18. Progressive expansion contract

PID-002 establishes the shell, not the ultimate ARENA. Later modules add capability progressively (SCOUT: source explorer/candidate intake/provenance/source claims; SPECIFICATION: strategy definition/version/deterministic rules/search ranges/ambiguity; ATHENA: optimisation runs/search-space views/heatmaps/parameter stability/plateaus; APOLLO: proof summary/equity/drawdown/ledger/trade drill-down/wick-intrabar decisions/DIKE decisions; QUALIFICATION: candidate comparison/promotion gates/leaderboard; PLUTUS/LIVE: forward/live evidence comparison). None of these are implemented by PID-002 — only the architectural slots and design language that let them arrive without a GUI replacement.

---

## 19. Current programme milestone — unchanged

DARWIN's first programme milestone remains at least five independently promising XAUUSD strategies discovered, normalised, optimised, and sequentially proven using canonical HERMES historical authority (PID.md §2). ARENA is the control/observability spine that helps reach and understand that milestone — it does not replace it.

---

## 20. Security / boundaries

Restated from §2 for the acceptance gate: no trading, no HERMES mutation, no SCOUT/ATHENA/APOLLO/DIKE-evaluation/qualification/TRON/NEO/SOCRATES implementation, no account/broker execution or authentication, no secret/DB-connection/secret-path exposure, no unnecessary write endpoints, no production secret value in the frontend bundle.

---

## 21. Delivery structure (bounded work sequence)

- **WI-1 — ARENA product shell / design system:** frontend build architecture; left nav; top utility bar; routing; typography/layout; status/evidence design language; empty/error/degraded patterns.
- **WI-2 — Foundation read integration:** system overview; health/readiness; build; counts; minimal missing read APIs only.
- **WI-3 — Dataset experience:** list/filter; detail; instrument semantics; provenance/fingerprint.
- **WI-4 — ResearchRun / evidence experience:** list/filter; detail; EvidenceLevel treatment; DIKE state/policy identity.
- **WI-5 — Pipeline / system operational views:** pipeline; HERMES; migrations; degraded behaviour.
- **WI-6 — Hardening:** accessibility; browser E2E; visual review; responsive behaviour; security; production packaging; Docker proof.
- **WI-7 — Independent Auditor:** fresh independent Auditor against the exact proposed merge head. No self-certification.

---

## 22. Required implementation evidence

Rogue returns: branch; exact head SHA; PR; files changed; frontend stack; production serving architecture; runtime/container impact; any Foundation read-only API additions; primary routes; left-navigation structure; top-bar structure; evidence-language implementation; multi-instrument proof; dataset proof; ResearchRun proof; DIKE rendering proof; degraded-state proof; accessibility evidence; browser/E2E test evidence; full backend + frontend test totals; CI exact-head result; screenshots/visual-review evidence; independent Auditor verdict; any genuine limitations. "Implemented" or "looks good" is not acceptance evidence.

---

## 23. Acceptance gate

PID-002 verdict may be `GREEN_DARWIN_PID002_ARENA_READY_FOR_ARCHITECT_REVIEW` only when all required evidence is present, the design review (§17) has been conducted and passed, the independent Auditor has confirmed the delta with genuine live browser verification (per this PID's `PRESENTATION_POLISHED` target), and no open defect violates a PID-001/A-001/A-002/A-003/A-004R1 invariant. Otherwise return a precise blocked/red verdict. Do not weaken this PID to make a failing implementation pass. This PID is not merged by Rogue — it returns to the Architect for acceptance, same as PID-001.
