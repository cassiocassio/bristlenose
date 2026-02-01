# Bristlenose — Where I Left Off

Last updated: 1 Feb 2026 (v0.6.4, concurrent LLM calls + performance audit)

---

## Done

- [x] Full 12-stage pipeline (ingest → render)
- [x] HTML report with CSS theme (v5), clickable timecodes, popout video player
- [x] Sentiment histogram (horizontal bars, side-by-side AI + user-tag charts)
- [x] Friction points, user journeys
- [x] Favourite quotes (star, reorder, FLIP animation, CSV export)
- [x] Inline quote editing (pencil icon, contenteditable, localStorage persistence)
- [x] Tag system — AI-generated badges (deletable with restore) + user-added tags (auto-suggest, keyboard nav), localStorage persistence, CSV export with separate AI/User columns
- [x] Atomic design system (`bristlenose/theme/`) — tokens, atoms, molecules, organisms, templates; CSS concatenated at render time
- [x] JavaScript extraction — report JS broken out of `render_html.py` into standalone modules (`bristlenose/theme/js/`): storage, player, favourites, editing, tags, histogram, csv-export, names, main; concatenated at render time mirroring the CSS pattern
- [x] `bristlenose render` command — re-render reports from intermediate JSON without retranscribing or calling LLMs
- [x] Apple Silicon GPU acceleration (MLX)
- [x] PII redaction (Presidio)
- [x] Cross-platform support (macOS, Linux, Windows)
- [x] AGPL-3.0 licence with CLA
- [x] Renamed gourani → bristlenose
- [x] Published to PyPI (0.1.0)
- [x] Published to GitHub (cassiocassio/bristlenose)
- [x] Homebrew tap (cassiocassio/homebrew-bristlenose) — `brew install cassiocassio/bristlenose/bristlenose` works
- [x] README with install instructions (brew, pipx, uv)
- [x] CONTRIBUTING.md with release process and design system documented
- [x] (0.3.2) Tag auto-suggest: don't offer tags the quote already has
- [x] Project logo in report header (top-right, copied alongside HTML)
- [x] (0.3.7) Markdown style template (`bristlenose/utils/markdown.py`) — single source of truth for all markdown/txt formatting; all stage files refactored to use it
- [x] (0.3.7) Per-session `.md` transcripts alongside `.txt` in `raw_transcripts/` and `cooked_transcripts/`
- [x] (0.3.7) Participant codes in transcript segments — `[p1]` instead of `[PARTICIPANT]` for researcher context
- [x] (0.3.7) Transcript parser accepts both `MM:SS` and `HH:MM:SS` timecodes
- [x] (0.3.8) Timecode handling audit: verified full pipeline for sessions <1h and ≥1h, added edge-case tests
- [x] Sentiment histogram: tag text left-aligned, shared bar scale across AI + user charts, positive greens on top / negative reds below, negatives sorted ascending (worst near divider)
- [x] `bristlenose help` command — rich-formatted help with topics: commands, config, workflows; plus `--version` / `-V` flag
- [x] Man page (`man/bristlenose.1`) — full groff man page covering all commands, options, config, examples; included in sdist, Homebrew formula installs to `man1/`
- [x] (0.4.0) Dark mode — CSS `light-dark()` function, follows OS/browser preference by default, `color_scheme` config override (`auto`/`light`/`dark`), `<meta name="color-scheme">` tag, `<picture>` element for dark logo, print forced to light, histogram hard-coded colours replaced with CSS tokens, 17 tests
- [x] PII redaction default OFF — `pii_enabled: bool = False` in config; CLI flags `--redact-pii` (opt in) / `--retain-pii` (explicit default); replaced `--no-pii`; 3 tests
- [x] People file (participant registry) — `people.yaml` in output dir; Pydantic models (`PersonComputed`, `PersonEditable`, `PersonEntry`, `PeopleFile`); `bristlenose/people.py` (load, compute, merge, write, display name map); merge strategy preserves human edits across re-runs; display names in quotes/tables/friction/journeys in both markdown and HTML reports; `data-participant` HTML attributes kept as canonical `participant_id` for JS; 21 new tests (14 people, 3 PII, 2 models, 2 markdown)
- [x] Participant table redesign — columns now `ID | Name | Role | Start | Duration | Words | Source file` (was 9 cols, now 7); ID shows raw `p1`/`p2`/`p3`; Name shows `full_name` from people.yaml (pale-grey italic "Unnamed" placeholder when empty); Role moved next to Name; Date+Start merged into single Start column with macOS Finder-style relative dates (`Today at 16:59` / `Yesterday at 17:00` / `29 Jan 2026 at 20:56`); removed % Words and % Time; `format_finder_date()` helper in `utils/markdown.py` with 8 tests
- [x] `render --clean` accepted gracefully — flag is ignored with a reassuring message that render is always non-destructive (overwrites reports only)
- [x] Per-participant HTML transcript pages — `transcript_p1.html`, `transcript_p2.html` etc.; participant table ID column is a hyperlink; back button styled after Claude search (`← {project_name} Research Report`); timecodes clickable with video player; speaker names resolved (short_name → full_name → pid); prefers cooked transcripts over raw when both exist; `transcript.css` added to theme; only `storage.js` + `player.js` loaded (no favourites/editing/tags); 17 tests
- [x] Quote attribution links to transcripts — `— p1` at end of each quote is a hyperlink to `transcript_p1.html#t-{seconds}`, deep-linking to the exact segment; `.speaker-link` CSS in `blockquote.css` (inherits muted colour, accent on hover)
- [x] Editable participant names in report — pencil icon on participant table Name/Role cells; `contenteditable` inline editing; localStorage persistence; YAML clipboard export; reconciliation with baked-in data on re-render; `names.js` module + `name-edit.css` molecule
- [x] Auto name/role extraction from transcripts — Stage 5b LLM prompt extended to extract `person_name` and `job_title`; `SpeakerInfo` dataclass; speaker label metadata harvesting for Teams/DOCX/VTT sources; `auto_populate_names()` fills empty editable fields (LLM > metadata, never overwrites); wired into `run()` and `run_transcription_only()`
- [x] Short name suggestion heuristic — `suggest_short_names()` in `people.py`; first token of `full_name`, disambiguates collisions with last-name initial ("Sarah J." vs "Sarah K."); JS mirror `suggestShortName()` in `names.js` for browser-side auto-fill; 26 new tests
- [x] Editable section/theme headings — pencil icon inline editing on section titles, section descriptions, theme titles, theme descriptions; bidirectional ToC sync; shared `bristlenose-edits` localStorage; `initInlineEditing()` in `editing.js`; 19 tests
- [x] (0.6.3) Header redesign — logo top-left (flipped, baseline-aligned), "Bristlenose" logotype + project name, right-aligned doc title + participant/session count + Finder-date meta; new `atoms/logo.css` layout
- [x] (0.6.3) View-switcher dropdown — borderless "All quotes" / "Favourite quotes" / "Participant data" menu in sticky toolbar; `view-switcher.js` module; replaces old hamburger/button-bar pattern; `currentViewMode` global shared with `csv-export.js`
- [x] (0.6.3) Copy CSV button with clipboard SVG icon — single adaptive button (exports all or favourites based on view mode); inline SVG replaces character entity
- [x] (0.6.3) Quote attributions use raw pids — report quotes show `— p1` (anonymisation boundary); transcript pages keep display names; `names.js` no longer updates `.speaker-link` text
- [x] (0.6.3) Analysis ToC column — Sentiment, Tags, Friction points, and User journeys in their own "Analysis" nav column, separate from Themes

