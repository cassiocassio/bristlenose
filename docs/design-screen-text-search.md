---
status: proposal
updated: 13 Oct 2026
---

# Searchable screen text

**Status: exploratory proposal, 13 Oct 2026. Nothing here is built and nothing is decided; the owner
decides whether it is.** Method and every number below:
[`experiments/screen-text/README.md`](../experiments/screen-text/README.md).

## 1. The problem

A researcher remembers the moment, not the words. "The bit where she got the *Die Planung kann nicht
geöffnet werden* error", "when he hit the postcode dialog". If the participant never read the dialog
aloud, no search over the transcript finds it, and the researcher scrubs the video. In a usability
session most of what matters is on the screen: the dialog, the error, the price, the button they did
not see.

The proposal: read the text on the shared screen at moments that matter, and make it searchable, so
typing a dialog's words lands on the moment it appeared and the transcript paragraph being spoken then.

This builds on the session timeline's scene strip (`bristlenose/utils/scene_strip.py`, computed by
serve in the background, `bristlenose/server/scene_strips.py`) and on the hover-thumbnail work in
`experiments/session-tapestry/thumb_mockup.py`, which picks one frame per participant turn and was
heading for one more frame at each colour change inside a turn.

## 2. What the measurements say, in one table

Two real sessions (38 and 18 minutes, both IKEA shopping flows shared over Teams at 1080p), one
dark-mode desktop capture, a synthetic terminal; 232 hand-written search targets on 11 frames; a dense
OCR sweep every 2 s as the oracle for coverage.

| question | answer |
|---|---|
| Can OCR read call-recorded UI well enough to search it? | **Yes, on the Mac.** Apple Vision (accurate) finds 98% of non-personal targets by the shipped search rule, at 0.15–0.18 s and ~0.13 CPU-s a frame. RapidOCR 96%, at ~5 CPU-s a frame and 1.4 GB. Tesseract 59–74%. |
| Is a frame at each colour change enough? | **No.** The thumbnail plan's frames capture 44–61% of text that stays on screen 4 s or more. 55–62% of text changes have no colour change within ±3 s (white page to white page). |
| What is enough? | OCR every 4 s and keep what changed: 84–87% of ≥ 4 s episodes, ~150 kept moments an hour, 900 OCR calls an hour. |
| Keep the full-resolution frames? | **No.** 73–555 KB each, and the recording already holds every one of them: any frame comes back in 0.11 s. Keep text, boxes and times: ~230 KB an hour (45 KB gzipped). |
| Does the PII stage protect it? | **Poorly.** Presidio catches 16 of 26 personal targets (15/17 names, 1/6 bookmark titles, 0/3 postcodes) and damages 27 of 202 ordinary UI strings. |
| Is there a better privacy tool? | **Stickiness.** Personal chrome (names under video tiles, bookmarks) is on nearly every share frame; content is not. Dropping lines on ≥ 50% of a session's share frames removes 17 of 19 personal targets and costs 11 of 137 content targets. |
| Cost for a 5-hour project | **Mac: ~12 minutes** of background work, mostly on the Neural Engine. **Linux/Windows with RapidOCR: ~2.5 hours** at 2 threads. Index ~1.2 MB. |

## 3. Options and recommendations

### 3.1 Which frames to read

| option | ≥ 4 s episodes captured | OCR calls / h | notes |
|---|---|---|---|
| thumbnail frames (turn + colour change in a participant turn) | 44–61% | 86–112 | free if thumbnails ship, but misses long same-colour stretches; a 14-minute participant turn gets frames only at colour changes |
| fixed interval, 10 s | 79–80% | 360 | simple, wasteful on talking heads |
| edge-map diff, no OCR in the loop | 77–89% | 390–970 | 5 ms a frame, but moving faces trigger it; would need the filmstrip masked |
| **OCR every 4 s, keep a moment when the lines change** | **84–87%** | **900** | the detector *is* the reader; one decode pass |

**Recommend OCR every 4 s with text-diff**, on the Mac. The one-pass decode at that rate costs about
9 s an hour of 1080p video (measured 5.8 s for 38 minutes at one frame per 2 s). It can share the scene
strip's decode with an ffmpeg `split`, so the recording is read once for both.

