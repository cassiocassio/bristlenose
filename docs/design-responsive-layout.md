# Responsive Quote Grid — Design & Implementation Notes

**Status (this first part, the quote grid):** ✅ Shipped — responsive multi-column grid is live, plus CSS Grid Lanes masonry for Safari/WebKit 26.4+ (see Update, 14 Jun 2026). The second part, § Global Layout Frame & Navigation Sidebar, is partly shipped and carries its own status and post-script.
**Mockup:** `docs/mockups/responsive-quote-grid.html` (original grid), `docs/mockups/grid-lanes-quotes.html` (masonry bake-off)
**Date:** 19 Feb 2026

## Changelog

- _2026-10-15_ — trued up the second part only (§ Global Layout Frame & Navigation
  Sidebar): added a dated post-script recording which goals shipped and which did not,
  marked "Current architecture (what changes)" superseded with the table kept, fixed the
  `SidebarLayout.tsx` path and the grid's column count, and narrowed the top status line to
  the quote grid. The first part was not re-trued. Anchors:
  `frontend/src/layouts/AppLayout.tsx:260-270`, `:365-380`, `:782-824`;
  `frontend/src/components/SidebarLayout.tsx:496`; `frontend/src/contexts/SidebarStore.ts:40`,
  `:53`, `:57`, `:326`; `bristlenose/theme/organisms/sidebar.css:88-119`; commits "fit cascade:
  the tab bar condenses, then its icons move up, then the minimap, Contents, Tags", "fit
  cascade on the mac: the minimap goes first, then the projects column", "sessions lens:
  responsive grid replaces the auto-table".

---

## Update — shipped, plus CSS Grid Lanes masonry (14 Jun 2026)

The responsive multi-column grid described below is **shipped** — `organisms/responsive-grid.css` is live in `_THEME_FILES`. The "Implementation plan" sections are kept as historical record. Since then, native CSS masonry was layered on top.

**What shipped:** an `@supports (display: grid-lanes)` block in `responsive-grid.css` swaps the rectangular grid for native masonry (`display: grid-lanes`) on engines that support it, reusing the same `grid-template-columns` and `gap`. New token `--bn-flow-tolerance: 5em` in `tokens.css` biases packing toward source order. Delete the `@supports` block to revert every surface to the rectangular grid — no other change.

**Why:** a bake-off mockup (`docs/mockups/grid-lanes-quotes.html`) showed masonry clearly tighter for varying-length quotes; validated on real long-form oral-history data (~284 quotes). The rectangular grid leaves ragged gaps under short cards (row height = tallest card in that row); masonry packs those away.

**The reading-order tradeoff (deliberate).** The rectangular grid places **row-major**, so it reads comic-strip — left-to-right-then-down = the quotes' time/sequence order (often a participant's train of thought or the product flow). Masonry places each card in the shortest column (**column-major**), so visual order diverges from source order. `flow-tolerance: 5em` means "only break reading order when a card is more than ~5 lines taller than its in-order neighbour" — it preserves sequence for ordinary quotes and lets only big outliers reflow to fill gaps. 5em is **provisional**, tuned by eye on the mockup + real long-form data; revisit per corpus (masonry's benefit scales with length variance).

**Accessibility.** Quote cards aren't tabbable; keyboard `j`/`k` walk DOM order (`FocusContext.moveFocus`), and DOM order is preserved (CSS reorders pixels only — WCAG 1.3.2 / 2.4.3 hold, screen-reader order unchanged). But under masonry the focused card can be visually non-local — "strange but workable" in QA; trackpad/scroll is unaffected. Possible future polish: geometry-aware `moveFocus`. Build only if it proves annoying.

**Browser support.** Native in Safari/WebKit 26.4+ — including the desktop app's WKWebView on macOS 26.4+ (gated on the host's Safari version; nothing is bundled). Chrome/Edge/Firefox are flagged, expected to ship later in 2026. The `@supports` query auto-upgrades each engine the day it ships stable — zero code change, no redeploy. Until then those engines get the rectangular grid. A polyfill to close that interim gap for non-Safari is tracked as a future follow-up.

**Files:** `bristlenose/theme/organisms/responsive-grid.css` (the `@supports` block) and `bristlenose/theme/tokens.css` (`--bn-flow-tolerance`). No React change, no `_THEME_FILES` change, no HTML change — same `.quote-group` selector, rendered only by `QuoteGroup.tsx`.

