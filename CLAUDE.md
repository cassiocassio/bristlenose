# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Anthropic or OpenAI APIs.

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

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls).

LLM provider: API keys via env vars (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), `.env` file, or `bristlenose.toml`. Prefix with `BRISTLENOSE_` for namespaced variants.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`

## People file (participant registry)

`people.yaml` lives in the output directory. It tracks every participant across pipeline runs.

- **Models**: `PersonComputed` (refreshed each run) + `PersonEditable` (preserved across runs) → `PersonEntry` → `PeopleFile` — all in `bristlenose/models.py`
- **Core logic**: `bristlenose/people.py` — load, compute, merge, write, build display name map
- **Merge strategy**: computed fields always overwritten; editable fields always preserved; new participants added with empty defaults; old participants missing from current run are **kept** (not deleted)
- **Display names**: `short_name` → used as display name in quotes/friction/journeys. `full_name` → used in participant table Name column. Resolved at render time only — canonical `participant_id` (p1, p2) stays in all data models and HTML `data-participant` attributes. Display names are cosmetic
- **Participant table columns**: `ID | Name | Role | Start | Duration | Words | Source file`. ID shows raw `participant_id`. Name shows `full_name` (pale-grey italic "Unnamed" placeholder when empty). Start uses macOS Finder-style relative dates via `format_finder_date()` in `utils/markdown.py`
- **Pipeline wiring**: `run()` and `run_transcription_only()` compute+write; `run_analysis_only()` and `run_render_only()` load existing for display names only
- **Key workflow**: user edits `short_name` / `full_name` in `people.yaml` → `bristlenose render` → report uses new names
- **YAML comments**: inline comments added by users are lost on re-write (PyYAML limitation, documented in file header)
- **Future**: editable participant names in HTML report; web UI for editing people; LLM-based auto name/role extraction (see TODO.md)

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

## Gotchas

- The repo directory is `/Users/cassio/Code/gourani` (legacy name, package is bristlenose)
- Both `models.py` and `utils/timecodes.py` define `format_timecode()` / `parse_timecode()` — they behave identically, stage files import from either
- `PipelineResult` references `PeopleFile` but is defined before it in `models.py` — resolved with `PipelineResult.model_rebuild()` after PeopleFile definition
- `format_finder_date()` in `utils/markdown.py` uses a local `import datetime as _dtmod` inside the function body because `from __future__ import annotations` makes the type hints string-only; `datetime` is in `TYPE_CHECKING` for the linter but not available at runtime otherwise
- `render --clean` is accepted but ignored — render is always non-destructive (overwrites HTML/markdown reports only, never touches people.yaml, transcripts, or intermediate JSON)
- `load_transcripts_from_dir()` in `pipeline.py` is a public function (no underscore) — used both internally by the pipeline and by `render_html.py` for transcript pages
- For transcript/timecode gotchas, see `bristlenose/stages/CLAUDE.md`

## Reference docs (read when working in these areas)

- **Theme / dark mode / CSS**: `bristlenose/theme/CLAUDE.md`
- **Pipeline stages / transcript format / output structure**: `bristlenose/stages/CLAUDE.md`
- **File map** (what lives where): `docs/file-map.md`
- **Release process / CI / secrets**: `docs/release.md`
- **Design system / contributing**: `CONTRIBUTING.md`

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

## Current status (v0.5.0, Feb 2026)

Core pipeline complete and published to PyPI + Homebrew. v0.5.0 adds per-participant transcript pages with deep-link anchors from quote attributions. v0.4.1 added people file (participant registry with display names), flipped PII redaction to off-by-default, and redesigned participant table with Finder-style dates. See `TODO.md` for full task list.
