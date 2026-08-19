# Pipeline Stages Context

## Bundled binary lookup (forward-looking)

Stages that shell out to FFmpeg/ffprobe (`s02_extract_audio.py`, `utils/video.py`, `utils/audio.py`) currently use `shutil.which()`. When the Mac sidecar work lands (Track C C1, see `docs/design-modularity.md`), call sites will switch to a `bundled_binary_path("ffmpeg")` helper that prefers an env var set by Swift, then a bundle-relative path, then falls through to `shutil.which()`. Single source code path on CLI and desktop — different acquisition. Don't inline `shutil.which()` calls or hard-code paths in new stages; they'll need updating again later.

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

## Stage 5: Transcription — Whisper hallucination mitigations

- **mlx-whisper and faster-whisper diverge on VAD by default.** `faster-whisper` runs with `vad_filter=True` so Silero VAD strips silence before transcription — hallucination-resistant out of the box. `mlx-whisper` has no built-in VAD, so the same recording transcribed on Apple Silicon (the primary alpha-cohort path) is more prone to "thanks thanks thanks", "Thank you. Thank you.", "Bye." loops in low-signal audio. When tuning transcription, don't assume parity across the two backends
- **mlx-whisper accepts `condition_on_previous_text`, `no_speech_threshold`, `compression_ratio_threshold` as kwargs** (mirrors openai-whisper API). B1 sets these to `False / 0.85 / 1.8` respectively in `transcribe_mlx` — breaks the autoregressive loop and tightens silence + compression-ratio drops. Trade-off: slightly worse cross-chunk proper-noun continuity
- **`collapse_adjacent_repeats()` is a post-process band-aid, not the proper fix.** Catches "thanks thanks thanks" + "facebook facebook" patterns; protects English interjection doubling ("No. No. No.", "yeah yeah", "very very good") via the `_REDUPLICABLE` set in `s05_transcribe.py`. English-only — non-English audio needs a locale-specific reduplicable list. Proper fix is Silero VAD pre-filter for mlx-whisper, tracked post-cohort

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
  - Google Meet: ` - {YYYY/MM/DD HH:MM} [TZ] - {kind}` dated tail (current), plus the older `({YYYY-MM-DD at ...})` parenthetical and `- Transcript` suffix
  - Legacy: `_transcript`, `_subtitles`, `_captions`, `_sub`, `_srt`
- **`_is_zoom_local_dir(dir_name)`**: matches `YYYY-MM-DD HH.MM.SS Topic MeetingID` pattern
- **`group_into_sessions()`**: Pass 1 groups Zoom local folder files by directory; Pass 2 groups remaining files by normalised stem
- **Regex patterns**: 7 compiled module-level patterns (`_TEAMS_SUFFIX_RE`, `_ZOOM_CLOUD_TAIL_RE`, `_ZOOM_CLOUD_PREFIX_RE`, `_ZOOM_LOCAL_DIR_RE`, `_GMEET_TAIL_RE`, `_GMEET_PAREN_RE`, `_GMEET_TRANSCRIPT_SUFFIX_RE`)
- **`_GMEET_TAIL_RE` strips the whole dated tail, and requires a trailing kind it does not read.** Confirmed 16 Aug 2026: the older two Google Meet patterns matched nothing Google emits, so a recording and its notes Doc ingested as two sessions. The tail must go entire — the recording carries the *meeting start* (`22:45`) and the Doc the *moment Gemini finished writing* (`23:02`), so a suffix-only strip still leaves two keys. The trailing kind is mandatory (it stops a title that merely ends in a date being truncated) but its text is never matched — "Recording" / "Notes by Gemini" are localised per tenant, and enumerating them is the trap that cost `_TEAMS_SUFFIX_RE` six months
- **Tests**: `tests/test_ingest.py` — normalisation, Zoom dir detection, session grouping for all platforms, false positive prevention. Teams and Google Meet each have an **observed-specimen block**; a case below those markers must be a filename seen on a real tenant, with tier and capture date recorded

## Google Meet transcripts — the .docx export is not a transcript (Stage 4)

