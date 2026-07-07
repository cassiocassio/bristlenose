# Tag overload — visual overlap of same-meaning tags

**Status (7 Jul 2026): exploration + one shipped decision. Not a committed roadmap item.**

> **BLUF.** Tags are highlighters; when several say the same thing they stop highlighting and start shouting, and the reader wants to turn them off. The fix is *visual* (stack same-meaning tags into a deck, show one, hint the rest), never *destructive* (no merge). **Phase 1 — defined and worth building now:** collapse **exactly-same-text** tags on a quote into a deck-of-cards (read one, see the edge of the other). Pure string equality, no thresholds, no LLM, non-destructive. **Later phases — captured, not scheduled:** near-identical text, then true semantic overlap (the hard one). A live calibration experiment (below) proved the semantic version can't be threshold-tuned from small studies yet, so it waits for real data.

Cross-refs: [design-codebook-island.md](design-codebook-island.md) (tag sidebar), [design-autocode.md](design-autocode.md), [design-finding-weight.md](design-finding-weight.md), [methodology/tag-rejections-are-great.md](methodology/tag-rejections-are-great.md) (the tuning corpus).

---

## 1. The problem

A tag is a **highlighter** — a visual marker of useful meaning on a quote. A highlighter that marks everything is off. When a quote accumulates several tags — some identical, some saying the same thing in different words, some merely co-occurring — they stop being *figure* and start fighting each other and the actual words of the quote. The researcher's instinct becomes "turn them off," at which point tags have inverted their purpose.

So this is a **signal / cognitive-load problem, not a data-integrity problem.** The goal is quiet and high signal-per-token, not a clean database. And the simplest, most defensible case — two tags with *identical text* on one quote — is pure disrespect for the reader's time: you're making them read the same word twice.

**Data model (facts, from code):**
- `QuoteTag` join carries `source ∈ {human, autocode, pipeline}` — provenance already exists (`server/models.py:462–476`); unique constraint `(quote_id, tag_definition_id)` stops the *same* definition landing twice, but same *text* in two groups = two `TagDefinition` rows = two badges.
- `TagDefinition` is instance-scoped, resolved by lowercased name *within* a group. Framework codes carry rich definitions (`TemplateTag{name, definition, apply_when, not_this}`, `server/codebook/__init__.py`); cultivated codes get a synthesized `TagPrompt` (`server/models.py:100–135`).
- Sentiment is the always-on codebook (applied from the pipeline `Quote.sentiment` field on import), so it's the code most others collide with.
- **No semantic comparison of codes exists anywhere.** Only fuzzy logic is `difflib.get_close_matches(0.9)` in `autocode.py` — name *resolution*, not dedup.

---

## 2. Phase 1 — exact-text visual overlap (the deck of cards) — DEFINED

**The smallest implementable surface.** When a quote carries two or more tags with **identical text** (normalised, case-insensitive), render them as a **deck of cards**: one face card fully legible, the others tucked behind with just an edge showing. You read the word once and *see* that there's another underneath. Click/hover fans them apart; dismiss slips them closed.

**Why it's worth doing on its own:** it's **user respect** — "don't waste my time with two identical tags." No researcher gains anything from reading `frustration` twice on one quote.

**Why it's safe and cheap:**
- **Pure string equality** on the tags already present on a quote. No overlap math, no thresholds, no LLM, no telemetry. Implementable entirely in the tag-render layer.
- **Non-destructive / presentation-only.** Both `TagDefinition`s and `QuoteTag`s remain; the deck is a live view. Hide a framework (existing per-group eye toggle) and its card leaves the deck; the rest re-flow.
- **Homograph-safe.** Even if the two identical-text tags are different concepts (`green` colour vs `green` novice, coinciding on one quote), the deck **never hides** — the edge signals "another tag here," and the fan reveals it with its group/framework as context to disambiguate. It only stops you re-reading the same string; it doesn't collapse meaning.

