import { Link, useParams } from "react-router-dom";
import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { EvidenceBadge, EvidenceExplain } from "../components/EvidenceBadge";
import { DikePanel } from "../components/DikePanel";
import { IdValue } from "../components/IdValue";
import { KvRow } from "../components/KeyValue";

export function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const run = useApi(() => api.getRun(id!), [id]);

  if (run.status === "loading") return <p className="page">Loading run…</p>;
  if (run.status === "error")
    return (
      <div className="page">
        <ErrorState error={run.error} dependency={`run ${id}`} onRetry={run.reload} />
      </div>
    );

  const r = run.data;

  return (
    <div className="page">
      <div className="page-header">
        <h1>{r.display_title}</h1>
        <EvidenceBadge level={r.result_kind} />
      </div>
      <EvidenceExplain level={r.result_kind} />

      <section className="panel" style={{ margin: "var(--space-5) 0" }}>
        <h2 className="panel-heading">Run identity</h2>
        <dl className="kv-list">
          <KvRow label="Run ID"><IdValue value={r.id} /></KvRow>
          <KvRow label="Candidate / version">
            {r.candidate_id ? <IdValue value={r.candidate_id} /> : <span style={{ color: "var(--ink-faint)" }}>—</span>}
            {r.version_id && <> / <IdValue value={r.version_id} /></>}
          </KvRow>
          <KvRow label="Instrument"><span className="mono">{r.instrument}</span></KvRow>
          <KvRow label="Instrument definition"><IdValue value={r.instrument_definition_id} /></KvRow>
          <KvRow label="Timeframe"><span className="mono">{r.timeframe}</span></KvRow>
          <KvRow label="Dataset">
            {r.dataset_id ? (
              <Link to={`/datasets/${r.dataset_id}`}>
                <IdValue value={r.dataset_id} />
              </Link>
            ) : (
              <span style={{ color: "var(--ink-faint)" }}>—</span>
            )}
          </KvRow>
          <KvRow label="Engine"><span className="mono">{r.engine}</span></KvRow>
          <KvRow label="Build version"><span className="mono">{r.build_version}</span></KvRow>
          <KvRow label="Configuration fingerprint">
            {r.configuration_fingerprint ? <IdValue value={r.configuration_fingerprint} /> : "—"}
          </KvRow>
          <KvRow label="Status"><span className="mono">{r.status}</span></KvRow>
          <KvRow label="Created (UTC)"><span className="mono">{r.created_at_utc}</span></KvRow>
          <KvRow label="Updated (UTC)"><span className="mono">{r.updated_at_utc ?? "—"}</span></KvRow>
        </dl>
      </section>

      <DikePanel run={r} />
    </div>
  );
}
