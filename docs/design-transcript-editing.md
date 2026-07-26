# Transcript Editing — Design Document

**Status:** Research phase. Now GA-gating (not beta) — target the GA cycle, ~2027. See [Bidirectional editing — the converged spec (26 Jul 2026)](#bidirectional-editing--the-converged-spec-26-jul-2026), which supersedes the two-operation framing below where they conflict.

**Created:** 1 Mar 2026 · **Spec section added:** 26 Jul 2026

---

## The problem

Researchers need to edit transcript text for two distinct reasons:

1. **Cleaning up junk** — deleting "is my camera on?", "sorry I need to feed the cat", "thanks for your time" sections that add no analytical value and that the AI should never try to analyse.
2. **Fixing transcription errors** — correcting misheard words, brand names, acronyms that Whisper interpreted as regular words.

These are fundamentally different from quote editing (trimming extracted quotes on the quotes page). Quote editing sharpens analytical assets. Transcript editing cleans the source material.

### Why this matters

In a researcher's workflow, the transcript is the raw material. Junk sections waste the researcher's attention and pollute downstream AI analysis (topic segmentation, quote extraction). Transcription errors make quotes unusable without manual correction. Both problems are currently unsolvable in Bristlenose — the transcript text is immutable after the pipeline runs.

### User behaviours observed

**Bulk deletion** (most common):
- "Getting to know you" intros — first 2-5 minutes
- Closing pleasantries — last 1-3 minutes
- Interruptions — "sorry my husband just came back", phone calls, tech issues
- Off-topic tangents that aren't relevant to the research

**Word-level correction** (less common but important):
- Brand names and product names ("Figma" → "FGMA", "Miro" → "mirror")
- Acronyms interpreted as words ("API" → "a pie", "UX" → "you ex")
- Names, especially non-English names
- Technical terms the model hasn't seen

**Neither of these is the same as quote trimming.** Quote trimming crops the beginning/end of an extracted quote ("what I think is that... [useful content] ...like you know"). Transcript editing modifies the source text itself.

---

## Prior art — how other tools handle this

### The fundamental tension

Every tool that edits time-aligned text faces the same problem: the text has per-word timestamps linked to audio. When you change the text, the timestamps become invalid. No tool has fully solved this.

### Five architectural approaches exist in the wild

| Approach | Tools | How it works | Tradeoffs |
|----------|-------|--------------|-----------|
| **Two-mode editing** | Descript, Reduct | Separate "correct transcript" (text only, preserves timing) from "edit composition" (modifies media). User explicitly chooses intent | Most flexible but complex UX. Requires users to understand the distinction |
| **Strikethrough / redact** | Trint, Reduct, Descript | Mark sections as excluded; playback skips them. Original text + timecodes remain intact | Elegant for removing sections. Cannot handle adding new text. Visual clutter from struck-through text |
| **Re-alignment** | Otter.ai | After editing, re-run forced alignment to reconcile modified text with original audio | Works for small corrections. Breaks on large deletions. Computationally expensive |
| **Immutable timestamps** | Rev, Grain, Dovetail | Timestamps baked in at transcription time. Editing text changes display but timing never adjusts | Simple. No sync drift for small corrections. Large structural edits break click-to-seek |
| **Timeline-coupled** | Descript (edit mode), Premiere Pro | Deleting text performs a ripple edit on the video timeline | Full video editing power. Not appropriate for research tools where the transcript is the artefact |

### Tool-by-tool details

#### Descript — the gold standard (for video editors)

Descript pioneered "edit video by editing text" and has the most sophisticated approach:

- **Correct Text mode** (`Opt+C`): Modifies transcript text without changing media. Re-analyses audio to adjust word-to-audio alignment after each correction. A dotted gray underline appears during re-alignment.
- **Normal Edit mode**: Text changes directly modify the media composition. Delete a word → audio disappears. Cut and paste → audio moves with it.
- **Ignore** (strikethrough): Non-destructively hides content. Text shows as strikethrough, audio is muted. Hover to restore or delete.
- **Restore removed media**: Right-click any edit boundary to recover deleted sections. Source media is never destroyed.
- **Patient Playback**: During playback, if you start typing corrections, audio automatically slows down and waits for you to finish, then resumes.
- **Overdub**: AI voice cloning synthesises audio for typed words that were never spoken. The only tool that handles "adding new text" to playback.
- **Word gap control**: Fine-tune silence duration between words at edit points.
- **Wordbar**: Waveform display with draggable word boundaries for manual timing adjustment.

#### Trint — strikethrough as first-class concept

- **Strike** (`Ctrl+J`): Visually redacts text with strikethrough instead of deleting. Struck-through text is skipped during playback. Timecodes remain intact.
- Trint explicitly documents: "Any extra words you add or delete will not adjust the timecode and may be skipped over during playback." Their solution is to recommend Strike instead of deletion.
- If you delete text outright, you must re-transcribe to get correct timecodes.
- Paragraph verification checkboxes track review progress.

#### Otter.ai — re-alignment approach

- Edit text directly, then "Realigning text with audio" runs automatically.
- **Explicitly warns against deleting large chunks** — the realignment algorithm can't reconcile gaps.
- Light edits (correcting a word) work well. Heavy edits (restructuring, large deletions) break alignment.

#### Dovetail — closest competitor, simplest approach

- Free-form text editing (place cursor, type).
- Find and replace (whole-word only).
- Rich formatting via `/` command palette.
- **Conspicuously silent** on what happens to timecodes when text is edited. Appears to accept timestamp drift as tolerable.
- Click-to-seek and video highlights work from VTT cue boundaries (paragraph-level, not per-word).

#### Rev — timestamps are immutable

- Text editable, but individual timestamps cannot be modified.
- Only timing adjustment: global offset (shift entire transcript by N seconds).
- EDL export maps selections to timecodes for external video editors.

#### Grain — "Correct transcript" framing

- "Correct transcript" button enters editing mode (the naming signals intent: fixing errors, not restructuring).
- Clip boundaries defined by word positions — timestamps likely preserved per-word, text changes don't alter timing map.

#### Reduct.video — clean two-mode model

- **Transcript correction**: Edit text to match what was said. Text must match audio exactly (including stammers) for alignment to work. Gray text appears when alignment fails.
- **Video editing (Reels)**: Strikethrough to remove sections. Struck-through sections skipped during playback. Non-destructive, restorable.

### Key insights from prior art

1. **No tool allows freely typed new text to participate in playback** except Descript (via AI voice synthesis). All others treat the transcript as read-only with respect to timing.

2. **Trint's Strike is the most pragmatic solution for research tools.** It acknowledges the fundamental problem is unsolvable in the general case and offers a constrained operation (hide/show) that preserves timing perfectly.

3. **Dovetail doesn't solve this rigorously.** They accept drift. For a research tool (where the transcript is a reference document, not a video edit), this is probably fine.

4. **Re-alignment (Otter) is fragile** and explicitly limited to small corrections.

5. **The "playback cursor stops during deleted sections" problem** — Descript and Trint both handle this via strikethrough/ignore: the text stays visible but playback skips it. The cursor passes through struck-through text without stopping.

6. **Original vs edited text tracking is not a first-class feature** in any of these tools. Descript has composition-level undo history. No tool shows a diff view.

---

## Quote editing vs transcript editing — two different problems

### Quote editing (existing, works well)

- **Context**: Quotes page. Quotes are extracted analytical assets — "tokens of meaning."
- **Operation**: Trim from beginning/end. Human speech has fluff ("what I think is that...") and trailing filler ("...like, you know"). Trimming sharpens quotes for pattern-matching in Miro/affinity mapping.
- **Data model**: `QuoteEdit.edited_text` replaces `Quote.text`. Revert restores original.
- **Scope**: One quote = one text area. No timing implications.
- **UI**: `useCropEdit` hook — idle → hybrid (contenteditable + bracket handles) → crop (word spans). Click to enter, Enter to commit, Escape to cancel.

### Transcript editing (proposed, different animal)

- **Context**: Transcript page. The raw interview record.
- **Operations**:
  - Delete whole sections (junk removal) — more like Trint Strike than text editing
  - Fix individual words (transcription correction) — simple contenteditable
- **Data model**: New `TranscriptSegmentEdit` table or similar. Must preserve original text for revert and for downstream quote/analysis integrity.
- **Scope**: Full transcript. Edits affect downstream analysis (topic segmentation, quote extraction) on re-run.
- **Timing**: Word-level timestamps (`words_json`) become invalid for edited regions. Playback sync degrades.

### Implications

The `useCropEdit` hook (designed for quote trimming) is not the right tool for transcript editing. Transcript editing needs:
- **Contenteditable on full segment text** (not just a marked substring)
- **Section deletion / strikethrough** (not end-trimming)
- **No crop handles** (you're not trimming a quote, you're rewriting text)

These are different interactions requiring different components.

---

## The quote-editing-on-transcripts question (initial investigation)

Before arriving at the transcript editing problem above, we investigated bringing the existing quote crop/trim interaction to the transcript page. This analysis is preserved here because the findings are relevant.

### Why it's harder than it looks

1. **Editing target mismatch**: `useCropEdit` operates on a flat string. On the transcript page, the quote text is a `verbatim_excerpt` substring embedded within `segment.text`, highlighted with `<mark>`. The editable region is a portion of a larger immutable text.

2. **Multi-segment quotes**: A quote spanning t=10 to t=39 appears as `<mark>` highlights in three separate segments. Crop boundaries in the combined text don't map to segment boundaries.

3. **`verbatim_excerpt` vs `text` vs `edited_text`**: Three-way mismatch between what the transcript shows (verbatim excerpt), what the quotes page shows (LLM-cleaned text), and what the user modifies (edited text).

4. **Word-level timing conflict**: When `words` data exists, `html_text` (with `<mark>`) is already skipped. Editing would stack on top of an already-unreconciled system.

5. **State synchronization**: QuotesStore (quotes page) and TranscriptPage local state are independent. No mechanism exists to sync edits between them.

### Conclusion

Direct inline quote editing within transcript `<mark>` tags is architecturally incompatible with the current codebase. If quote editing on transcripts is needed, a **popover panel** (floating UI anchored to the `<mark>`, containing the full quote text with `useCropEdit`) is the most viable approach. But this is a separate feature from transcript text editing.

---

## Proposed approach for transcript editing

Based on prior art analysis and the two-behaviour model (junk deletion + word correction):

### Two operations, not one

#### Operation 1: Section strike / exclude

Inspired by Trint's Strike feature. Select one or more segments → mark as excluded. Visual: strikethrough + dimmed. Playback: skips excluded sections (cursor jumps). Pipeline: excluded segments are omitted from re-analysis.

**Data model**: `TranscriptSegmentExclusion` table (session_id, segment_index range, excluded_at). Or a simpler boolean `is_excluded` on each segment edit record.

**UX**: Select segments (click first, shift-click last, or click + drag). Strike button in toolbar or keyboard shortcut. Toggle — click again to restore. Count indicator: "12 segments excluded (4m 30s removed)".

**Why strikethrough, not delete**: Original text remains visible (audit trail). Timestamps stay intact. Playback skips gracefully. Researcher can restore any time. Re-run pipeline knows to skip these sections.

#### Operation 2: Text correction

Simple contenteditable on individual segment text. Click to edit, type correction, blur to commit. No crop handles, no bracket UI — just a text editor.

**Data model**: `TranscriptSegmentEdit` table (session_id, segment_index, edited_text, edited_at). Original text preserved in `TranscriptSegment.text`.

**UX**: Click segment text to enter edit mode. Yellow background (same as quote editing — consistent "you're editing" signal). Type freely. Enter/blur commits. Escape cancels. Small undo icon on edited segments.

**Timing**: Word-level timestamps (`words_json`) are not updated. Playback cursor position degrades for edited segments but remains correct for surrounding segments. This matches Dovetail's approach (accept drift, it's fine for research).

