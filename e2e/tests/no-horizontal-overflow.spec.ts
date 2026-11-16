/**
 * No horizontal page scroll at phone, window-minimum and desktop widths, and
 * no zone title clipped by its action in a long-label locale.
 *
 * BR-18: at 390 px every route overflowed by ~30 px because the header's
 * title was `white-space: nowrap` inside a column narrower than logo + title.
 * BR-09: in German the Quotes zone title "Abschnitte" (one word, cannot wrap)
 * was clipped by its segmented control below ~540 px.
 */
import { test, expect } from '@playwright/test';
import { discoverSessionRoutes } from '../fixtures/routes';

const ROUTES = [
  '/report/',
  '/report/sessions/',
  '/report/quotes/',
  '/report/codebook/',
  '/report/signals/',
  '/report/discussion/',
];
const WIDTHS = [390, 720, 1280];

for (const width of WIDTHS) {
  test(`no horizontal overflow at ${width}px`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 900 });
    const routes = [...ROUTES, ...(await discoverSessionRoutes(baseURL!)).slice(0, 1)];
    const over: string[] = [];
    for (const path of routes) {
      await page.goto(path);
      await page.waitForLoadState('load');
      await page.waitForSelector('.report-header');
      const px = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      if (px > 0) over.push(`${path}: ${px}px`);
    }
    expect(over).toEqual([]);
  });
}

test('German Quotes zone titles are not clipped by their control at 520px', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('bn-locale', 'de'));
  await page.setViewportSize({ width: 520, height: 900 });
  await page.goto('/report/quotes/');
  await page.waitForSelector('.section-heading h1');
  const clipped = await page.evaluate(() =>
    [...document.querySelectorAll('.section-heading h1')]
      .filter((h) => h.scrollWidth > h.clientWidth)
      .map((h) => h.textContent),
  );
  expect(clipped).toEqual([]);
});
