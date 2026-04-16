# Pipeline Stages Context

## Transcript format conventions

- **Speaker codes**: Each segment is tagged with a speaker code in brackets: `[p1]` for participants, `[m1]`/`[m2]` for moderators (researchers), `[o1]` for observers. A single session file (e.g. `p1_raw.txt`) can contain segments from multiple speakers
- **Speaker labels**: Original Whisper labels (`Speaker A`, `Speaker B`) kept in parentheses in raw transcripts only
- **Timecodes**: `MM:SS` for segments under 1 hour, `HH:MM:SS` at or above 1 hour. Mixed formats in the same file is correct
- **Timecodes are floats internally**: All data structures store seconds as `float`. String formatting happens only at output. Never parse formatted timecodes back within the same session
- **`.txt` is canonical**: The parser (`load_transcripts_from_dir`) reads only `.txt` files. `.md` files are human-readable companions, not parsed back
- **Legacy format support**: Parser also accepts old-format files with `[PARTICIPANT]`/`[RESEARCHER]` role labels, and old files where all segments use `[p1]` (role will be UNKNOWN)
- **Speaker code inference**: Parser derives role from prefix: `m` → RESEARCHER, `o` → OBSERVER, `p` → UNKNOWN (backward compat). Code validation checks first char + remaining digits (e.g. `m1` valid, `misc` not)

## Output directory structure

Output goes **inside the input folder** by default. See root `CLAUDE.md` for the full v2 layout. Key paths for stages:

```
interviews/bristlenose-output/          # default output location
├── bristlenose-{slug}-report.html      # render/ package output
├── bristlenose-{slug}-report.md        # render_output.py output
├── people.yaml                         # people.py output
├── assets/                             # static files (CSS, logos, player)
├── sessions/                           # transcript pages (render/transcript_pages.py)
│   ├── transcript_s1.html
│   └── transcript_s2.html
├── transcripts-raw/                    # Stage 6 output (merge_transcript.py)
│   ├── s1.txt                          # each file has all speakers: [m1], [p1], [p2]
│   └── s1.md
├── transcripts-cooked/                 # Stage 7 output (pii_removal.py, only with --redact-pii)
│   ├── s1.txt
│   └── s1.md
└── .bristlenose/
    ├── intermediate/                   # JSON snapshots (render_output.py)
    └── temp/                           # FFmpeg scratch files
```

**Path helpers**: Use `OutputPaths` from `bristlenose/output_paths.py` for consistent path construction.

## Stage 5b: Speaker identification

`identify_speakers.py` runs a three-pass speaker assignment: splitting, heuristic, then LLM refinement.

- **Splitting pre-pass** (`split_single_speaker_llm`): when a session has 0-1 unique speaker labels (raw audio, no platform transcript), sends first ~10 minutes to the LLM to detect speaker boundaries from conversational cues (names, turn-taking, topic shifts). Mutates `speaker_label` on segments. Skipped when 2+ speakers already exist. Design doc: `docs/design-speaker-splitting.md`
- **Heuristic pass** (`identify_speaker_roles_heuristic`): scores speakers by question ratio, researcher-phrase hits, and word count asymmetry (speakers who talk less score higher). Assigns `RESEARCHER`, `PARTICIPANT`, or `OBSERVER`. Phrase list covers task-oriented prompts, conversation management, and open-ended prompting. Fast, no LLM needed
- **LLM pass** (`identify_speaker_roles_llm`): sends first ~5 minutes to the LLM for refined role assignment. Prompt is format-agnostic (covers UXR, oral history, journalism, market research). Also extracts `person_name` and `job_title` for each speaker when mentioned in the transcript. Design doc: `docs/design-speaker-role-detection.md`
- **Return type**: `identify_speaker_roles_llm()` returns `list[SpeakerInfo]` — a dataclass with `speaker_label`, `role`, `person_name`, `job_title`. Still mutates segments in place for role assignment (existing behaviour). Returns empty list on exception
- **`SpeakerInfo` import**: defined in `identify_speakers.py`. Other modules import it under `TYPE_CHECKING` to avoid circular imports (e.g. `people.py` uses `if TYPE_CHECKING: from bristlenose.stages.s05b_identify_speakers import SpeakerInfo`)
- **Structured output**: `SpeakerRoleItem` in `llm/structured.py` has `person_name` and `job_title` fields (both default `""` for backward compatibility with existing LLM responses)
- **Speaker code assignment**: `assign_speaker_codes(session_id, next_participant_number, segments)` runs after both heuristic and LLM passes. Groups segments by `speaker_label`, assigns codes based on `speaker_role`: RESEARCHER → `m1`/`m2`, OBSERVER → `o1`, PARTICIPANT/UNKNOWN → globally-numbered `p{next_participant_number}` (incremented per speaker). Sets `seg.speaker_code` on every segment. Returns `(dict[str, str], int)` — label→code map and the updated next participant number. The pipeline passes `next_participant_number` across sessions to ensure unique p-codes across the entire study (e.g. session 1 gets p1–p3, session 2 gets p4–p6). Called from `pipeline.py` after Stage 5b, before Stage 6