**Which card is on top (precedence cascade):**
1. **Manual/human beats auto** on identical text (a human deliberately made it).
2. Otherwise, **codebook precedence = sidebar order** — the `CodebookGroup.sort_order` that's already persisted today; drag a codebook above another to set which of its tags wins the face slot.

**Honest scope note:** the *shipped* frameworks use deliberately distinct vocabularies, so exact-text collisions don't arise between them. Phase 1's immediate bite is on **manual tags that duplicate an existing label** (a researcher types `frustration`, already a sentiment code) and **user-authored frameworks** that reuse words. Small blast radius today — but cheap, safe, and the correct foundation for later phases.

**Interaction & motion — foveal stability (applies to the deck now and any later fan):**
The eye is already fixated on the deck; any reflow/repaint/reorder throws content out of the fovea and forces a re-saccade (the felt "jump"). So: **nothing the eye is locked onto may move; everything animates around a fixed point.**
- **The face card is the pinned anchor** — it stays at its pixel; others emerge from behind it (`transform-origin` at the face card, like a held deck).
- **Expansion overlays, never reflows** — the fan renders on an absolutely-positioned layer; quote text and siblings don't move. (Same conclusion the a11y analysis reached — popover/overlay over inline expansion.)
- **Transform + opacity only** — the compositor-only properties; touching width/height/top/left is what *becomes* the jump.
- **Hidden cards already present** — no lazy-load/re-sort on expand; expand is a pure transform.
- **Short, symmetric, no showing off** — open fast and settle (ease-out ~120–160ms), close as fast (ease-in); no spring/bounce. Peek, then slip closed.
- **Trigger:** click as the contract (click-open, click-away/Esc-close), fast symmetric motion so it *reads* as peek-and-release; hover-peek as a pointer-only enhancement, never instead of click.

**Accessibility must-dos** (collapsed stacks are a known SR trap):
- The collapsed control is a real `<button>` with `aria-expanded`; toggles on Space/Enter. The "+N"/edge affordance is a native button, not a label.
- Collapsed cards are **programmatically unreachable** when collapsed (else keyboard/SR users tab into hidden tags); SR summary announces the hidden count; popover exposes `aria-haspopup`/`aria-expanded`/`aria-controls`; every expanded card *and its delete control* reachable by Tab.

---

## 3. Principles we nailed down (cross-cutting)

- **Presentation, never destruction.** No merge in this line of work. Manual-code merge already exists separately (drag-and-drop in the codebook); we don't touch it, and we **never merge across frameworks** — combining frameworks (Nielsen + Norman) yields overlap *and* difference, and the difference is signal. The layering is a live derived view; visibility-toggle gives full reversibility for free. (The QDA tools' merge model — NVivo/ATLAS.ti, §8 — is prior art we deliberately don't follow; their confirmation/audit ceremony guards *destructive* merges, which we don't have.)
- **No threshold/config UI. Tune defaults instead.** A slider is a *symptom of an untuned system*; the human response is "errm, complicated, I'll just hit OK and worry later," so it transfers unease, not control. The existing autotag confidence-histogram (`ConfidenceHistogram.tsx` / `ThresholdReviewModal`) is a candidate for *removal*, not a template. Ship invisible tuned constants; a knob is a last resort.
- **Do the hard work to make it easy for the user.** The easy escape-hatch (a `Human/AI/Both` provenance filter — cheap, `source` already exists) treats the *symptom*; the hard layering work removes the *cause*. The filter is a deferred fallback, not the headline.
- **Overlap decides grouping; text decides labelling; provenance decides the survivor.** (Relevant from Phase 2 on.)

---

## 4. What we learned (the signal analysis — for later phases)

The central lesson, arrived at four times over: **the number you'd naively measure is never the number you want.**

- **Text similarity is a false friend.** Identical text can be homographs (`green`/`green`); true synonyms share no text (`error handling` / `failure mode`). So beyond Phase 1's exact match, *text cannot detect same-meaning.*
- **Application overlap is the real signal — but it's *also* a false friend.** High co-occurrence between codes on *different axes* is complementary, not redundant (see cause/effect below). And at small N it's dominated by coincidence (see §5).
- **The 2×2** (overlap = deciding axis, text = presentation axis):

  | | high overlap | low overlap |
  |---|---|---|
  | **same text** | group → one label, fan reveals provenance (Phase 1 is the *cheap subset* of this) | **disambiguate**: homograph; show framework context |
  | **different text** | group → *bundle of near-synonyms*; fan shows **both** labels | leave alone |

