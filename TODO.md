# Bristlenose — Where I Left Off

Last updated: 24 Mar 2026

## Desktop app security (must-fix before any distribution)

From security review of desktop app plan (22 Mar 2026). All findings are in the serve-side and process management layer, not the Swift bridge code (which is clean).

- [x] **Localhost auth token** — bearer token middleware, per-session `secrets.token_urlsafe(32)`, validated on `/api/*` + `/media/*`. Injected into HTML (`json.dumps`) + WKUserScript (regex-validated). Design: `docs/design-localhost-auth.md`
- [x] **Media endpoint filtering** — extension allowlist + path-traversal guard on `/media/` route. Also requires auth token
- [x] **CORS middleware** — `CORSMiddleware(allow_origins=[])` blocks all cross-origin requests
- [x] **Don't bundle API key in binary** — verified clean: no hardcoded keys in Swift source, Keychain-only storage, user enters via Settings
- [x] **Skip zombie cleanup when BRISTLENOSE_DEV_PORT is set** — `killOrphanedServeProcesses()` now skips when dev port override is active, so the terminal dev server isn't killed on Xcode launch
- [ ] **Verify zombie cleanup targets** — `killOrphanedServeProcesses()` runs `lsof -ti :8150-9149` and kills every PID found, including non-Bristlenose processes. Check process command line contains "bristlenose" before `kill()`
- [ ] **Migrate KeychainHelper to Security framework** — current `/usr/bin/security` CLI approach is blocked in App Sandbox. Use `SecItemAdd`/`SecItemCopyMatching`/`SecItemDelete`. Also affects Python-side `credentials_macos.py`
- [x] **Minimal child process environment** — stripped to PATH, HOME, TMPDIR, USER, SHELL, locale, VIRTUAL_ENV + BRISTLENOSE_* overlay in `ServeManager.overlayPreferences()`
- [ ] **Port-restrict navigation policy** — `decidePolicyFor` allows any localhost port. Restrict to the expected serve port from `serveManager.state`

## Desktop app — shipped this session

- [x] **Video player popout (WKUIDelegate)** — `window.open()` now creates a native NSWindow with WKWebView for player.html. Dynamic title (`s1 — Bristlenose`), `setFrameAutosaveName` for position persistence, single-popout guard, `webViewDidClose` cleanup
- [x] **12 video menu actions wired** — playPause, skip±5/±30, speed up/down/normal, volume up/down/mute, PiP, fullscreen. `sendCommand` on PlayerContext → `bristlenose-command` postMessage → player.html
- [x] **Bridge player state** — `getState()` reports live `hasPlayer`/`playerPlaying` for Video menu dimming. `postPlayerState` notifies Swift on open/close/play/pause
- [x] **Security hardening** — origin validation on postMessage (both directions), payload namespacing, float rounding on speed/volume steps, no-video guard
- [x] **BroadcastChannel fallback** — defence-in-depth for glow sync if `window.opener` is nil in WKWebView popouts
- [x] **a11y announce** — `announce("Playing pid")` on seekTo for VoiceOver

## Desktop app — bugs found

- [x] **Native toolbar tabs don't navigate** — fixed: stale `navigate` closure in `installNavigationShims`. Module-level refs instead of direct closure capture. Also added `makeFirstResponder(webView)` after tab switch for keyboard focus
- [ ] **Native toolbar tab i18n not reactive** — changing language in Settings doesn't update toolbar labels until app restart. `I18n` `@StateObject` doesn't trigger segmented control re-render
- [ ] **i18n: extract ~180 hardcoded frontend strings** — infrastructure is ready (single source of truth, Vite alias, i18next). Strings need to be moved from JSX literals to locale JSON keys. Tier 1 (~40 strings) is the critical path. See `docs/design-i18n.md` string audit
- [ ] **i18n: pseudo-localisation QA** — add `i18next-pseudo` to catch hardcoded strings. See `docs/design-i18n.md`
- [ ] **i18n: Weblate setup** — connect `hosted.weblate.org` to repo for community translation. Free Libre plan. See `docs/design-i18n.md`
- [ ] **i18n: cross-check Spanish against Apple glossary** — verified 23 Mar 2026, all match. Do same for each new language before release

## Desktop app — future video player

- [ ] **Native AVPlayer (Option B)** — replace HTML5 popout with native AVPlayer in its own NSWindow. Better PiP, Touch Bar, media keys, pitch-corrected speed (`AVAudioTimePitchAlgorithm.spectral`). Popout, never in-pane (Dovetail anti-pattern). See `memory/project_video_player_options.md`

## Show/Hide panel label flip (desktop menu)

Menu View items now say "Show Contents" / "Show Tags" / "Show Heatmap" (per-tab dynamic, Mar 2026). Hide translations exist in all 3 locales (en/es/ko) but aren't wired yet. To flip labels based on panel state:

1. **Bridge**: add `leftPanelOpen`, `rightPanelOpen`, `inspectorOpen` to `BridgeState` in `frontend/src/shims/bridge.ts`. Source from `SidebarStore.getSnapshot()` and `InspectorStore.getSnapshot()`
2. **Swift**: add matching `@Published` properties on `BridgeHandler`. Read from `getState()` response
3. **Menu labels**: ternary on each Button — `isOpen ? i18n.t("...hide...") : i18n.t("...show...")`. Keys already exist: `desktop.menu.view.hideContents`, `hideCodes`, `hideSignals`, `hideTags`, `hideHeatmap`
4. **Toolbar tooltips**: same pattern — switch help text between show/hide variants. Need toolbar hide keys too (currently only menu has them)

Small task, ~30 min. No design decisions — just plumbing state from React stores → bridge → Swift.

## Near-horizon roadmap

- [ ] simplest versions of the left-hand navs
  - simple signal cards
  - simple speaker badges / sessions
  - simple codebook title lists
- [ ] right-align bar chart on tags
- [ ] sidebar tag assign: hover hint should match "add tag" visual language (not just `cursor: copy` — consider `+` icon, tooltip, or badge glow consistent with TagInput affordance)
- [ ] sidebar tag assign: toast undo ("Applied 'Trust' to 3 quotes — Undo")
- [ ] drag-and-drop tags to quotes
- [ ] hide unused tags → responsive card thing for analysis page
- [ ] new title bar
- [ ] **Dev HUD: end-to-end traceability panel** — debug overlay (dev-only, like the renderer overlay) showing provenance at every layer so you can instantly see if a code change carried through the full stack. Proposed contents:
  - **Git**: branch, short SHA, dirty flag
  - **Python**: `bristlenose.__version__`, editable-install source path
  - **Render**: timestamp of last `bristlenose render` (from report HTML comment or CSS header)
  - **Theme CSS**: full path being served, file mtime, `_CSS_VERSION` string, hash of first 1KB (detects stale file)
  - **Serve mode**: `hmr` / `prod` / `embedded`, port, output dir path
  - **Frontend**: Vite build hash (from `index.html` asset filenames), React Router mode (SPA vs legacy islands)
  - **Bridge**: `isEmbedded()`, `isReady`, active tab, window active/inactive state
  - **Health**: API version from `/api/health`
  - Render as a small semi-transparent panel (like the PlaygroundHUD) or a tab in the existing dev playground. Toggle with a keyboard shortcut (e.g. `Ctrl+I`). Data sourced from: git CLI at serve startup (injected as `window.__BRISTLENOSE_BUILD__`), `/api/health`, `/api/dev/info`, CSS `@import` inspection, `document.documentElement.className`
- [ ] **Design doc: themes vs colour schemes** — establish nomenclature and architecture for two orthogonal axes. **Theme** = structure (font family, sizes, spacing, button/icon styles): "web" (Inter, web metrics) vs "macOS" (SF Pro, system metrics). **Colour scheme** = palette that fills the token slots: light, dark, Edo (warm/muted?). One theme can have multiple schemes. Current `tokens.css` already has the slot structure (`--bn-colour-*`); `light-dark()` handles light/dark. Need: naming convention, file organisation, how schemes are selected (CSS class? data attribute?), how themes fork structural tokens, and where Edo sits in this. Write `docs/design-themes-and-schemes.md` before coding
- [ ] **Investigate dark-mode inactive selection token** — `--bn-selection-bg-inactive` dark value (`#262626`) may be too close to page bg (`#111111`), making inactive selections nearly invisible. macOS `unemphasizedSelectedContentBackgroundColor` is closer to `#3a3d41`. Address as part of colour scheme work above
- [ ] edo fish

## Essential simplicity and clarity (layout quality)

- [ ] animations for right-hand sidebar (match left-hand)
- [ ] design content LHS for Sessions
- [ ] LHS for codebooks: user, sentiment, default UXR, frameworks
- [ ] LHS for Analysis (like PowerPoint)
- [ ] empty cosmetic LHS rail for Project dashboard
- [ ] standard modal with nav for Settings
- [ ] standard modal with nav for About
- [ ] unify help and about modals?

## Adoptability

Blockers that mean new users give up or never try:

- [ ] hero image of report on GitHub README
- [ ] single-page website with image of each screen
- [ ] walkthrough script of features and benefits
- [ ] how to get an API key — screenshots

## Test data (real, public, credible)

- [ ] 5h of IKEA study
- [ ] test with actual user tags
- [ ] exercise the frameworks
- [ ] share with original authors

## Visual fit and finish

- [ ] grid, spacing, type, colours audit
- [ ] themes — edo as switch in appearance

## Microinteractions

- [ ] bounces and slides for opens/closes
- [ ] flashes of acceptance
- [ ] **Staggered fly-up animation for bulk hide** — stagger the ghost animation 150ms per card (like vanilla JS version) instead of plain collapse

## Immediate tasks

