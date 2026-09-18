import { test, expect } from "@playwright/test";

// PID-004B Strategy Workshop — workspace-loss proof (directive scenario
// 6). Runs as its OWN Playwright invocation, in a SEPARATE CI step, after
// a `docker exec` against the running darwin_core container has already
// deleted this exact Workshop's on-disk authoring workspace directory
// (see .github/workflows/ci.yml's "Simulate workspace loss" step) — using
// the backend's own filesystem, not a new production UI control (PID-004B
// directive: workspace deletion is deliberately NOT something this test
// (or any ARENA page) can trigger itself).
//
// The Workshop this targets is the SAME one e2e/workshop.spec.ts's own
// scenario-1 test opens and mutates (real questions/decisions/draft
// edits) — its id is captured to a file scenario 1 writes
// (frontend/e2e/fixtures/.workshop_scout_flow_id.txt) so the CI
// orchestration step can target the exact right directory
// (/srv/DARWIN/workspaces/<id>) without guessing.

const WORKSHOP_ID = process.env.DARWIN_E2E_WORKSPACE_LOSS_WORKSHOP_ID ?? "";

test.skip(
  !WORKSHOP_ID,
  "DARWIN_E2E_WORKSPACE_LOSS_WORKSHOP_ID was not set — the CI orchestration step that deletes the " +
    "on-disk workspace and exports this id did not run before this test.",
);

test("canonical DB-backed Workshop state survives its on-disk workspace directory being deleted", async ({ page }) => {
  await page.goto(`/workshops/${WORKSHOP_ID}`);

  // Everything on this page is read from Postgres via the real API
  // (darwin.workshop.workspace's own module docstring: the workspace is a
  // non-canonical authoring surface only) — deleting the directory on disk
  // must change NONE of this.
  await expect(page.locator(".workshop-raw-symbol", { hasText: "XAUUSD" })).toBeVisible();
  await expect(page.locator(".workshop-badge--decision-accepted")).toBeVisible();
  await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_COMPOSITION" })).toBeVisible();

  // A further mutating action (which internally calls
  // `_sync_workspace_best_effort` -> `ensure_workspace`, recreating the
  // deleted directory from scratch) must still succeed — a missing
  // workspace directory must never fail an otherwise-valid API call.
  await page.locator(".workshop-question-form input").first().fill("workspace.recovery");
  await page.locator(".workshop-question-form textarea").fill("Does the deleted workspace break anything?");
  await page.getByRole("button", { name: "Raise question" }).click();
  await expect(page.getByText("Does the deleted workspace break anything?")).toBeVisible();
});
