# PID-003 — SCOUT

Status: APPROVED FOR IMPLEMENTATION

## 1. Purpose

SCOUT turns uncontrolled external strategy ideas into governed DARWIN discoveries with
durable provenance. SCOUT answers *what strategy ideas exist, where did they come from,
exactly what did the source claim, do we have enough rules to investigate them, have we
seen this before, and should this idea move toward deterministic specification*. SCOUT
never answers *does this strategy work*.

## 2. Authority boundary

`external source -> SOURCE_CLAIM -> discovery`, never `external source -> DARWIN proof`.
A captured strategy enters lifecycle state `DISCOVERED` — captured with provenance only.
Not correct, profitable, testable, canonical, or suitable for live capital.

## 3. Source preflight findings — TRADER_DEV_PUBLIC

Inspected the real public browse surface at `https://mcp-api.trader.dev/browse` before
writing any adapter code (raw HTML fetched directly, no browser automation added to the
runtime). The page is server-rendered chrome plus inline vanilla JS that calls same-origin
JSON endpoints client-side. Reproduced those calls directly with `curl`.

**Public, unauthenticated, structured JSON — no API key required for any of these:**

- `GET /strategies/search` — discovery listing/enumeration.
  Query params: `symbol`, `timeframe`, `minNetProfitPct`, `minProfitFactor`,
  `minSharpeRatio`, `minSortinoRatio`, `minWinRatePct`, `maxDrawdownPct`, `minTrades`,
  `maxTrades`, `sort` (`profit`|`sharpe`|`sortino`|`winrate`|`trades`|`drawdown`|`recent`),
  `limit` (server-capped at 50 — confirmed via live `400 Number must be less than or
  equal to 50` on `limit=100`), `offset`.
  Response: `{results: [...], limit, offset, hasMore, sort}` — `hasMore` boolean drives
  pagination; no total-count field here (use `/strategies/stats` for global totals).
  Each result: `id` (ULID strategy id), `name`, `symbol` (raw, e.g. `XAUUSD`), `timeframe`
  (raw and INCONSISTENTLY formatted across records — observed both `"1d"` and `"D"` and
  `"60"` for what a human would call daily/hourly; store verbatim, never normalize/guess),
  `version`, `forkedFromStrategyId` (nullable — explicit fork lineage when present),
  `author` (`{username, displayName, avatarUrl}`, all nullable), `createdAt`/`updatedAt`
  (epoch ms), and a nested `result` object with `resultId`, `netProfit`, `netProfitPct`,
  `grossProfit`, `grossLoss`, `profitFactor`, `maxDrawdownPct`, `winRatePct`,
  `sharpeRatio`, `sortinoRatio`, `totalTrades`, `winningTrades`, `losingTrades`,
  `barsEvaluated`, `fromTs`, `toTs`, `createdAt`, `viewUrl`, `forkJsonUrl`.

- `GET /strategies/stats` — `{totalStrategies, totalBacktests}` global counts (currently
  248,274 / 1,031,051 in the live response observed).

- `GET /strategies/symbols` — `[{symbol, count}, ...]`. XAUUSD currently has 25,040
  public records — a genuinely usable density for the programme's XAUUSD milestone.

- `GET /backtest-results/{resultId}` — the authoritative public per-record summary,
  materially richer than the embedded `result` object above: adds `strategyId`, `userId`
  (author identity), `displaySymbol`, `market` (e.g. `"POLYGON forex"` — real venue/data
  attribution), an explicit `visibility` field (observed `"public"` on every record
  reachable through `/strategies/search`), `engineVersion`, `mcpruleValidated`,
  `parityProfile` (fee/sizing assumptions used for the backtest), `cascade` metadata, and
  `r2Url` pointing at the full equity/trade detail blob. This is the record SCOUT should
  snapshot as the canonical `SourceClaim` source, keyed by `resultId`.

