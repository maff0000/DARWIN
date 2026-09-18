import { useState } from "react";
import type { ValidationOutcome } from "../../api/types";

/** Real findings from the real validator (PID-004B directive) — the
 * canonical `status` code (`VALID` / `STRATEGY_NOT_SUFFICIENTLY_DEFINED`)
 * is always shown verbatim, never replaced by a vague frontend label (a
 * human-friendly explanation may accompany it, never replace it). */
export function ValidationPanel({
  validation,
  onRevalidate,
}: {
  validation: ValidationOutcome | null;
  onRevalidate: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  async function revalidate() {
    setBusy(true);
    try {
      await onRevalidate();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Validation</h2>
      <div style={{ padding: "var(--space-4)" }}>
        {validation === null ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>Not yet validated — no draft exists yet.</p>
        ) : (
          <>
            <p>
              <span className={`workshop-badge workshop-badge--validation-${validation.status.toLowerCase()}`}>
                {validation.status}
              </span>{" "}
              <span style={{ color: "var(--ink-dim)", fontSize: 12.5 }}>
                {validation.is_valid
                  ? "This draft is structurally and semantically complete."
                  : "This draft is not yet sufficiently defined to finalise — see findings below."}
              </span>
            </p>
            {validation.findings.length === 0 ? (
              <p style={{ color: "var(--ink-faint)", fontSize: 12.5, marginTop: "var(--space-3)" }}>
                No findings.
              </p>
            ) : (
              <table className="data-table" style={{ marginTop: "var(--space-3)" }}>
                <thead>
                  <tr>
                    <th scope="col">Stage</th>
                    <th scope="col">Code</th>
                    <th scope="col">Message</th>
                    <th scope="col">Path</th>
                  </tr>
                </thead>
                <tbody>
                  {validation.findings.map((f, i) => (
                    <tr key={`${f.code}-${i}`}>
                      <td className="mono">{f.stage}</td>
                      <td className="mono workshop-finding-code">{f.code}</td>
                      <td>{f.message}</td>
                      <td className="mono">{f.path ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
        <div className="row-actions" style={{ marginTop: "var(--space-3)" }}>
          <button type="button" className="button button--secondary" onClick={revalidate} disabled={busy}>
            {busy ? "Revalidating…" : "Revalidate"}
          </button>
        </div>
      </div>
    </section>
  );
}
