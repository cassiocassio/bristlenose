# Work Breakdown: Transcript & Speaker Editing

## Context

The pipeline makes mistakes — wrong speaker boundaries, wrong names, wrong roles, missed quotes, merged segments. Researchers notice these immediately when reading transcripts and need to fix them in place. This work breakdown captures everything needed to go from "pipeline output is read-only" to "researcher can correct and curate at every layer."

Two pages, two modes of work:

- **Transcript page** — the source. Continuous flowing text. Fix attribution, see what the pipeline found, correct the raw material
- **Quotes page** — the extracts. Atomic quote cards. Trim, tag, curate evidence for sharing

The pipeline gets from the first to the second. The researcher corrects both layers.

### Page responsibilities

**Transcript page — the source.** Continuous flowing text. The researcher reads the conversation, sees what the pipeline identified as quotes (inline highlighting), and fixes what it got wrong: speaker attribution (split, merge, reassign, name), junk sections (strike/exclude), transcription errors (text correction). The unit of interaction is arbitrary text selection within a flowing document.

**Quotes page — the extracts.** Atomic quote cards. The researcher trims quotes into sharp, usable evidence, tags them, stars the important ones, hides the noise, reorders within themes. The unit of interaction is the quote card. Surrounding transcript context is shown as a convenience (preceding and following paragraphs) so the researcher can read the quote in context without switching pages.

The transcript is continuous text. Segments are a pipeline artefact, not a user concept. The *units of meaning* are quotes — created when the researcher tags or highlights a passage, often selecting across multiple segments and speaker turns. A key insight might start in one participant segment, span an interviewer's "mm-hmm", and finish in the next segment. Speaker attribution and segment boundaries exist to get the raw text right; tagging is where analysis begins.

## Work Breakdown

### Layer 0: Pipeline speaker improvements (done)

LLM splitting pre-pass for single-speaker transcripts, generalised heuristic (word asymmetry, broader phrases), format-agnostic LLM prompt.

- [design-speaker-splitting.md](design-speaker-splitting.md) — LLM splitting for single-speaker transcripts
- [design-speaker-role-detection.md](design-speaker-role-detection.md) — generalised role detection

---

### Layer 1: Show the pipeline's work on transcript pages

Make the pipeline's quote extraction visible in context. The mechanism is built end-to-end but switched off.

**1a. Re-enable `<mark class="bn-cited">` CSS**
- One-line change in `bristlenose/theme/css/organisms/transcript.css` — set `background` to `var(--bn-colour-cited-bg)` instead of `transparent`
- Token already exists in `bristlenose/theme/css/tokens.css` (`#fef9c3` light / `#3b2f05` dark)
- Only works for segments without word-level timing (see 1b)

**1b. Reconcile word-level segments with quote marks**
- When `seg.words` exists (the common Whisper path), `TranscriptPage.tsx` renders individual `<span class="transcript-word">` elements and skips `html_text` entirely
- Need to map quote `verbatim_excerpt` ranges onto word spans so highlighting works in the word-level path too
- This is the real work — 1a without 1b only helps non-Whisper transcripts

**1c. Interaction on highlighted passages**
- Hover: show which quote this became (section, tags, sentiment)
- Click: jump to the quote on the quotes page
- Builds on the existing `data-quote-id` attributes on `<mark>` elements

**Files:** `transcript.css`, `TranscriptPage.tsx`, `transcript.py` (API already provides `quote_ids`, `html_text`, `annotations`)

---

### Layer 2: Editable speaker summary on project page

The project page shows all speakers across sessions — always visible, always editable. Not a gate or confirmation modal.

**2a. Inline name editing on SessionsTable**
- API exists: `PUT /projects/{id}/people` handles `full_name`, `short_name`
- Write-through to `people.yaml` already implemented
- Need: inline editing UI on `SessionsTable.tsx` (same pattern as quote inline editing)