---

## Next up: CI/CD automation

These are ready to implement. Do them in order — each builds on the previous.

### 1. ✅ CI on every push/PR

Done — `.github/workflows/ci.yml`. Ruff and pytest are hard gates; mypy runs informational (`continue-on-error`) due to 9 pre-existing third-party SDK type errors.

### 2. ✅ Publish to PyPI on tagged release

Done — `.github/workflows/release.yml`. Triggers on `v*` tags, runs CI first, builds sdist + wheel, publishes via PyPI trusted publishing (OIDC, no token needed). Trusted publisher configured at pypi.org.

### 3. ✅ Auto-update Homebrew tap after PyPI publish

Done — `release.yml` dispatches to `cassiocassio/homebrew-bristlenose` after PyPI publish. The tap repo's `update-formula.yml` fetches the sdist sha256 from PyPI and patches the formula. Requires `HOMEBREW_TAP_TOKEN` secret (classic PAT with `repo` scope).

### 4. ✅ GitHub Release with changelog

Done — `release.yml` `github-release` job creates a GitHub Release on the tag with auto-generated release notes.

---

## Secrets management

Current state and planned improvements.

### Done

- [x] **GitHub token** — stored in macOS Keychain via `gh auth`, accessed by `gh` CLI and git-credential-manager
- [x] **PyPI token** — stored in macOS Keychain via `keyring set https://upload.pypi.org/legacy/ __token__`, picked up automatically by `twine upload`
- [x] **PyPI Trusted Publishing** — configured; `release.yml` publishes via OIDC, no token needed in CI or locally for releases
- [x] **`HOMEBREW_TAP_TOKEN`** — classic PAT with `repo` scope (no expiry), stored as a GitHub Actions secret in the bristlenose repo; used by `notify-homebrew` job to dispatch `repository_dispatch` to `cassiocassio/homebrew-bristlenose`

