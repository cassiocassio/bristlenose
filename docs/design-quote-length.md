# Quote atomicity: extracting codeable units, not monologues

## Problem

When Bristlenose processes oral history or long-form interviews, extracted quotes contain multiple ideas mashed together — sometimes 200+ words covering 3-5 distinct themes. The quote extraction LLM prompt says "1-5 sentences" but this guidance is routinely ignored for content where speakers talk for minutes without interruption.

**The issue is atomicity, not length.** A 100-word quote that expresses one idea is correct — the researcher will trim it down to a punchy 15-word highlight with ellipses for stakeholder communication. That trim-and-edit workflow is exactly what Bristlenose's inline quote editing UI is built for. But a 200-word quote containing three separate ideas is wrong: it can't be tagged with one code, it lands in the wrong cluster, and the researcher has to mentally decompose it before they can work with it.

The root cause is structural, not a simple prompt fix:

1. **No moderator breaks.** UXR sessions have a moderator who asks questions every 30-60 seconds, creating natural quote boundaries. Oral history interviewers ask a question, then the subject talks for 3-5 minutes straight. The LLM sees one continuous block and returns it as one quote.

2. **Speaker role detection failure.** When the interviewer isn't identified as RESEARCHER, their speech isn't filtered out. The LLM extracts interviewer questions as quotes too, and sometimes concatenates question + answer into a single quote.

3. **No upper bound enforcement.** The pipeline has a 5-word minimum but no maximum. The prompt says "1-5 sentences" but this is advisory — there's no code that enforces it.

Discovered during the FOSSDA demo dataset stress test (Apr 2026): 10 oral history interviews, ~8.5 hours of video, 361 quotes extracted. Many quotes exceeded 150 words; some exceeded 300.

---

## Current quote length controls

| Layer | Where | Lower bound | Upper bound |
|-------|-------|-------------|-------------|
| LLM prompt | `llm/prompts/quote-extraction.md` rule 7 | — | "1-5 sentences" (advisory) |
| Post-extraction filter | `stages/s09_quote_extraction.py:231` | 5 words (hard drop) | **none** |
| Data model | `models.py:271` (ExtractedQuote.text) | — | **none** |
| LLM schema | `llm/structured.py:84` | — | **none** |
| Dashboard featured | `stages/s12_render/dashboard.py:266` | 12 words preferred | 33 words preferred; >33 penalised |

The dashboard's 12-33 word sweet spot is only for selecting featured quotes — long quotes still appear in the full report.

---

## Why this matters

- **Readability.** A 200-word quote is a paragraph, not a quote. Researchers scan quotes to find patterns; walls of text defeat that purpose.
- **Clustering quality.** The clustering and theming stages work on quote text. Long quotes that cover 3-4 topics get assigned to one cluster, hiding the others.
- **Report aesthetics.** The quote card UI is designed for 1-3 sentence quotes. Long quotes break the visual rhythm and make the report feel unedited.
- **Token cost.** Downstream stages (clustering, theming) process all quote text. Bloated quotes inflate input tokens and cost.
- **max_tokens truncation.** The FOSSDA run hit the 32K output token ceiling because quote extraction was returning enormous verbatim blocks. This is a symptom of the length problem, not a separate issue.

---

## What "right" looks like

### The semantic unit, not the paragraph

The real question isn't "how long should a quote be?" — it's "what is the unit of analysis?"

In academic QDA, researchers distinguish between:

- **A quote** — a verbatim extract from a transcript. Can be any length. It's a slice of data.
- **A codeable unit** — a single idea, claim, or experience that a researcher would tag with one code. This is the unit of analysis.

These aren't the same thing. A researcher might highlight a 3-paragraph passage as evidence of "community governance friction" — the quote is long, but the **semantic unit is singular**. Conversely, a single sentence might contain two codeable units ("I love the docs but the onboarding is terrible" = delight + frustration).

Bristlenose's quote extraction prompt currently conflates these. It asks the LLM to extract "quotes" but what it actually needs are **codeable units** — passages where each one maps to a single tag, sentiment, or finding. The word count is a symptom, not the disease.

