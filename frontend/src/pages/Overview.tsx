import { Link } from "react-router-dom";
import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { IdValue } from "../components/IdValue";

export function Overview() {
  const summary = useApi(api.systemSummary, []);
  const datasets = useApi(() => api.listDatasets(5), []);
  const runs = useApi(() => api.listRuns(5), []);

  if (summary.status === "loading") {
    return <p className="page">Loading system summary…</p>;
  }
  if (summary.status === "error") {
    return (
      <div className="page">
        <ErrorState error={summary.error} dependency="system summary" onRetry={summary.reload} />
      </div>
    );
  }

  const { build, readiness, record_counts: counts } = summary.data;
  const blocking = readiness.components.filter((c) => c.status !== "OK" && c.name !== "hermes_adapter");
  const hermes = readiness.components.find((c) => c.name === "hermes_adapter");

  return (
    <div className="page">
      <div className="page-header">
        <h1>Overview</h1>
        <span className="page-header__meta">
          v{build.application_version} · <IdValue value={build.commit} head={9} tail={0} />
        </span>
      </div>

      {blocking.length > 0 && (
        <div className="degraded-banner">
          <strong>DARWIN is degraded.</strong>
          <span>{blocking.map((c) => `${c.name}: ${c.detail || c.status}`).join(" — ")}</span>
        </div>
      )}
      {hermes && hermes.status !== "OK" && (
        <div className="degraded-banner">
          <strong>HERMES historical access is degraded.</strong>
          <span>{hermes.detail}. DARWIN's own control plane is unaffected.</span>
        </div>
      )}

      <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Component health</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Component</th>
              <th scope="col">Status</th>
              <th scope="col">Detail</th>
            </tr>
          </thead>
          <tbody>
            {readiness.components.map((c) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
                <td className="mono" style={{ color: "var(--ink-dim)" }}>
                  {c.detail || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <h2 style={{ fontSize: 14, color: "var(--ink-dim)", marginBottom: "var(--space-3)" }}>
        Foundation record counts
      </h2>
      <div className="grid-cards" style={{ marginBottom: "var(--space-6)" }}>
        <StatCard label="Source strategies" value={counts.source_strategies} />
        <StatCard label="Strategy candidates" value={counts.strategy_candidates} />
        <StatCard label="Strategy versions" value={counts.strategy_versions} />
        <StatCard label="Market datasets" value={counts.market_datasets} />
        <StatCard label="Research runs" value={counts.research_runs} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-5)" }}>
        <section className="panel">
          <h2 className="panel-heading">Recent datasets</h2>
          {datasets.status === "ready" && datasets.data.items.length === 0 && (
            <div style={{ padding: "var(--space-4)" }}>
              <EmptyState
                title="No datasets loaded yet"
                body="DARWIN hasn't loaded a MarketDataset from HERMES yet. Once a bounded historical range is loaded, it appears here."
              />
            </div>
          )}
          {datasets.status === "ready" && datasets.data.items.length > 0 && (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {datasets.data.items.map((d) => (
                <li key={d.id} style={{ borderBottom: "1px solid var(--line)" }}>
                  <Link className="row-link" to={`/datasets/${d.id}`} style={{ display: "block", padding: "10px 16px" }}>
                    <strong>{d.instrument}</strong> · {d.timeframe} · {d.record_count} rows
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel">
          <h2 className="panel-heading">Recent research runs</h2>
          {runs.status === "ready" && runs.data.items.length === 0 && (
            <div style={{ padding: "var(--space-4)" }}>
              <EmptyState
                title="No research runs yet"
                body="No ATHENA or APOLLO run has been recorded yet — DARWIN hasn't begun strategy research. This is expected before SCOUT/SPECIFICATION/ATHENA/APOLLO land."
              />
            </div>
          )}
          {runs.status === "ready" && runs.data.items.length > 0 && (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {runs.data.items.map((r) => (
                <li key={r.id} style={{ borderBottom: "1px solid var(--line)" }}>
                  <Link className="row-link" to={`/runs/${r.id}`} style={{ display: "block", padding: "10px 16px" }}>
                    {r.display_title}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat-card">
      <div className="stat-card__value">{value}</div>
      <div className="stat-card__label">{label}</div>
    </div>
  );
}
