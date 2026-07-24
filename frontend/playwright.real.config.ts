import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-real",
  testIgnore: ["docker-environment.ts", "global-teardown.ts"],
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  globalSetup: "./e2e-real/docker-environment.ts",
  globalTeardown: "./e2e-real/global-teardown.ts",
  reporter: process.env.CI ? [["html", { open: "never" }], ["github"]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4174",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-postgresql",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --port 4174",
    env: {
      VITE_API_PROXY_TARGET: "http://127.0.0.1:18000",
    },
    url: "http://127.0.0.1:4174",
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
