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

### 1 · Study at a glance / stats row · SETTLED 15 Jul 2026
**5 cards, 8 number-slots**, in fixed semantic order: `[sessions:1] [duration|words:2]
[quotes|themes:2] [sections:1] [AI tags|user tags:2]`. The pairs are semantic — they chunk the
numbers so it isn't a long list — and **must never be split**.

- **Justified grid, fixed gutters, cards flex.** `grid-template-columns: repeat(<units>, 1fr)`,
  `gap: --bn-space-md`, singles span 1, pairs span 2. The trilemma is fixed-gutter / fixed-card /
  justified — pick two; Martin picked fixed gutter + justified, so the card flexes. **Benign here**
  (unlike quotes): a stat card is a centred number + label, it doesn't reflow like prose — the 28px
  number stays 28px, the card just gains air.
- **`--units` is DATA-DRIVEN**, from React at render. No measurement, no layout JS.
- **Never wraps.** `[1][2][2][1][2]` in fixed order leaves holes at 6/4/2 columns (a span-2 can't
  start with one slot left). One row is the only clean layout — and it always fits, so this is moot.
- **No ceiling.** Real range is **6–8 units** → **132–296px**. Max anywhere is 296px (6u @ HD), so
  it never balloons.
- **Real distribution:** **7 units on first processing** (6 of 8 studies), 8 once tagged; 6 for
  non-usability studies (no sections — fossda, escuela).

**Two corrections worth keeping** (both caught by Martin's instinct, both from assuming rather than
reading the code):
1. **"AI tags" counts quotes carrying a SENTIMENT**, not codebook tags —
   `n_ai_tagged = sum(1 for q in all_quotes if q.sentiment is not None)`
   ([dashboard.py:502](../../bristlenose/server/routes/dashboard.py)). Humans always say something
   emotional (~70% of quotes carry a sentiment), so **the row is never sparse**. An earlier analysis
   assumed tags were 0 pre-autocode and wrongly concluded 6 was normal.
2. **A "4-unit study" does not exist.** Three trial-runs showed 0 sections/0 themes — but they have
   **0 quotes**: empty runs (uploads of silence), not a study shape. Don't design for them.

**Padding:** at 13"+sidebar-open the normal 7-unit row clears `"104,832"` @28px by only **2px**, and
the tagged 8-unit row **overflows**, at the shipped 24px side padding. That's what earns the
`space-lg → space-md` delta here — see [design-police.md](design-police.md).

### 7 · Verbatim / quotes  _(FIRST — easiest; a pure* multiply*)_ · PROPOSED, awaiting critique
The purest *multiply* widget: the **card is one fixed design**; faces change only **how many
cards** show. No per-card face adaptation — that's exactly why it's the easy one to settle
principles on.
- **SETTLED 15 Jul 2026 — the multiply is measure-driven, and it lands on real hardware.**
  Card **min 350px**, **max 544px** (34rem), gap 12. Breakpoints = N×350 + (N−1)×12:
  **2@712 · 3@1074 · 4@1436 · 5@1798** (these are *container/content* widths — bake straight
  into `@container` rules).
  Against measured Mac logical widths minus real chrome (rail 36 + padding 48; desktop project
  sidebar 220 ideal):

  | Display | content | quotes |
  |---|---|---|
  | 13" / 13.6" / 14" (sidebar closed) | 1356–1428 | **3-up** ← most people |
  | 16" MBP (closed) | 1644 | **4-up** |
  | **HD 1920 (closed)** | 1836 | **5-up** ← very common external |
  | iMac 2240 / Studio 2560 | 2156 / 2476 | 5-up (roomier, ~8–10 w/line) |

  Martin's sign-off: *"3 for most people, 4 with the nice 16" mac, 5 with the very very common
  HD display — very rational and defensible."*
  **Known wrinkle, accepted:** at 5-up/HD the measure is **6.7 words/line**, just under the
  7-word floor. It's arithmetic, not choice — 5 cards in 1836px are 357px each, and the card
  spends 50px on chrome. Getting 7+ at 5-up would need the card's side padding cut from 24→12.
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

### 4 · Pro & contra  _(CANDIDATE — from the kudos/kvetch order book, idea #3)_
Conformed 15 Jul 2026. **It is NOT a new widget** — it's the real `.bn-featured-quote` card in
two polarity columns (kudos = positive sentiment, kvetch = negative). Zero new elements; the demo
itself says it's a re-hang of `pick_featured_quotes()`, which already diversifies by polarity.
- **Design-police corrections to the order-book demo:**
  - **Dropped the "spread" (±N) column + the row-pairing.** FALSE SIGNAL — a real order book's
    row is bid/ask counterparties; here the left kudos and right kvetch are *independent* picks, so
    a number "between" them is noise dressed as data. Removing it is a correction, not a loss.
  - Raw hex + inline `.book-int` dots → real `--bn-sentiment-*` via the `.badge` atom; intensity
    dots dropped (featured cards don't show them).
  - Headers reuse the `.signal-card-source` uppercase-eyebrow pattern + a count. No new token.
- **THE challenge = quote length, and it's WORSE here than the featured row.** Two columns halve
  the width, so a median 79-word quote is even more brutal. Same fix, same mechanism — the featured
  pull/clamp ([featured-quotes.md](featured-quotes.md)). Because pro/contra IS featured picks
  re-hung, it inherits that work for free; it doesn't need its own. The demo hid this by
  cherry-picking short quotes ("179. That's quite cheap.") — real data won't.
- faces: TBD (candidate; likely a *multiply* like Verbatim — N per column by width).
- **Open (product):** pro/contra = automatic positive/negative sentiment split, or curated? And
  what does it show for an all-friction study (empty kudos column)?

### 2 · Who we spoke with
- faces: _(tbd)_
- ladder: _(tbd)_

### 3 · Sections | Themes
- faces: _(tbd)_
- ladder: _(tbd)_

### 8 · Coverage
- faces: _(tbd)_
- ladder: _(tbd)_