### What about playback sync?

During playback of an edited transcript:

- **Excluded segments**: Playback skips. Cursor jumps from end of segment N to start of segment N+3 (if N+1 and N+2 are excluded). The struck-through text stays visible but dimmed.
- **Corrected segments**: Playback uses original word timing. The corrected text is displayed but the "you are here" highlight tracks original timing. Small drift is acceptable — the researcher knows they changed the text.
- **Unedited segments**: Normal behaviour. No change.

This matches Dovetail's observed behaviour ("the indicator just stays still as the video plays over the bits you have deleted... doesn't try and match... just kind of stops and then jumps and catches up").

### Effect on downstream analysis

If the researcher re-runs the pipeline after transcript editing:

- **Excluded segments**: Omitted from topic segmentation and quote extraction. This is the primary value — preventing junk from polluting analysis.
- **Corrected segments**: The pipeline should use `edited_text` (if available) instead of original `text` for analysis. This ensures corrected brand names / acronyms flow through correctly.

This requires pipeline awareness of segment edits — a future pipeline enhancement.

---

## Data model sketch

### New ORM table

```python
class TranscriptSegmentEdit(Base):
    __tablename__ = "transcript_segment_edits"

    id: int (PK)
    session_id: int (FK -> sessions.id)
    segment_index: int              # Stable key within session
    edited_text: str | None         # None = no text change (may be excluded only)
    is_excluded: bool = False       # Strike/exclude flag
    edited_at: datetime

    __table_args__ = (
        UniqueConstraint("session_id", "segment_index"),
    )
```

