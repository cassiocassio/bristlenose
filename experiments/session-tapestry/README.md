# Session tapestry

An expandable timeline slice under each row of the Sessions grid, showing:
- section flags
- speaker clips on moderator and participant tracks
- sentiment bars (positive above the line, negative below)
- theme spans

The design mockups are `docs/mockups/session-tapestry.html` (first sketch) and `docs/mockups/session-tapestry-scale.html` (the scale rule, from measured transcript rates).

## Files

| File | What it is |
|---|---|
| `build.py` + `template.html` | Builds the tapestry from a real output folder, drawn in the real Sessions-grid markup with the shipped theme inlined |
| `colour_lab.py` + `colour-lab.html` | Samples frames from every distinct recording under a folder, so the clip-colour algorithm can be tuned live |
| `strip_lab.py` + `strip-lab.html` | Samples every recording at 4 fps as well as by keyframe, and draws scene stripes inside the tapestry's clips, so their opacity, floor and smoothing can be tuned live (see § Scene stripes) |
| `thumb_mockup.py` + `thumb-mockup.html` | The per-turn hover thumbnail, proposed 13 Oct 2026 and shipped the same day (§ Hover thumbnail): the timeline with one real frame 25% into each participant turn, stepped not scrubbed, with handles for open delay, warm reopen, swap rest, close grace, width, position and moderator-turn behaviour. Write to `trial-runs/_tapestry/` — it carries participants' screens. **One frame per colour scene was tried and rejected on 13 Oct 2026** (the per-scene commit and its revert carry the measurements): per-turn granularity, with the section flags above the lane naming where a frame sits, read better |

Both pages carry participant content, so write them to a gitignored, private folder:

```bash
.venv/bin/python experiments/session-tapestry/build.py <project>/bristlenose-output -o <private>/tapestry.html
.venv/bin/python experiments/session-tapestry/colour_lab.py <folder-of-projects> -o <private>/colour-lab.html --per-role 4
.venv/bin/python experiments/session-tapestry/strip_lab.py <folder-of-projects> -o <private>/strip-lab.html
```

The app's preview pane will not open a local page much over 500 KB. That is why `--per-role 4` is used and the thumbnails are downscaled. A normal browser opens the larger pages fine.

## Settled (6 Oct 2026)

- **Scale:** one shared scale per project, fitted to the longest session and held between 1 and 4 s/px. The speaker lane switches from clips to slivers above 2.5 s/px. Zoom runs from that fit down to 0.25 s/px.
- **Top lane:** sections, not s08 topics. "Topics" is not a product noun. ~~Each section is flagged at its first quote in the session~~ — since 17 Oct 2026 **every visit** is flagged: a new flag wherever the session's quotes move into another section, in time order, so a participant who returns to the basket is flagged there twice (`section_visits` in `routes/tapestry.py`, the transcript chain's rule). The first visit to a section is the anchor the row's User journey chain links to. The chain itself keeps the report's section order and first arrivals, by design: it is the simple version for comparing across the grid, and the timeline and the transcript carry the messy real path.
- **Clip colour:** the per-turn scene colour. These are the colour lab's defaults. The pipeline runs steps 1–6; step 7 is a lab handle only (see below):
  1. Crop black bars: drop an edge row or column when 85% of its pixels have luma below 30.
  2. Ignore pixels with luma below 18. Keep whites.
  3. Cluster the remaining pixels in OKLab, k = 4.
  4. A cluster is eligible only if it holds at least 15% of the pixels.
  5. Pick the most colourful eligible cluster.
  6. Tone it: map OKLab L into 0.42–0.88 and multiply chroma by 1.4.
  7. (Lab only.) If the cluster sets of two speakers are within a scene distance of 6, treat them as one scene and do not assign per-speaker colours.

## In the pipeline (6 Oct 2026)

