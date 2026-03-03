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
      // Ignore favicon 404 (browsers request this automatically)
      if (text.includes('favicon')) return;
      errors.push(`${page.url()}: ${text}`);
    }
  });

  const routes = await getAllRoutes(baseURL!);

  for (const path of routes) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
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
