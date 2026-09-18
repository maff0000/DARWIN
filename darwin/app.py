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
from pydantic import BaseModel, Field

from darwin.core.build import build_info
from darwin.core.config import DarwinConfig
from darwin.core.errors import DarwinError, NotReadyError, to_error_response
from darwin.core.health import ComponentHealth, ComponentStatus, ReadinessReport
from darwin.core.identities import new_id
from darwin.core.logging import configure_logging
from darwin.hermes.instrument_definition import (
    UnknownInstrumentDefinitionError,
    get_instrument_definition,
    list_instrument_definitions,
)
from darwin.hermes.reader import check_hermes_reachable
from darwin.research_store.db import check_postgres_reachable, connection
from darwin.research_store.migrations import migration_state
from darwin.research_store.models import StrategyCandidate
from darwin.research_store.repositories import (
    MarketDatasetRepository,
    ResearchRunRepository,
    ScoutDiscoveryRepository,
    ScoutDiscoveryRunRepository,
    ScoutSnapshotRepository,
    ScoutSourceRepository,
    SourceStrategyRepository,
    StrategyCandidateRepository,
    StrategyVersionRepository,
)
from darwin.research_store.specification_repositories import (
    SpecificationVersionRepository,
)
from darwin.scout import service as scout_service
from darwin.scout.domain import IntakeStatus, OriginKind
from darwin.scout.service import MAX_RECORDS_PER_RUN, ScoutRequestError
from darwin.scout.trader_dev_adapter import ALLOWED_SORTS as SCOUT_ALLOWED_SORTS
from darwin.specification.serialization import deserialize_strategy_version
from darwin.workshop.api import register_mendel_routes, register_workshop_routes

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "research_store" / "migrations_sql"

# ARENA static production bundle (PID-002 §5) — built at Docker image build
# time from ./frontend, packaged here. No Node runtime exists in production;
# this directory either exists (persistent/Docker deployment) or doesn't
# (plain `uvicorn` dev run against the API only) — both are valid.
STATIC_DIR = Path(__file__).resolve().parent / "static"


# --- PID-003 SCOUT request models ---------------------------------------
#
# Deliberately module-level, not nested inside create_app(): this file uses
# `from __future__ import annotations` (PEP 563 deferred evaluation), and
# FastAPI resolves a route's string annotations via `typing.get_type_hints`
# against the endpoint function's `__globals__` only -- a Pydantic model
# defined as a local inside create_app() is reachable at call time via
# closure, but NOT via __globals__, so FastAPI would silently fail to
# recognise it as a request-body model (observed directly: it degraded to
# an unresolvable "query" parameter named "body", a false 422 on every
# request). Every request-body model in this file must stay module-level.


class ScoutDiscoverRequest(BaseModel):
    """Bounded on-demand discovery run (PID-003 sec6). No raw URL parameter
    exists here or anywhere in SCOUT -- only these deliberately narrow,
    sensible filters."""

    symbol: str | None = None
    max_records: int = Field(default=25, ge=1, le=MAX_RECORDS_PER_RUN)
    sort: str = "recent"


class ScoutManualDiscoveryRequest(BaseModel):
    """Human-typed manual entry (Amendment 2026-09-17, PID-003 sec10) -- a
    SEPARATE concern from /scout/discover: no adapter is ever called, no
    fetch of any URL is ever triggered by this endpoint."""

    origin_kind: OriginKind
    title: str = Field(min_length=1)
    origin_description: str | None = None
    origin_url: str | None = None
    source_symbol: str | None = None
    source_timeframe: str | None = None
    original_description: str | None = None
    pasted_rule_text: str | None = None
    personal_notes: str | None = None
    tags: tuple[str, ...] = ()
    claimed_metrics: dict | None = None


class ScoutIntakeStatusRequest(BaseModel):
    """Narrow, explicit allowed-transition request (PID-003 sec6). No
    generic patch-everything endpoint exists anywhere in SCOUT."""

    target_status: IntakeStatus
    changed_by: str = Field(min_length=1)
    reason: str | None = None


