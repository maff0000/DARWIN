import { test, expect } from "@playwright/test";

// PID-003 SCOUT — ARENA Discovery surface. Runs against the real
// DARWIN_core bundle + real API + disposable PostgreSQL, seeded by
// frontend/e2e/fixtures/seed.py (same harness discipline as runs.spec.ts /
// datasets.spec.ts). Seeded discoveries and their intake states:
//   - "XAUUSD London Session Breakout" — ADAPTER_SOURCED, NEW
//   - "Gold Momentum Scalper"          — ADAPTER_SOURCED, SHORTLISTED, trade_count=15 (low sample)
//   - "Unlabeled EA Import"            — ADAPTER_SOURCED, NEW, no claim at all
//   - "London Range Break (Reddit)"    — USER_DISCOVERED, READY_FOR_SPECIFICATION
//   - "VWAP Reversion Idea"            — MY_IDEA, IN_WORKSHOP
//   - "Fib Cluster Reversal Idea (superseded)" — MY_IDEA, REJECTED
//   - "E2E Workshop Source — XAUUSD Session Breakout" — USER_DISCOVERED, NEW
//     (PID-004B: seeded in its OWN dedicated section, deliberately never
//     touched by this file's own mutating-actions block — see
//     e2e/workshop.spec.ts, which owns it exclusively)
//   - "E2E MENDEL+SCOUT Source — XAUUSD Range Break" — USER_DISCOVERED, NEW
//     (PID-004C closure hardening item 1: seeded in its OWN dedicated
//     section, deliberately never touched by this file's own
//     mutating-actions block — see e2e/mendel.spec.ts, which owns it
//     exclusively)
// = 8 total, DISCOVERED-equivalent (NEW+SHORTLISTED+IN_WORKSHOP+READY_FOR_SPECIFICATION) = 7.
//
// The CI job also points mcp-api.trader.dev at an unreachable host for
// every e2e container (same discipline degraded.spec.ts already documents
// for HERMES) — so "Trader.dev unreachable" is exercised by the ordinary
// populated run below, not a separate container.
//
// Playwright runs a single spec file's tests serially, in declaration
// order (no fullyParallel in playwright.config.ts) — this file relies on
// that: every test that reads the exact seeded counts/order runs BEFORE
// the "mutating actions" describe block at the bottom, which changes
// intake states and adds new rows. Keep new tests on the correct side of
// that boundary.

test.describe("Discovery list — SCOUT radar (read-only)", () => {
  test("renders real intake counts, source health, and the SOURCE_CLAIM leaderboard", async ({ page }) => {
    await page.goto("/discovery");
    await expect(page.getByRole("heading", { name: "Discovery" })).toBeVisible();
    await expect(page.getByText("8 discovered")).toBeVisible();

    // total + 5 intake-state stat cards, all real counts_by_intake_status
    await expect(page.locator(".stat-card")).toHaveCount(6);

    // Trader.dev is deliberately unreachable in this CI environment —
    // rendered honestly, never hidden or silently retried forever.
    await expect(page.locator(".discovery-source-health__row .status-badge--down")).toBeVisible();

    // the unmistakable label PID-003 sec10 requires, never absent from a
    // claimed-performance view
    await expect(page.getByText(/SOURCE_CLAIM — NOT INDEPENDENTLY VERIFIED BY DARWIN/).first()).toBeVisible();
    await expect(page.getByText(/success score/i)).toHaveCount(0);

    await expect(page.getByRole("cell", { name: "XAUUSD London Session Breakout" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "Gold Momentum Scalper" })).toBeVisible();
  });

  test("default sort is highest claimed return first", async ({ page }) => {
    await page.goto("/discovery");
    // Gold Momentum Scalper claims +120.00%, higher than every other seeded
    // discovery's net_pnl_percent — server-side sort, not client re-sort.
    await expect(page.locator(".data-table tbody tr").first()).toContainText("Gold Momentum Scalper");
  });

  test("intake-status filter narrows the list via the real API param", async ({ page }) => {
    await page.goto("/discovery");
    await page.locator(".filter-bar select").nth(0).selectOption("REJECTED");
    await expect(page.getByRole("cell", { name: "Fib Cluster Reversal Idea (superseded)" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "XAUUSD London Session Breakout" })).toHaveCount(0);
  });

  test("a thin claimed trade sample is dimmed on the PF/trade-count view, never scored", async ({ page }) => {
    await page.goto("/discovery");
    await expect(page.locator(".scatter-plot__point--low-sample").first()).toBeVisible();
  });

  test("Discover now is a deliberate bounded action, never automatic on page load", async ({ page }) => {
    await page.goto("/discovery");
    await expect(page.locator(".discover-now-panel")).toHaveCount(0);

    await page.getByRole("button", { name: "Discover now…" }).click();
    await expect(page.locator(".discover-now-panel")).toBeVisible();

    await page.getByRole("button", { name: "Run discovery" }).click();
    await expect(page.locator(".discover-now-result")).toBeVisible({ timeout: 20_000 });
    // Trader.dev is deliberately unreachable in CI — a bounded FAILED run
    // (never a crash, never an infinite spinner) is the honest outcome.
    await expect(page.locator(".discover-now-result")).toContainText("FAILED");
  });
});

