---
status: plan
updated: 17 Oct 2026
---

# Screens export: a folder, a clipboard, a Miro board

**Status: the plan, 17 Oct 2026, for the weekend of 17–18 Oct.** Three ways to take the Screens
lens's stills out of Bristlenose and into the research materials. The privacy line they rest on was
corrected the same day (`design-screens.md` §4, "17 Oct 2026"); this doc does not re-argue it.

## 1. The job

Assembling a project's screengrabs is a repeated, tedious part of writing a report: researchers
screenshot the product under test, or the Teams call, by hand and drop the shots into the research
materials. Very often the next step is a Miro board for a team workshop. The lens already holds
those stills, placed against what was said; the export saves the afternoon.

So there are two readers, and each output serves one:

- **The report author** wants files: every still, full size, in an order that makes sense in
  Finder (§4), or straight onto a canvas to sort by hand (§5).
- **The workshop team** wants a board they will rearrange: each still with its quotes beside it,
  in an order they can talk about (§6). A board people drag around is a collaboration surface, not
  a printout, and that drives most of §6.

## 2. The unit: one still per participant per screen

The lens groups by **screen** across participants: one screen holds a tab per session, each with
its own still (`ScreenTab.t`, chosen as the moment that pins the most quotes) and its own pins
(`screen_text/screens.py`). The export's unit is that tab, a **(screen, session) still**, because
it is the one picture with one participant's quotes on it.

- **Time order is per participant.** Each recording has its own clock; there is no shared timeline
  across sessions. A participant's stills are ordered by their first visit to each screen
  (`ScreenTab.visits[0][0]`). A screen revisited later appears once, at its first visit.
