import pytest

from darwin.core.config import ConfigError, DarwinConfig


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
