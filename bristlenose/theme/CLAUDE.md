# Theme / Design System Context

## Atomic CSS architecture

Tokens → Atoms → Molecules → Organisms → Templates. All visual values via `--bn-*` custom properties in `tokens.css`, never hard-coded. `render_html.py` concatenates files in order defined by `_THEME_FILES`.

**CSS ↔ React mapping:** CSS file boundaries are being aligned to match React component boundaries. See `docs/design-react-component-library.md` (CSS ↔ React alignment section) for the full mapping table and per-round refactoring schedule. When renaming or restructuring CSS files, check the mapping table first.

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

**Logo + appearance toggle gotcha**: `<picture>` `<source>` media queries only respond to the OS-level `prefers-color-scheme`, not the page-level `data-theme`/`colorScheme` override set by the Settings toggle. Setting `img.src` inside a `<picture>` has no effect when a matching `<source>` exists. Workaround in `settings.js` (`_updateLogo`): physically removes the `<source>` element when the user forces light/dark, stashes it, and restores it when switching back to auto. Messy but unavoidable without duplicating the logo as two `<img>` elements toggled by CSS classes.

**Logo click**: wrapped in `<a class="report-logo-link" href="#project" onclick="switchToTab('project');return false;">`. Clicking the fish logo navigates to the Project tab (home). CSS in `atoms/logo.css`: `.report-logo-link` removes underline and sets `line-height: 0` to prevent extra vertical space around the image.

### No JS theme toggle

Dark mode is CSS-only. No localStorage, no toggle button, no JS involved.

## Template CSS files

Template-level CSS in `templates/`: `report.css` (main report layout), `transcript.css` (per-session transcript pages — back button, segment layout, meta styling, citation highlight, anchor highlight animation), `print.css` (print overrides, hides interactive elements — includes `.feedback-links`, `.feedback-overlay`, `.footer-logo-picture`). Quote attribution links styled via `.speaker-link` in `organisms/blockquote.css` (inherits muted colour from `.speaker`, accent on hover). Dashboard stat cards, featured quotes, and session table rows all use `var(--bn-colour-hover)` for interactive hover — see "Dashboard cross-tab navigation" section below.

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

## PersonBadge molecule

`molecules/person-badge.css` — reusable badge + name pattern for speaker identification in the session table. Combines the `.badge` atom with a named span.

- **`.bn-person-badge`** — `inline-flex`, `align-items: center`, `gap: 0.4rem`, `white-space: nowrap`. Contains a `.badge` and a `.bn-person-badge-name`
- **`.bn-person-badge .badge`** — `flex-shrink: 0` (badge never truncates)
- **`.bn-person-badge-name`** — `font-weight: 600` (semibold). In the moderator header, names use regular weight (no `.bn-person-badge-name` class)
- **Usage**: session table speaker cells (semibold names) and moderator header (regular weight names). The molecule is included in `_THEME_FILES` in `render_html.py`. React equivalent: `PersonBadge` component in `frontend/src/components/PersonBadge.tsx`

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
- **`.bn-sparkline` / `.bn-sparkline-bar`** — per-session sentiment mini-bar chart. Container height: 54px (matches thumbnail) so baselines align. Bar heights set inline, colours via `--bn-sentiment-{name}` tokens
- **`.bn-interviews-link`** — folder header link (opens input folder via `file://` URI)
- **`.bn-folder-icon`** — inline SVG folder icon in header link
- **Clickable rows** — `tbody tr[data-session]` gets `cursor: pointer` and `var(--bn-colour-hover)` on hover (in `report.css`). JS click handler in `global-nav.js` calls `navigateToSession()`. Dashboard table rows (`_initGlobalNav`) and Sessions tab rows (`_initSessionDrillDown`) both use this pattern. Clicks on `<a>` elements within rows (filenames, session links) are not intercepted

## Tooltip pattern (system-wide)

All custom content tooltips use a consistent pattern: **soft surface, 300ms hover delay, float-down-from-above animation**. This applies to rationale tooltips on proposed badges, analysis cell tooltips, and any future hover-reveal content.