### API endpoints

```
GET  /api/projects/{id}/segment-edits          → {edits: Record<string, SegmentEdit>}
PUT  /api/projects/{id}/segment-edits           → upsert edits
```

Key format: `"s1-0"`, `"s1-1"` (session_id + segment_index, matching quote DOM ID pattern `"q-p1-123"`).

### Transcript API changes

Add to `TranscriptSegmentResponse`:
```typescript
edited_text: string | null;   // Researcher correction (null = original)
is_excluded: boolean;          // Strike/exclude flag
```

---

## Edit history question

> Do we need an infinite history stack for user actions?

### What the prior art does

- **Descript**: Composition-level undo/redo history. All editing is non-destructive against source files.
- **Everyone else**: Session-level undo at most. No persistent history.

### What Bristlenose needs (recommendation)

**Not an infinite history stack.** The existing pattern (original + current edit, with revert-to-original) is sufficient for the MVP:

- `TranscriptSegment.text` = original (immutable, from pipeline)
- `TranscriptSegmentEdit.edited_text` = current correction (overwritten on each edit)
- Revert = delete the `TranscriptSegmentEdit` row

This matches the quote editing pattern (`Quote.text` + `QuoteEdit.edited_text`).

**Why not full history**: Researchers edit transcripts to clean them up, not to explore alternatives. They don't need to undo-redo through a sequence of corrections. They need "what was the original?" (always available) and "what did I change it to?" (current edit). The pipeline manifest already tracks provenance (which pipeline stage produced what data, when).