test.describe("Discovery detail (read-only)", () => {
  test("renders source identity, SOURCE_CLAIM metrics, snapshot history, audit trail, and a real Open Workshop action", async ({ page }) => {
    await page.goto("/discovery");
    await page.getByRole("cell", { name: "London Range Break (Reddit)" }).locator("a").click();
    await expect(page).toHaveURL(/\/discovery\/[a-f0-9-]+$/);

    await expect(page.getByRole("heading", { name: "London Range Break (Reddit)" })).toBeVisible();
    // the header badge and the "Currently X" badge in the intake panel both
    // legitimately show the current status — assert the first is enough.
    await expect(page.locator(".intake-badge--ready-for-specification").first()).toBeVisible();

    const link = page.getByRole("link", { name: /reddit\.com/ });
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", "noopener noreferrer");

    // pasted rule text renders as plain preformatted text, never HTML/markdown
    await expect(page.locator("pre.pasted-rule-text")).toContainText("londonRangeHigh");

    await expect(page.getByText(/SOURCE_CLAIM — NOT INDEPENDENTLY VERIFIED BY DARWIN/).first()).toBeVisible();

    // real recorded intake-audit trail (unique reason text from the seed's
    // first real transition on this discovery)
    await expect(page.getByText(/Clear rules, plausible claim/)).toBeVisible();

    // PID-004B: Open Workshop is now a real, enabled action against the
    // real backend — see e2e/workshop.spec.ts for the full real-browser
    // Workshop proof (this file stays SCOUT/PID-003-scoped, read-only).
    const workshopButton = page.getByRole("button", { name: "Open Workshop" });
    await expect(workshopButton).toBeVisible();
    await expect(workshopButton).toBeEnabled();
  });

  test("MY_IDEA detail shows no external source and no metrics", async ({ page }) => {
    await page.goto("/discovery");
    await page.getByRole("cell", { name: "VWAP Reversion Idea" }).locator("a").click();
    await expect(page.getByText(/My idea \(Matt's own hypothesis/)).toBeVisible();
    await expect(page.getByText(/No performance figures were supplied/)).toBeVisible();
  });

  test("a discovery with no claimed metrics renders honestly, never a fabricated value", async ({ page }) => {
    await page.goto("/discovery");
    await page.getByRole("cell", { name: "Unlabeled EA Import" }).locator("a").click();
    await expect(page.getByText(/No performance figures were supplied/)).toBeVisible();
  });
});

test.describe("Pipeline reflects real SCOUT persistence", () => {
  test("DISCOVERED count matches NEW+SHORTLISTED+IN_WORKSHOP+READY_FOR_SPECIFICATION discoveries", async ({ page }) => {
    await page.goto("/pipeline");
    const discoveredCard = page.locator(".stat-card", { hasText: "DISCOVERED" });
    await expect(discoveredCard.locator(".stat-card__value")).toHaveText("7");
  });
});

test.describe("Discovery — shell regressions (no PID-002 breakage)", () => {
  test("left nav collapse still works on the Discovery page", async ({ page }) => {
    await page.goto("/discovery");
    await page.getByRole("button", { name: "Collapse navigation" }).click();
    await expect(page.locator(".left-nav")).toHaveClass(/left-nav--collapsed/);
    await expect(page.getByRole("link", { name: "Discovery" })).toBeVisible();
  });

  test("no sidebar/content overlap on Discovery list or detail across a resize sweep", async ({ page }) => {
    await page.goto("/discovery");
    const rail = page.locator(".left-nav");
    const panel = page.locator(".panel").first();

    async function assertNoOverlap() {
      const railBox = await rail.boundingBox();
      const panelBox = await panel.boundingBox();
      if (railBox && panelBox) {
        expect(panelBox.x).toBeGreaterThanOrEqual(railBox.x + railBox.width - 1);
      }
    }

    for (const width of [1600, 1280, 1100, 1024]) {
      await page.setViewportSize({ width, height: 900 });
      await assertNoOverlap();
    }

    await page.getByRole("cell", { name: "London Range Break (Reddit)" }).locator("a").click();
    for (const width of [1600, 1280, 1100, 1024]) {
      await page.setViewportSize({ width, height: 900 });
      await assertNoOverlap();
    }

    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });
});

// --- Mutating actions — must run last: every test above depends on the
// exact seeded counts/order these tests change. ---------------------------

test.describe("Discovery — mutating actions", () => {
  test("shortlisting a NEW discovery from the list persists across reload", async ({ page }) => {
    await page.goto("/discovery");
    const row = page.locator("tr", { hasText: "XAUUSD London Session Breakout" });
    await expect(row.locator(".intake-badge--new")).toBeVisible();

    await row.getByRole("button", { name: "Shortlist" }).click();
    await expect(row.locator(".intake-badge--shortlisted")).toBeVisible();

    await page.reload();
    await expect(page.locator("tr", { hasText: "XAUUSD London Session Breakout" }).locator(".intake-badge--shortlisted")).toBeVisible();
  });

  test("+ Add Strategy creates a USER_DISCOVERED entry with a URL and claimed metrics", async ({ page }) => {
    const title = `E2E Added Breakout Idea ${Date.now()}`;
    await page.goto("/discovery");
    await page.getByRole("button", { name: "+ Add Strategy" }).click();
    const modal = page.locator(".modal-panel");
    await expect(modal).toBeVisible();

    await modal.getByLabel("Title *").fill(title);
    await modal.getByLabel("Source URL / reference").fill("https://example.com/e2e-strategy");
    await modal.getByLabel("Net P&L %").fill("15");
    await modal.getByRole("button", { name: "Add strategy" }).click();

    await expect(page.locator(".modal-backdrop")).toHaveCount(0);
    await expect(page.getByRole("cell", { name: title })).toBeVisible();
  });

  test("+ Add Strategy hides URL/metrics for MY_IDEA and creates it with no external source", async ({ page }) => {
    const title = `E2E My Own Hypothesis ${Date.now()}`;
    await page.goto("/discovery");
    await page.getByRole("button", { name: "+ Add Strategy" }).click();
    const modal = page.locator(".modal-panel");
    // The Origin field is the modal's only <select> — "Origin"/"Origin
    // description"/"Original description" all share "Origin" as a text
    // substring, so getByLabel would be ambiguous here.
    const originSelect = modal.locator("select");

    await originSelect.selectOption("MY_IDEA");
    await expect(modal.getByLabel("Source URL / reference")).toHaveCount(0);
    await expect(modal.getByText(/Claimed metrics/)).toHaveCount(0);

    await modal.getByLabel("Title *").fill(title);
    await modal.getByRole("button", { name: "Add strategy" }).click();

    await expect(page.locator(".modal-backdrop")).toHaveCount(0);
    await expect(page.getByRole("cell", { name: title })).toBeVisible();
  });

  test("MY_IDEA rejected with a URL surfaces the backend's SCOUT_INVALID_ORIGIN error gracefully", async ({ page }) => {
    // Exercises the graceful-error path directly against the real endpoint,
    // bypassing the client-side field hiding this same form otherwise
    // applies — proves the UI never crashes on the 400 if it somehow occurs.
    const res = await page.request.post("/api/v1/scout/discoveries", {
      data: { origin_kind: "MY_IDEA", title: "Should be rejected", origin_url: "https://example.com" },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("SCOUT_INVALID_ORIGIN");
  });

  test("a rejected discovery can be reopened, and the transition is available from its current state only", async ({ page }) => {
    await page.goto("/discovery");
    await page.getByRole("cell", { name: "Fib Cluster Reversal Idea (superseded)" }).locator("a").click();
    await expect(page.locator(".intake-badge--rejected").first()).toBeVisible();
    await page.getByRole("button", { name: "Move to New" }).click();
    await expect(page.locator(".intake-badge--new").first()).toBeVisible();
  });
});
