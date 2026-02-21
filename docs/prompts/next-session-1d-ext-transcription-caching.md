# Next session prompt: Phase 1d-ext — Per-session caching for transcription and speaker ID

## Context

Phase 1d is done — stages 8 (topic segmentation) and 9 (quote extraction) now track which sessions completed, so a crashed/interrupted run only re-processes remaining sessions on resume. The CLI guard in `cli.py` also allows re-running into an existing output directory when a manifest exists.

But stages 1–7 always re-run on resume. Measured data from project-ikea (4 sessions, Apple M2 Max) shows transcription is **52% of resume wall time** (56s of 1m 48s). On a 20-session project with longer recordings, transcription could be 4+ minutes — all wasted on resume.

Phase 1d-ext adds per-session caching for transcription (biggest win) and speaker identification (saves time + LLM money).

## Measured data (project-ikea, 4 sessions, Apple M2 Max, Feb 2026)

| Stage | Time | % of resume | LLM cost | Cacheable? |
|---|---|---|---|---|
| Ingest | 0.4s | <1% | — | No (fast, always re-run) |
| Extract audio | 0.5s | <1% | — | Easy (`.wav` on disk) |
| **Transcribe** | **56s** | **52%** | — | **Yes — biggest win** |
| **Identify speakers** | **7.5s** | **7%** | **~$0.02** | **Yes — saves time + money** |
| Merge transcripts | 0.0s | <1% | — | No (instant) |
| Topic segmentation | (cached) | 0% | $0 | Done (Phase 1d) |
| Quote extraction | 34.5s | 32% | ~$0.22 | Done (Phase 1d) |
| Cluster + group | 8.9s | 8% | ~$0.02 | Phase 1c stage-level |

## What to build

### 1. Transcription caching (priority 1 — biggest time win)

**How it differs from stages 8–9**: Transcription produces one file per session in `transcripts-raw/` (e.g. `session-id.txt`, `session-id.md`). The caching check is **file-existence-based** rather than JSON-filtering-based — check which session transcript files already exist on disk.

**Current flow in `pipeline.py`**:
1. `_gather_all_segments(sessions, ...)` — processes all sessions (transcribes audio or parses existing transcripts)
2. `_collate_transcripts(sessions, session_segments)` — builds `list[SessionTranscript]`
3. `write_raw_transcripts(transcripts, raw_dir)` / `write_raw_transcripts_md(...)` — writes to `transcripts-raw/`

**Proposed per-session caching flow**:
1. Check which sessions already have transcript files in `transcripts-raw/` (file existence check)
2. Load cached transcripts for those sessions using `load_transcripts_from_dir()` (already exists as a public function)
3. Only pass remaining sessions to `_gather_all_segments()`
4. Mark completed sessions in the manifest via `mark_session_complete()`
5. Merge cached + fresh transcripts
6. Write merged results to `transcripts-raw/` (fresh ones only, or overwrite all — TBD)

**Key consideration**: `_gather_all_segments()` handles both transcription (audio → text) and parsing (existing `.vtt`/`.srt`/`.docx` → segments). Parsing is fast. We could:
- (a) Cache all of it uniformly (simpler, but skips fast re-parsing)
- (b) Only cache transcription results (more complex, distinguishes audio vs text sources)

Option (a) is simpler and probably correct — the researcher doesn't care why it's fast, they care that it resumes quickly.

**Interaction with downstream stages**: Speaker identification (stage 4) and transcript merging (stage 5) operate on the output of transcription. If transcription is cached, their input doesn't change, so they should produce identical output. But they currently always re-run. We could:
- Cache speaker identification too (see below)
- Or let it re-run on cached transcripts (fast-ish, but wastes an LLM call)

### 2. Speaker identification caching (priority 2 — saves time + LLM money)

**Current flow**: `identify_speaker_roles_llm()` takes `session_segments` and calls the LLM per session to identify speaker roles/names. Returns `list[SpeakerInfo]`.

**Challenge**: Speaker identification results aren't written as per-session files — they're applied in-place to segments and merged into the final transcript. Need to decide where to cache them.

**Options**:
- (a) Cache the `SpeakerInfo` list per session in the manifest's `SessionRecord` (new field)
- (b) Write a small per-session JSON file (e.g. `speaker-info/session-id.json`)
- (c) Infer caching from the transcript files — if a transcript exists with speaker names already assigned, skip speaker ID

Option (c) is tricky because raw transcripts might not contain speaker info. Option (b) is cleanest — matches the file-per-session pattern. Option (a) bloats the manifest.

### 3. Audio extraction caching (priority 3 — marginal, probably skip)

Audio extraction produces `.wav` files in `.bristlenose/temp/`. These already persist across runs. Could check for existing `.wav` files and skip extraction. But it's only 0.5s for 4 sessions — not worth the complexity unless projects are very large.

## Files to change

- `bristlenose/pipeline.py` — transcription stage gets per-session caching logic; speaker ID stage optionally too
- `bristlenose/manifest.py` — possibly `mark_session_complete()` calls for transcription stage (reuse existing infrastructure)
- `tests/test_pipeline_resume.py` — new tests for transcription caching

## Key constraints

- `load_transcripts_from_dir()` is a public function already used by `render_html.py` — don't change its interface
- `_gather_all_segments()` is a private method on `Pipeline` — can be modified freely
- The manifest already supports `SessionRecord` on any stage — reuse the Phase 1d infrastructure
- The `transcripts-raw/` directory already has per-session files — the caching signal is file existence
- `write_raw_transcripts()` writes one `.txt` file per session — matches the per-session caching model perfectly

## Open questions (resolve before implementing)

1. **Should parsing (VTT/SRT/DOCX) be cached too, or only audio transcription?** Parsing is fast but not free — a 20-session project with existing VTT files still takes a few seconds to re-parse
2. **How to cache speaker identification results?** Per-session JSON file in `speaker-info/`? Or inline in the manifest?
3. **Should `merge_transcript` be cached too?** It's instant now, but it depends on speaker ID output. If speaker ID is cached, merge input doesn't change, so merge output doesn't change either
4. **What about `_collate_transcripts()`?** It's called after `_gather_all_segments()` — does it need to handle mixed cached/fresh segments?
5. **Interaction with `--clean`**: `--clean` already wipes the output directory including `transcripts-raw/`. No special handling needed — but verify

## Risk

Low-medium. The file-existence check is simpler than the JSON-filtering approach used in stages 8–9. The main risk is getting the merge of cached + fresh transcripts right, and ensuring downstream stages (speaker ID, merge) produce correct output with mixed input.

## Size

Medium (~80–120 lines in pipeline.py, plus tests). Smaller than Phase 1d because the per-session infrastructure already exists.
