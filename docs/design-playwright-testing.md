# Playwright E2E Testing Strategy

_Design doc — not yet implemented._

## Problem

Visual screenshot comparison doesn't scale. Eyeballing hundreds of screenshots catches nothing reliably. The useful signals are programmatic — console errors, dead links, failed network requests, missing DOM elements.

## Prior art

QA session (1 Mar 2026) tested all routes manually via Playwright MCP and found:

1. **Duplicate React key errors** on transcript pages (s1, s3, s4) — caught by console monitoring
2. **Dead "Show all N quotes" links** on Analysis page — `<a>` tags with no `href` — caught by DOM inspection
3. **All API requests returned 200** — confirmed by network monitoring

None of these required screenshots.

## Test layers (in priority order)

### 1. Console error monitor

Catch React warnings, uncaught exceptions, failed resource loads. Run against every route including all session pages.

```ts
const ROUTES = [
  '/report/',
  '/report/sessions/',
  '/report/quotes/',
  '/report/codebook/',
  '/report/analysis/',
  '/report/settings/',
  '/report/about/',
  // Session pages discovered dynamically from /api/projects/{id}/sessions
];

test('no console errors on any route', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error' && !msg.text().includes('favicon'))
      errors.push(`${page.url()}: ${msg.text()}`);
  });

  for (const path of ROUTES) {
    await page.goto(`http://127.0.0.1:8150${path}`);
    await page.waitForLoadState('networkidle');
  }

  expect(errors).toEqual([]);
});
```

**Catches:** React key warnings, runtime exceptions, failed imports, broken resource loads.

### 2. Link crawler

Walk every `<a>` on every page. Assert all links have an `href` and internal links resolve (no 404).

```ts
test('all links have href and internal links resolve', async ({ page }) => {
  const deadLinks: string[] = [];
  const brokenLinks: string[] = [];

  for (const path of ROUTES) {
    await page.goto(`http://127.0.0.1:8150${path}`);
    const links = await page.locator('a').all();

    for (const link of links) {
      const href = await link.getAttribute('href');
      const text = (await link.textContent())?.trim();

      // Links with visible text should have an href
      if (!href && text) {
        deadLinks.push(`${path}: "${text.slice(0, 60)}" has no href`);
        continue;
      }

      // Internal links should resolve (skip hash-only and external)
      if (href && href.startsWith('/') && !href.startsWith('//')) {
        const res = await page.request.get(`http://127.0.0.1:8150${href}`);
        if (res.status() >= 400) {
          brokenLinks.push(`${path}: "${text?.slice(0, 40)}" → ${href} (${res.status()})`);
        }
      }
    }
  }

  expect(deadLinks).toEqual([]);
  expect(brokenLinks).toEqual([]);
});
```

**Catches:** Dead links (no href), broken internal navigation, orphaned routes.

### 3. Network assertion

Monitor all API requests during a full navigation flow. Assert zero failures.

```ts
test('no failed API requests during full navigation', async ({ page }) => {
  const failures: string[] = [];
  page.on('response', res => {
    if (res.url().includes('/api/') && res.status() >= 400)
      failures.push(`${res.status()} ${res.url()}`);
  });

  for (const path of ROUTES) {
    await page.goto(`http://127.0.0.1:8150${path}`);
    await page.waitForLoadState('networkidle');
  }

  expect(failures).toEqual([]);
});
```

**Catches:** API regressions, broken endpoints, auth failures, missing data.

### 4. Structural smoke tests

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

### 5. Visual regression (sparingly)

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

| Bug type                          | Layer            |
|-----------------------------------|------------------|
| React key warnings, runtime errors | Console monitor  |
| Dead links, missing hrefs          | Link crawler     |
| API regressions, broken endpoints  | Network assertion |
| Missing content, broken rendering  | Structural smoke |
| CSS layout regressions             | Visual regression |

## When to run

Layers 1–4 navigate ~10 routes and assert DOM/console/network state. Total runtime: under 30 seconds. Fast enough to run on every push.

Layer 5 (visual regression) is slower — screenshot comparison, baseline management, flaky across OSes/fonts. Keep manual or weekly.

| Trigger | What runs |
|---------|-----------|
| `npm test` (Vitest) | Unit tests only — stays fast |
| CI push | pytest + ruff + Vitest + **Playwright layers 1–4** |
| Manual / weekly | Visual regression (layer 5) |

## Setup

### Prerequisites

- Test project with known data (the `project-ikea` fixture works)
- `webServer` in `playwright.config.ts` auto-starts `bristlenose serve` against the test fixture before tests run — no separate setup step needed

### File structure

```
e2e/
  playwright.config.ts
  fixtures/
    routes.ts          # ROUTES array, session discovery
  tests/
    console.spec.ts    # Layer 1
    links.spec.ts      # Layer 2
    network.spec.ts    # Layer 3
    smoke.spec.ts      # Layer 4
    visual.spec.ts     # Layer 5 (excluded from CI, run manually)
```

### Open questions

- **Test data**: use the existing `project-ikea` test fixture, or create a dedicated minimal fixture?
- **Session discovery**: hardcode session IDs or fetch from `/api/projects/{id}/sessions` at test time?
- **Port**: hardcode 8150 or make configurable via env var?

## Known bugs (from 1 Mar 2026 QA session)

These should become failing tests once the harness is set up:

1. **Duplicate React key errors on transcript pages** — sessions s1, s3, s4 have duplicate segment IDs used as `key` props. s2 is clean. Keys: `t-267`, `t-275`, `t-277` (s1), `t-258`, `t-262`, `t-263` (s3), `t-3`, `t-48`, `t-86`, `t-122`, `t-174` (s4)
2. **Dead "Show all N quotes" links on Analysis page** — all 12 `<a>` tags have no `href` and no click handler
