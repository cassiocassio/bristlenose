# Design: CI Performance Regression Gate

## Problem

We ship PRs without knowing whether they made the app slower or bigger. Bundle size has a gate (305 KB gzip) but nothing catches DOM bloat, API latency regression, paint time regression, or export size growth. These are linear regressions — small datasets detect them fine.

## Goal

A CI job that runs on every PR, fails on regressions, passes in under 60 seconds. Uses the existing smoke-test fixture (1 session, 4 quotes). No LLM calls, no video, no large datasets.

## Measured baselines (smoke-test fixture, Apr 2026)

Measured on macOS, Chromium, `_BRISTLENOSE_AUTH_TOKEN=test-token`, Playwright `evaluate`. Fixture: 1 session (`s1`), 4 quotes, 2 speakers (`m1`, `p1`).

**Gotcha: stale server on port 8150.** The Playwright config uses `reuseExistingServer: !process.env.CI` — if a previous `bristlenose serve` is still running locally, measurements will be against the wrong dataset. Always kill stale servers before measuring: `lsof -i :8150` then `kill <pid>`.

### DOM node counts

| Page | Baseline | Nodes/item | Notes |
|------|----------|------------|-------|
| Dashboard (`/report/`) | 334 | — | Fixed structure |
| Sessions (`/report/sessions/`) | 304 | — | 1 session row |
| Quotes (`/report/quotes/`) | 549 | ~30/card | 4 cards + ~420 chrome (nav, sidebar, toolbar) |
| Codebook (`/report/codebook/`) | 342 | — | |
| Analysis (`/report/analysis/`) | 359 | — | |
| Settings (`/report/settings/`) | 334 | — | |
| About (`/report/about/`) | 334 | — | |
| Transcript (`/report/sessions/s1`) | 374 | — | 1 session, ~20 segments |

All pages are in the 300–550 range for this tiny fixture. The quotes page is heaviest (549) because quote cards (30 nodes each) plus chrome. At ~30 nodes/card, 1,500 quotes would produce ~45,000 card nodes + 420 chrome = ~45,420 total — that's where virtualisation matters.

### API latencies (in-browser `performance.now()`)

| Endpoint | Baseline | Notes |
|----------|----------|-------|
| `/dashboard` | 7ms | |
| `/quotes` | 6ms | |
| `/transcripts/s1` | 5ms | |
| `/codebook` | 5ms | |
| `/analysis/sentiment` | 5ms | |
| `/analysis/tags` | 4ms | |
| `/analysis/codebooks` | 3ms | |
| `/sessions` | 5ms | |
| `/people` | 3ms | |
| `/health` | 1ms | |

All endpoints return in under 10ms for the 4-quote fixture. These are local-machine numbers — CI runners will be slower (expect 2–5x).

### Export HTML

| Metric | Baseline |
|--------|----------|
| Export file size | **1.6 MB** (1,638,619 bytes) |

The export inlines all JS chunks uncompressed + theme CSS + base64 logos + transcript HTML. 1.6 MB for 4 quotes and 1 session. Mostly JS bundle overhead — the data payload is tiny.

## What to measure (thresholds)

Thresholds use a **doubling rule**: fail if a metric exceeds 2x baseline. This catches genuine regressions (accidentally rendering every quote twice, a leaked modal, a new dependency doubling bundle size) while allowing normal feature growth. Warn at 1.5x.

| Metric | Tool | Baseline | Warn | Fail | Rationale |
|--------|------|----------|------|------|-----------|
| Bundle size (JS gzip) | `size-limit` | ~267 KB | — | > 305 KB | Already in CI — keep as-is |
| DOM nodes (quotes page) | Playwright `evaluate` | 549 | > 800 | > 1,100 | 2x fail. Catches leaked modals, duplicated renders, wrapper bloat |
| DOM nodes (transcript page) | Playwright `evaluate` | 374 | > 550 | > 750 | 2x fail. Catches per-segment wrapper regressions |
| DOM nodes (dashboard) | Playwright `evaluate` | 334 | > 500 | > 670 | Fixed structure — any doubling is a bug |
| DOM nodes (sessions) | Playwright `evaluate` | 304 | > 450 | > 600 | |
| Export HTML file size | `curl` + `wc -c` | 1.6 MB | > 2.5 MB | > 3.2 MB | 2x fail. Safari/WKWebView stall above ~20 MB; tracks growth early |
| API latency (quotes) | Playwright `performance.now()` | 6ms | > 100ms | — | Warn-only. CI runners add variance; catches N+1 queries but not a hard gate |
| API latency (dashboard) | Playwright `performance.now()` | 7ms | > 100ms | — | Warn-only |

### Dropped: Lighthouse in CI

Lighthouse FCP/CLS scores are stochastic on shared CI runners (CPU allocation varies between runs). DOM node count and bundle size are deterministic proxies for the same regressions. **Decision: drop Lighthouse from the CI gate.** Run it locally against the smoke fixture for ad-hoc profiling; document baseline scores here for reference.

### Recalibration triggers

