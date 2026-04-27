# Bristlenose — Project Context for Claude

## What this is

Bristlenose is a local-first user-research analysis tool. It takes a folder of interview recordings (audio, video, or existing transcripts) and produces a browsable HTML report with extracted quotes, themes, sentiment, friction points, and user journeys. Everything runs on your laptop — nothing is uploaded to the cloud. LLM calls go to Claude (Anthropic), ChatGPT (OpenAI), Azure OpenAI (enterprise), Gemini (Google), or local models via Ollama (free, no account required).

## Commands

- `.venv/bin/python -m pytest tests/` — run tests
- `.venv/bin/ruff check bristlenose/` — lint (no global ruff install)
- `.venv/bin/ruff check --fix bristlenose/` — lint and auto-fix
- `.venv/bin/mypy bristlenose/` — type check (informational, not a hard gate)
- `cd e2e && npm test` — Playwright E2E tests (layers 1–3: console, links, network; Chromium + WebKit)

## Key conventions

- **Python 3.10+**, strict mypy, Ruff linting (line-length 100, rules: E/F/I/N/W/UP, E501 ignored)
- **Type hints everywhere** — Pydantic models for all data structures
- **Single source of version**: `bristlenose/__init__.py` (`__version__`). Never add version to `pyproject.toml`. Use `./scripts/bump-version.py` to bump (updates `__init__.py`, man page, creates git tag)
- **Markdown style template** in `bristlenose/utils/markdown.py` — single source of truth for all markdown/txt formatting. Change formatting here, not in stage files
- **Atomic CSS design system** in `bristlenose/theme/` — tokens, atoms, molecules, organisms, templates (see `bristlenose/theme/CLAUDE.md`)
- **Licence**: AGPL-3.0 with CLA
- **Provider naming**: user-facing text says "Claude", "ChatGPT", and "Azure OpenAI" (product names), not "Anthropic" and "OpenAI" (company names). Researchers know the products, not the companies. Internal code uses `"anthropic"` / `"openai"` / `"azure"` as config values — that's fine, only human-readable strings need product names
- **Changelog version/date format**: `**X.Y.Z** — _D Mon YYYY_` (e.g. `**0.8.1** — _7 Feb 2026_`). Bold version, em dash, italic date. No hyphens in dates, no leading zero on day. Used in both `CHANGELOG.md` and the changelog section of `README.md`
- **React is the primary rendering path (Feb 2026).** All visual/design work targets the React serve version (`bristlenose serve`). The static HTML renderer (`bristlenose/stages/s12_render/`) is **deprecated** — it ships correct data but does not receive design updates. `render_html()` emits a `DeprecationWarning`. Rules: (1) New features and design changes: React only. (2) CSS in `bristlenose/theme/` is shared — CSS changes apply to both paths automatically. (3) Vanilla JS in `bristlenose/theme/js/` is frozen — data-integrity fixes only, no feature work. (4) When a section becomes a React island, its Jinja2 equivalent becomes dead code — stop maintaining it. (5) The `bristlenose render` CLI command continues to work for users who want offline HTML, but it's the "frozen snapshot" format, not the actively developed experience. (6) The old monolithic `render_html.py` was refactored into `bristlenose/stages/s12_render/` package (Mar 2026): `theme_assets.py`, `html_helpers.py`, `quote_format.py`, `sentiment.py`, `dashboard.py`, `transcript_pages.py`, `standalone_pages.py`, `report.py`

## Architecture

12-stage pipeline: ingest → extract audio → parse subtitles → parse docx → transcribe → identify speakers → merge transcript → PII removal → topic segmentation → quote extraction → quote clustering → thematic grouping → render HTML + output files.

CLI commands: `run` (full pipeline), `transcribe-only`, `analyze` (skip transcription), `render` (re-render from JSON, no LLM calls), `serve` (local dev server), `status` (read-only project state from manifest), `doctor` (dependency health checks). **Default command**: `bristlenose <folder>` is shorthand for `bristlenose run <folder>` — if the first argument is an existing directory (not a known command), `run` is injected automatically.

