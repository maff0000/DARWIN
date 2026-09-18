import { useEffect, useState } from "react";
import type { SpecificationDraftDoc, Workshop } from "../../api/types";

/** Human-readable mechanism/thesis — explanation only, never executable
 * semantics (PID-004B directive). Editable through the same governed
 * draft-save path (PUT .../draft under optimistic concurrency) every other
 * panel uses — there is no separate "notes" field anywhere in the backend
 * contract, so this panel edits `draft.title`/`draft.thesis` directly. */
export function HypothesisPanel({
  workshop,
  draft,
  revision,
  onSave,
  conflict,
  onReloadDraft,
}: {
  workshop: Workshop;
  draft: SpecificationDraftDoc | null;
  revision: number | null;
  onSave: (next: SpecificationDraftDoc) => Promise<boolean>;
  conflict: string | null;
  onReloadDraft: () => Promise<void>;
}) {
  const [title, setTitle] = useState(draft?.title ?? "");
  const [thesis, setThesis] = useState(draft?.thesis ?? "");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!dirty) {
      setTitle(draft?.title ?? "");
      setThesis(draft?.thesis ?? "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft?.title, draft?.thesis, revision]);

  const editable = workshop.status === "ACTIVE";

  async function save() {
    if (!draft) return;
    setSaving(true);
    const ok = await onSave({ ...draft, title, thesis });
    setSaving(false);
    if (ok) setDirty(false);
  }

  return (
    <section className="panel" style={{ marginBottom: "var(--space-5)" }}>
      <h2 className="panel-heading">Hypothesis</h2>
      <div style={{ padding: "var(--space-4)", display: "grid", gap: "var(--space-3)" }}>
        <p style={{ fontSize: 12.5, color: "var(--ink-dim)" }}>
          Human-readable mechanism/thesis — an explanation of WHY this strategy might work, never itself
          executable semantics. The Specification panel below is what governs actual evaluation.
        </p>
        <label className="form-field">
          Title
          <input
            value={title}
            disabled={!editable}
            onChange={(e) => {
              setTitle(e.target.value);
              setDirty(true);
            }}
          />
        </label>
        <label className="form-field">
          Thesis
          <textarea
            rows={3}
            value={thesis}
            disabled={!editable}
            onChange={(e) => {
              setThesis(e.target.value);
              setDirty(true);
            }}
          />
        </label>
        {editable && (
          <div className="row-actions">
            <button type="button" className="button" onClick={save} disabled={!dirty || saving || !draft}>
              {saving ? "Saving…" : "Save hypothesis"}
            </button>
          </div>
        )}
        {conflict && (
          <div className="form-error" role="alert">
            <p>{conflict}</p>
            <button type="button" className="button button--secondary" onClick={onReloadDraft}>
              Reload latest draft
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
