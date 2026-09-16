# Foundation architecture

## Container topology

- `darwin_core` — the application/API (FastAPI) and all Foundation modules. Built from the repo `Dockerfile`, runs as a non-root user.
- `darwin_sql` — PostgreSQL 16, control/evidence/research metadata only. Named volume for persistence.
- No `darwin_redis` in Foundation. A later PID may introduce it only against a demonstrated requirement (job dispatch, event fan-out, measured cache need) — never by default.

Both containers run on a dedicated `darwin_net` Docker network. HERMES access is external and read-only; database ports are not exposed as public APIs.

## Module responsibilities (implemented this PID)

- `darwin/core/` — configuration, errors, logging, health/readiness, build identity, identities, lifecycle stages, evidence levels. Deliberately small.
- `darwin/hermes/` — the read-only HERMES adapter: `contract.py` (closed timeframe→object mapping, allowed instruments, contract version/commit), `reader.py` (one bulk parameterised query per load, readiness probe), `validation.py` (canonical row validation), `dataset.py` (fixed-point conversion, immutable `MarketDataset`, deterministic fingerprint, gap detection).
- `darwin/research_store/` — `db.py` (connection management), `models.py` (plain dataclasses, no ORM leakage), `repositories.py` (explicit per-table repositories), `migrations.py` (minimal explicit SQL migration runner).
- `darwin/app.py` — FastAPI wiring for health/ready/buildinfo/system-summary/pipeline-summary/datasets/runs.
- `darwin/cli.py` — `darwin health|db-status|migrate|hermes-check|dataset-load`.
- `darwin/{scout,specification,athena,apollo,qualification,arena,scheduler,integrations}/` — empty placeholder packages establishing module boundaries only. No implementation. See `PID.md` §5 for their eventual scope.

## Persistence

`darwin_sql` stores: `source_strategies`, `strategy_candidates`, `strategy_versions`, `market_datasets` (metadata/fingerprint, never candle rows), `research_runs`, `evidence_records`. Schema changes only via versioned files in `migrations/`, tracked in `schema_migrations`.

## Failure isolation

- DARWIN stopped → HERMES and live trading are unaffected (DARWIN has no write path into either).
- HERMES unreachable → `/api/v1/ready` reports the `hermes_adapter` component `DEGRADED`, historical work (dataset loads) fails loudly; DARWIN does not retry destructively, does not fall back to a substitute data source, and does not affect HERMES.
- PostgreSQL unreachable → readiness reports `postgres` `DOWN`, DARWIN refuses persistence-dependent work; no fallback writes to ad-hoc local files or to HERMES.

## Deployment flow

branch → CI (lint/tests/contract tests/disposable Postgres integration/image build/migration-on-empty-DB proof/secret scan) → disposable Docker Compose validation → merge → build/tag the exact tested image → deploy that exact image to the one persistent DARWIN environment → runtime proof → rollback if required.
