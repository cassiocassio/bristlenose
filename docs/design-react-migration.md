# React Migration Plan — Vanilla JS Shell → Full SPA

## Context

Bristlenose serve mode is a hybrid: 7 React islands render the content panels (dashboard, sessions table, quotes, codebook, analysis, transcripts) inside a vanilla JS shell that owns everything else — tab navigation, toolbar, settings, keyboard shortcuts, player, and state sync.

This worked well during the island-by-island migration, but the hybrid architecture now causes problems:

1. **Link escapes** — transcript page tabs navigate to static HTML files instead of staying in the served app (fixed with regex surgery in `app.py`, but fragile)
2. **Hash routing conflicts** — `#quotes` for tabs vs `#t-123` for timecodes vs `#src=...&t=...` for player params
3. **No shared state** — each island fetches data independently; the vanilla toolbar can't filter React-rendered quotes; search/tag-filter operate on DOM elements that React replaces
4. **Two interaction layers** — adding a feature requires writing both vanilla JS DOM manipulation AND React components
5. **Export blocked** — the planned DOM snapshot export requires a complete React app, not a hybrid

The vanilla JS shell owns ~2,800 lines across 25 modules. The React side has 16 primitives, 7 islands, 12 API endpoints, and 330+ tests. The path forward is clear: migrate the shell to React, smallest pieces first.

This plan supersedes `docs/design-reactive-ui.md` (migration strategy sections) and extends `docs/design-react-component-library.md` (which covered primitives — all 16 now complete).

## Sequencing principle

**Trivial → heavyweight, unless dependencies force otherwise.** Each step is self-contained and shippable. The vanilla JS modules are frozen for feature work (CLAUDE.md convention), so there's no pressure to migrate everything at once — each step just shrinks the vanilla surface.

## Migration steps

### Step 1: Settings panel → React island _(small)_ ✓ DONE

The easiest migration. Three radio buttons, one localStorage key, one DOM attribute.

- **Replaces:** `settings.js` (105 lines)
- **Dependencies:** None — completely self-contained
- **What to build:** `SettingsPanel` island. Controlled radio group. Reads `bristlenose-appearance` from localStorage on mount. Sets `data-theme` attr + `style.colorScheme` on `<html>`. Logo `<picture><source>` swap logic
- **Mount point:** Add `<!-- bn-settings -->` markers around `panel-settings` content in `render_html.py`
- **Test:** Vitest unit test. Manual: toggle appearance in serve mode, reload preserves setting

### Step 2: About panel → React island _(small)_ ✓ DONE

Static content with one dynamic element (version string from `/api/health`).

- **Replaces:** Inline HTML in `render_html.py` lines 530–578. Absorbs `AboutDeveloper` island (already React). Moves `feedback.js` help overlay here
- **Dependencies:** None
- **What to build:** `AboutPanel` island. Static JSX. Keyboard shortcuts table (reusable data, shared with future help modal). Version from API. Dev section (conditional on `--dev`)
- **Mount point:** Add `<!-- bn-about -->` markers
- **Test:** Vitest. Manual: version displays, links work, dev section appears with `--dev`

### Step 3: QuotesStore context _(medium — infrastructure)_ ✓ DONE

Cross-island state management. This is infrastructure, not a UI change, but it unblocks the toolbar migration. Without it, the React toolbar has no way to tell React quote islands what to filter.

- **Replaces:** Nothing directly — but absorbs the `localStorage → apiPut` fire-and-forget pattern from `storage.js` + `api-client.js`
- **Dependencies:** None to create; Steps 4–8 depend on it
- **What was built:** Module-level store (`frontend/src/contexts/QuotesContext.tsx`) with `useSyncExternalStore` — works across separate React roots without a shared provider wrapper. 11 action functions (`toggleStar`, `toggleHide`, `commitEdit`, `addTag`, `removeTag`, `deleteBadge`, `restoreBadges`, `acceptProposedTag`, `denyProposedTag`, `initFromQuotes`, `resetStore`). `useQuotesStore()` hook for React subscription. State shape includes `hidden`, `starred`, `edits`, `tags` (as `TagResponse[]` for colour info), `deletedBadges`, `proposedTags`, plus Step 4 placeholders (`viewMode`, `searchQuery`, `tagFilter`). `QuoteGroup.tsx` now reads from the store and delegates mutations — removed `stateMap`/`stateRef`/`QuoteLocalState`/`onStateChange`. Both `QuoteSections` and `QuoteThemes` call `initFromQuotes()` after fetch; `bn:tags-changed` uses `replace: true` for atomic clear-and-set. 18 Vitest tests. Key decision: used module-level store instead of React Context because the two quote islands mount as separate `createRoot()` calls
- **Test:** 18 Vitest tests for store, actions, and cross-island sharing

