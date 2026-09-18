import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { ReadinessResult, Workshop } from "../../api/types";

/** Visually distinct UNASSESSED / DATA_BLOCKED / TESTABLE (PID-004B
 * directive), separate from Validation. `DataReadinessAssessment` is
 * defined only against a finalised StrategyVersion (PID-004 sec26) — an
 * ACTIVE Workshop's readiness is honestly UNASSESSED, never fabricated.
 * "Assess readiness" is a deliberate, explicit action (genuine backend
 * gap this UI closed — see darwin.workshop.service's own comment); it is
 * never run automatically and never blocks finalisation either way. */
export function ReadinessPanel({
  workshopId,
  workshop,
  readiness,
  onAssessed,
}: {
  workshopId: string;
  workshop: Workshop;
  readiness: ReadinessResult | null;
  onAssessed: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function assess() {
    setBusy(true);
    setError(null);
    try {
      await api.assessWorkshopReadiness(workshopId);
      await onAssessed();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not assess readiness.");
    } finally {
      setBusy(false);
    }
  }

  const state = readiness?.state ?? "UNASSESSED";

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Readiness</h2>
      <div style={{ padding: "var(--space-4)" }}>
        <p>
          <span className={`workshop-badge workshop-badge--readiness-${state.toLowerCase()}`}>{state}</span>{" "}
          <span style={{ color: "var(--ink-dim)", fontSize: 12.5 }}>
            {state === "UNASSESSED" &&
              "No readiness assessment exists yet — this is honest, not an error: readiness can only be " +
                "assessed against a finalised StrategyVersion."}
            {state === "DATA_BLOCKED" &&
              "VALID + DATA_BLOCKED is a legitimate, finalisable state — a mandatory data requirement is " +
                "currently unmet. This never disables finalisation on its own."}
            {state === "TESTABLE" && "Every mandatory data requirement is currently available."}
          </span>
        </p>
        {readiness && readiness.requirements.length > 0 && (
          <table className="data-table" style={{ marginTop: "var(--space-3)" }}>
            <thead>
              <tr>
                <th scope="col">Requirement</th>
                <th scope="col">Availability</th>
                <th scope="col">Reason</th>
              </tr>
            </thead>
            <tbody>
              {readiness.requirements.map((r) => (
                <tr key={r.requirement_id}>
                  <td className="mono">{r.requirement_id}</td>
                  <td>
                    <span className={`workshop-badge workshop-badge--availability-${r.availability.toLowerCase().replace(/_/g, "-")}`}>
                      {r.availability}
                    </span>
                  </td>
                  <td>{r.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {readiness?.assessed_at_utc && (
          <p style={{ fontSize: 11.5, color: "var(--ink-faint)", marginTop: "var(--space-2)" }}>
            Last assessed {readiness.assessed_at_utc}
          </p>
        )}
        <div className="row-actions" style={{ marginTop: "var(--space-3)" }}>
          <button
            type="button"
            className="button button--secondary"
            onClick={assess}
            disabled={busy || workshop.finalised_strategy_version_id === null}
            title={
              workshop.finalised_strategy_version_id === null
                ? "Readiness can only be assessed once this Workshop has a finalised StrategyVersion"
                : undefined
            }
          >
            {busy ? "Assessing…" : "Assess readiness now"}
          </button>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </section>
  );
}
