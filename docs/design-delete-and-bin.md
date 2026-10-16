# Delete and the Bin

**Status: parked, 16 Oct 2026.** Research and planning from one owner conversation; nothing built. Parked in the forward plan (Missing, Icebox). This is the Trash tier of `design-quote-triage.md` §5, and it supersedes that section's "Trash isn't banished to a sidebar destination" (see Placement).

## What it is

Two ways to say "this isn't evidence", and one place to take it back.

- **Strike a passage.** In a transcript, select text and press Delete. It stays on the page, struck through, and nothing downstream uses it. For the chat about the weather, or "looking forward to seeing you at the party!". (`design-transcript-editing.md` Operation 1 is the earlier design.)
- **Delete a quote.** In the Quotes lens, Delete sits beside Hide and Star.
- **The Bin.** A page listing every struck passage and every deleted quote, newest first. Select several, Put Back.

Nothing is ever actually removed. The source text, its timecodes and the recording all stay as they are.

## Decisions (owner, 16 Oct 2026)

1. **Mark, never remove.** Deleting marks; it is clean and reversible. Actually deleting text from transcripts would leave gaps in the timecodes and create more problems than it solves. Probably never needed: the real delete already exists, which is removing a recording. Whole-session removal drops that session's pins on purpose, "so consent withdrawal genuinely removes data" (`design-curation-persistence.md` § What still destroys curation). It is the honest unit, because it takes the video too.
2. **Reversible through the Bin.** A list, newest first, multi-select, Put Back.
3. **Bin contents are absolutely excluded** from reports and exports. They are left out of the data, never hidden by CSS. The Bin is not a hidable view.
4. **Handing over the project folder is fine.** The recipient gets the recordings and could re-analyse anyway, so the Bin and Put Back travel with it. The deliverable is the export, not the folder.
5. **The Bin is not a lens.** Lenses are views onto the evidence; the Bin holds what was taken out of it.
6. **Placement:** pinned at the bottom of the sidebar, just above the version + ladybug footer (`SidebarFooter.swift`), on the sidebar's own material. It stays visible however many projects there are.
7. **Appears on the first delete** ("pops into life"); absent until then.

## Proposed, awaiting the owner's call

- **Words: Delete, Bin, Put Back.** The act is Delete: Bristlenose is document-centric, and struck-through deletion is the Track Changes look researchers already read correctly. Apple's apps with a deleted-items place all say Delete; only Finder says "Move to Bin", because it moves files. The place is Apple's word in each locale ("Bin" in British English, "Trash" in US English); take the others from Apple's glossaries, not our own translation. The way back is **Put Back**, Finder's verb, because the item returns to where it was. "Recover" (Photos, Files) implies expiry; "Undelete" is not an Apple word.
- **No Empty Bin.** Emptying would either destroy nothing (it only removes the safety net) or would be erasure, which is a different, participant-data feature. Erasure, if it is ever wanted, is a separately named action on struck passages ("Erase from Project…") with an honest list of what it reaches. It can't reach: the recording, exports already sent, backups, or what the LLM provider kept. It must also keep a record of the struck range, or re-transcription brings the words back. That belongs under `methodology/consent-gradient.md`.
- **A glyph in the footer line, or a full row above it.**
  - **A `trash` glyph with a count, beside the ladybug** (recommended for v1). The footer bar never changes height, and there's no custom selection drawing: it's a button that opens the Bin page.
  - **A full source-list row.** The frosted bar grows about 32 pt while the Bin shows; the list loses that height and must still scroll its last project clear. The row also needs a hand-drawn selection highlight matching the source list (capsule, accent, inactive-window dimming), because it sits outside the outline view.
- **When empty again:** the Bin goes once it's empty and you've left it. It never vanishes from under you: Put Back the last item and you stay on "Nothing in the Bin" until you navigate away. This is the same rule as Screens, which joins the rail only while it has something to show (`LensItem.rail(screenText:screensAvailable:)`).
- **The Bin is per project, in an all-projects place.** Accepted; the lens rail has the same oddity. The glyph or row shows the selected project's Bin, and the tooltip names the project. Switching projects makes it come and go under rule 7. Watch that in the app before committing to it.
- **Hide stays as Archive.** Hidden quotes stay in place, greyed, and never go to the Bin. That gives three tiers: Visible, Hidden (Archive), Bin (Trash).
- **A partly struck quote is excluded whole** in v1, so struck words can never leak. The researcher brings it back by cropping it clear of the strike with the existing crop handles. It is listed in the Bin under its passage.
- **No ⌘ number.** A place that comes and goes can't hold one (Screens' ⌘7 is already conditional). It gets a View menu item instead, which is also the route when the fit cascade folds the projects column.
- **Drag:** the Bin refuses a dragged project row (Finder has taught people to drag things to the Trash). Dropping quotes onto it is a later extra.
- **Web:** the browser report puts the Bin at the end of its tab bar. Same thing, native placement per surface. Never shown in the HTML export.

## Consequences across the app

### Data

