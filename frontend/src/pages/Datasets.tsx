import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { IdValue } from "../components/IdValue";

export function Datasets() {
  const datasets = useApi(() => api.listDatasets(100), []);
  const [instrument, setInstrument] = useState("");
  const [timeframe, setTimeframe] = useState("");

  const items = datasets.status === "ready" ? datasets.data.items : [];
  const instruments = useMemo(() => Array.from(new Set(items.map((d) => d.instrument))).sort(), [items]);
  const timeframes = useMemo(() => Array.from(new Set(items.map((d) => d.timeframe))).sort(), [items]);
  const filtered = items.filter(
    (d) => (!instrument || d.instrument === instrument) && (!timeframe || d.timeframe === timeframe),
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Datasets</h1>
        <span className="page-header__meta">{filtered.length} of {items.length}</span>
      </div>

      {datasets.status === "error" && (
        <ErrorState error={datasets.error} dependency="datasets" onRetry={datasets.reload} />
      )}

      {datasets.status === "ready" && items.length === 0 && (
        <EmptyState
          title="No MarketDatasets loaded yet"
          body="A MarketDataset is created whenever DARWIN loads a bounded, canonical historical range from HERMES. None has been loaded in this environment yet."
          hint="Foundation's own CLI (darwin dataset-load) or a later SCOUT/ATHENA/APOLLO workflow will populate this list."
        />
      )}

      {datasets.status === "ready" && items.length > 0 && (
        <>
          <div className="filter-bar">
            <label>
              Instrument
              <select value={instrument} onChange={(e) => setInstrument(e.target.value)}>
                <option value="">All</option>
                {instruments.map((i) => (
                  <option key={i} value={i}>
                    {i}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Timeframe
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
                <option value="">All</option>
                {timeframes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <section className="panel">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Instrument</th>
                  <th scope="col">Timeframe</th>
                  <th scope="col">Interval (UTC)</th>
                  <th scope="col">Rows</th>
                  <th scope="col">Fingerprint</th>
                  <th scope="col">Loaded</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <Link className="row-link" to={`/datasets/${d.id}`}>
                        {d.instrument}
                      </Link>
                    </td>
                    <td>{d.timeframe}</td>
                    <td className="mono" style={{ color: "var(--ink-dim)" }}>
                      {shortDate(d.requested_start_utc)} → {shortDate(d.requested_end_utc)}
                    </td>
                    <td>{d.record_count}</td>
                    <td>
                      <IdValue value={d.fingerprint_sha256} />
                    </td>
                    <td className="mono" style={{ color: "var(--ink-dim)" }}>
                      {shortDate(d.loaded_at_utc)}
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

function shortDate(iso: string): string {
  return iso.replace("T", " ").replace(/\.\d+/, "").replace("Z", " UTC").slice(0, 20);
}
