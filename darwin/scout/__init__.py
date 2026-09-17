"""DARWIN SCOUT -- PID-003 discovery module (docs/pids/PID-003-SCOUT.md).

`external source -> SOURCE_CLAIM -> discovery`, never `external source ->
DARWIN proof`. Implements Discovery only: no SPECIFICATION, HSA, strategy
execution/backtesting, ATHENA, APOLLO, DIKE evaluation, qualification, or
promotion exists in this module -- see the PID doc's exclusions list.

- `darwin.scout.domain` -- the constructor-enforced discovery/provenance
  domain model (Source, SourceDiscovery, SourceSnapshot, SourceClaim,
  DiscoveryRun, intake-status transitions).
- `darwin.scout.trader_dev_adapter` -- the bounded, read-only Trader.dev
  public-browse adapter.
- `darwin.scout.service` -- orchestration (idempotent ingest, manual
  discovery, intake transitions, SCOUT status).
"""
