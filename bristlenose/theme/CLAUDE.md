# Theme / Design System Context

## A theme CSS edit is also a desktop edit

`desktop/Bristlenose/Bristlenose/WelcomeTimelineCSS.swift` embeds a generated copy of
the theme CSS for the Mac welcome screen. After changing anything under
`bristlenose/theme/`, run `.venv/bin/python scripts/gen-welcome-timeline.py` and commit
the regenerated Swift file with the CSS. `tests/test_welcome_timeline.py` catches a
stale copy, but only in the full suite: on 15 Oct 2026 an icon commit that ran only the
theme-named tests turned `main` red until another session regenerated it (`235a7751`).

## Atomic CSS architecture

Tokens → Atoms → Molecules → Organisms → Templates. All visual values via `--bn-*` custom properties in `tokens.css`, never hard-coded. `render/theme_assets.py` concatenates files in order defined by `_THEME_FILES`.

**CSS ↔ React mapping:** CSS file boundaries are being aligned to match React component boundaries. See `docs/design-react-component-library.md` (CSS ↔ React alignment section) for the full mapping table and per-round refactoring schedule. When renaming or restructuring CSS files, check the mapping table first.

## Typography

**Font:** Inter Variable loaded from Google Fonts CDN (`display=swap`). Fallback stack: `"Inter", "Segoe UI Variable", "Segoe UI", system-ui, -apple-system, sans-serif`. Both `document_shell_open.html` (static render) and `frontend/index.html` (serve mode) include preconnect + stylesheet links.

**Font-weight tokens** — six body tiers plus three monospace values, all via CSS custom properties:

| Token | Value | Usage |
|-------|-------|-------|
| `--bn-weight-light` | 370 | Subordinate text — `.toc-link`, `.session-entry-name`. **Below the web's loaded axis; see Gotchas** |
| `--bn-weight-normal` | 420 | Body text, descriptions, quote content, secondary labels |
| `--bn-weight-emphasis` | 490 | Headings, section titles, labels |
| `--bn-weight-starred` | 520 | Starred quote body text (pops above emphasis, below strong) |
| `--bn-weight-semibold` | 600 | A chosen word in a text-only switch (person picker scope) |
| `--bn-weight-strong` | 700 | Page title h1, delete × glyphs, accept/deny ✓/✗, bar counts |
| `--bn-weight-mono` | 400 | Every monospace role at rest. Declared on footer keycaps and the codebook picker version; timecodes, speaker codes and paths reach 400 because `body` sets no `font-weight` |
| `--bn-weight-mono-tag` | 460 / 400 | Every tag (`.badge`): 460 in the light appearance, 400 in dark (set by `[data-theme="dark"]` and `prefers-color-scheme`, since `font-weight` cannot follow `light-dark()`) |
| `--bn-weight-mono-emphasis` | 560 | The one mono step up: the Screens path that names the screen. Bold in Menlo and Consolas |

**Monospace weights stay in two bands.** 400–490 is Regular in Menlo, Consolas and Cascadia Mono and varies only in SF Mono, so SF Mono-only nuance lives there; 560 is the emphasis because Windows matches the nearest weight and Consolas turns Bold only at 550. Don't put a mono weight at 500 (Cascadia jumps to SemiBold) or 500–549 (Bold in Menlo, Regular in Consolas). Measurements: `docs/design-monospace-roles.md` §6.

**Rules:** Never hardcode `font-weight` values in CSS — always use the tokens.

**Monospace: read the ground truth before measuring anything.** `docs/design-monospace-roles.md` §6 records, per platform and browser, which face each mono stack reaches and what every weight draws there, measured 15 Oct 2026 on macOS (WebKit, sandboxed WKWebView, Chromium) and Windows 10/11 (Edge), with the five traps that faked results on the way (`experiments/monospace-audit/ground-truth.json`, probes alongside). The two facts people re-derive wrongly: "SF Mono" by name exists only on Macs with Apple's developer download, so the developer's view is not the researcher's; and 400–490 is the only band that stays Regular on every non-SF face (Windows matches the nearest weight, so Consolas turns Bold at 550, not 501).

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