## LLM concurrency in stages

Stages 8 and 9 accept a `concurrency: int = 1` kwarg, passed by the pipeline from `settings.llm_concurrency`. The pattern:

```python
semaphore = asyncio.Semaphore(concurrency)
async def _process(transcript):
    async with semaphore:
        return await _segment_single(transcript, llm_client)
return list(await asyncio.gather(*(_process(t) for t in transcripts)))
```

- **Default 1**: behaves identically to the old sequential loop (backward compatible, useful for tests)
- **Pipeline passes 3**: `concurrency=self.settings.llm_concurrency` in both `run()` and `run_analysis_only()`
- **Error isolation**: each `_process()` closure has its own try/except. A failed participant doesn't cancel siblings (asyncio.gather default behaviour — if one raises, others still complete since the exception is caught inside `_process`)
- **No cross-stage semaphore**: each stage creates its own semaphore. Stages still execute sequentially in the pipeline

## Platform-aware session grouping (Stage 1)

`ingest.py` groups input files into sessions using a two-pass strategy that handles Teams, Zoom, and Google Meet naming conventions.

- **`_normalise_stem(stem)`**: strips platform suffixes before stem matching. Expects lowercased input:
  - Teams: `{YYYYMMDD}_{HHMMSS}-Meeting Recording`, `-meeting transcript`
  - Zoom cloud: `Audio Transcript_` prefix, `_{MeetingID}_{Month_DD_YYYY}` tail (9–11 digit IDs)
  - Google Meet: `({YYYY-MM-DD at ...})` parenthetical, `- Transcript` suffix
  - Legacy: `_transcript`, `_subtitles`, `_captions`, `_sub`, `_srt`
- **`_is_zoom_local_dir(dir_name)`**: matches `YYYY-MM-DD HH.MM.SS Topic MeetingID` pattern
- **`group_into_sessions()`**: Pass 1 groups Zoom local folder files by directory; Pass 2 groups remaining files by normalised stem
- **Regex patterns**: 6 compiled module-level patterns (`_TEAMS_SUFFIX_RE`, `_ZOOM_CLOUD_TAIL_RE`, `_ZOOM_CLOUD_PREFIX_RE`, `_ZOOM_LOCAL_DIR_RE`, `_GMEET_PAREN_RE`, `_GMEET_TRANSCRIPT_SUFFIX_RE`)
- **Tests**: `tests/test_ingest.py` — 35 tests covering normalisation, Zoom dir detection, session grouping for all platforms, false positive prevention

## Concurrent audio extraction (Stage 2)

`extract_audio_for_sessions()` is async — video files are extracted in parallel via `asyncio.to_thread()` (wrapping blocking `subprocess.run` FFmpeg calls) bounded by `asyncio.Semaphore(4)`.

