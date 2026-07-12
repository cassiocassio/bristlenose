# Design System Reference

Reference docs for contributors working on the Bristlenose UI.

- **style-guide.html** — visual inventory of design tokens, typography, colours, spacing
- **icon-catalog.html** — current icon usage and candidates for the SVG icon set migration
- **compliance-catalogue.html** — token-compliance X-ray: live specimens in all four theme
  combinations (default/edo × light/dark), scored by a two-axis metric — **Coverage** (share of
  themeable declarations that flow through `--bn-*` tokens; 100% = all tokens, 0% = all literals)
  and severity-weighted **Health** (SonarQube-style weighting so a missing colour token counts more
  than an off-scale margin). Magenta toggle lights up everything outside the system; each finding
  expands to source line + defect + fix. The metric borrows from `stylelint-declaration-strict-value`,
  SonarQube, and the design-system adoption literature (Curtis/Omlet/Mews) — see the "How the score
  works" panel. Lens 1 (Quotes) built; Sessions/Themes/Analysis/Codebook to follow. Compliance data
  is a curated snapshot hand-keyed to `file:line` (each finding carries a defect + fix); the
  headline metric is now also **computable from source** — see below.
- **`scripts/audit-css.py`** — the reproducible auditor behind the catalogue's metric. Parses the
  token values, scans every component CSS file, and prints per-file + per-lens Coverage/Health with
  the same formula (reads live CSS, so it reflects fixes automatically). `--json` for machine output,
  `--fail-under N` as a CI gate. Whole-theme baseline at time of writing: 81% coverage / 91% health
  across 55 files (`activity-chip` and `autocode-toast` are the worst offenders at ~30% — bespoke
  raw-hex dark palettes).
