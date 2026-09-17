import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";

const STAGE_ORDER = ["DISCOVERED", "SPECIFIED", "ATHENA_TESTED", "ATHENA_QUALIFIED", "APOLLO_PROVEN", "PROMISING"];

// intake_status values that still count as "at the DISCOVERED stage" from
// this per-stage (not cumulative — StrategyCandidateRepository.counts_by_
// stage() counts exact current pipeline_stage, never a running total) view
// of the funnel: everything SCOUT has found that has neither dropped out
// (REJECTED) nor actually been promoted into a StrategyCandidate row (no
// PID-003 action produces one — that is PID-004's job). REJECTED is
// excluded the same way a StrategyCandidate that moved on to SPECIFIED
// would no longer count as DISCOVERED.
const DISCOVERED_INTAKE_STATUSES = ["NEW", "SHORTLISTED", "IN_WORKSHOP", "READY_FOR_SPECIFICATION"] as const;

export function Pipeline() {
  const pipeline = useApi(api.pipelineSummary, []);
  // SCOUT (PID-003) persists discoveries in its own scout_discoveries
  // table, entirely separate from strategy_candidates (PID-003 sec4: "no
  // FK from scout_* into strategy_candidates/source_strategies exists
  // anywhere") — so the backend's own DISCOVERED count is always 0 today
  // (nothing has ever promoted a discovery into a StrategyCandidate row).
  // This page now reads SCOUT's real persistence directly for the
  // DISCOVERED tile instead of showing that structurally-empty count.
  // limit=1 is enough: counts_by_intake_status is global, not scoped to
  // the page of items returned.
  const scout = useApi(() => api.scoutDiscoveries({ limit: 1 }), []);

  const scoutDiscoveredCount =
    scout.status === "ready"
      ? DISCOVERED_INTAKE_STATUSES.reduce((sum, s) => sum + (scout.data.counts_by_intake_status[s] ?? 0), 0)
      : null;

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
            {STAGE_ORDER.map((stage, i) => {
              const isDiscovered = stage === "DISCOVERED";
              const value = isDiscovered && scoutDiscoveredCount !== null ? scoutDiscoveredCount : pipeline.data.counts_by_stage[stage] ?? 0;
              return (
                <div key={stage} className="stat-card" style={{ flex: "1 1 140px" }}>
                  <div className="stat-card__value">{value}</div>
                  <div className="stat-card__label">
                    {i + 1}. {stage.replace(/_/g, " ")}
                  </div>
                </div>
              );
            })}
          </div>
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5, marginTop: "var(--space-3)", maxWidth: 640 }}>
            DISCOVERED reflects SCOUT's own persistence (NEW + SHORTLISTED + IN_WORKSHOP + READY_FOR_SPECIFICATION
            discoveries; REJECTED is excluded), not a StrategyCandidate row — no PID-003 action ever creates one of
            those. See Discovery for the full intake breakdown.
          </p>
        </>
      )}
    </div>
  );
}
