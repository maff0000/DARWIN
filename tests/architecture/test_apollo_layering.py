"""PID-006B architecture-boundary proofs for `darwin.apollo`, mirroring
tests/architecture/test_research_contracts_layering.py's own discipline:
real, mechanical checks -- never comment-only assertions.
"""
from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import darwin.apollo as apollo_pkg

_FORBIDDEN_SOURCE_TOKENS = (
    "sqlite3",
    "sqlalchemy",
    " socket",
    "import socket",
    "requests.",
    "httpx.",
    "urllib.request",
    "eval(",
    "exec(",
    "subprocess",
    "__import__",
)

# psycopg IS legitimately used, but only inside persistence.py -- the one
# module PID-006B explicitly authorises to touch DARWIN_sql. Every other
# module in this package must never import it.
_PERSISTENCE_MODULE_NAME = "persistence.py"


def _module_paths(package) -> list[Path]:
    root = Path(package.__file__).resolve().parent
    return sorted(root.rglob("*.py"))


def _imported_module_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_no_forbidden_source_tokens_outside_persistence() -> None:
    for path in _module_paths(apollo_pkg):
        if path.name == _PERSISTENCE_MODULE_NAME:
            continue
        source = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_SOURCE_TOKENS:
            assert token not in source, f"{path} contains forbidden token {token!r}"


def test_only_persistence_module_imports_psycopg_or_research_store() -> None:
    for path in _module_paths(apollo_pkg):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_module_names(tree)
        db_imports = {
            name for name in imported
            if name == "psycopg" or name.startswith(("psycopg.", "darwin.research_store"))
        }
        if path.name == _PERSISTENCE_MODULE_NAME:
            continue
        assert not db_imports, f"{path} imports DB-layer module(s) outside persistence.py: {db_imports}"


def test_no_llm_or_broker_client_imports() -> None:
    forbidden_modules = ("openai", "anthropic", "ibapi", "ib_insync", "ccxt", "MetaTrader5")
    for path in _module_paths(apollo_pkg):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_module_names(tree)
        for forbidden in forbidden_modules:
            assert not any(name == forbidden or name.startswith(f"{forbidden}.") for name in imported), (
                f"{path} imports forbidden module {forbidden!r}"
            )


def test_apollo_package_imports_cleanly() -> None:
    importlib.import_module("darwin.apollo")
    for _finder, name, _ispkg in pkgutil.walk_packages(apollo_pkg.__path__, prefix="darwin.apollo."):
        importlib.import_module(name)


def test_no_hardcoded_tp_first_component_anywhere_in_apollo() -> None:
    """PID-006B intrabar policy: 'Do not implement TP_FIRST -- it is
    explicitly not authorised for this package.' Proven against the real,
    live capability allowlist data structure -- not a source-text grep,
    which would also (correctly) flag the module docstrings that document
    this very exclusion in prose."""
    from darwin.apollo.capability import _SUPPORTED

    for axis, allowed in _SUPPORTED.items():
        for component in allowed:
            assert component.component_id != "TP_FIRST", f"axis {axis} allowlists TP_FIRST, which PID-006B forbids"