**And let the thumbnails take their frames from it.** The text-diff moments are the moments the screen
visibly changed in a way a person would read; they may be a better thumbnail set than colour edges.
That is a question for the thumbnail mockup, not a decision here.

### 3.2 Keep or discard the full-resolution frames

| option | 5-hour project | notes |
|---|---|---|
| keep full-res PNG | ~350 MB (750 kept frames × 475 KB) | a second copy of every screen, PII included |
| keep full-res HEIC / JPEG q5 | 55–65 MB | same, smaller |
| keep 1280 px JPEG | ~40–60 MB | text mostly still legible |
| **OCR, then discard; keep text + boxes + times** | **~1.2 MB** | the recording is the archive |

**Recommend discard.** The recording is already in the project and a frame comes back in 0.11 s, so a
stored frame buys nothing a seek cannot, and it duplicates the most personal data in the project into
a second place to govern. A search result that wants a picture asks for one (§3.4), extracted on demand
at 320 px, the thumbnail size, or the existing hover thumbnail if one exists for that moment.

### 3.3 Which engine, on which channel

| channel | engine | added size | cost per frame | verdict |
|---|---|---|---|---|
| Mac app (sandboxed sidecar) | Apple Vision via pyobjc | ~7 MB of wheels | 0.15 s, ~0.13 CPU-s, 180 MB | **recommended** |
| Mac CLI (PyPI, Homebrew) | Apple Vision via pyobjc, as part of the `apple` extra | same | same | **recommended**, same code path as the app |
| Linux / Windows CLI, Snap, Copr | RapidOCR, an optional extra | ~75 MB of wheels, 10 dependencies, OpenCV | 2.0 s at 2 threads, 1.3 GB | possible, heavy; owner's call (§6) |
| Linux, from the distribution | Tesseract (system package) | 25 MB + leptonica | 0.4–0.8 s | **not recommended**: 59–74% |

Notes that matter for the choice:

