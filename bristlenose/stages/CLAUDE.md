# Pipeline Stages Context

## Bundled binary lookup (forward-looking)

Stages that shell out to FFmpeg/ffprobe (`s02_extract_audio.py`, `utils/video.py`, `utils/audio.py`) currently use `shutil.which()`. When the Mac sidecar work lands (Track C C1, see `docs/design-modularity.md`), call sites will switch to a `bundled_binary_path("ffmpeg")` helper that prefers an env var set by Swift, then a bundle-relative path, then falls through to `shutil.which()`. Single source code path on CLI and desktop — different acquisition. Don't inline `shutil.which()` calls or hard-code paths in new stages; they'll need updating again later.

## Transcript format conventions

- **Speaker codes**: Each segment is tagged with a speaker code in brackets: `[p1]` for participants, `[m1]`/`[m2]` for moderators (researchers), `[o1]` for observers. A single session file (e.g. `p1_raw.txt`) can contain segments from multiple speakers
- **Speaker labels**: Original Whisper labels (`Speaker A`, `Speaker B`) kept in parentheses in raw transcripts only
- **Timecodes**: `MM:SS` for segments under 1 hour, `HH:MM:SS` at or above 1 hour. Mixed formats in the same file is correct
- **Timecodes are floats internally**: All data structures store seconds as `float`. String formatting happens only at output. Never parse formatted timecodes back within the same session
- **`transcripts-raw/` is RAW, never the researcher's to edit (#120, owner 23 Oct 2026).** The transcripts as first transcribed, written again by every `run`; the edited transcripts are the ones in the report. `write_raw_transcripts` drops a `README.md` there saying so (`RAW_README_NAME`, text `utils.markdown.RAW_TRANSCRIPTS_README`). **Never make it a `.txt`:** `analyze`, the serve importer and the transcript pages read every `*.txt` in the folder as a transcript: as a `README.txt` the importer made it a session called "README" and `analyze` refused it by name as `unsupported_format` (both measured by mutation). Anything new that globs `*.md` here must skip it. Tests: `tests/test_transcripts_raw_readme.py`
- **`.txt` is canonical**: The parser (`load_transcripts_from_dir`) reads only `.txt` files. `.md` files are human-readable companions, not parsed back. A `.txt` with no timecoded line yields nothing; `analyze` names it in the files bucket as `unsupported_format` rather than dropping it (R119, 20 Oct 2026), or as `no_lines` when it holds nothing past its `#` header, as does a VTT with no cues (decision #80, 22 Oct 2026). Reading untimed text would be a feature
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
│   ├── README.md                       # "don't edit": RAW, rewritten every run (#120)
│   ├── s1.txt                          # each file has all speakers: [m1], [p1], [p2]
│   └── s1.md
├── transcripts-cooked/                 # Stage 7 output (pii_removal.py, only with --redact-pii)
│   ├── s1.txt
│   └── s1.md
├── clips/, screens/                    # the researcher's exports (serve, not the pipeline)
├── clips (from the analysis of 3 Oct 2026)/   # carried across a --clean (output_backup.carry_exports)
└── .bristlenose/
    ├── intermediate/                   # JSON snapshots (render_output.py)
    │   └── scene-colours/s1.json       # per-turn scene colour (utils/scene_colour.py), cached by video + turns
    └── temp/                           # FFmpeg scratch files
```

**Path helpers**: Use `OutputPaths` from `bristlenose/output_paths.py` for consistent path construction.

## Stage 5: Transcription — Whisper hallucination mitigations

- **mlx-whisper and faster-whisper diverge on VAD by default.** `faster-whisper` runs with `vad_filter=True` so Silero VAD strips silence before transcription — hallucination-resistant out of the box. `mlx-whisper` has no built-in VAD, so the same recording transcribed on Apple Silicon (the primary alpha-cohort path) is more prone to "thanks thanks thanks", "Thank you. Thank you.", "Bye." loops in low-signal audio. When tuning transcription, don't assume parity across the two backends
- **mlx-whisper accepts `condition_on_previous_text`, `no_speech_threshold`, `compression_ratio_threshold` as kwargs** (mirrors openai-whisper API). B1 sets these to `False / 0.85 / 1.8` respectively in `transcribe_mlx` — breaks the autoregressive loop and tightens compression-ratio drops. Trade-off: slightly worse cross-chunk proper-noun continuity
- **`no_speech_threshold` does nothing on the default model.** large-v3-turbo reports `no_speech_prob == 0.0` on every segment — digital silence and real speech alike (measured 27 Sep 2026 across six files; whisper-tiny reports 0.94 on the same silent minute, so it is the model, not mlx's plumbing). Four silent 29-minute videos came back as 52–66 lines of "Thank you.", one per 30 s window, and were analysed as interviews. **The guard that works is the signal gate in `s05_transcribe.py`**: decode once, measure 100 ms RMS; if nothing reaches `_SIGNAL_FLOOR_DBFS` (-60) the file never reaches Whisper, and any segment whose ±`_SEGMENT_PAD_S` (2 s) neighbourhood stays below the floor is dropped. Zero segments is stated downstream as `UnusableReason.NO_SPEECH` — no new message. It gates *signal*, not *speech*: room tone, music and hum pass, and Whisper can still hallucinate over them. The pad is load-bearing — a real word ("drainer") was stamped 1.2 s before its audio, and ±0.5 s drops it. **Don't "fix" this by trusting `no_speech_prob` or tuning its threshold**
- **`collapse_adjacent_repeats()` is a post-process band-aid, not the proper fix.** Catches "thanks thanks thanks" + "facebook facebook" patterns; protects English interjection doubling ("No. No. No.", "yeah yeah", "very very good") via the `_REDUPLICABLE` set in `s05_transcribe.py`. English-only — non-English audio needs a locale-specific reduplicable list. Proper fix is Silero VAD pre-filter for mlx-whisper, tracked post-cohort

**Whisper and transcription** (9) — [full entries](gotchas.md#whisper-and-transcription)

- Every Whisper window carries a punctuated "style prompt" (`STYLE_PROMPTS`: en and ja since 11 Oct 2026; es…
- Skipped-window net (mlx, 12 Oct 2026): speech Whisper jumped over is re-decoded.
- `[inaudible]` net (mlx, 12 Oct 2026): a partial prompt echo Whisper barely believed becomes a marker.
- Repetition loops across segments (mlx, 12 Oct 2026) are removed before the skipped-window net.
- Every Whisper decode fetches a cloud placeholder first (24 Oct 2026).
- Each transcribed session leaves a numbers-only diagnostics record (13 Oct 2026).
- Apple's speech model is a first-run stopgap, on since 22 Oct 2026 (built 18 Oct; `experimental_apple_speech`…
- A failed transcription is recorded FAILED in the manifest, not complete (18 Oct 2026).
- `bristlenose transcribe` writes no `intermediate/session_segments.json`.

## Stage 6: Paragraphs — the reading rule, and who gets it

**Paragraphing** (3) — [full entries](gotchas.md#paragraphing)

- A same-speaker paragraph ends at a sentence end once it has reached `PARAGRAPH_LENGTH` (60 words; a no-space…
- Only a session not yet written gets it — never re-paragraph an existing one.
- Lengths are kept as a running total — recomputing over the growing paragraph made a long unpunctuated…

## Stage 5b: Speaker identification

`identify_speakers.py` runs a three-pass speaker assignment: splitting, heuristic, then LLM refinement.

**Speaker identification and codes** (4) — [full entries](gotchas.md#speaker-identification-and-codes)

- Splitting pre-pass (`split_single_speaker_llm`): when a session has 0-1 unique speaker labels (raw audio, no…
- Voice pass (`stages/s05b_voice.py`, 4 Oct 2026): after the text split, each SPLIT session's segments…
- Speaker code assignment: `assign_speaker_codes(next_participant_number, segments, known=None)` runs after…
- Moderator/observer codes are assigned per-session but COLLIDE in `people.yaml` — they are NOT independent…

- **Heuristic pass** (`identify_speaker_roles_heuristic`, rewritten 10 Nov 2026): counts only, no model. Scores host-style opening-script phrases per turn (`_HOST_PHRASES`: "thanks for joining", "no right or wrong", "walk me through") minus guest-style ones (`_GUEST_PHRASES`: "thanks for having me", "do you want me to share my screen"), plus question share (tag questions like ", right?" don't count; "I always say, tell me about..." doesn't count) and a weak word-share nudge in 2-speaker sessions. **Who spoke first is not a signal** (an exact score tie only falls to the earlier speaker). No occupation words in the phrase list: "researcher" is a job title the interviewee may hold. A second moderator needs a host-introduced colleague or the script plus questions, and never in a 1:1. The old "at most 2 turns and under 20 words = observer" rule is unchanged, so a participant who says very little in a short session is called an observer. It decides alone only when the LLM pass fails or is skipped
- **LLM pass** (`identify_speaker_roles_llm`): sends first ~5 minutes to the LLM (prompt `speaker-identification` v0.2.0) **plus the same counts over the whole session as `{speaker_facts}`** (`speaker_facts()`), so the model sees turn, word and question counts it cannot eyeball. The prompt defines "researcher" as whoever runs this conversation, whatever their job. The speaker list and the counts are wrapped as untrusted (speaker labels on platform transcripts are real names). Measured on 82 real speakers: matches the earlier prompt on 80, all five real observers right. Also extracts `person_name` and `job_title`. Design doc: `docs/design-speaker-role-detection.md`
- **Return type**: `identify_speaker_roles_llm()` returns `list[SpeakerInfo]` — a dataclass with `speaker_label`, `role`, `person_name`, `job_title`. Still mutates segments in place for role assignment (existing behaviour). Returns empty list on exception
- **`SpeakerInfo` import**: defined in `identify_speakers.py`. Other modules import it under `TYPE_CHECKING` to avoid circular imports (e.g. `people.py` uses `if TYPE_CHECKING: from bristlenose.stages.s05b_identify_speakers import SpeakerInfo`)
- **Structured output**: `SpeakerRoleItem` in `llm/structured.py` has `person_name` and `job_title` fields (both default `""` for backward compatibility with existing LLM responses)

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
  - Zoom web portal (18 Oct 2026): `GMT{YYYYMMDD}-{HHMMSS}_Recording[_{W}x{H}][.transcript]` → the `gmt…` stamp, which is kept because it keeps meetings apart. Observed on a real account (Zoom developer forum, 29 Apr 2025); the cloud pattern above is constructed and matched nothing the portal emits, so a download came out as one session per file. Extra video layouts' names are not observed and not matched
  - Google Meet: ` - {YYYY/MM/DD HH:MM} [TZ] - {kind}` dated tail (current), plus the older `({YYYY-MM-DD at ...})` parenthetical and `- Transcript` suffix
  - Legacy: `_transcript`, `_subtitles`, `_captions`, `_sub`, `_srt`

**Ingest and session grouping** (8) — [full entries](gotchas.md#ingest-and-session-grouping)

- A format we never offered is left alone, not refused: `split_left_alone` counts it on `StageOutcome.left_alone`; `analyze` is the exception…
- `_is_zoom_local_dir(dir_name)`: matches `YYYY-MM-DD HH.MM.SS Topic [MeetingID]`; the ID is optional since 22…
- `group_into_sessions()`: Pass 1 groups Zoom local folder files by directory; Pass 2 (`_group_by_stem`) groups…
- `_GMEET_TAIL_RE` strips the whole dated tail, and requires a trailing kind it does not read.
- A cooked transcript's `# Source:` line is `[REDACTED]` (`utils.markdown.REDACTED_SOURCE`, 1 Oct 2026) — the…
- Transcript headers store the path relative to the input folder, subfolder included

- **Regex patterns**: 8 compiled module-level patterns (`_TEAMS_SUFFIX_RE`, `_ZOOM_CLOUD_TAIL_RE`, `_ZOOM_CLOUD_PREFIX_RE`, `_ZOOM_PORTAL_RE`, `_ZOOM_LOCAL_DIR_RE`, `_GMEET_TAIL_RE`, `_GMEET_PAREN_RE`, `_GMEET_TRANSCRIPT_SUFFIX_RE`)
- **Tests**: `tests/test_ingest.py` — normalisation, Zoom dir detection, session grouping for all platforms, false positive prevention. Teams, Zoom cloud and Google Meet each have an **observed-specimen block**; a case below those markers must be a filename seen on a real tenant, with tier and capture date recorded

## Session start time (Stage 1, `utils/session_start.py`)

`session_date` is the session's resolved START (11 Oct 2026), by a fixed precedence (cloud-import stamp > zone-stating filename > local-clock filename > container time > birthtime; filenames outrank the container on purpose). Two traps: numbering does not follow the start for a pre-registry project (`pipeline._may_order_by_start`), so reordering carries stars between interviews; and a run never downgrades a start (`SessionRegistry.settle_starts` keeps the best-ranked), so an evicted recording cannot fall back to its file date. A new `_END_WRITERS` row must be measured first. Full precedence and measurements: [gotchas.md](gotchas.md#ingest-and-session-grouping).

## One transcript per session (Stages 3–4, chosen in `_gather_all_segments`)

A session with several transcript files (Teams `.vtt` + `.docx`, cloud + hand-dropped) gets exactly one, chosen by `transcript_choice.choose_transcript`: named over unnamed, then coverage (spans within 10% equal), then format (cloud VTT > VTT/SRT > DOCX). Losers are stated (log WARNING + CLI line), never silently dropped; before 1 Oct 2026 every turn appeared twice. A file that fails to parse is still a recorded `StageFailure`. History: [gotchas.md](gotchas.md#ingest-and-session-grouping).

## Google Meet transcripts — the .docx export is not a transcript (Stage 4)

Google Meet's `.docx` export is Gemini notes plus a transcript, not a transcript; `s04_parse_docx.py` parses by LINE (not paragraph) and refuses a notes-only doc loudly (recorded, not just raised).
Full account (observed 16 Aug 2026, seven things to know, residue, tests): [full entries](gotchas.md#platform-transcripts-and-docx-parsing).

An untimed `.docx` with no speaker turns (a discussion guide) returns no segments and is stated `no_transcript` (6 Nov 2026): `_has_speaker_turns` in `s04_parse_docx.py`, narrow by design.

## Concurrent audio extraction (Stage 2)

`extract_audio_for_sessions()` is async — video files are extracted in parallel via `asyncio.to_thread()` (wrapping blocking `subprocess.run` FFmpeg calls) bounded by `asyncio.Semaphore(4)`.

- **Default 4**: fixed constant, not hardware-adaptive. The bottleneck is the macOS media engine (shared hardware decode), not CPU cores. 4 works well from M1 to M4 Ultra
- **`_extract_one()` helper**: runs `has_audio_stream()` + `extract_audio_from_video()` inside the semaphore. Both are blocking subprocess calls wrapped in `asyncio.to_thread()`
- **Platform transcript skip**: when `session.has_existing_transcript=True`, FFmpeg extraction is skipped entirely — the pipeline will use the parsed transcript and never call Whisper, so audio decode is unnecessary

**Audio extraction** (1) — [full entries](gotchas.md#audio-extraction)

- Tool failure is fail-loud, not isolated: `has_audio_stream()` and `extract_audio_from_video()` raise…

- **VideoToolbox**: `utils/audio.py` passes `-hwaccel videotoolbox` on macOS, so concurrent extractions share the hardware media engine for H.264/HEVC decode
- **`concurrency` kwarg**: exposed but not yet wired to config (unlike `llm_concurrency`). Default of 4 is sufficient; config wiring deferred until there's a real need
- **Tests**: `tests/test_extract_audio.py` — extraction-skip behaviour + the tool-error-vs-genuine-no-audio distinction (`has_audio_stream` raises `AudioToolError` on non-zero exit / missing binary / timeout; the stage propagates it to abort the run; a genuinely silent video is skipped without aborting)

## Quote exclusivity across report sections (Stages 9–11)

**Design rule: every quote appears in exactly one section of the final report.** Researchers expect this — duplicates confuse non-researchers and complicate downstream processing (Miro boards, spreadsheets, etc.).

The exclusivity is enforced at three levels:

1. **Quote type separation (Stage 9 → Stages 10/11)**: `extract_quotes()` classifies every quote as `QuoteType.SCREEN_SPECIFIC` or `QuoteType.GENERAL_CONTEXT`. Stage 10 (`quote_clustering.py`) filters to `SCREEN_SPECIFIC` only; stage 11 (`thematic_grouping.py`) filters to `GENERAL_CONTEXT` only. A quote cannot appear in both a screen cluster and a theme group.

2. **Within screen clusters (Stage 10)**: The LLM prompt in `prompts.py` says "Assign each quote to exactly one screen cluster." The schema does NOT enforce it (`ScreenClusterItem.quote_indices` is a plain list of ints), so the stage does: a quote the model places twice keeps its first placement, and a quote it leaves out of every section is placed by its own topic label after the model's sections rather than lost (N143, 1 Nov 2026; stage 11 puts such quotes in the Uncategorised group). Pinned by `tests/test_cluster_omitted_quotes.py`.

3. **Within theme groups (Stage 11)**: The LLM prompt says "Assign each quote to exactly one theme (even when it could fit several, pick the strongest fit — the researcher will reassign if needed)." The schema description on `ThemeGroupItem.quote_indices` reinforces this. A safety-net dedup in `thematic_grouping.py` catches LLM violations when weak themes are folded into "Uncategorised."

**History**: before Feb 2026, the theme prompt allowed "one or more themes" per quote. Changed to exclusive assignment because: (a) researchers expect to see each quote once and make reassignment decisions themselves, (b) non-researchers receiving the report find duplicates confusing, (c) export to CSV/clipboard doubles up rows unexpectedly.

**Smart-split preserves exclusivity.** `s09`'s `_extract_with_split` (the truncation-recovery path, `chunked-quote-extraction` `f8ea55a`) is Map-Reduce — independent chunks, no cross-chunk context — and dedups the merged result on `verbatim_excerpt` before it reaches s10/s11. So the merged quote list going into clustering/theming is the same shape as an un-chunked run, and the exclusivity invariant holds unchanged (verified live: 0 section/theme overlap on chunked runs). **Known drift (not an exclusivity break):** a chunk-local LLM can't judge "applies broadly across the interview," so chunking nudges `SCREEN_SPECIFIC`/`GENERAL_CONTEXT` classification toward `SCREEN_SPECIFIC` → s11 themes thin out. Bounded by cross-session voting (s10/s11 run over all sessions); the named follow-up is a post-merge `quote_type` re-classification stage if cohort reports feel under-themed.

## Duplicate timecode helpers

- **`parse_timecode` and `format_timecode` live in `utils/timecodes.py` only.** `models.py` re-exports `format_timecode` for the stages that import it there; it no longer defines a second `parse_timecode` (deleted 12 Sep 2026 — it had zero production callers, disagreed with the canonical one on 5 of 14 inputs, and was the object the round-trip test had been pointed at). Import the parser from `bristlenose.utils.timecodes`.

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

## Progress bar gotchas

Don't try to re-enable mlx-whisper or HF Hub progress bars — they don't overwrite inside Rich `console.status()` and will scroll line-by-line. Rule: suppress all tqdm/HF bars entirely, let the Rich spinner handle progress indication. **One exception, and it is not inside a spinner:** the first-run Whisper download, on a terminal, where `preflight_whisper` stops the spinner first and `_native_download_progress` (`bristlenose/preflight/whisper.py`) turns HF's bars on for that one fetch and off again, closing them before the spinner restarts (14 Oct 2026). See `docs/design-pipeline-resilience.md` ("Progress Bar Dead Ends") for the full list of dead ends (mlx-whisper `verbose` parameter, env var import timing, tqdm+Rich conflict).

## Speaker code gotchas

- **`speaker_code` defaults to `""`** — existing code that doesn't set it uses `seg.speaker_code or transcript.participant_id` as a fallback in all write functions. Old transcripts and single-speaker sessions work unchanged
- **`assign_speaker_codes()` must run after Stage 5b** — it reads `speaker_role` set by the heuristic/LLM passes. If called before role assignment, all speakers get the session's `participant_id` (UNKNOWN → fallback)
- **`PersonComputed.session_id` defaults to `""`** — backward compat with existing `people.yaml` files. New runs set it to `"s1"`, `"s2"`, etc. via `compute_participant_stats()`
- **`_session_duration()` accepts optional `people` parameter** — checks `PersonComputed.duration_seconds` (matched by `session_id`) before falling back to `InputFile.duration_seconds`. This fixes VTT-only sessions that have no `InputFile.duration_seconds` but do have segment timestamps
- **Report sessions table groups speakers by `computed.session_id`** — if people file is missing, falls back to showing `[session.participant_id]` only
- **Transcript files named by `session_id`** (`s1.txt` in `transcripts-raw/`, not `p1_raw.txt`) — a single file contains segments from all speakers in that session (`[m1]`, `[p1]`, `[p2]`, `[o1]`)
- **`assign_speaker_codes()` signature is `(next_participant_number, segments, known=None)`** — no `session_id` parameter (an earlier version of this line said there was one; corrected 2 Oct 2026). `known` is the session's label → code map from `SessionRegistry.speakers_for(sid)`; a label keeps its code while its role matches. Returns `(dict[str, str], int)` (label→code map, updated next number). The `next_participant_number` counter enables global p-code numbering across sessions

## Session table helpers (render/dashboard.py)

Reference for `_derive_journeys`, `_oxford_list_html`, `_build_session_rows`, `_render_sentiment_sparkline`, `_FAKE_THUMBNAILS` env var, `format_finder_filename`, and moderator display logic — see `docs/design-dashboard-navigation.md` ("Session table helpers" section).

## Pipeline runtime gotchas

**Pipeline runtime, resume and caching** (12) — [full entries](gotchas.md#pipeline-runtime-resume-and-caching)

- Smart-split halves cut by SEGMENT INDEX, not time — and never by a fixed clock-time.
- Pipeline resume (Phase 1c/1d/1d-ext): `run()` loads an existing manifest on startup via `_prev_manifest =…
- CLI resume guard (`cli.py`): The output directory guard allows re-running into an existing output directory…
- Session-count guard — REMOVED 19 Aug 2026. Was: >16 sessions prompted "Found N sessions in dir/. Continue?…
- Phase 2b hash verification and manifest invalidation — `_is_stage_verified()` checks SHA-256 of cached files…
- Corruption-tolerant per-session resume reads (`_load_cached_json`)
- Phase 2c input change detection — `_is_stage_verified()` accepts optional `current_input_hashes` dict. If…
- Transcribe fingerprints key on the path INSIDE the project folder (12 Oct 2026), and a manifest from before…
- A removed interview's files are pruned once the run succeeds (`prune_stale_session_files`, 12 Oct 2026).
- The same stem in two subfolders is two sessions, and a second recording in one session is stated…
- An analysed session keeps the files it was analysed from (decision #129, 23 Oct 2026).
- `analyze` into a project `run` has analysed records what it wrote

- **`_format_duration`, `_print_step`, `_print_cached_step`, `_is_stage_cached`, `_is_stage_verified`, and `_is_speaker_stage_verified` are module-level in `pipeline.py`** — `cli.py` imports `_format_duration` from there. Don't move them into the `Pipeline` class. Cache-check sites use `_is_stage_verified` (Phase 2b), not the old `_is_stage_cached` directly
- **`bristlenose status <folder>`**: Read-only command that prints project state from the manifest. Accepts input dir or output dir (auto-detects via `_resolve_output_dir()`). `-v` shows per-session detail with provider/model. Pure logic in `bristlenose/status.py` (`get_project_status()`, `format_resume_summary()`), printing in `cli.py` (`_print_project_status()`). Validates intermediate file existence for completed stages, warns if missing. 14 tests in `tests/test_status.py`
- **`llm_client` and `concurrency` in `run()`** — both are declared unconditionally before stage 5b (`llm_client: LLMClient | None = None`, `concurrency = self.settings.llm_concurrency`). `llm_client` is created inside the speaker-ID `else` branch when that stage actually runs, but when speaker ID is fully cached, `llm_client` stays `None`. Lazy init guards (`if llm_client is None: llm_client = LLMClient(...)`) before the LLM calls in topic segmentation and quote extraction ensure later stages always have a client. If adding new LLM stages, add the same guard
- **`PipelineResult` has optional LLM fields** (default 0/empty string) — `run_transcription_only()` doesn't use `LLMClient` so these stay at defaults. `_print_pipeline_summary()` in `cli.py` uses `getattr()` defensively
- **Pipeline metadata** (`metadata.json`): `write_pipeline_metadata()` in `render_output.py` writes `{"project_name": "..."}` to the intermediate directory during `run`/`analyze`. `read_pipeline_metadata()` reads it back. The CLI `render` command uses this as the source of truth for project name, falling back to directory-name heuristics for pre-metadata output dirs only
- **`PipelineResult.report_path`**: populated by all three pipeline methods (`run`, `run_analysis_only`, `run_render_only`) from the return value of `render_html()`. `_print_pipeline_summary()` in `cli.py` uses it to print the clickable report link (shows filename only, `file://` hyperlink resolves the full path)

## Other gotchas

- **`segment_topics()` returns `list[SessionTopicMap]`, NOT a dict** — use `sum(len(m.boundaries) for m in topic_maps)`, not `topic_maps.values()`. This was a bug that took two attempts to find because `_gather_all_segments()` returns `dict[str, list[TranscriptSegment]]` (which does have `.values()`), creating a misleading pattern
- **`InputSession.files` is a list, `InputFile.duration_seconds` is on each file** — to sum audio duration: `sum(f.duration_seconds or 0 for s in sessions for f in s.files)`, not `s.duration_seconds`
- **`transcripts-cooked/` only exists with `--redact-pii`** — if a previous run used PII redaction but the current one doesn't, stale cooked files remain on disk. Coverage and transcript pages must use the same transcript source to avoid broken links. `render_transcript_pages()` accepts a `transcripts` parameter to ensure consistency
- **`_render_transcript_page()` accepts `FullTranscript`, not just `PiiCleanTranscript`** — the assertion uses `isinstance(transcript, FullTranscript)`. Since `PiiCleanTranscript` is a subclass, both types pass. Don't tighten this to `PiiCleanTranscript` or it will crash when PII redaction is off (the default)
- **`player.js` only intercepts `.timecode` clicks with `data-participant` and `data-seconds`** — coverage section links use `class="timecode"` but NO data attributes, so they navigate normally. If you add new timecode links that should navigate (not open the player), omit the data attributes

## Stage-cache honesty (A4, May 2026)

When adding or modifying analysis stages, three invariants must hold or the cache poisons on failure (the 2026-05-09 first-run repro). All landed via `a4-stage-cache-honesty`:

1. **Abandon-check fires BEFORE `mark_stage_complete`** at every analysis-stage site in `pipeline.py` (raise `PipelineAbandonedError` before any manifest write); otherwise an empty intermediate is cached COMPLETE and the next run renders an empty report.
2. **Stages with fallback paths emit `StageFailure` at the LLM call site, BEFORE the fallback runs**; otherwise `succeeded > 0 and failed == 0` and the abandon predicate never fires.
3. **`Cause.message` is built from structured fields only** via `run_lifecycle._build_cause`, never `str(exc)` / `repr(exc)`; provider error bodies can echo participant text and `pipeline-events.jsonl` is a re-identification surface.
Code patterns, `mark_stage_complete`'s belt-and-braces check, stage signatures and the `_succeeded_sids` rule: [full entries](gotchas.md#stage-cache-honesty).
