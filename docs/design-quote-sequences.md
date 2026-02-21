# Quote Sequences

How Bristlenose detects and represents consecutive quotes from the same conversational flow.

---

## The problem

Transcription engines — Whisper, subtitle formats, Teams DOCX exports — divide speech into paragraphs. These paragraph breaks are artifacts of the technology: pauses in audio, subtitle display timing, or the written-text conventions of the export format. They don't correspond to boundaries in the speaker's thinking.

When a participant tells a story — recounting a sequence of events, building an argument, describing a frustration at length — the transcription engine may produce five or ten separate paragraphs. The quote extraction stage correctly identifies each paragraph as carrying signal (user need, frustration, narrative detail). The clustering and theming stages correctly group them by topic. The analysis page correctly flags the concentration of sentiment.

But when five quotes from the same participant appear in a signal card, the reader may perceive them as five independent observations when they are really one continuous narrative. The signal isn't inflated — it's genuine. Rich, sustained storytelling about a pain point is exactly what researchers look for. The problem is purely representational: the reader needs to understand that these quotes are a *sequence*, not a *set*.

### Paragraphing is a convention of written language

The paragraph as a unit of text organisation is a convention that emerged from medieval manuscript production — the *pilcrow* (¶) marked section breaks in liturgical texts. It was formalised for silent reading, a practice that became widespread only with the printing press. Spoken language doesn't have paragraphs. People speak in sentences, half-sentences, interjections, and extended turns. A research interview is closer to Socratic dialogue than to an essay.

The transcription engine imposes paragraph structure on speech because it must produce text, and text needs visual breaks. But these breaks are arbitrary relative to the speaker's intent. Two "paragraphs" separated by a 3-second pause and a researcher's "mm-hmm" are part of the same thought.

### What we're not doing

We are *not* saying these consecutive quotes are a single data point that has been miscounted as five. The signal concentration metrics are working correctly — multiple intense quotes about the same topic from the same participant *is* concentrated signal. We are not deduplicating, merging, or discounting. We are adding a visual affordance so the reader perceives the narrative flow.

---

## Source material classes

Interview data arrives in three forms, each with different temporal metadata:

| Class | Examples | Timecodes? | Sequence signal |
|-------|----------|------------|-----------------|
| **Timecoded audio/video** | Whisper transcription, VTT, SRT | Precise (sub-second) | Both timecode proximity and segment ordinal |
| **Timecoded text** | Teams DOCX export | Coarse (minute-level) | Both, but timecodes less precise |
| **Pure text** | Plain DOCX, pasted transcripts, researcher notes | None (all 0.0) | Segment ordinal only |

The third class is critical. We will never know how quickly Socrates spoke, or how long the pauses were in a transcript exported from a platform that doesn't include timecodes. For these sources, the ordinal position of the segment in the document is the *only* signal we have for sequence. This is why we need both detection methods.

---

## Detection methods

### Method 1: Timecode proximity

For timecoded transcripts, two quotes are part of the same conversational flow if the gap between one quote's end and the next quote's start is small. "Small" is a threshold that depends on interview style:

- A rapid-fire usability test might have 5-second gaps between participant turns
- A reflective depth interview might have 30-second pauses while the participant thinks
- A researcher's "tell me more" adds 3–5 seconds of non-participant speech

**Threshold**: needs empirical determination. Starting hypothesis: 30 seconds. This should capture natural pauses, researcher back-channelling ("mm-hmm", "go on"), and brief moderator prompts, without falsely linking quotes that are minutes apart.

### Method 2: Segment ordinal proximity

Every transcript segment gets a 0-based ordinal reflecting its position in the final merged transcript. Two quotes are part of the same flow if the gap between their segment ordinals is small.

A gap of 1 means the quotes came from adjacent segments. A gap of 2 means one segment was skipped — likely a researcher interjection ("mm-hmm") or a very short non-quoted segment. A gap of 3+ starts to include substantive moderator questions, suggesting the participant resumed a topic after being asked to continue.

**Threshold**: needs empirical determination. Starting hypothesis: gap of 2 (allows one intervening segment). This covers the common case of a researcher back-channel between two participant turns.