---

## Problem

The report uses a fixed `--bn-max-width: 52rem` (832px) article width. Quote cards fill that width with no internal constraint, producing ~18-22 words per line. This wastes screen real estate on large displays and ignores 500 years of typographic wisdom: optimal reading measure is 45-75 characters per line (~7-12 words of English).

Researchers with 27" iMacs, external 4K monitors, or 16" MacBook Pros see a centred 832px column with huge margins. Researchers with a skinny window next to Miro get the same 832px trying to squeeze into 500px. Neither is good.

## Design principles

1. **Reading measure stays constant, column count changes.** Like a broadsheet newspaper adding columns rather than widening them. The Aldus Manutius principle: the line length that's comfortable to scan never gets wider — you just get more of them.

2. **CSS-only.** No JavaScript for layout. The grid uses `auto-fill` — columns appear and disappear based on available space. The browser does the work.

3. **Modular and reversible.** The responsive grid is a single CSS file (`organisms/responsive-grid.css`) added to `_THEME_FILES`. Remove the file and everything reverts to the current fixed-width layout. No changes to HTML structure required.

## Chosen values

### Card width: `--bn-quote-max-width: 23rem` (368px)

Tested interactively with the mockup slider. At 23rem:
- Prose width after padding/timecode/action buttons: ~222px
- Characters per line: ~30
- **Words per line: ~5** (compact scanning, sticky-note density)

This was chosen visually — it feels right for quote scanning in a research tool. The cards read like sticky notes on an affinity wall, not like paragraphs in a book. Each quote is short enough to take in at a glance.

Aldus Manutius's pocket octavos ran 6-7 words/line for continuous prose. Research quotes are shorter fragments scanned serially, so 5 words/line works. The slider in the mockup goes from 18rem to 44rem for further experimentation.

### Column count by display

| Display | CSS px width | Columns at 23rem |
|---------|-------------|-----------------|
| Skinny window (Miro) | ~500px | 1 |
| MacBook Air 13" | 1470px | 3 |
| MacBook Pro 14" | 1512px | 3 |
| MacBook Pro 16" | 1728px | 4 |
| 4K external (2x) | 1920px | 4 |
| iMac 24" (4.5K) | 2240px | 5 |
| Studio Display 27" (5K) | 2560px | 5 |
| Pro Display XDR 32" (6K) | 3008px | 7 |

### Grid gap: `--bn-grid-gap: 1.25rem` (20px)

Enough separation to visually distinguish cards without wasting space.

---

## Implementation plan

### Phase 1: Quote grid (CSS-only, ~1 hour)

One new CSS file. Three token additions. One file list change. Zero HTML changes.

#### New file: `organisms/responsive-grid.css`

```css
/* Organism: responsive-grid — multi-column quote layout.
   Columns appear automatically via auto-fill as viewport widens.
   Card reading measure stays constant at --bn-quote-max-width.
   Remove this file from _THEME_FILES to revert to fixed-width layout. */

.quote-group {
    display: grid;
    grid-template-columns: repeat(
        auto-fill,
        minmax(min(var(--bn-quote-max-width), 100%), 1fr)
    );
    gap: var(--bn-grid-gap);
    align-items: start;
}

/* Section headings and descriptions span the full grid */
.quote-group ~ h2,
.quote-group ~ h3,
.quote-group ~ .description,
h2, h3, .description {
    /* These are siblings of .quote-group, not children.
       The grid only affects direct children of .quote-group.
       No spanning needed — they're outside the grid. */
}

/* Prevent cards splitting across columns in print */
.quote-group blockquote {
    break-inside: avoid;
}
```

Note: The existing `.quote-group` in `blockquote.css` currently uses `display: flex; flex-direction: column`. The new file overrides this to `display: grid`. Because it loads after `blockquote.css` in `_THEME_FILES`, the cascade handles it — no need to remove the old rule.

#### Token additions in `tokens.css`

```css
/* In :root, after --bn-max-width */
--bn-quote-max-width: 23rem;   /* card reading measure — ~5 words/line */
--bn-grid-gap: 1.25rem;        /* gap between grid columns */
```

#### Layout change in `report.css`

Replace the fixed article max-width with a fluid container:

```css
/* Before */
article {
    max-width: var(--bn-max-width);
    margin: 0 auto;
}

/* After */
article {
    max-width: none;
    margin: 0 auto;
    padding: 0 var(--bn-space-lg);
}
```

