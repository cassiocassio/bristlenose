# Transcript Editing — Design Document

---
status: partial
last-trued: 2026-10-24
trued-against: HEAD@main on 2026-10-24
---

**Status:** Partly built — split, join, moving one paragraph to another speaker (0.35.0) and copying (8 Oct 2026); see the two "built" sections near the end. Direct editing of the words is planned, not started: the order of work and the decisions are in [Where this stands](#where-this-stands-24-oct-2026-planned) (24 Oct 2026). Now GA-gating (not beta) — target the GA cycle, ~2027. See [Bidirectional editing — the converged spec (26 Jul 2026)](#bidirectional-editing--the-converged-spec-26-jul-2026), which supersedes the two-operation framing below where they conflict.

**Created:** 1 Mar 2026 · **Spec section added:** 26 Jul 2026

---

## Where this stands (24 Oct 2026, planned)

Start planning here. This section lists what is built, what is decided, the order of work and what
is still open. Each item points to the section or doc that holds the detail. Decisions 11 to 24 and
the revision of 6 were made with the owner on 24 Oct 2026, in a planning session that wrote no
product code. Decisions 21 to 24, and the plan's corrections layer, came from playing edits through
every surface: `docs/mockups/transcript-edit-consequences.html` (Findings, and the "Play-out: 1 + 20"
tab, one correction then a study-wide replace). Building waits: the beta is a reliability phase with almost no new features (owner,
19 Oct 2026), and transcript editing is GA-gating (~2027).

**Built**
- Split and join a paragraph (6 Oct 2026), and moving one paragraph to another speaker (0.35.0).
  These are recorded as layout edits with the words they named, then replayed on every import and
  refused when the words no longer match. See [Split and join, stage 1](#split-and-join-stage-1--built-6-oct-2026).
- A refused undo of a split or join says so and stays undoable (`f25456ff`).
- Copying from the transcript in the house format (8 Oct 2026). See [Copying from the transcript](#copying-from-the-transcript--built-8-oct-2026).
- The gutter finds each quote's words in the drawn text when the page is viewed
  (`frontend/src/utils/quoteExtents.ts`, `docs/design-transcript-gutter.md`). Nothing
  is persisted, so this is **not** the keystone anchor. It shows the join can work, and where it
  fails:
  - CJK without word timings;
  - words tidied between the anchors, which gives an approximate match;
  - repeated phrases, settled by time.
- Hidden quotes are kept out of the analysis, through one shared read-side filter
  (`speaker_slots.analysis_quotes`, 22 Oct 2026). Struck text is meant to use the same filter.

**Decided**
1. **Correcting the transcript is a duty, not a nicety.** In medical work a dropped "no" inverts a
   fact. Correction must be frictionless, and the original must stay recoverable underneath
   (26 Jul 2026, [Why this is GA-gating](#why-this-is-ga-gating-not-optional)).
2. **The edit vocabulary.** Each edit is judged on two axes: time and the analysis graph.
   - Word correction is the common case.
   - Merge and split are safe on time.
   - A split forks the quote it backs. Sentiment is scored again for each half; tags and themes are
     copied to both; the `durable_id` stays with one half.
   - A bracketed `[editor: …]` note is excluded from extraction and sentiment, and says who added
     it and when.
   - The only thing prevented is *unmarked* inserted text that looks like speech.

   See [The edit vocabulary](#the-edit-vocabulary) to [The one thing to prevent](#the-one-thing-to-prevent).
   Decision 13 refines what a correction does to the analysis.
3. **The keystone is a persisted word-range anchor.** It was to be shared with incremental analysis
   ([The keystone](#the-keystone-a-persisted-word-range-anchor), `docs/design-incremental-analysis.md`).
   _24 Oct 2026:_ incremental analysis shipped by freezing curated quotes instead (v0.20.0), so the
   anchor's payoff there is now only the ~9% of quotes the model sometimes omits. The anchor is
   justified by editing.
4. **One saved edit over an immutable original, not a history stack.** Revert deletes the edit row,
   as quote editing does ([What Bristlenose needs](#what-bristlenose-needs-recommendation),
   `docs/design-undo-catalog.md`).
5. **"Inaudible" is a segment flag, not bracketed text.** Brackets are kept for the researcher's own
   insertions (13 Oct 2026).
6. **Corrections flow both ways; editorial edits stay with the quote** (revised 24 Oct 2026; was
   "quote edits win, one way", 17 Oct). The researcher thinks they are editing the same words, one
   view with the ums left in. A *correction* (words swapped in place, any length: "bee bee sea" →
   "BBC") made in the transcript changes every quote that still holds those words, edited or not.
   Made in a quote, it changes the transcript. *Editorial* quote edits (crops, removed ums, ellipses,
   tidied grammar) stay in the quote. A quiet flag in the Quotes lens appears only where a correction
   falls inside the span the quote kept but cannot find its words there, because the edit reworded
   them ("it's not fine to take with food" under "Fine to take with food, apparently"). Words the
   quote's crop left out never flag: there is nothing to contradict (owner, 24 Oct 2026; the word
   range of step 1 tells the two apart without a model). Telling a correction
   from tidying in a quote edit is step 2b's judgement. This replaces the open single-word
   carry-back question ([Quote edits win, one way](#quote-edits-win-one-way-owner-17-oct-2026)).
7. **Names, brands, places and technical terms are corrected study-wide.** The tool finds every
   candidate and shows each in context. The researcher accepts them all or goes one by one; there is
   no blind replace-all. Accepted words become the study's word list, which can later feed Whisper's
   prompt. Corrections to people and places go through the people layer (17 Oct 2026, same section).
   Decision 20 says which candidates v1 finds.
8. **The transcript is a document, not a form.** A click puts the caret in the text, with no field
   fill. Links into the lenses live on the gutter marks, the margin titles and the right-click menu
   (17 Oct 2026, [The transcript is a document](#the-transcript-is-a-document-not-a-form-owner-17-oct-2026)).
9. **Strike: the verb is Delete.** The researcher selects a passage and presses Delete; the passage
   stays on the page, struck through. It is kept out of the analysis and every export.
   - A strike is keyed on session, time range and words, and replayed like a layout edit.
   - The pipeline reads strikes from a file (16 Oct 2026, [Operation 1](#operation-1-section-strike--exclude),
     `docs/design-delete-and-bin.md`). Decision 12 changes what Re-analyse does with them.
10. **Direct editing of a paragraph's words comes next.** It connects to quote editing and its
    revert, but should be simpler (6 Oct 2026).
11. **Every transcript edit is keyed on time plus words**, the strike's key. Split, join and move
    move off position plus six words, which a re-run that adds or drops an earlier paragraph breaks
    for every later edit. Time plus words survives that shift and refuses an ambiguous match.
12. **Re-analyse keeps nothing, transcript edits and strikes included.** It is the begin-again
    action, used rarely, and not keeping things is the feature. Analyse and incremental analysis
    always respect earlier work, so "strike, then Analyse" is how struck text leaves the themes.
    This supersedes `design-delete-and-bin.md`'s "Strikes must survive" (`docs/design-analysis-lifecycle.md`;
    commits `33a6e01c`, `e8aa29ff`).
13. **What an edit sets moving depends on what kind of edit it is.**
    - Striking a whole quote works like hiding it.
    - A partial strike leaves part of the text. At the next Analyse that part may move to another
      theme or change the quote; the researcher expects that ripple.
    - A factual correction (spelling, punctuation, a brand: "bee bee sea" → "BBC") changes nothing
      in the analysis.
    - A meaning change ("I really hate that" → "I really love that") should be tagged again and may
      leave a signal card.

    Which is which, and what each one re-runs, is measured before it is built: a corpus of plausible
    edits, a way to tell their kinds apart, and a rule per kind (step 2b).
14. **A caret in the words owns the keyboard.** Single keys are text there, as in any document.
    Clicks on margins, timecodes and badges stop placing the caret, so the page's shortcuts
    (`[` `]` `/` `?` `m`) keep working from them.
15. **VoiceOver hears one editable document.** Paragraphs are read with speaker and time;
    timecodes, badges and the margin are non-text islands. Checked by hand with VoiceOver at step 2a.
16. **The sentence-start capital (`::first-letter`) is checked by hand at step 2a**, for caret bugs
    in WebKit (the Mac app) and Chromium. If the caret misbehaves, the capital becomes a real span
    the editor treats as one character. The stored text never changes either way.
17. **Any edit can be removed, in any order**, which the Bin's Put Back needs. A removal that would
    strand a later edit (a split of a half) is refused and says so.
18. **A correction's new words share the replaced words' time span**, divided by length. Nothing
    touches the audio; a clip still cuts at real word times outside the correction.
19. **A strike covers any selection**, across paragraphs and speakers, widened to whole words at each
    end. One strike is one row in the Bin.
20. **Find and replace v1 finds text variants only**: case, spacing and punctuation ("B B C", "bbc",
    "B.B.C."). Post-v1 enhancements, each measured first:
    - sound-alikes (phonetic, local; check for English-only bias);
    - low-confidence words, which needs Whisper's per-word confidence kept at import (it is dropped
      today: `importer.py` keeps only word, start and end in `words_json`), and has nothing to offer
      on Apple or platform transcripts;
    - suggestions from the LLM (paid, and the text goes to the provider again).

    The word list feeds Whisper's prompt only after the prompt-echo measurement (step 3b).
21. **A factual correction rewrites a signal card only when the card's own text holds the old
    words.** A card's headline and pattern are cached on a hash of its quotes' text
    (`elaboration.py:86`), so any change would otherwise re-pay the model: four calls for one
    spelling fix in the play-out. A meaning change rewrites the card, once step 2b can tell the two
    apart; until then only the old-words check applies.
22. **When a new interview is analysed, the word list offers its known wrong forms at once**
    ("BBC: 4 to review in this session"), through the same review as find and replace, before it
    ever feeds Whisper. Never applied without review (decision 7). The same mishearings recur, and
    correcting them again by hand is the boring part this removes (owner). Quotes are extracted
    before the researcher accepts, so they arrive with the wrong form and are then corrected like
    any quote.
23. **The word list is study knowledge, not analysis.** It survives Re-analyse (the corrections do
    not; the list re-offers them, decision 22), so it is stored beside the study, carried across the
    way the study marker is, not in the output folder's database. It is a Dashboard widget, where
    the researcher sees and edits it. Later it is shared between studies in the same folder, because
    a client's or a product's vocabulary repeats from study to study; it then moves to the app-wide
    level, like codebook tags and people (instance-scoped tables, `bristlenose/server/CLAUDE.md`).
24. **Find and replace corrects inside struck and hidden text too.** It is still the record, so Put
    Back or unhide brings the passage back already right. The review list shows each candidate's
    state ("struck", "hidden").

**Order of work.** Each step names what it needs from the steps before it.

1. **One word-range type, and one edit record.** A word range is a span of the unedited transcript:
   session, start and end time, and the words, resolved to word positions at import. Quotes carry
   one (the keystone, decision 3) and so does every edit. Split, join and move migrate onto it
   (decision 11).
   - The record lives in the database and in a file in the output folder's `.bristlenose/`, which
     the pipeline reads, so re-extracting a session uses the corrected words and skips struck ones.
     Role pins are the sibling. It is discarded with everything else by Re-analyse (decision 12).
   - It must survive every other path: Analyse of new files, a session's re-extraction, a speaker
     recode, a re-transcription (an edit whose words changed is refused), a late file set aside, a
     crash and restore, a serve restart, a study moved or copied. Each becomes a row in
     `docs/design-lifecycle-failure-modes.md` with its proving test.
   - **Corrections are their own layer**, between the pipeline's text and the researcher's quote
     edit. Never a `QuoteEdit`: an edited quote is pinned and minted a durable id
     (`importer.py:2667`), so a study-wide replace would freeze dozens of quotes nobody chose.
   - **One correction reaches three copies on a quote** and must change them together: `Quote.text`
     (signal cards, AutoCode, the Dashboard's featured picks, the discussion lens's tie-break),
     `verbatim_excerpt` (the gutter's match) and the researcher's edit if it still holds the words
     (Quotes lens, exports, chat, MCP). One write path, pinned by a test that reads every surface.
   - **A re-read session rejoins its quotes against the corrected text.** The importer matches
     re-cut quotes to rows one to one by start second, and where two share a second, by words at
     0.6 (`importer.py:1839`); "the bee bee sea" against "the BBC" scores 0.36.
   - Needs: decisions 11, 12 and 17.
2. **(2a) Word correction.** Typing is let into the transcript; the `beforeinput` guard keeps
   refusing pasted or dropped markup. A correction lands on a word range, flows both ways
   (decision 6), takes the replaced words' time (decision 18), and reverts by deleting its row.
   An edit that changes only spacing is no edit (`design-undo-catalog.md`, decision #30). The
   analysis does not move yet. Acceptance includes decisions 14, 15 and 16 and input-method
   composition. Typing over a redaction token (`[NAME]`) is refused: a name typed there would
   re-identify a redacted study through every export and agent; names go through the people layer
   (decision 7). Needs from 1: a place to land, each quote's range, and the corrections layer.
3. **(2b) What an edit sets moving.** Research first, then build (decision 13): the corpus of
   plausible edits, both transcript and quote side; how to tell a factual correction from a meaning
   change, and a correction from tidying; and per kind, whether the session becomes owed work for
   the next Analyse (the sibling is a speaker recode, `10af9e8f`), re-tagged, or left alone. Needs
   from 2a: real corrections to classify.
4. **(3) Find and replace across the study.** Each accepted candidate is a 2a correction, so it
   flows to quotes and its consequences follow 2b. v1 finds text variants (decision 20). People and
   places go through the people layer. The batch is one act, one Undo entry. The word list and its
   Dashboard widget (decisions 22, 23) land here. Needs: 2a; 2b for the consequences of a batch.
   **(3b)** The word list feeds Whisper's prompt, after the prompt-echo measurement.
5. **(4) Strike (Delete) and the Bin.** Needs only step 1 and the shared filter (built), so it can
   move earlier or run beside 2a if the Bin's Mac sidebar work is scheduled separately. Plan:
   `docs/design-delete-and-bin.md`.
6. **(5) Editorial notes.** Need 2a's typing. Cheaper than they look: a note lives only in the edit
   record, so extraction never sees it and leaving it out of the analysis costs nothing. The work is
   the who-and-when attribution, the drawing, the soft word cap, and how a note appears in exports
   and copies. Every surface that prints quote text (cards, signal prompts, subtitles, exports,
   agents) must know a note as non-speech, so a note is a typed span, never plain text.

**Open**
- Should the Re-analyse sheet and `run --clean` list transcript edits and strikes among what is
  lost? Proposed yes: it follows from decision #135 (`e8aa29ff`) and decision 12, and today they
  list neither splits, joins nor moves (`curation_counts.py`).
- A quote that a strike covers in part: `design-delete-and-bin.md` (v1) excludes it whole until the
  researcher crops it clear; decision 13 expects the next Analyse to re-read the rest. Proposed:
  excluded whole until the next Analyse, which re-reads what is left.
- Where a refused replay is shown. Edits that no longer match are logged and shown nowhere.
- Step 2b's corpus, kinds and rules.
- For editorial notes: what "who" says in a one-researcher app, and the word cap's level.
- `design-delete-and-bin.md`'s own calls: the words, glyph or row, Empty Bin, the empty-again rule.
- From the consequences mockup (24 Oct 2026):
  - A restored "not" under a reworded quote: is a quiet flag loud enough when the correction
    inverts the meaning? The quote goes on feeding sentiment, signals, exports and agents.
  - A partial strike on a starred quote: the re-cut quote may cover too little of the starred span
    for the ≥70% overlap rule to carry the star. Re-cut at once keeping the star, or teach the carry
    about strikes.
  - Should find and replace offer renames for section and theme names that hold the find string
    ("Trust in bee bee sea news")? A rename is a heading edit, the researcher's own act.
  - Signal cards read `Quote.text`, never the researcher's quote edit, so today a quote edit never
    reaches a card. Decide whether it should, alongside decision 21.
  - A correction that shortens a quote can move it out of the 12–33-word band the Dashboard's
    featured picks prefer (`export_core.py:432`). Accept, or count words on the pipeline's text.
- Small, recorded with the 8 Oct review: the Backspace join guard compares displayed codes where the
  server compares slots; Return cannot split a paragraph with no spaces (CJK).

**Related:**
- `docs/design-delete-and-bin.md`: strike, the Bin, Put Back.
- `docs/design-analysis-lifecycle.md`: Analyse, Re-analyse, owed sessions.
- `docs/design-speaker-editing.md` and `docs/design-transcript-speaker-editing-roadmap.md`: merge,
  split and reassign.
- `docs/design-people.md` §K: speaker scope.
- `docs/design-curation-persistence.md`: `durable_id`, `frozen_form`.
- `docs/design-quote-editing.md`.
- `docs/design-transcript-readability.md`: display-only tidying, which is not editing.
- Mockups: `docs/mockups/transcript-edit-consequences.html` (what each edit reaches, surface by
  surface, with the code that decides it), `docs/mockups/transcript-quote-gutter.html`,
  `docs/mockups/edit-affordance-states.html`.

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

**Owner, 16 Oct 2026: still wanted, still future.** The user-facing verb is **Delete**: select a passage and delete it, and it shows struck through. Struck text is left out of the analysis *and* out of every export, not only out of re-analysis. The case is the chat about the weather, or "looking forward to seeing you at the party!". Its sibling in the Quotes lens is Delete next to Hide and Star, the Trash tier of `docs/design-quote-triage.md` §5 (see that section's 16 Oct 2026 note). Both need one read-side exclusion shared by every analysis surface, the same exclusion hidden quotes use since 22 Oct 2026 (`speaker_slots.analysis_quotes`). The plan, with the Bin and Put Back, is `docs/design-delete-and-bin.md`.

#### Operation 2: Text correction

Simple contenteditable on individual segment text. Click to edit, type correction, blur to commit. No crop handles, no bracket UI — just a text editor.

**Data model**: `TranscriptSegmentEdit` table (session_id, segment_index, edited_text, edited_at). Original text preserved in `TranscriptSegment.text`.

**UX**: Click segment text to enter edit mode. Type freely. Enter/blur commits. Escape cancels. Small undo icon on edited segments.

> **Treatment, corrected 2026-09-20.** This said "yellow background (same as quote editing)". Do not build that. The yellow (`--bn-colour-crop-bg`, named `--bn-colour-editing-bg` until that date) belongs to quote *cropping* only — it pairs with the bracket handles and signals "move this boundary", not "retype this string". A segment edit is an ordinary inline edit field and takes the `--bn-field-edit-*` set: segment text sits on page background, so the field tints up (`--bn-field-edit-fill-on-page`) with a 1px `--bn-field-edit-edge`. The rule and its one exemption are documented in `bristlenose/theme/tokens.css`; `docs/mockups/edit-field-idioms.html` renders every case. Borrowing the crop yellow for a text edit is precisely the drift the rename was done to stop.

**Timing** _(superseded 24 Oct 2026 by decision 18: the new words share the replaced words' time span, divided by length)_: Word-level timestamps (`words_json`) are not updated. Playback cursor position degrades for edited segments but remains correct for surrounding segments. This matches Dovetail's approach (accept drift, it's fine for research).

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

> _24 Oct 2026:_ 1, 3 and 4 were answered for strikes on 16 Oct (`design-delete-and-bin.md`). 2 is decision 13 at the top (it depends on the kind of edit; measured first, step 2b). 5 is decision 18 (new words share the replaced words' span). 6 is decision 19 (any selection, widened to whole words).

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

Runtime matching is recomputed every request in `bristlenose/server/routes/transcript.py`: segment↔quote by **timecode-range + `speaker_code`** (the `seg_quotes` match in `get_transcript`), in-segment offset by **case-insensitive `str.find()` of `verbatim_excerpt`** (`_highlight_quoted_text`), with a **whole-segment `<mark>` fallback** when the substring doesn't match. Consequences that already ship today:

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

`[editor: X]` is a long-standing transcription convention (family of `[inaudible]`, `[crosstalk]`, `[sic]`). _Note, 13 Oct 2026:_ in Bristlenose's own transcripts "inaudible" is no longer bracketed text — it is a segment flag the page draws as a muted, non-editable annotation, kept apart from the brackets precisely so that brackets can mean the analyst's insertions (`bristlenose/stages/CLAUDE.md`, the inaudible net; split and join refuse such a gap). It is generative but *marked as non-speech*, and that marking is exactly what preserves the truth claim: it says "a human added this, the participant didn't say it." The system already half-speaks this (PII emits bracketed `[NAME]`; `speaker_role` distinguishes moderator). Requirements: **excluded from quote extraction and sentiment**, visually distinct, **attributed** (who + when — doubly important in a medical/legal record), with a **soft, invisible word-cap backstop** (tuned from real data, not a visible setting) so a transcript can't quietly become mostly editorial.

### The one thing to prevent

Not insertion — *unmarked* insertion of speech-looking text that a reader or the extractor would take as the participant's words. **Fabrication is a formatting failure, not an editing capability to withhold:** inserted non-speech must always wear the editorial bracket/styling, and then it is fine. That single rule is what lets the whole vocabulary stay honest while giving the user the document they're right to expect.

### Quote edits win, one way (owner, 17 Oct 2026)

> _Revised 24 Oct 2026 (owner), decision 6 at the top:_ a **correction** (words swapped in place, any length) flows both ways automatically, into every quote that still holds the words and from a quote back into the transcript; **editorial** quote edits stay with the quote. The researcher thinks they are editing the same words. The single-word question below is answered by that. Kept as written for the reasoning.

An edit made in the Quotes lens is more definitive than a correction to the transcript, and it does not go back. A quote edit is editorial (crops, tidied wording, ellipses), so there is no faithful way to write it into what was said. So: a transcript correction flows into a derived quote only when that quote has no edit of its own; a quote with its own edit keeps it; nothing flows from a quote edit into the transcript. When a correction lands under a quote that has its own edit, the Quotes lens should say so quietly, so the researcher can look (a restored "no" must not sit in the transcript while the quote still says the opposite). That is a flag, not an automatic change.

**The likely exception: a single-word substitution** (owner, 17 Oct 2026, not yet decided). A quote edit that replaces exactly one word in place, with nothing cropped, inserted or reordered, is usually a mishearing ("Alesi" → "Alessi"), and it maps onto exactly one transcript word through the word-range anchor. Such a correction could be carried back into the transcript; anything more stays one way, because beyond one word the mapping gets hard. Open: carry it back automatically, or offer it ("Also correct the transcript?").

**What these words are, and what follows** (owner, 17 Oct 2026): brand names, places, people and technical terms. They recur, so a correction of one is really "this study says *Alessi*": offer to correct every occurrence (in this session, or the whole study), the way Descript and Otter do, and keep the study's corrected words as a list. The same list can go forward into transcription, which already sends Whisper a prompt on every window (`s05_transcribe.py`, the style prompt), so a later session or a re-transcription hears the word right first time. Two cautions. Prompt words can be hallucinated into silence (the stage already detects prompt echoes and guesses), so measure before shipping, per that file's rule for prompts. And **people and places** overlap anonymisation (names and locations are what redaction removes), so correcting a person's name goes through the people layer, never the redacted text; brands and technical terms carry no such risk.

**At real scale it is find and replace, and the wrong forms vary** (owner, 17 Oct 2026, from experience: a product name or acronym can be wrong in hundreds of places). One right word arrives as many wrong ones, some of them multi-word and some of them real English used correctly elsewhere, so a replacement that is right in one sentence is wrong in the next. So a blind replace-all is unsafe and a single-string replace finds too little. What it needs: find every candidate across the study, show each in context, and let the researcher accept all or go one by one (the shape of BBEdit's or Xcode's multi-file find and replace). The candidates come from more than exact matches: case and spacing variants of an acronym, sound-alikes, and Whisper's own low word confidence, which clusters on exactly these words. The accepted corrections become the study's word list above.

### The transcript is a document, not a form (owner, 17 Oct 2026)

Editing reads as a text editor: a click puts the caret in the text and the ground stays the same paper everywhere, with no field fill and no edge. Corrections, `[editorial notes]`, splits and joins all leave one continuous text. The white lift and the 0.5px ink keyline of `docs/mockups/transcript-quote-gutter.html` only ever show the chunks that feed the other lenses, on hover. Clicking text is always the caret; the links into the other lenses live on the gutter marks and margin titles, and in the Mac's right-click menu. This replaces the "Treatment, corrected 2026-09-20" note's field treatment above, for the transcript.

---

## Split and join, stage 1 — built 6 Oct 2026

The common case (owner, 6 Oct 2026): a long paragraph that does not read as one thing, split in
two with the same speaker; and the reverse. Speaker reassignment of a half is stage 2, and waits
on the scope question in `design-people.md` §K. *(Built 6 Oct 2026: the picker's Paragraph scope
moves one paragraph to another speaker — `design-people.md` §K6, `POST …/transcripts/{sid}/reassign`.)*

- **One editable region, not one per paragraph** (7 Oct 2026). The transcript section is
  the editing host; timecodes, badges and the margin are non-editable islands inside it,
  and Return and Backspace find their paragraph from the caret (`data-position`). Each
  paragraph was its own host until then, and a selection cannot leave the host it starts
  in, so dragging to select across paragraphs was impossible (owner).
- **The speaker label is not part of the text** (7 Oct 2026). The raw `.txt` writes each
  line's label after its code, `[00:14] [p1] (Speaker B) Okay…`, and a platform
  transcript's label is the person's real name. The importer kept it, so the page drew
  "(Speaker B)" and "(Rachel Okafor)" in front of the words, and the name reached exports,
  search and the agent endpoint past anonymisation. It now drops a leading label that is
  one of the session's own recorded labels (`speaker-info/<sid>.json`, the registry),
  never any other bracket: "(laughs)" stays. Measured on 3,237 real paragraphs: none
  still starts with a label. A split, join or move made in 0.35.0 on an *untimed*
  labelled paragraph counted the label's words; replay reads past them (8 Oct 2026,
  `transcript_layout._still_reads` / `_split_token`), and past case and punctuation, so
  a redaction switch — which drops word timings — does not lose the edits either.
- **Interaction.** The transcript's text takes a caret (the `contenteditable` host above) and nothing else: typing,
  dictation, autocorrect, pasting and dropping are refused by a native `beforeinput` guard, since
  the words are the recording's. **Return** splits at the caret; **Backspace** at a paragraph's
  start joins it to the one above, same speaker only. **⌘Z / ⇧⌘Z** undo and redo from the
  transcript (the page's own ⌘Z stands down inside editable text) and from Edit ▸ Undo. Not in an
  exported report. Prior art agrees on Return: Dovetail, Trint and Condens.
- **The cut** lands at the word boundary before the caret, counted in the words the page draws —
  Whisper's words where the paragraph has them, else its text — so the researcher's cut and the
  server's agree. The text is cut at the same word in its own spelling: the drawn words are
  aligned to the text's words (`transcript_layout.text_cut`), so a timed paragraph keeps its
  case and punctuation (until 6 Oct 2026 the halves were rebuilt from Whisper's words,
  lower-cased and unpunctuated). Both halves keep the speaker; the second starts on its first word's time, or a
  share of the paragraph's time by text length without word timings. With no time to share, it
  starts a hair after the first half, short of the next paragraph, so splitting the first half
  again lands between the two (a tie fell through to insertion order, reviewed 6 Oct).
  Backspace joins only with the caret before the first character — not inside the first word,
  and not anywhere in a paragraph with no spaces, as the word count would have had it.
- **Storage.** Each edit is a row of `transcript_layout_edits` (migration 015): kind, the
  paragraph's position in reading order (start, ordinal, id), the split's word count, and the
  first words it was made against. The importer rebuilds a session's paragraphs from the
  pipeline's transcript on every import and replays the edits in order
  (`transcript_layout.replay`), so a split outlives a re-run; an edit whose words changed under it
  (a re-analysis rewrote the transcript) is skipped and logged, never made on other words. Undo
  forgets the edit and rebuilds that session's paragraphs (`rebuild_session_paragraphs`).
- **Departure from the converged spec above.** The spec's rule is that a split forks any quote
  spanning it (sentiment re-evaluated, tags copied, `durable_id` kept by one half). Stage 1 does
  not fork quotes: the split is for reading, and the quote's highlight already marks both halves,
  because the match is by time window. The fork rule stays for when a split means "two points",
  with stage 2.
- **A paragraph's first letter** (owner, 7 Oct 2026: option C of
  `docs/mockups/transcript-paragraph-capitalisation.html`). Drawn as a capital where a
  sentence begins: the first paragraph, a new speaker's turn, or after a paragraph of the
  same speaker whose stored text ended a sentence (`utils/sentenceStart.ts`, read from the
  text because it carries punctuation more often than the word timings). A paragraph that
  carries on mid-sentence after a split stays as transcribed. Display only — CSS
  `::first-letter` on `.bn-sentence-start`, following the paragraphs' `lang` (the session's
  spoken language, `language` on `/transcripts/{sid}`) — so the stored text and the drawn
  words never change. A first word spelled lower-case on purpose (iPhone, eBay,
  ikea.com) keeps its spelling. Measured on 3,237 real paragraphs before building
  (`experiments/paragraph-case/`): 55 capitalised, all correct in the sample; 207 kept
  lower-case, mostly true continuations; about 31 real starts missed where the previous
  text has no punctuation, which stay as today. It does nothing for sentence starts and
  "i" *inside* a paragraph — that is the larger problem, and a separate one.
- **Known limits, from the 6 Oct review, not yet fixed.** A click into a paragraph's text makes
  the page "editing", so bare-key shortcuts stand down until focus leaves; an input method's
  composition cannot be cancelled by the `beforeinput` guard; a split or join the server refuses
  is silent (it needs a string); Return cannot split a paragraph with no spaces (CJK — needs a
  decision on what a cut means there); and one refused edit in a replay shifts every later
  position, so those are refused too and logged.
- **Known limits.** Positions count in reading order, so a paragraph that shares its start second
  with another keeps the page's existing anchor collision (`t-<second>`). The pipeline's own
  outputs (transcript files, markdown) do not carry splits; they are serve-side curation, like
  quote edits.
- **Direct editing of a paragraph's words** is the next distinct piece (owner, 6 Oct 2026):
  connected to quote editing with revert, wanted simpler, reusing that logic and UX where it fits.
  Not started.

---

### Open after the 8 Oct 2026 review — owner's calls

> _Answered 24 Oct 2026 (owner), decisions 11 and 14–17 at the top:_ the caret in the words owns the keyboard, and clicks on margins, timecodes and badges stop placing it; VoiceOver hears one editable document, checked by hand at 2a; `::first-letter` is checked by hand at 2a; every edit is keyed on time plus words; any edit can be removed in any order, and a removal that would strand a later edit is refused. The small items at the end stay open.

- **Is a focused transcript "editing"?** One editable region means a click on a margin or a
  timecode's text focuses it, and the page's bare-key shortcuts (`[` `]` `/` `?` `m`) stand
  down until something else takes focus. The region takes no typing, so it could be excluded
  from `isEditing()`; or the caret owns the keyboard, consistently. jsdom cannot see this.
- **What a screen reader hears.** VoiceOver likely announces the whole transcript as an
  editable text area although typing is refused. `role="document"` + `aria-readonly`, or a
  caret only while a split/join mode is on. Needs a VoiceOver pass by hand.
- **`::first-letter` in an editable region** — WebKit and Chromium have old caret bugs there
  (the caret between the drawn capital and the next letter). Check by hand.
- **Position + six words as an edit's anchor.** A re-run that adds or removes an earlier
  paragraph shifts every later position, and those edits are refused; a short paragraph
  ("Yeah.") could in principle match a neighbour. Time + words would survive the shift and
  refuse an ambiguous match. Edits that fail to replay are logged, not shown anywhere.
- **Undo is newest-first only in the UI**; `DELETE …/layout-edits/{id}` takes any edit, and
  deleting a middle one silently drops later edits whose words then fail. Refuse a
  non-newest delete, or keep the API general?
- **Small, recorded:** the Backspace join guard compares displayed codes where the server
  compares slots, so two slots of one person get a silent 409; an untimed transcript's
  second split of a first half still sorts after the other half (ties fall to insertion).

## Copying from the transcript — built 8 Oct 2026

A drag across paragraphs copies the house transcript format, not the page's
markup (`frontend/src/utils/transcriptCopy.ts`, wired as `onCopy` on
`section.transcript-body`, export mode included). Decided with the owner, 8 Oct
2026, against real pastes into iA Writer and Word:

- **text/plain is Markdown**, the same shape as the `.md` export:
  `` **`[00:42]` p1** words ``, one paragraph per block. The timecode is a code span
  so a renderer sets it in monospace; the stamp is bold.
- **text/html carries the same structure for Word**: the timecode as the app
  draws it — Menlo / Consolas at 85%, regular weight, accent blue with grey
  brackets — the code bold, and the words unstyled so they take the
  document's font. Margin annotations, × buttons and the speaker picker never
  reach the clipboard.
- **Speech is escaped minimally** (`escape_markdown_speech` / `escapeMarkdownSpeech`,
  pinned together in `tests/fixtures/shared-format-contract.json` →
  `markdown_speech`). The text never starts a line, so `#`, `-`, `>` and `1.` are
  inert; brackets matter only as `](`. Measured: 7 of 28,908 real paragraphs
  need any backslash. Rejected: escaping every punctuation mark (83 backslashes
  on the worst-case set, all visible in a source editor such as iA Writer), and
  transmuting characters (`*` → `∗`), which changes a verbatim quote.
- **A paragraph entered part-way** keeps only the selected words and takes the
  time of the first selected word, where words are timed.
- **A selection inside one paragraph copies plain words, unescaped** — a
  snippet for a sentence, not a document.
- **Capitals as drawn**: where option C draws a sentence-start capital and the
  selection takes the first letter, the copy carries the capital too.
- **Codes, not names; no source line.** iA Writer names an untitled document
  after its first line; that is its behaviour, not ours.

The prototype and its worst cases: `experiments/transcript-copy/`.

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