Serve mode: FastAPI + SQLite + React SPA. See `bristlenose/server/CLAUDE.md` for architecture.

Desktop app: `desktop/` — SwiftUI macOS shell. Alpha ships a bundled, signed PyInstaller sidecar running `bristlenose serve`, distributed via internal TestFlight. v0.2 currently uses launcher-style scaffolding (dev-only, not shippable). See `docs/design-desktop-app.md` for the overall app design, `docs/design-modularity.md` for cross-channel component decisions (CLI ≡ macOS Python code; packaging differences only), and `docs/private/road-to-alpha.md` for the 14-checkpoint path to TestFlight.

Frontend: `frontend/` — Vite + React + TypeScript + React Router. See `frontend/CLAUDE.md` for gotchas and architecture.

Export: DOM snapshot from serve mode (self-contained HTML). Static render (`bristlenose/stages/s12_render/`) is deprecated.

LLM providers: Claude, ChatGPT, Azure OpenAI, Gemini, Local (Ollama). See `bristlenose/llm/CLAUDE.md`.

Quote exclusivity: **every quote appears in exactly one report section.** See `bristlenose/stages/CLAUDE.md`.

Analysis page: `bristlenose/analysis/` — signal concentration metrics, pure math. Uses plain dataclasses (not Pydantic). Cell keys use `"label|sentiment"` format. See `docs/design-analysis-future.md`.

LLM prompts: Markdown files in `bristlenose/llm/prompts/`. Archive old versions to `bristlenose/llm/prompts-archive/`. See `bristlenose/llm/CLAUDE.md`.

Report JavaScript: 17 modules in `bristlenose/theme/js/`. See `bristlenose/theme/js/MODULES.md`.

Video thumbnails: `bristlenose/utils/video.py` — auto-extracted keyframes per session. See `docs/design-html-report.md`.

## Output directory structure

Output goes **inside the input folder** by default: `bristlenose run interviews/` creates `interviews/bristlenose-output/`. Override with `--output`. See `bristlenose/stages/CLAUDE.md` for the full directory layout.

Key helpers: `OutputPaths` in `output_paths.py` (consistent path construction), `slugify()` in `utils/text.py` (project names in filenames — lowercase, hyphens, max 50 chars). Report filenames include project name (`bristlenose-{slug}-report.html`) so multiple reports in Downloads are distinguishable.

## Boundaries

- **Safe to edit**: `bristlenose/`, `tests/`, `frontend/`, `desktop/`
- **Design artifacts** (tracked, not shipped): `docs/mockups/`, `docs/design-system/`, `experiments/` — HTML mockups, style guides, throwaway prototypes. These are working materials for contributors, kept in the tree for backup and collaboration. Users never navigate to them. Add new mockups to `docs/mockups/`, not the repo root. **Serve mode auto-discovery**: `bristlenose serve --dev` mounts all three directories and auto-discovers `*.html` files for the Design section in the About tab (`_build_dev_section_html()` in `app.py`). New HTML files added to these directories appear automatically — no code changes needed
- **Website** (deployed): `website/` — static HTML/CSS for bristlenose.app. Deploy with `/deploy-website` skill or `deploy-website` shell alias. See `docs/private/deploy-website.md`. **Note:** rsync deploy needs SSH agent access — Claude Code's sandbox can't reach it, so the user runs the deploy command manually
- **Never touch**: `.env`, output directories, `bristlenose/theme/images/`
- **Gitignored (private)**: `docs/private/`, `trial-runs/` — contain names, contacts, strategy, pricing, legal drafts, and value judgements that don't belong on the public repo. Local-only, backed up by a separate code-backup script, never committed to git. Do not suggest `git add -f` for files here.

## Deployment targets