**If history is needed later**: The `TranscriptSegmentEdit` table could gain a `version` column and keep all rows instead of upserting. But this adds complexity (which version to display, storage growth) without clear user value today.

### Word-level provenance

Each word already has provenance via its existence (or absence) in `words_json`:
- Words in `words_json` = original Whisper output with timing
- Words in `edited_text` but not in `words_json` = researcher additions (no timing)
- Words in `words_json` but not in `edited_text` = researcher deletions

This implicit provenance is sufficient. No need to track per-word edit history.

---

## Scope and complexity estimate

| Component | Effort | Notes |
|-----------|--------|-------|
| `TranscriptSegmentEdit` ORM + migration | Small | ~30 lines, follows `QuoteEdit` pattern |
| Segment edit API endpoints | Small | ~60 lines, follows existing data API pattern |
| Transcript API response changes | Small | ~20 lines, add fields to response model |
| Frontend: text correction (contenteditable on segments) | Medium | ~200 lines, simpler than `useCropEdit` |
| Frontend: section exclusion (strike UI + toggle) | Medium | ~200 lines, selection + strikethrough CSS |
| Frontend: state management (segment edit store) | Small | ~50 lines, follows QuotesStore pattern |
| Frontend: playback integration (skip excluded segments) | Medium | ~100 lines, modify `PlayerContext.tsx` |
| Pipeline: respect edits on re-run | Large | Needs design — how does pipeline read edits from DB? |
| Tests | Medium | ~150 lines across Python + Vitest |
| **Total** | **Large feature** | ~800-1000 lines new code |

