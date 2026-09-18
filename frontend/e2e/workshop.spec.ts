import { writeFileSync } from "fs";
import { test, expect } from "@playwright/test";

// PID-004B Strategy Workshop — ARENA Workshop UI, real browser proof
// against the real DARWIN_core bundle + real API + disposable PostgreSQL
// (same harness discipline as discovery.spec.ts / runs.spec.ts). Fixture
// ids come from frontend/e2e/fixtures/seed.py's own printed/written
// output, exported into these env vars by the CI step that runs after
// seeding (see .github/workflows/ci.yml) — never hardcoded, since every
// id is a real, freshly-generated UUID each seed run.
//
// This file deliberately does NOT touch any of the SIX pre-existing
// discoveries discovery.spec.ts's own "mutating actions" block changes —
// it uses its own dedicated seeded discovery/candidates so the two files
// can run concurrently in different Playwright workers without racing on
// the same row (no `fullyParallel` override forces file-level
// serialisation — see discovery.spec.ts's own comment on this).

const SCOUT_DISCOVERY_ID = process.env.DARWIN_E2E_WORKSHOP_SCOUT_DISCOVERY_ID ?? "";
const COMPLETE_WORKSHOP_ID = process.env.DARWIN_E2E_WORKSHOP_COMPLETE_ID ?? "";
const DATA_BLOCKED_WORKSHOP_ID = process.env.DARWIN_E2E_WORKSHOP_DATA_BLOCKED_ID ?? "";
const STALE_EDIT_WORKSHOP_ID = process.env.DARWIN_E2E_WORKSHOP_STALE_EDIT_ID ?? "";

test.skip(
  !SCOUT_DISCOVERY_ID || !COMPLETE_WORKSHOP_ID || !DATA_BLOCKED_WORKSHOP_ID || !STALE_EDIT_WORKSHOP_ID,
  "Workshop fixture ids were not exported (DARWIN_E2E_WORKSHOP_* env vars) — seed.py's " +
    ".seed_output.json was not read by the CI step before this run.",
);

// Shared across scenario 1 and scenario 5 (idempotent open) — scenario 5
// intentionally reopens the SAME discovery's Workshop and expects to land
// on the SAME id scenario 1 already captured. Tests in this file run in
// declared order (no fullyParallel), so this module-level mutation is safe.
let scoutFlowWorkshopId = "";

