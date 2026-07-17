# Signal grid — the participant × section/theme matrix, dashboard-scale

**Status:** Design **settled** (working session, 17 Jul 2026), parked with the rest of this
effort (post-TF). The two mockups are **CSS-correct and data-correct** — ready to float into
the total-page dashboard mock. Companions: [data-density.md](data-density.md) ·
[lineage.md](lineage.md) · [brief.md](brief.md).

**Mockups** (flat in `docs/mockups/`, so they auto-list in the dev About→Design tab):
- **[dashboard-signal-grid.html](../mockups/dashboard-signal-grid.html)** — **the widget.** Both
  panes, all interactions, the settled encoding.
- **[dashboard-heatmap-encoding-collision.html](../mockups/dashboard-heatmap-encoding-collision.html)**
  — the **evidence** for the single biggest decision (hue = sentiment, not residual). Keep it; it's
  the argument, not a throwaway.

---

## The job

A **dashboard-scale reduction of the analysis-lens heatmap**: which participants said what,
where, and how they felt — **glanceable, orienting, clickable through to the quotes.** It is
**not** a second analysis lens. Orientation is the job; the lens is the deep read. Lineage:
[`dashboard-10-ideas.html`](../mockups/dashboard-10-ideas.html) §5b already recorded the verdict
— *"the dashboard slot goes to 05's axes, at 5b's scale"* — and this is that, built on real tokens.

## Data — nothing new is invented

Every number is already in shipped structures. **No new pipeline pass, no LLM, no new maths.**

- A `MatrixCell` already carries `participants: dict[pid→count]` and `intensities` — the participant
  axis is inside every cell ([analysis/models.py](../../bristlenose/analysis/models.py)).
- `build_matrix_from_contributions(...)` is already dimension-agnostic
  ([analysis/generic_matrix.py](../../bristlenose/analysis/generic_matrix.py)) — feed it
  `rows=sections/themes, cols=participants` and it's a re-parameterisation.
- `AnalysisResult` already ships **both** `section_matrix` and `theme_matrix`.
- Residual = the **shipped** `adjustedResidual()` / `heatCellStyle()`
  ([islands/AnalysisPage.tsx:146](../../frontend/src/islands/AnalysisPage.tsx)), ported verbatim
  into the mockup JS.

## The encoding (settled)

- **Rows = sections/themes** (labelled); **columns = participants.** Transposed from the lens so the
  matrix **merges into brick-3's** Sections | Themes panes rather than floating as a separate widget.
- **Hue = the sentiment chip.** The **one canonical map**: the built-in codebook
  `sentiment.yaml` (`colour_set: sentiment`) → the `--bn-sentiment-*` tokens. **Seven-way
  categorical, in fixed order** (frustration · confusion · doubt · surprise · satisfaction · delight
  · confidence) — **not** a red↔green diverging ramp. Surprise is deliberately neutral. Depth must
  read **within** a hue.
- **Cell depth (background) = quote count.** Pale chip `-bg` → deeper chip, **capped ~60%** so the
  dot keeps contrast. Both ramp endpoints are the chip's own two colours (`-bg` and full) — no mixing
  against page-white; nothing in the grid can show a colour the codebook didn't define.
- **Inset circle area = residual** (over-representation). **Area, never radius** (`r = √value` — else
  a 2× value looks 4×). The **count option and its switcher were dropped** — decided, not a toggle.
- **Under-representation has no mark — it is the empty cells.** A radius is unsigned; present cells
  are almost all over-represented, so "under" lives in the blanks.
- **Signal cells = a keyline** copied from `.signal-card.bn-selected` (`--bn-selection-border`, the
  system blue), **inset** so the cell footprint — and the column-scan gestalt — is untouched.

## Why hue = sentiment, not residual (the collision)

The lens heatmap colours cells by the **adjusted residual** (green = over-represented, red = under)
— a chi-square *coverage* statistic, **not a feeling.** On a glanceable dashboard green reads as
"good", so the study's **worst** finding (p1 · Aftercare frustration, wildly over-represented because
only p1 reached it) paints **saturated green.** The collision is **structural, not a corner case** —
6 of 13 filled cells in the IKEA sample. On a sparse participant×section matrix the residual grid is
also **almost monochrome green** (every *present* cell is over-represented), so red/green can't even
carry good/bad. Full evidence in `dashboard-heatmap-encoding-collision.html`.

