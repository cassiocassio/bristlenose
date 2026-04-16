# Theme / Design System Context

## Atomic CSS architecture

Tokens → Atoms → Molecules → Organisms → Templates. All visual values via `--bn-*` custom properties in `tokens.css`, never hard-coded. `render/theme_assets.py` concatenates files in order defined by `_THEME_FILES`.

**CSS ↔ React mapping:** CSS file boundaries are being aligned to match React component boundaries. See `docs/design-react-component-library.md` (CSS ↔ React alignment section) for the full mapping table and per-round refactoring schedule. When renaming or restructuring CSS files, check the mapping table first.

## Typography

**Font:** Inter Variable loaded from Google Fonts CDN (`display=swap`). Fallback stack: `"Inter", "Segoe UI Variable", "Segoe UI", system-ui, -apple-system, sans-serif`. Both `document_shell_open.html` (static render) and `frontend/index.html` (serve mode) include preconnect + stylesheet links.

**Font-weight tokens** — four tiers, all via CSS custom properties:

| Token | Value | Usage |
|-------|-------|-------|
| `--bn-weight-normal` | 420 | Body text, descriptions, quote content, secondary labels |
| `--bn-weight-emphasis` | 490 | Headings, section titles, labels, badge text |
| `--bn-weight-starred` | 520 | Starred quote body text (pops above emphasis, below strong) |
| `--bn-weight-strong` | 700 | Page title h1, delete × glyphs, accept/deny ✓/✗, bar counts |

**Rules:** Never hardcode `font-weight` values in CSS — always use the tokens.

**Typography scale (Scale D)** — 8 stops, paired font-size + line-height tokens (line-height decreases as size increases, per Bringhurst — large letterforms provide visual anchoring, need less leading):

| Size token | Value | Line-height token | Value | Usage |
|------------|-------|-------------------|-------|-------|
| `--bn-text-micro` | 9.6px | `--bn-text-micro-lh` | 1.3 | Drag handles, pill counts |
| `--bn-text-badge` | 11.5px | `--bn-text-badge-lh` | 1.35 | Badges, compact indicators |
| `--bn-text-caption` | 12px | `--bn-text-caption-lh` | 1.4 | Timestamps, footnotes |
| `--bn-text-label` | 13px | `--bn-text-label-lh` | 1.45 | UI chrome, nav, sidebar, table cells |
| `--bn-text-body` | 15px | `--bn-text-body-lh` | 1.5 | Quote content, transcript, body text |
| `--bn-text-heading` | 18px | `--bn-text-heading-lh` | 1.3 | Section headings, card titles |
| `--bn-text-title` | 22px | `--bn-text-title-lh` | 1.25 | Page titles, h1 |
| `--bn-text-display` | 28px | `--bn-text-display-lh` | 1.2 | Dashboard hero numbers |

Desktop overrides (`tokens-desktop.css`, activated by `data-platform="desktop"`): `--bn-text-body` stays 15px (Apple callout), `--bn-text-caption` → 12px, `--bn-text-title` → 22px (Apple title 2), `--bn-text-display` → 28px (Apple title 1). Chrome defaults to `--bn-text-label` (13px) via `body { font-size: var(--bn-text-label) }` in `report.css`.

**Known limitation (Windows 10):** Static Segoe UI (pre-Variable) snaps 420→400 and 490→400 when offline (no Google Fonts). Structural cues (font-size, whitespace, borders) still carry hierarchy. Documented as acceptable degradation.

## Breakpoint tokens

Reference values in `tokens.css` — CSS `@media` can't use `var()`, so these document the canonical breakpoint values. When adding a media query, use one of these values and reference the token name in a comment.

| Token | Value | Usage |
|-------|-------|-------|
| `--bn-breakpoint-compact` | 500px | Help overlay, single-column fallback |
| `--bn-breakpoint-toolbar` | 600px | Toolbar collapse (planned) |
| `--bn-breakpoint-content` | 1100px | Transcript annotation margin layout |

## Inactive window dimming (macOS)

