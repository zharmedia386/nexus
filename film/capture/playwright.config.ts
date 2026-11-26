import { defineConfig } from "@playwright/test";

// Run from frontend/ with NODE_PATH=frontend/node_modules (see film/README.md). Video is 1x CSS px: Playwright screencasts at viewport size, so 2x detail comes from the screenshots.
export default defineConfig({
  testDir: ".",
  testMatch: /beats\.spec\.ts/,
  outputDir: "./raw/results",
  fullyParallel: false,
  workers: 1,
  timeout: 240_000,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: process.env.FILM_BASE_URL ?? "http://localhost:3000",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2,
    colorScheme: "dark",
    video: { mode: "on", size: { width: 1920, height: 1080 } },
  },
});