- **Default 4**: fixed constant, not hardware-adaptive. The bottleneck is the macOS media engine (shared hardware decode), not CPU cores. 4 works well from M1 to M4 Ultra
- **`_extract_one()` helper**: runs `has_audio_stream()` + `extract_audio_from_video()` inside the semaphore. Both are blocking subprocess calls wrapped in `asyncio.to_thread()`
- **Platform transcript skip**: when `session.has_existing_transcript=True`, FFmpeg extraction is skipped entirely — the pipeline will use the parsed transcript and never call Whisper, so audio decode is unnecessary
- **Error isolation**: same pattern as LLM stages — a failed extraction doesn't cancel siblings
- **VideoToolbox**: `utils/audio.py` passes `-hwaccel videotoolbox` on macOS, so concurrent extractions share the hardware media engine for H.264/HEVC decode
- **`concurrency` kwarg**: exposed but not yet wired to config (unlike `llm_concurrency`). Default of 4 is sufficient; config wiring deferred until there's a real need
- **Tests**: `tests/test_extract_audio.py` — 2 tests for extraction skip behaviour

## Quote exclusivity across report sections (Stages 9–11)

**Design rule: every quote appears in exactly one section of the final report.** Researchers expect this — duplicates confuse non-researchers and complicate downstream processing (Miro boards, spreadsheets, etc.).

The exclusivity is enforced at three levels:

1. **Quote type separation (Stage 9 → Stages 10/11)**: `extract_quotes()` classifies every quote as `QuoteType.SCREEN_SPECIFIC` or `QuoteType.GENERAL_CONTEXT`. Stage 10 (`quote_clustering.py`) filters to `SCREEN_SPECIFIC` only; stage 11 (`thematic_grouping.py`) filters to `GENERAL_CONTEXT` only. A quote cannot appear in both a screen cluster and a theme group.

2. **Within screen clusters (Stage 10)**: The LLM prompt in `prompts.py` says "Assign each quote to exactly one screen cluster." The structured output schema (`ScreenClusterItem.quote_indices`) enforces this at the index level.

3. **Within theme groups (Stage 11)**: The LLM prompt says "Assign each quote to exactly one theme (even when it could fit several, pick the strongest fit — the researcher will reassign if needed)." The schema description on `ThemeGroupItem.quote_indices` reinforces this. A safety-net dedup in `thematic_grouping.py` catches LLM violations when weak themes are folded into "Uncategorised observations."

**History**: before Feb 2026, the theme prompt allowed "one or more themes" per quote. Changed to exclusive assignment because: (a) researchers expect to see each quote once and make reassignment decisions themselves, (b) non-researchers receiving the report find duplicates confusing, (c) export to CSV/clipboard doubles up rows unexpectedly.

## Duplicate timecode helpers

Both `models.py` and `utils/timecodes.py` define `format_timecode()` and `parse_timecode()`. They behave identically. Stage files import from one or the other — both are fine. The `utils/timecodes.py` version has a more sophisticated parser (SRT/VTT milliseconds support).

## Transcript page / coverage link consistency

The HTML report has three places that generate links to transcript pages:
1. **Sessions table** (`session_table.html` template): `transcript_{session.session_id}.html`
2. **Quote speaker links** (`quote_card.html` template): `transcript_{quote.session_id}.html#t-{seconds}`
3. **Coverage section** (`coverage.html` template): `transcript_{transcript.session_id}.html#t-{seconds}`

Transcript pages are named `transcript_{transcript.session_id}.html` with anchor IDs `t-{int(seg.start_time)}`.

**The gotcha**: `transcripts-cooked/` only exists when `--redact-pii` was used. If a previous run used PII redaction but the current run doesn't:
- `transcripts-cooked/` contains stale files from the old run
- `transcripts-raw/` contains fresh files from the new run
- If coverage and transcript pages loaded from different directories, links would break

**Solution**: `render_transcript_pages()` accepts an optional `transcripts` parameter. When `render_html()` is called with transcripts, it passes them through to `render_transcript_pages()`, ensuring both coverage calculation and transcript page generation use the exact same data. For the `render` command (which loads from disk), both use the same preference: cooked > raw.

**Rule**: Always ensure coverage, quote links, and transcript pages use the same transcript source. If you add new timecode links, make sure they derive `session_id` from the same transcripts passed to `render_html()`.

## Performance optimisations

