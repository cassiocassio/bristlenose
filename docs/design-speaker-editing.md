# Design: Speaker Editing

## Problem

The pipeline's speaker identification (Stage 5b) makes mistakes. Names are guessed from context, roles are inferred from heuristics, and segment-to-speaker assignment can be wrong — especially when LLM splitting handles raw audio with no platform diarization. Researchers notice these errors immediately when reading transcripts and need to fix them in place.

Four distinct operations:

1. **Name a speaker**: "p1 is Joe Bloggs" — assign a human name to a speaker code
2. **Reassign speech**: "this segment is p2, not p1" — fix a misidentified speaker boundary
3. **Split a segment**: "this is actually two people talking, break it here" — a long segment that merged two speakers' speech needs splitting at the cursor, then the new second segment gets reassigned to the correct speaker
4. **Merge segments**: "these are actually one continuous thought" — join two or more adjacent segments into one, typically after deleting an interviewer interjection ("mm-hmm", "right") that falsely broke a participant's train of thought

Split (3) and merge (4) are inverses. Together with reassign (2), they give the researcher full control over speaker boundaries. All must be available on transcript pages.

## Prior art: Dovetail

Dovetail treats the transcript as a flowing document — like a word processor with speaker labels. You edit it organically: type to correct text, Enter to split, Backspace to join, click a speaker label to reassign. Speaker boundaries are invisible implementation details, not UI concepts. The researcher never thinks about "segments" — they think about text with speaker attribution.

Speaker corrections are incremental — researchers fix things as they notice them, not in a batch review step. This is the right pattern: fix in context, not up front.

**Design goal for Bristlenose:** the transcript page should feel like a word doc in transcription mode. The four operations (name, reassign, split, merge) should be as natural as editing text, not "segment management."

**Key principle:** the transcript is continuous flowing text. Segments are a pipeline artefact, not a user concept. The *units of meaning* are quotes — created when the researcher tags or highlights a passage, often selecting across multiple segments and speaker turns. A key insight might start in one participant segment, span an interviewer's "mm-hmm", and finish in the next segment. Speaker attribution and segment boundaries exist to get the raw text right; tagging is where analysis begins. See also [design-transcript-editing.md](design-transcript-editing.md) for the complementary text correction and section exclusion operations.

## Page responsibilities

The two main pages serve different stages of the researcher's workflow:

**Transcript page — the source.** Continuous flowing text. The researcher reads the conversation, sees what the pipeline identified as quotes (inline highlighting), and fixes what it got wrong: speaker attribution (split, merge, reassign, name), junk sections (strike/exclude), transcription errors (text correction). The unit of interaction is arbitrary text selection within a flowing document.

**Quotes page — the extracts.** Atomic quote cards. The researcher trims quotes into sharp, usable evidence, tags them, stars the important ones, hides the noise, reorders within themes. The unit of interaction is the quote card. Surrounding transcript context is shown as a convenience (preceding and following paragraphs) so the researcher can read the quote in context without switching pages.

The pipeline's job is to get from the first to the second — turn flowing text into useful atomic parts. The researcher corrects both layers: the transcript where attribution or text is wrong, and the quotes where extraction or trimming is wrong.

## What exists today

| Capability | Status |
|-----------|--------|
| Name a speaker (full/short name) | API exists (`PUT /people`), write-through to `people.yaml`. No UI |
| Change speaker role | Data model supports it (`SessionSpeaker.speaker_role` is mutable). No endpoint, no UI |
| Reassign segment to different speaker | `TranscriptSegment.speaker_code` is mutable in the DB. No endpoint, no UI. **Quote cascade is unsolved** |
| Editable speaker summary on project page | Not implemented. `SessionsTable` shows speakers read-only |
| Merge two speakers (cross-session identity) | Not implemented. `person_links` table noted as future work in code comments |

## Design

### Operation 1: Name and edit speakers

**Where it lives:** Project page, Sessions tab — an editable speaker summary table.

Columns: speaker code (`p1`), short name, full name, role (dropdown: researcher / participant / observer), session, word count.

