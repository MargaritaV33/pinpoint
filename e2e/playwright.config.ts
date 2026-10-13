import { defineConfig, devices } from "@playwright/test";

// Matches docker-compose.yaml's APP_PORT:-8100 default; overridable the same
// way `make up` is (`APP_PORT=... make up`).
const appPort = process.env.APP_PORT ?? "8100";

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: {
    timeout: 10_000,
  },
  // Two spec files, each driving the one shared compose stack through real
  // browser contexts; serial execution keeps failures legible and avoids
  // tuning parallelism for a two-test suite.
  workers: 1,
  fullyParallel: false,
  // Deterministic, no CI involved yet (#11).
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: `http://localhost:${appPort}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
