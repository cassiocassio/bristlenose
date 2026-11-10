---
status: current
last-trued: 2026-11-10
trued-against: HEAD@main on 2026-11-10 (863b7767f)
---

> **Truing status:** Mixed, trued 10 Nov 2026. The Problem, the oral-history observations and Options A–E are kept verbatim as the decision record. "How it works today", "Files involved" and the Status were rewritten to match the code after `863b7767f`. Three claims that reality reversed (word count as "the strongest signal", the enum rename, FOSSDA named as the test) are kept and marked in place. See the changelog.

## Changelog

- _2026-11-10_ — trued up: both passes rewritten to the counts-in-code, reading-in-prompt design; line references replaced with symbols; "strongest signal" and the enum-rename recommendation marked superseded; Status (10 Nov 2026) added; the test plan marked as never recorded as run.
  Anchors: "speaker roles: count in code, read in the prompt, fall back on better counts"; "a session with one speaker is coded p1, never m1, whatever the role model says"; "speaker detection: LLM splitting, generalised heuristic, format-agnostic prompt".
- _2026-04-16_ — initial draft.

# Speaker role detection: oral history and non-UXR formats

## Problem

Speaker role identification (stage 5b) fails completely on oral history interviews. Discovered during FOSSDA demo dataset stress test (Apr 2026): all 10 interviews showed "Moderated by Zach" with participants as "m1" — the interviewer was identified by name but assigned as participant, and the actual interviewees (Bruce Perens, Cat Allman, etc.) were unnamed.

Two failures:

1. **Role assignment** — the interviewer is never tagged as RESEARCHER
2. **Participant naming** — interviewee names aren't extracted from context

## How it works today

_Rewritten 10 Nov 2026. The pre-November description (a `_RESEARCHER_PHRASES` list, "highest score wins", a UXR-only prompt) is in git history and in the archived prompt `bristlenose/llm/prompts-archive/prompts_2026-11-10_speaker-identification-v0.1.1-before-counts.md`._

One set of per-speaker counts feeds two readers. `_count_speakers` measures, over the **whole session** (not the first five minutes): turns, words, real questions, host-style and guest-style opening-script phrases, and whether a speaker introduced a colleague.

### Heuristic pass (`identify_speaker_roles_heuristic`)

Decides alone only when the LLM pass fails or is skipped. The score is `question share × 1.5 + host phrases per turn × 4 − guest phrases per turn × 3 + word-share nudge × 0.5`; the top scorer is the researcher.

- **Direction of address decides.** `_HOST_PHRASES` are what the person running a session says to the person hosted ("thanks for joining", "no right or wrong", "I'll record", "walk me through"); `_GUEST_PHRASES` are the reverse ("thanks for having me", "do you want me to share my screen"). Phrase hits are a rate per turn and capped at 2 per segment, so a long talker cannot win on volume.
- **A job title is not a role.** The phrase lists hold no occupation words. "Researcher" is a title the interviewee may hold ("I'm a researcher for an MP"); the product manager running the session may never use the word.
- **Not questions:** tag questions (", right?", "you know?") do not count, and neither does reported or quoted speech ("I always say, tell me about…"): a participant describing their own method is not facilitating.
- **Who spoke first is not a signal.** It depends on who joined the call first. Before 10 Nov the first speaker took any near-tie (a score gap under 1.0); now only an exact tie falls to the earlier speaker.
- **Word count is weak evidence** (see the note under "What oral history interviewers actually do"): a 0.5-weight nudge, two-speaker sessions only.
- **More than one researcher:** in a session of three or more, a second researcher is recognised when the host introduces a colleague and that speaker only asks, or when they carry the host script and ask. A 1:1 always keeps its participant.
- **Observer:** at most two turns and under 20 words (unchanged from before, so a participant who says very little in a short session reads as an observer).

### LLM pass (`identify_speaker_roles_llm`)

Sends the first five minutes to the model with `llm/prompts/speaker-identification.md` (version 0.2.0) **and the same counts for the whole session** as `{speaker_facts}`: a model eyeballing a sample cannot count turns, and "two turns, fourteen words, no questions" is what marks an observer.

The prompt defines the researcher as whoever runs *this* conversation, whatever their job, and ranks the evidence: who frames the session; direction of thanks; who asks and who answers; word share is weak; who spoke first is not evidence. It carries the same job-title caution. The speaker list and the counts are wrapped as untrusted (speaker labels on platform transcripts are real names from files); `tests/test_prompt_boundary.py` pins both. The role enum stays RESEARCHER/PARTICIPANT/OBSERVER; the prompt's "researcher" means interviewer or moderator.

### Why both fail on oral history

> **Status 10 Nov 2026 (kept as the April diagnosis).** The LLM half was fixed on 16 Apr 2026 by the format-agnostic prompt (v0.1.1, "speaker detection: LLM splitting, generalised heuristic, format-agnostic prompt"); the heuristic half was patched then and reworked on 10 Nov 2026 (see How it works today). Whether the FOSSDA corpus now comes out right has never been re-run and recorded (see Test plan).

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

