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

Desktop app: `desktop/` — SwiftUI macOS shell. See `docs/design-desktop-app.md`.

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
- **Gitignored (private)**: `docs/private/`, `trial-runs/` — contain names, contacts, and value judgements not suitable for a public repo

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

- **Locale files live in `bristlenose/locales/` only** — `frontend/src/locales/` was deleted. The frontend imports from the canonical location via Vite alias `@locales`. Don't create locale files in the frontend tree
- **`I18n.swift` reads the same JSON** — the desktop app's `I18n` class loads from `bristlenose/locales/` at runtime. Dotted key lookup: `i18n.t("desktop.menu.file.print")`. Falls back English → raw key
- **SwiftUI `CommandMenu` titles can't use runtime strings** — `CommandMenu("Project")` uses `LocalizedStringKey` (`.lproj` bundles). Menu titles stay in English; only items inside are translated. See `docs/design-i18n.md`
- **Toolbar `_short` keys** — `common.nav.codebookShort` exists for languages where the full label overflows the segmented control (es: "Códigos" instead of "Libro de códigos"). `Tab.localizedLabel()` checks `_short` first
- **Apple glossary cross-check is mandatory** before shipping a new language — use [applelocalization.com](https://applelocalization.com/) or the macOS keyboard shortcuts page in the target locale. See `docs/design-i18n.md` for the full process and the Spanish cross-check results
- **`useTranslation()` is the hook; `i18n.t()` is the direct import** — use the hook inside React components, use `import i18n from "../i18n"` + `i18n.t()` in stores, announce utilities, and other non-component code (e.g. `QuotesContext.tsx`, `AppLayout.tsx` route announcements)
- **`useMemo` deps for translated arrays** — `t` function identity doesn't change on locale switch. Use `[t, i18n.language]` as dependency, or skip `useMemo` entirely for small arrays (2–5 items). See `ViewSwitcher.tsx` (inline) vs `HelpModal.tsx` (useMemo with language dep)
- **`i18n/index.ts` initialises test-setup** — `frontend/src/test-setup.ts` imports `"./i18n"` so all tests get English translations by default. `t("nav.project")` returns `"Project"` in tests — no test rewrites needed for i18n wiring
- **Sentiment tag translation in Badge** — `Badge.tsx` looks up `enums:sentiment.${text}` when `sentiment` prop is truthy. This translates API-returned lowercase sentiment names ("frustration") to locale-correct labels ("Frustration" / "Verwirrung"). Tests must expect capitalised forms
- **Built-in codebook groups translate client-side** — sentiment group (`colour_set === "sentiment"`) and uncategorised group (`name === "Uncategorised"`) have their names/subtitles translated in `CodebookPanel.tsx` using locale keys. Other codebook names are user data and stay untranslated
- **`format.ts` uses `Intl.DateTimeFormat`** — `formatFinderDate` and `formatCompactDate` accept an optional `locale` param. Callers pass `i18n.language`. Internally, any `en*` locale (including bare `"en"` from i18next and `"en-US"` from jsdom in tests) is mapped to `"en-GB"` to preserve day-month order ("12 Feb" not "Feb 12"). Non-English locales pass through unchanged. `formatFinderDate` uses `Intl.RelativeTimeFormat` for "today"/"yesterday"
- **`<html lang>` tracking** — `i18n.on("languageChanged")` in `i18n/index.ts` sets `document.documentElement.lang`. Required for screen reader pronunciation
- **Korean has no plural forms** — only `_other` keys needed in locale files (no `_one`). i18next CLDR rules handle this automatically
- **New keys must go in all 6 locale files** — en, es, fr, de, ko, ja. Every `t("key")` call needs a corresponding entry in each. If using `dt()`, the desktop override must also go in all 6 `desktop.json` files. Use machine translation for initial pass, flag for human review
- **Data-level vs chrome-level translation** — UI chrome (buttons, headings, labels) translates via `t()`. API data (codebook names, quote text, section labels) stays in the original language. Exceptions: sentiment group name/subtitle and uncategorised group are server constants that get client-side translation
- **Platform text forking** — `dt(t, key)` checks `desktop:` namespace first (falls back to base key). `ct(t, key)` returns `null` on desktop (hides CLI-only text). Both in `frontend/src/utils/platformTranslation.ts`. Desktop namespace loaded conditionally in `i18n/index.ts` when `data-platform="desktop"` is set. See `docs/platform-text-map.md` for the full inventory and decision tree
- **German typographic quotes break JSON** — `„"` (U+201E / U+201C) look like JSON string delimiters to parsers. Escape as `\u201e` / `\u201c` in locale JSON files. Caught in `de/desktop.json` during platform text fork work
- **Tests that mock `../utils/platform` must include `isDesktop`** — `HelpModal.test.tsx` mocked only `isMac`, which broke when `ContributingSection` started importing `dt()` (which imports `isDesktop`). Always mock `{ isMac, isDesktop, _resetPlatformCache }` together

### Other gotchas

- **Export JSON: always `ensure_ascii=True`** — `json.dumps(ensure_ascii=False)` does NOT escape `</script>` inside `<script>` tags. This is an XSS vector. The export endpoint embeds data as JSON in a script block — `ensure_ascii=True` escapes `<` as `\u003c`, preventing breakout. Fixed in v0.14.2
- **Export filenames: use `safe_filename()` not `slugify()`** — `slugify()` lowercases and hyphenates (`"Acme Research"` → `"acme-research"`). `safe_filename()` preserves spaces and case for human-readable Finder names. Both are in `bristlenose/utils/text.py`. Use `safe_filename()` for all export naming (zip folders, transcript files, clip files, download filenames)
- **Tests must not depend on local environment** — CI runs with no API keys, no Ollama, no local config. Always mock environment-dependent functions. The v0.6.7–v0.6.13 release failures were caused by tests that passed locally but failed in CI
- **PII redaction: `model_copy()` is shallow** — when redacting transcript segments, `seg.model_copy()` copies the Pydantic model but `words` (a list of `Word` objects) still references the original unredacted words. Always clear `clean_seg.words = []` after replacing `clean_seg.text`. Same caution applies to any field that might contain PII (`speaker_label`, `source_file`)
- **PII summary is a re-identification key** — `pii_summary.txt` lists every original PII value with timecodes. It lives in `.bristlenose/` (hidden), NOT in the shareable output root. Never move it back to the output directory
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
- **Stale `__pycache__` can serve old CSS after theme edits.** `bristlenose render` reads CSS files at runtime, but stale `.pyc` bytecode can interfere with the import chain. If theme CSS changes aren't appearing in the rendered output, run `find . -name __pycache__ -exec rm -rf {} +` before rendering. For daily dev, set `export PYTHONDONTWRITEBYTECODE=1` in your shell profile to prevent `.pyc` creation entirely
- **`Console(width=min(80, Console().width))`** — the `Console()` inside `min()` is a throwaway instance that auto-detects the real terminal width. This is the intended pattern; don't cache it
- **Homebrew tap repo must be named `homebrew-bristlenose`** (not `bristlenose-homebrew`). See `docs/design-homebrew-packaging.md`
- **Homebrew formula uses `post_install` pip to avoid dylib relinking failures.** See `docs/design-homebrew-packaging.md`
- **`BRISTLENOSE_FAKE_THUMBNAILS=1`** env var — layout testing only. Defined as `_FAKE_THUMBNAILS` in `bristlenose/stages/s12_render/dashboard.py`
- **Logging**: two independent knobs — `-v` controls terminal (WARNING/DEBUG), `BRISTLENOSE_LOG_LEVEL` env var controls log file (default INFO). See `docs/design-logging.md`
- For React/TypeScript/frontend gotchas (routing, video player, stores, testing), see `frontend/CLAUDE.md`
- For pipeline runtime gotchas (resume, caching, llm_client lifecycle, metadata), see `bristlenose/stages/CLAUDE.md`
- For stage/pipeline gotchas (topic maps, transcripts, coverage, speaker codes), see `bristlenose/stages/CLAUDE.md`
- For JS/CSS/report gotchas (load order, modals, hidden quotes, toolbar), see `bristlenose/theme/CLAUDE.md`
- For LLM/provider gotchas (Azure, Ollama, provider registry, max_tokens), see `bristlenose/llm/CLAUDE.md`

## Reference docs (read when working in these areas)

- **Terminology glossary + tone guide** (canonical vocabulary, forbidden alternatives, spelling rules, voice): `docs/glossary.md` — **read this before writing any user-facing text**
- **Platform text map** (which text is shared/desktop-only/CLI-only/forked, `dt()`/`ct()` inventory, decision tree): `docs/platform-text-map.md` — **read this before adding help text**
- **Design decisions** (why choices were made, alternatives considered): `docs/design-decisions.md`
- **Export: HTML report + cross-cutting concerns** (anonymisation matrix, shared infra, audit): `docs/design-export-html.md`
- **Export: CSV/XLS quotes** (11-column schema, selection logic, export dropdown): `docs/design-export-quotes.md`
- **Export: video clips** (FFmpeg/AVFoundation, naming, async toast): `docs/design-export-clips.md`
- **Export: Miro bridge** (OAuth PKCE, board creation, layout — post-beta): `docs/design-miro-bridge.md`
- **Export: original monolith** (superseded, kept for git history): `docs/design-export-sharing.md`
- **Export dropdown + quote slides** (per-quote copy, scope→format cascade, .pptx format): `docs/design-export-slides.md`
- **HTML report / people file / transcript pages**: `docs/design-html-report.md`
- **Frontend / React / TypeScript / Vite**: `frontend/CLAUDE.md`
- **Theme / dark mode / CSS conventions / gotchas**: `bristlenose/theme/CLAUDE.md`
- **JS module API reference**: `bristlenose/theme/js/MODULES.md`
- **CSS component reference**: `bristlenose/theme/CSS-REFERENCE.md`
- **Responsive layout** (quote grid, density setting, breakpoints): `docs/design-responsive-layout.md` — content-level responsiveness. See `docs/design-sidebar-playground.md` for chrome-level (sidebar modes)
- **Sidebar layout & responsive playground** (6-column grid, overlay, drag-resize, minimap, dev playground): `docs/design-sidebar-playground.md` — architecture, file map, token reference, QA checklist. **Read this before working on sidebar layout, overlay behaviour, or playground features**
- **Pipeline stages / transcript format / output structure**: `bristlenose/stages/CLAUDE.md`
- **LLM providers / credentials / concurrency**: `bristlenose/llm/CLAUDE.md`
- **File map** (what lives where): `docs/file-map.md`
- **Release process / CI / secrets**: `docs/release.md`
- **Design system / contributing**: `CONTRIBUTING.md`
- **Doctor command + Snap packaging design**: `docs/design-doctor-and-snap.md`
- **Homebrew formula packaging** (dylib relinking workaround, alternatives, automation): `docs/design-homebrew-packaging.md`
- **Platform transcript ingestion**: `docs/design-platform-transcripts.md`
- **Transcript coverage feature**: `docs/design-transcript-coverage.md`
- **CLI improvements**: `docs/design-cli-improvements.md`
- **LLM provider roadmap**: `docs/design-llm-providers.md`
- **React migration plan** (vanilla JS shell → full SPA, 10-step sequence): `docs/design-react-migration.md` — **the active plan.** Read this before working on serve-mode UI migration
- **Reactive UI architecture / framework / migration** (partially superseded): `docs/design-reactive-ui.md` — framework choice, business risk, file:// audit remain valid reference
- **Performance audit / optimisation decisions**: `docs/design-performance.md`
- **Research methodology** (quote selection, sentiment taxonomy, clustering/theming rationale): `docs/design-research-methodology.md` — single source of truth for analytical decisions. **Read this before changing prompts or analysis logic.**
- **Academic sources for analysis categories**: `docs/academic-sources.html` — theoretical foundations (emotion science, UX research, trust/credibility) behind quote tagging and sentiment analysis. **Update this file when investigating theories behind any Bristlenose features.**
- **Analysis page** (signal concentration, metrics, rendering): `docs/BRANCHES.md` → `analysis` section — architecture, design decisions, file list, test coverage
- **Analysis page future** (two-pane vision, grid-as-selector, user-tag grid, backlog): `docs/design-analysis-future.md`
- **Inspector panel** (bottom heatmap panel, DevTools metaphor, drag-resize, card↔matrix sync): `docs/design-inspector-panel.md` — design exploration (3 mockup iterations), interaction spec, implementation prompt. **Read this before working on the analysis tab inspector panel**
- **Finding weight** (signal direction, valence clarity, tag interpretability tiers, finding archetypes): `docs/design-finding-weight.md` — problem-space exploration for surfacing wins vs problems vs patterns in Analysis tab
- **Quote sequences** (consecutive quote detection, segment ordinals, threshold tuning): `docs/design-quote-sequences.md`
- **Dashboard stats** (inventory of unused pipeline data, improvement priorities): `docs/design-dashboard-stats.md`
- **Logging** (persistent log file, two-knob system, instrumentation tiers): `docs/design-logging.md` — architecture, tier 1 implementation plan, backlog. **Read this before adding log lines**
- **Minimap** (parallax scroll, stress-test math, interaction patterns): `docs/design-minimap.md` — VS Code-style abstract overview for Quotes tab, grid column 4 (between center and tag sidebar), scrollbar offset, parallax derivation
- **Pipeline resilience / crash recovery / data integrity**: `docs/design-pipeline-resilience.md` — manifest, event sourcing, incremental re-runs, provenance. **Read this before working on pipeline state tracking, resume, or data validation**
- **Server / data API / serve mode**: `bristlenose/server/CLAUDE.md`
- **Footer feedback restore (React serve/export)**: `docs/design-footer-feedback-react.md`
- **React component library** (16 primitives, complete): `docs/design-react-component-library.md` — primitive dictionary, coverage matrix, CSS alignment. All 16 primitives shipped
- **CI architecture** (job structure, matrix strategy, informational vs blocking, artifacts, maintenance): `docs/design-ci.md`
- **Testing & CI strategy** (gap audit, Playwright plan, visual regression, `data-testid` convention): `docs/design-test-strategy.md`
- **Playwright E2E tests** (layers 1–3 implemented, layers 4–5 planned, output options, CI integration): `docs/design-playwright-testing.md`
- **Installation guide**: `INSTALL.md` — detailed per-platform install instructions for non-technical users
- **Desktop app** (macOS, SwiftUI, PyInstaller sidecar, .dmg distribution): `docs/design-desktop-app.md` — vision, PRD, stack rationale, user flow, open questions. **Read this before working in `desktop/`**
- **Desktop app security audit** (WKWebView, sidecar, Keychain, sandbox, DASVS, Apple guidelines): `docs/design-desktop-security-audit.md` — challenges, opportunities, attack surface review, relevant standards. Items prioritised into `docs/private/100days.md`
- **WKWebView cross-view messaging** (BroadcastChannel, data store sharing, spike results): `docs/design-wkwebview-messaging.md` — validated pattern for multi-WKWebView communication. **Read this before adding a second WKWebView to the desktop app**
- **Multi-project awareness** (project index, person identity, lifecycle, assumptions audit, scope rules): `docs/design-multi-project.md` — data model future-proofing, single-project assumption inventory. Scope rules enforced in `bristlenose/server/CLAUDE.md`. **Read this before adding new DB tables or hardcoding project IDs**
- **Project sidebar** (macOS desktop sidebar UX, menus, rename, drag-drop, delete/bin, 5-phase plan): `docs/design-project-sidebar.md` — Mail-style sidebar, Recently Deleted bin, inline rename, system selection highlight. **Read this before working on desktop multi-project UI**
- **Session management** (re-import, session enable/disable, quarantine, pipeline re-run): `docs/design-session-management.md`
- **Serve mode milestone 1** (domain schema, importer, sessions API): `docs/design-serve-milestone-1.md`
- **Internationalisation** (codebook/sentiment translation strategy, UI chrome terminology research, mixed-language interviews): `docs/design-i18n.md` — terminology table sourced from ATLAS.ti/MAXQDA/NVivo localized UIs and academic QDA literature. **Read this before working on i18n or translation**
- **Codebook island** (migration audit, API design, drag-drop decisions): `docs/design-codebook-island.md`
- **Moderator question pill** (hover-triggered context reveal, interaction design, file map): `docs/design-moderator-question-pill.md`
- **Signal elaboration** (interpretive names + one-sentence summaries for framework signal cards, pattern types, generation algorithm): `docs/design-signal-elaboration.md`
- **Speaker splitting** (LLM pre-pass for single-speaker transcripts): `docs/design-speaker-splitting.md`
- **Speaker role detection** (generalised heuristic + prompt for non-UXR formats): `docs/design-speaker-role-detection.md`
- **Speaker editing** (name, reassign, split, merge — four transcript operations): `docs/design-speaker-editing.md` — Dovetail-style in-context editing. **Read this before working on transcript speaker UI**
- **Transcript editing** (future — section strike, text correction, prior art, data model): `docs/design-transcript-editing.md` — two-operation approach (junk deletion + word correction), prior art from 7 tools, edit history analysis. **Read this before working on transcript text editing**
- **Transcript & speaker editing roadmap** (11-layer work breakdown): `docs/design-transcript-speaker-editing-roadmap.md` — dependency graph, priority order, page responsibility model
- **Security & privacy**: `SECURITY.md` — local-first design, credential storage, PII redaction, anonymisation boundary, vulnerability reporting
- **Product roadmap**: `docs/ROADMAP.md`

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

## Current status (v0.14.4, Apr 2026)

Core pipeline published to PyPI + Homebrew + Snap. Latest: **Video clip extraction** (FFmpeg stream-copy, async job, `ClipBackend` Protocol for future AVFoundation), 6 languages (en, es, fr, de, ko, ja). Inspector panel, codebook sidebar, finding flags, Settings + Help modals with shared ModalNav. Static render formally deprecated. ~2090 Python tests, ~1265 Vitest tests. React migration complete (Steps 1–10). See `CHANGELOG.md` and git log for full history.

**Next up:** See `TODO.md` for full task list.
