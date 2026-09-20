---
status: partial
last-trued: 2026-09-20
trued-against: HEAD@main on 2026-09-20
---

# Signal Elaboration

## Changelog

- _2026-09-20_ — trued up. The header had been patched three times over a
  February body, which is the failure mode this doc is now the worked example
  of: a banner saying "the top-ten cap is gone" sat thirty lines above a Scope
  section still specifying "Top N cards only". Six single-claim corrections —
  Scope (every card, budget-guarded, now streamed), Caching (keyed on quote
  TEXTS and tag NAMES plus the prompt SHA, not ids), the prompt constraint list
  (two-part output, `||`, earned words; "exactly one sentence" is 0.2.0), the
  problem statement's card drawing, Pattern type (settled by WITHDRAWING the
  badge, not by choosing a control), and a Backlog listing five shipped items
  as outstanding. Anchors: `bristlenose/server/elaboration.py`,
  `bristlenose/server/routes/analysis.py`,
  `bristlenose/llm/prompts/signal-elaboration.md`; commits `08b4bb93`,
  `797079e6`, `54fdc615`, `6fc82d28`.

**Status is `partial`, deliberately.** Step 4, Step 5 and the worked examples
below are kept as the **pre-0.3.0 record** — they teach an instruction the
shipped prompt now forbids (one sentence, em-dash joins, group-name words), and
each already carries a dated truing note above it saying so. They are preserved
rather than rewritten because the delta is the point: the examples are what the
rewrite was reacting to. Read the notes, not the bodies.

How Bristlenose generates interpretive names and one-sentence summaries for framework signal cards.

_Last updated: 20 Sep 2026_

> **Prompt 0.3.0, and the cache can finally see it.** Step 4 was rewritten
> (earned words) and Step 5's paragraph break is now actually rendered. Both
> land on existing cards because `compute_content_hash` includes the prompt's
> SHA as of 20 Sep 2026 — until then a prompt rewrite invalidated nothing and
> would have reached none of the 54 cached elaborations. The top-ten cap is
> also gone: every card is elaborated, guarded by a payload budget rather than
> a count. See `docs/design-signal-card.md` §9.

---

## The problem

The analysis page detects signal concentration — it finds cells where a codebook group is overrepresented in a particular section or theme, ranks them, and shows the top cards. But the card currently says only *what was detected*, not *what it means*:

> **Homepage**
> Discoverability
> Signal 0.20 | Conc. 1.3× | Agree. 1.8 | Intensity 1.0
>
> _(Two things are out of date about this drawing, not one. The four metrics
> moved behind the hero chip on 13 Sep 2026 — one number, and a control that
> opens the working. And the **values** changed on 20 Sep (`6d247016`): this
> read `Signal 0.32 | Agree. 3.0`, which was arithmetically impossible on its
> face — it is worked example 4 below, Homepage × Discoverability, and only
> **two** participants speak in it (P2 and P3), so three effective voices could
> not happen. `simpsons_neff` was the unbiased population estimator and
> returned 3.00 for `[1,2]`; it is now the inverse Simpson index and returns
> **1.80**, with the composite falling to 0.195 accordingly. The old pair is
> the pre-fix baseline, kept here because it is what the shipped card showed
> for seven months. The problem the section describes is unchanged.)_

A researcher looking at this knows that something about Discoverability is concentrated on the Homepage. They don't know *what about Discoverability*. To find out, they have to read the quotes, recall what the codebook group means, and synthesise the finding themselves. This is exactly the interpretive work the tool should do for them.

The elaborated version:

> **Homepage:** Discoverability tension
> The top navigation makes product categories easy to find, but editorial content on the homepage body competes with the shopping entry point, forcing some first-time visitors to scan past it.

This tells the researcher what the signal *is*. They can hand that sentence to a stakeholder without further translation.

---

## Scope

**Framework cards only.** Sentiment signal cards (frustration, delight, etc.) are self-explanatory — the tag name *is* the interpretation. Framework cards (Norman, Garrett, UXR codebook) need elaboration because their group names are analytical categories, not plain language.

