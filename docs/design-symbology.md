# Symbology — § ¶ ❋ Prefix Symbols

## What this is

A visual layer that prefixes report elements with typographic symbols to
distinguish the three data types at a glance:

| Symbol | Meaning | Unicode |
|--------|---------|---------|
| §      | Section | U+00A7  |
| ¶      | Quote   | U+00B6  |
| ❋      | Theme   | U+275B  |

Symbols are **decorative wayfinding** — they help the eye, not the brain.
They should be subtle enough to ignore when reading, visible enough to
notice when scanning.

## Status

**Experimental — mockup only.** No production code yet.

- Mockup: `docs/mockups/mockup-symbology.html` (self-contained, all CSS inline)
- Branch: `symbology` (worktree: `bristlenose_branch symbology`)
- This idea might go nowhere. The mockup exists to judge the visuals before
  committing to production changes.

## Design decisions (settled)

### 1. CSS method: absolute positioning, no padding

We evaluated five CSS approaches to hanging punctuation and chose
**absolute positioning with no padding-left on the parent**.

The pattern:

```css
.sym-hang {
    position: relative;         /* positioning context only */
}                               /* NO padding-left */

.sym {
    position: absolute;
    left: calc(-1 * var(--bn-sym-gutter));   /* hangs LEFT of content edge */
    width: var(--bn-sym-gutter);             /* 1.5ch */
    text-align: center;
    color: var(--bn-colour-icon-idle);
}
```

```html
<h2 class="sym-hang"><span class="sym">§</span> Sections</h2>
```

**Why no padding-left:** An earlier version (v1) used `padding-left` on
`.sym-hang` to reserve a gutter. This shifted the heading text rightward
by 1.5ch relative to sibling elements (h3, p, description text). In tables
this was barely visible because each cell manages its own padding. But in
block contexts (TOC, content headings, analysis headings), "Section" started
1.5ch to the right of "Onboarding" below it — breaking the core rule:
*text aligns as if the symbol isn't there.*

The current approach (v2) uses `position: relative` only. The symbol hangs
left of the natural content edge. The space for the symbol comes from
ancestor padding (page body, report wrapper, table cell padding) — not from
the element itself.

**Why not the other four methods:**

1. **CSS `hanging-punctuation`** — Safari-only (~14%), wrong glyphs (only
   standard typographic punctuation, not §/¶/❋). Unusable.
2. **`text-indent: -Xch`** — First-line only, breaks in flex, magic numbers.
3. **Negative margin on inline-block** — Fragile in flex/grid (changes item
   sizing, clipped by overflow: hidden). Our v0 approach; broke when we
   changed container padding.
4. **Two-column grid** — Forces HTML restructuring. Can't just add a class
   to an `<h2>`.

Sources in the mockup CSS comment block.

### 2. Colour: `--bn-colour-icon-idle` (#c9ccd1 / #595959)

Symbols use `--bn-colour-icon-idle` — one step lighter than `--bn-colour-muted`.
Evaluated all 7 design-system greys at all 8 font sizes where symbols appear
(grey swatch section in the mockup). `icon-idle` is subtle enough to not
compete with heading text, visible enough to not vanish at small sizes.

Dark mode: `#595959` (from tokens.css).

Future consideration: hover interactions that darken the symbol (e.g. to
`--bn-colour-muted` or `--bn-colour-text`) when the parent element is
hovered. Not implemented yet.

### 3. Four CSS classes

| Class | Purpose | Position? |
|-------|---------|-----------|
| `.sym-hang` | Parent element (h2, th, h3). Positioning context only. | `position: relative` |
| `.sym` | Symbol span. Hangs left of content edge. | `position: absolute` |
| `.sym-inline` | Flat variant for cramped contexts (tabs, stat cards, tooltips). No hang. | None |
| `.sym-faded` | Modifier — halves opacity. Stacks with `.sym-inline`. | None |

### 4. Design token

```css
--bn-sym-gutter: 1.5ch;   /* width of the hanging gutter */
```

`ch` unit ties the gutter to the font's character width. Scales naturally
with font-size changes. 1.5ch gives the symbol room to breathe without
feeling detached from the text.

### 5. Ancestor space requirement

Because `.sym-hang` adds no padding, the symbol hangs into the **ancestor's**
padding or margin. If the symbol is clipped, add `padding-left` or
`margin-left` to a **container ancestor**, not to `.sym-hang` itself.

In the Bristlenose report:
- Page body has `padding: 2rem`
- `.bn-dashboard-pane` has `padding: var(--bn-space-lg)`
- Table `th` has `padding: 0.6rem var(--bn-space-md)`

All of these provide enough room for the 1.5ch gutter.

## Where symbols appear (13 contexts)

### Hanging (`.sym-hang` + `.sym`)

