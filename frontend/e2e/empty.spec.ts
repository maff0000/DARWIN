import { test, expect } from "@playwright/test";

// Run against a freshly-migrated, deliberately unseeded DARWIN_core instance
// — proves the empty states are intentional design, not missing markup
// (PID-002 §15). Zero is a valid, real API response here, not a fixture.
test("empty states are deliberately designed, not generic placeholders (item 13)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("0").first()).toBeVisible();
  await expect(page.getByText(/No datasets loaded yet/i)).toBeVisible();
  await expect(page.getByText(/No research runs yet/i)).toBeVisible();

  await page.goto("/datasets");
  await expect(page.getByText(/No MarketDatasets loaded yet/i)).toBeVisible();

  await page.goto("/runs");
  await expect(page.getByText(/No research runs recorded yet/i)).toBeVisible();
  await expect(page.getByText(/correct state for DARWIN's current milestone/i)).toBeVisible();
});
