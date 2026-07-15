# Brief + plan

**Companions:** [lineage.md](lineage.md) · [data-density.md](data-density.md) ·
[design-police.md](design-police.md) · [themes-testing-plan.md](themes-testing-plan.md).
The *tessellation* framework this feeds into:
[../mockups/dashboard-autolayout.html](../mockups/dashboard-autolayout.html).

---

## Brief

### Why now
The autolayout mockup settled the *layout* framework — a RAM auto-fill grid of
fixed-row-height **bricks**, each brick owning three container-query **faces**
(compact / default / expanded), with extra width answered by *stretch / stop /
multiply*. What it does **not** yet have is real widgets: the bricks are populated with
placeholder-grade content. Before tessellation is worth playing for real, each widget
needs to be designed as a self-contained thing — its faces, its essential-vs-luxury data
ladder, and its expression purely in Bristlenose design language.

### The problem this solves
Today the dashboard's graphical elements are ad-hoc: no principled compact/expanded
behaviour, no direct mapping to the atomic design system (`bristlenose/theme/`), and chart
design is entangled with dashboard placement. Those are three separable concerns being
solved at once, badly.

### Goal
A set of dashboard widgets where each one:
1. has **earned** faces — a distinct compact/normal/expanded only where real
   essential-vs-luxury tension justifies it (many widgets will have one or two faces, not
   three);
2. is expressed **entirely in BN design language** — every graphical element traces to a
   named atom/molecule/organism, or to a *logged* deliberate extension of the system;
3. is **provably correct** across accent scheme × colour mode — the full
   {edo, default} × {dark, light} matrix falls out of tokens, not hand-tuning;
4. is designed **independently of where it lands on any dashboard of screen-size X**.

**The endgame is one artifact:** a super-dense demo assembling every widget — CSS-correct,
data-correct (fake fixture data at *true* pipeline shapes and cardinalities), and **wired to
nothing**. It's a prototype you can look at and resize, not running software. Turning it into
live software (React SPA against real project data) is a separate **integration phase**
(Phase 4, out of scope here). This effort stops at the non-wired demo.

### First principles (these drive every downstream call)
- **Decouple intrinsic design from tessellation.** Widgets are designed in an isolated
  gallery, each in its own container-query sandbox. Placement + running order is a
  separate, later problem (Phase 3). The moment a widget's design bends to "but where does
  it go," the decoupling is lost.
- **Faces change data QUANTITY, not element SIZE.** Compact → expanded reveals *more data*
  (rows, columns, annotations) at *constant element size* — never zooms the same content up.
  Fonts and cells stay the same physical size across faces; density comes from quantity. This
  is the cardinal responsive rule — see [data-density.md](data-density.md).
- **Normal first; trim/add is a conversation, not a guess.** Build the normal face fully, then
  decide compact (trim) and expanded (add) *with Martin*, grounded in how researchers use the
  widget — essential-vs-luxury is workflow knowledge, not a designer inference. Count for
  *multiply* widgets is editorial (curated 1/3/5), not `auto-fill`.
- **Same-face is the default; a distinct face is earned.** A widget only gets a separate
  compact/expanded when there's genuine data tension. Default-first, per the framework's
  existing CQ discipline. — see [data-density.md](data-density.md).
- **The colour × mode matrix is a regression check, not design work.** Design once, in one
  mode (default / light). The other three of the 2×2 must fall out of `light-dark()` +
  semantic sentiment vars + the accent swap. A dark version that needs hand-tuning = a raw
  colour that leaked = a bug. — see [themes-testing-plan.md](themes-testing-plan.md).
- **Police the union, once, after the faces settle.** The responsive pass creates and
  destroys elements per face; auditing before the inventory is settled wastes the audit.
  Content/responsive first → then police the union. — see [design-police.md](design-police.md).
