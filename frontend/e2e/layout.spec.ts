import { expect, test } from "@playwright/test";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STATIC_ROUTES = ["/", "/ask", "/how-it-works", "/benchmarks", "/docs"];
const API_ROUTES = ["/explore", "/themes", "/eval"];

test.use({ viewport: { width: 375, height: 812 } });

const checkFits = async (page: import("@playwright/test").Page, route: string) => {
  await page.goto(route);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  await expect(page.getByRole("contentinfo")).toBeVisible();
};

for (const route of STATIC_ROUTES) {
  test(`${route} fits 375px and shows the footer`, async ({ page }) => checkFits(page, route));
}

for (const route of API_ROUTES) {
  test(`${route} fits 375px and shows the footer`, async ({ page, request }) => {
    const healthy = await request.get(`${API_URL}/health`).then((response) => response.ok(), () => false);
    test.skip(!healthy, `API health check failed at ${API_URL}/health; start the backend to check ${route}.`);
    await checkFits(page, route);
  });
}
