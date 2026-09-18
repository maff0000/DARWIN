"""Integration tests for the two genuine backend gaps found and fixed while
building ARENA's PID-004B Workshop UI (see migration 0010's own docstring
and darwin.workshop.service's readiness section docstring for the full
narrative):

1. There was no REST endpoint anywhere capable of creating a
   `strategy_candidates` row -- `POST /api/v1/candidates` /
   `GET /api/v1/candidates/{id}` (darwin/app.py) close that gap, narrowly.
2. `DataReadinessAssessment`/`DataReadinessAssessmentRepository` already
   existed (PID-004A) but had no HTTP surface and nothing ever called
   `assess_readiness` outside tests -- `GET .../readiness` /
   `POST .../readiness/assess` (darwin/workshop/api.py) close that gap.

Deliberately a small, focused file (mirrors test_workshop_api.py's own
"proves the ROUTES themselves are wired correctly" scope) -- not a
restatement of PID-004B's already-verified Workshop business logic.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig
from darwin.core.identities import new_id
from darwin.research_store.db import connection
from darwin.research_store.models import MarketDatasetRecord
from darwin.research_store.repositories import MarketDatasetRepository
from tests.fixtures.specification_drafts import minimal_valid_draft
from tests.fixtures.workshops import new_user_discovered_discovery

pytestmark = pytest.mark.integration


def _app_config(pg_config) -> DarwinConfig:
    return DarwinConfig(
        postgres=pg_config,
        hermes=HermesConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        build=BuildConfig(version="test", commit="deadbeef", build_time="2026-09-18T00:00:00Z", environment="test"),
        log_level="INFO",
    )


def _client(pg_config) -> TestClient:
    return TestClient(create_app(_app_config(pg_config)))


# --- POST /api/v1/candidates -------------------------------------------------


def test_open_candidate_from_discovery_is_idempotent(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        discovery_id = new_user_discovered_discovery(conn, source_symbol="XAUUSD")

    first = client.post("/api/v1/candidates", json={"title": "T", "origin_discovery_id": discovery_id})
    assert first.status_code == 200
    assert first.json()["created"] is True
    second = client.post("/api/v1/candidates", json={"title": "T", "origin_discovery_id": discovery_id})
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert first.json()["candidate"]["candidate_id"] == second.json()["candidate"]["candidate_id"]


def test_open_candidate_rejects_unknown_discovery(pg_config):
    client = _client(pg_config)
    resp = client.post(
        "/api/v1/candidates", json={"title": "T", "origin_discovery_id": "00000000-0000-0000-0000-000000000000"}
    )
    assert resp.status_code == 404


def test_open_candidate_with_no_discovery_creates_a_bare_candidate(pg_config):
    client = _client(pg_config)
    resp = client.post("/api/v1/candidates", json={"title": "No-origin candidate"})
    assert resp.status_code == 200
    assert resp.json()["created"] is True
    assert resp.json()["candidate"]["origin_discovery_id"] is None


def test_get_candidate_roundtrips(pg_config):
    client = _client(pg_config)
    created = client.post("/api/v1/candidates", json={"title": "Roundtrip"}).json()["candidate"]
    fetched = client.get(f"/api/v1/candidates/{created['candidate_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["candidate"]["title"] == "Roundtrip"


def test_get_unknown_candidate_returns_404(pg_config):
    client = _client(pg_config)
    resp = client.get("/api/v1/candidates/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# --- GET/POST .../readiness --------------------------------------------------


def test_readiness_is_unassessed_before_finalisation(pg_config):
    client = _client(pg_config)
    candidate_id = client.post("/api/v1/candidates", json={"title": "Readiness fixture"}).json()["candidate"][
        "candidate_id"
    ]
    workshop_id = client.post("/api/v1/workshops", json={"candidate_id": candidate_id}).json()["workshop"][
        "workshop_id"
    ]
    resp = client.get(f"/api/v1/workshops/{workshop_id}/readiness")
    assert resp.status_code == 200
    assert resp.json()["readiness"]["state"] == "UNASSESSED"


def test_assess_readiness_before_finalisation_is_refused(pg_config):
    client = _client(pg_config)
    candidate_id = client.post("/api/v1/candidates", json={"title": "Readiness fixture"}).json()["candidate"][
        "candidate_id"
    ]
    workshop_id = client.post("/api/v1/workshops", json={"candidate_id": candidate_id}).json()["workshop"][
        "workshop_id"
    ]
    resp = client.post(f"/api/v1/workshops/{workshop_id}/readiness/assess")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "WORKSHOP_HAS_NO_DRAFT"


def test_assess_readiness_after_finalisation_reflects_real_market_dataset_state(pg_config):
    """Genuinely computed, never fabricated: with NO MarketDataset row for
    XAU_USD/H1, the HERMES OHLCV requirement is honestly UNAVAILABLE and
    overall state is DATA_BLOCKED; after a real MarketDataset row is
    inserted covering it with sufficient depth, a fresh assessment (a
    NEW row, never a rewrite of the first) reports AVAILABLE/TESTABLE."""
    client = _client(pg_config)
    candidate_id = client.post("/api/v1/candidates", json={"title": "Readiness fixture 2"}).json()["candidate"][
        "candidate_id"
    ]
    workshop_id = client.post("/api/v1/workshops", json={"candidate_id": candidate_id}).json()["workshop"][
        "workshop_id"
    ]
    draft = minimal_valid_draft(candidate_id=candidate_id)
    from darwin.specification.serialization import serialize_specification_draft

    put_resp = client.put(
        f"/api/v1/workshops/{workshop_id}/draft",
        json={
            "expected_revision": 0,
            "draft": serialize_specification_draft(draft),
            "schema_semantic_version": draft.schema_semantic_version,
        },
    )
    assert put_resp.status_code == 200
    finalise_resp = client.post(f"/api/v1/workshops/{workshop_id}/finalise", json={"expected_revision": 1})
    assert finalise_resp.status_code == 200
    assert finalise_resp.json()["strategy_version_id"] is not None

    first = client.post(f"/api/v1/workshops/{workshop_id}/readiness/assess")
    assert first.status_code == 200
    assert first.json()["readiness"]["state"] == "DATA_BLOCKED"
    reasons = {r["requirement_id"]: r["availability"] for r in first.json()["readiness"]["requirements"]}
    assert reasons["hermes_xau_usd_h1_ohlcv"] == "UNAVAILABLE"

    with connection(pg_config) as conn:
        MarketDatasetRepository(conn).create(
            MarketDatasetRecord(
                id=new_id(),
                instrument="XAU_USD",
                instrument_definition_id="test-def",
                timeframe="H1",
                requested_start_utc=datetime.now(UTC),
                requested_end_utc=datetime.now(UTC),
                actual_first_open_utc=None,
                actual_last_open_utc=None,
                record_count=500,
                fingerprint_sha256="f" * 64,
                hermes_contract_version="v1",
                hermes_contract_commit="c" * 40,
                adapter_build_version="0.1.0",
                gap_summary={},
                loaded_at_utc=datetime.now(UTC),
            )
        )
        conn.commit()

    second = client.post(f"/api/v1/workshops/{workshop_id}/readiness/assess")
    assert second.status_code == 200
    assert second.json()["readiness"]["state"] == "TESTABLE"

    history = client.get(f"/api/v1/workshops/{workshop_id}/readiness")
    assert history.status_code == 200
    assert history.json()["readiness"]["state"] == "TESTABLE"
