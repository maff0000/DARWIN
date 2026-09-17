import { test, expect } from "@playwright/test";

// This E2E run is deliberately pointed at a DARWIN_core instance whose
// HERMES config targets an unreachable host — a real degraded dependency,
// not a frontend mock (PID-002 §13/§14).
test("HERMES degraded renders correctly without breaking the control plane (item 4)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/HERMES historical access is degraded/i)).toBeVisible();
  await expect(page.getByText(/DARWIN's own control plane is unaffected/i)).toBeVisible();

  await page.goto("/system/hermes");
  const statusBadge = page.locator(".status-badge--degraded");
  await expect(statusBadge.first()).toBeVisible();
  await expect(statusBadge.first()).toContainText("Degraded");
});

test("API failure (missing resource) produces a controlled UI, not a raw error (item 14)", async ({ page }) => {
  await page.goto("/datasets/00000000-0000-0000-0000-000000000000");
  await expect(page.locator(".error-state__title")).toContainText(/Couldn't load|not ready/i);
  // never a raw stack trace / unhandled exception rendering
  await expect(page.locator("body")).not.toContainText("Traceback");
});
