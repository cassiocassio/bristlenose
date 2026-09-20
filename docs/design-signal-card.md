# The signal card — anatomy, labelling and quote selection

_Last updated: 20 Sep 2026_

**Status: DECIDED IN MOCKUP, NOT IMPLEMENTED.** Every choice below was made
against real data rendered in the shipped design system. No product code has
moved. The mockups are `docs/mockups/signal-card-options.html` (the options),
`signal-card-v2.html` (the first pass, superseded), `signal-card-design-a.html`
(the chosen shape) and `sentiment-calibration.html` (the labelling study). The
harness is `experiments/signal_card_options/`.

Sibling docs: `design-signal-elaboration.md` owns the prompt that writes the
headline and the claim; `design-signal-strength.md` is the open spike on the
score. This doc owns the card.

---

## 0. Which version is which

**The card has had four generations. Two of them ship; two do not.**

| Gen | When | What it was | State |
|---|---|---|---|
| **1** | 23 Feb 2026 | the original card and its elaboration — `signal-card-expanded.html`, `signal-elaboration.html` | superseded by 2 |
| **2** | 26 Jul – 31 Aug 2026 | `mockup-signal-cards.html`; then the lead-paragraph atom, which moved the elaboration's two ranks from weight to colour (`a2ee11ad`) | superseded by 3 |
| **3** | **12–13 Sep 2026** | the overhaul: one navigation and one card list in one order (`aacf3e88`), the hero chip as a disclosure control (`54fdc615`), de-duplication, sections and themes interleaving unlabelled. Drawn in `signal-card-playground.html` and `signals-sidebar-row-layouts.html` | ⬅ **SHIPS TODAY** |
| **4** | **19–20 Sep 2026** | design A — whole cards fused into a stack, the location owned by the heading, four quotes open, the sentiment label rule, editorial quote selection. Drawn in `signal-card-design-a.html` | ⬅ **CURRENT DESIGN, NOT BUILT** |

**So: what you see in the app is generation 3. What this document specifies is
generation 4. Nothing in §2 has been implemented** — verified against HEAD on
20 Sep 2026.

### Generation 4's own lineage

The four mockups of 19–20 Sep are a sequence, not alternatives. Opening the
wrong one is the easy mistake:

```
signal-card-options.html      19 Sep   the menu — 29 labelled alternatives     SUPERSEDED
        ↓  nine decisions taken from it
signal-card-v2.html           19 Sep   first pass; built a hybrid that was     SUPERSEDED
                                       neither a fused stack nor a merged card
        ↓  the hybrid rejected, design A chosen
signal-card-design-a.html     20 Sep   the shape                               ⬅ CURRENT
        ↓  read alongside, not instead
signal-card-rules.html        20 Sep   each rule firing, with counterfactuals  ⬅ THE REVIEW ARTEFACT
signal-card-build-stages.html 20 Sep   shipped → tier 1 → tier 2
sentiment-calibration.html    19 Sep   the instrument behind the label rule
```

**One side branch, not superseded:** `signal-card-valence.html` (13 Sep) holds
eleven candidate treatments for showing a signal's valence. Generation 4
deferred it rather than rejecting it — `signal.pattern` still arrives on the
wire, so nothing has to be regenerated when it is picked up.

**What is being built now:** §9 tier 1 — the seven frontend changes that carry
no open questions. Everything else waits on the dependencies in §9's order
block.

---

## 1. What a card is

One React component renders every card in the analysis lens: `SignalCard` in
`frontend/src/islands/AnalysisPage.tsx`. It is not a library component — not
exported, not in `components/index.ts`, no test file of its own, sharing a
1,363-line file with the lens, the heatmap and the tooltip. What look like
different kinds of card are data variants of that one function.

A card is a **(location × tag group)** cell. Quotes join it when *any* of their
tags belongs to that group (`generic_signals.py:104`). Nothing reads the text
at grouping time, so **the grouping is evidence of a common label, not of a
common meaning** — whether a shared meaning exists is an open question the
elaboration has to answer, and sometimes the answer is no.

