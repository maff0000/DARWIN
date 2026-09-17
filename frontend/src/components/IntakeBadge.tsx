import type { IntakeStatus } from "../api/types";

// Operational triage workflow only — never an evidence level, never a
// research result, never the canonical strategy lifecycle (PID-003 sec10
// Amendment: "not an evidence level, not a research result, not a
// canonical strategy lifecycle state"). Deliberately its own small badge
// language, distinct from EvidenceBadge, so the two are never confused.
const LABEL: Record<IntakeStatus, string> = {
  NEW: "New",
  SHORTLISTED: "Shortlisted",
  IN_WORKSHOP: "In workshop",
  READY_FOR_SPECIFICATION: "Ready for specification",
  REJECTED: "Rejected",
};

export function IntakeBadge({ status }: { status: IntakeStatus }) {
  return (
    <span className={`intake-badge intake-badge--${status.toLowerCase().replace(/_/g, "-")}`}>
      {LABEL[status] ?? status}
    </span>
  );
}