> **Superseded 10 Nov 2026.** Word share is now weak evidence. In task phases a participant often says little while a moderator explains at length, and a talkative host who never asks a question inverts the signal (measured on invented hard cases, `863b7767f`). The prompt says "Don't decide on word count alone" and the heuristic weight fell from 2.0 to 0.5, two-speaker sessions only. The oral-history observation above still holds for that format.

> **Unsourced estimate.** The "10-20% vs 40-50%" figures above were never measured in this doc; the only measured moderator share nearby is 25%, in `docs/design-voice-diarization.md`.

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

**Not implemented:** D (configurable format), E (two-stage detection). Option A was first called superseded by B+C, but the phrase list kept growing and is now split by direction (see Status 10 Nov 2026). The role enum stays as RESEARCHER/PARTICIPANT (internal, not user-facing — renaming is high churn for no user value).

## Status (10 Nov 2026)

**Counts in code, reading in the prompt, the heuristic as fallback.** Commit `863b7767f` ("speaker roles: count in code, read in the prompt, fall back on better counts"):
- the first-speaker tiebreak is gone;
- opening-script phrases are split into host and guest lists and scored per turn;
- tag questions and reported speech are ignored; a second moderator is possible in sessions of three or more;
- `speaker_facts()` sends the same counts to the model, prompt 0.2.0, the speaker list and counts wrapped as untrusted.

Tests: `tests/test_speaker_heuristic_counts.py` (20), mutation-checked. Measured with a scratch harness (private, git-excluded) on 82 real speakers from the trial projects: the heuristic agrees with the model's reading on 78 (the previous heuristic 77); the prompt with counts agrees on 80, and the two it differs on are a junk placeholder transcript where it declined to claim evidence; all five real observers were right with counts. On 35 invented, labelled speakers the heuristic got 35 right (the previous one 24); those cases were tuned on, so that figure is not independent evidence, and the real sessions are easy (the moderator spoke first in all of them). **Not measured:** the shipped prompt on a paid run, and FOSSDA. **Known weakness (old and new):** on the heuristic fallback a facilitator who only gives statements while the participant asks clarifying questions can invert; only the model path fixes it.

Also related: "a session with one speaker is coded p1, never m1, whatever the role model says" (8 Nov 2026) removed a different m1 failure, for solo think-aloud sessions.

## Recommendation

> **Status 10 Nov 2026:** B was built and C was built, then C was demoted (word count is a weak nudge). The enum rename below was declined: see "Not implemented" above.

**B + C together.** Generalise the prompt (B) so the LLM understands interview roles beyond UXR, and add word count ratio (C) as a strong heuristic signal. The combination is robust across formats without requiring the user to configure anything.

The role enum change (RESEARCHER → INTERVIEWER) is worth doing — "researcher" is UXR jargon that doesn't make sense for oral history or journalism. "Interviewer" is universal.

Naming the interviewee (the "m1" problem) is likely also fixed by a better prompt (the prompt does extract `person_name`; whether the FOSSDA names now come out was never re-checked) — if the LLM correctly identifies the interviewee role, it can also extract their name from the conversation context ("I'm Bruce Perens, and I was at Pixar...").

## Files involved

By symbol, not line number (every line reference in the April version had gone stale):

- `bristlenose/stages/s05b_identify_speakers.py` — `_HOST_PHRASES` / `_GUEST_PHRASES`, `_count_speakers`, `speaker_facts`, `identify_speaker_roles_heuristic`, `identify_speaker_roles_llm`
- `bristlenose/llm/prompts/speaker-identification.md` — version 0.2.0 (`{transcript_sample}`, `{speaker_list}`, `{speaker_facts}`)
- `bristlenose/models.py` — `SpeakerRole` enum; `FullTranscript.full_text()` emits the role tag
- `bristlenose/stages/s09_quote_extraction.py` — reads the transcript through `full_text()`, so the role tag reaches the prompt; also filters segments by role
- `bristlenose/llm/prompts/quote-extraction.md` — Rule 1, the suppression gate
- `tests/test_speaker_heuristic_counts.py`, `tests/test_prompt_boundary.py` — the pins

## Test plan

> **Not recorded as run (10 Nov 2026).** Nothing in the repo records a FOSSDA, IKEA or rock-climbing re-run against these criteria. The nearest evidence is the measurement under Status (10 Nov 2026), which used the trial projects' real sessions (no FOSSDA).

1. Re-run FOSSDA corpus after fix — all 10 sessions should identify "Zach" as interviewer
2. Re-run IKEA and rock climbing corpora — verify no regression (UXR moderators still detected)
3. Check that interviewee names are extracted (Bruce Perens, Cat Allman, etc. not "m1")
4. Check that quote extraction volume drops ~30-50% (interviewer speech excluded)
5. Check that quote atomicity improves (without interviewer questions glued to answers)