### Spec

| Property | Value | Token/Note |
|---|---|---|
| background | `var(--bn-colour-bg)` | page-coloured — adapts to light/dark |
| color | `var(--bn-colour-text)` | primary text colour |
| border | `1px solid var(--bn-colour-border)` | standard border |
| border-radius | `var(--bn-radius-md)` | 6px |
| box-shadow | `0 4px 16px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04)` | subtle depth |
| hover delay | 300ms in, 0ms out | `transition-delay: 0.3s` on hover, `0s` on base |
| animation | `translateY(-8px)` → `translateY(0)` + opacity 0→1 | float down + fade |
| duration | `0.2s ease-out` | decelerates into final position |
| exit | instant | no delay, CSS transition reversal |

### Two implementations

1. **CSS-only** (`.has-tooltip .tooltip` in `molecules/autocode-report.css`) — used for rationale tooltips on proposed badges and in the AutoCode report modal. Uses `transition-delay` for the 300ms hover delay.
2. **JS-controlled** (`CellTooltip` in `frontend/src/islands/AnalysisPage.tsx`) — used for analysis heatmap cell tooltips. Uses `setTimeout(300)` in `handleCellEnter` for the delay, CSS `@keyframes cell-tooltip-in` for the animation.

### When to use custom tooltips vs native `title`

- **Custom tooltip**: for content — rationale text, quote previews, metric breakdowns. Use when you need to control timing, styling, and multi-line layout
- **Native `title` attribute**: for simple one-word icon labels (toolbar buttons, action hints like "Accept", "Deny"). Leave these as browser defaults

### Design exploration

`docs/mockups/tooltip-gallery.html` — 6 variants (A–F) with interactive comparison and dark mode toggle. Variant D was chosen.

## Badge action pill (proposed badges)

Floating `[✗ | ✓]` pill bar on autocode-proposed badges. Replaces the old inline `✓/✗` approach that caused layout shift (badge width grew on hover, pushing the `+` button).

### Design decision

7 variations explored in `docs/mockups/mockup-proposed-badge-actions.html` (A–G). **Var G chosen** — combines E's pill concept, D's 16px hit targets, and A's positioning at the existing delete-circle location.

### Spec

| Property | Value | Notes |
|---|---|---|
| position (vertical) | `top: calc(-0.3rem - 1px)` | Same as delete `×` circles |
| position (horizontal) | `right: calc(-0.3rem - 1px - 1rem)` | `✗` aligns with delete `×`, `✓` hangs right |
| compartment size | `1rem × 1rem` (16px) | Larger than delete circles (14.5px) for better Fitts' law |
| border-radius | `8px` | Pill shape |
| shadow | `0 1px 4px rgba(0,0,0,0.16), 0 0 1px rgba(0,0,0,0.06)` | Matches delete circles |
| `✗` colour | `var(--bn-colour-danger)` / `#fef2f2` bg on hover | Same red as all delete/deny actions |
| `✓` colour | `var(--bn-colour-success)` / `#dcfce7` bg on hover | Green accept |
| divider | `1px solid var(--bn-colour-border)` | Between compartments |

### CSS classes

- **`.badge-action-pill`** — absolute-positioned pill container, `opacity: 0` → `1` on `.badge-proposed:hover`
- **`.badge-action-deny`** — left compartment (`✗`), red
- **`.badge-action-accept`** — right compartment (`✓`), green, `border-left` divider

### React

`Badge.tsx` proposed variant: DOM order is deny-then-accept (left-to-right in pill). Click handlers via `onAccept` / `onDeny` props.

### Colour unification

All delete/deny actions across badge types use `var(--bn-colour-danger)` (red):
- Sentiment badge `::after` delete circle
- User tag `.badge-delete` circle
- Proposed badge pill `.badge-action-deny` compartment

