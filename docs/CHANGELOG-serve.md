# Changelog — Serve Branch

Development log for the `bristlenose serve` feature branch. Tracks milestones, architectural decisions, and the reasoning behind them. This branch runs in parallel with `main` and won't merge until the served version is production-ready.

---

## Milestone 5 — Codebook as React island (17 Feb 2026)

**The Codebook tab is now a React island with full CRUD.** Groups, tags, drag-and-drop, inline editing, merge, and delete — all backed by API endpoints. Two new primitives built for this milestone.

### New primitives

- **MicroBar** (`frontend/src/components/MicroBar.tsx`) — horizontal proportional bar, value 0–1. Two modes: trackless (codebook tag frequency) and tracked (analysis concentration bars). Reusable in both contexts. 12 tests.
- **ConfirmDialog** (`frontend/src/components/ConfirmDialog.tsx`) — contextual inline confirmation card positioned near the affected element (not a centred modal). Enter=confirm, Escape=cancel, optional colour tint. 13 tests.

### Codebook API endpoints

`bristlenose/server/routes/codebook.py` — 9 endpoints:

- `GET /api/projects/{id}/codebook` — groups with tags, quote counts (deduplicated), ungrouped tags, all tag names
- `POST /codebook/groups` — create group (auto colour set selection)
- `PATCH /codebook/groups/{id}` — rename, change subtitle/colour/order
- `DELETE /codebook/groups/{id}` — delete group, move tags to Ungrouped
- `POST /codebook/tags` — create tag (case-insensitive duplicate guard)
- `PATCH /codebook/tags/{id}` — rename or move tag between groups
- `DELETE /codebook/tags/{id}` — delete tag + QuoteTag associations
- `POST /codebook/merge-tags` — merge source into target (reassign QuoteTags, delete source)

36 tests in `tests/test_serve_codebook_api.py`.

### CodebookPanel React island

`frontend/src/islands/CodebookPanel.tsx` — composition using Badge, EditableText, TagInput, MicroBar, ConfirmDialog:

- **CSS columns masonry layout** — reuses existing `.codebook-grid` CSS
- **Inline editing** — group titles and subtitles via EditableText with `trigger="click"`
- **Tag management** — add (TagInput, duplicate guard), delete (ConfirmDialog), rename
- **Drag and drop** — native HTML5 drag API, three gestures: move to group, merge (with confirmation), create new group from drag
- **Pentadic colour system** — 5 colour sets (ux, emo, task, trust, opp) with CSS variable-based palette
- **Tab-visibility re-fetch** — MutationObserver on the parent `.bn-tab-panel` re-fetches codebook data when the tab gains `.active`, fixing stale counts from the localStorage `PUT /tags` race (vanilla JS tags sync may not have finished when the panel first mounts)

20 island tests in `frontend/src/islands/CodebookPanel.test.tsx`.

### CSS cleanup

7 changes to `codebook-panel.css`:
- Tokenised hardcoded spacing (12px→`--bn-space-md`, 4px→`--bn-space-xs`, 6px→`--bn-space-sm`)
- Fixed merge-target dark mode colour (hardcoded rgba → `color-mix()` with accent token)
- Fixed placeholder border (1.5px sub-pixel → 1px)
- Added `.codebook-group .tag-input` font-size override (0.82rem)
- Retired `.group-title-input`/`.group-subtitle-input` rules (replaced by EditableText)
- Added `.confirm-dialog` styles

### TypeScript API helpers

Extended `frontend/src/utils/api.ts` with generic `apiGet`, `apiPost`, `apiPatch`, `apiDelete` helpers and named codebook CRUD functions. Extended `types.ts` with `CodebookResponse`, `CodebookGroupResponse`, `CodebookTagResponse`.

### Test counts

- 182 Vitest tests (was 136 → +46: 12 MicroBar + 14 ConfirmDialog + 20 CodebookPanel)
- 1271 Python tests (was 1235 → +36 codebook API tests)

