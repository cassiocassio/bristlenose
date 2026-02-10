# Analysis Page — Future Phases

_Last updated: 10 Feb 2026_

This document captures ideas for the analysis page beyond Phase 3. **The first step is to use what we have on real studies before adding interactivity** — the current signal cards + heatmaps need to prove their value in practice before we layer on controls.

---

## Current state (Phases 1–3 complete)

The analysis page is a standalone `analysis.html` opened from the toolbar. It shows:

- **Signal cards** ranked by composite signal strength (concentration × agreement × intensity)
- **Section × Sentiment heatmap** — adjusted standardised residuals, clickable cells scroll to matching card
- **Theme × Sentiment heatmap** — same view for cross-cutting themes
- **Quote expansion** — each card shows top quote, expandable to show all
- **Dark mode responsive** — OKLCH heatmap colours recalculate on theme toggle
- **97 tests** across 4 files cover metrics, matrix building, signal detection, serialization, and HTML rendering

No filters, no sort controls, no interactivity beyond expansion and cell-click. This is intentional — explore the experience first.

---

## Next step: explore before building

Before adding controls, use the analysis page on 2–3 real studies and observe:

- Do the top-ranked signals match what a researcher would prioritise?
- Is the heatmap useful for discovery, or just confirmation?
- Does the composite formula weight the right things?
- Are 12 signals too many? Too few?
- What's the first thing a researcher wants to do after seeing the page?

The answers will determine which Phase 4 features actually matter.

---

## Two-pane vision

The analysis page should evolve into a **two-pane layout**:

### Left pane: grids (controls)

The heatmaps move to the left and become the primary navigation. They're no longer just visualisations — they're interactive selectors that control what appears in the right pane.

**Cell-level toggles:**
- Click a cell → toggle it on/off → right pane shows only signal cards matching active cells
- Click an already-active cell → deactivate it
- Visual: active cells keep their colour, inactive cells fade to border grey
- Multiple cells can be active simultaneously (additive selection)

**Row-level toggles:**
- Click a row header → toggle all cells in that row
- "Show me everything about Checkout" = click the Checkout row header
- Active row header highlighted with accent border

**Column-level toggles:**
- Click a sentiment column header → toggle all cells in that column
- "Show me all frustration signals" = click the Frustration column header
- Works across both section and theme grids simultaneously

**Grid interactions:**
- Shift-click for range selection (row or column)
- Click-away or "Clear" link to reset to all-active
- Both grids (section × sentiment and theme × sentiment) operate independently but can be combined — active cells from either grid show their cards

### Right pane: signal cards (results)

The signal cards that currently fill the page move into a scrollable right column. They respond to the grid selections:

- When no cells are active → show all cards (current behaviour)
- When cells are active → show only matching cards, sorted within selection
- Smooth entry/exit transitions (fade or slide) as cards appear/disappear
- Card count shown: "Showing 4 of 12 signals"

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Header + back link                                               │
├────────────────────────┬─────────────────────────────────────────┤
│ Section × Sentiment    │ Signal cards (scrollable)               │
│ ┌──────────────────┐   │ ┌─────────────────────────────────────┐ │
│ │ grid with         │   │ │ Card 1                              │ │
│ │ clickable cells   │   │ │ ...                                 │ │
│ │ rows and columns  │   │ ├─────────────────────────────────────┤ │
│ └──────────────────┘   │ │ Card 2                              │ │
│                        │ │ ...                                 │ │
│ Theme × Sentiment      │ ├─────────────────────────────────────┤ │
│ ┌──────────────────┐   │ │ Card 3                              │ │
│ │ grid with         │   │ │ ...                                 │ │
│ │ clickable cells   │   │ └─────────────────────────────────────┘ │
│ └──────────────────┘   │                                         │
│                        │ Showing 3 of 12 signals                 │
├────────────────────────┴─────────────────────────────────────────┤
```

Left pane is sticky (position: sticky) so grids remain visible while scrolling cards. On narrow viewports, stacks vertically (grids on top, cards below).

---

## Third grid: user-tags and groups

The section × sentiment and theme × sentiment heatmaps use the same tag taxonomy (7 sentiment values). But there's a third dimension: **user-applied tags** from the codebook.

This needs its own grid design — it's not just another copy of the sentiment matrix:

- **Rows**: user-defined tag groups (from codebook)
- **Columns**: individual tags within each group
- **Cells**: quote counts, but the relationship is different — a quote can have multiple user tags, so the contingency table assumptions (independence, expected frequencies) don't hold the same way
- **Signal detection**: may need different metrics — concentration ratio assumes exclusive categories, but user tags overlap

### Open design questions

- Should user-tag signals use the same composite formula, or a different one?
- Do overlapping tags make concentration ratio misleading? (A quote tagged "slow" and "confusing" would be counted in both cells)
- Should user-tag groups be rows or columns? Groups × sentiments? Tags × sections?
- Is the codebook taxonomy stable enough at analysis time? (Users can edit tags after analysis)

This is a separate design exercise. Park it until the two-pane layout proves the grid-as-selector pattern works.

---

## Backlog ideas (pre-two-pane)

These were brainstormed before the two-pane vision. Some become redundant once grids are interactive selectors (e.g. sentiment filter chips are replaced by column-click). Others remain useful. Kept here for reference.

### Sentiment filter chips

Row of inline badge-like chips (one per sentiment). Click to toggle. Hides signal cards and dims heatmap columns for deactivated sentiments. Simpler than a dropdown because there are only 7 sentiments.

_Status: likely replaced by column-click in two-pane layout._

### Source type toggle (Section / Theme / All)

Three-button segmented control to show only section-level or theme-level signals. Hides corresponding cards and heatmap table.

_Status: may still be useful as a quick toggle, or may be replaced by selecting rows in one grid vs the other._

### Sort controls

"Sort by" dropdown: Signal strength (default), Concentration, Agreement, Mean intensity. Reorders signal cards.

_Status: still useful in two-pane layout — sorting within the filtered set._

### Confidence badge restoration

Show Strong/Moderate/Emerging badge on signal cards. CSS exists (hidden). Original concern: misleading next to signal strength number. New placement: next to sentiment badge in the identity column.

_Status: independent of layout — can ship any time._

### Metric explanation tooltips

Upgrade `title` attribute wording on metric labels to explain in plain language. E.g. "This sentiment appears 3.2× more often here than in the study overall."

_Status: independent — can ship any time. Already has basic titles._

### Empty state messaging

"No signals match the current filters" when all filtered out. "No notable patterns detected" when study has no signals.

_Status: needed once any filter exists._

### Keyboard accessibility

Tab navigation for filter controls, Enter/Space toggles, Escape closes dropdowns. ARIA attributes on chips/buttons.

_Status: needed once any interactive controls exist._

---

## Open questions

1. Does the composite signal formula feel right on real data? Or does it over-weight concentration vs agreement?
2. Is 12 the right default for top_n? Should it be configurable?
3. Do researchers actually look at the heatmap, or just the signal cards?
4. Would a "surprising findings" section (high residual but low composite) catch things the ranked list misses?
5. Should signal cards link back to specific quotes in the report, not just the section heading?
6. Is the current card expansion (show/hide quotes) enough, or do researchers want quote-level actions (star, annotate, copy)?
