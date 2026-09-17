import type { NavIconName } from "../nav";

/*
 * Inline SVG line icons for the left nav. Kept as a single small registry
 * (rather than one file per icon, or an icon-font/library dependency) so the
 * set stays visually coherent by construction: one viewBox, one stroke
 * width, no fills — matching the instrument-panel language in tokens.css
 * rather than a colourful dashboard icon set. Build-time only; nothing here
 * reaches the shipped bundle as an external request.
 */
const PATHS: Record<NavIconName, JSX.Element> = {
  // Overview — home
  overview: (
    <>
      <path d="M2.5 8.2 8 3.2l5.5 5" />
      <path d="M4.2 6.8V13h7.6V6.8" />
    </>
  ),
  // Datasets — a small database/stack
  datasets: (
    <>
      <ellipse cx="8" cy="3.4" rx="5" ry="1.7" />
      <path d="M3 3.4v9.2c0 .94 2.24 1.7 5 1.7s5-.76 5-1.7V3.4" />
      <path d="M3 8c0 .94 2.24 1.7 5 1.7s5-.76 5-1.7" />
    </>
  ),
  // Discovery — radar sweep (SCOUT scans an external surface for a signal)
  discovery: (
    <>
      <circle cx="8" cy="8" r="1.15" />
      <path d="M8 8V3.2" />
      <path d="M5.05 5.05a4.5 4.5 0 0 1 5.9 0" />
      <path d="M3.15 3.15a6.85 6.85 0 0 1 9.7 0" />
    </>
  ),
  // Research Runs — activity trace
  runs: (
    <path d="M1.8 8.4h3.1l1.6-4.4 2.7 8.3 1.5-3.9h3.5" />
  ),
  // Evidence — shield with a check
  evidence: (
    <>
      <path d="M8 1.8 13.2 3.6v4c0 3.3-2.3 5.3-5.2 6.6-2.9-1.3-5.2-3.3-5.2-6.6v-4Z" />
      <path d="M5.7 7.9 7.3 9.5l3-3.2" />
    </>
  ),
  // Pipeline — staged nodes
  pipeline: (
    <>
      <circle cx="2.6" cy="8" r="1.3" />
      <path d="M3.9 8h1.9" />
      <rect x="6.3" y="5.9" width="3.1" height="4.2" rx="0.7" />
      <path d="M9.4 8h1.9" />
      <circle cx="12.7" cy="8" r="1.3" />
    </>
  ),
  // System Status — monitor
  "system-status": (
    <>
      <rect x="1.8" y="2.6" width="12.4" height="8.2" rx="1" />
      <path d="M5.4 13.8h5.2" />
      <path d="M8 10.8v3" />
    </>
  ),
  // HERMES — server rack
  hermes: (
    <>
      <rect x="2" y="2.2" width="12" height="4.4" rx="0.9" />
      <rect x="2" y="9.4" width="12" height="4.4" rx="0.9" />
      <path d="M4.4 4.4h.01" />
      <path d="M4.4 11.6h.01" />
    </>
  ),
  // Migrations — clock/history
  migrations: (
    <>
      <circle cx="8" cy="8.3" r="5.5" />
      <path d="M8 5.4v3l2.2 1.3" />
      <path d="M2.9 3.3 2.5 6l2.6-.5" />
    </>
  ),
};

export function NavIcon({
  name,
  className,
}: {
  name: NavIconName;
  className?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}
