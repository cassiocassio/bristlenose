# Design: Analysis Tab Bottom Inspector Panel (Heatmap)

## Problem

The analysis tab renders signal cards and heatmap matrices on the same scrolling surface. This creates two problems:

1. **Information overload** — cards and matrices compete for attention. The matrices are power-user reference data, but they visually dominate the page and push cards below the fold.

2. **Wonky navigation** — clicking a heatmap cell anchor-jumps to the matching card, scrolling the matrix out of view. The user loses context on both ends — they can't see the matrix while reading the card, and scrolling back to the matrix loses their card position.

## Solution

Move all heatmaps into a **collapsible bottom panel** using the Chrome/Safari DevTools inspector metaphor. Collapsed by default — just a thin handle bar. Signal cards become the clean, readable main content. The matrix is always visible when open, so cell clicks scroll the center pane without losing the matrix.

This is purely vertical layout — coexists with the left nav being built in a separate session.

## Design exploration (3 iterations)

### v1 mockup (`docs/mockups/analysis-inspector-panel.html`)

First cut. "Matrix" title, chevron toggle, Section/Theme split buttons inline in each source tab. UX review found: nested `<button>` inside `<button>` (invalid HTML), hardcoded colours instead of design system tokens, "Sec/Thm" abbreviations.

### v2 mockup (`docs/mockups/analysis-inspector-panel-v2.html`)

Two variants — A (toggle at right end of tab bar) and B (toggle inside body header). Fixed nested buttons, added `light-dark()` sentiment tokens, used typography scale. Still had chevron and "Matrix" title.

### v3 mockup (`docs/mockups/analysis-inspector-panel-v3.html`)

Current design. Major changes from feedback:

- **"Heatmap"** title (singular) — does what it says on the tin
- **Grid icon** (4-square SVG) → × close icon pattern, matching sidebar rails. No chevron
- **Section/Theme toggle moved into the table's top-left `<th>` cell** — Fitts' law: the toggle is right where the eye lands when reading the matrix. Styled as a "you are here" label, not a button
- **Grab handle**: click (`pointerup`) to open, click+drag to resize (3px movement threshold)
- **Shimmer teaching animation** on "Heatmap" label when a card is focused and panel is collapsed (sessionStorage counter, max 3 times)
- **Cards have `tabindex="0"`** and `.focused` class
- Only `.has-card` cells get pointer cursor and hover outline

## Finalized design decisions

### Interaction model

| Action | Trigger | Result |
|--------|---------|--------|
| Open panel | Click grid icon (`pointerup`) | Opens to auto-height |
| Open + resize | Click+drag grab handle | Opens and resizes in one gesture |
| Close panel | Click × icon, or `m` key | Collapses to 28px bar |
| Snap close | Drag below 80px | Collapses |
| Resize | Drag grab handle | Sets manual height (overrides auto-height) |
| Toggle | `m` keyboard shortcut | Route-guarded to `/report/analysis`, `isEditing()` guard |

### Auto-height

On first open (no manual height stored), measure content `scrollHeight` after React render, clamp to `[150px, 0.7 × viewportHeight]`. Once the user drags, their height is stored in localStorage and overrides auto-height permanently.

### Card ↔ heatmap connection

This is the core value — the heatmap gives spatial context to the signal cards.

- **Cell click** → scrolls center pane to matching card + 3px accent glow ring for 1.5s
- **Card focus** → auto-switches panel's active source tab and dimension to match the focused card's heatmap. The heatmap always shows context for what you're looking at
- **Shimmer teaching** → when card focused + panel collapsed, "Heatmap" label shimmers (CSS animation, max 3 times via sessionStorage). Teaches users the connection exists without being annoying

### Column header rotation

The heatmap columns contain single-digit numbers but their headers (sentiment names, codebook tag names) are much wider than the data. All column headers use `-30deg` rotation (CSS already exists in `analysis.css` at `.heatmap-col-label`).

**Regression to fix**: the React `Heatmap` component in `AnalysisPage.tsx` has an `isSentiment` guard that skips the rotation class for sentiment columns. This needs removing — all columns get rotation.

**Alignment fix**: rotated labels need a `margin-left` offset (roughly half cell width, ~28px) so the text visually anchors over the centre of its column, not the left edge. Tune visually at implementation time.

### Tall matrix handling

- **Sticky `<thead>`** — column headers stay visible when scrolling many sections/themes
- **Row label truncation** — `text-overflow: ellipsis`, full text on hover via `title`

### ARIA

- Grab handle: `role="separator"`, `aria-orientation="horizontal"`, `aria-valuenow`/`min`/`max`
- Source tabs: `role="tablist"` / `role="tab"` / `role="tabpanel"`
- Dimension toggle: `role="radiogroup"` with `role="radio"` options

### Open questions / future work

- **Uniform cell sizing** across grids with different column counts — likely `table-layout: fixed` with consistent widths
- **Drag-resize grab handle on left and right sidebar rails** — separate task, same interaction pattern

## Implementation plan

See `/Users/cassio/.claude/plans/vectorized-zooming-puddle.md` for the full implementation spec (store, hook, component, CSS, refactor, tests, verification checklist).

### Files

