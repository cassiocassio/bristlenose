---
status: partial
last-trued: 2026-10-14
trued-against: HEAD@main (6562c7be) on 2026-10-14
---

## Changelog

- _2026-10-14_ — trued up: per-session chaining (was #32) moved to Done with the conditions it runs under; Whisper's thread recorded under "Not worth optimising"; the issues heading no longer sends readers to closed issues. Anchors: `bristlenose/readable_chain.py`, `Pipeline._readable_chain` in `bristlenose/pipeline.py`, commits "progressive lenses phases 3 and 5: quotes found while the next session transcribes…" and "progressive lenses phase 3 review: the chain analyses only a true first analysis, and stage times are wall time".

# Performance Audit

Audited Feb 2026, re-confirmed against captured baselines Apr 2026. Stage concurrency shipped. Remaining items ranked by impact.

**Measurement procedures:** [`design-performance-monitoring.md`](design-performance-monitoring.md) indexes all three (regression gate in CI, stress test ad-hoc, FOSSDA manual). Run the FOSSDA baseline before/after any optimisation in this doc — procedure at [`design-perf-fossda-baseline.md`](design-perf-fossda-baseline.md), first baseline at [`trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md`](../trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md).

---

## Done

- **Concurrent per-participant LLM calls** — stages 5b, 8, 9 use `asyncio.Semaphore(llm_concurrency)` + `asyncio.gather()` to run up to 3 concurrent API calls per stage. Stages 10+11 (clustering + theming) also run concurrently via `asyncio.gather()`. For 8 participants, estimated ~2.5x speedup on LLM-bound time (~220s → ~85s)
- **Compact JSON in LLM prompts** — `quote_clustering.py` and `thematic_grouping.py` switched from `json.dumps(indent=2)` to `separators=(",",":")`. Saves 10–20% input tokens on the two cross-participant calls
- **FFmpeg VideoToolbox hardware decode** — `utils/audio.py` passes `-hwaccel videotoolbox` on macOS, offloading H.264/HEVC video decode to the Apple Silicon media engine. No-op for audio-only inputs and non-macOS platforms
- **Concurrent FFmpeg audio extraction** — `extract_audio_for_sessions()` is async with `asyncio.Semaphore(4)` + `asyncio.gather()`. Blocking `subprocess.run` calls wrapped in `asyncio.to_thread()`. Up to 4 FFmpeg processes in parallel. Default of 4 is optimal across all Apple Silicon (M1–M4 Ultra) — bottleneck is the shared media engine, not CPU cores
- **Cache `system_profiler` results** (#30) — `detect_hardware()` caches static hardware properties (chip_name, gpu_cores, memory_gb) to `~/.config/bristlenose/.hardware-cache.json` with 24h TTL. Dynamic properties (mlx_available, cuda_available) are always re-checked. Saves ~2–4s on macOS startup
- **Per-session chaining on a first analysis** (13 Oct 2026, was #32) — each session runs speakers → merge → topics → quotes as soon as Whisper finishes it, while the next session decodes (`bristlenose/readable_chain.py`). Whisper runs on its own thread so the chain's LLM calls overlap it. The chain's topic and quote calls run one session at a time per call, behind the `llm_concurrency` semaphore, and stages 8 and 9 take up its results by transcript fingerprint. **It runs only when all of these hold** (`Pipeline._readable_chain`, `_whisper_overlaps` in `pipeline.py`): no previous report rendered, no earlier topic or quote records, PII redaction off, intermediate files on, and a cloud provider. With the local provider the transcripts are still delivered session by session, but Whisper stays on the event loop and topics and quotes run as stages 8 and 9. On a re-analyse stages 8 and 9 run as batches, as before. Design and measurements: [`design-progressive-lenses.md`](design-progressive-lenses.md) Phase 3

---

## Open items

_The `#NN` numbers are GitHub issues #31–#35, all closed as not planned on 27 Sep 2026 with a pointer back here: this list is the tracker now._

### Quick wins

- **Skip logo copy when unchanged** (#31) — `render/report.py` runs `shutil.copy2()` on every render. Add size/mtime check first

### Medium effort

- ~~**Pipeline stages 8→9 per-participant chaining** (#32)~~ — _shipped in a different shape, see Done (13 Oct 2026). The plan as written:_ instead of "all stage 8 then all stage 9", run `_segment_single(p) → _extract_single(p)` as a chained coroutine per participant. Lets participant B's topic segmentation overlap with participant A's quote extraction
- **Pass transcript data to renderer** — `render_transcript_pages()` re-reads `.txt` files from disk even though the pipeline had all transcript data in memory. Thread `clean_transcripts` through to avoid redundant I/O
- **Temp WAV cleanup** (#33) — extracted WAV files in `output/temp/` are never cleaned up. ~115 MB per hour per participant; **FOSSDA baseline measured 944 MB left behind** on a 10-interview run ([pipeline-baseline.md](../trial-runs/fossda-opensource/perf-baselines/pipeline-baseline.md)). Add `shutil.rmtree(temp_dir)` after `_gather_all_segments`, guarded by config flag

### Larger effort

- **LLM response cache** (#34) — hash `(transcript + prompt + model)` → cache response JSON. Skip API calls on re-runs with unchanged transcripts. ~80 lines in `llm/client.py` + `--no-cache` flag
- **Word timestamp pruning** (#35) — `TranscriptSegment.words` stores per-word timing used only during merge. Drop after stage 6 to free memory (~80,000 Word objects for 10 interviews)
- **Per-model `llm_max_tokens` clamp** — default of 32,768 already exceeds provider caps for Haiku 3.5 (8K) and GPT-4o/mini (16K). Silent-fail potential if a user switches provider. Full context: [`design-perf-scale-and-tokens.md`](design-perf-scale-and-tokens.md). Recurring issue on real datasets (FOSSDA s5 dropped entirely on the baseline run)

---

## Not worth optimising (documented for posterity)

- **Whisper transcription is sequential**: GPU is already saturated by a single transcription. Parallelising wouldn't help on single-GPU machines. On CPU-only builds, `asyncio.to_thread()` could help but the speedup is marginal vs total transcription time. _Still true of decoding (13 Oct 2026): on a chained first analysis Whisper does run on a thread, but one thread, so that the LLM calls overlap it, not to decode files in parallel._
- **CSS/JS reads (32 small files)**: already lazy-cached in module-level globals. Only read once per process. Not a bottleneck
- **Intermediate JSON `indent=2` on disk**: adds ~15% file size vs compact JSON, but these files are for human debugging. Keep pretty-printed
- **Pydantic `model_dump()` serialisation cost**: called for every model when writing intermediate JSON. Profiling shows <100ms even for large quote lists
- **spaCy GPU acceleration for PII redaction**: benchmarked Feb 2026 — Presidio+spaCy processes 1,600 segments in ~6s on CPU (3.7ms/seg). For 10 participants that's 7.5s. Compared to transcription (~50 min for 10 participants) PII is 0.2% of total runtime. Adding `thinc-apple-ops` for Metal GPU would save single-digit seconds, add a dependency, and risk version compatibility issues