### Current (works but could be better)

- **Anthropic/OpenAI API keys** — shell env var (`ANTHROPIC_API_KEY`) set in shell profile, plus `.env` file in project root (gitignored). Standard approach, fine for local dev.

### To do

- [ ] **Bristlenose API keys → Keychain** — add optional `keyring` support in `config.py` so bristlenose can read `BRISTLENOSE_ANTHROPIC_API_KEY` from macOS Keychain (falling back to env var / `.env`). Would let users avoid plaintext keys on disk.

---

## Feature roadmap

Organised from easiest to hardest. The README has a condensed version; this is the full list.

### Trivial (hours each)

- [ ] Search-as-you-type filtering — filter visible quotes by text content
- [ ] Hide/show quotes — toggle individual quotes, persist state
- [ ] Keyboard shortcuts — j/k navigation, s to star, e to edit, / to search
- [ ] Timecodes: restore blue colour — currently showing visited-link colour; force `--bn-colour-accent` and drop the `[]` square brackets since the blue makes them visually distinct already
- [ ] User tag × button — vertically centre the close button optically (currently sits too low)
- [ ] AI badge × button — the circled × is ugly; restyle to match user tag delete or use a simpler glyph
- [ ] Indent tags — add left margin/padding so the badge row sits indented under the quote text
- [ ] Logo: slightly bigger — bump from 80px to ~100px
- [ ] JS: `'use strict'` — add to each JS module to catch accidental globals and silent errors
- [ ] JS: shared `utils.js` — extract duplicated quote-stripping regex (`QUOTE_RE` / `CSV_QUOTE_RE`) into a shared module
- [ ] JS: magic numbers → config — extract `150`ms blur delay, `200`ms animation, `250`ms FLIP duration, `2000`ms toast, `8` max suggestions, `48`px min input into a shared constants object
- [x] JS: histogram hardcoded colours — replaced inline `'#9ca3af'` / `'#6b7280'` with `var(--bn-colour-muted)` (done in v0.4.0 dark mode)
- [ ] JS: drop `execCommand('copy')` fallback — `navigator.clipboard.writeText` is sufficient for all supported browsers; remove deprecated fallback or gate behind a warning

### Small (a day or two each)