All fields editable inline. Changes save via the existing `PUT /people` API (names) and a new role endpoint.

This is also a useful reference — the researcher can see at a glance what the pipeline detected and whether it looks right, without it being a gate or a "confirm AI results" modal.

**API changes needed:**
- `PUT /projects/{id}/people` already handles names
- New: role update on `SessionSpeaker` (or extend the existing PUT to accept role)

**Frontend:**
- Enhance `SessionsTable.tsx` with inline editing (same pattern as quote inline editing in the report)

### Operation 2: Reassign speech

**Where it lives:** Transcript page segments, and potentially quote cards.

Interaction: click/tap a speaker code badge on a segment → dropdown of available speakers for that session → select → segment reassigned.

For consecutive misidentified segments (common when the LLM gets a boundary wrong), support shift-click range selection → reassign all selected.

**API:**
- New: `PATCH /projects/{id}/sessions/{sid}/segments` — accepts a list of `{segment_id, speaker_code}` pairs (batch, not one-at-a-time)

**Data model implications:**

The hard part is **quote cascade**. When a segment moves from p1 to p2:

- `Quote.participant_id` currently stores the speaker code at extraction time
- Quotes don't have a direct FK to `TranscriptSegment` — they're linked by timecode overlap and session
- Reassigning a segment doesn't automatically update quotes that span it

Options:
- **A: Cascade via timecode overlap** — when segment speaker changes, find quotes whose timecode range overlaps, update their `participant_id` if all constituent segments now belong to the new speaker
- **B: Quote-level reassign only** — don't cascade from segments. Instead, expose a speaker dropdown on quote cards too. Researcher fixes quotes independently of transcripts
- **C: Rebuild quotes on reassign** — re-run quote extraction for affected timecode ranges. Heavy, but accurate

**Recommendation:** B first (simplest, no cascade logic). Quote cards already support inline editing — adding a speaker dropdown is incremental. Segment reassignment on transcript pages is independent. The researcher fixes each where they see it.

**Stats invalidation:**
- `SessionSpeaker.words_spoken`, `pct_words`, `pct_time_speaking` become stale after reassignment
- Need a recompute step (sum words from segments grouped by speaker_code)
- Could be lazy (recompute on next API read) or eager (recompute in the PATCH handler)

### Editable speaker summary on project page

The project page should show a speakers table that's always visible and always editable — not a one-time review screen. Shows:

- All speakers across all sessions
- Pipeline-detected names (editable)
- Pipeline-detected roles (editable dropdown)
- Word count / speaking time per speaker
- Which session they belong to

This is useful even without the segment reassignment feature. It gives the researcher a single place to see "what did the pipeline think?" and correct names/roles.

### Operation 3: Split a segment (inverse of merge)

**Where it lives:** Transcript page.

Interaction: click into a segment's text → position cursor at the speaker boundary → press Enter (or a split button) → segment splits into two at that point. The new second segment inherits the original speaker but is immediately available for reassignment (Operation 2).

This is the fix for the most common diarization failure: two speakers merged into one block because the boundary wasn't detected. The researcher sees "Brian says welcome, Daniel says thanks" all in one paragraph and should be able to split and reassign in two actions.

**API:**
- New: `POST /projects/{id}/sessions/{sid}/segments/{seg_id}/split` — accepts `{char_offset}` (or word boundary offset). Returns the two new segments
- The split must also divide the `words_json` timing data at the correct word boundary (word-level timestamps make this precise)

**Data model implications:**
- New segment gets a new `segment_id` and `segment_index` (inserted between existing indices — use fractional ordering or reindex)
- `start_time`/`end_time` derived from word timestamps at the split point
- Quotes that span the split point may need updating (timecode range now covers two segments)

