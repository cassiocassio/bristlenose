# Signals lens — future phases

_Last updated: 13 Sep 2026_

This document captures ideas for the analysis page beyond Phase 3. **The first step is to use what we have on real studies before adding interactivity** — the current signal cards + heatmaps need to prove their value in practice before we layer on controls.

> **That first step happened, and it settled things this document predates.** A
> redesign pass on 13 Sep 2026 worked the lens against nine real trial projects
> and settled seven questions; see *Settled — 13 Sep 2026* immediately below.
> Where this document and that section disagree, the section wins. The panels,
> the measurements and the abandoned options live in
> `docs/mockups/signals-sidebar-row-layouts.html`, which carries its own decision trail — read that before re-deriving
> anything here.

---

## Settled — 13 Sep 2026, and SHIPPED

Twelve decisions, each drawn as a panel before any code moved. Codes refer to
benches in the mockup named above. The first seven are the card and the
navigation; the rest settled while building.

**Built on 13 Sep 2026, all of it.** `utils/signalDedup.ts` holds the rule and
the grouping; `SignalsPage` merges the two signal sources, de-duplicates once,
and renders one run of locations; `SignalsSidebar` groups the same list through
the same helper; `SignalStore` holds one list instead of two. The card's
top right is one hero chip — `SignalHero` in `SignalsPage.tsx`, a real
`<button>` with `aria-expanded` — carrying the group-or-sentiment and the score,
with the four metrics behind it and minimised by default. Both card kinds share
that one right column; the badge stack and the always-open metrics block are
gone, and `.signal-card-badges` with them.

| | decision | panel |
|---|---|---|
| 1 | **A card is a location × a tag group**, and it surfaces that group's tags. Sentiment is a group like any other. | S2 |
| 2 | **Location organises the navigation** — sections and themes, places ranked by strongest signal. | U3 |
| 3 | **A nav row is the elaborated name plus the group as a trailing tinted chip.** No pattern chip, no code pills. | T6b |
| 4 | **The card's top right is one hero chip** carrying group-or-sentiment and score, acting as the control that expands the metrics. | C3, C4, N |
| 5 | **Card text**: location in natural case, two complete sentences with air between claim and evidence. | N |
| 6 | **One card per set of quotes** — walk a location strongest-first, keep a card only if it brings a quote no kept card carries, ties break on quote count. | R2 |
| 7 | **The Sentiment card is exempt from being hidden** — an interim guard while the metric is unfixed. | R4 |
| 8 | **Nav rows wrap, never truncate.** Measured: 90% of rows truncate against a 28-character line. | V1 |
| 9 | **A nameless row is its group chip alone** — no location fallback, no placeholder. | T6b |
| 10 | **Sections and themes interleave, unlabelled.** The Quotes lens still owns the demarcation. | U3 |
| 11 | **The main content follows the navigation** — one run of locations under `.signals-codebook-heading`. | W2 |
| 12 | **Nothing caps the card count.** De-duplication is the bound; `SAFETY_CAP` exists so nothing pathological renders. | — |

**Still open, and the first one blocks ordering:**

1. **Normalising signal strength** so one number compares across codebooks and
   sentiment. Handed to a session of its own — `docs/design-signal-strength.md`.
   It is a maths problem with a semantics problem underneath: *are three
   participants this frustrated about a section the same strength as three
   participants carrying different tags from one Feedback group about the same
   or another place?*
2. **How far down the ranking elaboration runs.** `DEFAULT_TOP_N = 10` in
   `server/elaboration.py`, applied across all codebooks at once, so a location
   with nine cards can only have a handful named. Measured after
   de-duplication: 18 of 76 cards across the trial corpus have no elaborated
   name. A cost decision — every miss is an LLM call.
3. **Does the main content follow the navigation?** Proposed — location-sectioned
   cards matching the nav's sequence, reusing `.signals-codebook-heading` and
   inventing no new heading styles, with today's two flat grids kept as the
   second choice in the view menu. Not drawn yet.

**Thresholds and floors are deliberately not settled here.** `MIN_QUOTES_PER_CELL
= 2` is a volume floor, and whether it is the right one is answered by checking
real interview data against outputs, not by this document. For the record, at the
shipped floor the trial corpus gives 106 cards over 74 locations; at 3, 56 over
47; at 4, 30 over 26.

---

## Current state

_Trued 13 Sep 2026. The Phases 1–3 description this replaced was written for the
standalone `analysis.html`, which the React lens superseded._

The Signals lens is a React tab. It shows:

