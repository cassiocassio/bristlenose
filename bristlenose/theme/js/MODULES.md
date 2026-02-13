# JS Module Reference

20 standalone files in `js/` concatenated at render time (same pattern as CSS): storage, badge-utils, modal, codebook, player, starred, editing, tags, histogram, csv-export, view-switcher, search, tag-filter, hidden, names, focus, feedback, analysis, global-nav, main. Transcript pages use `storage.js` + `badge-utils.js` + `player.js` + `transcript-names.js` + `transcript-annotations.js`. Codebook page uses `storage.js` + `badge-utils.js` + `modal.js` + `codebook.js`. Analysis page uses `storage.js` + `analysis.js`. `transcript-names.js` only updates heading speaker names (preserving code prefix: `"m1 Sarah Chen"`); segment speaker labels stay as raw codes (`p1:`, `m1:`) and are not overridden by JS.

## storage.js

Thin localStorage abstraction. `createStore(key)` returns `{ get, set }` pair. Also provides `escapeHtml(s)` — shared HTML escaping utility (escapes `&`, `<`, `>`, `"`) used by `codebook.js`, `histogram.js`, and any module inserting user-provided text into `innerHTML`. Defined before `createStore()` so it's available to all modules in the concatenation order.

## badge-utils.js

Shared badge DOM helpers loaded on all three page types (report, transcript, codebook). Pure DOM — no localStorage access, no side-effects. Load after `storage.js` and before any feature module.

- **`createUserTagBadge(name, colourVar)`** — returns `<span class="badge badge-user" data-badge-type="user" data-tag-name="...">name<button class="badge-delete">×</button></span>`. Does NOT add `badge-appearing` class (callers opt-in). `colourVar` is a CSS var string or null
- **`createReadOnlyBadge(name, colourVar)`** — same markup as `createUserTagBadge` but without the `×` delete button. For informational/non-editable contexts (tag filter dropdown, tooltips, previews)
- **`animateBadgeRemoval(el, opts)`** — adds `.badge-removing`, on `animationend` either `el.remove()` (default) or `el.style.display = 'none'` (if `opts.hide` is true). Optional `opts.onDone` callback
- **`getTagColour(tagName, codebookData)`** — pure function, takes codebook data object `{ groups: [], tags: {} }` as parameter. Returns CSS `var()` string or null for ungrouped tags. Used directly by `transcript-annotations.js`; wrapped by `getTagColourVar()` in `codebook.js` (which adds `'var(--bn-custom-bg)'` fallback for ungrouped)
- **Consumers**: `tags.js` (`createUserTagEl` wraps `createUserTagBadge`, delete handlers call `animateBadgeRemoval`), `transcript-annotations.js` (badge creation and deletion), `codebook.js` (`getTagColourVar` delegates to `getTagColour`, `_renderTagRow` uses `createUserTagBadge`), `tag-filter.js` (`createReadOnlyBadge` for filter badges)

## player.js

Popout video/audio player integration and playback-synced glow highlighting.

- **`seekTo(pid, seconds)`** — opens player window (or posts seek message to existing one)
- **`initPlayer()`** — click delegation on `a.timecode[data-participant][data-seconds]`; listens for `postMessage` from the player window (`bristlenose-timeupdate`, `bristlenose-playstate`); polls `playerWin.closed` every 1s to clean up glow
- **Glow index**: `_buildGlowIndex()` runs lazily on first `timeupdate`. Indexes `.transcript-segment[data-start-seconds]` (transcript pages) and `blockquote[data-participant]` (report pages) into a `{pid → [{el, start, end}]}` lookup. Zero-length segments (where `end == start`, common in `.txt`-parsed transcripts) are patched to use the next segment's start time
- **Glow classes**: `.bn-timecode-glow` (steady, player paused) and `.bn-timecode-playing` (pulsating, player playing). Set-based diffing ensures only changed elements touch the DOM each tick (~4 calls/sec)
- **Auto-scroll**: transcript page segments auto-scroll to center on first entry into glow state. Report blockquotes do not auto-scroll
- **Cleanup**: `_clearAllGlow()` removes all glow classes when the player window is closed
- **CSS**: glow tokens in `tokens.css` (`--bn-glow-colour`, `--bn-glow-colour-strong`); keyframes and classes in `atoms/timecode.css`; suppressed in `templates/print.css`
- **Accessibility**: `.bn-no-animations` zeroes animation durations; `@media (prefers-reduced-motion: reduce)` disables pulse; steady glow (box-shadow) remains in all cases