- [x] Editable participant names in report — pencil icon inline editing, localStorage, YAML export, reconciliation
- [ ] Participant metadata: day of the week in recordings — Start column now shows date+time (Finder-style), but could also show day name (e.g. "Mon 29 Jan 2026 at 20:56")
- [ ] Reduce AI tag density — too many AI badges per quote; tune the LLM prompt or filter to show only the most relevant 2–3
- [x] Sentiment & friction as standalone sections — moved to "Analysis" TOC column alongside Tags and User journeys
- [ ] User-tags histogram: right-align bars — bars should grow from the same zero-x baseline as the AI sentiment chart so the two read side-by-side
- [ ] Clickable histogram bars — clicking a bar in sentiment or user-tags chart opens a filtered view showing only quotes with that tag/emotion
- [ ] Sticky header — the toolbar (view-switcher + Copy CSV) is sticky but the header (logo, logotype, project name) scrolls away; decide whether to make the full header sticky or keep current behaviour where only the toolbar sticks
- [x] Burger menu — replaced with borderless view-switcher dropdown (All quotes / Favourite quotes / Participant data) + Copy CSV button in sticky toolbar
- [ ] Refactor render_html.py header/toolbar into template helpers — the report page and transcript page duplicate header HTML (logo, logotype, project name, meta) and toolbar markup; extract into shared helper functions so page-specific rendering doesn't repeat the boilerplate
- [ ] Theme management in browser — create/rename/reorder/delete themes in the report, user-generated CSS themes (dark mode done; token architecture ready for custom themes)
- [ ] Dark logo — replace placeholder inverted image with a proper albino bristlenose pleco (transparent PNG, ~480x480, suitable licence)
- [ ] Lost quotes — surface quotes the AI didn't select, let users rescue them
- [x] Transcript linking — click a quote's `— p1` attribution to jump to that segment in the full transcript page (deep-link anchors `#t-{seconds}` on every segment)
- [ ] .docx export — export the report as a Word document
- [ ] Edit writeback — write inline corrections back to cooked transcript files
- [ ] JS: split `tags.js` (453 lines) — separate AI badge lifecycle, user tag CRUD, and auto-suggest UI into `ai-badges.js`, `user-tags.js`, `suggest.js`
- [ ] JS: explicit cross-module state — replace implicit globals (`userTags` read by `histogram.js`) with a shared namespace object (`bn.state.userTags`) or pass state through init functions
- [ ] JS: auto-suggest accessibility — add ARIA attributes (`role="combobox"`, `aria-expanded`, `aria-activedescendant`) so screen readers can navigate the tag suggest dropdown

### Medium (a few days each)

- [ ] Moderator identification and transcript page speaker styling (see design notes below)
- [x] LLM name/role extraction from transcripts — extended Stage 5b, `SpeakerInfo` dataclass, metadata harvesting, auto-populate
- [ ] Multi-participant sessions — handle recordings with more than one interviewee
- [ ] Speaker diarisation improvements — better accuracy, manual correction UI
- [ ] Batch processing dashboard — progress bars, partial results, resume interrupted runs
- [ ] JS tests — add lightweight DOM-based tests (jsdom or Playwright) covering tag persistence, CSV export output, favourite reordering, and edit save/restore

### `bristlenose doctor` and dependency UX

Full design doc: `docs/design-doctor-and-snap.md`

- [x] `bristlenose doctor` command — seven checks (FFmpeg, backend, model, API key, network, PII, disk)
- [x] Pre-flight gate on `run`/`transcribe-only`/`analyze` — catches problems before slow work starts
- [x] First-run auto-doctor — runs automatically on first invocation, sentinel at `~/.config/bristlenose/.doctor-ran`
- [x] Install-method-aware fix messages — detect snap/brew/pip, show tailored install instructions
- [x] API key validation in pre-flight — cheap API call to catch expired/revoked keys upfront
- [x] Whisper model cache check — detect whether model is cached without triggering download
- [ ] `--prefetch-model` flag — download Whisper model and exit (for slow connections, CI setups)
- [ ] Homebrew formula: add `post_install` for spaCy model download, improve caveats

### Performance (audited Feb 2026)

Full audit done. Stage concurrency (item 1) is shipped. Remaining items ranked by impact.

#### Done

- [x] **Concurrent per-participant LLM calls** — stages 5b, 8, 9 use `asyncio.Semaphore(llm_concurrency)` + `asyncio.gather()` to run up to 3 concurrent API calls per stage. Stages 10+11 (clustering + theming) also run concurrently via `asyncio.gather()`. Wires up the existing `llm_concurrency: int = 3` config. For 8 participants, estimated ~2.5x speedup on LLM-bound time (~220s → ~85s)

#### Quick wins (minimal code changes)

