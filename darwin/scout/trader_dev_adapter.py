"""Trader.dev public strategy/backtest browse adapter (PID-003 SCOUT,
docs/pids/PID-003-SCOUT.md sec3/sec5).

Fixed, owned origin -- `mcp-api.trader.dev` -- never a generic "fetch this
URL" capability anywhere in DARWIN. No Trader.dev credential exists or is
ever used: `/backtest/{id}/fork.json` 401s without a key (verified live in
the PID-003 preflight) and this adapter never calls it -- the rule/code
text is modelled as RuleAvailability.ACCESS_RESTRICTED, never fetched.

Untrusted-data discipline throughout: every value this module returns is
inert data to its callers. Nothing here executes, evals, or renders
anything from the source; `raw_metadata`/claim text is passed through
verbatim for storage as text only.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Self
from urllib.parse import urlparse

import httpx

from darwin.core.errors import DarwinError
from darwin.core.logging import log_event
from darwin.scout.domain import RuleAvailability

logger = logging.getLogger(__name__)

# The ONLY origin this adapter is authorised to call for JSON data
# (PID-003 sec5). A fixed adapter-owned constant -- never sourced from
# configuration, environment, or caller input -- exactly like
# darwin.hermes.contract's closed timeframe -> table mapping.
ALLOWED_API_HOST = "mcp-api.trader.dev"
BASE_URL = f"https://{ALLOWED_API_HOST}"

# The equity/trade detail blob's own inline-supplied host (PID-003 sec5) --
# validated per-URL against this suffix, never blindly followed. No
# discovery flow in this PID needs to fetch this blob for any SourceClaim
# metric (all seven live in /backtest-results/{id} itself) -- see
# `fetch_r2_blob`'s docstring. Implemented and tested as a standing
# SSRF-defence capability, exercised directly by the security tests.
ALLOWED_R2_HOST_SUFFIX = ".r2.dev"

USER_AGENT = "DARWIN-SCOUT/1 (+https://github.com/maff0000/DARWIN; read-only provenance capture, no credential used)"

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 10.0
TOTAL_TIMEOUT_S = 20.0
MAX_ATTEMPTS = 3  # one initial attempt + 2 bounded retries
RETRY_BACKOFF_S = (0.2, 0.5)
MAX_REDIRECTS = 3
MAX_PAGE_SIZE = 50  # server-enforced cap -- confirmed live: limit=100 -> 400

ADAPTER_NAME = "trader_dev_public_adapter"
ADAPTER_VERSION = "v1"

ALLOWED_SORTS = frozenset(
    {"profit", "sharpe", "sortino", "winrate", "trades", "drawdown", "recent"}
)

# The claim metrics SCOUT captures, keyed by their /backtest-results field
# name -> darwin.scout.domain.CLAIM_METRIC_FIELDS name (PID-003 sec4).
_METRIC_FIELD_MAP: dict[str, str] = {
    "netProfitPct": "net_pnl_percent",
    "maxDrawdownPct": "max_drawdown_percent",
    "winRatePct": "win_rate_percent",
    "profitFactor": "profit_factor",
    "totalTrades": "trade_count",
    "sharpeRatio": "sharpe",
    "sortinoRatio": "sortino",
}


class ScoutSourceError(DarwinError):
    code = "SCOUT_SOURCE_ERROR"


class ScoutSourceUnavailableError(ScoutSourceError):
    """Timeout, connection failure, 5xx, or rate-limit response. Must never
    be treated as a DARWIN-core fault -- see darwin.app's SCOUT status
    modelling (PID-003 sec5: source unavailability degrades SCOUT's own
    status only, never DARWIN readiness/health)."""

    code = "SCOUT_SOURCE_UNAVAILABLE"


class ScoutSourceMalformedResponseError(ScoutSourceError):
    code = "SCOUT_SOURCE_MALFORMED_RESPONSE"


class DisallowedHostError(ScoutSourceError):
    """Request or redirect target outside the allowed host set -- SSRF
    defence (PID-003 sec5: "no localhost/private-network escape")."""

    code = "SCOUT_DISALLOWED_HOST"


def _validate_url_host(url: str, *, allow_r2: bool = False) -> str:
    """The ONLY function permitted to decide a target URL is safe to call.
    Applied to every request AND every redirect hop before it is followed.

    Rejects anything that is not `https://mcp-api.trader.dev/...` (or,
    when `allow_r2=True`, `https://<sub>.r2.dev/...`) by exact/suffix
    hostname match -- which alone already rejects every IP-literal,
    `localhost`, and arbitrary third-party host a malicious redirect could
    name, since none of those strings can ever equal or end with an
    allowed host. As defence in depth beyond the string check, the
    hostname is also resolved and rejected if it resolves to a private/
    loopback/link-local address (DNS-rebinding defence) -- a DNS failure
    here is treated as source-unavailable, not a security violation.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise DisallowedHostError(f"Refusing non-HTTPS target: {url!r}")
    host = parsed.hostname or ""
    is_allowed = host == ALLOWED_API_HOST or (allow_r2 and host.endswith(ALLOWED_R2_HOST_SUFFIX))
    if not is_allowed:
        raise DisallowedHostError(f"Refusing target outside the allowed host set: {host!r}")

    try:
        addrinfo = socket.getaddrinfo(host, 443)
    except OSError as exc:
        raise ScoutSourceUnavailableError(f"DNS resolution failed for {host!r}: {exc}") from exc
    for family, _type, _proto, _canon, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise DisallowedHostError(
                f"Refusing target {host!r} — resolves to a private/loopback/link-local address {ip}"
            )
    return url