---

## Open questions

1. **Pipeline integration**: How does the CLI pipeline (which reads files, not a database) access segment edits for re-analysis? Options: (a) export edits to a JSON file that the pipeline reads, (b) pipeline queries the SQLite DB directly, (c) edits only apply in serve mode and re-analysis is a serve-mode-only operation.

2. **Re-analysis trigger**: After editing transcripts, should the researcher manually trigger re-analysis? Or should it happen automatically? Automatic is complex (incremental re-run of stages 8-11 for affected sessions only).

3. **Quote invalidation**: If a segment is excluded and it contains a quoted region, what happens to the quote? Options: (a) quote is auto-hidden, (b) quote is flagged with a warning, (c) nothing — the quote persists independently.

4. **Export**: Should exported transcripts (markdown, CSV) include original text, edited text, or both? Should excluded sections be omitted or marked?

5. **Reconciliation with word-level timing**: Should we attempt to update `words_json` after text corrections (forced re-alignment), or accept drift? Prior art suggests accepting drift is fine for research tools.

6. **Multi-select for exclusion**: Can the researcher exclude a contiguous range of segments in one action? Or one segment at a time? Range selection is more natural for "delete the first 3 minutes" but requires UI for range selection.

---

## Bidirectional editing — the converged spec (26 Jul 2026)

The 2026-03 draft above frames transcript editing as two operations (junk-strike + word-correction), with timing drift accepted à la Dovetail. A later design conversation — grounded in a full read of the quote↔transcript data model — widened this into a coherent spec for treating the transcript as a **live-editable document**: the "this is *my* document, I fix it" model users arrive with, and are right to. This section supersedes the two-operation framing where they conflict; the prior-art table and playback notes still stand.

### Why this is GA-gating, not optional

Transcription is *not* a solved problem in high-stakes domains. In technical medical conversations, ASR is wrong constantly — drug names, dosages, anatomy, and worst of all **negation**, where a single dropped "no" inverts a life-threatening clinical fact. A transcript in that state **cannot be shared with colleagues**, so the ability to correct it is a *duty of the product*, not a nicety. Two hard requirements follow:

1. **Correction must be frictionless** — it is high-volume (many per transcript), not an occasional touch-up.
2. **The original must stay recoverable underneath** — medico-legally, "what was captured vs what the researcher corrected" is a producible record.

Target: the **GA cycle (~2027)**. External-beta users tolerate its absence; a GA "this is my document" product cannot. This is Beta-must / GA-gating, not a "Could." Tracked in the maintainer's private planning notes — it subsumes the narrow "Edit writeback to transcript files" (#21) Could-item there, which is one sub-concern of it (persisting edits beyond the DB to source files).

