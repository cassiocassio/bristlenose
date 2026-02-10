# JS Module Reference

19 standalone files in `js/` concatenated at render time (same pattern as CSS): storage, badge-utils, modal, codebook, player, starred, editing, tags, histogram, csv-export, view-switcher, search, tag-filter, hidden, names, focus, feedback, global-nav, main. Transcript pages use `storage.js` + `badge-utils.js` + `player.js` + `transcript-names.js` + `transcript-annotations.js`. Codebook page uses `storage.js` + `badge-utils.js` + `modal.js` + `codebook.js`. `transcript-names.js` only updates heading speaker names (preserving code prefix: `"m1 Sarah Chen"`); segment speaker labels stay as raw codes (`p1:`, `m1:`) and are not overridden by JS.

## storage.js

Thin localStorage abstraction. `createStore(key)` returns `{ get, set }` pair. Also provides `escapeHtml(s)` — shared HTML escaping utility (escapes `&`, `<`, `>`, `"`) used by `codebook.js`, `histogram.js`, and any module inserting user-provided text into `innerHTML`. Defined before `createStore()` so it's available to all modules in the concatenation order.

## badge-utils.js

Shared badge DOM helpers loaded on all three page types (report, transcript, codebook). Pure DOM — no localStorage access, no side-effects. Load after `storage.js` and before any feature module.

- **`createUserTagBadge(name, colourVar)`** — returns `<span class="badge badge-user" data-badge-type="user" data-tag-name="...">name<button class="badge-delete">×</button></span>`. Does NOT add `badge-appearing` class (callers opt-in). `colourVar` is a CSS var string or null
- **`animateBadgeRemoval(el, opts)`** — adds `.badge-removing`, on `animationend` either `el.remove()` (default) or `el.style.display = 'none'` (if `opts.hide` is true). Optional `opts.onDone` callback
- **`getTagColour(tagName, codebookData)`** — pure function, takes codebook data object `{ groups: [], tags: {} }` as parameter. Returns CSS `var()` string or null for ungrouped tags. Used directly by `transcript-annotations.js`; wrapped by `getTagColourVar()` in `codebook.js` (which adds `'var(--bn-custom-bg)'` fallback for ungrouped)
- **Consumers**: `tags.js` (`createUserTagEl` wraps `createUserTagBadge`, delete handlers call `animateBadgeRemoval`), `transcript-annotations.js` (badge creation and deletion), `codebook.js` (`getTagColourVar` delegates to `getTagColour`, `_renderTagRow` uses `createUserTagBadge`)

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
- **`_hideEmptySections()`** — hides `<section>` elements (and preceding `<hr>`) when all child blockquotes are hidden. Only targets sections with `.quote-group` (skips Participants, Sentiment, Friction, Journeys)
- **`_hideEmptySubsections()`** — hides individual h3+description+quote-group clusters within a section when all their quotes are hidden
- **`_onViewModeChange()`** — called by `view-switcher.js` after view mode changes. Hides search in participants mode (no quotes to search), re-applies filter or restores view mode otherwise
- **Dependencies**: must load after `csv-export.js` (reads `currentViewMode` global) and after `view-switcher.js` (which calls `_onViewModeChange()`); before `names.js` and `main.js`
- **CSS**: `molecules/search.css`

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

Codebook data model, colour assignment, and interactive panel UI. Manages the researcher's tag taxonomy: named groups of tags with colours from the OKLCH pentadic palette. On the report page, provides colour lookups and the toolbar button. On `codebook.html`, renders the full interactive panel with drag-and-drop, inline editing, and group CRUD.

