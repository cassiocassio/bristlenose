# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Claude (Anthropic) or ChatGPT (OpenAI) APIs.

## Commands

- `.venv/bin/python -m pytest tests/` — run tests
- `.venv/bin/ruff check bristlenose/` — lint (no global ruff install)
- `.venv/bin/ruff check --fix bristlenose/` — lint and auto-fix
- `.venv/bin/mypy bristlenose/` — type check (informational, not a hard gate)

## Key conventions

- **Python 3.10+**, strict mypy, Ruff linting (line-length 100, rules: E/F/I/N/W/UP, E501 ignored)
- **Type hints everywhere** — Pydantic models for all data structures
- **Single source of version**: `bristlenose/__init__.py` (`__version__`). Never add version to `pyproject.toml`
- **Markdown style template** in `bristlenose/utils/markdown.py` — single source of truth for all markdown/txt formatting. Change formatting here, not in stage files
- **Atomic CSS design system** in `bristlenose/theme/` — tokens, atoms, molecules, organisms, templates (see `bristlenose/theme/CLAUDE.md`)
- **Licence**: AGPL-3.0 with CLA
- **Provider naming**: user-facing text says "Claude" and "ChatGPT" (product names), not "Anthropic" and "OpenAI" (company names). Researchers know the products, not the companies. Internal code uses `"anthropic"` / `"openai"` as config values — that's fine, only human-readable strings need product names

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls), `doctor` (dependency health checks).