## transcript-annotations.js

Right-margin annotations on transcript pages: section/theme labels, tag badges, and vertical span bars alongside quoted segments. Non-quoted segments are knocked back to 0.6 opacity by CSS.

- **Stores**: `bristlenose-tags`, `bristlenose-deleted-badges`, `bristlenose-codebook` — same stores as the report page, enabling cross-page sync
- **`initTranscriptAnnotations()`** — reads `BRISTLENOSE_QUOTE_MAP` (baked into HTML by Python renderer), initialises stores, renders annotations, installs event handlers, listens for `storage` events to re-render on cross-window changes
- **Two-pass rendering** (`_renderAllAnnotations`):
  1. Build `quoteSegments` map (qid → ordered list of `.segment-quoted` elements)
  2. For each segment, render margin annotations on the FIRST segment only per quote
  3. Render vertical span bars showing each quote's extent
- **Label dedup**: section/theme labels shown only on first occurrence via `seenLabels` map keyed by `type:label`
- **Badge deletion** (event delegation on `document`, scoped to `.segment-margin`):
  - AI sentiment badges: click anywhere to delete, animates out, persists to `bristlenose-deleted-badges`
  - User tags: click × button to delete, animates out, persists to `bristlenose-tags`
- **Span bars** (`_renderSpanBars`): reads `--bn-span-bar-gap` and `--bn-span-bar-offset` tokens from CSS. Greedy slot assignment avoids vertical overlap. Creates `.span-bar` elements (styled by `atoms/span-bar.css`); JS only sets position and height
- **Dependencies**: `storage.js` (`createStore`), `badge-utils.js` (`createUserTagBadge`, `animateBadgeRemoval`, `getTagColour`)
- **CSS**: `molecules/transcript-annotations.css` (margin layout, badge sizing, responsive breakpoints), `atoms/span-bar.css` (visual properties)

## names.js

Inline name editing for the participant table. Follows the same `contenteditable` lifecycle as `editing.js` (start → accept/cancel → persist).

- **Store**: `createStore('bristlenose-names')` — shape `{pid: {full_name, short_name, role}}`
- **Edit flow**: pencil icon on hover → click makes cell `contenteditable` → Enter/click-outside saves, Escape cancels
- **Auto-suggest**: `suggestShortName(fullName, allNames)` mirrors the Python heuristic — first name, disambiguate collisions with last-name initial ("Sarah J.")
- **DOM updates**: `updateAllReferences(pid)` propagates name changes to participant table cells only. Quote attributions (`.speaker-link`) intentionally show raw pids for anonymisation — not updated by JS
- **Reconciliation**: `reconcileWithBaked()` prunes localStorage entries that match `BN_PARTICIPANTS` (baked-in JSON from render time) — after user pastes edits into `people.yaml` and re-renders, browser state auto-cleans
- **Export**: "Export names" toolbar button copies a YAML snippet via `copyToClipboard()` + `showToast()` (from `csv-export.js`)
- **Dependencies**: must load after `csv-export.js` (needs `showToast`, `copyToClipboard`) and before `main.js` (boot calls `initNames()`)
- **Data source**: `BN_PARTICIPANTS` global — JSON object `{pid: {full_name, short_name, role}}` emitted by `render_html.py` in a `<script>` block

## view-switcher.js

Dropdown menu to switch between report views. Three modes: `all` (default), `starred`, `participants`.

