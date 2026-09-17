import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";

const STAGE_ORDER = ["DISCOVERED", "SPECIFIED", "ATHENA_TESTED", "ATHENA_QUALIFIED", "APOLLO_PROVEN", "PROMISING"];

export function Pipeline() {
  const pipeline = useApi(api.pipelineSummary, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Pipeline</h1>
      </div>

      {pipeline.status === "error" && (
        <ErrorState error={pipeline.error} dependency="pipeline summary" onRetry={pipeline.reload} />
      )}

      {pipeline.status === "ready" && (
        <>
          <p style={{ color: "var(--ink-dim)", marginBottom: "var(--space-5)", maxWidth: 640 }}>
            Strategy candidates move through this lifecycle as evidence accumulates.{" "}
            <strong style={{ color: "var(--ink)" }}>PROMISING does not mean approved for live capital</strong> — it
            means DARWIN's own evidence justifies later governed promotion consideration.
          </p>
          <div className="stage-flow" style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap" }}>
            {STAGE_ORDER.map((stage, i) => (
              <div key={stage} className="stat-card" style={{ flex: "1 1 140px" }}>
                <div className="stat-card__value">{pipeline.data.counts_by_stage[stage] ?? 0}</div>
                <div className="stat-card__label">
                  {i + 1}. {stage.replace(/_/g, " ")}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