Keep `--bn-max-width: 52rem` in `tokens.css` — it's still used by single-column elements (headings, description text, dashboard) that shouldn't span the full width on ultra-wide screens. Add:

```css
h1, h2, h3, .description, .bn-dashboard {
    max-width: var(--bn-max-width);
}
```

#### Add to `_THEME_FILES` in `render/theme_assets.py`

Insert after `organisms/blockquote.css`:

```python
"organisms/responsive-grid.css",
```

#### Modularity: how to swap in and out

To **enable** the responsive grid: include `organisms/responsive-grid.css` in `_THEME_FILES`.

To **disable** it: remove that one line. Everything reverts — `.quote-group` falls back to the `flex-direction: column` rule in `blockquote.css`, article uses `--bn-max-width`, and the layout is identical to today.

To **experiment** without changing Python: override in the browser dev tools:
```css
.quote-group { display: flex !important; flex-direction: column !important; }
article { max-width: 52rem !important; }
```

Or from serve mode, inject a one-line override CSS file.

### Phase 2: Toolbar and nav bar responsive (separate task)

Make the toolbar, search field, tag filter, and global nav compress gracefully at narrow viewports. This is the prerequisite for the "skinny window next to Miro" workflow.

**Key changes:**
- `@media (max-width: 600px)` in `organisms/toolbar.css`: search field shrinks, filter badges wrap, buttons collapse to icons
- `organisms/global-nav.css` already has a 600px breakpoint for tab scrolling — verify it's sufficient
- Card chrome (action buttons, padding) tightens at narrow widths

**Files:** `organisms/toolbar.css`, `organisms/global-nav.css`, `molecules/search.css`, `molecules/tag-filter.css`

### Phase 3: Dashboard grid (separate task)

Dashboard panes use the same `auto-fill` approach. Currently 2-column grid collapsing to 1 at 600px. Extend to grow beyond 2 columns on wide screens.

**File:** `organisms/global-nav.css` (dashboard styles are in the nav CSS)

### Phase 4: Transcript pages (verification only)

Transcript pages have an 800px breakpoint for annotation margin placement (lowered from 1100px on 2026-07-26). Above it the annotations occupy a real grid column whose width clamps (`clamp(8.5rem, 13vw, 12.5rem)`) so labels wrap in the narrow case; below it they drop inline. Verify this holds when the article width is no longer capped at 52rem.

**File:** `molecules/transcript-annotations.css`

---

## Content density setting (separate feature)

Three-way toggle: Compact / Normal / Generous. Scales all content inside `<article>` uniformly while keeping chrome (nav, toolbar, logo) at fixed size.

| Setting | `article` font-size | Use case |
|---------|---------------------|----------|
| Compact | 14px (0.875rem) | Dense scanning, big datasets |
| Normal | 16px (1rem) | Default |
| Generous | 18px (1.125rem) | Screen-sharing, calls, accessibility |

### Implementation pattern

Follows the existing settings.js/appearance toggle pattern exactly:

1. **Token:** `--bn-content-scale` in `tokens.css` (default `1`)
2. **CSS:** `article { font-size: calc(var(--bn-content-scale) * 1rem); }` — because all spacing tokens are `rem`-based, everything inside article scales together
3. **HTML:** Three radio buttons in the Settings panel (`render/report.py`), name `bn-density`, values `compact`/`normal`/`generous`
4. **JS:** New `density.js` module following `settings.js` pattern:
   - `createStore("bristlenose-density")` for localStorage persistence
   - `_applyDensity(value)` sets `data-density` attribute on `<html>`
   - `initDensity()` in boot sequence (add to `_bootFns` in `main.js`)
5. **CSS selectors:**
   ```css
   html[data-density="compact"] article { font-size: 0.875rem; }
   html[data-density="generous"] article { font-size: 1.125rem; }
   ```
6. **Files:** `tokens.css`, `organisms/settings.css`, new `js/density.js`, `render/report.py`, `main.js`
7. **Add to `_THEME_FILES`** and **`_JS_FILES`** in `render/theme_assets.py`

### Interaction with responsive grid

Generous + wide screen = fewer but more readable columns (23rem at 18px base = 25.9rem effective, so columns are slightly wider).

Compact + wide screen = more columns with tighter cards (23rem at 14px base = 20.1rem effective).