Bristlenose runs on three targets: macOS arm64 (primary dev), Linux x86_64 via GitHub Actions CI (release pipeline), and — newly — Claude Code Cloud VMs (ephemeral Ubuntu x86_64,  but reachable when the user picks Cloud in the picker). Cloud is useful for code/test/lint/frontend-build work, **not** for pipeline runs on private interview data. See `docs/design-deployment-targets.md for the audit checklist and use-case boundary table.

## HTML report features

The generated HTML report has interactive features: inline editing (quotes, headings, names), search-as-you-type, view switching, CSV export, tag filter, hidden quotes, and per-participant transcript pages with deep-linked timecodes. Full implementation details in `docs/design-html-report.md`. Key concepts: people file merge strategy, speaker codes, anonymisation boundary, tag filter persistence, hidden quotes with `.bn-hidden` defence-in-depth. See `bristlenose/theme/CLAUDE.md` for CSS/design gotchas, `bristlenose/theme/js/MODULES.md` for JS module details, `bristlenose/theme/CSS-REFERENCE.md` for per-component CSS docs.

Doctor command: `bristlenose doctor` — runtime environment checks. See `docs/design-doctor-and-snap.md`.

Snap + man page: see `docs/design-doctor-and-snap.md` and `docs/release.md`.

CLI output: Cargo/uv-style checkmark lines with per-stage timing. Time estimation via Welford's algorithm in `bristlenose/timing.py`. See `bristlenose/stages/CLAUDE.md` for pipeline runtime details.

## Gotchas

### Ruff F401 (unused imports) — reports only, won't auto-fix

F401 is marked `unfixable` in `pyproject.toml` so `ruff check --fix` (and the PostToolUse hook) won't delete imports during incremental edits. Ruff still *reports* unused imports — remove them manually when they're genuinely unused.

### macOS BSD userland — use GNU coreutils

macOS ships BSD versions of `sed`, `grep`, `awk`, `find`, `xargs`, `date`, `stat`, `readlink`, `tar`, and others. These differ from the GNU versions in subtle, bug-inducing ways:

- **`sed`**: no `\b` word boundary, `-i` requires backup extension arg (`sed -i '' ...`), no `\x00` hex escapes. **Use `gsed`** (installed via `brew install gnu-sed`)
- **`grep`**: BSD `-P` (PCRE) doesn't exist. Use `ggrep` or `rg` (ripgrep) for PCRE patterns
- **`date`**: BSD uses `-j -f` for parsing, GNU uses `-d`. Completely incompatible date arithmetic
- **`readlink`**: BSD has no `-f` (canonicalize). Use `greadlink -f` or `realpath`
- **`xargs`**: BSD `-r` (no-run-if-empty) doesn't exist — GNU behaviour is the default on BSD but the flag is missing
- **`stat`**: completely different flag syntax (`-f` vs `-c` for format strings)
- **`tar`**: BSD tar is `bsdtar` (libarchive), differs from GNU tar in flag handling, especially for `--transform`
- **`find`**: BSD `-regex` uses basic regex by default (GNU uses Emacs regex); `-regextype` doesn't exist
- **`awk`**: BSD awk is ancient POSIX awk — no `gensub`, no `length(array)`, no `FPAT`

**Rule: when writing shell commands that use regex or platform-specific flags, prefer `gsed`/`ggrep`/`gawk`/`greadlink` (all from `brew install coreutils gnu-sed gawk findutils grep`), or use Python/Perl for portability.** The `g`-prefixed GNU tools are always available on this machine.

### i18n — single source of truth

- **Locale files live in `bristlenose/locales/` only** — `frontend/src/locales/` was deleted. The frontend imports via Vite alias `@locales`. Don't create locale files in the frontend tree. `I18n.swift` (desktop) reads the same JSON at runtime
- **`useTranslation()` is the hook; `i18n.t()` is the direct import** — use the hook inside React components; use `import i18n from "../i18n"` + `i18n.t()` in stores, announce utilities, and other non-component code
- **New keys must go in all 6 locale files** — en, es, fr, de, ko, ja. Every `t("key")` call needs an entry in each. If using `dt()`, the desktop override must also go in all 6 `desktop.json` files
- **Platform text forking** — `dt(t, key)` checks `desktop:` namespace first (falls back to base key). `ct(t, key)` returns `null` on desktop (hides CLI-only text). Both in `frontend/src/utils/platformTranslation.ts`. See `docs/platform-text-map.md`
- **SwiftUI `CommandMenu` titles can't use runtime strings** — menu titles stay in English; only items inside are translated

See `docs/design-i18n.md` for implementation gotchas (Apple glossary cross-check, `useMemo` deps, sentiment tag translation, Intl.DateTimeFormat quirks, Korean plurals, data vs chrome translation, German typographic quote JSON escaping, test mocking requirements).

### Other gotchas

- **E2E allowlists must be registered.** Every `if (...) return;`-style suppression inside a Playwright spec (e.g. "this 404 is expected") needs (a) a matching entry in `e2e/ALLOWLIST.md` and (b) a `// ci-allowlist: CI-A<N>` comment marker above the code. Categories: `infra` (stack artefact, never fixable) / `by-design` (intentional correct behaviour) / `deferred-fix` (real bug, must link to 100days.md tracker). Prevents the e2e gate from accumulating silent suppressions nobody can audit six months later. See the register header for schema, retired IDs, and v2 tooling (validator + staleness gate, deferred until ~10 entries).
- **E2E tests: stale server on port 8150 gives wrong results** — `playwright.config.ts` uses `reuseExistingServer: !process.env.CI`. If a previous `bristlenose serve` is running locally on port 8150 (e.g. from `bristlenose serve trial-runs/project-ikea`), Playwright silently connects to it instead of starting the smoke-test fixture. This produces completely wrong measurements (353 quotes instead of 4). Always check `lsof -i :8150` before running E2E tests locally. In CI this can't happen (`reuseExistingServer: false`). The perf-gate spec has a server identity guard (`project_name === "Smoke Test"`) to catch this
- **E2E Node-side `fetch()` needs auth token explicitly** — Playwright's `extraHTTPHeaders` only applies to browser contexts (page navigation). Node-side `fetch()` in test fixtures gets 401'd without the bearer token. `e2e/fixtures/routes.ts` reads `_BRISTLENOSE_AUTH_TOKEN` from env and passes it via `authHeaders()`. Set the env var when running E2E tests: `_BRISTLENOSE_AUTH_TOKEN=test-token npx playwright test`
- **E2E: `waitForLoadState('networkidle')` is too fragile for SPAs** — fires after a 500ms idle window, which can beat deferred `useEffect` mounts on slow CI runners. Missed nodes look like "passed" tests and you measure the wrong state. In `perf-gate.spec.ts` the pattern is a `waitForPageReady()` helper that chains: `networkidle` → wait for `#bn-app-root` children → wait for `document.querySelectorAll('*').length` to be stable across two 200ms polls. Copy this pattern for any E2E spec that measures DOM state
- **E2E: in-browser `fetch()` in `page.evaluate` can silently 401** — a dropped auth token turns into 1ms latency and a ~50-byte error body. Without `res.ok` assertions this registers as "excellent latency" and sails past size thresholds. Always assert `res.ok` inside the evaluate (`expect(ok).toBe(true)`) AND add a sanity floor for payload sizes (`expect(sizeBytes).toBeGreaterThan(500_000)` when real size is ~1.6 MB). The server identity guard (first test, serial mode) catches most cases but defence-in-depth matters
- **Export JSON: always `ensure_ascii=True`** — `json.dumps(ensure_ascii=False)` does NOT escape `</script>` inside `<script>` tags. This is an XSS vector. The export endpoint embeds data as JSON in a script block — `ensure_ascii=True` escapes `<` as `\u003c`, preventing breakout. Fixed in v0.14.2
- **Export filenames: use `safe_filename()` not `slugify()`** — `slugify()` lowercases and hyphenates (`"Acme Research"` → `"acme-research"`). `safe_filename()` preserves spaces and case for human-readable Finder names. Both are in `bristlenose/utils/text.py`. Use `safe_filename()` for all export naming (zip folders, transcript files, clip files, download filenames)
- **Tests must not depend on local environment** — CI runs with no API keys, no Ollama, no local config. Always mock environment-dependent functions. The v0.6.7–v0.6.13 release failures were caused by tests that passed locally but failed in CI
- **PII redaction: `model_copy()` is shallow** — when redacting transcript segments, `seg.model_copy()` copies the Pydantic model but `words` (a list of `Word` objects) still references the original unredacted words. Always clear `clean_seg.words = []` after replacing `clean_seg.text`. Same caution applies to any field that might contain PII (`speaker_label`, `source_file`)
- **PII summary is a re-identification key** — `pii_summary.txt` lists every original PII value with timecodes. It lives in `.bristlenose/` (hidden), NOT in the shareable output root. Never move it back to the output directory
- **LLM call log is a re-identification key** — `<output_dir>/.bristlenose/llm-calls.jsonl` carries session ids, prompt shas, and timing fingerprints (sibling to `pii_summary.txt`). Never include in any export, support bundle, or shareable archive. Mode `0o600` + `O_NOFOLLOW` enforced by `bristlenose/llm/telemetry.py`. Kill switch: `BRISTLENOSE_LLM_TELEMETRY=0`
- **`pii_score_threshold` is the only PII config that's wired** — `pii_llm_pass` and `pii_custom_names` are declared in `config.py` but not used by `s07_pii_removal.py`. They emit runtime warnings when set. Don't write code that reads them without implementing the feature first
- **Presidio slow tests need spaCy model** — `@pytest.mark.slow` tests in `test_pii_audit.py` require `presidio-analyzer` + `spacy` + `en_core_web_lg` (400MB download). They're skipped in CI. Run with `pytest -m slow`
- The repo directory is `/Users/cassio/Code/bristlenose`
- `PipelineResult` references `PeopleFile` but is defined before it in `models.py` — resolved with `PipelineResult.model_rebuild()` after PeopleFile definition
- `format_finder_date()` in `utils/markdown.py` uses a local `import datetime as _dtmod` inside the function body because `from __future__ import annotations` makes the type hints string-only
- `render --clean` is accepted but ignored — render is always non-destructive
- `doctor.py` imports `platform` and `urllib` locally inside function bodies (not at module level). When testing, patch at stdlib level (`patch("platform.system")`) not module level
- `check_backend()` catches `Exception` (not just `ImportError`) for faster_whisper import — torch native libs can raise `OSError` on some machines
- **Never remove a worktree from inside it.** Always `cd /Users/cassio/Code/bristlenose` first, then `git worktree remove ...`. See `docs/BRANCHES.md`
- **Renaming the repo directory breaks the venv.** Fix: `find . -name __pycache__ -exec rm -rf {} +` then `.venv/bin/python -m pip install -e '.[dev]'`
- **Python 3.14's `ensurepip` is broken for `python -m venv` on some macOS installs.** If default `python3` points at 3.14 (brew-installed), `/new-feature` (or plain `python3 -m venv .venv`) fails with `ensurepip --upgrade --default-pip returned non-zero exit status 1`. Fix: use `python3.12 -m venv .venv` explicitly — 3.12 is what CI uses and what every other worktree uses. This will shake out when 3.14 tooling stabilises, but as of April 2026 it's a real papercut on fresh worktree setup
- **Stale `__pycache__` can serve old CSS after theme edits.** `bristlenose render` reads CSS files at runtime, but stale `.pyc` bytecode can interfere with the import chain. If theme CSS changes aren't appearing in the rendered output, run `find . -name __pycache__ -exec rm -rf {} +` before rendering. For daily dev, set `export PYTHONDONTWRITEBYTECODE=1` in your shell profile to prevent `.pyc` creation entirely
- **`Console(width=min(80, Console().width))`** — the `Console()` inside `min()` is a throwaway instance that auto-detects the real terminal width. This is the intended pattern; don't cache it
- **Homebrew tap repo must be named `homebrew-bristlenose`** (not `bristlenose-homebrew`). See `docs/design-homebrew-packaging.md`
- **Homebrew formula uses `post_install` pip to avoid dylib relinking failures.** See `docs/design-homebrew-packaging.md`
- **`BRISTLENOSE_FAKE_THUMBNAILS=1`** env var — layout testing only. Defined as `_FAKE_THUMBNAILS` in `bristlenose/stages/s12_render/dashboard.py`
- **Logging**: two independent knobs — `-v` controls terminal (WARNING/DEBUG), `BRISTLENOSE_LOG_LEVEL` env var controls log file (default INFO). Log file lives at `<output_dir>/.bristlenose/bristlenose.log` — **not** at `.bristlenose/bristlenose.log` relative to cwd. When grepping per-project logs, always prefix with the output dir. See `docs/design-logging.md`
- **LLM request latency**: every `LLMClient.analyze()` call emits one INFO line `llm_request | provider=X | model=Y | elapsed_ms=N | schema=Z` (added Apr 2026 for perf baselining). Greppable for median/p95 analysis — see `docs/design-perf-fossda-baseline.md` step 6. New providers get this automatically (wrapping is in the dispatcher, not per-provider)
- For React/TypeScript/frontend gotchas (routing, video player, stores, testing), see `frontend/CLAUDE.md`
- For pipeline runtime gotchas (resume, caching, llm_client lifecycle, metadata), see `bristlenose/stages/CLAUDE.md`
- For stage/pipeline gotchas (topic maps, transcripts, coverage, speaker codes), see `bristlenose/stages/CLAUDE.md`
- For JS/CSS/report gotchas (load order, modals, hidden quotes, toolbar), see `bristlenose/theme/CLAUDE.md`
- For LLM/provider gotchas (Azure, Ollama, provider registry, max_tokens), see `bristlenose/llm/CLAUDE.md`
- **Cloud-session `claude/...` branches: cherry-pick the docs, drop the staging dir.** When a Claude Code Cloud session (often phone-started) creates a `claude/<name>-XXXXX` branch, it tends to dump work into a staging dir like `_<name>-extract-me/` plus a design doc. The script/rules usually get installed to `~/bin/` + `~/.claude/` on the Mac during the session, so the staging dir is throwaway. Rescue pattern: `git checkout main && git checkout origin/claude/<name>-XXXXX -- docs/design-<thing>.md && git commit && git push && git branch -D … && git push origin --delete …`. Don't merge the whole branch — the staging dir doesn't belong in the tree. Also: the cloud session may leave the main repo dir checked out to the feature branch with stale "modifications" that are just main's progression — `git checkout -- <files>` is safe (vs-main diff is empty)
- **Release-to-PyPI workflow doesn't always fire on tag push via `--tags`** — `git push origin main --tags` triggers the branch-push workflows (CI, CodeQL, Snap) but the tag-driven `Release to PyPI` workflow can silently miss the event. Workaround: `git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>` — same SHA, fresh trigger, semantic no-op. Observed v0.15.0 (26 Apr 2026); root cause appears to be GitHub Actions debouncing tag-push events bundled with branch-push events. Future fix: add `workflow_dispatch:` to `release.yml` so it can be re-triggered without tag surgery
- **Subprocess signal-handling tests: poll the events file, don't `proc.wait`** — `tests/test_run_lifecycle.py` originally used `proc.wait(timeout=15)` after sending SIGINT, then asserted on the cancel event. Failed on Python 3.10 / ubuntu-latest only — slow runner, the lifecycle's `KeyboardInterrupt` catch + `Cause` build + fsync took longer than 15 s under matrix CPU contention. Pattern that works: `_wait_for_event(f, predicate, timeout=30)` polling the events file, with `proc.wait(timeout=10)` only in the `finally` for cleanup. Monotonic against runner load. See `tests/test_run_lifecycle.py:_wait_for_event`