- **Directional ≠ magnitude.** Symmetric overlap = synonym; asymmetric containment (A⊂B) = "child of" → a *nesting* treatment, not equal stacking. Can't ride a 1-D magnitude threshold.
- **Sentiment × framework is a *lens* problem, not a collapse problem.** They're different axes — emotion vs design-finding — so their overlap is signal (this emotion accompanies this cause), not redundancy. Solve cross-axis overload with **the lens** (view one axis at a time — the per-group eye toggle promoted from on/off to foreground/background), never collapse. Within-axis redundancy (two usability frameworks naming one flaw) is the collapse case.
- **Cross-framework convergence is signal.** When two lineages independently flag the same quote, the researcher wants to *see* the agreement — so the fan preserves "both frameworks flagged this"; it never merges the fact away.

---

## 5. The data — calibration run 1 (7 Jul, N=42, real autocode)

Drove autocode headless (read-only, wrote nothing) over project-ikea (42 quotes) with nielsen + norman + uxr + garrett, 1 tag/quote/framework → 189 nonzero cross-framework overlap pairs. Script: `scratchpad/overlap_experiment.py`.

**Jaccard distribution (cross-framework code pairs, ∩≥1, |set|≥2):**

```
0.0–0.1 |  7
0.1–0.2 | 96   <- dominant low-overlap mass
0.2–0.3 | 49
0.3–0.4 | 19
0.4–0.5 |  7
0.5–0.6 |  3
0.6–0.7 |  6
0.7–0.8 |  0
0.8–0.9 |  0
0.9–1.0 |  2   <- both are 2-quote coincidences, NOT synonyms
```

**Findings:**
- **No bimodal valley at this N.** A low-overlap mass + thin noisy tail, no clean coincidence/synonym split to place a threshold in.
- **High Jaccard = small-set coincidence, not synonymy.** The J=1.0 pairs are 2-quote flukes: `nielsen: emergency exit` × `norman: logical constraint`; `nielsen: platform convention` × `garrett: value proposition`. A magnitude-only threshold would collapse gibberish.
- **The concept works where N is adequate:** the real synonym `norman: model mismatch` × `uxr: expectation mismatch` (J=0.50, ∩3, cross-lineage) surfaced — a genuine collapse candidate — but sits *mid*-distribution, not separable by magnitude.
- **Cause/effect (sentiment × framework) held:** `confusion × expectation-mismatch` (J.50), `frustration × friction` (contain 1.0), `satisfaction × focused-design` (contain 1.0) — robust across the thin-data and N=42 runs.
- **The predicted NNG lineage-skew was NOT visible** — same- and cross-lineage look alike, both noise-swamped. Neither confirmed nor refuted; the earlier confident claim over-stated its detectability at N=42.

**What the run proved:** the naive "compute Jaccard → find the valley → set a threshold" plan does **not** work at real small-study scale. Two corrections it forces: (1) a **minimum-support gate** — trust the intersection *count* (∩≥~4) + containment + plausibility, not just the %; this empirically confirms the "small-N → show both" default. (2) **Much more data** is needed before any threshold is computable.

---

## 6. Future phases (speculation — captured, not scheduled)