- [ ] **Rotate API key** — key was visible in terminal paste during snap testing session. Rotate at console.anthropic.com
- [ ] **Export polish** — inline logo as base64, fix footer "Bristlenoseversion" missing space, fix in-report navigation links (hash router)
- [ ] **Responsive quote grid** — CSS-only Phase 1. Design doc: `docs/design-responsive-layout.md`
- [ ] **Auto-serve after run** — after `bristlenose run` completes, launch serve mode and open browser automatically. Consider: `--no-serve` flag, port selection, fallback if serve deps missing
- [ ] **QA: threshold review dialog on real data** — run AutoCode against real projects, evaluate confidence histogram + dual slider UX. Qualitative, not automated
- [ ] **CI snap smoke test** — add a post-build job to the snap workflow that installs the artifact and runs `bristlenose --version && bristlenose doctor`
- [ ] **Snap Store registration** — `snapcraft register bristlenose`, request classic confinement, add `SNAPCRAFT_STORE_CREDENTIALS` to GitHub secrets. See `docs/design-doctor-and-snap.md`

---

## Task tracking

**GitHub Issues is the source of truth for actionable tasks:** https://github.com/cassiocassio/bristlenose/issues

This file contains: session reminders, feature groupings with context, items too small for issues, architecture notes, dependency maintenance, and completed work history.

### Priority order

