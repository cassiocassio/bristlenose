# Design: LLM Speaker Splitting

## Problem

When source files have no speaker labels — raw audio transcribed by Whisper, or subtitles without voice tags — all segments get a single label. Stage 5b (speaker identification) classifies speakers into roles (researcher/participant/observer) but assumes upstream stages already split audio into distinct speakers. With only one speaker label, the heuristic assigns a single role and `assign_speaker_codes()` produces a single code (e.g. all `m1`), even when two or more people are clearly talking.

The FOSSDA oral history interviews are the primary example: raw video recordings of an interviewer and guest, no platform transcript. A human can trivially tell who is speaking from conversational cues ("my name is Brian", "thank you Daniel"), but the pipeline lumps everything together.

## Context

Bristlenose has no audio diarization. The pipeline relies on source files already having speaker labels:

- VTT/SRT with `<v Speaker>` tags or `Speaker: text` patterns (Stage 3)
- DOCX with speaker prefixes (Stage 4)
- Whisper produces only timestamps and text — no speaker info (Stage 5)

For the mainstream use case (Teams/Zoom/Meet recordings), diarization is handled by the platform and arrives in the transcript. The gap only affects raw recordings without platform transcripts.

### Alternatives considered

| Approach | Verdict |
|----------|---------|
| **pyannote.audio** (acoustic diarization) | Best accuracy. Gated HuggingFace model (account + agreement + token). Requires torch >=2.8 (~2GB). MPS buggy on Mac — CPU only. Overkill for the current scope; worth revisiting as an optional `--diarize` flag if raw recordings become a common input |
| **whisperx** | Wraps pyannote under the hood — same dependency cost, no independent value |
| **NeMo** (NVIDIA) | GPU-oriented, ~4-6GB deps, impractically slow on CPU. Not viable for local-first Mac tool |
| **SpeechBrain** | ~36% DER vs pyannote's ~11%. Not competitive for diarization accuracy |
| **LLM text-based splitting** | Zero new dependencies, uses existing LLM infrastructure. Handles obvious interview formats (name cues, turn-taking) with high reliability. Weaker for ambiguous rapid back-and-forth without contextual cues. **Chosen approach** |

The LLM approach was chosen because:
1. Zero dependency cost — reuses existing LLM client and structured output infrastructure
2. Handles the primary use case (2-person interview with clear conversational structure) well
3. Graceful degradation — if the LLM can't detect speaker changes, the pipeline falls back to single-speaker behaviour (no worse than before)
4. Acoustic diarization (pyannote) can be added later as a complementary Tier 2 for harder cases

## Design

### Two-tier model

**Tier 1 — platform transcripts (Teams/Zoom/Meet):** Speaker labels already present. Current pipeline handles this. No change.

**Tier 2 — raw audio/video (no transcript):** New LLM pre-pass detects speaker changes from text. Runs before existing heuristic + role identification.

The pipeline already knows which tier it's in — sessions with a single unique `speaker_label` (or none) need splitting; sessions with 2+ labels skip it.

### New function: `split_single_speaker_llm()`

Location: `bristlenose/stages/s05b_identify_speakers.py`

**Guard**: count unique `speaker_label` values. If >=2 distinct labels already exist, return segments unchanged.

**Whole transcript, in parts** (since 3 Oct 2026): every segment is read, `SPLIT_CHUNK_SEGMENTS` (200) at a time and in order. Each part after the first is shown the last `SPLIT_CONTEXT_SEGMENTS` (12) lines already labelled, in an `<untrusted_labelled_lines_*>` envelope, and told to keep using the same speaker identifiers. Parts are needed because the response is close to one boundary per segment in a real interview (281 boundaries for 377 segments, measured), so one call on a 2-hour recording would exceed some providers' output caps. The parts run in sequence, since each needs the labels before it; sessions still run concurrently.

*Until 3 Oct 2026* the splitter read a sample window of `min(max(300, total_duration * 0.18), 480)` seconds and carried the last label it saw to every later segment. § Measured below is why that changed.

**Input format**: numbered lines (`[0] text`, `[1] text`, ...) without timecodes. The LLM doesn't need timing information to detect speaker changes.

**Output format**: boundary markers — `(segment_index, speaker_id, person_name)`. Each boundary means "from this segment index onwards, this speaker is talking." This is simpler and more robust than per-segment assignment:
- Fewer items for the LLM to return
- A part's leading lines, before its first boundary, continue the label the previous part ended on
- Boundaries are sorted and applied in a single pass

