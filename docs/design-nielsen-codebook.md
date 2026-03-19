# Nielsen's 10 Usability Heuristics — Codebook Design

_Mar 2026. Evaluates whether Nielsen's heuristics transfer from expert evaluation to participant quote-coding, and proposes a codebook structure for Bristlenose._

---

## The adaptation problem

Jakob Nielsen published the 10 usability heuristics in 1994 as a framework for **expert evaluation** — a trained evaluator inspects an interface and catalogues violations. The evaluator brings knowledge that participants don't have: platform conventions, cross-screen comparisons, design pattern vocabularies.

Bristlenose codebooks tag **participant quotes**. The unit of analysis is something a person said in a research session, not an evaluator's inspection note. This is a fundamentally different use case.

The question isn't "are these heuristics valid?" — they're among the most cited in HCI history. The question is: **which heuristics produce reliable signal when the evidence is limited to what participants and moderators say?**

Some heuristics map cleanly. Participants narrate confusion, frustration, and surprise in ways that directly evidence heuristic violations. Others are properties of the system that require evaluator-level comparative knowledge — the participant feels the friction but can't name the cause, and the LLM can't infer the cause from the quote alone.

Being honest about this distinction is a differentiator. No other tool has attempted to map Nielsen to quote-coding with this level of rigour.

### The moderator speech question

In moderated sessions, the moderator's questions often surface evidence that participants wouldn't volunteer. "Why did you look there?" → "Because on the other page it was there" reveals a consistency expectation. "If you did this every day, how would you want it to work?" reveals an efficiency concern.

Bristlenose already captures moderator context. The quote extraction prompt (`bristlenose/llm/prompts/quote-extraction.md:31`) attaches a `researcher_context` prefix when a quote is unintelligible without the moderator's framing:

> In moderated sessions, if a quote is unintelligible without knowing the researcher's question, add a brief context prefix. Example: `researcher_context = "When asked about the settings page"`