Desktop overrides (`tokens-desktop.css`, activated by `data-platform="desktop"`) are calibrated to the live macOS AppKit ladder via the Type Parity Inspector: `--bn-text-body` 15px (macOS title3), `--bn-text-caption` 12px (callout), `--bn-text-title` 22px (title1), `--bn-text-display` 26px (largeTitle), with line-heights set to Apple's absolute leadings and a `--bn-track-*` tracking family (≈0 across the range). Chrome defaults to `--bn-text-label` (13px) via `body { font-size: var(--bn-text-label) }` in `report.css`. The full selector is `[data-platform="desktop"]:not([data-typography="inter"])` — the macOS **Appearance ▸ Typography** picker can emit `data-typography="inter"` (via `BRISTLENOSE_TYPOGRAPHY`, rendered by `app.py._html_root_attrs`) to opt the desktop app back to the web/Inter scale. SF Pro is Apple-licensed, so web/CLI never set `data-platform` and always get Inter.

**⚠ The token names do NOT match the macOS style names — `--bn-text-body` is title3, not AppKit `.body`.** On desktop the mapping is `--bn-text-body` = 15px = macOS **title3** = the *participant* voice (quotes, transcript), while AppKit's own `.body` = 13px = **`--bn-text-label`** = the *app* voice (our chrome). So when porting a SwiftUI view's type into CSS, a `Text(...).font(.body)` becomes `--bn-text-label`, **not** `--bn-text-body` — reaching for the same-sounding token silently renders chrome a whole stop too large. Same trap in reverse for `.title3`, which *is* `--bn-text-body`. The other three chrome stops: `.subheadline`/11 → `--bn-text-badge`, `.callout`/12 → `--bn-text-caption`, `.caption2`/10 → `--bn-text-micro`.

**Corollary — don't hardcode px in anything that also renders on desktop.** The web (Inter) and desktop (SF Pro) scales differ at several stops (micro, badge, body line-height), so a literal size that looks right in a browser is off-scale in the app. Copy the `--bn-text-*` / `--bn-track-*` block verbatim from `tokens-desktop.css` and diff it mechanically. The 2 Aug 2026 welcome-mockup incident: [full entry](gotchas.md#type-colour-and-tokens).

**Known limitation (Windows 10):** Static Segoe UI (pre-Variable) snaps 420→400 and 490→400 when offline (no Google Fonts). Structural cues (font-size, whitespace, borders) still carry hierarchy. Documented as acceptable degradation.

## Breakpoint tokens

Reference values in `tokens.css` — CSS `@media` can't use `var()`, so these document the canonical breakpoint values. When adding a media query, use one of these values and reference the token name in a comment.

| Token | Value | Usage |
|-------|-------|-------|
| `--bn-breakpoint-compact` | 500px | Help overlay, single-column fallback |
| `--bn-breakpoint-toolbar` | 600px | Toolbar collapse (planned) |
| `--bn-breakpoint-content` | 1100px | Transcript annotation margin layout |

**Complex data tables are custom by nature — do not build a generic responsive-table system** (decided 6 Aug 2026): every responsive decision is a judgement about the table's own content, so the next complex table carries its own organism, measured thresholds and degradation ladder. Share the atoms and the reasoning pattern, never the numbers. **The Sessions grid is a deliberate exception**: its seven bespoke container-query values in `organisms/sessions-grid.css` are not folded into the breakpoint scale above (tune them in `docs/mockups/sessions-grid-playground.html`). The five per-table judgements and the reasoning: [full entries](gotchas.md#layout-and-rendering-mechanics).

## Inactive window dimming (macOS)

When the macOS app window loses focus, `.bn-window-inactive` is added to `<html>`. CSS rules in `atoms/interactive.css` dim the *chrome* (selections → grey, focus shadow → none) while keeping *content* at full contrast. This matches the macOS convention: "recede the affordances, preserve the data."

