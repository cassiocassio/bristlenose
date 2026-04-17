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

export default defineConfig({
  testDir: './tests',
  testIgnore: '**/perf-stress.spec.ts', // run via playwright.stress.config.ts
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
    command: `${BRISTLENOSE} serve ${FIXTURE_DIR} --port ${PORT} --no-open`,
    port: PORT,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