When the macOS app window loses focus, `.bn-window-inactive` is added to `<html>`. CSS rules in `atoms/interactive.css` dim the *chrome* (selections → grey, focus shadow → none) while keeping *content* at full contrast. This matches the macOS convention: "recede the affordances, preserve the data."

- **Tokens**: `--bn-selection-bg-inactive`, `--bn-selection-border-inactive` in `tokens.css`
- **Trigger**: Swift bridge (`BridgeHandler.setWindowActive`) on `NSWindow.didBecomeKeyNotification`/`didResignKeyNotification`. Browser fallback: `window.blur`/`window.focus` in `AppLayout.tsx`
- **Design rule**: never dim body text, images, tags, or data. Only dim interactive state indicators (selection highlight, focus shadow)

## Dark mode

Uses CSS `light-dark()` function (supported in all major browsers since mid-2024, ~87%+ global). No JS involved. The cascade:

1. **OS/browser preference** → `color-scheme: light dark` on `:root` respects `prefers-color-scheme` automatically
2. **User override** → `color_scheme` in `bristlenose.toml` (or `BRISTLENOSE_COLOR_SCHEME` env var). Values: `"auto"` (default), `"light"`, `"dark"`
3. **HTML attribute** → when config is `"light"` or `"dark"`, `render/report.py` emits `<html data-theme="light|dark">` which forces `color-scheme` via CSS selector
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
- **HTML**: `<mark class="bn-cited">` elements are always emitted by `render/transcript_pages.py` regardless of CSS visibility — the mechanism is intact
- **Design rationale**: the knocked-back opacity on non-quoted segments (0.6) plus first-occurrence section/theme labels plus span bars provide sufficient visual cues for quote extent, making the inline highlight redundant for now

### Anchor highlight animation

When navigating to a transcript page via anchor link (e.g., from coverage section), the target segment flashes yellow and fades to normal over 5 seconds. Implemented via:
- **CSS**: `@keyframes anchor-fade` in `transcript.css` — fades from `--bn-colour-highlight` to transparent
- **JS**: `_highlightAnchorTarget()` in `transcript-names.js` — on page load, checks `location.hash` for `#t-\d+` pattern and adds `.anchor-highlight` class to matching segment

## Sentiment bar charts

Two side-by-side horizontal bar charts: AI sentiment (Python-rendered) and User tags (JS-rendered by `histogram.js`). CSS grid layout with `display: contents` on bar groups to align bar edges. See `docs/design-sentiment-charts.md` for layout details, AI sentiment ordering, histogram delete button, and CSS file list.

## PersonBadge molecule

`molecules/person-badge.css` — reusable badge + name pattern for speaker identification in the session table. Combines the `.badge` atom with a named span.

- **`.bn-person-badge`** — `inline-flex`, `align-items: center`, `gap: 0.4rem`, `white-space: nowrap`. Contains a `.badge` and a `.bn-person-badge-name`
- **`.bn-person-badge .badge`** — `flex-shrink: 0` (badge never truncates)
- **`.bn-person-badge-name`** — `font-weight: var(--bn-weight-emphasis)` (490). In the moderator header, names use normal weight (no `.bn-person-badge-name` class)
- **Usage**: session table speaker cells (semibold names) and moderator header (regular weight names). The molecule is included in `_THEME_FILES` in `render/theme_assets.py`. React equivalent: `PersonBadge` component in `frontend/src/components/PersonBadge.tsx`

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
- **`.bn-interviews-link`** — folder header link. Legacy HTML: opens input folder via `file://` URI. React island: copies `file://` URI to clipboard (browsers block `file://` navigation from `http://` pages). Future: desktop app custom URL scheme (`bristlenose://open-folder?path=...`) for native Finder integration
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

Floating `[✗ | ✓]` pill bar on autocode-proposed badges, appearing on hover. Replaces old inline `✓/✗` (caused layout shift). `.badge-action-pill` container + `.badge-action-deny`/`.badge-action-accept` compartments. All delete/deny actions use `var(--bn-colour-danger)` for colour unification. See `docs/design-badge-action-pill.md` for spec, CSS classes, and rationale.