**Every framework card, streamed.** ~~Top N cards only — the 6–12 strongest.~~ Superseded twice. First the count became a payload budget (`ELABORATION_BUDGET_CHARS`), because quote length varies far more than card count does: one real project carries 16.5 KB of evidence on 5 cards and another 4.8 KB on 29, so ten cards can be a bigger ask than thirty. Then the *waiting* was removed rather than the work: `GET /analysis/elaborations` walks a codebook's signals strongest-first in chunks of `ELABORATION_CHUNK` and emits each finding as it lands, so a headline appears on a card already on screen. Custom codebooks are still skipped, for the reason in `design-signal-card.md` §7.7. (20 Sep 2026.)

---

## Output structure

Each elaborated signal card has three levels of progressive disclosure:

| Level | Example | Purpose |
|-------|---------|---------|
| **Section** | Homepage | Where in the product |
| **Signal name** | Discoverability tension | 2–4 words — what the finding is |
| **Elaboration** | The top navigation makes product categories easy to find, but editorial content on the homepage body competes with the shopping entry point, forcing some first-time visitors to scan past it. | One sentence — what it means and why it matters |

The signal name is the most important output. It must be scannable (2–4 words), use the group's vocabulary (not raw quote words), and encode the pattern type.

---

## Generation algorithm

For a signal card with section S, group G, and quotes Q₁..Qₙ each tagged with tag T:

### Step 1 — Lens

Read G.subtitle as the question this signal answers.

Example: Discoverability → "Can the user figure out what actions are possible?"

### Step 2 — Evidence

For each quote Qᵢ, interpret it through Tᵢ.definition. Determine *valence*: does the quote show the definition being satisfied (+) or violated (−)?

This is the critical step. The tag definition describes an ideal state ("the interface makes its possibilities obvious"). A quote either satisfies that ideal or violates it. The tag name alone doesn't tell you — you need the definition + the quote together.

Example:
- P2: "That's easy. That's in the top navigation." + `visible action` definition → satisfied (+)
- P3: "ikea stories but we just want to go shopping" + `visible action` definition → strained (−)

### Step 3 — Pattern

Classify the overall pattern across all evidence:

| Pattern | Condition | Signal name shape |
|---------|-----------|-------------------|
| **success** | All quotes positive | "[Group] strength" or "[specific] clarity" |
| **gap** | All quotes negative | "[Group] gap" or "[specific] mismatch" |
| **tension** | Mixed positive and negative | "[Group] tension" |
| **recovery** | Negative → positive sequence | "[specific] delay" or "[Group] recovery" |

The pattern type is a first-class data field, not just a label. It tells the researcher what *kind* of finding this is before they read the elaboration. Four states, colour-coded, instantly scannable.

### Step 4 — Signal name

> **Trued 20 Sep 2026 — the instruction below generates the wrong headline
> about half the time, and the rule that fixes it is one clause.**
>
> *"Use the group's vocabulary"* mandates exactly the words that carry no
> triage value, because **the group name is already on the card as the chip
> beside the headline**. Scored against the examples in this very section:
>
> | headline | earned words | |
> |---|---|---|
> | `Feedback strength` | 0 of 2 | group + pattern; says nothing the chip doesn't |
> | `Discoverability tension` | 0 of 2 | same |
> | `Discoverability gap` | 0 of 2 | same |
> | `Filter discoverability` | 1 of 2 | "Filter" is earned |
> | `Response delay` | 2 of 2 | group is *Feedback* |
> | `Expectation mismatch` | 2 of 2 | group is *Conceptual model* |
>
> **Three of six spend their entire budget restating the chip.** The rule is
> tight and testable: **no word in the headline may be the group name or the
> pattern word.** Same 2–4 words, every one earned from the evidence.
>
> Why the length cap stays: the headline is a **triage device** — the shortest
> version of the finding that lets a researcher decide whether the rest is worth
> reading — and `signal_name` doubles as the navigator row label
> (`AnalysisSidebar.tsx`, `SignalEntry`), where a sentence will not fit. The
> claim sentence below it is what differentiates; the headline gets them there.
> See `docs/design-signal-card.md` §2.