## Reference docs (read when working in these areas)

**Must-read before writing user-facing text:**
- `docs/glossary.md` — terminology + tone guide
- `docs/platform-text-map.md` — shared/desktop/CLI text forking, `dt()`/`ct()` inventory

**Must-read before touching tag suggestion, telemetry, or data governance:**
- `docs/methodology/` — canonical methodology docs. Treat as authoritative: when code and doc disagree, the doc is the spec and the code is wrong.
  - `tag-rejections-are-great.md` — rejection-telemetry theory, alpha experiments, six-field data model, ten-year ratchet endgame
  - `consent-gradient.md` — Level 0–3 data-governance gradient, sensitivity model, consent UX principles, sequencing discipline
  - `framework-arc-quarterly-review.md` — quarterly review template and the long-arc commitments it reviews against

**Sibling CLAUDE.md files:** `frontend/`, `bristlenose/theme/`, `bristlenose/stages/`, `bristlenose/llm/`, `bristlenose/server/`, `desktop/`

**Frontend / UI:**
- `bristlenose/theme/js/MODULES.md`, `bristlenose/theme/CSS-REFERENCE.md` — JS + CSS component reference
- `docs/design-sidebar-playground.md` — 6-column grid, overlay, drag-resize, minimap, dev playground
- `docs/design-responsive-layout.md` — quote grid, density, breakpoints
- `docs/design-react-migration.md` — active migration plan
- `docs/design-react-component-library.md` — 16 primitives
- `docs/design-minimap.md`, `docs/design-inspector-panel.md`, `docs/design-finding-weight.md`