- **Signal cards grouped by location**, locations ranked by their strongest
  signal, cards ranked within — the same order and the same list the sidebar
  navigates. A card is a (location × tag group); sentiment is a group like any
  other, so `confusion` and `frustration` are tags inside the Sentiment card
- **De-duplicated**: where several cards point at the same quotes only the
  strongest is shown, and the Sentiment card is never hidden
- **Heatmaps in `InspectorPanel`**, a sibling of the cards column — not in it.
  Cells whose card is on the page are clickable and scroll to it
- **Quote expansion** — each card shows its top quote, expandable to all
- **Dark mode responsive** — OKLCH heatmap colours recalculate on theme toggle

No filters and no sort controls. The view menu — strongest signal, by codebook,
sections and themes — is designed and deliberately not shipped: one better lens
rather than a menu of equals.

> **The Section × Sentiment + Theme × Sentiment dual heatmap is the user-facing surface of the two-axis quotes-page model** validated in `experiments/thematic-spike/FINDINGS.md` (*"Two-axis quotes page"*). Sections answer "what's happening on this surface my team owns?"; themes answer "what's the cross-cutting concern that demultiplexes across teams?". Both needed; neither subsumes the other. The signal-cards architecture is the *deductive* (codebook-driven, action-oriented) complement to s11's *inductive* (Braun & Clarke, orientation-focused) themes — see FINDINGS *"Two methodological traditions, one product"*.

---

## Next step: explore before building

> **Superseded — this step happened on 13 Sep 2026.** The banner at the top of
> this document and §*Settled — 13 Sep 2026* record what the pass against nine
> real trial projects decided. The questions below are kept as the baseline they
> were answered against; they are not work owed.

Before adding controls, use the Signals lens on 2–3 real studies and observe:

- Do the top-ranked signals match what a researcher would prioritise?
- Is the heatmap useful for discovery, or just confirmation?
- Does the composite formula weight the right things?
- Are 12 signals too many? Too few?
- What's the first thing a researcher wants to do after seeing the page?

The answers will determine which Phase 4 features actually matter.

---

## Two-pane vision

_Superseded in part, 13 Sep 2026: **the heatmaps are not the navigation.**
Location is — sections and themes, ranked by strongest signal (decision 2
above). The grid-as-selector idea below survives as a filtering affordance and
is worth building on its own merits; the claim that it becomes the primary
navigation does not. The rest of this section is kept for the interaction
patterns it works out._

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
- **Signal detection**: may need different metrics — concentration ratio assumes exclusive categories, but user tags overlap _(this is the normalisation question; `docs/design-signal-strength.md` owns it)_

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

1. ~~Does the composite signal formula feel right on real data?~~ **Answered, 13 Sep 2026: no.** Its leading factor is a lift whose ceiling is table shape, and the sentiment framework has one column, so its concentration is structurally 1.00 in every sentiment cell of every project — mute exactly where it matters. Owned by `docs/design-signal-strength.md`.
2. Is 12 the right default for top_n? Should it be configurable? *(Partial answer from `experiments/thematic-spike/FINDINGS.md`: 9–12 is a multi-constraint optimum where psychology, screen scannability, and 1-hour-meeting attention budget converge. But the count is a navigation bound, not a quality bound — data overrules. Configurable would be the principled choice.)*
3. Do researchers actually look at the heatmap, or just the signal cards? _(Unanswered, and the heatmaps are deliberately untouched by the 13 Sep refactor. One known defect, accepted: a cell can be drawn `.has-card` and do nothing — fixed for the cards now rendered, since `signalKeys` is built from the rendered list, but the heatmaps' own improvements are a later release.)_
4. Would a "surprising findings" section (high residual but low composite) catch things the ranked list misses? *(Partial answer from FINDINGS: substantial single-participant clusters — one participant, ≥3 coherent quotes — are often deviant-case insights worth surfacing as first-class output, not folded into "Uncategorised". This is one shape "surprising findings" could take.)*
5. ~~Should signal cards link back to specific quotes in the report, not just the section heading?~~ **Partly answered, 13 Sep 2026:** a card's location is now a link to that place's anchor in the Quotes lens, on both the elaborated and the nameless card. Quote-level deep links are still open.
6. Is the current card expansion (show/hide quotes) enough, or do researchers want quote-level actions (star, annotate, copy)? *(FINDINGS *"Display quote vs evidence quote"* distinguishes one slide-ready quote per cluster from the surrounding evidence — relevant if quote-level actions get added.)*
