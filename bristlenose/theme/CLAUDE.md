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

**Logo click**: wrapped in `<a class="report-logo-link" href="#project" onclick="switchToTab('project');return false;">`. Clicking the fish logo navigates to the Project tab (home). CSS in `atoms/logo.css`: `.report-logo-link` removes underline and sets `line-height: 0` to prevent extra vertical space around the image.

### No JS theme toggle

Dark mode is CSS-only. No localStorage, no toggle button, no JS involved.

## Template CSS files

Template-level CSS in `templates/`: `report.css` (main report layout), `transcript.css` (per-session transcript pages — back button, segment layout, meta styling, citation highlight, anchor highlight animation), `print.css` (print overrides, hides interactive elements — includes `.feedback-links`, `.feedback-overlay`, `.footer-logo-picture`). Quote attribution links styled via `.speaker-link` in `organisms/blockquote.css` (inherits muted colour from `.speaker`, accent on hover).

### Inline citation highlight (bn-cited)

Quoted text within transcript segments is wrapped in `<mark class="bn-cited">` elements by the Python renderer. This marks the verbatim excerpt that was extracted as a quote — the rest of the segment is context.

- **CSS**: `.bn-cited` in `transcript.css` — currently `background: transparent` (visually invisible while treatment is being rethought). The `--bn-colour-cited-bg` token (`#fef9c3` light / `#3b2f05` dark) is preserved in `tokens.css`. To re-enable: change `background: transparent` to `background: var(--bn-colour-cited-bg)`
- **HTML**: `<mark class="bn-cited">` elements are always emitted by `render_html.py` regardless of CSS visibility — the mechanism is intact
- **Design rationale**: the knocked-back opacity on non-quoted segments (0.6) plus first-occurrence section/theme labels plus span bars provide sufficient visual cues for quote extent, making the inline highlight redundant for now

### Anchor highlight animation

When navigating to a transcript page via anchor link (e.g., from coverage section), the target segment flashes yellow and fades to normal over 5 seconds. Implemented via:
- **CSS**: `@keyframes anchor-fade` in `transcript.css` — fades from `--bn-colour-highlight` to transparent
- **JS**: `_highlightAnchorTarget()` in `transcript-names.js` — on page load, checks `location.hash` for `#t-\d+` pattern and adds `.anchor-highlight` class to matching segment

## Sentiment bar charts

Two side-by-side horizontal bar charts in the Sentiment section: AI sentiment (server-rendered) and User tags (JS-rendered by `histogram.js`). The dual-chart design lets researchers compare what the AI detected with what they've tagged themselves.

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

## Person-id molecule

`molecules/person-id.css` — reusable badge + name pattern for speaker identification in the session table. Combines the `.badge` atom with a named span.

- **`.bn-person-id`** — `inline-flex`, `align-items: center`, `gap: 0.4rem`, `white-space: nowrap`. Contains a `.badge` and a `.bn-person-id-name`
- **`.bn-person-id .badge`** — `flex-shrink: 0` (badge never truncates)
- **`.bn-person-id-name`** — `font-weight: 600` (semibold). In the moderator header, names use regular weight (no `.bn-person-id-name` class)
- **Usage**: session table speaker cells (semibold names) and moderator header (regular weight names). The molecule is included in `_THEME_FILES` in `render_html.py`

## Session table CSS

Session table styles in `templates/report.css`. The session table renders in both the Sessions tab and the Project tab.

- **`.bn-session-table`** — wrapper section, resets margin
- **`.bn-session-table tr`** — `border-bottom` on `<tr>` not `<td>` (ensures full-width horizontal rules even with varying cell heights)
- **`.bn-session-moderators`** — header sentence above table ("Sessions moderated by [m1] Rachel")
- **`.bn-session-speakers`** — flex column for vertically stacked speaker entries
- **`.bn-session-journey`** — muted colour, smaller text, wraps below start date
- **`.bn-session-id`** — `#N` format session number, compact column
- **`.bn-session-duration`** — `text-align: right` on both `<th>` and `<td>`
- **`.bn-video-thumb`** — 96×54px placeholder (16:9 HD aspect ratio), grey background, centred play icon
- **`.bn-play-icon`** — play triangle (▶) inside thumbnail
- **`.bn-session-friction`** — friction count, right-aligned
- **`.bn-sparkline` / `.bn-sparkline-bar`** — per-session sentiment mini-bar chart. Bar heights set inline, colours via `--bn-sentiment-{name}` tokens
- **`.bn-interviews-link`** — folder header link (opens input folder via `file://` URI)
- **`.bn-folder-icon`** — inline SVG folder icon in header link

