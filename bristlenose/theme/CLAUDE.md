# Theme / Design System Context

## Atomic CSS architecture

Tokens → Atoms → Molecules → Organisms → Templates. All visual values via `--bn-*` custom properties in `tokens.css`, never hard-coded. `render_html.py` concatenates files in order defined by `_THEME_FILES`.

## Dark mode

Uses CSS `light-dark()` function (supported in all major browsers since mid-2024, ~87%+ global). No JS involved. The cascade:

1. **OS/browser preference** → `color-scheme: light dark` on `:root` respects `prefers-color-scheme` automatically
2. **User override** → `color_scheme` in `bristlenose.toml` (or `BRISTLENOSE_COLOR_SCHEME` env var). Values: `"auto"` (default), `"light"`, `"dark"`
3. **HTML attribute** → when config is `"light"` or `"dark"`, `render_html.py` emits `<html data-theme="light|dark">` which forces `color-scheme` via CSS selector
4. **Print** → always light (forced by `color-scheme: light` in `print.css`)

### How tokens work

`tokens.css` has two blocks:
- `:root { --bn-colour-bg: #ffffff; ... }` — plain light values (fallback for old browsers)
- `@supports (color: light-dark(...)) { :root { --bn-colour-bg: light-dark(#ffffff, #111111); ... } }` — modern browsers get both values, resolved by `color-scheme`

### Adding a new colour token

Add both light and dark values in the `light-dark()` call inside the `@supports` block, and the plain light fallback in the `:root` block above it.

### Logo

The `<picture>` element swaps between `bristlenose-logo.png` (light) and `bristlenose-logo-dark.png` (dark) using `<source media="(prefers-color-scheme: dark)">`. Both are in `assets/` directory. Dark logo is currently a placeholder (inverted version) — needs replacing with a proper albino bristlenose pleco image.

### No JS theme toggle

Dark mode is CSS-only. No localStorage, no toggle button, no JS involved.

## Template CSS files

Template-level CSS in `templates/`: `report.css` (main report layout), `transcript.css` (per-session transcript pages — back button, segment layout, meta styling, anchor highlight animation), `print.css` (print overrides, hides interactive elements — includes `.feedback-links`, `.feedback-overlay`, `.footer-logo-picture`). Quote attribution links styled via `.speaker-link` in `organisms/blockquote.css` (inherits muted colour from `.speaker`, accent on hover).

### Anchor highlight animation

When navigating to a transcript page via anchor link (e.g., from coverage section), the target segment flashes yellow and fades to normal over 5 seconds. Implemented via:
- **CSS**: `@keyframes anchor-fade` in `transcript.css` — fades from `--bn-colour-highlight` to transparent
- **JS**: `_highlightAnchorTarget()` in `transcript-names.js` — on page load, checks `location.hash` for `#t-\d+` pattern and adds `.anchor-highlight` class to matching segment

## Sentiment bar charts

Two side-by-side horizontal bar charts in the Sentiment section: AI sentiment (server-rendered) and User tags (JS-rendered by `histogram.js`).

### Layout (CSS grid)

`.sentiment-chart` uses `display: grid; grid-template-columns: max-content 1fr max-content` with `row-gap: var(--bn-space-md)`. Each `.sentiment-bar-group` uses `display: contents` so its three children (label, bar, count) participate directly in the parent grid. This is what aligns all bar left edges — the `max-content` first column sizes to the widest label in that chart.

- **Labels** (`atoms/bar.css`): `width: fit-content` + `justify-self: start` — background hugs the text, variable gap falls between label right edge and bar left edge. `max-width: 12rem` with `text-overflow: ellipsis` for long tags
- **Bars**: inline `style="width:Xpx"` set by Python (`_build_sentiment_html()`) and JS (`renderUserTagsChart()`). `max_bar_px = 180`
- **Side-by-side**: `.sentiment-row` is `display: flex; align-items: flex-start` — charts top-align, wrap on narrow viewports
- **Title + divider**: `grid-column: 1 / -1` to span all three columns

### AI sentiment order

Positive (descending by count) → surprise (neutral) → divider → negative (ascending, worst near divider). See `_build_sentiment_html()` in `render_html.py`.

### Histogram delete button

