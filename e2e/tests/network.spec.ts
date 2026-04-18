/**
 * Layer 3: Network assertion.
 *
 * Monitors all API requests during a full navigation flow.
 * Asserts zero failures (status >= 400).
 * Catches: API regressions, broken endpoints, missing data.
 */
import { test, expect } from '@playwright/test';
import { getAllRoutes } from '../fixtures/routes';

test('no failed API requests during full navigation', async ({
  page,
  baseURL,
}) => {
  const failures: string[] = [];

  // Expected-404 allowlist: endpoints where 404 is the documented "no such
  // resource" response and the frontend handles it gracefully. Every entry
  // must have a register ID — see e2e/ALLOWLIST.md.
  const expected404s: RegExp[] = [
    // ci-allowlist: CI-A3 (by-design — see e2e/ALLOWLIST.md)
    /\/api\/projects\/[^/]+\/autocode\/[^/]+\/status$/,
  ];

  page.on('response', (res) => {
    const url = res.url();
    const status = res.status();
    if (!url.includes('/api/') || status < 400) return;
    if (status === 404 && expected404s.some((re) => re.test(url))) return;
    failures.push(`${status} ${url}`);
  });

  const routes = await getAllRoutes(baseURL!);

  for (const path of routes) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
  }

  expect(failures).toEqual([]);
});
