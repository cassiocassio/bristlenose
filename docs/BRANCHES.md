# Active Feature Branches

This document tracks active feature branches to help multiple Claude sessions coordinate without conflicts.

**Updated:** 18 Mar 2026 (settings-modal closed)

---

## Worktree Convention

Each active feature branch gets its own **git worktree** — a full working copy in a separate directory. This lets multiple Claude sessions work on different features simultaneously without interfering.

**Directory pattern:** `/Users/cassio/Code/bristlenose_branch <name>`

| Directory | Branch | Purpose |
|-----------|--------|---------|
| `bristlenose/` | `main` | Main repo, releases, hotfixes |
| `bristlenose_branch symbology/` | `symbology` | § ¶ ❋ Unicode prefix symbols for sections, quotes, themes |
| `bristlenose_branch highlighter/` | `highlighter` | Highlighter feature |
| `bristlenose_branch living-fish/` | `living-fish` | Animated "living portrait" logo for serve mode |
| `bristlenose_branch drag-push/` | `drag-push` | Sidebar drag-to-open uses push mode (not overlay) |
| `bristlenose_branch responsive-signal-cards/` | `responsive-signal-cards` | Responsive signal cards |
| `bristlenose_branch analysis-matrices-heatmaps-pane/` | `analysis-matrices-heatmaps-pane` | Analysis tab bottom inspector panel with heatmap matrices |



**Creating a new feature branch worktree:**

```bash
# From the main repo:
cd /Users/cassio/Code/bristlenose

# Create the branch (if it doesn't exist) and the worktree in one go:
git branch my-feature main
git worktree add "/Users/cassio/Code/bristlenose_branch my-feature" my-feature

# Or if the branch already exists:
git worktree add "/Users/cassio/Code/bristlenose_branch my-feature" my-feature
```

**Each worktree needs its own venv** to run tests:

```bash
cd "/Users/cassio/Code/bristlenose_branch my-feature"
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

**Listing worktrees:** `git worktree list` (from any worktree)

**Removing a worktree** (after merging to main):

**Important:** Always `cd` to the main repo *before* removing a worktree. If a Claude session or terminal has its CWD inside the worktree directory, removing it will break that shell — every subsequent command fails with "path does not exist" and the session is unrecoverable.

```bash
# 1. Switch to main repo FIRST (never remove a worktree from inside it)
cd /Users/cassio/Code/bristlenose

# 2. Remove the worktree and branch
git worktree remove "/Users/cassio/Code/bristlenose_branch my-feature"
git branch -d my-feature

# 3. If the directory was already deleted (rm -rf or Finder):
git worktree prune          # cleans stale worktree refs
git branch -d my-feature    # delete the branch

# 4. If also on remote:
git push origin --delete my-feature
```

**Rules:**
- `bristlenose/` always stays on `main` — never check out a feature branch there
- Each Claude session should confirm which worktree it's operating in at session start
- Commits made in any worktree are immediately visible to all others (shared `.git`)
- Don't run `git checkout` to switch branches inside a worktree — that defeats the point

---

## How to Use This File

When starting a new Claude session on a feature branch:
1. Check this file to see what other branches are active
2. Confirm you're in the right worktree directory
3. Note which files other branches are touching
4. Avoid editing those files unless necessary
5. Update this file when you create/complete a branch

When merging back to main:
1. Read the merge plan for your branch
2. Check for conflicts with other branches
3. Update this file to mark your branch as merged
4. Remove the worktree

---

## Backup Strategy

Feature branches are pushed to GitHub for backup without triggering releases (only `main` triggers releases). Use `git push origin <branch-name>` to back up.

| Branch | Local worktree | GitHub remote |
|--------|---------------|---------------|
| `main` | `bristlenose/` | `origin/main` (push via `origin/main:wip` until release time) |
| `symbology` | `bristlenose_branch symbology/` | `origin/symbology` |
| `highlighter` | `bristlenose_branch highlighter/` | `origin/highlighter` |
| `living-fish` | `bristlenose_branch living-fish/` | `origin/living-fish` |
| `drag-push` | `bristlenose_branch drag-push/` | local only |
| `responsive-signal-cards` | `bristlenose_branch responsive-signal-cards/` | local only |


---

## Active Branches

### `highlighter` — started 13 Feb 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch highlighter`