The clip colour is computed by `bristlenose/utils/scene_colour.py`, which `Pipeline.run()` calls just before render. It writes `.bristlenose/intermediate/scene-colours/<session>.json`: one `{t0, t1, speaker, colour, share}` per turn. The file is cached by the video's identity and the turn boundaries, so a re-run costs nothing until the recording or the speaker turns change. A failure logs a warning and leaves the session without colours, the same as thumbnails. A cloud placeholder (an iCloud or OneDrive file not yet downloaded) is read like any other file, through `ensure_materialised`, as thumbnails are. Don't add a skip for dataless files: Bristlenose manages no storage policy, and an attempt at one was abandoned on 6 Oct 2026.

**The module's constants are the colour lab's defaults.** To retune, regenerate the lab, move the handles, then copy the new values into the module and into the `P` table at the top of `colour-lab.html` in the same commit. The lab still carries the per-speaker distinctness and same-scene handles. The pipeline doesn't use them, because the lab showed the picture never changes with who is speaking.

**In the app (6 Oct 2026):** `GET /api/projects/{id}/tapestry` (`bristlenose/server/routes/tapestry.py`) serves every session's turns, section flags and quotes from the database, so hidden quotes, quote edits and heading renames apply. It matches each turn to a scene colour by time, so a speaker edit made in serve doesn't orphan the colours. The route is embedded in the HTML export. `frontend/src/components/SessionTapestry.tsx` draws it as a disclosure under each Sessions-grid row. The chevron sits in the ID cell, so the grid gains no column. The component is lazy-loaded; on first paint are only `utils/tapestryScale.ts`, the closed strip (`components/TapestryPreview.tsx`) and `utils/sceneInk.ts`; the open/close animation (`utils/tapestryMotion.ts`) is a dynamic import, prefetched once the grid has timelines. The CSS is `bristlenose/theme/organisms/session-tapestry.css`.

