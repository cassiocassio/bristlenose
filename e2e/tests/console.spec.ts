/**
 * Layer 1: Console error monitor.
 *
 * Navigates all routes and asserts no console.error messages appear.
 * Catches: React key warnings, runtime exceptions, failed imports,
 * broken resource loads.
 */
import { test, expect } from '@playwright/test';
import { getAllRoutes } from '../fixtures/routes';

test('no console errors on any route', async ({ page, baseURL }) => {
  const errors: string[] = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      const url = page.url();
      // ci-allowlist: CI-A1 (infra — see e2e/ALLOWLIST.md)
      if (text.includes('favicon')) return;
      // ci-allowlist: CI-A4 (deferred-fix — see e2e/ALLOWLIST.md; tracker: 100days.md §2)
      if (url.includes('/report/codebook') && text.includes('404')) return;
      errors.push(`${url}: ${text}`);
    }
  });

  const routes = await getAllRoutes(baseURL!);

  for (const path of routes) {
    await page.goto(path);
    // `networkidle` is bounded — the SPA owns several poll loops
    // (LastRunStore, ActivityChipStack, PlayerContext, AutoCodeToast,
    // PlaygroundHUD) which prevent the 500ms idle window from ever firing
    // under CI Linux. `load` is deterministic; the small follow-up settle
    // lets first-paint React effects run before we sample console errors.
    // See root CLAUDE.md "E2E: waitForLoadState('networkidle') is too
    // fragile for SPAs".
    await page.waitForLoadState('load');
    await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {});
  }

  expect(errors).toEqual([]);
});

// Known bug: duplicate React key errors on transcript pages with
// duplicate segment IDs. Only reproducible with the project-ikea
// fixture (sessions s1, s3, s4), not the smoke-test fixture which
// has unique segment IDs.
test.fixme(
  'KNOWN BUG: duplicate React key warnings on transcript pages',
  async () => {
    // Requires a fixture with duplicate segment IDs.
    // Promote this test when a richer committed fixture is available.
    // Affected keys: t-267, t-275, t-277 (s1), t-258, t-262, t-263 (s3),
    // t-3, t-48, t-86, t-122, t-174 (s4).
  },
);
