# Design police — every element traced to the system

This is role 2: take the **union** of every graphical element a widget uses across all its
faces (from [data-density.md](data-density.md)) and tie each one, very directly, to the
Bristlenose atomic design system. For each element there are exactly two acceptable
outcomes:

- **(i) Refactor to an official element** — the element already exists as an atom /
  molecule / organism; use it. This is the default and the strong preference.
- **(ii) Flex the system** — the element genuinely needs something that doesn't exist yet
  (a new colour, font size, line width, radius…). Legitimate, but it **must be logged** in
  the delta ledger below, or "flex the system" silently becomes "invent locally" — the
  exact fragmentation this role exists to prevent.

## Sequencing rule

Police **after** the faces settle, on the **union** — not in parallel per element. The
responsive pass creates and destroys elements per face; auditing before the inventory is
final wastes the audit.

## The system to police against (`bristlenose/theme/`)

Five layers (see `bristlenose/theme/CLAUDE.md`):
- **tokens** — colours, spacing, typography as CSS custom properties (`tokens.css`).
- **atoms** — badge, button, input, timecode, toggle, thumbnail.
- **molecules** — person badge, tag input, editable text, sparkline.
- **organisms** — quote card, toolbar, codebook panel, analysis grid.
- **templates** — report, transcript, print layouts.

Typography: four semantic weights (normal 420, emphasis 490, starred 520, strong 700).
Colour: content owns colour; **state** is expressed via semantic colour; every colour
token is `light-dark()`. Sentiment palette is a fixed semantic set — reuse it, don't
reinvent per widget.

## Where the pressure will come from

The heatmap-family widgets (co-occurrence matrix, friction heatmap) are the likeliest to
force outcome (ii) — a **sequential / diverging colour ramp** for cell intensity may not
exist in tokens yet. That's why they're first in the Phase-1 order: settle the ramp once
and amortise it across every later widget that needs one. Curves (saturation) may force a
thin **stroke-weight** token. Log both if they materialise.

---

## Ledger — design-system deltas

_Every deliberate extension: the new token, the widget that forced it, the justification,
and the end-state decision (promote into `tokens.css` as a real atom / reject / scope-local).
Empty = the goal (everything mapped to existing atoms)._

| Delta (proposed token) | Forced by | Justification | Decision |
|---|---|---|---|
| _(none yet)_ | | | |

## Promotion at the end

When the set is locked, each accepted delta is either promoted into `bristlenose/theme/`
as a first-class atom/token (with the usual review) or rejected and refactored away. No
delta ships as a widget-local one-off — that's the whole point of the ledger.