1. **Export polish** — fix remaining rough edges from Step 10 export
2. **Responsive quote grid** — CSS-only Phase 1
3. **Extract design tokens for Figma** — colours, spacing, typography, radii → JSON/CSS variables for Figma
4. **Moderator Phase 2** (#25) — cross-session linking
5. **Dark mode selection highlight** (#52) — visibility bug
6. **SVG icon set** — replace fragile character glyphs
7. **Miro bridge** — near-term sharing story. See `docs/private/design-miro-bridge.md`

---

## Feature roadmap by area

### Report UI

| Item | Issue | Effort |
|------|-------|--------|
| Dashboard: increase stats coverage | — | medium |
| Dark mode: selection highlight visibility | #52 | trivial |
| Logo: increase size from 80px to ~100px | #6 | trivial |
| Show day of week in session Start column | #11 | small |
| Reduce AI tag density (tune prompt or filter) | #12 | small |
| User-tags histogram: right-align bars | #13 | small |
| Clickable histogram bars → filtered view | #14 | small |
| Refactor render/ header/toolbar into template helpers | #16 | small |
| Theme management in browser (custom CSS themes) | #17 | small |
| Dark logo: proper albino bristlenose pleco | #18 | small |
| Lost quotes: surface unselected quotes for rescue | #19 | small |
| .docx export | #20 | small |
| Edit writeback to transcript files | #21 | small |
| Tag definitions page | #53 | small |
| Undo bulk tag (Cmd+Z for last tag action) | — | medium |
| Multi-page report (tabs or linked pages) | #51 | large |
| Project setup UI for new projects | #49 | large |
| Responsive quote grid layout | — | medium |
| Content density setting (Compact / Normal / Generous) | — | small |

### Content density setting

Three-way toggle (Compact / Normal / Generous) that scales content without touching chrome (nav, toolbar, logo). All spacing tokens are `rem`-based, so a single `font-size` change on `<article>` cascades to quote text, badges, timecodes, headings, and padding.

| Setting | `article` font-size | Use case |
|---------|---------------------|----------|
| Compact | 14px (0.875rem) | Dense scanning, big datasets, small screens |
| Normal | 16px (1rem) | Default — current look |
| Generous | 18px (1.125rem) | Screen-sharing, calls, accessibility, large monitors |

Implementation: add `--bn-content-scale` token (`0.875` / `1` / `1.125`), set `font-size: calc(var(--bn-content-scale) * 1rem)` on `<article>`. Toggle in toolbar or settings. Persist via preferences store. Interacts with responsive grid — Generous + wide screen = fewer but more readable columns.

### Responsive layout

Multi-column quote grid using CSS `auto-fill`. Card max-width `23rem` (368px) keeps ~5 words/line for fast scanning. Columns add automatically as viewport widens — no JS. Mockup: `docs/mockups/responsive-quote-grid.html`. Full design: `docs/design-responsive-layout.md`.

### Pipeline and analysis

| Item | Issue | Effort |
|------|-------|--------|
| Signal concentration: Phase 4 — two-pane layout, grid-as-selector | — | medium |
| Signal concentration: Phase 5 — LLM narration of signal cards | — | small |
| Signal concentration: user-tag × group grid (new design needed) | — | medium |
| Session enable/disable toggle (temporary exclusion from analysis) | — | medium |
| Delete/quarantine session from UI (`.bristlenose-ignore`) | — | medium |
| Re-run pipeline from serve mode (background, with progress) | — | large |
| Pipeline resilience Phase 2b — verify hashes on load | — | small |
| Pipeline resilience Phase 2c — input change detection | — | medium |
| Moderator Phase 2: cross-session linking | #25 | medium |
| Speaker diarisation improvements | #26 | medium |
| Batch processing dashboard | #27 | medium |
| Quote sequences: ordinal-based detection for non-timecoded transcripts | — | medium |
| Quote sequences: "verse numbering" for plain-text transcripts | — | medium |
| Quote sequences: per-project threshold configurability | — | small |

Session management design doc: `docs/design-session-management.md`

### CLI

| Item | Issue | Effort |
|------|-------|--------|
| Britannification pass | #40 | trivial |
| `--prefetch-model` flag for Whisper | #41 | trivial |
| Doctor: serve-mode checks + Vite auto-discovery | — | medium |

### Packaging

| Item | Issue | Effort |
|------|-------|--------|
| CI: automate `.dmg` build on push | — | medium |
| `.dmg` README: include "Open Anyway" instructions | — | trivial |
| ~~Homebrew formula: post_install for spaCy model~~ | #42 | trivial |
| Snap store publishing | #45 | small |
| Windows CI: pytest on `windows-latest` | — | medium |
| Windows installer (winget) | #44 | medium |

### Desktop app (macOS)

| Item | Issue | Effort |
|------|-------|--------|
| Keychain: migrate from `security` CLI to native Security framework | — | small |
| ReadyView: replace `NSOpenPanel.runModal()` with SwiftUI `.fileImporter()` | — | trivial |
| ProcessRunner: replace `availableData` polling with `AsyncBytes` | — | small |
| `hasAnyAPIKey()` only checks Anthropic — rename or extend | — | trivial |
| Settings shortcut ⌘, — show in Help shortcuts conditionally (desktop only, browser intercepts) | — | small |

### Desktop app — UX review findings (22 Mar 2026)

**Critical:**
- [ ] **v0.1→v1 transition story** — v0.1 opens reports in Safari, v1 shows them in-app. Plan a "What's New" sheet on first launch of v1. Keep "Open in Browser" as File menu option so the old workflow survives
- [ ] **v0.1 pipeline progress** — 12 stages known upfront, Welford estimator exists. Show "Stage 4 of 12" alongside streaming log, not just checkmark lines

**Major:**
- [ ] **Bare-key shortcuts invisible in menu bar** — `s`/`h`/`t`/`j`/`k` have no menu representation. Show as informational labels: "Star (press S in report)". The menu bar is how Mac users learn an app
- [ ] **"Delete Project" → "Remove Project"** — researchers fear "delete" means recordings. "Remove" communicates "take out of this app." Confirmation dialog should name the specific folder path
- [ ] **Disambiguate three "sidebars"** — native project sidebar, web TOC, web tags. Use "Project Sidebar", "Sections Panel", "Tags Panel" in View menu labels (not "Left Panel" / "Right Panel")
- [ ] **Archive feedback** — if ARCHIVE section is collapsed (default), archived project vanishes. Auto-expand briefly or show undo toast ("Q1 Study archived. [Undo]")

**Minor:**
- [ ] **Promote sidebar type-to-filter to P1** — `.searchable()` on List is trivial, essential at 10+ projects
- [ ] **Simplify drop zone flow** — auto-name project from folder, default to unfiled, let user rename later (currently asks name + folder + confirm during drag)
- [ ] **Fixed minimum width for toolbar trailing zone** — prevent centre segmented control shifting when contextual items appear/disappear per tab
- [ ] **Window state restoration** — persist selected project to `@AppStorage` so relaunch reopens where you left off
- [ ] **Dark mode appearance re-sync** — `syncAppearance()` only fires on `ready`. Add KVO on `NSApp.effectiveAppearance` to re-sync when user changes macOS system appearance while app is running
- [ ] **Embedded font token** — use `--bn-text-base-embedded` design token for 13px, not hardcoded pixel value in WKUserScript
- [ ] **Cursor reset scope** — `.bn-embedded` body class targeting non-link interactive elements only, not a blanket CSS override

### Desktop app — Mac-nativeness review findings (22 Mar 2026)

**P0:**
- [ ] **13pt font injection** — loudest web-view tell. Every second at 16px next to 13pt sidebar screams hybrid

**P1:**
- [ ] **Shared find pasteboard** — Cmd+E writes to `NSPasteboard(name: .find)`, Cmd+G reads. Menu items exist, bridge write is the gap
- [ ] **Selection dimming on inactive window** — `::selection:window-inactive` CSS in web layer
- [ ] **Temperature slider locale** — `LLMSettingsView` uses `String(format: "%.1f")`, not locale-aware. Use `temperature.formatted(.number.precision(.fractionLength(1)))`
- [ ] **Cocoa keybindings in contenteditable** — test Ctrl+A/E/K/F/B/P/N/Y first; may work for free in WKWebView
- [ ] **Services menu** — test early; right-click on selected text in WKWebView may or may not expose Services submenu
- [ ] **Scroll feel testing** — test Quotes page with 150+ quotes for jank from useScrollSpy RAF-throttled listeners vs native inertia
- [ ] **Serve startup progress** — show last stdout line as status text during the 8–10s boot (already parsing stdout)
- [x] **API key auto-save on focus loss** — currently only saves on Enter. Settings changes should apply immediately

**P2:**
- [ ] **Inactive selection dimming** — native sidebar automatic, WKWebView needs `:window-inactive` pseudo-class
- [ ] **Cursor reset in embedded mode** — `cursor: default` on non-link interactive elements behind `.bn-embedded` class
- [ ] **Option-drag copies** — SwiftUI `onDrag` with `.copy` modifier when Option held
- [ ] **Undo/Redo hiding deviation** — hidden during editing (not dimmed). Defensible, but document as known HIG deviation
- [ ] **Disabled "+" button on provider list** — permanently disabled "coming soon". Ship it or remove it
- [ ] **View menu: Enter Full Screen item** — HIG says View should include it (green button + Globe+F exist, but canonical location is View)

**Missing from audit (add):**
- [ ] **Window restoration** — persist selected project to `@SceneStorage` so relaunch remembers what was open
- [ ] **`Cmd+0` for main window** — needed when multi-window lands (Tower/Xcode convention)

### Desktop app — Accessibility review findings (22 Mar 2026)

**Critical:**
- [x] **VoiceOver label on WKWebView** — add `.accessibilityLabel("Report content")` and `.focusSection()` to both sidebar List and WebView container
- [ ] **Focus management on project switch** — call `webView.becomeFirstResponder()` on `"ready"` bridge message. Currently focus lands in undefined location after WKWebView recreation
- [ ] **Focus management on tab switch (Cmd+1-5)** — after React Router navigation, focus the first meaningful heading. ~~Add `aria-live="polite"` region in AppLayout announcing "Navigated to [tab name]"~~ (announcement done, focus management still needed)

**Major:**
- [x] **Loading overlay traps VoiceOver** — screen reader sees both spinner and half-loaded content. Add `.accessibilityHidden(!bridgeHandler.isReady)` on WebView during loading
- [x] **NavBar `role="tab"` is semantically wrong** — these are navigation links, not ARIA tabs. Remove `role="tablist"`/`role="tab"`, rely on `aria-current="page"` from React Router NavLink. Native toolbar correctly uses tab semantics
- [x] **`aria-live` announcement region in React SPA** — `AnnounceRegion` in AppLayout, `announce()` utility, wired to star/hide/tag actions and tab navigation
- [x] **Modal focus trapping** — `useInert` hook sets `inert` on `#bn-app-root` while any portal modal is open (ref-counted). Added to ModalNav, ExportDialog, FeedbackModal, ThresholdReviewModal, AutoCodeReportModal
- [x] **Edit mode entry/exit announced** — EditableText announces "Editing" / "Saved" / "Cancelled" via aria-live, plus `role="textbox"` and `aria-label="Edit text"` when editing
- [ ] **Drag handles need ARIA** — add `role="separator"` with `aria-orientation="vertical"` and `aria-valuenow`/`valuemin`/`valuemax` to sidebar resize handles
- [ ] **Dynamic Type scaling curve** — define native→web font-size mapping now (system `preferredContentSizeCategory` → CSS `font-size` on `<html>`). Observe changes via `NSApp` and re-inject

**Minor:**
- [ ] **Segmented Picker label** — change from "Tab" to "Report section" for VoiceOver clarity
- [x] **Reduced motion guard** — `ContentView.swift:222` animation needs `@Environment(\.accessibilityReduceMotion)` check
- [ ] **Verify `<h1>` in embedded mode** — Header is suppressed, confirm heading hierarchy still starts with `<h1>` in page content
- [ ] **Bare-key vs VoiceOver Quick Nav** — document in Help modal that s/h/t/j/k are inactive when VoiceOver Quick Nav is on (correct behaviour, just needs documentation)
- [ ] **Settings slider accessible values** — add contextual `accessibilityValue` to temperature slider ("0.1 — focused", "0.9 — creative")
- [ ] **API key toggle state** — add `.accessibilityAddTraits(.isToggle)` or `.accessibilityValue("Shown"/"Hidden")` to eye button

### Performance

See `docs/design-performance.md` for full audit, done items, and "not worth optimising" rationale.

| Item | Issue | Effort |
|------|-------|--------|
| ~~Cache `system_profiler` results~~ | #30 | ~~trivial~~ ✅ |
| Skip logo copy when unchanged | #31 | trivial |
| Pipeline stages 8→9 per-participant chaining | #32 | medium |
| Temp WAV cleanup after transcription | #33 | small |
| LLM response cache | #34 | medium |
| Word timestamp pruning after merge stage | #35 | small |

### Logging instrumentation

See `docs/design-logging.md` for architecture, philosophy, PII policy, and full tier breakdown. Infrastructure (log file, two-knob system) done v0.10.2. Tier 1 (LLM diagnostics + PII hardening) done v0.13.5.

**Tier 1 — done (v0.13.5):** LLM response shape logging (DEBUG, 5 providers), token usage at INFO (5 providers), AutoCode batch progress (job start/batch done/job finish), model name promoted to INFO, input filenames demoted to DEBUG (PII), importer uses project ID not name (PII).

| Item | Tier | Effort |
|------|------|--------|
| Cache hit/miss decisions in `_is_stage_cached()` | 2 | trivial |
| Concurrency queue depth at semaphore creation | 3 | trivial |
| PII entity type breakdown per session | 3 | small |
| FFmpeg command and return code on failure | 3 | trivial |
| Keychain resolution: which store, which keys | 3 | trivial |
| Manifest load/save: schema version, stage summary | 3 | trivial |

### Internal refactoring

| Item | Issue | Effort |
|------|-------|--------|
| Platform detection refactor: shared `utils/system.py` | #43 | small |

### Testing & infrastructure

| Item | Effort |
|------|--------|
| Storybook / component playground for primitives | medium |
| Playwright E2E layer 4 (structural smoke tests) | medium |
| Playwright E2E write-action tests (11 actions: star, hide, edit, tag, etc.) | large |

---

## Items only tracked here (not in issues)

These are too small for issues or are internal-only concerns.

- [ ] **SVG icon set** — replace all character glyphs (delete circles, modal close, search clear) with SVG icons. Candidates: Lucide, Heroicons, Phosphor, Tabler. See `docs/design-system/icon-catalog.html`
- [ ] **Relocate AI tag toggle** — removed from toolbar (too crowded); needs a new home. Code commented out in `render/report.py` and `codebook.js`/`tags.js`
- [ ] **User research panel opt-in** — optional email field in feedback modal
- [ ] **Miro bridge** — Miro-shaped CSV export → API integration → layout engine. See `docs/private/design-miro-bridge.md`
- [ ] **Custom prompts** — user-defined tag categories via `bristlenose.toml` or `prompts.toml`
- [ ] **Framework acronym prefixes on badges** — small-caps 2–3 letter author prefix (e.g. `JJG`, `DN`). CSS class exists, parked until visual pattern finalised
- [ ] **Drag-to-reorder codebook frameworks** — researchers drag framework `<details>` sections to prioritise. Persist order per project
- [ ] **Pass transcript data to renderer** — avoid redundant disk I/O in `render/report.py`
- [ ] **People.yaml web UI** — in-report UI to update unidentified participants. API endpoint exists, missing the HTML renderer and UX design. Part of Moderator Phase 2 (#25)
- [ ] **Post-analysis review panel** — non-modal, dismissable panel after pipeline completes in serve mode for name correction, token summary, coverage overview

### Investigations (no commitment)

- [ ] **Sentiment badges as a built-in codebook framework** — sentiments are conceptually just another codebook; refactoring would unify with thresholds, review dialog, accept/deny. Big but significant simplification
- [ ] **Tag namespace uniqueness + import merge strategy** — flat namespace, clash detection, provenance tracking (user-created vs framework vs AutoCode)
- [ ] **Tokenise acceptance flash as design system pattern** — generalise `badge-accept-flash` into reusable `.bn-confirm-flash` + `useFlash(key)` hook
- [ ] **Canonical tag → colour as first-class schema** — persist `colour_set`/`colour_index` on `TagDefinition` to survive reordering; eliminate client-side colour computation
- [ ] **Sidebar filter undo history stack** — multi-step undo for tag filter state changes in the Tag Sidebar (show-only clicks, tick toggles). See `docs/design-codebook-autocomplete.md` Decision 6b
- [ ] **Measure-aware leading** — line-height should increase with wider columns (longer measure needs more leading for the eye to track back). Current `--bn-text-*-lh` tokens are fixed per size (Bringhurst size→leading already shipped). Explore interpolating line-height based on container width across the 23rem–52rem range. Mockup: `docs/mockups/measure-aware-leading.html`. Playground already has a line-height slider for manual tuning. Reference: Bringhurst §2.1.2

### Transcript page interactions

Ideas from 9 Feb 2026 session, roughly in order of effort:

- [ ] User tags on transcript page (small)
- [ ] Tidy up extent bars (small)
- [ ] Expand/collapse sections and themes in main report (medium)
- [ ] Pulldown menu on margin annotations — move quote to different section/theme (medium)
- [ ] Flag uncited quote for inclusion (medium–large)
- [ ] Drag-and-drop quote reordering (large)

### Vanilla JS refactoring (frozen — static render path only)

These apply to the legacy vanilla JS in `bristlenose/theme/js/`. Per CLAUDE.md, vanilla JS is frozen (data-integrity fixes only, no feature work). Low priority.

- [ ] Typography and icon audit — 16 distinct font-sizes, consolidate to ~10
- [ ] Tag-count aggregation (3 implementations) → shared `countUserTags()`
- [ ] Shared user-tags data layer
- [ ] `isEditing()` guard deduplication
- [ ] Inline edit commit pattern (~6 repetitions) → shared helper
- [ ] Close button CSS base class → `.close-btn` atom
- [ ] Input focus CSS base class → `.bn-input` atom
- [ ] Checkbox atom — extract ghost checkbox style

### file:// → http:// migration prep

- [ ] Namespace localStorage keys by project slug (prevents multi-report collision)
- [ ] Tighten `postMessage` origin from `'*'` to same-origin

---

## Dependency maintenance

Bristlenose has ~30 direct + transitive deps across Python, ML, LLM SDKs, and NLP. CI runs `pip-audit` on every push (informational, non-blocking).

### Quarterly dep review (next: May 2026, then Aug 2026, Nov 2026)

- [ ] **May 2026** — Run `pip list --outdated`. Bump floor pins in `pyproject.toml` only if there's a security fix, a feature you need, or the floor is 2+ major versions behind
- [ ] **Aug 2026** — Same
- [ ] **Nov 2026** — Same

### Annual review (next: Feb 2027)

- [ ] **Feb 2027** — Full annual review:
  - Check Python EOL dates — Python 3.10 EOL is Oct 2026; if past EOL, bump `requires-python`, `target-version`, `python_version`
  - Check faster-whisper / ctranslate2 project health
  - Check spaCy major version
  - Check Pydantic major version
  - Rebuild snap; review `pip-audit` CI output

### Risk register

| Dependency | Risk | Escape hatch |
|---|---|---|
| faster-whisper / ctranslate2 | High — fragile chain, maintenance varies | `mlx-whisper` (macOS), `whisper.cpp` bindings |
| spaCy + thinc + presidio | Medium — spaCy 3.x pins thinc 8.x | Contained to PII stage; can pin 3.x indefinitely |
| anthropic / openai SDKs | Low — backward-compatible | Floor pins are fine |
| Pydantic | Low — stable at 2.x | Large migration but not urgent |
| Python itself | Low (now) — 3.10 EOL Oct 2026 | Bump floor at EOL |
| protobuf (transitive) | Low — CVE-2026-0994 (DoS); we don't parse untrusted protobuf | Resolves when patched |

---

## Key files to know

| File | What it does |
|------|-------------|
| `pyproject.toml` | Package metadata, deps, tool config (version is dynamic — from `__init__.py`) |
| `bristlenose/__init__.py` | **Single source of truth for version** (`__version__`) |
| `bristlenose/cli.py` | Typer CLI entry point |
| `bristlenose/config.py` | Pydantic settings (env vars, .env, bristlenose.toml) |
| `bristlenose/pipeline.py` | Pipeline orchestrator |
| `bristlenose/people.py` | People file: load, compute stats, merge, write, display name map |
| `bristlenose/stages/s12_render/` | HTML report renderer package |
| `bristlenose/theme/` | Atomic CSS design system |
| `bristlenose/theme/js/` | Report JavaScript modules (frozen — static render path only) |
| `bristlenose/llm/prompts/` | LLM prompt templates |
| `bristlenose/doctor.py` | Doctor check logic |
| `frontend/` | Vite + React + TypeScript SPA |
| `.github/workflows/` | CI (ci.yml), release (release.yml), snap (snap.yml) |
| `snap/snapcraft.yaml` | Snap recipe |

## Key URLs

- **Repo:** https://github.com/cassiocassio/bristlenose
- **Issues:** https://github.com/cassiocassio/bristlenose/issues
- **PyPI:** https://pypi.org/project/bristlenose/
- **Homebrew tap:** https://github.com/cassiocassio/homebrew-bristlenose
- **CI runs:** https://github.com/cassiocassio/bristlenose/actions

---

## Doctor: serve-mode checks + Vite auto-discovery

See `docs/design-serve-doctor.md` for full design. Summary: 4 new doctor checks, Vite auto-discovery via `/__vite_ping`, replace hardcoded port in `app.py`.

---

## Design docs

| Document | Covers |
|----------|--------|
| `docs/design-reactive-ui.md` | Framework comparison, risk assessment (partially superseded by React migration) |
| `docs/design-react-migration.md` | **React migration plan** (Steps 1–10, all complete) |
| `docs/design-react-component-library.md` | 16-primitive component library (complete) |
| `docs/design-llm-providers.md` | Provider roadmap |
| `docs/design-performance.md` | Performance audit |
| `docs/design-export-sharing.md` | Export and sharing phases 0–5 |
| `docs/design-html-report.md` | HTML report, people file, transcript pages |
| `docs/design-responsive-layout.md` | Responsive layout, density setting, breakpoints |
| `docs/design-doctor-and-snap.md` | Doctor command, snap packaging |
| `docs/design-serve-doctor.md` | Serve-mode doctor checks, Vite auto-discovery |
| `docs/design-research-methodology.md` | Quote selection, sentiment taxonomy, clustering rationale |
| `docs/design-pipeline-resilience.md` | Manifest, event sourcing, resume, provenance |
| `docs/design-logging.md` | Persistent log file, two-knob system |
| `docs/design-test-strategy.md` | Gap audit, Playwright plan, `data-testid` convention |
| `docs/design-desktop-app.md` | macOS app, SwiftUI, PyInstaller sidecar |
| `docs/design-session-management.md` | Re-import, enable/disable, quarantine |
| `docs/design-codebook-island.md` | Migration audit, API design, drag-drop |
| `docs/design-signal-elaboration.md` | Interpretive names, pattern types |
| `docs/design-transcript-editing.md` | Section strike, text correction, prior art |
| `docs/design-sidebar.md` | Dual-sidebar layout (TOC left, Tags right) |
| `docs/design-windows-ci.md` | Windows CI strategy, compatibility audit, phased plan |

---

## Done (reverse chronological)

- [x] **Unified i18n architecture** (Mar 2026) — single source of truth (`bristlenose/locales/`), desktop `I18n.swift`, bridge locale sync, startup flash prevention, Weblate plan, Apple glossary cross-check process. See `docs/design-i18n.md`
- [x] **Help modal** (Mar 2026) — 3 phases: platform-aware shortcuts, typography tokens, entrance animation, custom tooltips with keyboard shortcut badges
- [x] **Bulk actions on multi-selection** (Mar 2026) — star, hide, tag respect click + shift+click range selection
- [x] **Sidebar push animation** (Mar 2026) — drag-open pushes content; keyboard shortcuts and click trigger push animation
- [x] **Pipeline error/warning display** (Mar 2026) — red ✗ for failed stages, yellow ⚠ for partial success
- [x] **Render refactor** (Mar 2026) — `render_html.py` broken into `bristlenose/stages/s12_render/` package (8 submodules). Static render formally deprecated
- [x] **Numeric stage prefixes** (Mar 2026) — `bristlenose/stages/*.py` → `s01_ingest.py` … `s12_render/`
- [x] **Sidebar architecture** (Mar 2026) — 6-column grid, TOC + tag sidebars, rail drag-to-open, minimap, scroll spy, eye toggle, keyboard shortcuts
- [x] **Heading anchor scroll fix** (Mar 2026) — `scroll-margin-top` for section headings in React SPA
- [x] **Tag provenance** (Mar 2026) — `QuoteTag.source` column: `"human"` vs `"autocode"`, preserved across bulk replace
- [x] **Playwright E2E harness layers 1–3** (Mar 2026) — console error monitor, link crawler, network assertion. Chromium + WebKit
- [x] **React migration Steps 1–10** (Mar 2026) — full SPA with React Router, PlayerContext, FocusContext, keyboard shortcuts, export, app shell. See `docs/design-react-migration.md`
- [x] **CI stabilisation** (Mar 2026) — frontend lint/typecheck/vitest in GitHub Actions
- [x] **Export (Step 10)** — self-contained HTML download, blob-URL'd JS chunks, hash router for file://, optional anonymisation
- [x] **About panel redesign** — sidebar layout with 5 sections
- [x] **Configuration reference panel** in Settings
- [x] **Morville Honeycomb codebook** added
- [x] **Context expansion** — hover-reveal chevrons on timecodes, progressive transcript disclosure in quote cards
- [x] **Split speaker badges** — two-tone pill (code left, name right), settings toggle
- [x] **16-primitive React component library** (4 build rounds, 182 Vitest tests)
- [x] **Serve mode** — FastAPI + SQLite + React SPA, 22-table schema, full CRUD
- [x] **AutoCode** — engine, 7 API endpoints, Norman/Garrett/Plato prompts, threshold review dialog, 96 tests
- [x] **Signal elaboration** — LLM-generated interpretive names, pattern classification, sparkbar charts
- [x] **Video thumbnails** — auto-extracted keyframes, heuristic placement
- [x] **Analysis page** — signal cards, heatmaps, codebook grids, drill-down
- [x] **Pipeline crash recovery** (Phase 1a–1d-ext) — manifest-based resume, per-session tracking
- [x] **Phase 1 codebook import** — picker, preview, import, remove with impact stats
- [x] **Desktop app scaffold** — SwiftUI macOS shell, 5-state launcher, bundled sidecar
- [x] **Time estimation** — Welford's online algorithm, progressive disclosure
- [x] **Logging** — persistent log file, two-knob system (terminal + file)
- [x] **Session-count guard** — prompt before processing >16 sessions
- [x] **Status command** — `bristlenose status <folder>` reads manifest
- [x] **All LLM providers** — Claude, ChatGPT, Azure OpenAI, Gemini, Ollama
- [x] **Keychain integration** — `bristlenose configure`, native credential storage
- [x] **Doctor command** — 7 checks, pre-flight gate, first-run auto-doctor
- [x] **Codebook + hidden quotes** — tag organisation, colour-coded badges, group CRUD
- [x] **Keyboard shortcuts + search + multi-select** — j/k, star, tag, bulk actions
- [x] **Full 12-stage pipeline** — ingest → render, concurrent LLM + FFmpeg
- [x] **HTML report** — CSS theme, timecodes, video player, dark mode, people file, transcripts
- [x] **Published** — PyPI, Homebrew tap, snap (CI builds), man page
- [x] **CLI** — Cargo-style output, file-level progress, `--llm` aliases, British aliases
