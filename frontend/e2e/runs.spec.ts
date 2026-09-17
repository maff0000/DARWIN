import { test, expect } from "@playwright/test";

test("run list renders real persisted runs and distinct evidence badges (items 7, 12)", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByRole("cell", { name: /London Breakout/ }).first()).toBeVisible();

  // three distinct evidence classes are seeded (SOURCE_CLAIM, ATHENA_RESULT x2, APOLLO_PROOF)
  // and each must render a visually/semantically distinct badge, not one generic chip.
  const sourceBadge = page.locator(".evidence-badge.evi-source");
  const athenaBadge = page.locator(".evidence-badge.evi-athena");
  const apolloBadge = page.locator(".evidence-badge.evi-apollo");
  await expect(sourceBadge.first()).toBeVisible();
  await expect(athenaBadge.first()).toBeVisible();
  await expect(apolloBadge.first()).toBeVisible();
  // distinct classNames prove distinct CSS treatment, not the same badge reused
  await expect(sourceBadge).not.toHaveClass(/evi-athena|evi-apollo/);
});

test("instrument filter on Research Runs is generic (item 11)", async ({ page }) => {
  await page.goto("/runs");
  const filter = page.locator(".filter-bar select").first();
  await expect(filter.locator("option", { hasText: "EUR_USD" })).toHaveCount(1);
  await filter.selectOption("EUR_USD");
  await expect(page.getByRole("cell", { name: /Mean Reversion/ })).toBeVisible();
  await expect(page.getByRole("cell", { name: /London Breakout/ })).toHaveCount(0);
});

test("run detail renders evidence level and DIKE_DISABLED correctly (items 8, 9)", async ({ page }) => {
  await page.goto("/runs");
  const athenaRow = page.locator("tr", { has: page.locator(".evi-athena") }).filter({ hasText: "XAU_USD" }).first();
  await athenaRow.locator("a").click();

  await expect(page.locator(".evidence-badge").first()).toBeVisible();
  await expect(page.getByText(/historical optimisation\/search result/i)).toBeVisible();
  await expect(page.locator(".dike-state")).toHaveText("DIKE_DISABLED");
  await expect(page.getByText(/unguarded scientific baseline/i)).toBeVisible();
});

test("run detail renders DIKE_GUARDED policy identity correctly (item 10)", async ({ page }) => {
  await page.goto("/runs");
  const apolloRow = page.locator("tr", { has: page.locator(".evi-apollo") }).first();
  await apolloRow.locator("a").click();

  // Wait for the detail view to actually render before checking DIKE state --
  // this is the first assertion after an async client-side navigation, so it
  // needs the same warm-up as the sibling DIKE_DISABLED test below (which
  // gets it for free from its own earlier assertions).
  await expect(page.locator(".evidence-badge").first()).toBeVisible();
  // DIKE identity on the detail view is rendered by DikePanel as a plain
  // div (.dike-state), not a table cell -- the list page's own DIKE column
  // and filter <option> both also say "DIKE_GUARDED", so scope tightly to
  // the actual detail-page element rather than bare text.
  await expect(page.locator(".dike-state")).toHaveText("DIKE_GUARDED");
  // IdValue abbreviates long values for scanning but keeps the full value
  // reachable via the title attribute (PID-002 §4) — assert both.
  await expect(page.locator('[title="e2e-synthetic-conservative-policy"]')).toBeVisible();
  await expect(page.getByText("v0-e2e")).toBeVisible();
  // never implies Foundation evaluates DIKE
  await expect(page.getByText(/does not evaluate or enforce/i)).toBeVisible();
});
