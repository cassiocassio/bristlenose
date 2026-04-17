/**
 * Playwright config for the synthetic stress test.
 *
 * The orchestrator (scripts/perf-stress.sh) starts the server itself so
 * it can time SQLite import and enforce the port-8153 identity guard.
 * This config therefore does NOT declare a `webServer` block — the spec
 * assumes the fixture server is already running on port 8153.
 *
 * Chromium-only: the stress test measures DOM structure; WebKit adds
 * noise without changing the story.  Run under the default reporter.
 */
import { defineConfig } from '@playwright/test';

const PORT = parseInt(process.env.BN_STRESS_PORT ?? '8153', 10);

export default defineConfig({
  testDir: './tests',
  timeout: 120_000, // Stress runs can be slow — pages mount 1,500 cards
  retries: 0,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'off',
    // Browser fetch() inherits these for same-origin requests; Node-side
    // fetch still needs to add the bearer token manually.
    extraHTTPHeaders: process.env._BRISTLENOSE_AUTH_TOKEN
      ? { Authorization: `Bearer ${process.env._BRISTLENOSE_AUTH_TOKEN}` }
      : {},
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
});