- [ ] **Compact JSON in LLM prompts** — `quote_clustering.py:54` and `thematic_grouping.py:53` use `json.dumps(indent=2)` to serialize quotes for the LLM prompt. Switching to `indent=None` (or `separators=(",",":")`) saves 10–20% input tokens on the two cross-participant calls. Change: 2 lines
- [ ] **Cache `system_profiler` results** — `utils/hardware.py` runs `system_profiler SPHardwareDataType` and `system_profiler SPDisplaysDataType` on every startup (~2–4s on macOS). Results don't change between runs. Cache to `~/.config/bristlenose/.hardware-cache.json` with a TTL (e.g. 24h). Change: ~30 lines in `hardware.py`
- [ ] **Skip logo copy when unchanged** — `render_html.py` runs `shutil.copy2()` for both logo images on every render. Add a size/mtime check first. Minor savings but avoids unnecessary disk writes

#### Medium effort (one module each)

- [ ] **Pipeline stages 8→9 per participant** — instead of "all stage 8 then all stage 9", run `_segment_single(p) → _extract_single(p)` as a chained coroutine per participant, then gather all. This lets participant B's topic segmentation overlap with participant A's quote extraction. Max utilisation of the `llm_concurrency` window across both stages. Change: refactor the stage 8→9 calls in `pipeline.py` into a per-participant async chain, bounded by the same semaphore
- [ ] **Pass transcript data to renderer** — `render_transcript_pages()` in `render_html.py:652` re-reads `.txt` files from disk via `load_transcripts_from_dir()`, even though the full pipeline had all transcript data in memory during stages 6–11. Thread `clean_transcripts` through to the render call to avoid redundant disk I/O. Change: add a `transcripts` parameter to `render_html()` and `render_transcript_pages()`, pass it from `pipeline.py`
- [ ] **Concurrent FFmpeg audio extraction** — `stages/extract_audio.py:36` processes video files one at a time. Use `asyncio.create_subprocess_exec()` (or `asyncio.to_thread()` wrapping the existing subprocess) to run multiple FFmpeg instances in parallel. Bounded by number of CPU cores. Change: refactor `extract_audio_for_sessions()` to async with gather
- [ ] **Temp WAV cleanup** — extracted WAV files in `output/temp/` are never cleaned up. At ~115 MB per hour of audio per participant, 10 one-hour interviews leave ~1.15 GB of temp files. Add a cleanup step after transcription (or a `--clean-temp` flag). Change: add `shutil.rmtree(temp_dir)` after `_gather_all_segments` in `pipeline.py`, guarded by a config flag

#### Larger effort (new subsystem)

