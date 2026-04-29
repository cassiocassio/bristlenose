/**
 * Performance regression gate.
 *
 * Runs Chromium-only against the smoke-test fixture (1 session, 4 quotes).
 * Checks: server identity, DOM node counts, API latencies, export HTML size.
 * Thresholds use a doubling rule: fail at 2x baseline, warn at 1.5x.
 * See docs/design-perf-regression-gate.md for measured baselines.
 */
import { test, expect, Page } from '@playwright/test';
import { writeFileSync, appendFileSync } from 'fs';
import { resolve } from 'path';
import { execSync } from 'child_process';
import os from 'os';

test.describe.configure({ mode: 'serial' });

// ── Results collector ───────────────────────────────────────────────────

const results: Record<string, number> = {};

// Skip on WebKit — Chromium-only gate
test.skip(({ browserName }) => browserName !== 'chromium', 'perf gate is Chromium-only');

// ── Baselines and thresholds ────────────────────────────────────────────

interface PageThreshold {
  path: string;
  label: string;
  baseline: number;
  warn: number;
  fail: number;
}

const DOM_THRESHOLDS: PageThreshold[] = [
  { path: '/report/quotes/', label: 'Quotes', baseline: 549, warn: 800, fail: 1_100 },
  { path: '/report/sessions/s1', label: 'Transcript s1', baseline: 374, warn: 550, fail: 750 },
  { path: '/report/', label: 'Dashboard', baseline: 334, warn: 500, fail: 670 },
  { path: '/report/sessions/', label: 'Sessions', baseline: 304, warn: 450, fail: 600 },
];

const API_LATENCY_WARN_MS = 100;

const EXPORT_SIZE_WARN = 2.5 * 1024 * 1024; // 2.5 MB
const EXPORT_SIZE_FAIL = 3.2 * 1024 * 1024; // 3.2 MB

// ── Helpers ─────────────────────────────────────────────────────────────

function authToken(): string {
  return process.env._BRISTLENOSE_AUTH_TOKEN ?? '';
}

/**
 * Wait for the React SPA to fully mount, including deferred useEffect islands.
 *
 * `networkidle` alone is fragile on slow CI runners — it can fire before
 * lazy components mount, inflating false negatives. This:
 *  1. waits for `networkidle` (server chatter quiet)
 *  2. waits for `#bn-app-root` to have rendered children (React mounted)
 *  3. waits for DOM node count to stabilise across two 200ms polls
 *     (no deferred effects still adding nodes)
 */
async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await page.waitForFunction(
    () => {
      const root = document.querySelector('#bn-app-root');
      return !!(root && root.children.length > 0);
    },
    { timeout: 5_000 },
  );
  // DOM node count stable across two consecutive polls = deferred mounts done.
  // The __prevDomCount property is a primitive, not a DOM node — it doesn't
  // affect the count being measured.
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

function getGitSha(): string | null {
  try {
    return execSync('git rev-parse HEAD', {
      cwd: resolve(__dirname, '..', '..'),
      stdio: ['ignore', 'pipe', 'ignore'],
    })
      .toString()
      .trim();
  } catch {
    return null;
  }
}

function getRunner(): string {
  // GitHub Actions sets GITHUB_ACTIONS=true and RUNNER_OS
  if (process.env.GITHUB_ACTIONS === 'true') {
    return `ci:${process.env.RUNNER_OS ?? 'unknown'}:${process.env.GITHUB_RUN_ID ?? '?'}`;
  }
  return `local:${os.platform()}-${os.arch()}`;
}

// ── Tests ───────────────────────────────────────────────────────────────

test('server identity guard — smoke-test fixture', async ({ page, baseURL }) => {
  const res = await page.request.get(`${baseURL}/api/projects/1/info`, {
    headers: { Authorization: `Bearer ${authToken()}` },
  });
  expect(res.ok()).toBe(true);
  const data = await res.json();
  expect(data.project_name).toBe('Smoke Test');
});

for (const t of DOM_THRESHOLDS) {
  test(`DOM nodes — ${t.label} (baseline ${t.baseline}, fail > ${t.fail})`, async ({ page }) => {
    await page.goto(t.path);
    await waitForPageReady(page);

    const count = await page.evaluate(() => document.querySelectorAll('*').length);
    results[`dom_${t.label.toLowerCase().replace(/\s+/g, '_')}`] = count;

    if (count > t.warn) {
      console.warn(
        `⚠ DOM count warning: ${t.label} has ${count} nodes (baseline ${t.baseline}, warn ${t.warn})`,
      );
    }

    expect(count, `${t.label} DOM count ${count} exceeds fail threshold ${t.fail}`).toBeLessThan(
      t.fail,
    );
  });
}

