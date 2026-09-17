// Nav is data, not markup, specifically so SCOUT/Specification/ATHENA/APOLLO/
// Qualification can land later as new groups/items without touching the
// shell component (PID-002 §5's progressive-expansion requirement).
export interface NavItem {
  label: string;
  path: string;
}
export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  { label: "Core", items: [{ label: "Overview", path: "/" }] },
  { label: "Market Data", items: [{ label: "Datasets", path: "/datasets" }] },
  {
    label: "Research",
    items: [
      { label: "Research Runs", path: "/runs" },
      { label: "Evidence", path: "/evidence" },
    ],
  },
  { label: "Pipeline", items: [{ label: "Pipeline", path: "/pipeline" }] },
  {
    label: "System",
    items: [
      { label: "System Status", path: "/system" },
      { label: "HERMES", path: "/system/hermes" },
      { label: "Migrations", path: "/system/migrations" },
    ],
  },
];
