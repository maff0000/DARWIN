"""PID-003 SCOUT sec5: 'External-source failure must never make DARWIN core
health/readiness go down.' This test points the REAL adapter (real DNS
resolution, no mocked transport) at a genuinely unreachable host -- an
RFC 2606 `.invalid` domain, which is reserved to never resolve -- and
proves `/api/v1/health` and `/api/v1/ready` are completely unaffected.

Requires a real disposable PostgreSQL (DARWIN_TEST_PG_DSN) so `/ready` has
something real to report against; genuinely exercises DNS resolution
failure over the real network, so it is an integration test, not a unit
test with a mocked transport.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig
from darwin.scout import trader_dev_adapter as adapter_module

pytestmark = pytest.mark.integration


def test_scout_adapter_pointed_at_an_unreachable_host_never_affects_health_or_ready(pg_config, monkeypatch):
    monkeypatch.setattr(adapter_module, "ALLOWED_API_HOST", "scout-adapter-test.invalid")
    monkeypatch.setattr(adapter_module, "BASE_URL", "https://scout-adapter-test.invalid")

    with adapter_module.TraderDevAdapter() as adapter:
        assert adapter.check_reachable() is False  # real DNS resolution genuinely fails

    cfg = DarwinConfig(
        postgres=pg_config,
        hermes=HermesConfig(host="unreachable-in-test", port=3307, database="unused", user="unused", password="unused"),
        build=BuildConfig(version="test", commit="deadbeef", build_time="2026-09-17T00:00:00Z", environment="test"),
        log_level="INFO",
    )
    client = TestClient(create_app(cfg))

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {"status": "OK"}

    ready = client.get("/api/v1/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True  # postgres+migrations OK; HERMES non-blocking-degraded, SCOUT never consulted

    status = client.get("/api/v1/scout/status")
    assert status.status_code == 200
    assert status.json()["trader_dev_public"]["reachable"] is False