MEASURED, 9 trial projects, both axes: **131 cards over 89 locations**; 119
after excluding junk codebooks from the trial machine (`Chocolate`, `Booze`,
`New group`, `Pain`, `Pleasure`, `Mental model B`) and `Uncategorised`.

---

## 2. Decisions taken 20 Sep 2026

Each was chosen from labelled alternatives drawn with real data.

| # | Decision | |
|---|---|---|
| 1 | **Hero chip two steps down** | `--bn-text-label`, tighter padding, and `--bn-space-sm` between label and score — at `xs` they collided (`Mixed sentiments0.30`) |
| 2 | **The heading owns the location** | eyebrow removed from every card; heading takes the Quotes lens's own token, `--bn-text-heading` (1.125rem), no bottom rule |
| 3 | **Fused stack** | cards at a location join; the seam is a card's own `border-top` so it runs edge to edge |
| 4 | **Quotes open, capped at four** | one visible was not enough; the corpus tail runs to 56 |
| 5 | **Hero floats to the top-right corner** | title *and* elaboration wrap around and under it |
| 6 | **Earned-words headline** | no word may be the group name or the pattern word |
| 7 | **Flag as a chip prefix** | `Problem: frustration 0.42` |
| 8 | **Sentiment chip vocabulary** | a single value stays itself; several become `Positive` / `Negative` / `Mixed sentiments`. **Never a count** — the tags are there to eyeball |
| 10 | **Design A — whole cards** | see §3 |

### 2a. Why the heading matters more than it looks

Three surfaces name a location and they differed only in size: the Quotes lens
`h3` at `--bn-text-heading` (1.125rem), the analysis heading at
`--bn-text-label` (0.8125rem), the sidebar `.toc-sub-heading` at
`--bn-text-caption` (0.75rem). Same weight (`--bn-weight-emphasis`, 490), same
colour. The analysis heading **links to** the Quotes lens heading, so the two
now render the same object identically. The sidebar stays smaller because it is
navigation.

---

## 3. Design A, and the thing it replaced

Two coherent designs existed and a third was built by mistake.

**A — a true fused stack.** Whole cards, each a complete signal: its own
headline, claim, evidence, quotes, footer, participant grid. Several per
location, admitted by the marginal-value rule (§4). The seam is a card border.

**B — a true merged card.** One card per location, one location-level claim,
one quote list, every quote carrying all its tags. **B has a hidden dependency
that killed it for now:** elaborations are keyed `{axis}|{location}|{group}`, so
*there is no location-level finding anywhere in the data model*. Merging as a
layout change produces a card wearing its strongest facet's name — which showed
up immediately as the same headline printed twice, once on the card and once on
the facet inside it. B needs a new elaboration unit and a prompt to write it.

**The hybrid that was built first** had B's fragmented quote list with A's
borrowed identity: internal dividers that stopped inside the padding, holding
sections that were neither cards nor one card. It also re-introduced the defect
the whole exercise exists to remove — MEASURED, 3% of quotes are claimed by 2+
groups, and under facets each is drawn once per facet, concentrating in exactly
the over-grouped cards the design was meant to fix.

A was chosen. **It costs nothing in LLM spend**, because per-group elaborations
already exist.

---

## 4. The marginal-value rule

Strongest first; a later card is admitted only if it brings a quote no kept
card has shown. MEASURED: **119 cards in, 93 kept, 26 cut.**

Two further tests were named and are **not implemented**:

- **independent facets** — the spike's pairwise quote-set Jaccard. Its §7 reads
  a threshold of 0.8 off an empty band at 0.7–0.9, but *both* real pairs raised
  in review sat at **0.67**, under the cut. Likely wants ~0.6, or the quote-set
  test is not the whole test: Jaccard measures evidence overlap, and the
  question is meaning overlap. Two cards can share evidence and say genuinely
  different things (`system response` is a mechanism tag, `visual design` a
  quality tag — same moments, two altitudes).
- **strength** — deferred. §4 of the spike shows a fixed bar cannot work
  (1.41× ceiling drift across N=6–12); it has to be attainment.

