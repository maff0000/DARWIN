import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import { ALLOWED_INTAKE_TRANSITIONS, INTAKE_STATUS_LABEL } from "../api/intakeTransitions";
import { useApi } from "../api/useApi";
import type { IntakeStatus } from "../api/types";
import { ErrorState } from "../components/ErrorState";
import { IdValue } from "../components/IdValue";
import { IntakeBadge } from "../components/IntakeBadge";
import { KvRow } from "../components/KeyValue";
import { LoadingState } from "../components/LoadingState";
import { SourceClaimNotice } from "../components/SourceClaimNotice";

const ORIGIN_LABEL: Record<string, string> = {
  ADAPTER_SOURCED: "Adapter-sourced (Trader.dev)",
  USER_DISCOVERED: "User-discovered (Matt found this externally)",
  MY_IDEA: "My idea (Matt's own hypothesis, no external source)",
};

function fmtPercent(v: string | null): string {
  if (v === null) return "—";
  const n = Number(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function fmtNumber(v: string | null): string {
  return v === null ? "—" : Number(v).toFixed(2);
}
function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return iso.replace("T", " ").replace(/\.\d+/, "").replace("Z", " UTC");
}

export function DiscoveryDetail() {
  const { id } = useParams<{ id: string }>();
  const detail = useApi(() => api.scoutDiscovery(id!), [id]);

  if (detail.status === "loading")
    return (
      <div className="page">
        <LoadingState label="Loading discovery…" />
      </div>
    );
  if (detail.status === "error")
    return (
      <div className="page">
        <ErrorState error={detail.error} dependency={`discovery ${id}`} onRetry={detail.reload} />
      </div>
    );

  const { discovery: d, snapshots, intake_audit_history } = detail.data;
  const hasAnyMetric =
    d.net_pnl_percent !== null ||
    d.max_drawdown_percent !== null ||
    d.win_rate_percent !== null ||
    d.profit_factor !== null ||
    d.trade_count !== null ||
    d.sharpe !== null ||
    d.sortino !== null;

  return (
    <div className="page">
      <div className="page-header">
        <h1>{d.title}</h1>
        <IntakeBadge status={d.intake_status} />
      </div>

      <section className="panel" style={{ margin: "var(--space-5) 0" }}>
        <h2 className="panel-heading">Source identity</h2>
        <dl className="kv-list">
          <KvRow label="Discovery ID">
            <IdValue value={d.id} />
          </KvRow>
          <KvRow label="Origin">{ORIGIN_LABEL[d.origin_kind] ?? d.origin_kind}</KvRow>
          <KvRow label="Source record identity">
            {d.source_strategy_id ? (
              <IdValue value={d.source_strategy_id} mono abbreviate={false} />
            ) : (
              <span style={{ color: "var(--ink-faint)" }}>— (no external source identity for this origin)</span>
            )}
          </KvRow>
          <KvRow label="Forked from">
            {d.forked_from_source_strategy_id ? (
              <IdValue value={d.forked_from_source_strategy_id} mono abbreviate={false} />
            ) : (
              <span style={{ color: "var(--ink-faint)" }}>—</span>
            )}
          </KvRow>
          <KvRow label="Family resolution">
            <span className="mono">{d.family_resolution}</span>
          </KvRow>
          <KvRow label="Source URL / reference">
            {d.origin_url ? (
              <a href={d.origin_url} target="_blank" rel="noopener noreferrer">
                {d.origin_url}
              </a>
            ) : (
              <span style={{ color: "var(--ink-faint)" }}>—</span>
            )}
          </KvRow>
          <KvRow label="Origin description">{d.origin_description ?? <span style={{ color: "var(--ink-faint)" }}>—</span>}</KvRow>
          <KvRow label="Source symbol / timeframe (verbatim)">
            <span className="mono">
              {d.source_symbol ?? "—"} / {d.source_timeframe ?? "—"}
            </span>
          </KvRow>
          <KvRow label="First seen (UTC)">
            <span className="mono">{fmtDate(d.first_seen_utc)}</span>
          </KvRow>
          <KvRow label="Last seen (UTC)">
            <span className="mono">{fmtDate(d.last_seen_utc)}</span>
          </KvRow>
          <KvRow label="Rule/report availability">
            <span className="mono">{d.latest_rule_availability ?? "UNKNOWN"}</span>
          </KvRow>
          <KvRow label="Tags">
            {d.tags.length ? d.tags.join(", ") : <span style={{ color: "var(--ink-faint)" }}>—</span>}
          </KvRow>
        </dl>
      </section>

      <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Exact source claims</h2>
        <div style={{ padding: "var(--space-3) var(--space-4) 0" }}>
          <SourceClaimNotice />
        </div>
        {hasAnyMetric ? (
          <dl className="kv-list">
            <KvRow label="Net P&L">
              <span className="mono">{fmtPercent(d.net_pnl_percent)}</span>
            </KvRow>
            <KvRow label="Max drawdown">
              <span className="mono">{fmtPercent(d.max_drawdown_percent)}</span>
            </KvRow>
            <KvRow label="Win rate">
              <span className="mono">{fmtPercent(d.win_rate_percent)}</span>
            </KvRow>
            <KvRow label="Profit factor">
              <span className="mono">{fmtNumber(d.profit_factor)}</span>
            </KvRow>
            <KvRow label="Trade count">
              <span className="mono">{d.trade_count ?? "—"}</span>
            </KvRow>
            <KvRow label="Sharpe">
              <span className="mono">{fmtNumber(d.sharpe)}</span>
            </KvRow>
            <KvRow label="Sortino">
              <span className="mono">{fmtNumber(d.sortino)}</span>
            </KvRow>
          </dl>
        ) : (
          <p style={{ padding: "0 var(--space-4) var(--space-4)", color: "var(--ink-dim)", fontSize: 13 }}>
            No performance figures were supplied for this discovery — honestly absent, never defaulted to zero.
          </p>
        )}
      </section>

      {(d.original_description || d.pasted_rule_text || d.personal_notes) && (
        <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
          <h2 className="panel-heading">Source fidelity — exactly as written, never reinterpreted</h2>
          <div style={{ padding: "var(--space-4)", display: "grid", gap: "var(--space-4)" }}>
            {d.original_description && (
              <div>
                <h3 style={{ fontSize: 13, color: "var(--ink-dim)", marginBottom: "var(--space-1)" }}>
                  Original description
                </h3>
                <p style={{ fontSize: 13 }}>{d.original_description}</p>
              </div>
            )}
            {d.pasted_rule_text && (
              <div>
                <h3 style={{ fontSize: 13, color: "var(--ink-dim)", marginBottom: "var(--space-1)" }}>
                  Pasted rule/code text (inert — never executed, never rendered as HTML/markdown)
                </h3>
                {/* React text children are always escaped — this renders the exact
                    string as plain text, never dangerouslySetInnerHTML, per the
                    PID-003 security doctrine for untrusted external content. */}
                <pre className="pasted-rule-text">{d.pasted_rule_text}</pre>
              </div>
            )}
            {d.personal_notes && (
              <div>
                <h3 style={{ fontSize: 13, color: "var(--ink-dim)", marginBottom: "var(--space-1)" }}>
                  Personal notes
                </h3>
                <p style={{ fontSize: 13 }}>{d.personal_notes}</p>
              </div>
            )}
          </div>
        </section>
      )}

      <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Extraction / snapshot history</h2>
        {snapshots.length === 0 ? (
          <p style={{ padding: "var(--space-4)", color: "var(--ink-dim)", fontSize: 13 }}>
            No snapshot has been recorded for this discovery yet.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Extracted (UTC)</th>
                <th scope="col">Adapter</th>
                <th scope="col">Rule availability</th>
                <th scope="col">Fingerprint</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((s) => (
                <tr key={s.id}>
                  <td className="mono">{fmtDate(s.extraction_utc)}</td>
                  <td className="mono">
                    {s.adapter_name} {s.adapter_version}
                  </td>
                  <td className="mono">{s.rule_availability}</td>
                  <td>
                    <IdValue value={s.fingerprint_sha256} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <IntakeControls discoveryId={d.id} current={d.intake_status} auditHistory={intake_audit_history} onChanged={detail.reload} />

      <OpenWorkshopPanel discoveryId={d.id} title={d.title} />
    </div>
  );
}

function OpenWorkshopPanel({ discoveryId, title }: { discoveryId: string; title: string }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Open Workshop is a real, deliberate action against the real backend
  // (PID-004B directive) -- never a client-constructed Workshop. Idempotent
  // per discovery: POST /api/v1/candidates resolves to the SAME candidate
  // on a repeat click (migration 0010's own partial unique index), and
  // POST /api/v1/workshops is itself idempotent per candidate_id -- so a
  // second "Open Workshop" click (or a reload before navigation completed)
  // always lands on the SAME Workshop, never a duplicate.
  async function openWorkshop() {
    setBusy(true);
    setError(null);
    try {
      const { candidate } = await api.openCandidate({ title, origin_discovery_id: discoveryId });
      const { workshop } = await api.openWorkshop({
        candidate_id: candidate.candidate_id,
        discovery_ids: [discoveryId],
      });
      navigate(`/workshops/${workshop.workshop_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not open the Strategy Workshop.");
      setBusy(false);
    }
  }

  return (
    <section className="panel workshop-panel" style={{ margin: "var(--space-5) 0" }}>
      <h2 className="panel-heading">Strategy Workshop</h2>
      <div style={{ padding: "var(--space-4)" }}>
        <button type="button" className="button" onClick={openWorkshop} disabled={busy}>
          {busy ? "Opening…" : "Open Workshop"}
        </button>
        <p style={{ marginTop: "var(--space-2)", color: "var(--ink-faint)", fontSize: 12.5 }}>
          Opens (or resumes) a real Strategy Workshop against this discovery — a human authoring surface only.
          This never invokes an AI agent, generates rules automatically, or produces a StrategyVersion by itself.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </section>
  );
}

function IntakeControls({
  discoveryId,
  current,
  auditHistory,
  onChanged,
}: {
  discoveryId: string;
  current: IntakeStatus;
  auditHistory: Array<{ id: string; from_status: IntakeStatus | null; to_status: IntakeStatus; changed_by: string; reason: string | null; changed_at_utc: string }>;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = ALLOWED_INTAKE_TRANSITIONS[current] ?? [];

  async function act(target: IntakeStatus) {
    setBusy(true);
    setError(null);
    try {
      await api.scoutSetIntakeStatus(discoveryId, { target_status: target, changed_by: "matt" });
      onChanged();
    } catch {
      setError("That transition was not accepted — the discovery's state may have changed since this page loaded.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Intake status</h2>
      <div style={{ padding: "var(--space-4)" }}>
        <p style={{ marginBottom: "var(--space-3)" }}>
          Currently <IntakeBadge status={current} />
        </p>
        <div className="row-actions">
          {allowed.map((target) => (
            <button key={target} type="button" className="button button--secondary" disabled={busy} onClick={() => act(target)}>
              Move to {INTAKE_STATUS_LABEL[target]}
            </button>
          ))}
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}

        <h3 style={{ fontSize: 13, color: "var(--ink-dim)", marginTop: "var(--space-5)", marginBottom: "var(--space-2)" }}>
          Intake audit history
        </h3>
        {auditHistory.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>No intake-status change has been recorded yet.</p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--space-2)" }}>
            {auditHistory.map((a) => (
              <li key={a.id} style={{ fontSize: 12.5, color: "var(--ink-dim)" }}>
                <span className="mono">{fmtDate(a.changed_at_utc)}</span> — {a.from_status ?? "(created)"} →{" "}
                <strong style={{ color: "var(--ink)" }}>{a.to_status}</strong> by {a.changed_by}
                {a.reason && <> — {a.reason}</>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
