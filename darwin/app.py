"""DARWIN_core FastAPI application (PID-001 §24).

Minimal ASGI API — typed request/response contracts, health endpoints, and
enough read state for PID-002 ARENA to build on immediately. Not a custom
application framework; FastAPI is used directly.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from darwin.core.build import build_info
from darwin.core.config import DarwinConfig
from darwin.core.errors import DarwinError, to_error_response
from darwin.core.health import ComponentHealth, ComponentStatus, ReadinessReport
from darwin.core.logging import configure_logging
from darwin.hermes.reader import check_hermes_reachable
from darwin.research_store.db import check_postgres_reachable, connection
from darwin.research_store.migrations import migration_state
from darwin.research_store.repositories import (
    MarketDatasetRepository,
    ResearchRunRepository,
    SourceStrategyRepository,
    StrategyCandidateRepository,
    StrategyVersionRepository,
)

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "research_store" / "migrations_sql"


def create_app(config: DarwinConfig | None = None) -> FastAPI:
    cfg = config or DarwinConfig.load()
    configure_logging(cfg.log_level, cfg.build.commit)

    app = FastAPI(title="DARWIN Foundation", version=cfg.build.version)
    app.state.config = cfg

    @app.exception_handler(DarwinError)
    async def darwin_error_handler(_request, exc: DarwinError):
        status_code = 503 if exc.code in {"NOT_READY", "HERMES_UNAVAILABLE"} else 400
        return JSONResponse(status_code=status_code, content=to_error_response(exc))

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "OK"}

    @app.get("/api/v1/ready")
    def ready() -> dict:
        report = _readiness(cfg)
        if not report.ready:
            return JSONResponse(status_code=503, content=report.as_dict())
        return report.as_dict()

    @app.get("/api/v1/buildinfo")
    def buildinfo() -> dict:
        return build_info(cfg.build).as_dict()

    @app.get("/api/v1/system/summary")
    def system_summary() -> dict:
        report = _readiness(cfg)
        counts = {"source_strategies": 0, "strategy_candidates": 0, "strategy_versions": 0,
                  "market_datasets": 0, "research_runs": 0}
        pg_ok = any(c.name == "postgres" and c.status == ComponentStatus.OK for c in report.components)
        if pg_ok:
            try:
                with connection(cfg.postgres) as conn:
                    counts["source_strategies"] = SourceStrategyRepository(conn).count()
                    counts["strategy_candidates"] = StrategyCandidateRepository(conn).count()
                    counts["strategy_versions"] = StrategyVersionRepository(conn).count()
                    counts["market_datasets"] = MarketDatasetRepository(conn).count()
                    counts["research_runs"] = ResearchRunRepository(conn).count()
            except DarwinError:
                pass
        return {
            "build": build_info(cfg.build).as_dict(),
            "health": "OK",
            "readiness": report.as_dict(),
            "record_counts": counts,
        }

    @app.get("/api/v1/pipeline/summary")
    def pipeline_summary() -> dict:
        with connection(cfg.postgres) as conn:
            counts = StrategyCandidateRepository(conn).counts_by_stage()
        return {"counts_by_stage": counts}

    @app.get("/api/v1/datasets")
    def list_datasets(limit: int = 50) -> dict:
        with connection(cfg.postgres) as conn:
            items = MarketDatasetRepository(conn).list(limit=limit)
        return {"items": items}

    @app.get("/api/v1/datasets/{dataset_id}")
    def get_dataset(dataset_id: str) -> dict:
        with connection(cfg.postgres) as conn:
            item = MarketDatasetRepository(conn).get(dataset_id)
        if item is None:
            raise HTTPException(status_code=404, detail="dataset not found")
        return item

    @app.get("/api/v1/runs")
    def list_runs(limit: int = 50) -> dict:
        with connection(cfg.postgres) as conn:
            items = ResearchRunRepository(conn).list(limit=limit)
        return {"items": items}

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        with connection(cfg.postgres) as conn:
            item = ResearchRunRepository(conn).get(run_id)
        if item is None:
            raise HTTPException(status_code=404, detail="run not found")
        return item

    return app


def _readiness(cfg: DarwinConfig) -> ReadinessReport:
    pg_ok = check_postgres_reachable(cfg.postgres)
    components = [
        ComponentHealth(
            "postgres",
            ComponentStatus.OK if pg_ok else ComponentStatus.DOWN,
            "" if pg_ok else "DARWIN_sql unreachable",
        )
    ]

    if pg_ok:
        try:
            state = migration_state(cfg.postgres, MIGRATIONS_DIR)
            components.append(
                ComponentHealth(
                    "migrations",
                    ComponentStatus.OK if state["up_to_date"] else ComponentStatus.DEGRADED,
                    "" if state["up_to_date"] else f"pending: {state['pending']}",
                )
            )
        except Exception:  # noqa: BLE001 — readiness must never crash on a diagnostic
            components.append(ComponentHealth("migrations", ComponentStatus.DEGRADED, "state check failed"))

    hermes_ok = check_hermes_reachable(cfg.hermes)
    components.append(
        ComponentHealth(
            "hermes_adapter",
            ComponentStatus.OK if hermes_ok else ComponentStatus.DEGRADED,
            "" if hermes_ok else "HERMES unreachable — historical work degraded, HERMES itself unaffected",
        )
    )

    return ReadinessReport(components=tuple(components))


def app_for_uvicorn() -> FastAPI:
    """Entry point for `uvicorn darwin.app:app_for_uvicorn` style deployment.

    Deliberately not a bare module-level `app = create_app()`: that would
    call `DarwinConfig.load()` — which fails loudly on missing config — at
    *import* time, breaking any test or tool that imports this module without
    a fully configured environment. Tests use `create_app(config=...)`
    directly with an explicit, constructed config instead.
    """
    return create_app()
