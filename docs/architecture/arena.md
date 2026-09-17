# ARENA

## Serving route

ARENA is served from `/`, not `/arena`. Chosen deliberately (PID-002 §5):
at this stage ARENA *is* the whole DARWIN application shell — there is no
other product surface at `/` for it to share space with, and no PID-002
requirement calls for a sub-route. If DARWIN later needs `/` for something
else (an API landing page, a future multi-app split), that would be an
explicit architectural decision at that time, not assumed here.

## Runtime model

- `frontend/` is a Vite + React + TypeScript source tree, built at Docker
  image build time only (`npm ci && npm run build`), never at runtime.
- The build output (`frontend/dist/`) is copied into `darwin/static/` inside
  the image. No Node runtime exists in the production container — the final
  image stage is the same `python:3.12-slim` base Foundation already uses,
  with the frontend as static files alongside the Python package.
- `darwin.app._mount_arena()` mounts `darwin/static/assets` at `/assets`
  (Vite's asset directory) and serves `darwin/static/index.html` for every
  other non-`/api/...` path — a standard SPA fallback so client-side routes
  like `/datasets/<id>` work on a hard refresh.
- If `darwin/static/` doesn't exist (e.g. a bare API-only dev run, or a test
  fixture that never built a frontend), ARENA simply isn't mounted; the API
  is unaffected. This is a legitimate non-production mode, not an error.

## API boundary

ARENA's browser code talks only to `/api/v1/...`. It never connects to
PostgreSQL or HERMES directly (PID-002 §12). Two narrow read-only endpoints
were added specifically because no existing endpoint could serve the
requirement:

- `GET /api/v1/instrument-definitions` / `/{instrument_id}` — the governed
  `InstrumentDefinition` (base/quote asset, unit, version, fingerprint).
  `market_datasets`/`research_runs` only carry `instrument_definition_id`
  (a fingerprint); ARENA needs the underlying semantic fields to render unit
  meaning (e.g. "XAU_USD → USD per troy ounce") without hardcoding any
  instrument.
- `GET /api/v1/migrations` — the structured applied/pending migration list.
  `/ready`'s `migrations` component only carries a summary OK/DEGRADED
  status, not the version lists ARENA's Migrations page needs.

Neither endpoint, nor anything else added for PID-002, performs a write.
