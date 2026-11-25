import { test as base, expect, type Locator, type Page } from "@playwright/test";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SHOTS_DIR = "../docs/screenshots";

export const test = base.extend({
  // Skips the spec with a clear reason when the backend is unreachable.
  page: async ({ page, request }, provide) => {
    const healthy = await request.get(`${API_URL}/health`).then((response) => response.ok(), () => false);
    test.skip(!healthy, `API health check failed at ${API_URL}/health; start the backend before running e2e.`);
    await provide(page);
  },
});

export { expect };

// Viewport shot with the section scrolled to its top; names are stable per project.
// Fixed nav height plus breathing room, so the first heading is never under the nav.
const NAV_CLEARANCE = 104;

export async function shoot(page: Page, project: string, section: string, anchor = `#${section}`) {
  await page.locator(anchor).first().evaluate((element, clearance) => {
    element.scrollIntoView({ block: "start", behavior: "instant" });
    window.scrollBy(0, -clearance);
  }, NAV_CLEARANCE);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${SHOTS_DIR}/${project}-${section}.jpg`, type: "jpeg", quality: 80 });
}

// Element shot with the fixed nav hidden so it cannot overlap the frame.
export async function shootElement(page: Page, project: string, section: string, target: Locator) {
  const nav = page.locator("header, nav").first();
  await target.scrollIntoViewIfNeeded();
  await page.addStyleTag({ content: "[data-shot-hide]{visibility:hidden!important}" });
  await nav.evaluate((element) => element.setAttribute("data-shot-hide", ""));
  await target.screenshot({ path: `${SHOTS_DIR}/${project}-${section}.jpg`, type: "jpeg", quality: 80 });
  await nav.evaluate((element) => element.removeAttribute("data-shot-hide"));
}

// Interactive controls that expose no accessible name.
export async function unnamedControls(page: Page) {
  return page.evaluate(() => {
    const selector = 'button, a[href], input:not([type="hidden"]), select, textarea, [role="button"], [role="tab"], [role="combobox"], [role="option"]';
    const visible = (element: Element) => {
      const rect = element.getBoundingClientRect();
      return element.closest("[hidden]") === null && getComputedStyle(element).visibility !== "hidden" && (rect.width > 0 || rect.height > 0 || element.matches(".sr-only"));
    };
    const nameOf = (element: Element): string => {
      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy) return labelledBy.split(" ").map((id) => document.getElementById(id)?.textContent ?? "").join(" ").trim();
      const direct = element.getAttribute("aria-label") ?? element.getAttribute("title");
      if (direct?.trim()) return direct.trim();
      const labels = (element as HTMLInputElement).labels;
      if (labels?.length) return [...labels].map((label) => label.textContent).join(" ").trim();
      return (element.textContent ?? "").trim();
    };
    return [...document.querySelectorAll(selector)].filter(visible).filter((element) => !nameOf(element)).map((element) => element.outerHTML.slice(0, 160));
  });
}

// Mounts every lazy section so audits see the whole page.
export async function loadAllSections(page: Page) {
  for (const id of ["ask", "explore", "themes", "eval"]) {
    await page.locator(`#${id}`).evaluate((element) => element.scrollIntoView({ behavior: "instant", block: "start" }));
    await page.waitForTimeout(300);
  }
}
