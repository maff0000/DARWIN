import { test, expect } from "@playwright/test";

// Coverage for the three PID-002 shell refinement fixes: (1) the sidebar
// must never obscure content at any width, (2) the rail is a real
// collapsible control (persisted, keyboard-accessible, tooltip'd,
// reduced-motion-safe), (3) nav items use real icons rather than dots.

test.describe("shell refinement — collapse persistence + accessibility", () => {
  test("collapse state persists across reload via localStorage", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Collapse navigation" })).toBeVisible();

    await page.getByRole("button", { name: "Collapse navigation" }).click();
    await expect(page.getByRole("button", { name: "Expand navigation" })).toBeVisible();

    const stored = await page.evaluate(() => window.localStorage.getItem("arena.leftNav.collapsed"));
    expect(stored).toBe("1");

    await page.reload();
    await expect(page.getByRole("button", { name: "Expand navigation" })).toBeVisible();
    await expect(page.locator(".left-nav")).toHaveClass(/left-nav--collapsed/);

    // and it un-persists cleanly
    await page.getByRole("button", { name: "Expand navigation" }).click();
    await page.reload();
    await expect(page.getByRole("button", { name: "Collapse navigation" })).toBeVisible();
  });

  test("every nav item is reachable and activatable by keyboard while collapsed", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Collapse navigation" }).click();
    await expect(page.locator(".left-nav")).toHaveClass(/left-nav--collapsed/);

    // Tab from the toggle button through to the nav links in DOM order
    // (Overview, then Datasets), then activate one with the keyboard
    // alone — no click.
    await page.getByRole("button", { name: "Expand navigation" }).focus();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Overview" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Datasets" })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/datasets$/);

    // every configured item still exposes an accessible name and is
    // individually focusable, even though its visible label is hidden.
    for (const name of ["Overview", "Datasets", "Research Runs", "Evidence", "Pipeline", "System Status", "HERMES", "Migrations"]) {
      const link = page.getByRole("link", { name });
      await expect(link).toBeVisible();
      await link.focus();
      await expect(link).toBeFocused();
    }
  });

  test("hover and keyboard focus show the nav label as a tooltip while collapsed", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Collapse navigation" }).click();

    const runsLink = page.getByRole("link", { name: "Research Runs" });
    await expect(page.locator(".left-nav__tooltip")).toHaveCount(0);

    await runsLink.hover();
    await expect(page.locator(".left-nav__tooltip")).toHaveText("Research Runs");

    await page.mouse.move(600, 600);
    await expect(page.locator(".left-nav__tooltip")).toHaveCount(0);

    await runsLink.focus();
    await expect(page.locator(".left-nav__tooltip")).toHaveText("Research Runs");

    // tooltip never appears while expanded (label is already on screen)
    await page.getByRole("button", { name: "Expand navigation" }).click();
    await runsLink.hover();
    await expect(page.locator(".left-nav__tooltip")).toHaveCount(0);
  });

  test("collapse toggle and every nav icon-button expose an accessible name", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Collapse navigation" })).toHaveAttribute("aria-label", "Collapse navigation");
    await page.getByRole("button", { name: "Collapse navigation" }).click();
    await expect(page.getByRole("button", { name: "Expand navigation" })).toHaveAttribute("aria-label", "Expand navigation");

    // nav items render real SVG icons, not the old decorative dot
    await expect(page.locator(".left-nav__dot")).toHaveCount(0);
    await expect(page.locator(".left-nav__icon").first()).toBeVisible();
    const tag = await page.locator(".left-nav__icon").first().evaluate((el) => el.tagName.toLowerCase());
    expect(tag).toBe("svg");
  });

  test("active route stays visually identifiable in both expanded and collapsed states", async ({ page }) => {
    await page.goto("/datasets");
    const activeLink = page.locator(".left-nav__link--active");
    await expect(activeLink).toHaveAttribute("href", "/datasets");
    const expandedColor = await activeLink.locator(".left-nav__icon").evaluate((el) => getComputedStyle(el).color);

    await page.getByRole("button", { name: "Collapse navigation" }).click();
    await expect(page.locator(".left-nav--collapsed .left-nav__link--active")).toHaveAttribute("href", "/datasets");
    const collapsedColor = await page
      .locator(".left-nav--collapsed .left-nav__link--active .left-nav__icon")
      .evaluate((el) => getComputedStyle(el).color);
    // active-state cue (icon accent colour) survives the collapse, it does
    // not depend on the label text that disappears when collapsed.
    expect(collapsedColor).toBe(expandedColor);
  });

  test("respects prefers-reduced-motion for the collapse transition", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    const duration = await page.locator(".left-nav").evaluate((el) => getComputedStyle(el).transitionDuration);
    // tokens.css collapses every transition-duration to 0.001ms under
    // prefers-reduced-motion — assert it actually landed on this element
    // (browsers may serialise that as "0.001ms", "1e-06s", etc.), not just
    // declared globally, and that it is nowhere near the normal 150ms.
    const seconds = duration.endsWith("ms")
      ? parseFloat(duration) / 1000
      : parseFloat(duration);
    expect(seconds).toBeLessThan(0.001);
  });
});

test.describe("shell refinement — sidebar never obscures content", () => {
  test("dataset detail content stays fully clear of the rail across a live resize, expanded and collapsed", async ({ page }) => {
    await page.goto("/datasets");
    await page.getByRole("cell", { name: "XAU_USD" }).first().locator("a").click();
    await expect(page).toHaveURL(/\/datasets\/[a-f0-9-]+$/);

    const rail = page.locator(".left-nav");
    const panel = page.locator(".panel").first();

    async function assertNoOverlap() {
      const railBox = await rail.boundingBox();
      const panelBox = await panel.boundingBox();
      expect(railBox).not.toBeNull();
      expect(panelBox).not.toBeNull();
      if (railBox && panelBox) {
        // the panel's left edge must sit at or after the rail's right edge —
        // i.e. never underneath it — at every width sampled below.
        expect(panelBox.x).toBeGreaterThanOrEqual(railBox.x + railBox.width - 1);
      }
    }

    // sweep through wide desktop -> narrow desktop -> medium, expanded rail
    for (const width of [1600, 1440, 1280, 1180, 1100, 1024]) {
      await page.setViewportSize({ width, height: 900 });
      await assertNoOverlap();
    }

    // same sweep with the rail collapsed — wait for the (restrained, 150ms)
    // collapse width transition to settle before measuring; the resize
    // sweep itself is what proves the "live resize" requirement, this just
    // avoids asserting mid-animation on the toggle click that precedes it.
    await page.getByRole("button", { name: "Collapse navigation" }).click();
    await page.waitForTimeout(300);
    for (const width of [1024, 1100, 1180, 1280, 1440, 1600]) {
      await page.setViewportSize({ width, height: 900 });
      await assertNoOverlap();
    }

    // no page-level horizontal scrollbar at the narrowest width tested
    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
  });

  test("run detail content stays fully clear of the rail across a live resize", async ({ page }) => {
    await page.goto("/runs");
    await page.locator(".data-table tbody tr").first().locator("a").click();
    await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+$/);

    const rail = page.locator(".left-nav");
    const panel = page.locator(".panel").first();

    for (const width of [1600, 1280, 1100, 1024]) {
      await page.setViewportSize({ width, height: 900 });
      const railBox = await rail.boundingBox();
      const panelBox = await panel.boundingBox();
      if (railBox && panelBox) {
        expect(panelBox.x).toBeGreaterThanOrEqual(railBox.x + railBox.width - 1);
      }
    }
  });
});
