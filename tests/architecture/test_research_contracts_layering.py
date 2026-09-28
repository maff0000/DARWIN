"""PID-006A architecture-boundary proofs (docs/pids/PID-006-APOLLO.md
sec5/sec35/hard-exclusions).

Real, mechanical checks -- never comment-only assertions:

- `darwin.specification` never imports `darwin.research_contracts`
  (one-way dependency direction), proven via a real `ast`-based import
  walk of every module in `darwin/specification/`, not a grep that a
  reformatted import line could quietly defeat.
- `darwin.research_contracts` contains no replay/simulation-shaped code
  -- proven by walking every class/dataclass-field name defined in the
  package for order/position/fill/ledger/equity/broker-shaped
  identifiers, and by a source-token check for SQL drivers, network
  clients, and arbitrary-code-execution builtins.
"""
from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import darwin.research_contracts as research_contracts_pkg
import darwin.specification as specification_pkg

_FORBIDDEN_REPLAY_TOKENS = (
    "order",
    "position",
    "fill",
    "ledger",
    "equity",
    "drawdown",
    "broker",
    "pnl",
    "trade",
    "maefe",
    "mae",
    "mfe",
    "stoploss",
    "takeprofit",
    "trailingstop",
    "breakeven",
)

# Deliberately not flagged as "replay-shaped" even though they share a
# substring with a forbidden token above -- both are governed IDENTITY
# concepts this work package explicitly authorises (PID-006A sec7/sec9),
# never execution/simulation state.
_ALLOWED_FALSE_POSITIVES = {
    "researchpartitionpolicyversion",  # contains no forbidden token; listed defensively
}

_FORBIDDEN_SOURCE_TOKENS = (
    "psycopg",
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


def test_specification_never_imports_research_contracts() -> None:
    for path in _module_paths(specification_pkg):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_module_names(tree)
        offending = {name for name in imported if name.startswith("darwin.research_contracts")}
        assert not offending, f"{path} imports research_contracts: {offending}"


def test_research_contracts_may_import_specification() -> None:
    """Sanity check on the test above: the dependency direction really is
    exercised, not merely absent because nothing imports anything."""
    found_specification_import = False
    for path in _module_paths(research_contracts_pkg):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_module_names(tree)
        if any(name.startswith("darwin.specification") for name in imported):
            found_specification_import = True
    assert found_specification_import


def test_no_replay_or_simulation_shaped_classes() -> None:
    for path in _module_paths(research_contracts_pkg):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                lowered = node.name.lower()
                if lowered in _ALLOWED_FALSE_POSITIVES:
                    continue
                for token in _FORBIDDEN_REPLAY_TOKENS:
                    assert token not in lowered, f"{path}: class {node.name!r} looks replay/simulation-shaped"
                for stmt in node.body:
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        field_lowered = stmt.target.id.lower()
                        # `..._methodology` fields are PID-006A sec7's own
                        # required governed-IDENTITY axis names (e.g.
                        # `price_fill_methodology`) -- a reference to which
                        # fill/cost/timing METHODOLOGY was selected, never a
                        # live execution object. Exempted by construction,
                        # not by silently narrowing the token list itself.
                        if field_lowered.endswith("_methodology"):
                            continue
                        for token in _FORBIDDEN_REPLAY_TOKENS:
                            assert token not in field_lowered, (
                                f"{path}: class {node.name!r} field {stmt.target.id!r} looks "
                                f"replay/simulation-shaped"
                            )


def test_no_forbidden_source_tokens() -> None:
    """No SQL driver, network client, or arbitrary-code-execution builtin
    appears anywhere in darwin.research_contracts' own source (PID-006A
    sec2 hard prohibitions: no SQL, no network access, no eval/exec, no
    arbitrary plugin/code execution)."""
    for path in _module_paths(research_contracts_pkg):
        source = path.read_text(encoding="utf-8")
        for token in _FORBIDDEN_SOURCE_TOKENS:
            assert token not in source, f"{path} contains forbidden token {token!r}"


def test_no_llm_or_broker_client_imports() -> None:
    """No LLM client library and no broker/execution client is imported
    anywhere in darwin.research_contracts."""
    forbidden_modules = ("openai", "anthropic", "ibapi", "ib_insync", "ccxt", "MetaTrader5")
    for path in _module_paths(research_contracts_pkg):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = _imported_module_names(tree)
        for forbidden in forbidden_modules:
            assert not any(name == forbidden or name.startswith(f"{forbidden}.") for name in imported), (
                f"{path} imports forbidden module {forbidden!r}"
            )


def test_research_contracts_package_imports_cleanly() -> None:
    """Every submodule actually imports without error -- a real smoke test
    that the module-placement/dependency graph above is not merely
    theoretical."""
    for _finder, name, _ispkg in pkgutil.walk_packages(
        research_contracts_pkg.__path__, prefix="darwin.research_contracts."
    ):
        importlib.import_module(name)