### Step 4: Toolbar → React island _(large)_ ✓ DONE

The first step where React replaces a user-facing vanilla JS interaction surface. Also built the **Toast** primitive (deferred from Round 2) — the CSV export "Copied!" feedback needs it.

- **Replaces:** `toolbar.html` template + `search.js` (~420 lines) + `tag-filter.js` (~350 lines) + `view-switcher.js` (~170 lines) + `csv-export.js` (~250 lines). Vanilla JS toolbar init functions no-op in serve mode (DOM targets replaced by React mount div); shared utilities (`showToast`, `copyToClipboard`) remain available for other vanilla JS modules
- **Dependencies:** Step 3 (QuotesStore). The toolbar writes `searchQuery`, `viewMode`, `tagFilter` to the store; quote islands read them to filter
- **What was built:** `Toolbar` island (organism) composing 4 molecules: `SearchBox`, `TagFilterDropdown`, `ViewSwitcher`, CSV export button. Headless `useDropdown()` hook for click-outside + Escape dismiss (shared by TagFilterDropdown and ViewSwitcher). `Toast` component + imperative `toast()` wrapper. `filterQuotes()` pure utility for data-level filtering. `highlightText()` utility wrapping matches in `<mark>` elements. `ToolbarButton` atom (icon + label + arrow slots). `QuoteSections` and `QuoteThemes` islands read filter state from store and apply `filterQuotes()` in `useMemo`. `QuoteCard` applies `highlightText()` in idle mode. Mutual dropdown exclusion via parent-controlled `activeDropdown` state. Tag filter fetches codebook independently. CSV export builds from store data, not DOM
- **Key change:** Search and tag filtering moved from DOM manipulation (`.style.display = 'none'` on `blockquote` elements) to data filtering in the React quote islands. Sections with zero matches are not rendered (instead of hidden). This eliminates the fundamental problem of vanilla JS trying to manipulate React-rendered DOM
- **Mount point:** `<!-- bn-toolbar -->` markers added in `render_html.py`; `_REACT_TOOLBAR_MOUNT` in `app.py` replaces with mount div
- **Test:** 87 new Vitest tests across 12 test files — unit tests for each component, hook, and utility, plus 10 integration tests verifying toolbar → store → quote island filtering flow
- **Design doc:** Detailed plan at `.claude/plans/dynamic-wobbling-grove.md` — 7 discussion areas (component decomposition, state ownership, communication, toast, dropdown, portability, performance) with options, pros/cons, and resolved decisions

### Step 5: Tab navigation → React Router ✓ DONE

The structural hinge — everything before it is self-contained, everything after it assumes routing works.

