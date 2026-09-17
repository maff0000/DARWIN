import { test, expect } from "@playwright/test";

test("ARENA loads and shows build SHA, health, readiness (items 1,2,3)", async ({ page, request }) => {
  // Assert against the real value the running stack reports (PID-002 real-
  // data rule) rather than a hardcoded placeholder SHA, which is stale the
  // moment the CI env changes the commit it builds from.
  const buildInfo = await (await request.get("/api/v1/buildinfo")).json();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  // build/commit shown in the top bar
  await expect(page.locator(".top-bar__build")).toContainText(
    `v${buildInfo.application_version} · ${buildInfo.commit.slice(0, 7)}`,
  );
  // component health table renders real readiness data
  await expect(page.getByRole("cell", { name: "postgres" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "migrations" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "hermes_adapter" })).toBeVisible();
});

test("left navigation works (item 15)", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Datasets" }).click();
  await expect(page).toHaveURL(/\/datasets$/);
  await expect(page.getByRole("heading", { name: "Datasets" })).toBeVisible();

  await page.getByRole("link", { name: "Research Runs" }).click();
  await expect(page).toHaveURL(/\/runs$/);

  await page.getByRole("link", { name: "Pipeline" }).click();
  await expect(page).toHaveURL(/\/pipeline$/);

  await page.getByRole("link", { name: "System Status" }).click();
  await expect(page).toHaveURL(/\/system$/);
});

test("top utility bar works (item 16)", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".top-bar__health")).toBeVisible();
  await expect(page.getByRole("link", { name: "Repository" })).toHaveAttribute(
    "href",
    "https://github.com/maff0000/DARWIN",
  );
  await expect(page.getByRole("button", { name: /Account/ })).toContainText("Not configured");
});

test("primary nav collapse toggle works", async ({ page }) => {
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Collapse navigation" });
  await toggle.click();
  await expect(page.getByRole("button", { name: "Expand navigation" })).toBeVisible();
});