## Span bar atom & transcript annotations molecule

Vertical extent indicators (quote span bars) and right-margin annotation layout for transcript pages. Breakpoint 1100px — below that, annotations go inline and span bars are hidden. See `CSS-REFERENCE.md` for class inventory, tokens, and usage.

## JS modules

19 standalone files in `js/` — see `js/MODULES.md` for per-module API docs. Key dependency: load order matters (see Gotchas below).

## CSS component reference

Per-component CSS docs in `CSS-REFERENCE.md`. Key patterns: toolbar dual-class (`.toolbar-btn` + component class), modal base (`.bn-overlay` + `.bn-modal`), sentiment grid (`display: contents`).

## Jinja2 templates

14 HTML templates in `templates/`. All use `autoescape=False` — escape in Python with `_esc()` before passing to template. Jinja2 environment: `_jinja_env` at module level in `render/theme_assets.py`. See `CSS-REFERENCE.md` for the full template table (parameters + usage).

## Dashboard cross-tab navigation

The Project tab dashboard is fully interactive — stat cards, featured quotes, session table rows, and section/theme lists all navigate to other tabs.

- **Convention:** stat cards use `data-stat-link="tab"` or `data-stat-link="tab:anchorId"` attributes
- **Shims:** `switchToTab()`, `scrollToAnchor()`, `navigateToSession()` work in both static render (vanilla JS in `global-nav.js`) and serve mode (React Router shims in `frontend/src/shims/navigation.ts`)
- **Sticky toolbar gotcha:** two `scroll-margin-top` CSS selectors required — `.bn-tab-panel:has(.toolbar)` for static path, `.center:has(.toolbar)` for React SPA. Missing either breaks anchor navigation for one of the paths

See `docs/design-dashboard-navigation.md` for the full stat-to-target mapping, Python render helpers (`_timecode_html`, `_session_anchor`), JS navigation helper APIs, and session table render helpers.

## Off-screen rendering skip (`content-visibility`)

`.quote-group .quote-card` uses `content-visibility: auto` with `contain-intrinsic-size: auto 250px`. The browser skips layout and paint for quote cards scrolled out of the viewport, which matters when hundreds of quotes are in the DOM (no virtualization). The `auto` keyword in `contain-intrinsic-size` means the browser remembers each card's real height after first render — scroll position stays stable when scrolling back up.

**Scoped to `.quote-group` only** — featured quotes on the dashboard and other small-count contexts don't get containment.

**Gotcha:** `content-visibility: auto` applies `contain: layout style paint` implicitly. This creates a new containing block, but `.quote-group .quote-card` already has `position: relative`, so absolute-positioned action buttons (star, hide) are unaffected. If you add a new child that relies on a containing block *outside* the quote card (e.g. a portal or fixed-position overlay), it will be clipped — use a React portal mounted higher in the tree instead.

## Gotchas