But AutoCode's discrimination prompts don't currently instruct the LLM to use this context. For some Nielsen heuristics — especially Consistency (#4) and Error Prevention (#5) — the moderator's question is where the analytical signal lives.

**Proposal:** Add a generic moderator-context instruction to the AutoCode engine prompt (not Nielsen-specific). This benefits all codebooks. See [Moderator context enhancement](#moderator-context-enhancement) below.

---

## Heuristic-by-heuristic assessment

### Tier 1 — Strong verbal signal

These heuristics produce clear, quotable evidence from participant speech. Participants naturally narrate the experience that the heuristic describes.

#### H1: Visibility of system status

**Transferability: excellent.** Participants constantly narrate uncertainty about system state. Think-aloud protocols make this especially rich — the participant's real-time commentary about what the system is (or isn't) telling them is direct evidence.

Example participant utterances:
- "Is it loading?"
- "Did it save?"
- "I can't tell if that worked"
- "Nothing's happening... oh wait, there it is"
- "How long is this going to take?"

**Overlap with existing frameworks:**
- Norman → Feedback group (system response, delayed feedback, ambiguous feedback). **High overlap.** Norman's Feedback group covers the same terrain from a design-principle angle. Nielsen's framing is broader (system status includes progress indicators, state changes, mode indicators — not just action-response feedback). But the quotes that evidence both are often the same.
- Morville → Usable (ease of use). Low overlap — Morville's "ease of use" is much broader.

**Differentiation from Norman:** Norman asks "did the system communicate the result of this action?" (cause → effect). Nielsen asks "does the user know what's happening right now?" (system state). These overlap on action feedback but diverge on ambient status (loading indicators, sync state, mode indicators). Worth keeping as a separate lens.

#### H2: Match between system and the real world

**Transferability: excellent.** Language confusion is inherently verbal. When participants encounter unfamiliar terminology, they say so.

Example participant utterances:
- "What does that mean?"
- "I don't know what a 'widget' is"
- "I'd call it X not Y"
- "That icon doesn't look like [real-world thing]"
- "The order doesn't make sense to me — I'd expect A before B"

**Overlap with existing frameworks:**
- Morville → Findable (labelling). **Moderate overlap.** Morville's "labelling" covers vocabulary mismatch specifically for findability. Nielsen's scope is broader — it includes metaphor choices, icon conventions, and information ordering that follow real-world expectations, not just label text.
- Norman → Conceptual model (model mismatch). Moderate overlap — when the system's language doesn't match the user's mental model.

**Differentiation:** Nielsen specifically targets the *translation gap* between system language and user language. This is a tighter, more actionable lens than Morville's labelling (which focuses on findability impact) or Norman's conceptual model (which focuses on understanding/prediction).

#### H3: User control and freedom

**Transferability: excellent.** Getting stuck, wanting to undo, and feeling trapped are among the most emotionally charged moments in user sessions. Participants express these loudly.

Example participant utterances:
- "How do I go back?"
- "Can I undo?"
- "I didn't mean to click that"
- "I'm stuck — there's no way out of this"
- "What if I make a mistake? Can I fix it?"

**Overlap with existing frameworks:**
- Norman → Feedback (confirmation), Slips vs Mistakes (action slip). Partial overlap — Norman's confirmation tag covers "the system asked me to confirm before a destructive action," which is a *mechanism* for supporting user control. Norman's action slip covers the error itself, not the recovery path.
- Morville → Usable (error tolerance). **High overlap.** Morville's "error tolerance" asks exactly the same question from a quality-dimension angle: "can the participant recover from mistakes?"

**Differentiation:** Nielsen frames this as a *right* — users should always have an emergency exit. The emphasis is on escape hatches and undo, not on error tolerance broadly. This framing produces tighter, more specific tags (undo availability, exit clarity, destructive-action safety) vs Morville's broader quality assessment.

#### H6: Recognition rather than recall

**Transferability: excellent.** Memory-load complaints surface naturally, especially in complex workflows.

Example participant utterances:
- "I can't remember where that was"
- "Why do I have to type this again? It already knows my name"
- "I know I saw it somewhere..."
- "Wait, what was I supposed to do next?"
- "Oh right, I forgot you have to do that first"

**Overlap with existing frameworks:**
- Norman → Conceptual model (user mental model), Slips vs Mistakes (memory lapse). **Moderate overlap.** Norman's memory lapse specifically covers forgetting steps. Nielsen's scope is broader — it includes whether the interface *reduces the need to remember* (making options visible, showing recent items, pre-filling forms).
- Morville → Usable (ease of use). Low overlap — too broad.

**Differentiation:** Nielsen's framing is specifically about the interface *minimising memory load* — a design responsibility, not just a user experience. Tags can target: visible options, pre-filled defaults, persistent context, breadcrumbs. This is more specific than Norman's error-focused memory lapse.

#### H9: Help users recognise, diagnose, and recover from errors

**Transferability: excellent.** Error encounters produce strong verbal reactions. The quality of error messages is one of the most commonly discussed topics in usability sessions.

Example participant utterances:
- "What does this error mean?"
- "It just says 'something went wrong' — that's not helpful"
- "OK, so it tells me what happened, but not what to do about it"
- "I appreciate that it told me exactly what to fix"
- "Error 403 — what am I supposed to do with that?"

**Overlap with existing frameworks:**
- Norman → Feedback (ambiguous feedback). **Moderate overlap.** Norman's ambiguous feedback covers unclear system responses broadly. Nielsen's H9 is specifically about *error* messages — their clarity, diagnosis value, and recovery guidance.
- Morville → Usable (error tolerance). Moderate overlap.

**Differentiation:** Nielsen is specifically about the *quality* of error communication. This is narrower and more actionable than Norman (which asks whether the feedback was clear in general) or Morville (which asks whether recovery is possible). Tags can target: error message clarity, diagnostic specificity, recovery guidance, blame language.

---

### Tier 2 — Partial verbal signal

These heuristics can be identified from session speech, but require careful discrimination prompts. The signal is genuine but either sparse, indirect, or easy to confuse with adjacent concepts.

#### H5: Error prevention

**Transferability: partial.** The core problem: prevention is about what *didn't* happen. You can't quote an error that was successfully prevented. But **anticipatory anxiety and near-misses** are quotable.

Example participant utterances:
- "I'm scared I'll delete something"
- "I almost clicked the wrong button"
- "I'm going to double-check before I press this"
- "What happens if I accidentally...?"
- "Thank God there was a confirmation dialog"

**What doesn't surface verbally:** Whether the interface effectively prevents slips through good defaults, constraints, or input validation. These are design properties the evaluator notices; participants experience the *absence* of errors without attributing it to prevention design.

**Prompt strategy:** Frame `apply_when` around hesitation, anxiety, and near-misses — not around the abstract concept of prevention. The `not_this` should distinguish from Norman's confirmation tag (which is about a specific mechanism) and from general anxiety (which might be about trust, not error prevention).

**Overlap:** Norman → Feedback (confirmation), Constraints (physical constraint). Nielsen's framing is broader — it asks whether the *whole design* minimises error risk, not just whether specific mechanisms exist.

**Which heuristics benefit most from moderator context:** H5 is a prime candidate. "What were you worried about?" and "Why did you hesitate?" are moderator probes that surface prevention concerns participants wouldn't volunteer.

#### H8: Aesthetic and minimalist design

**Transferability: partial.** Participants react to the *symptom* (overwhelm, clutter, visual appeal) but not the *cause* (every extra unit of information competes with relevant information and diminishes their relative visibility). The symptom quotes are still useful — they're just surface-level.

Example participant utterances:
- "There's too much going on here"
- "This is overwhelming"
- "It looks clean and simple"
- "I don't know where to look first"
- "Why is all this stuff here? I just want [specific thing]"

**What doesn't surface verbally:** The evaluator judgement that specific elements are irrelevant and should be removed. Participants describe the feeling; the evaluator identifies the cause.

**Prompt strategy:** Frame `apply_when` around information density reactions — being overwhelmed, finding clarity, or noting clutter. The `not_this` must sharply distinguish from Morville → Desirable (aesthetic quality), which covers the *visual craft* dimension. Nielsen's H8 is not about beauty — it's about information discipline.

**Overlap:**
- Morville → Desirable (aesthetic quality). **High risk of confusion.** Morville's aesthetic quality is about visual craft ("it looks great", "the design is polished"). Nielsen's H8 is about information density ("there's too much going on", "this is overwhelming"). These sound similar but are analytically different. Strong `not_this` prompts are essential.
- Morville → Accessible (cognitive accessibility). **Moderate overlap.** Cognitive accessibility covers being overwhelmed by complexity, which overlaps with Nielsen's minimalism principle.

**Differentiation:** Nielsen's unique contribution is the *information economy* framing — every element competes for attention, so irrelevant elements actively harm relevant ones. This is a design argument, not a quality dimension (Morville) or a cognitive load issue (accessibility). Worth keeping for the specific analytical lens it provides.

#### H10: Help and documentation

**Transferability: partial but sparse.** Only surfaces when participants actively seek help, which many sessions never trigger. When it appears, it's clear and quotable.

Example participant utterances:
- "Is there a help section?"
- "I had to Google how to do this"
- "I wish it explained what this button does"
- "The FAQ didn't answer my question"
- "The tooltip was really helpful"

**Overlap:**
- UXR codebook → Learning (guidance). Moderate overlap.
- Morville → Findable (search effectiveness). Low overlap — finding help is a specific case.

**Prompt strategy:** `apply_when` should cover both explicit help-seeking and implicit signals ("I had to figure it out myself"). `not_this` should distinguish from general confusion (which is ease of use) and from missing labels (which is H2 Match).

---

### Tier 3 — Contested heuristics

These two heuristics pose a fundamental transferability question. The analysis below presents for, against, and a middle path for each.

#### H4: Consistency and standards

**The case for dropping it:**

Nielsen's consistency heuristic has two parts: *internal consistency* (does the product contradict itself across screens?) and *external consistency* (does it follow platform conventions?). Both require **comparative knowledge** that participants rarely have consciously:

- **Internal consistency** requires remembering across screens. Participants feel the friction but attribute it to other things — "I couldn't find the save button" sounds like findability, not consistency. The evaluator is the one who notices that the save button moved between pages.
- **External consistency** requires knowing platform conventions. Power users sometimes articulate this ("On every other app, swiping left deletes"), but most participants just feel confused without knowing why.

**The false-positive risk is high.** "I expected it to be there" could be:
- Consistency violation (it's in a different place than on other screens) ← this heuristic
- Poor information architecture (logically in the wrong category) ← Garrett Structure
- Findability failure (it's there but not visible) ← Morville Findable
- Learned behaviour from a competitor (not a consistency issue) ← Norman Conceptual model

AutoCode can't distinguish between these without seeing the actual interface — which it never does.

**The case for keeping it:**

When moderator probing is good, consistency *does* surface verbally:
- "Why did you look there?" → "Because on the other page it was there"
- "How does this compare to [competitor]?" → "Well, [competitor] puts it in the menu"
- "Was anything confusing?" → "The icons mean different things on different screens"

These quotes are analytically valuable when they appear. The problem isn't that consistency never surfaces — it's that it surfaces **only with skilled moderation** and is **easily confused with adjacent concepts** without tight discrimination.

**Overlap with existing frameworks:**
- Norman → Conceptual model (learned behaviour). **High overlap.** Norman's "learned behaviour" tag covers exactly the case where participants reference other products: "in [other app] you can," "I'm used to," "every other app does it this way." This is the strongest overlap of any heuristic pair in this analysis.
- Norman → Conceptual model (model mismatch). The "I expected X" case is already covered.

**Middle path:** Include it with a **narrow scope**. Don't try to tag all consistency issues — only the ones where the participant *explicitly references another screen, app, or convention*. The `apply_when` would require explicit comparison language: "on the other page," "in [app name] you can," "I thought it would work the same as." This filters out ambiguous expectation-mismatch quotes and keeps only the explicitly comparative ones. The `not_this` would specifically list Norman's learned behaviour and model mismatch as alternatives for quotes that don't contain explicit comparison.

**Risk if narrowed:** The tag will fire infrequently — maybe 2–5% of quotes in a typical study. This is fine; sparse-but-precise is better than frequent-but-noisy. But researchers expecting comprehensive consistency coverage will be disappointed. The preamble should set this expectation.

---

#### H7: Flexibility and efficiency of use

**The case for dropping it:**

This heuristic is about **design capacity** — does the interface support both novice and expert workflows? Accelerators for power users? Customisation? That's a property of the system, not something a single participant experiences:

- **Accelerators** (keyboard shortcuts, batch operations) — power users mention these ("I wish I could just Ctrl+D"), but novice participants never notice their absence. You'd need cross-participant analysis to validate the heuristic.
- **Customisation** (can users tailor the interface?) — only surfaces if participants are asked directly. Spontaneous "I wish I could rearrange this" is rare.
- **Efficiency over time** (does the product reward repeated use?) — this is a longitudinal observation, not a single-session quote. "This would get tedious" is projective, not experiential.

The heuristic's unit of analysis is the *system's flexibility*. The codebook's unit of analysis is the *participant's utterance*. These don't align.

**The case for keeping it:**

Efficiency frustration is real and quotable — it's just not about the *spectrum* that Nielsen describes:
- "This is so many clicks"
- "I do this fifty times a day, I need it faster"
- "Is there a keyboard shortcut for this?"
- "I already told it my name, why is it asking again?" (also Recognition #6)

These are legitimate UX findings. The question is whether tagging them as "Flexibility & Efficiency" adds analytical value over existing tags.

**Overlap with existing frameworks — severe:**
- Morville → Usable (efficiency). **Near-total overlap.** Morville's "efficiency" tag covers "too many clicks," "this should be faster," "why so many steps" — exactly the quotes that would evidence H7. The tag descriptions are almost interchangeable.
- Norman → Mapping (arbitrary mapping). Partial overlap — when controls require unnecessary steps.
- UXR → Behaviour (workaround). Moderate overlap — workarounds often emerge from efficiency problems.

**Middle path:** Reframe away from the dual-path design concept toward **efficiency pain in context**. Focus on what participants actually report: repetitive tasks, missing shortcuts, forced manual work. Drop the "flexibility" (system capacity) framing and keep the "efficiency" (user experience) framing. The preamble would note this adaptation explicitly.

**Risk if reframed:** This departs from Nielsen's original meaning and substantially overlaps with Morville's efficiency tag. A researcher applying both codebooks would see the same quotes tagged by both, with no analytical distinction. This undermines the purpose of stacking multiple lenses.

---

### Decision: include all 10

**All 10 heuristics are included.** The overlap concerns with existing frameworks are real but not a reason to exclude — researchers expect 10, it's a rhetorical flourish that gives the set its identity, and the only way to learn what falls out in the wash is to try with real data.

H4 (Consistency) uses a narrowed scope — explicit comparison language required. H7 (Flexibility/Efficiency) focuses on what participants actually report: shortcut desire, repetitive tasks, and customisation wants. These overlap with Morville and Norman, but overlapping lenses from different gurus is the nature of the field. Researchers choose the framework that matches their analytical question.

---

## Tag structure (as shipped)

10 groups, 3–4 tags each. 35 tags total. Full discrimination prompts in `bristlenose/server/codebook/nielsen.yaml`.

| # | Group | Subtitle | Tags | Colour |
|---|-------|----------|------|--------|
| H1 | Status visibility | Does the user know what's happening right now? | clear status, opaque status, progress indication, mode confusion | `ux` |
| H2 | Real-world matching | Does the system speak the user's language? | natural language, jargon barrier, metaphor fit, logical ordering | `ux` |
| H3 | Control and freedom | Can the user escape, undo, and recover? | emergency exit, trapped, undo available, destructive action | `task` |
| H4 | Consistency and standards | Does the system follow its own rules and platform conventions? | internal inconsistency, platform convention, terminology inconsistency | `trust` |
| H5 | Error prevention | Does the design prevent mistakes before they happen? | hesitation, near miss, guardrail, risky default | `task` |
| H6 | Recognition over recall | Does the interface minimise memory load? | visible options, memory burden, helpful default, context loss | `ux` |
| H7 | Flexibility and efficiency | Does the interface support both novice and expert workflows? | shortcut desire, repetitive task, customisation | `opp` |
| H8 | Aesthetics and minimalism | Does every element earn its place on screen? | information overload, focused design, competing elements | `emo` |
| H9 | Errors and recovery | When things go wrong, does the system explain clearly and help fix it? | clear error message, cryptic error, blame language, recovery guidance | `task` |
| H10 | Help and documentation | Can users find answers when they need them? | self-service help, help absent, contextual guidance | `opp` |

Notes:
- H4 (Consistency) requires explicit comparison language — the preamble instructs AutoCode to look for "on the other page," "in [app name]," etc.
- H8 is about information discipline, not visual beauty. "It looks ugly" → Morville. "There's too much going on" → this heuristic.

---

## Moderator context enhancement

**Scope:** Generic change to the AutoCode engine prompt. Benefits all codebooks.

**Current state:** `autocode.py` builds prompts from codebook YAML templates. The quote batch (`build_quote_batch()`) includes session/participant metadata, topic label, and sentiment — but no instruction to treat `[researcher_context]` or `[When asked about...]` prefixes as analytical signal.

**Proposal:** Add an instruction to the AutoCode system prompt:

> When a quote includes a bracketed prefix such as `[When asked about the settings page]` or `[researcher_context: comparing to competitor]`, treat the moderator's framing as analytical context. The moderator's question often reveals what aspect of the interface the participant is reacting to. Use this context to disambiguate between tags — for example, "I expected it to be there" after a question about other apps is a stronger consistency signal than the same quote after a question about where the participant looked.

**Implementation:** Add this instruction to the system prompt assembly in `autocode.py`, before the taxonomy section. This is a one-line-to-paragraph addition, not a structural change.

**Which heuristics benefit most:**
- H4 (Consistency) — "Why did you look there?" → reveals cross-screen/cross-app comparison
- H5 (Error prevention) — "What were you worried about?" → surfaces prevention anxiety
- H2 (Match) — "What did you think that meant?" → reveals vocabulary gap context

---

## Colour set rationale

| Colour set | Heuristics | Analytical theme |
|------------|-----------|-----------------|
| `ux` | H1, H2, H6 | Interface communication — does the system speak clearly? |
| `task` | H3, H5, H9 | Error and control — can the user act safely? |
| `trust` | H4 | Conventions — does the system follow its own rules? |
| `emo` | H8 | Attention — does the design respect cognitive limits? |
| `opp` | H10 | Support — can the user get help? |

---

## Overlap analysis summary

| Nielsen heuristic | Strongest existing overlap | Distinct value Nielsen adds |
|-------------------|--------------------------|----------------------------|
| H1 Visibility | Norman → Feedback | Ambient system state (not just action-response) |
| H2 Match | Morville → Findable (labelling) | Translation gap framing (language + metaphor + ordering) |
| H3 Control | Morville → Usable (error tolerance) | Rights-based framing (escape + undo as user entitlements) |
| H4 Consistency | Norman → Conceptual model (learned behaviour) | Convention violation lens (vs general expectation mismatch) |
| H5 Prevention | Norman → Constraints, Feedback (confirmation) | Whole-design prevention (not just individual mechanisms) |
| H6 Recognition | Norman → Slips vs Mistakes (memory lapse) | Design responsibility framing (minimise need to remember) |
| H8 Aesthetic/minimal | Morville → Desirable (aesthetic quality) | Information economy (not visual craft) |
| H9 Error recovery | Norman → Feedback (ambiguous feedback) | Error message quality specifically (clarity + recovery guidance) |
| H10 Help | UXR → Learning (guidance) | Help-seeking behaviour at point of need |
| H7 Flexibility | Morville → Usable (efficiency) | Shortcut desire, repetitive task, customisation — participant-voiced efficiency wants |

**Is overlap a problem?** No. Framework codebooks are complementary lenses, not competing taxonomies. The same quote tagged by both Norman (ambiguous feedback) and Nielsen (cryptic error) produces richer analysis than either alone. The frameworks ask different *questions* about the same evidence — Norman asks "what design principle was violated?", Nielsen asks "which usability heuristic was involved?" Researchers stack codebooks precisely for these multiple angles.

The only exception is H7, where the overlap adds no distinct angle.

---

## Legal status

Safe to proceed. Nielsen/NN Group explicitly permits use: "You may use these heuristics in your own work." FigJam ships Nielsen's 10 Heuristics as a template. See `docs/private/codebook-frameworks-legal.md` for full analysis.

---

## Related files

- `bristlenose/server/codebook/` — existing framework YAMLs (garrett, morville, norman, uxr)
- `bristlenose/server/codebook/__init__.py` — YAML loader and dataclass definitions
- `bristlenose/server/autocode.py` — AutoCode engine (discrimination prompt consumer)
- `bristlenose/llm/prompts/quote-extraction.md` — `researcher_context` prefix (line 31)
- `docs/design-codebook-ecosystem.md` — codebook layering strategy
- `docs/design-codebook-island.md` — codebook UI design
- `docs/private/codebook-frameworks-legal.md` — legal analysis
- `docs/design-i18n.md` — translation decision (Nielsen stays English)
- `docs/academic-sources.html` — citation to be added

## References

- Nielsen, J. (1994). Enhancing the explanatory power of usability heuristics. _Proceedings of the SIGCHI Conference on Human Factors in Computing Systems_ (CHI '94, pp. 152–158). ACM.
- Nielsen, J. (1994). _Usability Engineering._ Morgan Kaufmann.
- Nielsen Norman Group. (2024). 10 Usability Heuristics for User Interface Design (updated). https://www.nngroup.com/articles/ten-usability-heuristics/