LLM provider: API keys via env vars (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), `.env` file, or `bristlenose.toml`. Prefix with `BRISTLENOSE_` for namespaced variants.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`

## People file (participant registry)

`people.yaml` lives in the output directory. It tracks every participant across pipeline runs.

- **Models**: `PersonComputed` (refreshed each run) + `PersonEditable` (preserved across runs) → `PersonEntry` → `PeopleFile` — all in `bristlenose/models.py`
- **Core logic**: `bristlenose/people.py` — load, compute, merge, write, build display name map, extract names from labels, auto-populate names, suggest short names
- **Merge strategy**: computed fields always overwritten; editable fields always preserved; new participants added with empty defaults; old participants missing from current run are **kept** (not deleted)
- **Display names**: `short_name` → used as display name in quotes/friction/journeys. `full_name` → used in participant table Name column. Resolved at render time only — canonical `participant_id` (p1, p2) stays in all data models and HTML `data-participant` attributes. Display names are cosmetic
- **Participant table columns**: `ID | Name | Role | Start | Duration | Words | Source file`. ID shows raw `participant_id`. Name column has pencil icon for inline editing (see "Name editing in HTML report" below). Start uses macOS Finder-style relative dates via `format_finder_date()` in `utils/markdown.py`
- **Pipeline wiring**: `run()` and `run_transcription_only()` compute+write+auto-populate; `run_analysis_only()` and `run_render_only()` load existing for display names only
- **Key workflows**:
  - User edits `short_name` / `full_name` in `people.yaml` → `bristlenose render` → report uses new names
  - User edits name in HTML report → localStorage → "Export names" → paste YAML into `people.yaml` → `bristlenose render`
  - Full pipeline run auto-extracts names from LLM + speaker label metadata → auto-populates empty fields
- **YAML comments**: inline comments added by users are lost on re-write (PyYAML limitation, documented in file header)

### Auto name/role extraction

Stage 5b (speaker identification) extracts participant names and job titles alongside role classification — no extra LLM call.

- **LLM extraction**: `SpeakerRoleItem` in `bristlenose/llm/structured.py` has optional `person_name` and `job_title` fields (default `""`). The Stage 5b prompt in `prompts.py` asks the LLM to extract these from self-introductions. `identify_speaker_roles_llm()` in `identify_speakers.py` returns `list[SpeakerInfo]` (dataclass: `speaker_label`, `role`, `person_name`, `job_title`)
- **Metadata extraction**: `extract_names_from_labels()` in `people.py` harvests real names from `speaker_label` on `TranscriptSegment` — works for Teams/DOCX/VTT sources where labels are real names (e.g. "Sarah Jones"), skips generic labels ("Speaker A", "SPEAKER_00", "Unknown")
- **Auto-populate**: `auto_populate_names()` fills empty `full_name` (LLM > label metadata) and `role` (LLM only). Never overwrites user edits
- **Short name suggestion**: `suggest_short_names()` auto-fills `short_name` from first token of `full_name`. Disambiguates collisions: "Sarah J." vs "Sarah K." when two participants share a first name
- **Pipeline wiring**: `run()` collects `SpeakerInfo` from Stage 5b → calls `extract_names_from_labels()` + `auto_populate_names()` + `suggest_short_names()` after `merge_people()` and before `write_people_file()`. `run_transcription_only()` uses label extraction only (no LLM)

### Name editing in HTML report

Participant names and roles are editable inline in the HTML report.

- **Pencil icon**: `.name-pencil` button in Name and Role table cells, visible on row hover. Same contenteditable lifecycle as quote editing (Enter/Escape/click-outside)
- **JS module**: `bristlenose/theme/js/names.js` — `initNames()` in boot sequence (after `initCsvExport()`). Uses `createStore('bristlenose-names')` for localStorage. Shape: `{pid: {full_name, short_name, role}}`
- **Live DOM updates**: `updateAllReferences(pid)` propagates name changes to quote attributions (`.speaker-link`), participant table cells, etc.
- **Short name auto-suggest**: JS-side `suggestShortName()` mirrors the Python heuristic — when `full_name` is edited and `short_name` is empty, auto-fills with first name
- **YAML export**: "Export names" toolbar button copies edited names as a YAML snippet via `buildNamesYaml()` + `copyToClipboard()`. User pastes into `people.yaml`
- **Reconciliation**: `reconcileWithBaked()` on page load prunes localStorage entries that match the baked-in `BN_PARTICIPANTS` data (user already pasted edits and re-rendered)
- **BN_PARTICIPANTS**: JSON blob emitted in the HTML `<script>` block containing `{pid: {full_name, short_name, role}}` from people.yaml at render time. Used by JS for reconciliation and display name resolution
- **CSS**: `molecules/name-edit.css` — `.name-cell`, `.role-cell` positioning; `.name-pencil` hover reveal; `.unnamed` placeholder style; `.edited` indicator; print hidden

## Editable section/theme headings

Section titles, section descriptions, theme titles, and theme descriptions are editable inline in the HTML report — same UX as quote editing.

- **Markup**: `<span class="editable-text" data-edit-key="{anchor}:title|desc" data-original="...">` wraps the text inside `<h3>` (titles) and `<p class="description">` (descriptions). Pencil button (`.edit-pencil-inline`) sits inline after the text
- **ToC entries**: Section and theme titles in the Table of Contents are also editable (same `data-edit-key`). Sentiment and Friction points are NOT editable
- **Bidirectional sync**: Editing a title in the ToC updates the heading, and vice versa. Uses `_syncSiblings()` — all `.editable-text` spans sharing the same `data-edit-key` are kept in sync
- **Storage**: Reuses the same `bristlenose-edits` localStorage store as quote edits. Keys: `section-{slug}:title`, `section-{slug}:desc`, `theme-{slug}:title`, `theme-{slug}:desc`
- **JS**: `initInlineEditing()` in `editing.js`, called from `main.js` boot sequence after `initEditing()`. Separate `activeInlineEdit` tracker from `activeEdit` (quote editing)
- **CSS**: `.edit-pencil-inline` in `atoms/button.css` (static inline positioning); `.editable-text.editing` and `.editable-text.edited` in `molecules/quote-actions.css`
- **Tests**: `tests/test_editable_headings.py` — 19 tests covering markup, data attributes, CSS, JS bootstrap, ToC editability, and sentiment exclusion

## Report header and toolbar

The HTML report header uses a two-column flexbox layout with the logo, logotype, and project name on the left, and the document title and metadata on the right.

- **Header structure**: `.report-header` flex container → `.header-left` (logo + logotype + project name) + `.header-right` (doc title + meta line)
- **Logo**: fish image flipped horizontally (`transform: scaleX(-1)`) so it faces into the page from the right. 80px wide, positioned with `top: 1.7rem` to align nose near the text baseline. Dark mode uses `<picture>` with separate dark logo
- **Logotype**: "Bristlenose" (capitalised) in semibold 1.35rem, followed by an em-space (`\u2003`), then project name in regular weight at same size
- **Meta line**: session/participant count and Finder-style date in muted 0.82rem
- **Spacing**: `.report-header + hr` has tightened margins (0.75rem top/bottom); toolbar has negative top margin (-0.5rem) to pull it closer to the rule
- **CSS**: `atoms/logo.css` — header layout, logotype, project name, doc title, meta, print overrides
- **Shared layout**: both report and transcript pages use the same header structure (logotype + project name). The transcript page additionally has a back-link nav and `<h1>` heading below

### Sticky toolbar

Below the header rule, a sticky toolbar holds the view-switcher dropdown and export buttons.

- **CSS**: `organisms/toolbar.css` — `.toolbar` (sticky, flex, right-aligned), `.view-switcher-btn`, `.view-switcher-arrow` (SVG chevron), `.view-switcher-menu` (dropdown), `.menu-icon` (invisible spacers for alignment)
- **View switcher**: borderless dropdown button showing current view ("All quotes" default). Three views: `all` (show everything), `favourites` (show only starred quotes), `participants` (show only participant table)
- **JS**: `view-switcher.js` — `initViewSwitcher()` handles menu toggle, item selection, section visibility. Sets `currentViewMode` global (defined in `csv-export.js`) so the CSV export button adapts
- **Export buttons**: single `#export-csv` button (Copy CSV) with inline SVG clipboard icon; `#export-names` button (Export names) shown only in participants view. Both swap visibility based on view mode
- **Menu items**: "All quotes" (no icon), "★ Favourite quotes" (star icon), "⊞ Participant data" (grid icon). Items without icons get `<span class="menu-icon">&nbsp;</span>` spacers for text alignment
- **Boot order**: `initViewSwitcher()` runs after `initCsvExport()` in `main.js` because it depends on `currentViewMode`

