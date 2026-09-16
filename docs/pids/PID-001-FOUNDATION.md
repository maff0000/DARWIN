# PID-001 — DARWIN FOUNDATION

**Parent authority:** `PID.md`  
**Product:** DARWIN  
**Module/work package:** Foundation  
**Status:** APPROVED FOR IMPLEMENTATION  
**Version:** 0.1.0  
**Date:** 2026-09-16  
**Implementation owner:** FORGE under ROGUE  
**Infrastructure owner:** HELM outside FORGE

---

## 1. Purpose

PID-001 establishes the smallest robust substrate on which all later DARWIN modules can be built.

Foundation must prove:

- DARWIN is Docker-first;
- DARWIN has a clean modular application skeleton;
- DARWIN has durable SQL-backed control/evidence persistence;
- DARWIN can read canonical HERMES historical XAUUSD candles using its least-privilege read-only principal;
- DARWIN can validate/canonicalise a bounded historical range into an immutable in-memory `MarketDataset`;
- common identity/evidence/lifecycle primitives exist without prematurely modelling the entire future product;
- health/readiness/logging/configuration/migrations/tests/CI exist;
- enough API/read state exists for PID-002 ARENA to immediately become useful;
- DARWIN failure cannot modify or impair HERMES/live trading.

Foundation does **not** implement strategy discovery, strategy logic, optimisation or sequential trade proof.

---

## 2. Acceptance outcome

PID-001 is complete only when a clean checkout can build and run:

```text
DARWIN_core
DARWIN_sql
```

and prove through automated + runtime evidence that:

1. both containers start from declared Docker/Compose configuration;
2. `DARWIN_core` becomes healthy/read-ready only when its own mandatory dependencies are ready;
3. PostgreSQL migrations initialise the DARWIN schema cleanly;
4. a bounded XAU_USD HERMES range can be loaded through `darwin_ro` into an immutable `MarketDataset`;
5. exact OHLCV, timestamps and required HERMES provenance are preserved;
6. wick highs/lows survive the complete adapter/dataset path unchanged;
7. malformed/non-canonical input is rejected;
8. a dataset fingerprint is deterministic for identical canonical input;
9. product metadata can be persisted/retrieved;
10. Foundation API exposes system/build/health and minimal pipeline/read-model state for ARENA;
11. no HERMES write is possible from normal DARWIN credentials;
12. stopping/removing DARWIN has no effect on HERMES or live trading;
13. no Redis is required for Foundation;
14. the branch passes CI and disposable runtime validation.

---

## 3. Explicit boundaries

### Foundation owns

- repository/application skeleton;
- core configuration;
- external secret-loading pattern;
- structured logging;
- build/version identity;
- health/readiness;
- Docker image;
- Compose runtime;
- PostgreSQL runtime/migrations;
- minimum shared domain identities/contracts;
- HERMES historical read adapter;
- `MarketDataset`;
- minimum persistence repositories;
- minimum API required for operational visibility and PID-002;
- tests/CI/security baseline.

### Foundation does not own

- Trader.dev integration;
- SCOUT discovery;
- HSA absorption/specification workflow;
- strategy evaluation;
- ATHENA optimisation;
- APOLLO trade simulation/proof;
- qualification thresholds;
- scheduler/continuous factory;
- CER/HELIOS/PLUTUS integrations;
- production live-trading controls;
- HERMES remediation/derivation;
- independent H4/D1 derivation.

---

## 4. Repository/module skeleton

Proposed Foundation tree:

```text
/srv/DARWIN
├── PID.md
├── MEMORY.md
├── README.md
├── pyproject.toml
├── uv.lock / equivalent reproducible lock
├── .gitignore
├── .dockerignore
├── .env.example
├── compose.yaml
├── Dockerfile
├── migrations/
│   └── ...
├── docs/
│   ├── pids/
│   │   └── PID-001-FOUNDATION.md
│   ├── architecture/
│   │   ├── foundation.md
│   │   └── market-dataset.md
│   └── contracts/
│       └── api-foundation.md
├── darwin/
│   ├── __init__.py
│   ├── app.py
│   ├── core/
│   │   ├── config.py
│   │   ├── errors.py
│   │   ├── logging.py
│   │   ├── health.py
│   │   ├── build.py
│   │   ├── identities.py
│   │   ├── lifecycle.py
│   │   └── evidence.py
│   ├── hermes/
│   │   ├── contract.py
│   │   ├── reader.py
│   │   ├── validation.py
│   │   └── dataset.py
│   ├── research_store/
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── migrations.py
│   ├── scout/
│   │   └── __init__.py
│   ├── specification/
│   │   └── __init__.py
│   ├── athena/
│   │   └── __init__.py
│   ├── apollo/
│   │   └── __init__.py
│   ├── qualification/
│   │   └── __init__.py
│   ├── arena/
│   │   └── __init__.py
│   ├── scheduler/
│   │   └── __init__.py
│   └── integrations/
│       └── __init__.py
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   ├── runtime/
│   └── fixtures/
└── .github/
    └── workflows/
        └── ci.yml
```

