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


def resolve_mendel_provider_api_key(file_env: str = "DARWIN_MENDEL_PROVIDER_API_KEY_FILE") -> str | None:
    """PID-004C WP2 -- resolve the MENDEL Claude Code provider credential.

    Deliberately narrower than `_secret` above: this credential supports
    ONLY the `*_FILE` convention, never an inline env var (`.env.example`'s
    own comment on `DARWIN_MENDEL_PROVIDER_API_KEY_FILE` is explicit:
    "Never set an inline ANTHROPIC_API_KEY= anywhere") -- an inline value
    would sit in this process's own environment for the lifetime of the
    process (visible via /proc/<pid>/environ, inherited by every future
    child process), which is an unnecessary exposure surface for a
    genuinely optional, cost-bearing external-provider secret.

    Returns `None` (never an empty string masquerading as a real key) when
    the slot is not configured at all -- callers (e.g. `darwin.workshop.
    api.register_mendel_routes`'s adapter-selection DI point) use `None`
    to decide "fall back to `DeterministicTestMendelAdapter`", never a
    falsy-but-present string. Raises `ConfigError` (fails loudly, per this
    module's own PID-001 §7 discipline) if the file IS configured but
    missing or empty -- an operator who set the slot and got it wrong
    must find out immediately, never silently run with no real MENDEL
    provider while believing one is configured.
    """
    file_path = os.environ.get(file_env, "").strip()
    if not file_path:
        return None
    p = Path(file_path)
    if not p.exists():
        raise ConfigError(f"{file_env}={file_path!r} does not exist.")
    key = p.read_text(encoding="utf-8").strip()
    if not key:
        raise ConfigError(f"{file_env}={file_path!r} is empty.")
    return key


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
    #: PID-004C WP2 -- the MENDEL Claude Code provider credential, or
    #: `None` when unconfigured (see `resolve_mendel_provider_api_key`).
    #: `repr=False` so it can never appear in a logged/printed `DarwinConfig`,
    #: mirroring `PostgresConfig.password`/`HermesConfig.password` above.
    mendel_provider_api_key: str | None = field(default=None, repr=False)

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
        mendel_provider_api_key = resolve_mendel_provider_api_key()
        return DarwinConfig(
            postgres=postgres, hermes=hermes, build=build, log_level=log_level,
            mendel_provider_api_key=mendel_provider_api_key,
        )