**2b. Role dropdown on SessionsTable**
- `SessionSpeaker.speaker_role` is mutable in the DB
- Need: extend `PUT /people` to accept `role`, or new endpoint
- Dropdown: researcher / participant / observer

**Files:** `frontend/src/islands/SessionsTable.tsx`, `bristlenose/server/routes/data.py`

---

### Layer 3: Speaker reassignment on transcript page

Fix "this segment is p2, not p1" — the core Dovetail-style correction.

**3a. Speaker badge dropdown per segment**
- Click speaker code badge on a segment → dropdown of available speakers for that session
- Select → segment reassigned

**3b. Batch PATCH endpoint**
- `PATCH /projects/{id}/sessions/{sid}/segments` — accepts `[{segment_id, speaker_code}]`
- Validates target speaker_code exists in SessionSpeaker for that session
- Shift-click range selection for consecutive misidentified segments

**3c. Stats recompute**
- `SessionSpeaker.words_spoken`, `pct_words`, `pct_time_speaking` become stale
- Recompute in the PATCH handler (sum words from segments grouped by speaker_code)

**Files:** `TranscriptPage.tsx`, `bristlenose/server/routes/transcript.py`, `bristlenose/server/models.py`

- [design-speaker-editing.md](design-speaker-editing.md) — full design

---

### Layer 4: Speaker dropdown on quote cards

Fix "this quote is attributed to the wrong person" without touching the transcript.

**4a. Extend quote update API** — add `speaker_code` / `participant_id` to the quote PATCH endpoint
**4b. Speaker dropdown on QuoteCard** — small dropdown on the quote card, same speaker list as the session

**Files:** `QuoteCard.tsx`, `bristlenose/server/routes/data.py`

---

### Layer 5: Segment split

"This is actually two people talking, break it here."

**5a. Split endpoint**
- `POST /projects/{id}/sessions/{sid}/segments/{seg_id}/split`
- Accepts `{char_offset}` (or word boundary index)
- Divides `words_json` at the correct word boundary
- Returns two new segments with correct `start_time`/`end_time`

**5b. Split interaction**
- Cursor in segment text → split action (button or keyboard shortcut)
- New second segment's speaker badge immediately editable (composes with Layer 3)

**5c. Segment index management**
- Inserted segment needs an index between existing ones
- Fractional ordering (e.g. 5.5 between 5 and 6) or reindex

**Files:** `TranscriptPage.tsx`, `bristlenose/server/routes/transcript.py`, `bristlenose/server/models.py`

- [design-speaker-editing.md](design-speaker-editing.md) — Operation 3

---

### Layer 6: Segment merge

Inverse of split. "These are actually one continuous thought."

**6a. Merge endpoint**
- `POST /projects/{id}/sessions/{sid}/segments/merge`
- Accepts `{segment_ids: [id1, id2, ...]}` (must be adjacent)
- Concatenates text + `words_json`, spans timecodes

**6b. Delete interjection + merge as single action**
- When deleting a segment between two same-speaker segments, offer "delete and merge neighbours"
- Common pattern: participant thought interrupted by interviewer "mm-hmm"

**6c. Merge interaction**
- Backspace at segment start, or select multiple + merge button
- Should feel like joining paragraphs in a word processor

**Files:** `TranscriptPage.tsx`, `bristlenose/server/routes/transcript.py`

- [design-speaker-editing.md](design-speaker-editing.md) — Operation 4

---

### Layer 7: Section strike/exclude

Mark junk sections (warm-up, closing pleasantries, interruptions) as excluded. Strikethrough, not delete.

**7a. Strike UI** — select segments → strike. Visual: strikethrough + dimmed. Toggle to restore
**7b. `is_excluded` on segments** — `TranscriptSegmentEdit` table or boolean on segment
**7c. Pipeline respects exclusions on re-run** — excluded segments omitted from analysis

**Files:** `TranscriptPage.tsx`, `bristlenose/server/models.py`, pipeline stages