---

## Milestone 4 — Dashboard (Project tab) as React island (17 Feb 2026)

**The Project tab is now a React island.** Stat cards, compact sessions table, featured quotes, and section/theme navigation — all rendered by React from a new API endpoint. First composition built entirely from existing primitives (no new components needed).

### Dashboard API endpoint

`GET /api/projects/{id}/dashboard` — single endpoint returning everything the Project tab needs:

- **Stats:** session count, total duration (human-readable), total words, quote count, theme count, section count, AI tag count, user tag count
- **Sessions:** compact rows with ID, participant badges, start date, duration, source filename
- **Featured quotes:** up to 9 quotes selected by the existing "best quotes" algorithm (starred first, then highest-intensity, sentiment-diverse). Respects hidden/starred state
- **Nav items:** section and theme lists with anchor IDs for cross-tab navigation
- **Headers:** moderator/observer names for display

Implementation: `bristlenose/server/routes/dashboard.py`. 43 tests in `tests/test_serve_dashboard_api.py` covering stats, sessions, featured quotes (including starred/hidden reflection), nav items, headers, error handling.

### Dashboard React island

`frontend/src/islands/Dashboard.tsx` — composition of existing primitives:

- **Stat cards** = 8 × clickable cards (navigate to Sessions, Quotes, Analysis, Codebook tabs)
- **Compact sessions table** = PersonBadge + formatted dates/durations + source filenames
- **Featured quotes** = quote text + TimecodeLink + PersonBadge + Badge(sentiment), with reshuffle button
- **Section/theme nav** = anchor links that switch to Quotes tab and scroll to target

All navigation delegates to vanilla JS globals (`switchToTab`, `scrollToAnchor`, `navigateToSession`) via `window.*` interop — same pattern as the Sessions table island.

### Renderer overlay fix

The dashboard region now shows green (React) in the dev overlay. Required targeting `#panel-project` by ID instead of relying on `:has(#bn-dashboard-root)` — the `:has()` approach failed because the tab panel's blue `::after` painted over the child's green at the same z-index.

### Serve DX improvements

Three quality-of-life improvements to `bristlenose serve`:

1. **Auto-render before serving.** `serve` now calls `Pipeline.run_render_only()` before starting uvicorn. Eliminates stale-HTML bugs (e.g. missing mount-point markers after code changes). Fast — <0.1s.
2. **Clickable report URL.** Prints `Report: http://127.0.0.1:8150/report/` before uvicorn starts — Cmd-clickable in iTerm.
3. **Auto-open browser.** Opens the report URL in the default browser on startup. `--no-open` flag to suppress.

### What shipped

- `bristlenose/server/routes/dashboard.py` (new) — dashboard API endpoint
- `frontend/src/islands/Dashboard.tsx` (new) — dashboard React island
- `tests/test_serve_dashboard_api.py` (new) — 43 API tests
- `frontend/src/utils/types.ts` — dashboard TypeScript interfaces
- `frontend/src/main.tsx` — dashboard island mount
- `bristlenose/server/app.py` — router registration, mount point constant, regex swap, overlay CSS
- `bristlenose/stages/render_html.py` — `<!-- bn-dashboard -->` markers
- `bristlenose/cli.py` — auto-render, clickable URL, auto-open browser, `--no-open` flag

1235 Python tests + 136 Vitest tests all passing.

---

## React component library — Round 4 complete (17 Feb 2026)

**All 14 primitives complete. 12 component files, 136 tests across 12 test files.**

### Round 4 primitives (5 components)

**Metric** (`frontend/src/components/Metric.tsx`) — Render-only metric display for analysis signal cards. Three viz types: `bar` (percentage fill), `dots` (SVG intensity), `none`. Uses `useId()` for stable SVG clip-path IDs. Reuses all existing CSS from `organisms/analysis.css`.

