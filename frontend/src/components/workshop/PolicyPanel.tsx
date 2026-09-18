import type { PolicyClass, SpecificationDraftDoc } from "../../api/types";

const POLICY_LABEL: Record<PolicyClass, string> = {
  EXECUTION_POLICY: "Execution policy",
  DIKE_POLICY: "DIKE policy",
  SIZING_POLICY: "Sizing policy",
  NEWS_CONTEXT_POLICY: "News-context policy",
};

/** The four PID-004A policy axes — informational display only for this
 * slice (PID-004B directive explicitly permits this: "informational
 * display is fine ... if fixtures don't need authoring controls"). */
export function PolicyPanel({ draft }: { draft: SpecificationDraftDoc | null }) {
  const declarations = draft?.policy_declarations ?? [];

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Policy Compatibility</h2>
      <div style={{ padding: "var(--space-4)" }}>
        {declarations.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>
            No policy compatibility declarations recorded on this draft yet.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Policy axis</th>
                <th scope="col">Compatibility</th>
                <th scope="col">Notes</th>
              </tr>
            </thead>
            <tbody>
              {declarations.map((d) => (
                <tr key={d.policy_class}>
                  <td>{POLICY_LABEL[d.policy_class]}</td>
                  <td>
                    <span className={`workshop-badge workshop-badge--policy-${d.compatibility.toLowerCase()}`}>
                      {d.compatibility}
                    </span>
                  </td>
                  <td>{d.notes ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