**Observed 16 Aug 2026 on a live Workspace Business Standard tenant.** Google Meet saves no transcript *file*. It saves a **Google Doc** named `<meeting title> - <YYYY/MM/DD HH:MM TZ> - Notes by Gemini`, holding two document **tabs** — "Notes" (Gemini's AI summary) and "Transcript". Drive's default download is `.docx`, and **the export flattens both tabs into a single paragraph stream.** What `python-docx` actually sees is 19 paragraphs, of which exactly one is speech:

```
[00] 📝 Notes
[03] Invited participant@example.org Martin Storey  ← a real attendee email address, redacted here
[07] A summary wasn't produced for this meeting…    ← Gemini's summary (a stub here; pages on a real session)
[11] How is the quality of these specific notes? Take a short survey…
[12] 📖 Transcript
[15] 00:00:11
[16] Martin Storey: Okay. Talking, talking, talking. …
[17] Transcription ended after 00:00:39
[18] This editable transcript was computer generated and might contain errors.
```

**`s04_parse_docx.py` used to mis-parse this and say nothing — fixed 16 Aug 2026.** Both Teams speaker patterns anchor on a timecode at end-of-line (`Speaker Name  00:01:23`). Google puts the timecode alone on its own line and the speaker *inline* as `Name: text`, so neither matched. The bare timecode did match `_TIMESTAMP_ONLY` — but that branch **does not increment `matched_headers`**, so the counter stayed at 0, the `< 2` guard returned `None`, and `_parse_docx` fell through to `_parse_plain_paragraphs`. Every paragraph became a segment at `start_time=0.0` with no `speaker_label`, and Gemini's summary, Gemini's UI chrome and an attendee email address all entered the transcript corpus as quotable speech, at INFO ("Parsing as plain text (no timecodes)"), with the run completing normally.

**And the Teams path was broken the same way, which nothing caught for longer.** A `.docx` paragraph is **not** a line. Teams packs an entire turn — the `Martin Storey  0:04` header *and* every line of speech — into **one** paragraph separated by `<w:br/>`, which `python-docx` renders as `\n` inside `p.text`. A parser whose unit was the paragraph saw one unmatched blob per turn, so the real Teams specimen also produced segments at `start_time=0.0` with no `speaker_label`. The tests missed it because every constructed fixture put one line per paragraph — the shape the bug cannot occur in.

**How it is parsed now.** `_document_lines()` splits every paragraph on its line breaks first, so the parser's unit matches the transcript's. Then: **recognise speech, never find the tab boundary.** `_try_parse_gmeet_format` emits a segment only for an `HH:MM:SS`-only line *immediately followed by* `Name: text`, and drops everything else — Gemini's prose carries no such pairing, so the Notes tab cannot be ingested, without matching a single localised string. Meet is tried **before** Teams, because a Meet document can incidentally satisfy the looser Teams pattern (the `Transcription ended after 00:00:39` trailer does). Timecodes present but unalignable raise `DocxParseRefusedError` rather than degrading to `_parse_plain_paragraphs`.

Six things to know before touching it:

- **The unit of structure is the LINE, never the paragraph.** This is the finding that generalises: it cost the Teams path a silent mis-parse that no constructed fixture could ever have exposed. Any new format branch reads `_document_lines()`, and any new fixture must carry the real intra-paragraph line breaks. `_TIMESTAMP_ONLY` likewise has to be tested against lines — testing it against whole paragraphs is what let the refusal gate miss Teams entirely.
- **`matched_headers < 2` was refusing valid files.** The observed Teams export is a single 39-second turn, so a two-header threshold rejected it outright. One *strong* header now suffices — arrow notation, or the 2-or-more-space gap between name and timecode (`_TEAMS_SPEAKER_LINE_WIDE`) — while a single weak match still falls through. Don't restore the flat threshold.
- **The failure mode is quote fabrication, not a crash.** On a real session those summary paragraphs are pages of confident prose *about* what participants said, and quote extraction cannot tell them from testimony. **Refusing the file is better than parsing it optimistically** — the standing invariant is `docs/design-cloud-import.md` §6, "a parse refusal must produce a stated row, never a silent drop."
- **A refusal must be *recorded*, not merely raised.** A docx-bearing session has `has_existing_transcript=True`, so s02 skips audio extraction and leaves `audio_path=None` — which also excludes it from `needs_transcription`. `_gather_all_segments` therefore records a `StageFailure` (`MISSING_INPUT`, `source_file=<basename>`) and counts the lost session in `attempted`; without that the session leaves no trace anywhere in the run and the abandon check can never fire. The same treatment now covers subtitle parse errors, which had the identical silent drop.
- **The bold speaker name survives the export and is still unused.** `p.runs` carries the bold on `Martin Storey:`, but the parser reads `p.text`. The colon regex is safe here *because* the mandatory preceding timecode does the discriminating, but run-level bold would be a stronger signal if the pairing rule ever needs relaxing.
- **The tab boundary does *not* survive.** The only separators in the flattened stream are the emoji headers `📝 Notes` / `📖 Transcript` — emoji plus a word that is localised per tenant. Matching those literals is the same fragility class as path-matching the `Meet Recordings` folder that Google renamed in July 2026. **Known gap:** a Meet Doc whose Transcript tab is empty is untimed, so it lands in `_parse_plain_paragraphs` and its summary *would* be ingested. Closing that needs either those localised headings or refusing every untimed `.docx` — which would also reject agency-produced Word transcripts. Open product decision.
- **The upstream fix is to never export at all** — `documents.get` with `includeTabsContent=true` returns tabs as addressable subtrees under `document.tabs[]`. That belongs to the macOS cloud-import adapter (`docs/design-cloud-import.md` §3), and it **does not retire this bug**: hand-downloaded `.docx` files keep arriving through drag-drop, which the design commits to keeping first-class forever.

One related trap in the same neighbourhood, also fixed 16 Aug 2026: `_GMEET_TRANSCRIPT_SUFFIX_RE` and `_GMEET_PAREN_RE` did predate Google's renaming and matched nothing real — see `_GMEET_TAIL_RE` under "Platform-aware session grouping" above. Still live: **Drive's API `name` differs from the downloaded filename** — the API returns `2026/08/15 23:02` where the file on disk is sanitised to `2026_08_15 23_02`, so a grammar pinned from a download will not match a listing. `_GMEET_TAIL_RE` accepts both separators; anything new must too.

**Known residue, deliberately not fixed:** Teams' `<Name> stopped transcription` closing marker is absorbed into the final turn. Every removal rule available is either the English literal — the localisation fragility this module exists to avoid — or a heuristic that could eat a genuine last line. Pinned as a *visible* test rather than silently accepted, so it stays a known cost rather than becoming folklore.

Tests live in `tests/test_parse_docx.py`, pinned to two observed specimens in `tests/fixtures/platform-transcripts/` — `gmeet-notes-by-gemini-2026-08-15.json` (19 paragraphs) and `teams-meeting-recording-2026-08-15.json` — each tagged with tier, locale and capture date, and each recording its deliberate departures from the captured bytes (both redact the real attendee email; this repo is public). `docs/design-cloud-import.md` §6 records two separate six-month bugs (`TeamsRecordingName`, and `_TEAMS_SUFFIX_RE` in `s01_ingest.py`) caused by regexes that matched only the fixture invented alongside them — and the paragraph-vs-line bug above is the third in that family.

## Concurrent audio extraction (Stage 2)

`extract_audio_for_sessions()` is async — video files are extracted in parallel via `asyncio.to_thread()` (wrapping blocking `subprocess.run` FFmpeg calls) bounded by `asyncio.Semaphore(4)`.

- **Default 4**: fixed constant, not hardware-adaptive. The bottleneck is the macOS media engine (shared hardware decode), not CPU cores. 4 works well from M1 to M4 Ultra
- **`_extract_one()` helper**: runs `has_audio_stream()` + `extract_audio_from_video()` inside the semaphore. Both are blocking subprocess calls wrapped in `asyncio.to_thread()`
- **Platform transcript skip**: when `session.has_existing_transcript=True`, FFmpeg extraction is skipped entirely — the pipeline will use the parsed transcript and never call Whisper, so audio decode is unnecessary
- **Tool failure is fail-loud, not isolated**: `has_audio_stream()` and `extract_audio_from_video()` raise `AudioToolError` (in `utils/audio.py`) when ffprobe/ffmpeg fails to *run* — non-zero exit, missing binary, shared-library load failure (the libblas-on-amd64 repro), timeout, or corrupt input. `_extract_one` does NOT catch it: the error propagates through `asyncio.gather` → `extract_audio_for_sessions` → the pipeline → `run_lifecycle`'s top-level catch, which records a `RunFailedEvent`. This is deliberate — a broken media toolchain must never be mislabelled as "no audio stream" and degrade to an empty, confidently-"successful" report (the "no fake success" class the acceptance tests guard). A video that *genuinely* has no audio stream (ffprobe exits 0, finds no audio) is the separate non-fatal case: logged "has no audio stream, skipping" and the run continues. `has_audio_stream()` uses `-v error` (not `-v quiet`) so the failure reason survives in stderr for the exception message
- **VideoToolbox**: `utils/audio.py` passes `-hwaccel videotoolbox` on macOS, so concurrent extractions share the hardware media engine for H.264/HEVC decode
- **`concurrency` kwarg**: exposed but not yet wired to config (unlike `llm_concurrency`). Default of 4 is sufficient; config wiring deferred until there's a real need
- **Tests**: `tests/test_extract_audio.py` — extraction-skip behaviour + the tool-error-vs-genuine-no-audio distinction (`has_audio_stream` raises `AudioToolError` on non-zero exit / missing binary / timeout; the stage propagates it to abort the run; a genuinely silent video is skipped without aborting)

## Quote exclusivity across report sections (Stages 9–11)

**Design rule: every quote appears in exactly one section of the final report.** Researchers expect this — duplicates confuse non-researchers and complicate downstream processing (Miro boards, spreadsheets, etc.).

The exclusivity is enforced at three levels:

1. **Quote type separation (Stage 9 → Stages 10/11)**: `extract_quotes()` classifies every quote as `QuoteType.SCREEN_SPECIFIC` or `QuoteType.GENERAL_CONTEXT`. Stage 10 (`quote_clustering.py`) filters to `SCREEN_SPECIFIC` only; stage 11 (`thematic_grouping.py`) filters to `GENERAL_CONTEXT` only. A quote cannot appear in both a screen cluster and a theme group.

2. **Within screen clusters (Stage 10)**: The LLM prompt in `prompts.py` says "Assign each quote to exactly one screen cluster." The structured output schema (`ScreenClusterItem.quote_indices`) enforces this at the index level.

3. **Within theme groups (Stage 11)**: The LLM prompt says "Assign each quote to exactly one theme (even when it could fit several, pick the strongest fit — the researcher will reassign if needed)." The schema description on `ThemeGroupItem.quote_indices` reinforces this. A safety-net dedup in `thematic_grouping.py` catches LLM violations when weak themes are folded into "Uncategorised."

**History**: before Feb 2026, the theme prompt allowed "one or more themes" per quote. Changed to exclusive assignment because: (a) researchers expect to see each quote once and make reassignment decisions themselves, (b) non-researchers receiving the report find duplicates confusing, (c) export to CSV/clipboard doubles up rows unexpectedly.

**Smart-split preserves exclusivity.** `s09`'s `_extract_with_split` (the truncation-recovery path, `chunked-quote-extraction` `f8ea55a`) is Map-Reduce — independent chunks, no cross-chunk context — and dedups the merged result on `verbatim_excerpt` before it reaches s10/s11. So the merged quote list going into clustering/theming is the same shape as an un-chunked run, and the exclusivity invariant holds unchanged (verified live: 0 section/theme overlap on chunked runs). **Known drift (not an exclusivity break):** a chunk-local LLM can't judge "applies broadly across the interview," so chunking nudges `SCREEN_SPECIFIC`/`GENERAL_CONTEXT` classification toward `SCREEN_SPECIFIC` → s11 themes thin out. Bounded by cross-session voting (s10/s11 run over all sessions); the named follow-up is a post-merge `quote_type` re-classification stage if cohort reports feel under-themed.

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

## Progress bar gotchas

Don't try to re-enable mlx-whisper or HF Hub progress bars — they don't overwrite inside Rich `console.status()` and will scroll line-by-line. Rule: suppress all tqdm/HF bars entirely, let the Rich spinner handle progress indication. See `docs/design-pipeline-resilience.md` ("Progress Bar Dead Ends") for the full list of dead ends (mlx-whisper `verbose` parameter, env var import timing, tqdm+Rich conflict).

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

Reference for `_derive_journeys`, `_oxford_list_html`, `_build_session_rows`, `_render_sentiment_sparkline`, `_FAKE_THUMBNAILS` env var, `format_finder_filename`, and moderator display logic — see `docs/design-dashboard-navigation.md` ("Session table helpers" section).

## Pipeline runtime gotchas

- **Smart-split halves cut by SEGMENT INDEX, not time — and never by a fixed clock-time.** `s09_quote_extraction._split_transcript` has two tiers: (1) high-confidence s08 topic boundary in the middle 60% → cut by *time* around the boundary (safe from "one chunk keeps everything" because the middle-60% eligibility bounds split_time ± overlap inside the span); (2) mechanical halves → cut by *segment index* (`segments[:mid+k]` / `segments[mid-k:]`), NOT by the count-midpoint timecode. Reason: output scales with segment count, and a time-cut around the count-midpoint can pull nearly all segments into one chunk on temporally back-loaded density (sparse intro, dense tail) → the recursion burns its depth budget without shrinking output. **CRITICAL guardrail — never introduce a deterministic clock-time cut** ("always split at minute 30"): split timecodes must stay session-specific, or split bias correlates across the cohort and defeats the s10/s11 cross-session correction that bounds the `SCREEN_SPECIFIC`/`GENERAL_CONTEXT` classification drift. A session that exhausts depth-3 records exactly ONE `StageFailure` (category `OUTPUT_TRUNCATED`), not one per chunk; the run continues if other sessions succeed.
- **`_format_duration`, `_print_step`, `_print_cached_step`, `_is_stage_cached`, `_is_stage_verified`, and `_is_speaker_stage_verified` are module-level in `pipeline.py`** — `cli.py` imports `_format_duration` from there. Don't move them into the `Pipeline` class. Cache-check sites use `_is_stage_verified` (Phase 2b), not the old `_is_stage_cached` directly
- **Pipeline resume (Phase 1c/1d/1d-ext)**: `run()` loads an existing manifest on startup via `_prev_manifest = load_manifest(output_dir)`. **Stage-level caching (1c)**: Stages 8–11 check `_is_stage_cached(_prev_manifest, STAGE_*)` + intermediate JSON file existence — if both true, data is loaded from disk and `(cached)` is printed. **Per-session caching (1d)**: Stages 8 (topic segmentation) and 9 (quote extraction) track which sessions completed within the stage via `SessionRecord` entries in the manifest. On resume, completed sessions' results are loaded from intermediate JSON (filtered by `session_id`), only remaining sessions get LLM calls, then results are merged. `mark_session_complete()` writes after each session; `mark_stage_complete()` after all sessions finish. **Transcription + speaker ID caching (1d-ext)**: Stages 3-5 (transcription) cache `session_segments.json` to intermediate/; stage 5b (speaker ID) caches `speaker-info/{sid}.json` per session with `SpeakerInfo` + segments-with-roles. `assign_speaker_codes()` always re-runs (global participant numbering). `speaker_info_to_dict()` / `speaker_info_from_dict()` in `identify_speakers.py` serialize the `SpeakerInfo` dataclass. Stages 1-2 (ingest, audio extraction) and stage 6 (merge) always re-run (fast). Stage 12 (render) always re-runs. Cache requires `write_intermediate=True` (the default). Only `COMPLETE` status triggers stage-level cache; `RUNNING`/`PARTIAL`/`FAILED` trigger per-session resume path
- **CLI resume guard** (`cli.py`): The output directory guard allows re-running into an existing output directory when a pipeline manifest exists (resume path). If no manifest exists, it blocks with the original "Output directory already exists" error. This prevents accidental overwrites while enabling crash recovery. `--clean` always wipes everything including the manifest. On resume, a one-line summary is printed (e.g. "Resuming: 7/10 sessions have quotes, 3 remaining.") via `format_resume_summary()` in `status.py`
- **Session-count guard — REMOVED 19 Aug 2026.** Was: >16 sessions prompted "Found N sessions in dir/. Continue? [Y/n]", with `--yes` / `-y` to bypass. Deleted along with `_MAX_SESSIONS_NO_CONFIRM`, `_confirm_large_session_count`, `Pipeline(skip_confirm=)`, the CLI flag and `tests/test_session_guard.py`. **Two reasons, and both are worth carrying forward.** (1) *Count is the wrong axis.* A thousand ten-second video answers to one question is an ordinary unmoderated study; ten ninety-minute interviews is five times the transcription work at one percent of the file count. The guard blocked the cheap case and waved the expensive one through. (2) *It hung the desktop.* `Confirm.ask` reached a sidecar whose stdin was the inherited Xcode console TTY — a 57-session drop sat blocked for eleven hours at 2.7 s of CPU, with the sidebar still showing it as running and no terminus event ever written. **What replaced it:** the protection that was actually wanted lives in `s01_ingest.discover_files` — `_refuse_reason()` rejects filesystem and system roots structurally, before anything touches the disk, and `PipelineRunner.swift` now points the sidecar's stdin at `/dev/null` so no future prompt can block a headless run. If a cost warning is ever wanted back, key it on **total duration**, not session count, and never let it block a non-TTY run
- **`bristlenose status <folder>`**: Read-only command that prints project state from the manifest. Accepts input dir or output dir (auto-detects via `_resolve_output_dir()`). `-v` shows per-session detail with provider/model. Pure logic in `bristlenose/status.py` (`get_project_status()`, `format_resume_summary()`), printing in `cli.py` (`_print_project_status()`). Validates intermediate file existence for completed stages, warns if missing. 14 tests in `tests/test_status.py`
- **`llm_client` and `concurrency` in `run()`** — both are declared unconditionally before stage 5b (`llm_client: LLMClient | None = None`, `concurrency = self.settings.llm_concurrency`). `llm_client` is created inside the speaker-ID `else` branch when that stage actually runs, but when speaker ID is fully cached, `llm_client` stays `None`. Lazy init guards (`if llm_client is None: llm_client = LLMClient(...)`) before the LLM calls in topic segmentation and quote extraction ensure later stages always have a client. If adding new LLM stages, add the same guard
- **Phase 2b hash verification and manifest invalidation** — `_is_stage_verified()` checks SHA-256 of cached files against the manifest. On hash mismatch it **removes the stage from `_prev_manifest`** so `get_completed_session_ids()` returns empty — this prevents the per-session resume path from trying to JSON-parse a corrupt file. Without this invalidation, a hash mismatch triggers the `else` branch which still tries to load cached data for "completed" sessions from the same corrupt file. `_is_speaker_stage_verified()` does the same for per-session hashes
- **Corruption-tolerant per-session resume reads (`_load_cached_json`)** — defence-in-depth *under* Phase 2b. The hash check only fires on the full-cache (`_is_stage_verified` returns True) path; the **per-session resume reads run while the stage is still `RUNNING`**, where `_is_stage_verified` short-circuits at the status check *before* hashing (and backward-compat manifests with `content_hash=None` pass verification unconditionally). Those reads (transcription `session_segments.json`, speaker `speaker-info/{sid}.json`, topic `topic_boundaries.json`, quote `extracted_quotes.json`) used to `json.loads()` after an exists-only check → a power-cut-truncated file crashed the resume with `JSONDecodeError`. They now go through `_load_cached_json(path)` (in `pipeline.py`), which returns `None` on `OSError`/`ValueError` (covers `JSONDecodeError` + `UnicodeDecodeError`) and warns. **Critical: on a `None` (corrupt) read the call site also drops the affected session ids from the cached set** (`_cached_*_sids = set()`, or rebuilds it per-file for speaker-info) — otherwise those sessions are excluded from *both* cache and `_remaining`, silently vanishing from the report. The full-cache verified reads are intentionally left raw (Phase 2b hash-guards them for current-format manifests); the `content_hash=None` legacy edge and the `run_analysis_only`/render read path are known residuals. Tests: `tests/test_pipeline_resume.py::test_load_cached_json_*`
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

## Stage-cache honesty (A4, May 2026)

When adding or modifying analysis stages, three invariants must hold or the cache poisons on failure (the 2026-05-09 first-run repro). All landed via `a4-stage-cache-honesty`:

1. **Abandon-check fires BEFORE `mark_stage_complete`** at every analysis-stage site in `pipeline.py`. If `mark_stage_complete` runs first and the abandon then raises, the manifest is already poisoned (empty intermediate JSON cached as COMPLETE). The next run reads `(cached)` and renders an empty report. Pattern at every site:

   ```python
   # 1. Build the StageOutcome rollup
   self._summary.<bucket> = StageOutcome(...)

   # 2. Abandon check FIRST — raises before any manifest write on failure
   if self._summary.<bucket>.attempted > 0 and self._summary.<bucket>.succeeded == 0:
       raise PipelineAbandonedError(cause=_dominant_cause(...), summary=self._summary)

   # 3. ONLY THEN write success state to manifest
   mark_stage_complete(manifest, STAGE_X, ..., output_path=<intermediate_file>)
   write_manifest(manifest, output_dir)
   ```

2. **Stages with fallback paths must emit `StageFailure` at the LLM call site, BEFORE the fallback runs.** `s10_quote_clustering.cluster_by_screen` has `_fallback_clustering`; `s11_thematic_grouping` has `_fallback_grouping`. Both produce non-empty results on LLM failure. If `outcome.failed.append(...)` runs only when no fallback fires, `succeeded > 0 AND failed == 0` and the abandon predicate never fires (cluster_and_group was historically "soft" for this reason — now hard). Pattern:

   ```python
   try:
       result = await llm_call(...)
       outcome.succeeded = 1
   except Exception as exc:
       outcome.failed.append(StageFailure(
           session_id=None,  # or sid for session-scoped
           cause=_build_cause(exc, stage=..., provider=llm_client.provider),
       ))
       result = _fallback_something(...)  # fallback runs AFTER outcome.failed.append
   ```

3. **`Cause.message` is constructed from structured fields only, never from `str(exc)` or `repr(exc)`.** Provider error bodies sometimes echo prompt fragments (participant tokens, transcript substrings). `pipeline-events.jsonl` is a named re-identification surface (see CLAUDE.md alongside `pii_summary.txt`, `llm-calls.jsonl`). Use `_build_cause(exc, *, stage, provider, http_status, session_id)` from `run_lifecycle.py` — it composes `Cause.message` as `f"<stage> failed: <ClassName> on <provider>"` and never reads exception body content. Category is still inferred via `categorise_exception` substring matchers (bristlenose-controlled patterns like `\b401\b` / `\brate limit\b`, safe to run against raw text).

`mark_stage_complete` itself enforces invariant 1 belt-and-braces: pass `output_path=<intermediate_file>` and it refuses to record completion when the file is empty (zero-byte OR JSON-equivalent-to-empty: `[]` / `{}` / `null`). Defensive — covers call sites that forgot the explicit abandon-check.

Stage signatures: `s08_topic_segmentation.segment_topics` returns `tuple[list[SessionTopicMap], StageOutcome]` (session-scoped, `attempted=len(transcripts)` upfront). `s09_quote_extraction.extract_quotes` same pattern. `s10_quote_clustering.cluster_by_screen` and `s11_thematic_grouping.group_by_theme` return `tuple[..., StageOutcome]` stage-scoped (`attempted=1`).

`_succeeded_sids` (transcribe stage success derivation) treats Whisper-success-with-zero-segments as SUCCESS — silent recording is valid input. Drive the predicate off `_fresh_transcript_outcome.failed` exclusion, not `session_segments` value-truthiness.

Full design: `docs/design-pipeline-resilience.md` §"Changelog" 2026-05-12 entry. Implementation handoff: `docs/private/archive/A4-stage-cache-honesty.md`.
