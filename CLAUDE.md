# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Claude (Anthropic), ChatGPT (OpenAI), or local models via Ollama (free, no account required).

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
- **Provider naming**: user-facing text says "Claude" and "ChatGPT" (product names), not "Anthropic" and "OpenAI" (company names). Researchers know the products, not the companies. Internal code uses `"anthropic"` / `"openai"` as config values — that's fine, only human-readable strings need product names

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls), `doctor` (dependency health checks). **Default command**: `bristlenose <folder>` is shorthand for `bristlenose run <folder>` — if the first argument is an existing directory (not a known command), `run` is injected automatically.

LLM provider: Three providers supported — Claude (Anthropic), ChatGPT (OpenAI), and Local (Ollama). API keys via env vars (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`), `.env` file, or `bristlenose.toml`. Prefix with `BRISTLENOSE_` for namespaced variants. Local provider requires no API key — just Ollama running locally.

Report JavaScript — 11 modules in `bristlenose/theme/js/`, concatenated in dependency order into a single `<script>` block by `render_html.py` (`_JS_FILES`). Boot sequence in `main.js`:

1. `storage.js` — `createStore()` localStorage abstraction (used by all stateful modules)
2. `player.js` — `seekTo()`, `initPlayer()` for timecode playback
3. `favourites.js` — `initFavourites()`, star toggle, FLIP reorder animation
4. `editing.js` — `initEditing()`, `initInlineEditing()` for quote + heading editing
5. `tags.js` — `initTags()`, AI badge delete/restore, user tag CRUD, auto-suggest
6. `histogram.js` — `renderUserTagsChart()` for user-tags sentiment chart
7. `csv-export.js` — `initCsvExport()`, `copyToClipboard()`, `showToast()`, defines `currentViewMode` global
8. `view-switcher.js` — `initViewSwitcher()`, dropdown menu, section visibility (depends on `currentViewMode`)
9. `search.js` — `initSearchFilter()`, search-as-you-type filtering, exposes `_onViewModeChange()` hook
10. `names.js` — `initNames()`, participant name/role inline editing, YAML export
11. `main.js` — boot orchestrator, calls all `init*()` functions

Transcript pages use a separate list (`_TRANSCRIPT_JS_FILES`): `storage.js`, `player.js`, `transcript-names.js`.

## Output directory structure

Output goes **inside the input folder** by default: `bristlenose run interviews/` creates `interviews/bristlenose-output/`. This avoids collisions when processing multiple projects and keeps everything self-contained.

```
interviews/                              # input folder
├── Session 1.mp4
├── Session 2.mp4
└── bristlenose-output/                  # output folder (inside input)
    ├── bristlenose-interviews-report.html
    ├── bristlenose-interviews-report.md
    ├── people.yaml
    ├── assets/
    │   ├── bristlenose-theme.css
    │   ├── bristlenose-logo.png
    │   ├── bristlenose-logo-dark.png
    │   └── bristlenose-player.html
    ├── sessions/
    │   ├── transcript_s1.html
    │   └── transcript_s2.html
    ├── transcripts-raw/
    │   ├── s1.txt
    │   ├── s1.md
    │   └── ...
    ├── transcripts-cooked/              # only if --redact-pii
    │   └── ...
    └── .bristlenose/
        ├── intermediate/
        │   ├── extracted_quotes.json
        │   ├── screen_clusters.json
        │   ├── theme_groups.json
        │   └── topic_boundaries.json
        └── temp/
```

- **Report filenames include project name** — `bristlenose-{slug}-report.html` — so multiple reports in Downloads are distinguishable
- **`assets/`** — static files (CSS, logos, player)
- **`sessions/`** — per-session transcript HTML pages
- **`transcripts-raw/` / `transcripts-cooked/`** — Lévi-Strauss naming (researchers get it); cooked only exists with `--redact-pii`
- **`.bristlenose/`** — hidden internal files; `intermediate/` for JSON resumability, `temp/` for FFmpeg scratch
- **Path helpers** — `bristlenose/output_paths.py` defines `OutputPaths` dataclass for consistent path construction
- **Slugify** — `bristlenose/utils/text.py` has `slugify()` for project names in filenames (lowercase, hyphens, max 50 chars)

Override with `--output`: `bristlenose run interviews/ -o /elsewhere/`

## Platform-aware session grouping (Stage 1)

`ingest.py` groups input files into sessions using a two-pass strategy that understands Teams, Zoom, and Google Meet naming conventions.

- **`_normalise_stem(stem)`**: strips platform naming suffixes before stem comparison:
  - **Teams**: strips `{YYYYMMDD}_{HHMMSS}-Meeting Recording` and `-meeting transcript` suffixes (case-insensitive)
  - **Zoom cloud**: strips `Audio Transcript_` prefix and trailing `_{MeetingID}_{Month_DD_YYYY}` (meeting ID is 9–11 digits)
  - **Google Meet** (Phase 2 prep): strips `({YYYY-MM-DD at ...})` parenthetical and `- Transcript` suffix
  - **Legacy**: existing `_transcript`, `_subtitles`, `_captions`, `_sub`, `_srt` suffixes still work
- **`_is_zoom_local_dir(dir_name)`**: detects Zoom local recording folder pattern (`YYYY-MM-DD HH.MM.SS Topic MeetingID`)
- **`group_into_sessions()`** two-pass grouping:
  1. Files inside a Zoom local folder are grouped by directory (regardless of individual filenames)
  2. Remaining files are grouped by normalised stem
- **Regex patterns**: `_TEAMS_SUFFIX_RE`, `_ZOOM_CLOUD_TAIL_RE`, `_ZOOM_CLOUD_PREFIX_RE`, `_ZOOM_LOCAL_DIR_RE`, `_GMEET_PAREN_RE`, `_GMEET_TRANSCRIPT_SUFFIX_RE` — all compiled at module level
- **Audio extraction skip**: `extract_audio.py` skips FFmpeg extraction when `session.has_existing_transcript=True` (the pipeline already skips Whisper; now it also skips the unnecessary audio decode)
- **Design doc**: `docs/design-platform-transcripts.md` — full platform catalogue, market data, implementation phases
- **Tests**: `tests/test_ingest.py` (35 tests: normalisation, Zoom dir detection, session grouping for all platforms), `tests/test_extract_audio.py` (2 tests: extraction skip behaviour)

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`

## HTML report features

The generated HTML report has interactive features: inline editing (quotes, headings, names), search-as-you-type, view switching, CSV export, and per-participant transcript pages with deep-linked timecodes. Full implementation details in `docs/design-html-report.md`. Key concepts:

- **People file** (`people.yaml`): participant registry with computed stats + human-editable fields. Models in `models.py`, logic in `people.py`. Merge strategy preserves user edits across runs. Moderator codes (`m1`/`m2`) get their own entries alongside participants
- **Speaker codes**: per-segment identity (`p1`, `m1`, `m2`, `o1`) assigned by `assign_speaker_codes()` after Stage 5b. Participant codes (`p1`–`pN`) are globally numbered across sessions (not per-session) so each participant has a unique code across the entire study. Moderator/observer codes (`m1`, `o1`) remain per-session. Persisted in `.txt` files as bracket tokens. Phase 1 = per-session only; Phase 2 (cross-session linking for moderators) not yet implemented
- **Name editing**: inline in the report via `names.js` → localStorage → "Export names" YAML → paste into `people.yaml` → `bristlenose render`. Auto name/role extraction from LLM + speaker labels
- **Anonymisation boundary**: report quotes show raw `p1`/`p2` IDs (safe to copy to Miro/presentations). Transcript page segment labels also show raw codes (`p1:`, `m1:`); only the heading shows display names (private to researcher)
- **Search**: search-as-you-type with yellow highlights, match count in view-switcher, CSV export respects filter
- **Transcript pages**: per-session HTML pages in `sessions/transcript_s1.html` with heading showing all speakers (`Session 1: m1 Sarah Chen, p5 Maya, o1`), per-segment raw speaker codes (`p1:`, `m1:`), `.segment-moderator` CSS class for muted moderator styling, deep-link anchors from quote attributions, anchor highlight animation (yellow flash when arriving via link)
- **Sessions table**: report table shows one row per session with columns Session | Speakers | Start | Duration | Source. Speakers column lists all codes (m→p→o sorted) with `data-participant` spans for JS name resolution
- **PII redaction**: off by default (`--redact-pii` to opt in)

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

## Local LLM provider (Ollama)

`bristlenose/ollama.py` handles Ollama detection, installation, and model management. `bristlenose/providers.py` defines the provider registry.

- **Provider registry**: `ProviderSpec` dataclass with `name`, `display_name`, `aliases`, `default_model`, `sdk_module`, `pricing_url`. `PROVIDERS` dict maps canonical names to specs. `resolve_provider()` normalises aliases (claude→anthropic, chatgpt→openai, ollama→local)
- **Interactive first-run prompt**: `_prompt_for_provider()` in `cli.py` — when no API key and default provider, offers 3 choices: Local (free), Claude (~$1.50/study), ChatGPT (~$1.00/study). Only triggers for default anthropic case; explicit `--llm` choices skip the prompt
- **Ollama detection**: `check_ollama()` hits `http://localhost:11434/api/tags` to check if running and list models. `is_ollama_installed()` checks PATH. `validate_local_endpoint()` returns `(True, "")`, `(False, error)`, or `(None, error)` for connection issues
- **Auto-install**: `get_install_method()` returns "brew"/"snap"/"curl"/None based on platform and available tools. `install_ollama(method)` runs the appropriate command. Priority: macOS prefers brew, Linux prefers snap, fallback to curl script. Falls back to download page on failure
- **Auto-start**: `start_ollama_serve()` — macOS uses `open -a Ollama`, Linux uses `ollama serve` in background with `start_new_session=True`. Waits 2s and verifies running
- **Model auto-pull**: `pull_model()` runs `ollama pull` with stdout passthrough for progress bar. Triggered via interactive prompt when no suitable model found
- **Preferred models**: `PREFERRED_MODELS` list in order — `llama3.2:3b` (default), `llama3.2`, `llama3.2:1b`, `llama3.1:8b`, `mistral:7b`, `qwen2.5:7b`
- **LLM client**: `_analyze_local()` in `llm/client.py` uses OpenAI SDK with `base_url=settings.local_url`. Includes JSON schema in system prompt and 3 retries with exponential backoff for parse failures (~85% reliability vs ~99% for cloud)
- **Doctor integration**: `check_local_provider()` validates endpoint and model. Three fix keys: `ollama_not_installed`, `ollama_not_running`, `ollama_model_missing`. Fix messages are context-aware — suggest `--llm claude` only if user has Anthropic key, etc.
- **Config**: `local_url` (default `http://localhost:11434/v1`), `local_model` (default `llama3.2:3b`)
- **Tests**: `tests/test_providers.py` (47 tests), `tests/test_provider_horror_scenarios.py` (31 tests) — covers all error paths, fix messages, interactive prompt logic

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

## Man page

Full troff man page covering all commands, options, configuration, examples, input/output, and hardware auto-detection.

- **Canonical location**: `bristlenose/data/bristlenose.1` (inside the package, bundled in the wheel via `pyproject.toml` artifacts)
- **Repo symlink**: `man/bristlenose.1` → `../bristlenose/data/bristlenose.1` — keeps CI, snap build, release asset, and `man man/bristlenose.1` working
- **Self-install (pip/pipx)**: `_install_man_page()` in `cli.py` copies the man page to `~/.local/share/man/man1/` on first run (piggybacks on auto-doctor sentinel). Skipped in snap and Homebrew (they handle their own installation)
- **Snap**: installed to `$CRAFT_PART_INSTALL/share/man/man1/` during `override-build` in `snapcraft.yaml`
- **Homebrew**: formula in the tap repo needs `man1.install "man/bristlenose.1"` (sdist includes the file)
- **GitHub Release**: attached as a release asset by `release.yml`
- **CI version check**: `ci.yml` has a hard gate that greps `man/bristlenose.1` for `"bristlenose $VERSION"` — fails if the `.TH` line doesn't match `__version__`
- **Release checklist**: step 2 in `docs/release.md` — bump the `.TH` version whenever `__version__` changes

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

## Performance optimisations

- **Compact JSON in LLM prompts**: `quote_clustering.py` and `thematic_grouping.py` use `json.dumps(separators=(",",":"))` (no whitespace) to minimise input tokens sent to the LLM for stages 10 and 11. Saves 10–20% tokens on these cross-participant calls
- **FFmpeg VideoToolbox hardware decode**: `utils/audio.py` passes `-hwaccel videotoolbox` on macOS, offloading H.264/HEVC video decoding to the Apple Silicon media engine. Harmless no-op for audio-only inputs; flag omitted on non-macOS platforms. 2–4× faster video decode, frees CPU/GPU for other work
- **Concurrent audio extraction**: `extract_audio_for_sessions()` in `stages/extract_audio.py` is async — up to 4 FFmpeg processes run in parallel via `asyncio.Semaphore(4)` + `asyncio.gather()`. Blocking `subprocess.run` calls wrapped in `asyncio.to_thread()`. Default concurrency of 4 is a fixed constant (not hardware-adaptive) because the bottleneck is the shared media engine on macOS, not CPU core count — works well across all Apple Silicon variants (M1 through M4 Ultra). On Linux without hardware decode, 4 concurrent software-decode processes is still reasonable. `concurrency` kwarg exposed for future config wiring if needed
- **Audio extraction skip for platform transcripts**: `extract_audio.py` checks `session.has_existing_transcript` and skips FFmpeg entirely when a platform transcript (VTT/SRT/DOCX) is present — avoids unnecessary video decode when Whisper won't be called

## CLI output (Cargo/uv-style)

Pipeline output uses clean Cargo/uv-style checkmark lines with per-stage timing, a dim header, and a post-run summary. No Rich spinners or logging at default verbosity.

- **Output pattern**: `console.status()` spinner during work → `_print_step()` checkmark when done. Each stage: `status.update(" [dim]Doing X...[/dim]")` → do work → `_print_step("Did X", elapsed)`. Spinner is hidden; checkmark is permanent
- **Spinner–checkmark column alignment**: the spinner character (`⠋`) and the checkmark (`✓`) both render at column 1. `_print_step()` achieves this with a leading space (`" [green]✓[/green] {message}"` — text at col 3). The spinner is aligned by prepending a space to every frame in the Rich `Spinner` object immediately after creating the `console.status()` context: `status.renderable.frames = [" " + f for f in status.renderable.frames]`. Rich's `Text.assemble(frame, " ", text)` adds one separator space between the padded frame and the status text, so status text (no leading space) lands at col 3, matching the checkmark text. This line appears in all three pipeline methods (`run`, `run_transcription_only`, `run_analysis_only`). Rich's `Status.renderable` returns the internal `Spinner` object, and its `.frames` list is mutable — this is the least invasive way to shift the spinner position without subclassing or monkey-patching
- **Width cap**: `Console(width=min(80, Console().width))` in both `pipeline.py` and `cli.py`. Keeps output tidy on wide terminals while respecting narrow ones
- **Timing**: `time.perf_counter()` bracketing each stage. `_format_duration()` formats as `0.1s` or `3m 41s`
- **Header**: `Bristlenose [dim]v{version} · {n} sessions · {provider} · {hw.label}[/dim]` — "Bristlenose" in regular weight, rest dim. Printed after ingest (session count not known until then)
- **Summary** (`_print_pipeline_summary()` in `cli.py`): `[green]Done[/green]` + elapsed, dim stats line, dim LLM usage with cost estimate, `Report:` label (regular weight) with OSC 8 `file://` hyperlink
- **LLM usage tracking**: `LLMUsageTracker` class in `llm/client.py` accumulates input/output tokens across all async calls. `estimate_cost()` in `llm/pricing.py` uses a hardcoded pricing table + verification URL
- **Hardware label**: `HardwareInfo.label` property (e.g. "Apple M2 Max · MLX") — `utils/hardware.py`
- **Logging suppression**: `logging.WARNING` at default verbosity (`force=True`); noisy third-party loggers (`httpx`, `presidio-analyzer`, `faster_whisper`) always suppressed. `-v` flag restores `DEBUG` level
- **Progress bar suppression**: module-level `TQDM_DISABLE=1` and `HF_HUB_DISABLE_PROGRESS_BARS=1` env vars in `pipeline.py`, plus programmatic `disable_progress_bars()` call in `transcribe.py` after `import mlx_whisper`
- **Styling principle**: minimal colour. Green `✓` checkmarks, dim timing, dim header/stats/labels. "Bristlenose" and "Report:" in regular weight — everything else is muted. The checkmarks and their messages are the only other bright elements
- **Stage failure warnings**: `_print_warn(message, link="")` prints a dim yellow line below the checkmark when an LLM stage fails. `_short_reason(errors, provider)` extracts a human-readable message from API error JSON (regex on `'message':` field) and returns `(message, link)`. Detects credit-balance errors and provides a direct billing URL (`_BILLING_URLS` dict: `anthropic` → `platform.claude.com/settings/billing`, `openai` → `platform.openai.com/settings/organization/billing`). Deduplication via `_printed_warnings` set (cleared at start of each pipeline run). Messages truncated to 74 chars with `…`. Stage files (`identify_speakers.py`, `topic_segmentation.py`, `quote_extraction.py`) log errors at `logger.debug` level and append to an `errors: list[str]` parameter — pipeline.py prints clean warnings after the checkmark, not during the spinner
- **Tests**: `tests/test_cli_output.py` (13 tests: `_format_duration`, `HardwareInfo.label`), `tests/test_llm_usage.py` (10 tests: `LLMUsageTracker`, `estimate_cost`)

### Progress bar gotchas (things that were tried and failed)

These are documented to prevent re-exploration of dead ends:

- **mlx-whisper `verbose` parameter is counterintuitive**: `verbose=False` ENABLES tqdm progress bars (`disable=verbose is not False` → `disable=False`). `verbose=None` DISABLES them (`disable=True`). `verbose=True` also disables the bar but enables text output. We use `verbose=None`
- **`TQDM_DISABLE` env var must be set before any tqdm import**: setting it inside `Pipeline.__init__()` is too late — moved to module level in `pipeline.py`
- **`HF_HUB_DISABLE_PROGRESS_BARS` env var is read at `huggingface_hub` import time** (in `constants.py`): if `huggingface_hub` was already imported before `pipeline.py` loads, the env var has no effect. Belt-and-suspenders: also call `disable_progress_bars()` programmatically in `_init_mlx_backend()` after `import mlx_whisper`
- **tqdm progress bars don't overwrite inside Rich `console.status()`**: Rich's spinner takes control of the terminal cursor. tqdm's `\r` carriage return doesn't work properly, causing bars to scroll line-by-line instead of overwriting in place. This makes tqdm bars useless inside a Rich status context — they produce dozens of non-overwriting lines
- **`TQDM_NCOLS=80` doesn't help**: even with width capped, the non-overwriting bars still produce one line per update. The root issue is tqdm + Rich terminal conflict, not width
- **Conclusion**: suppress all tqdm/HF bars entirely; let the Rich status spinner handle progress indication. The per-stage timing on the checkmark line provides sufficient feedback. Don't try to re-enable mlx-whisper's tqdm bar — it will scroll

## Gotchas

### Ruff auto-removes unused imports (F401)

Ruff `--fix` removes unused imports. When making multi-step edits:

1. **Add imports and their usage in the same edit** — don't add imports in one edit and the code that uses them in a later edit
2. **If editing a large file incrementally**, add imports last (after the code that uses them is already in place), or add them together with at least one usage
3. **If an import keeps disappearing**, check whether the code that uses it is actually in place — the linter is telling you the import genuinely isn't used yet

This is especially common when:
- Planning to add a function call but editing the import section first
- Copy-pasting code that needs new imports but forgetting to verify the imports landed
- Making changes across multiple files where one file's import depends on another file's changes

### Other gotchas

- **Provider registry** — `bristlenose/providers.py` is the single source of truth for provider metadata (names, aliases, default models, SDK modules). `resolve_provider()` handles alias normalisation (claude→anthropic, ollama→local). `load_settings()` in `config.py` calls the registry to normalise aliases
- **Local LLM uses OpenAI SDK** — Ollama is OpenAI-compatible, so `_analyze_local()` in `llm/client.py` uses the same `openai.AsyncOpenAI` client with `base_url=settings.local_url` and `api_key="ollama"` (required by SDK but ignored by Ollama)
- **Local model retry logic** — `_analyze_local()` retries JSON parsing failures up to 3 times with exponential backoff; local models are ~85% reliable vs ~99% for cloud
- **`_needs_provider_prompt()` checks Ollama status** — for local provider, it calls `validate_local_endpoint()` to check if Ollama is running and has the model; for cloud providers, it just checks if the API key is set
- The repo directory is `/Users/cassio/Code/bristlenose`
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
- `view-switcher.js`, `search.js`, and `names.js` all load **after** `csv-export.js` in `_JS_FILES` — `view-switcher.js` writes the `currentViewMode` global defined in `csv-export.js`; `search.js` reads `currentViewMode` and exposes `_onViewModeChange()` called by `view-switcher.js`; `names.js` depends on `copyToClipboard()` and `showToast()`
- `_TRANSCRIPT_JS_FILES` includes `transcript-names.js` (after `storage.js`) — reads localStorage name edits and updates heading speaker names only (preserving code prefix: `"m1 Sarah Chen"`). Does NOT override segment speaker labels (they stay as raw codes). Separate from the report's `names.js` (which has full editing UI)
- `blockquote .timecode` in `blockquote.css` must use `--bn-colour-accent` not `--bn-colour-muted` — the `.timecode-bracket` children handle the muting. If you add a new timecode rendering context, ensure the parent rule uses accent
- `_normalise_stem()` expects a lowercased stem — callers must `.lower()` before passing. `group_into_sessions()` does this; unit tests pass lowercased literals directly
- **Renaming the repo directory breaks the venv.** Python editable installs (`pip install -e .`) write the absolute path into `.pth` files and CLI shim shebangs. If you `mv` the project directory, the venv silently breaks — imports may appear to work (CWD fallback on `sys.path`) but stale bytecode in `__pycache__/` will serve old code. Fix: `find . -name __pycache__ -exec rm -rf {} +` then `.venv/bin/python -m pip install -e '.[dev]'` (use `python -m pip`, not bare `pip`, because the pip shim's shebang is also broken). Alternatively, delete `.venv` and recreate
- **`segment_topics()` returns `list[SessionTopicMap]`, NOT a dict** — use `sum(len(m.boundaries) for m in topic_maps)`, not `topic_maps.values()`. This was a bug that took two attempts to find because `_gather_all_segments()` returns `dict[str, list[TranscriptSegment]]` (which does have `.values()`), creating a misleading pattern
- **`InputSession.files` is a list, `InputFile.duration_seconds` is on each file** — to sum audio duration: `sum(f.duration_seconds or 0 for s in sessions for f in s.files)`, not `s.duration_seconds`
- **`Console(width=min(80, Console().width))`** — the `Console()` inside `min()` is a throwaway instance that auto-detects the real terminal width. This is the intended pattern; don't cache it
- **`_format_duration` and `_print_step` are module-level in `pipeline.py`** — `cli.py` imports `_format_duration` from there. Don't move them into the `Pipeline` class
- **`PipelineResult` has optional LLM fields** (default 0/empty string) — `run_transcription_only()` doesn't use `LLMClient` so these stay at defaults. `_print_pipeline_summary()` in `cli.py` uses `getattr()` defensively
- **Homebrew tap repo must be named `homebrew-bristlenose`** (not `bristlenose-homebrew`). `brew tap cassiocassio/bristlenose` looks for a GitHub repo called `cassiocassio/homebrew-bristlenose` — this is a Homebrew convention, not configurable. The local directory name doesn't matter to Git, but keeping it matching avoids confusion
- **`speaker_code` defaults to `""`** — existing code that doesn't set it uses `seg.speaker_code or transcript.participant_id` as a fallback in all write functions. This means old transcripts and single-speaker sessions work unchanged
- **`assign_speaker_codes()` must run after Stage 5b** — it reads `speaker_role` set by the heuristic/LLM passes. If called before role assignment, all speakers get the session's `participant_id` (UNKNOWN → fallback)
- **Moderator codes are per-session, not cross-session** — `m1` in session 1 and `m1` in session 2 are independent entries in `people.yaml`. Cross-session linking is Phase 2 (not implemented)
- **`transcript-names.js` already handles moderator codes** — it queries `[data-participant]` generically, so `data-participant="m1"` works without JS changes
- **`PersonComputed.session_id` defaults to `""`** — backward compat with existing `people.yaml` files. New runs set it to `"s1"`, `"s2"`, etc. via `compute_participant_stats()`
- **`_session_duration()` accepts optional `people` parameter** — checks `PersonComputed.duration_seconds` (matched by `session_id`) before falling back to `InputFile.duration_seconds`. This fixes VTT-only sessions that have no `InputFile.duration_seconds` but do have segment timestamps
- **Report sessions table groups speakers by `computed.session_id`** — if people file is missing, falls back to showing `[session.participant_id]` only
- **Transcript files named by `session_id`** (`s1.txt` in `transcripts-raw/`, not `p1_raw.txt`) — a single file contains segments from all speakers in that session (`[m1]`, `[p1]`, `[p2]`, `[o1]`)
- **`assign_speaker_codes()` signature is `(session_id, next_participant_number, segments)`** — returns `(dict[str, str], int)` (label→code map, updated next number). The `next_participant_number` counter enables global p-code numbering across sessions
- **`transcripts-cooked/` only exists with `--redact-pii`** — if a previous run used PII redaction but the current one doesn't, stale cooked files remain on disk. Coverage and transcript pages must use the same transcript source to avoid broken links. `render_transcript_pages()` accepts a `transcripts` parameter to ensure consistency; see `bristlenose/stages/CLAUDE.md` for details
- **`_render_transcript_page()` accepts `FullTranscript`, not just `PiiCleanTranscript`** — the assertion uses `isinstance(transcript, FullTranscript)`. Since `PiiCleanTranscript` is a subclass, both types pass. Don't tighten this to `PiiCleanTranscript` or it will crash when PII redaction is off (the default)
- **`player.js` only intercepts `.timecode` clicks with `data-participant` and `data-seconds`** — coverage section links use `class="timecode"` but NO data attributes, so they navigate normally. If you add new timecode links that should navigate (not open the player), omit the data attributes

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

## Reference docs (read when working in these areas)

- **HTML report / people file / transcript pages**: `docs/design-html-report.md`
- **Theme / dark mode / CSS**: `bristlenose/theme/CLAUDE.md`
- **Pipeline stages / transcript format / output structure**: `bristlenose/stages/CLAUDE.md`
- **File map** (what lives where): `docs/file-map.md`
- **Release process / CI / secrets**: `docs/release.md`
- **Design system / contributing**: `CONTRIBUTING.md`
- **Doctor command + Snap packaging design**: `docs/design-doctor-and-snap.md`
- **Platform transcript ingestion**: `docs/design-platform-transcripts.md`
- **Transcript coverage feature**: `docs/design-transcript-coverage.md`
- **CLI improvements + LLM provider roadmap**: `docs/design-cli-improvements.md`

## Working preferences

- Keep changes minimal and focused — don't refactor or add features beyond what's asked
- Commit messages: short, descriptive, lowercase (e.g., "fix tag suggest offering tags the quote already has")

### Release timing (evening releases)

Releases should land on GitHub after 9pm London time on weekdays to avoid pushing version bumps during working hours.

**Workflow:**
1. Work on `main` as usual — commit everything locally
2. Don't push to `origin/main` until after 9pm (or weekends)
3. To see work remotely before release (CI checks, another machine): `git push origin main:wip` — the `wip` branch doesn't trigger releases
4. After 9pm: `git push origin main --tags`

**Override:** Just push if something is urgent. This is a guideline, not a gate.

**Why:** Avoids notifications during client working hours; batches releases into a predictable window.

## Before committing

1. `.venv/bin/python -m pytest tests/` — all pass
2. `.venv/bin/ruff check bristlenose/` — no lint errors

## Session-end housekeeping

When the user signals end of session, **proactively offer to run this checklist**:

1. **Run tests** — `.venv/bin/python -m pytest tests/`
2. **Run linter** — `.venv/bin/ruff check bristlenose/`
3. **Check maintenance schedule** — read the "Dependency maintenance" section of `TODO.md`; if today's date is past any unchecked quarterly/annual item, remind the user it's due
4. **Update `TODO.md`** — mark completed items, add new items discovered
5. **Update CLAUDE.md files** — persist new conventions, architectural decisions, or gotchas learned during the session (root CLAUDE.md or the appropriate child file: `bristlenose/theme/CLAUDE.md`, `bristlenose/stages/CLAUDE.md`); update version in "Current status" if bumped
6. **Update `CONTRIBUTING.md`** — if design system, release process, or dev setup changed
7. **Update `README.md`** — if version bump, add changelog entry
8. **Check for uncommitted changes** — `git status` + `git diff` — commit everything, push to `origin/main`
9. **Clean up branches** — delete merged feature branches
10. **Verify CI** — check latest push passes CI

## Current status (v0.6.11, Feb 2026)

Core pipeline complete and published to PyPI + Homebrew. Snap packaging implemented and tested locally (arm64); CI builds amd64 on every push. Latest: **Ollama local LLM support (Phase 1 complete)** — provider registry (`bristlenose/providers.py`), Ollama detection/installation/auto-start (`bristlenose/ollama.py`), interactive first-run prompt offering Local/Claude/ChatGPT choice, automated Ollama installation (brew on macOS, snap on Linux, curl fallback), smart cloud fallback hints in fix messages (checks which API keys are configured), retry logic for local model JSON parsing (~85% reliability), doctor integration; **78 new provider tests** (`test_providers.py` + `test_provider_horror_scenarios.py`). Prior: output inside input folder; transcript coverage section; multi-participant sessions with global p-codes; sessions table; transcript pages with speaker codes. v0.6.7 adds search enhancements, pipeline warnings, CLI polish. v0.6.6 adds Cargo/uv-style CLI output, search-as-you-type filtering, platform-aware session grouping, man page, page footer. v0.6.5 adds timecode typography, hanging-indent quote layout, transcript name propagation. v0.6.4 adds concurrent per-participant LLM calls. v0.6.3 redesigns report header, adds view-switcher dropdown, Analysis ToC column, anonymisation boundary. v0.6.2 adds editable participant names, auto name/role extraction, editable headings. v0.6.1 adds snap recipe, CI workflow. v0.6.0 added `bristlenose doctor`. v0.5.0 added per-participant transcript pages.

**Next up:** Phase 2 Azure OpenAI for enterprise users, Phase 3 Keychain integration for secure credential storage, Phase 4 Gemini for budget users. Also: Phase 2 cross-session moderator linking; snap store publishing. See `TODO.md` for full task list.