- **Replaces:** `global-nav.js` (~436 lines) — tab switching, hash routing, history/popstate, session drill-down, cross-tab stat links, speaker navigation
- **Dependencies:** Steps 1–4 (settings, about, store, toolbar must be React before their tabs become routes)
- **What was built:** `react-router-dom` v7.13.1 with `createBrowserRouter` (data router API). Single React root (`#bn-app-root`) replaces 11 separate `createRoot()` calls in serve mode
  - `NavBar` component — 5 text tabs + 2 icon tabs (Settings, About) using `<NavLink>` with existing `.bn-tab.active` CSS
  - `AppLayout` — `<NavBar />` + `<Outlet />`, installs backward-compat navigation shims on mount
  - 8 thin page wrappers in `frontend/src/pages/` — each composes existing island components (`QuotesTab` = Toolbar + QuoteSections + QuoteThemes)
  - SPA catch-all in FastAPI (`GET /report/{path:path}`), transcript file route defined first for priority
  - `<!-- bn-app -->` markers in `render_html.py` — one `re.sub` in `app.py` replaces the entire nav + panel region with `<div id="bn-app-root">`, making individual island marker substitutions no-ops
  - `useScrollToAnchor` hook — retry-aware scroll (50 × 100ms = 5s) for async-rendered targets
  - `useAppNavigate` hook — wraps `useNavigate()` with tab-name-to-path mapping
  - Backward-compat shims (`frontend/src/shims/navigation.ts`) install `window.switchToTab`, `window.scrollToAnchor`, `window.navigateToSession` delegating to React Router
  - Hash-to-pathname redirect (`frontend/src/utils/hashRedirect.ts`) — old `#quotes` bookmarks → `/report/quotes/`
  - `initGlobalNav()` no-op guard when `#bn-app-root` exists (same pattern as toolbar)
  - `main.tsx` dual mode: SPA (`RouterProvider`) when `#bn-app-root` exists, legacy island mode (dynamic `import()`) as fallback
- **Routes:** `/report/` (project), `/report/sessions/` (grid), `/report/sessions/:sessionId` (transcript), `/report/quotes/`, `/report/codebook/`, `/report/analysis/`, `/report/settings/`, `/report/about/`
- **Key simplification:** Pathname-based routing frees hash fragments for scroll targets. `#t-123` (timecodes), `#section-name` (deep links) all just work as fragments on the correct route. The `#quotes` vs `#t-123` conflict disappears
- **Link format change:** `sessions/transcript_s1.html#t-123` → `/report/sessions/s1#t-123` (clean session ID, matches API pattern)
- **Files:** 15 new files, 14 modified files (36 total in commit). Detailed plan at `.claude/plans/generic-scribbling-feigenbaum.md`
- **Test:** 45 new Vitest tests (635 total). NavBar, router, hash redirect, scroll hook, navigate hook, navigation shims
- **Post-QA fixes:** AnalysisPage slug generation aligned with QuoteSections/QuoteThemes (was stripping special chars, now only replaces spaces — matching anchor IDs). Scroll retry window increased from 2s to 5s for cross-tab navigation where destination page needs to mount + fetch data

### Step 6: Player integration _(medium)_ ✓ DONE

- **Replaces:** `player.js` (~250 lines) — popout window lifecycle, `postMessage` IPC, glow sync, `setInterval` close-poll
- **Dependencies:** Step 5 (router — player glow needs route context)
- **What was built:** `PlayerProvider` context + `usePlayer` hook wrapping `AppLayout`. `seekTo(pid, seconds)` manages popout window lifecycle. `TimecodeLink` calls `seekTo` via context (prevents default `href="#t=..."` navigation). Glow highlighting via DOM class manipulation (refs, not React state — 4× /sec timeupdate messages would re-render hundreds of cards). `buildGlowIndex` keys transcript segments by session ID (from URL pathname), not speaker code. Progress bar via `--bn-segment-progress` CSS custom property. `initPlayer()` bail-out when `bn-app-root` exists
- **Key fix:** `BRISTLENOSE_VIDEO_MAP` and `BRISTLENOSE_PLAYER_URL` exposed on `window` from IIFE in `render_html.py` — React runs in a separate ES module context and can't see IIFE-scoped `var` declarations. Also fixed session routing: non-transcript URLs (`/report/sessions/s1`) now serve SPA HTML instead of 404
- **Test:** 28 Vitest tests for PlayerContext, TimecodeLink integration, glow index building. 28 serve tests pass

### Step 7: Keyboard shortcuts _(medium-large)_ ✓ DONE

