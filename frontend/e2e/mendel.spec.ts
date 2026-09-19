import { test, expect } from "@playwright/test";

// PID-004C MENDEL Workshop Assistant — ARENA MendelPanel, real browser
// proof against the real DARWIN_core bundle + real API + disposable
// PostgreSQL (same harness discipline as e2e/workshop.spec.ts). This file
// deliberately does NOT re-prove anything WP1/WP2's own backend/adapter
// test suites already prove from scratch (malformed-output validation,
// cross-Workshop substitution, concurrency, the real-CLI prompt-injection
// boundary, the acceptance-transaction shapes) — see this work package's
// final report for exactly what those suites already cover. This file's
// job is the BROWSER-level proofs those suites structurally cannot give:
// real DOM rendering, real user interaction, real visual state.
//
// The seeded Workshop (frontend/e2e/fixtures/seed.py's "workshop_fixture_
// ids.mendel_workshop_id") is ACTIVE with a real, validation-clean draft
// at revision 1 — nothing about a MENDEL run/proposal is pre-seeded; every
// invocation below happens LIVE through the real UI against the real
// POST .../mendel/invoke endpoint. The running darwin_core container this
// suite targets must have DARWIN_MENDEL_E2E_FIXTURE_ADAPTER=1 set (see
// darwin.core.config.DarwinConfig.mendel_e2e_fixture_adapter_enabled's own
// docstring, and darwin/workshop/api.py's `_E2E_FIXTURE_RESULT`) — the
// SAME DeterministicTestMendelAdapter WP1 always used, just pre-loaded
// with a small fixed proposal set so a real browser can exercise the
// accept/reject/stale round trip without a real Claude Code credential
// (this darwin_core build has none configured — the honest, current
// default).

const DIR = "screenshots";
const MENDEL_WORKSHOP_ID = process.env.DARWIN_E2E_WORKSHOP_MENDEL_ID ?? "";
const MENDEL_SCOUT_DISCOVERY_ID = process.env.DARWIN_E2E_WORKSHOP_MENDEL_SCOUT_DISCOVERY_ID ?? "";

test.skip(
  !MENDEL_WORKSHOP_ID,
  "MENDEL Workshop fixture id was not exported (DARWIN_E2E_WORKSHOP_MENDEL_ID) — seed.py's " +
    ".seed_output.json was not read by the CI step before this run.",
);

test.describe.configure({ mode: "serial" });