- **Phase 2 — near-identical text.** Fuzzy match (the existing `difflib` 0.9 cutoff is the natural tool) for `satisfaction`/`satisfied`/`user satisfaction`. Still label-based, still cheap; extends the deck to trivially-different spellings. Beware: fuzzy text remains a false friend for meaning.
- **Phase 3 — semantic / overlap-driven grouping (the hard one).** Group by **application overlap with a minimum-support gate**, per-quote, within-axis. Continuous visual (the deck squishes tighter as overlap rises — "sliding scale, not a cliff"), rendered in a *few perceptible steps* (nobody sees 73%-vs-76% tuck). Directional overlap → a *nesting* treatment. Cross-axis (sentiment × framework) → **the lens**, not the deck.
- **Threshold tuning without a UI.** The tuning engine is **tag-rejection telemetry** ([methodology/tag-rejections-are-great.md](methodology/tag-rejections-are-great.md)): the accept/reject/edit stream tunes not just prompt *definitions* (as that doc frames it) but the *confidence threshold* — accept-vs-reject at each confidence level is a precision-vs-confidence calibration curve → set auto-accept where precision is high → review band shrinks → the histogram screen retires ("users just see worth-looking-at tags"). **Gap to fix in that doc:** its 4-field event model omits the **proposal confidence** — the exact axis to calibrate on; add a *coarse confidence bucket* (privacy-safe: a property of the machine proposal, not the researcher/quote). Collection is deferred post-TestFlight.
- **The `Human · AI · Both` provenance filter** — a cheap escape-hatch (the `source` field already drives it). Deferred fallback, not the headline; captured as an idea worth having once the layering exists.

---

## 7. Open questions

- **Where does the semantic threshold come from?** Not from a 42-quote study. Needs a large real UX study (none in the trial data — big ones are synthetic stress-tests or non-UX oral histories) or the post-TF telemetry corpus. Optional probe: rerun `overlap_experiment.py` on fossda (334q) to see if *scale alone* makes the distribution stabilise — caveat, oral-history content muddies the synonym signal; marginal value.
- **Calibration-sample bias.** The sample must span *intellectual distance*, not just register: Nielsen × Norman overlap by construction (NNG co-founders → high end only); need cross-lineage and distant pairs to see a floor. (At N=42 this skew was swamped; revisit at scale.)
- **Detection-aggregation scope.** Across which projects do we aggregate overlap evidence — one project, or a client's folder? Leans cross-project (more projects agreeing = stronger), but because it's presentation-only and reversible, a wrong grouping costs one visibility toggle to undo — a *tuning* question, not a governance fork.
- **Codebook/evidence scope.** Current model has only *instance* + *project*. A `client/folder/workspace` scope may be wanted so evidence and taxonomy belong to one client. (Only matters once cross-project aggregation is built; moot for Phase 1.) Ref [design-multi-project.md](design-multi-project.md).
- **The lens: one codebook lit at a time, or several?** (unresolved)

---

## 8. Prior art & references

- **QDA methodology (deep-research, cited).** Reconciling redundant codes is canonical, but the resolution is *human judgement surfaced by the tool, never mechanical dedup* (Saldaña: codes subsumed/relabelled/dropped by resonance). **Premature-lumping warning** (Saldaña: "lumping may lead to a superficial analysis"; "big difference between fuzzy and vague") → overlap is a *prompt*, never an auto-merge trigger. Tools (NVivo/ATLAS.ti) make merge deliberate, non-destructive, audit-trailed; MAXQDA keeps AI codes provenance-separate (`AI:` prefix, distinct colour). DeCuir-Gunby: an a-priori (sentiment) + emergent (user) two-origin codebook is a recognised structure.
- **Visual/interaction prior art (deep-research, cited).** Anchor pattern = **face-pile resting look × iOS/macOS notification-stack motion.** Ant `Avatar.Group` (−8px overlap, `#fff` separating border, `+N` → popover); iOS/macOS notification stacks (click, not hover, to expand; graduated opacity 100/75/50%; ~10pt y-offset; layered soft shadows, z-index = N−index); Carbon "operational tag" (expand-to-popover, not free-floating fan); Atlassian motion bands (50–150ms states, 150–400ms transitions). Pitfall: the literal "fly apart" is the least accessible option and shifts layout — use a proper disclosure with the fan as flourish.
- **Session research artefacts:** two deep-research reports (QDA methodology; stack/fan-out visual UX) and two codebase audits (codebook/sentiment data model; fuzzy/overlap infrastructure) informed this doc.
