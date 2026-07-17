# Dashboard widgets — intrinsic design system

**Status:** Parked exploration (post-TestFlight; remind ~Sept 2026). Not for `main`'s
release line until then — see memory `project_dashboard_autolayout_parked.md`.

This folder is the working home for one effort: designing each **dashboard widget** as a
self-contained thing — its faces (compact / normal / expanded), its essential-vs-luxury
data ladder, and its expression purely in Bristlenose design language — **decoupled**
from where it eventually lands on a dashboard of screen-size X. Tessellation is a
separate, later problem.

## The endgame (and where this effort stops)

The deliverable is a **single super-dense demo**: the whole dashboard, every widget in its
earned faces, assembled and densely tessellated — **CSS-correct** (every element in real BN
design language) and **data-correct** (true pipeline data *shapes* and cardinalities), but
using **fake fixture data** and **wired to nothing**. It is a front-of-house prototype, not
running software: no API calls, no React data binding, no live pipeline.

Wiring it into the React SPA against live project data is a **distinct integration phase**
(Phase 4) — named here so the seam is explicit, but **out of scope** for this effort. This
work ends when the demo is CSS-correct, data-correct, and theme-proofed; integration is a
separate piece of work with its own plan.

## How this folder is organised

| Doc | What it holds |
|---|---|
| [brief.md](brief.md) | The brief + the phased plan. Start here. |
| [lineage.md](lineage.md) | The historical experiments that led here, and what each contributed / discarded. |
| [data-density.md](data-density.md) | Essential-vs-luxury method + the per-widget **data-ladder** ledger (the responsive drop/expand spec). |
| [design-police.md](design-police.md) | Mapping every graphical element to the design system + the **delta ledger** (deliberate extensions). |
| [themes-testing-plan.md](themes-testing-plan.md) | The {edo, default} × {dark, light} × faces proof matrix and what "pass" means. |
| [featured-quotes.md](featured-quotes.md) | The 3-quotes-for-100k-words job, the shipped selection algorithm + why it doesn't bind, the quote-length measurements, and the proposed post-TF trim prompt. |
| [signal-grid.md](signal-grid.md) | The participant × section/theme matrix at dashboard scale: the settled encoding (sentiment hue + count depth + **residual dot**), why hue isn't residual (the colour collision), the interaction model, and the design-system reuse ledger. Two mockups. |

## Where the mockups live (and why not here)

The **gallery mockup is deliberately NOT in this folder.** The dev About→Design listing
(`_discover_design_files()` in `bristlenose/server/routes/dev.py`) globs
`docs/mockups/*.html` **non-recursively** — a file nested in a subfolder is still served
by URL but silently drops out of that auto-listing. So:

- **Gallery HTML → `docs/mockups/dashboard-widget-gallery.html`** (flat, auto-listed).
- **This folder → docs only** (markdown, which the listing ignores anyway).

Don't "tidy" the gallery into this folder — it'll vanish from the About tab.

## Lineage at a glance

`design-dashboard-stats.md` (Feb, content inventory) → `dashboard-theme-list-stress-test`
(Feb, cardinality) → `dashboard-coverage-box` (Feb) → `mini-heatmaps-dashboard` (Mar) →
`dashboard-10-ideas` (Jul, the idea pool) → `dashboard-autolayout` (Jul, the tessellation
framework) → **this effort** (intrinsic widget design) → gallery → back to autolayout for
Phase 3. Full story in [lineage.md](lineage.md).
