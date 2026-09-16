"""Regression tests for the readiness-masks-pending-migrations defect.

An independent Auditor reproduced this live on PR #2 (commit bd5be8e): a
genuinely fresh deploy (Postgres reachable, migrations not yet applied)
reported `/api/v1/ready` as `ready: true` while `/api/v1/pipeline/summary`,
`/api/v1/datasets`, and `/api/v1/runs` all returned raw 500s. Root cause:
`ReadinessReport.ready` treated any non-DOWN status as good enough, so a
DEGRADED "migrations pending" component never blocked readiness the way a
DOWN one would, even though DARWIN's own control-plane endpoints directly
depend on the schema existing. These tests pin the fix: `migrations`/
`postgres` are blocking components (DEGRADED must still fail readiness),
while `hermes_adapter` remains deliberately non-blocking per PID-001 §10.
"""
from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig, PostgresConfig
from darwin.core.health import ComponentHealth, ComponentStatus, ReadinessReport


def _config() -> DarwinConfig:
    return DarwinConfig(
        postgres=PostgresConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        hermes=HermesConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        build=BuildConfig(version="test", commit="deadbeef", build_time="2026-09-16T00:00:00Z", environment="test"),
        log_level="INFO",
    )


def test_ready_false_when_a_blocking_component_is_merely_degraded():
    report = ReadinessReport(components=(
        ComponentHealth("postgres", ComponentStatus.OK),
        ComponentHealth("migrations", ComponentStatus.DEGRADED, "pending: ['0001_foundation']"),
    ))
    assert report.ready is False


def test_ready_true_when_only_a_non_blocking_component_is_degraded():
    report = ReadinessReport(components=(
        ComponentHealth("postgres", ComponentStatus.OK),
        ComponentHealth("migrations", ComponentStatus.OK),
        ComponentHealth("hermes_adapter", ComponentStatus.DEGRADED, "HERMES unreachable", blocking=False),
    ))
    assert report.ready is True


def test_api_ready_reflects_pending_migrations(monkeypatch):
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state",
        lambda cfg, migrations_dir: {"up_to_date": False, "pending": ["0001_foundation"]},
    )
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    migrations = next(c for c in body["components"] if c["name"] == "migrations")
    assert migrations["status"] == "DEGRADED"


def test_data_endpoints_return_clean_503_not_500_when_migrations_pending(monkeypatch):
    """Reproduces the exact Auditor-found defect: these endpoints previously
    returned raw 500s (querying tables that don't exist yet) while /ready
    reported ready:true. Now they must return a clean 503/NOT_READY."""
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state",
        lambda cfg, migrations_dir: {"up_to_date": False, "pending": ["0001_foundation"]},
    )
    client = TestClient(create_app(_config()))
    for path in ("/api/v1/pipeline/summary", "/api/v1/datasets", "/api/v1/runs"):
        resp = client.get(path)
        assert resp.status_code == 503, f"{path} returned {resp.status_code}, expected a clean 503"
        assert resp.json()["error"]["code"] == "NOT_READY"


def test_system_summary_stays_200_with_zero_counts_when_migrations_pending(monkeypatch):
    """system/summary is the observability endpoint (PID-001 §24) — it must
    keep reporting operational state (200) even when not ready, not 503
    itself, but must not attempt to query tables that may not exist yet."""
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state",
        lambda cfg, migrations_dir: {"up_to_date": False, "pending": ["0001_foundation"]},
    )
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/system/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["readiness"]["ready"] is False
    assert body["record_counts"] == {
        "source_strategies": 0,
        "strategy_candidates": 0,
        "strategy_versions": 0,
        "market_datasets": 0,
        "research_runs": 0,
    }


def test_hermes_down_alone_leaves_ready_true(monkeypatch):
    """HERMES being unreachable must not block Foundation's own control-plane
    (PID-001 §10) — confirms the fix did not regress this pre-existing,
    deliberate behaviour."""
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state", lambda cfg, migrations_dir: {"up_to_date": True, "pending": []}
    )
    monkeypatch.setattr("darwin.app.check_hermes_reachable", lambda cfg: False)
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    hermes = next(c for c in body["components"] if c["name"] == "hermes_adapter")
    assert hermes["status"] == "DEGRADED"
