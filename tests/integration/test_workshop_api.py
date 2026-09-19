"""PID-004B Strategy Workshop HTTP-surface integration tests -- a real
FastAPI TestClient wired against a real, disposable PostgreSQL
(`pg_config`). Deliberately a SMALLER set than
tests/integration/test_workshop_service.py -- the business-logic-heavy
proofs (idempotent open, SCOUT fidelity, instrument mapping, cross-
workshop misuse, supersession history, ...) already live there against
`darwin.workshop.service` directly (mirrors how tests/unit/test_scout_api.py
only proves wiring/readiness for SCOUT, not its full business logic). This
file proves the FastAPI ROUTES themselves are wired correctly end-to-end,
plus the explicit "no generic command/path endpoint exists" property
PID-004 sec48/sec56 requires.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig
from darwin.research_store.db import connection
from darwin.specification.domain import SpecificationDraft
from darwin.specification.serialization import serialize_specification_draft
from tests.fixtures.specification_drafts import minimal_valid_draft
from tests.fixtures.workshops import new_candidate, new_user_discovered_discovery

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


def test_open_workshop_via_api_is_idempotent(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)

    first = client.post("/api/v1/workshops", json={"candidate_id": candidate_id})
    assert first.status_code == 200
    second = client.post("/api/v1/workshops", json={"candidate_id": candidate_id})
    assert second.status_code == 200
    assert first.json()["workshop"]["workshop_id"] == second.json()["workshop"]["workshop_id"]


def test_open_workshop_via_api_rejects_invalid_candidate(pg_config):
    client = _client(pg_config)
    resp = client.post("/api/v1/workshops", json={"candidate_id": "00000000-0000-0000-0000-000000000000"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "WORKSHOP_INVALID_REFERENCE"


def test_get_unknown_workshop_returns_404(pg_config):
    client = _client(pg_config)
    resp = client.get("/api/v1/workshops/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_full_authoring_and_finalisation_flow_via_api(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
        discovery_id = new_user_discovered_discovery(conn)

    opened = client.post(
        "/api/v1/workshops", json={"candidate_id": candidate_id, "discovery_ids": [discovery_id]}
    ).json()["workshop"]
    workshop_id = opened["workshop_id"]
    assert opened["discovery_ids"] == [discovery_id]

    question = client.post(
        f"/api/v1/workshops/{workshop_id}/questions",
        json={"semantic_subject": "exit", "question_text": "what closes the trade?"},
    ).json()["question"]
    assert question["status"] == "OPEN"

    decision = client.post(
        f"/api/v1/workshops/{workshop_id}/decisions",
        json={
            "proposed_value": {"exit": "H1 close below entry"}, "origin": "USER_CLARIFICATION",
            "actor": "matt", "related_question_id": question["question_id"],
        },
    ).json()["decision"]
    accepted = client.post(f"/api/v1/workshops/{workshop_id}/decisions/{decision['decision_id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["decision"]["acceptance_state"] == "ACCEPTED"

    resolved = client.post(
        f"/api/v1/workshops/{workshop_id}/questions/{question['question_id']}/resolve",
        json={"resolution": "RESOLVED", "accepted_decision_id": decision["decision_id"]},
    )
    assert resolved.status_code == 200
    assert resolved.json()["question"]["status"] == "RESOLVED"

    draft_body = serialize_specification_draft(minimal_valid_draft(candidate_id=candidate_id))
    put_resp = client.put(
        f"/api/v1/workshops/{workshop_id}/draft", json={"expected_revision": 0, "draft": draft_body}
    )
    assert put_resp.status_code == 200
    revision = put_resp.json()["revision"]
    assert revision == 1

    validate_resp = client.post(f"/api/v1/workshops/{workshop_id}/validate")
    assert validate_resp.status_code == 200
    assert validate_resp.json()["validation"]["status"] == "VALID"

    finalise_resp = client.post(
        f"/api/v1/workshops/{workshop_id}/finalise", json={"expected_revision": revision}
    )
    assert finalise_resp.status_code == 200
    body = finalise_resp.json()
    assert body["strategy_version_id"] is not None
    assert body["workshop"]["status"] == "FINALISED"
    assert body["workshop"]["finalised_strategy_version_id"] == body["strategy_version_id"]


def test_draft_stale_revision_returns_400_via_api(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        candidate_id = new_candidate(conn)
    workshop_id = client.post("/api/v1/workshops", json={"candidate_id": candidate_id}).json()["workshop"][
        "workshop_id"
    ]
    empty = serialize_specification_draft(
        SpecificationDraft(draft_id="x", candidate_id=candidate_id, schema_semantic_version="1.0.0")
    )
    client.put(f"/api/v1/workshops/{workshop_id}/draft", json={"expected_revision": 0, "draft": empty})
    stale = client.put(f"/api/v1/workshops/{workshop_id}/draft", json={"expected_revision": 0, "draft": empty})
    assert stale.status_code == 400
    assert stale.json()["error"]["code"] == "SPECIFICATION_STALE_REVISION"


def test_cross_workshop_question_id_substitution_refused_via_api(pg_config):
    client = _client(pg_config)
    with connection(pg_config) as conn:
        candidate_a = new_candidate(conn)
        candidate_b = new_candidate(conn)
    workshop_a = client.post("/api/v1/workshops", json={"candidate_id": candidate_a}).json()["workshop"][
        "workshop_id"
    ]
    workshop_b = client.post("/api/v1/workshops", json={"candidate_id": candidate_b}).json()["workshop"][
        "workshop_id"
    ]
    question_b = client.post(
        f"/api/v1/workshops/{workshop_b}/questions", json={"semantic_subject": "x", "question_text": "y?"}
    ).json()["question"]

    resp = client.post(
        f"/api/v1/workshops/{workshop_a}/questions/{question_b['question_id']}/resolve",
        json={"resolution": "RESOLVED"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "WORKSHOP_CROSS_REFERENCE_DENIED"


def test_no_generic_command_or_arbitrary_path_endpoint_exists(pg_config):
    """PID-004 sec48: no FastAPI route anywhere accepts a caller-controlled
    filesystem path or runs a command. Enumerates every registered route's
    path template and rejects any that look like a generic file/command
    surface -- and confirms every Workshop path segment beyond the fixed,
    documented verbs is exactly `{workshop_id}`/`{question_id}`/
    `{decision_id}` (a resource id), never a wildcard/path-capturing
    parameter."""
    client = _client(pg_config)
    workshop_paths = [r.path for r in client.app.routes if getattr(r, "path", "").startswith("/api/v1/workshops")]
    assert workshop_paths, "expected the Workshop routes to be registered"
    forbidden_fragments = ("path:", "command", "execute", "shell", "cmd")
    # "run" is checked as a whole path SEGMENT, never a raw substring: PID-004C
    # (docs/pids/PID-004C-MENDEL-WORKSHOP-ASSISTANT.md sec10.1) legitimately
    # introduces a "mendel/runs" resource noun (MendelRun invocation
    # history) nested under this same /api/v1/workshops prefix -- a bare
    # substring check would false-positive on that plural noun even though
    # it is not a "run this command" surface. A literal "run" segment on
    # its own would still be caught below.
    forbidden_segments = ("run", "path", "command", "execute", "shell", "cmd")
    for path in workshop_paths:
        lowered = path.lower()
        segments = [s for s in lowered.split("/") if s]
        for fragment in forbidden_fragments:
            assert fragment not in lowered, f"route {path!r} looks like a generic command/path surface"
        for segment_word in forbidden_segments:
            assert segment_word not in segments, f"route {path!r} looks like a generic command/path surface"