**Complementary to reassignment:** split first, then reassign the new segment. These two operations compose naturally — the UX should make the flow seamless (split → the new segment's speaker badge is immediately highlighted/editable).

### Operation 4: Merge segments (inverse of split)

**Where it lives:** Transcript page.

Interaction: select two or more adjacent segments → merge (keyboard shortcut, button, or Backspace at the start of a segment to join with the previous one). Text concatenates, timing spans the full range.

Common pattern: participant is mid-thought, interviewer interjects "mm-hmm" or "right", diarization creates three segments. The researcher deletes the interjection segment, then merges the two halves of the participant's thought back together.

**API:**
- New: `POST /projects/{id}/sessions/{sid}/segments/merge` — accepts `{segment_ids: [id1, id2, ...]}` (must be adjacent). Returns the merged segment
- Or: `DELETE /projects/{id}/sessions/{sid}/segments/{seg_id}` for removing interjection segments, then merge the neighbours

**Data model implications:**
- Merged segment gets the first segment's `speaker_code` (or the researcher reassigns after)
- `start_time` = earliest, `end_time` = latest
- `words_json` arrays concatenate
- `segment_index` of deleted segments freed up (reindex or gap)
- Quotes that referenced the deleted interjection segment: orphaned (acceptable — they were probably interviewer speech and shouldn't have been quotes)

**Delete + merge flow:** Deleting an interjection and merging the surrounding segments is a two-step operation that should feel like one. The UX could offer "delete and merge with neighbours" as a single action when deleting a segment that sits between two same-speaker segments.

## Sequence

These don't all need to ship together. Each phase is independently useful:

1. **Editable speaker summary on project page** — uses existing `PUT /people` API, add role endpoint, enhance `SessionsTable` with inline editing. Low risk, high value
2. **Speaker dropdown on quote cards** — add speaker_code to quote update API. Independent of transcript segment work. Fixes the "this quote is attributed to the wrong person" case
3. **Segment reassignment on transcript pages** — new PATCH endpoint, batch segment update, stats recompute. The "fix the boundary" case
4. **Segment splitting on transcript pages** — new POST endpoint, word-boundary split, timing data division. Composes with reassignment (step 3)
5. **Segment merging on transcript pages** — new POST endpoint, text + timing concatenation. Inverse of step 4. Composes with delete for interjection removal
6. **Cross-session speaker merge** — `person_links` table, merge UI. "These two p1s in different sessions are the same person"

## Files involved

| File | Phase | Change |
|------|-------|--------|
| `bristlenose/server/routes/data.py` | 1 | Extend PUT /people to accept role, or new role endpoint |
| `frontend/src/islands/SessionsTable.tsx` | 1 | Inline editing for names, roles |
| `bristlenose/server/routes/transcript.py` | 3, 4, 5 | New PATCH for reassignment, new POST for split, new POST for merge |
| `bristlenose/server/routes/data.py` | 2 | Extend quote update to accept speaker_code |
| `frontend/src/islands/TranscriptPage.tsx` | 3, 4 | Speaker dropdown per segment, split-on-Enter interaction |
| `frontend/src/components/QuoteCard.tsx` | 2 | Speaker dropdown on quotes |
| `bristlenose/server/models.py` | 3, 4 | Stats recompute helper, segment split logic |

## Open questions

- Should segment reassignment trigger a re-run of downstream stages (quote extraction, clustering) for affected segments? Or is manual quote reassignment sufficient?
- How does this interact with pipeline re-runs? If the user fixes speakers in serve mode, then re-runs the pipeline, the pipeline's Stage 5b will overwrite their corrections. The `people.yaml` write-through preserves names but not segment assignments. Need a "user override" flag or a way to lock segments
- Range selection UX for consecutive misidentified segments — shift-click? Drag? Select-all-by-speaker-in-range?
- Segment splitting: should Enter split at cursor (natural text editing) or should there be an explicit split button (safer, less accidental)?
- Split + reassign flow: should the new segment auto-open a speaker picker, or wait for the researcher to click?
- What happens to quotes that span a split point? Timecode range now covers two segments with potentially different speakers
- Merge: should Backspace at start of segment auto-merge with previous (text-editor feel), or require explicit action (safer)?
- Delete + merge as single action: when deleting a segment between two same-speaker segments, offer "delete and merge neighbours"?
- Undo: all four operations should be reversible. What's the undo model — per-operation undo stack, or broader session-level undo?
