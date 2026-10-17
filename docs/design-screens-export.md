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

## 6. A Miro board

Built on the existing bridge (`board_layout.py` layout, `miro_client.py` transport,
`server/miro_export.py`, `routes/miro.py`, `docs/design-miro-bridge.md`); a new board per export,
as today.

**Layout: one row per participant, left to right in visit order.** Each still is a Miro **frame**
titled so people can say it out loud — `P3 · Checkout` (code, then the lens's screen name). Rows
are stacked in code order, with a gutter between frames for the team's own stickies.

**Inside each frame:**

- **The still**, uploaded as an image.
- **Pinned quotes placed as the lens places them**, in the margins round the still: which edge,
  how a column stacks, how a band wraps, and the researcher's saved arrangement where there is one.
  _Changed 17 Oct 2026 from "the SPA composes and sends positions": the Mac app's Send to Miro sheet
  calls the server with no web page in the loop, so the server places them._ The lens's rules are
  ported to Python (`bristlenose/screens_board.py`) and both copies are held to one fixture,
  `tests/fixtures/screens-layout-contract.json`, asserted by `tests/test_screens_board.py` and
  `layout.contract.test.ts`. A Miro sticky is a fixed size, so nothing needs measuring.
- **The session's other quotes on that screen** in a row beneath the still.

**Workshop requirements** (§1):

- **Everything in a frame is a child of it** (`parent` on create), so dragging a frame carries its
  still and quotes. Today's export places stickies at absolute positions outside any frame
  (`design-miro-bridge.md` A9); that is fine for two columns of quotes and wrong here.
- **The still is locked**, so moving stickies about does not drag the picture out. Whether the REST
  API can lock an item is unverified (Saturday, with the clipboard check). If it cannot, the frame
  parenting still carries it, and the board says nothing.

**Measured against Miro, 17 Oct 2026** (a probe board, then a real one from a copy of
*IKEA with uxfriends*: 9 frames in 56 s, every image and sticky inside its frame):

- **Upload:** the settings go in a `data` part sent as a plain form field with a JSON content type.
  Attached as a file (with a filename) Miro answers 500, *"Failed to convert 'data'"*.
- **Parenting:** a child's position is its centre from the frame's top-left
  (`relativeTo: parent_top_left`); images and stickies both take `parent`.
- **No lock:** every lock field on PATCH is refused (code `2.0703`). The frame is what holds a
  picture with its quotes.
- **Frames refuse a new board for about half a minute**, with a bare 500 ("Internal error
  occurred"), and now and then later; stickies and images go through meanwhile. A refused frame was
  never found on the board afterwards. `create_frame` retries a 500, and before each retry looks for
  a frame with that title at that spot, so it cannot make two.
- **A square sticky is 1.146 times as tall as wide** (200 wide came back 229.1).

**Transport, new in the client:**

- `POST /v2/boards/{id}/images` as a file upload (multipart). The client creates frames, stickies
  and text today; nothing uploads.
- `parent` on frames' children, and positions relative to the frame. Verify against the API rather
  than assume.

**Volume.** Ten participants by a dozen screens is over a hundred frames, a hundred uploads and
several hundred stickies. Today's export is one request with no progress and a fixed backoff on
429. This one runs as a background job with a count and Cancel (the clip export's pattern; the
bridge doc's deferred A7), and a failure part-way keeps the existing "board left incomplete" result
with the board's link.

**Consent at the moment of export** (`design-miro-bridge.md`): the panel says the board will
include screenshots of participants' screens as well as quotes.

**Frame titles truncate at the frame's width** ("P1 · Kitchenware & t…"); Miro shows the whole
title as the board is zoomed in. Left as Miro draws it (owner, 17 Oct 2026: "this is just a thing
that Miro does and Miro users will be used to it"), so no title text box inside the frame. The
same goes for size: a still 1,200 wide with stickies 300 wide reads at a workshop's zoom, and is
left as it is ("let Miro do what it does").

**Not in v1:** leader lines (a Miro connector needs an item at each end; a small dot at the pin
point would do, later); FigJam as a target (`design-board-integrations.md`).

## 7. What changes when it ships

- **The Settings sentence** (`desktop.transcriptionSettings.readScreensHint`, all 21 locales):
  *"…Never sent to the AI, and not included in exports."* The last clause becomes untrue with the
  first export to ship. New English settled first, then the locales; it changes in the same
  release, not before.
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
by-hand checks below §9, and the Settings sentence (§7).

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

## 9. Open

1. ~~Which clipboard shape works where (§5).~~ File URLs, in FigJam and Miro (17 Oct 2026).
2. ~~Can the REST API lock an item (§6)?~~ No: measured 17 Oct 2026 (§6).
3. ~~Where the three actions live (§7).~~ Settled 17 Oct 2026: contextual to the Screens lens, in
   the existing export surfaces (§7).
4. A screen revisited later appears once, at its first visit (§2). Right for a workshop, or should a
   return trip get its own frame?
