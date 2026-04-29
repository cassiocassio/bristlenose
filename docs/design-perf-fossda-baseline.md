# Design: FOSSDA Pipeline Throughput Baseline

**Status (17 Apr 2026):** First baseline captured — [`trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md`](../trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md). Summary: 36m 48s wall-clock for 10 interviews (490 min audio), 238 quotes, $3.11. One LLM truncation on session s5 at default `max_tokens=32768` — see [`design-perf-scale-and-tokens.md`](design-perf-scale-and-tokens.md). This doc is the procedure for re-runs.

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

# 2. Record the hardware key (for comparing across runs)
.venv/bin/python -c "
from bristlenose.config import load_settings
from bristlenose.timing import build_hardware_key
print(build_hardware_key(load_settings()))
" > trial-runs/fossda-opensource/perf-baselines/hardware-key.txt

# 3. Run pipeline with timing
#    Defaults: --llm claude (→ anthropic), model from config
#    (claude-sonnet-4-20250514 as of 17 Apr 2026 — check hardware-key.txt
#    above to confirm what got resolved). Override with --llm if needed.
/usr/bin/time -l .venv/bin/bristlenose run trial-runs/fossda-opensource \
  2>&1 | tee trial-runs/fossda-opensource/perf-baselines/pipeline-run.log

# 3b. While the pipeline runs (after transcription starts), in a second
#     terminal, capture peak temp WAV size. Temp WAVs are written during
#     transcription and currently never cleaned up — but after the cleanup
#     optimisation ships, measuring at end-of-run gives zero. Run this
#     snapshot loop in a second terminal until the pipeline exits:
#
#        while pgrep -f 'bristlenose run' >/dev/null; do
#          date +%H:%M:%S
#          du -sk trial-runs/fossda-opensource/bristlenose-output/.bristlenose/temp/ \
#            2>/dev/null
#          sleep 30
#        done | tee trial-runs/fossda-opensource/perf-baselines/temp-wav-timeline.txt
#
#     Then extract the peak (kilobytes, converted to human-readable MB):
#
#        awk 'NF==2 {print $1}' \
#          trial-runs/fossda-opensource/perf-baselines/temp-wav-timeline.txt \
#          | sort -n | tail -1 \
#          | awk '{printf "peak_temp_wav_MB=%.1f\n", $1/1024}' \
#          > trial-runs/fossda-opensource/perf-baselines/temp-wav-peak.txt

# 4. Record output sizes
du -sh trial-runs/fossda-opensource/bristlenose-output/*/ \
  > trial-runs/fossda-opensource/perf-baselines/output-sizes.txt

# 5. Copy the timing summary from the log (strip ANSI colour codes)
grep '✓' trial-runs/fossda-opensource/perf-baselines/pipeline-run.log \
  | sed $'s/\033\\[[0-9;]*m//g' \
  > trial-runs/fossda-opensource/perf-baselines/stage-times.txt

# 6. Extract LLM request latencies from the log (one line per LLM call)
grep 'llm_request' \
  trial-runs/fossda-opensource/bristlenose-output/.bristlenose/bristlenose.log \
  > trial-runs/fossda-opensource/perf-baselines/llm-latencies.txt

# Summarise median and p95 latency
awk -F'elapsed_ms=' '{print $2}' \
  trial-runs/fossda-opensource/perf-baselines/llm-latencies.txt \
  | awk '{print $1}' | sort -n \
  | awk 'BEGIN{c=0} {a[c++]=$1} END{
      print "median="a[int(c/2)]"ms  p95="a[int(c*0.95)]"ms  n="c
    }' \
  >> trial-runs/fossda-opensource/perf-baselines/llm-latencies.txt

# 7. Record end-of-run temp WAV disk usage (separate file; may be zero after
#    the cleanup optimisation ships — see step 3b for peak mid-run size)
{
  echo "temp WAVs at end of run:"
  du -sh trial-runs/fossda-opensource/bristlenose-output/.bristlenose/temp/ \
    2>/dev/null || echo "(not present)"
} > trial-runs/fossda-opensource/perf-baselines/temp-wav-size.txt
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
- Hardware key: _paste contents of `hardware-key.txt` from step 2_
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
| Peak temp WAV (mid-run, from `temp-wav-peak.txt`) | ___ MB |
| End-of-run temp WAV (from `temp-wav-size.txt`) | ... |
```

## Output files

All results land in `trial-runs/fossda-opensource/perf-baselines/`, which is whitelisted in `.gitignore` (FOSSDA is open-source material so the measurements can be committed and diffed across runs; other `trial-runs/` data stays private).

| File | Purpose |
|------|---------|
| `pipeline-baseline.md` | Human-readable summary from the template in §Results format |
| `pipeline-run.log` | Raw pipeline stdout + `/usr/bin/time -l` tail (scrub any auth-token line before committing) |
| `hardware-key.txt` | Composite chip/backend/model key (step 2) |
| `stage-times.txt` | Per-stage elapsed (step 5, ANSI stripped) |
| `llm-latencies.txt` | LLM requests + median/p95 summary (step 6) |
| `temp-wav-timeline.txt` | Mid-run temp WAV snapshots (step 3b, optional) |
| `temp-wav-peak.txt` | Peak mid-run temp WAV in MB (step 3b post-process) |
| `temp-wav-size.txt` | End-of-run temp WAV size (step 7) |
| `output-sizes.txt` | Output directory sizes (step 4) |

No scripts to create — this is a manual procedure. The pipeline already prints everything we need.

## Comparing before/after

When per-participant chaining ships, stages 8 (topic segmentation) and 9 (quote extraction) will overlap via chained coroutines. The individual stage `✓` lines will mean something different — compare **combined topics + quotes wall-clock time**, not individual stage lines.

`stage-times.txt` captures **actual elapsed wall-clock** per stage, not the Welford-based ETA estimates that `timing.py` displays during a run. The ETA history in `~/.config/bristlenose/` is independent of this procedure and can be ignored for baselining.

## When to re-run

- After per-participant chaining ships (S2)
- After LLM response cache ships
- After any stage logic change that affects throughput
- Before launch (final baseline on release hardware)

## Non-goals

- Not automated — pipeline runs take 30+ minutes and cost real API tokens
- Not in CI — far too slow and expensive
- Not about frontend performance — that's covered by the regression gate and stress test