### Table of Contents

The ToC row (`.toc-row` flexbox) shows up to three navigation columns:

- **Sections** — screen-specific findings (editable titles with pencil icons)
- **Themes** — thematic clusters (editable titles with pencil icons)
- **Analysis** — Sentiment, Tags, Friction points, User journeys (not editable, plain links)

## Quote attribution and anonymisation boundary

Quote attributions in the main report intentionally show **raw participant IDs** (`— p1`, `— p2`) instead of display names. This is the anonymisation boundary: when researchers copy quotes to external tools (Miro, presentations, etc.), the IDs protect participant identity.

- **Report quotes**: `_format_quote_html()` uses `pid_esc` for the `.speaker-link` text. `names.js` `updateAllReferences()` does NOT update `.speaker-link` text
- **Transcript pages**: use display names (`short_name` → `full_name` → `pid`) since these are private to the researcher
- **Participant table**: Name column shows `full_name` (editable); ID column shows raw `p1`/`p2` as a link to the transcript page

## PII redaction

PII redaction is **off by default** (transcripts retain PII). Opt in with `--redact-pii`.

- **Config**: `pii_enabled: bool = False` in `bristlenose/config.py`
- **CLI flags**: `--redact-pii` (opt in) / `--retain-pii` (explicit default, redundant). Mutually exclusive
- When off: transcripts pass through as `PiiCleanTranscript` wrappers, no `cooked_transcripts/` directory written

## Per-participant transcript pages

Each participant gets a dedicated HTML page (`transcript_p1.html`, etc.) showing their full transcript with clickable timecodes. Generated at the end of `render_html()`.

