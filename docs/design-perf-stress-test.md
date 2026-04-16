# Design: Synthetic Stress Test

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
| DOM node count (quotes container) | `document.querySelectorAll('.quote-sections *, .quote-themes *').length` — scoped to quote content, excludes NavBar/sidebar/SVG noise |
| DOM node count (full page) | `document.querySelectorAll('*').length` — secondary metric for total page weight |
| Quote card count | `document.querySelectorAll('[data-testid="quote-card"]').length` — primary signal, cleanest comparison |
| DOM node count (dashboard) | Scoped to dashboard container |
| DOM node count (transcript s1) | Scoped to transcript container |
| API latency: `/api/projects/1/quotes` | Warm-up request first, then `performance.getEntriesByType("resource")` for `responseEnd - requestStart`. Median of 3 runs |
| API latency: `/api/projects/1/tag-groups-with-quotes` | Same |
| Page load time (quotes) | `page.goto('/report/quotes/', { waitUntil: 'networkidle' })` — time from navigation start to interactive. Captures React render cost of mounting all QuoteCard components |
| Tag filter DOM delta | Count before/after applying a tag filter |
| Search DOM delta | Count before/after typing in search |

All timing metrics (API latency, tag filter, search) use median-of-3 to reduce noise from macOS background processes, Chrome JIT warm-up, and Spotlight indexing. DOM counts are deterministic — single measurement is sufficient.

Output: `trial-runs/stress-test-1500/perf-baselines/stress-results.json`

### Lighthouse (optional, off by default — pass `--with-lighthouse` to enable)

Lighthouse will likely time out on unvirtualised 1,500-quote pages (returns `null` metrics, not poor scores). FCP/LCP are already captured cheaply via `performance.getEntriesByType("paint")` in the Playwright spec. Only enable Lighthouse when you specifically need the full audit (TTI, CLS, SI).

## Scaling runs

Run the generator at multiple quote counts to find the cliff:

```bash
for n in 100 200 300 500 750 1000 1500 2000 3000; do
  ./scripts/perf-stress.sh --quotes $n
done
```

Extra points at 200, 300, 750 add negligible run time but give a sharper inflection curve. The cliff is where frame rate drops below 30fps or DOM count exceeds browser paint budget (~10,000 nodes for smooth 60fps). The cliff shape also reveals whether the problem is O(n) linear paint cost or O(n²) layout reflow.

## New files

| File | Purpose |
|------|---------|
| `scripts/generate-stress-fixture.py` | Synthetic fixture generator |
| `scripts/perf-stress.sh` | Orchestrator: generate, serve, measure, report |
| `e2e/tests/perf-stress.spec.ts` | Playwright: DOM counts, API timing at scale |
| `e2e/playwright.stress.config.ts` | Config: stress fixture, port 8153, Chromium only |
| `trial-runs/stress-test-1500/` | Output (gitignored via `trial-runs/`) |

## Verification

1. `./scripts/perf-stress.sh` completes and prints summary
2. DOM count at 1,500 quotes is ~25,000–35,000 (confirming virtualisation is needed)
3. After `@tanstack/virtual` ships: re-run, DOM count drops to ~1,000–2,000 regardless of quote count
4. Export HTML at 1,500 quotes is under 2 MB (or we know the ceiling)

## Non-goals

- This is not a CI job — too slow, too environment-dependent
- No threshold assertions — measurement only. The regression gate handles thresholds
- No scroll smoothness measurement (Playwright can't measure perceived jank — that's manual)
