---
status: current
last-trued: 2026-10-04
trued-against: HEAD@main bd9a7f7d on 2026-10-04 — perf.yml (post-merge on main, hard); e2e/tests/perf-gate.spec.ts; check-bundle-budget.py (BUDGET_BYTES 222 kB) via ci.yml's `npm run size`
---

# Design: CI Performance Regression Gate

**Status (4 Oct 2026):** Shipped and live. The gate is
[`e2e/tests/perf-gate.spec.ts`](../e2e/tests/perf-gate.spec.ts), run by
**`.github/workflows/perf.yml`** — **post-merge on `main` only, and hard**
(no `continue-on-error`). All thresholds below are live. See
[`design-performance-monitoring.md`](design-performance-monitoring.md) for the
wider context.

The **bundle budget** is a separate, pre-merge gate: `scripts/check-bundle-budget.py`
in `ci.yml`'s *Check bundle size* step, ceiling **222 kB** gzipped first paint
(raised from 220 on 4 Oct for report undo). First paint measured **192,704 B
(19 chunks) at `bd9a7f7d`**, 29.3 kB under the ceiling, after the 4 Oct moves
in § Moves made. What is still on first paint that need not be, and whether to
ratchet the ceiling, is § Still open.

> **It is deliberately NOT a pre-merge gate, and that is a reversal of this
> doc's original design.** Until **20 May 2026** it was a `perf-gate` job inside
> `ci.yml` running on every push, exactly as §Goal and §CI-integration below
> still describe — so that description had been wrong for **four months** under
> a status line that read *"live and blocking"*. Runner noise and transient network failures were producing
> false positives that *silently stalled release-pipeline workflows*, so
> `628a3705` moved it post-merge: the regression signal is kept, and PRs and
> releases are no longer gated on it. `ci.yml:523-524` carries the forwarding
> comment; the rationale is at `perf.yml:3-8`.
>
> The consequence a cold reader needs: **your PR is not checked for perf
> regressions.** A regression lands on `main` and is caught on the next
> post-merge run — which is why a sustained red here is now watched by
> `check-release-ready.sh`'s `advisory workflows` row (`WF_ADVISORY` in
> `project.conf:91`), and why `docs/release-premortem.md` incident 12 exists.

## Changelog

- _2026-10-04_ — trued up: status block now covers the bundle budget (222 kB, 192,704 B at `bd9a7f7d`); Problem and metric-table numbers; headroom and the ratchet proposal recomputed; identity-guard snippet, export-fetch snippet and Auth handling matched to the spec; results-schema note matched to the CI artifact upload; dated note on the 3.38 MB export period; `ci.yml` line ref. Anchors: `scripts/check-bundle-budget.py:58`; `e2e/tests/perf-gate.spec.ts:113-120,196-212`; `.github/workflows/perf.yml:88-97`; `.github/workflows/ci.yml:523-524`; commits "bundle budget: 220 -> 222 kB for report undo", "first paint: the locale loader names only the namespaces the spa requests".
- _2026-09-20_ — trued up: the gate is post-merge on `main`, not pre-merge (see the banner above).

## Problem

We ship PRs without knowing whether they made the app slower or bigger. Bundle size has a gate (222 kB gzip, first-load — see below) but nothing catches DOM bloat, API latency regression, paint time regression, or export size growth. These are linear regressions — small datasets detect them fine.

## Goal

A CI job that runs on every PR, fails on regressions, passes in under 60 seconds. _(As-built: post-merge on `main`, not per-PR — see the status note above.)_ Uses the existing smoke-test fixture (1 session, 4 quotes). No LLM calls, no video, no large datasets.

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
| Analysis (`/report/signals/`) | 359 | — | |
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
| `/signals/sentiment` | 5ms | |
| `/signals/tags` | 4ms | |
| `/signals/codebooks` | 3ms | |
| `/sessions` | 5ms | |
| `/people` | 3ms | |
| `/health` | 1ms | |

All endpoints return in under 10ms for the 4-quote fixture. These are local-machine numbers — CI runners will be slower (expect 2–5x).

### Export HTML

| Metric | Baseline |
|--------|----------|
| Export file size | **1.6 MB** (1,638,619 bytes) |