**JourneyChain** (`frontend/src/components/JourneyChain.tsx`) — Ordered screen labels joined by arrow separators. Wired into `SessionsTable.tsx`, replacing inline join.

**Counter** (`frontend/src/components/Counter.tsx`) — Hidden-quotes badge with expandable preview dropdown and unhide actions. Reuses `molecules/hidden-quotes.css`.

**Thumbnail** (`frontend/src/components/Thumbnail.tsx`) — Media preview placeholder (96×54px) with play icon. CSS extracted from `templates/report.css` into `atoms/thumbnail.css`. Wired into `SessionsTable.tsx`, replacing inline markup.

**Annotation** (`frontend/src/components/Annotation.tsx`) — Transcript margin annotation: section/theme label link + sentiment badge + user tag badges. Composes Badge component. Reuses `molecules/transcript-annotations.css`. Render-only with delete callbacks for badges and tags.

### CSS extraction

- Created `atoms/thumbnail.css` — extracted `.bn-video-thumb` and `.bn-play-icon` from `templates/report.css`
- Added to `_THEME_FILES` in `render_html.py`

### What shipped

5 component files, 5 test files (19 new tests in this session → 136 total), `SessionsTable.tsx` refactored to use Thumbnail, barrel exports updated, design doc marked Round 4 complete.

---

## React component library — Round 3 (16 Feb 2026)

**2 new primitives: Sparkline and TagInput. CSS extraction. SessionsTable refactored.**

### Sparkline component (`frontend/src/components/Sparkline.tsx`)

Generic category-based mini-bar chart. Accepts `items: SparklineItem[]` where each item has `key`, `count`, and `colour`. Renders bottom-aligned bars in a `<div className="bn-sparkline">`. Empty state (all zero counts) shows an em-dash or custom `emptyContent`. Configurable `maxHeight`, `minHeight`, `gap`, `opacity` — defaults match the previous inline constants exactly.

Extracted from the inline `SentimentSparkline` in `SessionsTable.tsx`. CSS extracted from `templates/report.css` into `molecules/sparkline.css`.

### TagInput component (`frontend/src/components/TagInput.tsx`)

Text input with keyboard-navigable auto-suggest dropdown and ghost text completion. Replicates the behaviour from `tags.js` (470 lines of vanilla JS) as a controlled React component.

Props: `vocabulary`, `exclude`, `onCommit`, `onCancel`, `onCommitAndReopen`, `placeholder`, `maxSuggestions`, `className`, `data-testid`. Always "open" when mounted — consumer controls visibility. Auto-focuses on mount. Ghost text shows best prefix-match suffix (fish-shell style, accepted with ArrowRight). Arrow keys navigate suggestions, Enter/Tab commit, Escape cancels. Tab fires `onCommitAndReopen` for rapid multi-tag entry. Blur commits non-empty, cancels empty (150ms delay matching vanilla JS).

CSS already existed in `atoms/input.css` + `molecules/tag-input.css` — no extraction needed.

### SessionsTable refactor

Replaced inline `SentimentSparkline` sub-component and 5 sparkline constants with the new `Sparkline` primitive. Added `sentimentToSparklineItems()` helper to map `Record<string, number>` to `SparklineItem[]`.

**What shipped:** 2 component files, 2 test files (35 new tests → 82 total), 1 new CSS file, `templates/report.css` trimmed, `SessionsTable.tsx` refactored, barrel exports updated, `_THEME_FILES` updated, design doc marked Round 3 done. 1192 Python tests + 82 Vitest tests all passing.

---

## Quotes API endpoint (16 Feb 2026)

**`GET /api/projects/{id}/quotes` — quotes grouped by section and theme, with researcher state.**

Data layer for the future QuoteCard React island. Returns all quotes for a project organized by report structure: `sections` (screen clusters ordered by `display_order`) and `themes` (theme groups), each containing fully-hydrated quote objects.

### Response shape

