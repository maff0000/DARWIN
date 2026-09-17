import type { BuildInfo, ReadinessReport } from "../api/types";
import { IdValue } from "./IdValue";

interface TopBarProps {
  build?: BuildInfo;
  readiness?: ReadinessReport;
  loadFailed: boolean;
}

/** Global/utility only — never primary navigation (PID-002 §6). */
export function TopBar({ build, readiness, loadFailed }: TopBarProps) {
  const overall = loadFailed ? "DOWN" : readiness ? (readiness.ready ? "OK" : "DEGRADED") : "OK";

  return (
    <header className="top-bar">
      <div className="top-bar__brand">
        <span className="top-bar__mark" aria-hidden="true">
          ◆
        </span>
        <span>DARWIN</span>
        <span className="top-bar__product">ARENA</span>
      </div>

      <div className="top-bar__health" role="status" aria-label="System health">
        <span className={`health-dot health-dot--${overall.toLowerCase()}`} aria-hidden="true" />
        <span>{overall === "OK" ? "Healthy" : overall === "DEGRADED" ? "Degraded" : "Unreachable"}</span>
      </div>

      <div className="top-bar__spacer" />

      <div className="top-bar__meta">
        {build && (
          <span className="top-bar__env">{build.environment}</span>
        )}
        {build && (
          <span className="top-bar__build">
            v{build.application_version} · <IdValue value={build.commit} abbreviate head={7} tail={0} />
          </span>
        )}
      </div>

      <a
        className="top-bar__link"
        href="https://github.com/maff0000/DARWIN"
        target="_blank"
        rel="noreferrer"
      >
        Repository
      </a>

      <button type="button" className="top-bar__account" title="Account/profile — not configured">
        <span aria-hidden="true">◌</span>
        <span>Account</span>
        <span className="top-bar__account-status">Not configured</span>
      </button>
    </header>
  );
}
