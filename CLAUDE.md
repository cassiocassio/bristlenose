# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Claude (Anthropic), ChatGPT (OpenAI), Azure OpenAI (enterprise), Gemini (Google), or local models via Ollama (free, no account required).

## Commands

- `.venv/bin/python -m pytest tests/` — run tests
- `.venv/bin/ruff check bristlenose/` — lint (no global ruff install)
- `.venv/bin/ruff check --fix bristlenose/` — lint and auto-fix
- `.venv/bin/mypy bristlenose/` — type check (informational, not a hard gate)

## Key conventions

- **Python 3.10+**, strict mypy, Ruff linting (line-length 100, rules: E/F/I/N/W/UP, E501 ignored)
- **Type hints everywhere** — Pydantic models for all data structures
- **Single source of version**: `bristlenose/__init__.py` (`__version__`). Never add version to `pyproject.toml`. Use `./scripts/bump-version.py` to bump (updates `__init__.py`, man page, creates git tag)
- **Markdown style template** in `bristlenose/utils/markdown.py` — single source of truth for all markdown/txt formatting. Change formatting here, not in stage files
- **Atomic CSS design system** in `bristlenose/theme/` — tokens, atoms, molecules, organisms, templates (see `bristlenose/theme/CLAUDE.md`)
- **Licence**: AGPL-3.0 with CLA
- **Provider naming**: user-facing text says "Claude", "ChatGPT", and "Azure OpenAI" (product names), not "Anthropic" and "OpenAI" (company names). Researchers know the products, not the companies. Internal code uses `"anthropic"` / `"openai"` / `"azure"` as config values — that's fine, only human-readable strings need product names
- **Changelog version/date format**: `**X.Y.Z** — _D Mon YYYY_` (e.g. `**0.8.1** — _7 Feb 2026_`). Bold version, em dash, italic date. No hyphens in dates, no leading zero on day. Used in both `CHANGELOG.md` and the changelog section of `README.md`

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls), `doctor` (dependency health checks). **Default command**: `bristlenose <folder>` is shorthand for `bristlenose run <folder>` — if the first argument is an existing directory (not a known command), `run` is injected automatically.

LLM providers: Claude, ChatGPT, Azure OpenAI, Gemini, Local (Ollama). See `bristlenose/llm/CLAUDE.md` for credentials, config, and provider details.

Quote exclusivity: **every quote appears in exactly one report section.** See `bristlenose/stages/CLAUDE.md` for the three-level enforcement design (quote type separation → within-cluster → within-theme). This matches researcher expectations — each quote appears once, suitable for handoff to non-researchers.

Analysis page: `bristlenose/analysis/` computes signal concentration metrics from grouped quotes — no LLM calls, pure math. `_compute_analysis()` in `pipeline.py` is the glue (lazy import, called from all three pipeline methods). Renderer produces standalone `analysis.html` with JSON data injected into an IIFE. Client-side JS (`analysis.js`) builds signal cards and heatmaps. Confidence thresholds use strict `>` (not `>=`): strong requires conc > 2, moderate requires conc > 1.5. Cell keys use `"label|sentiment"` format — pipe characters in labels would create ambiguous keys (documented, not currently guarded). 97 tests across 4 files cover metrics, matrix building, signal detection, serialization, and HTML rendering end-to-end.

LLM prompts: All prompt templates live in `bristlenose/llm/prompts.py`. When iterating on prompts, archive the old version to `bristlenose/llm/prompts-archive/` with naming convention `prompts_YYYY-MM-DD_description.py` (e.g., `prompts_2026-02-04_original-14-tags.py`). This folder is ignored by the application but tracked in git for easy comparison without digging through commit history. Future goal: allow users to customise prompts via config.

Report JavaScript — 17 modules in `bristlenose/theme/js/`, concatenated in dependency order into a single `<script>` block by `render_html.py` (`_JS_FILES`). Transcript pages and codebook page use separate JS lists. See `bristlenose/theme/js/MODULES.md` for per-module API docs.

## Output directory structure

Output goes **inside the input folder** by default: `bristlenose run interviews/` creates `interviews/bristlenose-output/`. Override with `--output`. See `bristlenose/stages/CLAUDE.md` for the full directory layout.

