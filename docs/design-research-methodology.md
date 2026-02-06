# Research Methodology

How Bristlenose processes interview data into a structured research report. This document is the single source of truth for analytical decisions — why certain categories exist, what thresholds mean, and what research traditions inform the approach.

Future goal: a user-facing "How it works" page in the report itself, drawn from this document.

---

## Pipeline overview

A user-research study typically involves 3–15 interview sessions. Each session is a moderated interview (researcher + participant) or a solo think-aloud recording (participant narrating their own experience). Bristlenose's pipeline transforms these recordings into a browsable report with quotes organised by screen/task and by theme.

The analytical stages:

| Stage | What it does | Key decision |
|-------|-------------|--------------|
| 5b | Speaker identification | Who is the researcher, participant, observer? |
| 8 | Topic segmentation | Where does the conversation shift topic? |
| 9 | Quote extraction | What's worth quoting? How to clean it up? |
| 10 | Screen clustering | Which quotes are about the same screen/task? |
| 11 | Thematic grouping | What patterns emerge from general-context quotes? |

---

## Speaker roles (Stage 5b)

Three roles, reflecting the structure of user-research sessions:

- **Researcher** — conducts the session. Asks questions, gives instructions, guides through tasks. Their speech is never quoted in the report (it's facilitation, not data).
- **Participant** — the research subject. Their speech is the primary data source for quotes.
- **Observer** — silent or near-silent attendee (note-taker, stakeholder). Excluded from quotes.

**Why these three?** User-research sessions have a clear power dynamic: one person asks, another answers. The observer role exists because enterprise research sessions often include silent stakeholders on the call. Misidentifying who is who would contaminate the report with researcher questions presented as participant opinions.

**Two-pass identification:** A fast heuristic pass scores speakers by question ratio and researcher-phrase frequency (see `_RESEARCHER_PHRASES` in `identify_speakers.py`), then the LLM refines using the first ~5 minutes of transcript. The heuristic catches obvious cases; the LLM handles ambiguous ones (e.g., a chatty participant who asks a lot of questions back).

**Name and title extraction:** The LLM pass also extracts `person_name` and `job_title` when speakers mention them in conversation. These populate `people.yaml` for the researcher to review and edit.

---

## Topic segmentation (Stage 8)

Before extracting quotes, the transcript is segmented into topical sections. This gives the quote extractor context — it knows which screen or topic each section of dialogue is about.

Four transition types:

- **`screen_change`** — participant navigates to or is shown a new screen/page. The most important boundary for usability research.
- **`task_change`** — researcher assigns a new task (even if it's on the same screen).
- **`topic_shift`** — discussion moves to a new subject within the same screen (e.g., from layout to colour).
- **`general_context`** — conversation moves away from screens entirely: job role, daily workflow, life context. These sections feed the thematic grouping stage, not screen clustering.

**Why these four?** They reflect how moderated research sessions actually flow. The researcher guides the participant through screens and tasks (product-specific data), interspersed with contextual questions about their work and habits (general data). The `general_context` type is the mechanism that separates the two pools for later stages.

**Confidence scores:** Each boundary includes a confidence score (0.0–1.0). Currently used only for debugging; future work may use low-confidence boundaries to merge over-segmented topics.

---

## Quote extraction (Stage 9)

### What gets quoted

Every substantive participant utterance — anything revealing experience, opinion, behaviour, confusion, delight, or frustration. The bar is deliberately low: we over-extract and let the clustering/theming stages organise.

**Think-aloud narration is data.** When a participant reads menu items aloud, describes clicks, or narrates their path ("Home textiles and rugs. Bedding. Duvets."), this shows the user journey through the interface. Short navigational sequences are bundled into a single quote capturing the path taken. Only truly empty utterances ("Okay", "Right" with no navigational or emotional content) are skipped.

**Minimum quote length:** 5 words (hardcoded in `quote_extraction.py`). Below this threshold, utterances rarely carry enough meaning to stand alone as a quote. Very short meaningful reactions ("I hate this") are 3 words but typically occur mid-sentence and get captured as part of a longer thought.

### Editorial cleanup — "dignity without distortion"

Participants deserve to look articulate without having their words changed. The rules:

1. Remove filler words (um, uh, er, hmm) → replace with `...`
2. Remove filler uses of "like", "you know", "sort of" → replace with `...`
3. Keep "like" when it's a comparison ("it looked like a dashboard")
4. Light grammar fixes where the participant would look foolish — never change meaning, tone, or emotional register
5. Insert `[clarifying words]` where meaning would be lost ("the thing" → "the [settings page]")
6. Preserve self-corrections that reveal thought process ("no wait, I mean the other one")
7. Mark unclear speech as `[inaudible]`
8. Preserve meaningful non-verbal cues: `[laughs]`, `[sighs]`, `[pause]`

**Why "dignity without distortion"?** Research reports get shared with stakeholders, clients, and sometimes publicly. Raw transcript speech is full of false starts and filler that make intelligent people sound confused. But heavy editing risks changing what they actually meant. This principle threads the needle: the participant sounds like themselves on a good day.

### Researcher context prefixes

In moderated sessions, a quote is sometimes unintelligible without knowing the researcher's question. Example:

> **researcher_context:** "When asked about the settings page"
> **quote:** "That's exactly what I expected to see there."

Any words not spoken by the participant must be in `[square brackets]`. In solo think-aloud recordings, context prefixes are rarely needed since the participant provides their own context.

---

## Sentiment taxonomy

Seven categories, designed for UX research specifically:

| Sentiment | What it captures | Example |
|-----------|-----------------|---------|
| **Frustration** | Difficulty, annoyance, friction | "This is so slow", "Why won't it work?" |
| **Confusion** | Not understanding, uncertainty | "I don't get what this means" |
| **Doubt** | Scepticism, worry, distrust | "I'm not sure I'd trust this" |
| **Surprise** | Expectation mismatch (neutral) | "Oh, that's not what I expected" |
| **Satisfaction** | Met expectations, task success | "Good, that worked" |
| **Delight** | Exceeded expectations, pleasure | "Oh I love this!" |
| **Confidence** | Trust, feeling in control | "I know exactly what to do here" |

**Intensity:** Each sentiment has a 1–3 intensity scale (mild, moderate, strong). A quiet "hm, that's odd" is surprise at 1; "WHAT? No way!" is surprise at 3.

**No sentiment:** Purely descriptive quotes with no emotional content (e.g., "I'm clicking on beds") get no sentiment tag. This is correct — navigational narration is valuable data but doesn't express feeling.

### Why these seven?

The previous taxonomy had 14 tags and was over-specified — researchers couldn't reliably distinguish between similar categories, and the LLM produced inconsistent results. The redesign (Feb 2026) followed these principles:

1. **UX-specific, not universal emotion.** Generic emotion taxonomies (Ekman's 6 basic emotions, Plutchik's 8 primaries, GoEmotions' 27 categories) are built for general affect. UX research cares about specific things: can the user complete their task? Do they trust the interface? Where do they get stuck? The seven categories map to actionable UX insights.

2. **Negative sentiments are more granular than positive ones.** This is deliberate: frustration, confusion, and doubt each point to different design problems (performance, information architecture, and credibility respectively). The positive side is simpler because "it works" and "it delights" cover the main success signals.

3. **Surprise is neutral.** Unlike most emotion models that code surprise as positive, here it flags expectation mismatches for the researcher to investigate. "That's not what I expected" could be good (a pleasant shortcut) or bad (a confusing redirect) — only the researcher can tell from context.

4. **Doubt is separate from confusion.** Confusion means "I don't understand this." Doubt means "I understand it but don't trust it." These require different design responses: better labelling vs. better credibility signals.

### Theoretical foundations

The taxonomy draws on but does not replicate these traditions:

- **Russell (2003)** — core affect (valence × arousal) as the substrate of emotion. Our 7 categories span the valence dimension (frustration→delight) with arousal captured by intensity (1–3).
- **Scherer (2005)** — appraisal theory: emotions arise from evaluating events against goals. In UX, the "goal" is task completion; each sentiment maps to a different appraisal outcome (goal blocked → frustration, goal uncertain → confusion, goal achieved → satisfaction).
- **Hassenzahl (2003)** — pragmatic vs hedonic UX. Frustration/confusion/doubt map to pragmatic failures; delight maps to hedonic quality.
- **Fogg (2003)** — web credibility. The doubt category directly captures credibility/trust concerns that Fogg's research shows matter to users.

Full citations in `docs/academic-sources.html`.

---

## Quote classification: the two pools

Stage 9 classifies every quote as one of two types:

- **`SCREEN_SPECIFIC`** — about a specific screen, page, or task in the product being tested. Goes to Stage 10 (screen clustering).
- **`GENERAL_CONTEXT`** — about the participant's broader context: job role, daily workflow, software habits, life situation. Goes to Stage 11 (thematic grouping).

**Why two pools?** A usability study produces two kinds of insight. Screen-specific quotes answer "what happened when they used our product?" — these are organised by screen in the report's Section-by-Section Analysis. General-context quotes answer "who are these people and what's their world like?" — these are organised by theme. The two pools are mutually exclusive: a quote is one or the other, never both. This prevents the same quote appearing in both sections of the report.

The classification is made by the LLM during extraction based on the topic segmentation from Stage 8. Segments tagged `general_context` by the topic segmenter produce `GENERAL_CONTEXT` quotes; everything else produces `SCREEN_SPECIFIC` quotes.

---

## Screen clustering (Stage 10)

Takes all `SCREEN_SPECIFIC` quotes across all participants and groups them by screen/task.

**The problem it solves:** Different participants describe the same screen differently. One says "the main page", another says "the homepage", a third says "the landing screen." The LLM normalises these into a single cluster with a consistent label.

**Ordering:** Clusters are ordered in the logical flow of the product — the order a user would encounter the screens. This makes the report's Section-by-Section Analysis read as a user journey.

**Exactly one cluster per quote.** A quote about the checkout page goes in the checkout cluster, not also in the payment cluster. Even if it touches on both, the LLM picks the strongest fit. The researcher can reassign via inline editing in the report.

**Fallback:** If the LLM call fails, quotes are grouped by their raw `topic_label` from Stage 8. Less polished but functional.

---

## Thematic grouping (Stage 11)

Takes all `GENERAL_CONTEXT` quotes and identifies emergent themes.

**Emergent, not prescribed.** The LLM identifies patterns across participants — shared challenges, common workflows, recurring concerns. Theme labels are generated from the data, not from a fixed taxonomy. This follows Braun & Clarke's (2006) inductive thematic analysis: themes emerge from the data rather than being imposed on it.

**Exactly one theme per quote.** Even when a quote could fit multiple themes, the LLM picks the strongest fit. This matches researcher expectations: each quote appears once in the report. When further processing the output (Miro boards, affinity diagrams, spreadsheets), duplicates would cause confusion. The researcher can reassign quotes using inline editing.

**Minimum evidence threshold:** A theme must have at least 2 quotes. Themes with fewer are folded into an "Uncategorised observations" bucket. A single quote doesn't constitute a pattern — it's an individual observation. The threshold of 2 is the minimum for "more than one person said this", which is the basic requirement for calling something a theme rather than an anecdote. A higher threshold (3+) would hide emergent patterns in small studies (3–5 participants).

**Fallback:** If the LLM call fails, quotes are grouped by their raw `topic_label`. Functional but loses the cross-participant synthesis.

---

## Quote exclusivity — the design rule

**Every quote appears in exactly one section of the final report.**

This is enforced at three levels:

1. **Quote type separation** — `SCREEN_SPECIFIC` and `GENERAL_CONTEXT` are mutually exclusive pools. A quote cannot appear in both a screen cluster and a theme group.
2. **Within screen clusters** — the prompt requires "exactly one screen cluster" per quote.
3. **Within theme groups** — the prompt requires "exactly one theme" per quote (pick strongest fit).

A safety-net dedup in `thematic_grouping.py` catches any LLM violations when weak themes are consolidated.

**Why exclusivity?** Researchers expect to process each quote once. When they export to CSV, paste into Miro, or hand the report to a non-researcher stakeholder, duplicated quotes cause confusion — "didn't I already see this?" — and inflate apparent evidence for a theme. The researcher is the one who should decide if a quote belongs elsewhere; the tool's job is to make a single best-guess assignment.

---

## What the tool does not do

These are explicit non-goals, reflecting the philosophy that the tool assists but does not replace the researcher:

- **No cross-quote synthesis.** The tool extracts and organises individual quotes. It does not write summary paragraphs or draw conclusions. The researcher synthesises.
- **No severity ranking.** Themes and screen clusters are not ranked by importance. The researcher decides what matters based on their research questions.
- **No recommendation generation.** The tool shows what participants said, not what to do about it.
- **No statistical claims.** Quote counts and coverage percentages are descriptive, not inferential. "4 of 6 participants mentioned X" is observation, not statistical significance.

---

## File map

| What | Where |
|------|-------|
| LLM prompt templates | `bristlenose/llm/prompts.py` |
| Prompt archive | `bristlenose/llm/prompts-archive/` |
| Structured output schemas | `bristlenose/llm/structured.py` |
| Sentiment enum | `bristlenose/models.py` (`Sentiment`) |
| Quote type enum | `bristlenose/models.py` (`QuoteType`) |
| Transition type enum | `bristlenose/models.py` (`TransitionType`) |
| Speaker identification | `bristlenose/stages/identify_speakers.py` |
| Topic segmentation | `bristlenose/stages/topic_segmentation.py` |
| Quote extraction | `bristlenose/stages/quote_extraction.py` |
| Screen clustering | `bristlenose/stages/quote_clustering.py` |
| Thematic grouping | `bristlenose/stages/thematic_grouping.py` |
| Academic citations | `docs/academic-sources.html` |
| Quote exclusivity detail | `bristlenose/stages/CLAUDE.md` |