`QuotesListResponse` with `sections: SectionResponse[]`, `themes: ThemeResponse[]`, summary counts (`total_quotes`, `total_hidden`, `total_starred`). Each `QuoteResponse` includes: `dom_id`, `text`, `verbatim_excerpt`, `participant_id`, `session_id`, `speaker_name` (resolved from Person table, falls back to speaker code), `start_timecode`, `end_timecode`, `sentiment`, `intensity`, `researcher_context`, `quote_type`, `topic_label`, `is_starred`, `is_hidden`, `edited_text`, `tags` (with codebook group info), `deleted_badges`.

### Implementation

- Bulk-loads all quotes, joins, and researcher state in ~8 queries, assembles in-memory (same pattern as sessions endpoint)
- Speaker names resolved server-side via Session → SessionSpeaker → Person join
- Tags returned as `TagResponse` objects (name + codebook_group) — richer than data.py's bare strings, avoids extra API call from the React island
- Quotes ordered by `start_timecode` within sections, by `(session_id, start_timecode)` within themes

**What shipped:** `bristlenose/server/routes/quotes.py` (new), 2-line registration in `app.py`, 48 tests in `tests/test_serve_quotes_api.py`. 1192 Python tests + 59 Vitest tests all passing.

---

## React component library — Round 2 (16 Feb 2026)

**CSS refactoring + 2 interactive primitives: EditableText and Toggle.**

### CSS refactoring

Extracted toggle and editing rules into dedicated files to align CSS architecture with React component boundaries. No class names changed — same rules, different source files.

- Created `atoms/toggle.css` — star-btn, hide-btn, toolbar-btn-toggle rules (from `button.css` + `hidden-quotes.css`)
- Created `molecules/editable-text.css` — editing/edited state rules for quotes, headings, and names (from `quote-actions.css` + `name-edit.css`)

### EditableText component (`frontend/src/components/EditableText.tsx`)

Contenteditable inline text editing primitive. Two trigger modes:

- `trigger="external"` (default) — parent controls `isEditing` prop, provides pencil button
- `trigger="click"` — clicking the text itself enters edit mode, with `cursor: text` hover hint

Props: `value`, `originalValue`, `isEditing`, `committed`, `onCommit`, `onCancel`, `trigger`, `as` (span/p), `className`, `committedClassName`, `data-testid`, `data-edit-key`. Commit on Enter/blur, cancel on Escape. Strips whitespace. Shows `.edited` dashed underline when committed. Context-specific effects (smart-quote wrapping, ToC sync, name propagation) are `onCommit` callbacks — not part of the component.

### Toggle component (`frontend/src/components/Toggle.tsx`)

Controlled on/off button primitive. Parent composes with icon, positioning, and side effects.

Props: `active`, `onToggle`, `children`, `className`, `activeClassName`, `aria-label`, `data-testid`. Renders `<button>` with `aria-pressed`. Star/hide animations are composition-level effects in `onToggle`, not inside Toggle.

**What shipped:** 2 component files, 2 test files, 2 new CSS files, 4 CSS files trimmed, barrel export updated, `_THEME_FILES` updated. Python tests + Vitest all passing.

---

## Serve-mode mount point injection (16 Feb 2026)

**Vite backend-integration for one-command React dev workflow.** `_mount_dev_report()` now injects the React mount point (`<div id="bn-sessions-table-root">`) and three Vite HMR scripts (React Fast Refresh preamble, `@vite/client`, `src/main.tsx`) so React islands render automatically when Vite is running alongside `bristlenose serve --dev`. This is Option (c) from the original backlog — the standard Vite backend-integration pattern.

Key implementation in `bristlenose/server/app.py`:
- `_build_vite_dev_scripts()` — generates the three `<script type="module">` tags pointing to `localhost:5173`
- `_mount_dev_report()` — regex-replaces `<!-- bn-session-table -->` markers with React mount point, injects Vite scripts before `</body>`

---

## React component library — Round 1 (16 Feb 2026)