- **Compact JSON in LLM prompts**: `quote_clustering.py` and `thematic_grouping.py` use `json.dumps(separators=(",",":"))` (no whitespace) to minimise input tokens sent to the LLM for stages 10 and 11. Saves 10–20% tokens on these cross-participant calls
- **FFmpeg VideoToolbox hardware decode**: `utils/audio.py` passes `-hwaccel videotoolbox` on macOS, offloading H.264/HEVC video decoding to the Apple Silicon media engine. Harmless no-op for audio-only inputs; flag omitted on non-macOS platforms. 2–4× faster video decode, frees CPU/GPU for other work
- **Concurrent audio extraction**: `extract_audio_for_sessions()` in `stages/s02_extract_audio.py` is async — up to 4 FFmpeg processes run in parallel via `asyncio.Semaphore(4)` + `asyncio.gather()`. Blocking `subprocess.run` calls wrapped in `asyncio.to_thread()`. Default concurrency of 4 is a fixed constant (not hardware-adaptive) because the bottleneck is the shared media engine on macOS, not CPU core count — works well across all Apple Silicon variants (M1 through M4 Ultra). On Linux without hardware decode, 4 concurrent software-decode processes is still reasonable. `concurrency` kwarg exposed for future config wiring if needed
- **Audio extraction skip for platform transcripts**: `extract_audio.py` checks `session.has_existing_transcript` and skips FFmpeg entirely when a platform transcript (VTT/SRT/DOCX) is present — avoids unnecessary video decode when Whisper won't be called

## Transcript coverage

Collapsible section at the end of the research report showing what proportion of the transcript made it into quotes.

- **Purpose**: researchers worry the AI silently dropped important material. The coverage section provides triage: if "% omitted" is low, they can trust the report; if high, they expand and review
- **Three percentages**: `X% in report · Y% moderator · Z% omitted` — word-count based, whole numbers. "In report" = participant words in quote timecode ranges. "Moderator" = moderator + observer speech. "Omitted" = participant words not covered by any quote
- **Omitted content**: per-session, shows participant speech that didn't become quotes. Segments >3 words shown in full with speaker code and timecode; segments ≤3 words collapsed into a summary with repeat counts (`Okay. (4×), Yeah. (2×)`)
- **Module**: `bristlenose/coverage.py` — `CoverageStats`, `SessionOmitted`, `OmittedSegment` dataclasses, `calculate_coverage()` function
- **Rendering**: `_build_coverage_html()` in `render/dashboard.py`. HTML `<details>` element, collapsed by default. CSS in `organisms/coverage.css`
- **Pipeline wiring**: `render_html()` accepts optional `transcripts` parameter. All three paths (`run`, `analyze`, `render`) pass transcripts
- **Tests**: `tests/test_coverage.py` — 14 tests covering percentage calculation, fragment threshold, repeat counting, edge cases
- **Design doc**: `docs/design-transcript-coverage.md`

## Progress bar gotchas (things that were tried and failed)

These are documented to prevent re-exploration of dead ends:

- **mlx-whisper `verbose` parameter is counterintuitive**: `verbose=False` ENABLES tqdm progress bars (`disable=verbose is not False` → `disable=False`). `verbose=None` DISABLES them (`disable=True`). `verbose=True` also disables the bar but enables text output. We use `verbose=None`
- **`TQDM_DISABLE` env var must be set before any tqdm import**: setting it inside `Pipeline.__init__()` is too late — moved to module level in `pipeline.py`
- **`HF_HUB_DISABLE_PROGRESS_BARS` env var is read at `huggingface_hub` import time** (in `constants.py`): if `huggingface_hub` was already imported before `pipeline.py` loads, the env var has no effect. Belt-and-suspenders: also call `disable_progress_bars()` programmatically in `_init_mlx_backend()` after `import mlx_whisper`
- **tqdm progress bars don't overwrite inside Rich `console.status()`**: Rich's spinner takes control of the terminal cursor. tqdm's `\r` carriage return doesn't work properly, causing bars to scroll line-by-line instead of overwriting in place. This makes tqdm bars useless inside a Rich status context — they produce dozens of non-overwriting lines
- **`TQDM_NCOLS=80` doesn't help**: even with width capped, the non-overwriting bars still produce one line per update. The root issue is tqdm + Rich terminal conflict, not width
- **Conclusion**: suppress all tqdm/HF bars entirely; let the Rich status spinner handle progress indication. The per-stage timing on the checkmark line provides sufficient feedback. Don't try to re-enable mlx-whisper's tqdm bar — it will scroll

