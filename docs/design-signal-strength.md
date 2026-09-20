# Signal strength — one attention order over sentiment and codebook alike

_Written 13 Sep 2026. Status re-checked 20 Sep 2026 — see the block below._

**Status: SPIKE, still unbuilt. Maths experiments only; no product code has
moved, and nothing here is decided.** The decision waits on richer data and a
side-by-side look at what the new maths does to the UX. This note is the
working: what breaks, what to try instead, and what each option costs.

### Re-checked 20 Sep 2026 — the UX moved, the maths did not

A week and 32 commits on, the lens has been rebuilt around this spike's
*conclusions* while the metric underneath it is untouched. Worth knowing before
reading on, because it changes which half of the note is still owed:

- **Adopted.** The card is one shape rather than two; the chip names the group
  or the sentiment rather than the framework (`9e9af6fd` — the §1 unit change,
  landed in the UI); the four metrics are demoted behind one press, on the
  measurement that *"Agreement takes 3 distinct values and Intensity 4 … two of
  the four are captions, not columns"* (`54fdc615`) — which predates this note
  and is §2's premise rather than its finding.
- **Not adopted.** `bristlenose/analysis/metrics.py` is unchanged —
  `concentration_ratio`, `simpsons_neff`, `composite_signal` and
  `adjusted_residual`, exactly as §2 describes them. Nothing in `bristlenose/`
  computes a hypergeometric or a Hill number.

**The gap that leaves, stated plainly: the lens now leads with a single hero
number, and that number is `compositeSignal`** — the one §2e shows has no
ceiling and reaches 1.05, §2d shows is built on a breadth factor that reports
10.00 voices in an eight-person study, and §4 shows runs *backwards* as a study
grows. Presenting it as *the* number raises the cost of every defect in §2,
because a figure a researcher reads once and trusts is doing more work than a
figure sitting fourth in a metrics block. That is an argument for §5's
recommendation (rank on strength, show attainment), not against the UX change.

**Re-measured at HEAD**, the harness still reconciles against the app path
(**105 cells compared, 0 mismatched**) and every headline holds: 69
sentiment-framework cards still read concentration exactly 1.00,
`adjusted_residual` still reads 0.00 on all of them, `n_eff` still overstates on
14 cards with the same worst case, and the composite still tops out at 1.05. One
figure drifted — **104 cards at `k ≥ 2` became 103**, and the flat count 73
became 74 — because a trial project's data changed, not because anything here
was wrong. The §2 tables below are the 13 Sep numbers and are left as written.

There is no truth to be had here. A signal score is not a measurement of
anything real — it is an ordering device whose only job is *"this deserves your
attention before that"*. Everything below is judged on that and nothing else.

**The goal, in one sentence:** make `frustration` and `Structure` rankable in
one sequence, so that *four of six users aligned on frustration about this
section* and *four of six users with strong opinions about Structure* land
next to each other, and the researcher reads them in order without having to
know which analysis produced which.

**The move:** stop denominating the maths in the matrix and denominate it in
the study. One change of denominator makes a sentiment value and a codebook
group the same kind of object — a subset of the study's quotes — and every
degeneracy below falls out of it.

---

## 1. The unit changes: a label, not a column

Today the lens computes two different things and calls both a signal card:

- the **7-column sentiment matrix** (`signals.py`) — location × `frustration`
- the **codebook matrices** (`generic_signals.py`) — location × `Structure`,
  partitioned by framework, plus a one-column *Sentiment group* matrix that is
  the union of the seven values

The proposal collapses that to one unit: **a card is a (location × label)
cell**, where a label is *either* a sentiment value *or* a codebook group. The
arithmetic cannot tell them apart, which is the entire point. The one-column
Sentiment-group card disappears — it is the union of its own values, so
carrying both double-counts the same material at two granularities.

The definition of the ordering, stated before any arithmetic:

> **Two cards deserve equal attention when the same number of independent
> people said something equally strongly, and each label is equally
> over-represented here against its own rate in the rest of the study.**

Three clauses, three factors. MEASURED — a six-participant study, 60 quotes, a
section holding 10 of them, three participants contributing one quote each at
intensity 2 (a constructed example, to show the identity directly):

| the label on the card | its rate across the study | voices | surprise | heat | **strength** |
|---|---:|---:|---:|---:|---:|
| `frustration` | 20% | 0.50 | 0.791 | 0.50 | **59** |
| `Feedback` | 20% | 0.50 | 0.791 | 0.50 | **59** |

Same evidence, two vocabularies, one number. What separates two labels on
identical evidence is only how common each is in the rest of the study — which
is the honest difference, and the only one.

---

## 2. What is wrong today

`composite_signal = concentration × (n_eff / P) × (mean_intensity / 3)`

MEASURED across 8 real projects, reconstructed through the app's own path and
cross-checked cell by cell (**106 cells compared, 0 mismatched**). Two label
sets are quoted below and they are not interchangeable:

- **as shipped** — codebook groups plus the one-column Sentiment group:
  454 pairs, **104 cards** at `MIN_QUOTES_PER_CELL = 2`
- **proposed** — sentiment values beside codebook groups:
  881 pairs, **107 cards** (72 sentiment, 35 codebook)

(fossda's database holds the same project twice, as `project_id` 1 and 2; the
second copy is excluded so nothing is double-counted.)

### 2a. Concentration is 1.00 in 73 of 104 shipped cards

`concentration_ratio` is `(cell/row_total) ÷ (col_total/grand_total)` — exactly
1 whenever the cell's row or column exhausts the matrix:

| why | cards |
|---|---:|
| the framework declares one column — the Sentiment group, every project | 69 |
| the row carries the whole matrix | 2 |
| the only column with any data | 1 |
| coincidence | 1 |
| **total reading exactly 1.00** | **73 of 104** |

The third row is the instructive one: **Rockclimbing's `nielsen` framework on
the section axis — ten declared groups, one with any data there.** A ten-column
matrix goes mute the moment nine columns are empty. This is what a
contingency-table lift does to a sparse table, and sparse is the normal
condition here. Widening the codebook does not protect you.