- **`initViewSwitcher()`** — wires up button toggle, menu item selection, outside-click-to-close
- **`_applyView(view, btn, menu, items)`** — sets `currentViewMode` global (defined in `csv-export.js`), updates button label text, toggles active menu item, swaps export button visibility, toggles `<section>` visibility
- **Section visibility**: `all` shows everything, `starred` shows all sections but hides non-starred blockquotes, `participants` shows only the section whose `<h2>` contains "Participants"
- **Export button swap**: `#export-csv` (Copy CSV) visible in `all`/`starred` views; `#export-names` (Export names) visible in `participants` view
- **Search notification**: `_applyView()` calls `_onViewModeChange()` (defined in `search.js`) after applying the view — guarded with `typeof` check so transcript pages (which don't load search.js) don't error
- **Dependencies**: must load after `csv-export.js` (writes `currentViewMode`); before `search.js` and `main.js`
- **CSS**: `organisms/toolbar.css` — `.view-switcher`, `.view-switcher-label`, `.view-switcher-menu` (dropdown positioned absolute right), `.menu-icon` (invisible spacer for alignment). The view switcher button uses dual classes `toolbar-btn view-switcher-btn` — shared round-rect from `atoms/button.css`, dropdown arrow uses `.toolbar-arrow`

## search.js

Search-as-you-type filtering for report quotes. Collapsed magnifying glass icon in the toolbar.

- **`initSearchFilter()`** — wires up toggle button (expand/collapse), text input (debounced 150ms), clear button (×), Escape to clear+collapse
- **`_applySearchFilter()`** — when query >= 3 chars, searches across ALL quotes regardless of view mode (`currentViewMode`). Matches against `.quote-text`, `.speaker-link`, and `.badge` text (skipping `.badge-add`). Case-insensitive `indexOf()` matching. Toggles `.has-query` class on container, highlights matches, hides ToC/Participants, overrides view-switcher label with match count
- **`_highlightMatches(query)`** — wraps matched substrings in visible `.quote-text` elements with `<mark class="search-mark">` using a TreeWalker over text nodes
- **`_clearHighlights()`** — removes all `<mark class="search-mark">` elements, unwrapping text. Called at start of every `_applySearchFilter()`
- **`_setNonQuoteVisibility(display)`** — hides/shows `.toc-row` and Participants section during active search
- **`_overrideViewLabel(label)` / `_restoreViewLabel()`** — temporarily sets the view-switcher button text to the match count ("7 matching quotes") during active search. Saves/restores original label via `_savedViewLabel` module variable
- **`_restoreViewMode()`** — when query is cleared or < 3 chars, restores the view-switcher's visibility state (respects starred mode), restores ToC/Participants, restores view-switcher label
- **`_hideEmptySections()`** — hides `<section>` elements (and preceding `<hr>`) when all child blockquotes are hidden. Only targets sections with `.quote-group` (skips Participants, Sentiment, Journeys)
- **`_hideEmptySubsections()`** — hides individual h3+description+quote-group clusters within a section when all their quotes are hidden
- **`_onViewModeChange()`** — called by `view-switcher.js` after view mode changes. Hides search in participants mode (no quotes to search), re-applies filter or restores view mode otherwise
- **Dependencies**: must load after `csv-export.js` (reads `currentViewMode` global) and after `view-switcher.js` (which calls `_onViewModeChange()`); before `names.js` and `main.js`
- **CSS**: `molecules/search.css`

## tag-filter.js

Dropdown filter for quotes by user tag. Reads the codebook's group hierarchy to organise tags into tinted sections matching the codebook page's visual design. Search matches both tag names and group names.

- **Store**: `createStore('bristlenose-tag-filter')` — shape `{ unchecked: [], noTagsUnchecked: false, clearAll: false }`
- **`initTagFilter()`** — wires up button toggle, outside-click close, Escape handling, applies persisted filter state on load
- **`_buildTagFilterMenu(menu)`** — called every time the menu opens (tags are dynamic). Renders: actions row → search input (8+ tags) → "(No tags)" checkbox → divider → ungrouped tags (flat) → codebook groups (tinted `.tag-filter-group` containers with `var(--bn-group-{set})` background)
- **`_groupTagsByCodebook(names, tagCounts)`** — reads the `codebook` global, buckets tags into groups. Returns array of sections `{ label, groupId, groupBgVar, tags }`. Ungrouped first, codebook groups in order. Falls back to flat count-sorted list when codebook has no groups
- **`_createCheckboxItem(tag, label, checked, muted, count, colourVar)`** — creates checkbox + badge row. User tags use `createReadOnlyBadge()` from badge-utils.js (no delete button). "(No tags)" uses plain italic text
- **`_filterMenuItems(menu, query)`** — search matches tag names OR group names (via `data-group-name` attribute on containers). Group name match shows all tags in that group. Hides containers when no children match
- **`_applyTagFilter()`** — core filtering: quotes visible if ≥1 checked tag. Respects `.bn-hidden`, starred view, "(No tags)" toggle. Cascades `_hideEmptySections()` / `_hideEmptySubsections()`
- **`_updateTagFilterButton()`** — updates button label ("12 of 16 tags"). Sets stable `min-width` to prevent layout shift
- **`_updateVisibleQuoteCount()`** — replaces view-switcher label with filtered count during active filter
- **`_onTagFilterViewChange()`** — called by `view-switcher.js` on mode change. Hides filter in participants view
- **Dependencies**: `storage.js`, `badge-utils.js` (`createReadOnlyBadge`), `codebook.js` (`codebook`, `COLOUR_SETS`, `getTagColourVar`), `tags.js` (`allTagNames`, `userTags`), `csv-export.js` (`currentViewMode`), `search.js` (`_hideEmptySections`, `_hideEmptySubsections`)
- **Rebuild-on-open**: menu DOM is rebuilt every open, so codebook colour changes from the codebook window are picked up without a dedicated `storage` event listener
- **CSS**: `molecules/tag-filter.css`

## Inline heading/description editing

Section titles, descriptions, theme titles, and theme descriptions use `.editable-text` spans with pencil icons for inline editing. Handled by `initInlineEditing()` in `editing.js` (same file as quote editing, separate state tracker).

- **`.edit-pencil-inline`** in `atoms/button.css` — overrides `.edit-pencil` absolute positioning with `position: static; display: inline` for flow-inline placement after text
- **`.editable-text.editing`** in `molecules/quote-actions.css` — editing highlight (same visual as `.quote-text` editing)
- **`.editable-text.edited`** in `molecules/quote-actions.css` — dashed underline indicator for changed text
- **Bidirectional ToC sync** — ToC entries and section headings share the same `data-edit-key`; `_syncSiblings()` keeps all matching spans in sync on edit

## hidden.js

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

## modal.js

Shared modal factory used by help overlay (`focus.js`), feedback modal (`feedback.js`), codebook panel (`codebook.js`), and histogram delete (`histogram.js`). Two main functions:

- **`createModal({ className, modalClassName, content, onHide })`** — builds overlay + card + close button DOM, wires click-outside and close button, registers in `_modalRegistry`. Returns `{ show, hide, isVisible, toggle, el, card }`. The `toggle()` method simplifies show/hide switching (used by `focus.js` help overlay and codebook help)
- **`showConfirmModal({ title, body, confirmLabel, confirmClass, onConfirm })`** — reusable confirmation dialog with Cancel + action button. Lazily creates a single modal instance, replaces body content each call. `confirmClass` defaults to `'bn-btn-danger'`; use `'bn-btn-primary'` for non-destructive actions (e.g. merge). Used by `codebook.js` (delete tag, delete group, merge tags) and `histogram.js` (delete tag from all quotes)

`closeTopmostModal()` pops the most recent visible modal — called from Escape handler in `focus.js` and codebook panel keydown handler.

## feedback.js

Feedback modal logic, gated behind `BRISTLENOSE_FEEDBACK` JS constant. `initFeedback()` checks flag, adds `body.feedback-enabled` class (CSS shows footer links), creates draft store, wires footer trigger. `getFeedbackModal()` lazily creates modal via `createModal()`. `submitFeedback()` tries `fetch()` to `BRISTLENOSE_FEEDBACK_URL` if endpoint configured and HTTP(S), falls back to `copyToClipboard()`. Draft persistence via `createStore('bristlenose-feedback-draft')`. Dependencies: `storage.js`, `modal.js`, `csv-export.js`.

## codebook.js

Codebook data model, colour assignment, and interactive panel UI. Manages the researcher's tag taxonomy: named groups of tags with colours from the OKLCH pentadic palette. On the report page, provides colour lookups. On the codebook tab (or standalone `codebook.html`), renders the full interactive panel with drag-and-drop, inline editing, and group CRUD.

- **Store**: `createStore('bristlenose-codebook')` — shape `{ groups: [], tags: {}, aiTagsVisible: true }`
- **Colour sets**: 5 pentadic sets (UX blue, Emotion red-pink, Task green-teal, Trust purple, Opportunity amber), each with 5–6 slots. `COLOUR_SETS` includes `bgVar`, `groupBg`, `barVar` properties for panel rendering
- **`getTagColourVar(tagName)`** — returns CSS `var()` reference for a tag's background colour; `var(--bn-custom-bg)` for ungrouped tags. Delegates to shared `getTagColour()` from `badge-utils.js` and adds the ungrouped fallback
- **`assignTagToGroup(tagName, groupId)`** — assigns tag with auto-picked colour index
- **`createCodebookGroup(name, colourSet)`** — creates a group with auto-assigned colour set if not specified
- **`initCodebook()`** — restores AI tag visibility, applies codebook colours to badges. On codebook tab or codebook page, calls `_initCodebookPanel()` to render the interactive grid
- **AI tag toggle**: code commented out (removed from toolbar — TODO: relocate to future settings panel). Functions `isAiTagsVisible()`, `toggleAiTags()`, `_applyAiTagVisibility()` remain available
- **Cross-window sync**: `storage` event listener reloads codebook state and re-renders panel (or re-applies colours on report page) when the other window writes
- **Panel rendering** (codebook tab and standalone codebook page):
  - `_initCodebookPanel(grid)` — renders grid, wires `?` key for help modal and `Escape` for `closeTopmostModal()`
  - `_renderCodebookGrid(grid)` — builds ungrouped column, group columns, and "+ New group" placeholder
  - `_renderGroupColumn()` — header (title, subtitle, close button), tag list with micro bars, add-tag row
  - `_renderTagRow()` — badge with colour, delete button, micro histogram bar, quote count, drag handlers
- **Drag-and-drop**: `_dragTag`/`_dragGhost` state. Drag tag → group column = move. Drag tag → tag row = merge (with `showConfirmModal`). Drag tag → "+ New group" = create group with tag
- **Inline editing**: `_editGroupTitle()`, `_editGroupSubtitle()`, `_addTagInline()` — all use `committed` flag guard pattern to prevent double-commit on blur+Enter
- **Confirmation dialogs**: `_confirmMergeTags()`, `_confirmDeleteTag()`, `_confirmDeleteGroup()` — all use `showConfirmModal()` from `modal.js`
- **Help modal**: `_toggleCodebookHelp()` with codebook-specific shortcuts (?, Esc, Enter, drag actions), wired to `?` key
- **Tag name collection**: `_allTagNames()` merges tags from both `bristlenose-tags` (user tags with quotes) AND `codebook.tags` (tags assigned to groups but possibly with 0 quotes)
- **Dependencies**: `storage.js` (for `createStore`, `escapeHtml`), `badge-utils.js` (for `createUserTagBadge`, `getTagColour`), `modal.js` (for `createModal`, `showConfirmModal`, `closeTopmostModal` — on codebook page only)

## global-nav.js

Top-level tab bar for report navigation. Manages switching between tab panels (Project, Sessions, Quotes, Codebook, Analysis, Settings, About), the Sessions tab drill-down sub-navigation, and all cross-tab navigation from the Project dashboard.

### Reusable navigation helpers

- **`scrollToAnchor(anchorId, opts)`** — waits one rAF, finds element by ID, smooth-scrolls to it. Options: `{ block: 'start'|'center', highlight: true|false }`. When `highlight` is true, triggers the yellow-flash `anchor-highlight` CSS animation (same as standalone transcript pages). Use this whenever you need to scroll to an element after a tab switch or layout change
- **`navigateToSession(sid, anchorId)`** — switches to Sessions tab, drills into the session, and optionally scrolls to a timecode anchor with highlight. Null-safe (returns early if `sid` is falsy or `_sessGrid` is uninitialised). Use this from any module that needs to deep-link into a session transcript

### Tab switching

- **`switchToTab(tabName, pushHash)`** — switch to a named tab. Updates `aria-selected` on tab buttons, toggles `.active` on panels, pushes URL hash (`#codebook`, `#analysis`, etc.) for reload persistence and back/forward navigation. Pass `pushHash=false` to skip hash update (used by `popstate` handler and initial load). Exported for cross-module use (e.g. speaker links navigating to Sessions tab, logo click → Project tab via inline `onclick` in `report_header.html`)
- **Hash-based tab persistence**: `_validTabs` whitelist; `history.pushState` on tab switch; `popstate` listener for back/forward; hash read on init for reload. Invalid/missing hash falls back to Project tab (server-rendered default)

### Session drill-down (Sessions tab)

- **`_initSessionDrillDown()`** — click handlers on session table rows (`tr[data-session]`) and session number links (`a[data-session-link]`) in the Sessions tab grid to drill into inline transcript views; back button returns to grid
- **`_showSession(sid)`** — hides session grid, shows the matching `.bn-session-page`, updates sub-nav label, re-renders transcript annotations (span bars need layout measurements). Stores `_currentSessionId` so returning to the Sessions tab restores drill-down state
- **`_showGrid()`** — returns to the session grid, hides all transcript pages, clears `_currentSessionId`

### Cross-tab navigation (Project dashboard)

- **`_initSpeakerLinks()`** — click handlers on `a[data-nav-session]` links in quote cards. Delegates to `navigateToSession()`
- **Stat card links** — elements with `data-stat-link="tab"` or `data-stat-link="tab:anchorId"` navigate to the target tab and optionally scroll to an anchor. Uses `switchToTab()` + `scrollToAnchor()`. Python renderer adds these attributes to dashboard stat cards in `render_html.py`
- **Featured quote cards** — clicking a `.bn-featured-quote` card body (not its internal links) either opens the video player via `seekTo()` (if a video-enabled timecode link exists) or falls back to `navigateToSession()` for transcript navigation
- **Dashboard session table rows** — rows in the Project tab's session table navigate via `navigateToSession()`. The `#N` session-link clicks are also intercepted. Filename links (video/file) pass through unhandled
- **Section/theme list links** — `.bn-dashboard-nav a[href^="#"]` links switch to the Quotes tab and scroll to the target section/theme anchor via `scrollToAnchor()`

### Module state and dependencies

- **Module state**: `_validTabs`, `_sessGrid`, `_sessSubnav`, `_sessLabel`, `_sessPages`, `_currentSessionId` — valid tab names, cached DOM references, and current drill-down state
- **`initGlobalNav()`** — wires all of the above: tab click handlers, hash restore, popstate, session drill-down, speaker links, stat cards, featured quotes, dashboard table rows, section/theme list links, featured quotes reshuffle
- **Dependencies**: must load after `focus.js` and `feedback.js`; before `transcript-names.js` and `transcript-annotations.js` (transcript pages embedded in Sessions tab need annotation rendering). Calls `_renderAllAnnotations()` from `transcript-annotations.js` if available
- **CSS**: `organisms/global-nav.css` — tab bar, tab buttons, panels, session grid, session sub-nav, dashboard stats/featured/list panes, responsive horizontal scroll

## Codebook page

Standalone HTML page (`codebook.html`) at the output root. Rendered by `_render_codebook_page()` in `render_html.py`. Same content is also rendered inline in the report's Codebook tab. Features:

- **Layout**: CSS columns masonry grid (`columns: 240px`, `organisms/codebook-panel.css`) with colour-coded group cards
- **Content**: description text + `<div class="codebook-grid" id="codebook-grid">` container populated by `_initCodebookPanel()` from `codebook.js`
- **JS files**: `_CODEBOOK_JS_FILES` = `storage.js` + `badge-utils.js` + `modal.js` + `codebook.js`. Boot calls `initCodebook()` which detects the `#codebook-grid` element and renders the panel
- **Interactive features**: drag-and-drop tags between groups, merge tags, inline-edit group titles/subtitles, add/delete tags, create/delete groups, keyboard shortcuts (? help, Esc close)
- **Cross-window sync**: localStorage `storage` event — changes in the codebook page propagate to the report (badge colours update), and vice versa (new user tags appear)

## settings.js

Application appearance toggle. Lets users switch between system/light/dark theme via radio buttons in the Settings tab.

- **`initSettings()`** — reads saved preference from localStorage, sets the matching radio button, applies theme to `<html>`, attaches change listeners
- **localStorage key**: `bristlenose-appearance` (via `createStore`). Values: `"auto"`, `"light"`, `"dark"`
- **Theme application**: sets/removes `data-theme` attribute on `<html>` and updates `style.colorScheme`. "auto" removes the attribute and restores `"light dark"` so the browser follows OS preference
- **`_settingsThemeAttr`**: uses `"data-" + "theme"` concatenation to avoid the literal string in embedded HTML (dark mode tests assert its absence when `color_scheme="auto"`)
- **Dependencies**: `storage.js` (`createStore`)
- **CSS**: `organisms/settings.css` (fieldset reset, radio label layout)

## analysis.js

Analysis rendering: signal cards, heatmaps, and interactive features. Renders analysis content from `BRISTLENOSE_ANALYSIS` JSON data both in the report's Analysis tab and on standalone `analysis.html`.

- **Data source**: `BRISTLENOSE_ANALYSIS` global — JSON object injected by `render_html.py` containing `signals`, `sectionMatrix`, `themeMatrix`, `totalParticipants`, `sentiments`, `participantIds`, `reportFilename`
- **`initAnalysis()`** — if `#signal-cards` container and `BRISTLENOSE_ANALYSIS` data exist, renders signal cards + heatmaps; otherwise returns early
- **`renderSignalCards()`** — builds signal card list from `data.signals`. Each card has: accent bar (sentiment colour), location/sentiment header, metrics grid (concentration bar, Neff, intensity dots), expandable quote list, participant presence grid, link back to report section
- **`renderHeatmap(matrix, containerId, rowHeader, sourceType)`** — builds contingency table with OKLCH-coloured cells. Computes adjusted residuals client-side for theme-responsive colouring. Cells with matching signals are clickable (smooth-scroll to card with highlight flash)
- **`adjustedResidual(observed, rowTotal, colTotal, grandTotal)`** — client-side duplicate of Python `adjusted_residual()` from `metrics.py`, needed for theme-responsive heatmap colours (recomputed on dark mode toggle)
- **`heatCellColour(heat, hue, chroma, isDark)`** — OKLCH colour ramp: lightness interpolated between `lMin` and `lMax` based on normalised heat value
- **`intensityDotsSvg(intensity, size, colour)`** — renders 1–5 filled/empty dots as inline SVG
- **Dark mode**: `MutationObserver` on `<html>` attribute changes re-renders heatmaps when theme toggles (OKLCH lightness direction inverts). Uses `THEME_ATTR = "data-" + "theme"` constant to avoid literal string in embedded HTML (dark mode tests assert absence)
- **Dependencies**: none (self-contained). Loaded on both report page (`_JS_FILES`, for inline Analysis tab) and standalone analysis page (`_ANALYSIS_JS_FILES`)
- **CSS**: `organisms/analysis.css` (signal cards, heatmap table, confidence badges, expansion animation)

## Analysis page

Standalone HTML page (`analysis.html`) at the output root. Rendered by `_render_analysis_page()` in `render_html.py`. Same content also renders inline in the report's Analysis tab. Features:

- **Layout**: signal cards list + two heatmap tables (Section×Sentiment, Theme×Sentiment)
- **JS files**: `_ANALYSIS_JS_FILES` = `storage.js` + `analysis.js`. Boot calls `initAnalysis()` which detects `#signal-cards` element and renders content
- **Data injection**: `BRISTLENOSE_ANALYSIS` JSON global with serialised matrices and signals (injected into both main report and standalone page)
- **Interactive features**: expandable quote lists per signal card, heatmap cell click → scroll to signal card, dark mode toggle re-renders heatmaps
- **Cross-page**: signal card links point back to report sections

Four page types in the output:
1. **Report** (`bristlenose-{slug}-report.html`) — main window, full JS suite (20 modules)
2. **Transcript** (`sessions/transcript_{id}.html`) — separate pages, `storage.js` + `badge-utils.js` + `player.js` + `transcript-names.js` + `transcript-annotations.js`
3. **Codebook** (`codebook.html`) — new window, `storage.js` + `badge-utils.js` + `modal.js` + `codebook.js`
4. **Analysis** (`analysis.html`) — new window, `storage.js` + `analysis.js`
