"""Typed external configuration — created once at startup, never re-read ad hoc.

PID-001 §7: no host-specific defaults that silently point to real infrastructure,
no embedded credentials, missing required config fails loudly, secrets are
supplied externally (inline for disposable/dev use, or via a `*_FILE` path for
persistent deployment).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid. Fails loudly."""


def _secret(value_env: str, file_env: str, *, required: bool) -> str:
    """Resolve a secret from an inline env var or a mounted file, never both silently.

    Prefers the file path when both are set to zero (an operator error) rather
    than guessing which one is authoritative.
    """
    inline = os.environ.get(value_env, "").strip()
    file_path = os.environ.get(file_env, "").strip()

    if inline and file_path and Path(file_path).exists():
        raise ConfigError(
            f"Both {value_env} and {file_env} are set — ambiguous secret source. "
            f"Set exactly one."
        )

    if file_path:
        p = Path(file_path)
        if not p.exists():
            if inline:
                # File configured but not mounted yet (e.g. disposable/dev run) —
                # fall back to inline only if explicitly provided.
                return inline
            if required:
                raise ConfigError(f"Secret file {file_env}={file_path!r} does not exist.")
            return ""
        return p.read_text(encoding="utf-8").strip()

    if inline:
        return inline

    if required:
        raise ConfigError(f"Required secret missing: set {value_env} or {file_env}.")
    return ""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Required configuration missing: {name}")
    return value


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)

    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        )


@dataclass(frozen=True)
class HermesConfig:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class BuildConfig:
    version: str
    commit: str
    build_time: str
    environment: str


@dataclass(frozen=True)
class DarwinConfig:
    postgres: PostgresConfig
    hermes: HermesConfig
    build: BuildConfig
    log_level: str
    #: PID-004C WP2 auth-architecture correction (2026-09-19) -- an
    #: explicit, narrow, OFF-BY-DEFAULT opt-in: `DARWIN_MENDEL_USE_REAL_
    #: PROVIDER=1` makes `darwin.workshop.api.register_mendel_routes`'s
    #: adapter-selection DI point wire the real `ClaudeCodeMendelAdapter`
    #: (darwin.workshop.claude_code_mendel_adapter) instead of
    #: `DeterministicTestMendelAdapter`. There is deliberately no
    #: credential-based signal here any more -- MENDEL no longer
    #: configures or uses any Anthropic API key at all; authentication is
    #: entirely the ambient Claude Code CLI installation's own
    #: subscription/OAuth login state (see `ClaudeCodeMendelAdapter.
    #: auth_status`/`get_claude_auth_status`). Off by default, explicit,
    #: never silently active -- mirrors `mendel_e2e_fixture_adapter_
    #: enabled`'s own discipline below. `darwin_core` must never fail to
    #: start over this: the default (`False`) always keeps the
    #: deterministic test adapter, which has no external dependency at
    #: all.
    mendel_use_real_provider: bool = False
    #: PID-004C WP3 -- an explicit, narrow, OFF-BY-DEFAULT test-only escape
    #: hatch: `DARWIN_MENDEL_E2E_FIXTURE_ADAPTER=1` makes
    #: `darwin.workshop.api.register_mendel_routes`'s adapter-selection DI
    #: point wire a `DeterministicTestMendelAdapter` pre-loaded with a
    #: small, fixed, illustrative proposal set instead of the bare
    #: (zero-proposal) default -- WITHOUT requiring a caller-supplied
    #: `adapter=` at construction time. This exists ONLY so a real browser
    #: (Playwright, against a real running darwin_core container) can
    #: exercise a genuine MENDEL invocation -> proposal render -> accept/
    #: reject/stale round trip end to end, since a browser cannot inject a
    #: Python test double directly. Never set in production; a real
    #: deployment never sets this var, so this field defaults to `False`
    #: and changes nothing about existing behaviour.
    mendel_e2e_fixture_adapter_enabled: bool = False

    @staticmethod
    def load() -> DarwinConfig:
        """Build configuration once from the process environment. Fails loudly."""
        postgres = PostgresConfig(
            host=_require("DARWIN_PG_HOST"),
            port=_int("DARWIN_PG_PORT", 5432),
            database=_require("DARWIN_PG_DB"),
            user=_require("DARWIN_PG_USER"),
            password=_secret("DARWIN_PG_PASSWORD", "DARWIN_PG_PASSWORD_FILE", required=True),
        )
        hermes = HermesConfig(
            host=_require("DARWIN_HERMES_HOST"),
            port=_int("DARWIN_HERMES_PORT", 3307),
            database=_require("DARWIN_HERMES_DB"),
            user=_require("DARWIN_HERMES_USER"),
            password=_secret("DARWIN_HERMES_PASSWORD", "DARWIN_HERMES_PASSWORD_FILE", required=True),
        )
        build = BuildConfig(
            version=os.environ.get("DARWIN_BUILD_VERSION", "0.0.0-unset"),
            commit=os.environ.get("DARWIN_BUILD_COMMIT", "unknown"),
            build_time=os.environ.get("DARWIN_BUILD_TIME", "unknown"),
            environment=os.environ.get("DARWIN_ENV", "dev"),
        )
        log_level = os.environ.get("DARWIN_LOG_LEVEL", "INFO").upper()
        mendel_use_real_provider = (
            os.environ.get("DARWIN_MENDEL_USE_REAL_PROVIDER", "").strip() == "1"
        )
        mendel_e2e_fixture_adapter_enabled = (
            os.environ.get("DARWIN_MENDEL_E2E_FIXTURE_ADAPTER", "").strip() == "1"
        )
        return DarwinConfig(
            postgres=postgres, hermes=hermes, build=build, log_level=log_level,
            mendel_use_real_provider=mendel_use_real_provider,
            mendel_e2e_fixture_adapter_enabled=mendel_e2e_fixture_adapter_enabled,
        )
