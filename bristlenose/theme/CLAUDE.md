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

15 standalone files in `js/` concatenated at render time (same pattern as CSS): storage, modal, player, starred, editing, tags, histogram, csv-export, view-switcher, search, tag-filter, names, focus, feedback, main. Transcript pages use `storage.js` + `player.js` + `transcript-names.js` (no starred/editing/tags/search/names/view-switcher/focus/feedback). `transcript-names.js` only updates heading speaker names (preserving code prefix: `"m1 Sarah Chen"`); segment speaker labels stay as raw codes (`p1:`, `m1:`) and are not overridden by JS.

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
- **CSS**: `organisms/toolbar.css` — `.view-switcher`, `.view-switcher-btn`, `.view-switcher-arrow` (SVG chevron), `.view-switcher-menu` (dropdown positioned absolute right), `.menu-icon` (invisible spacer for alignment)

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

Dropdown filter for quotes by user tag. `.tag-filter` (relative wrapper), `.tag-filter-btn` (inline-flex, text colour, accent on hover), `.tag-filter-icon` (filter-lines SVG), `.tag-filter-arrow` (chevron, muted), `.tag-filter-label` (inline-block, text-align right, min-width set by JS for layout stability). `.tag-filter-menu` (absolute dropdown, right-aligned, `z-index: 200`, `max-height: 32rem`, width locked by JS on open). `.tag-filter-actions` (Select all · Clear row), `.tag-filter-search` / `.tag-filter-search-input` (search field, only shown for 8+ tags). `.tag-filter-item` (flex row: checkbox + name + count), `.tag-filter-item-name` (ellipsis truncation at `max-width: 16rem`), `.tag-filter-item-muted` (italic for "(No tags)"), `.tag-filter-count` (right-aligned, muted, tabular-nums). `.tag-filter-divider` between "(No tags)" and user tags.

### modal.css (atom)

Shared base styles for overlay modal dialogs, used by both help-overlay and feedback modals. `.bn-overlay` (fixed fullscreen backdrop, `z-index: 1000`, opacity/visibility transition), `.bn-modal` (centred card, relative position, `--bn-colour-bg` background, `--bn-radius-lg`, shadow), `.bn-modal-close` (absolute top-right × button, muted → text on hover), `.bn-modal-footer` (centred footer text, small muted). Each modal adds its own content-specific classes on top (e.g. `.help-modal { max-width: 600px }`, `.feedback-modal { max-width: 420px }`).

### feedback.css (molecule)

Feedback modal content styles, extends `.bn-modal` from `modal.css`. `.feedback-modal` (max-width), `.feedback-sentiments` (flex row of emoji buttons), `.feedback-sentiment` (column layout, border highlight on `.selected`), `.feedback-label` (above textarea), `.feedback-textarea` (accent border on focus), `.feedback-actions` (Cancel + Send buttons), `.feedback-btn-send:disabled` (dimmed).

### modal.js

Shared modal factory used by both help overlay (`focus.js`) and feedback modal (`feedback.js`). `createModal({ className, modalClassName, content, onHide })` builds overlay + card + close button DOM, wires click-outside and close button, registers in `_modalRegistry`. Returns `{ show, hide, isVisible, el, card }`. `closeTopmostModal()` pops the most recent visible modal — called from Escape handler in `focus.js`, replaces per-modal visibility flag checks.

### feedback.js

Feedback modal logic, gated behind `BRISTLENOSE_FEEDBACK` JS constant. `initFeedback()` checks flag, adds `body.feedback-enabled` class (CSS shows footer links), creates draft store, wires footer trigger. `getFeedbackModal()` lazily creates modal via `createModal()`. `submitFeedback()` tries `fetch()` to `BRISTLENOSE_FEEDBACK_URL` if endpoint configured and HTTP(S), falls back to `copyToClipboard()`. Draft persistence via `createStore('bristlenose-feedback-draft')`. Dependencies: `storage.js`, `modal.js`, `csv-export.js`.

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