**The right heuristic:** a quote should contain exactly one idea that a researcher would code. Sometimes that's 15 words, sometimes 80. A 200-word quote is almost never one idea — but a hard word limit is the wrong tool. The LLM needs to detect **thought boundaries**, not count words.

### Quotes can span multiple paragraphs

A codeable unit doesn't have to be a single paragraph. Consider:

> "When I first showed up to the mailing list, nobody responded to my patches for three weeks. I thought maybe I was doing something wrong.
>
> Then one day someone replied and said 'oh we just don't check that list very often.' That was the moment I realised this wasn't a meritocracy — it was a club."

That's two paragraphs, but it's one semantic unit: "exclusionary community dynamics." Splitting it at the paragraph break would lose the narrative arc — the setup matters because it makes the punchline land.

The chunking logic (Option D below) needs to respect this: chunk boundaries should fall between codeable units, not between paragraphs within a unit.

### Target characteristics (not word counts)

Rather than a word count target, define what a well-extracted quote looks like:

- **One codeable idea.** A researcher could tag it with a single code without feeling they're losing nuance.
- **Can stand alone.** Makes sense without reading the surrounding transcript.
- **Has a point.** Expresses an opinion, describes an experience, reveals a feeling, or states a fact that matters for analysis. Purely procedural speech ("so the next thing I did was...") is filler, not a quote.
- **Preserves the arc.** If the idea has a setup-punchline structure, keep both. Don't split mid-thought to hit a word count.

In practice this means most quotes will be 15-60 words, some will be 80-100 for narrative beats, and anything over 120 words should be scrutinised — it probably contains multiple ideas.

### The researcher's workflow: extract wide, trim narrow

Bristlenose's quote editing UI exists precisely because the researcher's job is to turn evidence into communication:

1. **Pipeline extracts** a codeable unit — the full passage, as long as it needs to be for the idea to be complete. This is the analysis layer.
2. **Researcher browses** quotes in the report, tags them, clusters them. The full context helps them understand the theme.
3. **Researcher trims** — inline editing, ellipses, cutting the setup to leave the punchline. "I thought maybe I was doing something wrong ... it wasn't a meritocracy — it was a club." This is the communication layer.
4. **Export** sends the trimmed version to slides, CSV, stakeholder deliverables.

The pipeline should optimise for step 1: give the researcher a complete codeable unit. The researcher handles steps 2-4. A long quote that's one idea is a feature — the researcher has material to work with. A long quote that's three ideas is a bug — the researcher has to do the pipeline's job.

---

## Design options

### Option A: Stronger prompt guidance (low effort, partial fix)

Add explicit word count targets and splitting instructions to `quote-extraction.md`:

```
Quote length: aim for 10-60 words (1-3 sentences). If a speaker makes
a point that runs longer than ~60 words, split it into separate quotes
at natural thought boundaries. Each quote should express ONE idea that
a researcher could tag with a single code.
```

**Pros:** Simple, no code change. Works well when the LLM follows instructions.
**Cons:** LLMs don't reliably count words. Long monologues with no clear internal boundaries are hard to split via prompt alone. Already tried ("1-5 sentences") and it's not working.

### Option B: Post-extraction splitting (medium effort, reliable)

After the LLM returns quotes, add a second pass that identifies and splits overlong quotes:

1. Flag any quote over a word threshold (e.g. 80 words)
2. Send it back to the LLM with a focused splitting prompt: "This quote contains multiple ideas. Split it into 2-4 shorter quotes, each expressing a single thought. Preserve the timecodes."
3. Replace the original with the splits

**Pros:** Catches what the prompt misses. Works regardless of interview format. The splitting prompt is simpler and more reliable than the full extraction prompt.
**Cons:** Extra LLM call per overlong quote — adds cost and latency. Could produce awkward splits if the monologue is genuinely one sustained argument.

### Option C: Hard ceiling with soft warning (low effort, blunt)