Re-measure and update thresholds when:
- After first stress test scaling run — results may reveal the per-quote marginal DOM cost is higher than expected, requiring tighter thresholds. See [design-perf-stress-test.md](design-perf-stress-test.md)
- `@tanstack/virtual` ships (S2) — quotes page DOM should drop dramatically
- Export format changes (e.g. gzip-compressed JS chunks)
- New pages or heavy components are added
- Smoke-test fixture grows (more sessions/quotes)

## Architecture

### New files (shipped Apr 2026)

| File | Purpose |
|------|---------|
| `e2e/tests/perf-gate.spec.ts` | Playwright test: server identity guard, DOM counts, API latency, export size. Chromium-only via `test.skip`. Writes results in `test.afterAll` |
| `scripts/perf-history.sh` | Tabular view of `e2e/.perf-history.jsonl` — one row per perf-gate run |
| `e2e/perf-results.json` | Latest run snapshot (gitignored, overwritten each run) |
| `e2e/.perf-history.jsonl` | Append-only run history (gitignored, local-only) |

The perf-gate runs inside the existing E2E suite — no separate job, no orchestrator script, no separate port. Server identity guard (first test, serial mode) catches stale servers on 8150 before wrong metrics are recorded.

### CI integration

Add a `perf-gate` job to `.github/workflows/ci.yml`:

```yaml
perf-gate:
  runs-on: ubuntu-latest
  needs: [test, frontend-lint-type-test]  # needs passing tests + built assets
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: "20"
    - uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Install Python dependencies (including serve extras)
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev,serve]"
    - name: Build frontend
      working-directory: frontend
      run: |
        npm ci
        npm run build
    - name: Install E2E dependencies
      run: cd e2e && npm ci && npx playwright install chromium
    - name: Perf gate
      run: ./scripts/perf-gate.sh
```

### Server identity guard

The first thing the perf-gate spec does is verify it's talking to the smoke-test fixture, not a stale server from a previous manual session:

```typescript
test('verify smoke-test fixture', async ({ page }) => {
  await page.goto('/report/');
  await page.waitForLoadState('networkidle');
  const projectName = await page.evaluate(async () => {
    const res = await fetch('/api/projects/1/dashboard', {
      headers: { Authorization: `Bearer ${(window as any).__BRISTLENOSE_AUTH_TOKEN__}` },
    });
    const data = await res.json();
    return data.project_name;
  });
  expect(projectName).toBe('Smoke Test');
});
```

This catches the exact failure we hit during baseline measurement — a stale `bristlenose serve` on port 8150 serving a different project (353 quotes instead of 4). Fails immediately with a clear message instead of producing silently wrong metrics.

### How thresholds work

The Playwright spec uses `expect(domCount).toBeLessThan(1_100)` for the quotes page. Failures break CI. Warnings are `console.log` output only — they signal "getting close" without blocking.

Thresholds use a doubling rule: fail at 2x baseline, warn at 1.5x. Calibrated from measured baselines (see table above). API latency is warn-only (CI runner variance makes it unsuitable as a hard gate).

### Export size measurement

The shell script calls the export endpoint to produce the HTML file, then measures it:

```bash
curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
  "http://127.0.0.1:${PORT}/api/projects/1/export" \
  -o /tmp/bristlenose-export.html
EXPORT_SIZE=$(wc -c < /tmp/bristlenose-export.html)
```

This tests the real serve-mode export path (the same code that runs when a user clicks "Download HTML"). The Playwright spec asserts on the size after the shell script captures it, or the shell script itself exits non-zero if the threshold is exceeded.

### Auth handling

Set `_BRISTLENOSE_AUTH_TOKEN=test-token` as an env var before starting the server. Pass that token in Playwright via `extraHTTPHeaders` in the config, and use it for Node-side `fetch()` calls in fixture helpers and the `curl` export call above.

### What this does NOT cover

- Scroll smoothness (needs real human + large dataset)
- Animation hitches (needs Xcode Instruments)
- Non-linear scaling breakpoints (needs synthetic 1,500-quote fixture)
- Pipeline throughput (needs real audio/video)

Those are covered by the stress test and FOSSDA plans.

## Verification

1. `./scripts/perf-gate.sh` exits 0 on current main
2. Intentionally inflate DOM (add 10,000 divs in a test branch) → gate fails
3. CI job passes on a clean PR

## Decisions

1. **Lighthouse dropped from CI.** DOM count + bundle size are deterministic proxies for the same regressions. Lighthouse is local-only tooling
2. **DOM count and export size are blocking.** API latency is warn-only (too noisy across CI runners)
3. **Doubling rule for thresholds.** Fail at 2x baseline, warn at 1.5x. Simple, auditable, catches real regressions without false positives from normal feature work

## Resolved

1. **Folded into the existing `e2e` job** (Apr 2026). Added `perf-gate.spec.ts` to `e2e/tests/`. The server identity guard prevents stale-server contamination; separate shell script and CI job were unnecessary.
2. **Results archive** — each run writes `e2e/perf-results.json` (latest snapshot) and appends one JSON line to `e2e/.perf-history.jsonl`. View with `./scripts/perf-history.sh`. Fancy charts (Observable/matplotlib/React page) tracked in `100days.md` §11 Operations → Could.
