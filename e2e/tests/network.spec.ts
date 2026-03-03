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

  page.on('response', (res) => {
    if (res.url().includes('/api/') && res.status() >= 400) {
      failures.push(`${res.status()} ${res.url()}`);
    }
  });

  const routes = await getAllRoutes(baseURL!);

  for (const path of routes) {
    await page.goto(path);
    await page.waitForLoadState('networkidle');
  }

  expect(failures).toEqual([]);
});