This replaced the previous grey `var(--bn-colour-muted)` on delete circles. Rationale: delete IS deny ("I don't want this tag"), so the colour should be consistent.

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
| `content_section.html` | `heading`, `item_type`, `groups` | Report (sections + themes). `h2` has `id="{{ heading | lower }}"` for anchor navigation from dashboard |
| `sentiment_chart.html` | `max_count`, `pos_bars`, `surprise_bar`, `neg_bars` | Report |
| `friction_points.html` | `groups` (list of dicts with `pid`, `entries`) | Report |
| `user_journeys.html` | `rows` (list of dicts) | Report |
| `coverage.html` | `summary`, `pct_omitted`, `sessions` | Report |
| `player.html` | (none — static) | Separate player file |
| `analysis.html` | (none — structural only, JS populates) | Analysis page. `h2` has `id="section-x-sentiment"` for anchor navigation from dashboard |

## Dashboard cross-tab navigation

The Project tab dashboard is fully interactive — stat cards, featured quotes, session table rows, and section/theme lists all navigate to other tabs.

### `data-stat-link` convention

Stat cards use `data-stat-link="tab"` or `data-stat-link="tab:anchorId"` attributes. JS in `global-nav.js` handles the click: calls `switchToTab(tab)` then `scrollToAnchor(anchorId)` if present. Current mappings:

| Stat | Target |
|------|--------|
| Audio/video duration | `sessions` |
| Word count | `sessions` |
| Quote count | `quotes` |
| Section count | `quotes:sections` |
| Theme count | `quotes:themes` |
| AI tag count | `analysis:section-x-sentiment` |
| User tag count | `codebook` |

The anchor IDs `sections` and `themes` come from `content_section.html` (`id="{{ heading | lower }}"`). The `section-x-sentiment` anchor is on the h2 in `analysis.html`.

### `--bn-colour-hover` token

Interactive hover background for clickable rows and cards: `light-dark(#e8f0fe, #1e293b)`. Used by stat cards, featured quotes, and session table rows. Dark mode value is a dark blue-grey so white text stays readable (not a light blue which would require black text).

### Featured quote attribution

Featured quote footer shows a speaker code lozenge (`<a class="badge speaker-link">`) instead of the display name. The lozenge links to the session transcript via `data-nav-session` / `data-nav-anchor`. Clicking the card body tries the video player first (`seekTo`), falls back to transcript navigation.

### Python render helpers

Two helpers in `render_html.py` reduce duplication across quote rendering:

- **`_timecode_html(quote, video_map)`** — returns `<a class="timecode" ...>` if video exists for the participant, otherwise `<span class="timecode">`. Used by `_format_quote_html()` and `_render_featured_quote()`
- **`_session_anchor(quote)`** — returns `(pid_esc, sid_esc, anchor)` tuple for session navigation attributes. The anchor format is `t-{sid}-{start_seconds}`

### JS navigation helpers (global-nav.js)

- **`scrollToAnchor(anchorId, opts)`** — rAF + `getElementById` + `scrollIntoView`. Options: `block` (`'start'`/`'center'`), `highlight` (adds `anchor-highlight` class for yellow flash)
- **`navigateToSession(sid, anchorId)`** — `switchToTab('sessions')` + `_showSession(sid)` + optional `scrollToAnchor` with highlight. Used by speaker links, featured quotes, and dashboard table rows
- **Sticky toolbar scroll offset** — `--bn-toolbar-height` CSS variable (default `3rem` in `tokens.css`, measured at runtime on first tab switch in `global-nav.js`). `toolbar.css` applies `scroll-margin-top` to `h2[id]`/`h3[id]` inside any `.bn-tab-panel:has(.toolbar)`. This prevents anchor links from scrolling headings behind the sticky toolbar. If the toolbar height changes (new buttons, typography), the JS measurement auto-adapts

## Gotchas

