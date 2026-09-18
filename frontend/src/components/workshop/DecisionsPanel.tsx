import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { RuleOrigin, Workshop, WorkshopDecision, WorkshopQuestion } from "../../api/types";

const ORIGIN_LABEL: Record<RuleOrigin, string> = {
  SOURCE_RULE: "Source rule",
  USER_CLARIFICATION: "User clarification",
  WORKSHOP_PROPOSAL: "Workshop proposal",
};

/** Auditable decision timeline (PID-004B directive). `origin` is visually
 * distinct per value — SOURCE_RULE / USER_CLARIFICATION / WORKSHOP_PROPOSAL
 * each get their own badge colour, deliberately (this distinction matters
 * for the future MENDEL slice). The UI never relabels an origin after
 * acceptance — accept/reject/supersede only ever change acceptance_state,
 * never origin. */
export function DecisionsPanel({
  workshopId,
  workshop,
  decisions,
  questions,
  onChanged,
}: {
  workshopId: string;
  workshop: Workshop;
  decisions: WorkshopDecision[];
  questions: WorkshopQuestion[];
  onChanged: () => Promise<void>;
}) {
  const [proposedValue, setProposedValue] = useState("");
  const [origin, setOrigin] = useState<RuleOrigin>("USER_CLARIFICATION");
  const [relatedQuestionId, setRelatedQuestionId] = useState("");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editable = workshop.status === "ACTIVE";

  async function createDecision() {
    let parsed: unknown;
    try {
      parsed = JSON.parse(proposedValue);
    } catch {
      parsed = { note: proposedValue };
    }
    setBusy(true);
    setError(null);
    try {
      await api.createWorkshopDecision(workshopId, {
        proposed_value: parsed,
        origin,
        actor: "matt",
        related_question_id: relatedQuestionId || null,
        rationale: rationale.trim() || undefined,
      });
      setProposedValue("");
      setRationale("");
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the decision.");
    } finally {
      setBusy(false);
    }
  }

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That action was not accepted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Decisions</h2>
      <div style={{ padding: "var(--space-4)" }}>
        {decisions.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>No decisions recorded yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Origin</th>
                <th scope="col">Proposed value</th>
                <th scope="col">Actor</th>
                <th scope="col">State</th>
                <th scope="col">Rationale</th>
                <th scope="col">Affected paths</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {decisions.map((d) => (
                <tr key={d.decision_id} className={d.acceptance_state === "SUPERSEDED" ? "workshop-row--superseded" : undefined}>
                  <td>
                    <span className={`workshop-badge workshop-badge--origin-${d.origin.toLowerCase().replace(/_/g, "-")}`}>
                      {ORIGIN_LABEL[d.origin]}
                    </span>
                  </td>
                  <td className="mono workshop-proposed-value">{JSON.stringify(d.proposed_value)}</td>
                  <td>{d.actor}</td>
                  <td>
                    <span className={`workshop-badge workshop-badge--decision-${d.acceptance_state.toLowerCase()}`}>
                      {d.acceptance_state}
                    </span>
                    {d.superseded_by_decision_id && (
                      <div style={{ fontSize: 11, color: "var(--ink-faint)" }}>
                        superseded by <span className="mono">{d.superseded_by_decision_id}</span>
                      </div>
                    )}
                  </td>
                  <td>{d.rationale ?? <span style={{ color: "var(--ink-faint)" }}>—</span>}</td>
                  <td className="mono">{d.affected_semantic_paths.join(", ") || "—"}</td>
                  <td>
                    {editable && d.acceptance_state === "PROPOSED" && (
                      <div className="row-actions">
                        <button
                          type="button"
                          className="button button--secondary"
                          disabled={busy}
                          onClick={() => act(() => api.acceptWorkshopDecision(workshopId, d.decision_id))}
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          className="button button--secondary"
                          disabled={busy}
                          onClick={() => act(() => api.rejectWorkshopDecision(workshopId, d.decision_id))}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {editable && (
          <div className="workshop-decision-form">
            <h3 className="workshop-subheading">Propose a decision</h3>
            <div className="form-row">
              <label className="form-field">
                Origin
                <select value={origin} onChange={(e) => setOrigin(e.target.value as RuleOrigin)}>
                  <option value="USER_CLARIFICATION">User clarification</option>
                  <option value="SOURCE_RULE">Source rule</option>
                  <option value="WORKSHOP_PROPOSAL">Workshop proposal</option>
                </select>
              </label>
              <label className="form-field">
                Related question (optional)
                <select value={relatedQuestionId} onChange={(e) => setRelatedQuestionId(e.target.value)}>
                  <option value="">— none —</option>
                  {questions.map((q) => (
                    <option key={q.question_id} value={q.question_id}>
                      {q.semantic_subject}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="form-field">
              Proposed value (plain text, or JSON for structured values)
              <textarea rows={2} value={proposedValue} onChange={(e) => setProposedValue(e.target.value)} />
            </label>
            <label className="form-field">
              Rationale (optional)
              <input value={rationale} onChange={(e) => setRationale(e.target.value)} />
            </label>
            <div className="row-actions">
              <button type="button" className="button" onClick={createDecision} disabled={busy}>
                Propose decision
              </button>
            </div>
          </div>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </section>
  );
}
