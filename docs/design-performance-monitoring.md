# Performance Monitoring — Index

How we measure performance in Bristlenose, and what's been built. This doc indexes the three measurement plans and tracks their delivery status.

For the **optimisation audit** (what was sped up, what's still slow), see [`design-performance.md`](design-performance.md).

## The framework: three plans, three datasets, three jobs

| Plan | Data | Catches | Cadence | Cost |
|---|---|---|---|---|
| **Regression gate** | Smoke fixture (4 quotes) | Linear creep — DOM bloat, bundle growth, export size, API latency | Every PR (CI) | Free, ~60s |
| **Stress test** | Synthetic (1,500 quotes) | Non-linear cliffs — when does the browser choke? | Before/after virtualisation | Free, ~2 min |
| **FOSSDA baseline** | Real video (10 interviews) | Pipeline throughput — stage timing, memory, token cost | Manual, before/after stage optimisation | ~$5 API, ~30 min |

Design docs:
- [`design-perf-regression-gate.md`](design-perf-regression-gate.md)
- [`design-perf-stress-test.md`](design-perf-stress-test.md)
- [`design-perf-fossda-baseline.md`](design-perf-fossda-baseline.md)

## What's built

### Regression gate — partly shipped

- `e2e/tests/perf-gate.spec.ts` — DOM counts, API latency, export size assertions
- `scripts/perf-history.sh` — viewer for `e2e/.perf-history.jsonl` (gitignored, append-only local archive)
- Doubling-rule thresholds (fail at 2× baseline). Quotes page = 549 nodes baseline, export = 1.6 MB
- E2E auth bug fixed along the way
- Silent-pass assertions, robust waits, schema forward-compat
- **Not yet wired into `.github/workflows/ci.yml`** — the spec exists but isn't a CI job yet

### Stress test — shipped

- `scripts/generate-stress-fixture.py` — synthetic project generator, no LLM
- `scripts/perf-stress.sh` — orchestrator
- `e2e/tests/perf-stress.spec.ts` — measurement-only Playwright spec
- Scaling run includes `n=0` for fixed-overhead measurement
- Lighthouse off-by-default (times out on 1,500-quote pages)
- **Not yet run for the scaling sweep** — produces results when invoked

### FOSSDA baseline — procedure documented, not yet run

- Pure manual procedure — no scripts to write
- Captures hardware key, peak temp WAV size mid-run, ANSI-stripped stage times, LLM latency median/p95
- Pipeline LLM latency logging added (`3ca4396`) so the procedure has data to extract

### Supporting infrastructure (this week)

- `scripts/download-fossda.sh` — dataset acquisition (10 OSS pioneer interviews from fossda.org)
- `.claude/agents/perf-review.md` — adversarial PR review agent (catches new deps without size justification, unvirtualised lists, missing `passive: true`)
- LLM per-request latency logging in `bristlenose.log`
- Bundle size CI gate (already shipped pre-S1, 305 KB gzip via `size-limit`)
- E2E gotchas documented (networkidle fragility, silent-pass fetches)

## Cross-references between plans

- Stress test scaling results → recalibrate regression gate thresholds
- FOSSDA before/after numbers → validate per-participant chaining (S2) and LLM cache wins
- Regression gate baseline (11,546 nodes for 4 quotes) → flagged the export size question for stress test to investigate
- Stress test → will reveal whether export bloat is fixed-overhead (gzip JS chunks) or per-quote (virtualisation)

## What's left

1. ~~**Wire perf-gate into CI**~~ — **done 17 Apr 2026**. New `perf-gate` job in `.github/workflows/ci.yml`, chromium-only, 90-day artifact retention on `perf-results.json` + `.perf-history.jsonl`. Perf-gate now runs only via `BN_RUN_PERF_GATE=1` (set in the dedicated job); default e2e run skips it
2. ~~**Run the stress test scaling sweep**~~ — **done 17 Apr 2026**. Linear scaling confirmed, no cliff up to n=3000. See [design-perf-stress-findings.md](design-perf-stress-findings.md). No gate recalibration needed
3. ~~**Run FOSSDA baseline**~~ — **done 17 Apr 2026**. 36m 48s, 238 quotes, $3.11. One LLM truncation on s5 at default max_tokens=32768. See [trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md](../trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md) and [design-perf-scale-and-tokens.md](design-perf-scale-and-tokens.md)
4. **Perf history charts** (post-launch icebox) — render `.perf-history.jsonl` over time as a chart. Currently view-only via `scripts/perf-history.sh` (tabular)

## Decisions worth noting

- **Lighthouse dropped from CI** — too stochastic on shared runners. DOM count + bundle size are deterministic proxies
- **Doubling rule for thresholds** — fail at 2× baseline, not arbitrary numbers. Allows feature growth, catches regressions
- **API latency is warn-only** in CI — runner variance too high for hard gates
- **Three separate ports**: 8150 (E2E smoke), 8153 (stress), no port for FOSSDA (pipeline run)
- **Auth pattern**: `_BRISTLENOSE_AUTH_TOKEN=test-token` env var, passed via Playwright `extraHTTPHeaders` and `curl -H Authorization` in shell scripts

## Philosophy

From `100days.md` §15: *"Safari's performance team made WebKit fast by never allowing it to become slower — every commit runs benchmarks, regressions are rejected before they land. The report SPA is the core product surface inside both the macOS app and the CLI. It needs the same discipline."*

The three-plan structure follows from this:
- The regression gate enforces the "never slower" rule on every PR
- The stress test reveals where the cliffs are, so we know when virtualisation is mandatory vs nice-to-have
- The FOSSDA baseline grounds optimisation work in real wall-clock numbers, not micro-benchmarks
