import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { Workshop, WorkshopDecision, WorkshopQuestion } from "../../api/types";

/** Material questions raised against this Workshop (PID-004B directive) —
 * governed create + resolve actions via the real API. Resolved questions
 * are never hidden; they stay in the list with their resolution and any
 * linked accepted Decision visible. */
export function QuestionsPanel({
  workshopId,
  workshop,
  questions,
  decisions,
  onChanged,
}: {
  workshopId: string;
  workshop: Workshop;
  questions: WorkshopQuestion[];
  decisions: WorkshopDecision[];
  onChanged: () => Promise<void>;
}) {
  const [subject, setSubject] = useState("");
  const [text, setText] = useState("");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editable = workshop.status === "ACTIVE";
  const unresolvedCount = questions.filter((q) => q.status === "OPEN").length;

  async function createQuestion() {
    if (!subject.trim() || !text.trim()) {
      setError("Semantic subject and question text are both required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createWorkshopQuestion(workshopId, {
        semantic_subject: subject.trim(),
        question_text: text.trim(),
        rationale: rationale.trim() || undefined,
      });
      setSubject("");
      setText("");
      setRationale("");
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the question.");
    } finally {
      setBusy(false);
    }
  }

  async function resolve(questionId: string, resolution: "RESOLVED" | "WITHDRAWN", acceptedDecisionId?: string) {
    setBusy(true);
    setError(null);
    try {
      await api.resolveWorkshopQuestion(workshopId, questionId, {
        resolution,
        accepted_decision_id: acceptedDecisionId ?? null,
      });
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resolve the question.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">
        Questions <span className="workshop-count-badge">{unresolvedCount} unresolved</span>
      </h2>
      <div style={{ padding: "var(--space-4)" }}>
        {questions.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>No questions have been raised yet.</p>
        ) : (
          <ul className="workshop-question-list">
            {questions.map((q) => {
              const acceptedProposals = decisions.filter(
                (d) => d.related_question_id === q.question_id && d.acceptance_state === "ACCEPTED",
              );
              return (
                <li key={q.question_id} className={`workshop-question workshop-question--${q.status.toLowerCase()}`}>
                  <div className="workshop-question__head">
                    <span className={`workshop-badge workshop-badge--question-${q.status.toLowerCase()}`}>
                      {q.status}
                    </span>
                    <span className="mono workshop-semantic-subject">{q.semantic_subject}</span>
                  </div>
                  <p className="workshop-question__text">{q.question_text}</p>
                  {q.rationale && <p className="workshop-question__rationale">Rationale: {q.rationale}</p>}
                  {q.accepted_decision_id && (
                    <p className="workshop-question__linked">
                      Linked accepted decision: <span className="mono">{q.accepted_decision_id}</span>
                    </p>
                  )}
                  {editable && q.status === "OPEN" && (
                    <div className="row-actions">
                      {acceptedProposals.length > 0 && (
                        <button
                          type="button"
                          className="button button--secondary"
                          disabled={busy}
                          onClick={() => resolve(q.question_id, "RESOLVED", acceptedProposals[0].decision_id)}
                        >
                          Resolve with accepted decision
                        </button>
                      )}
                      <button
                        type="button"
                        className="button button--secondary"
                        disabled={busy}
                        onClick={() => resolve(q.question_id, "RESOLVED")}
                      >
                        Mark resolved
                      </button>
                      <button
                        type="button"
                        className="button button--secondary"
                        disabled={busy}
                        onClick={() => resolve(q.question_id, "WITHDRAWN")}
                      >
                        Withdraw
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {editable && (
          <div className="workshop-question-form">
            <h3 className="workshop-subheading">Raise a new question</h3>
            <div className="form-row">
              <label className="form-field">
                Semantic subject (e.g. a semantic path)
                <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="composition.trigger" />
              </label>
            </div>
            <label className="form-field">
              Question text
              <textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} />
            </label>
            <label className="form-field">
              Rationale (optional)
              <input value={rationale} onChange={(e) => setRationale(e.target.value)} />
            </label>
            <div className="row-actions">
              <button type="button" className="button" onClick={createQuestion} disabled={busy}>
                Raise question
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