Empty module packages are acceptable only to establish clear boundaries; do not create speculative implementations behind them.

If FORGE has a simpler package layout that preserves these boundaries, it may propose it, but it must not collapse HERMES/data access, persistence and future strategy engines into an undifferentiated package.

---

## 5. Technology baseline

### Language/runtime

Python 3.12+ unless a proven dependency constraint requires another supported version.

### API

A small ASGI API is appropriate; FastAPI is acceptable for Foundation because it provides typed request/response contracts, health endpoints and later ARENA API growth without requiring a custom framework.

Do not build a custom application framework.

### DARWIN SQL

Use PostgreSQL in container `DARWIN_sql`.

Preferred supported version: PostgreSQL 16 unless current platform constraints require a later/compatible maintained version.

Use an explicit migration tool. Alembic is acceptable.

### HERMES access

Use a minimal MariaDB client boundary against the versioned HERMES SQL contract.

PyMySQL or an equivalently small DB-API driver is acceptable.

Do not introduce ORM coupling to HERMES.

### In-memory MarketDataset

Use a compact immutable columnar representation suitable for later high-speed iteration.

NumPy is acceptable and preferred for Foundation's first implementation if it keeps the representation simple and testable.

Do not use Python object-per-candle as the only canonical hot-path representation if it creates avoidable memory/iteration overhead.

### Redis

Not present in PID-001.

---

## 6. Container topology

Foundation runtime:

```text
DARWIN_core
DARWIN_sql
```

### `DARWIN_core`

Contains the application/API and Foundation modules.

It must be built from the repository Dockerfile and run as a non-root user where practical.

### `DARWIN_sql`

PostgreSQL persistence.

Data persisted to a named volume/external volume appropriate to the platform.

### Network

Use a DARWIN-specific Docker network for internal communication.

HERMES historical access is external/read-only.

Do not embed HERMES host/IP in source.

### Ports

Expose only what is operationally required.

Database exposure to the host should be avoided unless required for administration; internal Compose networking should be preferred.

---

## 7. Configuration model

Configuration is external and validated at startup.

At minimum separate:

- application/runtime config;
- PostgreSQL connection config;
- HERMES read connection config;
- secret references;
- logging;
- build/runtime mode.

Requirements:

- no host-specific defaults that silently point to real infrastructure;
- no embedded credentials;
- missing required config fails loudly;
- test config is isolated;
- production-like runtime config is not committed.

A typed configuration object should be created once at startup rather than reading environment variables throughout business logic.

### Secret handling

Secrets must be supplied externally.

For persistent deployment, mounted/read-only secret files are preferred.

The application may support an explicit `*_FILE` pattern or equivalent.

DARWIN may know the deployment reference for its own `darwin_ro` credential, but no root/admin secret path may enter project memory/source.

Never log secret values.

---

## 8. Build identity

Every running `DARWIN_core` must expose:

- application version;
- Git commit SHA where supplied at build time;
- build timestamp or immutable build identity;
- environment/runtime label.

This must be visible through a build-info endpoint and structured logs.

The image used for persistent deployment must be traceable to a tested Git commit.

---

## 9. Logging

Use structured logging.

Required contextual fields where relevant:

- timestamp UTC;
- level;
- service;
- build/commit;
- event name;
- correlation/request ID;
- research run ID when later available;
- dataset ID/fingerprint when relevant;
- error code/class.

Do not log:

- credentials;
- connection passwords;
- full secret paths if operational policy treats them as sensitive;
- source payloads containing credentials/tokens.

Foundation should not introduce a separate log aggregation platform.

---

## 10. Health and readiness

Expose at least:

