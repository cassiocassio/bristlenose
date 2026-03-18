# Changelog

All notable changes to Bristlenose are documented here. See also the [README](README.md) for the latest releases.

**0.13.8** — _18 Mar 2026_

- **Help modal** — replaces the About page route and keyboard shortcut overlay with a single ModalNav-based sidebar-nav modal. Seven sections: Help (stub landing), Shortcuts (keyboard grid with platform-aware badges), Signals, Codebook, and About disclosure group (Developer, Design, Contributing). Triggered by ⓘ navbar icon (opens to Help) or `?` key (opens to Shortcuts). `/report/about/` URL gracefully redirects to `/report/`
- **ModalNav genericised** — extracted `modal-nav.css` organism from `settings-modal.css`. Generic shell (`.modal-nav-shell`, `.modal-nav-overlay` transition) with parameterised sizing per consumer. Settings and Help both use the same ModalNav component with their own sizing classes. Fixed: unique `titleId` per modal (ARIA), removed incorrect `role="navigation"` from `<ul>`

**0.13.7** — _16 Mar 2026_

- **Spanish locale** — machine-translated all 102 UI strings across 8 locale files (3 frontend, 5 backend). Covers navigation, settings, enums, CLI messages, doctor, pipeline progress, and server errors. Ready for native-speaker review and polish

**0.13.6** — _16 Mar 2026_

- **Single tag focus mode** — click a tag count in the sidebar to solo that tag (mixing-desk style). All other sidebar controls dim to 50%; the focused tag row stays at full brightness. "You are here" blue wash highlight matches the TOC sidebar's active link style. Click again or press Escape to exit and restore the previous tag filter
- **Fix circular dependency crash** — `SidebarStore` importing `setTagFilter` from `QuotesContext` at module scope created a circular dependency that caused "Cannot access uninitialized variable" in production builds. Refactored to pass `setTagFilter` as a callback parameter
- **Used/unused tag filter toggle** — "Used" link in tag sidebar header filters to show only tags that appear on at least one quote, hiding zero-count tags for a cleaner view
- **Sidebar tag click-to-assign** — select quotes then click a tag badge in the sidebar to apply that tag to all selected quotes. Flash animation on each newly tagged quote, toast notification when tagged quotes are off-screen
- **Tier 1 logging instrumentation** — persistent log file with stage-level timing, session counts, and LLM token usage. PII hardening: file paths, API keys, and participant names are scrubbed from log output
- **Multilingual UI infrastructure** — i18next integration with `useTranslation` hook, Python i18n module, browser language auto-detection on first visit. Translation keys for all user-facing strings (not yet translated)
- **Responsive signal cards** — signal framework cards use CSS grid layout with narrow-screen stacking for readable display on mobile viewports
- **Cache `system_profiler` results** — 24-hour TTL cache for macOS `system_profiler` output, avoiding the slow 2-3s startup penalty on every `bristlenose doctor` or `bristlenose run`

**0.13.4** — _14 Mar 2026_

- **Fix import FK constraint** — delete `ProposedTag` rows (AutoCode proposals) before removing stale quotes during re-import, preventing `FOREIGN KEY constraint failed` errors on `bristlenose serve` startup

**0.13.3** — _14 Mar 2026_