test.describe("PID-004B Workshop — real SCOUT flow (scenario 1)", () => {
  test("opens a Workshop from a real Discovery, shows source provenance, resolves validation deficiencies via real edits, and survives reload", async ({
    page,
  }) => {
    const beforeDiscoveryResp = await page.request.get(`/api/v1/scout/discoveries/${SCOUT_DISCOVERY_ID}`);
    const beforeDiscovery = (await beforeDiscoveryResp.json()).discovery;
    expect(beforeDiscovery.source_symbol).toBe("XAUUSD");

    await page.goto(`/discovery/${SCOUT_DISCOVERY_ID}`);
    await expect(page.getByRole("heading", { name: "E2E Workshop Source — XAUUSD Session Breakout" })).toBeVisible();
    await expect(page.getByText(/SOURCE_CLAIM — NOT INDEPENDENTLY VERIFIED BY DARWIN/).first()).toBeVisible();
    await expect(page.locator(".mono", { hasText: "XAUUSD" }).first()).toBeVisible();

    await page.getByRole("button", { name: "Open Workshop" }).click();
    await expect(page).toHaveURL(/\/workshops\/[a-f0-9-]+$/);
    scoutFlowWorkshopId = page.url().split("/workshops/")[1];
    // Written for the CI orchestration step behind e2e/workshop-workspace-
    // loss.spec.ts (scenario 6) — the only way that step's `docker exec`
    // can target this exact freshly-created Workshop's on-disk directory.
    // Playwright's own process runs with cwd == the frontend/ project root
    // (where playwright.config.ts lives), so this relative path resolves
    // there regardless of module system (no __dirname under ESM).
    writeFileSync("e2e/fixtures/.workshop_scout_flow_id.txt", scoutFlowWorkshopId);

    // SOURCE CLAIM warning + XAUUSD raw source context on the Workshop page
    await expect(page.getByText(/SOURCE_CLAIM — NOT INDEPENDENTLY VERIFIED BY DARWIN/).first()).toBeVisible();
    await expect(page.locator(".workshop-raw-symbol", { hasText: "XAUUSD" })).toBeVisible();

    // Initial real validation deficiencies — an auto-materialised empty
    // draft (PID-004B: never construct Workshop state client-side; this
    // draft was created via the real PUT .../draft endpoint on page load).
    await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_INSTRUMENT_APPLICABILITY" })).toBeVisible();
    await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_COMPOSITION" })).toBeVisible();

    // Create + accept a USER_CLARIFICATION decision proposing XAU_USD.
    await page.locator(".workshop-decision-form textarea").fill('{"instrument_id":"XAU_USD"}');
    await page.getByRole("button", { name: "Propose decision" }).click();
    await expect(page.locator(".workshop-badge--origin-user-clarification")).toBeVisible();
    await expect(page.locator(".workshop-badge--decision-proposed")).toBeVisible();
    await page.getByRole("button", { name: "Accept" }).click();
    await expect(page.locator(".workshop-badge--decision-accepted")).toBeVisible();

    // Accepting a decision alone must NOT change the draft — the
    // instrument-applicability deficiency is still present.
    await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_INSTRUMENT_APPLICABILITY" })).toBeVisible();

    // Explicitly update the draft's instrument applicability through the
    // authoring UI (never client-side-only). The instrument dropdown is
    // populated from a real GET /api/v1/instrument-definitions call —
    // wait for its option to actually attach before selecting it.
    await page.locator('option[value="XAU_USD"]').first().waitFor({ state: "attached" });
    await page.getByLabel("Instrument", { exact: false }).selectOption("XAU_USD");
    await page.getByRole("button", { name: "Save specification" }).click();

    // MISSING_INSTRUMENT_APPLICABILITY disappears; MISSING_COMPOSITION remains.
    await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_INSTRUMENT_APPLICABILITY" })).toHaveCount(0);
    await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_COMPOSITION" })).toBeVisible();

    // Reload — state persists from the real backend, never client memory.
    await page.reload();
    await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_INSTRUMENT_APPLICABILITY" })).toHaveCount(0);
    await expect(page.locator(".workshop-finding-code", { hasText: "MISSING_COMPOSITION" })).toBeVisible();
    await expect(page.locator(".workshop-badge--decision-accepted")).toBeVisible();

    // The underlying SCOUT discovery row is genuinely untouched.
    const afterDiscoveryResp = await page.request.get(`/api/v1/scout/discoveries/${SCOUT_DISCOVERY_ID}`);
    const afterDiscovery = (await afterDiscoveryResp.json()).discovery;
    expect(afterDiscovery.source_symbol).toBe(beforeDiscovery.source_symbol);
    expect(afterDiscovery.title).toBe(beforeDiscovery.title);
    expect(afterDiscovery.intake_status).toBe(beforeDiscovery.intake_status);
    expect(afterDiscovery.updated_at_utc).toBe(beforeDiscovery.updated_at_utc);
  });
});

test.describe("PID-004B Workshop — controlled complete flow (scenario 2)", () => {
  test("a fully valid draft finalises to an immutable StrategyVersion and the page becomes read-only", async ({ page }) => {
    await page.goto(`/workshops/${COMPLETE_WORKSHOP_ID}`);
    await expect(page.locator(".workshop-chip--status-active")).toBeVisible();
    await expect(page.locator(".workshop-badge--validation-valid, .workshop-chip--validation-valid").first()).toBeVisible();

    // Complete rules visible/editable, material decision present.
    await expect(page.getByLabel("Title")).toHaveValue("Simple close-above-level long");
    await expect(page.locator(".workshop-badge--decision-accepted")).toBeVisible();

    // Finalisation summary visible before the explicit click.
    await expect(page.getByText("Finalising creates an immutable StrategyVersion.")).toBeVisible();
    const finaliseButton = page.getByRole("button", { name: "Finalise Workshop" });
    await expect(finaliseButton).toBeEnabled();
    await finaliseButton.click();

    await expect(page.getByText("Specified — not yet research-tested.")).toBeVisible();
    await expect(page.locator(".workshop-chip--status-finalised")).toBeVisible();
    const fingerprintValue = page.locator(".kv-row", { hasText: "Semantic fingerprint" }).locator(".id-value");
    await expect(fingerprintValue).toBeVisible();

    // Candidate advanced to SPECIFIED.
    const candidateResp = await page.request.get(`/api/v1/workshops/${COMPLETE_WORKSHOP_ID}`);
    const candidateId = (await candidateResp.json()).workshop.candidate_id;
    const candidate = await (await page.request.get(`/api/v1/candidates/${candidateId}`)).json();
    expect(candidate.candidate.pipeline_stage).toBe("SPECIFIED");

    // Reload/restart retains state.
    await page.reload();
    await expect(page.locator(".workshop-chip--status-finalised")).toBeVisible();
    await expect(page.getByText("Specified — not yet research-tested.")).toBeVisible();
  });
});

