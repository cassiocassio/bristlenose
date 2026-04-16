# Speaker role detection: oral history and non-UXR formats

## Problem

Speaker role identification (stage 5b) fails completely on oral history interviews. Discovered during FOSSDA demo dataset stress test (Apr 2026): all 10 interviews showed "Moderated by Zach" with participants as "m1" — the interviewer was identified by name but assigned as participant, and the actual interviewees (Bruce Perens, Cat Allman, etc.) were unnamed.

Two failures:

1. **Role assignment** — the interviewer is never tagged as RESEARCHER
2. **Participant naming** — interviewee names aren't extracted from context

## How it works today

### Heuristic pass (`s05b_identify_speakers.py:119-125`)

Scores each speaker by:
- Question ratio (what proportion of their segments end with `?`)
- Hits against `_RESEARCHER_PHRASES` (lines 43-69) — phrases like "can you try", "what would you do", "walk me through", "let's move on to", "think aloud"

The speaker with the highest score is assigned `SpeakerRole.RESEARCHER`.

### LLM pass (`s05b_identify_speakers.py:166-249`)

Sends the first 5 minutes of transcript to the LLM using `llm/prompts/speaker-identification.md`. The prompt frames roles entirely around UX research:
- RESEARCHER: "conducts the research session", "facilitates discussion", "guides the participant through tasks or screens"
- PARTICIPANT: "the person being studied"
- OBSERVER: "watches but doesn't participate"

### Why both fail on oral history

**Heuristic pass:** Oral history interviewers don't use UXR phrases. They don't say "can you try clicking" or "walk me through the interface." They ask substantive historical questions ("tell me about your time at Pixar", "how did you get involved with Debian"). Question ratio alone isn't discriminating enough — the interviewee also asks rhetorical questions.

**LLM pass:** The prompt asks the model to look for someone giving "instructions" and guiding people "through tasks or screens." Oral history interviewers do none of this. The model sees two people having a substantive conversation and can't identify who's driving it.

### Downstream impact

When both speakers are tagged PARTICIPANT or UNKNOWN:
- Quote extraction (stage 9) includes interviewer speech — Rule 1 ("only extract participant speech, skip [RESEARCHER] segments") can't fire because nobody has the RESEARCHER tag
- Interviewer questions get extracted as quotes
- Question + answer sometimes concatenate into single mega-quotes
- Roughly doubles the volume of extracted text
- Contributes to max_tokens truncation

## What oral history interviewers actually do

Unlike UXR moderators, oral history interviewers:
- Ask open-ended questions about the past ("tell me about...", "what was it like when...")
- Prompt for elaboration ("can you say more about that", "what happened next")
- Introduce topics ("I'd like to talk about your work on...")
- Summarise and reflect back ("so you're saying that...")
- Speak much less than the interviewee (typically 10-20% of total words vs 40-50% for a UXR moderator)
- Don't give instructions, assign tasks, or reference screens/interfaces

The **word count asymmetry** is actually the strongest signal: in oral history, the interviewer speaks far less than the interviewee. In UXR, it's more balanced.

## Options

### A: Expand the heuristic phrase list

Add oral-history-style phrases to `_RESEARCHER_PHRASES`:
- "tell me about", "can you describe", "what was it like"
- "how did you get involved", "what happened next", "can you say more"
- "I'd like to ask about", "let's talk about"

**Pros:** Simple. Addresses the immediate failure.
**Cons:** Brittle — always playing catch-up with new interview styles. Journalism, market research, academic interviews all have different moderator patterns.

### B: Generalise the LLM prompt

Rewrite `speaker-identification.md` to describe interview roles generically, not UXR-specifically:

- INTERVIEWER (not RESEARCHER): "the person who drives the conversation by asking questions, introducing topics, and prompting elaboration. They guide the structure of the conversation but may not give explicit instructions."
- INTERVIEWEE (not PARTICIPANT): "the person whose experiences, opinions, or knowledge are being explored."