- **Replaces:** `focus.js` (~645 lines) — j/k navigation, multi-select, bulk actions, help overlay, Escape cascade
- **Dependencies:** Steps 3 (store for star/hide/tag), 4 (toolbar for `/`=search), 5 (router for `?`=about), 6 (player for Enter=play)
- **What was built:** `FocusProvider` context exposing `focusedId`, `selectedIds`, `setFocus`, `toggleSelection`, `selectRange`, `clearSelection`, `moveFocus`, `registerVisibleQuoteIds`, `getVisibleQuoteIds`. `useKeyboardShortcuts` hook — single `useEffect` with `keydown` listener + background click handler. `HelpModal` component (? toggle). QuoteCard click-to-focus with modifier support (Cmd/Ctrl+click toggle, Shift+click range). Hide handler registry (`registerHideHandler`/`hideQuote`) so keyboard `h` triggers `QuoteGroup.handleToggleHide` (fly-up ghost animation) instead of raw store toggle. `initFocus()` bail-out when `bn-app-root` exists
- **Key change:** `getVisibleQuotes()` replaced by data-derived `registerVisibleQuoteIds` — no more DOM queries with `offsetParent`. QuoteSections and QuoteThemes register their visible quote IDs; FocusProvider merges them in order
- **Test:** 62 new Vitest tests across FocusContext, useKeyboardShortcuts, HelpModal. 703 total frontend tests pass

### Step 8: Retire remaining vanilla JS _(medium — mostly deletion)_ ✓ DONE

At this point, every vanilla JS module has been replaced by a React equivalent. This step removes them from the serve path.

- **Retires:** All 26 modules in `_JS_FILES` — `storage.js`, `api-client.js`, `badge-utils.js`, `modal.js`, `codebook.js`, `player.js`, `starred.js`, `editing.js`, `tags.js`, `histogram.js`, `csv-export.js`, `view-switcher.js`, `search.js`, `tag-filter.js`, `hidden.js`, `names.js`, `focus.js`, `feedback.js`, `global-nav.js`, `transcript-names.js`, `transcript-annotations.js`, `journey-sort.js`, `analysis.js`, `settings.js`, `person-display.js`, `main.js`
- **What changed:** `_strip_vanilla_js()` in `app.py` uses the existing `_JS_MARKER` boundary to remove concatenated module code from the IIFE while keeping global declarations (`BRISTLENOSE_VIDEO_MAP`, `BRISTLENOSE_PLAYER_URL`, `BRISTLENOSE_ANALYSIS`) that React reads from `window.*`. Called from `_transform_report_html()` (both dev and prod paths). Dead code removed: 9 individual island marker substitutions, `_replace_baked_js()` calls from dev routes, 9 `_REACT_*_MOUNT` constants. `_JS_FILES` list in `render_html.py` stays for `bristlenose render` (offline HTML). 6 new tests
- **Test:** `bristlenose serve` works with zero vanilla JS. `bristlenose render` still produces a working static report

### Step 9: React app shell — kill the skeleton _(large)_

The serve path stops reading the static HTML file and doing `re.sub` marker replacement. Instead, it serves the Vite-built SPA.

- **Replaces:** `_transform_report_html()`, `_transform_transcript_html()`, all `_REACT_*_MOUNT` constants, `_replace_baked_js()`, the marker-based substitution pattern. The `serve_mode` parameter in `render_html.py`
- **What to build:** React `<Header>` (logo, project name, subtitle), `<Footer>` (version, links). The Vite `index.html` becomes the SPA entry point. FastAPI serves it for all `/report/*` routes; React Router handles client-side routing. API routes unchanged
- **What stays:** `render_html.py` continues producing static HTML for `bristlenose render`. CSS in `bristlenose/theme/` is shared. The regex surgery in `app.py` is deleted — no more link escape bugs, ever
- **Test:** `bristlenose serve` serves a complete React SPA. No Jinja2 HTML in the serve path. All tabs, navigation, interactions work

### Step 10: Export — DOM snapshot _(large — new feature)_

Enabled by the complete React app. Not a migration step, but the payoff.

