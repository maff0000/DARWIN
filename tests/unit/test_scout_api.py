"""PID-003 SCOUT API wiring unit tests -- readiness gating, request
validation, and the "SCOUT status never affects DARWIN readiness" contract.
Mirrors tests/unit/test_readiness_blocking.py / test_arena_api.py's style:
monkeypatched readiness checks, no real database required.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig, PostgresConfig


def _config() -> DarwinConfig:
    return DarwinConfig(
        postgres=PostgresConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        hermes=HermesConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        build=BuildConfig(version="test", commit="deadbeef", build_time="2026-09-17T00:00:00Z", environment="test"),
        log_level="INFO",
    )


def test_scout_status_returns_200_even_when_postgres_unreachable(monkeypatch):
    """PID-003 sec5/sec6: SCOUT status must never itself fail, and must
    never depend on DARWIN_sql being ready."""
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: False)
    monkeypatch.setattr(
        "darwin.scout.service.TraderDevAdapter",
        lambda *a, **k: type("A", (), {
            "check_reachable": lambda self: False, "close": lambda self: None,
            "__enter__": lambda self: self, "__exit__": lambda self, *a: None,
        })(),
    )
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/scout/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trader_dev_public"]["reachable"] is False
    assert body["last_discovery_run"] is None


def test_scout_status_never_shows_up_in_ready_response(monkeypatch):
    """Confirms darwin.app._readiness never references anything SCOUT --
    a Trader.dev outage must not appear as a readiness component at all."""
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state", lambda cfg, migrations_dir: {"up_to_date": True, "pending": []}
    )
    monkeypatch.setattr("darwin.app.check_hermes_reachable", lambda cfg: True)
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 200
    names = {c["name"] for c in resp.json()["components"]}
    assert "scout" not in names
    assert "trader_dev" not in names
    assert "scout_source" not in names


def test_scout_discoveries_returns_503_when_migrations_pending(monkeypatch):
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state",
        lambda cfg, migrations_dir: {"up_to_date": False, "pending": ["0005_scout_discovery"]},
    )
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/scout/discoveries")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "NOT_READY"


def test_scout_discover_returns_503_when_not_ready(monkeypatch):
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: False)
    client = TestClient(create_app(_config()))
    resp = client.post("/api/v1/scout/discover", json={"symbol": "XAUUSD"})
    assert resp.status_code == 503


def test_scout_discover_rejects_max_records_above_hard_ceiling(monkeypatch):
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state", lambda cfg, migrations_dir: {"up_to_date": True, "pending": []}
    )
    client = TestClient(create_app(_config()))
    resp = client.post("/api/v1/scout/discover", json={"max_records": 100000})
    assert resp.status_code == 422  # pydantic Field(le=...) rejects before any adapter/DB call


def test_scout_discover_accepts_no_raw_url_parameter(monkeypatch):
    """PID-003 sec6: no arbitrary input beyond bounded filters -- an
    arbitrary 'url' field must simply be ignored by the typed request
    model, never become a fetch target."""
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state", lambda cfg, migrations_dir: {"up_to_date": False, "pending": ["x"]}
    )
    client = TestClient(create_app(_config()))
    resp = client.post("/api/v1/scout/discover", json={"url": "https://evil.example.com/whatever"})
    # Not ready (no real DB here) -- the point is that this never reaches
    # 422 for an unrecognised field (pydantic ignores extras by default)
    # nor is 'url' ever visible to darwin.scout.service.run_discovery's
    # signature (it has no such parameter at all).
    assert resp.status_code == 503


def test_scout_intake_status_request_requires_changed_by(monkeypatch):
    monkeypatch.setattr("darwin.app.check_postgres_reachable", lambda cfg: True)
    monkeypatch.setattr(
        "darwin.app.migration_state", lambda cfg, migrations_dir: {"up_to_date": True, "pending": []}
    )
    client = TestClient(create_app(_config()))
    resp = client.post(
        "/api/v1/scout/discoveries/some-id/intake-status",
        json={"target_status": "SHORTLISTED", "changed_by": ""},
    )
    assert resp.status_code == 422
