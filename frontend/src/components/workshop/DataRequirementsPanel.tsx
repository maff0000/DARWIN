import type { SpecificationDraftDoc } from "../../api/types";

/** Real DataRequirement fields (PID-004B directive) — separate from the
 * Validation panel. An unavailable/mandatory requirement is never hidden
 * here; this panel only displays what draft.data_requirements actually
 * contains — governed authoring of these currently happens outside ARENA
 * (via the Workshop backend directly / a future MENDEL slice), so this
 * MVP surface is deliberately read-only display, not an add/edit form. */
export function DataRequirementsPanel({ draft }: { draft: SpecificationDraftDoc | null }) {
  const requirements = draft ? Object.values(draft.data_requirements) : [];

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Data Requirements</h2>
      <div style={{ padding: "var(--space-4)" }}>
        {requirements.length === 0 ? (
          <p style={{ color: "var(--ink-faint)", fontSize: 12.5 }}>No data requirements declared yet.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Display name</th>
                <th scope="col">Fact class</th>
                <th scope="col">Authority</th>
                <th scope="col">Timeframe</th>
                <th scope="col">Historical depth</th>
                <th scope="col">Fields</th>
                <th scope="col">Mandatory</th>
              </tr>
            </thead>
            <tbody>
              {requirements.map((r) => (
                <tr key={r.requirement_id}>
                  <td>{r.display_name}</td>
                  <td className="mono">{r.fact_class}</td>
                  <td className="mono">{r.authority_class}</td>
                  <td className="mono">{r.timeframe ?? "—"}</td>
                  <td className="mono">
                    {r.required_historical_depth.count} {r.required_historical_depth.unit}
                  </td>
                  <td className="mono">{r.required_fields.join(", ")}</td>
                  <td>
                    <span className={`workshop-badge workshop-badge--${r.mandatory ? "mandatory" : "optional"}`}>
                      {r.mandatory ? "MANDATORY" : "OPTIONAL"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
