"""PID-003 SCOUT Trader.dev adapter unit tests (docs/pids/PID-003-SCOUT.md
sec3/sec5). Every network call in this file goes through `httpx.MockTransport`
-- no real network call is ever made, including for the security/SSRF tests
(a real malicious host is never contacted, per the PID's own testing
instruction)."""
from __future__ import annotations

import json

import httpx
import pytest

from darwin.scout.domain import RuleAvailability
from darwin.scout.trader_dev_adapter import (
    ALLOWED_API_HOST,
    MAX_PAGE_SIZE,
    USER_AGENT,
    DisallowedHostError,
    ScoutSourceError,
    ScoutSourceMalformedResponseError,
    ScoutSourceUnavailableError,
    TraderDevAdapter,
    _validate_url_host,
    classify_rule_availability,
    normalize_record,
)

SEARCH_HIT_FIXTURE = {
    "id": "01M2R92EBYK57YH173W1TP9SP9",
    "name": "LINREG 100 SL1.5TP3.0",
    "symbol": "XAUUSD",
    "timeframe": "60",
    "version": 1,
    "forkedFromStrategyId": None,
    "author": None,
    "createdAt": 1789668702591,
    "updatedAt": 1789668702591,
    "result": {
        "resultId": "01M2R92DY6YXMDYK7FEMZTAZWS",
        "netProfitPct": -70.08602735,
        "viewUrl": "https://mcp-api.trader.dev/backtest/01M2R92DY6YXMDYK7FEMZTAZWS",
        "forkJsonUrl": "https://mcp-api.trader.dev/backtest/01M2R92DY6YXMDYK7FEMZTAZWS/fork.json",
    },
}

BACKTEST_RESULT_DETAIL_FIXTURE = {
    "id": "01M2R92DY6YXMDYK7FEMZTAZWS",
    "strategyId": "01M2R92EBYK57YH173W1TP9SP9",
    "symbol": "XAUUSD",
    "timeframe": "60",
    "netProfitPct": -70.08602735,
    "maxDrawdownPct": 72.16667629,
    "winRatePct": 22.5170068,
    "profitFactor": 0.69658106,
    "totalTrades": 1470,
    "sharpeRatio": -1.36014385,
    "sortinoRatio": -0.68045882,
    "visibility": "public",
    "r2Url": "https://pub-5880a55c41fd4cd1a11146f4fd522fbe.r2.dev/backtests/01M2R92DY6YXMDYK7FEMZTAZWS.json.gz",
}


def _json_response(status_code: int, body) -> httpx.Response:
    return httpx.Response(status_code, content=json.dumps(body).encode("utf-8"),
                           headers={"content-type": "application/json"})


def _adapter_with_handler(handler) -> TraderDevAdapter:
    return TraderDevAdapter(transport=httpx.MockTransport(handler))


# --- host/URL validation (SSRF defence) --------------------------------------

def test_validate_url_host_accepts_the_allowed_api_host():
    _validate_url_host(f"https://{ALLOWED_API_HOST}/strategies/stats")  # must not raise


def test_validate_url_host_rejects_non_https():
    with pytest.raises(DisallowedHostError):
        _validate_url_host(f"http://{ALLOWED_API_HOST}/strategies/stats")


def test_validate_url_host_rejects_a_disallowed_host():
    with pytest.raises(DisallowedHostError):
        _validate_url_host("https://evil.example.com/strategies/stats")


def test_validate_url_host_rejects_localhost():
    with pytest.raises(DisallowedHostError):
        _validate_url_host("https://localhost/strategies/stats")


def test_validate_url_host_rejects_an_ip_literal_impersonation_attempt():
    with pytest.raises(DisallowedHostError):
        _validate_url_host("https://169.254.169.254/latest/meta-data/")


def test_validate_url_host_rejects_r2_url_unless_allow_r2_flag_set():
    with pytest.raises(DisallowedHostError):
        _validate_url_host("https://pub-abc123.r2.dev/backtests/x.json.gz", allow_r2=False)
    _validate_url_host("https://pub-abc123.r2.dev/backtests/x.json.gz", allow_r2=True)  # must not raise


