import type { ResearchRun } from "../api/types";
import { IdValue } from "./IdValue";

/** Displays immutable DIKE identity only. Never implies Foundation is
 * evaluating a policy (PID-001 §1d, PID-002 §9) — this panel is a record,
 * not a control surface. */
export function DikePanel({ run }: { run: ResearchRun }) {
  const guarded = run.dike_state === "DIKE_GUARDED";
  return (
    <section className="dike-panel" aria-label="DIKE capital-protection identity">
      <h3 className="panel-heading">DIKE identity</h3>
      <div className={`dike-state dike-state--${guarded ? "guarded" : "disabled"}`}>
        {guarded ? "DIKE_GUARDED" : "DIKE_DISABLED"}
      </div>
      <p className="dike-note">
        {guarded
          ? "This run was bound to an immutable, versioned DIKE policy identity at creation time."
          : "This run carries no DIKE policy — the unguarded scientific baseline."}
      </p>
      {guarded && (
        <dl className="kv-list">
          <div className="kv-row">
            <dt>Policy ID</dt>
            <dd>
              <IdValue value={run.dike_policy_id ?? ""} />
            </dd>
          </div>
          <div className="kv-row">
            <dt>Policy version</dt>
            <dd>{run.dike_policy_version}</dd>
          </div>
          <div className="kv-row">
            <dt>Policy fingerprint</dt>
            <dd>
              <IdValue value={run.dike_policy_fingerprint ?? ""} mono abbreviate />
            </dd>
          </div>
        </dl>
      )}
      <p className="dike-disclaimer">
        ARENA displays DIKE identity only. DARWIN does not evaluate or enforce DIKE policy — enforcement authority
        belongs to TRON.
      </p>
    </section>
  );
}
