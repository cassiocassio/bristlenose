# Themes testing plan — the proof matrix

The eventual deliverable Martin needs to *see* is every widget rendered in **{edo, default}
accent scheme × {dark, light} colour mode × {compact, normal, expanded} faces**. This doc
defines how that matrix is produced and — crucially — reframes it from design work to a
**regression check**.

## The core reframe

You do **not** design 12 states per widget. You design **once**, in a single mode
(proposed: default / light), at each earned face. The remaining three of the 2×2 must then
**fall out of tokens for free**:

- **Dark** falls out of `light-dark()` on every colour token.
- **edo** falls out of swapping the accent token (see the [OPEN] below).
- Semantic sentiment vars carry their own light/dark pairs.

**Clean output across the matrix is the proof the tokens are right.** If a dark or edo
variant needs *any* hand-tuning, that's not design — it's a **raw colour (or hardcoded
size) that leaked past the** [**design police**](design-police.md), and it routes back to
Phase 1 as a bug, not forward as a new state to maintain.

So the matrix is cheap by construction, or it reveals a defect. Either outcome is the point.

## The matrix (per locked widget)

| | compact | normal | expanded |
|---|---|---|---|
| default · light | design here | design here | design here |
| default · dark | *falls out* | *falls out* | *falls out* |
| edo · light | *falls out* | *falls out* | *falls out* |
| edo · dark | *falls out* | *falls out* | *falls out* |

(Rows collapse for single-face or two-face widgets — only render the faces that exist.)

## What "pass" means

- No colour, size, weight, or radius differs from tokens across any cell.
- Sentiment colours read correctly in both modes (contrast holds — note the star-icon
  contrast is a *state differential*, not a WCAG floor; don't over-correct).
- edo is a pure accent swap, not a re-layout.
- Cardinality stress cases hold in every cell.

## [OPEN] — what is "edo"?

Assumed here to be a **second named accent scheme** — i.e. a token swap (change
`--bn-accent` + its wash), structurally identical layout. If that's right, the whole 2×2
stays mechanical and free. **If edo is instead a different *treatment*** (different type,
spacing, or component shapes), then it's not a swap and Phase 2 stops being free — it
becomes a second design pass. Confirm before Phase 2. Default accent today is Apple system
blue `#007AFF` (memory `project_native_seam_alignment_discipline`).

## Where the renders live

Proof renders are faces of the gallery mockup
(`../mockups/dashboard-widget-gallery.html`), toggled by scheme + mode controls — not
separate files. `prefers-color-scheme` drives dark; a scheme control swaps the accent
token. This keeps one source of truth and makes the "falls out of tokens" claim literally
testable by flipping a control.