> _4 Oct 2026:_ export size left this baseline once. From 21 Aug 2026 every
> locale and namespace was inlined into the export and a real project's file
> reached 3.38 MB, so the export gate here was red until 0.28.0 embedded one
> language and the measured file fell to 1.55 MB
> ([`design-export-locale.md`](design-export-locale.md)). The recalibration
> trigger *Export format changes* below fired twice without a re-baseline; that
> call is still open, not made here.

The export inlines all JS chunks uncompressed + theme CSS + base64 logos + transcript HTML. 1.6 MB for 4 quotes and 1 session. Mostly JS bundle overhead — the data payload is tiny.

## What to measure (thresholds)

Thresholds use a **doubling rule**: fail if a metric exceeds 2x baseline. This catches genuine regressions (accidentally rendering every quote twice, a leaked modal, a new dependency doubling bundle size) while allowing normal feature growth. Warn at 1.5x.

| Metric | Tool | Baseline | Warn | Fail | Rationale |
|--------|------|----------|------|------|-----------|
| Bundle size (JS gzip, first load) | `scripts/check-bundle-budget.py` | 192.7 kB (`bd9a7f7d`, 4 Oct 2026) | — | > 222 kB | Was `size-limit` at a claimed ~267 KB / 305 KB — neither number was ever enforced; the real one lived in `frontend/package.json`. See the section below |
| DOM nodes (quotes page) | Playwright `evaluate` | 549 | > 800 | > 1,100 | 2x fail. Catches leaked modals, duplicated renders, wrapper bloat |
| DOM nodes (transcript page) | Playwright `evaluate` | 374 | > 550 | > 750 | 2x fail. Catches per-segment wrapper regressions |
| DOM nodes (dashboard) | Playwright `evaluate` | 334 | > 500 | > 670 | Fixed structure — any doubling is a bug |
| DOM nodes (sessions) | Playwright `evaluate` | 304 | > 450 | > 600 | |
| Export HTML file size | in-spec `fetch` of `/api/projects/1/export` | 1.6 MB | > 2.5 MB | > 3.2 MB | 2x fail. Safari/WKWebView stall above ~20 MB; tracks growth early |
| API latency (quotes) | Playwright `performance.now()` | 6ms | > 100ms | — | Warn-only. CI runners add variance; catches N+1 queries but not a hard gate |
| API latency (dashboard) | Playwright `performance.now()` | 7ms | > 100ms | — | Warn-only |

### Dropped: Lighthouse in CI

Lighthouse FCP/CLS scores are stochastic on shared CI runners (CPU allocation varies between runs). DOM node count and bundle size are deterministic proxies for the same regressions. **Decision: drop Lighthouse from the CI gate.** Run it locally against the smoke fixture for ad-hoc profiling. (This line once asked for baseline scores to be recorded here; none ever were, as of 4 Oct 2026.)

### Recalibration triggers

Re-measure and update thresholds when:
- After first stress test scaling run — results may reveal the per-quote marginal DOM cost is higher than expected, requiring tighter thresholds. See [design-perf-stress-test.md](design-perf-stress-test.md)
- `@tanstack/virtual` ships — quotes page DOM should drop dramatically (still not a dependency as of 4 Oct 2026)
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

The perf-gate runs in its **own workflow** (`perf.yml`), against its own server
on the smoke fixture. Server identity guard (first test, serial mode) catches
stale servers on 8150 before wrong metrics are recorded.

