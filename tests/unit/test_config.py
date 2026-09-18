import pytest

from darwin.core.config import (
    ConfigError,
    DarwinConfig,
    resolve_mendel_provider_api_key,
)


def _clear_darwin_env(monkeypatch):
    for key in list(__import__("os").environ):
        if key.startswith("DARWIN_"):
            monkeypatch.delenv(key, raising=False)


def test_missing_required_config_fails_loudly(monkeypatch):
    _clear_darwin_env(monkeypatch)
    with pytest.raises(ConfigError):
        DarwinConfig.load()


def test_inline_secret_used_when_no_file(monkeypatch):
    _clear_darwin_env(monkeypatch)
    monkeypatch.setenv("DARWIN_PG_HOST", "localhost")
    monkeypatch.setenv("DARWIN_PG_DB", "darwin")
    monkeypatch.setenv("DARWIN_PG_USER", "darwin_app")
    monkeypatch.setenv("DARWIN_PG_PASSWORD", "secret123")
    monkeypatch.setenv("DARWIN_HERMES_HOST", "hermes-host")
    monkeypatch.setenv("DARWIN_HERMES_DB", "tradingSignals")
    monkeypatch.setenv("DARWIN_HERMES_USER", "darwin_ro")
    monkeypatch.setenv("DARWIN_HERMES_PASSWORD", "hermes_secret")

    cfg = DarwinConfig.load()
    assert cfg.postgres.password == "secret123"
    assert cfg.hermes.password == "hermes_secret"
    assert cfg.postgres.port == 5432
    assert cfg.hermes.port == 3307


def test_secret_file_takes_precedence_over_missing_inline(tmp_path, monkeypatch):
    _clear_darwin_env(monkeypatch)
    secret_file = tmp_path / "pg_password"
    secret_file.write_text("from-file-secret\n")

    monkeypatch.setenv("DARWIN_PG_HOST", "localhost")
    monkeypatch.setenv("DARWIN_PG_DB", "darwin")
    monkeypatch.setenv("DARWIN_PG_USER", "darwin_app")
    monkeypatch.setenv("DARWIN_PG_PASSWORD_FILE", str(secret_file))
    monkeypatch.setenv("DARWIN_HERMES_HOST", "hermes-host")
    monkeypatch.setenv("DARWIN_HERMES_DB", "tradingSignals")
    monkeypatch.setenv("DARWIN_HERMES_USER", "darwin_ro")
    monkeypatch.setenv("DARWIN_HERMES_PASSWORD", "hermes_secret")

    cfg = DarwinConfig.load()
    assert cfg.postgres.password == "from-file-secret"


def test_repr_never_exposes_password(monkeypatch):
    _clear_darwin_env(monkeypatch)
    monkeypatch.setenv("DARWIN_PG_HOST", "localhost")
    monkeypatch.setenv("DARWIN_PG_DB", "darwin")
    monkeypatch.setenv("DARWIN_PG_USER", "darwin_app")
    monkeypatch.setenv("DARWIN_PG_PASSWORD", "super-secret-value")
    monkeypatch.setenv("DARWIN_HERMES_HOST", "hermes-host")
    monkeypatch.setenv("DARWIN_HERMES_DB", "tradingSignals")
    monkeypatch.setenv("DARWIN_HERMES_USER", "darwin_ro")
    monkeypatch.setenv("DARWIN_HERMES_PASSWORD", "hermes-secret-value")

    cfg = DarwinConfig.load()
    assert "super-secret-value" not in repr(cfg.postgres)
    assert "hermes-secret-value" not in repr(cfg.hermes)


# ============================================================================
# PID-004C WP2 -- DARWIN_MENDEL_PROVIDER_API_KEY_FILE resolution.
# ============================================================================


def test_resolve_mendel_provider_api_key_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("DARWIN_MENDEL_PROVIDER_API_KEY_FILE", raising=False)
    assert resolve_mendel_provider_api_key() is None


def test_resolve_mendel_provider_api_key_reads_the_configured_file(tmp_path, monkeypatch):
    secret_file = tmp_path / "mendel_key"
    secret_file.write_text("sk-real-looking-but-fake-test-key\n")
    monkeypatch.setenv("DARWIN_MENDEL_PROVIDER_API_KEY_FILE", str(secret_file))
    assert resolve_mendel_provider_api_key() == "sk-real-looking-but-fake-test-key"


def test_resolve_mendel_provider_api_key_raises_loudly_if_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DARWIN_MENDEL_PROVIDER_API_KEY_FILE", str(tmp_path / "does_not_exist"))
    with pytest.raises(ConfigError):
        resolve_mendel_provider_api_key()


def test_resolve_mendel_provider_api_key_raises_loudly_if_file_empty(tmp_path, monkeypatch):
    secret_file = tmp_path / "empty_mendel_key"
    secret_file.write_text("   \n")
    monkeypatch.setenv("DARWIN_MENDEL_PROVIDER_API_KEY_FILE", str(secret_file))
    with pytest.raises(ConfigError):
        resolve_mendel_provider_api_key()


def test_darwin_config_load_carries_mendel_provider_api_key_and_never_reprs_it(tmp_path, monkeypatch):
    _clear_darwin_env(monkeypatch)
    monkeypatch.setenv("DARWIN_PG_HOST", "localhost")
    monkeypatch.setenv("DARWIN_PG_DB", "darwin")
    monkeypatch.setenv("DARWIN_PG_USER", "darwin_app")
    monkeypatch.setenv("DARWIN_PG_PASSWORD", "secret123")
    monkeypatch.setenv("DARWIN_HERMES_HOST", "hermes-host")
    monkeypatch.setenv("DARWIN_HERMES_DB", "tradingSignals")
    monkeypatch.setenv("DARWIN_HERMES_USER", "darwin_ro")
    monkeypatch.setenv("DARWIN_HERMES_PASSWORD", "hermes_secret")
    secret_file = tmp_path / "mendel_key"
    secret_file.write_text("sk-real-looking-but-fake-test-key")
    monkeypatch.setenv("DARWIN_MENDEL_PROVIDER_API_KEY_FILE", str(secret_file))

    cfg = DarwinConfig.load()
    assert cfg.mendel_provider_api_key == "sk-real-looking-but-fake-test-key"
    assert "sk-real-looking-but-fake-test-key" not in repr(cfg)


def test_darwin_config_load_leaves_mendel_provider_api_key_none_when_unconfigured(monkeypatch):
    _clear_darwin_env(monkeypatch)
    monkeypatch.setenv("DARWIN_PG_HOST", "localhost")
    monkeypatch.setenv("DARWIN_PG_DB", "darwin")
    monkeypatch.setenv("DARWIN_PG_USER", "darwin_app")
    monkeypatch.setenv("DARWIN_PG_PASSWORD", "secret123")
    monkeypatch.setenv("DARWIN_HERMES_HOST", "hermes-host")
    monkeypatch.setenv("DARWIN_HERMES_DB", "tradingSignals")
    monkeypatch.setenv("DARWIN_HERMES_USER", "darwin_ro")
    monkeypatch.setenv("DARWIN_HERMES_PASSWORD", "hermes_secret")

    cfg = DarwinConfig.load()
    assert cfg.mendel_provider_api_key is None