**Goal:** Highlighter feature (TBD — to be detailed when scope is defined).

**Files likely to touch:**
- TBD

---

### `symbology` — started 12 Feb 2026

**Worktree:** `/Users/cassio/Code/bristlenose_branch symbology`

**Goal:** Add consistent Unicode prefix symbols (§ Section, ¶ Quote, ❋ Theme) across all user-facing surfaces — navigation, headings, dashboards, analysis, tooltips, and text output.

**Files likely to touch:**
- `bristlenose/stages/render_html.py` — dashboard stats, pane headings, template params
- `bristlenose/stages/s12_render_output.py` — markdown heading call sites
- `bristlenose/theme/templates/toc.html` — TOC headings
- `bristlenose/theme/templates/global_nav.html` — tab labels
- `bristlenose/theme/templates/analysis.html` — analysis page headings
- `bristlenose/theme/js/analysis.js` — signal cards, heatmap headers
- `bristlenose/theme/js/transcript-annotations.js` — margin label tooltips
- `bristlenose/theme/js/codebook.js` — quote count tooltips

---

### `living-fish` — started 26 Feb 2026

**Status:** Just started
**Worktree:** `/Users/cassio/Code/bristlenose_branch living-fish/`
**Remote:** `origin/living-fish`

**What it does:** Animated "living portrait" bristlenose logo for serve mode. AI-generated video loop (WebM VP9 alpha + MOV HEVC alpha) with subtle breathing, gill pulsing, and fin movement — replacing the static PNG in serve mode only. Also fixes dark-mode logo by switching to a transparent-background PNG (eliminates `mix-blend-mode: lighten` hack and `<picture>` source-swapping).

**Files this branch will touch:**
- `bristlenose/server/app.py` — serve video assets as static files
- `bristlenose/theme/report_header.html` — `<video>` element in serve-mode branch
- `bristlenose/theme/atoms/logo.css` — video element styling, remove `mix-blend-mode` hack
- `bristlenose/theme/images/` — new assets (`.webm`, `.mov`, transparent `.png`)
- `frontend/src/` — React header component if logo is already a React island

**Potential conflicts with other branches:**
- `symbology` touches `render_html.py` and template headings — low risk (logo is separate from section symbols)
- `highlighter` — unknown scope, likely no overlap

---

### `drag-push`

**Status:** Just started
**Started:** 14 Mar 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch drag-push/`
**Remote:** local only (push when ready)

**What it does:** Changes sidebar rail drag-to-open from overlay (position: fixed, floats over content) to push mode (grid column resize). Both left TOC and right tag sidebars affected. Mouseover overlay on left rail unchanged. Design rationale: dragging is a sizing commitment — user needs to preview layout impact on center content during drag.

**Files this branch will touch:**
- `bristlenose/theme/organisms/sidebar.css` — grid rules for `*-rail-dragging` classes
- `frontend/src/hooks/useDragResize.ts` — animating class on rail drag commit/abort

**Potential conflicts with other branches:**
- `symbology` — no overlap (touches render/template files, not sidebar CSS/hooks)
- `highlighter` — unknown scope, likely no overlap
- `living-fish` — no overlap (logo assets, not sidebar)

---

### `responsive-signal-cards`

**Status:** Just started
**Started:** 15 Mar 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch responsive-signal-cards/`
**Remote:** local only (push when ready)

**What it does:** Responsive layout for signal/analysis cards across screen sizes.

**Files this branch will touch:**
- TBD — will be filled in as work progresses

**Potential conflicts with other branches:**
- `symbology` — low risk (touches render/template files, not signal card layout)
- `drag-push` — low risk (sidebar CSS, not signal cards)