- `/health`
- `/ready`
- `/buildinfo`

### `/health`

Answers whether the application process is alive and internally functioning.

### `/ready`

Answers whether DARWIN can perform Foundation responsibilities.

Readiness should include:

- DARWIN SQL connectivity/migration state;
- configuration validity;
- HERMES historical reader configuration presence and a lightweight safe contract/readiness check where configured.

Readiness must not execute large historical queries.

### Failure semantics

HERMES unavailable:

- DARWIN readiness may be degraded/not-ready for historical work;
- HERMES itself is unaffected;
- DARWIN must not retry in a destructive/tight-loop way.

PostgreSQL unavailable:

- DARWIN cannot accept work requiring persistence;
- fail clearly;
- do not fall back to undocumented local files as substitute truth.

---

## 11. HERMES historical contract

Foundation consumes the existing HERMES v1 SQL contract.

Canonical HERMES repository:

`github.com/maff0000/hermes`

Canonical contract commit:

`3f90e640c9c9c1f4a22ba4ac586a1d478f35a997`

Principal:

`darwin_ro`

Allowed objects only:

- `canonical_candles_m1`
- `canonical_candles_m5`
- `canonical_candles_m15`
- `canonical_candles_h1`
- `canonical_candles_h4`
- `canonical_candles_d1`
- `canonical_candles`

DARWIN must not query legacy/base candle tables.

The adapter should map timeframe to an allowlisted per-timeframe object and use the unified object only where a use case genuinely benefits from it.

No runtime-supplied arbitrary table name is permitted.

---

## 12. Historical adapter API

Foundation should expose an internal interface conceptually equivalent to:

```python
load_market_dataset(
    instrument: InstrumentId,
    timeframe: Timeframe,
    start: datetime,
    end: datetime,
) -> MarketDataset
```

Contract:

- `start` inclusive;
- `end` exclusive;
- UTC only;
- bounded range mandatory;
- timeframe allowlisted;
- instrument validated;
- ordered ascending by candle open time;
- one bulk/range query, not row-by-row queries;
- no writes;
- no hidden timeframe derivation.

The adapter may stream/fetch in driver-efficient batches internally if required for memory safety, but produces one immutable dataset for the requested workload.

---

## 13. Canonical query shape

Prefer per-timeframe object:

```sql
SELECT
    instrument,
    timeframe,
    open_time,
    open,
    high,
    low,
    close,
    volume,
    is_closed,
    status,
    source_timeframe,
    derivation_policy,
    source_policy_epoch,
    source_count,
    expected_source_count,
    source_coverage,
    gap_state,
    derivation_run_id,
    derivation_generated_at_utc,
    created_at
FROM <ALLOWLISTED_CANONICAL_OBJECT>
WHERE instrument = %s
  AND open_time >= %s
  AND open_time < %s
ORDER BY open_time ASC
```

The actual selected provenance columns may be adjusted only if the HERMES contract differs; Foundation must preserve enough provenance to validate/reproduce the input.

All values must be parameterised except the table/view identifier, which must come from a fixed internal timeframe→object mapping.

---

## 14. Canonical row validation

Every loaded row must be validated against the HERMES contract.

At minimum reject:

- unsupported timeframe;
- incorrect returned timeframe;
- incorrect instrument;
- non-closed row;
- non-`OK` status;
- `source_coverage != 1.0000`;
- non-`NONE` gap state in an exposed row;
- duplicate `(instrument,timeframe,open_time)`;
- non-monotonic timestamps;
- malformed OHLC values;
- negative/invalid volume;
- impossible OHLC relationships such as `high < low`, `high < open/close`, `low > open/close`;
- timestamps outside requested bounds;
- unexpected nulls in required semantic fields.

HERMES contract-documented nullable provenance fields such as M15 creation timestamps must not be incorrectly rejected.

Missing expected candle timestamps are gaps, not malformed rows. Detect/report gaps separately.

---

## 15. Exact OHLCV preservation and price representation

Foundation must preserve HERMES price precision and wick highs/lows.

Recommended in-memory canonical representation:

- timestamps: UTC `int64` epoch units with explicit documented scale;
- OHLC: fixed-point `int64` scaled from HERMES `DECIMAL(12,5)` by `100000`;
- volume: integer type sufficient for contract values;
- provenance metadata: immutable compact structures/arrays as appropriate.

Reasons:

