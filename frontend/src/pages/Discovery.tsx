import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../api/useApi";
import { api, ApiError } from "../api/client";
import { ALLOWED_INTAKE_TRANSITIONS, INTAKE_STATUS_LABEL, INTAKE_STATUS_ORDER } from "../api/intakeTransitions";
import type { DiscoverySort, IntakeStatus, ScoutDiscovery, ScoutDiscoveryRun, ScoutStatus } from "../api/types";
import { AddStrategyModal } from "../components/AddStrategyModal";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { IntakeBadge } from "../components/IntakeBadge";
import { LoadingState } from "../components/LoadingState";
import { ScatterPlot } from "../components/ScatterPlot";
import { SourceClaimNotice } from "../components/SourceClaimNotice";
import { StatusBadge } from "../components/StatusBadge";

const SORT_OPTIONS: Array<{ value: DiscoverySort; label: string }> = [
  { value: "net_pnl_percent", label: "Highest claimed return" },
  { value: "profit_factor", label: "Highest profit factor" },
  { value: "sharpe", label: "Highest Sharpe" },
  { value: "sortino", label: "Highest Sortino" },
  { value: "max_drawdown_percent", label: "Lowest claimed drawdown" },
  { value: "trade_count", label: "Most trades" },
  { value: "recent", label: "Most recently seen" },
];

const ORIGIN_LABEL: Record<string, string> = {
  ADAPTER_SOURCED: "Adapter",
  USER_DISCOVERED: "User",
  MY_IDEA: "My idea",
};

// A thin claimed-trade-count sample is shown honestly (dimmed) — never
// scored, never used to compute a significance/confidence figure
// (PID-003 sec10: "without implying statistical validity").
const LOW_SAMPLE_THRESHOLD = 30;

