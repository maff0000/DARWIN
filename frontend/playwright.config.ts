import { defineConfig } from "@playwright/test";

// Acceptance browser tests run against the REAL ARENA bundle -> real
// DARWIN_core -> real API -> disposable PostgreSQL (PID-002 §16/§18). This
// config never starts its own server — the test harness (scripts/run-e2e.sh
// or CI) is responsible for a real DARWIN_core container already listening
// on DARWIN_E2E_BASE_URL before Playwright runs.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: process.env.DARWIN_E2E_BASE_URL ?? "http://localhost:8000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
