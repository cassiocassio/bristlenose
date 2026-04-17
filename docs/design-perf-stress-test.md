# Design: Synthetic Stress Test

**Status (17 Apr 2026):** Shipped. First scaling sweep run 17 Apr 2026 — see [`design-perf-stress-findings.md`](design-perf-stress-findings.md) for results. This doc is the design reference (how to run, what it measures, invariants).

## Problem

The quotes page renders every quote as a DOM node. A real 15-hour study produces ~1,500 quotes (~100/hour). That's ~30,000 DOM nodes without virtualisation. We need to know exactly where the browser starts choking — and prove that `@tanstack/virtual` (S2) fixes it.

Small datasets can't find this. The regression gate catches linear creep; this test finds the cliffs.

## Goal

A synthetic fixture generator + measurement script that:
1. Creates a realistic 1,500-quote project from nothing (no pipeline, no LLM, no audio)
2. Measures DOM count, scroll frame rate, API latency, export size at that scale
3. Runs locally in under 2 minutes
4. Runs again after virtualisation to prove the fix

## Fixture generator

### `scripts/generate-stress-fixture.py`

Generates a complete serve-mode-ready project directory:

```
trial-runs/stress-test-1500/
  bristlenose-output/
    .bristlenose/
      intermediate/
        metadata.json          # {"project_name": "Stress Test (1500 quotes)"}
        screen_clusters.json   # 8 sections, ~120 quotes each
        theme_groups.json      # 6 themes, ~80 quotes each (overlap with sections)
    transcripts-raw/
      s1.txt ... s5.txt        # 5 sessions, minimal transcript segments
    people.yaml                # 5 participants
```

**Dependency note**: the generator uses `pyyaml` for `people.yaml` — available in `.[dev]` extras but not base install. Run from the project venv.

Parameters (CLI flags):
- `--quotes N` (default 1500) — total quote count (~70% screen_specific in clusters, ~30% general_context in themes)
- `--sessions N` (default 5) — number of sessions
- `--sections N` (default 8) — number of screen_cluster sections
- `--themes N` (default 6) — number of theme groups
- `--output DIR` (default `trial-runs/stress-test-1500`)

### Quote generation strategy

Not random gibberish — realistic enough that the UI renders correctly:

- **Text**: draw from a pool of ~50 template sentences with slot-filling (participant name, feature area, sentiment word). Varying lengths (10–80 words). Real quote text matters because the DOM tree depends on text wrapping, tag badges, sentiment labels
- **Timecodes**: sequential within each session, non-overlapping, realistic gaps (2–30s between quotes)
- **Sentiment distribution**: match real data (~35% frustration, ~20% confusion, ~15% satisfaction, ~10% delight, ~8% doubt, ~7% surprise, ~5% confidence)
- **Quote type split**: ~70% `screen_specific` (go into `screen_clusters.json`), ~30% `general_context` (go into `theme_groups.json`). These are separate quotes with different timecodes — a quote never appears in both files. This matches the pipeline's exclusivity rule (Stage 9 assigns `QuoteType`, Stages 10/11 filter by type)
- **Section assignment**: each `screen_specific` quote belongs to exactly one screen cluster
- **Theme assignment**: each `general_context` quote belongs to exactly one theme group
- **Participants**: distributed across 5 sessions (p1–p5), roughly equal

### Transcript generation

Minimal but valid — the importer needs parseable transcripts to create sessions and speakers:

```
# Transcript: s1
# Source: Session 1.mp4
# Date: 2026-01-20
# Duration: 01:30:00

[00:10] [m1] Can you tell me about your experience?
[00:18] [p1] I found the dashboard pretty confusing at first.
[00:26] [m1] What was confusing about it?
...
```

Each quote's timecode range maps to a segment in the transcript. The moderator lines (m1) are interleaved.

## Measurement script

### `scripts/perf-stress.sh`

```
Usage: ./scripts/perf-stress.sh [--quotes N] [--skip-generate] [--with-lighthouse]
```

