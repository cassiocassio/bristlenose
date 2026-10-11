/**
 * Every lens at Windows display scaling.
 *
 * Windows laptops usually run at 125% or 150%. A 1920×1080 panel then gives the
 * page a 1536×864 CSS viewport at devicePixelRatio 1.25, or 1280×720 at 1.5 — the
 * smallest common desktop viewport, and fractional ratios a Mac never uses. This
 * emulates both in Chromium (Edge is Chromium) and asserts each lens mounts and
 * does not scroll sideways. A screenshot of each is attached to the report for a
 * human to look at: fonts and hairlines need eyes, not assertions. Real Windows
 * rendering (ClearType, Segoe fallback) is the VM harness's job
 * (packaging/windows/vbox-test.sh, docs/release-winget.md).
 */
import { test, expect, Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

function authToken(): string {
  return process.env._BRISTLENOSE_AUTH_TOKEN ?? 'test-token';
}

// Copied from lenses-load-clean.spec.ts: networkidle alone is fragile.
async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(
    () => {
      const root = document.querySelector('#bn-app-root');
      return !!(root && root.children.length > 0);
    },
    { timeout: 5_000 },
  );
  await page.waitForFunction(
    () => {
      const current = document.querySelectorAll('*').length;
      const prev = (window as unknown as { __prevDomCount?: number }).__prevDomCount;
      (window as unknown as { __prevDomCount?: number }).__prevDomCount = current;
      return prev !== undefined && prev === current;
    },
    { timeout: 5_000, polling: 200 },
  );
}

const LENSES = [
  { path: '/report/', label: 'dashboard' },
  { path: '/report/sessions/', label: 'sessions' },
  { path: '/report/quotes/', label: 'quotes' },
  { path: '/report/codebook/', label: 'codebook' },
  { path: '/report/signals/', label: 'signals' },
];

const SCALINGS = [
  { name: '125%', width: 1536, height: 864, deviceScaleFactor: 1.25 },
  { name: '150%', width: 1280, height: 720, deviceScaleFactor: 1.5 },
];

test.skip(({ browserName }) => browserName !== 'chromium', 'Edge is Chromium; WebKit has no Windows');

test('server identity guard — smoke-test fixture', async ({ page, baseURL }) => {
  const res = await page.request.get(`${baseURL}/api/projects/1/info`, {
    headers: { Authorization: `Bearer ${authToken()}` },
  });
  expect(res.ok()).toBe(true);
  expect((await res.json()).project_name).toBe('Smoke Test');
});

for (const s of SCALINGS) {
  for (const lens of LENSES) {
    test(`${lens.label} at ${s.name} (${s.width}×${s.height} @${s.deviceScaleFactor})`, async ({ browser, baseURL }, testInfo) => {
      const context = await browser.newContext({
        baseURL,
        viewport: { width: s.width, height: s.height },
        deviceScaleFactor: s.deviceScaleFactor,
      });
      try {
        const page = await context.newPage();
        await page.goto(lens.path);
        await waitForPageReady(page);

        // The whole page must not scroll sideways: a horizontal scrollbar at 150% is
        // the first thing a Windows laptop user would see go wrong.
        const overflow = await page.evaluate(() => {
          const el = document.scrollingElement ?? document.documentElement;
          return { scrollWidth: el.scrollWidth, clientWidth: el.clientWidth };
        });
        expect(
          overflow.scrollWidth,
          `${lens.path} is ${overflow.scrollWidth - overflow.clientWidth}px wider than the ${s.name} viewport`,
        ).toBeLessThanOrEqual(overflow.clientWidth + 1);

        await testInfo.attach(`${lens.label}-${s.name}.png`, {
          body: await page.screenshot(),
          contentType: 'image/png',
        });
      } finally {
        await context.close();
      }
    });
  }
}