class CandidateOpenRequest(BaseModel):
    """PID-004B Workshop UI enablement (genuine backend gap found while
    building ARENA's Workshop page -- see migration 0010's own docstring):
    there was no endpoint anywhere capable of creating a StrategyCandidate.
    Idempotent per `origin_discovery_id` when one is given (mirrors
    `/api/v1/workshops`'s own idempotent-per-candidate open) -- a repeated
    call for the SAME discovery always resolves to the same candidate,
    never a duplicate. `origin_discovery_id=None` creates a bare candidate
    with no discovery origin (PID-004 sec4.2 permits this; never idempotent
    in that case, since there is nothing to key idempotency on)."""

    title: str = Field(min_length=1)
    origin_discovery_id: str | None = None


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

    # --- PID-003 SCOUT: discovery API surface (docs/pids/PID-003-SCOUT.md sec6) ---

    @app.get("/api/v1/scout/status")
    def scout_status_endpoint() -> dict:
        """Source reachability/last-run summary, SCOUT-scoped. Deliberately
        NEVER calls `_ensure_ready_for_data`/`_readiness` -- a Trader.dev
        outage (or even a not-yet-migrated DARWIN_sql) must never make this
        endpoint fail, and must never be folded into `/api/v1/ready`
        (PID-003 sec5: "source unavailability degrades SCOUT's own status
        only, never DARWIN core readiness/health")."""
        try:
            pg_ok = check_postgres_reachable(cfg.postgres)
        except Exception:  # noqa: BLE001 - status must never itself fail
            pg_ok = False
        if not pg_ok:
            return scout_service.scout_status(None)
        with connection(cfg.postgres) as conn:
            return scout_service.scout_status(conn)

    @app.get("/api/v1/scout/sources")
    def scout_sources_endpoint() -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            return {"items": ScoutSourceRepository(conn).list()}

    @app.get("/api/v1/scout/discovery-runs")
    def scout_discovery_runs_endpoint(limit: int = 50) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            return {"items": ScoutDiscoveryRunRepository(conn).list(limit=limit)}

    @app.get("/api/v1/scout/discovery-runs/{run_id}")
    def scout_discovery_run_detail_endpoint(run_id: str) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            item = ScoutDiscoveryRunRepository(conn).get(run_id)
        if item is None:
            raise HTTPException(status_code=404, detail="discovery run not found")
        return item

    @app.get("/api/v1/scout/discoveries")
    def scout_discoveries_endpoint(
        symbol: str | None = None,
        intake_status: str | None = None,
        origin_kind: str | None = None,
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            repo = ScoutDiscoveryRepository(conn)
            items = repo.list(
                symbol=symbol, intake_status=intake_status, origin_kind=origin_kind,
                sort=sort, limit=limit, offset=offset,
            )
            counts_by_intake_status = repo.counts_by_intake_status()
        return {"items": items, "counts_by_intake_status": counts_by_intake_status}

    @app.get("/api/v1/scout/discoveries/{discovery_id}")
    def scout_discovery_detail_endpoint(discovery_id: str) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            discovery_repo = ScoutDiscoveryRepository(conn)
            item = discovery_repo.get(discovery_id)
            if item is None:
                raise HTTPException(status_code=404, detail="discovery not found")
            snapshots = ScoutSnapshotRepository(conn).list_for_discovery(discovery_id)
            audit_history = discovery_repo.list_intake_audit(discovery_id)
        return {"discovery": item, "snapshots": snapshots, "intake_audit_history": audit_history}

    @app.post("/api/v1/scout/discover")
    def scout_discover_endpoint(body: ScoutDiscoverRequest) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        if body.sort not in SCOUT_ALLOWED_SORTS:
            raise ScoutRequestError(
                f"sort {body.sort!r} is not one of the allowed sort values: {sorted(SCOUT_ALLOWED_SORTS)}"
            )
        with connection(cfg.postgres) as conn:
            run = scout_service.run_discovery(
                conn, symbol=body.symbol, max_records=body.max_records, sort=body.sort
            )
        return {"discovery_run": run}

    @app.post("/api/v1/scout/discoveries")
    def scout_create_manual_discovery_endpoint(body: ScoutManualDiscoveryRequest) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            discovery = scout_service.create_manual_discovery(
                conn,
                origin_kind=body.origin_kind,
                title=body.title,
                origin_description=body.origin_description,
                origin_url=body.origin_url,
                source_symbol=body.source_symbol,
                source_timeframe=body.source_timeframe,
                original_description=body.original_description,
                pasted_rule_text=body.pasted_rule_text,
                personal_notes=body.personal_notes,
                tags=body.tags,
                claimed_metrics=body.claimed_metrics,
            )
        return {"discovery": discovery}

    @app.post("/api/v1/scout/discoveries/{discovery_id}/intake-status")
    def scout_intake_status_endpoint(discovery_id: str, body: ScoutIntakeStatusRequest) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            discovery_repo = ScoutDiscoveryRepository(conn)
            if discovery_repo.get(discovery_id) is None:
                raise HTTPException(status_code=404, detail="discovery not found")
            updated = discovery_repo.set_intake_status(
                discovery_id, body.target_status, changed_by=body.changed_by, reason=body.reason
            )
        return {"discovery": updated}

    # --- PID-004B Workshop UI enablement: StrategyCandidate creation -------
    # Genuine backend gap (migration 0010's own docstring): no endpoint
    # anywhere could create a strategy_candidates row, which ARENA's "Open
    # Workshop" action (PID-004B directive) needs before it can call
    # POST /api/v1/workshops at all. Deliberately narrow -- one create
    # (idempotent per discovery), one read -- never a generic candidate
    # PATCH/update surface.

    @app.post("/api/v1/candidates")
    def open_candidate_endpoint(body: CandidateOpenRequest) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            if body.origin_discovery_id is not None:
                if ScoutDiscoveryRepository(conn).get(body.origin_discovery_id) is None:
                    raise HTTPException(status_code=404, detail="discovery not found")
                row, created = StrategyCandidateRepository(conn).get_or_create_for_discovery(
                    body.origin_discovery_id, body.title
                )
            else:
                candidate_id = new_id()
                StrategyCandidateRepository(conn).create(StrategyCandidate(id=candidate_id, title=body.title))
                row = StrategyCandidateRepository(conn).get_row(candidate_id)
                created = True
        return {"candidate": _candidate_dict(row), "created": created}

    @app.get("/api/v1/candidates/{candidate_id}")
    def get_candidate_endpoint(candidate_id: str) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            row = StrategyCandidateRepository(conn).get_row(candidate_id)
        if row is None:
            raise HTTPException(status_code=404, detail="candidate not found")
        return {"candidate": _candidate_dict(row)}

    # --- Workshop UI enablement: a minimal StrategyVersion read ------------
    # Genuine gap: PID-004A's SpecificationVersionRepository already
    # persists the immutable StrategyVersion in full (including both
    # fingerprints), but nothing anywhere exposed it over HTTP -- the
    # Workshop finalise response only ever returned the bare
    # strategy_version_id (darwin/workshop/api.py), never enough for
    # ARENA's post-finalisation panel (PID-004B directive: "semantic
    # fingerprint ... fingerprint displayed") to show the fingerprint.
    # Deliberately narrow: one read, the minimal identity/fingerprint
    # fields -- never the full composition/parameter payload (which
    # already round-trips through the Workshop draft endpoints).

    @app.get("/api/v1/strategy-versions/{strategy_version_id}")
    def get_strategy_version_endpoint(strategy_version_id: str) -> dict:
        _ensure_ready_for_data(_readiness(cfg))
        with connection(cfg.postgres) as conn:
            row = SpecificationVersionRepository(conn).get_row(strategy_version_id)
        if row is None:
            raise HTTPException(status_code=404, detail="strategy version not found")
        version = deserialize_strategy_version(row["full_payload"])
        return {
            "strategy_version_id": version.strategy_version_id,
            "candidate_id": version.candidate_id,
            "title": version.title,
            "thesis": version.thesis,
            "semantic_fingerprint": version.semantic_fingerprint,
            "artifact_record_fingerprint": version.artifact_record_fingerprint,
            "finalised_at_utc": version.finalised_at_utc,
            "version_label": row.get("version_label"),
        }

    # --- PID-004B Strategy Workshop (docs/pids/PID-004-SPECIFICATION-WORKSHOP.md
    # sec45-sec56) -- routes live in darwin.workshop.api, kept out of this file
    # to avoid unbounded growth; wired the same way SCOUT's routes are (same
    # FastAPI app/process, not a separate service -- PID-004 sec53).
    register_workshop_routes(app, cfg, ensure_ready_for_data=_ensure_ready_for_data, readiness=_readiness)

    # --- PID-004C MENDEL Workshop Assistant (docs/pids/
    # PID-004C-MENDEL-WORKSHOP-ASSISTANT.md sec12) -- WP1 backend + WP2 real
    # Claude Code adapter. darwin.workshop.api.register_mendel_routes picks
    # ClaudeCodeMendelAdapter when cfg.mendel_provider_api_key is configured
    # (DARWIN_MENDEL_PROVIDER_API_KEY_FILE), else falls back to
    # DeterministicTestMendelAdapter -- an honest, additive, non-fatal
    # default, never a startup requirement. Same process, same mounting
    # discipline as the Workshop routes immediately above.
    register_mendel_routes(app, cfg, ensure_ready_for_data=_ensure_ready_for_data, readiness=_readiness)

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


def _candidate_dict(row: dict) -> dict:
    return {
        "candidate_id": str(row["id"]),
        "title": row["title"],
        "pipeline_stage": row["pipeline_stage"],
        "source_strategy_id": str(row["source_strategy_id"]) if row.get("source_strategy_id") else None,
        "origin_discovery_id": str(row["origin_discovery_id"]) if row.get("origin_discovery_id") else None,
        "created_at_utc": row.get("created_at_utc"),
        "updated_at_utc": row.get("updated_at_utc"),
    }


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