- **Flex the system only through a ledger.** Adding a new colour / size / weight is
  legitimate, but every delta is logged centrally, or "flex the system" silently becomes
  "invent locally." — see [design-police.md](design-police.md).
- **Study-level → dashboard; session/time-level → Session lens.** The governing filter for
  what is even *eligible* to be a dashboard widget. (First application: the sentiment tape
  is a per-session timeline → Session lens, not a brick.)

### In scope
- Per-widget **data ladder** (essential → first-to-drop, ranked).
- Per-widget **faces** (1, 2, or 3), with the responsive drop/expand calls.
- Every graphical element mapped to the design system, or logged as a delta.
- One **isolated gallery** surface rendering each widget in its faces, on a real data
  fixture, outside the dashboard grid.
- The {edo, default} × {dark, light} × faces **proof renders** per locked widget.

### Out of scope / deferred (named, not omitted)
- **Tessellation + running order** — Phase 3, separate surface (the autolayout mockup).
- **Interaction + motion states** — hover, tooltip, transitions. Parked; static faces
  first.
- **Empty / overflow states** — parked, *except* **cardinality** stress cases (1 vs 30
  sessions; 2 vs 20 themes), which are not deferrable: they are often *how a widget earns
  "no compact version at all."*
- **Non-dashboard surfaces** — noted where a widget was reassigned (sentiment tape →
  Session lens) but their host surfaces are designed elsewhere.
- **Integration / data wiring** — connecting widgets to the live React SPA and pipeline
  data is **Phase 4, a separate effort**. This whole effort stops at a non-wired demo with
  fake fixture data. The fixture's data *shapes* are correct so the seam to real data is
  clean, but nothing is fetched.

### Deliverables
1. `docs/mockups/dashboard-widget-gallery.html` — isolated per-widget sandboxes.
2. The **data-ladder** ledger in [data-density.md](data-density.md), filled during Phase 1.
3. The **delta ledger** in [design-police.md](design-police.md), filled as extensions are
   proposed.
4. Proof renders (the 2×2 × faces matrix) per locked widget —
   [themes-testing-plan.md](themes-testing-plan.md).
5. **The terminal deliverable:** the assembled **super-dense demo** — all locked widgets
   tessellated (Phase 3 output), CSS-correct, data-correct, non-wired, on fake fixture data.