Include examples of different interview formats: UXR moderated session, oral history, journalistic interview, market research focus group.

**Pros:** Handles all interview formats. More robust than pattern-matching.
**Cons:** May need the role enum to change (RESEARCHER → INTERVIEWER), which touches models, prompts, and quote extraction logic.

### C: Word count ratio as primary signal

In any 2-speaker interview, the person who speaks less is almost certainly the interviewer. Use total word count per speaker as the primary heuristic, with question ratio as a tiebreaker:

```python
word_counts = {speaker: sum(len(seg.text.split()) for seg in segs) for speaker, segs in by_speaker.items()}
# Speaker with fewer total words is likely the interviewer
```

**Pros:** Format-agnostic. Works for UXR, oral history, journalism. No phrase list to maintain.
**Cons:** Fails for panel discussions, focus groups, or interviews where two people speak roughly equally. Fails if diarisation merged speakers incorrectly.

### D: Configurable interview format

Add a `--format` flag or config option: `uxr` (default), `oral-history`, `focus-group`, `auto`. Each format activates different heuristics and prompt variants.

**Pros:** Explicit. User knows what they're getting. Can tune each format independently.
**Cons:** Users have to choose. "Auto" would need its own detection logic. More config surface to maintain.

### E: Two-stage detection (detect format, then detect roles)

1. First LLM call: "what kind of interview is this?" (moderated UXR, oral history, panel discussion, focus group, lecture, etc.)
2. Second LLM call: role identification with format-specific prompt and heuristics

**Pros:** Most robust. Different formats get different treatment.
**Cons:** Extra LLM call. Two prompts to maintain. Format detection itself may be unreliable.

## Status (Apr 2026)

**Options B + C implemented.** The LLM role identification prompt (`speaker-identification.md`) has been generalised to cover all interview formats (UXR, oral history, journalism, market research). Word count asymmetry is now a heuristic scoring factor. Researcher phrases expanded with oral-history patterns.

**Companion work:** The single-speaker diarization problem (raw audio with no speaker labels) is addressed separately by an LLM splitting pre-pass — see [design-speaker-splitting.md](design-speaker-splitting.md).

**Not implemented:** Options A (superseded by B+C), D (configurable format), E (two-stage detection). The role enum stays as RESEARCHER/PARTICIPANT (internal, not user-facing — renaming is high churn for no user value).

## Recommendation

**B + C together.** Generalise the prompt (B) so the LLM understands interview roles beyond UXR, and add word count ratio (C) as a strong heuristic signal. The combination is robust across formats without requiring the user to configure anything.

The role enum change (RESEARCHER → INTERVIEWER) is worth doing — "researcher" is UXR jargon that doesn't make sense for oral history or journalism. "Interviewer" is universal.

Naming the interviewee (the "m1" problem) is likely also fixed by a better prompt — if the LLM correctly identifies the interviewee role, it can also extract their name from the conversation context ("I'm Bruce Perens, and I was at Pixar...").

## Files involved

- `bristlenose/stages/s05b_identify_speakers.py` — heuristic phrases (43-69), scoring (119-125), LLM call (166-249)
- `bristlenose/llm/prompts/speaker-identification.md` — UXR-only framing
- `bristlenose/models.py` — `SpeakerRole` enum, `full_text()` role tagging (line 207)
- `bristlenose/stages/s09_quote_extraction.py` — reads `[RESEARCHER]` tags to skip interviewer speech
- `bristlenose/llm/prompts/quote-extraction.md` — Rule 1 (line 15), the suppression gate

## Test plan

1. Re-run FOSSDA corpus after fix — all 10 sessions should identify "Zach" as interviewer
2. Re-run IKEA and rock climbing corpora — verify no regression (UXR moderators still detected)
3. Check that interviewee names are extracted (Bruce Perens, Cat Allman, etc. not "m1")
4. Check that quote extraction volume drops ~30-50% (interviewer speech excluded)
5. Check that quote atomicity improves (without interviewer questions glued to answers)
