import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type {
  Candidate,
  ReadinessResult,
  ScoutDiscovery,
  SpecificationDraftDoc,
  ValidationOutcome,
  Workshop as WorkshopModel,
  WorkshopDecision,
  WorkshopQuestion,
} from "../api/types";
import { DecisionsPanel } from "../components/workshop/DecisionsPanel";
import { DataRequirementsPanel } from "../components/workshop/DataRequirementsPanel";
import { FinalisationPanel } from "../components/workshop/FinalisationPanel";
import { HypothesisPanel } from "../components/workshop/HypothesisPanel";
import { PolicyPanel } from "../components/workshop/PolicyPanel";
import { QuestionsPanel } from "../components/workshop/QuestionsPanel";
import { ReadinessPanel } from "../components/workshop/ReadinessPanel";
import { SourcePanel } from "../components/workshop/SourcePanel";
import { SpecificationPanel } from "../components/workshop/SpecificationPanel";
import { ValidationPanel } from "../components/workshop/ValidationPanel";
import { WorkshopHeader } from "../components/workshop/WorkshopHeader";
import { ErrorState } from "../components/ErrorState";
import { LoadingState } from "../components/LoadingState";

// darwin.specification.serialization.deserialize_specification_draft
// requires BOTH the wrapper envelope's `serialization_schema_version`
// (must be exactly "1") AND its `__type__` discriminator (must be exactly
// "SpecificationDraft") on every document it decodes — including the
// very first, otherwise-empty draft a brand-new Workshop materialises
// (PID-004A persistence directive item 15: "REJECT unknown ... schema
// versions explicitly" / this module's own closed __type__ dispatch,
// never a silent best-effort decode). Omitting either field here (as a
// bare `{}` would) is a genuine bug this UI build caught: the very first
// Workshop page load for any brand-new Workshop would fail outright.
const EMPTY_DRAFT_SEED: Partial<SpecificationDraftDoc> = {
  serialization_schema_version: "1",
  __type__: "SpecificationDraft",
};
const SCHEMA_SEMANTIC_VERSION = "1.0.0";

/** PID-004B Strategy Workshop page. Every field on screen is real state
 * read from `darwin.workshop.api`/`darwin.specification` — nothing here is
 * constructed client-side or survives only in this component's memory. A
 * browser reload, a navigate-away-and-back, or a DARWIN_core restart all
 * reconstruct this page from the same GETs (PID-004B directive). */