test.describe("PID-004C MENDEL panel — real invoke/accept/reject/stale round trip", () => {
  test("real vertical slice: invoke, render, accept QUESTION (no mutation), accept DRAFT_MUTATING (mutation)", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto(`/workshops/${MENDEL_WORKSHOP_ID}`);
    await expect(page.locator(".workshop-chip--status-active")).toBeVisible();
    await expect(page.getByRole("heading", { name: /MENDEL Assistant/ })).toBeVisible();
    await expect(page.locator(".mendel-proposal-list li")).toHaveCount(0);

    // No free-form prompt box anywhere — only the closed purpose picker.
    await expect(page.locator(".mendel-invoke-form textarea")).toHaveCount(0);
    await expect(page.locator('.mendel-invoke-form input[type="text"], .mendel-invoke-form input:not([type])')).toHaveCount(1);

    await page.getByRole("button", { name: "Invoke MENDEL" }).click();
    await expect(page.locator(".mendel-reasoning-summary")).toBeVisible();
    await expect(page.locator(".mendel-proposal-list li")).toHaveCount(4);
    await page.screenshot({ path: `${DIR}/mendel-01-proposals-rendered.png`, fullPage: true });

    // Category-A (QUESTION) proposal: distinguishable panel treatment —
    // a genuinely different card class from a DRAFT_MUTATING card, never
    // just a status-chip colour difference.
    const questionCard = page.locator(".mendel-proposal-card--category-question").first();
    await expect(questionCard).toBeVisible();
    await expect(questionCard.locator(".mendel-mutation-banner")).toHaveText(
      /will NOT change the strategy draft/,
    );
    const revisionChipBefore = await page.locator(".workshop-chip--revision").innerText();

    await questionCard.getByRole("button", { name: "Accept" }).click();
    await expect(questionCard.locator(".workshop-badge--mendel-status-accepted")).toBeVisible();
    // Re-fetched/re-rendered state — the panel visually reflects NO draft
    // mutation happened: the revision chip elsewhere on the page is
    // byte-identical to before this accept.
    await expect(page.locator(".workshop-chip--revision")).toHaveText(revisionChipBefore);
    await questionCard.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${DIR}/mendel-02-question-accepted-no-mutation.png`, fullPage: true });

    // Category-C (DRAFT_MUTATING) proposal — PARAMETER_CHANGE.
    const paramCard = page
      .locator(".mendel-proposal-card--category-draft_mutating")
      .filter({ hasText: "PARAMETER_CHANGE" })
      .first();
    await expect(paramCard).toBeVisible();
    await expect(paramCard.locator(".mendel-mutation-banner")).toHaveText(/WILL create a new draft revision/);

    await paramCard.getByRole("button", { name: "Accept" }).click();
    await expect(paramCard.locator(".workshop-badge--mendel-status-accepted")).toBeVisible();
    // Re-fetched/re-rendered state — the panel visually reflects that a
    // NEW draft revision WAS created: the revision chip elsewhere on the
    // page has genuinely advanced.
    await expect(page.locator(".workshop-chip--revision")).not.toHaveText(revisionChipBefore);
    await paramCard.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${DIR}/mendel-03-draft-mutating-accepted-revision-bumped.png`, fullPage: true });
  });

  test("reject an ADVISORY proposal — remains historical, draft unchanged", async ({ page }) => {
    await page.goto(`/workshops/${MENDEL_WORKSHOP_ID}`);
    const revisionChipBefore = await page.locator(".workshop-chip--revision").innerText();

    const advisoryCard = page.locator(".mendel-proposal-card--category-advisory").first();
    await expect(advisoryCard).toBeVisible();
    await advisoryCard.getByRole("button", { name: "Reject" }).click();
    await expect(advisoryCard.locator(".workshop-badge--mendel-status-rejected")).toBeVisible();

    // Still present in history (never removed from the list), and the
    // draft is untouched.
    await expect(advisoryCard).toBeVisible();
    await expect(page.locator(".workshop-chip--revision")).toHaveText(revisionChipBefore);
  });

  test("data-capability: accepting a DATA_REQUIREMENT proposal for an unsupported authority leaves the requirement honestly unmet", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto(`/workshops/${MENDEL_WORKSHOP_ID}`);

    // The FIRST invocation's own DATA_REQUIREMENT proposal was generated
    // against the SAME draft revision as the PARAMETER_CHANGE proposal
    // already accepted above — accepting either one first legitimately
    // stales its siblings from that same batch (PID-004C sec7.5, applied
    // uniformly). A fresh invocation gets a new one bound to the CURRENT
    // revision instead of reusing the now-stale original.
    await page.getByRole("button", { name: "Invoke MENDEL" }).click();
    await expect(page.locator(".mendel-reasoning-summary")).toBeVisible();

    // The proposal list is sorted newest-first (created_at_utc DESC), so
    // `.first()` here is the card THIS invocation just created — never a
    // filter keyed on the "PROPOSED" badge itself, which would stop
    // matching its own target the instant the click below changes that
    // badge to "ACCEPTED" (a live Playwright locator re-evaluates its
    // filter predicate on every wait, so a status-based filter used both
    // before AND after the status-changing action is self-invalidating).
    const dataReqCard = page
      .locator(".mendel-proposal-card--category-draft_mutating")
      .filter({ hasText: "DATA_REQUIREMENT" })
      .first();
    await expect(dataReqCard).toBeVisible();
    await expect(dataReqCard.getByRole("button", { name: "Accept" })).toBeEnabled();
    await dataReqCard.getByRole("button", { name: "Accept" }).click();
    await expect(dataReqCard.locator(".workshop-badge--mendel-status-accepted")).toBeVisible();

    // PID-004C sec8.3.1's DraftCapabilityView, surfaced directly on the
    // panel: the new requirement is recorded faithfully (never a silent
    // proxy substitution) and honestly shown as UNSUPPORTED_OR_AUTHORITY_
    // MISSING — this DARWIN build has no options-authority integration.
    await expect(page.locator(".mono", { hasText: "iv_percentile_d1" })).toBeVisible();
    const capabilityRow = page.locator(".workshop-badge--availability-unsupported-or-authority-missing").first();
    await expect(capabilityRow).toBeVisible();
    await capabilityRow.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${DIR}/mendel-04-data-capability-unsupported.png`, fullPage: true });
  });

  test("stale proposal: a proposal generated against a superseded draft revision is shown STALE and Accept is disabled", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto(`/workshops/${MENDEL_WORKSHOP_ID}`);

    // A second, fresh MENDEL invocation — its proposals bind to whatever
    // the draft revision is RIGHT NOW.
    await page.getByRole("button", { name: "Invoke MENDEL" }).click();
    await expect(page.locator(".mendel-reasoning-summary")).toBeVisible();

    // Newest-first sort (see the data-capability test's own comment above
    // for why this is `.first()` by creation order, never a status-based
    // filter that would self-invalidate once this exact card's badge
    // changes from PROPOSED to STALE below).
    const secondParamCard = page
      .locator(".mendel-proposal-card--category-draft_mutating")
      .filter({ hasText: "PARAMETER_CHANGE" })
      .first();
    await expect(secondParamCard).toBeVisible();
    await expect(secondParamCard.getByRole("button", { name: "Accept" })).toBeEnabled();

    // Advance the draft revision through a completely different, ordinary
    // authoring action (never MENDEL) — editing the Hypothesis title and
    // saving, exactly as e2e/workshop.spec.ts's own stale-edit scenario
    // does.
    // (Note: this page's MENDEL panel legitimately renders its own
    // ".form-error"-classed notices for every ALREADY-stale proposal
    // card, unrelated to this save — so, unlike e2e/workshop.spec.ts's
    // own stale-edit scenario, this test checks the save succeeded via
    // the saved value itself rather than a page-wide ".form-error" count.)
    const titleField = page.getByLabel("Title");
    const newTitle = "Simple close-above-level long (MENDEL stale-proof edit)";
    await titleField.fill(newTitle);
    await page.getByRole("button", { name: "Save hypothesis" }).click();
    await expect(page.getByText(/NOT saved and the draft was NOT overwritten/)).toHaveCount(0);
    await expect(titleField).toHaveValue(newTitle);

    // The second PARAMETER_CHANGE proposal, generated against the NOW-
    // superseded revision, must display as STALE — with its Accept
    // control disabled, never silently still clickable.
    await expect(secondParamCard.locator(".workshop-badge--mendel-status-stale")).toBeVisible();
    await expect(secondParamCard.getByRole("button", { name: "Accept" })).toBeDisabled();
    await secondParamCard.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${DIR}/mendel-05-proposal-stale-accept-disabled.png`, fullPage: true });
  });
});