@dataclass(frozen=True)
class NormalizedRecord:
    """One Trader.dev public strategy+backtest-result, combined from a
    `/strategies/search` hit and its authoritative `/backtest-results/{id}`
    detail (PID-003 sec3: "This is the record SCOUT should snapshot as the
    canonical SourceClaim source, keyed by resultId."). `symbol`/`timeframe`
    are stored EXACTLY as the source supplied them -- never normalized
    (PID-003 sec4: `"1d"` vs `"D"` vs `"60"` all observed live for what a
    human would call daily/hourly)."""

    source_strategy_id: str
    result_id: str
    name: str
    symbol: str
    timeframe: str
    forked_from_source_strategy_id: str | None
    strategy_updated_at_utc: datetime | None
    view_url: str | None
    claim_payload: dict[str, Any]
    rule_availability: RuleAvailability
    raw_metadata: dict[str, Any]


def classify_rule_availability(detail: dict | None) -> RuleAvailability:
    """Honest, deterministic mapping onto the closed RuleAvailability set
    (PID-003 sec3/sec4). Trader.dev's JSON contract carries no explicit
    "category"/"state" field matching the "Private"/"Quarantined"/"Report
    unavailable" template states the preflight observed only in the HTML
    report page (which SCOUT never fetches) -- so this classifier is built
    from the signals the JSON contract genuinely exposes, not a fabricated
    read of a field that does not exist:

    - `detail is None` (fetch failed entirely, e.g. 404/deleted) ->
      UNAVAILABLE, matching the "Report unavailable" template state.
    - `visibility == "private"` -> UNAVAILABLE, matching the owner-withheld
      "Private" template state (never observed live through the public
      `/strategies/search` listing, which the preflight confirmed always
      returns `visibility: "public"" -- but modelled honestly rather than
      assumed impossible).
    - any other non-"public" visibility (e.g. a future "quarantined" value)
      -> PARTIAL, matching the "Quarantined · Parity investigation" state:
      something is reachable but explicitly flagged non-public/uncertain.
    - reachable, visibility public/absent, but none of the required numeric
      fields present -> UNKNOWN (reachable, nothing usable came back).
    - otherwise (the normal, currently-universal live case: numeric summary
      present, visibility public) -> ACCESS_RESTRICTED, because the
      rule/code text (`fork.json`) is auth-gated for every caller regardless
      of this record's own state, and SCOUT never fetches it.
    """
    if detail is None:
        return RuleAvailability.UNAVAILABLE
    visibility = detail.get("visibility")
    if visibility == "private":
        return RuleAvailability.UNAVAILABLE
    if visibility is not None and visibility != "public":
        return RuleAvailability.PARTIAL
    required = ("netProfitPct", "maxDrawdownPct", "winRatePct", "profitFactor", "totalTrades")
    if not any(detail.get(k) is not None for k in required):
        return RuleAvailability.UNKNOWN
    return RuleAvailability.ACCESS_RESTRICTED