## Span bar atom

Reusable vertical extent indicator for showing how far a range (e.g. a quote) extends across a list of items. Positioned absolutely by JS; visual properties come from `--bn-span-bar-*` tokens.

- **CSS**: `atoms/span-bar.css` — `.span-bar` uses `background`, `border-radius`, `opacity`, `width` from tokens, `pointer-events: none`
- **Tokens** (in `tokens.css`): `--bn-span-bar-width` (2px), `--bn-span-bar-gap` (6px), `--bn-span-bar-offset` (8px), `--bn-span-bar-colour` (border colour), `--bn-span-bar-opacity` (0.5), `--bn-span-bar-radius` (1px)
- **Usage**: JS creates `<div class="span-bar">`, sets `position: absolute`, `top`, `height`, `right` via inline styles, and appends to a `position: relative` container. Currently used by `transcript-annotations.js` for quote extent bars
- **Responsive**: hidden on narrow viewports via `molecules/transcript-annotations.css` (`@media (max-width: 1099px) { .span-bar { display: none } }`)

## Transcript annotations molecule

Right-margin annotation layout for transcript pages. Shows section/theme labels, tag badges, and span bars alongside quoted segments. This helps researchers see at a glance which parts of a transcript contributed to which report sections.

- **CSS**: `molecules/transcript-annotations.css`
- **`.segment-margin`** — annotation container. Wide viewports: absolute-positioned in right margin (`right: -13.5rem`, `width: 12.5rem`). Narrow viewports: inline below the segment text (`margin-left: 3.5rem` to align past timecode column)
- **`.transcript-body`** — gets `padding-right: 14rem` on wide viewports to make room for the margin column
- **`.margin-annotation`** — one per quote in a segment, flex column with 2px gap
- **`.margin-label`** — section/theme label, accent colour, truncated with ellipsis, links to report quote
- **`.margin-tags`** — flex row of badge elements, `overflow: visible` to allow delete × circles to protrude
- **Breakpoint**: 1100px — below this, annotations are inline and span bars are hidden

## JS modules

19 standalone files in `js/` — see `js/MODULES.md` for per-module API docs. Key dependency: load order matters (see Gotchas below).

## CSS component reference

Per-component CSS docs in `CSS-REFERENCE.md`. Key patterns: toolbar dual-class (`.toolbar-btn` + component class), modal base (`.bn-overlay` + `.bn-modal`), sentiment grid (`display: contents`).

## Jinja2 templates

14 HTML templates in `templates/` (alongside CSS template files). All use `autoescape=False` — escape in Python with `_esc()` before passing to template. Jinja2 environment: `_jinja_env` at module level in `render_html.py`.

| Template | Parameters | Used by |
|----------|------------|---------|
| `document_shell_open.html` | `color_scheme`, `title`, `css_href` | Report, transcript, codebook |
| `report_header.html` | `assets_prefix`, `has_logo`, `has_dark_logo`, `project_name`, `doc_title`, `meta_right` | Report, transcript, codebook |
| `footer.html` | `version`, `assets_prefix` | Report, transcript, codebook |
| `quote_card.html` | `q` (quote context dict) | Report |
| `toolbar.html` | (none — static) | Report |
| `session_table.html` | `rows` (list of dicts), `moderator_header` (str) | Report |
| `toc.html` | `section_toc`, `theme_toc`, `chart_toc` | Report |
| `content_section.html` | `heading`, `item_type`, `groups` | Report (sections + themes) |
| `sentiment_chart.html` | `max_count`, `pos_bars`, `surprise_bar`, `neg_bars` | Report |
| `friction_points.html` | `groups` (list of dicts with `pid`, `entries`) | Report |
| `user_journeys.html` | `rows` (list of dicts) | Report |
| `coverage.html` | `summary`, `pct_omitted`, `sessions` | Report |
| `player.html` | (none — static) | Separate player file |
| `analysis.html` | (none — structural only, JS populates) | Analysis page |

## Gotchas

