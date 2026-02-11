# Generating Synthetic Interview Test Data

How to create realistic VTT interview transcripts for stress testing the Bristlenose pipeline. This document captures the repeatable process so future datasets (any topic, any language, any scale) can be generated consistently.

---

## Why synthetic data

Real interview data contains PII, client confidentiality constraints, and licensing issues. Synthetic data lets us:

- Stress test every pipeline stage with known characteristics
- Exercise specific features (multi-participant, sentiment range, speaker identification)
- Create datasets of any size without waiting for real studies
- Include edge cases that rarely occur naturally (disagreements, technical failures, speech artefacts)
- Share datasets publicly (in `trial-runs/` or `tests/fixtures/`)

---

## Existing datasets

| Dataset | Location | Sessions | Duration | Topic |
|---------|----------|----------|----------|-------|
| Rock climbing | `tests/fixtures/multi_participant/` | 7 | ~4 min each | Indoor climbing |
| Fishkeeping | `trial-runs/Fishkeeping/` | 20 | ~20-30 min each | Freshwater tropical fish |

---

## The process

### Step 1: Define the study brief

Tell Claude what you want. The brief needs:

- **Topic** — what the interviews are about
- **Number of sessions** — how many VTT files
- **Duration** — target length per session (affects word count and cue count)
- **Session formats** — ratio of 1:1 to multi-participant (paired, trio, with observer)
- **Interview structure** — what the two halves cover (e.g. attitudinal + website exploration)
- **Language** — for non-English datasets, specify the language for all dialogue
- **Output location** — where the files go (`trial-runs/<Topic>/` for stress tests, `tests/fixtures/` for unit test fixtures)

Example brief:

> Create 13 half-hour interviews about llama farming in Bolivia. All dialogue in Spanish. 10 × 1:1, 3 × multi-participant. Part 1: farming practices and challenges. Part 2: exploring a livestock equipment website. Output to `trial-runs/Llama-Farming/`.

### Step 2: Research the domain

Before writing a discussion guide, Claude should understand the topic well enough to write realistic dialogue. This means:

- **Fetch relevant websites** that participants will explore in Part 2 (if the study includes website evaluation). Use `WebFetch` to grab homepage structure, navigation categories, product ranges, and content types. Save key details for the agents that will write individual sessions.
- **Understand domain vocabulary** — fishkeeping has "cycling", "nitrate", "substrate"; llama farming has "fibre quality", "alpaca crosses", "altiplano grazing". Participants at different expertise levels use different vocabulary.
- **Identify the participant spectrum** — who keeps fish / farms llamas / climbs rocks? What are the experience levels, motivations, common frustrations?

This step produces raw material. Don't skip it — agents writing individual sessions need concrete details (product names, species, equipment brands, website sections) to produce realistic dialogue.

### Step 3: Write and validate the discussion guide

Create a structured discussion guide following UX research best practice:

1. **Warm-up** (1 min) — easy, non-threatening opener to settle nerves
2. **Grand tour questions** (Spradley, 1979) — open-ended, establish context
3. **Contrast questions** — surface preferences and mental models
4. **Experience questions** — concrete stories (critical incident technique, Flanagan 1954)
5. **Process questions** — how they do things, decision-making
6. **Bridge** — natural transition from discussion to stimulus
7. **Stimulus-response** — think-aloud exploration of website/product/prototype
8. **Closing reflection** — synthesis and attitude shifts

Each question should include **probes** (follow-up prompts for thin answers). The guide should explicitly note which questions map to which research tradition.

**Ask to review the guide before proceeding.** The user may want to add, remove, or reword questions. Changes at this stage are cheap; changes after 20 transcripts are written are expensive.

### Step 4: Design the session matrix

Create a table of all sessions with:

| Column | Purpose |
|--------|---------|
| Session number | S1, S2, ... |
| Participant name(s) | Realistic names matching the study's cultural context |
| Experience level | Beginner / intermediate / experienced / lapsed / expert |
| Tank/farm/hobby focus | What makes this participant distinctive |
| Key themes to surface | What unique data this session should generate |
| Website | Which website they explore (if split across multiple sites) |
| Moderator | Which moderator runs this session |
| Format | 1:1 / paired / trio / paired + observer |

**Design decisions at this stage:**

- **Moderators** — use 2 moderators (one primary, one secondary for ~3 sessions) to test speaker identification with different moderator names
- **Expertise spread** — deliberately include complete beginners through experts. Different vocabulary densities test quote extraction
- **Multi-participant dynamics** — couple, friends, mentor/mentee, strangers. Include at least one session with mild disagreement to test friction/sentiment detection
- **Cultural diversity** — realistic for the study's geographic context
- **Website split** — if evaluating multiple sites, split sessions across them (e.g. 10 sessions on site A, 10 on site B)

### Step 5: Generate VTT files in parallel

This is where the actual writing happens. **Launch one background agent per session** (or per batch of 4), each with:

1. The discussion guide
2. The participant profile for that session
3. Website structure details (from Step 2)
4. Speech artefact requirements
5. Target duration and cue count

**Critical details for the agent prompt:**

