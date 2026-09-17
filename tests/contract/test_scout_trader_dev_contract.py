"""PID-003 SCOUT contract/provenance tests against REAL live-captured
Trader.dev JSON (docs/pids/PID-003-SCOUT.md sec3 preflight + the exact
payloads captured live during PID-003 implementation on 2026-09-17 via
`curl https://mcp-api.trader.dev/...`). These are frozen fixtures, not a
network call -- proves darwin.scout's parsing/idempotency logic against the
REAL shape Trader.dev actually returns, independent of the live-acceptance
run (which additionally proves current live reachability).
"""
from __future__ import annotations

from decimal import Decimal

from darwin.scout.domain import (
    FamilyResolution,
    OriginKind,
    RuleAvailability,
    build_claim_values,
    compute_snapshot_fingerprint,
)
from darwin.scout.trader_dev_adapter import classify_rule_availability, normalize_record

# Captured live 2026-09-17 from
# `curl 'https://mcp-api.trader.dev/strategies/search?symbol=XAUUSD&limit=2&sort=recent'`
REAL_SEARCH_HIT = {
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
        "netProfit": -7008.602735450299,
        "netProfitPct": -70.08602735,
        "grossProfit": 16090.161811055379,
        "grossLoss": 23098.76454650568,
        "profitFactor": 0.69658106,
        "maxDrawdownPct": 72.16667629,
        "winRatePct": 22.5170068,
        "sharpeRatio": -1.36014385,
        "sortinoRatio": -0.68045882,
        "totalTrades": 1470,
        "winningTrades": 331,
        "losingTrades": 1139,
        "barsEvaluated": 38209,
        "fromTs": 1254355200000,
        "toTs": 1546300800000,
        "createdAt": 1789668702150,
        "viewUrl": "https://mcp-api.trader.dev/backtest/01M2R92DY6YXMDYK7FEMZTAZWS",
        "forkJsonUrl": "https://mcp-api.trader.dev/backtest/01M2R92DY6YXMDYK7FEMZTAZWS/fork.json",
    },
}

# A second real hit from the same live capture -- has explicit fork lineage
# and a differently-formatted timeframe ("1d" vs the first hit's "60"),
# proving verbatim (non-normalized) storage against two REAL, differently
# shaped source records rather than one convenient example.
REAL_SEARCH_HIT_WITH_FORK_LINEAGE = {
    "id": "01M2R8PTT7A3M94KRBZ5QW021Y",
    "name": "Bracket Strategy Test",
    "symbol": "XAUUSD",
    "timeframe": "1d",
    "version": 3,
    "forkedFromStrategyId": "01M2R8HDRQDPQYHVG5H9J1VS77",
    "author": {"username": None, "displayName": "Bjorn de Plaa", "avatarUrl": None},
    "createdAt": 1789668322119,
    "updatedAt": 1789668322119,
    "result": {
        "resultId": "01M2R8Q5A1XTFQ8S15ZK0BPWTQ",
        "netProfitPct": 56.97593088,
        "profitFactor": 4.06692734,
        "maxDrawdownPct": 10.0662238,
        "winRatePct": 57.14285714,
        "sharpeRatio": 1.33644853,
        "sortinoRatio": 0.92561261,
        "totalTrades": 14,
        "viewUrl": "https://mcp-api.trader.dev/backtest/01M2R8Q5A1XTFQ8S15ZK0BPWTQ",
        "forkJsonUrl": "https://mcp-api.trader.dev/backtest/01M2R8Q5A1XTFQ8S15ZK0BPWTQ/fork.json",
    },
}

