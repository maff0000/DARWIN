"""PID-004C WP2 -- the adapter-selection DI point in
`darwin.workshop.api.register_mendel_routes` (WP2 brief item 3, updated
by the 2026-09-19 auth-architecture correction): the explicit
`DarwinConfig.mendel_use_real_provider` opt-in selects the real
`ClaudeCodeMendelAdapter`; its absence falls back to
`DeterministicTestMendelAdapter` -- `darwin_core` must start and behave
correctly either way. There is no credential involved in this selection
any more -- MENDEL authenticates via Claude Code's own ambient
subscription/OAuth login, never a separately-provisioned API key.

Uses a real disposable Postgres (mirrors tests/integration/
test_mendel_api.py's own discipline) and a real FastAPI `TestClient`. The
real `ClaudeCodeMendelAdapter` CLASS is monkeypatched (at
`darwin.workshop.api`'s own imported name) to a tiny recording stub for
the "real provider opted in" case, so this test never depends on, or
requires an authenticated session against, a real `claude` subprocess
call -- the REAL adapter's own behaviour (command construction, env
scrubbing, timeout, envelope parsing, auth-mode diagnostic, and the real
live-CLI prompt-injection proof) is exercised separately in
tests/unit/test_claude_code_mendel_adapter.py and
tests/unit/test_claude_code_mendel_adapter_live_probe.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import darwin.workshop.api as api_module
from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig
from darwin.research_store.db import connection
from darwin.workshop.mendel_adapter import MendelInvocationResult
from darwin.workshop.mendel_domain import InvocationPurpose
from tests.fixtures.mendel import open_workshop_with_draft

pytestmark = pytest.mark.integration


class _StubClaudeCodeMendelAdapter:
    """A minimal recording stand-in for the real `ClaudeCodeMendelAdapter`
    -- never launches a subprocess, never touches the real `claude`
    binary. Constructed with NO arguments, exactly like the real class
    now is (no credential of any kind), purely to prove the DI point
    selects this class at all when the real provider is opted into."""

    def __init__(self, **_kwargs: object) -> None:
        self.provider_identity = "stub-claude-code-adapter/test"

    def invoke(self, *, context: object, purpose: object, focus_text: object) -> MendelInvocationResult:
        return MendelInvocationResult(proposals=(), reasoning_summary="stub adapter response")


def _app_config(pg_config, *, mendel_use_real_provider: bool) -> DarwinConfig:
    return DarwinConfig(
        postgres=pg_config,
        hermes=HermesConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        build=BuildConfig(
            version="test", commit="deadbeef", build_time="2026-09-18T00:00:00Z", environment="test",
        ),
        log_level="INFO", mendel_use_real_provider=mendel_use_real_provider,
    )


def test_real_provider_not_opted_in_falls_back_to_deterministic_adapter(pg_config):
    client = TestClient(create_app(_app_config(pg_config, mendel_use_real_provider=False)))
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    resp = client.post(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/invoke",
        json={"purpose": InvocationPurpose.REVIEW_DRAFT.value, "focus_text": None},
    )
    assert resp.status_code == 200
    run = resp.json()["run"]
    assert run["status"] == "SUCCEEDED"
    assert run["provider_identity"] == "deterministic-test-adapter/1.0.0"


def test_real_provider_opted_in_selects_claude_code_adapter(pg_config, monkeypatch):
    monkeypatch.setattr(api_module, "ClaudeCodeMendelAdapter", _StubClaudeCodeMendelAdapter)
    client = TestClient(
        create_app(_app_config(pg_config, mendel_use_real_provider=True))
    )
    with connection(pg_config) as conn:
        workshop, _ = open_workshop_with_draft(conn)
    resp = client.post(
        f"/api/v1/workshops/{workshop.workshop_id}/mendel/invoke",
        json={"purpose": InvocationPurpose.REVIEW_DRAFT.value, "focus_text": None},
    )
    assert resp.status_code == 200
    run = resp.json()["run"]
    assert run["status"] == "SUCCEEDED"
    assert run["provider_identity"] == "stub-claude-code-adapter/test"
