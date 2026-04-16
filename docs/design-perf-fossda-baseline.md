# Design: FOSSDA Pipeline Throughput Baseline

## Problem

We don't know how long the full pipeline takes on a real dataset of meaningful size. Stage timing is printed to the terminal during a run, but we've never recorded a baseline against a consistent corpus. When we optimise pipeline stages (S2: per-participant chaining, LLM response cache), we need before/after numbers.

## Goal

Run the full pipeline against FOSSDA (10 interviews, ~10 hours), record per-stage wall-clock times, and save the results as a reference baseline. This is a **manual, one-off** task — not automated, not CI.

## Dataset

Already downloaded and processed: `trial-runs/fossda-opensource/` (10 MP4 interviews, open-source pioneers from fossda.org). The pipeline output already exists — this task re-runs it fresh to capture timing.

## What to measure

| Metric | Source | Notes |
|--------|--------|-------|
| Per-stage wall-clock time | CLI stdout (checkmark lines with timing) | Already printed by the pipeline |
| Total pipeline wall-clock time | `time` command wrapper | Start to finish |
| LLM token usage | Provider billing / `bristlenose.log` | Cost per run |
| Peak memory (RSS) | `/usr/bin/time -l` on macOS | Memory pressure on 8GB machines |
| Output sizes | `du -sh` on output subdirectories | Transcripts, JSON intermediates, HTML |

## Procedure (manual)

Before starting: machine should be idle for 10+ minutes (thermal stabilisation). Lid open, connected to power if on a laptop. Sustained Whisper workloads trigger thermal throttling on Apple Silicon after 10–20 minutes — a warm re-run can be 15–30% slower than a cold one.

```bash
# 1. Clear existing output (force fresh run)
rm -rf trial-runs/fossda-opensource/bristlenose-output
mkdir -p trial-runs/fossda-opensource/perf-baselines

# 2. Run pipeline with timing
/usr/bin/time -l .venv/bin/bristlenose run trial-runs/fossda-opensource \
  --provider anthropic --model claude-sonnet-4-20250514 \
  2>&1 | tee trial-runs/fossda-opensource/perf-baselines/pipeline-run.log

# 3. Record output sizes
du -sh trial-runs/fossda-opensource/bristlenose-output/*/ \
  > trial-runs/fossda-opensource/perf-baselines/output-sizes.txt

# 4. Copy the timing summary from the log
grep '✓' trial-runs/fossda-opensource/perf-baselines/pipeline-run.log \
  > trial-runs/fossda-opensource/perf-baselines/stage-times.txt

# 5. Extract LLM request latencies (median/p95) from the log
grep -i 'request.*ms\|latency\|duration' .bristlenose/bristlenose.log \
  > trial-runs/fossda-opensource/perf-baselines/llm-latencies.txt

# 6. Record temp WAV disk usage (baseline for cleanup optimisation)
du -sh trial-runs/fossda-opensource/bristlenose-output/.bristlenose/temp/ \
  >> trial-runs/fossda-opensource/perf-baselines/output-sizes.txt
```

## Results format

Write to `trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md`:

```markdown
# FOSSDA Pipeline Baseline — DD Mon YYYY

## Environment
- Machine: MacBook Pro M_ __, ___GB RAM
- Python: 3.1_
- Whisper model: large-v3-turbo (or whichever `whisper_model` was resolved)
- Whisper backend: mlx / faster-whisper / openai-api (resolved value, not "auto")
- Provider: Claude (claude-sonnet-4-20250514)
- LLM concurrency: 3 (default — record actual `llm_concurrency` value)
- Hardware key: `chip | backend | whisper_model | provider | model` (from `build_hardware_key()` in `timing.py`)
- Dataset: 10 FOSSDA interviews

## Stage Timing
| Stage | Time |
|-------|------|
| Extract audio | ... |
| Transcribe | ... |
| ... | ... |
| **Total** | **...** |

## Resource Usage
- Peak RSS: ___MB
- LLM tokens: ___ input, ___ output
- Estimated API cost: $___
- LLM request latency: median ___ms, p95 ___ms (from bristlenose.log)
- Run started: YYYY-MM-DD HH:MM local time (API load varies by time of day)

## Output Sizes
| Directory | Size |
|-----------|------|
| transcripts-raw/ | ... |
| .bristlenose/intermediate/ | ... |
| sessions/ | ... |
| Total | ... |
```

## New files

| File | Purpose |
|------|---------|
| `trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md` | Results (gitignored) |
| `trial-runs/fossda-opensource/perf-baselines/pipeline-run.log` | Raw log (gitignored) |

No scripts to create — this is a manual procedure. The pipeline already prints everything we need.

## Comparing before/after

When per-participant chaining ships, stages 8 (topic segmentation) and 9 (quote extraction) will overlap via chained coroutines. The individual stage `✓` lines will mean something different — compare **combined topics + quotes wall-clock time**, not individual stage lines.

## When to re-run

- After per-participant chaining ships (S2)
- After LLM response cache ships
- After any stage logic change that affects throughput
- Before launch (final baseline on release hardware)

## Non-goals

- Not automated — pipeline runs take 30+ minutes and cost real API tokens
- Not in CI — far too slow and expensive
- Not about frontend performance — that's covered by the regression gate and stress test
