"""PID-004C MENDEL Workshop Assistant HTTP-surface integration tests -- a
real FastAPI TestClient against a real, disposable PostgreSQL
(`pg_config`). Mirrors tests/integration/test_workshop_api.py's own
"smaller set, business logic lives in the service-layer tests" discipline
-- see tests/integration/test_mendel_service.py for the acceptance-
transaction proofs. This file proves: the routes are wired correctly,
the closed `InvocationPurpose` vocabulary is actually enforced at the API
boundary (422 for an out-of-vocabulary value), and there is no generic
command/path endpoint anywhere under `/mendel/`.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig
from darwin.research_store.db import connection
from darwin.workshop import mendel_service
from darwin.workshop.mendel_adapter import (
    DeterministicTestMendelAdapter,
    MendelInvocationResult,
)
from darwin.workshop.mendel_domain import InvocationPurpose
from tests.fixtures.mendel import (
    ask_question_proposal,
    material_concern_proposal,
    open_workshop_with_draft,
)

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


def _seed_proposals(pg_config, workshop_id: str) -> list[dict]:
    """Seeds real proposals directly through `mendel_service` (never
    through the HTTP layer, whose default adapter has no configured
    proposals) -- mirrors how test_workshop_api.py seeds prerequisite
    state directly via `connection(pg_config)` before exercising the
    actual endpoint under test."""
    with connection(pg_config) as conn:
        adapter = DeterministicTestMendelAdapter(
            result=MendelInvocationResult(
                proposals=(ask_question_proposal(), material_concern_proposal()), reasoning_summary="seed",
            )
        )
        mendel_service.invoke_mendel(
            conn, workshop_id, purpose=InvocationPurpose.REVIEW_DRAFT, focus_text=None, adapter=adapter,
        )
        return [
            {"proposal_id": p.proposal_id, "proposal_category": p.proposal_category.value}
            for p in mendel_service.list_proposals(conn, workshop_id)
        ]


def test_invoke_mendel_endpoint_returns_a_succeeded_run(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)

    resp = client.post(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/invoke",
        json={"purpose": "REVIEW_DRAFT", "focus_text": "please review"},
    )
    assert resp.status_code == 200
    run = resp.json()["run"]
    assert run["status"] == "SUCCEEDED"
    assert run["workshop_id"] == workshop.workshop_id
    assert run["context_fingerprint"]


def test_invoke_mendel_endpoint_rejects_out_of_vocabulary_purpose_with_422(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)

    resp = client.post(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/invoke",
        json={"purpose": "DO_ANYTHING_YOU_WANT"},
    )
    assert resp.status_code == 422


def test_invoke_mendel_endpoint_unknown_workshop_returns_404(pg_config):
    client = _client(pg_config)
    resp = client.post(
        "/api/v1/workshops/00000000-0000-0000-0000-000000000000/mendel/invoke",
        json={"purpose": "REVIEW_DRAFT"},
    )
    assert resp.status_code == 404


def test_list_mendel_runs_endpoint(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    _seed_proposals(pg_config, workshop.workshop_id)

    resp = client.get(f"/api/v1/workshops/{workshop.workshop_id}/mendel/runs")
    assert resp.status_code == 200
    runs = resp.json()["items"]
    assert len(runs) == 1
    assert runs[0]["status"] == "SUCCEEDED"


def test_get_mendel_run_endpoint_404_for_unknown_run(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    resp = client.get(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/runs/00000000-0000-0000-0000-000000000000"
    )
    # Mirrors darwin.workshop.api's own existing convention for an
    # explicitly-caught-and-converted 404 (e.g. test_get_unknown_workshop_
    # returns_404 in test_workshop_api.py): FastAPI's plain
    # {"detail": ...} body, not the DarwinError-global-handler's
    # {"error": {"code": ...}} shape (that shape is reserved for errors
    # that propagate to the global handler unconverted, at 400/503).
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower() or "does not belong" in resp.json()["detail"].lower()


def test_list_mendel_proposals_endpoint_with_status_filter(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    seeded = _seed_proposals(pg_config, workshop.workshop_id)
    assert len(seeded) == 2

    all_resp = client.get(f"/api/v1/workshops/{workshop.workshop_id}/mendel/proposals")
    assert all_resp.status_code == 200
    assert len(all_resp.json()["items"]) == 2

    proposed_resp = client.get(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/proposals", params={"status": "PROPOSED"}
    )
    assert proposed_resp.status_code == 200
    assert len(proposed_resp.json()["items"]) == 2

    accepted_resp = client.get(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/proposals", params={"status": "ACCEPTED"}
    )
    assert accepted_resp.status_code == 200
    assert accepted_resp.json()["items"] == []


def test_accept_mendel_proposal_endpoint_question_category(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    seeded = _seed_proposals(pg_config, workshop.workshop_id)
    question_proposal = next(p for p in seeded if p["proposal_category"] == "QUESTION")

    resp = client.post(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/proposals/{question_proposal['proposal_id']}/accept",
        json={"actor": "matt"},
    )
    assert resp.status_code == 200
    body = resp.json()["proposal"]
    assert body["status"] == "ACCEPTED"
    assert body["resulting_question_id"] is not None


def test_accept_mendel_proposal_endpoint_unknown_proposal_returns_404(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    resp = client.post(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/proposals/"
        "00000000-0000-0000-0000-000000000000/accept",
        json={"actor": "matt"},
    )
    assert resp.status_code == 404
    assert "does not belong" in resp.json()["detail"].lower()


def test_reject_mendel_proposal_endpoint(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    seeded = _seed_proposals(pg_config, workshop.workshop_id)
    advisory_proposal = next(p for p in seeded if p["proposal_category"] == "ADVISORY")

    resp = client.post(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/proposals/{advisory_proposal['proposal_id']}/reject",
        json={"reason": "not applicable"},
    )
    assert resp.status_code == 200
    assert resp.json()["proposal"]["status"] == "REJECTED"


def test_no_generic_command_or_arbitrary_path_endpoint_under_mendel(pg_config):
    client = _client(pg_config)
    mendel_paths = [
        r.path for r in client.app.routes if "/mendel/" in getattr(r, "path", "") or getattr(r, "path", "").endswith("/mendel")
    ]
    assert mendel_paths, "expected the MENDEL routes to be registered"
    forbidden_fragments = ("path:", "command", "execute", "shell", "cmd", "prompt")
    for path in mendel_paths:
        lowered = path.lower()
        for fragment in forbidden_fragments:
            assert fragment not in lowered, f"route {path!r} looks like a generic command/prompt surface"
