import type { Candidate, ReadinessResult, ValidationOutcome, Workshop } from "../../api/types";
import { IdValue } from "../IdValue";

const STATUS_LABEL: Record<Workshop["status"], string> = {
  ACTIVE: "Active",
  FINALISED: "Finalised",
  ABANDONED: "Abandoned",
};

/** PID-004B directive: operational status, draft revision, validation
 * state, readiness state, and (once finalised) the StrategyVersion ID must
 * each be visually distinct — never collapsed into one generic "status"
 * badge. Five separate chips below, each with its own class/colour. */
export function WorkshopHeader({
  workshop,
  candidate,
  revision,
  validation,
  readiness,
}: {
  workshop: Workshop;
  candidate: Candidate | null;
  revision: number | null;
  validation: ValidationOutcome | null;
  readiness: ReadinessResult | null;
}) {
  return (
    <div className="page-header workshop-header">
      <div>
        <h1>{candidate?.title ?? "Strategy Workshop"}</h1>
        <p className="workshop-header__subtitle">
          Workshop <IdValue value={workshop.workshop_id} /> · Candidate <IdValue value={workshop.candidate_id} />
        </p>
      </div>
      <div className="workshop-header__chips">
        <span className={`workshop-chip workshop-chip--status-${workshop.status.toLowerCase()}`}>
          {STATUS_LABEL[workshop.status]}
        </span>
        <span className="workshop-chip workshop-chip--revision">
          Draft revision {revision ?? "—"}
        </span>
        <span
          className={`workshop-chip workshop-chip--validation-${
            validation ? validation.status.toLowerCase() : "unknown"
          }`}
        >
          {validation ? (validation.is_valid ? "VALID" : "STRATEGY_NOT_SUFFICIENTLY_DEFINED") : "Not yet validated"}
        </span>
        <span className={`workshop-chip workshop-chip--readiness-${(readiness?.state ?? "unassessed").toLowerCase()}`}>
          Readiness: {readiness?.state ?? "UNASSESSED"}
        </span>
        {workshop.finalised_strategy_version_id && (
          <span className="workshop-chip workshop-chip--strategy-version">
            StrategyVersion <IdValue value={workshop.finalised_strategy_version_id} />
          </span>
        )}
      </div>
    </div>
  );
}