Each user tag label has a hover `×` button (`.histogram-bar-delete` in `atoms/bar.css`, same visual as `.badge-delete`). Click shows a confirmation modal via `createModal()`, then `_deleteTagFromAllQuotes()` removes the tag from all quotes and calls `persistUserTags()`.

### CSS files

- `atoms/bar.css` — `.sentiment-bar`, `.sentiment-bar-label`, `.sentiment-bar-count`, `.histogram-bar-delete`, `.sentiment-divider`
- `molecules/bar-group.css` — `.sentiment-bar-group` (`display: contents`)
- `organisms/sentiment-chart.css` — `.sentiment-row`, `.sentiment-chart`, `.sentiment-chart-title`

## JS modules

17 standalone files in `js/` concatenated at render time (same pattern as CSS): storage, modal, codebook, player, starred, editing, tags, histogram, csv-export, view-switcher, search, tag-filter, hidden, names, focus, feedback, main. Transcript pages use `storage.js` + `player.js` + `transcript-names.js` (no starred/editing/tags/search/names/view-switcher/focus/feedback). Codebook page uses `storage.js` + `modal.js` + `codebook.js`. `transcript-names.js` only updates heading speaker names (preserving code prefix: `"m1 Sarah Chen"`); segment speaker labels stay as raw codes (`p1:`, `m1:`) and are not overridden by JS.

### storage.js

Thin localStorage abstraction. `createStore(key)` returns `{ get, set }` pair. Also provides `escapeHtml(s)` — shared HTML escaping utility (escapes `&`, `<`, `>`, `"`) used by `codebook.js`, `histogram.js`, and any module inserting user-provided text into `innerHTML`. Defined before `createStore()` so it's available to all modules in the concatenation order.

### names.js

Inline name editing for the participant table. Follows the same `contenteditable` lifecycle as `editing.js` (start → accept/cancel → persist).

- **Store**: `createStore('bristlenose-names')` — shape `{pid: {full_name, short_name, role}}`
- **Edit flow**: pencil icon on hover → click makes cell `contenteditable` → Enter/click-outside saves, Escape cancels
- **Auto-suggest**: `suggestShortName(fullName, allNames)` mirrors the Python heuristic — first name, disambiguate collisions with last-name initial ("Sarah J.")
- **DOM updates**: `updateAllReferences(pid)` propagates name changes to participant table cells only. Quote attributions (`.speaker-link`) intentionally show raw pids for anonymisation — not updated by JS
- **Reconciliation**: `reconcileWithBaked()` prunes localStorage entries that match `BN_PARTICIPANTS` (baked-in JSON from render time) — after user pastes edits into `people.yaml` and re-renders, browser state auto-cleans
- **Export**: "Export names" toolbar button copies a YAML snippet via `copyToClipboard()` + `showToast()` (from `csv-export.js`)
- **Dependencies**: must load after `csv-export.js` (needs `showToast`, `copyToClipboard`) and before `main.js` (boot calls `initNames()`)
- **Data source**: `BN_PARTICIPANTS` global — JSON object `{pid: {full_name, short_name, role}}` emitted by `render_html.py` in a `<script>` block

### view-switcher.js

Dropdown menu to switch between report views. Three modes: `all` (default), `starred`, `participants`.