**Pipeline / backend:**
- `docs/design-pipeline-resilience.md` — manifest, event sourcing, resume, provenance
- `docs/design-platform-transcripts.md`, `docs/design-transcript-coverage.md`
- `docs/design-speaker-splitting.md`, `docs/design-speaker-role-detection.md`
- `docs/design-speaker-editing.md`, `docs/design-transcript-editing.md`, `docs/design-transcript-speaker-editing-roadmap.md`
- `docs/design-multi-project.md` — scope rules (instance vs project tables)
- `docs/design-session-management.md`, `docs/design-serve-milestone-1.md`
- `docs/design-logging.md`

**Export:**
- `docs/design-export-html.md` (anonymisation), `docs/design-export-quotes.md` (CSV/XLS), `docs/design-export-clips.md`, `docs/design-export-slides.md`, `docs/design-miro-bridge.md`, `docs/design-footer-feedback-react.md`

**Desktop:**
- `docs/design-desktop-app.md`, `docs/design-desktop-security-audit.md`
- `docs/design-modularity.md` — **canonical cross-channel component strategy** (CLI + macOS, Background Assets, no-fork principle, trickle-to-full-capability)
- `docs/design-desktop-python-runtime.md` — Mac sidecar mechanics (to be written as Track C C0 output)
- `docs/private/sprint2-tracks.md` — Track A (sandbox), B (MVP UX), C (sidecar bundling + signing, C0–C5)
- `docs/private/road-to-alpha.md` — 14 checkpoints to TestFlight
- `docs/design-project-sidebar.md`, `docs/design-wkwebview-messaging.md`
- `docs/design-desktop-menu-actions.md`, `docs/design-desktop-settings.md`