| # | Context | Element | Font size | Symbol |
|---|---------|---------|-----------|--------|
| 2 | TOC headings | `h2` | 1.1rem | § ❋ |
| 3 | Content section headings | `h2` | 1.35rem | § |
| 4 | Content theme headings | `h2` | 1.35rem | ❋ |
| 6–7 | Dashboard pane table headers | `th` | 0.9rem | § ¶ ❋ |
| 6–7 | Dashboard pane titles | `h3` | 1.1rem | § ❋ |
| 8 | Analysis page headings | `h2` | 1.1rem | § ❋ |
| 10 | Heatmap first-column headers | `th` | 0.75rem | § ❋ |

### Inline (`.sym-inline`)

| # | Context | Font size | Symbol | Notes |
|---|---------|-----------|--------|-------|
| 1 | Nav tab bar | 0.88rem | ¶ | `.sym-inline` — no hang in tabs |
| 5 | Stat card labels | 0.8rem | § ¶ ❋ | `.sym-inline.sym-faded` |
| 9 | Signal card source labels | 0.7rem | § ❋ | `.sym-inline.sym-faded` |
| 11 | Transcript margin tooltips | 0.75rem | § ❋ | `.sym-inline.sym-faded` |
| 12 | Codebook tooltips | 0.75rem | ¶ | `.sym-inline.sym-faded` |

### Plain text (no CSS)

| # | Context | Notes |
|---|---------|-------|
| 13 | Markdown/text output | `## § Sections` — symbol is just a character prefix |

## Integration plan — rolling it into production

**Approach:** Add a few atoms/elements at a time. Each step should be a
small, self-contained commit that can be reverted independently.

### Phase 1: Token and atoms (no visible change)

1. Add `--bn-sym-gutter: 1.5ch` to `bristlenose/theme/tokens.css`
2. Create `bristlenose/theme/atoms/symbology.css` with `.sym-hang`, `.sym`,
   `.sym-inline`, `.sym-faded`
3. Add `atoms/symbology.css` to the CSS concatenation order in `render_html.py`
4. **Test:** render a report, confirm no visual change (atoms exist but
   nothing uses them yet)

### Phase 2: Headings (highest-impact, most visible)

5. Content section headings (`h2`) — `render_html.py` templates
6. Content theme headings (`h2`) — same templates
7. TOC headings — TOC generation in `render_html.py`
8. **Test:** render a report, check alignment. The `--bn-space-lg` page
   padding should provide room for the symbol. Check dark mode too.

### Phase 3: Dashboard tables

9. Dashboard pane titles (`h3`)
10. Dashboard pane table headers (`th`)
11. **Test:** symbols should hang into the pane's `var(--bn-space-lg)` padding

### Phase 4: Analysis page

12. Analysis section headings (`h2`)
13. Heatmap first-column headers (`th`)
14. Signal card source labels (`.sym-inline.sym-faded`)
15. **Test:** check that analysis.html renders correctly

### Phase 5: Nav, stats, tooltips

16. Nav tab bar (`.sym-inline` — Quotes tab only)
17. Stat card labels (`.sym-inline.sym-faded`)
18. Transcript margin annotation tooltips
19. Codebook tooltips
20. **Test:** full regression — all tabs, dark mode, export

### Phase 6: Markdown/text output

21. `bristlenose/utils/markdown.py` — prefix `§` / `¶` / `❋` in plain-text
    section/theme/quote headings
22. **Test:** generate markdown report, check formatting

### Phase 7: Cleanup

23. Remove swatch section and debug red line from mockup
24. Update `bristlenose/theme/CLAUDE.md` with symbology conventions
25. Update `bristlenose/theme/CSS-REFERENCE.md` with atom docs

## Files that will change (production)

| File | What changes |
|------|-------------|
| `bristlenose/theme/tokens.css` | Add `--bn-sym-gutter` token |
| `bristlenose/theme/atoms/symbology.css` | New file — 4 CSS classes |
| `bristlenose/theme/render_html.py` | CSS concat order; `<span class="sym">` in templates |
| `bristlenose/analysis/render.py` | Analysis heading and heatmap templates |
| `bristlenose/theme/js/*.js` | If any JS generates headings dynamically |
| `bristlenose/utils/markdown.py` | Plain-text symbol prefixes |
| `bristlenose/theme/CLAUDE.md` | Document conventions |
| `bristlenose/theme/CSS-REFERENCE.md` | Atom reference |

## Gotchas to watch for

- **Overflow clipping:** If any ancestor has `overflow: hidden`, the
  negative-positioned symbol may be clipped. The report doesn't use
  `overflow: hidden` on content containers, but check after each phase.
- **Print/PDF:** `position: absolute` should print fine, but test.
- **RTL:** Not currently supported by Bristlenose, but if added later,
  the hang direction would need to flip (`right` instead of `left`).
- **`ch` unit variation:** `1.5ch` depends on the font's `0` character
  width. With Inter (the report font), this is consistent. If the font
  stack falls through to a system font, the gutter width may shift slightly.
- **Hover darkening (future):** When implementing hover states, the
  transition should be on `.sym` / `.sym-inline`, not on `.sym-hang`.
  The parent hover can trigger a child colour change via
  `.sym-hang:hover .sym { color: var(--bn-colour-muted); }`.