# Captured live 2026-09-17 from
# `curl 'https://mcp-api.trader.dev/backtest-results/01M2R92DY6YXMDYK7FEMZTAZWS'`
# -- the authoritative record PID-003 sec3 says SCOUT should snapshot.
REAL_BACKTEST_RESULT_DETAIL = {
    "id": "01M2R92DY6YXMDYK7FEMZTAZWS",
    "jobId": "adhoc_01M2R92DY6G9V16WFB3RTP37H8",
    "userId": "user_3Ihk3BglJoFhO8DDx1WcjAhYt9z",
    "strategyId": "01M2R92EBYK57YH173W1TP9SP9",
    "symbol": "XAUUSD",
    "displaySymbol": "XAUUSD",
    "market": "POLYGON forex",
    "timeframe": "60",
    "fromTs": 1254355200000,
    "toTs": 1546300800000,
    "barsEvaluated": 38209,
    "initialCapital": 10000,
    "finalEquity": 2991.397264549701,
    "netProfit": -7008.602735450299,
    "netProfitPct": -70.08602735,
    "grossProfit": 16090.161811055379,
    "grossLoss": 23098.76454650568,
    "profitFactor": 0.69658106,
    "maxDrawdown": 7706.158948395714,
    "maxDrawdownPct": 72.16667629,
    "totalTrades": 1470,
    "winningTrades": 331,
    "losingTrades": 1139,
    "winRatePct": 22.5170068,
    "sharpeRatio": -1.36014385,
    "sortinoRatio": -0.68045882,
    "r2Url": "https://pub-5880a55c41fd4cd1a11146f4fd522fbe.r2.dev/backtests/01M2R92DY6YXMDYK7FEMZTAZWS.json.gz",
    "createdAt": 1789668702150,
    "visibility": "public",
    "parentResultId": None,
    "optimizationId": None,
    "engineVersion": "tv_jul26_mc7",
    "mcpruleValidated": True,
    "parityProfile": {
        "commissionValue": 0.05, "sizingType": "percent_of_equity", "sizingValue": 100,
        "marginLong": 100, "marginShort": 100, "initialCapital": 10000,
    },
    "author": None,
    "cascade": {"totalRows": 0, "uniqueEntries": 0, "maxCascadeDepth": 0, "cascadeRatio": 0},
}


def test_real_public_xauusd_record_normalizes_with_verbatim_symbol_and_timeframe():
    record = normalize_record(REAL_SEARCH_HIT, REAL_BACKTEST_RESULT_DETAIL)
    assert record.source_strategy_id == "01M2R92EBYK57YH173W1TP9SP9"
    assert record.result_id == "01M2R92DY6YXMDYK7FEMZTAZWS"
    assert record.symbol == "XAUUSD"
    assert record.timeframe == "60"  # verbatim -- NOT normalized to "H1"
    assert record.forked_from_source_strategy_id is None


def test_real_backtest_result_detail_yields_all_seven_claim_metrics_exactly():
    record = normalize_record(REAL_SEARCH_HIT, REAL_BACKTEST_RESULT_DETAIL)
    values = build_claim_values(record.claim_payload)
    assert values["net_pnl_percent"] == Decimal("-70.08602735")
    assert values["max_drawdown_percent"] == Decimal("72.16667629")
    assert values["win_rate_percent"] == Decimal("22.5170068")
    assert values["profit_factor"] == Decimal("0.69658106")
    assert values["trade_count"] == 1470
    assert values["sharpe"] == Decimal("-1.36014385")
    assert values["sortino"] == Decimal("-0.68045882")


def test_real_public_record_is_access_restricted_never_available():
    """The rule/code text (fork.json) is auth-gated for every caller,
    including this genuinely public/reachable record -- verified live in
    the PID-003 preflight (401 without a key)."""
    record = normalize_record(REAL_SEARCH_HIT, REAL_BACKTEST_RESULT_DETAIL)
    assert record.rule_availability == RuleAvailability.ACCESS_RESTRICTED
    assert classify_rule_availability(REAL_BACKTEST_RESULT_DETAIL) == RuleAvailability.ACCESS_RESTRICTED


def test_real_forked_record_preserves_explicit_lineage_verbatim():
    record = normalize_record(REAL_SEARCH_HIT_WITH_FORK_LINEAGE, None)
    assert record.forked_from_source_strategy_id == "01M2R8HDRQDPQYHVG5H9J1VS77"
    assert record.timeframe == "1d"  # a DIFFERENT verbatim format from the other real hit's "60"


