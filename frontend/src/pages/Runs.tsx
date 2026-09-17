import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";

export function Runs() {
  const runs = useApi(() => api.listRuns(100), []);
  const [instrument, setInstrument] = useState("");
  const [resultKind, setResultKind] = useState("");
  const [dikeState, setDikeState] = useState("");

  const items = runs.status === "ready" ? runs.data.items : [];
  const instruments = useMemo(() => Array.from(new Set(items.map((r) => r.instrument))).sort(), [items]);
  const kinds = useMemo(() => Array.from(new Set(items.map((r) => r.result_kind))).sort(), [items]);

  const filtered = items.filter(
    (r) =>
      (!instrument || r.instrument === instrument) &&
      (!resultKind || r.result_kind === resultKind) &&
      (!dikeState || r.dike_state === dikeState),
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Research Runs</h1>
        <span className="page-header__meta">{filtered.length} of {items.length}</span>
      </div>

      {runs.status === "error" && <ErrorState error={runs.error} dependency="research runs" onRetry={runs.reload} />}

      {runs.status === "ready" && items.length === 0 && (
        <EmptyState
          title="No research runs recorded yet"
          body="A ResearchRun is created when a strategy candidate is tested against a MarketDataset by ATHENA or APOLLO. Neither module exists yet — this list will populate once they land."
          hint="This is the correct state for DARWIN's current milestone stage, not an error."
        />
      )}

      {runs.status === "ready" && items.length > 0 && (
        <>
          <div className="filter-bar">
            <label>
              Instrument
              <select value={instrument} onChange={(e) => setInstrument(e.target.value)}>
                <option value="">All</option>
                {instruments.map((i) => (
                  <option key={i} value={i}>{i}</option>
                ))}
              </select>
            </label>
            <label>
              Evidence class
              <select value={resultKind} onChange={(e) => setResultKind(e.target.value)}>
                <option value="">All</option>
                {kinds.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </label>
            <label>
              DIKE state
              <select value={dikeState} onChange={(e) => setDikeState(e.target.value)}>
                <option value="">All</option>
                <option value="DIKE_DISABLED">DIKE_DISABLED</option>
                <option value="DIKE_GUARDED">DIKE_GUARDED</option>
              </select>
            </label>
          </div>

          <section className="panel">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Instrument</th>
                  <th scope="col">Timeframe</th>
                  <th scope="col">Evidence</th>
                  <th scope="col">Engine</th>
                  <th scope="col">Status</th>
                  <th scope="col">DIKE</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link className="row-link" to={`/runs/${r.id}`}>
                        {r.display_title}
                      </Link>
                    </td>
                    <td>{r.instrument}</td>
                    <td>{r.timeframe}</td>
                    <td><EvidenceBadge level={r.result_kind} dense /></td>
                    <td>{r.engine}</td>
                    <td>{r.status}</td>
                    <td className="mono" style={{ color: "var(--ink-dim)" }}>{r.dike_state}</td>
                    <td className="mono" style={{ color: "var(--ink-dim)" }}>
                      {r.created_at_utc.replace("T", " ").slice(0, 16)} UTC
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
