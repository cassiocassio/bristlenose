# FOSSDA Pipeline Baseline — 17 Apr 2026

## Environment
- Machine: MacBook Pro M2 Max, 32 GB RAM
- Python: 3.12.13
- Whisper model: large-v3-turbo
- Whisper backend: MLX (via faster-whisper 1.2.1 / ctranslate2 4.7.0)
- Provider: Claude (claude-sonnet-4-20250514)
- LLM concurrency: 3 (default)
- Hardware key: `Apple M2 Max | mlx | large-v3-turbo | anthropic | claude-sonnet-4-20250514`
- Dataset: 10 FOSSDA interviews (6,367 transcript segments, 490m 45s audio)

## Stage Timing
| Stage | Time |
|-------|------|
| Ingest | 0.4s |
| Extract audio | 9.4s |
| Transcribe | 17m 21s |
| Identify speakers | 39.5s |
| Merge transcripts | 0.0s |
| Topic segmentation | 35.9s |
| Quote extraction | 17m 30s ⚠ |
| Cluster / group | 27.1s |
| Render | 4.5s |
| **Total** | **36m 48s** |

⚠ Quote extraction hit `max_tokens=32768` on at least one session; response was truncated. Suggests raising `BRISTLENOSE_LLM_MAX_TOKENS` and re-running before using this baseline as a strict target for that stage.

## Resource Usage
- Peak RSS (max resident set size): 3.27 GB
- Peak memory footprint (macOS, incl. mmap/compressed): 24.88 GB
- LLM tokens: 308,240 in · 145,947 out
- Estimated API cost: ~$3.11
- LLM request latency: median 7,167 ms, p95 373,808 ms (n=42)
- p95 is skewed by a single slow request (likely the truncation/retry path); median is the more honest steady-state latency.
- Run started: 2026-04-17 01:37 local time

## Output Sizes
| Directory | Size |
|-----------|------|
| transcripts-raw/ | 768 KB |
| sessions/ | 1.0 MB |
| assets/ | 700 KB |
| **Total (shareable output)** | **~2.5 MB** |
| Peak temp WAV (mid-run) | 943.5 MB |
| End-of-run temp WAV | 944 MB (not cleaned up) |

Temp WAVs are still present at end of run — the transcription stage does not currently delete them. Worth flagging as a cleanup task (see `docs/design-perf-fossda-baseline.md` step 3b note).

## Report Output
10 participants (10/10 named) · 6 screens · 15 themes · 238 quotes

## Notes for the next run
- Raise `BRISTLENOSE_LLM_MAX_TOKENS` beyond 32,768 to avoid the quote-extraction truncation before treating this as a strict stage-time target.
- When per-participant chaining ships in S2, compare **combined topic segmentation + quote extraction** wall-clock (here: 35.9s + 17m 30s ≈ 18m 6s), not individual stage lines.
- `/usr/bin/time -l real` also captured the serve-mode idle after pipeline completion — ignore it. The 36m 48s total above is the pipeline wall-clock as printed by the CLI.