- exact equality/fingerprint stability;
- deterministic level-touch comparisons;
- avoids binary floating-point changing a five-decimal canonical market fact;
- fast contiguous in-memory representation.

Downstream engines may derive float/vector views for indicators if required, but raw canonical OHLC must remain recoverable/exact.

Do not discard `high` or `low`.

---

## 16. MarketDataset contract

Minimum immutable structure:

### Identity/metadata

- `dataset_id` — DARWIN-generated immutable identity;
- `instrument`;
- `timeframe`;
- `requested_start_utc`;
- `requested_end_utc`;
- `actual_first_open_utc` if non-empty;
- `actual_last_open_utc` if non-empty;
- `record_count`;
- `hermes_contract_version`;
- `hermes_contract_commit/reference`;
- `fingerprint_sha256`;
- `loaded_at_utc`;
- adapter/build identity.

### Candle columns

- `open_time`;
- `open`;
- `high`;
- `low`;
- `close`;
- `volume`.

### Provenance

Preserve the canonical derivation/provenance facts necessary to show whether rows are direct or derived and under what policy epoch.

The dataset object and its underlying arrays/collections must be immutable from the consumer perspective.

If NumPy is used, mark arrays non-writeable.

---

## 17. Dataset fingerprint

Foundation must produce a deterministic SHA-256 fingerprint for identical canonical input.

The fingerprint must not depend on:

- load timestamp;
- Python object identity;
- DB row surrogate IDs;
- `derivation_run_id` if HERMES explicitly defines it as non-identity provenance that may differ while canonical candle content remains identical;
- machine/host.

It should include enough canonical semantic content to detect market-data changes, including:

- instrument;
- timeframe;
- ordered open timestamps;
- exact OHLCV;
- relevant canonical policy/source semantics where they affect the meaning of the series.

Document the canonical serialisation used for hashing.

Two independent loads of unchanged HERMES rows for the same range must produce the same fingerprint.

---

## 18. Gap detection

Foundation should calculate gap metadata appropriate to the requested timeframe/grid.

Requirements:

- never fabricate missing rows;
- never forward-fill;
- never interpolate;
- report detected missing expected opens;
- distinguish weekend/market-closed expectations only if HERMES contract/time-grid authority makes that deterministic; otherwise report raw expected-grid gaps without inventing a trading-calendar doctrine.

The dataset remains usable or rejected according to later experiment/specification policy, not a universal Foundation rule, unless the canonical HERMES row contract itself is violated.

---

## 19. Memory-first workload contract

Foundation must make it structurally natural for later engines to reuse the loaded dataset.

The adapter is not an iterator that performs SQL per candle.

ATHENA/APOLLO must receive a fully materialised `MarketDataset` (or a clearly equivalent immutable in-memory object) and operate without further HERMES queries during the inner loop.

Later work may add a dataset cache keyed by fingerprint/range if measurements justify it.

PID-001 does not require a Redis/cache service.

---

## 20. Core domain concepts

Introduce only the minimum stable concepts needed across modules.

### `SourceStrategy`

Represents an externally/internal discovered strategy source identity/provenance shell.

Foundation fields should be minimal; no Trader.dev-specific metrics required yet.

### `StrategyCandidate`

DARWIN candidate identity associated with source provenance.

No trading-rule implementation in PID-001.

### `StrategyVersion`

Immutable candidate version identity.

Foundation proves version identity/persistence, not strategy semantics.

### `MarketDataset`

As specified above.

### `ResearchRun`

Identity and reproducibility envelope for a future DARWIN experiment.

Foundation fields may include:

- run ID;
- result kind/evidence level;
- candidate/version references if present;
- dataset reference if present;
- engine/module;
- build version;
- configuration fingerprint;
- status;
- timestamps.

Do not add ATHENA/APOLLO-specific result schemas yet.

### `EvidenceLevel` / `ResultKind`

At minimum reserve canonical semantics for:

- `SOURCE_CLAIM`;
- `ATHENA_RESULT`;
- `APOLLO_PROOF`;
- `PLUTUS_RESULT`.

Foundation may persist enum/reference values even though only generic Foundation runs exist.

### `PipelineStage`

At minimum:

- `DISCOVERED`;
- `SPECIFIED`;
- `ATHENA_TESTED`;
- `ATHENA_QUALIFIED`;
- `APOLLO_PROVEN`;
- `PROMISING`.