### Why both methods

- Timecodes are more semantically precise — temporal distance directly measures conversational continuity
- Ordinals are more universally available — they work for every source format, including those with no timing data
- For timecoded sources, the two methods provide cross-validation: a sequence detected by both is high-confidence
- For non-timecoded sources, ordinals are the only option

The frontend should use timecodes when available (quote `start_timecode` > 0), falling back to segment ordinals when timecodes are absent or unreliable.

---

## Empirical threshold determination

The right thresholds depend on interview style, and style varies:

- **Moderated usability testing**: short turns, frequent moderator prompts, gaps are brief. Tight thresholds work.
- **Semi-structured depth interviews**: long participant monologues, reflective pauses, researcher asks follow-ups. Wider thresholds needed.
- **Focus groups / co-discovery**: multiple participants, cross-talk, moderator managing turn-taking. Sequence detection is less applicable.
- **Asynchronous / written responses**: no temporal flow at all. Ordinals still provide document order.

Rather than guessing, we analysed real pipeline output using `experiments/segment_proximity_analysis.py`. Results from the IKEA usability study (52 quotes, 35 consecutive pairs):

```
Threshold   Pairs within   % of pairs
    5s          18           51.4%
   10s          25           71.4%
   15s          27           77.1%
   20s          27           77.1%
   30s          28           80.0%
   45s          30           85.7%
```

The distribution plateaus at 15–20s (both 77.1%) — a natural break between "same conversational flow" and "returned to topic later." Most sub-5s gaps are 0.0s (coarse VTT timecodes where adjacent segments share the same second).

**Default threshold: 17.5s** (`SEQUENCE_GAP_SECONDS` in `bristlenose/analysis/models.py`). Splits the 15–20s plateau. May need adjustment for depth interviews (longer pauses) or rapid usability tests (tighter gaps). Eventually configurable per-project.

---

## Data model: `segment_index`

A 0-based integer ordinal assigned to each transcript segment at the merge stage (Stage 6), carried through quotes to the frontend.

### Assignment

In `merge_transcript.py`, after segments are sorted by `start_time` and merged for same-speaker adjacency:

```python
for i, seg in enumerate(merged):
    seg.segment_index = i
```

This is the canonical assignment point. The merge stage produces the final segment ordering that the rest of the pipeline sees.

### Resolution (quote → segment)

In `quote_extraction.py`, after the LLM returns quotes with timecodes, each quote is matched back to its source segment:

- For timecoded transcripts: find the segment whose time range contains the quote's `start_timecode`
- For non-timecoded transcripts (all `start_time == 0.0`): return `-1` (timecode matching impossible; ordinal available through other paths)

### Data flow

```
TranscriptSegment.segment_index (assigned at merge)
    → ExtractedQuote.segment_index (resolved at extraction)
        → intermediate JSON (Pydantic serialization, automatic)
            → SignalQuote.segment_index (analysis computation)
            → baked BRISTLENOSE_ANALYSIS JSON (render_html.py)
            → Quote ORM row (server importer)
                → API responses (quotes, analysis, transcript endpoints)
                    → frontend TypeScript types
                        → run detection algorithm (future)
                            → visual grouping (future)
```

### Backward compatibility

Default value is `-1` throughout (Pydantic defaults, SQLite column defaults, TypeScript fallbacks). Old data from previous pipeline runs works unchanged — `-1` means "unknown, no run detection possible for this quote."

---

## Future: visual treatment

Out of scope for the initial `segment_index` plumbing, but the intended direction:

Within a signal card or quote group, quotes that form a detected run should be visually connected — perhaps a continuous left border, reduced vertical spacing, or a subtle "sequence" indicator. The reader should perceive them as chapters of the same story rather than independent observations.

The run detection algorithm will live in the frontend (it's a view concern, not a data concern) and will use both proximity methods with configurable thresholds.

---

## Related

- `docs/design-research-methodology.md` — analytical decisions, quote extraction rationale
- `docs/design-analysis-future.md` — analysis page roadmap
- `bristlenose/analysis/` — signal concentration computation
- `bristlenose/stages/quote_extraction.py` — where quotes are born from transcript segments