### This overlaps machinery that already shipped — fold-in, don't rebuild

The provenance model this needs is **already the grain of the codebase** (v0.20.0 curation persistence, shipped 11 Jul 2026):

- **Immutable base + editable overlay + durable identity already exist.** Editing a quote today never mutates it — it writes a separate `QuoteEdit.edited_text` override and mints a `durable_id` + `frozen_form` (a stable, human-owned identity flagged as a re-identification key, excluded from export). See `docs/design-curation-persistence.md`, `docs/design-curation-persistence-plan.md`. The transcript side simply hasn't been given the same treatment yet — the 2026-03 `TranscriptSegmentEdit` sketch above is the mirror of `QuoteEdit`.
- **Redaction is already one-way upstream.** `PiiCleanTranscript` is a separate object; quotes are extracted *after* redaction (`s07_pii_removal.py`), so "original recoverable underneath" is an existing pattern, not a new imposition.
- **The keystone anchor is already a Beta-gate — for a different reason.** The shipped incremental-analysis work (v0.20.0, 11 Jul 2026) leaves the *unpinned-quote tail* (~4/43 quotes the model omits on re-extraction) needing **"a sturdier anchor (segment_index / char-span)"**, marked **BLOCKING-before-Beta**. That char-span anchor **is** the word-range anchor this spec needs (see below). One primitive, two payoffs: quote-survival-across-re-extraction *and* edit-survives-highlighting. Build it once. Canonical: `docs/design-incremental-analysis.md`.
- **Merge / split / reassign of segments** overlaps the speaker-editing surface — `docs/design-speaker-editing.md`, `docs/design-transcript-speaker-editing-roadmap.md`. The vocabulary below should share those interactions, not fork them.

### The coupling reality (why it's hard) — from the data model

There is **no shared string** to bind. A quote is a *detached copy* with weak back-pointers (`bristlenose/models.py:266`, `bristlenose/server/models.py:310`):

- `text` — the quote's own copy, *with editorial cleanup applied* (so often **not even a substring** of the segment).
- `verbatim_excerpt` — the raw substring, but it **defaults to `""`** and is backward-compat-fragile.
- `start_timecode`/`end_timecode` — floats; the **only hard link to media**.
- `segment_index` — a **single loose ordinal** (`-1` common), **not an FK**, and it cannot represent a multi-segment quote.
- **No character offset, no word-index range.**

Runtime matching is recomputed every request in `bristlenose/server/routes/transcript.py`: segment↔quote by **timecode-range + `speaker_code`** (`:341-348`), in-segment offset by **case-insensitive `str.find()` of `verbatim_excerpt`** (`:116-166`), with a **whole-segment `<mark>` fallback** when the substring doesn't match. Consequences that already ship today:

- **Editing a quote already desyncs the highlight** — the `QuoteEdit` override no longer substring-matches its segment, so highlighting silently falls back to marking the whole segment.
- **The common Whisper (word-level) path skips citation highlighting entirely** — `TranscriptPage.tsx` renders per-word spans and drops the `<mark>` reconciliation ("a future enhancement").
- **Redaction clears word timings** (`clean_seg.words = []`, `s07_pii_removal.py:193`), so a redacted session has no word-level anchor at all.

### The keystone: a persisted word-range anchor

Replace the recomputed substring match with a **persisted (session, word-start-index, word-end-index) anchor** binding each quote to its transcript span. This is the char-span anchor already Beta-gated in incremental analysis. It pays rent immediately (independent of the full edit feature):

- Lights up citation highlighting on the Whisper path (currently skipped).
- Stops the edit-desyncs-highlight fallback.
- Gives corrections a precise place to land, and the incremental-analysis unpinned tail a sturdy identity.

Every row of the edit vocabulary below rides on this anchor. Without it, you are back to the fragile substring match that breaks the moment anyone edits.