- **Two records with two keys.** A deleted quote is keyed on the quote, with when it was deleted, for the sort. A strike is keyed on its session, its time range and the words it covers. The sibling to copy is transcript layout edits: they're recorded with the words they named, replayed on every import and refused when the words no longer match (`importer.py` `_replay_layout_edits`, `transcript_layout.replay`).
- **A deleted quote must survive re-runs the way a star does.** Hide is best-effort by design: about 5% come back after a re-run (`design-curation-persistence.md`, What still destroys curation, item 3). A deleted quote that quietly comes back is a broken promise.

### Analysis: one filter, then an audit

- **`speaker_slots.evidence_quotes` is already the single gate** ("count quotes through them", `server/CLAUDE.md`). It already drops two classes of quote until the next re-analysis. Deleted and struck become a third class there, and about 18 consumers get it for free. Hidden stays a separate filter, because Sessions and the tapestry keep hidden quotes; they would drop struck ones.
- **Some code reads quotes directly, without the filter:** `autocode.py`, `codebook_builder`, `clips_export`, `journey.py`, the transcript route, `export_core` and `data.py`. The costly one is AutoCode, which loads every quote (`autocode.py:244`). It would pay the LLM to tag the Bin and leave proposals on it.
- **Gate it mechanically**, as `tests/test_serve_export_coverage.py` does for routes: a test fails if anything reads quotes without the filter.
- **What recalculates:**
  - **Free:** grid counts, concentration, card strength, folding and Sentiment. Serve computes Signals per request, so exclusion is a filter on read.
  - **Paid once:** a card's written headline and pattern. The elaboration cache is keyed on a hash of the card's quote texts (`elaboration.py:86`), so the card is rewritten once. The cache keeps one row per card and overwrites it (`elaboration.py:271`), so a strike followed by an un-strike pays twice; keeping rows by hash would make undo free.
  - **Stale until Re-analyse:** section and theme names and descriptions, and the Dashboard summary. They were written by the pipeline from quotes that included the excluded one. The researcher can rename them (renames reach every surface since 16 Oct 2026); Re-analyse rewrites them. An emptied section or theme disappears from Quotes.

### Re-analysis

- **The pipeline does not read the database.** For struck text to stay out of the LLM's input, the strike has to live in a file the pipeline reads. Role pins are the precedent: they live in the session registry and the next run honours them (`server/routes/reanalyse.py`). The transcript keeps its text and timecodes; only the prompt drops the struck lines, or marks them `[removed]` so the context stays honest.
- **A clean Re-analyse wipes the database by design**, and the confirmation sheet counts what's lost. So:
  - **Deleted quotes are lost**, and the sheet must count them.
  - **Strikes must survive.** They're carried across `--clean` the way the study marker is. This is the property that makes the strike worth having: it acts on the input, so it is the only curation that survives a re-analysis. Strike, then Re-analyse, gives clean themes.

### Exports and every outward path

- **Left out of the data:** the HTML export's embedded JSON, CSV/XLS, Miro, the chat lens, MCP, and every LLM call made after the delete (AutoCode, card elaboration, the codebook builder).
- **Embedded transcripts** in the HTML export show "passage removed (0:42–1:10)" where struck text was. That's the only visible gap, and it's display only: no timecodes change.
- **Clips are the leak to watch.** A kept quote's clip can include struck audio from the passage next to it. For v1, trim or refuse a clip that overlaps a strike.
- **Words already sent once** during the original analysis are in `llm-calls.jsonl`. Deleting doesn't change that, and the docs must not imply it does.

### UX

- **In the transcript:** select, Delete, struck through. **In Quotes:** Delete beside Hide and Star.
- **Undo:** ⌘Z through the existing undo stack. Quotes shows "N in Bin", the way it shows "N hidden".
- **Selection on the Bin page:** the selection Quotes already uses (click, shift-click, ⌘-click, ⌘A), not checkboxes. Checkboxes are iOS's Select mode.
- **Conflict:** `design-quote-triage.md` §6 proposed the Delete key for Hide/Archive. That key now belongs to the Bin.
- **Accepted edge case:** a participant who withdraws part of an interview, not all of it. That needs the recording cut, which happens outside Bristlenose: edit the file and re-add it.

## The sidebar footer, as it stands

`SidebarFooter` (version left, ladybug right) has no band of its own: it sits on the sidebar's material as plain `.secondary` text. On macOS 26 the list slides under it behind the system's soft scroll edge:

- **SwiftUI sidebar:** `.safeAreaBar`.
- **AppKit outline:** a split-view item accessory, `SidebarFooterAccessory.swift`.
- **macOS 15:** no soft edge, so the footer stacks below the list.

A Bin row or glyph goes wherever the footer goes, on all three paths (`ContentView.swift` `sidebarWithFooter`). If the bar grows, check that the AppKit accessory path insets the list. It should, but that's unmeasured.

## Before building

- The owner's calls above: the wording, glyph or row, Empty Bin, and the empty-again rule.
- Run `what-would-gruber-say` on the placement and, if it's a row, the selection drawing.
- Run `is-this-bristlenosey` against the nearest siblings: Screens' appear-when-available, layout-edit replay, role pins, `evidence_quotes`.
- Settle the hidden-quotes-in-Signals question first (`TODO.md`, 16 Oct 2026). It needs the same read-side filter, built once.