- **What to build:** Export button → dialog (report-only vs full archive, anonymise toggle). React app detects `BRISTLENOSE_EMBEDDED_DATA` (export mode) vs `BRISTLENOSE_API_BASE` (serve mode). Export produces a self-contained HTML file with embedded JSON state, inlined CSS, React bundle
- **Dependencies:** Step 9 (full React app shell)
- **Design:** Already specified in `docs/design-export-sharing.md`
- **Test:** Export report, open in different browser without Bristlenose running. All tabs render, search works

## Dependency graph

```
Step 1 (Settings) ✓   Step 2 (About) ✓   Step 3 (QuotesStore) ✓
    \                     |                    /
     \                    |                   /
      +-------------------+------------------+
                          |
                    Step 4 (Toolbar + Toast) ✓
                          |
                    Step 5 (React Router) ✓
                          |
                    Step 6 (Player) ✓
                          |
                    Step 7 (Keyboard) ✓
                          |
                    Step 8 (Retire vanilla JS) ✓  <-- you are here
                          |
                    Step 9 (App shell)
                          |
                    Step 10 (Export)
```

**Steps 1, 2, 3 can run in parallel** — no dependencies between them.
**Steps 5–10 are sequential** — each builds on the previous.

## What stays frozen

| Thing | Why |
|-------|-----|
| `bristlenose render` | Offline HTML fallback — works today, no changes |
| `bristlenose/theme/js/` | Kept for offline path; data-integrity fixes only |
| `bristlenose/theme/` CSS | Shared between both paths — changes apply to both |
| 16 React primitives | Already built and tested — consumed as-is |
| 12 API endpoints | Already built — consumed as-is |

## Risks

**Step 5 is the structural hinge.** Everything before it is independently shippable and low-risk. Everything after it assumes React Router works correctly for all navigation paths (tabs, deep links, back/forward, cross-tab stat links, session drill-down). Mitigation: maintain `window.switchToTab` / `window.navigateToSession` shims during transition.

**Step 4 (toolbar) must be atomic for the quotes tab.** The vanilla toolbar and React toolbar cannot coexist — they'd both try to filter the same content. When the toolbar migrates, search/filter/view-switch must all move together.

## Rough timeline

| Step | Effort |
|------|--------|
| 1. Settings | Half day |
| 2. About | Half day |
| 3. QuotesStore | 1–2 days |
| 4. Toolbar + Toast | 3–4 days |
| 5. React Router | 3–4 days |
| 6. Player | 1–2 days |
| 7. Keyboard | 2–3 days |
| 8. Retire vanilla JS | 1 day |
| 9. App shell | 2–3 days |
| 10. Export | 3–5 days |

**Total: ~3–4 weeks of focused work.** Steps 1–4 can happen incrementally between other feature work. Step 5 is a concentrated push.

## Files to modify

| File | Role in migration |
|------|-------------------|
| `frontend/src/main.tsx` | Entry point — evolves into React Router root |
| `frontend/src/islands/` | New islands: SettingsPanel, AboutPanel, Toolbar, NavBar |
| `frontend/src/contexts/` | New: QuotesStore, PlayerProvider, FocusProvider |
| `frontend/src/utils/api.ts` | Already exists — extended for new data fetching |
| `bristlenose/server/app.py` | Marker substitution → SPA serving |
| `bristlenose/stages/render_html.py` | Add markers for settings/about/toolbar; eventually `serve_mode` removed |
| `bristlenose/theme/templates/` | `global_nav.html`, `toolbar.html` become dead code |
| `bristlenose/theme/js/` | Modules retired one by one from serve path |
| `frontend/package.json` | Add `react-router-dom` at Step 5 |

## Relationship to existing design docs

| Doc | Status after this plan |
|-----|----------------------|
| `docs/design-reactive-ui.md` | Migration strategy sections superseded. Framework choice, business risk assessment, file:// audit, server options, and testing strategy sections remain valid reference |
| `docs/design-react-component-library.md` | Primitive dictionary and build sequence complete (all 16 primitives shipped). Coverage matrix and CSS alignment sections remain valid reference |
| `docs/design-export-sharing.md` | Unchanged — Step 10 implements the design described there |
| `docs/design-serve-milestone-1.md` | Complete — domain schema, importer, sessions API all shipped |