Not wired yet:
- `analyze` (no video) and render-only runs (serve's `_auto_render`) don't compute colours.
- Projects analysed before this change show neutral clips until their next `run`.
- ~~Under a progressive first analysis readable rows show neutral clips until render~~ — closed
  the same night: the readable chain computes each session's colours before recording it merged
  (`bristlenose/readable_chain.py`, `88a27592`).


**Tuning lives in `frontend/src/utils/tapestryTuning.ts`, and the playground stays (decided 6 Oct 2026).** The defaults there are the shipped type steps and container padding. Under `serve --dev`, a slider icon beside the zoom opens `TapestryPlayground`. It moves each kind of text along the existing `--bn-text-*` ladder, the popover padding along `--bn-space-*`, and the pixel paddings, bar width and bar click margin only through the snapped lists in `PAD_STEPS`. It then lists the changes to commit. It is dev-only and code-split, so it is not dead code: keep it.

## Interaction (shipped 6 Oct 2026)

- **Zoom is shared, scrolling is not.** The zoom control sets one scale for every open slice; each slice scrolls horizontally on its own.
- **State survives Back.** Which slices are open, the zoom and each slice's scroll position are kept per project (module state plus sessionStorage key `bn-tapestry-view:<projectId>`, in `utils/tapestryScale.ts`), so visiting a transcript and returning shows the same page.
- **Speaker track from the role, not the tag.** The route sends a `team` flag per turn from the speaker slot's role; the client falls back to the first letter of the displayed code. A recode in serve therefore moves a turn between tracks (`docs/design-people.md` §J7).
- **Clicks jump.** A click on the speaker lane opens the transcript at exactly that moment; a click on a section flag opens it at that visit's first quote. While the pointer is on the speaker lane, the nearest timecode tick lights in accent blue.
- **Sentiment marks are 6 px wide** (`barW`). Each carries an invisible click target 2 px wider (`hitExtra`) and at least 12 px tall, which stops halfway to a neighbouring mark, so close marks never steal each other's clicks.
- **The quote is a floating popover** under its bar, with an arrow, an X, and ← → to step between quotes. An outside click or Esc closes it (Esc is claimed in the capture phase, unless a modal has made the app inert), and focus returns to the bar. Only one slice holds an open quote at a time.
- **Themes are spans** from a theme's first quote to its last, packed into up to three rows. Each carries its name in full on a chip at the span's start; a chip is cut only at the slice edge, and its fill fades out over its last 20%.

**Decided (6 Oct 2026): the zoom has no keyboard shortcut.** ⌘+ and ⌘− stay the browser's text zoom, because readers rely on text size more than they would on a timeline zoom. Don't add a shortcut.

**Review calls (6 Oct 2026):**
- **Observers share the Moderators track.** "Moderators" stands for everyone who is not a participant; they do not get a track of their own.
- **Theme highlighting stays hover-only for now**, and section flags are mouse-only. The popover shows a quote's section or its theme, not both. Left as is for the moment.
- **A screen-reader summary of each timeline needs thought.** Today the timeline reads as disconnected text. Tracked in the 100-days plan.
- **Two sections renamed to the same name share one flag.** An accepted edge case.
- **Dimmed bars at 0.4 opacity** are fine for v1.
- **The export carries quote text twice** (in `/quotes`, and up to 400 characters each in `/tapestry`). Deferred to v1.1.

**Open after the second review (6 Oct 2026), for the owner to decide:**
- While a quote is open, the slice takes Esc and the arrow keys first, ahead of other surfaces (the person picker's Esc, the grid's arrows).
- The sessionStorage key falls back to project id `1` when the page has none, so two such projects in one tab share a view.
- Theme chips can now overlap a neighbouring chip on the same row, since names are no longer cut.
- Scroll is stored in pixels, not seconds, so a restored position drifts if the zoom changed.
- Clicking a slice's scrollbar counts as an outside click and closes the popover; the popover also stays open when its bar scrolls out of view.
- Accessibility: Prev/Next moves focus off the bar; the popover has no role or accessible name; the timecode button's name doesn't say it opens the transcript; a selection is announced twice; Option-click "open all" has no keyboard path; in dark mode the span bar shows through the chip's fade at about 4.4:1.

## The strip and the open motion (shipped 17 Oct 2026)

Designed in `docs/mockups/sessions-timeline-strip.html` (option C of three; the commentary there carries every number and the owner's calls). Commits `80d5c745`, `0645c6f4`, and `1e77fb37` for the ink.

- **The closed timeline is a strip under every readable row** (`components/TapestryPreview.tsx`): the whole interview, participant turns only, merged into one lane when a session has several, in scene colour on the timeline's own track, so the gaps are where the team spoke. It fills the row whatever the session's length; the open timeline uses the shared scale, so a short session keeps its length on open and a long one stretches. 4.5 px, a quarter of the open participant clips; clips at 60% (`--bn-tp-preview-opacity`) under a 0.5 px keyline; no text. **Hover is a tint and nothing else** (`--bn-tp-preview-track-hover`): a playhead on a strip too small to read was too much, and a strip that grows under the pointer is web-page manners, not Mac ones (owner, 17 Oct 2026).
- **Clicks:** the strip opens the timeline **on the moment clicked**, scrolled so that moment sits in the middle (owner, 17 Oct 2026, `0a99ffb7`), and, while it fades out, closes it, so a double-click cannot fall through. Anywhere else on the row opens the transcript (`729033bb`). The strip is `aria-hidden` and out of the tab order: the disclosure is the keyboard and assistive route to the same timeline.
- **Opening from a click animates** (`utils/tapestryMotion.ts`): the slice unfolds (220 ms); the strip's clips spring into the participant lane at its height and the open scale (320 ms, about 8% overshoot); everything else lands in a left-to-right domino, 60 ms plus its place across the visible width × 150 ms; and each word of the row's journey chain flies to its section's first-visit flag (380 ms), crossing where the user's path left the report's order. A revisit's flag has no word and fades in 120 ms later. The chain's arrows fade in place and the chain keeps its space while the timeline is open (its words live in the flags). Closing flies the words home and folds. None of it under reduced motion or `.bn-no-animations`, for Option-click, or for a timeline restored open on return.
- **One label ink for the screen** (`utils/sceneInk.ts`): names on scene-coloured clips used to alternate dark and white, picked per clip by contrast; now the grid picks the ink most clips prefer, dark on a tie. On the Talismanic study dark won on 281 of 282 clips, its weakest at 4.1:1.
- **Keyboard flags (6033b0f4, 17 Oct 2026):** an open timeline hides the chain's links, and the flags were mouse-only. Flags are now buttons with one roving Tab stop per timeline (← → move, Return or Space jumps), shared with the transcript's sticky timeline, which draws the same `SessionTapestry`.

## Measured

- **The video never flips with the speaker.** Across 25 distinct recordings in the maintainer's test corpus, all 12 with two speakers showed the same picture whoever spoke (scene distance 0.3–4.6). The speaker is shown by the track; the colour shows what was on screen.
- **Keyframe colour sampling is cheap.** It takes about 1.5 s per hour of video (15 s for the 9 hours of the FOSSDA oral histories), cheap enough to run in the pipeline beside thumbnail extraction.
- **Some transcripts have coarse or mislabelled turns** (FOSSDA s5 has the narrator on `m1` from about 10 minutes in). The slice makes this visible at a glance.
- **Quote extraction does not record which words carried a quote's sentiment.** `verbatim_excerpt` is only the first 200 characters of the quote.

## Scene stripes (shipped in serve, 12 Oct 2026)

The clip keeps its one scene colour, and over it, at an opacity, run stripes of what was on screen
moment by moment, so a change of environment (call → share → terminal) shows inside the bar without
the bar losing its track identity. A notch above the lane marks each change. **Notches parked 13 Oct
2026** (`featureFlags.sceneNotches`, off): with the strip in the clips the change is already visible,
and the owner is unsure the second mark adds value. The edges are still computed and served.

**What ships.** `bristlenose/utils/scene_strip.py` samples every frame at 4 fps (one sample per
pixel at the maximum zoom), takes the mean OKLab of each frame's kept pixels, tones it into a light
band (0.64–1.0, the strip's own band, above the clip's 0.42–0.88) and writes
`.bristlenose/intermediate/scene-strips/<session>.json`: a 1×n RGB PNG (a 1-hour session is a few
KB) plus the notch times, cached by the recording's identity, written whole and renamed into place.
The first sample's time is read from ffmpeg (`showinfo`), never assumed to be zero: a stream that
starts late (an edit list, a trimmed container) keeps its stripes and notches on the transcript's
clock, and a decode whose frame and time counts disagree is refused rather than mis-paired. One
recording per session: the first imported source file whose suffix is in the pipeline's
`VIDEO_EXTENSIONS` and which exists on disk (the importer's own `file_type` is narrower).
**Serve computes it, never the pipeline** (`bristlenose/server/scene_strips.py`): a daemon thread
started by the app lifespan, after each `run_completed`, and on every change to the events log,
which is what starts it again after a run that failed, was cancelled or died and so wrote no
`run_completed`. It defers while the project's latest run is in progress (liveness re-checked, so a
run that died without a terminus does not defer it for good), stops between sessions when a run
starts mid-pass, and a `start` during a running pass asks for another pass, so sessions a run
added meanwhile are not missed. The tapestry route serves whatever exists and says
`strips_pending` while the job runs; the Sessions grid then refetches, from 5 s apart backing off
to 30 s for a few hours, so the stripes arrive without a reload. Every refetch (a session import, a
speaker write, a strip poll) merges layer by layer (`frontend/src/utils/tapestryMerge.ts`, since
`88a27592`): turns, sections, quotes and strip are each kept by reference when unchanged, so an open
quote popover survives and an idle poll re-renders nothing.
`SessionTapestry.tsx` draws one `<image>` per track from the first sample's time,
`preserveAspectRatio="none"`, clipped to that track's clips, at the track's CSS opacity
(participant 0.7, moderator 0.75), with the clip's edge redrawn over it and a notch per edge above
the tracks, notches past the recording's end dropped. Kill switch: `BRISTLENOSE_SCENE_STRIPS=0`.
The HTML export embeds whatever strips existed when it was made and never polls its own embedded
`strips_pending`. Strips do not depend on the run kind: any project opened in serve whose sessions
have a video source file gets them, a transcribe-only project included; the only projects without
them are CLI runs never opened in serve, since the static render is sealed and does not draw the
tapestry. **Under a progressive first analysis** (phase 1, Mac, 12 Oct 2026) a session readable
mid-run has no strip until the run ends and the job has decoded it; its scene colours do arrive
with it, since the readable chain writes them per session (`88a27592`).
`docs/design-progressive-lenses.md` §7 carries whether the strip job should run per readable
session too.

**Notches are measured on the untoned means**, with the mean of the 2 s before a moment against
the 2 s after it, threshold ΔE 14, strongest within the window. Toned space was tried first and hid
the Teams session's call-to-share transitions (6.5 toned against 17.9 untoned). Calibration over the
28-recording corpus, notches per recording:

| threshold | gallery calls (9, up to 100 min) | Teams usability session, 18 min | screen recordings, 3–4 min |
|---|---|---|---|
| ΔE 10 | 0–1 | 17 | 12–19 |
| ΔE 14 | 0–1 | 9 | 11–14 |
| ΔE 18 | 0–1 | 1 | 8–10 |

At 14 a gallery call gets at most its title card, and a usability session with page switches one
every couple of minutes. The lab's notch handle uses the same space; `strip_lab.py` is kept for
retuning, and its defaults are the module's constants (strip tone, notch threshold and window) plus
the owner's opacities. One difference from the shipped sampler: the lab calls bare `ffmpeg` without
`showinfo`, so it places a late-starting stream at time 0 where the product does not.

**Cost, measured 12 Oct 2026** (software decode to 32×18; VideoToolbox was 18× slower, the per-frame
download dominates). One sample per pixel at the maximum zoom (0.25 s/px) means 4 fps:

| source | keyframe gap | keyframes only (today) | every frame at 4 fps |
|---|---|---|---|
| Teams 1080p, 18 min | 6 s fixed | 0.7 s | 2.4 s |
| YouTube-style 720p, 22 min | 10 s fixed | 0.6 s | 2.9 s |
| macOS screen recording 3456×2234 @120 fps, 79 s | ~1 s | 5.3 s | 9.1 s |

So a call recording costs about 8 s per hour of video for the dense pass, and a 4K 120 fps screen
capture about 7 minutes per hour, under a 3,600 s decode limit per recording. **What ships decodes
every frame of every recording**: the keyframe column above is the per-turn colour's pass, not a
mode of the strip, and the adaptive rule once considered here (dense only where keyframes are more
than about a second apart) was not built. The lab's own numbers are higher because it computes the
per-frame colour in pure Python per frame; the per-video cost is shown on the page.

**Decided in conversation, 12 Oct 2026:** the dense pass is a local enhancement that may arrive after
the run, and must not gate the report being readable. Stripes go on both tracks, since the scene is a
property of the moment, with the moderator track at a lower opacity if it should sit quieter.

**The lab page.** Each recording is drawn as the real lane geometry: track, moderator and participant
clips in the shipped turn colour, stripes source-atop at the track's opacity. Handles: stripe source
(keyframes as today, 4 fps, or 4 fps averaged down), zoom (fit to the maximum), per-track opacity, a
floor that hides stripes within a ΔE of the clip colour so a steady scene stays flat, a median window
against shimmer, notch threshold and window, and the tone handles shared with the colour lab. The raw
row above each lane is the same data at full strength, the movie-barcode view. Worst cases to look
for: a uniform web session, a scrolled or animated share, a gallery call with people moving, the 4K
capture. Transcript turns are used where a recording has one; otherwise a fixed 15 s / 45 s
alternation stands in. One thing the keyframe view exposes: a recording's first keyframe can be a
splash or transition frame, which the per-turn colour already survives (it clusters the whole turn)
but a stripe shows.

## Hover thumbnail (shipped in serve, 13 Oct 2026)

**Decided in the mockup** (`thumb-mockup.html`; its handles stay for retuning, and the shipped values
are the `thumb` group in `frontend/src/utils/tapestryTuning.ts`, movable in the dev playground):

- **Frames.** One per participant turn, 25% in. Plus one at each colour change inside a participant
  turn: changes at ΔE 8 on the untoned 4 fps means (`scene_strip.CHANGE_DE`, carried in the strip
  record as `changes`), a change within 2 s of the turn's start ignored, each later stretch framed
  2 s after its change, or halfway through a stretch shorter than 4 s. Measured: 86–112 frames an
  hour; on the Ikea project 5, 21 and 13 frames, taken in 2–5 s a session.
- **Size: 160 px wide**, the size it was drawn at. Small, medium and large were tried on 13 Oct; the
  size handle stays in the mockup in case it is reopened. Frames are taken 320 px wide.
- **Position:** below the tracks, so the section flags stay visible above. It follows the pointer,
  kept within the slice's sides.
- **Timing:** open after 700 ms at rest, reopen at once within 1 s of a close, swap after 100 ms at
  rest (stepped, never scrubbed), close after a 300 ms grace. A lane crossed without the preview
  opening does not count as a close.
- **Over a moderator turn** the last participant frame holds. The stretch the frame stands for is
  outlined. The caption is the timecode only.
- **Click:** the transcript jump as before; while a change frame shows, the jump lands 1 s before
  the change. That includes a change frame held over a moderator turn, as in the mockup: the frame
  on screen decides, not where the pointer is.
- Mouse-only and `aria-hidden`: the transcript and the strip carry the same information.

**As built.** `bristlenose/utils/turn_frames.py` selects the frames (`select_frames`) and takes them
with ffmpeg; serve's strip job (`server/scene_strips.py`) takes them after each session's strip, from
the turns `server/tapestry_turns.py` derives (the one definition the route draws from too). Each
session's frames are one JSON record, `.bristlenose/intermediate/turn-frames/<session>.json`, holding
base64 JPEGs, cached by the recording's identity and the selection, written whole and renamed into
place. **Every failure is written down:** an unreadable recording, a download that timed out, ffmpeg
missing or some frames not taken all leave a record of the selection with `complete: false`. The
route asks for a pass only when the selection on disk differs from the turns it draws (a paragraph
split, joined or moved, a speaker recoded), and only for a session whose recording the job can
reach, so no failure can make it ask on every poll; an incomplete record is never a cache hit, so the
job's next ordinary pass (serve starting, a run completing) tries again. The tapestry route sends
only `frames_key`; the grid fetches `GET /api/projects/{id}/sessions/{sid}/turn-frames` the first
time the pointer enters that slice, inside the open delay, behind the bearer token — frames of
participants' screens are never under the unauthenticated `/report/assets/`. A failed fetch is not
retried until the key changes. The HTML export classifies the route server-only and the SPA never
fetches it in an export. Frontend: `utils/tapestryThumb.ts` (one controller for the page, so the
warm-up and the grace span sessions), `components/TapestryThumb.tsx` (the outline in the SVG, the
preview as a fixed layer on `document.body`).

**Not tested:** that a frames failure leaves the next session's strip alone (the job wraps the
frames step per session; the smoke fixture has one session, so no test can tell the wrap from the
job's own catch-all).

**Later:** the screen-text session (`docs/design-screen-text-search.md`) found that a text diff
every 4 s catches what colour changes miss. If OCR ships, the thumbnails could take their frames
from those moments.