- **Vision reaches the sidecar through pyobjc, not a helper.** `pyobjc-framework-Vision` calls the
  system framework from Python, so the CLI on a Mac and the sidecar run the same code
  (`docs/design-modularity.md`'s no-fork principle). Vision is a system framework, needs no
  entitlement, and is used by sandboxed App Store apps; a sidecar run under the sandbox has **not**
  been tried here and must be, before anything is promised. A Swift helper executable (like
  `desktop/mcp-helper/`) would also work but adds a fifth signed executable and leaves the Mac CLI
  without OCR. The host app doing OCR itself is ruled out: it forks the code path.
- **The App Store question does not arise for Vision**: it is code that ships in the OS. RapidOCR's
  models are data and could be fetched on demand, but its code (OpenCV, shapely, pyclipper) would have
  to be bundled (§2.5.2, as `docs/design-redact-pii.md` sets out for spaCy). On the Mac there is no
  reason to carry it.
- **Vision fast is not a cheap Vision.** It scored 29% and garbles characters (`Get instsni benefws`).
  Use accurate.
- **Languages.** German was read correctly under Vision's default setting. CJK needs Vision's
  recognition languages set (from the project's language), and RapidOCR's default model is
  Chinese–English. Neither was measured on CJK here.
- **RapidOCR on all cores takes the machine.** 5 CPU-s a frame; capped at 2 threads, 2 s a frame. A
  background job must run it capped, which is why a 5-hour project costs about 2.5 hours there.

### 3.4 Where it surfaces

**Search.** The settled engine for project-wide search is SQLite FTS5 shared by CLI, SPA and MCP
(`docs/design-search.md` D1); slice 1 is TypeScript over data the SPA holds. Screen text should **not**
be shipped to the SPA wholesale: ~1 MB of text a project, most of it never searched, and all of it
personal-data-dense. It is a server-side search from the start, in a POST body (the search doc's §9:
query strings reach access logs).

A hit is a **moment**, not a quote. The result row:

```
[320 px frame, the matched line outlined]   "Die Planung kann nicht geöffnet werden"
                                            On screen 20:43–20:51 · Session 1 · p3
                                            p3, 20:41: "…the paragraph being spoken at that moment…"
```

- The outline comes from the stored box, drawn over a frame extracted on demand.
- The third line is the transcript paragraph covering the moment's start (or the one before it), so
  the researcher sees what was on screen and what was said at once.
- **The jump** opens the transcript at that second (the existing `#t-<seconds>` fragment,
  `frontend/src/utils/reportHref.ts`) with the video player cued to the start of the episode. One
  moment per episode, not per frame: a dialog on screen for 8 s is one result.
- In the Sessions lens, the timeline can mark the moments a search matched, as a lane of ticks under
  the tracks. **That data must not ride in the tapestry payload**: the tapestry route is embedded in
  the HTML export (`EMBED_PATH_TEMPLATES` in `server/routes/export.py`). Screen text gets its own
  route, classified `SERVER_ONLY_PATH_TEMPLATES`, which `tests/test_serve_export_coverage.py` forces
  someone to decide explicitly.

Where it fits the search roadmap: the results pseudo-lens (idea 04) and Transcript Find (idea 06),
with "On screen" as its own group in the suggestions menu, after people and tags. Not the Quotes lens:
a screen moment is not a quote and must not be counted as one.

**The chat lens and MCP.** An agent citing screen text ("the participant hesitated at the *Weiter als
Gast* step") is the most interesting use and the most dangerous one. The grounding core's invariant is
that speakers are known by code only and never joined to anyone outside the study
(`server/grounding.py` `INVARIANTS`); screen text is full of exactly those people. **Recommend: not in
MCP or the chat lens in the first build.** If it comes later, as a citation kind of its own (session,
start, end, line), only stickiness-filtered and redacted text, behind the per-project agent access
switch.

### 3.5 Privacy

Measured: **every real frame carried personal data.** Names under the video tiles, browser bookmarks
and tab titles, a postcode typed into a checkout form, a delivery address, and on one desktop capture
a chat sidebar listing the presenter's colleagues. That last kind is the hardest: **third parties who
are in no consent form at all**, captured because someone shared a whole screen.

The model this proposes:

1. **The index stays in the project, private, like `transcripts-raw/`.** It lives under
   `.bristlenose/intermediate/screen-text/`, alongside the scene strips. It is the researcher's
   working data: they were in the session and saw the screen, which is the same reasoning that keeps
   raw transcripts on disk (`docs/design-redact-pii.md` D4).
2. **It never leaves.** Not in the HTML export, not in the anonymised outputs, not in clip or quote
   exports, not in the MCP endpoint or the chat lens, not in support bundles, **and never sent to the
   LLM.** That last one matters more than the others: the analysis is a cloud call
   (Claude, ChatGPT, Gemini), and feeding screen text into quote extraction or themes would send
   bookmarks, colleagues' names and typed addresses to a provider. Any future use that sends screen
   text onward is a new decision with its own consent copy (§6).
3. **Index what changes, not what stays.** Lines present on half or more of a session's share frames
   are dropped before indexing: they are chrome (names under tiles, bookmark bars, tab strips, chat
   sidebars), and measured, they are where 17 of 19 personal targets sit. Content that a researcher
   searches for changes with the page. Cost: 11 of 137 content targets, mostly site navigation nobody
   searches for.
4. **Structured recognisers on what remains**, for personal data typed into the page: email, phone,
   card and IBAN already exist in stage 7 at the pattern floor; postcodes do not, and stage 7
   deliberately has no location entity. Typed form values are the residual risk the stickiness rule
   cannot see. Whether to redact them in a private, local index at all is a question (§6); they matter
   most if text ever flows onward.
5. **Presidio's PERSON model is the wrong tool here.** On screen text it caught 15 of 17 names but
   damaged 13% of ordinary UI strings (IKEA product names read as people, buttons, headings), and
   missed bookmark titles because they are lower-case. Do not run NER over screen text by default.
6. **What the researcher is told.** A sentence where the feature is switched on: Bristlenose reads text
   on shared screens so you can search it; it stays in this project, is not sent to the AI provider and
   is not included in exports. Participant consent forms cover the recording; they rarely anticipate
   their screen being made searchable, and never cover a colleague's name in a sidebar. The
   researcher's existing practice (asking participants to share a single window, close other tabs) is
   the first line of defence and the copy can say so.

### 3.6 Cost envelope, 5-hour project

Measured on an M2 Max; the scene strip job's pattern (serve, background thread, after the report is
readable, deferred while a run is in progress, one session at a time).

| | Mac (Vision) | Linux/Windows (RapidOCR, 2 threads) |
|---|---|---|
| decode, 1 frame per 4 s, full res | ~45 s (shared with the strip decode if combined) | same order |
| OCR, 900 frames an hour | ~12 min wall, ~10 CPU-min | ~2.5 h wall, ~5 CPU-h |
| text diff, episodes, stickiness | seconds | seconds |
| stored | ~1.2 MB JSON (~250 KB gzipped) | same |
| memory | ~180 MB | ~1.3 GB |

A 4K, 120 fps screen capture costs more to **decode** than to read: the strip job already measures
about 7 minutes per hour of such video, and the full-resolution pass is similar. OCR on a Retina frame
measured 0.21 s with Vision.

## 4. What it would take to build

Each step ends usable and green; none is started.

1. **`bristlenose/utils/screen_text.py`**: sample a recording at 1 frame per 4 s at full resolution in
   one ffmpeg pass (raw frames on a pipe, nothing written to disk), OCR each (Vision via pyobjc where
   available), keep a moment when the line set changes (Jaccard < 0.6), build episodes (line, box,
   start, end, confidence), mark sticky lines, write `<session>.json` whole and rename into place,
   cached by the recording's identity with a `VERSION` in the key. The scene strip module is the
   template, including its refusal to mis-pair frames and times.
2. **Serve job**: generalise `SceneStripJob` into one media-enhancement job that does strips, then
   screen text, per session, with the same deferral and rerun rules and a kill switch
   (`BRISTLENOSE_SCREEN_TEXT=0`). Never on the pipeline's path.
3. **Search route**: `POST /api/projects/{id}/screen-text/search`, folded matching by the shared
   contract (`tests/fixtures/search-match-contract.json`), returning moments with the paragraph at
   each; classified server-only for export. FTS5 when the search core lands (D1).
4. **SPA**: an "On screen" group in the results surface, the result row in §3.4, the jump, and the
   ticks on the timeline from their own route.
5. **Packaging**: pyobjc in the `apple` extra and the sidecar spec; prove Vision runs under the
   sandbox in the bundled sidecar before anything ships. RapidOCR only if §6 says so.
6. **Tests**: synthetic frames with known text (rendered, never participant frames) for the sampler
   and the episode builder; the stickiness rule against a synthetic session whose chrome is known;
   a test that the route is server-only and that nothing screen-text reaches the export, the MCP
   tools or any LLM prompt.

## 5. What this did not measure

CJK, Windows desktops, a real terminal session, a 4K share, mobile screen shares, Zoom's and Meet's
layouts (only Teams), a sandboxed run of Vision in the bundled sidecar, and the CPU and thermal cost of
the job on a fan-less laptop during a call. Two sessions and one reader's targets: directionally firm,
not a benchmark.

## 6. Open questions for the owner

1. **Build it at all?** The measurements say it works well on the Mac and cheaply. Is "find the moment
   by what was on screen" worth a new feature surface now?
2. **Mac only, or every channel?** Vision on the Mac costs ~7 MB and minutes. Everywhere else the
   honest choice is RapidOCR at ~75 MB of wheels and hours of background CPU, or nothing. A Mac-only
   feature is a parity break (`docs/design-modularity.md`); an optional extra on the CLI keeps parity
   in principle.
3. **On by default?** On the Mac it is cheap and stays in the project. Elsewhere it is heavy. And it is
   a new kind of reading of the participant's screen that they did not anticipate.
4. **Should screen text ever reach the LLM?** It would make the analysis better: the model could see
   that the participant's hesitation coincided with a dialog. It would also send screen PII to the
   provider. This proposal says no for the first build; is that the right line, and what would it take
   to cross it?
5. **Redact typed form values in a private local index?** Stickiness removes chrome; it cannot remove a
   postcode the participant typed. Locally the researcher already saw it. Leave it, or add postcode and
   address patterns now?
6. **Should the hover thumbnails take their frames from the text-diff moments?** They are the moments
   the screen changed in a way a person reads, and they would make one sampling pass serve both.
