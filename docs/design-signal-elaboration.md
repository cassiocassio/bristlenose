# Signal Elaboration

How Bristlenose generates interpretive names and one-sentence summaries for framework signal cards.

_Last updated: 23 Feb 2026_

---

## The problem

The analysis page detects signal concentration — it finds cells where a codebook group is overrepresented in a particular section or theme, ranks them, and shows the top cards. But the card currently says only *what was detected*, not *what it means*:

> **Homepage**
> Discoverability
> Signal 0.32 | Conc. 1.3× | Agree. 3.0 | Intensity 1.0

A researcher looking at this knows that something about Discoverability is concentrated on the Homepage. They don't know *what about Discoverability*. To find out, they have to read the quotes, recall what the codebook group means, and synthesise the finding themselves. This is exactly the interpretive work the tool should do for them.

The elaborated version:

> **Homepage:** Discoverability tension
> The top navigation makes product categories easy to find, but editorial content on the homepage body competes with the shopping entry point, forcing some first-time visitors to scan past it.

This tells the researcher what the signal *is*. They can hand that sentence to a stakeholder without further translation.

---

## Scope

**Framework cards only.** Sentiment signal cards (frustration, delight, etc.) are self-explanatory — the tag name *is* the interpretation. Framework cards (Norman, Garrett, UXR codebook) need elaboration because their group names are analytical categories, not plain language.

**Top N cards only.** Generate elaborations for the 6–12 strongest framework signals. Don't pre-compute for every cell in the matrix — most are weak or empty. If a user drills into a weaker card later, generate on demand.

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

2–4 words. Combine the pattern type with specificity drawn from quote content. Use the group's vocabulary, not raw quote words.

Examples from real data:
- Feedback + all positive → "Feedback strength"
- Discoverability + mixed → "Discoverability tension"
- Discoverability + all negative (hidden features, forced exploration) → "Discoverability gap"
- Conceptual model + all negative (model mismatch tags) → "Expectation mismatch"
- Feedback + negative then positive → "Response delay"
- Discoverability + all positive (exploration tags, filters) → "Filter discoverability"

### Step 5 — Elaboration

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

Cache elaborations in SQLite keyed by a hash of (group_id, section, quote_ids, tag_ids). Invalidate when quotes are added/removed or tags change. This avoids redundant LLM calls on page refresh while staying fresh when the underlying data changes.

### Prompt template

The prompt is the algorithm above, almost verbatim. Key constraints in the prompt:

- Signal name MUST be 2–4 words
- Signal name MUST use the group's vocabulary (provide group name + subtitle)
- Elaboration MUST be exactly one sentence
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

Where and how to expose the pattern type in the UI is an open question. Options include: a small coloured badge on the card, a filter control, a summary line ("3 gaps, 2 tensions, 2 strengths"), or a grouping mechanism. The mockup uses a badge next to the signal name. We'll iterate after seeing it on real data.

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

## Backlog

- **Prompt template file** — write the actual prompt as a Markdown file in `bristlenose/llm/prompts/signal-elaboration.md`, following the existing prompt convention
- **API endpoint** — `GET /api/projects/{id}/analysis/codebooks/elaborations` or extend the existing codebook endpoint with an `?elaborate=true` query parameter
- **Caching layer** — SQLite table for cached elaborations with content hash invalidation
- **Batch generation** — batch multiple cards into a single LLM call to reduce latency (structured output, one JSON object per card)
- **Pattern filtering** — UI control to filter signal cards by pattern type
- **Sentiment card elaboration** — evaluate whether sentiment cards benefit from elaboration (hypothesis: they don't, but test with real data)
- **Editable elaborations** — let the researcher edit the generated signal name and elaboration (same inline-edit pattern as quote text)
- **Export integration** — include signal names and elaborations in the exported report
- **Multi-codebook** — when multiple codebooks are active, generate elaborations using the relevant codebook's definitions (already partitioned by the existing API)

---

## References

- **Mockup**: `docs/mockups/signal-elaboration.html` — full visual with algorithm traces on real IKEA data
- **Codebook definitions**: `bristlenose/server/codebook/norman.yaml`, `garrett.yaml`, `plato.yaml`, `uxr.yaml`
- **Signal detection**: `bristlenose/analysis/signals.py`, `bristlenose/analysis/generic_signals.py`
- **Analysis API**: `bristlenose/server/routes/analysis.py`
- **Analysis future**: `docs/design-analysis-future.md`
- **Research methodology**: `docs/design-research-methodology.md`