Add a `max_quote_words` config (default 80) to the post-extraction filter in `s09_quote_extraction.py`, parallel to the existing `min_quote_words`. Quotes exceeding it are either:
- (C1) Dropped entirely with a warning
- (C2) Truncated to the last sentence boundary within the limit
- (C3) Kept but flagged for the researcher to review

**Pros:** Simple, deterministic, no extra LLM cost.
**Cons:** C1 loses data. C2 loses the ending (often the most important part — conclusions, judgements). C3 doesn't actually fix the problem, just surfaces it.

### Option D: Chunked extraction with overlap (high effort, structural fix)

Instead of sending the full transcript to quote extraction in one call, chunk it by topic boundaries (from stage 8). Each chunk goes to the LLM separately with a smaller context window:

1. Group segments by topic boundary (stage 8 already identifies 10-15 per session)
2. Send each chunk (2-5 minutes of transcript) to quote extraction independently
3. Merge results, dedup quotes that span chunk boundaries

**Pros:** Fundamentally solves the "endless monologue" problem — each chunk is short enough that the LLM can identify natural boundaries. Also fixes the max_tokens truncation issue (smaller outputs per call). Naturally parallelisable.
**Cons:** Most complex to implement. Chunk boundaries may split a quote-worthy moment. Dedup logic needed. Changes the extraction architecture.

### Option E: Pre-segmentation prompt (medium effort, elegant)

Before quote extraction, add an intermediate LLM step that segments long speaker turns into "thought units" — marking where one idea ends and another begins within a monologue. Then quote extraction operates on these pre-segmented turns.

This is how human researchers work: they read a transcript, mentally segment it into codeable units, then tag each unit.

**Pros:** Mirrors the actual research process. Separates "where are the boundaries?" from "what is this quote about?" — two different cognitive tasks that the LLM can do better in sequence.
**Cons:** Extra LLM pass over the full transcript. New intermediate data structure needed. Adds pipeline complexity.

---

## Recommendation

**A + B in sequence.** Strengthen the prompt guidance (A) as a first pass — this will help for content where boundaries exist but the LLM is being lazy. Then add post-extraction splitting (B) as a safety net for quotes that still exceed the threshold.

This covers the most ground for moderate effort:
- Prompt improvement catches 70% of cases
- Post-extraction splitting catches the remaining 30%
- No architectural change to the pipeline
- Cost of the splitting pass is small (only runs on overlong quotes)

Option D (chunked extraction) is the right long-term architecture but is a larger refactor that should be done alongside the max_tokens truncation fix — they share the same solution (smaller inputs/outputs per call).

---

## Interaction with other issues

- **Speaker role detection** (see FOSSDA findings, Apr 2026): When the interviewer is correctly identified, their speech is excluded from extraction. This alone roughly halves the volume of extracted text and removes the worst "question + answer concatenated" quotes. Fix speaker ID first, then reassess whether quote length is still a problem.
- **max_tokens truncation**: Long quotes are the primary driver of hitting the 32K token ceiling. Shorter quotes = smaller LLM responses = no truncation. Option D also directly solves truncation.
- **Quote exclusivity**: Splitting a quote into 2-3 shorter quotes means each piece needs its own cluster/theme assignment. The existing exclusivity logic ("every quote in exactly one section") handles this naturally — splitting creates more quotes, not duplicates.

---

## Metrics to track

Once a fix ships, measure on the FOSSDA corpus:

- **Atomicity (primary):** manually review 50 random quotes — what percentage contain more than one codeable idea? (Target: < 10%)
- **Word count distribution (secondary):** P50 / P90 / P99 quote word count. Not a target in itself, but a proxy — if P99 drops from 250 to 120, atomicity is probably improving
- **Total quote count per session:** expect increase — splitting multi-idea quotes creates more, atomic quotes
- **LLM output tokens for quote extraction:** expect decrease per quote, possible increase in total (more quotes but each is shorter)
- **Clustering quality:** do themes become more granular with atomic quotes? Does each theme feel like one idea rather than a grab-bag?
- **Researcher effort:** how much trimming does the researcher need to do before a quote is slide-ready? Atomic quotes should need less decomposition, more trimming — which is easier
