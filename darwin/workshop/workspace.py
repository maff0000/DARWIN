"""PID-004B Workshop workspace -- a bounded authoring FILESYSTEM surface
(docs/pids/PID-004-SPECIFICATION-WORKSHOP.md sec47/sec55).

`/srv/DARWIN/workspaces/<workshop-id>/` (root overridable via
`DARWIN_WORKSPACES_ROOT`, purely for test isolation -- the real deployment
never sets it, so it defaults to the exact PID-004 sec47 path).

This is an AUTHORING SURFACE, never canonical storage (PID-004 sec47: "It
is not canonical StrategyVersion storage. Canonical truth remains DARWIN
persistence."). Every function here is deliberately narrow:

* No function anywhere in this module accepts an arbitrary caller-supplied
  path string. Every relative path used against a Workshop's directory is
  one of a small, fixed, hardcoded set of governed filenames
  (`GOVERNED_FILES` / `SOURCE_MATERIAL_DIR`) that `darwin.workshop.service`
  calls with literal string constants -- never user input.
* `workshop_id` is validated as a real UUID (`darwin.core.identities.
  is_valid_id`) before it is ever joined onto the workspace root -- this
  alone rules out `..`/absolute-path/null-byte tricks arriving via the
  Workshop id itself.
* `_resolve_within` additionally resolves the final path with symlinks
  followed (`Path.resolve()`) and asserts the result still lives under the
  Workshop's own realpath'd directory -- refusing a symlink planted inside
  the workspace that points outside it, not just a `..` string.
* Nothing here executes/interprets file content in any way (no
  `subprocess`, `eval`, `exec`, or dynamic import anywhere in this module)
  -- source material is written and read back as opaque bytes only
  (PID-004 sec55: "Do not execute source code").
* Every write here is best-effort against a NON-canonical surface --
  callers (`darwin.workshop.service`) must never let a workspace
  filesystem failure abort a canonical database transaction; see
  `sync_workspace_from_db`'s docstring.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

from darwin.core.identities import is_valid_id
from darwin.workshop.errors import WorkspacePathViolationError

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = "/srv/DARWIN/workspaces"

# The complete, fixed set of top-level workspace files (PID-004 sec47).
# Never extended by caller input -- adding a new governed file is a code
# change, not a runtime parameter.
DISCOVERY_JSON = "DISCOVERY.json"
CONTEXT_MD = "CONTEXT.md"
QUESTIONS_MD = "QUESTIONS.md"
DECISIONS_JSONL = "DECISIONS.jsonl"
SPECIFICATION_DRAFT_JSON = "SPECIFICATION_DRAFT.json"
VALIDATION_JSON = "VALIDATION.json"
SOURCE_MATERIAL_DIR = "SOURCE_MATERIAL"

GOVERNED_FILES: frozenset[str] = frozenset(
    {DISCOVERY_JSON, CONTEXT_MD, QUESTIONS_MD, DECISIONS_JSONL, SPECIFICATION_DRAFT_JSON, VALIDATION_JSON}
)


def workspaces_root() -> Path:
    """Resolved once per call (deliberately not cached at import time) so
    tests can point `DARWIN_WORKSPACES_ROOT` at a disposable temp directory
    without needing to reload this module."""
    return Path(os.environ.get("DARWIN_WORKSPACES_ROOT", _DEFAULT_ROOT)).resolve()


def _require_valid_workshop_id(workshop_id: str) -> str:
    if not isinstance(workshop_id, str) or not is_valid_id(workshop_id):
        raise WorkspacePathViolationError(
            f"workshop_id {workshop_id!r} is not a valid UUID -- refusing to build a workspace path "
            f"from it"
        )
    return workshop_id


def workshop_dir(workshop_id: str) -> Path:
    """The bounded directory for one Workshop -- never created here (see
    `ensure_workspace`); this function only computes the path, validating
    `workshop_id` first."""
    _require_valid_workshop_id(workshop_id)
    root = workspaces_root()
    candidate = (root / workshop_id).resolve()
    if candidate.parent != root:
        # Structurally unreachable given a real UUID (no "/" or ".."
        # survives `is_valid_id`) -- defence in depth kept explicit anyway.
        raise WorkspacePathViolationError(
            f"Computed workspace path {candidate} for workshop_id={workshop_id!r} escapes root {root}"
        )
    return candidate


def _resolve_within(base: Path, relative: str) -> Path:
    """Joins `relative` onto `base` and refuses, explicitly, any attempt to
    leave `base` -- an absolute `relative`, a `..` component, or (via
    `Path.resolve()`, which follows symlinks) a symlink planted inside
    `base` that points outside it."""
    if not relative or relative.startswith(("/", "\\")):
        raise WorkspacePathViolationError(f"Workspace-relative path must be relative, got {relative!r}")
    parts = Path(relative).parts
    if any(part in ("..", "") for part in parts) or Path(relative).is_absolute():
        raise WorkspacePathViolationError(f"Workspace-relative path must not traverse, got {relative!r}")

    base_real = base.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base_real)
    except ValueError as exc:
        raise WorkspacePathViolationError(
            f"Path {relative!r} resolves to {candidate}, which escapes workspace root {base_real} "
            f"(possible symlink escape)"
        ) from exc
    return candidate


def ensure_workspace(workshop_id: str) -> Path:
    """Idempotently creates the Workshop's bounded directory + its
    `SOURCE_MATERIAL/` subdirectory. Safe to call repeatedly (e.g. after the
    directory was deleted out-of-band -- see `sync_workspace_from_db`)."""
    directory = workshop_dir(workshop_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / SOURCE_MATERIAL_DIR).mkdir(parents=True, exist_ok=True)
    return directory


def workspace_exists(workshop_id: str) -> bool:
    return workshop_dir(workshop_id).is_dir()


def write_governed_file(workshop_id: str, filename: str, content: str) -> Path:
    """Writes one of the fixed `GOVERNED_FILES` inside the Workshop's own
    directory. `filename` must be a literal caller-controlled CONSTANT from
    this module (`DISCOVERY_JSON`, etc.) -- never derived from external
    input; this function still refuses anything outside the allowlist as
    defence in depth."""
    if filename not in GOVERNED_FILES:
        raise WorkspacePathViolationError(
            f"{filename!r} is not one of the governed workspace files {sorted(GOVERNED_FILES)}"
        )
    directory = ensure_workspace(workshop_id)
    target = _resolve_within(directory, filename)
    target.write_text(content, encoding="utf-8")
    return target


def read_governed_file(workshop_id: str, filename: str) -> str | None:
    if filename not in GOVERNED_FILES:
        raise WorkspacePathViolationError(
            f"{filename!r} is not one of the governed workspace files {sorted(GOVERNED_FILES)}"
        )
    directory = workshop_dir(workshop_id)
    target = _resolve_within(directory, filename)
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8")


def _require_relative_name(relative_name: str) -> None:
    """Validates the CALLER-SUPPLIED fragment on its own, before it is
    ever concatenated onto `SOURCE_MATERIAL_DIR` -- catches an absolute
    path (e.g. `/etc/evil.txt`) that would otherwise stop looking absolute
    the moment it is joined onto a prefix string (`SOURCE_MATERIAL//etc/
    evil.txt` no longer starts with `/`). `_resolve_within`'s own checks
    against the FULL joined path still separately catch `..` traversal and
    symlink escape either way -- this is defence in depth, not a
    replacement for it."""
    if not relative_name or Path(relative_name).is_absolute() or relative_name.startswith(("/", "\\")):
        raise WorkspacePathViolationError(
            f"Source-material relative name must be relative, got {relative_name!r}"
        )


def write_source_material(workshop_id: str, relative_name: str, data: bytes) -> Path:
    """Writes one inert source-material file under `SOURCE_MATERIAL/`.
    Content is written and later read back as opaque bytes only -- nothing
    in this module (or anywhere in darwin.workshop) ever executes,
    interprets, or imports it (PID-004 sec55)."""
    _require_relative_name(relative_name)
    directory = ensure_workspace(workshop_id)
    target = _resolve_within(directory, f"{SOURCE_MATERIAL_DIR}/{relative_name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def read_source_material(workshop_id: str, relative_name: str) -> bytes | None:
    _require_relative_name(relative_name)
    directory = workshop_dir(workshop_id)
    target = _resolve_within(directory, f"{SOURCE_MATERIAL_DIR}/{relative_name}")
    if not target.is_file():
        return None
    return target.read_bytes()


def delete_workspace(workshop_id: str) -> None:
    """Deletes ONLY this Workshop's own bounded directory tree -- never
    anything outside it (the same `workshop_dir` validation/containment
    applies here as everywhere else in this module, so a crafted
    `workshop_id` can never make this reach a sibling Workshop's directory
    or an ancestor of the workspace root)."""
    directory = workshop_dir(workshop_id)
    root = workspaces_root()
    if directory == root or root not in directory.parents:
        raise WorkspacePathViolationError(f"Refusing to delete {directory} -- not a workshop leaf under {root}")
    if directory.is_dir():
        shutil.rmtree(directory)


def sync_workspace_from_db(*, workshop: dict, discoveries: list[dict], questions: list[dict],
                            decisions: list[dict], draft_payload: dict | None,
                            validation: dict | None) -> None:
    """Regenerates the Workshop's workspace files FROM canonical Postgres
    state (PID-004 sec49: "Filesystem workspace is not the only copy of
    critical decision truth"). Deliberately best-effort and non-canonical:
    callers (`darwin.workshop.service`) call this AFTER a canonical DB
    transaction has already committed, and must never let an `OSError`
    here fail an otherwise-successful API call -- this function itself
    raises normally (callers are responsible for the try/except), but nothing
    it does is required for `darwin.workshop.service.get_workshop` (etc) to
    return correct state: the database is always sufficient on its own
    (proved directly in tests/unit/test_workshop_workspace_security.py's
    deleted-workspace-survives-in-DB case)."""
    workshop_id = str(workshop["id"])
    ensure_workspace(workshop_id)
    write_governed_file(workshop_id, DISCOVERY_JSON, json.dumps(discoveries, indent=2, default=str))
    write_governed_file(
        workshop_id,
        CONTEXT_MD,
        f"# Workshop {workshop_id}\n\ncandidate_id: {workshop.get('candidate_id')}\n"
        f"status: {workshop.get('status')}\n",
    )
    open_questions = [q for q in questions if q.get("status") == "OPEN"]
    lines = [f"- [{q['status']}] {q['question_text']}" for q in questions]
    write_governed_file(workshop_id, QUESTIONS_MD, "\n".join(lines) + ("\n" if lines else ""))
    write_governed_file(
        workshop_id, DECISIONS_JSONL, "\n".join(json.dumps(d, default=str) for d in decisions) + ("\n" if decisions else "")
    )
    write_governed_file(
        workshop_id, SPECIFICATION_DRAFT_JSON, json.dumps(draft_payload, indent=2, default=str) if draft_payload else "null"
    )
    write_governed_file(workshop_id, VALIDATION_JSON, json.dumps(validation, indent=2, default=str) if validation else "null")
    logger.debug("workshop_workspace_synced", extra={"workshop_id": workshop_id, "open_questions": len(open_questions)})