| File | Change |
|------|--------|
| `frontend/src/contexts/InspectorStore.ts` | **New** — module-level store (SidebarStore pattern) |
| `frontend/src/hooks/useVerticalDragResize.ts` | **New** — vertical drag hook (useDragResize pattern) |
| `frontend/src/components/InspectorPanel.tsx` | **New** — panel component |
| `bristlenose/theme/organisms/inspector.css` | **New** — all panel styles |
| `frontend/src/islands/AnalysisPage.tsx` | Extract heatmaps into panel, card focus → panel sync, fix sentiment rotation |
| `bristlenose/theme/organisms/analysis.css` | Column header offset fix, `.analysis-layout`/`.analysis-center` |
| `frontend/src/hooks/useKeyboardShortcuts.ts` | Add `m` shortcut |
| `bristlenose/stages/s12_render/theme_assets.py` | Register inspector.css |

## Implementation prompt

Paste this into a new Claude Code session to start the build:

---

**Implement the analysis tab bottom inspector panel (heatmap panel)**

There's a plan file at `/Users/cassio/.claude/plans/vectorized-zooming-puddle.md` — read it first, it has the full design spec. Also read the design doc at `docs/design-inspector-panel.md` for problem context and design exploration history. Read the v3 mockup at `docs/mockups/analysis-inspector-panel-v3.html` for visual reference (the plan supersedes the mockup where they differ).

Start by creating a feature branch with `/new-feature inspector-panel`.

**Implementation order:**

1. **InspectorStore** (`frontend/src/contexts/InspectorStore.ts`) — module-level store, same pattern as `SidebarStore.ts`. State: `open`, `height`, `hasManualHeight`, `activeSource`, `activeDimension`. localStorage persistence. Write tests alongside.

2. **useVerticalDragResize** (`frontend/src/hooks/useVerticalDragResize.ts`) — pointer-event state machine adapted from `useDragResize.ts` but vertical. Key difference: 3px movement threshold distinguishes click (open to auto-height) from drag (open and resize). `pointerup` is the event trigger for click-to-open, not `pointerdown`. Snap-close at 80px. Write tests alongside.

3. **inspector.css** (`bristlenose/theme/organisms/inspector.css`) — `.analysis-layout` vertical flexbox, `.analysis-center` scrolling card area, `.inspector-panel` with `var(--inspector-height)`, collapsed state, grab handle, tabs, shimmer keyframe animation. Register in `_THEME_FILES` in `bristlenose/stages/s12_render/theme_assets.py`.

4. **InspectorPanel** (`frontend/src/components/InspectorPanel.tsx`) — the panel component. Collapsed: 28px bar with grid icon (4-square SVG) + "Heatmap" label. Open: grid icon becomes × close, grab handle along top edge, source tabs, scrollable body. Section/Theme toggle lives inside the heatmap table's top-left `<th>` cell (not in the tab bar). Auto-height on first open: measure content `scrollHeight`, clamp to `[150px, 0.7 × vh]`. Once user drags, their height overrides auto-height via `hasManualHeight`. Shimmer teaching: when card focused + panel collapsed, animate "Heatmap" label (sessionStorage counter, max 3 times). Write tests alongside.

5. **Refactor AnalysisPage.tsx** — extract all heatmap rendering into InspectorPanel sources. Build sources array from existing sentiment + codebook data. Wrap page in `.analysis-layout` > `.analysis-center` + `<InspectorPanel>`. Card focus → auto-switch panel's `activeSource` and `activeDimension` to match (call `setInspectorSourceAndDimension()`). Cell click keeps existing behaviour (scroll to card + glow). Update existing tests.

6. **Fix the sentiment column rotation regression** — in `AnalysisPage.tsx`, the `isSentiment` guard on line ~749 skips the `heatmap-col-header` class for sentiment columns. Remove that guard — all column headers should get the rotation. Also in `analysis.css`, add `margin-left` (~28px, half cell width) to `.heatmap-col-label` so rotated labels visually anchor over the centre of their column. Tune the exact offset visually.

7. **Keyboard shortcut** — add `m` to `useKeyboardShortcuts.ts`, route-guarded to `/report/analysis`, with `isEditing()` guard. Add to HelpModal. Update keyboard shortcut tests.

8. **Sticky thead** for tall matrices — column headers stick when scrolling the inspector body.

**Key design decisions (don't deviate):**
- Title is "Heatmap" (singular, not "Matrix" or "Heatmap matrices")
- Grid icon → × close icon (no chevron anywhere)
- Section/Theme toggle goes in the table's empty top-left `<th>` cell — Fitts' law
- `pointerup` for click-to-open, not `pointerdown`
- Collapsed by default, min 150px, max 600px, snap-close 80px
- Card focus auto-switches panel source/dimension to match
- ARIA: `role="separator"` on grab handle, `role="tablist"/"tab"` on source tabs, `role="radiogroup"` on dimension toggle

**Verification:** `cd frontend && npm test`, `cd frontend && npm run build` (tsc), `.venv/bin/python -m pytest tests/`, `.venv/bin/ruff check .`. Then tell me to QA in browser with `.venv/bin/bristlenose serve --dev trial-runs/project-ikea` → `/report/analysis/`.
