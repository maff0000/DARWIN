# Runtime proofs

These are deliberately **not** pytest-automated — PID-001 §31/§32 require
real disposable Docker Compose validation and a bounded real HERMES DEV
read-only proof, run manually (or by CI's `docker build` step for the image
build itself) rather than mocked in a unit test:

1. `docker compose up --build` — clean build, `darwin_sql` healthy, migrations
   apply, `darwin_core` becomes ready, API responds, restart `darwin_core`
   and confirm PostgreSQL state survived, clean teardown.
2. `darwin hermes-check` / `darwin dataset-load ...` against real HERMES DEV
   with the real `darwin_ro` principal — proves canonical SELECT, OHLCV/wick
   preservation, fingerprint repeatability (run twice, compare), and that no
   mutation is attempted anywhere in the path.

See the PR/evidence report for the actual commands run and their output for
this delivery.