def test_validate_url_host_rejects_dns_rebinding_to_a_private_address(monkeypatch):
    """Even if `mcp-api.trader.dev` (an ALLOWED hostname) somehow resolved
    to a private/loopback address, the adapter must still refuse it --
    DNS-rebinding defence, tested deterministically by making the allowed
    hostname resolve to 127.0.0.1 for this test only."""
    import socket

    import darwin.scout.trader_dev_adapter as adapter_module

    def fake_getaddrinfo(host, port):
        assert host == ALLOWED_API_HOST
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(adapter_module.socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(DisallowedHostError):
        _validate_url_host(f"https://{ALLOWED_API_HOST}/strategies/stats")


def test_redirect_to_a_disallowed_host_is_rejected(monkeypatch):
    """PID-003 sec5: 'a redirect to a non-allowed host is rejected in a
    real test (fake it with a local test server or mock, don't hit a real
    malicious host)'. httpx.MockTransport IS that mock."""
    import darwin.scout.trader_dev_adapter as adapter_module

    def fake_getaddrinfo(host, port):
        import socket as _socket
        return [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(adapter_module.socket, "getaddrinfo", fake_getaddrinfo)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == ALLOWED_API_HOST
        return httpx.Response(302, headers={"location": "https://evil.example.com/steal"})

    with _adapter_with_handler(handler) as adapter, pytest.raises(DisallowedHostError):
        adapter.get_stats()


def test_redirect_to_an_allowed_host_is_followed(monkeypatch):
    import darwin.scout.trader_dev_adapter as adapter_module

    def fake_getaddrinfo(host, port):
        import socket as _socket
        return [(_socket.AF_INET, _socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(adapter_module.socket, "getaddrinfo", fake_getaddrinfo)

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(302, headers={"location": f"https://{ALLOWED_API_HOST}/strategies/stats"})
        return _json_response(200, {"totalStrategies": 1, "totalBacktests": 1})

    with _adapter_with_handler(handler) as adapter:
        result = adapter.get_stats()
    assert result == {"totalStrategies": 1, "totalBacktests": 1}


def test_no_authorization_header_is_ever_sent():
    """PID-003 sec5: no Trader.dev credential exists or is ever used."""
    seen_headers = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return _json_response(200, {"totalStrategies": 1, "totalBacktests": 1})

    with _adapter_with_handler(handler) as adapter:
        adapter.get_stats()
    assert "authorization" not in {k.lower() for k in seen_headers}
    assert seen_headers.get("user-agent") == USER_AGENT
    assert "key" not in USER_AGENT.lower() and "token" not in USER_AGENT.lower()


# --- retries / rate-limit / malformed responses ------------------------------

def test_transient_5xx_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return _json_response(200, {"totalStrategies": 1, "totalBacktests": 1})

    with _adapter_with_handler(handler) as adapter:
        result = adapter.get_stats()
    assert result["totalStrategies"] == 1
    assert calls["n"] == 2


def test_persistent_5xx_raises_source_unavailable_after_bounded_retries():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _adapter_with_handler(handler) as adapter, pytest.raises(ScoutSourceUnavailableError):
        adapter.get_stats()


def test_timeout_raises_source_unavailable_not_a_bare_exception():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated timeout")

    with _adapter_with_handler(handler) as adapter, pytest.raises(ScoutSourceUnavailableError):
        adapter.get_stats()


def test_rate_limit_429_raises_source_unavailable():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, content=b'{"error":"rate_limited"}')

    with _adapter_with_handler(handler) as adapter, pytest.raises(ScoutSourceUnavailableError):
        adapter.get_stats()


def test_malformed_non_json_response_raises_malformed_error():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>not json</html>")

    with _adapter_with_handler(handler) as adapter, pytest.raises(ScoutSourceMalformedResponseError):
        adapter.get_stats()


def test_404_on_backtest_result_returns_none_not_an_exception():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    with _adapter_with_handler(handler) as adapter:
        assert adapter.get_backtest_result("does-not-exist") is None


def test_search_strategies_rejects_limit_above_server_cap():
    with _adapter_with_handler(lambda r: _json_response(200, {})) as adapter, pytest.raises(ScoutSourceError):
        adapter.search_strategies(limit=MAX_PAGE_SIZE + 1)


def test_search_strategies_rejects_an_unsupported_sort_value():
    with _adapter_with_handler(lambda r: _json_response(200, {})) as adapter, pytest.raises(ScoutSourceError):
        adapter.search_strategies(sort="not-a-real-sort")


def test_check_reachable_never_raises_on_failure():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("simulated")

    with _adapter_with_handler(handler) as adapter:
        assert adapter.check_reachable() is False


# --- record normalisation ------------------------------------------------------

def test_normalize_record_preserves_symbol_and_timeframe_verbatim():
    record = normalize_record(SEARCH_HIT_FIXTURE, BACKTEST_RESULT_DETAIL_FIXTURE)
    assert record.symbol == "XAUUSD"
    assert record.timeframe == "60"  # NOT normalized to "H1"/"1h" — verbatim


def test_normalize_record_carries_the_exact_metric_values():
    record = normalize_record(SEARCH_HIT_FIXTURE, BACKTEST_RESULT_DETAIL_FIXTURE)
    assert record.claim_payload["net_pnl_percent"] == -70.08602735
    assert record.claim_payload["trade_count"] == 1470


def test_normalize_record_rule_availability_is_access_restricted_for_reachable_public_record():
    record = normalize_record(SEARCH_HIT_FIXTURE, BACKTEST_RESULT_DETAIL_FIXTURE)
    assert record.rule_availability == RuleAvailability.ACCESS_RESTRICTED


def test_normalize_record_preserves_fork_lineage_when_present():
    hit = dict(SEARCH_HIT_FIXTURE)
    hit["forkedFromStrategyId"] = "01PARENTSTRATEGYIDXXXXXX"
    record = normalize_record(hit, BACKTEST_RESULT_DETAIL_FIXTURE)
    assert record.forked_from_source_strategy_id == "01PARENTSTRATEGYIDXXXXXX"


def test_normalize_record_missing_result_id_is_malformed():
    hit = dict(SEARCH_HIT_FIXTURE)
    hit["result"] = {}
    with pytest.raises(ScoutSourceMalformedResponseError):
        normalize_record(hit, None)


# --- classify_rule_availability: the three degraded states ------------------

def test_classify_rule_availability_none_detail_is_unavailable():
    assert classify_rule_availability(None) == RuleAvailability.UNAVAILABLE


def test_classify_rule_availability_private_visibility_is_unavailable():
    assert classify_rule_availability({"visibility": "private"}) == RuleAvailability.UNAVAILABLE


def test_classify_rule_availability_quarantined_visibility_is_partial():
    assert classify_rule_availability({"visibility": "quarantined", "netProfitPct": 1}) == RuleAvailability.PARTIAL


def test_classify_rule_availability_reachable_empty_payload_is_unknown():
    assert classify_rule_availability({"visibility": "public"}) == RuleAvailability.UNKNOWN


def test_classify_rule_availability_normal_public_record_is_access_restricted():
    assert classify_rule_availability(BACKTEST_RESULT_DETAIL_FIXTURE) == RuleAvailability.ACCESS_RESTRICTED


# --- bounded pagination + per-record resilience ------------------------------

def test_iter_public_records_bounds_total_fetched_to_max_records():
    def search_page(offset: int) -> dict:
        hit = dict(SEARCH_HIT_FIXTURE)
        hit["id"] = f"strategy-{offset}"
        hit["result"] = dict(SEARCH_HIT_FIXTURE["result"])
        hit["result"]["resultId"] = f"result-{offset}"
        return {"results": [hit], "limit": 1, "offset": offset, "hasMore": True, "sort": "recent"}

    def handler(request: httpx.Request) -> httpx.Response:
        if "/strategies/search" in str(request.url):
            offset = int(dict(request.url.params).get("offset", 0))
            return _json_response(200, search_page(offset))
        return _json_response(200, dict(BACKTEST_RESULT_DETAIL_FIXTURE))

    with _adapter_with_handler(handler) as adapter:
        records, errors = adapter.iter_public_records(symbol="XAUUSD", max_records=3)
    assert len(records) == 3
    assert errors == []


def test_iter_public_records_collects_per_record_errors_without_aborting():
    hit_ok = dict(SEARCH_HIT_FIXTURE)
    hit_bad = dict(SEARCH_HIT_FIXTURE)
    hit_bad["id"] = "bad-strategy"
    hit_bad["result"] = {}  # missing resultId -> malformed, caught per-record

    def handler(request: httpx.Request) -> httpx.Response:
        if "/strategies/search" in str(request.url):
            return _json_response(
                200, {"results": [hit_bad, hit_ok], "limit": 2, "offset": 0, "hasMore": False, "sort": "recent"}
            )
        return _json_response(200, dict(BACKTEST_RESULT_DETAIL_FIXTURE))

    with _adapter_with_handler(handler) as adapter:
        records, errors = adapter.iter_public_records(symbol="XAUUSD", max_records=10)
    assert len(records) == 1
    assert len(errors) == 1
    assert "bad-strategy" in errors[0]
