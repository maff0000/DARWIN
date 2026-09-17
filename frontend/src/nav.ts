// Nav is data, not markup, specifically so SCOUT/Specification/ATHENA/APOLLO/
// Qualification can land later as new groups/items without touching the
// shell component (PID-002 §5's progressive-expansion requirement). The
// icon name is data too, for the same reason — LeftNav looks it up in
// NavIcon's registry rather than embedding markup here.
export type NavIconName =
  | "overview"
  | "datasets"
  | "runs"
  | "evidence"
  | "pipeline"
  | "system-status"
  | "hermes"
  | "migrations";

export interface NavItem {
  label: string;
  path: string;
  icon: NavIconName;
}
export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  { label: "Core", items: [{ label: "Overview", path: "/", icon: "overview" }] },
  { label: "Market Data", items: [{ label: "Datasets", path: "/datasets", icon: "datasets" }] },
  {
    label: "Research",
    items: [
      { label: "Research Runs", path: "/runs", icon: "runs" },
      { label: "Evidence", path: "/evidence", icon: "evidence" },
    ],
  },
  { label: "Pipeline", items: [{ label: "Pipeline", path: "/pipeline", icon: "pipeline" }] },
  {
    label: "System",
    items: [
      { label: "System Status", path: "/system", icon: "system-status" },
      { label: "HERMES", path: "/system/hermes", icon: "hermes" },
      { label: "Migrations", path: "/system/migrations", icon: "migrations" },
    ],
  },
];
