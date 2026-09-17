import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { IdValue } from "../components/IdValue";
import { KvRow } from "../components/KeyValue";

export function SystemStatus() {
  const summary = useApi(api.systemSummary, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>System Status</h1>
      </div>

      {summary.status === "error" && (
        <ErrorState error={summary.error} dependency="system summary" onRetry={summary.reload} />
      )}

      {summary.status === "ready" && (
        <>
          <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
            <h2 className="panel-heading">Build</h2>
            <dl className="kv-list">
              <KvRow label="Application version"><span className="mono">{summary.data.build.application_version}</span></KvRow>
              <KvRow label="Commit"><IdValue value={summary.data.build.commit} abbreviate={false} /></KvRow>
              <KvRow label="Build time (UTC)"><span className="mono">{summary.data.build.build_time}</span></KvRow>
              <KvRow label="Environment"><span className="mono">{summary.data.build.environment}</span></KvRow>
              <KvRow label="Process health"><span className="mono">{summary.data.health}</span></KvRow>
            </dl>
          </section>

          <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
            <h2 className="panel-heading">Readiness — {summary.data.readiness.ready ? "ready" : "not ready"}</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Component</th>
                  <th scope="col">Status</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {summary.data.readiness.components.map((c) => (
                  <tr key={c.name}>
                    <td>{c.name}</td>
                    <td><StatusBadge status={c.status} /></td>
                    <td className="mono" style={{ color: "var(--ink-dim)" }}>{c.detail || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="panel">
            <h2 className="panel-heading">Record counts</h2>
            <div className="grid-cards" style={{ padding: "var(--space-4)" }}>
              {Object.entries(summary.data.record_counts).map(([k, v]) => (
                <div key={k} className="stat-card">
                  <div className="stat-card__value">{v}</div>
                  <div className="stat-card__label">{k.replace(/_/g, " ")}</div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
