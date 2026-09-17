"""PID-002 ARENA — the two narrow read-only API additions, plus the static
mount boundary (never intercepting /api/...). STATIC_DIR is monkeypatched in
every test that cares about it, rather than relying on whatever happens to
exist on disk at test-run time (the real frontend build is a Docker-build-
time artifact, not something backend unit tests should depend on)."""
from fastapi.testclient import TestClient

from darwin.app import create_app
from darwin.core.config import BuildConfig, DarwinConfig, HermesConfig, PostgresConfig


def _config() -> DarwinConfig:
    return DarwinConfig(
        postgres=PostgresConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        hermes=HermesConfig(host="127.0.0.1", port=1, database="nope", user="nope", password="nope"),
        build=BuildConfig(version="test", commit="deadbeef", build_time="2026-09-17T00:00:00Z", environment="test"),
        log_level="INFO",
    )


def test_list_instrument_definitions_returns_governed_registry():
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/instrument-definitions")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(d["instrument_id"] == "XAU_USD" for d in items)
    xau = next(d for d in items if d["instrument_id"] == "XAU_USD")
    assert xau["base_asset"] == "XAU"
    assert xau["quote_asset"] == "USD"
    assert xau["base_quantity_unit"] == "TROY_OUNCE"
    assert xau["price_unit"] == "USD_PER_TROY_OUNCE"
    assert len(xau["fingerprint"]) == 64  # sha256 hex


def test_get_instrument_definition_by_id():
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/instrument-definitions/XAU_USD")
    assert resp.status_code == 200
    assert resp.json()["instrument_id"] == "XAU_USD"


def test_get_instrument_definition_unknown_returns_404():
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/instrument-definitions/EUR_USD")
    assert resp.status_code == 404


def test_migrations_endpoint_returns_structured_state(monkeypatch):
    monkeypatch.setattr(
        "darwin.app.migration_state",
        lambda cfg, migrations_dir: {
            "total_migrations": 4,
            "applied": ["0001_foundation", "0002_x", "0003_y", "0004_z"],
            "pending": [],
            "up_to_date": True,
        },
    )
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/migrations")
    assert resp.status_code == 200
    body = resp.json()
    assert body["up_to_date"] is True
    assert body["total_migrations"] == 4
    assert body["pending"] == []


def test_spa_fallback_never_intercepts_the_api_surface(tmp_path, monkeypatch):
    """Even with a real ARENA bundle mounted, api/... paths must 404 through
    the API router's own semantics, never fall through to the SPA catch-all."""
    (tmp_path / "index.html").write_text("<html>arena</html>")
    (tmp_path / "assets").mkdir()
    monkeypatch.setattr("darwin.app.STATIC_DIR", tmp_path)
    client = TestClient(create_app(_config()))
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    # and a real unknown API path never returns the SPA's index.html
    assert b"arena" not in resp.content


def test_no_static_dir_means_no_arena_mount_and_api_still_works(tmp_path, monkeypatch):
    """A bare API-only run (no frontend built) is a legitimate mode, not an
    error — the existing API must keep working, and a browser route falls
    through to a plain 404 rather than a broken mount."""
    monkeypatch.setattr("darwin.app.STATIC_DIR", tmp_path / "does-not-exist")
    client = TestClient(create_app(_config()))
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/datasets").status_code == 404


def test_spa_route_serves_index_html_when_bundle_exists(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<html>arena-bundle</html>")
    monkeypatch.setattr("darwin.app.STATIC_DIR", tmp_path)
    client = TestClient(create_app(_config()))
    resp = client.get("/datasets/some-id")
    assert resp.status_code == 200
    assert b"arena-bundle" in resp.content