// PID-004C CLOSURE HARDENING item 1 -- real SCOUT-Discovery-rooted
// vertical slice, browser layer. Every OTHER test above opens against
// `mendel_workshop_id` -- a bare StrategyCandidate/Workshop with no SCOUT
// Discovery linked at all. THIS block opens a Workshop LIVE, through the
// real "Open Workshop" click on a real Discovery page (mirrors
// e2e/workshop.spec.ts's own scenario-1 discipline exactly: the discovery
// alone is pre-seeded by seed.py; the candidate/Workshop are created live
// via the real API during the test, never pre-seeded or constructed
// client-side), then shows -- through the real UI, reusing the existing
// SourcePanel/SpecificationPanel components (PID-004B's own, never a new
// component built for this) -- the real raw SCOUT source text ("XAUUSD")
// and the draft's separately-governed canonical instrument applicability
// ("XAU_USD") as two visually distinct facts, never one derived from the
// other. A live MENDEL invocation against this exact real, SCOUT-linked
// Workshop then proves the whole chain runs end to end through the real
// UI, not just the backend integration suite.
test.describe("PID-004C item 1 — real SCOUT-linked MENDEL vertical slice (browser)", () => {
  test.skip(
    !MENDEL_SCOUT_DISCOVERY_ID,
    "MENDEL+SCOUT discovery fixture id was not exported (DARWIN_E2E_WORKSHOP_MENDEL_SCOUT_DISCOVERY_ID).",
  );

  test("opens live from a real XAUUSD Discovery, shows raw source text distinct from canonical instrument applicability, then a live MENDEL invocation runs against it", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 1100 });

    const beforeDiscoveryResp = await page.request.get(`/api/v1/scout/discoveries/${MENDEL_SCOUT_DISCOVERY_ID}`);
    const beforeDiscovery = (await beforeDiscoveryResp.json()).discovery;
    expect(beforeDiscovery.source_symbol).toBe("XAUUSD");

    // Real Discovery page -> real "Open Workshop" click -> a genuinely
    // new candidate+Workshop, created live via the real API, linked to
    // this real Discovery (never pre-seeded).
    await page.goto(`/discovery/${MENDEL_SCOUT_DISCOVERY_ID}`);
    await expect(page.getByRole("heading", { name: "E2E MENDEL+SCOUT Source — XAUUSD Range Break" })).toBeVisible();
    await page.getByRole("button", { name: "Open Workshop" }).click();
    await expect(page).toHaveURL(/\/workshops\/[a-f0-9-]+$/);
    const scoutMendelWorkshopId = page.url().split("/workshops/")[1];

    // --- The SOURCE panel shows the real, raw, uninterpreted SCOUT
    // source text -- "XAUUSD" -- explicitly labelled as such.
    await expect(page.locator(".workshop-raw-symbol", { hasText: "XAUUSD" })).toBeVisible();
    await page.screenshot({ path: `${DIR}/mendel-06-scout-source-raw-symbol.png`, fullPage: true });

    // --- Set the draft's CANONICAL instrument applicability through the
    // real authoring UI (PID-004B: never client-side-only) -- a
    // deliberately DIFFERENT, separately-governed value ("XAU_USD") from
    // the raw source string ("XAUUSD") above, never auto-derived from it.
    await page.locator('option[value="XAU_USD"]').first().waitFor({ state: "attached" });
    await page.getByLabel("Instrument", { exact: false }).selectOption("XAU_USD");
    await page.getByRole("button", { name: "Save specification" }).click();

    // Both facts visible on the SAME page, at the SAME time, as two
    // distinct DOM elements -- the raw source symbol never changed to
    // match the canonical id, and vice versa.
    await expect(page.locator(".workshop-raw-symbol", { hasText: "XAUUSD" })).toBeVisible();
    await expect(page.getByLabel("Instrument", { exact: false })).toHaveValue("XAU_USD");
    await page.screenshot({ path: `${DIR}/mendel-07-raw-symbol-vs-canonical-applicability.png`, fullPage: true });

    // --- A live MENDEL invocation against this exact real, SCOUT-linked
    // Workshop -- proving the full chain (real Discovery -> real
    // Workshop -> real MENDEL invoke) runs end to end through the real UI.
    await expect(page.getByRole("heading", { name: /MENDEL Assistant/ })).toBeVisible();
    await page.getByRole("button", { name: "Invoke MENDEL" }).click();
    await expect(page.locator(".mendel-reasoning-summary")).toBeVisible();
    await expect(page.locator(".mendel-proposal-list li").first()).toBeVisible();
    await page.screenshot({ path: `${DIR}/mendel-08-scout-linked-invocation-succeeded.png`, fullPage: true });

    // --- No source mutation: the underlying SCOUT discovery row is
    // genuinely untouched by any of the above.
    const afterDiscoveryResp = await page.request.get(`/api/v1/scout/discoveries/${MENDEL_SCOUT_DISCOVERY_ID}`);
    const afterDiscovery = (await afterDiscoveryResp.json()).discovery;
    expect(afterDiscovery).toEqual(beforeDiscovery);

    // Sanity: this really is a fresh Workshop, not the pre-seeded
    // `mendel_workshop_id` fixture the tests above use.
    expect(scoutMendelWorkshopId).not.toBe(MENDEL_WORKSHOP_ID);
  });
});