- **Tokens**: `--bn-selection-bg-inactive`, `--bn-selection-border-inactive` in the palette files (`colors/palette-*.css` — part of the colour contract, see `colors/_contract.css`)
- **Trigger**: Swift bridge (`BridgeHandler.setWindowActive`) on `NSWindow.didBecomeKeyNotification`/`didResignKeyNotification`. Browser fallback: `window.blur`/`window.focus` in `AppLayout.tsx`
- **Design rule**: never dim body text, images, tags, or data. Only dim interactive state indicators (selection highlight, focus shadow)

## Dark mode

Uses CSS `light-dark()` function (supported in all major browsers since mid-2024, ~87%+ global). No JS involved. The cascade:

1. **OS/browser preference** → `color-scheme: light dark` on `:root` respects `prefers-color-scheme` automatically
2. **User override** → `BRISTLENOSE_COLOR_SCHEME` env var (or `.env`). Values: `"auto"` (default), `"light"`, `"dark"`
3. **HTML attribute** → when config is `"light"` or `"dark"`, `render/report.py` emits `<html data-theme="light|dark">` which forces `color-scheme` via CSS selector
4. **Print** → always light (forced by `color-scheme: light` in `print.css`)

### How tokens work

`tokens.css` has two blocks:
- `:root { --bn-colour-bg: #ffffff; ... }` — plain light values (fallback for old browsers)
- `@supports (color: light-dark(...)) { :root { --bn-colour-bg: light-dark(#ffffff, #111111); ... } }` — modern browsers get both values, resolved by `color-scheme`

### Adding a new colour token

Add both light and dark values in the `light-dark()` call inside the `@supports` block, and the plain light fallback in the `:root` block above it.

### Showing light and dark SIDE BY SIDE — `color` inherits as a COMPUTED value

Inherited `color` is a *computed* value, so a column forced to the other `color-scheme` keeps its parent's resolved text colour, silently: re-declare `color: var(--bn-colour-text)` on the forced-scheme container itself. The tell and the elements that betray it: [full entry](gotchas.md#type-colour-and-tokens).

### Logo

The `<picture>` element swaps between `bristlenose-logo.png` (light) and `bristlenose-logo-dark.png` (dark) using `<source media="(prefers-color-scheme: dark)">`. Both are in `assets/` directory. Dark logo is currently a placeholder (inverted version) — needs replacing with a proper albino bristlenose pleco image.