2–4 words. Combine the pattern type with specificity drawn from quote content. Use the group's vocabulary, not raw quote words.

Examples from real data:
- Feedback + all positive → "Feedback strength"
- Discoverability + mixed → "Discoverability tension"
- Discoverability + all negative (hidden features, forced exploration) → "Discoverability gap"
- Conceptual model + all negative (model mismatch tags) → "Expectation mismatch"
- Feedback + negative then positive → "Response delay"
- Discoverability + all positive (exploration tags, filters) → "Filter discoverability"

### Step 5 — Elaboration

> **Trued 20 Sep 2026 — THE PARAGRAPH BREAK THIS SECTION SPECIFIES HAS NEVER
> BEEN RENDERED.** The prompt says `||` *"marks a paragraph break, not a
> syntactic pause"* and that the card renders the evidence *"beneath the claim,
> in a tint, **after a blank line**"*. `renderLead`
> (`frontend/src/utils/leadSentence.tsx`) emits `<strong>{lead}</strong> {rest}`
> — **a single space**. One paragraph, run together.
>
> The decision was made, written into the prompt, and never implemented. Two
> consequences: the model has been told its evidence will appear as a separate
> paragraph and it does not, and the cached corpus still carries em dashes
> joining the halves from an earlier prompt version — some entries carry `||`
> *and* a dash. Any implementation must strip the legacy dash, not just split.
>
> Confirmed as still-wanted 20 Sep 2026: claim in full ink, a line break with
> vertical space, then the evidence as its own tinted paragraph. The reader
> takes the headline, the claim and the chip as one block, then a small breather,
> then the rest.

> **Trued 31 Aug 2026 — two corrections, and the second is the one that would
> stop an implementation working.**
>
> **1. The treatment is COLOUR, not weight.** This section teaches "two
> typographic weights — bold opening, regular continuation". That shipped, and
> was replaced on 31 Aug by the shared `.bn-lead-para` atom
> (`bristlenose/theme/atoms/lead-paragraph.css`): the lead in normal ink, the
> remainder in `--bn-colour-muted`, **both at `--bn-weight-normal`**. Weight was
> already spent on headings, starred quotes and destructive verbs; a bolded run
> inside body prose reads as emphasis-in-a-sentence, where a tint reads as rank.
> Chosen from `docs/mockups/lead-sentence-playground.html`, variant A.
>
> **2. The `||` delimiter is the contract, and it is not written down here.**
> The model writes a literal `||` into the elaboration
> (`bristlenose/llm/prompts/signal-elaboration.md`) and the renderer splits on
> it — `frontend/src/utils/leadSentence.tsx`, consumed by
> `AnalysisPage.tsx`. Signal cards pass **no `autoSplit`**, deliberately: an
> author's marker beats any heuristic, and an unmarked elaboration stays one
> rank rather than acquiring a break nobody authored. (The codebook-description
> surface shares the splitter and *does* pass `autoSplit`, because its prose is
> hand-written YAML carrying no marker.) A contributor implementing this section
> as written produces an elaboration with no `||`, which renders unranked.
>
> The four worked splits below are **unchanged and still correct** — they are
> about *where* the break falls, which is the part that did not move.
>
> Note the prompt still calls the halves "the bold assertion" and "the regular
> continuation". Doc and prompt currently agree with each other and disagree
> with the code, which is the worst of the three configurations; the prompt
> wording is deliberately left for a separate pass, since editing it changes
> model output and prompt versions are archived on change.

One sentence with two typographic weights. Structure:

**Bold opening** (the assertion): a self-contained clause stating what was found. This is the core finding — it should make sense on its own. End the bold portion at the first natural punctuation break: an em dash, a comma before a dependent clause, or an opening parenthetical. Aim for roughly the first third of the sentence by length.