## Speaker code gotchas

- **`speaker_code` defaults to `""`** — existing code that doesn't set it uses `seg.speaker_code or transcript.participant_id` as a fallback in all write functions. Old transcripts and single-speaker sessions work unchanged
- **`assign_speaker_codes()` must run after Stage 5b** — it reads `speaker_role` set by the heuristic/LLM passes. If called before role assignment, all speakers get the session's `participant_id` (UNKNOWN → fallback)
- **Moderator codes are per-session, not cross-session** — `m1` in session 1 and `m1` in session 2 are independent entries in `people.yaml`. Cross-session linking is Phase 2 (not implemented)
- **`PersonComputed.session_id` defaults to `""`** — backward compat with existing `people.yaml` files. New runs set it to `"s1"`, `"s2"`, etc. via `compute_participant_stats()`
- **`_session_duration()` accepts optional `people` parameter** — checks `PersonComputed.duration_seconds` (matched by `session_id`) before falling back to `InputFile.duration_seconds`. This fixes VTT-only sessions that have no `InputFile.duration_seconds` but do have segment timestamps
- **Report sessions table groups speakers by `computed.session_id`** — if people file is missing, falls back to showing `[session.participant_id]` only
- **Transcript files named by `session_id`** (`s1.txt` in `transcripts-raw/`, not `p1_raw.txt`) — a single file contains segments from all speakers in that session (`[m1]`, `[p1]`, `[p2]`, `[o1]`)
- **`assign_speaker_codes()` signature is `(session_id, next_participant_number, segments)`** — returns `(dict[str, str], int)` (label→code map, updated next number). The `next_participant_number` counter enables global p-code numbering across sessions

## Session table helpers (render/dashboard.py)

- **`_derive_journeys(screen_clusters, all_quotes)`** — extracts per-participant journey paths from screen clusters. Returns `(participant_screens, participant_session)`. Shared by the session table and user journeys table — extracted from `_build_task_outcome_html()` to avoid duplication
- **`_oxford_list_html(*items)`** — joins pre-escaped HTML fragments with Oxford commas ("A", "A and B", "A, B, and C"). Different from the plain-text `_oxford_list()` helper — this one does NOT escape its arguments (caller must pre-escape). Used for moderator header with badge markup
- **`_build_session_rows()` return type** — returns `tuple[list[dict[str, object]], str]` (row dicts + moderator header HTML). The second element is empty string when no moderators. Both Sessions tab (~line 311) and Project tab (~line 1195) destructure this tuple
- **`_render_sentiment_sparkline(counts)`** — generates an inline bar chart (div with per-sentiment spans) from a `dict[str, int]` of sentiment counts. Bar heights are normalised to `_SPARKLINE_MAX_H` (20px). Uses `--bn-sentiment-{name}` CSS custom properties for colours. Returns `"&mdash;"` when all counts are zero
- **`_FAKE_THUMBNAILS` feature flag** — `os.environ.get("BRISTLENOSE_FAKE_THUMBNAILS", "") == "1"`. When enabled, all sessions with files show thumbnail placeholders (even VTT-only projects). Used for layout testing. The shipped version retains real `video_map` logic — only the env var override is added
- **`format_finder_filename(name, *, max_len=24)`** in `utils/markdown.py` — Finder-style middle-ellipsis filename truncation. Preserves extension, splits stem budget 2/3 front + 1/3 back. Returns unchanged if within `max_len`. Used by `_build_session_rows()` for the Interviews column with `title` attr for full name on hover
- **Moderator display logic** — 1 moderator globally → shown in header only, omitted from row speaker lists. 2+ moderators → header AND in each row's speaker list. Header uses `_oxford_list_html()` with `bn-person-badge` molecule markup (regular-weight names, not semibold)

## Pipeline runtime gotchas