The grid's `auto-fill` handles this automatically — no special logic needed.

---

## Files touched (Phase 1 only)

| File | Change |
|------|--------|
| `bristlenose/theme/tokens.css` | Add `--bn-quote-max-width`, `--bn-grid-gap` tokens |
| `bristlenose/theme/templates/report.css` | Make article fluid, cap headings at `--bn-max-width` |
| `bristlenose/theme/organisms/responsive-grid.css` | **New file** — grid layout for `.quote-group` |
| `bristlenose/stages/s12_render/theme_assets.py` | Add `responsive-grid.css` to `_THEME_FILES` |

No HTML template changes. No JavaScript changes. No Python logic changes.

## Files touched (density setting)

| File | Change |
|------|--------|
| `bristlenose/theme/tokens.css` | Add `--bn-content-scale` token |
| `bristlenose/theme/organisms/settings.css` | Density radio button styles |
| `bristlenose/theme/js/density.js` | **New file** — density preference module |
| `bristlenose/theme/js/main.js` | Add `initDensity` to `_bootFns` |
| `bristlenose/stages/s12_render/report.py` | Add density radios to settings HTML |
| `bristlenose/stages/s12_render/theme_assets.py` | Add `density.js` to `_JS_FILES` |

---

## Testing

**Automated:** No new tests needed for Phase 1 (pure CSS). Existing Vitest/pytest suites verify rendering produces valid HTML — the grid CSS doesn't affect that.

