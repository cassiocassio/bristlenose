# Performance Monitoring — Index

How we measure performance in Bristlenose, what each measurement caught, and where to look next. This doc is the top of the tree; every perf sub-doc is reachable from here.

For the **optimisation audit** (what we sped up in code) see [`design-performance.md`](design-performance.md).

## The framework: three measurements, three datasets, three cadences

| Measurement | Data | Catches | Cadence | Cost |
|---|---|---|---|---|
| **Regression gate** | Smoke fixture (4 quotes) | Linear creep — DOM bloat, bundle growth, export size, API latency | Every PR (CI) | Free, ~60s |
| **Stress test** | Synthetic (up to 3,000 quotes) | Non-linear cliffs — when does the browser choke? | Ad-hoc, before/after structural changes | Free, ~2 min |
| **FOSSDA baseline** | Real video (10 FOSSDA interviews) | Pipeline throughput — stage timing, memory, token cost | Manual, before/after pipeline optimisation | ~$5 API, ~35 min |

The philosophy: from `100days.md` §15, *"Safari's performance team made WebKit fast by never allowing it to become slower — every commit runs benchmarks, regressions are rejected before they land."* The three-plan structure follows:

- The **regression gate** enforces "never slower" on every PR.
- The **stress test** shows where the cliffs are, so we know when virtualisation is mandatory vs nice-to-have.
- The **FOSSDA baseline** grounds pipeline optimisation in real wall-clock numbers, not micro-benchmarks.

## Status (Apr 2026)

All three measurements are built, running, and have produced at least one baseline.

| Measurement | Status | See |
|---|---|---|
| Regression gate | Live in CI (`perf-gate` job, chromium-only, 90-day artifact) | [`design-perf-regression-gate.md`](design-perf-regression-gate.md) |
| Stress test | Sweep run 17 Apr 2026 | [`design-perf-stress-findings.md`](design-perf-stress-findings.md) + [`design-perf-stress-test.md`](design-perf-stress-test.md) |
| FOSSDA baseline | Captured 17 Apr 2026 | [`trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md`](../trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md) + [`design-perf-fossda-baseline.md`](design-perf-fossda-baseline.md) |

## What we learned (Apr 2026)

### The report SPA is not the bottleneck at any realistic scale

From the stress sweep ([findings](design-perf-stress-findings.md)):

- DOM cost is **linear** — ~39 nodes per quote, stable from n=100 to n=3000, no super-linear term.
- JS heap grows from ~10 MB to ~150 MB across the same range; comfortably under a 500 MB per-tab ceiling on 8 GB machines.
- Quotes API latency is the first thing to feel slow (180 ms at n=1500, 337 ms at n=3000) — backend serialisation, not frontend paint.
- Export size is linear too (~2.8 KB per quote, 1.56 MB + per-quote cost).

**Implication for launch:** virtualisation is not a beta-blocker. Someone running >1,000 quotes isn't evaluating a new tool for the first time anyway. Virtualisation remains on the S2 plan for the long tail.

**Caveat:** all measurements on M2 Max / 32 GB. Scroll jank and paint stalls arrive earlier on low-end hardware. A throttled-Chromium or actual-8GB-machine pass is worth doing before public beta.

### Token output caps are the recurring LLM failure mode

From FOSSDA baseline + cross-trial analysis ([scale-and-tokens](design-perf-scale-and-tokens.md)):

- Default `llm_max_tokens = 32768` truncated **one session** in the FOSSDA run (s5 was dropped entirely — ~50 quotes lost).
- Quote length varies ~6× across studies (oral history 140 token median, task-based 22 token median). Output volume isn't predictable from input size alone.
- Raising the default to 64K is safe for Sonnet 4 and Gemini 2.5. It's **not** safe for Haiku 3.5 (8K cap) or GPT-4o/mini (16K cap) — and we currently have no per-model clamp.
- The lasting fix is quote atomicity (see [design-quote-length.md](design-quote-length.md)); raising the cap is a stopgap.

### The real pipeline runs cleanly on FOSSDA

From the FOSSDA baseline ([results](../trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md)):

- 10 interviews / 490 min of audio → 36m 48s wall-clock, $3.11.
- Transcribe and Quote Extraction each take ~17 min — those are the two stages that matter for S2 optimisation.
- Peak RSS 3.27 GB; peak macOS memory footprint 24.88 GB (dominated by MLX model weights).
- Temp WAVs (944 MB) are **not cleaned up at end of run** — known optimisation item on [`design-performance.md`](design-performance.md).

### CI was silently red before perf-gate landed

Before the dedicated `perf-gate` job, the spec ran inside the `e2e` job but failed every run because `_BRISTLENOSE_AUTH_TOKEN` wasn't set. The `e2e` job is `continue-on-error: true` (parked S2 failures), so nobody noticed. Now the perf-gate job is isolated, auth'd, and red-is-red.

## Supporting infrastructure

- `scripts/download-fossda.sh` — FOSSDA dataset acquisition (10 OSS pioneer interviews from fossda.org).
- `scripts/generate-stress-fixture.py` — synthetic N-quote project generator.
- `scripts/perf-stress.sh` — stress orchestrator (picks ephemeral port, handles auth safely, writes JSON results).
- `scripts/perf-history.sh` — tabular viewer for `e2e/.perf-history.jsonl` (local append-only archive).
- `.claude/agents/perf-review.md` — adversarial PR review agent for frontend/CSS/bundle changes.
- LLM per-request latency logging in `bristlenose.log` (`llm_request | ... | elapsed_ms=N | ...`).
- Bundle size CI gate (pre-S1, 305 KB gzip via `size-limit`).

## Decisions worth keeping in mind

- **Doubling rule for thresholds.** Fail at 2× baseline, warn at 1.5×. Allows feature growth, catches regressions.
- **Lighthouse not in CI.** Too stochastic on shared runners. DOM count + bundle size are deterministic proxies.
- **API latency is warn-only.** Runner variance too high for hard gates.
- **Perf-gate is chromium-only.** Determinism > cross-browser coverage; WebKit peculiarities are noise at these scales.
- **History is artifact-only.** No CI-to-branch write. Offline analysis via `scripts/perf-history.sh` against the downloaded artifact.
- **Three separate ports:** 8150 (E2E smoke + perf-gate), ephemeral (stress), no port for FOSSDA (pipeline run).
- **Auth:** `_BRISTLENOSE_AUTH_TOKEN=test-token` env var — injected at job level in `ci.yml`, passed via Playwright `extraHTTPHeaders` and shell scripts.

## Cross-references

- Stress findings → confirm regression gate thresholds (no recalibration needed as of Apr 2026).
- Scale and tokens → informs LLM-layer work (per-model max-tokens clamp; quote atomicity).
- FOSSDA before → compare against after S2 ships (per-participant chaining, LLM response cache).

## Backlog

- **Per-model `llm_max_tokens` clamp.** Defaults exceed provider caps for Haiku 3.5 / GPT-4o / GPT-4o-mini. See [`design-perf-scale-and-tokens.md`](design-perf-scale-and-tokens.md).
- **Low-end-hardware stress pass.** Throttled Chromium or actual 8 GB machine before public beta.
- **Perf history charts.** Icebox — render `.perf-history.jsonl` as a trend chart. Currently view-only via `scripts/perf-history.sh`.
