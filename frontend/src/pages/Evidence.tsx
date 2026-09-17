import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { EVIDENCE, EVIDENCE_LEVELS, EvidenceBadge } from "../components/EvidenceBadge";
import { ErrorState } from "../components/ErrorState";

/** A reference page, not a static glossary: counts are real, computed from
 * the actual persisted runs (there is no dedicated aggregate endpoint yet —
 * this page tallies client-side over the same /api/v1/runs response the
 * Runs list uses; noted as a known limitation for a later, larger sample). */
export function Evidence() {
  const runs = useApi(() => api.listRuns(200), []);
  const counts: Record<string, number> = {};
  if (runs.status === "ready") {
    for (const r of runs.data.items) counts[r.result_kind] = (counts[r.result_kind] ?? 0) + 1;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Evidence</h1>
      </div>
      <p style={{ color: "var(--ink-dim)", maxWidth: 640, marginBottom: "var(--space-5)" }}>
        Every result in DARWIN carries an explicit evidence class. These classes are never blended — a number's
        evidence class always answers "where did this come from?" without opening source code.
      </p>

      {runs.status === "error" && <ErrorState error={runs.error} dependency="research runs" onRetry={runs.reload} />}

      <section className="panel">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Class</th>
              <th scope="col">Meaning</th>
              <th scope="col">Runs recorded</th>
            </tr>
          </thead>
          <tbody>
            {EVIDENCE_LEVELS.map((level) => (
              <tr key={level}>
                <td><EvidenceBadge level={level} /></td>
                <td style={{ color: "var(--ink-dim)" }}>{EVIDENCE[level].explain}</td>
                <td className="mono">{runs.status === "ready" ? counts[level] ?? 0 : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