**Manual QA checklist:**
- [ ] Open report at 1728px (16" MBP) — should see 4 columns at 23rem
- [ ] Drag window to ~500px — should collapse to 1 column gracefully
- [ ] Full-screen on 4K — should see 4-5 columns
- [ ] Verify section headings (h2, h3) don't get trapped inside grid cells
- [ ] Verify starred quotes still render correctly (border-left, bold)
- [ ] Verify hidden quotes still hide/show correctly
- [ ] Verify keyboard navigation (focus.js) works across grid columns
- [ ] Verify search highlighting works across columns
- [ ] Verify dark mode renders correctly in grid layout
- [ ] Verify print layout is unaffected (print.css hides interactive elements)
- [ ] Verify transcript pages are unaffected (they don't use `.quote-group`)
- [ ] Remove `responsive-grid.css` from `_THEME_FILES` — verify clean revert

---

## References

- Aldus Manutius pocket octavo format: ~6-7 words/line, optimised for portable reading (1501)
- Robert Bringhurst, _The Elements of Typographic Style_: 45-75 characters per line for body text
- Mockup image reference: `docs/mockups/responsive-quote-grid.html` (interactive, with slider and HUD)

---

# Global Layout Frame & Navigation Sidebar

**Status:** Design brief — Figma in progress, not yet implemented.
**Date:** 4 Mar 2026

_Changed 15 Oct 2026:_ partly shipped. The left-panel half is built; the sticky
toolbar band, the global `min-width` and the heatmap's rotated sentiment headers
are not. See the post-script directly below. The brief after it is the 4 Mar
baseline and is kept as written.

## Post-script — what shipped (15 Oct 2026)

Each goal checked against `main` on 15 Oct 2026.

**Shipped**

- **The left-panel slot.** `SidebarLayout` renders `leftPanel ?? <TocSidebar/>`
  (`frontend/src/components/SidebarLayout.tsx:496`), and `AppLayout` passes a panel
  per lens (`frontend/src/layouts/AppLayout.tsx:782-802`). Panels followed for
  Sessions (14 Mar, "add sessions sidebar with live-resize breakpoints"), Codebook
  (19 Mar, "add codebook sidebar — Phase 1 of LHS navigation for all tabs"; the v2
  navigator since 31 Aug) and Signals (21 Mar, "add analysis sidebar with signal
  entries and store"). What each panel lists is described in
  [design-sidebar.md](design-sidebar.md).
- **Where it applies.** Quotes, Sessions, Codebook and Signals use the shared
  panel. Sessions has it in the browser only: on the Mac a native popover replaces
  it (`AppLayout.tsx:260-270`). Project has no left panel (open question 1 is still
  open). Discussion and Screens have their own navigator columns inside the page.
- **Pin state is global.** One persisted `tocMode` under one key, `bn-toc-open`
  (`frontend/src/contexts/SidebarStore.ts:57`, `:181`), not per route.
- **Overlay and push.** Both shipped as user gestures: hover or click the rail
  for overlay, the rail button or `[` for push. A heading click in overlay leaves
  the panel open by default; mousing out closes it (`frontend/src/components/TocSidebar.tsx:207-210`; the
  playground's `overlayAutoClose` is off). That answers open question 3.
- **One default width.** One `tocWidth`, default 240 px (`SidebarStore.ts:40`),
  shared by every lens. That answers open question 2.
- **The rail on every lens, in the browser.** Lenses without the shared panel
  render `.layout-inert`: the rail column and a matching right spacer, no panel
  (`bristlenose/theme/organisms/sidebar.css:88-103`; commit "add inert rail layout
  for non-sidebar tabs"). Its button exists only on Discussion and Screens. On the
  Mac the rails are zeroed (`sidebar.css:116-119`) and the native toolbar toggles
  the panels.
- **Sessions narrower.** The table became a container-query grid on 6 Aug
  ("sessions lens: responsive grid replaces the auto-table").

**Not shipped, checked on 15 Oct 2026**

- **No layout shift across lenses.** Met only while the panel is closed. With
  the panel pushed open, moving to Project, Discussion or Screens moves the
  content edge, because `.layout-inert` has no panel column (`sidebar.css:93-98`).
- **The global sticky toolbar band.** Not built. Only Quotes has a sticky
  `.toolbar` (`bristlenose/theme/organisms/toolbar.css:19-29`, rendered by
  `QuotesTab.tsx` alone). Codebook and Signals have no contextual sticky headers.
  Signals' heatmap pane sticks to the window bottom, which is a different thing.
- **Rotated sentiment headers on the heatmap.** Not built. Only the tag heatmaps
  rotate their column labels (`signals.css:421-441`); sentiment columns skip
  `heatmap-col-header` (`frontend/src/islands/SignalsPage.tsx:894`).
- **The global `min-width`.** Not set: nothing on `html`, `body`, `#bn-app-root`
  or `.layout` carries one. What the fit cascade covers instead (15 Oct 2026,
  [design-sidebar-playground.md § Fit to width](design-sidebar-playground.md)):
  - The centre column keeps `CONTENT_FLOOR_PX` (368 px, one quote card) or, in the
    browser, the tab bar's one-row width if that is wider (`SidebarStore.ts:53`,
    `fitPanels` at `:326`). To hold it, things give way in order: the tab bar
    condenses, its icon tabs move into the report header, the minimap hides,
    Contents closes, Tags closes. The tabs wrap only after that.
  - Lenses without panels get the tab-bar steps from the same function.
  - On the Mac the minimap goes first, then the projects column folds, then
    Contents, then Tags. The panels' needed width is sent as `minWidth` in
    `panel-state` (`AppLayout.tsx:365-380`) and decides when the column folds;
    it never sets a window minimum.
  - The Mac window has a fixed minimum, 700 pt, the same on every lens
    (`desktop/Bristlenose/Bristlenose/DetailFloor.swift:110`).

  What it does not cover: a browser page minimum below which nothing squeezes;
  the panel just opened is exempt, so if it alone leaves the centre under the
  floor, the centre squeezes. The floor is one quote card, not each page's
  comfortable width from the problem table below, so a lens wider than a card
  (Project's stat row, the Signals heatmap) is not protected by it.
- **Codebook badge wrapping.** Not re-measured. The lens was rebuilt as the v2
  navigator on 30–31 Aug, so the 4 Mar observation may no longer hold.

---

## Problem

The current layout varies structurally between tabs. The Quotes page has a 5-column grid with two sidebars; all other tabs are a simple centred `<article>`. Switching tabs causes visible layout jumping — the content column shifts position as sidebars appear and disappear. There is no viewport minimum width set anywhere (body, html, containers), so the app squeezes to arbitrary narrow widths with degraded rendering.

Additionally, several pages need wide viewports to look good:

| Page | Comfortable min width | Bottleneck |
|------|----------------------|------------|
| Project (dashboard) | ~780px | Stat cards row |
| Sessions | ~900px | Table columns (thumbnail, sentiment, journey) |
| Quotes (no sidebars) | ~500px | Quote cards (just flowing text) |
| Quotes (both sidebars) | ~1100px | Three-panel layout |
| Codebook | ~800px | Badge pills wrapping to two lines |
| Analysis (heatmap) | ~950px | 7 sentiment columns + labels |
| Analysis (signals) | ~700px | Signal cards |

Setting a single global `min-width` requires making the harder pages work narrower.

## Goals

1. **One consistent frame across all tabs** — no layout shift when switching between Project / Sessions / Quotes / Codebook / Analysis
2. **Single global `min-width`** — identical for all pages, number TBD after Figma design
3. **Global left navigation sidebar** — present on every tab with contextual content
4. **Global sticky toolbar band** — same depth on every tab, contextual content
5. **Make wide pages work narrower** — Sessions table redesign, Analysis heatmap rotation

## Design decisions

### The rigid frame

Three fixed horizontal bands plus a left rail. Everything below the toolbar scrolls. The frame never moves — only content inside it changes.

```
┌──────────────────────────────────────┐
│  Header (logo, project name)         │
├──────────────────────────────────────┤
│  Nav tabs                            │
├──┬───────────────────────────────────┤
│  │  Sticky toolbar band (per-tab)    │  ← same height, same position
│  │───────────────────────────────────│
│R │                                   │
│A │  Scrollable content               │
│I │                                   │
│L │                                   │
└──┴───────────────────────────────────┘
```

### Global left sidebar

- **Always-visible left rail** on every tab (thin strip, hosts toggle button, hover target)
- **Two user-controlled modes** (not breakpoint-driven — the user chooses, not the viewport):
  - **Slide-over** (mouse into rail margin): overlays content, temporary, click a heading and you're done — sidebar dismisses. For quick peeks and narrow screens
  - **Slide-out** (click rail button / `[` keyboard shortcut): pushes content, persistent. For keeping navigation omnipresent on wider screens
- **Pin state is global**: if pinned on Quotes, stays pinned when switching to Sessions — sidebar stays open, content swaps
- **Default opening width is the same for all tabs** — consistent frame regardless of which tab you're on
- **Content is contextual per tab:**

  | Tab | Sidebar content |
  |-----|----------------|
  | Project | TBD |
  | Sessions | Session list (participants, times, dates) |
  | Quotes | Sections + Themes (current TOC) |
  | Codebook | Codebook list (active + available) |
  | Analysis | Mini signal cards (slide-navigator style, like a PowerPoint slide navigator) |

- _Changed 15 Oct 2026 (see the post-script):_ the rail is on every lens in the
  browser but holds a button only on Discussion and Screens, and the Mac has no
  rails. A slide-over heading click leaves the panel open by default. The modes are
  still the user's, but a pushed panel the window cannot hold is closed by the fit
  cascade and comes back when the window widens. The content table above is the
  4 Mar plan; what each panel lists now is in [design-sidebar.md](design-sidebar.md).
- Interaction model inspired by Reddit (slide-over + slide-out as separate user-initiated gestures)
- The tradeoff is good for narrow screens: a 13" screen can live with only the right-hand tag sidebar open for analysis work on a still reasonably sized single column of quotes

### Global sticky toolbar band

- **Same vertical position and height on every tab** — consistent depth in the layout
- Content is contextual per tab:

  | Tab | Sticky toolbar content |
  |-----|----------------------|
  | Project | Import files button + project admin controls |
  | Sessions | Table header row (ID, Participants, Start, Duration, etc.) — column headers stay visible while scrolling rows |
  | Quotes | Search, Tags dropdown, Stars/view filter, Copy CSV |
  | Codebook | Current codebook header (name, author, AutoCode button, Remove) — swaps as you scroll past frameworks |
  | Analysis | Current signal card group title (e.g. "Section × Sentiment") — swaps as you scroll past grids |

- Codebook and Analysis use **contextual sticky headers** — the toolbar content changes as you scroll past section boundaries (iOS `UITableView` grouped-style section headers: the next section pushes the current one up). Pure CSS via `position: sticky` with the right `top` offset
- Sticks below the nav tabs, above scrollable content

### Right sidebar (tags)

- Stays Quotes-only, unchanged for now

### Analysis heatmap — rotated sentiment badge headers

- Rotate the sentiment `<Badge>` pills in column headers (the tag grid headers already use `.heatmap-col-label` with `-30deg` rotation at 56px fixed column width — follow this pattern)
- **Badges keep their visual identity** — pill shape, background colour, border-radius, monospace text. The user must recognise them as the same sentiment pills used on quotes, in the tag sidebar, and on signal cards. The rotation is a layout trick, not a redesign
- Columns shrink from ~100px+ (horizontal badge width for `satisfaction`) to ~56px each, saving ~300px+ across 7 columns
- **Experiment first** in `docs/mockups/` before committing to production

### Sessions table

- Needs layout redesign to work narrower (currently needs ~900px with thumbnail + sentiment + journey columns)
- Designing in Figma — details TBD

### Codebook badges

- Long tag names (`spatial correspondence`, `knowledge-based mistake`, `perceived affordance`) wrap to two lines inside their pills at narrow widths
- Functional but not fine — needs attention
- Approach TBD

### Global min-width

- Single value on body/main container, applied to all tabs identically
- Number determined after Figma design and responsive experiments land
- Currently **no `min-width` is set anywhere** (body, html, `#bn-app-root`, article, `.layout`)
- Only width constraint today: `--bn-max-width: 52rem` (832px) as a ceiling on `<article>`

## Current architecture (what changes)

> **Superseded by the post-script (15 Oct 2026).** "Current" below means 4 Mar 2026.
> Since then the left column of the table has flipped for the first four rows:
> `SidebarLayout` is active on four lenses and renders an inert rail on the rest,
> pin state is one persisted `tocMode`, and the left panel is a slot. The last two
> rows still describe `main`. Kept as the baseline.

| Current | New |
|---------|-----|
| `SidebarLayout` wraps only `/report/quotes/` | Becomes global — wraps `AppLayout` or merges into it |
| `SidebarStore` pin state is Quotes-scoped | Pin state becomes global (persists across tab switches) |
| 5-column CSS grid is Quotes-only | Left rail + left sidebar become global; right rail + right sidebar stay Quotes-only |
| Left sidebar content hardcoded as `TocSidebar` | Becomes a slot/router-aware component rendering per-tab content |
| No sticky toolbar band | New component at consistent depth on every tab |
| No body/container `min-width` | Single global `min-width` |

## Key files

- `frontend/src/components/SidebarLayout.tsx` — the sidebar layout, active on Quotes, Sessions (browser), Codebook and Signals, inert elsewhere. _15 Oct 2026: this line said `layouts/SidebarLayout.tsx`; the file has always been in `components/`, and `layouts/` holds `AppLayout.tsx`._
- `frontend/src/contexts/SidebarStore.ts` — sidebar state (open/width/hidden groups), and `fitPanels`, the fit to width
- `bristlenose/theme/organisms/sidebar.css` — 6-column grid CSS (rail, left panel, centre, minimap, tags, tag rail; it was 5 columns when this was written)
- `frontend/src/components/TocSidebar.tsx` — the Quotes left panel (what it lists: [design-sidebar.md](design-sidebar.md))
- `frontend/src/components/TagSidebar.tsx` — current right sidebar content (tag filter)
- `frontend/src/islands/SignalsPage.tsx` — heatmap grid with badge headers
- `bristlenose/theme/organisms/signals.css` — heatmap CSS (rotated headers pattern exists for tag grids)
- `bristlenose/theme/atoms/badge.css` — badge styling
- `bristlenose/theme/tokens.css` — `--bn-max-width`, sidebar width tokens

## Open questions

1. What goes in the Project tab sidebar?
2. Exact default sidebar width (same for all tabs) — _answered: 240 px, one `tocWidth` for every lens (post-script)_
3. Slide-over dismiss behaviour — click-outside? click heading? both? — _answered: mousing out closes it; a heading click leaves it open (post-script)_
4. Does sidebar content swapping feel natural across tab switches, or does it need a transition?
5. Sessions table redesign details — _answered: a container-query grid, 6 Aug 2026 (post-script)_
6. Codebook badge wrapping fix approach
7. Final `min-width` value

## Approach

1. **Figma designs first** (in progress)
2. **Standalone mockup** in `docs/mockups/` for slide-over / slide-out interaction
3. **Heatmap rotation experiment** (CSS-only, can run independently)
4. **Sessions table experiment** (after Figma design)
5. **Implementation** — once mockups feel right, plan the real component/CSS work

## Dependency chain

The responsive work on individual pages isn't optional polish — it's a prerequisite for the global sidebar. The sidebar consumes ~250–280px. If Sessions currently needs ~900px *without* a sidebar, it would need ~1150px *with* one — wider than a 13" MacBook.

**Narrow the pages → add the sidebar → set the min-width.** All three are one piece of work.