**Logo + appearance toggle gotcha:** `<picture>` `<source>` media queries only follow the OS-level `prefers-color-scheme`, not the page-level override, so `settings.js` (`_updateLogo`) physically removes the `<source>` when light or dark is forced. The logo also links to the Project tab (`.report-logo-link`). Details: [full entries](gotchas.md#type-colour-and-tokens).

### No JS theme toggle

Dark mode is CSS-only. No localStorage, no toggle button, no JS involved.

## Template CSS files

Template-level CSS in `templates/`: `report.css` (main report layout), `transcript.css` (per-session transcript pages — back button, segment layout, meta styling, citation highlight, anchor highlight animation), `print.css` (print overrides, hides interactive elements — includes `.feedback-links`, `.feedback-overlay`, `.footer-logo-picture`). Quote attribution links styled via `.speaker-link` in `organisms/blockquote.css` (inherits muted colour from `.speaker`, accent on hover). Dashboard stat cards, featured quotes, and session table rows all use `var(--bn-colour-hover)` for interactive hover — see "Dashboard cross-tab navigation" section below.

### Inline citation highlight (bn-cited)

Quoted text within transcript segments is wrapped in `<mark class="bn-cited">` elements by the Python renderer. This marks the verbatim excerpt that was extracted as a quote — the rest of the segment is context.

The `.bn-cited` rule is currently `background: transparent` while the treatment is rethought, but the `<mark>` is always emitted. CSS, HTML and rationale: [full entry](gotchas.md#static-render-jinja2-and-report-js).

### Arrival flash (was "anchor highlight")

Whatever a link lands on flashes and fades to its own background: the transcript paragraph, the quote card or group heading in Quotes, the screen's title in Screens, the asking in Discussion. One atom, `atoms/arrival.css` (`@keyframes bn-arrival`), driven by three tokens in `tokens.css`: `--bn-arrival-colour` (an alias of the palette's `--bn-colour-highlight`), `--bn-arrival-duration` (5s), `--bn-arrival-easing` (ease-out). Change those to change it everywhere. Full spec and catalogue: `docs/design-arrival-flash.md`.
Details (the SPA writes `data-arrived` through `markArrived()`, never a class; the keyframe has only a `from` and no fill-mode; the selector is `:root [data-arrived]`; the static render keeps `.anchor-highlight`; no reduced-motion override, by decision): [full entry](gotchas.md#interaction-controls-and-motion).

## Sentiment bar charts

Two side-by-side horizontal bar charts: AI sentiment (Python-rendered) and User tags (JS-rendered by `histogram.js`). CSS grid layout with `display: contents` on bar groups to align bar edges. See `docs/design-sentiment-charts.md` for layout details, AI sentiment ordering, histogram delete button, and CSS file list.

## PersonBadge molecule

`molecules/person-badge.css` — reusable badge + name pattern for speaker identification in the session table. Combines the `.badge` atom with a named span.

- **`.bn-person-badge`** — `inline-flex`, `align-items: center`, `gap: 0.4rem`, `white-space: nowrap`. Contains a `.badge` and a `.bn-person-badge-name`
- **`.bn-person-badge .badge`** — `flex-shrink: 0` (badge never truncates)
- **`.bn-person-badge-name`** — `font-weight: var(--bn-weight-emphasis)` (490). In the moderator header, names use normal weight (no `.bn-person-badge-name` class)
- **Usage**: session table speaker cells (semibold names) and moderator header (regular weight names). The molecule is included in `_THEME_FILES` in `render/theme_assets.py`. React equivalent: `PersonBadge` component in `frontend/src/components/PersonBadge.tsx`

## Session grid CSS

**The Sessions lens is a CSS grid, not a `<table>` (since 6 Aug 2026)** — `organisms/sessions-grid.css`. It uses container queries on `.bn-session-table` (which is the container: `container-type: inline-size`), `grid-template-columns: subgrid` on rows, a proportional shrink pair, and a narrow-width degradation ladder that sheds surnames → user journey → names entirely. It is pure CSS: every cell renders at every width and the queries decide what shows, so there is no width measurement in JS and it survives `file://` in an exported report. Full rationale in the file header; class inventory in `CSS-REFERENCE.md`.

`templates/report.css` keeps the legacy `.bn-session-table tr/td` rules, still used by the sealed static render and the Project-tab session list.

**Three specificity traps live here** (`.bn-cell-*` rules losing to the `templates/` layer, which concatenates after organisms): when adding any `.bn-cell-*` rule, grep `templates/report.css` for the twin `.bn-session-*` class first, and never fix it by editing `report.css`. The fix is a 0-2-0 rule such as `.bn-sessions-row .bn-cell-*`, and not applying `.bn-session-meta` to the start cell. The measured cases and the eleven-day inert ladder rung: [full entries](gotchas.md#css-cascade-specificity-and-caching).

Class inventory for the grid (`.bn-session-*`, `.bn-video-thumb`, `.bn-sparkline`, `.bn-interviews-link`, clickable rows): [full entry](gotchas.md#layout-and-rendering-mechanics); per-component CSS docs are in `CSS-REFERENCE.md`.

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

1. **CSS-only** (`.has-tooltip .tooltip` in `molecules/autocode-report.css`) — used for rationale tooltips on proposed badges and on the proposal rows of the threshold review modal (`ProposalZoneList.tsx`). Parked behind `featureFlags.proposalRationaleTooltip`. Uses `transition-delay` for the 300ms hover delay.
2. **JS-controlled** (`CellTooltip` in `frontend/src/islands/SignalsPage.tsx`) — used for analysis heatmap cell tooltips. Uses `setTimeout(300)` in `handleCellEnter` for the delay, CSS `@keyframes cell-tooltip-in` for the animation.

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

**Two `content-visibility` gotchas:** measuring a card with `getBoundingClientRect()` forces the layout the property exists to skip, and `content-visibility: auto` implies `contain: layout style paint`. The measurements and the fix: [full entries](gotchas.md#layout-and-rendering-mechanics).

## Gotchas

**The full entries — the incident, the measurement, the fix — are in [`gotchas.md`](gotchas.md), by theme.** Read the theme's section before working in that area. This index is the rule and the tell, nothing more: one line per entry, same order as the file. Add a new gotcha to `gotchas.md` and its headline here.

**CSS cascade, specificity and caching** (8) — [full entries](gotchas.md#css-cascade-specificity-and-caching)

- Three specificity traps live here, all three measured shipping wrong before being raised
- The speakers one is the cautionary case: it made a whole ladder rung inert for eleven days
- A sibling combinator breaks silently when a wrapper is added, and nothing goes red.
- A running `bristlenose serve` caches the concatenated theme CSS IN MEMORY — edit…
- Theme CSS caches HARD in the browser — a plain reload (and even Playwright's CDP…
- A state class only ONE of the two renderers writes is a rule that cannot fire in the app — and it…
- CSS specificity vs source order in concatenated theme — `render/theme_assets.py` concatenates CSS…
- Count specificity, don't assert it in a comment — and never let a `@media print` override outlive…

**Layout and rendering mechanics** (10) — [full entries](gotchas.md#layout-and-rendering-mechanics)

- Complex data tables are custom by nature — do not build a generic responsive-table system (decided…
- The Sessions grid is a deliberate exception — do NOT fold its thresholds into this scale.
- Session grid class inventory (`.bn-session-*`, `.bn-video-thumb`, `.bn-sparkline`, clickable rows)
- Measuring a card with `getBoundingClientRect()` FORCES the layout `content-visibility` is meant to…
- `content-visibility: auto` applies `contain: layout style paint` implicitly, creating a new…
- A measuring probe inside the box it measures takes that box's state classes — and a fit that…
- `background-clip: text` shimmer — keep `background-position` inside `[0%, 100%]`, and divide the…
- Standalone mockups that reuse `.tag-sidebar` render blank until you neutralise its reveal rule.
- `auto-fit` grid collapse is DEFEATED by a full-span (`grid-column: 1 / -1`) sibling → ragged right…
- Symmetric inline padding on a component inside a *wrapping* chain reads as a stray character, not…

**Type, colour and tokens** (10) — [full entries](gotchas.md#type-colour-and-tokens)

- Corollary — don't hardcode px in anything that also renders on desktop
- Forcing `color-scheme` on one column and the other on another to show light and dark side by side…
- Logo + appearance toggle gotcha: `<picture>` `<source>` only responds to the OS-level…
- Logo click: the fish logo navigates to the Project tab (`.report-logo-link`)
- `blockquote .timecode` in `blockquote.css` must use `--bn-colour-accent` not `--bn-colour-muted`…
- `--bn-colour-border-hover` token — 3-state border progression for toolbar buttons: rest…
- Mute readable text with a colour token, never with `opacity`.
- Delete circles are red, not grey — `badge-ai::after` and `.badge-user .badge-delete` use…
- `--bn-colour-danger` and `--bn-colour-success` are not in `tokens.css`
- Font-weight tokens — the body tiers, and two of them do not render as the ladder promises.

**Interaction, controls and motion** (7) — [full entries](gotchas.md#interaction-controls-and-motion)

- Arrival flash: the SPA writes `data-arrived`, never a class; the keyframe names only a `from`; the…
- Focus outline convention — `:focus:not(:focus-visible) { outline: none }` in…
- Modifier-clicks must open new tabs — any clickable element that behaves like navigation (tabs…
- Modal infrastructure: every React dialog draws through `frontend/src/components/Dialog.tsx`, and…
- Toolbar button dual-class pattern — tag filter and view switcher buttons use dual classes…
- Pencil icon convention for inline editing — an affordance is hidden at rest and revealed by…
- A `prefers-reduced-motion` block is a *set*, not a checkbox — add a transition, add its selector…

**Static render, Jinja2 and report JS** (19) — [full entries](gotchas.md#static-render-jinja2-and-report-js)

- `.bn-cited` inline citation highlight: visually off (`background: transparent`) while the `<mark>`…
- Jinja2 dict key naming: never use Python dict method names (`items`, `keys`, `values`, `get`…
- JS load order matters: `view-switcher.js`, `search.js`, `tag-filter.js`, `hidden.js`, and…
- `_TRANSCRIPT_JS_FILES` includes `badge-utils.js`, `transcript-names.js`, and…
- Footer feedback visibility now has two paths: legacy static path still uses…
- Sentiment chart layout: both AI sentiment and user-tags charts use CSS grid…
- Surprise sentiment placement: surprise is neutral — it renders between positive sentiments and the…
- IIFE scoping and inline onclick: all report JS is wrapped in `(function() { ... })()` by…
- Stale HTML files cause debugging confusion — if a previous render created a differently-named file…
- Codebook page sits at output root — `codebook.html` is at the same level as the report (not in…
- `BRISTLENOSE_PLAYER_URL` for transcript pages — `player.js` needs to open…
- Player→opener uses `postMessage`, not `window.opener` function calls
- Analysis and codebook render both inline and standalone — `analysis.html` and `codebook.html` sit…
- `analysis.js` avoids literal `"data-theme"` string — dark mode tests (`test_dark_mode.py`) assert…
- Analysis heatmap uses client-side `adjustedResidual()` — the function exists in both Python…
- Renderer overlay (dev-only) — `_build_renderer_overlay_html()` in `server/app.py` injects a…
- `<!-- bn-session-table -->` markers — SUPERSEDED. Dead as of 21 Sep 2026 — nothing reads these…
- `serve_mode` vs runtime replacement — `render/report.py` has a `serve_mode` param that renders…
- `Element.closest()` only matches compound selectors — `closest()` walks up the DOM tree and tests…

**Tags, the tag filter and hidden quotes** (10) — [full entries](gotchas.md#tags-the-tag-filter-and-hidden-quotes)

- Hidden quotes vs visibility filters: hidden quotes use `.bn-hidden` class +…
- Hidden badge count depends on operation order in `hideQuote()`
- Histogram delete-from-all: clicking the hover `×` on a user tag label in the histogram shows a…
- Reserved sentiment names — `_RESERVED_SENTIMENTS` in `tags.js` blocks users from creating tags…
- Case-insensitive tag deduplication — `closeTagInput()` uses `.some(t.toLowerCase() === valLower)`…
- Bulk tag visual feedback — when committing a tag to multiple quotes, each new badge gets…
- `tagFocusedQuote()` selection guard — pressing `t` only triggers bulk mode if the focused quote is…
- Tag-filter rebuilds on every open — `_buildTagFilterMenu()` is called each time the dropdown opens…
- Tag-filter codebook integration — tags are grouped into tinted `.tag-filter-group` containers using…
- Search threshold is 8 tags — the tag-filter search input only appears when there are 8+ tags. This…

## Cross-seam alignment: inspector chrome + first baselines (desktop/embedded)

The flanking sidebars (tags right; TOC left since 14 Aug 2026) are styled to read as native-feeling **inspector** chrome continuous with the AppKit sidebar. Three coupled gotchas, all in `organisms/sidebar.css` + `tokens.css` (added Jul 2026, commit `a96c7c6f`):

**Inspector chrome and the native seam** (6) — [full entries](gotchas.md#inspector-chrome-and-the-native-seam)

- `--bn-colour-inspector-bg` is a themeable chrome tint, not a content surface.
- A light strip beside a panel that no CSS colour explains is the WINDOW showing through the…
- Sticky teleport. `position: sticky; top: 0; height: 100vh` on a grid column whose *flow origin* is…
- First-baseline datum is web-internal (`--bn-first-baseline` RETIRED, 25 Jul 2026).
- `text-decoration: none` on a child does NOT remove an ancestor's underline — and `getComputedStyle`…
- A leading LITERAL cannot fork platforms — so `line-height: 1.5` is a web-only value that ships to…
