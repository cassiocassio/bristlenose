# Data density — essential vs luxury, and the data ladder

This is role 1: for each widget, decide **what data is essential and what is luxury**, and
from that derive the responsive drop/expand behaviour. The output is a **data ladder** per
widget — the single source of truth for its faces.

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
`faces` = how many earned (1/2/3) and why. Filled during Phase 1, novelty-descending._

### 5 · Friction & co-occurrence  _(first — highest novelty)_
- faces: _(tbd)_
- ladder: _(tbd)_

### 6 · Friction heatmap component
- faces: _(tbd)_
- ladder: _(tbd)_

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
