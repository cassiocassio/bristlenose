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
├── bristlenose-{slug}-report.html      # render_html.py output
├── bristlenose-{slug}-report.md        # render_output.py output
├── people.yaml                         # people.py output
├── assets/                             # static files (CSS, logos, player)
├── sessions/                           # transcript pages (render_html.py)
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

`identify_speakers.py` runs a two-pass speaker role assignment: heuristic first, then LLM refinement.

- **Heuristic pass** (`identify_speaker_roles_heuristic`): scores speakers by question ratio and researcher-phrase hits. Assigns `RESEARCHER`, `PARTICIPANT`, or `OBSERVER`. Fast, no LLM needed
- **LLM pass** (`identify_speaker_roles_llm`): sends first ~5 minutes to the LLM for refined role assignment. Also extracts `person_name` and `job_title` for each speaker when mentioned in the transcript
- **Return type**: `identify_speaker_roles_llm()` returns `list[SpeakerInfo]` — a dataclass with `speaker_label`, `role`, `person_name`, `job_title`. Still mutates segments in place for role assignment (existing behaviour). Returns empty list on exception
- **`SpeakerInfo` import**: defined in `identify_speakers.py`. Other modules import it under `TYPE_CHECKING` to avoid circular imports (e.g. `people.py` uses `if TYPE_CHECKING: from bristlenose.stages.identify_speakers import SpeakerInfo`)
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
- **Concurrent audio extraction**: `extract_audio_for_sessions()` in `stages/extract_audio.py` is async — up to 4 FFmpeg processes run in parallel via `asyncio.Semaphore(4)` + `asyncio.gather()`. Blocking `subprocess.run` calls wrapped in `asyncio.to_thread()`. Default concurrency of 4 is a fixed constant (not hardware-adaptive) because the bottleneck is the shared media engine on macOS, not CPU core count — works well across all Apple Silicon variants (M1 through M4 Ultra). On Linux without hardware decode, 4 concurrent software-decode processes is still reasonable. `concurrency` kwarg exposed for future config wiring if needed
- **Audio extraction skip for platform transcripts**: `extract_audio.py` checks `session.has_existing_transcript` and skips FFmpeg entirely when a platform transcript (VTT/SRT/DOCX) is present — avoids unnecessary video decode when Whisper won't be called

## Transcript coverage

Collapsible section at the end of the research report showing what proportion of the transcript made it into quotes.

- **Purpose**: researchers worry the AI silently dropped important material. The coverage section provides triage: if "% omitted" is low, they can trust the report; if high, they expand and review
- **Three percentages**: `X% in report · Y% moderator · Z% omitted` — word-count based, whole numbers. "In report" = participant words in quote timecode ranges. "Moderator" = moderator + observer speech. "Omitted" = participant words not covered by any quote
- **Omitted content**: per-session, shows participant speech that didn't become quotes. Segments >3 words shown in full with speaker code and timecode; segments ≤3 words collapsed into a summary with repeat counts (`Okay. (4×), Yeah. (2×)`)
- **Module**: `bristlenose/coverage.py` — `CoverageStats`, `SessionOmitted`, `OmittedSegment` dataclasses, `calculate_coverage()` function
- **Rendering**: `_build_coverage_html()` in `render_html.py`. HTML `<details>` element, collapsed by default. CSS in `organisms/coverage.css`
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

## Gotchas

- **`segment_topics()` returns `list[SessionTopicMap]`, NOT a dict** — use `sum(len(m.boundaries) for m in topic_maps)`, not `topic_maps.values()`. This was a bug that took two attempts to find because `_gather_all_segments()` returns `dict[str, list[TranscriptSegment]]` (which does have `.values()`), creating a misleading pattern
- **`InputSession.files` is a list, `InputFile.duration_seconds` is on each file** — to sum audio duration: `sum(f.duration_seconds or 0 for s in sessions for f in s.files)`, not `s.duration_seconds`
- **`transcripts-cooked/` only exists with `--redact-pii`** — if a previous run used PII redaction but the current one doesn't, stale cooked files remain on disk. Coverage and transcript pages must use the same transcript source to avoid broken links. `render_transcript_pages()` accepts a `transcripts` parameter to ensure consistency
- **`_render_transcript_page()` accepts `FullTranscript`, not just `PiiCleanTranscript`** — the assertion uses `isinstance(transcript, FullTranscript)`. Since `PiiCleanTranscript` is a subclass, both types pass. Don't tighten this to `PiiCleanTranscript` or it will crash when PII redaction is off (the default)
- **`player.js` only intercepts `.timecode` clicks with `data-participant` and `data-seconds`** — coverage section links use `class="timecode"` but NO data attributes, so they navigate normally. If you add new timecode links that should navigate (not open the player), omit the data attributes
