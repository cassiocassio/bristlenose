# Lineage — the experiments that led here

This effort isn't a fresh start; it's the convergence point of a run of dashboard
experiments across Feb–Jul 2026. Each explored one facet in isolation. This doc records
what each contributed and what was chosen or discarded, so the gallery inherits decisions
rather than re-litigating them.

Read chronologically — the thread is: *what data is even available* → *does it survive
real cardinalities* → *individual widget explorations* → *the idea pool* → *the layout
framework* → **this effort** (intrinsic widget design) → tessellation.

---

## 1 · Content inventory — what data exists at all
**[../design-dashboard-stats.md](../design-dashboard-stats.md)** · Feb 2026 · doc

A priority-ranked inventory of pipeline data the dashboard *could* show but doesn't
(per-participant stats, sentiment breakdown, top signals, coverage, journeys, topic
segmentation, run metadata). **Contributed:** the raw material — the superset every widget
draws from. **Superseded by:** the richer idea pool (below) folded most of these into
concrete widgets; the flat inventory is now a reference, not a plan.

## 2 · Cardinality stress — does a list survive real data?
**[../mockups/dashboard-theme-list-stress-test.html](../mockups/dashboard-theme-list-stress-test.html)**
· Feb 2026 · mockup

Stress-tested the theme/section nav list against long theme names and high theme counts.
**Contributed:** the discipline that a widget's face is decided by *true cardinalities*,
not invented sample data — now a first principle (cardinality stress cases are
non-deferrable). Feeds [data-density.md](data-density.md).

## 3 · Coverage widget exploration
**[../mockups/dashboard-coverage-box.html](../mockups/dashboard-coverage-box.html)** ·
Feb 2026 · mockup

Focused study of the transcript-coverage widget (pct in report / moderator / omitted).
**Contributed:** the "bounded strip, max useful width ≈720, don't full-bleed" behaviour —
the canonical example of the *stop* answer to extra width. Becomes brick 8.

## 4 · Heatmap explorations
**[../mockups/mini-heatmaps-dashboard.html](../mockups/mini-heatmaps-dashboard.html)** ·
Mar 2026 · mockup

Explored small-multiple heatmaps (section × sentiment, co-occurrence). **Contributed:** the
visual grammar behind the friction heatmap and co-occurrence matrix — the widgets most
likely to force a design-system flex (a sequential/heat ramp that may not exist in tokens
yet). This is why they're sequenced *first* in Phase 1.

## 5 · The idea pool — 10 widget ideas
**[../mockups/dashboard-10-ideas.html](../mockups/dashboard-10-ideas.html)** · Jul 2026 ·
mockup

Ten richer widget concepts, each tagged with a fate: ridgeline *(superseded)*, sentiment
tape *(promoted)*, kudos/kvetch order book, ambivalence portraits *(parked)*, co-occurrence
matrix, friction heatmap, session small multiples, hero quote, fingerprint + KWIC,
saturation curves *(developed)*. **Contributed:** the candidate set. **Reconciled into:**
the 8-brick running order (see [brief.md](brief.md) — most ideas already have a brick home;
the two loose ends are sentiment tape → Session lens, and fingerprint/KWIC → split).

## 6 · The tessellation framework
**[../mockups/dashboard-autolayout.html](../mockups/dashboard-autolayout.html)** · Jul 2026
· mockup

The layout system: RAM auto-fill grid, fixed-row-height **bricks**, three container-query
**faces** per brick, *stretch / stop / multiply* answers to extra width, live resizable
stage + zoom to preview big-monitor layouts on a laptop. WKWebView-verified (CQ / clamp /
cqi are Baseline ≤ macOS 13). **Contributed:** the brick contract every widget signs, and
the decoupling insight that makes *this* effort possible — a widget promises shape + faces;
layout resolves pixels later. **This is Phase 3's surface** — the gallery's locked widgets
return here for running-order + packing.

## 7 · This effort — intrinsic widget design
**This folder** + **`../mockups/dashboard-widget-gallery.html`** (forthcoming) · Jul 2026 →

Takes each brick from the running order and designs it *intrinsically*: data ladder, earned
faces, design-system compliance, colour/mode proof — all decoupled from tessellation. The
missing middle between "we have a layout framework" and "we can play the tessellation game
for real."

---

## The through-line

Three concerns kept getting entangled across the earlier experiments — *what data shows*
(stats, stress-test), *how it looks* (heatmaps, coverage box), and *where it goes*
(autolayout). This effort's whole contribution is **separating them**: intrinsic design
(here) vs tessellation (Phase 3, autolayout), with the design-system audit and the
theme-matrix proof as the two guardrails that keep intrinsic design honest.
