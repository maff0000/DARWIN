import { useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import type {
  ReadinessResult,
  SpecificationDraftDoc,
  StrategyVersionSummary,
  ValidationOutcome,
  Workshop,
  WorkshopDecision,
  WorkshopQuestion,
} from "../../api/types";
import { IdValue } from "../IdValue";

/** A deliberate, explicit action — never auto-triggered (PID-004B
 * directive). Gating: STRATEGY_NOT_SUFFICIENTLY_DEFINED disables the
 * button for clarity, but the backend call remains the sole authority
 * (there is no frontend-only override — a disabled button here never
 * substitutes for the real POST .../finalise refusal). VALID + DATA_BLOCKED
 * is legitimate and finalisable; readiness never gates this button. */
export function FinalisationPanel({
  workshopId,
  workshop,
  draft,
  revision,
  validation,
  readiness,
  questions,
  decisions,
  onFinalised,
}: {
  workshopId: string;
  workshop: Workshop;
  draft: SpecificationDraftDoc | null;
  revision: number | null;
  validation: ValidationOutcome | null;
  readiness: ReadinessResult | null;
  questions: WorkshopQuestion[];
  decisions: WorkshopDecision[];
  onFinalised: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [strategyVersion, setStrategyVersion] = useState<StrategyVersionSummary | null>(null);

  const unresolvedCount = questions.filter((q) => q.status === "OPEN").length;
  const acceptedDecisions = decisions.filter((d) => d.acceptance_state === "ACCEPTED");
  const missingRequirements = draft ? Object.values(draft.data_requirements).filter((r) => r.mandatory) : [];
  const canFinalise = validation !== null && validation.is_valid && revision !== null && workshop.status !== "ABANDONED";

  useEffect(() => {
    if (workshop.finalised_strategy_version_id) {
      api
        .getStrategyVersion(workshop.finalised_strategy_version_id)
        .then(setStrategyVersion)
        .catch(() => setStrategyVersion(null));
    } else {
      setStrategyVersion(null);
    }
  }, [workshop.finalised_strategy_version_id]);

  async function finalise() {
    if (revision === null) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.finaliseWorkshop(workshopId, { expected_revision: revision });
      if (result.strategy_version_id === null) {
        setError(
          "Finalisation refused: " +
            result.validation.findings.map((f) => `${f.code} (${f.message})`).join("; "),
        );
      }
      await onFinalised();
    } catch (err) {
      setError(err instanceof ApiError ? `${err.code ?? "ERROR"}: ${err.message}` : "Finalisation failed.");
    } finally {
      setBusy(false);
    }
  }

  if (workshop.status === "FINALISED") {
    return (
      <section className="panel workshop-finalised-panel" style={{ marginBottom: "var(--space-5)" }}>
        <h2 className="panel-heading">Finalised</h2>
        <div style={{ padding: "var(--space-4)" }}>
          <p className="workshop-finalised-statement">
            Specified — not yet research-tested. This StrategyVersion has not been submitted to ATHENA or APOLLO
            and carries no PROMISING status.
          </p>
          <dl className="kv-list">
            <div className="kv-row">
              <dt>StrategyVersion ID</dt>
              <dd>
                <IdValue value={workshop.finalised_strategy_version_id!} abbreviate={false} />
              </dd>
            </div>
            <div className="kv-row">
              <dt>Semantic fingerprint</dt>
              <dd>{strategyVersion ? <IdValue value={strategyVersion.semantic_fingerprint} /> : "loading…"}</dd>
            </div>
            <div className="kv-row">
              <dt>Artifact record fingerprint</dt>
              <dd>{strategyVersion ? <IdValue value={strategyVersion.artifact_record_fingerprint} /> : "loading…"}</dd>
            </div>
            <div className="kv-row">
              <dt>Readiness</dt>
              <dd>
                <span className={`workshop-badge workshop-badge--readiness-${(readiness?.state ?? "unassessed").toLowerCase()}`}>
                  {readiness?.state ?? "UNASSESSED"}
                </span>
              </dd>
            </div>
          </dl>
          <p style={{ fontSize: 12, color: "var(--ink-faint)" }}>
            The draft and authoring controls above are now read-only — this Workshop is FINALISED and its
            StrategyVersion is immutable.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel workshop-finalisation-panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Finalisation</h2>
      <div style={{ padding: "var(--space-4)" }}>
        <dl className="kv-list">
          <div className="kv-row">
            <dt>Unresolved questions</dt>
            <dd>{unresolvedCount}</dd>
          </div>
          <div className="kv-row">
            <dt>Validation status</dt>
            <dd>
              <span className={`workshop-badge workshop-badge--validation-${(validation?.status ?? "unknown").toLowerCase()}`}>
                {validation?.status ?? "NOT YET VALIDATED"}
              </span>
            </dd>
          </div>
          <div className="kv-row">
            <dt>Current draft revision</dt>
            <dd>{revision ?? "—"}</dd>
          </div>
          <div className="kv-row">
            <dt>Readiness state</dt>
            <dd>
              <span className={`workshop-badge workshop-badge--readiness-${(readiness?.state ?? "unassessed").toLowerCase()}`}>
                {readiness?.state ?? "UNASSESSED"}
              </span>
            </dd>
          </div>
          <div className="kv-row">
            <dt>Missing mandatory data requirements</dt>
            <dd>
              {missingRequirements.length === 0
                ? "none declared"
                : missingRequirements.map((r) => r.display_name).join(", ")}
            </dd>
          </div>
          <div className="kv-row">
            <dt>Accepted decisions</dt>
            <dd>{acceptedDecisions.length}</dd>
          </div>
        </dl>
        <p className="workshop-finalise-consequence">Finalising creates an immutable StrategyVersion.</p>
        <div className="row-actions">
          <button
            type="button"
            className="button"
            onClick={finalise}
            disabled={!canFinalise || busy}
            title={!canFinalise ? "STRATEGY_NOT_SUFFICIENTLY_DEFINED — resolve the validation findings above first" : undefined}
          >
            {busy ? "Finalising…" : "Finalise Workshop"}
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
