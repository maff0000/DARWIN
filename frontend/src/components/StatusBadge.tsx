import type { ComponentStatus } from "../api/types";

const LABEL: Record<ComponentStatus, string> = {
  OK: "OK",
  DEGRADED: "Degraded",
  DOWN: "Down",
};

/** Status is conveyed by shape + label + color together — never color
 * alone (PID-002 §15 accessibility requirement). */
export function StatusBadge({ status }: { status: ComponentStatus }) {
  return (
    <span className={`status-badge status-badge--${status.toLowerCase()}`} role="status">
      <span className="status-badge__dot" aria-hidden="true" />
      {LABEL[status]}
    </span>
  );
}
