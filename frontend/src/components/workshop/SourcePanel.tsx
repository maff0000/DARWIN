import type { ScoutDiscovery } from "../../api/types";
import { SourceClaimNotice } from "../SourceClaimNotice";
import { KvRow } from "../KeyValue";

/** What SCOUT actually discovered — reuses the exact SOURCE_CLAIM notice
 * treatment from the Discovery pages (PID-004B directive: "don't invent a
 * new one"). The raw `source_symbol` stays visually distinct (mono, its
 * own row, explicitly labelled "raw / uninterpreted") from any later
 * canonical instrument selection made in the Specification panel. */
export function SourcePanel({
  discovery,
  discoveryCount,
}: {
  discovery: ScoutDiscovery | null;
  discoveryCount: number;
}) {
  return (
    <section className="panel" style={{ margin: "var(--space-5) 0" }}>
      <h2 className="panel-heading">Source (SCOUT)</h2>
      {discovery === null ? (
        <p style={{ padding: "var(--space-4)", color: "var(--ink-dim)", fontSize: 13 }}>
          This Workshop was opened with no SCOUT discovery attached — a legitimate controlled fixture (PID-004
          sec49). There is no external source claim to display.
        </p>
      ) : (
        <>
          <div style={{ padding: "var(--space-3) var(--space-4) 0" }}>
            <SourceClaimNotice />
          </div>
          <dl className="kv-list">
            <KvRow label="Title">{discovery.title}</KvRow>
            <KvRow label="Origin">{discovery.origin_kind}</KvRow>
            <KvRow label="Source URL / reference">
              {discovery.origin_url ? (
                <a href={discovery.origin_url} target="_blank" rel="noopener noreferrer">
                  {discovery.origin_url}
                </a>
              ) : (
                <span style={{ color: "var(--ink-faint)" }}>—</span>
              )}
            </KvRow>
            <KvRow label="Raw source symbol (uninterpreted)">
              <span className="mono workshop-raw-symbol">{discovery.source_symbol ?? "—"}</span>
            </KvRow>
            <KvRow label="Raw source timeframe (uninterpreted)">
              <span className="mono workshop-raw-symbol">{discovery.source_timeframe ?? "—"}</span>
            </KvRow>
            <KvRow label="Source description">
              {discovery.origin_description ?? <span style={{ color: "var(--ink-faint)" }}>—</span>}
            </KvRow>
            <KvRow label="Rule/report availability">
              <span className="mono">{discovery.latest_rule_availability ?? "UNKNOWN"}</span>
            </KvRow>
          </dl>
          {discoveryCount > 1 && (
            <p style={{ padding: "0 var(--space-4) var(--space-4)", color: "var(--ink-dim)", fontSize: 12.5 }}>
              This Workshop links {discoveryCount} SCOUT discoveries in total — showing the first; every linked
              discovery is durably recorded (`strategy_workshop_discovery_links`), never merged into one.
            </p>
          )}
        </>
      )}
    </section>
  );
}
