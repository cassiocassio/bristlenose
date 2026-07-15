# Data density — essential vs luxury, and the data ladder

This is role 1: for each widget, decide **what data is essential and what is luxury**, and
from that derive the responsive drop/expand behaviour. The output is a **data ladder** per
widget — the single source of truth for its faces.

## The cardinal rule: faces change DATA QUANTITY, not element SIZE

Compact → normal → expanded reveals **more data** (more rows, more columns, more
annotations) at **constant element size**. A cell, a label, a line of body text is the
*same physical size* in all three faces — density comes from *quantity*, not *scale*.

**Faces must never zoom.** If a face works by growing the font, ballooning a cell, or
scaling the same content up, it's wrong — that's a magnifying glass, not a responsive face.
Symptoms to catch in review: grid tracks on `1fr`/`minmax(…,1fr)` that stretch with width;
a `font-size` that changes between faces; anything that gains *presence* rather than
*information* as it widens. Give elements a **fixed** (or gently `clamp()`-bounded) size and
let the faces add or drop *content*.

Corollary: a matrix/grid whose data cardinality is fixed (e.g. 8×8) therefore hits a
**bounded footprint** — extra width goes to *supporting data* (labels, legend, reading
aids), the framework's *stop* answer, not to bigger cells. (First caught on the
co-occurrence widget, Jul 2026 — cells were `1fr` and the expanded face bumped font-size.)

## Normal first — the faces are a conversation, not a guess

**Build the NORMAL face fully first. It is the anchor.** What to *trim* for compact and what
to *add* for expanded is **not designer-guessable** — it's an editorial call that depends on
**context, the data, and how researchers actually use this widget**. The designer builds
normal and surfaces the candidate elements; Martin decides the trim/add, because
essential-vs-luxury is researcher-workflow knowledge, not a layout inference. (Established
15 Jul 2026.)

So the loop per widget is: **build normal → show the candidate ladder → converse about
trim (compact) and add (expanded) → then implement those two faces.** Any compact/expanded a
designer proposes ahead of that conversation is provisional scaffolding, to be redecided —
not a settled face.

Count semantics for *multiply* widgets are also **editorial** — curated top-N (1/3/5), not
`auto-fill`. Which quote/card is "the one" for compact is Martin's selection call.

## The method

1. **List every candidate element** the widget could show (from
   [../design-dashboard-stats.md](../design-dashboard-stats.md) + the idea pool).
2. **Rank them** — rank 1 = essential (must survive the smallest face) … rank N = first to
   drop. Martin's critique *is* this ranking.
3. **Cut the faces from the ladder:**
   - **compact** = top of ladder (the essentials that fit the small brick);
   - **normal** = the default working set;
   - **expanded** = ladder + luxuries (what extra width *reveals*, not just pads).
4. **Same-face is the default.** A widget earns a *distinct* compact or expanded only when
   there's genuine essential/luxury tension. If the honest ladder has no natural cut,
   the widget is single-face — record that explicitly.
5. **Test against real cardinalities** (from the Phase-0 fixture), and against the stress
   cases (1 vs 30 sessions; 2 vs 20 themes). Cardinality is often *how a widget earns "no
   compact version at all."* — lineage item 2.

## How a face answers extra width (from the framework)

A widget doesn't just gain whitespace — it does one of three things (autolayout mockup):
- **stretch** — full-bleed (session band, sentiment strip);
- **stop** — a max useful width, then let the rest breathe (coverage ≈720);
- **multiply** — a quantity query showing *more of the same* (signals/quotes 1 → 3 → 5).

Note which one each ladder rung uses when it appears.

---

## Ledger — data ladders

_One block per widget. Rank 1 = essential (survives compact) … rank N = first to drop.
`faces` = how many earned (1/2/3) and why. Filled during Phase 1, EASIEST-first._

### 7 · Verbatim / quotes  _(FIRST — easiest; a pure* multiply*)_ · PROPOSED, awaiting critique
The purest *multiply* widget: the **card is one fixed design**; faces change only **how many
cards** show. No per-card face adaptation — that's exactly why it's the easy one to settle
principles on.
- **NORMAL (anchor, settled): 3 cards.** compact (**1**) and expanded (**5**) counts are
  provisional scaffolding in the gallery — the trim-to-1 (which quote survives?) and the
  add-to-5 are **pending the researcher-usage conversation**, not decided.