test.describe("PID-004B Workshop — DATA_BLOCKED flow (scenario 3)", () => {
  test("VALID + DATA_BLOCKED is truthfully shown and finalisation still succeeds", async ({ page }) => {
    await page.goto(`/workshops/${DATA_BLOCKED_WORKSHOP_ID}`);
    await expect(page.locator(".workshop-badge--validation-valid, .workshop-chip--validation-valid").first()).toBeVisible();
    await expect(page.locator(".workshop-chip--readiness-unassessed")).toBeVisible();

    const finaliseButton = page.getByRole("button", { name: "Finalise Workshop" });
    await expect(finaliseButton).toBeEnabled();
    await finaliseButton.click();
    await expect(page.getByText("Specified — not yet research-tested.")).toBeVisible();

    await page.getByRole("button", { name: "Assess readiness now" }).click();
    await expect(page.locator(".workshop-badge--readiness-data_blocked").first()).toBeVisible();
    // Truthful missing-requirement display — never fabricated.
    await expect(page.getByText("AUTHORITY_NOT_ONBOARDED").first()).toBeVisible();
    await expect(page.getByText(/no data authority integration exists for OPTIONS_AUTHORITY/).first()).toBeVisible();
  });
});

test.describe("PID-004B Workshop — stale-edit conflict (scenario 4)", () => {
  test("a stale save is refused with a clear conflict, never a silent overwrite", async ({ browser }) => {
    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();

    await pageA.goto(`/workshops/${STALE_EDIT_WORKSHOP_ID}`);
    await pageB.goto(`/workshops/${STALE_EDIT_WORKSHOP_ID}`);

    // Both contexts loaded the same draft revision. A saves first, via the
    // Hypothesis panel's title field (same PUT .../draft + expected_revision
    // mechanism the Specification panel uses).
    const titleFieldA = pageA.getByLabel("Title");
    await titleFieldA.fill("Simple close-above-level long (edited by A)");
    await pageA.getByRole("button", { name: "Save hypothesis" }).click();
    await expect(pageA.locator(".form-error")).toHaveCount(0);

    // B, still holding the OLD revision in memory, now tries to save.
    const titleFieldB = pageB.getByLabel("Title");
    await titleFieldB.fill("Simple close-above-level long (edited by B, stale)");
    await pageB.getByRole("button", { name: "Save hypothesis" }).click();

    await expect(pageB.getByText(/NOT saved and the draft was NOT overwritten/).first()).toBeVisible();

    // A's save is the one that actually persisted.
    await pageA.reload();
    await expect(pageA.getByLabel("Title")).toHaveValue("Simple close-above-level long (edited by A)");

    await contextA.close();
    await contextB.close();
  });
});

test.describe("PID-004B Workshop — idempotent open/finalise (scenario 5)", () => {
  test("repeated Open Workshop clicks never create a duplicate ACTIVE Workshop", async ({ page }) => {
    test.skip(!scoutFlowWorkshopId, "requires scenario 1 to have run first in this same file");
    await page.goto(`/discovery/${SCOUT_DISCOVERY_ID}`);
    await page.getByRole("button", { name: "Open Workshop" }).click();
    await expect(page).toHaveURL(new RegExp(`/workshops/${scoutFlowWorkshopId}$`));
  });

  test("a repeated finalisation resolves to the same StrategyVersion, not a second one", async ({ page }) => {
    const before = await (await page.request.get(`/api/v1/workshops/${COMPLETE_WORKSHOP_ID}`)).json();
    expect(before.workshop.status).toBe("FINALISED");
    const strategyVersionId = before.workshop.finalised_strategy_version_id;
    expect(strategyVersionId).toBeTruthy();

    const draftResp = await (await page.request.get(`/api/v1/workshops/${COMPLETE_WORKSHOP_ID}/draft`)).json();
    const retry = await page.request.post(`/api/v1/workshops/${COMPLETE_WORKSHOP_ID}/finalise`, {
      data: { expected_revision: draftResp.revision },
    });
    expect(retry.status()).toBe(200);
    const retryBody = await retry.json();
    expect(retryBody.strategy_version_id).toBe(strategyVersionId);
    expect(retryBody.candidate_advanced).toBe(false);
  });
});