Foundation does not implement stage-transition business rules beyond basic validation/storage.

---

## 21. Identity strategy

Use application-generated opaque stable IDs.

UUIDv7 is preferred if the chosen library/runtime support is straightforward; UUIDv4 is acceptable if avoiding an unnecessary dependency.

Do not encode business meaning into IDs.

Human-readable source/candidate names are attributes, not canonical identity.

Strategy version should be an explicit version identifier associated with immutable candidate content; exact semantic-version mechanics can be refined in PID-004 with HSA reuse, but Foundation storage must not make later immutable versioning impossible.

---

## 22. PostgreSQL schema scope

PID-001 should create only the tables needed to prove Foundation.

Suggested minimum:

### `source_strategies`

- id;
- source type;
- external/source reference;
- title/name;
- provenance metadata JSON where minimal flexibility is useful;
- created_at_utc;
- updated_at_utc.

### `strategy_candidates`

- id;
- source_strategy_id nullable where internal;
- title/name;
- current pipeline stage;
- created_at_utc;
- updated_at_utc.

### `strategy_versions`

- id;
- candidate_id;
- version label;
- specification fingerprint/reference placeholder;
- immutable marker/state;
- created_at_utc.

No full specification body is required in PID-001 unless needed to prove version persistence.

### `market_datasets`

Persist dataset metadata/fingerprint, not necessarily all candle rows.

DARWIN must not duplicate HERMES market history into PostgreSQL.

Fields:

- id;
- instrument;
- timeframe;
- requested/actual bounds;
- record_count;
- fingerprint;
- HERMES contract reference;
- adapter/build reference;
- gap summary metadata;
- created/loaded timestamp.

### `research_runs`

Generic run identity/status/reproducibility metadata.

### `evidence_records`

Small generic evidence index/reference table if needed for later extension.

Do not create large ATHENA result/trade ledger tables in Foundation.

### Migration metadata

Managed by the chosen migration tool.

---

## 23. Timestamps

UTC everywhere.

Application timestamps must be timezone-aware.

PostgreSQL timestamps should use `timestamptz` where semantically applicable.

HERMES MariaDB `open_time` is naive-by-storage but UTC-by-contract; the adapter must attach/interpret UTC explicitly without local-time conversion.

No system-local timezone assumptions.

---

## 24. API substrate for ARENA

Foundation must expose enough read-only API state that PID-002 can immediately build a useful GUI.

Suggested Foundation endpoints:

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/buildinfo`
- `GET /api/v1/system/summary`
- `GET /api/v1/pipeline/summary`
- `GET /api/v1/datasets`
- `GET /api/v1/datasets/{id}`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{id}`

Optional Foundation-only test/admin endpoint for loading a dataset should not automatically become a public production API. Prefer an internal service/CLI for controlled runtime proof unless PID review authorises an API mutation surface.

`system/summary` should be able to expose at least:

- build version;
- service health;
- DB status;
- HERMES adapter status;
- counts of persisted source/candidate/version/dataset/run records.

`pipeline/summary` should expose counts by `PipelineStage` even if initially zero.

---

## 25. Foundation CLI / operator proof

Provide a small supported CLI or management command to perform bounded Foundation operations without relying on ad-hoc Python snippets.

At minimum:

```text
darwin health
darwin db-status
darwin hermes-check
darwin dataset-load --instrument XAU_USD --timeframe H1 --from ... --to ...
```

`dataset-load` should:

- use the configured HERMES adapter;
- validate rows;
- create an immutable MarketDataset;
- calculate fingerprint/gap summary;
- persist dataset metadata;
- print only non-secret summary/evidence.

Do not create a general strategy-run CLI yet.

---

## 26. Research persistence repositories

Application code should use explicit repository abstractions for its own PostgreSQL persistence.

Do not leak ORM/session objects throughout business logic.

Foundation should have clear repository/service boundaries for:

- source strategy metadata;
- candidates;
- versions;
- dataset metadata;
- research runs.

Keep abstractions practical. Do not build a generic enterprise repository framework.

---

## 27. Migration/versioning approach

All PostgreSQL schema changes occur through versioned migrations committed to Git.

Requirements:

- fresh empty DB migration proof;
- upgrade from previous Foundation migration within the branch as needed;
- deterministic migration ordering;
- failure exits non-zero;
- migration state exposed in readiness/build diagnostics.

