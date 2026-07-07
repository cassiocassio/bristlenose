/**
 * Every lens loads clean.
 *
 * Phase-1 acceptance-tier E2E (docs/testing/acceptance-matrix.md). Visits all five
 * lenses and asserts each one actually MOUNTS the SPA and has no uncaught error or
 * failed app request — the cheap, high-value "did a regression blank a whole lens?"
 * signal.
 *
 * The review (2026-07-07, finding H2) flagged three false-greens this spec must NOT
 * inherit — all closed here:
 *  1. Stale server on :8150 → wrong project. Closed by the identity guard (first test,
 *     serial mode): project_name must be "Smoke Test" or the whole file aborts.
 *  2. "Clean" over a page that never mounted the SPA is vacuous. Closed by asserting
 *     `#bn-app-root` has children (waitForPageReady) BEFORE sampling for cleanliness.
 *  3. A dropped auth token silently shrinks the session route set to green. Closed by
 *     asserting the Sessions lens shows >= the fixture's session count.
 *
 * Console-error coverage across routes lives in console.spec.ts; this spec owns the
 * per-lens MOUNT + no-uncaught-error + no-failed-app-request signal (complementary,
 * not duplicative).
 */
import { test, expect, Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

function authToken(): string {
  return process.env._BRISTLENOSE_AUTH_TOKEN ?? 'test-token';
}

// Copied from perf-gate.spec.ts — networkidle alone is fragile; wait for the SPA to
// actually mount and for deferred islands to stop adding nodes.
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
  { path: '/report/', label: 'Project / Dashboard' },
  { path: '/report/sessions/', label: 'Sessions' },
  { path: '/report/quotes/', label: 'Quotes' },
  { path: '/report/codebook/', label: 'Codebook' },
  { path: '/report/analysis/', label: 'Analysis' },
];

// ── Guard 1: right server, right project (stale-:8150 trap) ────────────────

test('server identity guard — smoke-test fixture', async ({ page, baseURL }) => {
  const res = await page.request.get(`${baseURL}/api/projects/1/info`, {
    headers: { Authorization: `Bearer ${authToken()}` },
  });
  expect(res.ok()).toBe(true);
  const data = await res.json();
  expect(data.project_name).toBe('Smoke Test');
});

// ── Guard 3: the session route set didn't silently shrink to green ─────────

test('Sessions lens shows the fixture session (route set not truncated)', async ({ page }) => {
  await page.goto('/report/sessions/');
  await waitForPageReady(page);
  // The smoke fixture has exactly one session. A dropped token / 401 would yield an
  // empty table that still "loads clean" — assert the content is actually present.
  const sessionLinks = page.locator('a[href*="/report/sessions/s"]');
  expect(await sessionLinks.count()).toBeGreaterThanOrEqual(1);
});

// ── Every lens: mounts + no uncaught error + no failed app request ─────────

for (const lens of LENSES) {
  test(`${lens.label} loads clean`, async ({ page }) => {
    const pageErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on('pageerror', (err) => pageErrors.push(err.message));
    page.on('response', (res) => {
      const url = res.url();
      const status = res.status();
      const isAppRequest = /\/(api|report|static|assets)\//.test(url);
      if (!isAppRequest || status < 400) return; // unrelated favicon 404 etc. — not ours
      // ci-allowlist: CI-A3 — `autocode/*/status` 404s when no job has been started;
      // REST-correct "resource absent", CodebookPanel treats it as idle. See ALLOWLIST.md.
      if (status === 404 && /\/autocode\/[^/]+\/status/.test(url)) return;
      failedRequests.push(`${status} ${url}`);
    });

    await page.goto(lens.path);
    await waitForPageReady(page); // asserts #bn-app-root has children BEFORE we judge "clean"

    // Mount proof: the SPA root rendered content, not the server status page.
    const rootChildren = await page.evaluate(
      () => document.querySelector('#bn-app-root')?.children.length ?? 0,
    );
    expect(rootChildren, `${lens.label}: SPA did not mount`).toBeGreaterThan(0);

    expect(pageErrors, `${lens.label}: uncaught errors`).toEqual([]);
    expect(failedRequests, `${lens.label}: failed app requests`).toEqual([]);
  });
}