export function Workshop() {
  const { workshopId } = useParams<{ workshopId: string }>();

  const [workshop, setWorkshop] = useState<WorkshopModel | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [discoveries, setDiscoveries] = useState<ScoutDiscovery[]>([]);
  const [draft, setDraft] = useState<SpecificationDraftDoc | null>(null);
  const [revision, setRevision] = useState<number | null>(null);
  const [questions, setQuestions] = useState<WorkshopQuestion[]>([]);
  const [decisions, setDecisions] = useState<WorkshopDecision[]>([]);
  const [validation, setValidation] = useState<ValidationOutcome | null>(null);
  const [readiness, setReadiness] = useState<ReadinessResult | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [loadError, setLoadError] = useState<Error | null>(null);
  const [conflict, setConflict] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    if (!workshopId) return;
    setLoadState("loading");
    try {
      const { workshop: w } = await api.getWorkshop(workshopId);
      setWorkshop(w);

      const [{ candidate: c }, questionsRes, decisionsRes] = await Promise.all([
        api.getCandidate(w.candidate_id),
        api.listWorkshopQuestions(workshopId),
        api.listWorkshopDecisions(workshopId),
      ]);
      setCandidate(c);
      setQuestions(questionsRes.items);
      setDecisions(decisionsRes.items);

      if (w.discovery_ids.length > 0) {
        const details = await Promise.all(
          w.discovery_ids.map((id) => api.scoutDiscovery(id).then((r) => r.discovery)),
        );
        setDiscoveries(details);
      } else {
        setDiscoveries([]);
      }

      let { draft: draftDoc, revision: rev } = await api.getWorkshopDraft(workshopId);
      // A Workshop legitimately has no draft yet the first time it is
      // opened (PID-004B: current_draft_id starts null). Materialise an
      // empty, real draft through the same governed authoring endpoint
      // every other edit uses (expected_revision=0 creates one) — never a
      // client-only placeholder — so validation has something real to
      // assess (MISSING_INSTRUMENT_APPLICABILITY / MISSING_COMPOSITION are
      // themselves genuine findings, not an error state).
      if (draftDoc === null && w.status === "ACTIVE") {
        const created = await api.updateWorkshopDraft(workshopId, {
          expected_revision: 0,
          draft: EMPTY_DRAFT_SEED,
          schema_semantic_version: SCHEMA_SEMANTIC_VERSION,
        });
        draftDoc = created.draft;
        rev = created.revision;
      }
      setDraft(draftDoc);
      setRevision(rev);

      if (draftDoc !== null) {
        const { validation: v } = await api.validateWorkshop(workshopId);
        setValidation(v);
      } else {
        setValidation(null);
      }

      const { readiness: r } = await api.getWorkshopReadiness(workshopId);
      setReadiness(r);

      setLoadState("ready");
    } catch (err) {
      setLoadError(err instanceof Error ? err : new Error("Unknown error"));
      setLoadState("error");
    }
  }, [workshopId]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const revalidate = useCallback(async () => {
    if (!workshopId) return;
    const { validation: v } = await api.validateWorkshop(workshopId);
    setValidation(v);
  }, [workshopId]);

  const reloadQuestions = useCallback(async () => {
    if (!workshopId) return;
    const { items } = await api.listWorkshopQuestions(workshopId);
    setQuestions(items);
  }, [workshopId]);

  const reloadDecisions = useCallback(async () => {
    if (!workshopId) return;
    const { items } = await api.listWorkshopDecisions(workshopId);
    setDecisions(items);
  }, [workshopId]);

  const reloadReadiness = useCallback(async () => {
    if (!workshopId) return;
    const { readiness: r } = await api.getWorkshopReadiness(workshopId);
    setReadiness(r);
  }, [workshopId]);

  const reloadWorkshop = useCallback(async () => {
    if (!workshopId) return;
    const { workshop: w } = await api.getWorkshop(workshopId);
    setWorkshop(w);
  }, [workshopId]);

  // Every draft save goes through here — the SOLE place expected_revision
  // is threaded, so a stale-revision conflict is handled identically no
  // matter which panel triggered the save (PID-004B directive: "a stale
  // write must surface a clear conflict message, never silently
  // overwrite"). Returns true on success so the calling panel can clear
  // its own "unsaved" flag; on conflict, the caller's local edits are left
  // exactly as the user typed them (never overwritten), and the caller
  // decides whether to re-read.
  const saveDraft = useCallback(
    async (nextDraft: Partial<SpecificationDraftDoc>): Promise<boolean> => {
      if (!workshopId || revision === null) return false;
      setConflict(null);
      try {
        const result = await api.updateWorkshopDraft(workshopId, {
          expected_revision: revision,
          draft: nextDraft,
          schema_semantic_version: SCHEMA_SEMANTIC_VERSION,
        });
        setDraft(result.draft);
        setRevision(result.revision);
        await revalidate();
        return true;
      } catch (err) {
        if (err instanceof ApiError && err.code === "SPECIFICATION_STALE_REVISION") {
          setConflict(
            "Someone (or another browser tab) saved a newer revision of this draft since you loaded " +
              "it. Your changes were NOT saved and the draft was NOT overwritten — reload the latest " +
              "draft below to see the current revision, then reapply your edit.",
          );
        } else if (err instanceof ApiError) {
          setConflict(err.message);
        } else {
          setConflict("Could not save the draft.");
        }
        return false;
      }
    },
    [workshopId, revision, revalidate],
  );

  const reloadDraftOnly = useCallback(async () => {
    if (!workshopId) return;
    const { draft: d, revision: rev } = await api.getWorkshopDraft(workshopId);
    setDraft(d);
    setRevision(rev);
    setConflict(null);
    await revalidate();
  }, [workshopId, revalidate]);

  if (!workshopId) return null;

  if (loadState === "loading") {
    return (
      <div className="page">
        <LoadingState label="Loading Strategy Workshop…" />
      </div>
    );
  }
  if (loadState === "error" || !workshop) {
    return (
      <div className="page">
        <ErrorState error={loadError ?? new Error("Unknown error")} dependency={`workshop ${workshopId}`} onRetry={loadAll} />
      </div>
    );
  }

  const primaryDiscovery = discoveries[0] ?? null;

  return (
    <div className="page workshop-page">
      <WorkshopHeader
        workshop={workshop}
        candidate={candidate}
        revision={revision}
        validation={validation}
        readiness={readiness}
      />

      <SourcePanel discovery={primaryDiscovery} discoveryCount={discoveries.length} />

      <HypothesisPanel
        workshop={workshop}
        draft={draft}
        revision={revision}
        onSave={saveDraft}
        conflict={conflict}
        onReloadDraft={reloadDraftOnly}
      />

      <QuestionsPanel
        workshopId={workshopId}
        workshop={workshop}
        questions={questions}
        decisions={decisions}
        onChanged={reloadQuestions}
      />

      <DecisionsPanel
        workshopId={workshopId}
        workshop={workshop}
        decisions={decisions}
        questions={questions}
        onChanged={async () => {
          await reloadDecisions();
          await revalidate();
        }}
      />

      <SpecificationPanel
        workshop={workshop}
        draft={draft}
        revision={revision}
        onSave={saveDraft}
        conflict={conflict}
        onReloadDraft={reloadDraftOnly}
      />

      <ValidationPanel validation={validation} onRevalidate={revalidate} />

      <DataRequirementsPanel draft={draft} />

      <ReadinessPanel
        workshopId={workshopId}
        workshop={workshop}
        readiness={readiness}
        onAssessed={reloadReadiness}
      />

      <PolicyPanel draft={draft} />

      <FinalisationPanel
        workshopId={workshopId}
        workshop={workshop}
        draft={draft}
        revision={revision}
        validation={validation}
        readiness={readiness}
        questions={questions}
        decisions={decisions}
        onFinalised={async () => {
          await reloadWorkshop();
          await reloadDraftOnly();
          await reloadReadiness();
        }}
      />
    </div>
  );
}
