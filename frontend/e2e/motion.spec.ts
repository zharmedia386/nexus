import { expect, test } from "@playwright/test";

test("reduced motion: no running animations after load", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1500);
  const running = () => page.evaluate(() => document.getAnimations().filter((animation) => animation.playState === "running").map((animation) => animation.id || String((animation.effect as KeyframeEffect | null)?.target?.className)));
  expect(await running()).toEqual([]);
});

test("reduced motion: walkthrough steps sit in their end state after a full scroll", async ({ page }) => {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y <= height; y += 400) await page.evaluate((top) => window.scrollTo(0, top), y);
  await page.waitForTimeout(1000);
  expect(await page.evaluate(() => document.getAnimations().filter((animation) => animation.playState === "running").length)).toBe(0);
  const steps = page.locator("[data-walkthrough-step]");
  await expect(steps).toHaveCount(3);
  for (const step of await steps.all()) {
    await expect(step).toBeVisible();
    expect(await step.evaluate((element) => getComputedStyle(element).opacity)).toBe("1");
  }
});
