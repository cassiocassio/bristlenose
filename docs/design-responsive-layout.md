# Responsive Quote Grid — Design & Implementation Notes

**Status:** Mockup complete, not yet implemented.
**Mockup:** `docs/mockups/responsive-quote-grid.html`
**Date:** 19 Feb 2026

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

#### Add to `_THEME_FILES` in `render_html.py`

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

Transcript pages already have a 1100px breakpoint for annotation margin placement. Verify this works correctly when the article width is no longer capped at 52rem. May need to adjust the annotation column to stay within a readable width.

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
3. **HTML:** Three radio buttons in the Settings panel (`render_html.py` lines 508-523), name `bn-density`, values `compact`/`normal`/`generous`
4. **JS:** New `density.js` module following `settings.js` pattern:
   - `createStore("bristlenose-density")` for localStorage persistence
   - `_applyDensity(value)` sets `data-density` attribute on `<html>`
   - `initDensity()` in boot sequence (add to `_bootFns` in `main.js`)
5. **CSS selectors:**
   ```css
   html[data-density="compact"] article { font-size: 0.875rem; }
   html[data-density="generous"] article { font-size: 1.125rem; }
   ```
6. **Files:** `tokens.css`, `organisms/settings.css`, new `js/density.js`, `render_html.py`, `main.js`
7. **Add to `_THEME_FILES`** and **`_JS_FILES`** in `render_html.py`

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
| `bristlenose/stages/render_html.py` | Add `responsive-grid.css` to `_THEME_FILES` |

No HTML template changes. No JavaScript changes. No Python logic changes.

## Files touched (density setting)

| File | Change |
|------|--------|
| `bristlenose/theme/tokens.css` | Add `--bn-content-scale` token |
| `bristlenose/theme/organisms/settings.css` | Density radio button styles |
| `bristlenose/theme/js/density.js` | **New file** — density preference module |
| `bristlenose/theme/js/main.js` | Add `initDensity` to `_bootFns` |
| `bristlenose/stages/render_html.py` | Add density radios to settings HTML, add `density.js` to `_JS_FILES` |

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