**CSS rename + frontend tooling + 3 primitives + SessionsTable refactor.**

### CSS rename: `.bn-person-id` → `.bn-person-badge`

The only Round 1 naming mismatch. "person-id" described data; "person-badge" describes the UI element. Establishes the rule: React component name wins, CSS is renamed to match. 12 files changed across CSS, Python renderers, Jinja templates, React TSX, tests, and docs.

### Frontend tooling infrastructure

- **Vitest + React Testing Library** — `jsdom` environment, globals enabled, `test-setup.ts` imports `@testing-library/jest-dom`
- **ESLint** — flat config with `typescript-eslint` + `react-hooks` rules
- **TypeScript** — `types: ["vitest/globals", "@testing-library/jest-dom"]` in tsconfig
- **Scripts** — `npm test`, `npm run lint`, `npm run typecheck` added alongside existing `build`/`dev`

### Badge component (`frontend/src/components/Badge.tsx`)

1:1 mapping with `atoms/badge.css`. Three variants: `ai` (click-to-delete), `user` (× button), `readonly`. Props: `text`, `variant`, `sentiment`, `colour`, `onDelete`, `className`, `data-testid`. 8 tests.

### PersonBadge component (`frontend/src/components/PersonBadge.tsx`)

1:1 mapping with `molecules/person-badge.css` (after rename). Props: `code`, `role`, `name`, `highlighted`, `href` (wraps in `<a>`), `data-testid`. 5 tests.

### TimecodeLink component (`frontend/src/components/TimecodeLink.tsx`)

1:1 mapping with `atoms/timecode.css`. Auto-formats seconds to `[MM:SS]` or `[H:MM:SS]`. Emits `data-participant`, `data-seconds`, `data-end-seconds` attributes for `player.js` interop. Props: `seconds`, `endSeconds`, `participantId`, `formatted`, `data-testid`. 6 tests.

### SessionsTable refactor

- Extracted `formatDuration`, `formatFinderDate`, `formatFinderFilename` → `frontend/src/utils/format.ts`
- Replaced inline `SpeakerBadge` with `PersonBadge` from the component library
- Barrel export at `frontend/src/components/index.ts`

### Documentation

- CSS ↔ React alignment table appended to `docs/design-react-component-library.md` — full mapping of 13 CSS files to 14 primitives, naming convention, per-round refactoring schedule
- Cross-reference from `bristlenose/theme/CLAUDE.md` to the mapping table

**What shipped:** 3 component files, 3 test files (19 tests), barrel export, format utils, eslint config, test setup, refactored SessionsTable. 1144 Python tests + 19 Vitest tests all passing.

---

## Renderer overlay (15 Feb 2026)

**Dev-only renderer overlay toggle.** A floating button (top-right, `D` keyboard shortcut) that tints report regions by renderer origin: pale blue for Jinja2 static HTML, pale green for React islands, pale amber for vanilla JS rendered content. Shows at a glance which parts of the report come from which renderer.

**Implementation:** Self-contained `<style>` + `<div>` + `<script>` block injected before `</body>` by `_mount_dev_report()` in `app.py` — same pattern as the About tab developer section injection. Toggles `body.bn-dev-overlay` CSS class. Off by default. Three CSS rule groups target existing classes/IDs:

- **Jinja2 (blue `#eef4fe`):** `.bn-tab-panel`, `.bn-dashboard`, `.bn-session-grid`, `.toolbar`, `.toc`, `section`, `.bn-about`, `.report-header`, `.bn-global-nav`, `.footer`
- **React (green `#e8fce8`):** `#bn-sessions-table-root`, `#bn-about-developer-root`
- **Vanilla JS (amber `#fef6e0`):** `#codebook-grid`, `#signal-cards`, `#heatmap-section-container`, `#heatmap-theme-container`

ID selectors have higher specificity than class selectors, so React/vanilla JS tints override the parent Jinja2 blue without needing extra specificity hacks.

