import { defineConfig, devices } from "@playwright/test";

const MOTION_SPEC = /motion\.spec\.ts/;
const PORT = Number(process.env.PORT ?? 3000);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 240_000,
  retries: process.env.CI ? 2 : 0,
  use: { baseURL: process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`, trace: "on-first-retry" },
  projects: [
    { name: "desktop-light", testIgnore: MOTION_SPEC, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, colorScheme: "light" } },
    { name: "desktop-dark", testIgnore: MOTION_SPEC, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, colorScheme: "dark" } },
    { name: "mobile", testIgnore: MOTION_SPEC, use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 }, colorScheme: "light" } },
    // Only the motion assertion runs here; everything else is covered by the other projects.
    { name: "reduced-motion", testMatch: /motion\.spec\.ts/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" } },
  ],
  webServer: {
    command: `npm run start -- --port ${PORT}`,
    port: PORT,
    reuseExistingServer: !process.env.CI,
  },
});