### Definition of done (the effort)
The super-dense demo renders every widget, in every earned face, across the theme matrix,
from fake fixture data — correct and **non-wired** — with both ledgers filled and every
delta resolved. Explicitly **not** done here: wiring to live data (that's Phase 4).

### Definition of done (per widget)
- Faces settled, each justified by the data ladder.
- Every element traces to an atom/molecule/organism **or** a logged, accepted delta.
- 2×2 colour/mode matrix renders correct **from tokens alone**, no hand-tuning.
- Cardinality stress cases pass (or the widget is explicitly single-face).

### Risk / estimate
Realistically **~a month** *if* two disciplines hold: (a) the colour/mode matrix stays
mechanical, and (b) same-face-as-default keeps the combinatorics down. If every widget
instead got hand-built faces × schemes × modes, this is a three-month effort — that's the
failure mode this brief exists to prevent.

---

## Plan

### Phase 0 — set the frame (½ day, once)
- Stand up `dashboard-widget-gallery.html` (isolated container-query sandboxes; inlined
  tokens mirroring `bristlenose/theme/tokens.css`, per the existing mockups).
- Pick the **real fixture** (an IKEA / FOSSDA trial-run) so essential-vs-luxury is judged
  against true cardinalities.
- Seed the ledgers in [data-density.md](data-density.md) and [design-police.md](design-police.md).
- Confirm the single **design mode** (proposed: default / light).
- ~~Confirm what "edo" is~~ **RESOLVED** — edo is a shipped palette
  (`palette-edo.css`): Prussian-blue / washi-paper chrome swap via `data-color-theme="edo"`.
  Pure chrome override; sentiment hues are shared. Phase 2 stays mechanical. The gallery
  already renders it via the real attribute. See [themes-testing-plan.md](themes-testing-plan.md).

### Phase 1 — the loop, per **brick**, EASIEST-first
Sequence **least-to-most challenging**. The first job isn't token-delta amortisation — it's
**settling the gallery mechanism and the responsive principles** on a widget with few hard
design questions, so the framework is proven before it meets the hard ones. (Superseded the
earlier "novelty-descending" order, 15 Jul 2026 — Martin's call: get the gallery *right* on
an easy widget first; the heat-ramp delta can wait for the heatmap family.)

For each brick: (1) content pass → data ladder; (2) faces, driven by the ladder,
same-face-default, **constant element size**; (3) police the union → refactor to atoms or log
a delta. The unit is a **brick**, which may hold a welded pair (friction + co-occurrence;
sections + themes) designed *together* because their tradeoffs interact.

Order (easiest → hardest):
1. **Verbatim / quotes** — pure *multiply* (1·3·5 cards); the cleanest demonstration of
   "more data, constant element size." ← current
2. Coverage — bounded strip (*stop*).
3. Signals — *multiply* (1·3·5 cards) with a confidence badge.
4. Pro & contra — two columns, top-N ± .
5. Sections | Themes — nav lists + counts.
6. Who we spoke with — person cards (thumb · arc · journey).
7. Saturation / study-at-a-glance — curves + numbers.
8. Fingerprint — aggregate signature.
9. **Friction & co-occurrence** — PARKED as *hardest* (matrix cardinality, welded-pair
   question, heat ramp, the "no compact" question). Return once principles are settled.

### Phase 2 — mechanical proof (rolling)
Expand each *locked* brick across {edo, default} × {dark, light}. Clean = tokens proven.
Any hand-tuning needed = a leak → back to Phase 1. See
[themes-testing-plan.md](themes-testing-plan.md).

### Phase 3 — the tessellation game → the demo (last of *this* effort)
Real bricks (shape + true faces) go back to `dashboard-autolayout.html`. Running order +
dense packing decided here, informed by study-level narrative flow — never per-widget. The
**output is the endgame demo**: the whole dashboard, super-dense, CSS-correct,
data-correct, non-wired, on fake fixture data. This is where this effort ends.

### Phase 4 — integration (a SEPARATE effort, out of scope here)
Wire the locked widgets into the React SPA (`frontend/`) against live project/pipeline
data — port the fixture-driven demo to real API-fed components. Named here only to mark the
seam; it gets its own plan when this effort's demo is signed off. The fixture's correct data
*shapes* are what make this seam clean.

---

## Widget set (reconciled from the 10 ideas)

Loose-end decisions:
- **Sentiment tape (idea #2)** — per-session *timeline*. Reassigned to the **Session
  lens**, not a dashboard brick.
- **Fingerprint + KWIC (idea #9)** — likely splits: **fingerprint** (aggregate signature)
  = candidate brick; **KWIC** (a search interaction) = behaviour on the Verbatim/Quotes
  surface. [OPEN — final call pending.]
- **Out by decision:** ridgeline (#1, superseded), ambivalence portraits (#4, parked).

| Brick (running order) | Absorbs (of the 10) |
|---|---|
| 1 · Study at a glance (numbers + saturation band) | #10 saturation |
| 2 · Who we spoke with (person cards) | #7 small multiples (partial) |
| 3 · Sections \| Themes (pair) | — |
| 4 · Pro & contra | #3 kudos/kvetch |
| 5 · Friction & co-occurrence (welded 1:2) | #5 co-occurrence + #6 friction heatmap |
| 6 · Signals (1·3·5) | — |
| 7 · Verbatim (1·3·5) | #8 hero quote |
| 8 · Coverage (bounded ≈720) | — |
| (candidate) Fingerprint | #9 fingerprint |
