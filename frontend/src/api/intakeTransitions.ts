import type { IntakeStatus } from "./types";

// Mirrors darwin/scout/domain.py ALLOWED_INTAKE_TRANSITIONS exactly — ARENA
// never offers a control for a transition the backend would reject, but
// the backend is still the sole authority (this list is display/UX
// convenience only, never trusted as validation on its own).
export const ALLOWED_INTAKE_TRANSITIONS: Record<IntakeStatus, IntakeStatus[]> = {
  NEW: ["SHORTLISTED", "REJECTED"],
  SHORTLISTED: ["IN_WORKSHOP", "REJECTED", "NEW"],
  IN_WORKSHOP: ["READY_FOR_SPECIFICATION", "REJECTED", "SHORTLISTED"],
  READY_FOR_SPECIFICATION: ["REJECTED", "IN_WORKSHOP"],
  REJECTED: ["NEW"],
};

export const INTAKE_STATUS_LABEL: Record<IntakeStatus, string> = {
  NEW: "New",
  SHORTLISTED: "Shortlisted",
  IN_WORKSHOP: "In workshop",
  READY_FOR_SPECIFICATION: "Ready for specification",
  REJECTED: "Rejected",
};

export const INTAKE_STATUS_ORDER: IntakeStatus[] = [
  "NEW",
  "SHORTLISTED",
  "IN_WORKSHOP",
  "READY_FOR_SPECIFICATION",
  "REJECTED",
];
