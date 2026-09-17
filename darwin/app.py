"""DARWIN_core FastAPI application (PID-001 §24).

Minimal ASGI API — typed request/response contracts, health endpoints, and
enough read state for PID-002 ARENA to build on immediately. Not a custom
application framework; FastAPI is used directly.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from darwin.core.build import build_info
from darwin.core.config import DarwinConfig
from darwin.core.errors import DarwinError, NotReadyError, to_error_response
from darwin.core.health import ComponentHealth, ComponentStatus, ReadinessReport
from darwin.core.logging import configure_logging
from darwin.hermes.instrument_definition import (
    UnknownInstrumentDefinitionError,
    get_instrument_definition,
    list_instrument_definitions,
)
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

# ARENA static production bundle (PID-002 §5) — built at Docker image build
# time from ./frontend, packaged here. No Node runtime exists in production;
# this directory either exists (persistent/Docker deployment) or doesn't
# (plain `uvicorn` dev run against the API only) — both are valid.
STATIC_DIR = Path(__file__).resolve().parent / "static"


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
        if report.ready:
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
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            counts = StrategyCandidateRepository(conn).counts_by_stage()
        return {"counts_by_stage": counts}

    @app.get("/api/v1/datasets")
    def list_datasets(limit: int = 50) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            items = MarketDatasetRepository(conn).list(limit=limit)
        return {"items": items}

    @app.get("/api/v1/datasets/{dataset_id}")
    def get_dataset(dataset_id: str) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            item = MarketDatasetRepository(conn).get(dataset_id)
        if item is None:
            raise HTTPException(status_code=404, detail="dataset not found")
        return item

    @app.get("/api/v1/runs")
    def list_runs(limit: int = 50) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            items = ResearchRunRepository(conn).list(limit=limit)
        return {"items": items}

    @app.get("/api/v1/runs/{run_id}")
    def get_run(run_id: str) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            item = ResearchRunRepository(conn).get(run_id)
        if item is None:
            raise HTTPException(status_code=404, detail="run not found")
        return item

    @app.get("/api/v1/instrument-definitions")
    def list_instrument_definitions_endpoint() -> dict:
        """Read-only governed InstrumentDefinition registry (PID-002 §12) — the
        existing dataset/run APIs only carry `instrument_definition_id`
        (a fingerprint); ARENA needs the underlying semantic fields
        (base/quote asset, unit) to render unit meaning without hardcoding
        any instrument. No existing endpoint can serve this."""
        return {"items": [_instrument_definition_dict(d) for d in list_instrument_definitions()]}

    @app.get("/api/v1/instrument-definitions/{instrument_id}")
    def get_instrument_definition_endpoint(instrument_id: str) -> dict:
        try:
            definition = get_instrument_definition(instrument_id)
        except UnknownInstrumentDefinitionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _instrument_definition_dict(definition)

    @app.get("/api/v1/migrations")
    def migrations_endpoint() -> dict:
        """Structured read-only migration state (PID-002 §12) — /ready only
        exposes a summary OK/DEGRADED status for the "migrations" component,
        not the applied/pending version lists ARENA's Migrations page needs.
        No migration-execution path exists here or anywhere in ARENA."""
        return migration_state(cfg.postgres, MIGRATIONS_DIR)

    _mount_arena(app)

    return app


def _mount_arena(app: FastAPI) -> None:
    """Serve the ARENA static bundle from `/` (PID-002 §5 — deliberately `/`,
    not `/arena`, since ARENA is the whole application shell at this stage;
    documented in docs/architecture/arena.md). A missing STATIC_DIR (e.g. a
    bare API-only dev run) is not an error — ARENA simply isn't served, the
    API still works, and this function does nothing rather than fail loudly
    for a legitimate non-production run mode.
    """
    if not STATIC_DIR.is_dir():
        return

    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="arena-assets")

    index_path = STATIC_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def arena_spa(full_path: str):
        # Never intercept the API surface — FastAPI already matches literal
        # /api/v1/... routes above this catch-all with higher priority, but
        # this guard makes the boundary explicit rather than relying on
        # registration order alone.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        if not index_path.is_file():
            raise HTTPException(status_code=404, detail="ARENA bundle not built")
        return FileResponse(index_path)


def _instrument_definition_dict(d) -> dict:
    return {
        "instrument_id": d.instrument_id,
        "base_asset": d.base_asset,
        "quote_asset": d.quote_asset,
        "base_quantity_unit": d.base_quantity_unit,
        "price_unit": d.price_unit,
        "definition_version": d.definition_version,
        "fingerprint": d.fingerprint,
    }


def _ensure_ready_for_data(report: ReadinessReport) -> None:
    """Guard for endpoints that serve DARWIN's own persisted data.

    Postgres/migrations not being OK means the underlying tables may not
    exist yet — querying them would surface a raw, unhandled DB exception
    as a 500. Fail loudly and cleanly instead (PID-001 §7/§10): a 503 with
    an explicit NOT_READY code, never a bare traceback.
    """
    if not report.ready:
        blocking_detail = ", ".join(
            f"{c.name}={c.status.value}" for c in report.components if c.blocking and c.status != ComponentStatus.OK
        )
        raise NotReadyError(f"DARWIN is not ready to serve persisted data: {blocking_detail}")


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
            blocking=False,
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
