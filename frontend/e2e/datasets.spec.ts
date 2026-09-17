import { test, expect } from "@playwright/test";

test("dataset list renders real persisted datasets, filters are instrument-generic (items 5, 11)", async ({ page }) => {
  await page.goto("/datasets");
  await expect(page.getByRole("cell", { name: "XAU_USD" }).first()).toBeVisible();
  await expect(page.getByRole("cell", { name: "EUR_USD" }).first()).toBeVisible();

  // the instrument filter dropdown is built from real data, not a hardcoded
  // XAU_USD-only list — this is the multi-instrument-genericity proof.
  const filter = page.locator(".filter-bar select").first();
  await expect(filter.locator("option", { hasText: "EUR_USD" })).toHaveCount(1);
  await filter.selectOption("EUR_USD");
  await expect(page.getByRole("cell", { name: "XAU_USD" })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "EUR_USD" }).first()).toBeVisible();
});

test("dataset detail renders instrument/timeframe/unit semantics/fingerprint from the real InstrumentDefinition API (item 6)", async ({ page }) => {
  await page.goto("/datasets");
  await page.getByRole("cell", { name: "XAU_USD" }).first().locator("a").click();
  await expect(page).toHaveURL(/\/datasets\/[a-f0-9-]+$/);

  await expect(page.getByRole("heading", { name: /XAU_USD/ })).toBeVisible();
  // unit sentence is derived from the governed InstrumentDefinition API response
  await expect(page.getByText(/price → usd per troy ounce/i)).toBeVisible();
  await expect(page.getByText("TROY_OUNCE", { exact: true })).toBeVisible();
  await expect(page.getByText("USD_PER_TROY_OUNCE", { exact: true })).toBeVisible();
  // fingerprint identity is present (abbreviated id-value component)
  await expect(page.locator(".id-value").first()).toBeVisible();
});