### The edit vocabulary

Two independent axes decide safety: **time** (does it break text↔media bijection / click-to-seek / clip export?) and **analysis graph** (what happens to derived quotes, tags, sentiment, theme placement?).

| Edit | Time axis | Analysis graph |
|---|---|---|
| **Word correction** (same span) — the 99% case | Stable | Patch the quote's copy in place; no re-extraction |
| **Merge segments / drop line breaks** | Union of timecodes — safe | One node, unchanged |
| **Split into logical paragraphs** | Partition at word timing — safe | **Forks one node → two quotes** (see rule below) |
| **Editorial interpolation** `[editor: they mean X]` | Zero-width marker | **Excluded** from extraction/sentiment; attributed to who/when |
| **Deletion** → *exclude-from-share* (strike) | Struck, timecodes intact → clip stays honest | Trim/hide the derived quote |
| **Unmarked speech-looking insertion** | — | **The only thing to prevent** (see below) |

### Split forks a quote — the inheritance rule

In this domain a paragraph break *is* a quote boundary, so "break this big paragraph into its logical paragraphs" means "the extractor lumped two distinct points into one; make it two." The split point's timecode comes from the word timing at the boundary (bijection preserved). The wrinkle is the derived graph: if the passage already backed a curated quote, splitting **forks the node**, and the honest default falls out of *why* people split — the two halves say different things:

- **Sentiment: re-evaluate per half, do not copy.**
- **Tags:** copy to both, then researcher prunes.
- **`durable_id`:** stays with one half; the other mints fresh.
- **Theme/cluster membership:** copy, then researcher re-sorts.

### Editorial interpolation — generative-when-marked is safe

`[editor: X]` is a long-standing transcription convention (family of `[inaudible]`, `[crosstalk]`, `[sic]`). It is generative but *marked as non-speech*, and that marking is exactly what preserves the truth claim: it says "a human added this, the participant didn't say it." The system already half-speaks this (PII emits bracketed `[NAME]`; `speaker_role` distinguishes moderator). Requirements: **excluded from quote extraction and sentiment**, visually distinct, **attributed** (who + when — doubly important in a medical/legal record), with a **soft, invisible word-cap backstop** (tuned from real data, not a visible setting) so a transcript can't quietly become mostly editorial.

### The one thing to prevent

Not insertion — *unmarked* insertion of speech-looking text that a reader or the extractor would take as the participant's words. **Fabrication is a formatting failure, not an editing capability to withhold:** inserted non-speech must always wear the editorial bracket/styling, and then it is fine. That single rule is what lets the whole vocabulary stay honest while giving the user the document they're right to expect.

---

## References

- `docs/design-curation-persistence.md`, `docs/design-curation-persistence-plan.md` — the durable-id + frozen_form overlay this spec extends (shipped v0.20.0)
- `docs/design-incremental-analysis.md` — re-analysis machinery; names the char-span anchor (= the keystone here) as BLOCKING-before-Beta
- `docs/design-speaker-editing.md`, `docs/design-transcript-speaker-editing-roadmap.md` — segment merge/split/reassign interactions to share, not fork
- `docs/design-quote-editing.md` — existing quote editing design (useCropEdit, crop handles, three rendering modes)
- `docs/design-pipeline-resilience.md` — manifest, event sourcing, crash recovery
- `bristlenose/stages/CLAUDE.md` — pipeline stage details, output structure
- `bristlenose/server/CLAUDE.md` — serve mode architecture, API patterns
- `frontend/src/hooks/useCropEdit.ts` — crop/edit state machine hook
- `frontend/src/islands/TranscriptPage.tsx` — current transcript rendering
- `frontend/src/islands/QuoteCard.tsx` — quote editing implementation
- `bristlenose/server/routes/transcript.py` — transcript API endpoint
- `bristlenose/server/models.py` — ORM schema (TranscriptSegment, QuoteEdit)
