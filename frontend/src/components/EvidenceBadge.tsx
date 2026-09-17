import type { EvidenceLevel } from "../api/types";

// The single most important visual rule in ARENA (PID.md §11, PID-002 §9):
// these five classes must never look interchangeable. Each gets its own
// hue, its own label, and its own one-line explanation of what the number
// actually proves — never a generic "performance" chip.
const EVIDENCE: Record<
  EvidenceLevel,
  { label: string; short: string; explain: string; className: string }
> = {
  SOURCE_CLAIM: {
    label: "Source claim",
    short: "CLAIM",
    explain: "External claim — not independently proven by DARWIN.",
    className: "evi-source",
  },
  ATHENA_RESULT: {
    label: "ATHENA result",
    short: "SEARCH",
    explain: "Historical optimisation/search result — not independent proof.",
    className: "evi-athena",
  },
  APOLLO_PROOF: {
    label: "APOLLO proof",
    short: "PROOF",
    explain: "Independent sequential proof of a frozen candidate.",
    className: "evi-apollo",
  },
  PLUTUS_RESULT: {
    label: "PLUTUS result",
    short: "FORWARD",
    explain: "Forward/demo evidence.",
    className: "evi-plutus",
  },
  LIVE: {
    label: "Live",
    short: "LIVE",
    explain: "Real-world live evidence.",
    className: "evi-live",
  },
};

export function EvidenceBadge({ level, dense = false }: { level: EvidenceLevel; dense?: boolean }) {
  const meta = EVIDENCE[level] ?? {
    label: level,
    short: level,
    explain: "Unrecognised evidence class.",
    className: "evi-unknown",
  };
  return (
    <span className={`evidence-badge ${meta.className}`} title={meta.explain}>
      <span className="evidence-badge__glyph" aria-hidden="true">
        {meta.short}
      </span>
      {!dense && <span className="evidence-badge__label">{meta.label}</span>}
    </span>
  );
}

export function EvidenceExplain({ level }: { level: EvidenceLevel }) {
  const meta = EVIDENCE[level];
  if (!meta) return null;
  return <p className="evidence-explain">{meta.explain}</p>;
}

export const EVIDENCE_LEVELS: EvidenceLevel[] = [
  "SOURCE_CLAIM",
  "ATHENA_RESULT",
  "APOLLO_PROOF",
  "PLUTUS_RESULT",
  "LIVE",
];

export { EVIDENCE };
