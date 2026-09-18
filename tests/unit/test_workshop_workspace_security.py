"""PID-004B Workshop workspace filesystem security tests (docs/pids/
PID-004-SPECIFICATION-WORKSHOP.md sec47/sec55/sec56). No database required
-- pure filesystem behaviour against a disposable temp directory pointed
to via `DARWIN_WORKSPACES_ROOT`."""
from __future__ import annotations

import os
import uuid

import pytest

from darwin.workshop import workspace
from darwin.workshop.errors import WorkspacePathViolationError


@pytest.fixture
def wsroot(tmp_path, monkeypatch):
    monkeypatch.setenv("DARWIN_WORKSPACES_ROOT", str(tmp_path))
    return tmp_path


def _uuid() -> str:
    return str(uuid.uuid4())


# --- fixed root / valid workshop ids only ------------------------------------


def test_workspaces_root_is_the_configured_fixed_root(wsroot):
    assert workspace.workspaces_root() == wsroot.resolve()


@pytest.mark.parametrize(
    "bad_id",
    ["../etc/passwd", "..", "foo/bar", "/etc/passwd", "not-a-uuid", "", "a" * 5, "..\\..\\windows"],
)
def test_rejects_non_uuid_workshop_ids(wsroot, bad_id):
    with pytest.raises(WorkspacePathViolationError):
        workspace.workshop_dir(bad_id)


def test_accepts_a_real_uuid_workshop_id(wsroot):
    workshop_id = _uuid()
    directory = workspace.workshop_dir(workshop_id)
    assert directory == (wsroot.resolve() / workshop_id)


# --- no `..` traversal in a relative workspace path --------------------------


def test_ensure_workspace_creates_bounded_directory_and_source_material(wsroot):
    workshop_id = _uuid()
    directory = workspace.ensure_workspace(workshop_id)
    assert directory.is_dir()
    assert (directory / workspace.SOURCE_MATERIAL_DIR).is_dir()


def test_write_source_material_rejects_dotdot_traversal(wsroot):
    workshop_id = _uuid()
    workspace.ensure_workspace(workshop_id)
    with pytest.raises(WorkspacePathViolationError):
        workspace.write_source_material(workshop_id, "../../etc/evil.txt", b"pwned")


def test_write_source_material_rejects_absolute_path(wsroot):
    workshop_id = _uuid()
    workspace.ensure_workspace(workshop_id)
    with pytest.raises(WorkspacePathViolationError):
        workspace.write_source_material(workshop_id, "/etc/evil.txt", b"pwned")


def test_read_source_material_rejects_dotdot_traversal(wsroot):
    workshop_id = _uuid()
    workspace.ensure_workspace(workshop_id)
    with pytest.raises(WorkspacePathViolationError):
        workspace.read_source_material(workshop_id, "../../../etc/passwd")


# --- no symlink escape outside the workshop's own directory -----------------


def test_symlink_escape_via_source_material_is_refused(wsroot):
    workshop_id = _uuid()
    directory = workspace.ensure_workspace(workshop_id)
    outside = wsroot / "outside_secret.txt"
    outside.write_text("top secret")
    link = directory / workspace.SOURCE_MATERIAL_DIR / "escape_link"
    os.symlink(outside, link)
    with pytest.raises(WorkspacePathViolationError):
        workspace.read_source_material(workshop_id, "escape_link")


def test_symlink_escape_via_nested_directory_is_refused(wsroot):
    workshop_id = _uuid()
    directory = workspace.ensure_workspace(workshop_id)
    outside_dir = wsroot / "outside_dir"
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("top secret")
    link = directory / workspace.SOURCE_MATERIAL_DIR / "escape_dir"
    os.symlink(outside_dir, link)
    with pytest.raises(WorkspacePathViolationError):
        workspace.read_source_material(workshop_id, "escape_dir/secret.txt")


# --- governed-file allowlist (no arbitrary top-level filename) --------------


def test_write_governed_file_rejects_names_outside_the_fixed_allowlist(wsroot):
    workshop_id = _uuid()
    with pytest.raises(WorkspacePathViolationError):
        workspace.write_governed_file(workshop_id, "NOT_A_GOVERNED_FILE.txt", "data")


def test_read_governed_file_rejects_names_outside_the_fixed_allowlist(wsroot):
    workshop_id = _uuid()
    with pytest.raises(WorkspacePathViolationError):
        workspace.read_governed_file(workshop_id, "../../../etc/passwd")


def test_write_and_read_governed_file_round_trips(wsroot):
    workshop_id = _uuid()
    workspace.write_governed_file(workshop_id, workspace.CONTEXT_MD, "# hello")
    assert workspace.read_governed_file(workshop_id, workspace.CONTEXT_MD) == "# hello"


def test_read_governed_file_returns_none_when_absent(wsroot):
    workshop_id = _uuid()
    workspace.ensure_workspace(workshop_id)
    assert workspace.read_governed_file(workshop_id, workspace.VALIDATION_JSON) is None


# --- no arbitrary deletion outside the workshop's own directory -------------


def test_delete_workspace_removes_only_its_own_directory(wsroot):
    workshop_id = _uuid()
    directory = workspace.ensure_workspace(workshop_id)
    sibling_id = _uuid()
    sibling_dir = workspace.ensure_workspace(sibling_id)
    (directory / "marker.txt").write_text("mine")
    (sibling_dir / "marker.txt").write_text("not mine")

    workspace.delete_workspace(workshop_id)

    assert not directory.exists()
    assert sibling_dir.exists()
    assert (sibling_dir / "marker.txt").read_text() == "not mine"


def test_delete_workspace_rejects_invalid_workshop_id(wsroot):
    with pytest.raises(WorkspacePathViolationError):
        workspace.delete_workspace("../../etc")


def test_delete_workspace_is_a_safe_no_op_when_directory_never_existed(wsroot):
    workshop_id = _uuid()
    workspace.delete_workspace(workshop_id)  # must not raise


# --- source material is treated as inert data, never executed --------------


def test_workspace_module_never_executes_or_interprets_content():
    """PID-004 sec55: 'Do not execute source code.' Structural proof: the
    workspace module's source contains no ACTUAL execution/dynamic-import
    call sites (only its own docstring prose mentions these tool names as
    things it deliberately avoids) -- there is no code path in this module
    capable of running written content, not merely a convention against
    doing so."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(workspace))
    forbidden_calls = {"eval", "exec", "system", "Popen", "run", "call", "import_module", "__import__"}
    forbidden_imports = {"subprocess", "importlib"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = {alias.name for alias in node.names}
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
            assert not (names & forbidden_imports), f"workspace.py must never import {names & forbidden_imports}"
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            assert name not in forbidden_calls, f"workspace.py must never call {name!r}"


def test_write_source_material_stores_arbitrary_bytes_without_interpreting_them(wsroot):
    workshop_id = _uuid()
    script = b"#!/bin/sh\nrm -rf /\n"
    workspace.write_source_material(workshop_id, "suspicious.sh", script)
    assert workspace.read_source_material(workshop_id, "suspicious.sh") == script


# --- deleted-workspace-survives-in-DB is proven at the service layer -------
# (tests/integration/test_workshop_service.py --
# test_deleted_workspace_directory_does_not_lose_canonical_state)