---

## 5. The sentiment chip label

Formalised in `experiments/signal_card_options/label_rule.py`, fitted to 27
human judgements on real cards (`sentiment-calibration.html`).

```
1. nothing opposing          → name the leading feeling        MEASURED 5/5
2. both directions,
   enough material           → name the leading feeling        MEASURED 10/10
3. both directions, thin     → "Mixed sentiments"              12 cases, 8/2/2
```

**The finding that matters: volume decides, ratio does not.** A 3:1 split on
six units of feeling was judged `Mixed`; a 60/40 split on thirty units was
named. `surprise` is **neutral** and never makes a card mixed — MEASURED, four
cards were labelled `Mixed` on a neutral quote alone, one of them 76 units of
positive weight against 4 of neutral.

**There is no dominance test in the judgements.** Cards naming their leading
feeling at 42–47% of its own side are common; one names it where the leader
beats the runner-up 32 to 30. `VALUE_DOMINANCE = 0.60` survives in the code
because it was *asserted* ("65/35 frustration/confusion is definitely
frustration"), not because anything measured it.

### 5a. The calibration ran in the wrong regime — read this before tuning

MEASURED, and it is the most important caveat in this doc:

| corpus | median quotes/card | median sentiment weight | below `MIN_WEIGHT=7` |
|---|---:|---:|---:|
| fossda — 136k words, 9 people, 20 sessions | 20 | 40 | 18% |
| uxfriends + dick + tom | 2 | 6 | 84% |
| project-ikea pair — **829 words total** | 1 | 4 | 94% |

Twenty of the 27 calibration cases came from projects whose entire transcript is
shorter than one real session. On the one substantial real study the rule
outputs **82% value / 18% valence / 0% mixed** — `Mixed sentiments` never fires
at all — against 74/9/17 corpus-wide. So `MIN_WEIGHT = 7` sits in the middle of
the fixture distribution and far below the real one, and on a real study it is
never binding.

**The question the thread was circling is therefore unanswered, not answered
badly.** The corpus holds *three* real high-volume genuinely-split cards, all
fossda (weights 130, 40, 30 at 55/45, 56/44, 60/40), and the rule names a single
feeling on all three. Whether that is right is what a re-run on fossda's 17
sentiment cards would settle.

### 5b. The distribution is genre-conditional

MEASURED, and both distributions are the instrument working rather than a
defect — challenge someone with unfamiliar UX and you get confusion; ask them to
reflect on a career they are proud of and you get satisfaction.

```
                    satisf delight confid frustr confus doubt surprise
oral history (fossda)  30%    24%    16%    20%     2%    4%     5%
usability sessions     41%     0%     3%     3%    51%    0%     3%
```

Consequences: `doubt` is genre-bound (4% in reflective interviews, **0%** in
task-based usability) and its rarity is not a gap. `Negative` is rare
structurally — it needs 2+ negative values, no positive present, none leading —
and positive-only cards are both more common (28 vs 22) and more often
multi-value (14 vs 7), so `Positive` has twice the opportunities.

**Any threshold tuned on one genre will misbehave on the other.**

---

## 6. Quote selection is editorial, and separable from ordering

The shipped order is `(participant_id, start_seconds)` — alphabetical by
participant, then chronological (`generic_signals.py:105`, `signals.py:96`).
The lead quote is therefore *whatever the lowest-numbered participant said
earliest*, which is a byproduct rather than a choice, and it causes two visible
defects: sibling cards at one location systematically open with the same quote,
and on a 56-quote card the first four say nothing about the whole.

That order is **load-bearing** for the sequence treatment: `detectSequences`
fuses same-participant quotes within 17.5s into a visual run, which requires
them adjacent in the array. Re-sorting by strength would scatter them and could
manufacture false sequences, since the check is pid/session/gap and never that
the order is chronological.

**The resolution is that selection and ordering are separable.** Pick which
quotes to show editorially; then sort the chosen ones by `(pid, time)` as now.

```
supporting = quotes whose sentiment supports the label
pick       = strongest 3 supporting
if strongest dissenter has intensity >= 2:  pick.append(it)
return sorted(pick, key=(pid, start))
```

MEASURED over the 20 cards where selection matters:

| | no supporting quote visible | shows a dissenter |
|---|---:|---:|
| chronological (shipped) | 3 (15%) | 13 (65%) |
| editorial | **0** | **16 (80%)** |

**Fewer ungrounded labels and more dissenting quotes, not fewer.** The
reservation is deliberate and is not a statistical correction: *"a very strong
one in five saying something clear and interesting with intensity earns a right
to be seen"* — the card is the most illuminating thing learned about a place,
not a proof of its label.

**Open:** the criterion is *high clarity **and** high intensity*, and only
intensity exists on a quote. The dissenter slot is currently picked on
forcefulness alone, which will sometimes surface something loud and muddy over
something quiet and sharp. Tracked as a Value/Could item.

---

## 7. Defects found, not yet fixed

1. **The elaboration gutter.** `.signal-card-top` is a flex row and the
   elaboration sits in `.signal-card-identity`, its left child — so it *cannot*
   reach the space under the hero. Unreachable by construction. Decision 5 fixes
   it, and needs the hero emitted first for the float to catch the text, which
   puts the chip before the title in reading order.
2. **The claim/evidence break has never been rendered.** The prompt says
   *"`||` marks a paragraph break, not a syntactic pause"* and *"the card
   renders this beneath the claim, in a tint, after a blank line"*. `renderLead`
   emits `<strong>{lead}</strong> {rest}` — a single space. The decision was
   made, written into the prompt, and never implemented; cached elaborations
   still carry em dashes from an earlier prompt, some with `||` *and* a dash.
3. **Elaboration is gated by a project-wide top-10.**
   `_elaborate_top_signals` pools every non-custom codebook's signals, sorts by
   composite and takes `DEFAULT_TOP_N = 10`. So the cut slices through locations
   arbitrarily, and **every card from a custom codebook is skipped
   unconditionally, at any score**. It is one batched call cached on a content
   hash — project-ikea's 29 cards carry 4,791 characters of evidence — so the
   cap is not buying anything on a realistic study.
4. **Fields on the wire, rendered nowhere.** `signal.pattern` (deliberately —
   the chip was withdrawn 13 Sep; MEASURED 45 tension / 24 success / 16 gap /
   7 recovery across 92 elaborations), plus `signal.confidence`,
   `signal.count` and `quote.segmentIndex`, none of which have a stated reason.
5. **`classify_flag` is computed for every sentiment signal, reaches the API
   (`analysis.py:95`, `:389`) and is rendered nowhere.** Its documented value
   `Pattern` is **unreachable** — an exhaustive sweep returns only
   `Win / Problem / Niggle / Success / Surprising`.
6. **`.signal-rank`** in `theme/organisms/analysis.css` has zero consumers
   anywhere in the tree.

---

## 8. Open questions

1. **Does a genuinely split, high-volume card say `Mixed sentiments`?**
   **DEFERRED 20 Sep 2026 — waiting on more real study data.** §5a has the
   measurement: the corpus holds exactly **three** cards that are both
   high-volume and genuinely split (weights 130, 40 and 30 at 55/45, 56/44 and
   60/40), all of them fossda's, and the rule names a feeling on all three.
   Three cases cannot settle it either way.

   *What answers it:* the same method that produced the first 27 judgements —
   cards with the chip blanked, judged by eye — run on a study in the **right
   volume regime**. `build_calibrate.py` does this; point it at the new corpus.

   *The trigger:* the next real multi-participant study of any size. Not more
   fixtures — §5a is the record of what calibrating on those produced.

   *What happens meanwhile:* `MIN_WEIGHT` stays a **GUESS** in
   `label_rule.py`, and on real data it is never binding — so the shipped
   behaviour is "name the leading feeling", and `Mixed sentiments` effectively
   does not appear. **That is the risk of deferring:** a guess that never fires
   looks like a settled decision, and nobody has cause to revisit it. The
   provenance marker in the source is what stops that, so leave it there.
2. **Elaborate before or after the filter?** The filter tests quote sets, not
   prose, so it can run first — but "write titles for everything" then means 93
   titles, not 119.
3. **Can the prompt return nothing?** Step 3 forces a pattern and Step 5 forces
   a claim, so a card whose evidence does not cohere gets a manufactured
   finding. A card that cannot honestly be elaborated is probably not a card —
   a better filter than any score threshold, because it tests whether the
   evidence supports a reading rather than a proxy for it.
4. **Does the score stay visible?** It may become instrumentation — a
   development affordance for judging the cut-off and the ranking — in which
   case it need never be portable across studies, and `serve --dev` is the
   precedent.

### 5c. Chip casing — noted, not blocking

The chip capitalises and the quote badges do not: `Frustration 0.42` above a
badge reading `frustration`. **Accepted as-is for now** — a visual-convention
pass, not a blocker.

The reasoning, so it does not get re-opened at build time. The framework
codebooks are internally consistent (**groups 56/56 capitalised, tags 23/234 —
and the 23 are proper nouns**: `Fitts:`, `Gestalt:`, `Doherty:`), and
`enums.json` already carries the capitalised sentiment forms in all 21 locales.
**Capitalisation is not uniform across languages** — German capitalises every
noun, so `Frustration` is obligatory there whatever English decides — so the
capitalised form is both already translated and already correct, and a lowercase
rule would mean 21 files and a per-language argument.

**And the convention cannot be enforced anyway**, which is the argument against
spending more on it: user tags and user tag groups are free text and can be
whatever the researcher types. A rule that holds only for the shipped
frameworks is a house style, not an invariant.

*One real defect in the same area, which IS worth fixing at build time:* the
`enums` translation in `SignalHero` is gated on `isSentiment` —
`isFromSentimentLens`, the fallback path — so **the card that actually renders
never reaches it** and falls through to the raw `columnLabel`, showing the
untranslated string `Sentiment`. The capitalisation machinery exists; the
rendered card cannot get to it. Folded into tier 2 item J.

*Known inaccuracy in the mockups:* every card drawn on 19–20 Sep renders the raw
lowercase value in the chip, because the build script bypasses i18n. The chip
should read `Frustration`, not `frustration`. Cosmetic, corrected on the next
rebuild.

---

## 9. Build plan

Verified against HEAD on 20 Sep 2026: **none of §2 is implemented.**
`visibleQuotes = signal.quotes.slice(0, 1)`, `.signal-card-source` renders on
both branches, `.signal-cards` is still `repeat(auto-fill, …)`,
`renderLead` still emits a single space, `DEFAULT_TOP_N` is still 10.

### Tier 1 — no open questions, frontend only

Seven changes, no data model, no LLM, no new endpoint. They can land together.

| | change | where |
|---|---|---|
| A | chip to `--bn-text-label`, tighter padding, `--bn-space-sm` gap | `analysis.css` |
| B | drop the eyebrow on both branches; heading takes `--bn-text-heading`, no rule; **move the Quotes-lens deep link from the card to the heading** | `AnalysisPage.tsx`, `analysis.css` |
| C | fused stack — `:first-child`/`:last-child` radius, `border-top: none` on the rest, drop the grid, drop the hover shadow for a background tint | `analysis.css` |
| D | `visibleQuotes` cap 1 → 4; toggle label follows | `AnalysisPage.tsx` |
| E | float the hero; emit `.signal-card-right` **before** `.signal-card-identity` | `AnalysisPage.tsx`, `analysis.css` |
| F | `renderLead` emits two paragraphs; **strip a leading em dash** from the remainder — the cached corpus predates the rule and some entries carry `\|\|` *and* a dash | `leadSentence.tsx`, `lead-paragraph.css` |
| G | delete `.signal-rank`; drop `confidence`, `count`, `segmentIndex` from the adapters | `analysis.css`, `AnalysisPage.tsx` |

**B and E both touch reading order.** E puts the chip before the headline for a
screen reader; the fix is `order` on a flex parent or an ARIA reorder, decided
at build time rather than discovered.

### Tier 2 — logic to write, design settled

| | change | note |
|---|---|---|
| H | admission rule: keep `dedupeSignals`' novel-quote test, add pairwise Jaccard clustering, **fold rather than delete** | spike §7. Threshold ~0.6, not its 0.8 — see §4 |
| I | editorial quote selection, then sort `(pid, time)` | §6. **Gap: the rule selects quotes supporting the *sentiment* label, and a codebook card has none.** Needs an equivalent — support the `pattern`, or fall back to intensity |
| J | sentiment chip label + vocabulary | `label_rule.py` is written and validated; port it server-side so the label is on the wire |
| K | flag as a chip prefix — **one chip, not two** | degrades cleanly; see below |

**K is a prefix inside the existing chip, not a second chip.** G1 stacked a
separate chip under the hero and was rejected 20 Sep 2026: *"two chips is too
complex visually, adds confusion — the eye will jump to a single patch of
colour."* The chip's job is to be the one thing the eye lands on in that corner;
splitting it into two competing patches destroys that, and it is the same
failure the `pattern` chip had on 13 Sep (*"competed with the score for this
exact corner"*). Decision 7 is `Problem: frustration 0.42` as **one button with
one background**, the flag a `<span>` before the label. **That means a null flag costs nothing** — the chip
renders `frustration 0.42` with no gap and no placeholder, so K never blocks
anything; it lights up when J lands.

**It is not implementable *today*, and the reason is seven days old.**
`classify_flag` is passed the *column* label; for the sentiment framework that
is the literal string `"Sentiment"`, which is not in `SENTIMENT_VALENCE`, so it
returns `None` —
`classify_flag("Sentiment", …) → None` while
`classify_flag("frustration", …) → Problem`. **The flag is null on every card
that renders.** The fix follows from J: compute the flag over *the subset the
adaptive label names*, so a card whose chip says `frustration` gets the flag for
its frustration quotes. That also makes J a prerequisite for K.

*History, since "is this new?" is the natural question.* `classify_flag` was
written 19 Mar 2026 (`2a822d11`) and **has never been rendered by either
renderer** — zero commits touch `flag` in `AnalysisPage.tsx` or the frozen
vanilla `analysis.js`. The codebook call site passing `col` has been inert from
the day it was written. What changed is *reachability*: until 13 Sep 2026 the
rendered cards came from the sentiment-**value** path (`signals.py:111` passes a
real value, and the flag populates), and `aacf3e88` — "one navigation, one card
list, one order" — made the sentiment-**group** card primary. So the field went
from computed-but-unused to structurally null on everything that renders, and
nothing was red because nothing consumed it. Same shape as the CLAUDE.md gotcha
about deleting a UI surface orphaning a wire contract.

### Tier 3 — blocked on a decision

| | change | blocked on |
|---|---|---|
| L | `MIN_WEIGHT` | **DEFERRED 20 Sep 2026** — waiting on a study in the right volume regime, not more fixtures. §8.1 has the trigger and the risk |
| M | elaborate every card, not ten | needs the escape hatch: the prompt able to return *no finding* |
| N | Step 4 earned-words rewrite | **needs M's cache fix first** |
| O | score visible, or dev-only instrument | §8.4 |

**N has a hard prerequisite that is easy to miss.** `compute_content_hash`
hashes quote texts and tag names **and nothing else** — not the prompt version.
So rewriting Step 4 invalidates nothing: all 54 cached elaborations keep the
names they were given under the old instruction, forever. **Add the prompt's
`version:` frontmatter to the hash before touching the prompt**, or the change
silently applies only to cards generated after it.

### Order

```
Tier 1  →  J  →  K            (label before flag)
        →  I                  (selection needs J for sentiment cards)
        →  H                  (independent)

cache-hash fix  →  N          (prompt change needs invalidation)
fossda re-calibration  →  L
escape hatch design  →  M
```

Tier 1 is the whole visual change and depends on nothing.