> _Superseded 20 May 2026._ This read *"runs inside the existing E2E suite — no
> separate job, no orchestrator script, no separate port"*, which contradicted
> the §CI-integration paragraph four lines below it (*"a dedicated `perf-gate`
> job"*) even before the move made both false. Two adjacent sentences
> disagreeing is the tell that neither was being re-read.

### CI integration

A dedicated `perf-gate` job in **`.github/workflows/perf.yml`** runs perf-gate
against the smoke fixture **on push to `main` only** (`perf.yml:9-11`) —
post-merge, not pre-merge. Chromium-only
(`npx playwright test tests/perf-gate.spec.ts --project=chromium`,
`perf.yml:81`), `timeout-minutes: 25` to fail fast rather than sit on the 6h
job ceiling. The job sets `BN_RUN_PERF_GATE=1` and
`_BRISTLENOSE_AUTH_TOKEN=test-token` (smoke fixture has no real data, so the
token isn't a secret).

> _Superseded 20 May 2026 (recorded here 20 Sep)._ This paragraph read: *"A
> dedicated `perf-gate` job in `.github/workflows/ci.yml` runs perf-gate against
> the smoke fixture on every push. Chromium-only, `needs: [test,
> frontend-lint-type-test]`."* True until `628a3705`. The `needs:` chain went
> with the move — `perf.yml` is a separate workflow, so nothing gates on it and
> it gates nothing.

By default `npx playwright test` skips perf-gate — `testIgnore` in `e2e/playwright.config.ts` filters it out unless `BN_RUN_PERF_GATE=1`. That keeps the regular `e2e` job's coverage scoped to smoke specs.

On every CI run, results are archived for 90 days:

```
Artifact: perf-results-${{ github.run_id }}
Contents: e2e/perf-results.json, e2e/.perf-history.jsonl
```

Download the artifact locally and run `scripts/perf-history.sh` against the JSONL for a tabular trend view.

To run locally:

```bash
cd e2e && BN_RUN_PERF_GATE=1 _BRISTLENOSE_AUTH_TOKEN=test-token \
  npx playwright test tests/perf-gate.spec.ts --project=chromium
```

### Results schema

Each run appends a JSON line to `e2e/.perf-history.jsonl`:

```json
{
  "timestamp": "2026-04-16T15:58:02.996Z",
  "git_sha": "7e56768...",
  "runner": "local:darwin-arm64",
  "dom_quotes": 549,
  "dom_transcript_s1": 374,
  "dom_dashboard": 334,
  "dom_sessions": 304,
  "api_latency_quotes_ms": 11.6,
  "api_latency_dashboard_ms": 5.3,
  "export_html_bytes": 1638619
}
```

`git_sha` and `runner` make the JSONL comparable across machines. `runner` is `local:<platform>-<arch>` on dev machines and `ci:<os>:<run_id>` in GitHub Actions. The file is gitignored in the tree; CI uploads it with `perf-results.json` as a 90-day artifact (`perf.yml:88-97`, and Resolved #2 below).

### Server identity guard

The first thing the perf-gate spec does is verify it's talking to the smoke-test fixture, not a stale server from a previous manual session:

```typescript
// e2e/tests/perf-gate.spec.ts:113-120
test('server identity guard — smoke-test fixture', async ({ page, baseURL }) => {
  const res = await page.request.get(`${baseURL}/api/projects/1/info`, {
    headers: { Authorization: `Bearer ${authToken()}` },
  });
  expect(res.ok()).toBe(true);
  const data = await res.json();
  expect(data.project_name).toBe('Smoke Test');
});
```

This catches the exact failure we hit during baseline measurement — a stale `bristlenose serve` on port 8150 serving a different project (353 quotes instead of 4). Fails immediately with a clear message instead of producing silently wrong metrics.

### How thresholds work

The Playwright spec asserts `expect(domCount).toBeLessThan(t.fail)` per entry in `DOM_THRESHOLDS` (1,100 for the quotes page). Failures break CI. Warnings are `console.log` output only — they signal "getting close" without blocking.

Thresholds use a doubling rule: fail at 2x baseline, warn at 1.5x. Calibrated from measured baselines (see table above). API latency is warn-only (CI runner variance makes it unsuitable as a hard gate).

### Export size measurement

The spec fetches the export endpoint from inside the page and measures the body
(`e2e/tests/perf-gate.spec.ts:190-226`):

```ts
// inside page.evaluate — the token is read from the page
const res = await fetch(`${url}/api/projects/1/export`, {
  headers: token ? { Authorization: `Bearer ${token}` } : {},
});
expect(ok, `export returned ${status} — auth token missing?`).toBe(true);
// …then: warn > EXPORT_SIZE_WARN (2.5 MB), fail > EXPORT_SIZE_FAIL (3.2 MB)
```

This tests the real serve-mode export path (the same code that runs when a user
clicks "Download HTML").

Two details of the assertion are load-bearing, and both are the house
silent-failure defence rather than decoration: it asserts `res.ok` **inside**
the fetch, because a dropped auth token otherwise returns a ~50-byte error body
in 1 ms and registers as excellent latency at an excellent size; and it carries
an implausibly-small **floor** as well as a ceiling, so a broken export cannot
pass the gate by being empty.

> _Superseded._ This section described a `curl` + `wc -c` shell script capturing
> the file to `/tmp` for the spec to assert on afterwards. No such script was
> ever written — the measurement is in the spec, and there is nothing for a
> shell script to exit non-zero about.

### Auth handling

Set `_BRISTLENOSE_AUTH_TOKEN=test-token` as an env var before starting the server. Pass that token in Playwright via `extraHTTPHeaders` in the config, and send it explicitly on Node-side requests — the identity guard's `page.request.get` uses `authToken()`. The export measurement fetches from inside the page and reads `window.__BRISTLENOSE_AUTH_TOKEN__`; its `res.ok` assertion is what turns a missing token into a failure rather than a 50-byte pass.

### What this does NOT cover

- Scroll smoothness (needs real human + large dataset)
- Animation hitches (needs Xcode Instruments)
- Non-linear scaling breakpoints (needs synthetic 1,500-quote fixture)
- Pipeline throughput (needs real audio/video)

Those are covered by the stress test and FOSSDA plans.

## Verification

1. `cd e2e && BN_RUN_PERF_GATE=1 _BRISTLENOSE_AUTH_TOKEN=test-token npx playwright test tests/perf-gate.spec.ts --project=chromium`
   exits 0 on current `main`
2. Intentionally inflate DOM (add 10,000 divs in a test branch) → gate fails
3. The `Perf` workflow is green on `main` after the merge

> _Corrected 20 Sep 2026._ Step 1 read **`./scripts/perf-gate.sh` exits 0 on
> current main**. That script has never existed in this repo — the gate ships as
> a Playwright spec. Step 3 read *"CI job passes on a clean PR"*, which it
> cannot: the gate does not run pre-merge. A cold reader verifying this design
> would have run a missing script and then waited for a PR check that never
> appears.

## Decisions

1. **Lighthouse dropped from CI.** DOM count + bundle size are deterministic proxies for the same regressions. Lighthouse is local-only tooling
2. **DOM count and export size are blocking.** API latency is warn-only (too noisy across CI runners)
3. **Doubling rule for thresholds.** Fail at 2x baseline, warn at 1.5x. Simple, auditable, catches real regressions without false positives from normal feature work

## The bundle budget now measures first-load cost, not chunk filenames (5 Sep 2026)

`size-limit` measured a **filename allow-list**: one glob over `assets/*.js` plus
**22 negations**, each naming a chunk, so the lazy locale chunks stayed out of
the number. The negations existed for a good reason — adding a language is meant
to be size-neutral on the web (`CLAUDE.md` § i18n). But a chunk filename is a
bundler implementation detail, and Rolldown rechunks between vite minors.

`#143`'s reported +24 kB overage was traced to `vite 8.0.10 → 8.2.2` alone. Both
builds measured on this Mac, same source, nothing else changed:

| | 8.0.10 | 8.2.2 | Δ |
|---|---:|---:|---:|
| Counted by the old allow-list | 207.7 kB | **231.9 kB** | **+24.1 kB → red** |
| All emitted JS, gzipped | 944.9 kB | 938.5 kB | −6.3 kB |
| **Eagerly fetched by `index.html`** | **205.5 kB, 20 chunks** | **199.8 kB, 6 chunks** | **−5.7 kB, 14 fewer requests** |

**The gate failed a build that is strictly better**, and it was wrong in *both*
directions at once. `index.html` on 8.0.10 was eagerly loading `common-*`
(12.4 kB), `desktop-*` (11.4 kB), `settings-*` (3.4 kB) and `enums-*` — locale
chunks on the negation list, so a visitor paid for them and the budget did not.
Then 8.2 merged 225 chunks into 211, roughly 30 kB crossed from negated names
into counted ones, and the same list started over-counting instead.

Major-ignoring vite would not have helped either: `8.0.10 → 8.2.2` is a **minor**,
which the `semver-major` ignore never touched.

### The replacement

`scripts/check-bundle-budget.py`, run by `npm run size` and by CI's *Check bundle
size* step. It parses `index.html` and sums the gzipped size of every chunk the
entry document makes a visitor fetch before first paint — `<script src>` and
`<link rel="modulepreload">`. Anything reached by a dynamic `import()` is out, by
construction rather than by name, so the locale split keeps its property and no
rename can move the number.

Budget **held at 220 kB across the change**, deliberately: only the definition
moved, so the two are reviewable apart. Headroom is 15.4 kB on 8.0.10 and 20.8 kB
on 8.2.2.

It also refuses three ways of scoring well by being broken — an unbuilt tree, an
`index.html` referencing no JS, and a reference to a chunk not on disk — each of
which the old gate would have reported as 0 kB or as an improvement. And a chunk
that stops being lazy now *raises* the number, loudly, which is the regression
the allow-list could not see. Proof: `scripts/test-bundle-budget.py`, 16 cases,
offline, paired so the ratchet counts it proven.

`size-limit` and `@size-limit/file` are removed. Note `npm run size:why` never
worked — `@size-limit/why` was never installed, so the flag was silently ignored;
the per-chunk table is now the default output.

**Was open:** whether 220 kB is the right ceiling for the new definition. It was
chosen for an allow-list that was measuring something else, and it was 91–93% used.
Carried into § Still open, item 1.

_4 Oct 2026: raised to 222 kB for report undo (~1.2 kB at first paint). The
headroom above (15–21 kB in early September) had fallen to 126 B before that
change, with nothing having raised the alarm._ Where it went is now measured;
see the next section.

### Where the September headroom went (measured 4 Oct 2026)

**Method.** Throwaway `git worktree add --detach` checkouts at seven dates,
`frontend/node_modules` symlinked from main (the only dependency change in the
window was `lodash.deburr`, so this isolates source), `vite build --sourcemap
hidden`, then the eager set measured by HEAD's `check-bundle-budget.py --list`.
Chunk names reshuffle between builds (the 25 Sep and 4 Oct builds share almost
no names with 5 Sep), so a per-chunk diff alone is misleading: bytes were
attributed **per source file** from the sourcemaps, each chunk's gzipped size
shared pro-rata by raw bytes. The scripts are not in the tree; the recipe is
the paragraph.

| Commit (date) | First paint | Δ |
|---|---:|---:|
| `679294de` (5 Sep) | 204,607 B | — |
| `2419938c` (15 Sep) | 204,625 B | +18 |
| `934f7d65` (20 Sep) | 205,736 B | +1.1 kB |
| `59755757` (25 Sep) | 204,051 B | −1.7 kB |
| `9fd6af62` (30 Sep) | 205,660 B | +1.6 kB |
| `ebf482fc` (3 Oct) | 216,267 B | **+10.6 kB** |
| `b089a73e` (4 Oct) | 221,043 B | +4.8 kB |

Net +16.4 kB. The movers, gross (smaller offsets in both directions make up the rest):

1. **The Mac app's own strings, about +6.7 kB.** `en/desktop.json` was a
   static import in `i18n/index.ts`, so every browser visitor downloaded it —
   though it is registered only in desktop mode, and the SPA reads it at two
   `dt()` sites. The 21–22 Sep Swift i18n sweep moved the macOS chrome's prose
   into it (11.6 → 17.6 kB gzipped across ~20 commits). It is invisible in the
   totals because `common.json` lost ~5.8 kB the same week (the retired help
   modal's keys, `1ff44e60`) — the two cancelled, which is exactly why nobody
   saw it.
2. **Search, about +6.5 kB, 3–4 Oct.** `searchMatch`, `searchSuggest`,
   `searchTokens`, `searchBridge`, `NativeSearchSync`, `badgeStyle`,
   `lodash.deburr`, `useSearchAnnouncement`, and growth in `QuotesContext`.
3. **Report undo and the person picker, about +2.5 kB, 4 Oct**
   (`SessionsTable` +1 kB, `speakerNames`, `UndoStore`, `UndoSync`), plus
   ~1.6 kB of `common.json` copy.

Nothing was wrong with any of these individually. The gate fails only at the
ceiling, so 20 kB of headroom is spent silently by whoever arrives first, and
the one change that finally tripped it (undo, ~1.2 kB) is not where the money
went.

### Moves made (4 Oct 2026): 221,101 → 195,187 B

Measured from `e1763ea7`, which is 58 B over the `b089a73e` row above (a person-picker
commit landed between the two builds). Items 4 and 5 of § Still open later took it to
192,094 B; undo for quote edits brought HEAD to 192,704 B (`bd9a7f7d`).

| Move | Before | After | Δ |
|---|---:|---:|---:|
| `UncategorisedFloor` and `SessionsTable` import primitives by path, not via `components/index.ts` | 221,101 B | 213,289 B | −7.8 kB |
| English `desktop` namespace fetched on the Mac before mount, not bundled (`desktopEnReady`) | 213,289 B | 195,187 B | −18.1 kB |

The barrel finding sharpens `frontend/CLAUDE.md`'s rule: it was not one island
but **two statically routed modules** — `QuotesTab → UncategorisedFloor` and
`SessionsTab → SessionsTable` — and *either one alone* keeps the whole barrel on
first paint (measured: fixing only one saved 1.0 kB of the 7.8). Rolldown keeps
barrel members it cannot prove side-effect-free, so the cost was
`ThresholdReviewModal`, `ProposalZoneList`, `DualThresholdSlider`,
`ConfidenceHistogram`, `TagInput`, `ConfirmDialog`, `Counter`, `Metric`,
`Selector`, `Annotation` and others, none of which first paint renders. The
HTML export is unaffected by either move beyond +0.3 kB gzipped (the dynamic
import's wrapper, inlined).

Headroom after these two moves was **26.8 kB under 222 kB**; at `bd9a7f7d` it is
**29.3 kB**. `BUDGET_BYTES` was deliberately not touched.

## Still open

1. **Ratchet the ceiling, or the next 29 kB goes the same way.** The September
   slide happened because the gate is a cliff, not a ratchet. Proposal: lower
   `BUDGET_BYTES` to about 205 kB in its own commit that says why (≈12 kB of
   headroom over today's 192.7 kB, enough for a feature, not enough for a month of unexamined
   growth), and treat each later raise as the deliberate edit the script's
   header already asks for. Not done here: it is a policy call, and this task
   was asked not to move the number without one.
2. **The always-mounted modals, ~12 kB.** `SettingsModal` (7.6 kB, plus
   `ModalNav` 1.1 kB and `localeLabels`), `MiroExportPanel` (1.9 kB) and
   `FeedbackModal` (1.1 kB) are statically imported by `AppLayout` and
   rendered closed on every page. `React.lazy` plus mount-on-first-open would
   take them off first paint, but each is a CSS-fade overlay (`.visible`
   toggles opacity), so a component mounted already-open skips its fade on the
   first opening, and the first open waits on a chunk fetch. Preloading the
   chunk on idle and mounting it closed keeps both behaviours. Not made here
   because it changes first-open feel, which is a design call.
3. **Search, ~6.3 kB.** The matcher, suggester and tokenizer are needed only
   once someone types; `NativeSearchSync` (~1 kB) only on the Mac. Loading the
   engine on first focus of the field is the obvious split, but the field is on
   every searching lens and its suggestions are synchronous today — needs a
   look from whoever owns search.
4. ~~**`PlaygroundStore`, 2.2 kB of a dev-only feature.**~~ Done 4 Oct 2026:
   the sidebar reads `contexts/sidebarTuning.ts` (defaults, or the store's live
   values once the dev playground loads it), and the Ctrl+Shift+P/U chords in
   `useKeyboardShortcuts` import the store on use — that hook was a second
   static importer the proposal had missed. 195,190 → 192,856 B.
5. ~~**`localeLoader`'s glob map, 3.7 kB.**~~ Done 4 Oct 2026: an
   `import.meta.glob` over `common`, `settings`, `enums` and `desktop`, after
   checking nothing in `frontend/src` reads `preflight` or `server`.
   192,856 → 192,094 B — the map shed 1.2 kB, partly given back as
   shared-chunk compression, so the estimate above was optimistic.
6. **`react-router` is 31 kB**, the second-largest single source after
   `react-dom`. Its package exports map points every condition at
   `dist/development`, but that build is byte-identical in size to
   `dist/production` here (375,382 vs 375,383 B), so aliasing it buys nothing.
   Recorded so nobody spends the cycle again.


## Resolved

1. **Initial placement inside the `e2e` job, then split into a dedicated `perf-gate` job** (17 Apr 2026). The first attempt folded perf-gate into the existing `e2e` job, but `_BRISTLENOSE_AUTH_TOKEN` wasn't set — every CI run was red and nobody noticed because `e2e` is `continue-on-error: true`. Splitting into a dedicated job made failures visible: red-is-red, artifact scope is clean, perf signal isn't entangled with parked S2 smoke failures.
2. **Results archive** — each run writes `e2e/perf-results.json` (latest snapshot) and appends one JSON line to `e2e/.perf-history.jsonl`. In CI, both are uploaded as a 90-day artifact. View with `./scripts/perf-history.sh`. Fancy charts (Observable/matplotlib/React page) tracked in `100days.md` §11 Operations → Could.
