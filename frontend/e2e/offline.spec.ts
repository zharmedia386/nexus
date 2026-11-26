import { expect, test } from "@playwright/test";
import { shoot } from "./helpers";

const ROUTES = ["/", "/how-it-works", "/benchmarks", "/docs"];

for (const route of ROUTES) {
  test(`${route} renders with every other host unreachable`, async ({ page, baseURL }, testInfo) => {
    const origin = new URL(baseURL ?? "http://localhost:3000").origin;
    const foreign: string[] = [];
    await page.route("**/*", (handled) => {
      const url = handled.request().url();
      if (new URL(url).origin === origin || url.startsWith("data:")) return handled.continue();
      foreign.push(url);
      return handled.abort();
    });
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(foreign).toEqual([]);
    // The landing shot comes from app.spec; content pages are shot here, offline.
    if (route !== "/") await shoot(page, testInfo.project.name, route.slice(1), "main");
  });
}