---


### `analysis-matrices-heatmaps-pane`

**Status:** In progress
**Started:** 19 Mar 2026
**Worktree:** `/Users/cassio/Code/bristlenose_branch analysis-matrices-heatmaps-pane/`
**Remote:** local only (push when ready)

**What it does:** DevTools-style collapsible bottom inspector panel in the Analysis tab. Heatmap matrices (section × sentiment, theme × sentiment, codebook group matrices) live in a resizable bottom pane. Collapsed by default with a grid-icon handle bar; opens via click, drag, or `m` shortcut. Signal card selection (blue wash from atomic design system) syncs with inspector source tabs. Tooltip flips above when near viewport bottom.

**Key files:**
- `frontend/src/contexts/InspectorStore.ts` — module-level store for panel state
- `frontend/src/hooks/useVerticalDragResize.ts` — vertical drag resize hook (3px threshold, drag-from-collapsed grows from 28px)
- `frontend/src/components/InspectorPanel.tsx` — panel component (handle bar, source tabs, body)
- `bristlenose/theme/organisms/inspector.css` — panel CSS, viewport layout constraints
- `bristlenose/theme/organisms/analysis.css` — signal card `.bn-selected` state
- `frontend/src/islands/AnalysisPage.tsx` — heatmap sources, card focus state, tooltip flip
- `frontend/src/hooks/useKeyboardShortcuts.ts` — `m` shortcut (route-guarded to analysis)
- `frontend/src/components/about/ShortcutsSection.tsx` — shortcut in help modal

**Potential conflicts with other branches:**
- `responsive-signal-cards` — moderate risk (both touch analysis page layout)
- `symbology` — low risk (touches render/template files, not analysis components)
- `drag-push` — low risk (sidebar drag, not inspector drag)

---

## Completed Branches (for reference)

### `settings-modal` — merged 18 Mar 2026

Settings modal dialog (⌘, / gear icon) with sidebar nav. Help modal with genericised ModalNav organism. WCAG 2.1 AA accessibility audit for quotes page. About tab section components (AboutSection, CodebookSection, ContributingSection, DesignSection, DeveloperSection, SignalsSection). Phase 1 modal shell and General page. Reusable `ModalNav` component for future modals.

### `render-refactor` — merged 11 Mar 2026

Break up `render_html.py` (2,903 lines) into `bristlenose/stages/s12_render/` package with 8 submodules: `theme_assets.py`, `html_helpers.py`, `quote_format.py`, `sentiment.py`, `dashboard.py`, `transcript_pages.py`, `standalone_pages.py`, `report.py`. Added `DeprecationWarning` to `render_html()`. Updated all imports (3 production, 11 test files) and ~99 doc references across 34 files. No behaviour change — pure structural refactor.

### `responsive-playground` — merged 10 Mar 2026

Responsive layout playground and sidebar overlay mode. Responsive CSS grid for quote cards, sidebar TOC overlay with hover-trigger, minimap component, dev-only responsive playground (FAB toggle, device presets, type scale previews, HUD). New components: `Minimap`, `PlaygroundFab`, `PlaygroundHUD`, `ResponsivePlayground`, `TypeScalePreview`. New hook: `useTocOverlay`. New store: `PlaygroundStore`. Design docs: `design-sidebar-playground.md`, `design-minimap.md`, mockup `mockup-minimap.html`. Rollback tag: `pre-responsive-playground-merge`.

### `sentiment-tags` — merged 10 Mar 2026

Unify sentiment badges (frustration, confusion, doubt, surprise, satisfaction, delight, confidence) into the codebook framework system. Sentiment framework YAML, auto-import on first serve, auto-tagging from pipeline sentiment field. Deduplicates 4 overlapping tags from UXR codebook. Adds "sentiment" colour set. Suppresses legacy AI badge when codebook tag exists.

### `shall-we-try-it` — merged 3 Mar 2026