Steps:
1. Run `generate-stress-fixture.py` (unless `--skip-generate`)
2. Delete any existing `.bristlenose/bristlenose.db` (force fresh import)
3. Start `bristlenose serve trial-runs/stress-test-1500 --port 8153 --no-open`, timing the startup (`time` around wait-for-ready) — captures SQLite import duration
4. Wait for server ready. Log import time in summary table (if >20s at 1,500 quotes, that's a separate finding — batch inserts needed)
5. Run Playwright stress test (DOM counts, API timing)
6. Run Lighthouse against `/report/quotes/` (heaviest page)
7. Hit serve-mode export endpoint (`GET /api/projects/1/export`) and measure response size (the production export path — `bristlenose render` is deprecated)
8. Print summary table
9. Kill server

### Playwright stress spec: `e2e/tests/perf-stress.spec.ts`

Measures (does NOT assert thresholds — this is measurement, not gating):

| Metric | How |
|--------|-----|
| DOM node count (quotes container) | `document.querySelectorAll('.quote-group *').length` — scoped to quote content, excludes NavBar/sidebar/SVG noise. The `.quote-group` class wraps each section/theme; there is no `.quote-sections` wrapper in the current React tree |
| DOM node count (full page) | `document.querySelectorAll('*').length` — secondary metric for total page weight |
| Quote card count | `document.querySelectorAll('.quote-card').length` — primary signal, cleanest comparison. `data-testid="quote-card"` is not emitted; the CSS class is the stable selector |
| DOM node count (dashboard) | Scoped to dashboard container |
| DOM node count (transcript s1) | Scoped to transcript container |
| fetch roundtrip: `/api/projects/1/quotes` | Warm-up request first, then `performance.now()` around `fetch()`. Median of 3 runs. Note: this measures browser round-trip (JS queue + network + server + response delivery), not server-side time alone |
| fetch roundtrip: `/api/projects/1/codebook` | Same (the codebook endpoint powers the right sidebar's tag groups and quote counts) |
| Page load time (quotes) | `page.goto('/report/quotes/', { waitUntil: 'networkidle' })` — time from navigation start to interactive. Captures React render cost of mounting all QuoteCard components |
| Tag filter DOM delta | Count before/after applying a tag filter |
| Search DOM delta | Count before/after typing in search |

All timing metrics (fetch roundtrip, tag filter, search) use median-of-3 to reduce noise from macOS background processes, Chrome JIT warm-up, and Spotlight indexing. DOM counts are deterministic — single measurement is sufficient.

Output: `trial-runs/stress-test-1500/perf-baselines/stress-results.json`

### Lighthouse (optional, off by default — pass `--with-lighthouse` to enable)

Lighthouse will likely time out on unvirtualised 1,500-quote pages (returns `null` metrics, not poor scores). FCP/LCP are already captured cheaply via `performance.getEntriesByType("paint")` in the Playwright spec. Only enable Lighthouse when you specifically need the full audit (TTI, CLS, SI).

**Version pinning.** `e2e/package.json` pins Lighthouse as a devDependency so scoring weights don't drift between runs. Lighthouse's Chromium compatibility matrix and scoring weights changed materially between major versions (TTI was deprecated at v11 → v12). **Review pin: October 2026** — bump if the current range has been stable in upstream for a quarter.

## Scaling runs

Run the generator at multiple quote counts to find the cliff:

```bash
for n in 0 100 200 300 500 750 1000 1500 2000 3000; do
  ./scripts/perf-stress.sh --quotes $n
done
```

The `n=0` run establishes the fixed DOM overhead (sidebar, toolbar, codebook, SVG icons, modals) — the regression gate baseline shows 11,546 nodes for just 4 quotes, so the fixed cost is significant. Extra points at 200, 300, 750 add negligible run time but give a sharper inflection curve. The cliff is where frame rate drops below 30fps or DOM count exceeds browser paint budget (~10,000 nodes for smooth 60fps). The cliff shape also reveals whether the problem is O(n) linear paint cost or O(n²) layout reflow.

Results from this scaling run feed back into the regression gate — see [design-perf-regression-gate.md](design-perf-regression-gate.md) recalibration triggers. If the per-quote marginal DOM cost is higher than expected, the gate thresholds may need tightening.

## New files

| File | Purpose |
|------|---------|
| `scripts/generate-stress-fixture.py` | Synthetic fixture generator |
| `scripts/stress-tag-fixture.py` | Post-import DB augmentation for realistic tag fanout |
| `scripts/perf-stress.sh` | Orchestrator: generate, serve, measure, report |
| `e2e/tests/perf-stress.spec.ts` | Playwright: DOM counts, fetch roundtrip at scale |
| `e2e/playwright.stress.config.ts` | Chromium-only; honours `BN_STRESS_PORT` env |
| `trial-runs/stress-test-<N>/` | Output (gitignored via `trial-runs/`) |

## Verification

1. `./scripts/perf-stress.sh` completes and prints summary.
2. DOM count at 1,500 quotes is in the 55,000–65,000 range (59,202 observed 17 Apr 2026). Virtualisation is needed to ship that comfortably on low-end hardware, though scaling is clean and linear to n=3,000.
3. After `@tanstack/virtual` ships: re-run, DOM count should drop to ~1,000–2,000 regardless of quote count.
4. Export HTML at 1,500 quotes measured at 5.78 MB (fixed overhead 1.56 MB + ~2.8 KB per quote). Growth is per-quote content, not fixed overhead — confirms virtualisation/lazy rendering is the right lever.

Full scaling results: [`design-perf-stress-findings.md`](design-perf-stress-findings.md).

## Non-goals

- This is not a CI job — too slow, too environment-dependent
- No threshold assertions — measurement only. The regression gate handles thresholds
- No scroll smoothness measurement (Playwright can't measure perceived jank — that's manual)

## Review outcomes (Apr 2026)

Three review agents (`code-review`, `security-review`, `perf-review`) ran against the initial implementation via the `usual-suspects` skill. 23 numbered findings total.

### Actioned

- **Token safety (bugs 1–4, 19)** — heredoc interpolation removed in favour of `STRESS_EXPORT_*` env vars; `curl -v` dropped in favour of `-w` response metrics (`curl -v` echoed stdin-config content on some builds); `server.err` relocated outside the results tree with a redact-on-cleanup copy; startup-failure tail piped through `_redact`; `_BRISTLENOSE_AUTH_TOKEN` unset before the stats-merge Python block.
- **Portability (7)** — all `mktemp` calls use full-template form (works on BSD and GNU).
- **Selectors (8)** — design-doc table updated to match actual DOM: `.quote-group *` + `.quote-card`. The React tree has no `.quote-sections` wrapper and quote cards carry the CSS class but no `data-testid`.
- **Config deduplication (9)** — identity-guard test drops its explicit `Authorization` header; `extraHTTPHeaders` in `playwright.stress.config.ts` is the sole source of truth.
- **Stability polling (10, 13)** — `waitForPageReady` requires 3 consecutive equal 200ms polls and resets counters on each call, closing the race where two adjacent polls could false-stabilise mid-render at 1,500 quotes.
- **Metric rename (11)** — `api_latency_ms` → `fetch_roundtrip_ms` to reflect that it measures browser round-trip (JS queue + network + server), not server-side latency.
- **Lighthouse pin (12)** — pinned as `"lighthouse": "^12.0.0"` in `e2e/package.json`. Scoring weights drift between majors (TTI deprecated at v12). **Review pin: October 2026.**
- **Port randomisation (18)** — ephemeral port picked via `socket.bind(('127.0.0.1', 0))` and exported as `BN_STRESS_PORT`. Closes the check-then-bind race against a same-UID attacker.
- **Defence-in-depth (20, 22)** — `umask 077` around `mktemp` calls; Playwright `beforeAll` refuses to run if `trace !== 'off'` under `CI=true` (trace ZIPs bundle the bearer token from `extraHTTPHeaders`).
- **Sentinel guard (21)** — `generate-stress-fixture.py` refuses to `rmtree` any `--output` directory missing `.bristlenose-stress-fixture`; drops the sentinel on creation.
- **Summary box (23)** — long results-path moved outside the box so the border never overflows.
- **Realistic fixture (14)** — new `scripts/stress-tag-fixture.py` opens the per-project SQLite after import and adds two synthetic codebook groups (`User goals`, `Friction types`, 6 tags each, `framework_id="stress-*"`) with 1–2 tags per group applied per quote (`source="autocode"`). Real projects run AutoCode and produce ~3–5 tags per quote — the sidebar `/api/projects/{id}/codebook` endpoint now returns a realistic payload instead of sentiment-only floor.

### Auto-handled

- **Sed case-sensitivity (5)** — the `_redact` helper uses `[Aa]uthorization` + `[Bb]earer` so HTTP/2 lowercase headers would be caught. Not triggered in practice (uvicorn serves HTTP/1.1 plaintext locally).
- **Disputed perf-review claim (6)** — agent claimed `window.__BRISTLENOSE_AUTH_TOKEN__` was never set so API-latency tests would silently 401. Verified wrong: `bristlenose/server/app.py:311` injects the global on every `/report/*` response, and the smoke run showed real (non-401) latencies.

### Parked — worth revisiting

- **Identity-guard regex vs exact match (16)** — the Playwright spec asserts `/^Stress Test \(\d+ quotes?\)$/`; the orchestrator knows the exact count via `$STRESS_QUOTES`. The two checks disagree where they could match exactly. Tightening is safe but not urgent — the orchestrator-side exact check already fires before Playwright runs.
- **70/30 coin-flip vs deterministic index (17)** — `generate-stress-fixture.py` hand-rolls a 70/30 screen/theme split via coin-flip + drift correction. Switching to `i % 10 < 7` would be future-proof against ratio tweaks and consume less RNG, but would change every byte of today's fixture and break seed=0 continuity with existing baselines. Revisit if the 70/30 ratio ever changes, or if we need cross-version comparability.
- **Fixture "floor" variants** — the current fixture is "realistic" (AutoCode-simulated tags applied). If we want a pure "quote-card cost" floor measurement, add a `--no-tag-fanout` flag that skips the DB augmentation step. Not built — we have one realistic mode, not two.
