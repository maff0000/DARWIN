import type { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { IdValue } from "../components/IdValue";

/** Renders instrument unit semantics ("USD per troy ounce") entirely from
 * the governed InstrumentDefinition API response — never a hardcoded XAU
 * string (A-001 instrument-genericity requirement, PID-002 §8). If a second
 * instrument existed, this page renders it correctly with zero changes. */
function unitSentence(def: { price_unit: string; base_quantity_unit: string; base_asset: string; quote_asset: string }) {
  const priceUnit = def.price_unit.replace(/_/g, " ");
  return `${def.base_asset}_${def.quote_asset} price → ${priceUnit.toLowerCase()}`;
}

export function DatasetDetail() {
  const { id } = useParams<{ id: string }>();
  const dataset = useApi(() => api.getDataset(id!), [id]);
  const instrument = dataset.status === "ready" ? dataset.data.instrument : undefined;
  const def = useApi(() => (instrument ? api.getInstrumentDefinition(instrument) : Promise.reject(new Error("no instrument"))), [instrument]);

  if (dataset.status === "loading") return <p className="page">Loading dataset…</p>;
  if (dataset.status === "error")
    return (
      <div className="page">
        <ErrorState error={dataset.error} dependency={`dataset ${id}`} onRetry={dataset.reload} />
      </div>
    );

  const d = dataset.data;

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          {d.instrument} <span style={{ color: "var(--ink-dim)", fontWeight: 400 }}>· {d.timeframe}</span>
        </h1>
      </div>

      {def.status === "ready" && (
        <p style={{ color: "var(--ink-dim)", marginBottom: "var(--space-5)" }}>{unitSentence(def.data)}</p>
      )}

      <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Dataset identity</h2>
        <dl className="kv-list">
          <Row label="Dataset ID"><IdValue value={d.id} /></Row>
          <Row label="Instrument"><span className="mono">{d.instrument}</span></Row>
          <Row label="Timeframe"><span className="mono">{d.timeframe}</span></Row>
          <Row label="Requested interval (UTC)">
            <span className="mono">{d.requested_start_utc} → {d.requested_end_utc}</span>
          </Row>
          <Row label="Actual first/last candle">
            <span className="mono">
              {d.actual_first_open_utc ?? "—"} → {d.actual_last_open_utc ?? "—"}
            </span>
          </Row>
          <Row label="Record count">{d.record_count}</Row>
          <Row label="Dataset fingerprint"><IdValue value={d.fingerprint_sha256} abbreviate={false} /></Row>
          <Row label="Gaps"><span className="mono">{JSON.stringify(d.gap_summary)}</span></Row>
          <Row label="Loaded at (UTC)"><span className="mono">{d.loaded_at_utc}</span></Row>
        </dl>
      </section>

      <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Governed instrument definition</h2>
        {def.status === "loading" && <p style={{ padding: "var(--space-4)" }}>Loading…</p>}
        {def.status === "error" && (
          <div style={{ padding: "var(--space-4)" }}>
            <ErrorState error={def.error} dependency="instrument definition" onRetry={def.reload} />
          </div>
        )}
        {def.status === "ready" && (
          <dl className="kv-list">
            <Row label="Instrument ID"><span className="mono">{def.data.instrument_id}</span></Row>
            <Row label="Base asset"><span className="mono">{def.data.base_asset}</span></Row>
            <Row label="Quote asset"><span className="mono">{def.data.quote_asset}</span></Row>
            <Row label="Base quantity unit"><span className="mono">{def.data.base_quantity_unit}</span></Row>
            <Row label="Price unit"><span className="mono">{def.data.price_unit}</span></Row>
            <Row label="Definition version"><span className="mono">{def.data.definition_version}</span></Row>
            <Row label="Definition fingerprint"><IdValue value={def.data.fingerprint} /></Row>
          </dl>
        )}
      </section>

      <section className="panel">
        <h2 className="panel-heading">HERMES provenance</h2>
        <dl className="kv-list">
          <Row label="Contract version"><span className="mono">{d.hermes_contract_version}</span></Row>
          <Row label="Contract commit"><IdValue value={d.hermes_contract_commit} /></Row>
          <Row label="Adapter/build version"><span className="mono">{d.adapter_build_version}</span></Row>
        </dl>
      </section>
    </div>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="kv-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