Throwaway branch to test the improved `/new-feature` and `/close-branch` skills after reliability fixes. No code changes.

### `sidebar` — merged 1 Mar 2026

Dual-sidebar layout for the Quotes tab. Left sidebar: TOC with scroll-spy (sections + themes). Right sidebar: tag filter with codebook tree, eye toggles for badge hiding (persisted to localStorage), drag-to-resize with snap-close. 5-column CSS grid, keyboard shortcuts (`[`, `]`, `\`, `⌘.`). Quotes-tab-only scope — other tabs unaffected. 3 feature commits + merge-from-main conflict resolution (AppLayout.tsx: SidebarLayout + ExportDialog coexistence). New files: 2 CSS organisms, 6 components, 2 hooks, 1 store, 1 design doc. 845 Vitest tests (60 files), 1856 Python tests.

### `stabilise-ci` — merged 1 Mar 2026

Frontend CI hardening. Added `frontend-lint-type-test` job to GitHub Actions (ESLint, TypeScript typecheck, Vitest on Node 20). ESLint step is `continue-on-error: true` pending fix of 84 pre-existing lint errors. Also added `CODEX.md` working agreement.

### `react-router` — merged 28 Feb 2026

React migration Steps 5–9. Step 5: React Router SPA with pathname-based routing, `AppLayout` (NavBar + Outlet), 8 page wrappers, backward-compat navigation shims. Step 6: `PlayerContext` with popout window lifecycle, `seekTo`, glow sync. Step 7: `FocusContext` with j/k navigation, multi-select, bulk actions, `useKeyboardShortcuts` hook. Step 8: Vanilla JS modules stripped from serve path (17 modules frozen, `main.js` boot array no-ops). Step 9: Full React app shell — `Header`, `Footer`, `HelpModal`, `AppLayout`; serve mode serves SPA directly, no more `_transform_report_html()` marker substitution. Also: video player links on sessions page and dashboard, importer source-path subdirectory fix, speaker name sizing, word-level timing plumbing. 17 commits, 85 files, +6063/−1066 lines, 717 Vitest tests (55 files), 1813 Python tests.

### `react-settings-about` — merged 25 Feb 2026

Settings panel and About panel migrated from vanilla JS to React islands (React migration steps 1 & 2). `SettingsPanel.tsx` and `AboutPanel.tsx` islands, QuotesStore module-level store with `useSyncExternalStore`, comment-marker injection in `render_html.py` and `app.py`.

### `split-badge` — merged 24 Feb 2026

Two-tone split speaker badges (Treatment E). Left half = speaker code in mono on badge-bg, right half = participant name in body font on quote-bg. Settings toggle (code+name / code-only). Em-dash removed from quote attribution. Always-on sticky transcript header with session selector. Serve mode: inline Jinja2 transcripts stripped, session links navigate to React transcript pages instead of vanilla JS drill-down.

### `context-expansion` — merged 24 Feb 2026

Quote context expansion on the quotes page. Hover over a quote's timecode to reveal chevron arrows (⌃/⌄); click to progressively disclose surrounding transcript segments inside the quote card. Speaker badge conditionally hidden when context segment is same speaker. New components: `ContextSegment`, `ExpandableTimecode`. CSS atom: `context-expansion.css`. Expansion state managed via reducer in `QuoteGroup`, transcript cache wired through `QuoteSections`/`QuoteThemes`.

### `serve` — merged 17 Feb 2026

`bristlenose serve` command — FastAPI + SQLite + React islands architecture. 22-table domain schema, data sync API, sessions/quotes/dashboard/codebook endpoints. 16 React primitives (182 Vitest tests), 5 React islands (SessionsTable, Dashboard, QuoteSections, QuoteThemes, CodebookPanel). Full codebook CRUD with drag-and-drop, inline editing, merge, delete. Desktop app scaffold (SwiftUI macOS shell, sidecar architecture). 330+ Python serve tests across 8 files.

### `project-dashboard` — merged 13 Feb 2026

At-a-glance project dashboard redesign. Clickable stats, featured quotes, session rows, cross-tab navigation. Compact layout with paired stats, slim session table, linked sections/themes. Non-scrolling single-viewport design for the Project tab.

### `analysis` — merged 11 Feb 2026

Analysis page with signal cards ranked by composite score (concentration × agreement × intensity), section × sentiment and theme × sentiment heatmaps with adjusted standardised residuals, dark mode support. Full pipeline integration: Python math module (`bristlenose/analysis/`), standalone `analysis.html` with injected JSON, client-side JS rendering. 97 tests across 4 files. Future phases in `docs/design-analysis-future.md`.


### `codebook-tag-filter` — merged 11 Feb 2026

Tag filter dropdown uses codebook colours and hierarchy. Tags grouped into tinted sections matching codebook page. Badge-styled labels via `createReadOnlyBadge()` in `badge-utils.js`. Search matches both tag names and group names.

### `navigation` — merged 11 Feb 2026

Global tab bar navigation for the HTML report. 7 tabs (Project, Sessions, Quotes, Codebook, Analysis, Settings, About). Sessions tab with grid → inline transcript drill-down. Project tab dashboard with stats, featured quotes, sections/themes tables, sentiment chart. Speaker cross-navigation from quote cards to session timecodes. Full ARIA/accessibility. `global-nav.js`, `global-nav.css`, `global_nav.html`, `session_table.html` added; `render_html.py` extended with ~800 lines; `main.js` boot refactored to `_bootFns` array.

### `jinja2-migration` — merged 9 Feb 2026

Phase 1 Jinja2 template extraction: footer, document shell, report header, quote card. Adds `jinja2>=3.1` dependency, comparison script (`scripts/compare-render.sh`), 12 parity tests. `render_html.py` reduced by ~170 lines. Output byte-identical. Phase 2+ (toolbar, sentiment chart, coverage, player) tracked in `docs/jinja2-migration-plan.md`.

### `transcript-annotations` — merged 9 Feb 2026

Transcript page annotations: quote highlighting with margin labels, tag badges, span bars for quote extent, citation toggle. Also: badge abstraction (`badge-utils.js`), delete circle restyle (white floating chip), design-system reference docs (`docs/design-system/`).

### `codebook` — merged 7 Feb 2026

Interactive codebook page with tag taxonomy management. Phases 1–3: OKLCH colour tokens, toolbar redesign, standalone `codebook.html` with drag-and-drop, inline editing, group CRUD, cross-window sync. Also: shared `escapeHtml()`, `showConfirmModal()`, `toggle()` in modal infrastructure.

---

## Coordination Notes for Claude Sessions

### Reading this file

Before making changes, run:
```bash
git fetch origin
cat docs/BRANCHES.md
```

### Conflict-prone files

These files are frequently edited by multiple features. Take extra care:

| File | Why it's hot |
|------|-------------|
| `bristlenose/stages/render_html.py` | All UI features touch this |
| `bristlenose/theme/js/main.js` | Boot sequence for all JS modules |
| `bristlenose/cli.py` | All new commands land here |
| `TODO.md` | Everyone updates it |
| `CLAUDE.md` | Everyone updates it |

### Safe editing patterns

1. **New files are safe** — if your feature adds a new module (`export.js`, `help-overlay.css`), no conflict risk
2. **Append-only changes are safe** — adding a new function to an existing file rarely conflicts
3. **Structural changes are risky** — refactoring existing code will conflict with parallel work

### When you encounter a conflict

1. Don't resolve it yourself — note it in the merge plan
2. Ask the user which version to keep
3. Or wait for the other branch to merge first, then rebase

### Communication pattern

If you need to signal something to a future Claude session:
1. Add a note to this file under your branch
2. Or create a `docs/notes-{branch-name}.md` for longer notes
3. Reference it in `CLAUDE.md` under "Reference docs"