- **`_format_duration`, `_print_step`, `_print_cached_step`, `_is_stage_cached`, `_is_stage_verified`, and `_is_speaker_stage_verified` are module-level in `pipeline.py`** — `cli.py` imports `_format_duration` from there. Don't move them into the `Pipeline` class. Cache-check sites use `_is_stage_verified` (Phase 2b), not the old `_is_stage_cached` directly
- **Pipeline resume (Phase 1c/1d/1d-ext)**: `run()` loads an existing manifest on startup via `_prev_manifest = load_manifest(output_dir)`. **Stage-level caching (1c)**: Stages 8–11 check `_is_stage_cached(_prev_manifest, STAGE_*)` + intermediate JSON file existence — if both true, data is loaded from disk and `(cached)` is printed. **Per-session caching (1d)**: Stages 8 (topic segmentation) and 9 (quote extraction) track which sessions completed within the stage via `SessionRecord` entries in the manifest. On resume, completed sessions' results are loaded from intermediate JSON (filtered by `session_id`), only remaining sessions get LLM calls, then results are merged. `mark_session_complete()` writes after each session; `mark_stage_complete()` after all sessions finish. **Transcription + speaker ID caching (1d-ext)**: Stages 3-5 (transcription) cache `session_segments.json` to intermediate/; stage 5b (speaker ID) caches `speaker-info/{sid}.json` per session with `SpeakerInfo` + segments-with-roles. `assign_speaker_codes()` always re-runs (global participant numbering). `speaker_info_to_dict()` / `speaker_info_from_dict()` in `identify_speakers.py` serialize the `SpeakerInfo` dataclass. Stages 1-2 (ingest, audio extraction) and stage 6 (merge) always re-run (fast). Stage 12 (render) always re-runs. Cache requires `write_intermediate=True` (the default). Only `COMPLETE` status triggers stage-level cache; `RUNNING`/`PARTIAL`/`FAILED` trigger per-session resume path
- **CLI resume guard** (`cli.py`): The output directory guard allows re-running into an existing output directory when a pipeline manifest exists (resume path). If no manifest exists, it blocks with the original "Output directory already exists" error. This prevents accidental overwrites while enabling crash recovery. `--clean` always wipes everything including the manifest. On resume, a one-line summary is printed (e.g. "Resuming: 7/10 sessions have quotes, 3 remaining.") via `format_resume_summary()` in `status.py`
- **Session-count guard** (`pipeline.py`): If ingest discovers more than 16 sessions (`_MAX_SESSIONS_NO_CONFIRM`), the pipeline prompts "Found N sessions in dir/. Continue? [Y/n]" before proceeding. Prevents accidentally transcribing an entire multi-project directory. Applies to `run()`, `run_transcription_only()`, and `run_analysis_only()`. `--yes` / `-y` CLI flag (threaded as `Pipeline(skip_confirm=True)`) bypasses the prompt for scripting/CI. Ingest (Stage 1) runs outside the Rich spinner context so the terminal prompt works. 8 tests in `tests/test_session_guard.py`
- **`bristlenose status <folder>`**: Read-only command that prints project state from the manifest. Accepts input dir or output dir (auto-detects via `_resolve_output_dir()`). `-v` shows per-session detail with provider/model. Pure logic in `bristlenose/status.py` (`get_project_status()`, `format_resume_summary()`), printing in `cli.py` (`_print_project_status()`). Validates intermediate file existence for completed stages, warns if missing. 14 tests in `tests/test_status.py`
- **`llm_client` and `concurrency` in `run()`** — both are declared unconditionally before stage 5b (`llm_client: LLMClient | None = None`, `concurrency = self.settings.llm_concurrency`). `llm_client` is created inside the speaker-ID `else` branch when that stage actually runs, but when speaker ID is fully cached, `llm_client` stays `None`. Lazy init guards (`if llm_client is None: llm_client = LLMClient(...)`) before the LLM calls in topic segmentation and quote extraction ensure later stages always have a client. If adding new LLM stages, add the same guard
- **Phase 2b hash verification and manifest invalidation** — `_is_stage_verified()` checks SHA-256 of cached files against the manifest. On hash mismatch it **removes the stage from `_prev_manifest`** so `get_completed_session_ids()` returns empty — this prevents the per-session resume path from trying to JSON-parse a corrupt file. Without this invalidation, a hash mismatch triggers the `else` branch which still tries to load cached data for "completed" sessions from the same corrupt file. `_is_speaker_stage_verified()` does the same for per-session hashes
- **Phase 2c input change detection** — `_is_stage_verified()` accepts optional `current_input_hashes` dict. If stored `input_hashes` differ from current, stage is stale — popped from manifest and re-run. Cascade is implicit: re-running stage N changes its `content_hash`, which becomes stage N+1's `input_hashes["upstream"]`, triggering N+1's re-run, etc. **Two input types**: (1) transcribe stage hashes source file metadata via `hash_file_metadata()` (size+mtime, no content read); (2) all other cached stages use `{"upstream": prev_stage_content_hash}`. Topic segmentation also tracks `pii_enabled` — toggling `--redact-pii` invalidates topics and everything downstream. `_MISSING_HASH` sentinel (not empty string) used when upstream hash is `None`
- **`PipelineResult` has optional LLM fields** (default 0/empty string) — `run_transcription_only()` doesn't use `LLMClient` so these stay at defaults. `_print_pipeline_summary()` in `cli.py` uses `getattr()` defensively
- **Pipeline metadata** (`metadata.json`): `write_pipeline_metadata()` in `render_output.py` writes `{"project_name": "..."}` to the intermediate directory during `run`/`analyze`. `read_pipeline_metadata()` reads it back. The CLI `render` command uses this as the source of truth for project name, falling back to directory-name heuristics for pre-metadata output dirs only
- **`PipelineResult.report_path`**: populated by all three pipeline methods (`run`, `run_analysis_only`, `run_render_only`) from the return value of `render_html()`. `_print_pipeline_summary()` in `cli.py` uses it to print the clickable report link (shows filename only, `file://` hyperlink resolves the full path)