- **Participants in code order** (`p1`, `p2`, …), as the Sessions lens lists them.
- **Each quote appears once**, on its own participant's still: that session's pinned quotes, then
  its other quotes on that screen (`loose`). This departs from the lens, which shows one screen as
  one place and lists everyone's quotes under whichever version is showing (`ScreensLens.tsx`,
  `said`). A frame per still carries only its own participant's words. The tab's cross-links
  (another participant's quote whose words appear on this still) are left out too: they would put
  one quote on two frames.
- **Hidden quotes are dropped** by the same rule as every other export (`export_core`).
- **Speaker codes, never names**, as on the existing Miro stickies (`board_layout.QuoteCard` has no
  name field). Codes are already the file-name convention for clips.

Scope is the whole project in v1. The All/Selected/Starred picker the other exports share
(`ExportDropdown`) can follow; selection on the Screens lens is per card, not per still, so its
meaning here needs a decision first.

## 3. One shared step: the shot list

All three outputs start from the same list, built server-side from `derive_screens` and the
project's quotes: per still, `{session_id, code, seq, screen_key, screen_name, t, crop,
quotes[]}` in the order above. One function, tested once, so the three cannot disagree about
which stills exist or what order they are in.

**Rendering a still at full size.** The lens asks for a scaled still (`GET …/screens/still`,
`w` default 1200, capped at 1600, cached as JPEG under `screen-text/stills/`). The export wants the
crop at its source resolution. The ffmpeg call moves out of the route into a function both use,
with `w=None` meaning "no scale"; the route keeps its cap.

## 4. A folder of images

The sibling is **clip export** (`routes/clips_export.py`, settled 10 Jul 2026): a folder, not a
zip; files copied from a manifest, never a glob; each export replaces the previous one; Show in
Finder after.

- **Names:** `p3-07.jpg` — participant code, then visit order within that session, zero-padded.
  Finder's name sort is then time order per participant. No screen names in file names: they are
  page titles and addresses, long and often unhelpful as names.
- **Where:** CLI and browser, `bristlenose-output/screens/`. Mac app, the same folder, then the
  native folder picker and copy, as clips do.
- **Anonymise:** nothing to strip — codes only, and ffmpeg's JPEG output carries no location
  metadata. The setting is obeyed by construction.
- **Cancellable, with a count**, through the clip export's job and chip pattern, since a large
  study is a minute of ffmpeg.

## 5. A clipboard of images

Copy every still, then paste into Miro or FigJam and keep sorting there.

**Measured 17 Oct 2026: file URLs.** Four stills written as file URLs (what Finder's ⌘C writes for
a selection) pasted as four images in FigJam and in Miro (Safari), in order, in a row. The second
candidate was not needed. The two that were considered:

1. **File URLs**, as Finder's ⌘C on a selection writes. If both canvases take that, the clipboard
   export is "export the folder (§4), then put its files on the clipboard" — and the browser
   fallback is Finder itself (select all, ⌘C).
2. **Several image items** (one `NSPasteboardItem` per still, `public.jpeg`).

So the clipboard copy is the folder export (§4) followed by its files on the pasteboard, in the
shot list's order: a Mac-app action over a bridge message, following `find-pasteboard-write`. The
browser Clipboard API cannot write files (Chrome writes one image per copy), so in the browser the
route to the same clipboard is Finder: Show in Finder, select all, ⌘C. That is why the folder's
manifest is a dotfile.

The copy belongs to the window that asked. Its chip remembers that it is a copy across a reload
(⌘R, Retry), so the files still reach the clipboard when the export finishes; no other window copies,
and a chip whose export a newer one has replaced (the status read's `job_id` differs) copies
nothing (RE#38, decision #35, 22 Oct 2026).

## 6. A Miro board

Built on the existing bridge (`board_layout.py`, `miro_client.py`, `routes/miro.py`,
`docs/design-miro-bridge.md`); a new board per export. **As built, 17 Oct 2026** (`2fb81386`,
`ebacacaf`, reworked the same day as below): `POST /export/screens/miro`, a background job with
progress and Cancel; `bristlenose/screens_board.py` lays it out; `screen_text/shots.py`
`journey` decides what goes on it.

**One frame per screen, everyone's quotes on it** (owner, 17 Oct 2026). Pooling all the feedback
on a screen is normal research practice, looking for consensus problems and edge cases, and it is
the expectation the lens already sets: a screen is one place for everything said about it. The
first build (a frame per participant per screen, a row per participant) was replaced the same day.

- **Every participant's screengrab of the screen, cascaded** (owner, 17 Oct 2026): the version
  the lens shows first (`default_tab`) in front, the others behind it, each 40 px further down and
  right, so a researcher can count them, peek, and keep the one that fits. Two views of "the same
  screen" often differ in what a participant was talking about; when they don't, the researcher
  deletes the extras. Each image is titled "P3 · Checkout" from its own still (Miro shows the
  title when it is selected). A version whose still or upload fails is left out and logged; only a
  screen with no still at all counts as skipped, and a refused front upload fails the board.
- **Journey order, left to right, in one row.** There is no shared clock across recordings, so a
  screen goes where it fell on average in its participants' own visit order; ties to the screen
  with more said about it.
- **Every quote stacked beneath the still, a new row for each participant**, in time order within
  a participant, four rectangle stickies to a row (together the still's width). Each quote appears
  once, under the participant who said it; the attribution line already names them.
- **Not placed round the still as the lens places them.** That placement rests on a participant
  reading the page's own words aloud, and "this bit over here" with a wave of the mouse never
  lands; on a board the team will rearrange, plain stacks are the reliable shape, and wires and
  connectors are out (owner, 17 Oct 2026). A Python port of the lens's placement rules, with a
  fixture holding it to the TypeScript, was built and removed the same day.
- **Everything in a frame is a child of it** (`parent` on create), so dragging a frame carries its
  still and quotes. The quotes board places stickies outside any frame (`design-miro-bridge.md`
  A9).
- **Frame titles are the lens's screen title**, and truncate at the frame's width as Miro draws
  them; Miro users zoom in to read them (owner: "let Miro do what it does"). No title text box.
- **Rectangle stickies on every board** (owner: "nearly always better"; `board_layout.STICKY_SHAPE`):
  a quote wraps in longer, fewer lines.

**Measured against Miro, 17 Oct 2026** (probe boards, then the real thing from a copy of
*IKEA with uxfriends*: 9 frames, 14–56 s):

- **Upload:** the settings go in a `data` part sent as a plain form field with a JSON content type.
  Attached as a file (with a filename) Miro answers 500, *"Failed to convert 'data'"*.
- **Parenting:** a child's position is its centre from the frame's top-left
  (`relativeTo: parent_top_left`); images and stickies both take `parent`.
- **No lock:** every lock field on PATCH is refused (code `2.0703`). The frame holds a picture with
  its quotes.
- **Frames refuse a new board for about half a minute**, with a bare 500 ("Internal error
  occurred"), and now and then later; stickies and images go through meanwhile. A refused frame was
  never found on the board afterwards. `create_frame` retries a 500, and before each retry looks for
  a frame with that title at that spot, so it cannot make two.
- **Miro sizes a sticky from its width and keeps the shape's proportion:** a rectangle is 0.651 as
  tall as wide (300 → 195.4), a square 1.146 (200 → 229.1). A layout must reserve the height Miro
  draws; the quotes board reserved 200 for a 240-wide square Miro drew 275 tall, so its columns
  overlapped until the shape and heights were corrected together (`b614da58`).

**Expected volume** (owner's scenario: 5 participants, 8 screens, 40-minute sessions; extrapolated
from one 18-minute session, where 31 quotes came out and 61% landed on a screen): 150–200 quotes
on 8 frames, 20–25 a screen, 50–75 on the screen people struggled with, which stacks about
13–19 rows deep under its still.

**Consent at the moment of export** (`design-miro-bridge.md`): on the Screens lens the panel and
the Mac sheet say the board will include every screengrab with its quotes.

**Not in v1:** FigJam as a target (`design-board-integrations.md`).

## 7. What changes when it ships

- **The Settings sentence** (`desktop.transcriptionSettings.readScreensHint`, all 21 locales) ended
  *"…Never sent to the AI, and not included in exports."* The clause was dropped on 17 Oct 2026
  (owner), with the exports on `main`: it now ends *"Never sent to the AI."*
- **Export classification:** the new routes are actions, not GET reads, so
  `tests/test_serve_export_coverage.py` is unaffected; the screens routes stay server-only in the
  HTML export.
- **Where the actions live** (owner, 17 Oct 2026): in the existing export surfaces, contextual to
  the Screens lens, as the toolbar already is — "menus dim, toolbars morph". The Mac toolbar's
  export popover on Screens gains **Copy Screens** and **Export Screens**, and its **Send to Miro**
  builds the screens board there (the quotes board on every other lens). The menu bar carries the
  two dimmed off the Screens lens. The browser's export dropdown shows Export Screens on Screens.

## 8. The weekend

**As built, 17 Oct 2026:** steps 1–7 are on `main` (`3db394fa`, `ab7696ce`, `2fb81386`,
`ebacacaf`); step 8 ran on a copy of *IKEA with uxfriends* (9 frames, 56 s). Still owed: the
by-hand checks.

Smallest first; each step ends usable and green.

**Saturday**

1. **Measure the clipboard** (§5) and Miro locking (§6). Decides the shape of step 4.
2. **The shot list** (§3) and full-size stills, with tests.
3. **The folder** (§4): route, job, manifest, CLI and browser; then the Mac folder picker.
4. **The clipboard** (§5), Mac app, on step 3's files or as image items.

**Sunday**

5. **The board model:** `board_layout` gains images, frames per still and parented children; pure,
   tested like `test_miro_board.py`.
6. **The client:** image upload and `parent`; a fake-client test of the whole push, which the
   existing export lacks.
7. **The SPA side:** compose each still's placements with `layout.ts`, send them, and the job's
   progress and Cancel in the panel.
8. **A real board** from a real study, dragged about as a workshop would.

## 8a. Where it stands — 17 Oct 2026, evening (for the next session)

All on `main`, not pushed. The weekend's arc, newest last:

- **Exports:** folder (`3db394fa`), Copy Screens + Export Screens on the lens (`ab7696ce`), Miro
  screens board (`2fb81386` → reworked `8926b870`, cascade `73015733`), review fixes
  (`0fc4193f`), removed interviews prune their exported stills (`09172ebf`).
- **All Miro boards** (quotes and screens), owner's decisions of 17 Oct: rectangle stickies
  (`b614da58`); no 300-character cut, only Miro's 6,000 limit (`3a5f1140`); long quotes split at
  **325** characters into at most three parts at sentence ends, with "…" (`da38b6f1`, `fe666b27`);
  every sticky **sized by its text**, 17 × √chars (the owner's hand), so the type is one size;
  parts **overlap by one x-height and step right by the same** (X_HEIGHT = 5), a square notch;
  each set **grouped** on Miro; a **"Break long quotes into multiple sticky notes"** checkbox, on by
  default, in the panel and the Mac sheet (`ea52bc36`).
- **FigJam session** imports `board_layout.quote_part_texts` (board-neutral parts) and leaves
  sizing, overlap and grouping to itself — FigJam stickies are fixed widths and ungrouped.

**Still owed:** the Swift suite since `ea52bc36` (the app builds; the suite has not run); a by-hand
check of Copy Screens from the sandboxed app; the sample boards are in the owner's Miro account
(the latest: quotes `uXjVEYp6kn0=`, `uXjVEYp1o9g=`, screens `uXjVEYpEdVM=`).

**Open with the owner:** an LLM choosing the breaks (sentence numbers only, never text; during
analysis, recommended, or on-machine at export) — asked, not answered.

## 9. Open

1. ~~Which clipboard shape works where (§5).~~ File URLs, in FigJam and Miro (17 Oct 2026).
2. ~~Can the REST API lock an item (§6)?~~ No: measured 17 Oct 2026 (§6).
3. ~~Where the three actions live (§7).~~ Settled 17 Oct 2026: contextual to the Screens lens, in
   the existing export surfaces (§7).
4. ~~A screen revisited later appears once, at its first visit (§2).~~ Overtaken: the board has a
   frame per screen (§6); the folder keeps one still per participant per screen.
5. ~~**Quote stickies are cut at 300 characters**~~ Removed 17 Oct 2026 (owner); only Miro's own
   6,000-character limit is guarded. Was: on both Miro boards (`MAX_QUOTE_CHARS` in
   `server/miro_export.py`, `_MAX_QUOTE_CHARS` in `routes/screens_export.py`), from the days of
   240-wide squares; FigJam's board document carries the full text. Remove the cut now stickies
   are 300-wide rectangles and Miro shrinks the type? Owner's call (raised by the FigJam session,
   17 Oct 2026).
6. **Withdrawn participants:** the pipeline's per-session prune does not touch
   `bristlenose-output/screens/` (files are named by participant code), so a withdrawn
   participant's stills stay until the next export rewrites the folder. Clear them on withdrawal?
7. **By hand:** Copy Screens from the sandboxed Mac app, pasted into Miro and FigJam (the probe
   that settled §5 ran unsandboxed).