- **Jinja2 dict key naming**: never use Python dict method names (`items`, `keys`, `values`, `get`, `update`, `pop`) as dict keys passed to templates. Jinja2's attribute lookup resolves `group.items` as `dict.items` (the method) before `dict["items"]` (the key). Use alternative names (e.g. `entries` instead of `items`). Bracket notation (`group["items"]`) also works but is less readable
- **JS load order matters**: `view-switcher.js`, `search.js`, `tag-filter.js`, `hidden.js`, and `names.js` all load **after** `csv-export.js` in `_JS_FILES` — `view-switcher.js` writes the `currentViewMode` global defined in `csv-export.js`; `search.js` reads `currentViewMode` and exposes `_onViewModeChange()` called by `view-switcher.js`; `tag-filter.js` loads after `search.js` (reads `currentViewMode`, `_hideEmptySections`, `_hideEmptySubsections`; exposes `_applyTagFilter()`, `_onTagFilterViewChange()`, `_isTagFilterActive()`, `_updateVisibleQuoteCount()` called by `view-switcher.js`, `search.js`, and `tags.js`); `hidden.js` loads after `tag-filter.js` (reads `currentViewMode`, `_isTagFilterActive`, `_applyTagFilter`, `_hideEmptySections`; exposes `hideQuote()`, `bulkHideSelected()`, `isHidden()` called by `focus.js`); `names.js` depends on `copyToClipboard()` and `showToast()`
- **Hidden quotes vs visibility filters**: hidden quotes use `.bn-hidden` class + `style.display = 'none'`. This is fundamentally different from search/tag-filter/starred hiding (which are temporary view filters). Every visibility restore path (`_showAllQuotes`, `_showStarredOnly`, `_restoreViewMode`, `_restoreQuotesForViewMode`, `_applyTagFilter`, `_applySearchFilter`) must check for `.bn-hidden` and skip those quotes. The CSS `display: none !important` on `.bn-hidden` is defence-in-depth. **Hidden quotes always lose selection** — `hideQuote()` removes the quote from `selectedQuoteIds` and strips `.bn-selected`; unhidden quotes always come back unselected
- **Hidden badge count depends on operation order in `hideQuote()`** — `_updateBadgeForGroup()` counts hidden quotes via `querySelectorAll('blockquote.bn-hidden')`. The `.bn-hidden` class and `style.display = 'none'` must be added to the quote **before** calling `_updateBadgeForGroup`, otherwise the count is off by one. But the ghost clone must be created **before** hiding (it needs visible content and dimensions). The correct order is: snapshot siblings → record rect → clone ghost → hide quote → animate siblings → build badge → animate ghost. This ordering bug was fixed in Feb 2026; if refactoring `hideQuote()`, preserve this sequence
- **`_TRANSCRIPT_JS_FILES`** includes `badge-utils.js`, `transcript-names.js`, and `transcript-annotations.js` (after `storage.js`). `transcript-names.js` reads localStorage name edits and updates heading speaker names only (preserving code prefix: `"m1 Sarah Chen"`). Does NOT override segment speaker labels (they stay as raw codes). Separate from the report's `names.js` (which has full editing UI). `transcript-annotations.js` renders margin annotations, span bars, and handles badge deletion
- **`blockquote .timecode`** in `blockquote.css` must use `--bn-colour-accent` not `--bn-colour-muted` — the `.timecode-bracket` children handle the muting. If you add a new timecode rendering context, ensure the parent rule uses accent
- **Modal infrastructure**: `atoms/modal.css` provides shared `.bn-overlay`, `.bn-modal`, `.bn-modal-close`, `.bn-modal-footer`, `.bn-modal-actions`, `.bn-btn`, `.bn-btn-cancel`, `.bn-btn-danger`, `.bn-btn-primary` classes. `.bn-modal` has `max-width: 24rem` default — override per-modal for wider content (e.g. `.help-modal { max-width: 600px }`). `js/modal.js` provides `createModal()` factory (returns `{ show, hide, isVisible, toggle }`) + `showConfirmModal()` reusable confirmation dialog + `_modalRegistry` + `closeTopmostModal()`. Help, feedback, codebook, and histogram modals all use these — don't duplicate overlay/card/close patterns
- **Sentiment chart layout**: both AI sentiment and user-tags charts use CSS grid (`grid-template-columns: max-content 1fr max-content`) on `.sentiment-chart`. Bar groups use `display: contents` so label/bar/count participate directly in the parent grid — this is what aligns all bar left edges within each chart. Labels use `width: fit-content` + `justify-self: start` so the background hugs the text and the variable gap falls between the label's right edge and the bar. The two charts sit side-by-side in `.sentiment-row` (flexbox, `align-items: flex-start` for top-alignment). Don't change the grid structure without checking both charts
- **Surprise sentiment placement**: surprise is neutral — it renders between positive sentiments and the divider, not after negative sentiments. See `_build_sentiment_html()` in `render_html.py`
- **Histogram delete-from-all**: clicking the hover `×` on a user tag label in the histogram shows a confirmation modal via `showConfirmModal()`, then removes that tag from every quote via `_deleteTagFromAllQuotes()` in `histogram.js`. This calls `persistUserTags()` which re-renders the histogram and re-applies tag filter
- **Reserved sentiment names** — `_RESERVED_SENTIMENTS` in `tags.js` blocks users from creating tags matching the 7 AI sentiment names (frustration, confusion, doubt, surprise, satisfaction, delight, confidence). Guard at both commit time (toast + skip) and suggestion filter (defence-in-depth). Case-insensitive comparison
- **Case-insensitive tag deduplication** — `closeTagInput()` uses `.some(t.toLowerCase() === valLower)` not `indexOf(val)`. If all target quotes already have the tag (any casing), shows toast "Tags are not case-sensitive". This prevents ghost duplicates like "UX" and "ux" on the same quote
- **Bulk tag visual feedback** — when committing a tag to multiple quotes, each new badge gets `.badge-bulk-flash` (0.8s blue ring pulse). A toast ("Tag 'Foo' applied to N quotes") only appears when some tagged quotes are off-screen — if all are visible, the flash alone is sufficient
- **`tagFocusedQuote()` selection guard** — pressing `t` only triggers bulk mode if the focused quote is in `selectedQuoteIds`. If focus is on a non-selected quote, `t` tags only that single quote. Matches the `+` click handler pattern in `tags.js`
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
- **Renderer overlay (dev-only)** — `_build_renderer_overlay_html()` in `server/app.py` injects a floating toggle (press **D** or click the button) that colour-codes report regions by renderer origin: blue outline+wash for Jinja2, green for React islands, amber for Vanilla JS. Uses `::after` pseudo-elements with `pointer-events: none` for the translucent wash, plus `outline` for an always-visible border. Key CSS patterns: (1) Jinja2 containers that hold React/Vanilla JS mount points suppress their own `::after` via `:not(:has(#bn-...))` so the child colour shows through; (2) elements *inside* React mount points (e.g. React-rendered `<section>`) get their `::after` cancelled with `display: none` to prevent blue bleed; (3) the `body.bn-dev-overlay` class gates all overlay styles. If you add a new React island or Vanilla JS mount point, add its ID to the relevant CSS selector groups in `_build_renderer_overlay_html()`
- **`<!-- bn-session-table -->` markers** — `render_html.py` wraps the Jinja2 session table (inside `.bn-session-grid`) with `<!-- bn-session-table -->` / `<!-- /bn-session-table -->` comment markers. The serve command's `serve_report_html()` uses `re.sub` to replace everything between these markers with the React mount point `<div id="bn-sessions-table-root">`. This avoids re-running the full render pipeline with `serve_mode=True`. If you add new React islands that replace Jinja2 content, follow the same marker pattern
- **`serve_mode` vs runtime replacement** — `render_html.py` has a `serve_mode` param that renders React mount points instead of Jinja2 content. But `bristlenose serve` doesn't call `render_html()` — it reads the existing HTML (rendered with `serve_mode=False`) and does string replacement at serve time. Running `bristlenose render` before `bristlenose serve` is expected workflow — the markers make the replacement work. Don't assume #bn-sessions-table-root exists in the static HTML file on disk
- **Delete circles are red, not grey** — `badge-ai::after` and `.badge-user .badge-delete` use `var(--bn-colour-danger)` (red), not `var(--bn-colour-muted)` (grey). Changed to unify delete/deny colour across all badge types (sentiment delete, user tag delete, proposed badge deny pill). If adding a new deletable badge variant, use `--bn-colour-danger` for the `×`
