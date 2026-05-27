import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:80";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  retries: 0,
  use: {
    baseURL,
    ...devices["Desktop Chrome"],
    headless: true,
    viewport: { width: 1440, height: 900 },
  },
  projects: [{ name: "chromium" }],
});