### 2b. The contingency model is the wrong model for codebook tags

Chi-square independence — and the lift and adjusted residual built on it —
assumes each observation lands in **exactly one** cell. Codebook tags are a
many-to-many relation: a quote carrying codes from four groups produces four
contributions. `analysis.py` documents the consequence as a trade-off note
("quotes tagged with codes from multiple groups count in each group column…
this inflates `grand_total`"). It is not a trade-off, it is a misapplied model,
and it is why `grand_total` is not a number anything can be divided by and
compared across frameworks.

### 2c. `adjusted_residual` does not rescue it

The textbook answer to comparing cells across differently-shaped tables, and
the tree holds **three identical copies**: `metrics.adjusted_residual` (Python,
called by nothing but its own tests), `adjustedResidual` in `AnalysisPage.tsx`
(which does colour the heatmap, via `heatCellStyle`), and a third in the frozen
vanilla `theme/js/analysis.js`. VERIFIED 13 Sep 2026: all three agree line for
line — no drift today, and no entry in `docs/design-shared-formats.md` to
notice it if there were.

But its denominator carries `(1 − col_total/grand_total)`, which is **zero**
wherever a column carries the whole matrix. MEASURED: `z = 0.00` in all 69
one-column cards. It states the same structural fact more honestly than `1.00`
does, and it still ranks nothing. **Swapping lift for z is not the fix.**

### 2d. `simpsons_neff` overstates breadth, on shipped cards, visibly

It is the *unbiased population estimator* `N(N−1)/Σnᵢ(nᵢ−1)` — it estimates the
diversity of the population the quotes were drawn from, and is **not bounded by
the number of people who actually spoke**.

MEASURED, 104 shipped cards: **14 (13%)** report more effective voices than
people who spoke; **7** report breadth 1.00 — "every participant" — on fewer
participants than that; **1** reports breadth **1.25**, so the factor the
composite calls a 0–1 share is not a share. Worst case, Rockclimbing: four
people speak, counts `[2,1,1,1]`, and `n_eff` = **10.00** in an **eight**-person
study.

This is user-visible. `AnalysisPage.tsx` renders `signal.nEff.toFixed(1)` as
the card's **Agree.** figure under `analysis.agreeTitle` — *"effective number of
voices"*. The bar beside it is `agreePct`, written
`Math.min(100, (signal.nEff / allPids.length) * 100)` — **the clamp is already
there**, so the overflow was noticed at the bar and papered over rather than
fixed at the number. (Cited by symbol, not line: that file is under active edit.)

### 2e. The composite has no ceiling, and it pays for rarity

It reaches **1.50** on the proposed label set (7 cards above 1.0), so
"normalised to 0–1" is not true of the product either. And because lift is
`observed/expected`, it pays most for rare things in small denominators.
MEASURED, `project-ikea` with `MIN_QUOTES_PER_CELL` lowered to 1:

| # | composite | card | quotes | people | conc |
|---:|---:|---|---:|---:|---:|
| 1 | 1.50 | Product Detail × Mapping | 1 | 1 | 13.50 |
| 2 | 1.50 | Checkout & Store Selection × Constraints | 1 | 1 | 13.50 |
| 3 | 1.22 | Top Navigation × Skeleton | 1 | 1 | 11.00 |
| 4 | 1.19 | Duvets & Bedding Category × surprise | 1 | 1 | 5.33 |
| 5 | 1.19 | App Prompt & QR Code × surprise | 1 | 1 | 5.33 |
| 6 | 1.19 | Search & Sort Results × delight | 1 | 1 | 5.33 |

Six single quotes from single participants, above every finding two people
agreed on.

### 2f. Intensity is a thumb on the scale — it favours sentiment by construction

This one is specific to the goal of this note and was not previously recorded.
**A sentiment label selects quotes *by* their emotional content; a codebook
group selects by topic.** So `mean_intensity / 3` is systematically higher on
the sentiment side, and mixing the two kinds in one ranking inherits that.

MEASURED within each project carrying both kinds — same quotes available to
both, only the selection differs:

| project | study mean intensity | under a sentiment label | under a codebook label |
|---|---:|---:|---:|
| project-ikea | 1.30 | **1.50** | 1.29 |
| project-ikea2 | 1.24 | **1.33** | 1.24 |
| Rockclimbing | 1.91 | **2.11** | 1.60 |

Consistent, and in the direction that breaks exactly the comparison this note
exists to make. At card level the median heat factor differs by **+0.333**
between the kinds.

---

## 3. The proposal

```
strength = 100 · voices^0.50 · surprise^0.35 · heat^0.15
```

Three factors, each a bounded 0–1 quantity, combined as a weighted geometric
mean so none can run away and all three must be present. **Every quantity is
counted in study quotes — unique quotes on the axis — never in matrix
contributions.**

| symbol | is |
|---|---|
| `k` | quotes at this location carrying this label |
| `K_r` | **all** quotes at this location |
| `n_c` | **all** quotes in the study carrying this label |
| `K_all` | **all** quotes in the study, on this axis |
| `P` | participants in the study |

`K_r` and `K_all` count *unique quotes*, so a quote tagged from four codebooks
is counted once and `grand_total`'s inflation (§2b) never enters the arithmetic.

The three factors share one shape: **each asks how this cell compares with what
this label normally does.** That is what makes them poolable across labels of
wildly different prevalence, and it is the only idea in the note.

### voices — how much of the study is behind it

```
n_eff  = 1 / Σ (nᵢ / n)²          # Hill number of order 2
voices = min(1, n_eff / P)
```

Bounded above by the number of people who actually spoke — which is what the
card's **Agree.** label has always claimed and `simpsons_neff` has never
delivered. `[2,1,1,1]` reads **3.57**, not 10.00. `[2,1]` reads **1.80**, not
3.00.

### surprise — is this more than the study would produce anyway

The null model is the one the data obeys: *this label is applied at its
study-wide rate, independently of location.* Drawing this location's `K_r`
quotes from the study's `K_all`, of which `n_c` carry the label, the count is
hypergeometric. The statistic is the **mid-p left tail**:

```
surprise = P(X < k) + ½·P(X = k)      X ~ Hypergeometric(K_all, n_c, K_r)
```

`0.5` is "exactly what this study produces here anyway", `→1` notably
concentrated, `→0` notably absent. Four properties earn it the job:

1. **Defined at any label prevalence and any table shape.** Columns are no
   longer a partition of a denominator, so a one-label framework is not
   degenerate. MEASURED on the proposed label set, surprise runs 0.183 … 1.000
   (median 0.789) on the sentiment side and 0.245 … 0.997 (median 0.877) on the
   codebook side — two overlapping distributions where there was a constant.
2. **Exact, not approximate.** The median populated cell holds **2 quotes**. A
   normal-approximation z at n=2 is not a number to rank on. This is Fisher's
   exact test on the 2×2 collapse.
3. **Bounded and centred, so there is no ceiling to normalise away.** 0.5 means
   the same thing in every table of every shape.
4. **Signed.** Below 0.5 is depletion — where "notably absent" lives.

MEASURED cost: big-integer `math.comb` is 0.018 ms at fossda's scale
(K_all = 231) but 1.2 s at 20,000 quotes. Compute in log space with
`math.lgamma` — 1.1 ms at 20,000, agreeing with the exact form to
**1.6 × 10⁻¹³** across the corpus. No new dependency either way.

### heat — hotter than this label usually is

```
r    = cell mean intensity / this label's own study-wide mean intensity
heat = r / (1 + r)          # 0.5 == this label's own average
```

The naive `mean_intensity / 3` carries §2f's bias straight into the ranking.
Comparing each cell with **its own label's baseline** removes it, and it is the
same move `surprise` makes one factor over.

MEASURED, median heat by kind:

| form | sentiment | codebook | gap |
|---|---:|---:|---:|
| `mean/3` (shipped shape) | 0.667 | 0.333 | **+0.333** |
| `r/(1+r)` (proposed) | 0.500 | 0.500 | **+0.000** |

The cost is ρ **+0.991** against the ordering the naive form gives — so the
correction is nearly free, and it is the difference between the two kinds being
comparable and merely being adjacent.

The price, stated plainly: a label that appears in only one place can never be
hotter than its own average, so it sits at heat 0.5 by construction. Under a
label that is *always* hot, `frustration` no longer scores above `delight` for
being frustration — the card already says which it is; the number adds "and
unusually intensely so here".

### The weights are not load-bearing

MEASURED, Spearman of the resulting **ranking** against `0.50 / 0.35 / 0.15`:

| voices | surprise | heat | ρ |
|---:|---:|---:|---:|
| 0.60 | 0.25 | 0.15 | +0.986 |
| 0.40 | 0.45 | 0.15 | +0.990 |
| 0.50 | 0.50 | 0.00 | +0.974 |
| 0.34 | 0.33 | 0.33 | +0.965 |
| 0.70 | 0.30 | 0.00 | +0.976 |

Every reasonable weighting gives effectively the same order. The weights tune
the *spread*, not the sequence — a presentation choice, not a hidden model.
The proposed set encodes one judgement: **breadth of agreement is the scarce
thing and should lead.** MEASURED, the median populated cell carries quotes
from exactly one participant, in every project including the 20-session one.

---

## 4. The attainable range — and the sting in it

*"If we called the strongest possible frustration and the strongest possible
Structure, and the weakest measurable signal, for a study of N users — what are
the highs and lows?"*

That question is the one that decides whether "out of 100" can ever be honest,
so it is worth answering exactly. The strongest possible card is: the label
fills the location, one quote per participant, every quote at intensity 3. The
weakest measurable is one quote from one participant at intensity 1 with the
label no rarer here than anywhere.

MEASURED, against a study model whose every constant comes from the corpus
rather than from invention — 8 quotes per session (measured 6.7–10.1, and
near-independent of session length), 0.65 sentiments per quote over 7 values,
1.2 codes per quote over 8 groups, 2.2 locations per session:

| N users | quotes | per location | strongest/weakest `frustration` | strongest/weakest `Structure` | band overlap |
|---:|---:|---:|---|---|---:|
| 3 | 24 | 4 | 46.2 … 75.6 | 44.5 … 92.9 | **61%** |
| 5 | 40 | 3 | 36.6 … 72.0 | 34.9 … 71.9 | **95%** |
| 6 | 48 | 3 | 33.2 … 65.7 | 31.9 … 65.7 | **96%** |
| 8 | 64 | 3 | 28.9 … 56.9 | 27.8 … 56.9 | **96%** |
| 12 | 96 | 3 | 23.5 … 46.4 | 22.6 … 46.4 | **96%** |
| 20 | 160 | 3 | 18.1 … 36.0 | 17.4 … 36.0 | **96%** |

**Two findings, and the second is the awkward one.**

**(a) The two kinds are comparable from N=5 up.** At five participants and
above the attainable bands are within 4% of identical, so a sentiment value and
a codebook group are competing for the same ground and the ranking is fair. At
N=3 they are not — a codebook group can reach 92.9 while a sentiment value caps
at 75.6, because the codebook group is common enough to fill a four-quote
location and the sentiment value is not. **The corpus's residual disagreement
between the two kinds is a three-participant artefact, not a property of the
metric.** Every project here with more than three participants interleaves.

**(b) The ceiling FALLS as the study grows — a better study produces lower
numbers.** The strongest card a 20-person study can produce scores **36.0**;
the strongest a 3-person study can produce scores **92.9**. That is not a bug
in the score, it is the structure of the data: quotes per session is near
constant, so locations stay small while participants multiply, and a
three-quote location can never involve twenty people. `voices = n_eff / P` is
therefore capped at `min(K_r, P)/P`, which shrinks as `P` grows.

**Consequence: a raw 0–100 score is not portable across studies, and it is
backwards.** A researcher who ran a proper twenty-person study would see
nothing above 36 and conclude the study was weak. Any "out of 100" presentation
has to answer this, which is §5.

### Narrowing to the v1 band: 6–12 participants

v1 optimises for 6–12 participants, so the question is whether that constraint
makes the ceiling problem go away. MEASURED at every size in the band:

| N | quotes | per location | `frustration` | `Structure` | kind overlap |
|---:|---:|---:|---|---|---:|
| 6 | 48 | 3 | 33.2 … 65.7 | 31.9 … 65.7 | 96% |
| 7 | 56 | 3 | 30.6 … 60.8 | 29.6 … 60.8 | 97% |
| 8 | 64 | 3 | 28.9 … 56.9 | 27.8 … 56.9 | 96% |
| 9 | 72 | 3 | 27.1 … 53.6 | 26.2 … 53.6 | 97% |
| 10 | 80 | 3 | 25.7 … 50.9 | 24.7 … 50.9 | 96% |
| 11 | 88 | 3 | 24.4 … 48.5 | 23.6 … 48.5 | 96% |
| 12 | 96 | 3 | 23.5 … 46.4 | 22.6 … 46.4 | 96% |

**It half goes away, and the half that remains is the one that matters.**

**The good half.** Kind overlap is **96–97% across the whole band** — a
sentiment value and a codebook group are competing for identical ground at
every size v1 targets. The comparison this note exists to make is sound
throughout v1's scope, with nothing left to argue. And the ceiling drift
narrows from **2.58×** over 3→20 to **1.41×** over 6→12.

**The half that remains.** 1.41× is still enough to break a fixed bar, and
this is the number that decides the presentation question:

| a fixed bar at | N=6 | N=8 | N=10 | N=12 |
|---:|---|---|---|---|
| 30 | keeps everything | keeps 96% of the band | 83% | 72% |
| 40 | 79% | 60% | 43% | 28% |
| 50 | 48% | 25% | 3% | **unreachable** |
| 60 | 17% | **unreachable** | **unreachable** | **unreachable** |

A bar at 50 keeps half of a six-person study's range and **cannot be reached at
all** by an eleven- or twelve-person one. Only a bar at 30 survives the band,
and at N=6 it keeps everything, so it is not a bar.

The same bars expressed as **attainment** are flat to within 1% across the
entire band — 50% keeps the whole range at every size, 75% keeps ~51% at every
size. So the v1 verdict is specific:

> **Rank on raw `strength` — within one study it orders correctly and needs
> nothing. Express any number the researcher reads, and any floor, as
> attainment.** Narrowing to 6–12 fixes the comparability question completely
> and the threshold question not at all.

---

## 5. Presentation — five schemes over one ordering

**Ordering and presentation are separable, and it is worth stating loudly:**
every scheme below is a monotone per-study transform of the same score, so all
five produce the **identical sequence**. Choosing between them changes nothing
about what the researcher reads first. It changes only what the number claims.

| scheme | what it says | portable across studies? | thresholdable? | the flaw |
|---|---|:--:|:--:|---|
| **Signal** (today) | an unbounded composite | no | no | §2e: no ceiling, rewards rarity, reaches 1.50 |
| **Strength** raw 0–100 | the score itself | **no** — §4(b) | yes | a 20-person study tops out at 36 and reads as weak |
| **Attainment %** | share of the strongest card *this study could have produced* | **yes** | yes | needs the ceiling explained if anyone asks |
| **% of best** | share of this study's strongest card | no | no | the top card is always 100%, so an empty study still has a winner |
| **Percentile** | position in this study's list | no | no | same flaw, plus it flatters long lists |
| **Rank only** | `#1, #2, #3` | n/a | **no** | no magnitude at all, so nothing can be cut |

**Attainment is the one that survives the §4(b) problem**, and it is cheap: the
ceiling is the same three factors evaluated at their best achievable values for
that label at that location, so the code is already written. MEASURED, what
each project actually attained:

| project | P | cards | best card | this study's ceiling | **attainment** |
|---|---:|---:|---:|---:|---:|
| project-ikea | 3 | 24 | 72.7 | 95.8 | **76%** |
| project-ikea2 | 3 | 14 | 68.6 | 95.8 | **72%** |
| Rockclimbing | 8 | 17 | 55.7 | 87.3 | **64%** |
| fossda-opensource | 9 | 38 | 58.5 | 92.2 | **63%** |
| foo | 5 | 9 | 49.7 | 94.8 | **52%** |

Raw strength says ikea (72.7) beat fossda (58.5) — mostly a statement about
participant count. Attainment says ikea found 76% of what it could have found
and fossda 63%, which is a claim about the *studies* and survives being carried
between them.

**A sixth option, and it composes with any of the above: a band.** `Strong /
Clear / Emerging / Faint` cut on attainment. It is what `confidence` in
`generic_signals.py` already tries to be — it is computed, passed to the client,
and gates nothing. MEASURED, the bands discriminate in a plausible direction:
project-ikea's list is almost all *Clear*, fossda's almost all *Emerging*.

**The measurement does make one recommendation, narrowly.** §4's v1 band shows
a fixed bar on raw `strength` is unreachable at N=11–12 while the same bar in
attainment is flat to within 1% across 6–12 — so *if a number is shown or a
floor is cut, it should be attainment*. Everything else — bands or no bands,
where the bar sits, whether a number appears at all — is a UX call to make by
looking, which is what the side-by-side page is for.

---

## 6. Before and after

Full re-ranking on the proposed label set — sentiment values (**S**) interleaved
with codebook groups (C). `▲`/`▼` is the move against today's `Signal`.


#### project-ikea#1 — 3 participants, 24 cards (1 sentiment value, 23 codebook group)

| was | now | kind | label | location | quotes | people | Signal | voices | surprise | heat | **Strength** | attain |
|----:|----:|:--:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 13 | **1** ▲12 | C | Discoverability | Task orientation and shopping  | 2 | 2 | 0.33 | 0.67 | 0.967 | 0.50 | **73** | 76% |
| 11 | **2** ▲9 | C | Strategy | Task orientation and shopping  | 2 | 2 | 0.37 | 0.67 | 0.900 | 0.50 | **71** | 74% |
| 8 | **3** ▲5 | C | Motivation | Task orientation and shopping  | 2 | 2 | 0.44 | 0.67 | 0.900 | 0.50 | **71** | 74% |
| 3 | **4** ▼1 | C | Behaviour | Beds & Mattresses Category | 2 | 2 | 0.64 | 0.67 | 0.844 | 0.55 | **70** | 73% |
| 5 | **5** | C | Structure | Beds & Mattresses Category | 4 | 2 | 0.61 | 0.67 | 0.877 | 0.49 | **70** | 73% |
| 9 | **6** ▲3 | C | Real-world matching | Task orientation and shopping  | 2 | 2 | 0.44 | 0.67 | 0.900 | 0.43 | **69** | 72% |
| 1 | **7** ▼6 | C | Scope | Shopping Bag | 2 | 2 | 1.05 | 0.67 | 0.760 | 0.51 | **67** | 70% |
| 2 | **8** ▼6 | **S** | confusion | Beds & Mattresses Category | 3 | 2 | 0.67 | 0.60 | 0.909 | 0.43 | **66** | 69% |
| 6 | **9** ▼3 | C | Feedback | Shopping Bag | 4 | 2 | 0.60 | 0.53 | 0.975 | 0.47 | **65** | 68% |
| 4 | **10** ▼6 | C | Surface | Search & Sort Results | 2 | 1 | 0.61 | 0.33 | 0.975 | 0.53 | **52** | 54% |
| 10 | **11** ▼1 | C | Motivation | Sofa Beds Category | 2 | 1 | 0.43 | 0.33 | 0.970 | 0.50 | **51** | 54% |
| 7 | **12** ▼5 | C | Aesthetics and minimalism | Homepage content and navigatio | 2 | 1 | 0.50 | 0.33 | 0.967 | 0.50 | **51** | 54% |
| 12 | **13** ▼1 | C | Structure | Checkout & Store Selection | 2 | 1 | 0.37 | 0.33 | 0.936 | 0.54 | **51** | 54% |
| 14 | **14** | C | Feedback | Search & Sort Results | 3 | 1 | 0.30 | 0.33 | 0.930 | 0.49 | **51** | 53% |

#### project-ikea2#1 — 3 participants, 14 cards (4 sentiment value, 10 codebook group)

| was | now | kind | label | location | quotes | people | Signal | voices | surprise | heat | **Strength** | attain |
|----:|----:|:--:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **1** | C | Discoverability | Navigation & Homepage Orientat | 3 | 2 | 0.56 | 0.60 | 0.950 | 0.50 | **69** | 72% |
| 2 | **2** | C | Mental model | Checkout & Delivery | 3 | 2 | 0.50 | 0.60 | 0.807 | 0.46 | **64** | 67% |
| 7 | **3** ▲4 | **S** | confusion | Beds Category | 5 | 2 | 0.29 | 0.49 | 0.924 | 0.48 | **61** | 64% |
| 5 | **4** ▲1 | **S** | frustration | Beds Category | 2 | 2 | 0.31 | 0.67 | 0.570 | 0.46 | **60** | 62% |
| 12 | **5** ▲7 | C | Pleasure | Top Navigation | 2 | 1 | 0.11 | 0.33 | 0.997 | 0.50 | **52** | 54% |
| 14 | **6** ▲8 | C | New group | Top Navigation | 2 | 1 | 0.11 | 0.33 | 0.997 | 0.50 | **52** | 54% |
| 9 | **7** ▲2 | C | Discoverability | Duvets & Bedding | 3 | 1 | 0.25 | 0.33 | 0.948 | 0.50 | **51** | 53% |
| 6 | **8** ▼2 | **S** | delight | Beds Category | 2 | 1 | 0.31 | 0.33 | 0.901 | 0.50 | **50** | 52% |
| 4 | **9** ▼5 | C | Errors and recovery | Top Navigation | 2 | 1 | 0.33 | 0.33 | 0.859 | 0.49 | **49** | 51% |
| 8 | **10** ▼2 | C | Errors and recovery | Checkout & Delivery | 3 | 1 | 0.28 | 0.33 | 0.807 | 0.52 | **49** | 51% |
| 10 | **11** ▼1 | C | Mental model | Beds Category | 6 | 1 | 0.16 | 0.33 | 0.756 | 0.50 | **47** | 49% |
| 11 | **12** ▼1 | **S** | surprise | Beds Category | 3 | 1 | 0.12 | 0.33 | 0.737 | 0.42 | **46** | 48% |
| 3 | **13** ▼10 | C | Errors and recovery | Beds Category | 4 | 2 | 0.40 | 0.67 | 0.245 | 0.49 | **45** | 47% |
| 13 | **14** ▼1 | C | Discoverability | Beds Category | 5 | 1 | 0.11 | 0.33 | 0.501 | 0.50 | **41** | 43% |

#### fossda-opensource#1 — 9 participants, 38 cards (38 sentiment value, 0 codebook group)

| was | now | kind | label | location | quotes | people | Signal | voices | surprise | heat | **Strength** | attain |
|----:|----:|:--:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **1** | **S** | confidence | Open source philosophy and imp | 7 | 5 | 1.50 | 0.42 | 0.998 | 0.51 | **59** | 63% |
| 6 | **2** ▲4 | **S** | delight | Community building and mentors | 6 | 3 | 0.53 | 0.29 | 0.985 | 0.47 | **47** | 51% |
| 5 | **3** ▲2 | **S** | frustration | Corporate career transitions a | 15 | 3 | 0.56 | 0.25 | 1.000 | 0.52 | **45** | 49% |
| 8 | **4** ▲4 | **S** | delight | Open source project creation a | 7 | 3 | 0.37 | 0.29 | 0.789 | 0.50 | **44** | 48% |
| 7 | **5** ▲2 | **S** | confidence | Open source project creation a | 4 | 3 | 0.48 | 0.30 | 0.609 | 0.48 | **41** | 44% |
| 9 | **6** ▲3 | **S** | surprise | Open source project creation a | 2 | 2 | 0.34 | 0.22 | 0.884 | 0.50 | **41** | 44% |
| 3 | **7** ▼4 | **S** | doubt | Diversity and inclusion challe | 3 | 2 | 1.23 | 0.20 | 0.999 | 0.42 | **39** | 43% |
| 18 | **8** ▲10 | **S** | satisfaction | Corporate career transitions a | 8 | 3 | 0.19 | 0.24 | 0.661 | 0.50 | **38** | 41% |
| 13 | **9** ▲4 | **S** | satisfaction | Open source project creation a | 6 | 3 | 0.30 | 0.33 | 0.419 | 0.46 | **38** | 41% |
| 20 | **10** ▲10 | **S** | delight | Open source philosophy and imp | 3 | 3 | 0.19 | 0.33 | 0.393 | 0.51 | **38** | 41% |
| 10 | **11** ▼1 | **S** | satisfaction | Personal growth and life refle | 6 | 3 | 0.34 | 0.22 | 0.689 | 0.52 | **38** | 41% |
| 11 | **12** ▼1 | **S** | satisfaction | Technical innovation and probl | 3 | 2 | 0.33 | 0.20 | 0.667 | 0.52 | **35** | 38% |
| 14 | **13** ▲1 | **S** | delight | Academic and research environm | 6 | 2 | 0.29 | 0.15 | 0.971 | 0.51 | **35** | 38% |
| 16 | **14** ▲2 | **S** | satisfaction | Organizational involvement and | 6 | 2 | 0.26 | 0.15 | 0.948 | 0.52 | **35** | 38% |

### What moved, and whether it should have

**project-ikea** (5 codebooks, 3 participants). `Task orientation` takes the
top three and four of the top six: two quotes each, two of three participants,
in a section where almost nothing else is coded — surprise 0.90–0.97. Today
those top three sit 13th, 11th and 8th. Falling hardest are the single-participant cards
with big lifts: `Scope` 1 → 7, `Surface` 4 → 10, `Aesthetics and minimalism`
7 → 12. One voice is one voice.

**project-ikea2** is the project that shows the actual goal working. Its top
four reads `Discoverability` (codebook), `Mental model` (codebook),
**`confusion`** (sentiment), **`frustration`** (sentiment) — four cards a
researcher reads in order without needing to know which analysis produced
which. Under today's `Signal` the two sentiment values sit 7th and 5th behind
codebook cards scoring on lift alone.

**fossda-opensource** (9 participants, 20 sessions, sentiment only). 38 cards
where the shipped lens draws 14, because the sentiment *values* are now
first-class rather than folded into one Sentiment group — and that split is
itself the point: the Sentiment-group card said *"this place is emotional"*,
where `confidence`, `delight`, `frustration` and `doubt` at the same place are
four different things a researcher can act on. Its top card is
`confidence @ Open source philosophy` (7 quotes, 5 of 9 participants), top
under both metrics. The re-ranking below it is driven entirely by surprise — a
factor that was switched off for this whole project before, since every card in
it had concentration exactly 1.00.

---

## 7. De-duplication, rebuilt

Attention is the scarce thing, and the argument for de-duplication is sound:
if two or three quotes have surfaced once with the best available reading of
why they matter, a second card showing **the same two or three quotes** to say
"it also means this" spends attention for nothing. The researcher decides
whether that material is worth interpreting, and the strongest reading is
enough to start the thinking.

But the other reading is very unlikely to be *useless*. Morville and Spool and
Norman and Nielsen overlap heavily; the second card is usually **the same thing
in another codebook's language**. So the rule should fold it in, not delete it.

### The shipped rule deletes, and it over-deletes

It walks a location's cards strongest-first and keeps one only if it brings a
quote the kept cards do not already carry — an **asymmetric, union-based**
test. MEASURED over the corpus, 52 locations and 107 cards, it hides 14. Of the
19 hidden on the as-shipped label set, **11 are killed by the union of other
cards while matching no single kept card**:

| best pairwise Jaccard with any kept card | card | location |
|---:|---|---|
| 0.25 | Real-world matching | Beds & Mattresses Category |
| 0.29 | surprise | Beds Category (ikea2) |
| 0.33 | Status visibility · Feedback · Discoverability | Beds & Mattresses Category |
| 0.50 | Status visibility | Shopping Bag |
| 0.50 | Structure | Beds & Mattresses Category |
| 0.67 | Needs and desires | Beds & Mattresses Category |

A card sharing 25% of its quotes with its nearest neighbour is not the thing
the argument is about. It is being deleted because five *other* cards jointly
cover it — and a finding that spans several other findings is arguably the most
interesting one at that location, not the least.

### Pairwise near-identity is the test, and the data hands you the threshold

MEASURED, the pairwise Jaccard between two cards at the same location, n=126:

| Jaccard | pairs | |
|---|---:|---|
| 0.0–0.1 | 81 | `#################################################################################` |
| 0.1–0.2 | 4 | `####` |
| 0.2–0.3 | 13 | `#############` |
| 0.3–0.4 | 9 | `#########` |
| 0.4–0.5 | 2 | `##` |
| 0.5–0.6 | 5 | `#####` |
| 0.6–0.7 | 2 | `##` |
| 0.7–0.9 | **0** | — |
| 0.9–1.0 | 10 | `##########` |

**There is an empty band at 0.7–0.9.** Card pairs are either near-disjoint or
literally identical; almost nothing sits between. So the threshold is *read off
the data* rather than tuned — anything in 0.7–0.9 picks out the same set. This
is the strongest evidence in the note for any single number in it.

### The rule

> **Cluster a location's cards by pairwise quote-set Jaccard ≥ 0.8. Show one
> card per cluster — the strongest — carrying the others as named alternate
> readings. Nothing is deleted.**

MEASURED against the shipped rule:

| rule | cards shown | lost entirely | folded in as alternates |
|---|---:|---:|---:|
| SHIPPED — delete on union coverage | 93 | **14** | 0 |
| PROPOSED — merge, Jaccard ≥ 0.8 | 100 | **0** | 7 |
| merge, Jaccard ≥ 0.6 | 98 | 0 | 9 |
| merge, Jaccard ≥ 0.5 | 94 | 0 | 13 |

Seven merges across the corpus, all of them genuine duplicates — and seven
fewer cards for the researcher to read at the locations where duplication was
real. The union-only casualties survive as cards, because they were never the
thing the rule was aimed at.

### The Sentiment exemption disappears, by construction

The standing exemption exists because a coverage rule deletes the Sentiment
card: MEASURED, in 9 of 9 locations where a Sentiment-group card sat beside
codebook cards, the codebook cards collectively covered **100%** of its quotes —
it contributed a unique quote exactly zero times. It could survive only by
ranking first, and that is a coin-flip no metric change loads. (An earlier
expectation, recorded in the UX bench, was that normalisation would remove the
need for the exemption. MEASURED, it does not: under `strength` the unguarded
rule hides the Sentiment card **7** times against the shipped rule's 5.)

Two changes retire it without a special case:

1. **Merge rather than delete.** Nothing can be lost, so nothing needs
   protecting.
2. **The Sentiment-group card stops existing** (§1). Sentiment values are
   labels in their own right, and a value's quote set is a fraction of a
   codebook group's, not a superset of it — so the pathology has no subject.

---

## 8. What it costs

**Arithmetic.** One new function (hypergeometric mid-p, ~10 lines,
`math.lgamma`, no dependency), two corrected ones (`simpsons_neff` → Hill
number; `mean_intensity/3` → own-baseline heat), and different arguments at the
call site. `adjusted_residual` is untouched in all three of its homes — a
heatmap cell is a cell of the framework's own matrix, which is the question the
contingency residual answers.

**A new input the detector does not have.** `_compute_signals` sees only the
matrix. It now needs `K_r`, `K_all` and each label's study-wide mean intensity —
all derivable from what `_load_shared_data` already holds in `quote_section` /
`quote_theme` and simply does not pass down. Plumbing, not new data.

**One analysis replaces two.** `signals.py` and `generic_signals.py` compute
the same thing over different label sets; under this proposal there is one
label set, so one of them goes. That is a simplification, but it is also the
largest structural change here and it touches `/analysis/sentiment`,
`/analysis/tags` and `/analysis/codebooks`.

**Every number on the card changes.** `Conc. 1.3×`, `Agree. 3.0`, `Signal 0.32`
are all user-facing, carried by `en/common.json` — `analysis.concLabel` /
`analysis.concTitle` ("how overrepresented vs study average"),
`analysis.agreeLabel` / `analysis.agreeTitle`, and the longer
`help.signals.agreementDesc` ("Simpson's diversity index") — and all translated
into 21 locales. `Agree.` keeps its label and finally matches it, but both its
tooltip and its help text name Simpson's explicitly and must change with it.
`Conc.` stops being a multiplier. The `agreePct` clamp becomes dead. Per the
house i18n rule that is 21 files in one commit, and `check-locales.py` reports
a missing key as a **warning**, so a partial landing ships English in twenty
locales.

**Confidence weighting gets harder, not easier.** `_compute_group_analysis`
carries `weighted_count` for pending `ProposedTag` rows (weight = LLM
confidence); the shipped composite ignores it and uses the raw `cell.count`. An
exact hypergeometric needs integer counts, so adopting weights means the normal
approximation or rounding. VERIFIED 13 Sep 2026, `project-ikea` carries **31
accepted tags and 112 pending proposals** — most of what the codebook half
ranks today is AutoCode's unreviewed suggestions, so this is not a hypothetical.

**Elaboration re-runs.** `_elaborate_top_signals` picks the top N by
`composite_signal`. Changing the ranking changes which signals get an LLM
elaboration, so stored elaborations stop lining up with the top of the list.
Cache invalidation, and billable.

---

## 9. What it cannot do

**It is a within-study ordering.** The three one-participant projects score
63–91 because in a one-person study one voice is unanimity and `voices` is
correctly 1.00. §4(b) is the general form of this: the raw number is not
portable across study sizes and moves the wrong way. **Attainment (§5) is the
answer if a portable number is wanted**; the raw score's contract is the
sequence inside one study.

**Four cards still have no surprise to report.** Where a label covers *every*
quote on the axis (`n_c == K_all`, tiny projects), the statistic returns 0.5 and
says nothing — correctly, since with no variation there is nothing to be
surprised by. The shipped metric returns 1.00, which reads as a measurement.

**"Notably absent" is computable and cheap, but it is not a card.** MEASURED
across every (location × label) pair including the empty ones: 11 of 454 fall
below `surprise < 0.05` on the as-shipped label set, **6 of them empty** —
*"Neurodiversity in Programming: no sentiment at all in 3 quotes where 1.9 were
expected"*, *"Checkout & Delivery: nothing about Discoverability in 6 quotes
where 2.0 were expected"*. One of the six sits on exactly 0.05 (a two-quote
theme where `P(X=0) = 0.1`), decided by the last bit of a float rather than by
evidence — a reminder that the bar is a convention.

But an absent cell has no quotes, and every affordance on a card — quote list,
timecodes, participant dots, CSV export, the chat lens's grounding — is built on
having some. **The metric computes absence and makes it available; whether the
lens draws it is a layout question and is not settled here.** What matters is
that it is not structurally prevented, and the shipped multiplicative composite
with no negative range is.

**It does not know that Feedback and Status visibility are the same
observation.** §7 catches them only when they pick out the same *quotes*.
MEASURED, ikea's four UX codebooks tag an identical set of 33 quotes with 25
carrying codes from all four — so a better ranking over near-synonyms is still
a ranking over near-synonyms.

---

## 10. Abandoned options, and the evidence

**Swap lift for `adjusted_residual` on the existing matrix.** Fails on the case
it was reached for: `z = 0.00` in all 69 one-column cards, because
`(1 − col_total/grand_total)` is zero wherever a column carries the matrix.

**Detect synonymous codebooks study-wide, and use that to guard merging.** The
idea was to merge two cards only when their *groups* are near-identical across
the whole study, so a genuinely different reading would never be folded away.
MEASURED, it does not separate: `Status visibility` × `Feedback` — the canonical
near-synonym pair — reaches Jaccard only **0.46**, with `Feedback` × `Sentiment`
right behind at 0.36 and **zero** cross-codebook pairs anywhere above 0.5.
Co-occurrence surprise separates them no better (0.994 against 0.921), because
saturated coverage puts nearly every pair above chance. At 33 quotes and 45
groups every intersection is 2–6 quotes and the measure is noise. **Location-
local quote-set identity (§7) does the job the study-wide measure could not.**

**Rank on `|z|` and show direction.** Lets absence into the ranking, which puts
a card with no quotes above a card with quotes.

**Blend share-of-study with absolute voice count** —
`voices = √((n_eff/P) × (n_eff/(n_eff+2)))` — to stop one-participant studies
scoring 90. MEASURED, it compresses them (63–91 → 48–69) at the cost of a magic
constant, and does not fully work: one voice still scores 69 at the top of a
one-person study, because within that study one voice *is* everyone. Attainment
(§5) addresses the same problem without the constant.

**Keep `mean_intensity / 3`.** §2f — a measured +0.333 median gap between the
two kinds, in the direction that breaks the comparison. Correcting it costs
ρ 0.991.

**Drop heat entirely** (weights `0.50/0.50/0.00`). Also removes the bias, ρ
0.985, and loses a real dimension for nothing extra over the own-baseline form.

**Normalise `strength` per project as a share of the best card.** Makes the top
card 100% in every study, including a study that found nothing — §5's "% of
best" row.

---

## 11. The floor-independence check

Where `MIN_QUOTES_PER_CELL` should sit is a separate open experiment, so a
metric that needs it pinned would prejudge the answer. MEASURED, `project-ikea`
with the floor at 1 — 122 cells, both label kinds in one list:

| # | shipped `Signal` | | proposed `strength` | |
|---:|---|---:|---|---:|
| 1 | Product Detail × Mapping | 1 quote, 1 person | Beds & Mattresses × Behaviour | 2 quotes, 2 people |
| 2 | Checkout & Store Selection × Constraints | 1, 1 | Task orientation × Discoverability | 2, 2 |
| 3 | Top Navigation × Skeleton | 1, 1 | Beds & Mattresses × Structure | 4, 2 |
| 4 | Duvets & Bedding × surprise | 1, 1 | Session wrap-up × Sentiment | 2, 2 |
| 5 | App Prompt & QR Code × surprise | 1, 1 | Shopping Bag × Scope | 2, 2 |
| 6 | Search & Sort Results × delight | 1, 1 | Task orientation × Strategy | 2, 2 |

Corpus-wide: at `k ≥ 1` the proposed top ten holds **2** single-quote cells; at
`k ≥ 2`, **0** — and the median and range barely move. **The floor becomes a
policy choice rather than a load-bearing part of the maths**, which is what a
separate experiment needs it to be.

The same run answers the cross-shape requirement incidentally: it interleaves a
1-column matrix, a 5-, 7-, 8- and 10-column matrix, and the 7-column
sentiment-value matrix, in one sequence, with no per-matrix adjustment anywhere.

---

## 12. What would change the answer

1. **Richer data, which is the stated gate.** This corpus is thin: 107 cards,
   median 2 quotes each, median 1 participant per cell, and **only three
   projects carry both kinds of label at all** — one of them contributing a
   single sentiment card. §4 predicts the two kinds converge from N=5; the
   corpus cannot confirm it, only fail to contradict it. The numbers to
   re-measure when real data lands: the median rank percentile of each kind
   within a project (predicted ~0.50 either side), and the heat gap (predicted
   ~0.00).
2. **A researcher disagreeing with a specific pair.** The claim is a definition
   of "deserves attention first" (§1). The test is not a statistic, it is
   whether the order matches what a working researcher would pick up — which
   `docs/design-analysis-future.md` has been asking for since Feb 2026.
3. **The depletion half reading as noise.** If *"this place is unusually flat"*
   is not a finding, clamp `surprise` at 0.5 from below and drop the absence
   half — one line, costs §9's capability and nothing else. The cheapest thing
   here to reverse.
4. **The 0.7–0.9 empty band closing.** §7's threshold is read off the corpus.
   On denser data the band may fill in, and then it becomes a tuned number and
   has to be argued rather than measured.

---

## 13. Reproducing this

`experiments/signal_strength/` holds the spike. It opens a project database,
runs the app's own path (`_resolve_active_groups` → `_load_shared_data` →
`_compute_group_analysis`), and re-derives the shipped composite from raw cells
so both metrics come from one source. The reconstruction is asserted against
the app cell by cell, and the script exits non-zero if that ever fails — so a
future change that invalidates these numbers announces itself.