- **Data source**: prefers `cooked_transcripts/` (PII-redacted) over `raw_transcripts/`. Uses `load_transcripts_from_dir()` from `pipeline.py` (public function, formerly `_load_transcripts_from_dir`)
- **Page heading**: `{pid} {full_name}` (e.g. "p1 Sarah Jones") or just `{pid}` if no name
- **Speaker name per segment**: resolved as `short_name` → `full_name` → `pid` via `_resolve_speaker_name()` in `render_html.py`
- **Back button**: `← {project_name} Research Report` linking to `research_report.html`, styled muted with accent on hover, hidden in print
- **JS**: only `storage.js` + `player.js` + `initPlayer()` — no favourites/editing/tags modules
- **Participant table linking**: ID column (`p1`, `p2`) is a hyperlink to the transcript page
- **Quote attribution linking**: `— p1` at end of each quote in the main report links to `transcript_p1.html#t-{seconds}`, deep-linking to the exact segment. `.speaker-link` CSS in `blockquote.css` (inherits muted colour, accent on hover)
- **Segment anchors**: each transcript segment has `id="t-{int(seconds)}"` for deep linking from quotes
- **CSS**: `transcript.css` in theme templates (back button, segment layout, meta styling); `.speaker-link` in `organisms/blockquote.css`
- **Speaker role caveat**: `.txt` files store `[p1]` for all segments — researcher/participant role not preserved on disk. All segments render with same styling

## Doctor command (dependency health checks)

`bristlenose doctor` checks the runtime environment and gives install-method-aware fix instructions.

- **Pure check logic**: `bristlenose/doctor.py` — `CheckResult`, `CheckStatus` (OK/WARN/FAIL/SKIP), `DoctorReport`, 7 check functions, `run_all()`, `run_preflight()`
- **Fix instructions**: `bristlenose/doctor_fixes.py` — `detect_install_method()` (snap/brew/pip), `get_fix(fix_key, install_method)`, 12 fix functions in `_FIX_TABLE`
- **CLI wiring**: `cli.py` — `doctor` command, `_maybe_auto_doctor()`, `_run_preflight()`, sentinel logic
- **Seven checks**: FFmpeg, transcription backend, Whisper model cache, API key (with validation), network, PII deps, disk space
- **Command-to-check matrix**: `_COMMAND_CHECKS` dict in `doctor.py` — different commands need different checks. `render` has no pre-flight at all
- **Three invocation modes**: (1) explicit `bristlenose doctor` — full report, always runs; (2) first-run auto-doctor — triggers when sentinel missing or version mismatch; (3) pre-flight — terse single-failure output on every `run`/`transcribe-only`/`analyze`
- **Sentinel file**: `~/.config/bristlenose/.doctor-ran` (or `$SNAP_USER_COMMON/.doctor-ran` in snap). Contains version string. Written on successful doctor or auto-doctor
- **API key validation**: `_validate_anthropic_key()` and `_validate_openai_key()` make cheap HTTP calls; return `(True, "")`, `(False, error)`, or `(None, error)` for network issues
- **Install method detection**: snap (`$SNAP` env var) > brew (`/opt/homebrew/` or `/usr/local/Cellar/` in `sys.executable`) > pip (default). Linuxbrew (`/home/linuxbrew/`) is NOT detected as brew — falls through to pip (gives correct instructions)
- **Rich formatting**: `ok` = dim green, `!!` = bold yellow, `--` = dim grey. Feels like `git status`
- **Design doc**: `docs/design-doctor-and-snap.md`

## Snap packaging

`snap/snapcraft.yaml` builds a classic-confinement snap for Linux. `.github/workflows/snap.yml` builds on CI and publishes to the Snap Store.