- **Store**: `createStore('bristlenose-codebook')` — shape `{ groups: [], tags: {}, aiTagsVisible: true }`
- **Colour sets**: 5 pentadic sets (UX blue, Emotion red-pink, Task green-teal, Trust purple, Opportunity amber), each with 5–6 slots. `COLOUR_SETS` includes `bgVar`, `groupBg`, `barVar` properties for panel rendering
- **`getTagColourVar(tagName)`** — returns CSS `var()` reference for a tag's background colour; `var(--bn-custom-bg)` for ungrouped tags. Delegates to shared `getTagColour()` from `badge-utils.js` and adds the ungrouped fallback
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
- **Dependencies**: `storage.js` (for `createStore`, `escapeHtml`), `badge-utils.js` (for `createUserTagBadge`, `getTagColour`), `modal.js` (for `createModal`, `showConfirmModal`, `closeTopmostModal` — on codebook page only)

## global-nav.js

Top-level tab bar for report navigation. Manages switching between tab panels (Project, Sessions, Quotes, Codebook, Analysis, Settings, About) and the Sessions tab drill-down sub-navigation.

- **`switchToTab(tabName)`** — switch to a named tab. Updates `aria-selected` on tab buttons, toggles `.active` on panels. Exported for cross-module use (e.g. speaker links navigating to Sessions tab)
- **`initGlobalNav()`** — wires tab click handlers, initialises session drill-down and speaker link navigation
- **`_initSessionDrillDown()`** — click handlers on session table rows (`tr[data-session]`) and session number links (`a[data-session-link]`) to drill into inline transcript views; back button returns to grid
- **`_initSpeakerLinks()`** — click handlers on `a[data-nav-session]` links in quote cards. Navigates: switch to Sessions tab → drill into session → scroll to `data-nav-anchor` timecode
- **`_showSession(sid)`** — hides session grid, shows the matching `.bn-session-page`, updates sub-nav label, re-renders transcript annotations (span bars need layout measurements). Stores `_currentSessionId` so returning to the Sessions tab restores drill-down state
- **`_showGrid()`** — returns to the session grid, hides all transcript pages, clears `_currentSessionId`
- **Module state**: `_sessGrid`, `_sessSubnav`, `_sessLabel`, `_sessPages`, `_currentSessionId` — cached DOM references and current drill-down state
- **Dependencies**: must load after `focus.js` and `feedback.js`; before `transcript-names.js` and `transcript-annotations.js` (transcript pages embedded in Sessions tab need annotation rendering). Calls `_renderAllAnnotations()` from `transcript-annotations.js` if available
- **CSS**: `organisms/global-nav.css` — tab bar, tab buttons, panels, session grid, session sub-nav, responsive horizontal scroll

## Codebook page

Standalone HTML page (`codebook.html`) at the output root, opened in a new window by the toolbar Codebook button. Rendered by `_render_codebook_page()` in `render_html.py`. Features:

- **Layout**: CSS columns masonry grid (`columns: 240px`, `organisms/codebook-panel.css`) with colour-coded group cards
- **Content**: description text + `<div class="codebook-grid" id="codebook-grid">` container populated by `_initCodebookPanel()` from `codebook.js`
- **JS files**: `_CODEBOOK_JS_FILES` = `storage.js` + `badge-utils.js` + `modal.js` + `codebook.js`. Boot calls `initCodebook()` which detects the `#codebook-grid` element and renders the panel
- **Interactive features**: drag-and-drop tags between groups, merge tags, inline-edit group titles/subtitles, add/delete tags, create/delete groups, keyboard shortcuts (? help, Esc close)
- **Cross-window sync**: localStorage `storage` event — changes in the codebook page propagate to the report (badge colours update), and vice versa (new user tags appear)

Three page types in the output:
1. **Report** (`bristlenose-{slug}-report.html`) — main window, full JS suite (19 modules)
2. **Transcript** (`sessions/transcript_{id}.html`) — separate pages, `storage.js` + `badge-utils.js` + `player.js` + `transcript-names.js` + `transcript-annotations.js`
3. **Codebook** (`codebook.html`) — new window, `storage.js` + `badge-utils.js` + `modal.js` + `codebook.js`
