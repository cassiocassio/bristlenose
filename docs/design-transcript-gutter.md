# Transcript gutter — linking a transcript out to the lenses

**Status:** built 17 Oct 2026 — stages 1 (Quotes), 2 (Screens) and 3 (Discussion). Decided in conversation with the owner on 16–17 Oct 2026 against
two mockups: `docs/mockups/transcript-quote-hooks.html` (round 1, six ways to find a quote) and
`docs/mockups/transcript-quote-gutter.html` (round 2, the direction). The editing decisions made in
the same conversation are in `design-transcript-editing.md` ("Quote edits win, one way", "The
transcript is a document, not a form"). Editing is not part of this work.

## The job

A researcher reading a session's transcript sees what became of it: which passages are quotes and
where they went (a section or theme of the Quotes lens), which screen was showing (the Screens
lens), and which question in the guide the moderator was asking (the Discussion lens). From the
transcript they can jump to each, landing on the thing itself.

## What it looks like (settled)

- **Ground.** The transcript sits on very pale paper. Quotes lift to white ("sheet") on hover. Two
  new palette colours, defined by every palette:

  | | light paper / sheet | dark paper / sheet |
  |---|---|---|
  | default | `#f6f7f8` / `#ffffff` | `#111111` / `#1c1c1e` |
  | edo | `#f7f2e6` / `#fdfbf7` | `#1a1816` / `#26221b` |

  The transcript scope re-points badge grey to `#ebedf0` in default light (shipped `#f3f4f6`
  disappears into the paper, 1.03:1); edo and dark keep theirs. One scoped remap, no
  per-component overrides: tags and speaker badges both read the token.
- **Gutter.** A 2rem column between the text and the margin. Marks sit 0.25rem right of its
  centre. Gutter and margin are one two-column block, so each mark sits beside the margin entry it
  names; the first sits on the paragraph's first baseline.
- **Marks** (the lenses' own icons): Quotes `text.quote` (web: Lucide `TextQuote`), Screens
  `macwindow.on.rectangle` (web: `app-window-mac`), Discussion `questionmark.bubble` (web:
  `message-circle-question-mark`). Pale at rest, dark ink while the pointer is on the row, blue on
  their own hover. No Signals mark (deferred).
- **Margin order.** Section or theme title (blue link), then tags, then the screen (title + a
  thumbnail). A title is not repeated down a run of the same group. A screen whose name equals the
  section's drops its words. The question topic shows beside a Discussion mark, grey, a link with a
  hover underline and no blue.
- **Thumbnails** hang below the screen title out of flow and fade out under what follows; hovering
  the title, the thumbnail or the mark brings it up whole, over the neighbouring text.
- **Hover.** Anywhere along a paragraph's row lifts its quotes to white. Hovering a mark, a margin
  title or the quote's own words draws a 0.5px ink keyline round that quote as one block, notched
  where its first line starts and its last line ends; a Discussion mark keylines the question, a
  Screens mark the paragraph where the screen starts.
- **Clicks.** Text is never a link: a click is the caret. Marks and margin titles are the links.
- **Hidden quotes** draw in grey (text, mark, title). Following one into the Quotes lens un-hides it
  (the researcher's deliberate choice; undoable).
- **Narrow** (<800px): the gutter stays; the margin's titles and thumbnails drop under the text.

## The data (measured)

- **Where a quote's words are.** Today the server marks a quote only by finding its
  `verbatim_excerpt` as an exact substring of one paragraph (else it marks the whole paragraph),
  and the page skips even that when the paragraph has Whisper word timings. Measured 17 Oct 2026 on
  918 quotes in 10 local projects: 782 (85%) are on the word path, where nothing is marked today;
  exact substring finds 629 (69%); matching the excerpt's normalised words against the drawn words,
  across paragraph boundaries, finds 699 (76%), 68 of them spanning paragraphs. The 219 not found
  are mostly one oral-history project whose excerpts are tidied. As built
  (`frontend/src/utils/quoteExtents.ts`): the client matches the excerpt's words against the words
  it draws, first in the quote's speaker's paragraphs that overlap it in time (so a moderator's
  "mm-hm" inside a quote does not break the run), then in every overlapping paragraph (diarisation
  files a participant's words under the moderator often enough); where the whole sequence is not
  there (the model tidied it), it anchors on the excerpt's first and last four words within half to
  twice its length. Measured on the same 918 quotes: exact 711, anchored 175, unlocated 32 (3.5%).
  An unlocated quote is its server paragraphs' remaining words. The server's own join lists a
  paragraph only when it starts inside the quote's time, so it misses the paragraph a quote begins
  in; the client's overlap search covers it, and a paragraph that draws a quote's words is not
  knocked back whatever the join said. This is a display join, not the persisted word-range anchor
  of `design-transcript-editing.md`, which remains the keystone for editing. Both paths mark the
  quote's words the same way (`data-q`, `data-q-hidden` on spans; the untimed path draws a quoted
  paragraph's words as spans too, its text unchanged) — data attributes, never classes, because
  PlayerContext sets classes on those spans imperatively.
- **Quotes.** `/transcripts/{sid}` annotations gain each quote's group `anchor` (`section-<id>` /
  `theme-<id>`, `heading_names.section_anchor`) and `is_hidden`.
- **Screens.** `/screens` (only when the lens is available): each screen's tabs for this session
  carry `visits` [[start, end], …]. A visit's start joins to the paragraph containing it;
  consecutive visits to one screen collapse. Title by `screenTitle()` (shared with the lens, not
  copied); thumbnail from `/screens/still`, lazily, behind the bearer. Not in an export.
- **Discussion.** `/discussion`: `turns[]` with `session`, `sec` and `item`; a turn joins to the
  moderator paragraph containing its `sec`; `item: null` is not a question. Topic text from the
  record's items.

## Arrival (each lens lands on the thing)

- **Quotes:** `/report/quotes/?reveal=<dom_id>#<anchor>` (`utils/quotesLink.ts`), so a plain click
  and a new tab arrive alike. A `section-<id>`, `theme-<id>`, `sections` or `themes` fragment shows
  Sections & themes for that visit (QuotesTab: held per location, never saved over the remembered
  grouping, given up when the researcher picks). `QuotesArrival` waits until the lens has loaded
  this visit's quotes (the store outlives navigation), then un-hides a hidden quote and changes the
  fewest filters that keep it from showing (`filter.ts relaxFor`, the same checks as
  `isQuoteVisible`, pinned equal: starred-only → all; re-tick one of its tags, leaving tag solo
  first; drop the tokens it fails; clear typed text), keeps what it changed (`lastQuotesArrival`,
  for the toast question), and scrolls to the anchor once. Each island fetches `/quotes` as it
  mounts, and one answered before the un-hide reached the server brings the hide back, so for ten
  seconds after the first load a later load that says hidden is un-hidden again (that only); if the
  quotes take five seconds to come, the lens scrolls anyway and reveals when they do. Once the quote
  has landed, `reveal` is taken off the address (`dropRevealFromAddress`, `history.replaceState`),
  so Back to the lens or a reload cannot un-hide a quote hidden since. A `reveal` not in the report
  scrolls to the group and says so in the console. In an export a hidden quote cannot be un-hidden,
  so its link carries no `reveal`.
  Signals' location heading and the Dashboard's section, theme and stat links use the same address,
  which also ends their silent no-op under By session grouping.
- **Screens:** `/report/screens/?screen=<ref>&session=<sid>` (`islands/screens/screenModel.ts`). The
  reference is an FNV-1a hash of the screen's key, never the key: a key is a path from a
  participant's screen, deleted when screen text is switched off, and an address lives on in
  history, the web view's back list and the route the page reports to the Mac. The lens reads the
  query at mount (it exists only in serve mode, under the browser router) and, on the first load
  holding that screen, opens it on that session's version. When a load that is no longer pending
  still lacks it (screen text rebuilt, an old address), the lens stops waiting and says so in the
  console, so a later poll cannot jump the reader to it mid-read.
- **Discussion:** `/report/discussion/?item=<id>&turn=<turn id>` (`islands/discussion/discussionLinks.ts`).
  The lens's focus lives in module memory, which a new tab does not share, so the address carries
  it. `DiscussionView` reads it (`utils/appQuery.ts`: the browser router's query, or the part of an
  export's hash after `?`), opens that turn's session with the asking focused, and scrolls it into
  view. A turn it does not have (the record rebuilt) still focuses its item if the item is known,
  and says so in the console.
- **Back** returns to the paragraph the jump left from: the transcript's address is replaced with
  `#t-<seconds>` before the jump, which the page already honours (with its brief highlight).

## Review fixes and known limits (17 Oct 2026)

Three reviews after the build (accessibility, silent failure, code) changed these:

- **Keyboard.** A mark or label taking focus lights its quote and draws its keyline as hover does;
  Escape clears it. The quote mark and the question mark on one moderator paragraph have distinct
  targets (`p:<pos>:s`, `p:<pos>:d`), so hovering one no longer lights the other.
- **Contrast.** Where hover is unavailable (`hover: none`) or more contrast is asked for, marks
  rest at the muted ink instead of the pale one; forced colours draw them in `CanvasText`.
- **Which occurrence.** An excerpt whose words occur more than once in its paragraphs takes the
  occurrence that is free and starts within two seconds of the quote's time, else the first free
  one; a quote whose words are all taken by earlier quotes is unlocated rather than drawn over
  them. A quote found only by its anchors (words tidied between) draws its keyline dashed.
- **Failures say so.** A screens or discussion read that fails, a still that fails (not cached, so
  the next view retries), a scroll that gives up, and every stale address log a console warning
  instead of drawing nothing silently. Screens poll every 20 s while the lens is still reading.
- **Before the router is ready** a link's own `href` is followed rather than a click that does
  nothing (`navigationReady()`).

Known limits, not fixed: in a transcript without word timings, CJK text is matched by its
space-separated runs, which are rarely words, so its quotes fall back to the server's paragraphs;
WebKit reaches links with Tab only when "Press Tab to highlight each item" is on (Option-Tab
otherwise), as everywhere in the report.

Owner calls still open: whether a hidden quote's mark needs a spoken "(hidden)" (a new key in all
21 locales); the blue hover title at 3.75:1 on default light paper; the pale mark at rest; the mark
and label being two tab stops for one quote; the playback glow's contrast on paper; the toast that
says which filters arrival changed (`lastQuotesArrival` holds them).

## Where the CSS lives

New transcript rules live in `frontend/src/islands/transcript/`, imported by the page, as the
Screens and Discussion lenses do. A project serves its baked copy of the theme CSS
(`server/app.py`, `serve_theme_css_with_fallback`), so rules added under `bristlenose/theme/`
would reach no project analysed before the release; the new markup would render unstyled. The
paper and sheet tokens go in the palettes and `_contract.css` too, and the frontend reads them with
a fallback.

## Stages

1. **Quotes** (built 17 Oct 2026): annotation fields; the quote extent join; paper, gutter, marks,
   hover, keyline, hidden-grey; margin restructure (`islands/transcript/GutterEntry.tsx`, replacing
   the retired `Annotation`); arrival in the Quotes lens; Signals and Dashboard through the same
   address; Back. Checked headless in WebKit and Chromium on a dev serve of a copy of a real
   project.
2. **Screens** (built 17 Oct 2026): the `screens` icon concept (Lucide `AppWindowMac`, standing
   in for `macwindow.on.rectangle`); `screenTitle` moved out of the lens into `screenModel.ts`
   with the join, so the transcript does not load the lens's chunk; one mark per stay (a return
   to the same title with nothing between is the same stay, and two keys with one title are one
   place: QA found a paragraph naming "Storage furniture" twice); the title (not repeated when a
   section shown in the paragraph says the same) and a thumbnail fetched as it nears the
   viewport (`GutterThumb`), fading under what follows and surfacing on hover; arrival. Off,
   unavailable, failed or in an export: no screen marks. Checked headless in WebKit on a dev serve
   of a copy of a real project (12 screen marks in its first session, no key in any address).
3. **Discussion** (built 17 Oct 2026): the `discussion` icon concept (Lucide
   `MessageCircleQuestionMark`, matching `questionmark.bubble`); the record read when ready or
   partial, the states the lens shows (not run, stale and failed draw nothing), embedded in an
   export so it works offline; a moderator turn the model matched to a guide item marks the
   paragraph it was asked in, first in that paragraph's entries, with the item's short form as a
   grey topic link (an item asked twice in one paragraph is marked once); arrival. Checked headless
   in WebKit on a dev serve of a copy of a real project (8 questions in its second session, all on
   moderator paragraphs; landing lights the asking and has it in view).

## Not in this work

The Mac right-click menu and menu-bar items (need the Swift side), editing, Signals marks, and the
tag outdent (the tag-hang catalogue's job, awaiting the owner).
