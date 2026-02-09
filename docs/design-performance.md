# Performance Audit

Audited Feb 2026. Stage concurrency shipped. Remaining items ranked by impact.

---

## Done

- **Concurrent per-participant LLM calls** — stages 5b, 8, 9 use `asyncio.Semaphore(llm_concurrency)` + `asyncio.gather()` to run up to 3 concurrent API calls per stage. Stages 10+11 (clustering + theming) also run concurrently via `asyncio.gather()`. For 8 participants, estimated ~2.5x speedup on LLM-bound time (~220s → ~85s)
- **Compact JSON in LLM prompts** — `quote_clustering.py` and `thematic_grouping.py` switched from `json.dumps(indent=2)` to `separators=(",",":")`. Saves 10–20% input tokens on the two cross-participant calls
- **FFmpeg VideoToolbox hardware decode** — `utils/audio.py` passes `-hwaccel videotoolbox` on macOS, offloading H.264/HEVC video decode to the Apple Silicon media engine. No-op for audio-only inputs and non-macOS platforms
- **Concurrent FFmpeg audio extraction** — `extract_audio_for_sessions()` is async with `asyncio.Semaphore(4)` + `asyncio.gather()`. Blocking `subprocess.run` calls wrapped in `asyncio.to_thread()`. Up to 4 FFmpeg processes in parallel. Default of 4 is optimal across all Apple Silicon (M1–M4 Ultra) — bottleneck is the shared media engine, not CPU cores

---

## Open items (tracked in GitHub issues)

### Quick wins

- **Cache `system_profiler` results** (#30) — `utils/hardware.py` runs `system_profiler` twice on every startup (~2–4s on macOS). Cache to `~/.config/bristlenose/.hardware-cache.json` with 24h TTL. ~30 lines change
- **Skip logo copy when unchanged** (#31) — `render_html.py` runs `shutil.copy2()` on every render. Add size/mtime check first

### Medium effort

- **Pipeline stages 8→9 per-participant chaining** (#32) — instead of "all stage 8 then all stage 9", run `_segment_single(p) → _extract_single(p)` as a chained coroutine per participant. Lets participant B's topic segmentation overlap with participant A's quote extraction
- **Pass transcript data to renderer** — `render_transcript_pages()` re-reads `.txt` files from disk even though the pipeline had all transcript data in memory. Thread `clean_transcripts` through to avoid redundant I/O
- **Temp WAV cleanup** (#33) — extracted WAV files in `output/temp/` are never cleaned up. ~115 MB per hour per participant. Add `shutil.rmtree(temp_dir)` after `_gather_all_segments`, guarded by config flag

### Larger effort

- **LLM response cache** (#34) — hash `(transcript + prompt + model)` → cache response JSON. Skip API calls on re-runs with unchanged transcripts. ~80 lines in `llm/client.py` + `--no-cache` flag
- **Word timestamp pruning** (#35) — `TranscriptSegment.words` stores per-word timing used only during merge. Drop after stage 6 to free memory (~80,000 Word objects for 10 interviews)

---

## Not worth optimising (documented for posterity)

- **Whisper transcription is sequential**: GPU is already saturated by a single transcription. Parallelising wouldn't help on single-GPU machines. On CPU-only builds, `asyncio.to_thread()` could help but the speedup is marginal vs total transcription time
- **CSS/JS reads (32 small files)**: already lazy-cached in module-level globals. Only read once per process. Not a bottleneck
- **Intermediate JSON `indent=2` on disk**: adds ~15% file size vs compact JSON, but these files are for human debugging. Keep pretty-printed
- **Pydantic `model_dump()` serialisation cost**: called for every model when writing intermediate JSON. Profiling shows <100ms even for large quote lists
- **spaCy GPU acceleration for PII redaction**: benchmarked Feb 2026 — Presidio+spaCy processes 1,600 segments in ~6s on CPU (3.7ms/seg). For 10 participants that's 7.5s. Compared to transcription (~50 min for 10 participants) PII is 0.2% of total runtime. Adding `thinc-apple-ops` for Metal GPU would save single-digit seconds, add a dependency, and risk version compatibility issues