Key helpers: `OutputPaths` in `output_paths.py` (consistent path construction), `slugify()` in `utils/text.py` (project names in filenames — lowercase, hyphens, max 50 chars). Report filenames include project name (`bristlenose-{slug}-report.html`) so multiple reports in Downloads are distinguishable.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`
- **Design artifacts** (tracked, not shipped): `docs/mockups/`, `docs/design-system/`, `experiments/` — HTML mockups, style guides, throwaway prototypes. These are working materials for contributors, kept in the tree for backup and collaboration. Users never navigate to them. Add new mockups to `docs/mockups/`, not the repo root. **Serve mode auto-discovery**: `bristlenose serve --dev` mounts all three directories and auto-discovers `*.html` files for the Design section in the About tab (`_build_dev_section_html()` in `app.py`). New HTML files added to these directories appear automatically — no code changes needed
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`
- **Gitignored (private)**: `docs/private/`, `trial-runs/` — contain names, contacts, and value judgements not suitable for a public repo

## HTML report features

The generated HTML report has interactive features: inline editing (quotes, headings, names), search-as-you-type, view switching, CSV export, tag filter, hidden quotes, and per-participant transcript pages with deep-linked timecodes. Full implementation details in `docs/design-html-report.md`. Key concepts: people file merge strategy, speaker codes, anonymisation boundary, tag filter persistence, hidden quotes with `.bn-hidden` defence-in-depth. See `bristlenose/theme/CLAUDE.md` for CSS/design gotchas, `bristlenose/theme/js/MODULES.md` for JS module details, `bristlenose/theme/CSS-REFERENCE.md` for per-component CSS docs.

## Doctor command

`bristlenose doctor` checks the runtime environment (FFmpeg, transcription backend, API keys, network, disk space) and gives install-method-aware fix instructions. Three modes: explicit `bristlenose doctor`, first-run auto-doctor (sentinel file), and per-command pre-flight. See `docs/design-doctor-and-snap.md` for full design.

## Snap packaging and man page

Snap: `snap/snapcraft.yaml` builds classic-confinement snap for Linux. CI builds amd64; local Multipass builds arm64. See `docs/design-doctor-and-snap.md`.

Man page: canonical location `bristlenose/data/bristlenose.1`, symlinked from `man/bristlenose.1`. Self-installs on first run (pip/pipx). CI version check gates release. See `docs/release.md`.

## CLI output (Cargo/uv-style)

Pipeline output uses clean checkmark lines with per-stage timing. `console.status()` spinner during work → `_print_step()` checkmark when done. Width capped at 80. Minimal colour: green checkmarks, dim timing/header/stats. `_format_duration` and `_print_step` are module-level in `pipeline.py`. `LLMUsageTracker` in `llm/client.py` accumulates tokens; `estimate_cost()` in `llm/pricing.py` uses hardcoded pricing table. Stage failure warnings via `_print_warn()` with dedup and credit-balance URL detection.

**Time estimation** (`bristlenose/timing.py`): After ingest, the pipeline prints an upfront time estimate (`~8 min (±2 min)`) using **Welford's online algorithm** — stores running mean, variance, and count per rate-based metric (e.g. seconds per audio minute for transcription, seconds per session for LLM stages). Profiles are keyed by hardware+config combo (`"chip | backend | model | provider | llm_model"`) and persisted to `~/.config/bristlenose/timing.json`. **Progressive disclosure**: no estimate until n ≥ 4 runs (`_MIN_N_ESTIMATE`); point estimate only (no ±range) until n ≥ 8 (`_MIN_N_RANGE`), because Welford variance with few samples produces absurdly wide ranges (e.g. ±16 min on a 14 min estimate with n=2). The CLI prints the upfront estimate only — "remaining" events are emitted via `PipelineEvent` for future progress-bar UI but not printed to the terminal. `Pipeline.__init__` accepts `on_event` callback and `estimator` (both typed as `object` to avoid module-level imports). `PipelineEvent` dataclass supports future visual UI (progress bars) via `kind` field: `"estimate"`, `"remaining"`, `"stage_start"`, `"stage_complete"`, `"progress"`. 29 tests in `tests/test_timing.py`.

## Gotchas

### Ruff F401 (unused imports) — reports only, won't auto-fix