function fmtPercent(v: string | null): string {
  if (v === null) return "—";
  const n = Number(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}
function fmtNumber(v: string | null, digits = 2): string {
  if (v === null) return "—";
  return Number(v).toFixed(digits);
}
function fmtCount(v: number | null): string {
  return v === null ? "—" : String(v);
}
function shortDate(iso: string): string {
  return iso.replace("T", " ").replace(/\.\d+/, "").replace("Z", "").slice(0, 16);
}

export function Discovery() {
  const [symbol, setSymbol] = useState("");
  const [intakeStatus, setIntakeStatus] = useState<IntakeStatus | "">("");
  const [originKind, setOriginKind] = useState<"" | "ADAPTER_SOURCED" | "USER_DISCOVERED" | "MY_IDEA">("");
  const [sort, setSort] = useState<DiscoverySort>("net_pnl_percent");
  const [showAddForm, setShowAddForm] = useState(false);
  const [discoverOpen, setDiscoverOpen] = useState(false);

  const discoveries = useApi(
    () =>
      api.scoutDiscoveries({
        symbol: symbol.trim() || undefined,
        intakeStatus: intakeStatus || undefined,
        originKind: originKind || undefined,
        sort,
        limit: 200,
      }),
    [symbol, intakeStatus, originKind, sort],
  );
  const status = useApi(api.scoutStatus, []);

  const items = discoveries.status === "ready" ? discoveries.data.items : [];
  const counts = discoveries.status === "ready" ? discoveries.data.counts_by_intake_status : null;
  const total = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;

  async function transition(id: string, target: IntakeStatus) {
    try {
      await api.scoutSetIntakeStatus(id, { target_status: target, changed_by: "matt" });
      discoveries.reload();
    } catch {
      // No optimistic UI — a rejected transition just leaves the row
      // exactly where it was; the reload above never fires on failure.
      window.alert("Could not update intake status — that transition may not be allowed from the current state.");
    }
  }

  const returnDrawdownPoints = useMemo(
    () =>
      items
        .filter((d) => d.net_pnl_percent !== null && d.max_drawdown_percent !== null)
        .map((d) => ({
          id: d.id,
          x: Number(d.max_drawdown_percent),
          y: Number(d.net_pnl_percent),
          label: d.title,
        })),
    [items],
  );
  const pfTradeCountPoints = useMemo(
    () =>
      items
        .filter((d) => d.profit_factor !== null && d.trade_count !== null)
        .map((d) => ({
          id: d.id,
          x: d.trade_count as number,
          y: Number(d.profit_factor),
          label: d.title,
          lowSample: (d.trade_count as number) < LOW_SAMPLE_THRESHOLD,
        })),
    [items],
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Discovery</h1>
        <span className="page-header__meta">{total} discovered</span>
      </div>
      <p className="page-intro">
        DARWIN's strategy radar — where SCOUT's adapter-sourced and manually entered candidates land before Strategy
        Workshop (PID-004). Nothing here is proven; every performance figure is a source's own claim.
      </p>

      <div className="discovery-toolbar">
        <button type="button" className="button" onClick={() => setShowAddForm(true)}>
          + Add Strategy
        </button>
        <button type="button" className="button button--secondary" onClick={() => setDiscoverOpen((v) => !v)}>
          {discoverOpen ? "Close discover panel" : "Discover now…"}
        </button>
      </div>

      {discoverOpen && <DiscoverNowPanel onRun={() => discoveries.reload()} onClose={() => setDiscoverOpen(false)} />}

      {status.status === "ready" && <SourceHealthPanel status={status.data} />}
      {status.status === "error" && (
        <div className="degraded-banner">
          <span>Couldn't load SCOUT source status — this never affects DARWIN's own readiness.</span>
        </div>
      )}

      {discoveries.status === "loading" && <LoadingState label="Loading discoveries…" />}
      {discoveries.status === "error" && (
        <ErrorState error={discoveries.error} dependency="SCOUT discoveries" onRetry={discoveries.reload} />
      )}

      {discoveries.status === "ready" && counts && (
        <div className="grid-cards" style={{ marginBottom: "var(--space-5)" }}>
          <div className="stat-card">
            <div className="stat-card__value">{total}</div>
            <div className="stat-card__label">Total discovered</div>
          </div>
          {INTAKE_STATUS_ORDER.map((s) => (
            <div className="stat-card" key={s}>
              <div className="stat-card__value">{counts[s] ?? 0}</div>
              <div className="stat-card__label">{INTAKE_STATUS_LABEL[s]}</div>
            </div>
          ))}
        </div>
      )}

      {discoveries.status === "ready" && total === 0 && (
        <EmptyState
          title="No discoveries yet"
          body="SCOUT has not recorded any strategy discoveries in this environment yet. Run a bounded 'Discover now' pass against Trader.dev's public surface, or add one yourself with + Add Strategy."
          hint="Zero is the correct, honest state here — not an error."
        />
      )}

      {discoveries.status === "ready" && total > 0 && (
        <>
          <div className="filter-bar">
            <label>
              Symbol
              <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="e.g. XAUUSD" />
            </label>
            <label>
              Intake status
              <select value={intakeStatus} onChange={(e) => setIntakeStatus(e.target.value as IntakeStatus | "")}>
                <option value="">All</option>
                {INTAKE_STATUS_ORDER.map((s) => (
                  <option key={s} value={s}>
                    {INTAKE_STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Origin
              <select value={originKind} onChange={(e) => setOriginKind(e.target.value as typeof originKind)}>
                <option value="">All</option>
                <option value="ADAPTER_SOURCED">Adapter-sourced</option>
                <option value="USER_DISCOVERED">User-discovered</option>
                <option value="MY_IDEA">My idea</option>
              </select>
            </label>
            <label>
              Sort
              <select value={sort} onChange={(e) => setSort(e.target.value as DiscoverySort)}>
                {SORT_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
            <h2 className="panel-heading">Claimed-performance leaderboard</h2>
            <div style={{ padding: "var(--space-3) var(--space-4) 0" }}>
              <SourceClaimNotice />
            </div>
            {items.length === 0 ? (
              <div style={{ padding: "var(--space-4)" }}>
                <EmptyState
                  title="No discoveries match these filters"
                  body="Try widening the symbol, intake status, or origin filter."
                />
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Title</th>
                    <th scope="col">Origin</th>
                    <th scope="col">Symbol / TF</th>
                    <th scope="col">Net P&amp;L</th>
                    <th scope="col">Max DD</th>
                    <th scope="col">Win %</th>
                    <th scope="col">PF</th>
                    <th scope="col">Trades</th>
                    <th scope="col">Sharpe</th>
                    <th scope="col">Sortino</th>
                    <th scope="col">Intake</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((d) => (
                    <DiscoveryRow key={d.id} d={d} onTransition={transition} />
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <div className="discovery-viz-grid">
            <section className="panel">
              <h2 className="panel-heading">Claimed return vs claimed drawdown</h2>
              <div className="scatter-wrap">
                <SourceClaimNotice compact />
                <ScatterPlot
                  points={returnDrawdownPoints}
                  xLabel="Max drawdown %"
                  yLabel="Net P&L %"
                  formatX={(v) => `${v.toFixed(0)}%`}
                  formatY={(v) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
                />
              </div>
            </section>
            <section className="panel">
              <h2 className="panel-heading">Profit factor vs trade count</h2>
              <div className="scatter-wrap">
                <SourceClaimNotice compact />
                <ScatterPlot
                  points={pfTradeCountPoints}
                  xLabel="Trade count"
                  yLabel="Profit factor"
                  formatX={(v) => v.toFixed(0)}
                  formatY={(v) => v.toFixed(1)}
                />
                <p className="scatter-caption">
                  Faded points have fewer than {LOW_SAMPLE_THRESHOLD} claimed trades — a thin sample, shown honestly,
                  never scored.
                </p>
              </div>
            </section>
          </div>
        </>
      )}

      {showAddForm && (
        <AddStrategyModal
          onClose={() => setShowAddForm(false)}
          onCreated={() => {
            setShowAddForm(false);
            discoveries.reload();
          }}
        />
      )}
    </div>
  );
}

function DiscoveryRow({
  d,
  onTransition,
}: {
  d: ScoutDiscovery;
  onTransition: (id: string, target: IntakeStatus) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const allowed = ALLOWED_INTAKE_TRANSITIONS[d.intake_status] ?? [];

  async function act(target: IntakeStatus) {
    setBusy(true);
    await onTransition(d.id, target);
    setBusy(false);
  }

  return (
    <tr>
      <td>
        <Link className="row-link" to={`/discovery/${d.id}`}>
          {d.title}
        </Link>
      </td>
      <td>{ORIGIN_LABEL[d.origin_kind] ?? d.origin_kind}</td>
      <td className="mono" style={{ color: "var(--ink-dim)" }}>
        {d.source_symbol ?? "—"}
        {d.source_timeframe ? ` / ${d.source_timeframe}` : ""}
      </td>
      <td className="mono">{fmtPercent(d.net_pnl_percent)}</td>
      <td className="mono">{fmtPercent(d.max_drawdown_percent)}</td>
      <td className="mono">{fmtPercent(d.win_rate_percent)}</td>
      <td className="mono">{fmtNumber(d.profit_factor)}</td>
      <td className="mono">{fmtCount(d.trade_count)}</td>
      <td className="mono">{fmtNumber(d.sharpe)}</td>
      <td className="mono">{fmtNumber(d.sortino)}</td>
      <td>
        <IntakeBadge status={d.intake_status} />
      </td>
      <td>
        <div className="row-actions">
          {allowed.includes("SHORTLISTED") && (
            <button
              type="button"
              className="button button--secondary"
              disabled={busy}
              onClick={() => act("SHORTLISTED")}
            >
              Shortlist
            </button>
          )}
          {allowed.includes("REJECTED") && (
            <button type="button" className="button button--secondary" disabled={busy} onClick={() => act("REJECTED")}>
              Reject
            </button>
          )}
          {d.intake_status === "REJECTED" && allowed.includes("NEW") && (
            <button type="button" className="button button--secondary" disabled={busy} onClick={() => act("NEW")}>
              Reopen
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function SourceHealthPanel({ status }: { status: ScoutStatus }) {
  const run = status.last_discovery_run;
  return (
    <section className="panel discovery-source-health" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Source health</h2>
      <div className="discovery-source-health__row">
        <span>Trader.dev public surface</span>
        <StatusBadge status={status.trader_dev_public.reachable ? "OK" : "DOWN"} />
      </div>
      <div className="discovery-source-health__row">
        <span>Latest discovery run</span>
        {run ? (
          <span>
            <span className={`run-status run-status--${run.status.toLowerCase()}`}>{run.status}</span>{" "}
            <span className="mono" style={{ color: "var(--ink-dim)" }}>
              {shortDate(run.completed_at_utc ?? run.started_at_utc)} UTC
            </span>{" "}
            — {run.records_accepted} accepted / {run.records_changed} changed / {run.records_unchanged} unchanged /{" "}
            {run.records_rejected} rejected
          </span>
        ) : (
          <span style={{ color: "var(--ink-faint)" }}>No discovery run has been made yet</span>
        )}
      </div>
    </section>
  );
}

function DiscoverNowPanel({ onRun, onClose }: { onRun: () => void; onClose: () => void }) {
  const [symbol, setSymbol] = useState("");
  const [maxRecords, setMaxRecords] = useState(25);
  const [sort, setSort] = useState<DiscoverySort>("recent");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ScoutDiscoveryRun | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.scoutDiscover({ symbol: symbol.trim() || undefined, max_records: maxRecords, sort });
      setResult(res.discovery_run);
      onRun();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The discovery run could not be started.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="panel discover-now-panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Discover now — bounded, on-demand Trader.dev pass</h2>
      <div style={{ padding: "var(--space-4)" }}>
        <p style={{ color: "var(--ink-dim)", fontSize: 13, marginBottom: "var(--space-3)" }}>
          Runs exactly one deliberate, bounded pass against Trader.dev's public surface when you press Run — it never
          runs automatically, and it calls a real external service.
        </p>
        <div className="form-row">
          <label className="form-field">
            Symbol (optional)
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="e.g. XAUUSD"
              disabled={running}
            />
          </label>
          <label className="form-field">
            Max records
            <input
              type="number"
              min={1}
              max={200}
              value={maxRecords}
              onChange={(e) => setMaxRecords(Number(e.target.value))}
              disabled={running}
            />
          </label>
          <label className="form-field">
            Sort
            <select value={sort} onChange={(e) => setSort(e.target.value as DiscoverySort)} disabled={running}>
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="modal-panel__actions" style={{ justifyContent: "flex-start", padding: 0, marginTop: "var(--space-3)" }}>
          <button type="button" className="button" onClick={run} disabled={running}>
            {running ? "Running…" : "Run discovery"}
          </button>
          <button type="button" className="button button--secondary" onClick={onClose} disabled={running}>
            Close
          </button>
        </div>
        {running && <LoadingState label="Contacting Trader.dev — this can take a few seconds…" />}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {result && (
          <p className="discover-now-result" data-run-status={result.status}>
            Run <strong>{result.status}</strong>: {result.records_observed} observed, {result.records_accepted}{" "}
            accepted, {result.records_changed} changed, {result.records_unchanged} unchanged,{" "}
            {result.records_rejected} rejected.
            {result.error_summary && <> {result.error_summary}</>}
          </p>
        )}
      </div>
    </section>
  );
}
