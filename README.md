# DARWIN

DARWIN is a continuously operating, multi-instrument research appliance that
discovers, normalises, optimises, independently proves and qualifies trading
strategies for any canonical instrument HERMES makes available. XAUUSD is
the first programme milestone and initial proving market, not a product
boundary (Amendment A-001). It is a research/incubation side-chain — it does not place live
trades and is not on the live capital-control path. See [`PID.md`](PID.md)
for the full product constitution.

**No strategy engine exists yet.** This is PID-001 Foundation only: the
substrate (Docker runtime, PostgreSQL persistence, a read-only HERMES
historical adapter, and the immutable in-memory `MarketDataset`) that later
modules (SCOUT, specification, ATHENA, APOLLO, qualification, ARENA) build on.
See [`docs/pids/PID-001-FOUNDATION.md`](docs/pids/PID-001-FOUNDATION.md).

## Architecture boundary

```text
HERMES canonical SQL (read-only, darwin_ro)
        |
DARWIN read-only adapter (darwin/hermes/)
        |
canonical validation
        |
immutable MarketDataset (in RAM)
        |
(future) ATHENA / APOLLO computation
        |
DARWIN_sql (PostgreSQL) — control/evidence metadata only
```

DARWIN never writes to HERMES, never derives its own H4/D1 history, and never
duplicates HERMES candle history into PostgreSQL — see
[`docs/architecture/market-dataset.md`](docs/architecture/market-dataset.md).

## Local / disposable startup

Requires Docker and Docker Compose.

```sh
cp .env.example .env                 # edit values for your environment
mkdir -p secrets
echo -n '<darwin_ro password>' > secrets/darwin_ro_credential_DO_NOT_COMMIT.txt
chmod 600 secrets/darwin_ro_credential_DO_NOT_COMMIT.txt

export DARWIN_HERMES_HOST=<hermes host>   # required, no default is baked in
docker compose up --build
```

`darwin_core` will not become ready until `darwin_sql` is healthy and its own
migrations are applied. HERMES being unreachable degrades *historical* work
only — it never blocks the health/control-plane endpoints and never affects
HERMES or live trading (PID-001 §35).

## Persistent deployment concept

There is one persistent DARWIN environment (currently `dell-debian:/srv/DARWIN`).
The deployment flow is: branch → CI/tests → disposable Docker validation →
merge → build/tag the exact tested image → deploy that exact image → runtime
proof → rollback if required. Application source never hard-codes a hostname,
IP address, or filesystem path as a semantic dependency — all of that is
deployment wiring, supplied externally.

## Configuration / secrets

See [`.env.example`](.env.example) for the full list of variables — no values,
only names and shapes. Secrets are supplied either as an inline environment
variable (disposable/dev only) or a mounted `*_FILE` path (preferred for
persistent deployment); the application fails loudly if a required value is
missing, and never logs a secret value.

## Migrations

```sh
darwin migrate         # applies migrations/*.sql in filename order
darwin db-status       # reports connectivity + which migrations are applied/pending
```

Runtime application code never uses ORM `create_all` as a migration mechanism.

## Health endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | process alive |
| `GET /api/v1/ready` | can DARWIN perform Foundation responsibilities right now |
| `GET /api/v1/buildinfo` | version / commit / build time / environment |
| `GET /api/v1/system/summary` | build + health + record counts |
| `GET /api/v1/pipeline/summary` | candidate counts by lifecycle stage |
| `GET /api/v1/datasets`, `/datasets/{id}` | persisted MarketDataset metadata |
| `GET /api/v1/runs`, `/runs/{id}` | persisted research run metadata |

## Foundation CLI

```sh
darwin health
darwin db-status
darwin hermes-check
darwin dataset-load --instrument XAU_USD --timeframe H1 --from 2026-09-01T00:00:00+00:00 --to 2026-09-02T00:00:00+00:00 [--persist]
```

`dataset-load` prints only a non-secret summary (record count, fingerprint,
gap summary) — never candle data or credentials.

## Tests

```sh
pip install -e '.[dev]'
pytest tests/unit tests/contract                       # no external services required
DARWIN_TEST_PG_DSN=postgresql://... pytest -m integration   # disposable PostgreSQL required
```

Real HERMES DEV proof (bounded, read-only, run manually — never part of CI,
never dependent on live credentials being available in CI):

```sh
darwin hermes-check
darwin dataset-load --instrument XAU_USD --timeframe H1 --from ... --to ...
```
