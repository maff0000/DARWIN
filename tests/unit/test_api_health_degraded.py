"""API-level tests that require no real Postgres/HERMES — they exercise the
degraded-but-not-crashed path deliberately (PID-001 §10/§35 failure semantics).
"""
from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig, PostgresConfig


def _unreachable_config() -> DarwinConfig:
    return DarwinConfig(
        postgres=PostgresConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        hermes=HermesConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        build=BuildConfig(version="test", commit="deadbeef", build_time="2026-09-16T00:00:00Z", environment="test"),
        log_level="INFO",
    )


def test_health_always_ok_even_with_dependencies_down():
    client = TestClient(create_app(_unreachable_config()))
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "OK"}


def test_ready_reports_503_and_never_crashes_when_dependencies_down():
    client = TestClient(create_app(_unreachable_config()))
    resp = client.get("/api/v1/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["ready"] is False
    names = {c["name"] for c in body["components"]}
    assert "postgres" in names
    assert "hermes_adapter" in names


def test_buildinfo_reflects_injected_config():
    client = TestClient(create_app(_unreachable_config()))
    resp = client.get("/api/v1/buildinfo")
    assert resp.status_code == 200
    assert resp.json()["commit"] == "deadbeef"


def test_error_response_never_leaks_credentials_or_dsn():
    client = TestClient(create_app(_unreachable_config()))
    resp = client.get("/api/v1/datasets")
    assert resp.status_code in (503, 500)
    assert "nope" not in resp.text  # the fake password/user must never appear in a response