**Learnings during implementation:**
- Transparent tints (`rgba(..., 0.15)`) are invisible on elements that inherit an opaque body `background: #fff` — the tint blends into white with no visible boundary. Opaque pastels (`#eef4fe` etc.) make the regions unmistakable.
- Tab panels (`.bn-tab-panel`) needed to be in the Jinja2 selector list — without them, switching tabs showed no tint because the child elements have no explicit background.
- The dashboard compact session table and the Sessions tab full table both use `.bn-session-table` — the `bn-session-grid` parent wrapper distinguishes them (relevant for future serve-mode mount point injection).

**What shipped:**
- `bristlenose/server/app.py` — `_build_renderer_overlay_html()` function, injection in `_mount_dev_report()`

---

## Visual parity testing (15 Feb 2026)

### Visual diff tool + dev URL directory

**Built a dev-only visual comparison tool** to verify the React sessions table matches the Jinja2 static report. Three view modes: side-by-side (synced scroll), overlay (opacity slider blends between the two), and toggle (Space key instant swap).

**Results:** Near-perfect visual parity confirmed. Both tables render with the same CSS classes, same sparkline bars, same badge styling, same hover states. Minor differences in the Interviews column (filename wrapping differs slightly between `<a>` links in the static report vs `<span>` in the dev endpoint) and journey line-break points (consequence of column width differences). These are dev endpoint rendering differences, not React component bugs — the React version matches the real report.

**Dev URL directory:** `bristlenose serve --dev` now prints all available URLs on startup (Cmd-clickable in iTerm): report, visual diff, API docs, sessions API, sessions HTML, health check.

**What shipped:**
- `bristlenose/server/routes/dev.py` — dev-only API router: `GET /api/dev/sessions-table-html?project_id=1` renders the Jinja2 sessions table template from DB data, returns raw HTML fragment. Reuses `_render_sentiment_sparkline()`, `format_finder_date()`, `format_finder_filename()`, and the Jinja2 template environment from `render_html.py`
- `bristlenose/server/app.py` — recovers `_BRISTLENOSE_DEV` env var, registers dev router when dev mode, prints dev URL directory on startup
- `bristlenose/cli.py` — stashes `_BRISTLENOSE_DEV=1` and `_BRISTLENOSE_PORT` env vars for uvicorn factory recovery
- `frontend/visual-diff.html` + `frontend/src/visual-diff-main.tsx` — separate Vite entry point for the diff page (excluded from production build)
- `frontend/src/pages/VisualDiff.tsx` — diff UI with three view modes (side-by-side, overlay with opacity slider, toggle with Space key), keyboard shortcuts (1/2/3 for modes), synced scroll
- `frontend/src/pages/visual-diff.css` — toolbar and layout styles
- `frontend/vite.config.ts` — `visual-diff.html` added as second Vite entry point

---

## Milestone 1 — Sessions Table as React Island (complete)

### 15 Feb 2026 — Dev mode fixes and live testing

**Live-tested `bristlenose serve trial-runs/project-ikea --dev` end-to-end.** Three bugs found and fixed during hands-on testing:

1. **`--dev` mode lost `project_dir` on reload.** Uvicorn's `factory=True` + `reload=True` calls `create_app()` with no arguments on child process spawn — the `project_dir` arg from the CLI was lost. Fix: CLI stashes `project_dir` in `_BRISTLENOSE_PROJECT_DIR` env var; `create_app()` recovers it. Also separated dev and non-dev code paths in `cli.py` — dev mode never calls `create_app()` directly (only uvicorn's factory does), non-dev mode creates the app instance directly and opens the browser.

2. **`/report/` returned 404.** `StaticFiles(html=True)` expects `index.html` but the report file is `bristlenose-project-ikea-report.html` (includes project slug). Fix: `_ensure_index_symlink()` creates a relative `index.html → *-report.html` symlink at serve startup. Idempotent, portable. Noted in `docs/windows-tech-debt.md` — symlinks need admin/Developer Mode on Windows.

