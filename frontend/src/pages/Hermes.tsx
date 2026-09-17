import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { StatusBadge } from "../components/StatusBadge";
import { IdValue } from "../components/IdValue";
import { KvRow } from "../components/KeyValue";

/** DARWIN's adapter/dependency view of HERMES only — never an administration
 * panel, never a mutation surface (PID-002 §12). */
export function Hermes() {
  const summary = useApi(api.systemSummary, []);
  const datasets = useApi(() => api.listDatasets(1), []);

  if (summary.status === "error") {
    return (
      <div className="page">
        <div className="page-header"><h1>HERMES</h1></div>
        <ErrorState error={summary.error} dependency="system summary" onRetry={summary.reload} />
      </div>
    );
  }
  if (summary.status !== "ready") return <p className="page">Loading…</p>;

  const hermes = summary.data.readiness.components.find((c) => c.name === "hermes_adapter");
  const sample = datasets.status === "ready" ? datasets.data.items[0] : undefined;

  return (
    <div className="page">
      <div className="page-header">
        <h1>HERMES</h1>
      </div>
      <p style={{ color: "var(--ink-dim)", maxWidth: 640, marginBottom: "var(--space-5)" }}>
        HERMES is DARWIN's canonical historical market-data authority. DARWIN is a read-only consumer. This page
        shows DARWIN's own dependency view — not a HERMES administration surface.
      </p>

      <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Adapter status</h2>
        <dl className="kv-list">
          <KvRow label="Status">{hermes ? <StatusBadge status={hermes.status} /> : "—"}</KvRow>
          <KvRow label="Detail"><span className="mono" style={{ color: "var(--ink-dim)" }}>{hermes?.detail || "Reachable"}</span></KvRow>
          <KvRow label="Relationship"><span>Read-only historical authority — no write path exists from DARWIN.</span></KvRow>
        </dl>
      </section>

      <section className="panel">
        <h2 className="panel-heading">Canonical contract</h2>
        {sample ? (
          <dl className="kv-list">
            <KvRow label="Contract version"><span className="mono">{sample.hermes_contract_version}</span></KvRow>
            <KvRow label="Contract commit"><IdValue value={sample.hermes_contract_commit} /></KvRow>
          </dl>
        ) : (
          <p style={{ padding: "var(--space-4)", color: "var(--ink-dim)" }}>
            No dataset has been loaded yet, so no contract identity has been observed in this environment.
          </p>
        )}
      </section>
    </div>
  );
}
