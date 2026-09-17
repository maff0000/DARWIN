import { test } from "@playwright/test";

// Not an acceptance test — captures real screenshots of every primary route
// for Rogue's design-review gate (PID-002 §17/§19). Run against the seeded
// stack (DARWIN_E2E_BASE_URL) unless SCREENSHOT_EMPTY=1, in which case it
// targets the empty-state instance instead.
const DIR = "screenshots";

test.describe.configure({ mode: "serial" });

test("capture primary routes", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });

  const routes: Array<[string, string]> = process.env.SCREENSHOT_EMPTY
    ? [
        ["/", "01-overview-empty"],
        ["/datasets", "02-datasets-empty"],
        ["/runs", "03-runs-empty"],
      ]
    : [
        ["/", "01-overview"],
        ["/datasets", "02-datasets-list"],
        ["/discovery", "06a-discovery-list"],
        ["/pipeline", "07-pipeline"],
        ["/system", "08-system-status"],
        ["/system/hermes", "09-hermes-degraded"],
        ["/system/migrations", "10-migrations"],
        ["/evidence", "11-evidence"],
      ];

  for (const [path, name] of routes) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${DIR}/${name}.png`, fullPage: true });
  }

  if (!process.env.SCREENSHOT_EMPTY) {
    // dataset detail
    await page.goto("/datasets");
    await page.getByRole("cell", { name: "XAU_USD" }).first().locator("a").click();
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${DIR}/03-dataset-detail-xau.png`, fullPage: true });

    // runs list
    await page.goto("/runs");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${DIR}/04-runs-list.png`, fullPage: true });

    // run detail — DIKE_DISABLED
    const athenaRow = page.locator("tr", { has: page.locator(".evi-athena") }).filter({ hasText: "XAU_USD" }).first();
    await athenaRow.locator("a").click();
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${DIR}/05-run-detail-dike-disabled.png`, fullPage: true });

    // run detail — DIKE_GUARDED
    await page.goto("/runs");
    const apolloRow = page.locator("tr", { has: page.locator(".evi-apollo") }).first();
    await apolloRow.locator("a").click();
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${DIR}/06-run-detail-dike-guarded.png`, fullPage: true });

    // discovery detail (PID-003 SCOUT)
    await page.goto("/discovery");
    await page.waitForLoadState("networkidle");
    await page.locator(".data-table tbody tr").first().locator("a").click();
    await page.locator(".page-header h1").waitFor({ state: "visible" });
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${DIR}/06b-discovery-detail.png`, fullPage: true });

    // discovery visualisations (return/drawdown + PF/trade-count scatters)
    // and the + Add Strategy modal
    await page.goto("/discovery");
    await page.waitForLoadState("networkidle");
    await page.locator(".discovery-viz-grid").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${DIR}/06c-discovery-visualisations.png`, fullPage: false });
    await page.getByRole("button", { name: "+ Add Strategy" }).click();
    await page.locator(".modal-panel").waitFor({ state: "visible" });
    await page.screenshot({ path: `${DIR}/06d-discovery-add-strategy-modal.png`, fullPage: false });
  }
});