3. **Vite proxy missing `/report` route.** `vite.config.ts` only proxied `/api` to the backend. Added `/report` proxy so the Vite dev server forwards report requests to FastAPI.

**What shipped:**
- `bristlenose/cli.py` — separated dev/non-dev serve paths, env var passthrough
- `bristlenose/server/app.py` — env var recovery, `_ensure_index_symlink()`, warning on missing output dir
- `frontend/vite.config.ts` — `/report` proxy
- `docs/windows-tech-debt.md` — new file tracking platform assumptions (symlinks, config dirs, FFmpeg, etc.)
- `.gitignore` — font files in mockups directory

### 14 Feb 2026 — Steps 4-5 complete (milestone done)

**Mount point and React component.** `render_html.py` gains `serve_mode` flag; `SessionsTable.tsx` replaces the Jinja2 sessions table as a React island.

**What shipped:**

- `serve_mode: bool = False` parameter on `render_html()`. When True, the Sessions tab renders `<div id="bn-sessions-table-root" data-project-id="1">` instead of the Jinja2 `session_table.html` template. Dashboard compact table stays static. Static export path unchanged.

- JS audit: only `global-nav.js` binds to session table DOM (`tr[data-session]`, `a[data-session-link]`). React replaces that DOM in serve mode; the JS queries return empty NodeLists gracefully.

- `SessionsTable.tsx` — full-parity React component. Reads project ID from mount point, fetches `GET /api/projects/{id}/sessions`, renders the identical table structure with all CSS classes. All columns: ID with transcript link, speaker badges, Finder-style relative dates with journey arrows, duration, filename with middle-ellipsis, thumbnail play icon, sentiment sparkline bars, moderator/observer header. Loading and error states included.

- `main.tsx` updated with island pattern: finds `#bn-sessions-table-root`, reads `data-project-id`, mounts `<SessionsTable>`.

**What's next:** Milestone 2 planning — likely the quotes/codebook workspace.

### 14 Feb 2026 — Steps 1-3 complete

**Schema, importer, and sessions API.** 3,215 lines across 10 files. 72 new tests, full suite (1050) passing.

**What shipped:**

- Full 22-table SQLAlchemy domain schema (`server/models.py`). Instance-scoped tables (person, codebook_group, tag_definition) and project-scoped tables (session, quote, cluster, theme, plus all researcher state and conflict tables). Every grouping join table has `assigned_by` ("pipeline" | "researcher") from day one. Every AI-generated entity has `last_imported_at` for stale-data detection.

- Pipeline importer (`server/importer.py`). Reads `metadata.json`, `screen_clusters.json`, `theme_groups.json`, and raw transcript files. Creates sessions (with date and duration from transcript headers), speakers, persons, transcript segments, quotes, clusters, themes, and all join tables. Built as upsert by stable key — idempotent, safe to re-run. Called automatically on `bristlenose serve` startup.

- Sessions API endpoint (`server/routes/sessions.py`). `GET /api/projects/{project_id}/sessions` returns the full data shape needed by the React sessions table: speakers sorted m→p→o, journey labels derived from screen clusters by display_order, per-session sentiment counts aggregated from quotes, source files, moderator/observer names. Pydantic response models.

- Infrastructure: `db.py` updated to register all models and use `StaticPool` for in-memory SQLite testing. `app.py` registers sessions router, stores DB factory in app state for dependency injection, auto-imports on startup.

**What's next:** Step 4 (mount point in HTML — `serve_mode` flag) and Step 5 (React SessionsTable component with full visual parity).

### 14 Feb 2026 — Design session: domain model and pipeline→workspace paradigm

Extended design discussion that shaped the schema. Key decisions and the reasoning behind them:

