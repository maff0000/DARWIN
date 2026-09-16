# Foundation API contract

All routes are versioned under `/api/v1`. All responses are JSON. Error
bodies are `{"error": {"code": "...", "message": "..."}}` — never a raw
stack trace, connection string, or credential.

| Method | Path | Purpose | Notes |
|---|---|---|---|
| GET | `/api/v1/health` | liveness | always `200 {"status":"OK"}` if the process is up |
| GET | `/api/v1/ready` | readiness | `200` when ready, `503` with the same body otherwise; never runs a large historical query |
| GET | `/api/v1/buildinfo` | build identity | version, commit, build time, environment |
| GET | `/api/v1/system/summary` | operator overview | build + readiness + record counts (for ARENA's Overview page) |
| GET | `/api/v1/pipeline/summary` | lifecycle counts | counts by `PipelineStage`, zero-filled |
| GET | `/api/v1/datasets` | list `MarketDataset` metadata | metadata/fingerprint only, never candle rows |
| GET | `/api/v1/datasets/{id}` | one dataset's metadata | 404 if not found |
| GET | `/api/v1/runs` | list research runs | generic run identity/status |
| GET | `/api/v1/runs/{id}` | one run | 404 if not found |

No mutation endpoint exists in Foundation. A dataset-load admin/test mutation
surface was considered (PID-001 §24) and deliberately not exposed as a public
API — use the `darwin dataset-load` CLI for controlled runtime proof instead.