**Regular continuation** (the evidence/nuance): specifics, examples, qualifying detail, or tension that supports the assertion. This is what makes the finding credible but isn't needed for scanning.

The split point is syntactic, not character-counted. The bold ends where the sentence's grammar naturally pauses before adding detail. If the entire sentence is a single clause with no natural break, restructure it to create one — add an em dash or subordinate clause.

Examples of good splits (bold | regular):
- **"Filters and sort options are easy to find and use"** | — participants confidently narrow results by price, material, size, and style without guidance.
- **"The top navigation makes categories easy to find, but editorial content competes with the shopping entry point,"** | forcing first-time visitors to scan past it.
- **"The category navigation hides specific product attributes"** | (like bed sizes) and forces participants to explore multiple paths before reaching their target.
- **"The homepage fails to acknowledge clicks immediately"** | — the participant had to click multiple times before the navigation responded.

Use vocabulary from the group subtitle, not the raw quotes. The sentence should be handoff-ready — a stakeholder who hasn't seen the quotes should understand the finding.

---

## Implementation

### Where it runs

This is an LLM call, not pure code. Step 2 (interpreting a quote through a tag definition) and step 4 (synthesising a pattern into a name) require language understanding. But it's a very constrained call:

- **Input**: group name + subtitle + tag definitions (from codebook YAML) + quotes with tags
- **Output**: `{ "signal_name": "...", "pattern": "success|gap|tension|recovery", "elaboration": "..." }`
- **Cost**: tiny — a few hundred tokens per card, 6–12 cards per project

### When it runs