- [design-transcript-editing.md](design-transcript-editing.md) — Operation 1 (Section strike/exclude)

---

### Layer 8: Text correction

Fix transcription errors (misheard words, brand names, acronyms).

**8a. Contenteditable on segment text** — click to edit, blur to commit
**8b. `TranscriptSegmentEdit` table** — stores corrections, preserves original. Follows `QuoteEdit` pattern
**8c. Pipeline uses edited text on re-run** — corrected brand names flow through to quote extraction

**Files:** `TranscriptPage.tsx`, `bristlenose/server/models.py`, `bristlenose/server/routes/transcript.py`

- [design-transcript-editing.md](design-transcript-editing.md) — Operation 2 (Text correction), data model sketch, edit history question

---

### Layer 9: User corrections survive pipeline re-run

Without this, re-running the pipeline overwrites everything the researcher fixed.

**9a. Speaker reassignments** — override flag on segments, pipeline respects it
**9b. Splits/merges** — structural changes persisted, pipeline doesn't flatten back
**9c. Text corrections and exclusions** — pipeline reads edited text, skips excluded segments

This is the hardest layer — it requires the pipeline to be aware of the serve-mode database.

- [design-pipeline-resilience.md](design-pipeline-resilience.md) — manifest, event sourcing, incremental re-runs

---

### Layer 10: Context preview on quotes page

Show surrounding transcript around each quote card so the researcher can read the extract in context.

**10a. Preceding/following paragraphs** — a few lines of transcript above and below the quote
**10b. Speaker labels in context** — show who said what around the quote

This is a convenience, not a correction tool. The quotes page is for curating atomic parts; context helps the researcher understand what they're curating.

---

### Layer 11: Cross-session speaker identity

"These two p1s in different sessions are the same person."

**11a. `person_links` table** — map speaker codes across sessions to a single person
**11b. Merge UI** — on the project page speaker summary (Layer 2)

- [design-multi-project.md](design-multi-project.md) — person identity, single-project assumption inventory

---

## Dependencies

Most layers are soft dependencies — each is independently useful.

```
Layer 0 (done) ──→ Layer 1 (show pipeline's work)
                ──→ Layer 2 (speaker summary)
                ──→ Layer 3 (reassign) ──→ Layer 5 (split)
                                       ──→ Layer 6 (merge)
                ──→ Layer 4 (quote speaker)
                ──→ Layer 7 (strike) ──→ Layer 9 (survive re-run)
                ──→ Layer 8 (text correction) ──→ Layer 9
                ──→ Layer 10 (context preview)
                ──→ Layer 11 (cross-session identity)
```

## Suggested priority

Highest value-to-effort first:

1. **Layer 1a** — one CSS line, immediate visibility
2. **Layer 2** — API exists, just needs UI
3. **Layer 1b** — word-level quote highlighting (unlocks the full transcript-as-reading-experience)
4. **Layer 3** — speaker reassignment (fixes the problem that started this conversation)
5. **Layer 5 + 6** — split/merge (the Dovetail word-doc feel)
6. **Layer 4** — quote speaker dropdown
7. **Layer 7 + 8** — strike and text correction
8. **Layer 9** — corrections survive re-run
9. **Layer 10** — context preview
10. **Layer 11** — cross-session identity

## Related design docs

- [design-speaker-editing.md](design-speaker-editing.md) — the four transcript operations (name, reassign, split, merge), Dovetail model, data model gaps
- [design-speaker-splitting.md](design-speaker-splitting.md) — LLM splitting for single-speaker transcripts (Layer 0, done)
- [design-speaker-role-detection.md](design-speaker-role-detection.md) — generalised role detection (Layer 0, done)
- [design-transcript-editing.md](design-transcript-editing.md) — text correction, section strike/exclude, prior art analysis
- [design-pipeline-resilience.md](design-pipeline-resilience.md) — manifest, event sourcing, re-run integrity
- [design-multi-project.md](design-multi-project.md) — person identity, cross-session linking
