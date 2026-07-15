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
- **edo** falls out of the `data-color-theme="edo"` chrome swap (all `--bn-colour-*`; sentiment
  hues are shared, so they don't move — see RESOLVED below).
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

## RESOLVED — "edo" is a shipped palette, and it IS a clean token swap

edo already exists end-to-end (`bristlenose/theme/colors/palette-edo.css`; CHANGELOG "Palette
picker + Edo, end to end"). It's the Edo-period Japanese art palette — **Prussian-blue accent**
(`#0f5c9e` light / `#4d9fe0` dark, bero-ai undertone), **washi paper-white ground** (`#fdfbf7`),
**passport-navy ink** (`#1b2230`), warm parchment borders/surfaces, warmer paper in dark. Desktop
default; web default is `default` (Apple system-blue `#007aff`). Swapped by the
`data-color-theme="edo"` attribute on `<html>` (CLI `--palette edo`, env `BRISTLENOSE_PALETTE`).

**It's a pure chrome swap — exactly what makes Phase 2 mechanical:**
- edo overrides only `--bn-colour-*` **chrome** tokens (bg, text, muted, border, accent,
  surfaces). Layout, type, spacing are untouched.
- **Sentiment hues are SHARED** — `--bn-sentiment-*` live in `tokens.css`, *not* in the palette
  files, so a co-occurrence cell's colour is identical in default and edo. edo changes the
  *frame and ground*, never the signal. (Verify: switching Scheme in the gallery must move the
  labels/borders/paper but leave the cell hues put.)
- Dark mode is `light-dark()` on both palettes. So the 2×2 is genuinely free — the gallery
  proves it by toggling the real attribute, not a placeholder.

Known edo caveat (from the palette file): warm surfaces read slightly warmer against the brighter
v1 paper — a surface-harmony pass is a noted follow-up in `palette-edo.css`, not our concern here.

## Where the renders live

Proof renders are faces of the gallery mockup
(`../mockups/dashboard-widget-gallery.html`), toggled by scheme + mode controls — not
separate files. `prefers-color-scheme` drives dark; a scheme control swaps the accent
token. This keeps one source of truth and makes the "falls out of tokens" claim literally
testable by flipping a control.