- **Jinja2 dict key naming**: never use Python dict method names (`items`, `keys`, `values`, `get`, `update`, `pop`) as dict keys passed to templates. Jinja2's attribute lookup resolves `group.items` as `dict.items` (the method) before `dict["items"]` (the key). Use alternative names (e.g. `entries` instead of `items`). Bracket notation (`group["items"]`) also works but is less readable
- **JS load order matters**: `view-switcher.js`, `search.js`, `tag-filter.js`, `hidden.js`, and `names.js` all load **after** `csv-export.js` in `_JS_FILES` — `view-switcher.js` writes the `currentViewMode` global defined in `csv-export.js`; `search.js` reads `currentViewMode` and exposes `_onViewModeChange()` called by `view-switcher.js`; `tag-filter.js` loads after `search.js` (reads `currentViewMode`, `_hideEmptySections`, `_hideEmptySubsections`; exposes `_applyTagFilter()`, `_onTagFilterViewChange()`, `_isTagFilterActive()`, `_updateVisibleQuoteCount()` called by `view-switcher.js`, `search.js`, and `tags.js`); `hidden.js` loads after `tag-filter.js` (reads `currentViewMode`, `_isTagFilterActive`, `_applyTagFilter`, `_hideEmptySections`; exposes `hideQuote()`, `bulkHideSelected()`, `isHidden()` called by `focus.js`); `names.js` depends on `copyToClipboard()` and `showToast()`
- **Hidden quotes vs visibility filters**: hidden quotes use `.bn-hidden` class + `style.display = 'none'`. This is fundamentally different from search/tag-filter/starred hiding (which are temporary view filters). Every visibility restore path (`_showAllQuotes`, `_showStarredOnly`, `_restoreViewMode`, `_restoreQuotesForViewMode`, `_applyTagFilter`, `_applySearchFilter`) must check for `.bn-hidden` and skip those quotes. The CSS `display: none !important` on `.bn-hidden` is defence-in-depth
- **`_TRANSCRIPT_JS_FILES`** includes `badge-utils.js`, `transcript-names.js`, and `transcript-annotations.js` (after `storage.js`). `transcript-names.js` reads localStorage name edits and updates heading speaker names only (preserving code prefix: `"m1 Sarah Chen"`). Does NOT override segment speaker labels (they stay as raw codes). Separate from the report's `names.js` (which has full editing UI). `transcript-annotations.js` renders margin annotations, span bars, and handles badge deletion
- **`blockquote .timecode`** in `blockquote.css` must use `--bn-colour-accent` not `--bn-colour-muted` — the `.timecode-bracket` children handle the muting. If you add a new timecode rendering context, ensure the parent rule uses accent
- **Modal infrastructure**: `atoms/modal.css` provides shared `.bn-overlay`, `.bn-modal`, `.bn-modal-close`, `.bn-modal-footer`, `.bn-modal-actions`, `.bn-btn`, `.bn-btn-cancel`, `.bn-btn-danger`, `.bn-btn-primary` classes. `.bn-modal` has `max-width: 24rem` default — override per-modal for wider content (e.g. `.help-modal { max-width: 600px }`). `js/modal.js` provides `createModal()` factory (returns `{ show, hide, isVisible, toggle }`) + `showConfirmModal()` reusable confirmation dialog + `_modalRegistry` + `closeTopmostModal()`. Help, feedback, codebook, and histogram modals all use these — don't duplicate overlay/card/close patterns
- **Sentiment chart layout**: both AI sentiment and user-tags charts use CSS grid (`grid-template-columns: max-content 1fr max-content`) on `.sentiment-chart`. Bar groups use `display: contents` so label/bar/count participate directly in the parent grid — this is what aligns all bar left edges within each chart. Labels use `width: fit-content` + `justify-self: start` so the background hugs the text and the variable gap falls between the label's right edge and the bar. The two charts sit side-by-side in `.sentiment-row` (flexbox, `align-items: flex-start` for top-alignment). Don't change the grid structure without checking both charts
- **Surprise sentiment placement**: surprise is neutral — it renders between positive sentiments and the divider, not after negative sentiments. See `_build_sentiment_html()` in `render_html.py`
- **Histogram delete-from-all**: clicking the hover `×` on a user tag label in the histogram shows a confirmation modal via `showConfirmModal()`, then removes that tag from every quote via `_deleteTagFromAllQuotes()` in `histogram.js`. This calls `persistUserTags()` which re-renders the histogram and re-applies tag filter
- **IIFE scoping and inline onclick**: all report JS is wrapped in `(function() { ... })()` by `render_html.py`. Functions defined inside are NOT accessible from inline `onclick` HTML attributes. Wire click handlers via `addEventListener` from JS instead. Footer links use `role="button" tabindex="0"` (no `href`) for keyboard accessibility
- **Stale HTML files cause debugging confusion** — if a previous render created a differently-named file (e.g. from a bug), the old file remains on disk. Always check which HTML file you're viewing matches the timestamp of your last render
- **Codebook page sits at output root** — `codebook.html` is at the same level as the report (not in `sessions/` or `assets/`), so it uses `assets/bristlenose-theme.css` (no `../` prefix). The `_footer_html()` helper uses `assets/` paths which work correctly for root-level pages
- **Tag-filter rebuilds on every open** — `_buildTagFilterMenu()` is called each time the dropdown opens because user tags are dynamic. This also means codebook colour/group changes from the codebook window are picked up automatically without a dedicated `storage` event listener. Don't cache the menu DOM
- **Tag-filter codebook integration** — tags are grouped into tinted `.tag-filter-group` containers using `var(--bn-group-{set})` tokens (same as codebook panel columns). Ungrouped tags appear first as flat items with no wrapper. Search matches both tag names and group names (via `data-group-name` attribute). Uses `createReadOnlyBadge()` from `badge-utils.js` (no delete button) — don't switch to `createUserTagBadge()` which includes a `×` button
- **Search threshold is 8 tags** — the tag-filter search input only appears when there are 8+ tags. This is a UX heuristic hardcoded in `_buildTagFilterMenu()`. If changing, update the MODULES.md entry too
- **Toolbar button dual-class pattern** — tag filter and view switcher buttons use dual classes (`toolbar-btn tag-filter-btn`, `toolbar-btn view-switcher-btn`). The shared `.toolbar-btn` provides round-rect styling; the component-specific class allows dropdown-specific overrides. Don't remove either class
- **`--bn-colour-border-hover` token** — 3-state border progression for toolbar buttons: rest (`--bn-colour-border` gray-200) → hover (`--bn-colour-border-hover` gray-300) → active (`--bn-colour-accent` blue-600). Adding a new interactive bordered element should follow this pattern
- **`BRISTLENOSE_PLAYER_URL` for transcript pages** — `player.js` needs to open `assets/bristlenose-player.html`, but transcript pages live in `sessions/` so the relative path is `../assets/bristlenose-player.html`. The renderer injects `BRISTLENOSE_PLAYER_URL` on transcript pages; `player.js` falls back to `'assets/bristlenose-player.html'` when the variable is absent (report pages). If you add a new page type that loads `player.js` from a subdirectory, inject this variable
- **Player→opener uses `postMessage`, not `window.opener` function calls** — Safari (and other browsers) block `window.opener` property access for `file://` URIs opened via `window.open()`. The player sends `bristlenose-timeupdate` and `bristlenose-playstate` messages via `postMessage`; `player.js` receives them with `window.addEventListener('message', ...)`. Never switch back to direct `window.opener.fn()` calls — they silently fail on `file://`
- **Analysis and codebook render both inline and standalone** — `analysis.html` and `codebook.html` sit at the output root alongside the report (use `assets/bristlenose-theme.css`). The same content also renders inline in the report's Analysis and Codebook tabs. `BRISTLENOSE_ANALYSIS` JSON is injected into both the main report and the standalone page
- **`analysis.js` avoids literal `"data-theme"` string** — dark mode tests (`test_dark_mode.py`) assert that `"data-theme"` doesn't appear in the full HTML when `color_scheme="auto"`. Since `analysis.js` is embedded inline, it uses `var THEME_ATTR = "data-" + "theme"` to construct the attribute name. Similarly, `analysis.css` uses `light-dark()` instead of `[data-theme="dark"]` selectors. If adding new dark-mode-responsive code to inline JS or embedded CSS, avoid the literal string
- **Analysis heatmap uses client-side `adjustedResidual()`** — the function exists in both Python (`metrics.py`) and JS (`analysis.js`). The JS copy is needed because heatmap cell colours are theme-responsive (OKLCH lightness direction inverts in dark mode), so residuals must be recomputed on theme toggle. Keep both implementations in sync
