/**
 * Mount precondition gate.
 *
 * Asserts the React SPA actually mounts against the smoke-test fixture on
 * every primary route before any perf/DOM-count check runs. If the bundle
 * is broken or the server's status-page intercept silently fires (e.g. the
 * fixture is missing a terminus event), this fails LOUDLY here rather than
 * surfacing five layers downstream as ``DOM nodes — Quotes`` timing out.
 *
 * Five PyPI releases (v0.15.5–v0.15.9) shipped to GitHub but never reached
 * PyPI because that downstream failure mode was unreadable. Keep this test
 * as the canonical "did the SPA render at all?" check.
 *
 * See ``tests/test_server_status_page.py::TestSmokeFixtureMountsSPA`` for
 * the parallel Python-layer check that catches the same class of fixture
 * regression at the pytest layer.
 */
import { test, expect, Page } from '@playwright/test';

const ROUTES = ['/report/', '/report/quotes/', '/report/sessions/', '/report/sessions/s1'];

async function waitForMount(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(
    () => {
      const root = document.querySelector('#bn-app-root');
      return !!(root && root.children.length > 0);
    },
    { timeout: 10_000 },
  );
}

for (const path of ROUTES) {
  test(`SPA mounts on ${path}`, async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });
    page.on('pageerror', (err) => pageErrors.push(`${err.message}\n${err.stack ?? ''}`));

    await page.goto(path);
    await waitForMount(page);

    // Smoke fixture in "completed run" state must render the SPA, not the
    // server-rendered status page intercept. The status page would surface
    // a ``bn-status-page`` body class and the "Nothing to see here" copy.
    const bodyClass = await page.evaluate(() => document.body.className);
    expect(bodyClass, `${path} returned the status-page intercept`).not.toContain(
      'bn-status-page',
    );

    const rootChildren = await page.evaluate(() => {
      const root = document.querySelector('#bn-app-root');
      return root ? root.children.length : 0;
    });
    expect(rootChildren, `${path} #bn-app-root has no children`).toBeGreaterThan(0);

    // Mount failures often correlate with a noisy console — surface them so
    // future regressions land with diagnostic context, not just a timeout.
    if (consoleErrors.length || pageErrors.length) {
      const detail = [
        ...consoleErrors.map((e) => `console.error: ${e}`),
        ...pageErrors.map((e) => `pageerror: ${e}`),
      ].join('\n');
      throw new Error(`Browser errors during mount of ${path}:\n${detail}`);
    }
  });
}