- **Focus outline convention** — `:focus:not(:focus-visible) { outline: none }` in `atoms/interactive.css` suppresses the browser's default focus outline for mouse/touch clicks globally. Keyboard Tab navigation still shows the blue ring via `:focus-visible` rules on individual components. When adding a new interactive element that needs a visible keyboard focus indicator, add a `:focus-visible` rule with `outline: 2px solid var(--bn-colour-accent); outline-offset: -2px;` — the global suppressor handles the mouse case automatically. Never add per-element `:focus:not(:focus-visible)` rules (the global rule covers it). For text inputs, `:focus { border-color: var(--bn-colour-accent) }` provides a secondary cue that works for both mouse and keyboard
- **Modifier-clicks must open new tabs** — any clickable element that behaves like navigation (tabs, session links, stat cards, speaker links, dashboard links) must check `e.metaKey || e.ctrlKey || e.shiftKey` and let the default browser behaviour handle it (opens a new tab). Users don't know or care that this is a single-page app — cmd+click should always open a new tab. **Serve mode (React Router):** `<NavLink>` handles modifier-clicks natively for tabs. For other navigation, React click handlers check modifiers and `return` early (letting the `<a href>` handle it). **Static render:** vanilla JS pattern: `if (e.metaKey || e.ctrlKey || e.shiftKey) { window.open(window.location.pathname + '#' + target, '_blank'); return; }`. Already applied to: tab bar buttons (NavLink in serve / `initGlobalNav` in static), speaker links, featured quote cards, dashboard session/list links, TOC links, analysis page, and dashboard React island. When adding new click handlers for navigation-like actions, include the modifier-key guard
- **Jinja2 dict key naming**: never use Python dict method names (`items`, `keys`, `values`, `get`, `update`, `pop`) as dict keys passed to templates. Jinja2's attribute lookup resolves `group.items` as `dict.items` (the method) before `dict["items"]` (the key). Use alternative names (e.g. `entries` instead of `items`). Bracket notation (`group["items"]`) also works but is less readable
- **JS load order matters**: `view-switcher.js`, `search.js`, `tag-filter.js`, `hidden.js`, and `names.js` all load **after** `csv-export.js` in `_JS_FILES` — `view-switcher.js` writes the `currentViewMode` global defined in `csv-export.js`; `search.js` reads `currentViewMode` and exposes `_onViewModeChange()` called by `view-switcher.js`; `tag-filter.js` loads after `search.js` (reads `currentViewMode`, `_hideEmptySections`, `_hideEmptySubsections`; exposes `_applyTagFilter()`, `_onTagFilterViewChange()`, `_isTagFilterActive()`, `_updateVisibleQuoteCount()` called by `view-switcher.js`, `search.js`, and `tags.js`); `hidden.js` loads after `tag-filter.js` (reads `currentViewMode`, `_isTagFilterActive`, `_applyTagFilter`, `_hideEmptySections`; exposes `hideQuote()`, `bulkHideSelected()`, `isHidden()` called by `focus.js`); `names.js` depends on `copyToClipboard()` and `showToast()`
- **Hidden quotes vs visibility filters**: hidden quotes use `.bn-hidden` class + `style.display = 'none'`. This is fundamentally different from search/tag-filter/starred hiding (which are temporary view filters). Every visibility restore path (`_showAllQuotes`, `_showStarredOnly`, `_restoreViewMode`, `_restoreQuotesForViewMode`, `_applyTagFilter`, `_applySearchFilter`) must check for `.bn-hidden` and skip those quotes. The CSS `display: none !important` on `.bn-hidden` is defence-in-depth. **Hidden quotes always lose selection** — `hideQuote()` removes the quote from `selectedQuoteIds` and strips `.bn-selected`; unhidden quotes always come back unselected
- **Hidden badge count depends on operation order in `hideQuote()`** — `_updateBadgeForGroup()` counts hidden quotes via `querySelectorAll('blockquote.bn-hidden')`. The `.bn-hidden` class and `style.display = 'none'` must be added to the quote **before** calling `_updateBadgeForGroup`, otherwise the count is off by one. But the ghost clone must be created **before** hiding (it needs visible content and dimensions). The correct order is: snapshot siblings → record rect → clone ghost → hide quote → animate siblings → build badge → animate ghost. This ordering bug was fixed in Feb 2026; if refactoring `hideQuote()`, preserve this sequence
- **`_TRANSCRIPT_JS_FILES`** includes `badge-utils.js`, `transcript-names.js`, and `transcript-annotations.js` (after `storage.js`). `transcript-names.js` reads localStorage name edits and updates heading speaker names only (preserving code prefix: `"m1 Sarah Chen"`). Does NOT override segment speaker labels (they stay as raw codes). Separate from the report's `names.js` (which has full editing UI). `transcript-annotations.js` renders margin annotations, span bars, and handles badge deletion
- **`blockquote .timecode`** in `blockquote.css` must use `--bn-colour-accent` not `--bn-colour-muted` — the `.timecode-bracket` children handle the muting. If you add a new timecode rendering context, ensure the parent rule uses accent
- **Modal infrastructure**: `atoms/modal.css` provides shared `.bn-overlay`, `.bn-modal`, `.bn-modal-close`, `.bn-modal-footer`, `.bn-modal-actions`, `.bn-btn`, `.bn-btn-cancel`, `.bn-btn-danger`, `.bn-btn-primary` classes. `.bn-modal` has `max-width: 24rem` default — override per-modal for wider content (e.g. `.help-modal { max-width: 600px }`). `js/modal.js` provides `createModal()` factory (returns `{ show, hide, isVisible, toggle }`) + `showConfirmModal()` reusable confirmation dialog + `_modalRegistry` + `closeTopmostModal()`. Help, feedback, codebook, and histogram modals all use these — don't duplicate overlay/card/close patterns
- **Footer feedback visibility now has two paths**: legacy static path still uses `body.feedback-enabled .feedback-links` (set by `feedback.js` feature flag). React serve/export path uses `.feedback-links.feedback-links-visible` (set directly by `Footer.tsx`) and does not rely on `body.feedback-enabled`
- **Sentiment chart layout**: both AI sentiment and user-tags charts use CSS grid (`grid-template-columns: max-content 1fr max-content`) on `.sentiment-chart`. Bar groups use `display: contents` so label/bar/count participate directly in the parent grid — this is what aligns all bar left edges within each chart. Labels use `width: fit-content` + `justify-self: start` so the background hugs the text and the variable gap falls between the label's right edge and the bar. The two charts sit side-by-side in `.sentiment-row` (flexbox, `align-items: flex-start` for top-alignment). Don't change the grid structure without checking both charts
- **Surprise sentiment placement**: surprise is neutral — it renders between positive sentiments and the divider, not after negative sentiments. See `_build_sentiment_html()` in `render/sentiment.py`
- **Histogram delete-from-all**: clicking the hover `×` on a user tag label in the histogram shows a confirmation modal via `showConfirmModal()`, then removes that tag from every quote via `_deleteTagFromAllQuotes()` in `histogram.js`. This calls `persistUserTags()` which re-renders the histogram and re-applies tag filter
- **Reserved sentiment names** — `_RESERVED_SENTIMENTS` in `tags.js` blocks users from creating tags matching the 7 AI sentiment names (frustration, confusion, doubt, surprise, satisfaction, delight, confidence). Guard at both commit time (toast + skip) and suggestion filter (defence-in-depth). Case-insensitive comparison
- **Case-insensitive tag deduplication** — `closeTagInput()` uses `.some(t.toLowerCase() === valLower)` not `indexOf(val)`. If all target quotes already have the tag (any casing), shows toast "Tags are not case-sensitive". This prevents ghost duplicates like "UX" and "ux" on the same quote
- **Bulk tag visual feedback** — when committing a tag to multiple quotes, each new badge gets `.badge-bulk-flash` (0.8s blue ring pulse). A toast ("Tag 'Foo' applied to N quotes") only appears when some tagged quotes are off-screen — if all are visible, the flash alone is sufficient
- **`tagFocusedQuote()` selection guard** — pressing `t` only triggers bulk mode if the focused quote is in `selectedQuoteIds`. If focus is on a non-selected quote, `t` tags only that single quote. Matches the `+` click handler pattern in `tags.js`
- **IIFE scoping and inline onclick**: all report JS is wrapped in `(function() { ... })()` by `render/report.py`. Functions defined inside are NOT accessible from inline `onclick` HTML attributes. Wire click handlers via `addEventListener` from JS instead. Footer links use `role="button" tabindex="0"` (no `href`) for keyboard accessibility
- **Stale HTML files cause debugging confusion** — if a previous render created a differently-named file (e.g. from a bug), the old file remains on disk. Always check which HTML file you're viewing matches the timestamp of your last render
- **Codebook page sits at output root** — `codebook.html` is at the same level as the report (not in `sessions/` or `assets/`), so it uses `assets/bristlenose-theme.css` (no `../` prefix). The `_footer_html()` helper uses `assets/` paths which work correctly for root-level pages
- **Tag-filter rebuilds on every open** — `_buildTagFilterMenu()` is called each time the dropdown opens because user tags are dynamic. This also means codebook colour/group changes from the codebook window are picked up automatically without a dedicated `storage` event listener. Don't cache the menu DOM
- **Tag-filter codebook integration** — tags are grouped into tinted `.tag-filter-group` containers using `var(--bn-group-{set})` tokens (same as codebook panel columns). Ungrouped tags appear first as flat items with no wrapper. Search matches both tag names and group names (via `data-group-name` attribute). Uses `createReadOnlyBadge()` from `badge-utils.js` (no delete button) — don't switch to `createUserTagBadge()` which includes a `×` button
- **Search threshold is 8 tags** — the tag-filter search input only appears when there are 8+ tags. This is a UX heuristic hardcoded in `_buildTagFilterMenu()`. If changing, update the MODULES.md entry too
- **Toolbar button dual-class pattern** — tag filter and view switcher buttons use dual classes (`toolbar-btn tag-filter-btn`, `toolbar-btn view-switcher-btn`). The shared `.toolbar-btn` provides round-rect styling; the component-specific class allows dropdown-specific overrides. Don't remove either class
- **`--bn-colour-border-hover` token** — 3-state border progression for toolbar buttons: rest (`--bn-colour-border` gray-200) → hover (`--bn-colour-border-hover` gray-300) → active (`--bn-colour-accent` blue-600). Adding a new interactive bordered element should follow this pattern
- **Pencil icon convention for inline editing** — pencil affordances (✎) hide when the field enters edit mode, reappear on commit/cancel. The outline/highlight on the active field signals edit state; the pencil is redundant during editing and adds visual noise near the cursor. This follows the Microsoft 365 / Notion convention. Implementation: conditionally render the pencil button with `{!isEditing && <button ...>}` in React. Applied to: session grid name editing (`.bn-name-pencil` in `person-badge.css`). When adding new pencil affordances, follow this pattern
- **`BRISTLENOSE_PLAYER_URL` for transcript pages** — `player.js` needs to open `assets/bristlenose-player.html`, but transcript pages live in `sessions/` so the relative path is `../assets/bristlenose-player.html`. The renderer injects `BRISTLENOSE_PLAYER_URL` on transcript pages; `player.js` falls back to `'assets/bristlenose-player.html'` when the variable is absent (report pages). If you add a new page type that loads `player.js` from a subdirectory, inject this variable
- **Player→opener uses `postMessage`, not `window.opener` function calls** — Safari (and other browsers) block `window.opener` property access for `file://` URIs opened via `window.open()`. The player sends `bristlenose-timeupdate` and `bristlenose-playstate` messages via `postMessage`; `player.js` receives them with `window.addEventListener('message', ...)`. Never switch back to direct `window.opener.fn()` calls — they silently fail on `file://`
- **Analysis and codebook render both inline and standalone** — `analysis.html` and `codebook.html` sit at the output root alongside the report (use `assets/bristlenose-theme.css`). The same content also renders inline in the report's Analysis and Codebook tabs. `BRISTLENOSE_ANALYSIS` JSON is injected into both the main report and the standalone page
- **`analysis.js` avoids literal `"data-theme"` string** — dark mode tests (`test_dark_mode.py`) assert that `"data-theme"` doesn't appear in the full HTML when `color_scheme="auto"`. Since `analysis.js` is embedded inline, it uses `var THEME_ATTR = "data-" + "theme"` to construct the attribute name. Similarly, `analysis.css` uses `light-dark()` instead of `[data-theme="dark"]` selectors. If adding new dark-mode-responsive code to inline JS or embedded CSS, avoid the literal string
- **Analysis heatmap uses client-side `adjustedResidual()`** — the function exists in both Python (`metrics.py`) and JS (`analysis.js`). The JS copy is needed because heatmap cell colours are theme-responsive (OKLCH lightness direction inverts in dark mode), so residuals must be recomputed on theme toggle. Keep both implementations in sync
- **Renderer overlay (dev-only)** — `_build_renderer_overlay_html()` in `server/app.py` injects a floating toggle (press **D** or click the button) that colour-codes report regions by renderer origin: blue outline+wash for Jinja2, green for React islands, amber for Vanilla JS. Uses `::after` pseudo-elements with `pointer-events: none` for the translucent wash, plus `outline` for an always-visible border. Key CSS patterns: (1) Jinja2 containers that hold React/Vanilla JS mount points suppress their own `::after` via `:not(:has(#bn-...))` so the child colour shows through; (2) elements *inside* React mount points (e.g. React-rendered `<section>`) get their `::after` cancelled with `display: none` to prevent blue bleed; (3) the `body.bn-dev-overlay` class gates all overlay styles. If you add a new React island or Vanilla JS mount point, add its ID to the relevant CSS selector groups in `_build_renderer_overlay_html()`
- **`<!-- bn-session-table -->` markers** — `render/report.py` wraps the Jinja2 session table (inside `.bn-session-grid`) with `<!-- bn-session-table -->` / `<!-- /bn-session-table -->` comment markers. The serve command's `serve_report_html()` uses `re.sub` to replace everything between these markers with the React mount point `<div id="bn-sessions-table-root">`. This avoids re-running the full render pipeline with `serve_mode=True`. If you add new React islands that replace Jinja2 content, follow the same marker pattern
- **`serve_mode` vs runtime replacement** — `render/report.py` has a `serve_mode` param that renders React mount points instead of Jinja2 content. But `bristlenose serve` doesn't call `render_html()` — it reads the existing HTML (rendered with `serve_mode=False`) and does string replacement at serve time. Running `bristlenose render` before `bristlenose serve` is expected workflow — the markers make the replacement work. Don't assume #bn-sessions-table-root exists in the static HTML file on disk
- **Delete circles are red, not grey** — `badge-ai::after` and `.badge-user .badge-delete` use `var(--bn-colour-danger)` (red), not `var(--bn-colour-muted)` (grey). Changed to unify delete/deny colour across all badge types (sentiment delete, user tag delete, proposed badge deny pill). If adding a new deletable badge variant, use `--bn-colour-danger` for the `×`
- **`--bn-colour-danger` and `--bn-colour-success` are not in `tokens.css`** — badge CSS uses `var(--bn-colour-danger, #dc2626)` and `var(--bn-colour-success, #16a34a)` with hardcoded fallbacks. The tokens file defines `--bn-colour-negative` instead. The fallback values work but don't adapt in dark mode (delete circles stay `#dc2626` on dark backgrounds). The pill's dark mode overrides in `badge.css` handle this for the pill only. Future: add `--bn-colour-danger` / `--bn-colour-success` as proper `light-dark()` tokens
- **CSS specificity vs source order in concatenated theme** — `render/theme_assets.py` concatenates CSS files in `_THEME_FILES` order (tokens → atoms → molecules → organisms → templates). At **equal specificity**, the later file wins. `atoms/interactive.css` loads before `organisms/blockquote.css`, so `blockquote.bn-selected` (0,1,1) lost to `blockquote.quote-card` (0,1,1) even though both set `background`. Fix: interactive state selectors use `blockquote.quote-card.bn-selected` (0,2,1) to win regardless of source order. When adding new state classes that override organism-level base styles, **always qualify with the base class** to avoid source-order traps
- **`Element.closest()` only matches compound selectors** — `closest()` walks **up** the DOM tree and tests each ancestor against the selector. It cannot match descendant combinators (`.parent .child`), child combinators (`.parent > .child`), or any selector that implies a structural relationship between two elements. Use compound selectors only: `target.closest("blockquote.quote-card")` works; `target.closest(".quote-group blockquote")` silently returns `null` even when the element is inside a `.quote-group`. This caused the background-click handler to miss all quote clicks and clear selection on every click
- **Font-weight tokens** — four tiers: `var(--bn-weight-normal)` (420), `var(--bn-weight-emphasis)` (490), `var(--bn-weight-starred)` (520), `var(--bn-weight-strong)` (700). Starred quotes get 520 to pop above headings/labels (490) without reaching bold (700). Inter variable font loaded from Google Fonts (`wght@400..700`) in `document_shell_open.html` and `frontend/index.html`. Static fonts (Win 10 Segoe UI) degrade 420→400 and 490→400 — acceptable
