import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../../api/client";
import type {
  DraftCapabilityView,
  InvocationPurpose,
  MendelProposal,
  MendelRun,
  ProposalCategory,
  SpecificationDraftDoc,
  Workshop,
} from "../../api/types";

// PID-004C MENDEL Workshop Assistant panel. Deliberately NOT a chat UI —
// there is no free-form prompt box anywhere here, only a picker over the
// closed InvocationPurpose vocabulary plus a bounded, optional focus-text
// field, mirroring exactly what POST .../mendel/invoke accepts (PID-004C
// sec11.1.1/sec12). Every field shown is real state read from
// darwin.workshop.api's real MENDEL routes — nothing here is invented or
// survives only in this component's memory (same PID-004B discipline the
// rest of the Workshop page already follows).

const PURPOSE_OPTIONS: { value: InvocationPurpose; label: string }[] = [
  { value: "REVIEW_DRAFT", label: "Review draft" },
  { value: "ANALYSE_AMBIGUITY", label: "Analyse ambiguity" },
  { value: "SUGGEST_NEXT_QUESTIONS", label: "Suggest next questions" },
  { value: "EXPLAIN_VALIDATION", label: "Explain validation" },
  { value: "PROPOSE_DATA_REQUIREMENTS", label: "Propose data requirements" },
  { value: "INTERPRET_RULE", label: "Interpret rule" },
];

const CATEGORY_LABEL: Record<ProposalCategory, string> = {
  QUESTION: "QUESTION",
  ADVISORY: "ADVISORY",
  DRAFT_MUTATING: "DRAFT-MUTATING",
};

function currentBinding(revision: number | null): number | "NO_DRAFT_YET" {
  return revision === null ? "NO_DRAFT_YET" : revision;
}

/** Mirrors darwin.workshop.mendel_domain.is_stale_binding exactly, purely
 * as a client-side DISPLAY hint — clicking Accept always re-checks for
 * real on the server (darwin.workshop.mendel_service.accept_proposal is
 * the only authority that can actually mark a proposal STALE). This just
 * means the UI never silently offers a clickable Accept on a proposal
 * that the server would refuse. */
function isLocallyStale(proposal: MendelProposal, revision: number | null): boolean {
  if (proposal.status !== "PROPOSED") return false;
  return proposal.generated_against_draft_revision !== currentBinding(revision);
}

function effectiveStatus(proposal: MendelProposal, revision: number | null): string {
  if (proposal.status === "PROPOSED" && isLocallyStale(proposal, revision)) return "STALE";
  return proposal.status;
}

function payloadString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  if (value === null || value === undefined) return null;
  return typeof value === "string" ? value : JSON.stringify(value);
}

/** Best-effort "proposed value" rendering, per proposal class — never a
 * generic path/value patch (PID-004C sec6.6): each branch below reads
 * only the exact field(s) that class's own closed payload shape defines
 * (darwin.workshop.mendel_service's own per-class handlers), purely for
 * DISPLAY. This function never constructs anything DARWIN applies. */
function describeProposedValue(proposal: MendelProposal): string {
  const p = proposal.payload;
  switch (proposal.proposal_class) {
    case "ASK_QUESTION":
      return payloadString(p, "question_text") ?? "(question)";
    case "MATERIAL_CONCERN":
      return payloadString(p, "concern") ?? "(concern)";
    case "PARAMETER_CHANGE": {
      const unit = payloadString(p, "unit");
      return `${payloadString(p, "parameter_id")} = ${payloadString(p, "fixed_value")}${unit ? ` ${unit}` : ""} (${payloadString(p, "value_type")})`;
    }
    case "DATA_REQUIREMENT":
      return `New requirement: ${payloadString(p, "display_name") ?? payloadString(p, "requirement_id")}`;
    case "THESIS_CHANGE":
      return payloadString(p, "new_thesis") ?? "(new thesis)";
    case "INSTRUMENT_CLARIFICATION":
      return `${payloadString(p, "kind")} — ${JSON.stringify(p.instrument_ids ?? p.generic_criteria ?? [])}`;
    case "TIMEFRAME_CLARIFICATION":
      return `Session ${payloadString(p, "iana_timezone")} ${payloadString(p, "local_start")}–${payloadString(p, "local_end")}`;
    case "POLICY_CLASSIFICATION":
      return `${payloadString(p, "policy_class")}: ${payloadString(p, "compatibility")}`;
    case "SEMANTIC_CHANGE":
      return "(replacement composition subtree — see Specification panel after acceptance)";
    default:
      return JSON.stringify(p);
  }
}