- **`initViewSwitcher()`** — wires up button toggle, menu item selection, outside-click-to-close
- **`_applyView(view, btn, menu, items)`** — sets `currentViewMode` global (defined in `csv-export.js`), updates button label text, toggles active menu item, swaps export button visibility, toggles `<section>` visibility
- **Section visibility**: `all` shows everything, `starred` shows all sections but hides non-starred blockquotes, `participants` shows only the section whose `<h2>` contains "Participants"
- **Export button swap**: `#export-csv` (Copy CSV) visible in `all`/`starred` views; `#export-names` (Export names) visible in `participants` view
- **Search notification**: `_applyView()` calls `_onViewModeChange()` (defined in `search.js`) after applying the view — guarded with `typeof` check so transcript pages (which don't load search.js) don't error
- **Dependencies**: must load after `csv-export.js` (writes `currentViewMode`); before `search.js` and `main.js`
- **CSS**: `organisms/toolbar.css` — `.view-switcher`, `.view-switcher-label`, `.view-switcher-menu` (dropdown positioned absolute right), `.menu-icon` (invisible spacer for alignment). The view switcher button uses dual classes `toolbar-btn view-switcher-btn` — shared round-rect from `atoms/button.css`, dropdown arrow uses `.toolbar-arrow`

### search.js

Search-as-you-type filtering for report quotes. Collapsed magnifying glass icon in the toolbar.

- **`initSearchFilter()`** — wires up toggle button (expand/collapse), text input (debounced 150ms), clear button (×), Escape to clear+collapse
- **`_applySearchFilter()`** — when query >= 3 chars, searches across ALL quotes regardless of view mode (`currentViewMode`). Matches against `.quote-text`, `.speaker-link`, and `.badge` text (skipping `.badge-add`). Case-insensitive `indexOf()` matching. Toggles `.has-query` class on container, highlights matches, hides ToC/Participants, overrides view-switcher label with match count
- **`_highlightMatches(query)`** — wraps matched substrings in visible `.quote-text` elements with `<mark class="search-mark">` using a TreeWalker over text nodes
- **`_clearHighlights()`** — removes all `<mark class="search-mark">` elements, unwrapping text. Called at start of every `_applySearchFilter()`
- **`_setNonQuoteVisibility(display)`** — hides/shows `.toc-row` and Participants section during active search
- **`_overrideViewLabel(label)` / `_restoreViewLabel()`** — temporarily sets the view-switcher button text to the match count ("7 matching quotes") during active search. Saves/restores original label via `_savedViewLabel` module variable
- **`_restoreViewMode()`** — when query is cleared or < 3 chars, restores the view-switcher's visibility state (respects starred mode), restores ToC/Participants, restores view-switcher label
- **`_hideEmptySections()`** — hides `<section>` elements (and preceding `<hr>`) when all child blockquotes are hidden. Only targets sections with `.quote-group` (skips Participants, Sentiment, Friction, Journeys)
- **`_hideEmptySubsections()`** — hides individual h3+description+quote-group clusters within a section when all their quotes are hidden
- **`_onViewModeChange()`** — called by `view-switcher.js` after view mode changes. Hides search in participants mode (no quotes to search), re-applies filter or restores view mode otherwise
- **Dependencies**: must load after `csv-export.js` (reads `currentViewMode` global) and after `view-switcher.js` (which calls `_onViewModeChange()`); before `names.js` and `main.js`
- **CSS**: `molecules/search.css`

### Inline heading/description editing

Section titles, descriptions, theme titles, and theme descriptions use `.editable-text` spans with pencil icons for inline editing. Handled by `initInlineEditing()` in `editing.js` (same file as quote editing, separate state tracker).

- **`.edit-pencil-inline`** in `atoms/button.css` — overrides `.edit-pencil` absolute positioning with `position: static; display: inline` for flow-inline placement after text
- **`.editable-text.editing`** in `molecules/quote-actions.css` — editing highlight (same visual as `.quote-text` editing)
- **`.editable-text.edited`** in `molecules/quote-actions.css` — dashed underline indicator for changed text
- **Bidirectional ToC sync** — ToC entries and section headings share the same `data-edit-key`; `_syncSiblings()` keeps all matching spans in sync on edit

### search.css (molecule)

Collapsible search filter in the toolbar: `.search-container` (flex, `margin-right: auto` for left alignment), `.search-toggle` (muted icon, accent on hover), `.search-field` (relative wrapper, hidden until `.expanded`), `.search-input` (right padding for clear button), `.search-clear` (absolute right inside field, hidden until `.has-query`, muted ×, accent on hover). `.search-mark` (highlight background via `--bn-colour-highlight`, 2px radius).

### tag-filter.css (molecule)

Dropdown filter for quotes by user tag. `.tag-filter` (relative wrapper). The tag filter button uses dual classes `toolbar-btn tag-filter-btn` — shared round-rect from `atoms/button.css`, dropdown-specific overrides in this file. SVG icons use `.toolbar-icon-svg` and `.toolbar-arrow` (shared toolbar classes). `.tag-filter-label` (inline-block, text-align right, min-width set by JS for layout stability). `.tag-filter-menu` (absolute dropdown, right-aligned, `z-index: 200`, `max-height: 32rem`, width locked by JS on open). `.tag-filter-actions` (Select all · Clear row), `.tag-filter-search` / `.tag-filter-search-input` (search field, only shown for 8+ tags). `.tag-filter-item` (flex row: checkbox + name + count), `.tag-filter-item-name` (ellipsis truncation at `max-width: 16rem`), `.tag-filter-item-muted` (italic for "(No tags)"), `.tag-filter-count` (right-aligned, muted, tabular-nums). `.tag-filter-divider` between "(No tags)" and user tags.

### hidden-quotes.css (molecule)

Styles for hidden quotes feature: `.bn-hidden` state, hide button, per-group badge, dropdown, preview items.

- **`blockquote.bn-hidden`** — `display: none !important` (defence-in-depth; JS also sets `style.display = 'none'`)
- **`.hide-btn`** — absolute positioned at `right: 2rem` (between star at `0.65rem` and pencil at `3.35rem`), eye-slash SVG icon, opacity 0 by default → 1 on `blockquote:hover` / `.bn-focused`
- **`.bn-hidden-badge`** — right-aligned in `.quote-group` via `align-self: flex-end`, contains toggle button + dropdown
- **`.bn-hidden-toggle`** — accent-coloured text button ("3 hidden quotes ▾"), underline on hover
- **`.bn-hidden-dropdown`** — absolute below badge, `z-index: 200`, card styling (border, shadow, radius), scrollable
- **`.bn-hidden-item`** — flex row: timecode | preview (ellipsis-truncated) | participant code, border-bottom separator
- **`.bn-hidden-preview`** — clickable text to unhide, cursor pointer, underline on hover, `title="Unhide"`

### hidden.js

Hide/unhide quotes with per-group badge and dropdown. ~350 lines.

- **Store**: `createStore('bristlenose-hidden')` — shape `{ "q-p1-42": true }` (same pattern as starred)
- **`hideQuote(quoteId)`** — adds `.bn-hidden` + `display: none`, persists, updates badge, shows toast, animates (ghost clone shrinks toward badge + FLIP siblings slide up, 300ms)
- **`unhideQuote(quoteId)`** — removes `.bn-hidden`, restores display (respects `currentViewMode` starred filter and tag filter), persists, updates badge, scrolls to quote with highlight, animates (expand from badge + FLIP siblings slide down)
- **`bulkHideSelected()`** — hide all selected quotes (called by `focus.js` for multi-select `h`)
- **`isHidden(quoteId)`** — check if quote is hidden (called by other modules)
- **`_updateBadgeForGroup(group)`** — create/update/remove badge as first child of `.quote-group`
- **`initHidden()`** — restore from localStorage, prune stale IDs, build all badges, wire event delegation
- **Dropdown**: click badge → toggle, click outside / Escape → close, click `.bn-hidden-preview` → unhide, timecode/participant links navigate normally
- **Dependencies**: loads after `tag-filter.js` (reads `currentViewMode`, `_isTagFilterActive`, `_applyTagFilter`, `_hideEmptySections`); exposes `hideQuote()`, `bulkHideSelected()`, `isHidden()` called by `focus.js`

### modal.css (atom)

Shared base styles for overlay modal dialogs, used by help-overlay, feedback, and confirmation modals. `.bn-overlay` (fixed fullscreen backdrop, `z-index: 1000`, opacity/visibility transition), `.bn-modal` (centred card, relative position, `--bn-colour-bg` background, `--bn-radius-lg`, shadow, `max-width: 24rem` default — override per-modal for wider content), `.bn-modal-close` (absolute top-right × button, muted → text on hover), `.bn-modal-footer` (centred footer text, small muted), `.bn-btn-primary` (accent-coloured action button). Each modal adds its own content-specific classes on top (e.g. `.help-modal { max-width: 600px }`, `.feedback-modal { max-width: 420px }`).

### feedback.css (molecule)

Feedback modal content styles, extends `.bn-modal` from `modal.css`. `.feedback-modal` (max-width), `.feedback-sentiments` (flex row of emoji buttons), `.feedback-sentiment` (column layout, border highlight on `.selected`), `.feedback-label` (above textarea), `.feedback-textarea` (accent border on focus), `.feedback-actions` (Cancel + Send buttons), `.feedback-btn-send:disabled` (dimmed).

### modal.js

Shared modal factory used by help overlay (`focus.js`), feedback modal (`feedback.js`), codebook panel (`codebook.js`), and histogram delete (`histogram.js`). Two main functions:

- **`createModal({ className, modalClassName, content, onHide })`** — builds overlay + card + close button DOM, wires click-outside and close button, registers in `_modalRegistry`. Returns `{ show, hide, isVisible, toggle, el, card }`. The `toggle()` method simplifies show/hide switching (used by `focus.js` help overlay and codebook help)
- **`showConfirmModal({ title, body, confirmLabel, confirmClass, onConfirm })`** — reusable confirmation dialog with Cancel + action button. Lazily creates a single modal instance, replaces body content each call. `confirmClass` defaults to `'bn-btn-danger'`; use `'bn-btn-primary'` for non-destructive actions (e.g. merge). Used by `codebook.js` (delete tag, delete group, merge tags) and `histogram.js` (delete tag from all quotes)

`closeTopmostModal()` pops the most recent visible modal — called from Escape handler in `focus.js` and codebook panel keydown handler.

### feedback.js

Feedback modal logic, gated behind `BRISTLENOSE_FEEDBACK` JS constant. `initFeedback()` checks flag, adds `body.feedback-enabled` class (CSS shows footer links), creates draft store, wires footer trigger. `getFeedbackModal()` lazily creates modal via `createModal()`. `submitFeedback()` tries `fetch()` to `BRISTLENOSE_FEEDBACK_URL` if endpoint configured and HTTP(S), falls back to `copyToClipboard()`. Draft persistence via `createStore('bristlenose-feedback-draft')`. Dependencies: `storage.js`, `modal.js`, `csv-export.js`.

### codebook.js

Codebook data model, colour assignment, and interactive panel UI. Manages the researcher's tag taxonomy: named groups of tags with colours from the OKLCH pentadic palette. On the report page, provides colour lookups and the toolbar button. On `codebook.html`, renders the full interactive panel with drag-and-drop, inline editing, and group CRUD.

- **Store**: `createStore('bristlenose-codebook')` — shape `{ groups: [], tags: {}, aiTagsVisible: true }`
- **Colour sets**: 5 pentadic sets (UX blue, Emotion red-pink, Task green-teal, Trust purple, Opportunity amber), each with 5–6 slots. `COLOUR_SETS` includes `bgVar`, `groupBg`, `barVar` properties for panel rendering
- **`getTagColourVar(tagName)`** — returns CSS `var()` reference for a tag's background colour; `var(--bn-custom-bg)` for ungrouped tags
- **`assignTagToGroup(tagName, groupId)`** — assigns tag with auto-picked colour index
- **`createCodebookGroup(name, colourSet)`** — creates a group with auto-assigned colour set if not specified
- **`initCodebook()`** — restores AI tag visibility, applies codebook colours to badges, wires Codebook toolbar button. On codebook page, calls `_initCodebookPanel()` to render the interactive grid
- **Codebook button**: opens `codebook.html` via `window.open()` with `'bristlenose-codebook'` window name
- **AI tag toggle**: code commented out (removed from toolbar — TODO: relocate to future settings panel). Functions `isAiTagsVisible()`, `toggleAiTags()`, `_applyAiTagVisibility()` remain available
- **Cross-window sync**: `storage` event listener reloads codebook state and re-renders panel (or re-applies colours on report page) when the other window writes
- **Panel rendering** (codebook page only):
  - `_initCodebookPanel(grid)` — renders grid, wires `?` key for help modal and `Escape` for `closeTopmostModal()`
  - `_renderCodebookGrid(grid)` — builds ungrouped column, group columns, and "+ New group" placeholder
  - `_renderGroupColumn()` — header (title, subtitle, close button), tag list with micro bars, add-tag row
  - `_renderTagRow()` — badge with colour, delete button, micro histogram bar, quote count, drag handlers
- **Drag-and-drop**: `_dragTag`/`_dragGhost` state. Drag tag → group column = move. Drag tag → tag row = merge (with `showConfirmModal`). Drag tag → "+ New group" = create group with tag
- **Inline editing**: `_editGroupTitle()`, `_editGroupSubtitle()`, `_addTagInline()` — all use `committed` flag guard pattern to prevent double-commit on blur+Enter
- **Confirmation dialogs**: `_confirmMergeTags()`, `_confirmDeleteTag()`, `_confirmDeleteGroup()` — all use `showConfirmModal()` from `modal.js`
- **Help modal**: `_toggleCodebookHelp()` with codebook-specific shortcuts (?, Esc, Enter, drag actions), wired to `?` key
- **Tag name collection**: `_allTagNames()` merges tags from both `bristlenose-tags` (user tags with quotes) AND `codebook.tags` (tags assigned to groups but possibly with 0 quotes)
- **Dependencies**: `storage.js` (for `createStore`, `escapeHtml`), `modal.js` (for `createModal`, `showConfirmModal`, `closeTopmostModal` — on codebook page only)

### Codebook page

Standalone HTML page (`codebook.html`) at the output root, opened in a new window by the toolbar Codebook button. Rendered by `_render_codebook_page()` in `render_html.py`. Features:

- **Layout**: CSS columns masonry grid (`columns: 240px`, `organisms/codebook-panel.css`) with colour-coded group cards
- **Content**: description text + `<div class="codebook-grid" id="codebook-grid">` container populated by `_initCodebookPanel()` from `codebook.js`
- **JS files**: `_CODEBOOK_JS_FILES` = `storage.js` + `modal.js` + `codebook.js`. Boot calls `initCodebook()` which detects the `#codebook-grid` element and renders the panel
- **Interactive features**: drag-and-drop tags between groups, merge tags, inline-edit group titles/subtitles, add/delete tags, create/delete groups, keyboard shortcuts (? help, Esc close)
- **Cross-window sync**: localStorage `storage` event — changes in the codebook page propagate to the report (badge colours update), and vice versa (new user tags appear)

Three page types in the output:
1. **Report** (`bristlenose-{slug}-report.html`) — main window, full JS suite
2. **Transcript** (`sessions/transcript_{id}.html`) — separate pages, `storage.js` + `player.js` + `transcript-names.js`
3. **Codebook** (`codebook.html`) — new window, `storage.js` + `modal.js` + `codebook.js`

### Toolbar button styling

All toolbar controls use the shared `.toolbar-btn` round-rect atom from `atoms/button.css`. Controls with additional behaviour (dropdowns, toggles) use dual classes:

- Codebook: `class="toolbar-btn"` (plain)
- Tag filter: `class="toolbar-btn tag-filter-btn"` (dropdown)
- View switcher: `class="toolbar-btn view-switcher-btn"` (dropdown)
- Copy CSV: `class="toolbar-btn"` (plain)

Shared child elements: `.toolbar-icon-svg` (SVG icon), `.toolbar-arrow` (dropdown chevron). Three-state border: rest (`--bn-colour-border`) → hover (`--bn-colour-border-hover`) → active (`--bn-colour-accent`).

### name-edit.css (molecule)

Styles for participant name inline editing: `.name-cell` / `.role-cell` positioning, `.name-pencil` (opacity 0 → 1 on row hover), editing state background, `.edited` dashed-underline indicator, `.unnamed` muted italic placeholder. Print-hidden.

### coverage.css (organism)

Styles for the transcript coverage section at the end of the report. Section has `<h2>` heading like other sections.

- **`.coverage-summary`** — percentages line below heading (muted colour)
- **`.coverage-details`** — `<details>` element for session list with custom disclosure triangle (▶/▼ via `::before` pseudo-element)
- **`.coverage-details summary`** — clickable "Show omitted segments" text, styled with custom list-style-none and `::before` for arrow
- **`.coverage-body`** — inner content wrapper
- **`.coverage-session`** — per-session group
- **`.coverage-session-title`** — "Session 1" heading (semibold)
- **`.coverage-segment`** — omitted segment text (muted colour, left padding); timecode links to transcript page
- **`.coverage-fragments`** — summary line for short fragments (`.label` italic, `.verbatim` roman)
- **`.coverage-empty`** — "Nothing omitted" message (muted, italic)

### codebook-panel.css (organism)

Codebook page grid layout and interactive components. Uses CSS columns masonry (`columns: 240px`) for space-efficient tiling with `break-inside: avoid` on group cards. All values via design tokens — no hard-coded colours/spacing. Dark mode handled automatically via `light-dark()` tokens.

- **`.codebook-grid`** — masonry container, `max-width: 1200px`
- **`.codebook-group`** — group card with rounded corners, transparent border (accent on `.drag-over`), coloured background via `--bn-group-*` tokens
- **`.group-header`** — flex row: title area + close button (close fades in on group hover)
- **`.group-title-text`** / **`.group-subtitle`** — click-to-edit text with hover highlight
- **`.group-title-input`** / **`.group-subtitle-input`** — inline edit inputs with focus ring
- **`.group-total-row`** — tag count + total quote count summary
- **`.tag-row`** — grid row: badge + bar area, `cursor: grab`, drag states (`.dragging`, `.merge-target`)
- **`.tag-bar-area`** / **`.tag-micro-bar`** / **`.tag-count`** — micro histogram with bar colours from `--bn-bar-*` tokens
- **`.tag-add-row`** / **`.tag-add-badge`** / **`.tag-add-input`** — dashed "+" button → inline input
- **`.new-group-placeholder`** — dashed border card for creating new groups, also a drop target
- **`.drag-ghost`** — fixed-position ghost element during drag
- **`.tag-preview`** — inline badge in merge confirmation modal

## Gotchas

- **JS load order matters**: `view-switcher.js`, `search.js`, `tag-filter.js`, `hidden.js`, and `names.js` all load **after** `csv-export.js` in `_JS_FILES` — `view-switcher.js` writes the `currentViewMode` global defined in `csv-export.js`; `search.js` reads `currentViewMode` and exposes `_onViewModeChange()` called by `view-switcher.js`; `tag-filter.js` loads after `search.js` (reads `currentViewMode`, `_hideEmptySections`, `_hideEmptySubsections`; exposes `_applyTagFilter()`, `_onTagFilterViewChange()`, `_isTagFilterActive()`, `_updateVisibleQuoteCount()` called by `view-switcher.js`, `search.js`, and `tags.js`); `hidden.js` loads after `tag-filter.js` (reads `currentViewMode`, `_isTagFilterActive`, `_applyTagFilter`, `_hideEmptySections`; exposes `hideQuote()`, `bulkHideSelected()`, `isHidden()` called by `focus.js`); `names.js` depends on `copyToClipboard()` and `showToast()`
- **Hidden quotes vs visibility filters**: hidden quotes use `.bn-hidden` class + `style.display = 'none'`. This is fundamentally different from search/tag-filter/starred hiding (which are temporary view filters). Every visibility restore path (`_showAllQuotes`, `_showStarredOnly`, `_restoreViewMode`, `_restoreQuotesForViewMode`, `_applyTagFilter`, `_applySearchFilter`) must check for `.bn-hidden` and skip those quotes. The CSS `display: none !important` on `.bn-hidden` is defence-in-depth
- **`_TRANSCRIPT_JS_FILES`** includes `transcript-names.js` (after `storage.js`) — reads localStorage name edits and updates heading speaker names only (preserving code prefix: `"m1 Sarah Chen"`). Does NOT override segment speaker labels (they stay as raw codes). Separate from the report's `names.js` (which has full editing UI)
- **`blockquote .timecode`** in `blockquote.css` must use `--bn-colour-accent` not `--bn-colour-muted` — the `.timecode-bracket` children handle the muting. If you add a new timecode rendering context, ensure the parent rule uses accent
- **Modal infrastructure**: `atoms/modal.css` provides shared `.bn-overlay`, `.bn-modal`, `.bn-modal-close`, `.bn-modal-footer`, `.bn-modal-actions`, `.bn-btn`, `.bn-btn-cancel`, `.bn-btn-danger`, `.bn-btn-primary` classes. `.bn-modal` has `max-width: 24rem` default — override per-modal for wider content (e.g. `.help-modal { max-width: 600px }`). `js/modal.js` provides `createModal()` factory (returns `{ show, hide, isVisible, toggle }`) + `showConfirmModal()` reusable confirmation dialog + `_modalRegistry` + `closeTopmostModal()`. Help, feedback, codebook, and histogram modals all use these — don't duplicate overlay/card/close patterns
- **Sentiment chart layout**: both AI sentiment and user-tags charts use CSS grid (`grid-template-columns: max-content 1fr max-content`) on `.sentiment-chart`. Bar groups use `display: contents` so label/bar/count participate directly in the parent grid — this is what aligns all bar left edges within each chart. Labels use `width: fit-content` + `justify-self: start` so the background hugs the text and the variable gap falls between the label's right edge and the bar. The two charts sit side-by-side in `.sentiment-row` (flexbox, `align-items: flex-start` for top-alignment). Don't change the grid structure without checking both charts
- **Surprise sentiment placement**: surprise is neutral — it renders between positive sentiments and the divider, not after negative sentiments. See `_build_sentiment_html()` in `render_html.py`
- **Histogram delete-from-all**: clicking the hover `×` on a user tag label in the histogram shows a confirmation modal via `showConfirmModal()`, then removes that tag from every quote via `_deleteTagFromAllQuotes()` in `histogram.js`. This calls `persistUserTags()` which re-renders the histogram and re-applies tag filter
- **IIFE scoping and inline onclick**: all report JS is wrapped in `(function() { ... })()` by `render_html.py`. Functions defined inside are NOT accessible from inline `onclick` HTML attributes. Wire click handlers via `addEventListener` from JS instead. Footer links use `role="button" tabindex="0"` (no `href`) for keyboard accessibility
- **Stale HTML files cause debugging confusion** — if a previous render created a differently-named file (e.g. from a bug), the old file remains on disk. Always check which HTML file you're viewing matches the timestamp of your last render
- **Codebook page sits at output root** — `codebook.html` is at the same level as the report (not in `sessions/` or `assets/`), so it uses `assets/bristlenose-theme.css` (no `../` prefix). The `_footer_html()` helper uses `assets/` paths which work correctly for root-level pages
- **Toolbar button dual-class pattern** — tag filter and view switcher buttons use dual classes (`toolbar-btn tag-filter-btn`, `toolbar-btn view-switcher-btn`). The shared `.toolbar-btn` provides round-rect styling; the component-specific class allows dropdown-specific overrides. Don't remove either class
- **`--bn-colour-border-hover` token** — 3-state border progression for toolbar buttons: rest (`--bn-colour-border` gray-200) → hover (`--bn-colour-border-hover` gray-300) → active (`--bn-colour-accent` blue-600). Adding a new interactive bordered element should follow this pattern

## Future refactoring opportunities

Identified during the codebook panel implementation. These are low-priority improvements to pick up when working in these areas — not blockers.

### Tag-count aggregation (3 implementations)

Three modules independently count user tags by iterating `userTags`: `histogram.js` (`renderUserTagsChart`), `tag-filter.js` (`_getFilteredTagCounts`), and `codebook.js` (`_countQuotesPerTag`). A shared `countUserTags()` function in `storage.js` or a new `tag-utils.js` module would eliminate the duplication. Not urgent — the implementations are simple and correct.

### Shared user-tags data layer

`tags.js` (report page) owns the in-memory `userTags` map and `persistUserTags()` function. `codebook.js` (codebook page) reads user tags via `createStore('bristlenose-tags').get({})` directly. If a future feature needs write access from the codebook page (e.g. bulk rename), extract a shared `userTagStore` module with `get()`, `set()`, and `count()` methods.

### isEditing() guard deduplication

Both `editing.js` and `names.js` have their own `isEditing` / `nameIsEditing` boolean to prevent conflicting edits. A shared `EditGuard` class (`acquire()`, `release()`, `isActive()`) would unify these. Low value until a third editing context is added.

### Inline edit commit pattern

`codebook.js` (`_editGroupTitle`, `_editGroupSubtitle`, `_addTagInline`), `editing.js`, and `names.js` all use the same pattern: create `<input>`, focus, wire `blur`/`Enter`/`Escape` with a `committed` flag guard. A shared `inlineEdit({ element, value, onCommit, onCancel })` helper would reduce boilerplate. Medium value — the pattern is well-understood but repeated ~6 times.

### Close button CSS base class

`.bn-modal-close`, `.group-close`, `.histogram-bar-delete`, and `.badge-delete` all share the same visual pattern: muted → text on hover, small padding, `×` character. Extract a `.close-btn` atom with the shared base styles, then each context adds positioning overrides.

### Input focus CSS base class

`.group-title-input`, `.group-subtitle-input`, `.tag-add-input`, `.search-input`, and `.tag-filter-search-input` all share: `font-family: inherit`, `border: 1px solid var(--bn-colour-border)`, `border-radius: var(--bn-radius-sm)`, accent border + focus ring on `:focus`. Extract a `.bn-input` atom with shared base styles.