Runtime application should not silently create random tables with ORM `create_all` as the production migration mechanism.

---

## 28. Tests

### Unit tests

Cover:

- config validation;
- identity validation;
- enums/result kinds;
- HERMES row validation;
- fixed-point conversion;
- OHLC invariants;
- wick high/low preservation;
- UTC conversion;
- dataset immutability;
- fingerprint determinism;
- gap detection;
- lifecycle-stage representation.

### Contract tests

Use fixtures matching HERMES v1 canonical contract.

Test:

- direct rows;
- H4 derived rows;
- D1 derived rows;
- M15 nullable provenance timestamps;
- malformed rows;
- duplicate rows;
- non-OK/non-closed rows;
- ordering violations.

### Integration tests

Run against disposable PostgreSQL.

Run HERMES adapter integration against a disposable/fake MariaDB fixture/schema that reproduces the canonical contract where CI cannot reach DEV.

No CI dependency on live HERMES.

### Runtime DEV proof

Separately, on `dell-debian`, prove a read using real `darwin_ro` against real HERMES canonical views.

Read-only only.

### Failure tests

Prove:

- wrong/missing HERMES secret → clear failure;
- write attempt is not part of adapter API;
- invalid timeframe cannot select arbitrary tables;
- PostgreSQL down → readiness failure;
- HERMES down → historical readiness degraded without affecting HERMES/live systems.

---

## 29. Security tests

At minimum:

- secret scanning in CI;
- no committed `.env`/secret files;
- HERMES query table mapping is allowlisted;
- query values parameterised;
- API input validation;
- no raw exception/credential disclosure;
- Docker non-root check where applicable;
- dependency vulnerability/static checks that are lightweight and maintainable.

Do not create security theatre that significantly slows every build without actionable value.

---

## 30. CI gate

CI should run on PRs and main.

Minimum gate:

1. formatting/lint;
2. type/static checks where adopted;
3. unit tests;
4. contract tests;
5. disposable PostgreSQL integration tests;
6. container image build;
7. migration-on-empty-DB proof;
8. security/secret scan;
9. `git diff --check` equivalent hygiene.

The CI workflow must not require live HERMES credentials.

---

## 31. Docker validation

A disposable Foundation validation must prove:

1. clean build;
2. `DARWIN_sql` starts;
3. migrations apply;
4. `DARWIN_core` starts;
5. readiness goes green in fixture/test mode;
6. API endpoints respond;
7. DB persistence survives core restart;
8. clean teardown.

Persistent deployment to `/srv/DARWIN` occurs only after the tested image/commit is accepted.

---

## 32. Real HERMES DEV runtime proof

After disposable proof, execute a bounded read-only DEV integration.

Use:

- principal `darwin_ro`;
- XAU_USD;
- a small deterministic period;
- at least H1;
- and at least one governed derived timeframe (H4 or D1).

Prove:

- canonical SELECT succeeds;
- rows validate;
- OHLCV preserved;
- high/low preserved;
- provenance captured;
- MarketDataset immutable;
- fingerprint stable on repeated load;
- no mutation attempted;
- PostgreSQL stores only dataset metadata, not candle history.

Do not run ATHENA/APOLLO.

---

## 33. Observability

Foundation metrics/log events should include at minimum:

- service start/build;
- migration state;
- HERMES readiness;
- dataset load requested/completed/failed;
- dataset rows loaded;
- load duration;
- validation failures;
- gap count;
- dataset fingerprint/id;
- PostgreSQL operation failures.

No Prometheus/Grafana stack is required by PID-001 unless already platform-standard and effectively free to integrate.

Structured application observability plus API state is sufficient.

---

## 34. Performance baseline

Foundation must record baseline MarketDataset loading numbers during real HERMES proof:

- timeframe;
- requested interval;
- row count;
- SQL fetch duration;
- canonicalisation/validation duration;
- fingerprint duration;
- total load duration;
- peak/estimated dataset memory footprint.

This is a baseline, not a performance optimisation contest.

No premature caching layer.

The key invariant is that later strategy evaluation runs from RAM rather than re-querying SQL.

---

## 35. Failure isolation proof

Explicitly prove:

### DARWIN stopped

- HERMES remains healthy;
- no live trading dependency is affected.

### HERMES unavailable