- [ ] **LLM response cache** — hash `(transcript content + prompt template + model name)` → store response JSON in `output/intermediate/cache/`. On `analyze` re-runs with unchanged transcripts, skip the API call and return cached response. Benefits: saves money and time on re-runs (e.g. after editing prompts for one stage, the other stages don't re-run). Implementation: compute SHA-256 of `(system_prompt + user_prompt + model)` in `LLMClient.analyze()`, check for cached file, write on miss. Add `--no-cache` flag to force fresh calls. Change: ~80 lines in `llm/client.py` + config flag
- [ ] **Word timestamp pruning** — `TranscriptSegment.words: list[Word]` stores per-word timing for every segment. These are used only during transcript merging (overlap detection). After stage 6 (merge), the word lists could be dropped to free memory. For 10 one-hour interviews: ~80,000 Word objects freed. Also reduces intermediate JSON size. Change: add a `strip_word_timestamps()` pass after merge in `pipeline.py`

#### Not worth optimising (documented for completeness)

- **Whisper transcription is sequential**: GPU is already saturated by a single transcription. Parallelising wouldn't help on single-GPU machines. On CPU-only builds, `asyncio.to_thread()` could help for multi-file runs but the speedup is marginal vs the total transcription time
- **CSS/JS reads (32 small files)**: already lazy-cached in module-level globals. Only read once per process. Not a bottleneck
- **Intermediate JSON `indent=2` on disk**: adds ~15% file size vs compact JSON, but these files are for human debugging. Keep pretty-printed
- **Pydantic `model_dump()` serialisation cost**: called for every model when writing intermediate JSON. Profiling shows this is <100ms even for large quote lists. Not worth optimising

### Packaging (partially done)

- [x] PyPI (`pipx install bristlenose`)
- [x] Homebrew tap (`brew install cassiocassio/bristlenose/bristlenose`)
- [x] Snap for Ubuntu/Linux (`snap install bristlenose --classic`) — `snap/snapcraft.yaml` + `.github/workflows/snap.yml`. Classic confinement, ~307 MB full-featured snap, GitHub Actions CI (edge on push to main, stable on tags). Bundles FFmpeg + spaCy model + all ML deps. Tested locally on arm64 (Multipass), CI builds amd64. Pre-launch: register name, request classic confinement approval, add `SNAPCRAFT_STORE_CREDENTIALS` secret.
- [ ] Windows installer (winget or similar)

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — read from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`); the only file to edit when releasing |
| `bristlenose/cli.py` | Typer CLI entry point (`run`, `transcribe-only`, `analyze`, `render`, `doctor`) |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator (full run, transcribe-only, analyze-only, render-only) |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/render_html.py` | HTML report renderer — loads CSS + JS from theme/, all interactive features |
| `bristlenose/theme/` | Atomic CSS design system (tokens, atoms, molecules, organisms, templates) |
| `bristlenose/theme/js/` | Report JavaScript modules (storage, player, favourites, editing, tags, histogram, csv-export, view-switcher, names, main) — concatenated at render time |
| `bristlenose/llm/prompts.py` | LLM prompt templates |
| `bristlenose/utils/hardware.py` | GPU/CPU auto-detection |
| `bristlenose/doctor.py` | Doctor check logic (pure, no UI) — 7 checks, `run_all()`, `run_preflight()` |
| `bristlenose/doctor_fixes.py` | Install-method-aware fix instructions (`detect_install_method()`, `get_fix()`) |
| `.github/workflows/ci.yml` | CI: ruff, mypy, pytest on push/PR; also called by release.yml via workflow_call |
| `.github/workflows/release.yml` | Release pipeline: build → PyPI → GitHub Release → Homebrew dispatch |
| `.github/workflows/snap.yml` | Snap build & publish: edge on push to main, stable on v* tags |
| `.github/workflows/homebrew-tap/update-formula.yml` | Reference copy of the tap repo's workflow (authoritative copy is in homebrew-bristlenose) |
| `snap/snapcraft.yaml` | Snap recipe: classic confinement, core24, Python plugin, bundles FFmpeg + spaCy |
| `CONTRIBUTING.md` | CLA, code style, design system docs, full release process and cross-repo topology |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap repo:** https://github.com/cassiocassio/homebrew-bristlenose
- **CI runs:** https://github.com/cassiocassio/bristlenose/actions
- **Tap workflow runs:** https://github.com/cassiocassio/homebrew-bristlenose/actions
- **PyPI trusted publisher settings:** https://pypi.org/manage/project/bristlenose/settings/publishing/
- **Repo secrets:** https://github.com/cassiocassio/bristlenose/settings/secrets/actions

---

## Implementation notes: Name extraction and editable names (done)

Implemented as an extension to the existing Stage 5b speaker identification — no new pipeline stage, no new config flag.

### How it works

1. **LLM extraction**: Stage 5b prompt asks for `person_name` and `job_title` alongside role assignment. `SpeakerRoleItem` (structured output model) has both fields defaulting to `""`. `identify_speaker_roles_llm()` returns `list[SpeakerInfo]` with extracted data
2. **Metadata harvesting**: `extract_names_from_labels()` in `people.py` checks `speaker_label` metadata for real names (Teams/DOCX/VTT sources often have them). Skips generic labels ("Speaker A", "SPEAKER_00", "Unknown") via `_GENERIC_LABEL_RE`
3. **Auto-populate**: `auto_populate_names()` fills empty `full_name` (LLM > metadata) and empty `role` (LLM only). Never overwrites human edits
4. **Short name**: `suggest_short_names()` takes first token of `full_name`, disambiguates collisions ("Sarah J." vs "Sarah K.")
5. **Browser editing**: `names.js` — pencil icon inline editing, localStorage persistence, YAML clipboard export, reconciliation with baked-in `BN_PARTICIPANTS` data
6. **Data flow**: pipeline → auto-populate → write people.yaml → bake into HTML → browser edits → export YAML → paste into people.yaml → re-render → reconcile

### Key decisions

- **Extends Stage 5b** (no extra LLM call) — name extraction piggybacks on the speaker identification prompt
- **Always on** — no opt-in flag; the LLM is already being called for role assignment
- **localStorage only** — static HTML can't write files; YAML clipboard export bridges the gap
- **Human edits always win** — `auto_populate_names()` only fills empty fields

---

## Design notes: Moderator identification and transcript page speaker styling

Transcript pages currently show every segment as the same speaker (`p1:`) because the `.txt` files store `[p1]` for all segments — the researcher/participant role distinction is lost when writing to disk. This needs to change before multi-speaker transcripts can render properly.

### The problem

In a real user research interview there are (at least) two speakers: a **moderator** (the researcher asking questions) and a **participant** (the user being interviewed). Currently:

- Speaker diarisation labels everyone as participants (`p1`, `p2`...)
- The `SpeakerRole` enum exists in models (`PARTICIPANT` / `RESEARCHER`) and is used during the pipeline
- But when transcripts are written to `.txt` files, only the participant code `[p1]` is stored — the role is discarded
- When transcript pages load from disk, all segments look the same

### What needs to happen

#### 1. Moderator identity in `people.yaml`

Moderators need entries in `people.yaml` with a distinct code scheme. Options to decide:

- **`m1`, `m2`** — clear prefix distinction from `p1`, `p2`
- **`moderator`** — single code if there's always one researcher (but some studies have two)
- **`r1`, `r2`** — "researcher" prefix

The `PersonEditable` model already has `full_name`, `short_name`, `role` — moderators would use the same fields. The `role` field could default to "Moderator" for these entries.

#### 2. Role preserved in `.txt` files

The canonical `.txt` format needs to encode who is the moderator vs participant. Options:

- **Extend the `[p1]` code** — use `[m1]` for moderator segments: `[00:16] [m1] So tell me about your experience...`
- **Add a role marker** — `[00:16] [p1:researcher] ...` (more explicit but noisier)
- Simplest: just use the `m1`/`m2` prefix convention — the parser already reads the code between `[]`, and anything not starting with `p` would be a non-participant

#### 3. Transcript page visual treatment

The moderator's questions should be visually distinct — they're context, not evidence. Design direction from user research practice:

- **Moderator lines are structural headers** — a good moderator speaks ~20% of the time, so their questions naturally break the participant's responses into chunks
- **Heavier/darker styling for moderator** — bold or semi-bold, slightly larger, acting as section breaks
- **Participant text flows beneath** — lighter weight, the "body text" of each Q&A block
- Think of it as a **Q&A layout**: moderator question as a bold heading, followed by the participant's response paragraphs

This is the opposite of what you might expect (usually the important content is bold) — but in research the moderator's words are scaffolding and the participant's words are the data. The moderator lines stand out as **structural markers** that help you navigate, while the participant's words are what you actually read.

#### 4. CSS classes needed

```css
.segment-moderator { font-weight: 600; /* or 700 */ }
.segment-participant { /* default weight, the readable body */ }
```

Possibly with spacing: more margin-top before a moderator segment to create visual "question blocks".

### Blockers

- **No multi-speaker test data** — current test recordings are single-person. Need a real two-person interview (moderator + participant) flowing through the full pipeline before we can validate the design
- **Speaker diarisation → role assignment** — the pipeline currently assigns `PARTICIPANT` / `RESEARCHER` roles during stage 5 (identify speakers), but this distinction doesn't survive to disk. Need to verify the role assignment logic works correctly before persisting it
- **Parser changes** — `load_transcripts_from_dir()` needs to handle moderator codes (`m1` etc.) and return the role information so the transcript page renderer can apply different CSS classes

### Dependencies

- Depends on having real multi-speaker test data
- Related to "Multi-participant sessions" TODO item
- Related to "Speaker diarisation improvements" TODO item
- LLM name extraction could auto-populate moderator names too