## Other gotchas

- **`segment_topics()` returns `list[SessionTopicMap]`, NOT a dict** — use `sum(len(m.boundaries) for m in topic_maps)`, not `topic_maps.values()`. This was a bug that took two attempts to find because `_gather_all_segments()` returns `dict[str, list[TranscriptSegment]]` (which does have `.values()`), creating a misleading pattern
- **`InputSession.files` is a list, `InputFile.duration_seconds` is on each file** — to sum audio duration: `sum(f.duration_seconds or 0 for s in sessions for f in s.files)`, not `s.duration_seconds`
- **`transcripts-cooked/` only exists with `--redact-pii`** — if a previous run used PII redaction but the current one doesn't, stale cooked files remain on disk. Coverage and transcript pages must use the same transcript source to avoid broken links. `render_transcript_pages()` accepts a `transcripts` parameter to ensure consistency
- **`_render_transcript_page()` accepts `FullTranscript`, not just `PiiCleanTranscript`** — the assertion uses `isinstance(transcript, FullTranscript)`. Since `PiiCleanTranscript` is a subclass, both types pass. Don't tighten this to `PiiCleanTranscript` or it will crash when PII redaction is off (the default)
- **`player.js` only intercepts `.timecode` clicks with `data-participant` and `data-seconds`** — coverage section links use `class="timecode"` but NO data attributes, so they navigate normally. If you add new timecode links that should navigate (not open the player), omit the data attributes
- **Transcript headers store filename only, not full path** — `merge_transcript.py` (line 59) and `render_output.py` (line 202) write `# Source: filename.mov` using `.path.name`, stripping the subdirectory. The static renderer (`html_helpers._build_video_map()` in `render/`) doesn't use these headers — it reads `InputSession.files` directly (full absolute paths). But the serve-mode importer reads transcript headers and must reconstruct the path. If source files live in a subdirectory (e.g. `interviews/`), the importer's `_import_source_files()` scans one level of subdirectories to find them (mirroring `ingest.discover_files()`). This is a known data-loss point — the pipeline has access to `InputSession.files` with full paths, but this information is not persisted in intermediate data. Future improvement: store relative paths (including subdirectory) in transcript headers or in a dedicated manifest field