**Fallback**: if the first part fails, log the error and return segments unchanged — the single-speaker path continues. If a later part fails, the parts already labelled stand and every remaining segment carries the last label (the old behaviour, now only past a failure); the error names the part (`speaker splitting (part 2 of 3): …`). If the model finds only one speaker overall, the original labels are kept.

### Pipeline integration

In `pipeline.py`, before the heuristic pass:

1. Identify sessions with <=1 unique speaker label
2. Run `split_single_speaker_llm()` concurrently for those sessions (same semaphore pattern as role identification)
3. Proceed to heuristic pass — now with multi-speaker labels, the heuristic can detect researcher vs participant
4. LLM role refinement runs as before

### Caching

No new cache files needed. The existing speaker-info cache (`speaker-info/{sid}.json`) stores segments-with-roles. Since splitting mutates `speaker_label` before the heuristic runs, the cached segments already reflect the split. On resume, loaded segments have the correct multi-speaker labels.

### Structured output

New Pydantic models in `bristlenose/llm/structured.py`:

```python
class SpeakerBoundary(BaseModel):
    segment_index: int    # 0-based, first must be 0
    speaker_id: str       # "Speaker A", "Speaker B"
    person_name: str = "" # extracted name if mentioned

class SpeakerSplitAssignment(BaseModel):
    speaker_count: int
    boundaries: list[SpeakerBoundary]
```

### Prompt

`bristlenose/llm/prompts/speaker-splitting.md` — instructs the LLM to look for:
- Self-introductions ("my name is...")
- Direct address ("thank you, Brian")
- Turn-taking (question followed by answer)
- Role shifts (facilitator vs respondent)
- Conversational markers ("welcome", "thanks for coming")

Default assumption: 2 speakers (interviewer + interviewee). Returns `speaker_count=1` if the transcript genuinely contains a single person (monologue, lecture).

## File map

| File | Change |
|------|--------|
| `bristlenose/stages/s05b_identify_speakers.py` | New `split_single_speaker_llm()` function |
| `bristlenose/llm/structured.py` | New `SpeakerBoundary`, `SpeakerSplitAssignment` models |
| `bristlenose/llm/prompts/speaker-splitting.md` | New prompt |
| `bristlenose/pipeline.py` | Wire splitting before heuristic pass, import new function |
| `tests/test_speaker_splitting.py` | 10 tests: guards, success, fallback, integration |

## Status (Apr 2026)

**Implemented.** LLM splitting pre-pass is live in `s05b_identify_speakers.py`. Review findings addressed (ge=0 constraint, PII logging downgraded to debug, out-of-range boundary filtering).

**Companion work:** The role detection problem (UXR-specific heuristics and prompt failing on oral history) is addressed separately — see [design-speaker-role-detection.md](design-speaker-role-detection.md). That work generalised the LLM prompt, added word count asymmetry to heuristic scoring, and expanded researcher phrases for oral history formats.

## Limitations

- **Text-only**: relies on linguistic cues, not acoustic features. Won't work for rapid back-and-forth without name mentions or clear conversational structure
- **Sample window — removed 3 Oct 2026.** Until then the LLM read only the first 5–8 minutes and carried the last label to the end, so a 2-hour recording had ~112 minutes of propagated labels. Whole-transcript splitting replaced it (§ Measured).
- **Cost and time grow with length.** Every segment is sent, in sequential parts, so a long session takes several calls. The whole transcript also reaches the provider *before* PII redaction (stage 7), where it used to be the first few minutes — `SECURITY.md` § Speaker identification and PII timing.
- **Existing projects keep their old split.** Speaker results are cached per session and the cache is keyed on the transcripts, not the splitter, so re-running a project analysed before 3 Oct 2026 reuses the old labels; only a run from scratch (`--clean`) re-splits.
- **No overlapping speech**: assumes one speaker per segment. If a segment contains two speakers talking simultaneously, it gets assigned to one
- **LLM accuracy varies**: local models (Ollama) are less reliable than cloud models for structured output. The 3-retry mechanism in `_analyze_local()` helps but doesn't guarantee correct boundary detection

## Measured: opening sample vs whole transcript (3 Oct 2026)