/** Best-effort "current value" rendering — read-only lookups against the
 * live draft already loaded by the Workshop page, never a second source
 * of truth. Returns null where there genuinely is no comparable "current"
 * concept (a question/concern, or an additive new requirement). */
function describeCurrentValue(proposal: MendelProposal, draft: SpecificationDraftDoc | null): string | null {
  if (!draft) return null;
  const p = proposal.payload;
  switch (proposal.proposal_class) {
    case "PARAMETER_CHANGE": {
      const parameterId = payloadString(p, "parameter_id");
      if (!parameterId) return null;
      const fixed = (draft.fixed_parameters as Record<string, { fixed_value?: unknown }> | undefined)?.[parameterId];
      return fixed ? `${parameterId} = ${JSON.stringify(fixed.fixed_value)}` : "(not currently set)";
    }
    case "THESIS_CHANGE":
      return draft.thesis ?? "(no thesis set)";
    default:
      return null;
  }
}

export function MendelPanel({
  workshopId,
  workshop,
  draft,
  revision,
  onDraftMutated,
}: {
  workshopId: string;
  workshop: Workshop;
  draft: SpecificationDraftDoc | null;
  revision: number | null;
  onDraftMutated: () => Promise<void>;
}) {
  const [runs, setRuns] = useState<MendelRun[]>([]);
  const [proposals, setProposals] = useState<MendelProposal[]>([]);
  const [capability, setCapability] = useState<DraftCapabilityView | null>(null);
  const [lastInvokedRun, setLastInvokedRun] = useState<MendelRun | null>(null);
  const [purpose, setPurpose] = useState<InvocationPurpose>("REVIEW_DRAFT");
  const [focusText, setFocusText] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyProposalId, setBusyProposalId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const editable = workshop.status === "ACTIVE";

  const load = useCallback(async () => {
    const [runsRes, proposalsRes, capabilityRes] = await Promise.all([
      api.listMendelRuns(workshopId),
      api.listMendelProposals(workshopId),
      api.getMendelCapability(workshopId),
    ]);
    setRuns(runsRes.items);
    setProposals(proposalsRes.items);
    setCapability(capabilityRes.capability);
  }, [workshopId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function invoke() {
    setBusy(true);
    setError(null);
    try {
      const { run } = await api.invokeMendel(workshopId, {
        purpose,
        focus_text: focusText.trim() || null,
      });
      setLastInvokedRun(run);
      setFocusText("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "MENDEL invocation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function accept(proposal: MendelProposal) {
    setBusyProposalId(proposal.proposal_id);
    setError(null);
    try {
      await api.acceptMendelProposal(workshopId, proposal.proposal_id, { actor: "matt" });
      await load();
      if (proposal.proposal_category === "DRAFT_MUTATING") {
        await onDraftMutated();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept the proposal.");
      await load();
    } finally {
      setBusyProposalId(null);
    }
  }

  async function reject(proposal: MendelProposal) {
    setBusyProposalId(proposal.proposal_id);
    setError(null);
    try {
      await api.rejectMendelProposal(workshopId, proposal.proposal_id, {});
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reject the proposal.");
    } finally {
      setBusyProposalId(null);
    }
  }

  const sortedProposals = [...proposals].sort((a, b) =>
    (b.created_at_utc ?? "").localeCompare(a.created_at_utc ?? ""),
  );
  const sortedRuns = [...runs].sort((a, b) => (b.started_at_utc ?? "").localeCompare(a.started_at_utc ?? ""));

  return (
    <section className="panel mendel-panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">
        MENDEL Assistant <span className="workshop-count-badge">{proposals.length} proposals</span>
      </h2>
      <div style={{ padding: "var(--space-4)" }}>
        <p style={{ color: "var(--ink-dim)", fontSize: 12.5, marginTop: 0 }}>
          A bounded strategy-engineering specialist — not a chat assistant. MENDEL sees a fixed, assembled
          context and answers exactly one closed, chosen task at a time; there is no free-form prompt.
        </p>

        {editable && (
          <div className="mendel-invoke-form">
            <div className="form-row">
              <label className="form-field">
                Invocation purpose
                <select value={purpose} onChange={(e) => setPurpose(e.target.value as InvocationPurpose)}>
                  {PURPOSE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="form-field">
              Focus text (optional — narrows the task, never expands MENDEL's authority)
              <input
                value={focusText}
                onChange={(e) => setFocusText(e.target.value)}
                placeholder="e.g. which validation finding, which rule"
              />
            </label>
            <div className="row-actions">
              <button type="button" className="button" onClick={invoke} disabled={busy}>
                {busy ? "Invoking MENDEL…" : "Invoke MENDEL"}
              </button>
            </div>
          </div>
        )}

        {lastInvokedRun && (
          <div className="mendel-reasoning-summary">
            <h3 className="workshop-subheading">Last invocation — {lastInvokedRun.purpose}</h3>
            <p>
              <span className={`workshop-badge workshop-badge--mendel-run-${lastInvokedRun.status.toLowerCase()}`}>
                {lastInvokedRun.status}
              </span>
            </p>
            {lastInvokedRun.reasoning_summary && <p className="mendel-reasoning-summary__text">{lastInvokedRun.reasoning_summary}</p>}
            {lastInvokedRun.error_classification && (
              <p className="form-error">{lastInvokedRun.error_classification}</p>
            )}
          </div>
        )}

        <h3 className="workshop-subheading">Data capability (current draft)</h3>
        {!capability || capability.per_requirement.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>
            No data requirements are declared on the current draft yet.
          </p>
        ) : (
          <table className="data-table" style={{ marginBottom: "var(--space-3)" }}>
            <thead>
              <tr>
                <th scope="col">Requirement</th>
                <th scope="col">Availability</th>
                <th scope="col">Reason</th>
              </tr>
            </thead>
            <tbody>
              {capability.per_requirement.map((r) => (
                <tr key={r.requirement_id}>
                  <td className="mono">{r.requirement_id}</td>
                  <td>
                    <span
                      className={`workshop-badge workshop-badge--availability-${r.availability.toLowerCase().replace(/_/g, "-")}`}
                    >
                      {r.availability}
                    </span>
                  </td>
                  <td>{r.reason ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <h3 className="workshop-subheading">Proposals</h3>
        {sortedProposals.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>
            No proposals yet — invoke MENDEL above to generate some.
          </p>
        ) : (
          <ul className="mendel-proposal-list">
            {sortedProposals.map((proposal) => {
              const status = effectiveStatus(proposal, revision);
              const stale = status === "STALE";
              const proposedValue = describeProposedValue(proposal);
              const currentValue = describeCurrentValue(proposal, draft);
              const canAccept = editable && proposal.status === "PROPOSED" && !stale;
              const canReject = editable && proposal.status === "PROPOSED";
              const busyHere = busyProposalId === proposal.proposal_id;

              return (
                <li
                  key={proposal.proposal_id}
                  className={`mendel-proposal-card mendel-proposal-card--category-${proposal.proposal_category.toLowerCase()}`}
                >
                  <div className="mendel-proposal-card__head">
                    <span
                      className={`workshop-badge workshop-badge--mendel-category-${proposal.proposal_category.toLowerCase()}`}
                    >
                      {CATEGORY_LABEL[proposal.proposal_category]}
                    </span>
                    <span className="mono">{proposal.proposal_class}</span>
                    <span className={`workshop-badge workshop-badge--mendel-status-${status.toLowerCase()}`}>
                      {status}
                    </span>
                  </div>

                  {/* PID-004C sec13.1's critical UX distinction: category
                      A/B acceptance NEVER mutates the draft or its
                      revision; category C acceptance ALWAYS creates a new
                      draft revision. Distinguishable panel treatment
                      (border colour + explicit banner text), never just
                      the status chip above. */}
                  <div className="mendel-mutation-banner">
                    {proposal.proposal_category === "DRAFT_MUTATING"
                      ? `Accepting this WILL create a new draft revision (current revision: ${
                          revision ?? "none yet"
                        }).`
                      : "Accepting this will NOT change the strategy draft or its revision."}
                  </div>

                  {proposal.proposal_class === "THESIS_CHANGE" && (
                    <p className="mendel-hypothesis-warning">
                      ⚠ This materially changes the strategy hypothesis — review carefully before accepting.
                    </p>
                  )}

                  <dl className="kv-list" style={{ padding: 0 }}>
                    {currentValue !== null && (
                      <div className="kv-row">
                        <dt>Current value</dt>
                        <dd>{currentValue}</dd>
                      </div>
                    )}
                    <div className="kv-row">
                      <dt>Proposed value</dt>
                      <dd>{proposedValue}</dd>
                    </div>
                    <div className="kv-row">
                      <dt>Rationale</dt>
                      <dd>{proposal.rationale}</dd>
                    </div>
                    <div className="kv-row">
                      <dt>Affected semantic paths</dt>
                      <dd className="mono">
                        {proposal.affected_semantic_paths.length > 0
                          ? proposal.affected_semantic_paths.join(", ")
                          : "—"}
                      </dd>
                    </div>
                    <div className="kv-row">
                      <dt>Generated against draft revision</dt>
                      <dd className="mono">{String(proposal.generated_against_draft_revision)}</dd>
                    </div>
                    {proposal.resulting_question_id && (
                      <div className="kv-row">
                        <dt>Resulting question</dt>
                        <dd className="mono">{proposal.resulting_question_id}</dd>
                      </div>
                    )}
                    {proposal.resulting_decision_id && (
                      <div className="kv-row">
                        <dt>Resulting decision</dt>
                        <dd className="mono">{proposal.resulting_decision_id}</dd>
                      </div>
                    )}
                  </dl>

                  {stale && (
                    <p className="form-error" role="alert">
                      This proposal was generated against a draft revision that is no longer current — the
                      draft has changed since. Accepting is refused; MENDEL would need to be re-invoked
                      against the current revision.
                    </p>
                  )}

                  {editable && proposal.status === "PROPOSED" && (
                    <div className="row-actions">
                      <button
                        type="button"
                        className="button"
                        disabled={!canAccept || busyHere}
                        title={stale ? "Refused — this proposal is stale against the current draft revision" : undefined}
                        onClick={() => accept(proposal)}
                      >
                        {busyHere ? "Working…" : "Accept"}
                      </button>
                      <button
                        type="button"
                        className="button button--secondary"
                        disabled={!canReject || busyHere}
                        onClick={() => reject(proposal)}
                      >
                        {busyHere ? "Working…" : "Reject"}
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        <h3 className="workshop-subheading">Invocation history</h3>
        {sortedRuns.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>No MENDEL invocations yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Purpose</th>
                <th scope="col">Status</th>
                <th scope="col">Started</th>
                <th scope="col">Completed</th>
                <th scope="col">Error</th>
              </tr>
            </thead>
            <tbody>
              {sortedRuns.map((r) => (
                <tr key={r.run_id}>
                  <td>{r.purpose}</td>
                  <td>
                    <span className={`workshop-badge workshop-badge--mendel-run-${r.status.toLowerCase()}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="mono">{r.started_at_utc ?? "—"}</td>
                  <td className="mono">{r.completed_at_utc ?? "—"}</td>
                  <td>{r.error_classification ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