- **VTT format**: `WEBVTT` header, blank line, then cue blocks with `HH:MM:SS.mmm --> HH:MM:SS.mmm` timestamps and `<v Speaker Name>` voice tags
- **Speech artefacts**: "um", "uh", "er", self-corrections ("I mean—"), false starts, incomplete sentences, filler words. Every session should include these for realism
- **Crosstalk in multi-participant sessions**: overlapping speech, interruptions, people finishing each other's sentences, side conversations
- **Timing realism**: vary cue lengths — some short (2-3 seconds for "Yeah" or "Mm-hmm"), some long (20-40 seconds for detailed stories). Don't make every cue the same length
- **Participant voice**: each participant should have a distinctive speech pattern matching their background. A shop worker talks differently from a nervous beginner
- **Website exploration**: participants should describe what they see, read headings aloud, comment on navigation, compare to expectations from Part 1. Reference real sections/products from the website research in Step 2
- **Target**: ~80-120 cue blocks for a 30-minute 1:1 session, ~140-170 for multi-participant

**Parallelisation**: launch all agents simultaneously using `Task` with `run_in_background: true`. 20 sessions can be generated in parallel in ~3-5 minutes.

### Step 6: Extract and write files

Background agents return VTT content embedded in their output. Extract the VTT content (everything from `WEBVTT` to the end of the last cue block) and write to individual files.

**File naming convention**: `{Topic} Research S{N}.vtt` — e.g. `Fishkeeping Research S14.vtt`, `Llama Farming Research S7.vtt`.

### Step 7: Fix and verify

After writing all files:

1. **Check for invalid timestamps** — LLMs occasionally generate `00:26:60.000` (seconds >= 60). Scan all files with regex and fix any invalid values
2. **Parse with Bristlenose** — run `_parse_vtt()` from `bristlenose.stages.parse_subtitles` on every file. Confirm:
   - All files parse without errors
   - Correct number of speakers per session
   - Speaker names match the session matrix
   - Duration is in the expected range
3. **Count totals** — report file count, total segments, total size, unique speakers

**Verification script pattern:**

```python
from bristlenose.stages.parse_subtitles import _parse_vtt
from pathlib import Path

folder = Path('trial-runs/Fishkeeping')
for f in sorted(folder.glob('*.vtt')):
    segments = _parse_vtt(f)
    speakers = set(s.speaker_label for s in segments)
    duration = segments[-1].end_time
    print(f'{f.name}: {len(segments)} segs, {len(speakers)} speakers, {duration/60:.0f} min')
```

### Step 8 (optional): Run the full pipeline

The ultimate validation is running the generated data through the full Bristlenose pipeline:

```bash
bristlenose run trial-runs/Fishkeeping/
```

Check the output report for:
- All participants identified correctly
- Moderator vs participant roles assigned correctly
- Diverse themes generated
- Quotes span all sentiment tags
- Multi-participant sessions don't confuse speaker identification
- Website exploration quotes cluster into screen-level sections

---

## Checklist for a new dataset

Copy this checklist when creating a new test dataset:

- [ ] Define brief (topic, count, duration, formats, language, output location)
- [ ] Research domain (fetch websites, understand vocabulary, identify participant spectrum)
- [ ] Write discussion guide (funnel structure, probes, validated against research best practice)
- [ ] Get user approval on discussion guide before proceeding
- [ ] Design session matrix (participants, expertise levels, moderators, website splits)
- [ ] Generate VTT files in parallel (one agent per session, all launched simultaneously)
- [ ] Extract VTT content from agent outputs and write to files
- [ ] Fix invalid timestamps (seconds >= 60)
- [ ] Parse all files with `_parse_vtt()` — zero errors
- [ ] Report summary (file count, total segments, total size, unique speakers, duration range)
- [ ] Optionally run `bristlenose run` on the dataset to validate end-to-end

---

## Non-English datasets

For interviews in languages other than English:

- **All dialogue** (questions and answers) should be in the target language
- **Speaker names** should be culturally appropriate for the study context
- **VTT format stays the same** — `WEBVTT` header, timestamps, and `<v>` tags are language-agnostic
- **Speech artefacts** should use the target language's fillers (Spanish: "eh", "bueno", "o sea", "pues"; Japanese: "eto", "ano"; Portuguese: "tipo", "n\u00e9")
- **Domain vocabulary** should use the correct local terminology, not translated English jargon
- The discussion guide can be written in English (as a reference for Claude) but the generated VTT content must be in the target language

---

## Lessons learned

### From the fishkeeping dataset (Feb 2026)

1. **LLMs occasionally generate invalid VTT timestamps** — `00:26:60.080` instead of `00:27:00.080`. Always scan for seconds >= 60 or minutes >= 60 after generation
2. **Agent output extraction needs care** — VTT content is returned inside the agent's conversation log. Extract from `WEBVTT` to the last cue block; don't include markdown fences or trailing text
3. **Website fetching often returns 404 on deep links** — homepage scraping is usually enough. Capture navigation structure, product categories, and content sections from the homepage
4. **20 agents in parallel works fine** — all complete within 3-5 minutes. No need to batch
5. **`_parse_vtt()` is the function to use** (underscore prefix — it's the internal parser). The attribute for speaker name is `speaker_label`, not `speaker`
6. **Speech artefacts must be explicitly requested** — without them, agents produce unnaturally clean dialogue. Specify "ums", self-corrections, and incomplete sentences in every agent prompt
7. **Give each agent concrete website details** — don't just say "they explore a fishkeeping website". List the actual navigation categories, product names, and page sections so agents can write realistic think-aloud dialogue
8. **Multi-participant sessions need explicit dynamic instructions** — "the couple disagrees about X", "the mentor corrects the beginner on Y", "two friends have a running joke about Z". Without this, group sessions read like sequential 1:1 interviews