- **Recipe**: `snap/snapcraft.yaml` — core24 base, Python plugin, bundles FFmpeg + spaCy model + all Python deps
- **CI**: `.github/workflows/snap.yml` — edge on push to main, stable on v* tags, build-only on PRs
- **Version**: uses `adopt-info` + `craftctl set version=...` to read from `bristlenose/__init__.py` at build time — no manual version in snapcraft.yaml
- **Python path wiring**: the snap must set `PATH`, `PYTHONPATH`, and `PYTHONHOME` in the app environment block. Without all three, the pip-generated shim script finds the system Python instead of the snap's bundled Python and crashes with `ModuleNotFoundError`. This is the #1 gotcha
- **Snap size**: ~307 MB (larger than estimated 130-160 MB due to FFmpeg's full dependency tree). Normal for the Store
- **Local testing**: requires Multipass 1.16.1+ on macOS (older versions have broken VM boot on Apple Silicon). Use `multipass launch lts` (not `noble`). Build with `sudo snapcraft --destructive-mode` inside the VM. Install with `sudo snap install --dangerous --classic ./bristlenose_*.snap`
- **Architecture**: CI builds amd64. Local Multipass on Apple Silicon builds arm64. Cross-compilation not possible for Python wheels with native C extensions
- **Install method detection**: `$SNAP` env var is set inside the snap runtime → `detect_install_method()` in `doctor_fixes.py` returns `"snap"`
- **Pre-launch steps** (manual, one-off): register snap name, request classic confinement approval at forum.snapcraft.io, export store credentials, add `SNAPCRAFT_STORE_CREDENTIALS` to GitHub secrets
- **Design doc**: `docs/design-doctor-and-snap.md` — full implementation notes, gotchas, local build workflow
- **Release process**: `docs/release.md` — snap section covers channels, manual operations, first-time setup

## LLM concurrency

Per-participant LLM calls (stages 5b, 8, 9) run concurrently, bounded by `llm_concurrency` (default 3). Stages 10 + 11 also run concurrently with each other (single call each, independent inputs).

- **Config**: `llm_concurrency: int = 3` in `bristlenose/config.py`. Controls max concurrent API calls via `asyncio.Semaphore`
- **Pattern**: each parallelised stage uses `asyncio.Semaphore(concurrency)` + `asyncio.gather()`. The semaphore is created per stage call, not shared across stages (stages still run sequentially relative to each other)
- **Stage 5b** (pipeline.py): heuristic pass runs synchronously for all participants first, then LLM refinement runs concurrently. Results collected as `dict[str, list]` via gather + dict conversion
- **Stage 8** (topic_segmentation.py): `segment_topics()` accepts `concurrency` kwarg. Inner `_process()` closure wraps `_segment_single()` with semaphore. `asyncio.gather()` preserves input order
- **Stage 9** (quote_extraction.py): `extract_quotes()` accepts `concurrency` kwarg. Same pattern. Results flattened from `list[list[ExtractedQuote]]` to `list[ExtractedQuote]` in input order
- **Stages 10+11** (pipeline.py): `cluster_by_screen()` and `group_by_theme()` run via `asyncio.gather()` — no semaphore needed (only 2 calls). Applied in both `run()` and `run_analysis_only()`
- **Safety**: all per-participant calls are fully independent (no shared mutable state). `LLMClient` is safe to share — stateless across calls except for cached httpx client. asyncio's single-threaded model prevents lazy-init races
- **Error handling**: preserved from sequential version. Failed participants get empty results (empty `SessionTopicMap`, empty quote list). Exceptions logged, pipeline continues
- **Ordering**: `asyncio.gather()` returns results in input order — quote ordering by participant is preserved
- **Dependency chain**: stage 8 must complete before stage 9 (topic maps feed quote extraction). Stages 10+11 depend on stage 9 output. Concurrency is within-stage only, not cross-stage

## Gotchas

- The repo directory is `/Users/cassio/Code/gourani` (legacy name, package is bristlenose)
- Both `models.py` and `utils/timecodes.py` define `format_timecode()` / `parse_timecode()` — they behave identically, stage files import from either
- `PipelineResult` references `PeopleFile` but is defined before it in `models.py` — resolved with `PipelineResult.model_rebuild()` after PeopleFile definition
- `format_finder_date()` in `utils/markdown.py` uses a local `import datetime as _dtmod` inside the function body because `from __future__ import annotations` makes the type hints string-only; `datetime` is in `TYPE_CHECKING` for the linter but not available at runtime otherwise
- `render --clean` is accepted but ignored — render is always non-destructive (overwrites HTML/markdown reports only, never touches people.yaml, transcripts, or intermediate JSON)
- `load_transcripts_from_dir()` in `pipeline.py` is a public function (no underscore) — used both internally by the pipeline and by `render_html.py` for transcript pages
- For transcript/timecode gotchas, see `bristlenose/stages/CLAUDE.md`
- `doctor.py` imports `platform` and `urllib` locally inside function bodies (not at module level). When testing, patch at stdlib level (`patch("platform.system")`) not module level (`patch("bristlenose.doctor.platform.system")`)
- `check_backend()` catches `Exception` (not just `ImportError`) for faster_whisper import — torch native libs can raise `OSError` on some machines
- `people.py` imports `SpeakerInfo` from `identify_speakers.py` under `TYPE_CHECKING` only (avoids circular import at runtime). The `auto_populate_names()` type hint works because `from __future__ import annotations` makes all annotations strings
- `identify_speaker_roles_llm()` changed return type from `list[TranscriptSegment]` to `list[SpeakerInfo]` — still mutates segments in place for role assignment, but now also returns extracted name/title data. Only one call site in `pipeline.py`
- `view-switcher.js` and `names.js` both load **after** `csv-export.js` in `_JS_FILES` — `view-switcher.js` writes the `currentViewMode` global defined in `csv-export.js`; `names.js` depends on `copyToClipboard()` and `showToast()`

## Reference docs (read when working in these areas)

- **Theme / dark mode / CSS**: `bristlenose/theme/CLAUDE.md`
- **Pipeline stages / transcript format / output structure**: `bristlenose/stages/CLAUDE.md`
- **File map** (what lives where): `docs/file-map.md`
- **Release process / CI / secrets**: `docs/release.md`
- **Design system / contributing**: `CONTRIBUTING.md`
- **Doctor command + Snap packaging design**: `docs/design-doctor-and-snap.md`

## Working preferences

- Keep changes minimal and focused — don't refactor or add features beyond what's asked
- Commit messages: short, descriptive, lowercase (e.g., "fix tag suggest offering tags the quote already has")

## Before committing

1. `.venv/bin/python -m pytest tests/` — all pass
2. `.venv/bin/ruff check bristlenose/` — no lint errors

## Session-end housekeeping

When the user signals end of session, **proactively offer to run this checklist**:

1. **Run tests** — `.venv/bin/python -m pytest tests/`
2. **Run linter** — `.venv/bin/ruff check bristlenose/`
3. **Update `TODO.md`** — mark completed items, add new items discovered
4. **Update CLAUDE.md files** — persist new conventions, architectural decisions, or gotchas learned during the session (root CLAUDE.md or the appropriate child file: `bristlenose/theme/CLAUDE.md`, `bristlenose/stages/CLAUDE.md`); update version in "Current status" if bumped
5. **Update `CONTRIBUTING.md`** — if design system, release process, or dev setup changed
6. **Update `README.md`** — if version bump, add changelog entry
7. **Check for uncommitted changes** — `git status` + `git diff` — commit everything, push to `origin/main`
8. **Clean up branches** — delete merged feature branches
9. **Verify CI** — check latest push passes CI

## Current status (v0.6.4, Feb 2026)

Core pipeline complete and published to PyPI + Homebrew. Snap packaging implemented and tested locally (arm64); CI builds amd64 on every push. v0.6.4 adds concurrent per-participant LLM calls (stages 5b, 8, 9 bounded by `llm_concurrency`, stages 10+11 run in parallel), measured ~2.7x speedup on LLM-bound time. v0.6.3 redesigns the report header (logo top-left, "Bristlenose" logotype + project name, right-aligned doc title + meta), adds a view-switcher dropdown (All quotes / Favourite quotes / Participant data) with Copy CSV button in a sticky toolbar, moves Sentiment/Tags/Friction/User journeys into an "Analysis" ToC column, and uses raw participant IDs in quote attributions (anonymisation boundary). v0.6.2 adds editable participant names, auto name/role extraction, short name suggestions, and editable section/theme headings. v0.6.1 adds snap recipe, CI workflow, author identity. v0.6.0 added `bristlenose doctor`. v0.5.0 added per-participant transcript pages. Next up: register snap name, request classic confinement approval, first edge channel publish. See `TODO.md` for full task list.