- **card content (constant across faces — its own essential/luxury, not a face ladder):**
  1. quote text — *essential*
  2. attribution (speaker code + who: `P3 · Retail manager`) — *essential*
  3. sentiment badge — near-essential (the emotional read)
  4. timecode (→ video) — luxury
  5. context prefix (the researcher question) — luxury
- **open design questions for critique (these define what "multiply" MEANS):**
  - **(a) count semantics:** curated odd **1/3/5** by breakpoint (built), or **as-many-as-fit**
    (`auto-fill`)? 1/3/5 is editorial; auto-fill is mechanical.
  - **(b) spare width:** fixed card + whitespace (built, purest principle), flex-to-fill, or
    min/max `auto-fill`? i.e. what happens to width that isn't enough for another whole card.
  - **(c) is compact's single quote a "hero"** (larger/special, per idea #8) **or just card #1
    at normal size?** Built = card #1 at constant size (honours the principle). If hero =
    bigger, that *breaks* constant-element-size and needs justifying.
- built with fixed `14rem` cards; presets 320 / 720 / 1168px (5-across fits the gallery width
  with no zoom needed — a deliberate card-width choice).

### 5a · Co-occurrence  _(PARKED — hardest; return once principles settle)_ · PROPOSED
Rows = participants, columns = sections, cell hue = dominant sentiment, cell depth = quote
count. **One representation that enriches in place** (not a grid→matrix swap) — the framework
prefers "same widget adapts" over "two widgets swapped."
- **faces: 3 (earned).** compact = bare grid · normal = + labels + legend + column
  pervasiveness · expanded = + emphasis markers + three-continua reading + method note.
- **ladder (essential → first-to-drop):**
  1. grid cells (hue + depth) — *essential* (the signal itself)
  2. participant row labels — *essential*
  3. section column labels — *essential* (abbreviate/rotate in compact; full at normal+)
  4. legend (hue = sentiment · depth = quotes) — normal+
  5. column pervasiveness indicator (how many participants per section) — normal+
  6. emphasis marker ⁺ (intensity-3 quote in cell) — *luxury*, expanded
  7. three-continua reading (Sporadic↔Pervasive · Unbalanced↔Balanced · Consensus↔Conflict) — *luxury*, expanded
  8. method / citation note — *luxury*, expanded
- **cardinality:** rows = participant count (8 in the fixture; real studies 8–14). Columns =
  section count. **Open question for critique:** does compact survive >~12 columns, or does it
  cap columns / need horizontal scroll? That may be where a "no compact" call gets made.
- **breakpoints (container):** normal ≥ 380px · expanded ≥ 660px. compact = base.

### 6 · Friction heatmap component
- faces: _(tbd)_
- **UNRESOLVED CONTENT TENSION:** `dashboard-10-ideas.html` prose argues the friction heatmap
  ("where is negative signal densest?") is *analysis-lens* territory (duplicates signal-card
  concentration math), NOT a second dashboard matrix — while `dashboard-autolayout.html` brick 5
  welds friction + co-occurrence into one dashboard brick (1:2 split). Resolve before designing:
  is brick 5 a welded pair, or is co-occurrence the sole dashboard tenant and friction lives in
  the analysis lens? Flagged to Martin.
- ladder: _(tbd — pending the above)_

### 1 · Study at a glance (numbers + saturation)
- faces: _(tbd)_
- ladder: _(tbd)_

### (candidate) Fingerprint
- faces: _(tbd)_
- ladder: _(tbd)_

### 7 · Verbatim (quotes)
- faces: _(tbd)_
- ladder: _(tbd)_

### 4 · Pro & contra
- faces: _(tbd)_
- ladder: _(tbd)_

### 2 · Who we spoke with
- faces: _(tbd)_
- ladder: _(tbd)_

### 3 · Sections | Themes
- faces: _(tbd)_
- ladder: _(tbd)_

### 8 · Coverage
- faces: _(tbd)_
- ladder: _(tbd)_
