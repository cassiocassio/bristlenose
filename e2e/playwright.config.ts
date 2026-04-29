import { defineConfig } from '@playwright/test';
import { resolve } from 'path';

const PORT = parseInt(process.env.BN_E2E_PORT ?? '8150', 10);
const BASE_URL = `http://127.0.0.1:${PORT}`;

// Resolve paths relative to this config file (which lives in e2e/)
const REPO_ROOT = resolve(__dirname, '..');
const FIXTURE_DIR = resolve(REPO_ROOT, 'tests/fixtures/smoke-test/input');

// Use venv Python locally, bare command in CI (pip install puts it on PATH)
const BRISTLENOSE = process.env.CI
  ? 'bristlenose'
  : resolve(REPO_ROOT, '.venv/bin/bristlenose');

// perf-stress is always excluded here — it needs its own fixture + orchestrator
// (scripts/perf-stress.sh + playwright.stress.config.ts).
// perf-gate is excluded from the default e2e run and runs in a dedicated CI job;
// set BN_RUN_PERF_GATE=1 to include it explicitly (e.g. for local diagnostics).
const testIgnore = ['**/perf-stress.spec.ts'];
if (process.env.BN_RUN_PERF_GATE !== '1') {
  testIgnore.push('**/perf-gate.spec.ts');
}

export default defineConfig({
  testDir: './tests',
  testIgnore,
  timeout: 30_000,
  retries: 0,
  workers: 1, // Serial — all tests share one server
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
    {
      name: 'webkit',
      use: { browserName: 'webkit' },
    },
  ],
  webServer: {
    // Quote the paths so worktree directories with spaces in the name
    // (e.g. "bristlenose_branch ci-cleanup") don't break the shell split.
    command: `"${BRISTLENOSE}" serve "${FIXTURE_DIR}" --port ${PORT} --no-open`,
    port: PORT,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    // Pin the server's auth token so fixtures can send a predictable bearer.
    // Inherits _BRISTLENOSE_AUTH_TOKEN from the parent shell if set (CI uses
    // "test-token"); falls back to "test-token" locally when unset.  See root
    // CLAUDE.md → "E2E Node-side fetch() needs auth token explicitly".
    env: {
      _BRISTLENOSE_AUTH_TOKEN: process.env._BRISTLENOSE_AUTH_TOKEN ?? 'test-token',
    },
  },
});
