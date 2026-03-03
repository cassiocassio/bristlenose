# Playwright E2E Testing Strategy

_Layers 1–3 implemented (3 Mar 2026). Layers 4–5 not yet implemented._

## Problem

Visual screenshot comparison doesn't scale. Eyeballing hundreds of screenshots catches nothing reliably. The useful signals are programmatic — console errors, dead links, failed network requests, missing DOM elements.

## Prior art

QA session (1 Mar 2026) tested all routes manually via Playwright MCP and found:

1. **Duplicate React key errors** on transcript pages (s1, s3, s4) — caught by console monitoring
2. **Dead "Show all N quotes" links** on Analysis page — `<a>` tags with no `href` — caught by DOM inspection
3. **All API requests returned 200** — confirmed by network monitoring

None of these required screenshots.

## Running the tests

```bash
# Default — auto-starts bristlenose serve, runs layers 1–3 on Chromium + WebKit
cd e2e && npm test

# Headed mode — visible browser for debugging
cd e2e && npm run test:headed

# Against an already-running server (faster iteration)
# Terminal 1:
bristlenose serve tests/fixtures/smoke-test/input --port 8150 --no-open
# Terminal 2:
cd e2e && npm test

# Override port (e.g. avoid collision with a running dev server)
BN_E2E_PORT=8151 npm test
```

### Output options

| Command | What you get |
|---------|-------------|
| `npm test` | Default list: pass/fail per test with timing |
| `npx playwright test --reporter=html` | Full HTML report at `e2e/playwright-report/index.html` — per-test timelines, error context, traces on failure |
| `npx playwright show-report` | Opens the HTML report in your browser |
| `npm run test:headed` | Visible browser — watch it navigate all routes |

### First-time setup

```bash
cd e2e
npm install
npx playwright install chromium webkit
```

## Test layers (in priority order)

### 1. Console error monitor ✅

Catch React warnings, uncaught exceptions, failed resource loads. Runs against every route including dynamically discovered session pages.

**File:** `e2e/tests/console.spec.ts`

**What it does:** Navigates all routes, captures `console.error` messages (ignoring favicon 404s), asserts the list is empty.

**Catches:** React key warnings, runtime exceptions, failed imports, broken resource loads.

### 2. Link crawler ✅

Walk every `<a>` on every page. Assert all links with visible text have an `href` and internal links resolve (no 404).

**File:** `e2e/tests/links.spec.ts`

**What it does:** For every `<a>` element on every route:
- Skips `<a role="button">` (interactive elements like modal triggers — intentionally no `href`)
- Skips external links, hash-only links, `javascript:` links
- Flags dead links (visible text but no `href`)
- Checks internal links resolve (GET request, assert status < 400)

**Catches:** Dead links (no href), broken internal navigation, orphaned routes.

### 3. Network assertion ✅

Monitor all API requests during a full navigation flow. Assert zero failures.

**File:** `e2e/tests/network.spec.ts`

**What it does:** Listens to all HTTP responses containing `/api/` during route navigation, asserts none return status >= 400.

**Catches:** API regressions, broken endpoints, auth failures, missing data.

### 4. Structural smoke tests (not yet implemented)

Assert expected DOM structure exists — not pixel-perfect, just "is the content there".

```ts
test('dashboard has stats and session table', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/');
  await expect(page.getByText('sessions')).toBeVisible();
  await expect(page.getByText('quotes')).toBeVisible();
  await expect(page.getByRole('table')).toBeVisible();
});

test('quotes page has sections and themes headings', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/quotes/');
  await expect(page.getByRole('heading', { name: 'Sections' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Themes' })).toBeVisible();
});

test('session transcript has segments', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/sessions/s1');
  const segments = page.locator('.transcript-segment');
  expect(await segments.count()).toBeGreaterThan(5);
});

test('codebook page loads groups', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/codebook/');
  await expect(page.getByRole('heading', { name: 'Codebook' })).toBeVisible();
});

test('analysis page has signal cards', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/analysis/');
  await expect(page.getByText('Signal')).toBeVisible();
});

test('settings page has appearance toggle', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/settings/');
  await expect(page.getByText('Application appearance')).toBeVisible();
});

test('export modal opens and closes', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/');
  await page.getByRole('button', { name: 'Export' }).click();
  await expect(page.getByText('Export report')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByText('Export report')).not.toBeVisible();
});

test('help modal opens via ? button', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/');
  await page.getByRole('button', { name: /for Help/ }).click();
  await expect(page.getByText('Keyboard Shortcuts')).toBeVisible();
});
```

**Catches:** Missing content, broken component rendering, mount failures.

### 5. Visual regression (not yet implemented, sparingly)

Use Playwright's `toHaveScreenshot()` for pixel-diff against baselines. Only for ~5 key views — not every permutation. First run generates baselines, subsequent runs auto-detect regressions.

```ts
test('dashboard layout', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/');
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveScreenshot('dashboard.png', { maxDiffPixels: 100 });
});

test('quotes layout', async ({ page }) => {
  await page.goto('http://127.0.0.1:8150/report/quotes/');
  await page.waitForLoadState('networkidle');
  await expect(page).toHaveScreenshot('quotes.png', { maxDiffPixels: 100 });
});
```

**Catches:** CSS layout regressions, spacing changes, visual breakage. Noisy — keep the list short.

