# Stress test findings: scaling to 3,000 synthetic quotes

Ran `./scripts/perf-stress.sh --quotes $n` for `n ∈ {0, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000}` on 17 Apr 2026 (Chromium on Apple M2 Max, 32 GB). Synthetic fixture, no real LLM calls. Full sweep took ~1m 47s end-to-end because per-run startup + 7 playwright tests is ~6–18s.

**Hardware caveat.** All numbers here are on an M2 Max with 32 GB RAM — the top-end consumer Mac. A beta user on an 8 GB MacBook Air or Chromebook will hit scroll jank and paint stalls noticeably earlier. The linear per-quote cost (~39 DOM nodes, ~2.8 KB export) doesn't change, but the threshold where it starts to *feel* slow shifts down. Worth re-running this sweep on a low-end machine before the public beta — or at least throttling Chromium to "4× slowdown" in a future pass to simulate it.

## Results

| n | DOM quotes | DOM dashboard | DOM transcript | Heap quotes (MB) | Heap dashboard (MB) | Heap transcript (MB) | quotes API (ms) | codebook API (ms) | export (MB) |
|----:|----------:|--------------:|---------------:|-----------------:|--------------------:|---------------------:|----------------:|------------------:|------------:|
|   0 |    425 |   335 |    286 |   9.5 |   9.5 |   9.5 |   4.2 |   4.9 | 1.56 |
| 100 |  4,586 |   436 |    992 |   9.5 |   9.5 |   9.5 |  13.2 |   7.3 | 1.88 |
| 200 |  8,486 |   436 |  1,749 |  15.4 |   9.5 |   9.5 |  21.1 |   7.9 | 2.16 |
| 300 | 12,386 |   436 |  2,466 |  18.4 |   9.5 |   9.5 |  27.2 |   9.0 | 2.44 |
| 500 | 20,200 |   436 |  3,897 |  26.3 |   9.5 |   9.5 |  69.6 |   8.1 | 3.00 |
| 750 | 29,950 |   436 |  5,713 |  37.8 |   9.5 |  10.7 |  92.6 |  10.3 | 3.69 |
| 1000 | 39,672 |  436 |  7,513 |  51.0 |   9.5 |  13.6 | 112.8 |  12.8 | 4.39 |
| 1500 | 59,202 |  436 | 11,102 |  77.6 |   9.5 |  23.4 | 180.3 |  16.6 | 5.78 |
| 2000 | 78,712 |  436 | 14,756 |  98.2 |   9.5 |  31.6 | 214.1 |  16.9 | 7.17 |
| 3000 | 117,724 | 436 | 21,898 | 149.7 |   9.5 |  37.8 | 337.4 |  22.7 | 9.98 |

Heap from `performance.memory.usedJSHeapSize` (Chromium-only, quantized to ~1 MB). Raw per-n results: `trial-runs/stress-test-$n/perf-baselines/stress-results.json` (gitignored).

**Heap stays well under any modern ceiling.** Dashboard is flat (9.5 MB — same aggregating-not-listing story as its DOM count). Quotes page grows from 9.5 MB baseline at n=0 to ~150 MB at n=3000, which is ~47 KB JS heap per quote (slightly super-linear — React fiber overhead compounds at scale). Transcript grows more slowly (~9 KB/quote). Add ~200–300 MB for Chromium's base memory + DOM native, and even n=3000 sits comfortably under 500 MB per tab — fine on an 8 GB machine alongside browser + OS + editor. JS heap is not the constraint; perceived responsiveness (scroll jank from DOM size) hits first.

## Where's the cliff?

**There isn't one up to 3,000 quotes.** Growth is clean and linear across every metric.

- **DOM grows at ~39 nodes/quote, constant.** 41.6 at n=100, 39.1 at n=3000 — the overhead per quote is stable, no super-linear term kicks in. Dashboard is flat (436 nodes regardless of n — it aggregates rather than lists). Transcript grows at ~7 nodes/quote.
- **Export size grows at ~2.8 KB/quote.** 1.56 MB baseline + ~2.8 KB per quote → 9.98 MB at n=3000.
- **API latency grows linearly for `/quotes`** (4 ms → 337 ms) and **sub-linearly for `/codebook`** (5 ms → 23 ms). No stair-step, no timeout.
- **Paint FCP is noisy and doesn't scale with n** (444 ms at n=0, 124 ms at n=1500). Warm-cache variation dominates the signal. Not a reliable metric at these scales.

## What this means

**Virtualisation (`@tanstack/virtual`, already on the S2 list) is not a beta blocker.**

- Only the quotes page is affected; dashboard and transcript aren't the pain point.
- Under the 50K-DOM "starts to feel sluggish" range through **n ≈ 1,000**.
- Above n ≈ 1,500 (59K nodes) scroll jank is perceptible; above n ≈ 3,000 (117K nodes) the browser pauses on filter/sort.
- Someone running >1,000 quotes through a tool is running a serious research engagement, not trying a new tool for the first time. That's a different audience profile from the beta. Virtualisation matters for them, and it's on the S2 plan anyway — but its absence doesn't block the beta.

**Export endpoint:**
- Export hits the regression gate's **fail threshold (3.2 MB)** somewhere around **n ≈ 550**. That's fine for real datasets (FOSSDA's real run: 1.6 MB at 238 quotes) but means the stress fixture will trip the gate if we ever point the gate at it. Current gate points at the 4-quote smoke fixture only — no conflict.

**Quotes API latency:**
- Starts to feel heavy around n=1500 (180 ms). That's the bucket where backend pagination or response compression becomes worth looking at. Virtualisation on the frontend doesn't help this — it's serialisation + transport time.

## Regression-gate recalibration — none needed

The existing thresholds in [e2e/tests/perf-gate.spec.ts:34-44](e2e/tests/perf-gate.spec.ts) are calibrated against the 4-quote smoke fixture with a doubling rule. The stress sweep confirms per-quote cost is stable, so the doubling rule will catch regressions regardless of fixture size. **No change required.**

Two caveats, for when someone decides to expand the gate:

1. If the smoke fixture ever grows past ~15 quotes, recompute baselines. At 4 quotes the quotes-page DOM is ~580 nodes (425 + 4×39), matching the observed 549 baseline within jitter. Jump to 20 quotes and baseline drifts to ~1,200 — above the current fail threshold.
2. If we want to add a cheaper "scaling" test to CI using a 100- or 500-quote fixture instead of 4, the per-n results here give deterministic expected values to threshold against.

## What to do next (out of scope for this doc)

1. **Raise `BRISTLENOSE_LLM_MAX_TOKENS` default from 32K → 64K** ([design-perf-scale-and-tokens.md](design-perf-scale-and-tokens.md)) — unrelated to this sweep but the other recurring perf issue.
2. **Land `@tanstack/virtual` on the quotes page in S2** — priority ordering: projects with >1,500 quotes will thank us; most users won't notice.
3. **Track export size as a linear baseline** (`export_mb ≈ 1.56 + 0.0028 × n`). If a future change bumps per-quote export cost above ~3 KB, something regressed structurally.

## Files

- [scripts/perf-stress.sh](scripts/perf-stress.sh) — orchestrator
- [e2e/tests/perf-stress.spec.ts](e2e/tests/perf-stress.spec.ts) — Playwright spec (7 tests)
- `trial-runs/stress-test-$n/perf-baselines/stress-results.json` — raw results (gitignored)
- [docs/design-performance-monitoring.md](design-performance-monitoring.md) — index