**Analysis / research methodology:**
- `docs/design-research-methodology.md` — read before changing prompts or analysis logic
- `docs/academic-sources.html` — theoretical foundations
- `docs/design-analysis-future.md`, `docs/design-quote-sequences.md`, `docs/design-dashboard-stats.md`, `docs/design-signal-elaboration.md`

**i18n:** `docs/design-i18n.md` — terminology table, implementation gotchas

**Codebook:** `docs/design-codebook-island.md`, `docs/design-moderator-question-pill.md`

**HTML report / dashboard / auth:**
- `docs/design-html-report.md`, `docs/design-dashboard-navigation.md`
- `docs/design-sentiment-charts.md`, `docs/design-badge-action-pill.md`
- `docs/design-react-islands.md`, `docs/design-autocode.md`

**Ops / release:**
- `docs/release.md`, `docs/file-map.md`, `CONTRIBUTING.md`, `INSTALL.md`, `SECURITY.md`
- `docs/design-ci.md`, `docs/design-test-strategy.md`, `docs/design-playwright-testing.md`
- `docs/design-doctor-and-snap.md`, `docs/design-homebrew-packaging.md`
- `docs/design-cli-improvements.md`, `docs/design-llm-providers.md`, `docs/design-performance.md`
- `docs/design-decisions.md` (why), `docs/design-reactive-ui.md` (partially superseded)
- `docs/ROADMAP.md`

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
test -f .claude/setup-incomplete && cat .claude/setup-incomplete
```

If `.claude/setup-incomplete` exists, the worktree's environment isn't fully prepped (`/new-feature` either aborted or hasn't finished). **Do not start real work until the user re-runs `/new-feature` or completes setup manually** (frontend build, venv, smoke test). Tell the user the sentinel is present and wait. The file is removed only when the smoke test passes — its absence means the env is ready.

If the user starts asking about a feature without specifying, **remind them to check** which worktree they want to work in. Never check out a feature branch inside the main `bristlenose/` directory — use the worktree instead. A `PreToolUse` hook in `.claude/settings.json` blocks `git checkout`/`git switch` to feature branches when CWD is the main repo.

**Skills for branch lifecycle:**
- **`/new-feature <name>`** — creates branch, worktree, venv, pushes to origin, updates `docs/BRANCHES.md`, pauses for Finder labelling
- **`/close-branch <name>`** — archives a merged branch: drops a `_Stale - Merged by Claude DD-Mon-YY.txt` marker in the worktree directory, detaches worktree from git (directory stays on disk), asks before deleting local/remote branches, updates `docs/BRANCHES.md`
- **Reverting a merge:** `git revert -m 1 <merge-commit-hash>` — creates a new commit that undoes the merge. The worktree directory is still on disk for further work

**If `/new-feature` cannot be invoked** (e.g. `disable-model-invocation` blocks auto-invocation), read `.claude/skills/new-feature/SKILL.md` and follow every step manually. Do not improvise — the skill contains critical setup steps (venv with `.[dev,serve]` extras, symlinks, BRANCHES.md entry) that are easy to miss.

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
- **Human QA after each task**: when you finish a task, suggest only the checks a human needs to do that automated tests can't cover (visual regression, browser interaction, UX feel). Skip this for pure data/logic work where unit tests are sufficient. Include copy-pasteable commands to make it easy (e.g. server start command, URL to open). Don't duplicate what pytest already covers
- **NEVER use Claude Code preview tools (`preview_start`, `preview_screenshot`, `preview_snapshot`, `preview_eval`, etc.) for QA.** They consistently fail for Bristlenose — wrong port, missing Vite HMR, white-on-white rendering, incomplete React mount. Every attempt wastes time. Bristlenose needs the full stack (Vite dev server on 5173 + FastAPI serve on 8150) running together. For QA, tell the user to run the full stack in their own browser:
  ```
  .venv/bin/bristlenose serve --dev trial-runs/project-ikea
  ```
  `--dev` auto-starts Vite on :5173 as a subprocess (cleaned up on exit). Then open http://localhost:8150/report/. For worktrees: use the port from `.claude/launch.json`

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

When the user signals end of session, **run `/end-session`** — the skill handles verify, document, commit, and close-out. See `.claude/skills/end-session/SKILL.md` for the full checklist.

## Current status (v0.15.0, Apr 2026)

Core pipeline published to PyPI + Homebrew + Snap. v0.15.0 lands **pipeline resilience Phase 1f / 4a-pre** — append-only `pipeline-events.jsonl` with structured `Cause` (10 categories), honest cost estimates, stranded-run reconciliation, desktop `EventLogReader`. Replaces the old "infer from manifest" path that mis-classified interrupted runs as `.ready`. Earlier product feature: **Video clip extraction** (FFmpeg stream-copy, async job, `ClipBackend` Protocol for future AVFoundation), 6 languages (en, es, fr, de, ko, ja). Inspector panel, codebook sidebar, finding flags, Settings + Help modals with shared ModalNav. Static render formally deprecated. ~2328 Python tests, ~1265 Vitest tests, 90 Swift tests. React migration complete (Steps 1–10). See `CHANGELOG.md` and git log for full history.

**Next up:** See `TODO.md` for full task list.