**Outcome: whole-transcript splitting, in parts, shipped the same day** (owner's call). The last two rows of the table below are the shipped function — `split_single_speaker_llm` itself, three parts for this 435-segment session — scored the same way; "sampled" is the function it replaced, and "whole" the single-call experiment.

The propagation limit above was measured, not just reasoned about. Harness:
`experiments/speaker_split_full/` (`run.py`, `eval_platform.py`, `page.html`).
Data and results stay outside the tracked tree because they carry participant
speech. "Whole" is the shipped prompt and model (Sonnet 4.6) given every
segment instead of the sample. Each method is followed by the shipped
heuristic and LLM role passes.

**Against platform ground truth.** A 38-minute Teams interview came with its
`.docx` transcript (named turns). The video was transcribed separately with
Whisper, and each Whisper segment was scored against two truths built from
that `.docx`:

- **Text truth (primary).** Label a segment by whose nearby Teams text holds
  its words: one speaker at least 0.7, the other under 0.4. 338 of 435
  segments qualify.
- **Timing truth.** Label a segment by whose turn interval covers at least
  75% of it, and keep it only when half its words appear in that speaker's
  nearby text. 239 segments qualify.

The timing truth is the weaker of the two. Teams' turn starts often come
late, so short moderator turns fall inside the participant's interval, and
the filter keeps 47% of moderator segments against 81% of participant ones.
With the filter off, the moderator ranking survives and overall accuracy does
not, because that truth is mostly swapped there.

| | truth | moderator segments right | participant segments right | all segments right |
|---|---|---|---|---|
| sampled (shipped) | text | 36/95 (38%) | 235/243 (97%) | 80% |
| whole, runs 1–3 | text | 84–92/95 (88–97%) | 214–217/243 (88–89%) | 89–91% |
| sampled (shipped) | timing | 42/81 (52%) | 156/158 (99%) | 83% |
| whole, runs 1–3 | timing | 68–74/81 (84–91%) | 140–144/158 (89–91%) | 87–91% |
| **shipped, chunked (200), 2 runs** | text | 81–84/95 (85–88%) | 225–232/243 (93–95%) | 91–94% |
| **shipped, chunked (200), 2 runs** | timing | 63–65/81 (78–80%) | 141–146/158 (89–92%) | 85–88% |

- **Stability:** the three whole runs label 407/435 segments the same.
- **Where the shipped method works, they agree.** Inside the window the
  shipped method reads, the shipped split and two of the three whole runs
  score 45/47 on the timing truth (the other whole run, 39/47). All of the
  shipped method's loss is in the propagated tail.
- **The shipped method's high participant score is structural, not skill.**
  After the window it scores 0/39 moderator and 153/153 participant. That is
  the last label carried forward, and this window happened to end on a
  participant line. A window that ends on the moderator flips the failure:
  every later participant line becomes the moderator's. The Talismanic
  session below is that case.
- **Mixed segments:** 67 of 435 Whisper segments (15%) hold both voices by
  the Teams timing. No segment-level method can get those right — see
  *No overlapping speech* above.

**Two bare recordings, no ground truth yet.** On the Talismanic project the
methods agree on 66/71 and 60/61 segments inside the sample window, and on
127/167 and 127/316 after it. In the 35-minute session the shipped split
gives the moderator 69% of talk time. A hand-labelling page (`page.html`)
exists for these; the labels are not in yet.

**Costs not yet measured:**
- *Output size grows with the session.* The 35-minute session returned 281
  boundaries for 377 segments, which is close to one label per segment. A
  2-hour recording would need ~1,000+ boundaries in one structured response.
  That would exceed some providers' output caps (gpt-4o: 16,384 tokens) and
  take minutes to stream. Long sessions therefore need the chunked passes
  named under *Future*, not one call.
- Input cost scales with length: roughly 4–6× the sampled call for a
  30–40 minute session.
- n = 1 platform session, with one moderator. Treat the numbers as
  direction, not calibration.

## Future

- **Acoustic diarization (pyannote)**: optional `pip install bristlenose[diarize]` extra for raw recordings where text-based splitting is insufficient. Would run as a true diarization step on the audio before transcription
- **Confidence scoring**: the LLM could return confidence per boundary, allowing the pipeline to flag uncertain splits for human review
- ~~**Full-transcript splitting**~~ — **shipped 3 Oct 2026**, in parts that carry speaker identities across (§ Design, § Measured).
