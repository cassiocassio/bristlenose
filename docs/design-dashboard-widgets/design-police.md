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

## The hard rule: a deep-linked widget MIRRORS its target component exactly

If clicking a widget takes the user to an item in a lens (a signal card → the Signals lens,
a quote card → the Quotes lens), the widget **must be pixel-identical to that item.** A style
jump on click reads as a bug. So these widgets are **not designed by eye — they are mirrored:**

1. **Read the real component** — both the CSS (`bristlenose/theme/organisms/*.css`) *and* the
   JSX (`frontend/src/…`), to get the exact DOM, class names, tokens, and values.
2. **Copy the rules verbatim**, real class names and all. Don't paraphrase into look-alike
   classes — that's how the divergence creeps in.
3. **Check the element is actually SHOWN.** A class existing in CSS ≠ it being rendered.
4. **The trim (what a narrow dashboard slot shows) is a subset** of the real item, each kept
   element still pixel-identical — never a restyle.

Worked example — **Signals card (15 Jul 2026).** First pass was freelanced by eye and wrong on
*every* element: card `radius-lg`+`quote-bg`+asymmetric padding (real: `radius-sm`+`--bn-colour-bg`
+`space-lg`); name at `label` size (real: `heading`, 18px, a link, with an uppercase source
eyebrow above it); pattern badge a sans pill weight-600 (real: **mono, uppercase, `radius-sm`,
weight-starred, opacity .9**); metrics a bold bottom row (real: a `label · mono-value · viz`
grid, top-right, with conc-bars + intensity dots). And it showed a **confidence badge that is
`hidden from UI, preserved for future`** in the shipped CSS — pure invention. Rebuilt by mirroring
`.signal-card` verbatim. Lesson: **mirror, don't approximate; and confirm render, not just class
existence.**

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
| `--ramp-1/2/3` (heat weights 30/56/84) | 5a Co-occurrence | Cell depth = quote count needs a 3-step intensity ramp. The 10-ideas版 hardcoded raw hex (`#93c6a1`…) — a leak. Replaced with `color-mix(in oklab, var(--sent-*) calc(var(--w)*1%), var(--bn-surface))`: theme-aware, uses only existing sentiment + surface tokens. **No new *colour* token.** The three *weights* are the only new values. | PENDING — promote weights to `tokens.css` as `--bn-ramp-*`, or keep widget-local? Any other heat/depth widget (friction heatmap, saturation fill) will want the same ramp → leaning promote. |

**Observation — pre-existing un-tokenised colours in the shipped system (not our delta):**
- **Signal `confidence-*` badge is `hidden from UI, preserved for future`** (its own CSS
  comment) — so it is NOT part of the signal card and must not appear in the widget.
- **Signal `pattern-*` label IS shown** and hardcodes hex directly in `organisms/analysis.css`
  (e.g. `pattern-gap` `light-dark(#fee2e2,#450a0a)`) rather than reading tokens — palette-blind,
  so it can't get an Edo-specific treatment today. Replicated verbatim in the gallery. Candidate
  future tokenisation — *not* blocking this effort.
- **Coverage bar colours ARE tokenised and palette-specific** (`--bn-coverage-*` differ in
  `palette-default` vs `palette-edo`) — the model to follow. Coverage is the gallery's proof
  that palette-specific *data* colour works, distinct from shared sentiment.

**Mirror-audit — all four active widgets now match their shipped component (15 Jul 2026):**
- **Verbatim** → `.bn-featured-quote` (global-nav.css). Fix: quote text is `label` (13px) not `body`;
  footer uses the real mono `.badge` atom + `.badge-<sentiment>`; multiply is `.bn-featured-row` (3-up, 5 at wide).
- **Coverage** → `.bn-coverage-box` (coverage.css). Fix: bar is **8px** tall (was 1.6rem), `radius 4px`;
  legend dots are **round 8px** (was 12px square); values use `.bn-coverage-legend-value`.
- **Sections | Themes** → `.bn-dashboard-pane--pair` + `.bn-dashboard-nav`. Fix: links are **accent**-coloured
  (were text+hover-accent); shared border, no divider; **no counts** (shipped shows none — counts are a proposed addition).
- **Signals** → `.signal-card` (see worked example above).

**Resolved (outcome i — mapped to existing system):**
- Cell hue → `--sent-*` tokens (existing sentiment palette). No new colour.
- Heat depth → `color-mix()` toward `--bn-surface`. Technique, not a token. `color-mix` is
  Baseline (Safari 16.2+) so WKWebView-safe at the macOS-15 floor — consistent with the
  autolayout mockup's baseline check.
- Empty cell → `--bn-surface-2` (existing). Empty is information (Scharp), so it must read as a
  faint but present cell, not blank.

## Promotion at the end

When the set is locked, each accepted delta is either promoted into `bristlenose/theme/`
as a first-class atom/token (with the usual review) or rejected and refactored away. No
delta ships as a widget-local one-off — that's the whole point of the ledger.
