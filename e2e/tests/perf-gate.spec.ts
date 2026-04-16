/**
 * Performance regression gate.
 *
 * Runs Chromium-only against the smoke-test fixture (1 session, 4 quotes).
 * Checks: server identity, DOM node counts, API latencies, export HTML size.
 * Thresholds use a doubling rule: fail at 2x baseline, warn at 1.5x.
 * See docs/design-perf-regression-gate.md for measured baselines.
 */
import { test, expect } from '@playwright/test';
import { writeFileSync, appendFileSync } from 'fs';
import { resolve } from 'path';

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
    await page.waitForLoadState('networkidle');

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
  await page.waitForLoadState('networkidle');

  const ms = await page.evaluate(async (url: string) => {
    const token = (window as any).__BRISTLENOSE_AUTH_TOKEN__;
    const start = performance.now();
    await fetch(`${url}/api/projects/1/quotes`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return performance.now() - start;
  }, baseURL!);

  results.api_latency_quotes_ms = Math.round(ms * 10) / 10;

  if (ms > API_LATENCY_WARN_MS) {
    console.warn(`⚠ API latency warning: quotes ${ms.toFixed(1)}ms (warn > ${API_LATENCY_WARN_MS}ms)`);
  }
  // Warn-only — no hard gate
});

test('API latency — dashboard endpoint', async ({ page, baseURL }) => {
  await page.goto('/report/');
  await page.waitForLoadState('networkidle');

  const ms = await page.evaluate(async (url: string) => {
    const token = (window as any).__BRISTLENOSE_AUTH_TOKEN__;
    const start = performance.now();
    await fetch(`${url}/api/projects/1/dashboard`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    return performance.now() - start;
  }, baseURL!);

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
  await page.waitForLoadState('networkidle');

  const sizeBytes = await page.evaluate(async (url: string) => {
    const token = (window as any).__BRISTLENOSE_AUTH_TOKEN__;
    const res = await fetch(`${url}/api/projects/1/export`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const blob = await res.blob();
    return blob.size;
  }, baseURL!);

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
  const record = { timestamp, ...results };
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
