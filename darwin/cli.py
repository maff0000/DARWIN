"""Foundation operator CLI (PID-001 §25). Bounded, supported commands only —
no general strategy-run CLI at this stage.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from darwin.core.config import ConfigError, DarwinConfig
from darwin.core.errors import DarwinError
from darwin.hermes.contract import Timeframe
from darwin.hermes.reader import check_hermes_reachable, load_market_dataset
from darwin.research_store.db import check_postgres_reachable, connection
from darwin.research_store.migrations import migration_state, run_migrations
from darwin.research_store.models import MarketDatasetRecord
from darwin.research_store.repositories import MarketDatasetRepository

MIGRATIONS_DIR = Path(__file__).resolve().parent / "research_store" / "migrations_sql"


def cmd_health(_args: argparse.Namespace) -> int:
    print(json.dumps({"status": "OK"}))
    return 0


def cmd_db_status(_args: argparse.Namespace) -> int:
    try:
        cfg = DarwinConfig.load()
    except ConfigError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    reachable = check_postgres_reachable(cfg.postgres)
    result = {"reachable": reachable}
    if reachable:
        result["migrations"] = migration_state(cfg.postgres, MIGRATIONS_DIR)
    print(json.dumps(result, default=str))
    return 0 if reachable else 1


def cmd_migrate(_args: argparse.Namespace) -> int:
    cfg = DarwinConfig.load()
    applied = run_migrations(cfg.postgres, MIGRATIONS_DIR)
    print(json.dumps({"applied": applied}))
    return 0


def cmd_hermes_check(_args: argparse.Namespace) -> int:
    cfg = DarwinConfig.load()
    reachable = check_hermes_reachable(cfg.hermes)
    print(json.dumps({"reachable": reachable}))
    return 0 if reachable else 1


def cmd_dataset_load(args: argparse.Namespace) -> int:
    cfg = DarwinConfig.load()
    try:
        timeframe = Timeframe(args.timeframe)
    except ValueError:
        print(json.dumps({"error": f"unsupported timeframe {args.timeframe!r}"}))
        return 2

    start = datetime.fromisoformat(args.frm).astimezone(UTC)
    end = datetime.fromisoformat(args.to).astimezone(UTC)

    try:
        dataset = load_market_dataset(
            cfg.hermes,
            instrument=args.instrument,
            timeframe=timeframe,
            start=start,
            end=end,
            adapter_build_version=cfg.build.version,
        )
    except DarwinError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}))
        return 1

    if args.persist:
        with connection(cfg.postgres) as conn:
            MarketDatasetRepository(conn).create(
                MarketDatasetRecord(
                    id=dataset.dataset_id,
                    instrument=dataset.instrument,
                    instrument_definition_id=dataset.instrument_definition_id,
                    timeframe=dataset.timeframe.value,
                    requested_start_utc=dataset.requested_start_utc,
                    requested_end_utc=dataset.requested_end_utc,
                    actual_first_open_utc=dataset.actual_first_open_utc,
                    actual_last_open_utc=dataset.actual_last_open_utc,
                    record_count=dataset.record_count,
                    fingerprint_sha256=dataset.fingerprint_sha256,
                    hermes_contract_version=dataset.hermes_contract_version,
                    hermes_contract_commit=dataset.hermes_contract_commit,
                    adapter_build_version=dataset.adapter_build_version,
                    gap_summary=dataset.gap_summary.as_dict(),
                    loaded_at_utc=dataset.loaded_at_utc,
                )
            )

    # Never print secrets — this is candle-count/fingerprint summary/evidence only.
    print(json.dumps(dataset.as_metadata_dict(), default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="darwin")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health").set_defaults(func=cmd_health)
    sub.add_parser("db-status").set_defaults(func=cmd_db_status)
    sub.add_parser("migrate").set_defaults(func=cmd_migrate)
    sub.add_parser("hermes-check").set_defaults(func=cmd_hermes_check)

    load_parser = sub.add_parser("dataset-load")
    load_parser.add_argument("--instrument", required=True)
    load_parser.add_argument("--timeframe", required=True, choices=[t.value for t in Timeframe])
    load_parser.add_argument("--from", dest="frm", required=True, help="ISO-8601 UTC, inclusive")
    load_parser.add_argument("--to", required=True, help="ISO-8601 UTC, exclusive")
    load_parser.add_argument("--persist", action="store_true", help="persist dataset metadata to DARWIN_sql")
    load_parser.set_defaults(func=cmd_dataset_load)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        sys.exit(args.func(args))
    except ConfigError as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(2)


if __name__ == "__main__":
    main()