F401 is marked `unfixable` in `pyproject.toml` so `ruff check --fix` (and the PostToolUse hook) won't delete imports during incremental edits. Ruff still *reports* unused imports — remove them manually when they're genuinely unused.

### Other gotchas

- **Tests must not depend on local environment** — CI runs with no API keys, no Ollama, no local config. Functions like `_get_cloud_fallback_hint()` in `doctor_fixes.py` return different output based on configured keys. Always mock environment-dependent functions in tests. The v0.6.7–v0.6.13 release failures were caused by tests that passed locally (where API keys exist) but failed in CI
- The repo directory is `/Users/cassio/Code/bristlenose`
- Both `models.py` and `utils/timecodes.py` define `format_timecode()` / `parse_timecode()` — they behave identically, stage files import from either
- `PipelineResult` references `PeopleFile` but is defined before it in `models.py` — resolved with `PipelineResult.model_rebuild()` after PeopleFile definition
- `format_finder_date()` in `utils/markdown.py` uses a local `import datetime as _dtmod` inside the function body because `from __future__ import annotations` makes the type hints string-only; `datetime` is in `TYPE_CHECKING` for the linter but not available at runtime otherwise
- `format_finder_filename()` in `utils/markdown.py` — Finder-style middle-ellipsis filename truncation (preserves extension, 2/3 front + 1/3 back split). Used by session table Interviews column. `max_len` defaults to 24
- `render --clean` is accepted but ignored — render is always non-destructive (overwrites HTML/markdown reports only, never touches people.yaml, transcripts, or intermediate JSON)
- `load_transcripts_from_dir()` in `pipeline.py` is a public function (no underscore) — used both internally by the pipeline and by `render_html.py` for transcript pages
- For transcript/timecode gotchas, see `bristlenose/stages/CLAUDE.md`
- `doctor.py` imports `platform` and `urllib` locally inside function bodies (not at module level). When testing, patch at stdlib level (`patch("platform.system")`) not module level (`patch("bristlenose.doctor.platform.system")`)
- `check_backend()` catches `Exception` (not just `ImportError`) for faster_whisper import — torch native libs can raise `OSError` on some machines
- `people.py` imports `SpeakerInfo` from `identify_speakers.py` under `TYPE_CHECKING` only (avoids circular import at runtime). The `auto_populate_names()` type hint works because `from __future__ import annotations` makes all annotations strings
- `identify_speaker_roles_llm()` changed return type from `list[TranscriptSegment]` to `list[SpeakerInfo]` — still mutates segments in place for role assignment, but now also returns extracted name/title data. Only one call site in `pipeline.py`
- `_normalise_stem()` expects a lowercased stem — callers must `.lower()` before passing. `group_into_sessions()` does this; unit tests pass lowercased literals directly
- **Never remove a worktree from inside it.** If a shell (or Claude session) has its CWD inside a worktree directory, deleting that directory makes the shell unrecoverable — every command fails with "path does not exist." Always `cd /Users/cassio/Code/bristlenose` first, then `git worktree remove ...`. If the directory was already deleted, run `git worktree prune` from the main repo. See `docs/BRANCHES.md` for the full cleanup recipe
- **Renaming the repo directory breaks the venv.** Python editable installs (`pip install -e .`) write the absolute path into `.pth` files and CLI shim shebangs. If you `mv` the project directory, the venv silently breaks — imports may appear to work (CWD fallback on `sys.path`) but stale bytecode in `__pycache__/` will serve old code. Fix: `find . -name __pycache__ -exec rm -rf {} +` then `.venv/bin/python -m pip install -e '.[dev]'` (use `python -m pip`, not bare `pip`, because the pip shim's shebang is also broken). Alternatively, delete `.venv` and recreate
- **`Console(width=min(80, Console().width))`** — the `Console()` inside `min()` is a throwaway instance that auto-detects the real terminal width. This is the intended pattern; don't cache it
- **`_format_duration` and `_print_step` are module-level in `pipeline.py`** — `cli.py` imports `_format_duration` from there. Don't move them into the `Pipeline` class
- **`PipelineResult` has optional LLM fields** (default 0/empty string) — `run_transcription_only()` doesn't use `LLMClient` so these stay at defaults. `_print_pipeline_summary()` in `cli.py` uses `getattr()` defensively
- **Homebrew tap repo must be named `homebrew-bristlenose`** (not `bristlenose-homebrew`). `brew tap cassiocassio/bristlenose` looks for a GitHub repo called `cassiocassio/homebrew-bristlenose` — this is a Homebrew convention, not configurable. The local directory name doesn't matter to Git, but keeping it matching avoids confusion
- For speaker code conventions (`assign_speaker_codes`, moderator codes, `session_id`, transcript file naming), see `bristlenose/stages/CLAUDE.md`
- **Pipeline metadata** (`metadata.json`): `write_pipeline_metadata()` in `render_output.py` writes `{"project_name": "..."}` to the intermediate directory during `run`/`analyze`. `read_pipeline_metadata()` reads it back. The CLI `render` command uses this as the source of truth for project name, falling back to directory-name heuristics for pre-metadata output dirs only
- **`PipelineResult.report_path`**: populated by all three pipeline methods (`run`, `run_analysis_only`, `run_render_only`) from the return value of `render_html()`. `_print_pipeline_summary()` in `cli.py` uses it to print the clickable report link (shows filename only, `file://` hyperlink resolves the full path)
- **Python 3.14 + pydantic v1 crash** — `import presidio_analyzer` → spacy → pydantic v1 → `ConfigError` on Python 3.14. `check_pii` in `doctor.py` catches `Exception` (not just `ImportError`) and returns `SKIP` when `pii_enabled=False` (the default). If adding new import-guarded checks, use `except Exception` for robustness
- **`llm_max_tokens` default is 32768** — output token ceiling per LLM call. Only pay for tokens generated, not the limit. All providers detect truncation (`stop_reason`/`finish_reason`) and raise `RuntimeError` with actionable `.env` fix. Quote extraction is the most output-heavy stage. See `bristlenose/llm/CLAUDE.md` for details
- For LLM/provider gotchas (Azure, Ollama, provider registry, max_tokens), see `bristlenose/llm/CLAUDE.md`
- **`BRISTLENOSE_FAKE_THUMBNAILS=1`** env var — shows video thumbnail placeholders in the session table for all sessions (even VTT-only). Layout testing only. Defined as `_FAKE_THUMBNAILS` in `render_html.py`. The shipped version retains real `video_map` logic
- For JS/CSS/report gotchas (load order, modals, hidden quotes, toolbar), see `bristlenose/theme/CLAUDE.md`; for per-module JS docs see `bristlenose/theme/js/MODULES.md`; for per-component CSS docs see `bristlenose/theme/CSS-REFERENCE.md`
- For stage/pipeline gotchas (topic maps, transcripts, coverage), see `bristlenose/stages/CLAUDE.md`
- **Analysis module**: `bristlenose/analysis/` uses plain dataclasses (not Pydantic) — ephemeral computation, never persisted. `_compute_analysis()` in `pipeline.py` returns `object | None` (typed as `object` to avoid import at module level, lazy import inside the function). `_serialize_analysis()` in `render_html.py` uses `# type: ignore[attr-defined]` for the same reason. Cell key format `"label|sentiment"` — pipe in labels is a known limitation (documented in tests, not guarded)

## Reference docs (read when working in these areas)

- **Export and sharing**: `docs/design-export-sharing.md`
- **HTML report / people file / transcript pages**: `docs/design-html-report.md`
- **Theme / dark mode / CSS conventions / gotchas**: `bristlenose/theme/CLAUDE.md`
- **JS module API reference**: `bristlenose/theme/js/MODULES.md`
- **CSS component reference**: `bristlenose/theme/CSS-REFERENCE.md`
- **Pipeline stages / transcript format / output structure**: `bristlenose/stages/CLAUDE.md`
- **LLM providers / credentials / concurrency**: `bristlenose/llm/CLAUDE.md`
- **File map** (what lives where): `docs/file-map.md`
- **Release process / CI / secrets**: `docs/release.md`
- **Design system / contributing**: `CONTRIBUTING.md`
- **Doctor command + Snap packaging design**: `docs/design-doctor-and-snap.md`
- **Platform transcript ingestion**: `docs/design-platform-transcripts.md`
- **Transcript coverage feature**: `docs/design-transcript-coverage.md`
- **CLI improvements**: `docs/design-cli-improvements.md`
- **LLM provider roadmap**: `docs/design-llm-providers.md`
- **Reactive UI architecture / framework / migration**: `docs/design-reactive-ui.md`
- **Performance audit / optimisation decisions**: `docs/design-performance.md`
- **Research methodology** (quote selection, sentiment taxonomy, clustering/theming rationale): `docs/design-research-methodology.md` — single source of truth for analytical decisions. **Read this before changing prompts or analysis logic.**
- **Academic sources for analysis categories**: `docs/academic-sources.html` — theoretical foundations (emotion science, UX research, trust/credibility) behind quote tagging and sentiment analysis. **Update this file when investigating theories behind any Bristlenose features.**
- **Analysis page** (signal concentration, metrics, rendering): `docs/BRANCHES.md` → `analysis` section — architecture, design decisions, file list, test coverage
- **Analysis page future** (two-pane vision, grid-as-selector, user-tag grid, backlog): `docs/design-analysis-future.md`
- **Dashboard stats** (inventory of unused pipeline data, improvement priorities): `docs/design-dashboard-stats.md`
- **Installation guide**: `INSTALL.md` — detailed per-platform install instructions for non-technical users

## Working preferences

### Worktree check (do this first!)

Feature branches live in **separate git worktrees** — each is a full working copy in its own directory. This lets multiple Claude sessions work on different features simultaneously.

**Directory convention:** `/Users/cassio/Code/bristlenose_branch <name>`

| Directory | Branch | Purpose |
|-----------|--------|---------|
| `bristlenose/` | `main` | Main repo — always stays on main |
| `bristlenose_branch codebook/` | `codebook` | Codebook feature |

**At the start of every session**, check which worktree you're in and whether it's correct for the task:

```bash
pwd
git branch --show-current
cat docs/BRANCHES.md
```

If the user starts asking about a feature without specifying, **remind them to check** which worktree they want to work in. Never check out a feature branch inside the main `bristlenose/` directory — use the worktree instead. A `PreToolUse` hook in `.claude/settings.json` blocks `git checkout`/`git switch` to feature branches when CWD is the main repo.

**Skills for branch lifecycle:**
- **`/new-feature <name>`** — creates branch, worktree, venv, pushes to origin, updates `docs/BRANCHES.md`, pauses for Finder labelling
- **`/close-branch <name>`** — archives a merged branch: drops a `_Stale - Merged by Claude DD-Mon-YY.txt` marker in the worktree directory, detaches worktree from git (directory stays on disk), asks before deleting local/remote branches, updates `docs/BRANCHES.md`
- **Reverting a merge:** `git revert -m 1 <merge-commit-hash>` — creates a new commit that undoes the merge. The worktree directory is still on disk for further work

**Creating a new feature branch worktree manually** (or use `/new-feature`):
```bash
cd /Users/cassio/Code/bristlenose
git branch my-feature main
git worktree add "/Users/cassio/Code/bristlenose_branch my-feature" my-feature
```

Each worktree needs its own `.venv` to run tests. Commits are shared instantly across all worktrees.

See `docs/BRANCHES.md` for active branches, worktree paths, what files they touch, and conflict resolution strategies.

### General

- Keep changes minimal and focused — don't refactor or add features beyond what's asked
- Commit messages: short, descriptive, lowercase (e.g., "fix tag suggest offering tags the quote already has")

### Release timing (evening releases)

Releases should land on GitHub after 9pm London time on weekdays to avoid pushing version bumps during working hours. Weekends are fine any time.

**Workflow (weekdays only):**
1. Work on `main` as usual — commit everything locally
2. Don't push to `origin/main` until after 9pm
3. To see work remotely before release (CI checks, another machine): `git push origin main:wip` — the `wip` branch doesn't trigger releases
4. After 9pm: `git push origin main --tags`

**Weekends:** Push any time — no restrictions.

**Override:** Just push if something is urgent. This is a guideline, not a gate.

**Why:** Avoids notifications during client working hours; batches releases into a predictable window.

## Before committing

1. `.venv/bin/python -m pytest tests/` — all pass
2. `.venv/bin/ruff check .` — no lint errors (**note: check whole repo, not just `bristlenose/`** — CI runs `ruff check .` which includes `tests/`)

**CI parity matters.** The release workflow failed for 7 versions (v0.6.7–v0.6.13) because local checks didn't match CI:
- Local ran `ruff check bristlenose/`, CI runs `ruff check .` — test file lint errors went unnoticed
- Tests that depend on environment (API keys, installed tools) must mock those dependencies — CI has no keys configured

## Branch switching

When the user says "let's switch to branch X" or similar, **automatically run this checklist before switching**:

### Pre-switch checks (on current branch)

1. **Check for uncommitted changes** — `git status`
   - If changes exist, commit them with a descriptive message (ask user for message if unclear)
   - Never leave uncommitted work when switching branches
2. **Run tests** — `.venv/bin/python -m pytest tests/`
   - If tests fail, warn the user before proceeding
3. **Run linter** — `.venv/bin/ruff check .`
   - If lint errors, fix them or warn before proceeding

### Switch

4. **Execute the switch** — `git checkout <branch-name>`
   - If branch doesn't exist locally but exists on remote: `git checkout -b <branch-name> origin/<branch-name>`
   - If branch doesn't exist anywhere, ask user if they want to create it

### Post-switch cleanup

5. **Clear Python cache** — `find . -name __pycache__ -exec rm -rf {} +`
   - Editable installs cache imports; stale `.pyc` files cause mysterious bugs
6. **Reinstall package** — `.venv/bin/pip install -e .`
   - Shebang paths and import paths may reference old locations
7. **Report status** — `git status` + `git log --oneline -3`
   - Show user what branch they're on and recent commits

### Why this matters

Python editable installs (`pip install -e .`) write absolute paths into `.pth` files. Switching branches can leave stale bytecode that serves old code, causing:
- `ImportError` for modules that don't exist on the new branch
- Functions behaving like the old branch's version
- Mysterious test failures

The PreferencesFile incident (keyboard-navigation branch, Feb 2026) was caused by exactly this — stale imports from a feature that was stashed on another branch.

## Session-end housekeeping

When the user signals end of session, **proactively offer to run this checklist**:

1. **Run tests** — `.venv/bin/python -m pytest tests/`
2. **Run linter** — `.venv/bin/ruff check bristlenose/`
3. **Check maintenance schedule** — read the "Dependency maintenance" section of `TODO.md`; if today's date is past any unchecked quarterly/annual item, remind the user it's due
4. **Update `TODO.md`** — mark completed items, add new items discovered
5. **Update CLAUDE.md files** — persist new conventions, architectural decisions, or gotchas learned during the session (root CLAUDE.md or the appropriate child file: `bristlenose/theme/CLAUDE.md`, `bristlenose/stages/CLAUDE.md`, `bristlenose/llm/CLAUDE.md`); update version in "Current status" if bumped
6. **Update `CONTRIBUTING.md`** — if design system, release process, or dev setup changed
7. **Update `README.md`** — if version bump, add changelog entry
8. **Check for uncommitted changes** — `git status` + `git diff` — commit everything, push to `origin/main`
9. **Clean up branches** — delete merged feature branches
10. **Verify CI** — check latest push passes CI

## Current status (v0.9.3, Feb 2026)

Core pipeline complete and published to PyPI + Homebrew. Snap packaging implemented and tested locally (arm64); CI builds amd64 on every push. Latest: **Interactive dashboard** — Project tab stat cards are clickable links to target tabs, featured quote cards open video player or fall back to transcript, session rows drill into Sessions tab, section/theme names navigate to Quotes anchors, `--bn-colour-hover` design token, speaker code lozenges on featured quotes, reusable JS/Python navigation helpers. Prior: sessions table redesign (speaker badges, sparklines, thumbnails), appearance toggle (system/light/dark), user journeys table, tab navigation with hash persistence, Gemini provider (~$0.20/study), transcript annotations, Hidden quotes + Codebook, Azure OpenAI provider, install smoke tests, chart layout + histogram delete, multi-select and tag filter, tag taxonomy redesign (7 research-backed sentiments), keychain credential storage, Ollama local LLM support, output inside input folder, transcript coverage, multi-participant sessions. See git log for full history.

**Next up:** Phase 2 cross-session moderator linking; snap store publishing; tag definitions page in report UI. See `TODO.md` for full task list.