**Decision:** sentiment on hue; residual demoted to the dot; the click-through to the analysis lens
is a **deliberate, signposted** change of colour-language, not a pretend-continuity.

## Why residual on the dot, not count

Depth already carries count, so **area is a free channel** — putting count on it too would be
redundant (the dot would just echo the background). Residual is **additive**, and it's the antidote
to the *chatty-participant* trap: a chatty participant's high row-total inflates their expected
counts, shrinking the residual on their *non-distinctive* cells. **Proof in the mockup** (IKEA): two
`count = 1` cells — **p2 · Top-nav** (distinctive: only p2 touched that section) shows a **big dot**;
**p3 · Beds browsing** (common: three participants hit it) shows a **tiny dot** — a **~7× size
difference that `count` is blind to.** Caveat: the residual is statistically thin at n≈9 (chi-square
wants expected ≥ 5); it rides on top of the honest count-depth, so the noise is bounded, not the sole
signal.

## Interaction (settled)

- **Hover a cell → lights only its two coordinates**: the **row label** (section/theme) and the
  **speaker badge** (participant), in the **same** selection wash. It does **not** flood the column of
  cells — that lit empty cells and fought the signal keylines. "What it's about" and "who said it",
  nothing else.
- **Tooltip** = the sentiment as its **real `.badge` chip** + `N quote(s) · residual X.XX`. No
  `p · section` header (the highlight already says that), no quote line for now (the data is retained
  in the mockup — re-adding is one line).
- **Click** — **signal cells jump to their card** (analysis lens); **every other cell lands in the
  section/theme quotes, in context of its siblings.** Universal and predictable, and it dissolves the
  "which of N quotes?" problem (you land among all of them). Reuses `TimecodeLink` for the transcript
  and the lens for the signal card — no new navigation plumbing.

## Design-system reuse ledger (import these directly into the total-page mock)

Everything is real tokens / atoms — nothing bespoke:

| Element | Source |
|---|---|
| Sentiment hue + depth endpoints | `--bn-sentiment-{name}` / `--bn-sentiment-{name}-bg` (from `sentiment.yaml`) |
| Tooltip sentiment chip | `.badge` / `.badge-{sentiment}` — [atoms/badge.css](../../bristlenose/theme/atoms/badge.css) |
| Participant column headers | `.bn-person-badge > .bn-speaker-badge--split > .bn-speaker-badge-code` — [molecules/person-badge.css](../../bristlenose/theme/molecules/person-badge.css) |
| Signal keyline | `--bn-selection-border` (from `.signal-card.bn-selected`) |
| Hover highlight (row + badge) | `--bn-selection-bg` + `--bn-selection-border` |
| Residual maths | `adjustedResidual()` — [AnalysisPage.tsx](../../frontend/src/islands/AnalysisPage.tsx) |
| Radius / spacing / mono | `--bn-radius-sm`, `--bn-space-*`, `--bn-font-mono` |

## Deliberately NOT imported

- The lens's **-30° rotated column headers** (`.heatmap-col-label`): a horror show at 30–40px cells
  (they need ~56px). **Columns stay label-less** — the row label + speaker-badge cross-highlight *is*
  the legend, exactly as GitHub's contribution grid works.

## Open for the total-page mock

- **Panes side by side when wide, stack when narrow** (flex-wrap) — matches brick-3. Confirm the
  width threshold in the tessellation pass.
- **Signal keyline colour**: blue (selected-card) is loud against the sentiment fills; the quieter
  resting-grey card border is a one-token fallback — judge in situ once real density is on screen.
- **Dark mode**: the sentiment `-bg` darks are deep/muted, so low-count cells lean on the dot — check
  `count = 1` legibility in dark on the assembled page.
- **No resting sentiment legend** now (it's taught via the tooltip). Fine for an orientation layer;
  confirm it still reads on the full page.
- **Quote in the tooltip**: removed for now, data retained — bring back if the tooltip has room.
- Minor: two dead CSS rules (`.dest`, `.dim-note`) left in the mockup from removed features — harmless,
  sweep on next touch.