- **Help modal polish** — platform-aware keyboard shortcuts (⌘ on Mac, Ctrl on Windows/Linux), sans-serif keycaps with deeper shadow and min-width for visual consistency, typography tokens and spacing overhaul, entrance animation, dark-mode keyboard styling. Phase 3 adds custom tooltips with keyboard shortcut badges across the UI
- **Bulk actions on multi-selection** — star, hide, and tag operations now respect click-based multi-selection: clicking a starred quote in a selection unstars all, clicking an unstarred one stars all. Shift+click range selection no longer triggers browser text selection. Tag commits apply to all selected quotes
- **Sidebar animations** — push animation on keyboard shortcuts (`[`, `]`, `\`) and click, 4× faster open/close transitions, two-row header layout. Rail drag-to-open with 60px commit threshold and pointer-tracking overlay. Drag handle hover-intent (80ms delay) filters casual mouse traversal
- **TOC overlay clip-path animation** — smooth reveal/hide for the table-of-contents overlay panel, with playground toggle for overlay style
- **Scroll spy Safari fix** — two-phase click-intent override (immune phase 0–600ms, sticky phase >600ms) resolves Safari's smooth-scroll `getBoundingClientRect()` timing glitch. Minimap reordered to grid column 4 (between center and tag sidebar)
- **Pipeline error display** — failed stages show red ✗, partially successful stages show yellow ⚠ in CLI output
- **Speaker badge fix** — correct indent when speaker badge wraps to a new line
- **Scroll-margin fix** — section headings in React SPA now scroll to the correct position, accounting for the sticky navbar
- **CLAUDE.md refactor** — extracted frontend, pipeline, and LLM gotchas into dedicated child files (`frontend/CLAUDE.md`, `bristlenose/stages/CLAUDE.md`, `bristlenose/llm/CLAUDE.md`), keeping the root file focused on architecture and conventions

**0.13.2** — _11 Mar 2026_

- **Render refactor** — broke up the 2,903-line `render_html.py` monolith into `bristlenose/stages/s12_render/` package with 8 focused submodules: `theme_assets.py` (CSS/JS loaders, Jinja2 env), `html_helpers.py` (escaping, timecodes, badges, video map), `quote_format.py` (quote HTML, badges), `sentiment.py` (sparklines, rewatch/friction), `dashboard.py` (project tab, featured quotes, coverage), `transcript_pages.py` (standalone + inline transcripts), `standalone_pages.py` (codebook, analysis), `report.py` (orchestrator). No behaviour change — same HTML output, all 1,872 tests pass
- **Static render deprecated** — `render_html()` now emits `DeprecationWarning`. `bristlenose serve` is the canonical path; `bristlenose render` still works but is frozen
- Updated ~99 documentation references across 34 files to point to the new submodules

**0.13.1** — _10 Mar 2026_

- **Responsive layout playground** — dev-only responsive design tool (`--dev` mode) with device presets, type scale previews, and a HUD overlay for testing quote grid layouts across breakpoints. FAB toggle button, `PlaygroundStore` with `useSyncExternalStore`
- **Sidebar TOC overlay mode** — left sidebar TOC switches to hover-triggered overlay on narrower viewports. `useTocOverlay` hook manages open/close transitions with mouse-enter/leave
- **Minimap component** — document minimap for the quotes page, showing a scaled overview of quote sections with viewport indicator
- **Responsive quote grid CSS** — CSS-only responsive grid for quote cards, adapting column count to available width

**0.13.0** — _10 Mar 2026_

- **Codebook-aware tag autocomplete** — TagInput now groups suggestions by codebook section with colour-coded pills and section headers, matching the IDE-style autocomplete pattern. Highlighted suggestion takes priority over ghost text. Active pill uses white text, z-index fix prevents clipping under sidebar, deeper dropdown accommodates more suggestions
- **Sentiment tags unified into codebook framework** — sentiment tags (positive, negative, neutral, mixed) are now a proper codebook framework (`sentiment.yaml`) imported through the standard codebook system, replacing the ad-hoc UXR sentiment group. Tag colours use the design-system colour sets. Importer handles migration of existing sentiment tags to the new framework
- **Tag provenance tracking** — `QuoteTag.source` column tracks `"human"` (manual adds) vs `"autocode"` (LLM-suggested). Provenance is preserved across bulk tag operations (snapshot before delete, restore on re-insert). Exposed in the quotes API via `TagResponse.source`. Case-insensitive duplicate guard prevents adding the same tag twice
- **Hidden-group tag UX** — eye-toggled codebook groups show a grey closed-eye icon in TagInput autocomplete. Accepting a tag from a hidden group auto-unhides the group so the badge is immediately visible. `allTagNames` prop prevents invisible re-adds from hidden groups
- **Quick-repeat tag shortcut** (`r`) — press `r` on a focused quote to re-apply the last-used tag without opening the tag input. Shown in help modal
- **Context expansion fix** — fixed infinite re-render loop when clicking the up chevron to expand context on a quote card. `FocusContext` and `QuotesContext` updated to break the render cycle
- **Doctor offers MLX install on Apple Silicon** — `bristlenose doctor` now detects Apple Silicon Macs without MLX and offers interactive installation for GPU-accelerated transcription. Install helpers use `sys.executable` to target the correct Python. Skipped in non-interactive contexts
- **Sidebar UX accessibility** — focus management, ARIA attributes, and `prefers-reduced-motion` support for sidebar drag-resize animations
- **Dashboard Cmd+click fix** — stat cards now use `<a>` elements with real `href` attributes, so Cmd+click opens in a new tab as expected. Normal clicks still use React Router navigation

**0.12.2** — _2 Mar 2026_

- **Footer feedback restored in React serve mode** — the footer once again exposes both "Report a bug" and "Feedback" in the served React app. "Feedback" now opens a React-native modal (sentiment picker + optional message), matching the legacy flow rather than reusing the keyboard-shortcuts help modal
- **Feedback submit + fallback parity** — feedback sends `{version, rating, message}` JSON to the configured feedback endpoint when available over HTTP(S). On failure (or non-HTTP contexts), it falls back to copying a plain-text feedback payload to the clipboard and shows toast guidance
- **Health API contract extended** — `GET /api/health` now returns `links.github_issues_url` and `feedback.{enabled,url}` alongside existing `status` and `version` keys (unchanged)
- **Export parity with serve mode** — exported reports embed the same `health.links` + `health.feedback` shape so footer behavior is consistent between serve and export
- **Config via environment variables** — optional server-side overrides: `BRISTLENOSE_GITHUB_ISSUES_URL`, `BRISTLENOSE_FEEDBACK_ENABLED`, `BRISTLENOSE_FEEDBACK_URL`

**0.12.1** — _1 Mar 2026_

- **Word-level transcript highlighting** — during video playback, individual words in the transcript highlight in sync with the audio, karaoke-style. Whisper captures per-word start/end timestamps during transcription; these flow through the pipeline (`session_segments.json` → SQLite `words_json` → transcript API `words` field) and render as `<span class="transcript-word">` elements with `data-start`/`data-end` attributes. `PlayerContext.updateGlow()` scans word spans at 4 Hz and toggles `.bn-word-active` on the current word. Three-tier rendering fallback: word spans (Whisper sessions) → `html_text` with `<mark>` quote highlighting (non-Whisper with quotes) → plain text. CSS uses `color-mix(in srgb, accent 30%, transparent)` with `prefers-reduced-motion` underline fallback. VTT/SRT-imported sessions gracefully degrade to segment-level glow only. Glow brightness rebalanced: paragraph glow dimmed 50%, word glow brightened 50% — the active word pops against a subtler segment background
- Design doc: `docs/design-word-highlighting.md` — pipeline diagram, data flow, frontend architecture

**0.12.0** — _1 Mar 2026_

- **Dual sidebar for Quotes tab** — left sidebar: table of contents with scroll-spy (sections + themes, active heading highlights on scroll). Right sidebar: tag filter with codebook tree, eye toggles for badge hiding (persisted to localStorage). 5-column CSS grid (`rail | sidebar | center | sidebar | rail`), drag-to-resize with snap-close thresholds, keyboard shortcuts (`[` left, `]` right, `\` both, `⌘.` tag sidebar). Quotes-tab-only — other tabs see no grid or rails. New components: `SidebarLayout`, `TocSidebar`, `TagSidebar`, `TagGroupCard`, `TagRow`, `EyeToggle`. New hooks: `useDragResize`, `useScrollSpy`. Module-level `SidebarStore` with `useSyncExternalStore`. Backend: tag-group-with-quotes API endpoint, admin panel registration. 845 Vitest tests (60 files), 1856 Python tests
- **Frontend CI** — ESLint, TypeScript typecheck, and Vitest added to GitHub Actions (`frontend-lint-type-test` job on Node 20). ESLint step informational pending fix of 84 pre-existing errors

**0.11.2** — _1 Mar 2026_

- **Self-contained HTML export** — download button in the NavBar bundles all API data as embedded JSON, blob-URL'd JS chunks, and a hash router for `file://` — recipients open the report in any browser without Bristlenose installed. Optional anonymisation checkbox strips participant names before download. Read-only CSS + JS guards hide mutation UI in exported files. 26 Python tests, 20 frontend tests
- **About panel redesign** — sidebar layout (Claude-settings style) with 5 sections: About (per-screen product guide), Signals (sentiment taxonomy, concentration metrics, academic references), Codebook (sections/themes, sentiment tags, framework codebooks with author refs), Developer (architecture, stack, APIs, contributing), Design (design system, dark mode, component library, typography)
- **Configuration reference panel** — read-only grid in Settings tab showing all 63 configurable values across 12 categories with defaults, file badges, clickable env var names (copy to clipboard), and valid options
- **Morville honeycomb codebook** — Peter Morville's User Experience Honeycomb: 7 groups (useful, usable, desirable, findable, accessible, credible, valuable), 28 tags with discrimination prompts and cross-codebook references. Codebooks now sorted by browse order via `sort_order` field

**0.11.1** — _28 Feb 2026_

- **Fix video player** — double URL encoding broke playback for files with spaces (`%20` → `%2520`). Removed Python-side `_url_quote()` from `_file_to_media_uri()`; JS `encodeURIComponent()` now handles encoding once. Also fixed subdirectory loss: `merge_transcript.py` now stores relative paths (e.g. `interviews/show and tell 40.mov`) instead of just the filename

**0.11.0** — _28 Feb 2026_

- **Full React SPA in serve mode** — React Router (`react-router-dom` v7) replaces vanilla JS hash-based tab navigation. Single `RouterProvider` root with pathname routes (`/report/`, `/report/quotes/`, `/report/sessions/:id`, etc.). `AppLayout` wraps `NavBar` + `Outlet`. 8 page wrappers compose existing island components. Backward-compat shims (`window.switchToTab`, `window.navigateToSession`) delegate to React Router for any remaining callers
- **Player integration** — `PlayerContext` manages popout video player lifecycle, `seekTo(pid, seconds)`, glow sync via DOM class manipulation (not React state). `buildGlowIndex` keys by session ID from URL pathname. Progress bar via `--bn-segment-progress` CSS custom property. `player.js` bails out in SPA mode
- **Keyboard shortcuts** — `FocusContext` + `useKeyboardShortcuts` hook. j/k navigation, multi-select (Shift+j/k, x), bulk star/hide/tag, `?` help modal, `/` focus search, Escape cascade (modal → search → selection → focus). Data-derived visible quote IDs replace DOM queries
- **React app shell** — `Header` (logo, project name, subtitle), `Footer` (version, `?` for Help), `HelpModal` (keyboard shortcuts overlay). Serve mode serves Vite-built SPA directly — no more `_transform_report_html()` marker substitution. Route extraction: `app.py` refactored to route modules
- **Vanilla JS retired from serve path** — `_strip_vanilla_js()` removes all 26 modules from the IIFE while keeping `window.*` globals (`BRISTLENOSE_VIDEO_MAP`, `BRISTLENOSE_PLAYER_URL`, `BRISTLENOSE_ANALYSIS`). Static render path unchanged
- Video player links on sessions page and dashboard open the popout player
- Importer finds source files in one-level subdirectories (mirrors ingest scan pattern), fixing video 404s when files are in `interviews/`
- Speaker display names in sessions grid use normal font size (matching date/duration columns)
- Word-level timing data plumbed through pipeline to transcript API (`words` field on segments)

**0.10.3** — _21 Feb 2026_

- `bristlenose status` command — read-only project status from the manifest, shows stage completion with session counts, intermediate file validation, and `-v` per-session detail
- Pre-run resume summary — one-line status message before pipeline output when resuming an interrupted run (e.g. "Resuming: 7/10 sessions have quotes, 3 remaining.")
- Split speaker badges — two-tone pill with speaker code (left, mono) and participant name (right, body font). Settings toggle: "Show participants as: Code and name / Code only", persisted in localStorage. Applied across all surfaces: quote cards, session table, dashboard, transcript pages, user journeys, friction points
- Em-dash removed from quote attribution — replaced with `margin-left: 1rem` gap between quote text and speaker badge
- Always-on sticky transcript header — session selector dropdown always visible on transcript pages (not gated on journey data). Single-session pages show a plain label as page title
- Serve-mode session routing — session links now navigate to standalone transcript pages (React island) instead of inline Jinja2 drill-down. Inline Jinja2 transcript pages and vanilla JS subnav stripped in serve mode
- AutoCode frontend — complete lifecycle for LLM-assisted tag application: ✦ button on framework codebook sections triggers AutoCode run, progress toast with 2s polling and cancel support, threshold review dialog with confidence histogram and dual-threshold slider (accept/tentative/exclude zones), per-row override, proposed badges on quotes (pulsating dashed border, hover accept/deny with brightness flash animation). Tag colour pipeline carries `colour_set` + `colour_index` from CodebookGroup through to accepted user tags
- Threshold review dialog — confidence-aware triage: 20-bin histogram with tag colours, three proposal zones, bulk accept/deny with max_confidence filter, per-quote override before committing
- Activity chip and chip stack components — lightweight status indicators for background jobs with multi-stage progress, cancel button, and auto-dismiss on completion
- Transcript page improvements — greedy slot layout for annotation span bars (no overlapping when multiple quotes span the same region), suppress repeated label+sentiment annotations (show only on topic change), speaker badges use `bn-person-badge` styling consistent with sessions table
- Journey chain: full sequence with revisits — transcript sticky header now shows the complete user journey including revisited sections (e.g. Cat Nav → Prod List → Cat Nav → Checkout), not the deduplicated summary. Index-based tracking distinguishes repeated labels — clicking the second "Cat Nav" jumps to the second occurrence, scrolling highlights only the current one. Sessions table retains deduplicated labels unchanged
- Journey label active state — new `journey-label` CSS atom with `--bn-colour-hover` pill background on the active step, extracted from transcript styles into the atomic design system. Fixed CSS specificity bug where `all: unset` on buttons suppressed the active background
- Resilient transcript discovery — serve-mode importer now searches four locations in priority order (cooked → raw/output → raw/project → transcripts/project) instead of only `transcripts-raw/`, fixing empty transcript pages when pointing serve at non-standard output layouts
- Generic analysis matrix and signals — reusable computation engine for cross-tabulating any labelled data (not just quotes), with API routes for serve mode
- Man page and docs updated for `status` and `serve` commands
- Fix: serve-mode navigation escape — transcript page back link pointed to `/report/{filename}.html` (raw static HTML without React islands) instead of `/report/` (serve-mode route with React injection). Clicking "← Research Report" from a transcript now stays in serve mode

**0.10.2** — _21 Feb 2026_

- Pipeline crash recovery — interrupted runs resume where they left off instead of starting over. Kill mid-analysis, re-run the same command, and only the unfinished sessions get LLM calls. Completed sessions are loaded from cache in milliseconds
- Per-session tracking for topic segmentation and quote extraction — the manifest records which sessions finished within each stage, so a crash after 7 of 10 sessions only re-processes the remaining 3. Cached + fresh results are merged transparently
- CLI resume guard — re-running into an existing output directory now detects the pipeline manifest and resumes automatically. No `--clean` needed, no "output directory already exists" error. `--clean` still available for full re-runs
- Pipeline resilience design doc — CS foundations research (build systems, event sourcing, WAL, CAS, sagas) and phased implementation plan for crash recovery, data integrity, and incremental re-runs

**0.10.1** — _19 Feb 2026_

- Desktop app API key onboarding — first-run setup screen prompts for Claude API key, stores in macOS Keychain via `security` CLI, sidecar picks it up automatically via `_populate_keys_from_keychain()`. Settings panel (⌘,) for viewing, changing, or deleting the key
- `.dmg` packaging — `build-dmg.sh` archives via xcodebuild with ad-hoc signing, packages with hdiutil (or `create-dmg` for drag-to-Applications). `build-all.sh` chains sidecar + ffmpeg + whisper + dmg into one command
- Serve mode after pipeline — desktop app auto-launches `bristlenose serve` after pipeline completes, opens report at `http://127.0.0.1:8150/report/` with full React islands
- Deployment target updated to macOS 15 Sequoia (was 14 Sonoma)
- Codebook tag templates — pre-built tag sets via new API endpoints and UI

**0.10.0** — _18 Feb 2026_

- Desktop app v0.1 — SwiftUI macOS launcher (`desktop/Bristlenose/`) with folder picker, drag-and-drop, pipeline output streaming, View Report in browser. 4-state UI (ready → selected → running → done), ANSI escape stripping, report path detection from both OSC 8 hyperlinks and `Report:` text fallback. Xcode 26 project, 840 KB .app, macOS 14+ deployment target
- ProcessRunner — `@MainActor` ObservableObject that spawns `Process()`, reads stdout via `Task.detached`, streams lines to SwiftUI, extracts report file path
- FolderValidator — scans directories recursively for processable file extensions (mirrors `models.py` extension lists)
- Back-to-folder navigation on Done screen — re-validates folder state for re-render/re-analyse without starting over

**0.9.4** — _17 Feb 2026_

- `bristlenose serve` command — FastAPI local dev server that serves the HTML report over HTTP with SQLite persistence, React islands, and live JS reload in dev mode. Auto-renders before serving, auto-opens browser, prints clickable report URL
- React islands architecture — 5 islands (SessionsTable, Dashboard, QuoteSections, QuoteThemes, CodebookPanel) mount into static HTML via comment markers and `re.sub` at serve time; 16 reusable React primitives (Badge, PersonBadge, TimecodeLink, EditableText, Toggle, TagInput, Sparkline, Counter, Metric, JourneyChain, Annotation, Thumbnail, MicroBar, ConfirmDialog); 182 Vitest component tests
- Codebook CRUD — React island replaces vanilla JS codebook: drag-and-drop tags between groups, inline editing of group titles and subtitles, tag merge with confirmation, create/delete groups and tags, pentadic colour system, MicroBar frequency bars, ConfirmDialog for destructive actions. 9 API endpoints, 36 Python tests
- Dashboard island — Project tab as React composition: 8 clickable stat cards, compact sessions table, featured quotes with reshuffle, section/theme navigation with cross-tab anchor links. 43 API tests
- Data API — 6 fire-and-forget PUT endpoints sync researcher state (hidden, starred, tags, edits, people, deleted-badges) from localStorage to SQLite. 94 tests (37 happy-path + 57 stress)
- 22-table SQLAlchemy domain schema with instance-scoped people/codebook and project-scoped sessions/quotes/themes; `assigned_by` tracks pipeline vs researcher authorship; idempotent upsert importer
- Desktop app scaffold — SwiftUI macOS shell with folder picker, pipeline runner, sidecar architecture (self-contained in `desktop/`)
- Renderer overlay (dev-only, press **D**) — colour-codes report regions by origin: blue for Jinja2, green for React, amber for vanilla JS
- Visual diff page (dev-only) — side-by-side, overlay, and toggle comparison of Jinja2 vs React sessions table

**0.9.3** — _13 Feb 2026_

- Interactive dashboard — Project tab stat cards are clickable links to their target tabs (audio→Sessions, quotes→Quotes, sections/themes→Quotes anchors, AI tags→Analysis, user tags→Codebook); featured quote cards open video player or fall back to transcript; session table rows drill into Sessions tab; section/theme names switch to Quotes tab and scroll to the anchor
- New `--bn-colour-hover` design token with `light-dark()` support
- Speaker code lozenge attribution on featured quotes
- Reusable JS helpers (`scrollToAnchor`, `navigateToSession`) and Python helpers (`_timecode_html`, `_session_anchor`)
- Fix: logo dark/light swap on appearance toggle

**0.9.2** — _12 Feb 2026_

- Sessions table redesign — speaker badges with colour-coded IDs, user journey paths below start dates, video thumbnail placeholders (96×54px, 16:9), per-session sentiment sparkline mini-bar charts
- Appearance toggle — system/light/dark mode switcher in settings tab
- User journeys — derived from topic-segmentation screen clusters, shown in sessions table and sortable journeys table
- Time estimates — upfront pipeline duration estimate after ingest (`~8 min (±2 min)`), recalculated remaining time after each stage, Welford's online algorithm for per-metric running stats, hardware+config keyed profiles persisted to `~/.config/bristlenose/timing.json`
- Clickable logo — Bristlenose logo in report header navigates to project tab
- Fix: `llm_max_tokens` truncation causing silent 0-quote extraction — providers now detect truncation via `stop_reason`/`finish_reason` and raise `RuntimeError` with actionable `.env` fix
- Fix: sentiment sparkline bars now align with video thumbnail baseline (removed inline height override that capped sparkline container at 20px instead of the intended 54px)

**0.9.1** — _11 Feb 2026_

- Moderator and observer names shown in Project tab stats row (Oxford comma lists, observer box only when observers exist)
- Fix: clicking [+] to add a tag on a quote now tags that quote, not the previously-focused quote

**0.9.0** — _11 Feb 2026_

- Tab navigation — tabs remember their position across page reloads via URL hash (`#codebook`, `#analysis`, etc.); browser back/forward navigates between tabs; deep-linkable tab URLs
- Analysis tab — inline signal cards and heatmaps in the main report (previously a placeholder); `BRISTLENOSE_ANALYSIS` data injected into the report's script block alongside the standalone `analysis.html`
- Codebook tab — fixed empty grid caused by `_countQuotesPerTag` function name collision between `codebook.js` and `tag-filter.js` in the concatenated JS bundle; codebook panel now renders correctly in the main report
- Removed dead toolbar button handlers from `analysis.js` and `codebook.js` (replaced by navigation tabs)

**0.8.2** — _9 Feb 2026_

- Transcript annotations — per-participant transcript pages now highlight which segments were selected as quotes, with margin labels showing sentiment, colour-coded span bars connecting multi-segment quotes, and a citation toggle to show/hide annotations; playback-synced glow on both transcript segments and report quote cards when video is playing
- Gemini provider — `--llm gemini` for budget-conscious teams (~$0.20/study, 5–7× cheaper than Claude or ChatGPT); `bristlenose configure gemini` stores your key in the system credential store; interactive provider picker now includes Gemini as option [4]
- Jinja2 template extraction — report renderer migrated from f-strings to Jinja2 templates (13 templates extracted across two phases); pure refactor, no output changes
- Platform-specific credential language — doctor and configure now show the actual store name: "Keychain" on macOS, "Secret Service" on Linux, instead of generic "credential store"

**0.8.1** — _7 Feb 2026_

- Hidden quotes — press `h` (or click the eye-slash button) to hide volume quotes you want to keep as evidence but need out of your working view; per-subsection badge shows count with dropdown of truncated previews; click a preview to unhide with highlight animation; bulk hide via multi-select + `h`; hidden state persists in localStorage and survives search, tag filter, and view switching
- Codebook — standalone `codebook.html` page (opens in a new window via toolbar button) with interactive panel for organising tags into groups; drag-and-drop reordering within and between groups; inline editing of group names; add/delete groups with confirmation; toggle AI tag visibility per-tag; colour-coded tag badges with 24-colour palette; shared data model across report and codebook via localStorage
- Toolbar redesign — unified round-rect button styling with 3-state border progression (rest → hover → active); tag filter and view switcher use dual-class pattern for consistent appearance
- Python 3.14 compatibility — `check_pii` in doctor now catches `Exception` (not just `ImportError`) to handle pydantic v1 crash when importing presidio on Python 3.14

**0.8.0** — _7 Feb 2026_

- Azure OpenAI provider — `--llm azure` for enterprise users with Microsoft Azure contracts; uses `AsyncAzureOpenAI` from the existing OpenAI SDK (no new dependencies); configure with `bristlenose configure azure` or `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` env vars
- Install smoke tests — new CI workflow (`install-test.yml`) verifies install instructions work on clean Linux and macOS VMs; runs `bristlenose doctor` and `bristlenose render` from pre-built fixtures with no API key needed; weekly full-pipeline run with real API key catches integration regressions

**0.7.1** — _6 Feb 2026_

- Bar chart alignment — sentiment and user-tag charts use CSS grid so bar left edges align within each chart; labels hug text with variable gap to bars
- Histogram delete — hover × on user tag labels in the histogram to remove that tag from all quotes (with confirmation modal)
- Surprise placement — surprise sentiment bar now renders between positive and negative sentiments
- Quote exclusivity in themes — each quote assigned to exactly one theme (pick strongest fit)

**0.7.0** — _5 Feb 2026_

- Multi-select — Finder-like click selection (click, Shift-click, Cmd/Ctrl-click) with bulk starring (`s` key) and bulk tagging; selection count shown in view-switcher label; CSV export respects selection
- Tag filter — toolbar dropdown between search and view-switcher filters quotes by user tags; checkboxes per tag with "(No tags)" for untagged quotes; per-tag quote counts, search-within-filter for large tag lists, dropdown chevron, ellipsis truncation for long names

**0.6.15** — _4 Feb 2026_

- Unified tag close buttons — AI badges and user tags now use the same floating circle "×" style
- Tab-to-continue tagging — pressing Tab commits the current tag and immediately opens a new input for adding another tag (type, Tab, type, Tab, Enter for fast keyboard-only tagging)
- Render command path fix — `bristlenose render <input-dir>` now auto-detects `bristlenose-output/` inside the input directory

**0.6.14** — _4 Feb 2026_

- Doctor fixes — improved Whisper model detection and PII capability checking

**0.6.13** — _3 Feb 2026_

- Keychain credential storage — `bristlenose configure claude` (or `chatgpt`) validates and stores API keys securely in macOS Keychain or Linux Secret Service; keys are loaded automatically with priority keychain → env var → .env; `bristlenose doctor` now shows "(Keychain)" suffix when key comes from system credential store; `--key` option available for non-interactive use

**0.6.12** — _3 Feb 2026_

- File-level transcription progress — spinner now shows "(2/4 sessions)" during transcription
- Improved Ollama start command detection — uses `brew services start ollama` for Homebrew installs, `open -a Ollama` for macOS app, platform-appropriate commands for snap/systemd
- Doctor displays "(MLX)" accelerator — when mlx-whisper is installed on Apple Silicon, doctor now shows "(MLX)" instead of "(CPU)"
- Whisper model line fits 80 columns — shortened to "~1.5 GB download on first run"
- Provider header fix — pipeline header now shows "Local (Ollama)" instead of "ChatGPT" when using local provider
- Improved fix messages — doctor fix messages now use `pipx inject` for pipx installs, proper Homebrew Python path for brew installs (PEP 668 compliance)
- Retry logic catches ValidationError — local model retries now also handle Pydantic schema validation failures, not just JSON parse errors

**0.6.11** — _3 Feb 2026_

- Local AI support via Ollama — run bristlenose without an API key using local models like Llama 3.2; interactive first-run prompt offers Local/Claude/ChatGPT choice
- Automated Ollama installation — offers to install Ollama automatically (Homebrew on macOS, snap on Linux, curl script fallback); falls back to download page if installation fails
- Auto-start Ollama — if installed but not running, bristlenose will start it for you
- Provider registry — centralised `bristlenose/providers.py` with `ProviderSpec` dataclass, alias resolution (claude→anthropic, chatgpt→openai, ollama→local)
- Ollama integration — `bristlenose/ollama.py` with status checking, model detection, and auto-pull with consent
- Retry logic for local models — 3 retries with exponential backoff for JSON parsing failures (~85% reliability vs ~99% for cloud)
- Smart cloud fallback hints — fix messages for Ollama issues now check which API keys you have and only suggest providers you can actually use
- Doctor integration for local provider — shows "Local (llama3.2:3b via Ollama)" status, helpful fix messages for Ollama not running or model missing

**0.6.10** — _3 Feb 2026_

- Output directory inside input folder — `bristlenose run interviews/` now creates `interviews/bristlenose-output/` to avoid collisions when processing multiple projects
- New directory structure — `assets/` for static files, `sessions/` for transcript pages, `transcripts-raw/`/`transcripts-cooked/` for transcripts, `.bristlenose/` for internal files
- Report filenames include project name — `bristlenose-{slug}-report.html` so multiple reports in Downloads are distinguishable
- Coverage link fix — player.js no longer intercepts non-player timecode links
- Anchor highlight — transcript page segments flash yellow when arriving via anchor link

**0.6.9** — _3 Feb 2026_

- Transcript coverage section — collapsible section at the end of the report showing what % of the transcript made it into quotes (X% in report · Y% moderator · Z% omitted), with expandable omitted content per session
- Transcript page fix — pages now render correctly when PII redaction is off (was failing with assertion error)

**0.6.8** — _3 Feb 2026_

- Multi-participant session support — sessions with multiple interviewees get globally-numbered participant codes (p1–p11 across sessions); report header shows correct participant count
- Sessions table — restructured from per-participant rows to per-session rows with a Speakers column showing all speaker codes (m1, p1, p2, o1) per session
- Transcript page format — heading shows `Session N: m1 Name, p5 Name, o1`; segment labels show raw codes for consistency with the anonymisation boundary
- Session duration — now derived from transcript timestamps for VTT-only sessions (previously showed "—")
- Moderator identification (Phase 1) — per-session speaker codes (`[m1]`/`[p1]`) in transcript files, moderator entries in `people.yaml`, `.segment-moderator` CSS class for muted moderator styling

**0.6.7** — _2 Feb 2026_

- Search enhancements — clear button (×) inside the search input, yellow highlight markers on matching text, match count shown in view-switcher label ("7 matching quotes"), ToC and Participants hidden during search, CSV export respects search filter
- Pipeline warnings — clean dim-yellow warning lines when LLM stages fail (e.g. credit balance too low), with direct billing URL for Claude/ChatGPT; deduplication and 74-char truncation
- CLI polish — "Bristlenose" in regular weight in the header line, "Report:" label in regular weight in the summary

**0.6.6** — _2 Feb 2026_

- Cargo/uv-style CLI output — clean `✓` checkmark lines with per-stage timing, replacing garbled Rich spinner output; dim header (version · sessions · provider · hardware), LLM token usage with cost estimate, OSC 8 terminal hyperlinks for report path; output capped at 80 columns; all tqdm/HuggingFace progress bars suppressed
- Search-as-you-type quote filtering — collapsible magnifying glass icon in the toolbar; filters by quote text, speaker, and tag content; overrides view mode during search; hides empty sections/subsections; 150ms debounce
- Platform-aware session grouping — Teams, Zoom cloud, Zoom local, and Google Meet naming conventions recognised automatically; two-pass grouping (Zoom folders by directory, remaining files by normalised stem); audio extraction skipped when a platform transcript is present
- Man page — full troff man page (`man bristlenose`); bundled in the wheel and self-installs to `~/.local/share/man/man1/` for pip/pipx users on first run; wired into snap, CI version gate, and GitHub Release assets
- Page footer — "Bristlenose version X.Y.Z" colophon linking to the GitHub repo on every generated page

**0.6.5** — _2 Feb 2026_

- Timecode typography — two-tone treatment with blue digits and muted grey brackets; `:visited` colour fix so clicked timecodes stay blue
- Hanging-indent layout — timecodes sit in a left gutter column on both report quotes and transcript pages, making them scannable as a vertical column
- Non-breaking spaces on quote attributions prevent the `— p1` from widowing onto a new line
- Transcript name propagation — name edits made in the report's participant table now appear on transcript page headings and speaker labels via shared localStorage

**0.6.4** — _1 Feb 2026_

- Concurrent LLM calls — per-participant stages (speaker identification, topic segmentation, quote extraction) now run up to 3 API calls in parallel via `llm_concurrency` config; screen clustering and thematic grouping also run concurrently; ~2.7× speedup on the LLM-bound portion for multi-participant studies

**0.6.3** — _1 Feb 2026_

- Report header redesign — logo top-left (flipped horizontally), "Bristlenose" logotype with project name, right-aligned document title and session metadata
- View-switcher dropdown — borderless menu to switch between All quotes, Favourite quotes, and Participant data views; replaces old button-bar pattern
- Copy CSV button with clipboard icon — single adaptive button that exports all or favourites based on the current view
- Quote attributions use raw participant IDs (`— p1`) in the report for anonymisation; transcript pages continue to show display names
- Table of Contents reorganised — Sentiment, Tags, Friction points, and User journeys moved to a dedicated "Analysis" column, separate from Themes

**0.6.2** — _1 Feb 2026_

- Editable participant names — pencil icon on Name and Role cells in the participant table; inline editing with localStorage persistence; YAML clipboard export for writing back to `people.yaml`; reconciliation with baked-in data on re-render
- Auto name and role extraction — Stage 5b LLM prompt now extracts participant names and job titles alongside speaker role identification; speaker label metadata harvested from Teams/DOCX/VTT sources; empty `people.yaml` fields auto-populated (LLM results take priority over metadata, human edits never overwritten)
- Short name suggestion — `short_name` auto-suggested from first token of `full_name` with disambiguation for collisions ("Sarah J." vs "Sarah K."); works both in the pipeline and in-browser
- Editable section and theme headings — inline editing on section titles, descriptions, theme titles, and theme descriptions with bidirectional Table of Contents sync

**0.6.1** — _1 Feb 2026_

- Snap packaging for Linux — `snap/snapcraft.yaml` recipe and CI workflow (`.github/workflows/snap.yml`); builds on every push to main, publishes to edge/stable when Store registration completes
- Pre-release snap testing instructions in README for early feedback on amd64 Linux
- Author identity (Martin Storey) added to copyright headers, metadata, and legal files

**0.6.0** — _1 Feb 2026_

- `bristlenose doctor` command — checks FFmpeg, transcription backend, Whisper model cache, API key validity, network, PII dependencies, and disk space
- Pre-flight gate on `run`, `transcribe-only`, and `analyze` — catches missing dependencies before slow work starts
- First-run auto-doctor — runs automatically on first invocation, guides users through setup
- Install-method-aware fix messages — detects snap, Homebrew, or pip and shows tailored install instructions
- API key validation — cheap API call catches expired or revoked keys upfront

**0.5.0** — _1 Feb 2026_

- Per-participant transcript pages — full transcript for each participant with clickable timecodes and video player; participant IDs in the table link to these pages
- Quote attribution deep-links — clicking `— p1` at the end of a quote jumps to the exact segment in the participant's transcript page
- Segment anchors on transcript pages for deep linking from quotes and external tools

**0.4.1** — _31 Jan 2026_

- People file (`people.yaml`) — participant registry with computed stats (words, % words, % speaking time) and human-editable fields (name, role, persona, notes); preserved across re-runs
- Display names — set `short_name` in `people.yaml`, re-render with `bristlenose render` to update quotes and tables
- Enriched participant table in reports (ID, Name, Role, Start, Duration, Words, Source) with macOS Finder-style relative dates
- PII redaction now off by default; opt in with `--redact-pii` (replaces `--no-pii`)
- Man page updated for new CLI flags and output structure

**0.4.0** — _31 Jan 2026_

- Dark mode — report follows OS/browser preference automatically via CSS `light-dark()` function
- Override with `color_scheme = "dark"` (or `"light"`) in `bristlenose.toml` or `BRISTLENOSE_COLOR_SCHEME` env var
- Dark-mode logo variant (placeholder; proper albino bristlenose pleco coming soon)
- Print always uses light mode
- Replaced hard-coded colours in histogram JS with CSS custom properties

**0.3.8** — _31 Jan 2026_

- Timecode handling audit: verified full pipeline copes with sessions shorter and longer than one hour (mixed `MM:SS` and `HH:MM:SS` in the same file round-trips correctly)
- Edge-case tests for timecode formatting at the 1-hour boundary, sub-minute sessions, long sessions (24h+), and format→parse round-trips

**0.3.7** — _31 Jan 2026_

- Markdown style template (`bristlenose/utils/markdown.py`) — single source of truth for all markdown/txt formatting constants and formatter functions
- Per-session `.md` transcripts alongside `.txt` in `raw_transcripts/` and `cooked_transcripts/`
- Participant codes in transcript segments (`[p1]` instead of `[PARTICIPANT]`) for better researcher context when copying quotes
- Transcript parser accepts both `MM:SS` and `HH:MM:SS` timecodes

**0.3.6** — _31 Jan 2026_

- Document full CI/CD pipeline topology, secrets, and cross-repo setup

**0.3.5** — _31 Jan 2026_

- Automated Homebrew tap updates and GitHub Releases on every tagged release

**0.3.4** — _31 Jan 2026_

- Participants table: renamed columns (ID→Session, Session date→Date), added Start time column, date format now dd-mm-yyyy

**0.3.3** — _31 Jan 2026_

- README rewrite: install moved up, new quick start section, changelog with all versions, dev setup leads with git clone
- Links to Anthropic and OpenAI API key pages in install instructions

**0.3.2** — _30 Jan 2026_

- Fix tag auto-suggest offering tags the quote already has
- Project logo in report header

**0.3.1** — _30 Jan 2026_

- Single-source version: `__init__.py` is the only place to bump
- Updated release process in CONTRIBUTING.md

**0.3.0** — _30 Jan 2026_

- CI on every push/PR (ruff, mypy, pytest)
- Automated PyPI publishing on tagged releases (OIDC trusted publishing)

**0.2.0** — _30 Jan 2026_

- Tag system: AI-generated badges (deletable/restorable) + user tags with auto-suggest and keyboard navigation
- Favourite quotes with reorder animation and CSV export (separate AI/User tag columns)
- Inline quote editing with localStorage persistence
- Sentiment histogram (side-by-side AI + user-tag charts)
- `bristlenose render` command for re-rendering without LLM calls
- Report JS extracted into 8 standalone modules under `bristlenose/theme/js/`
- Atomic CSS design system (`bristlenose/theme/`)

**0.1.0** — _30 Jan 2026_

- 12-stage pipeline: ingest, extract audio, parse subtitles/docx, transcribe (Whisper), identify speakers, merge, PII redaction (Presidio), topic segmentation, quote extraction, screen clustering, thematic grouping, render
- HTML report with clickable timecodes and popout video player
- Quote enrichment: intent, emotion, intensity, journey stage
- Friction points and user journey summaries
- Apple Silicon GPU acceleration (MLX), CUDA support, CPU fallback
- PII redaction with Presidio
- Cross-platform (macOS, Linux, Windows)
- Published to PyPI and Homebrew tap
- AGPL-3.0 licence with CLA