- DARWIN cannot load new MarketDataset;
- DARWIN reports degraded/not-ready historical capability;
- existing persisted DARWIN metadata remains intact;
- no write/recovery attempt is made against HERMES.

### DARWIN SQL unavailable

- DARWIN reports not ready for persisted work;
- no fallback writes to HERMES/local ad-hoc files.

No Foundation component may require HELIOS or live trading services to be available.

---

## 36. Backup/recovery foundation

Foundation must document:

- PostgreSQL volume/data location;
- minimum backup command/procedure owned by platform operations;
- restore expectation;
- which data is authoritative vs regenerable.

At PID-001 stage:

- Git = source/product authority;
- HERMES = market-history authority;
- PostgreSQL = DARWIN control/evidence metadata authority;
- MarketDataset candle arrays are regenerable from HERMES if only metadata/fingerprint is persisted.

Do not implement an elaborate backup platform inside DARWIN.

---

## 37. README requirements

Foundation README must explain:

- product purpose;
- architecture boundary;
- local/disposable startup;
- persistent deployment concept;
- configuration variables/secret references without values;
- migrations;
- health endpoints;
- Foundation CLI;
- HERMES read-only boundary;
- test commands;
- explicit statement that no strategy engine exists yet.

A fresh engineer/agent should not need chat context to run Foundation safely.

---

## 38. Architecture documentation

Create concise docs covering:

### `docs/architecture/foundation.md`

- container topology;
- module responsibilities;
- persistence;
- failure isolation;
- deployment flow.

### `docs/architecture/market-dataset.md`

- HERMES contract reference;
- exact in-memory representation;
- fixed-point price semantics;
- immutability;
- fingerprint;
- gap semantics;
- wick high/low requirement;
- no SQL inner-loop invariant.

Do not duplicate large chunks of PID prose unnecessarily; document implementation facts.

---

## 39. ARENA handoff

PID-001 must leave PID-002 with:

- working API;
- health/build state;
- persisted counts/state;
- datasets/runs read endpoints;
- stable IDs;
- enough operational read models to render an Overview page immediately.

Foundation should not implement the polished ARENA UI itself beyond any minimal developer diagnostic page required for proof.

---

## 40. Redis gate

`DARWIN_redis` must not exist in Foundation Compose.

A later PID may introduce Redis only with a specific requirement such as:

- cross-process job dispatch;
- transient progress/event fan-out;
- measured cache need;
- near-real-time GUI coordination that PostgreSQL/application memory cannot reasonably satisfy.

The decision must be evidence-driven.

---

## 41. Explicit non-goals

PID-001 must not implement:

- Trader.dev;
- web scraping/MCP source discovery;
- strategy rules;
- HSA ingestion;
- ATHENA;
- APOLLO;
- trade ledger;
- qualification logic;
- scheduling;
- worker farm;
- Redis;
- ClickHouse/Kafka/Elastic;
- HERMES candle derivation;
- HERMES schema changes;
- HELIOS/CER/PLUTUS integration;
- live trading;
- generic microservice framework.

---

## 42. Required implementation evidence

ROGUE must return:

- branch name;
- commit SHA;
- changed-file inventory;
- migration inventory;
- test count/results;
- CI result/run;
- Docker build result;
- image identity/digest if available;
- disposable Compose proof;
- real HERMES read-only proof;
- MarketDataset fingerprint repeatability proof;
- wick high/low preservation proof;
- PostgreSQL persistence/restart proof;
- failure-isolation proof;
- known limitations;
- working-tree status;
- independent audit result if required by ROGUE/FORGE governance.

"Implemented" or "looks good" is not acceptance evidence.

---

## 43. Acceptance gate

PID-001 verdict may be:

`FOUNDATION_GREEN`

only when all required acceptance evidence is present and no open defect violates a parent-PID invariant.

Otherwise return a precise blocked/red verdict, for example:

`BLOCKED_FOUNDATION_HERMES_CONTRACT_MISMATCH`

or:

`FOUNDATION_RED_MARKETDATASET_MUTABLE`

Do not weaken the PID to make a failing implementation green.

---

## 44. Post-acceptance

After PID-001 is merged/deployed GREEN:

1. freeze the Foundation contract sufficiently for consumers;
2. create/finalise `PID-002-ARENA.md`;
3. build ARENA operational shell;
4. do not jump directly to ATHENA/APOLLO just because the data substrate now exists.

One bounded capability at a time.