- The `r2Url` blob (`https://pub-<hash>.r2.dev/backtests/{resultId}.json.gz`, Cloudflare
  R2, public + CORS-enabled per the source's own client code comments) — full
  `{equity: [...], trades: [...]}` detail, unauthenticated, for public rows.

**Confirmed to require authentication — NOT fetched, no credential introduced:**

- `GET /backtest/{resultId}/fork.json` (the actual strategy rules/code) — returns
  `401 {"error":"unauthorized","message":"missing Authorization header"}` live. The
  source's own client code documents the entitlement gate explicitly: owner of the
  result, paid subscriber, "OG" comped status, or admin. This is the one part of the
  source's data model SCOUT must record as access-restricted, not fetch.
- No Trader.dev API key was used, requested, or is required for anything SCOUT needs.
  Per PID authority: rule/code text is out of reach without one, so it is modelled as
  `ACCESS_RESTRICTED` and left alone — not escalated, because the discovery/summary
  contract above is genuinely sufficient without a key.

**Other source realities observed (from template states in the report page, not fetched
since they require auth to reach) and modelled honestly rather than guessed:**
`"Martingale · Private"` (owner-withheld category), `"Quarantined · Parity investigation"`
(engine-version re-run flagged a result as possibly invalid), `"Report unavailable"`
(deleted/bad-link/private). These map onto the required bounded rule/report-availability
states.

**Policy note for the Architect's awareness (not a technical block):** `robots.txt` on
`mcp-api.trader.dev` publishes only the IETF "content signals" legend with no per-path
`search`/`ai-input`/`ai-train` signal actually set for this origin — i.e. explicitly
neither granted nor restricted under that voluntary framework. Flagging this transparently
rather than silently assuming it is clear. SCOUT's use (bounded, courteous, read-only
provenance capture of the site's own public API, modelled as untrusted `SOURCE_CLAIM`
data, never republished as DARWIN's own proof) is consistent with the access pattern the
site's own public browse page performs anonymously.

**Rate limiting:** no throttling observed on 10 rapid sequential public requests in this
preflight; SCOUT still implements bounded timeouts/retries/pacing regardless (see §5).

*Implementation-time correction (2026-09-17):* the original preflight's "(see §10)"
cross-reference above pointed at a section that did not exist in this document (§5
"Network/security boundary" is where the bounded timeouts/retries/pacing are actually
specified and implemented — `darwin/scout/trader_dev_adapter.py`'s `CONNECT_TIMEOUT_S`/
`READ_TIMEOUT_S`/`MAX_ATTEMPTS`/`RETRY_BACKOFF_S`). Fixed to `§5` here rather than left
dangling now that a real `§10` exists below (the 2026-09-17 Workshop/Specification
amendment) and would otherwise be confused for the rate-limiting detail this sentence
means.

**Conclusion:** a stable, sufficient, genuinely public discovery contract exists. No
Playwright/Chromium/Node browser automation is needed or added. No API key is needed.
Proceeding to implementation without escalation.

## 4. Provenance model

- **Source** — `TRADER_DEV_PUBLIC`, one row, adapter identity + base URL + adapter
  version.
- **SourceDiscovery** — stable DARWIN discovery identity keyed on the strongest stable
  source identity actually supplied: source `strategyId` (the `id` field from
  `/strategies/search`). Never manufactured.
- **SourceSnapshot** — one immutable row per materially distinct extraction of a given
  discovery, referencing the `resultId` observed at that extraction, extraction UTC,
  source-updated timestamp (`updatedAt`), adapter/version identity, source URL
  (`viewUrl`), source symbol/timeframe verbatim, raw source metadata, rule-availability
  state, and a snapshot fingerprint (SHA-256 over the normalized claim payload). Repeated
  extraction of identical normalized content is idempotent (no new snapshot); a changed
  claim value creates a new snapshot and the prior one remains readable.
- **SourceClaim** — first-class, typed `EvidenceLevel = SOURCE_CLAIM`, one row per
  snapshot, holding whichever of `NET_PNL_PERCENT` / `MAX_DRAWDOWN_PERCENT` /
  `WIN_RATE_PERCENT` / `PROFIT_FACTOR` / `TRADE_COUNT` / `SHARPE` / `SORTINO` the source
  actually supplied, as exact `NUMERIC`, never binary float. Every value traces back to
  its source, snapshot, and extraction time.
- **RuleAvailability** — `AVAILABLE` | `PARTIAL` | `UNAVAILABLE` | `ACCESS_RESTRICTED` |
  `UNKNOWN`. Trader.dev's numeric summary is `AVAILABLE`; its rule/code text is
  `ACCESS_RESTRICTED` (auth-gated, never fetched). Never inferred up to `AVAILABLE`.
- **Source-symbol vs canonical instrument** — `symbol`/`timeframe` are stored exactly as
  Trader.dev supplies them (e.g. `XAUUSD`/`D`). No implicit mapping to a HERMES
  `InstrumentId`. That mapping is an explicit later governed step, out of scope here.
- **Discovery lifecycle** — `DISCOVERED` only; no further transition in PID-003.
- **Intake status** — `NEW` | `SHORTLISTED` | `REJECTED` | `READY_FOR_SPECIFICATION`,
  auditable, never deletes provenance. `READY_FOR_SPECIFICATION` != `SPECIFIED`.
- **Dedup/family** — exact source identity dedups to the same discovery; explicit
  `forkedFromStrategyId` lineage is preserved as-is; without deterministic evidence,
  family is `UNRESOLVED`. No fuzzy/semantic/LLM clustering.
- **DiscoveryRun** — durable identity per bounded fetch, recording requested
  filter/bounds, started/completed UTC, adapter version, status, records
  observed/accepted/unchanged/changed/rejected, and error summary. No silent partial
  success.

## 5. Network/security boundary

Trader.dev adapter owns its fixed allowed host (`mcp-api.trader.dev` +
`*.r2.dev` for the specific `r2Url` returned inline, host-validated, not attacker
supplied). HTTPS only. Bounded connect/read timeouts, bounded retries, bounded
page/item count (server-enforced 50/page besides DARWIN's own cap), redirect-destination
host validation (no localhost/private-network escape), descriptive User-Agent, no
credentials logged (none are used). No generic "fetch this URL" endpoint is exposed.
Source unavailability degrades SCOUT's own status only — never DARWIN core
readiness/health.

## 6. API surface

Read: `/api/v1/scout/status`, `/api/v1/scout/sources`, `/api/v1/scout/discovery-runs`,
`/api/v1/scout/discovery-runs/{id}`, `/api/v1/scout/discoveries` (filterable/paginated),
`/api/v1/scout/discoveries/{id}`.
Controlled mutation: `POST /api/v1/scout/discover` (bounded on-demand run, no arbitrary
URL input), `POST /api/v1/scout/discoveries/{id}/intake-status`. No deletes, no
patch-everything endpoint, no backtest/optimisation trigger.

## 7. ARENA surface

New nav entry `Discovery` (semantic monochrome icon consistent with the existing set).
Discovery list + detail per the Architect's directive, with every external metric
carrying the established `SOURCE_CLAIM` visual treatment. Pipeline's `DISCOVERED` count
now reflects real SCOUT persistence. Existing shell/visual character preserved, not
redesigned.

## 8. Acceptance evidence (see delivery report)

Domain/contract/persistence/security test totals, exact-head CI, a bounded live
read-only Trader.dev discovery run against the real public XAUUSD surface (idempotency
+ changed-snapshot proof), ARENA screenshots, independent Auditor verdict.

## 9. Exclusions

No SPECIFICATION, HSA, strategy execution/backtesting, ATHENA, APOLLO, DIKE evaluation,
qualification, promotion, HELIOS/TRON/NEO/SOCRATES/PLUTUS integration, generic scheduler,
continuous crawling, live trading, broker adapters, fuzzy/LLM family classification, or
canonical source-symbol→HERMES instrument mapping. Runtime remains `DARWIN_core` +
`DARWIN_sql` only.

## 10. Amendment (2026-09-17) — SCOUT vs Strategy Workshop vs Specification

The Architect has ruled that the canonical research flow is:

`SCOUT` → `Strategy Workshop` → deterministic `Specification` → immutable
`StrategyVersion` → `ATHENA` → `APOLLO`.

Strategy Workshop is a future ARENA experience over a future `specification/` capability.
It is not a separate microservice. **PID-003 implements Discovery only.** PID-004 (not
this PID) will implement Strategy Workshop + Specification, using a bounded filesystem
workspace (`/srv/DARWIN/workspaces/<workshop-id>/` with `DISCOVERY.json`,
`CONTEXT.md`, `QUESTIONS.md`, `DECISIONS.jsonl`, `SPECIFICATION_DRAFT.json`,
`VALIDATION.json`) for a governed Claude Code reasoning partner — never an unrestricted
FastAPI-launched process, never direct StrategyVersion creation or lifecycle promotion
from the Workshop itself. PID-004 will also inspect and absorb useful proven standalone
HSA capability (ambiguity refusal, deterministic decomposition, timeframe semantics,
atomic-condition concepts, tuning ranges, immutable version semantics) rather than
duplicate it from scratch; HSA is not retired during PID-003 or merely because
replacement code exists during PID-004 — retirement requires demonstrable replacement,
evidence/acceptance, and explicit central-architecture closure.

Revised canonical PID sequence: PID-002 ARENA → **PID-003 SCOUT/Discovery** → PID-004
Strategy Workshop + Specification → PID-005 ATHENA → PID-006 APOLLO → PID-007
Qualification → PID-008 Continuous Factory. This changes sequencing/product experience
only — the programme's first milestone (five independently promising XAUUSD strategies
discovered, normalised, optimised and sequentially proven against canonical HERMES
history) is unchanged.

This amendment extends PID-003's scope within Discovery (not into Workshop/Specification):

- **Manual discovery.** Matt must be able to add strategies he finds himself, via a
  `+ Add Strategy` ARENA flow. Two new provenance classes distinct from adapter-sourced
  discoveries: `USER_DISCOVERED` (an idea found outside SCOUT's automated adapter — a
  website, TradingView, Reddit, YouTube, a paper, a forum, a trader, etc. — with optional
  title, origin description, URL/reference, source symbol/timeframe, original
  description, pasted inert rule/code text, claimed metrics if supplied, personal notes,
  tags) and `MY_IDEA` (a hypothesis that originated with Matt, not an external source —
  legitimately has no URL, no external source, and no SOURCE_CLAIM metrics at all; still
  a valid `DISCOVERED` strategy). Any performance figure entered manually remains
  `SOURCE_CLAIM`. Never fabricate an external source identity for an internally
  originated idea.
- **Source fidelity.** SCOUT preserves what a source said; it never silently completes
  ambiguous trading semantics (e.g. "trade a London breakout" is stored as written — SCOUT
  does not decide session timezone, wick-vs-close, breakout buffer, SL/TP, DST, or entry
  timing; those questions belong to Strategy Workshop/Specification).
- **Intake states** gain `IN_WORKSHOP` (operational workflow only — not an evidence
  level, not a research result, not a canonical strategy lifecycle state): `NEW` |
  `SHORTLISTED` | `IN_WORKSHOP` | `READY_FOR_SPECIFICATION` | `REJECTED`. No PID-003
  action may produce `SPECIFIED` or a canonical `StrategyVersion`.
- **ARENA Discovery becomes DARWIN's strategy radar/intelligence inbox**, not a plain
  CRUD table: status counts by intake state, source health, latest discovery-run status,
  a claimed-performance leaderboard (default sort: highest claimed return first, where
  comparable source data exists; alternative sorts by PF/Sharpe/Sortino/drawdown/trade
  count/recency), and restrained visualisations — claimed return vs claimed drawdown
  (scatter-style, so high-return/high-drawdown claims are visually distinguishable from
  lower-return/lower-drawdown ones) and claimed profit-factor vs trade-count context (so
  a thin sample size is visually obvious, without implying statistical validity). Every
  leaderboard/visualisation is a **display/triage ordering only**, unmistakably labelled
  `SOURCE_CLAIM — NOT INDEPENDENTLY VERIFIED BY DARWIN`, never DARWIN endorsement, never a
  composite/success score. A discovery-priority score is architecturally permitted later
  only if transparently defined, its inputs visible, explicitly labelled as
  prioritisation, and never presented as evidence — not required or built in PID-003.
  Discovery detail exposes a truthful `Open Workshop` / `Prepare Workshop` affordance
  that is honestly disabled/future-state (no dead button masquerading as live
  functionality) since PID-004 does not exist yet — it must not invoke Claude Code,
  create AI sessions, generate rules, create a `StrategyVersion`, mark anything
  `SPECIFIED`, or silently resolve ambiguity.
- **Material Workshop decision trail** (ambiguity/question, resolution, origin,
  rationale, timestamp UTC, accepted state — the decision trail, never the raw chat
  transcript) is recorded here as durable forward doctrine for PID-004; it is not
  implemented in PID-003.

No contradiction with `PID.md` was identified; this amendment refines PID-003's own scope
and records forward doctrine for PID-004 without altering the master constitution.