```bash
.venv/bin/python experiments/signal_strength/measure.py --summary
```

`--as-shipped` measures the label set the product renders today (codebook
groups plus the one-column Sentiment group) — use it for §2's defects. Without
it you get the proposal's label set (sentiment values beside codebook groups).
`--project <name>` scopes to one project, `--floor N` re-reports at a different
`MIN_QUOTES_PER_CELL`.

```bash
.venv/bin/python experiments/signal_strength/schemes.py
.venv/bin/python experiments/signal_strength/schemes.py --html experiments/signal_strength/normalisation-spike.html
```

prints §4's attainable range and §5's five presentations per project, or
renders them as a page to look at.

Two things to know before pointing any of it at a database:

- The databases under `trial-runs/<project>/.bristlenose/` are empty stubs. The
  real ones are under `trial-runs/<project>/bristlenose-output/.bristlenose/`.
- Several projects predate `quotes.durable_id` and `projects.pii_redacted`. Each
  database is **copied** before anything touches it; the copy gains the missing
  project columns and the ones still too old are skipped with a line saying so.
  8 of 11 real projects survive, which is the corpus quoted throughout.

One incidental defect found on the way and **not** acted on: `project-ikea2`
carries three codebook groups all literally named `New group`.
`_compute_group_analysis` keys `quote_group_weights` by group *name*, and
`build_matrix_from_contributions` keys cells `f"{row}|{col}"` by name too, so
same-named groups inside one framework silently merge into one column and then
emit one identical signal per group. It is user-created test data and it
affects both metrics equally, so it changes nothing here — written down so the
next person does not spend the cycle rediscovering it.