test('API latency — quotes endpoint', async ({ page, baseURL }) => {
  await page.goto('/report/');
  await waitForPageReady(page);

  const { ms, ok, status } = await page.evaluate(async (url: string) => {
    const token = (window as unknown as { __BRISTLENOSE_AUTH_TOKEN__?: string }).__BRISTLENOSE_AUTH_TOKEN__;
    const start = performance.now();
    const res = await fetch(`${url}/api/projects/1/quotes`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return { ms: performance.now() - start, ok: res.ok, status: res.status };
  }, baseURL!);

  // Guard against silent-pass trap: a 401 completes in ~1ms and would look
  // like excellent latency. Fail loudly if the response wasn't 2xx.
  expect(ok, `quotes API returned ${status} — auth token missing?`).toBe(true);

  results.api_latency_quotes_ms = Math.round(ms * 10) / 10;

  if (ms > API_LATENCY_WARN_MS) {
    console.warn(`⚠ API latency warning: quotes ${ms.toFixed(1)}ms (warn > ${API_LATENCY_WARN_MS}ms)`);
  }
  // Warn-only — no hard gate
});

test('API latency — dashboard endpoint', async ({ page, baseURL }) => {
  await page.goto('/report/');
  await waitForPageReady(page);

  const { ms, ok, status } = await page.evaluate(async (url: string) => {
    const token = (window as unknown as { __BRISTLENOSE_AUTH_TOKEN__?: string }).__BRISTLENOSE_AUTH_TOKEN__;
    const start = performance.now();
    const res = await fetch(`${url}/api/projects/1/dashboard`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return { ms: performance.now() - start, ok: res.ok, status: res.status };
  }, baseURL!);

  expect(ok, `dashboard API returned ${status} — auth token missing?`).toBe(true);

  results.api_latency_dashboard_ms = Math.round(ms * 10) / 10;

  if (ms > API_LATENCY_WARN_MS) {
    console.warn(`⚠ API latency warning: dashboard ${ms.toFixed(1)}ms (warn > ${API_LATENCY_WARN_MS}ms)`);
  }
  // Warn-only — no hard gate
});

test(`export HTML size (fail > ${(EXPORT_SIZE_FAIL / 1024 / 1024).toFixed(1)} MB)`, async ({
  page,
  baseURL,
}) => {
  await page.goto('/report/');
  await waitForPageReady(page);

  const { sizeBytes, ok, status } = await page.evaluate(async (url: string) => {
    const token = (window as unknown as { __BRISTLENOSE_AUTH_TOKEN__?: string }).__BRISTLENOSE_AUTH_TOKEN__;
    const res = await fetch(`${url}/api/projects/1/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const blob = await res.blob();
    return { sizeBytes: blob.size, ok: res.ok, status: res.status };
  }, baseURL!);

  // Silent-pass guard: a 401 body is ~50 bytes and would trivially pass the
  // 3.2 MB fail threshold. Assert 2xx + a sanity floor.
  expect(ok, `export returned ${status} — auth token missing?`).toBe(true);
  expect(
    sizeBytes,
    `Export HTML ${sizeBytes} bytes is implausibly small — real export is ~1.6 MB`,
  ).toBeGreaterThan(500_000);

  results.export_html_bytes = sizeBytes;
  const sizeMB = sizeBytes / 1024 / 1024;

  if (sizeBytes > EXPORT_SIZE_WARN) {
    console.warn(
      `⚠ Export size warning: ${sizeMB.toFixed(2)} MB (warn > ${(EXPORT_SIZE_WARN / 1024 / 1024).toFixed(1)} MB)`,
    );
  }

  expect(
    sizeBytes,
    `Export HTML ${sizeMB.toFixed(2)} MB exceeds fail threshold ${(EXPORT_SIZE_FAIL / 1024 / 1024).toFixed(1)} MB`,
  ).toBeLessThan(EXPORT_SIZE_FAIL);
});

// ── Write results ───────────────────────────────────────────────────────

test.afterAll(() => {
  if (Object.keys(results).length === 0) return;

  const timestamp = new Date().toISOString();
  const git_sha = getGitSha();
  const runner = getRunner();
  // Fields at the top so they read first in the JSONL; results spread after.
  // Schema stays forward-compatible — new fields can be added without breaking
  // readers that do `.get(key, '—')`.
  const record = { timestamp, git_sha, runner, ...results };
  const e2eDir = resolve(__dirname, '..');

  // Latest snapshot (overwritten each run)
  writeFileSync(
    resolve(e2eDir, 'perf-results.json'),
    JSON.stringify(record, null, 2) + '\n',
  );

  // Append to history (one JSON line per run)
  appendFileSync(
    resolve(e2eDir, '.perf-history.jsonl'),
    JSON.stringify(record) + '\n',
  );

  // Human-readable summary to stdout
  const domKeys = Object.keys(results).filter((k) => k.startsWith('dom_'));
  const lines = [
    '',
    '┌─────────────────────────────────────────────┐',
    '│  Performance results                        │',
    '├─────────────────────────────────────────────┤',
    ...domKeys.map((k) => {
      const label = k.replace('dom_', '').replace(/_/g, ' ');
      const baseline = DOM_THRESHOLDS.find(
        (t) => t.label.toLowerCase().replace(/\s+/g, '_') === k.replace('dom_', ''),
      )?.baseline;
      const delta = baseline ? ` (${results[k] > baseline ? '+' : ''}${results[k] - baseline})` : '';
      return `│  DOM ${label.padEnd(18)} ${String(results[k]).padStart(5)} nodes${delta.padStart(10)} │`;
    }),
    '│                                             │',
    `│  API quotes          ${String(results.api_latency_quotes_ms ?? '—').padStart(6)} ms            │`,
    `│  API dashboard       ${String(results.api_latency_dashboard_ms ?? '—').padStart(6)} ms            │`,
    `│  Export HTML      ${((results.export_html_bytes ?? 0) / 1024 / 1024).toFixed(2).padStart(7)} MB            │`,
    '└─────────────────────────────────────────────┘',
    `  Saved: perf-results.json, .perf-history.jsonl`,
    '',
  ];
  console.log(lines.join('\n'));
});