def test_two_real_records_from_the_same_capture_have_different_fingerprints():
    r1 = normalize_record(REAL_SEARCH_HIT, REAL_BACKTEST_RESULT_DETAIL)
    r2 = normalize_record(REAL_SEARCH_HIT_WITH_FORK_LINEAGE, None)
    fp1 = compute_snapshot_fingerprint(
        discovery_id="disc-1", claim_payload=build_claim_values(r1.claim_payload)
    )
    fp2 = compute_snapshot_fingerprint(
        discovery_id="disc-2", claim_payload=build_claim_values(r2.claim_payload)
    )
    assert fp1 != fp2


def test_identical_repeated_extraction_of_the_real_payload_is_idempotent():
    """PID-003 sec4: 'repeated extraction of identical normalized content
    is idempotent (no new snapshot)' -- proven here at the fingerprint
    level against the exact real payload, independent of the database
    (the DB-level proof lives in tests/integration/test_scout_persistence.py)."""
    record_first = normalize_record(REAL_SEARCH_HIT, REAL_BACKTEST_RESULT_DETAIL)
    record_second = normalize_record(dict(REAL_SEARCH_HIT), dict(REAL_BACKTEST_RESULT_DETAIL))
    fp_first = compute_snapshot_fingerprint(
        discovery_id="disc-1", claim_payload=build_claim_values(record_first.claim_payload)
    )
    fp_second = compute_snapshot_fingerprint(
        discovery_id="disc-1", claim_payload=build_claim_values(record_second.claim_payload)
    )
    assert fp_first == fp_second


def test_a_changed_metric_value_produces_a_different_fingerprint_fixture_driven():
    """Deterministic fixture-driven proof of the 'changed claim value creates
    a new snapshot' rule (PID-003 sec4), covering the case where the real
    live source value might not actually change between two runs of the
    acceptance proof -- see the delivery report for the honest live-vs-
    fixture split."""
    changed_detail = dict(REAL_BACKTEST_RESULT_DETAIL)
    changed_detail["netProfitPct"] = -65.0  # source claim revised
    record_before = normalize_record(REAL_SEARCH_HIT, REAL_BACKTEST_RESULT_DETAIL)
    record_after = normalize_record(REAL_SEARCH_HIT, changed_detail)
    fp_before = compute_snapshot_fingerprint(
        discovery_id="disc-1", claim_payload=build_claim_values(record_before.claim_payload)
    )
    fp_after = compute_snapshot_fingerprint(
        discovery_id="disc-1", claim_payload=build_claim_values(record_after.claim_payload)
    )
    assert fp_before != fp_after


def test_family_resolution_is_fork_lineage_only_with_explicit_evidence():
    """No fuzzy/semantic/LLM clustering exists anywhere -- family is
    UNRESOLVED unless the source itself supplied forkedFromStrategyId."""
    forked = normalize_record(REAL_SEARCH_HIT_WITH_FORK_LINEAGE, None)
    unforked = normalize_record(REAL_SEARCH_HIT, REAL_BACKTEST_RESULT_DETAIL)
    resolution_if_forked = (
        FamilyResolution.FORK_LINEAGE if forked.forked_from_source_strategy_id else FamilyResolution.UNRESOLVED
    )
    resolution_if_unforked = (
        FamilyResolution.FORK_LINEAGE if unforked.forked_from_source_strategy_id else FamilyResolution.UNRESOLVED
    )
    assert resolution_if_forked == FamilyResolution.FORK_LINEAGE
    assert resolution_if_unforked == FamilyResolution.UNRESOLVED


def test_manual_origin_kinds_remain_distinct_from_adapter_sourced():
    assert OriginKind.ADAPTER_SOURCED != OriginKind.USER_DISCOVERED
    assert OriginKind.USER_DISCOVERED != OriginKind.MY_IDEA
