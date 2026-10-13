import { defineConfig, devices } from "@playwright/test";

process.env.E2E_API_BASE_URL = "http://127.0.0.1:18080/api/v1/";

export default defineConfig({
  testDir: "./e2e-real",
  testIgnore: [
    "docker-environment.ts",
    "global-teardown.ts",
    "prod-docker-environment.ts",
    "global-teardown-prod.ts",
  ],
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  globalSetup: "./e2e-real/prod-docker-environment.ts",
  globalTeardown: "./e2e-real/global-teardown-prod.ts",
  reporter: process.env.CI ? [["html", { open: "never" }], ["github"]] : "list",
  use: {
    baseURL: "http://127.0.0.1:18080",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-production-postgresql",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