def normalize_record(search_hit: dict, detail: dict | None) -> NormalizedRecord:
    """Combine one `/strategies/search` hit with its `/backtest-results/{id}`
    detail into a `NormalizedRecord`. Never guesses a missing field --
    absent optional fields stay `None`/absent, they are never defaulted."""
    try:
        source_strategy_id = str(search_hit["id"])
        symbol = str(search_hit["symbol"])
        timeframe = str(search_hit["timeframe"])
        result = search_hit.get("result") or {}
        result_id = str(result.get("resultId") or (detail or {}).get("id") or "")
    except KeyError as exc:
        raise ScoutSourceMalformedResponseError(
            f"Trader.dev search hit missing required field: {exc}"
        ) from exc
    if not result_id:
        raise ScoutSourceMalformedResponseError(
            f"Trader.dev search hit {source_strategy_id!r} has no resultId"
        )

    updated_at_ms = search_hit.get("updatedAt")
    strategy_updated_at_utc = (
        datetime.fromtimestamp(updated_at_ms / 1000, tz=UTC) if isinstance(updated_at_ms, (int, float)) else None
    )

    source_for_metrics = detail if detail is not None else result
    claim_payload = {
        mapped: source_for_metrics.get(raw_key)
        for raw_key, mapped in _METRIC_FIELD_MAP.items()
    }

    view_url = result.get("viewUrl")

    raw_metadata = {
        "search_hit": search_hit,
        "backtest_result_detail": detail,
    }

    return NormalizedRecord(
        source_strategy_id=source_strategy_id,
        result_id=result_id,
        name=str(search_hit.get("name") or ""),
        symbol=symbol,
        timeframe=timeframe,
        forked_from_source_strategy_id=(
            str(search_hit["forkedFromStrategyId"]) if search_hit.get("forkedFromStrategyId") else None
        ),
        strategy_updated_at_utc=strategy_updated_at_utc,
        view_url=view_url,
        claim_payload=claim_payload,
        rule_availability=classify_rule_availability(detail),
        raw_metadata=raw_metadata,
    )