On demand at serve time, when the analysis page loads. Not pre-computed during the pipeline (avoids stale summaries when tags change), not baked into static HTML (the render path doesn't have LLM access).

Flow:
1. Analysis page loads → frontend requests codebook signals (existing endpoint)
2. Frontend requests elaborations for top N signals (new endpoint)
3. Server loads group/tag definitions from codebook YAML
4. Server makes one LLM call per signal card (or batches into fewer calls)
5. Returns signal name + pattern + elaboration
6. Frontend renders the three-level card

### Caching

Cached in SQLite under two values, and neither is what this line used to claim. `compute_signal_key(source_type, location, group_name)` identifies the card; `compute_content_hash(quote_texts, tag_names)` decides whether the cached answer is still good — **quote *texts* and tag *names*, not ids**, plus the prompt's SHA since 20 Sep 2026. The SHA is the load-bearing part: without it a prompt rewrite invalidated nothing and reached none of the cached elaborations, so the instruction changed and the output did not.

### Prompt template

The prompt is the algorithm above, almost verbatim. Key constraints in the prompt:

- Signal name MUST be 2–4 words
- Signal name MUST use the group's vocabulary (provide group name + subtitle)
- Each part MUST be one or more complete sentences ending in a full stop (~~exactly one sentence~~ — changed in 0.3.0)
- The two parts MUST be separated by `||`, and neither may be joined with an em dash
- The name MUST use words earned from the evidence: no word may be the group name or the pattern word
- Pattern MUST be one of: success, gap, tension, recovery
- Valence assessment MUST reference the tag definition, not just the quote text
- Do not invent findings not supported by the quotes

The full tag definitions (definition + apply_when + not_this) are included for each tag that appears in the card's quotes. The group subtitle is the framing question.

### Data model

Add to the signal card response:

```json
{
    "signal_name": "Discoverability tension",
    "pattern": "tension",
    "elaboration": "The top navigation makes product categories easy to find, but editorial content on the homepage body competes with the shopping entry point, forcing some first-time visitors to scan past it."
}
```

These three fields are nullable — cards without elaboration fall back to the current display (group name as heading, no elaboration text).

---

## Pattern type as a first-class concept

The pattern classification (success/gap/tension/recovery) emerged from applying the algorithm to real data. It was not designed upfront — it fell out of the valence assessment step.

It's worth preserving as a standalone data point because:

1. **It's scannable** — a researcher can scan 12 cards by pattern badge alone and immediately know which are problems (gap), which are strengths (success), and which need nuanced reading (tension)
2. **It enables filtering** — "show me all gaps" is a natural researcher question
3. **It maps to stakeholder language** — "we found 3 gaps and 2 tensions in the checkout flow" is a sentence a product manager understands
4. **It's colour-codeable** — green/red/amber/blue is a universal vocabulary

~~Where and how to expose the pattern type in the UI is an open question.~~ **Settled 13 Sep 2026, and not by adding a control.** The badge was built, seen on real data, and *withdrawn* — a second chip beside the hero competed with it for the same glance. `pattern` stays on the wire and now has a job that is not decorative: it decides which quotes a codebook card counts as supporting its finding (`frontend/src/utils/quoteSelection.ts`). So the classification survived and its display did not, which is why nothing has to be regenerated if a better treatment is found.

---

## Worked examples (real IKEA data)

These 7 elaborations were generated by running the algorithm manually on the IKEA usability study (Norman codebook, 4 participants). See `docs/mockups/signal-elaboration.html` for the full visual mockup with algorithm traces.

### 1. Product Details — Feedback strength (success)

**Lens:** "Does the system communicate results clearly?"
**Tags:** all `system response`
**Valence:** all positive — participants confirm actions are acknowledged, respond to product descriptions and login greeting
**Elaboration:** Product detail pages communicate well — participants read descriptions with confidence, respond positively to the Swedish login greeting, and get clear confirmation when adding items to bag.

### 2. Product Listing — Filter discoverability (success)

**Lens:** "Can the user figure out what actions are possible?"
**Tags:** all `exploration`
**Valence:** all positive — exploration is productive, participants find filters and use them fluently
**Elaboration:** Product listing filters and sort options are easy to find and use — participants confidently narrow results by price, material, size, and style without guidance.

### 3. Text Notifications — Notification clarity (success)

**Lens:** "Does the system communicate results clearly?"
**Tags:** all `system response`
**Valence:** all strongly positive (intensity 2.3), single participant
**Elaboration:** Text notifications communicate the right information at the right time — the participant strongly valued recovery guidance, appointment confirmations, and pre-operative health checks delivered via SMS.

### 4. Homepage — Discoverability tension (tension)

**Lens:** "Can the user figure out what actions are possible?"
**Tags:** `first-time use`, `visible action` (×2)
**Valence:** P2 positive (nav works), P3 negative-then-recovery (editorial obscures path)
**Elaboration:** The top navigation makes product categories easy to find, but editorial content on the homepage body competes with the shopping entry point, forcing some first-time visitors to scan past it.

### 5. Category Navigation — Discoverability gap (gap)

**Lens:** "Can the user figure out what actions are possible?"
**Tags:** `hidden feature`, `exploration`
**Valence:** both negative — P3 can't find king size, P4 tries multiple nav paths
**Elaboration:** The category navigation structure hides specific product attributes (like bed sizes) and forces participants to explore multiple paths — Products, Rooms, Ideas — before reaching their target.

### 6. Product Details — Expectation mismatch (gap)

**Lens:** "Does user understanding match reality?"
**Tags:** both `model mismatch`
**Valence:** both negative — irrelevant recommendations, platform-inappropriate CTA
**Elaboration:** Product detail pages break participant expectations with irrelevant recommendations (chest of drawers while shopping for beds) and desktop-inappropriate CTAs (app download link leading to a QR code).

### 7. Homepage — Response delay (recovery)

**Lens:** "Does the system communicate results clearly?"
**Tags:** `delayed feedback`, `system response`
**Valence:** Q1 negative (no response), Q2 positive (eventually works)
**Elaboration:** The homepage fails to acknowledge clicks immediately — the participant had to click multiple times before the navigation responded, creating uncertainty about whether the interface was working.

---

## Why streaming, and not the three other ways (20 Sep 2026)

The outcome is recorded above; the alternatives are recorded here, because
"why not just elaborate during the pipeline run?" is an attractive idea that
will be proposed again by anyone who meets the wait without knowing it was
weighed.

- **Elaborate during the pipeline run.** Move generation to analyse time, where
  a wait is expected and there is already per-stage progress. The lens would
  then only ever read cache. **Rejected, not dismissed** — it is the strongest
  alternative and may still be right later. Two costs decided it now: a prompt
  change forces a re-analysis rather than a re-read (and the prompt SHA is in
  the cache key precisely so prompt changes DO invalidate), and cards created
  after the run — a new codebook, an AutoCode accept — still need a path, so
  the serve-time route has to exist anyway.
- **Background job + activity chip.** The house pattern AutoCode already uses.
  Rejected because it fills in one go when the job ends, which is a shorter
  wait rather than a progressive one, and it spends the machinery of a
  long-running job on something that should feel like page load.
- **Chunked client fetch.** Simplest transport, no new anything. Rejected on a
  measurement: the analysis is recomputed on every request with no caching, so
  N slices means N full recomputes of the codebook analysis on top of the LLM
  time. If analysis results are ever cached, this becomes viable again.

`ELABORATION_CHUNK = 6` is marked **GUESS** in the source and nothing measures
it. It is now measurable: elaboration calls reach `llm-calls.jsonl` as of the
same day (`801fb083`), so a real project's per-chunk latency will settle
whether six is the right trade between time-to-first-headline and prompt
overhead.

## Backlog

**Shipped, kept so the list is not read as outstanding work:** ~~prompt template file~~ (`bristlenose/llm/prompts/signal-elaboration.md`, version 0.3.0) · ~~API endpoint~~ (both, as it turned out: `?elaborate=true` for one answer, and `GET /analysis/elaborations` streaming) · ~~caching layer~~ (`uq_elaboration_project_signal`) · ~~batch generation~~ — **and then partly un-batched**: one call per codebook got every finding at the cost of the first one, so it is now one call per chunk of `ELABORATION_CHUNK`.
- **Pattern filtering** — UI control to filter signal cards by pattern type
- **Sentiment card elaboration** — evaluate whether sentiment cards benefit from elaboration (hypothesis: they don't, but test with real data)
- **An output meaning "no finding here"** — Step 3 forces a pattern from `{success, gap, tension, recovery}` and Step 5 forces a claim, so a card whose evidence does not cohere gets a *manufactured* finding. Worked example 20 Sep 2026: a `system response` card whose three quotes were checked against the tag definition — *"the system communicates the result of a user action clearly and immediately"* — had **two of three not meeting it at all** (image quality; a login greeting). The algorithm would still have produced a confident sentence. This matters more once every card is elaborated rather than ten per project, and a card that cannot honestly be elaborated is probably not a card — a better filter than any score threshold, because it tests whether the evidence supports a reading rather than a proxy for it.
- **Editable elaborations** — let the researcher edit the generated signal name and elaboration (same inline-edit pattern as quote text)
- **Export integration** — include signal names and elaborations in the exported report
- **Multi-codebook** — when multiple codebooks are active, generate elaborations using the relevant codebook's definitions (already partitioned by the existing API)

---

## References

- **Mockup**: `docs/mockups/signal-elaboration.html` — full visual with algorithm traces on real IKEA data
- **Codebook definitions**: `bristlenose/server/codebook/norman.yaml`, `garrett.yaml`, `plato.yaml`, `uxr.yaml`
- **Signal detection**: `bristlenose/analysis/signals.py`, `bristlenose/analysis/generic_signals.py`
- **The card itself**: `docs/design-signal-card.md` — anatomy, the chip label rule, quote selection
- **The score**: `docs/design-signal-strength.md` — open spike
- **Analysis API**: `bristlenose/server/routes/analysis.py`
- **Analysis future**: `docs/design-analysis-future.md`
- **Research methodology**: `docs/design-research-methodology.md`