**1. "Model the world, not this week's UI."** The user pushed back on a minimal schema (just enough for the sessions table) and asked: "is it smart to model all the data schema as a big picture exercise?" Yes — getting the entities right now means API endpoints and React components follow naturally. Getting them wrong means every milestone fights the schema.

**2. Instance-scoped vs project-scoped split.** Born from the question: "the same moderators, observers, and possibly participants might reappear across multiple projects." People, codebook groups, and tag definitions exist independently of any project. Everything else is project-scoped. This enables:
- Cross-session moderator linking (same person_id across session_speaker rows)
- Codebook reuse across studies (project_codebook_group join table)
- Future longitudinal analysis (same participant across wave 1 and wave 2)

Originally called "researcher-scoped" — renamed to "instance-scoped" after the user clarified that codebook groups belong to the Bristlenose installation, not to a particular researcher. Multi-researcher access control is a future permissions layer on top of this data model, not a change to it.

**3. Codebook groups as the reusable unit, not whole codebooks.** There is no `codebook` table. The user noted that a researcher might reuse their "Friction" group across five studies but create a fresh "Pricing" group for one study. The atom of reuse is the group, not the codebook.

**4. The AI is a "7 out of 10" draft.** The user's framing: "the initial analysis is often very good, like a 7 out of 10 and saves hours or days of work, and reveals insights a human might have missed — but it's also guaranteed to be wrong in some fundamental ways that humans can spot with contextual knowledge of the world." This is the philosophical foundation for the entire `assigned_by`/`created_by` pattern. The database treats pipeline output as a strong first draft, not ground truth with annotations on top.

**5. `assigned_by` over `is_override`.** Originally proposed as a boolean `is_override` on join tables. The user's question about what happens when the pipeline re-runs led to the realisation that "override" is the wrong mental model. Both pipeline and researcher are first-class authors. `assigned_by ("pipeline" | "researcher")` tracks who made each assignment. On re-import, the pipeline replaces its own assignments but never touches the researcher's. This was a correction from the user — the distinction matters because "override" implies a hierarchy (pipeline is default, researcher is exception), while "assigned_by" implies equal authorship with different sources.

**6. Moving quotes between clusters is "very common."** The user emphasised this is a core workflow, not an edge case. Likewise merging/splitting/deleting groups and putting quotes back into an unsorted pool. This validated the design of the unsorted pool (quotes with no join rows are visible in a "To be sorted" section) and the simple CRUD model for grouping operations.

**7. Incremental analysis is the normal workflow.** Running 2-3 interviews, getting an initial analysis, then adding more data later is standard qualitative research practice. The user: "this needs to be a first-class part of the system rather than a hack." This drove the upsert-based import design, `last_imported_at` timestamps for stale data, and the "researcher edits always win" principle.

**8. Import conflicts, not assignment history.** When the pipeline re-creates "Homepage" after the researcher renamed it to "Landing page", we need conflict detection — not a full audit trail. The `import_conflict` table logs clashes for human review. Full history can be added later as an additive `assignment_log` table if needed.

**9. Signals are recomputed, not stored.** The analysis module runs in <100ms. Storing signals creates a staleness problem every time the researcher hides a quote, renames a heading, or unlinks a quote from a grouping. Only `dismissed_signal` is persisted.

**10. `session_speaker` as the missing entity.** Identified during the concept inventory: a speaker code is really a join between a person and a session. Modelling it explicitly (with speaker_code, role, and per-session stats) is what makes cross-session moderator linking possible in Phase 2.

Full design rationale in `docs/design-serve-milestone-1.md`.

---

## Milestone 0 — Serve Shell (complete)

### 13 Feb 2026

**FastAPI + React + SQLite scaffolding.** `bristlenose serve` command, FastAPI application factory, SQLite with WAL mode, React + Vite + TypeScript tooling, HelloIsland proof of concept, Vite proxy for `/api/*` to FastAPI, health check endpoint.

Design docs: `docs/design-serve-migration.md` (architecture, tech stack, migration roadmap).