class TraderDevAdapter:
    """Bounded, read-only client for the Trader.dev public browse API. One
    `httpx.Client` per adapter instance, closed explicitly by callers (or
    used as a context manager) -- no module-level shared client, so tests
    can freely construct/mock/tear one down without cross-test state.
    """

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        # `follow_redirects=False`: redirects are followed manually below so
        # every hop's target host is validated BEFORE the request is sent
        # (httpx's own auto-follow would send the request first).
        self._client = httpx.Client(
            timeout=httpx.Timeout(TOTAL_TIMEOUT_S, connect=CONNECT_TIMEOUT_S, read=READ_TIMEOUT_S),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            transport=transport,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get_json(self, url: str, *, params: dict | None = None, allow_r2: bool = False) -> Any:
        target = _validate_url_host(url, allow_r2=allow_r2)
        last_exc: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = self._client.get(target, params=params)
            except httpx.TimeoutException as exc:
                last_exc = exc
            except httpx.TransportError as exc:
                last_exc = exc
            else:
                if response.status_code in (301, 302, 303, 307, 308):
                    return self._follow_redirect(response, allow_r2=allow_r2, hops_remaining=MAX_REDIRECTS)
                if response.status_code == 429:
                    last_exc = ScoutSourceUnavailableError("Trader.dev rate-limited this request (429)")
                elif response.status_code >= 500:
                    last_exc = ScoutSourceUnavailableError(
                        f"Trader.dev returned {response.status_code} for {target}"
                    )
                elif response.status_code == 404:
                    return None
                elif response.status_code >= 400:
                    raise ScoutSourceUnavailableError(
                        f"Trader.dev returned {response.status_code} for {target}: {response.text[:200]}"
                    )
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ScoutSourceMalformedResponseError(
                            f"Trader.dev returned non-JSON for {target}"
                        ) from exc

            if attempt < MAX_ATTEMPTS - 1:
                log_event(
                    logger, logging.WARNING, "scout_source_retry",
                    url=target, attempt=attempt + 1, error_class=last_exc.__class__.__name__,
                )
                time.sleep(RETRY_BACKOFF_S[min(attempt, len(RETRY_BACKOFF_S) - 1)])

        raise ScoutSourceUnavailableError(f"Trader.dev unreachable after {MAX_ATTEMPTS} attempts: {last_exc}") from last_exc

    def _follow_redirect(self, response: httpx.Response, *, allow_r2: bool, hops_remaining: int) -> Any:
        if hops_remaining <= 0:
            raise ScoutSourceUnavailableError("Too many redirects following a Trader.dev/R2 request")
        location = response.headers.get("location")
        if not location:
            raise ScoutSourceMalformedResponseError("Redirect response carried no Location header")
        target = _validate_url_host(location, allow_r2=allow_r2)
        next_response = self._client.get(target)
        if next_response.status_code in (301, 302, 303, 307, 308):
            return self._follow_redirect(next_response, allow_r2=allow_r2, hops_remaining=hops_remaining - 1)
        if next_response.status_code >= 400:
            raise ScoutSourceUnavailableError(f"Trader.dev redirect target returned {next_response.status_code}")
        try:
            return next_response.json()
        except ValueError as exc:
            raise ScoutSourceMalformedResponseError("Trader.dev redirect target returned non-JSON") from exc

    def get_stats(self) -> dict:
        return self._get_json(f"{BASE_URL}/strategies/stats")

    def get_symbols(self) -> list[dict]:
        return self._get_json(f"{BASE_URL}/strategies/symbols")

    def search_strategies(
        self,
        *,
        symbol: str | None = None,
        limit: int = MAX_PAGE_SIZE,
        offset: int = 0,
        sort: str = "recent",
    ) -> dict:
        if limit > MAX_PAGE_SIZE:
            raise ScoutSourceError(f"limit {limit} exceeds Trader.dev's own page-size cap ({MAX_PAGE_SIZE})")
        if sort not in ALLOWED_SORTS:
            raise ScoutSourceError(f"sort {sort!r} is not one of the allowed sort values: {sorted(ALLOWED_SORTS)}")
        params: dict[str, Any] = {"limit": limit, "offset": offset, "sort": sort}
        if symbol:
            params["symbol"] = symbol
        return self._get_json(f"{BASE_URL}/strategies/search", params=params)

    def get_backtest_result(self, result_id: str) -> dict | None:
        return self._get_json(f"{BASE_URL}/backtest-results/{result_id}")

    def fetch_r2_blob(self, r2_url: str) -> bytes:
        """Fetch the public equity/trade detail blob at its own inline-
        supplied R2 URL, with the same host-allowlist + redirect-validation
        discipline as every other call this adapter makes. Not invoked by
        the standard discovery flow -- SCOUT's SourceClaim metrics (PID-003
        sec4) all live in `/backtest-results/{id}` itself, and the
        equity/trade arrays inside this blob are execution detail SCOUT has
        no use for (that is APOLLO's future domain, not this PID's). Exists
        so the r2.dev host-validation path is real, callable, and directly
        testable rather than a documented-but-unimplemented claim.
        """
        target = _validate_url_host(r2_url, allow_r2=True)
        response = self._client.get(target)
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            if not location:
                raise ScoutSourceMalformedResponseError("R2 redirect carried no Location header")
            target = _validate_url_host(location, allow_r2=True)
            response = self._client.get(target)
        if response.status_code >= 400:
            raise ScoutSourceUnavailableError(f"R2 blob fetch returned {response.status_code}")
        return response.content

    def check_reachable(self) -> bool:
        """Lightweight readiness probe for GET /api/v1/scout/status. Must
        never raise -- a source failure is reported as False, never an
        exception the caller has to guess how to handle."""
        try:
            stats = self.get_stats()
            return isinstance(stats, dict) and "totalStrategies" in stats
        except ScoutSourceError:
            return False
        except Exception:  # noqa: BLE001 - a readiness probe must never crash the caller
            return False

    def iter_public_records(
        self,
        *,
        symbol: str | None,
        max_records: int,
        sort: str = "recent",
    ) -> tuple[list[NormalizedRecord], list[str]]:
        """Bounded, paginated, read-only public-record fetch (PID-003 sec5:
        "bounded page/item count"). Never fetches beyond `max_records`
        (itself always <= the caller-facing endpoint's own hard ceiling —
        see darwin.app) and always respects Trader.dev's own 50/page cap.

        A failure fetching/parsing the initial `/strategies/search` page
        propagates (nothing was observed yet -- the caller treats that as a
        total run failure). A failure on one individual hit's
        `/backtest-results/{id}` detail call or its own parsing is caught
        HERE and returned as an entry in the second (`errors`) list rather
        than aborting the whole page -- this is what makes bounded partial
        ingestion (PID-003 sec4) real rather than "one bad record kills the
        run".
        """
        records: list[NormalizedRecord] = []
        errors: list[str] = []
        offset = 0
        while len(records) + len(errors) < max_records:
            page_limit = min(MAX_PAGE_SIZE, max_records - len(records) - len(errors))
            page = self.search_strategies(symbol=symbol, limit=page_limit, offset=offset, sort=sort)
            if not isinstance(page, dict) or "results" not in page:
                raise ScoutSourceMalformedResponseError("Trader.dev /strategies/search returned an unexpected shape")
            hits = page["results"]
            if not hits:
                break
            for hit in hits:
                try:
                    result = hit.get("result") or {}
                    result_id = result.get("resultId")
                    detail = self.get_backtest_result(result_id) if result_id else None
                    records.append(normalize_record(hit, detail))
                except ScoutSourceError as exc:
                    errors.append(f"{hit.get('id', '<unknown>')}: {exc.__class__.__name__}: {exc}")
                if len(records) + len(errors) >= max_records:
                    break
            if not page.get("hasMore"):
                break
            offset += len(hits)
        return records, errors