## What catches what

| Bug type                          | Layer            | Status |
|-----------------------------------|------------------|--------|
| React key warnings, runtime errors | Console monitor  | ✅ |
| Dead links, missing hrefs          | Link crawler     | ✅ |
| API regressions, broken endpoints  | Network assertion | ✅ |
| Missing content, broken rendering  | Structural smoke | Planned |
| CSS layout regressions             | Visual regression | Planned |

## Architecture

### File structure

```
e2e/
  package.json             # @playwright/test dependency, npm scripts
  package-lock.json        # Lockfile (committed)
  playwright.config.ts     # webServer, browser projects, port config
  tsconfig.json            # TypeScript config
  .gitignore               # node_modules/, test-results/, playwright-report/
  fixtures/
    routes.ts              # ROUTES array, dynamic session discovery
  tests/
    console.spec.ts        # Layer 1 ✅
    links.spec.ts          # Layer 2 ✅
    network.spec.ts        # Layer 3 ✅
    smoke.spec.ts          # Layer 4 (planned)
    visual.spec.ts         # Layer 5 (planned, excluded from CI)
```

### Key design decisions

**TypeScript (`@playwright/test`), not Python (`pytest-playwright`).** These tests target the browser + React layer. The Python test suite already covers the HTTP API (330+ tests via pytest). Keeping E2E in TypeScript matches the browser code and avoids adding browser binaries to the Python dev dependencies.

**Smoke-test fixture.** Tests run against `tests/fixtures/smoke-test/input/` — the same committed fixture used by 330+ Python tests. It has 1 session with 4 quotes, enough for route navigation. The known bugs (duplicate React keys on s1/s3/s4, dead analysis links) are project-ikea-specific — they're encoded as `test.fixme()` stubs to be promoted when a richer committed fixture exists.

**Dynamic session discovery.** `e2e/fixtures/routes.ts` exports `getAllRoutes(baseURL)` which fetches session IDs from `/api/projects/1/sessions` at test time, then appends `/report/sessions/{id}` routes. New sessions in the fixture appear in tests automatically.

**Chromium + WebKit.** Two browser projects — Chromium for Chrome/Edge coverage, WebKit for Safari. Most Bristlenose users are researchers on macOS. Firefox can be added later.

**`webServer` auto-start.** `playwright.config.ts` starts `bristlenose serve` pointing at the fixture. Locally it uses `.venv/bin/bristlenose` (resolved via `__dirname`); in CI it uses the bare `bristlenose` command (on PATH via `pip install -e`). `reuseExistingServer: !process.env.CI` lets you run against an already-running server during development.

**Port.** Default 8150, overridable via `BN_E2E_PORT` env var.

**Serial execution.** `workers: 1` — all test files share one server instance. Total runtime ~32 seconds including server startup.

### CI integration

The `e2e` job in `.github/workflows/ci.yml` runs after the Python and frontend jobs pass. It installs Python `[dev,serve]` extras, builds the frontend, installs Playwright browsers (`chromium`, `webkit` with system deps), and runs all tests. On failure, the HTML report is uploaded as a GitHub Actions artifact (7-day retention).

## Resolved decisions (from open questions)

- **Test data**: smoke-test fixture (`tests/fixtures/smoke-test/input/`). Committed, stable, sufficient for route navigation. Known bugs that need richer data are `test.fixme()` stubs
- **Session discovery**: dynamic — fetched from `/api/projects/1/sessions` at test time
- **Port**: configurable via `BN_E2E_PORT` env var, default 8150

## Known bugs (from 1 Mar 2026 QA session)

Encoded as `test.fixme()` stubs — promote to real assertions when a richer committed fixture is available:

1. **Duplicate React key errors on transcript pages** — sessions s1, s3, s4 have duplicate segment IDs used as `key` props. s2 is clean. Keys: `t-267`, `t-275`, `t-277` (s1), `t-258`, `t-262`, `t-263` (s3), `t-3`, `t-48`, `t-86`, `t-122`, `t-174` (s4)
2. **Dead "Show all N quotes" links on Analysis page** — all 12 `<a>` tags have no `href` and no click handler

## When to run

Layers 1–3 navigate ~8 routes (7 static + session pages) and assert console/DOM/network state. Total runtime: ~32 seconds (including server startup). Fast enough to run on every push.

Layer 5 (visual regression) would be slower — screenshot comparison, baseline management, flaky across OSes/fonts. Keep manual or weekly.

| Trigger | What runs |
|---------|-----------|
| `npm test` (Vitest, in `frontend/`) | Unit tests only — stays fast |
| CI push | pytest + ruff + Vitest + **Playwright layers 1–3** |
| Manual / weekly | Visual regression (layer 5, when implemented) |

## Future work

- **Layer 4 (structural smoke tests)** — per-page DOM assertions, `data-testid` selectors
- **Layer 5 (visual regression)** — `toHaveScreenshot()` baselines for key views
- **Write-action E2E tests** — 11 DB-mutating user actions (star, hide, edit, tag, etc.)
- **Richer committed fixture** — 3+ sessions, analysis data, codebook entries, to trigger the known bugs
- **Firefox project** — add to `playwright.config.ts` projects when stability is proven
- **axe-core accessibility** — `@axe-core/playwright` in structural smoke tests
