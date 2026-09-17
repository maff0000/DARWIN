import { EvidenceBadge } from "./EvidenceBadge";

/** The unmistakable label PID-003 sec10 requires on every leaderboard/
 * visualisation of claimed performance: "SOURCE_CLAIM — NOT INDEPENDENTLY
 * VERIFIED BY DARWIN". Reuses EvidenceBadge's existing SOURCE_CLAIM visual
 * treatment (evi-source hue) rather than inventing a second badge language
 * for the same evidence level — the same discipline the Runs pages already
 * use for evidence-level display. */
export function SourceClaimNotice({ compact = false }: { compact?: boolean }) {
  return (
    <div className="source-claim-notice">
      <EvidenceBadge level="SOURCE_CLAIM" dense />
      <span className="source-claim-notice__text">
        SOURCE_CLAIM — NOT INDEPENDENTLY VERIFIED BY DARWIN
        {!compact && (
          <> · every figure here is the source's own claim, exactly as extracted. This is a display/triage
            ordering only, never DARWIN endorsement and never a composite score.</>
        )}
      </span>
    </div>
  );
}
