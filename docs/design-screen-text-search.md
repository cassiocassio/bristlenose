---
status: proposal
updated: 13 Oct 2026
---

# Searchable screen text

> **Part of one project, 13 Oct 2026.** Screen text and the Screens lens are planned together in
> [`design-screens.md`](design-screens.md), which owns the UX, architecture, privacy model and
> phases (Mac first, engine pluggable). This doc is the **evidence record** for reading the shared
> screen; where its §3.4, §4 or §6 disagree with the plan, the plan wins.

> _15 Oct 2026: this is the evidence record behind `design-screens.md`, kept as it was. The Screens
> lens and the screen-text index it describes have since been built; `design-screens.md` says what
> shipped and what is still the plan._

**Status: exploratory proposal, 13 Oct 2026. Nothing here is built and nothing is decided; the owner
decides whether it is.** Method and every number below:
[`experiments/screen-text/README.md`](../experiments/screen-text/README.md). A second pass the same day
spiked the open risks (§4): the end-to-end pipeline, Vision under the App Sandbox, the search result
model, a better privacy filter, and cheaper settings for the non-Mac channels. A third pass ran Vision
inside the real sidecar, as the sandboxed app launches it (§3.3).

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
dark-mode desktop capture, a 4K screen recording, a synthetic terminal; 232 hand-written search targets
on 11 frames; a dense OCR sweep every 2 s as the oracle for coverage.

| question | answer |
|---|---|
| Can OCR read call-recorded UI well enough to search it? | **Yes, on the Mac.** Apple Vision (accurate) finds 98% of non-personal targets by the shipped search rule. RapidOCR 96%. Tesseract 59–74%. |
| Is a frame at each colour change enough? | **No.** The thumbnail plan's frames capture 44–61% of text that stays on screen 4 s or more. 55–62% of text changes have no colour change within ±3 s (white page to white page). |
| What is enough? | OCR every 4 s and keep what changed: 84–87% of ≥ 4 s episodes. |
| What does the whole pipeline cost on a Mac? | **Measured end to end: 1.9–2.0 minutes per hour of 1080p call recording**, ~200 MB, one decode pass on a pipe, nothing written but the index. 5.5 min/h for a 4K, 120 fps screen capture (decode-bound). |
| Does Vision work inside the App Sandbox? | **Yes, in the real sidecar, with one environment variable.** Run by the sandboxed Debug app as its inherited-sandbox child, Vision failed until `CFFIXED_USER_HOME` pointed Foundation at the container; with it, 8 of 8 frames read, 0.15–0.22 s each warm. pyobjc adds ~2 MB to the bundle. |
| Keep the full-resolution frames? | **No.** 73–555 KB each, and the recording already holds every one of them: any frame comes back in 0.11 s. Keep text, boxes and times: ~200–230 KB an hour (45 KB gzipped). |
| Does the PII stage protect it? | **Poorly.** Presidio catches 16 of 26 personal targets (15/17 names, 1/6 bookmark titles, 0/3 postcodes) and damages 27 of 202 ordinary UI strings. |
| Is there a better privacy tool? | **Word-position stickiness.** A word that sits in the same place on half the share frames is chrome. Removes 16 of 19 personal targets and **no page content**; the 5 other strings it removes are browser chrome. |
| Do search results make sense? | **Yes, once grouped by screen.** Specific queries land on one moment, in the right place. Common words return 1–7 rows, after two grouping rules (§3.4). |
| Cost for a 5-hour project | **Mac: ~10 minutes.** Linux/Windows with RapidOCR, tuned: **about an hour** at 2 threads. Index ~1 MB. |

## 3. Options and recommendations

### 3.1 Which frames to read

| option | ≥ 4 s episodes captured | OCR calls / h | notes |
|---|---|---|---|
| thumbnail frames (turn + colour change in a participant turn) | 44–61% | 86–112 | free if thumbnails ship, but misses long same-colour stretches; a 14-minute participant turn gets frames only at colour changes |
| fixed interval, 10 s | 79–80% | 360 | simple, wasteful on talking heads |
| edge-map diff, no OCR in the loop | 77–89% | 390–970 | 5 ms a frame, but moving faces trigger it; would need the filmstrip masked |
| **OCR every 4 s, keep a moment when the lines change** | **84–87%** | **900** | the detector *is* the reader; one decode pass |
| OCR every 6 s, same rule | 81–83% | 600 | the lever if a channel is slow |

**Recommend OCR every 4 s with text-diff.** Measured end to end on the Mac, the decode runs alongside
the OCR on a pipe, so it adds no wall time. It can share the scene strip's decode with an ffmpeg
`split` so the recording is read once for both, though that would make one job's failure the other's.

**And let the thumbnails take their frames from it.** The text-diff moments are the moments the screen
visibly changed in a way a person would read; they may be a better thumbnail set than colour edges.
That is a question for the thumbnail mockup, not a decision here.

### 3.2 Keep or discard the full-resolution frames

| option | 5-hour project | notes |
|---|---|---|
| keep full-res PNG | ~350 MB (750 kept frames × 475 KB) | a second copy of every screen, PII included |
| keep full-res HEIC / JPEG q5 | 55–65 MB | same, smaller |
| keep 1280 px JPEG | ~40–60 MB | text mostly still legible |
| **OCR, then discard; keep text + boxes + times** | **~1 MB** | the recording is the archive |

**Recommend discard.** The recording is already in the project and a frame comes back in 0.11 s, so a
stored frame buys nothing a seek cannot, and it duplicates the most personal data in the project into
a second place to govern. A search result that wants a picture asks for one (§3.4), extracted on demand
at 320 px, the thumbnail size, or the existing hover thumbnail if one exists for that moment.

### 3.3 Which engine, on which channel

| channel | engine | added size | cost | verdict |
|---|---|---|---|---|
| Mac app (sandboxed sidecar) | Apple Vision via pyobjc | **~2 MB** in a frozen bundle | 0.12–0.13 s and about one core per 1080p frame; 0.27 s at 4K | **recommended** |
| Mac CLI (PyPI, Homebrew) | Apple Vision via pyobjc, in the `apple` extra | ~7 MB of wheels | same | **recommended**, same code path as the app |
| Linux / Windows CLI, Snap, Copr | RapidOCR, an optional extra | ~75 MB of wheels, 10 dependencies, OpenCV | 1.55 s a frame at 2 threads (tuned), 1.3 GB | possible, heavy; owner's call (§6) |
| Linux, from the distribution | Tesseract (system package) | 25 MB + leptonica | 0.4–0.8 s | **not recommended**: 59–74% |

Notes that matter for the choice:

- **Vision reaches the sidecar through pyobjc, not a helper.** `pyobjc-framework-Vision` calls the
  system framework from Python, so the CLI on a Mac and the sidecar run the same code
  (`docs/design-modularity.md`'s no-fork principle). **Spiked:** a PyInstaller-frozen probe signed
  with the App Sandbox entitlement ran in its container (its home resolved to
  `~/Library/Containers/<id>/Data`) and read a frame with Vision accurate, no extra entitlement.
  pyobjc's frozen footprint is ~2 MB (`objc` 0.9 MB, `Quartz` 0.7 MB, the rest small), because
  PyInstaller keeps only the compiled extensions. **Spiked in the real sidecar** (third pass, below).
  **Still unproven:** a TestFlight-shaped build (Apple Distribution signing, Hardened Runtime on the
  host) and the privacy manifest's required-reason coverage for pyobjc's binaries. A Swift helper executable (like
  `desktop/mcp-helper/`) would also work but adds a fifth signed executable and leaves the Mac CLI
  without OCR. The host app doing OCR itself is ruled out: it forks the code path.
- **Vision in the real sidecar needs `CFFIXED_USER_HOME`, measured.** The sidecar was built by
  `ensure-sidecar.sh` with pyobjc added, signed with its shipped entitlements (`app-sandbox`,
  `inherit`, the JIT exceptions) and launched by the sandboxed Debug app, which reported
  `sandbox=on`; a read of an ordinary file outside the grant was refused with `EPERM`. The first
  `VNRecognizeTextRequest` then returned failure with no error object. The log said
  `E5RT Error: e5rt_e5_compiler_create call failed (Code: 11)` and `Underlying detector load error`.
  **Cause:** Vision compiles its text model once and caches it at
  `<NSHomeDirectory()>/Library/Caches/<id>/com.apple.e5rt.e5bundlecache`. A sandboxed *app* resolves
  that inside its container, and so did the standalone probe. An *inherited* child resolves
  `NSHomeDirectory()` to the real home even though the host passes `HOME` as the container. The cache
  write is refused, and the compile fails. **Fix:** set `CFFIXED_USER_HOME` to the container before
  anything initialises Foundation. With it, 8 of 8 frames of a 3456×2234 screen recording read 74–97
  lines each at peak RSS ~408 MB for the whole serve. **First use compiles the model:** 41 s on the
  first frame of the cold run, then 0.15–0.20 s. A relaunch read its first frame in 0.63 s, so the
  cache persists in the container. The cache folder is named for the OS build, so expect one compile
  after each macOS update, and a newly built sidecar compiled again (41.5 s) despite a cache from an
  earlier build in the same container, so expect it once per app version too. **Wired** into
  `BristlenoseShared.childEnvironment` on 13 Oct 2026 (`foundationHomeEnvironment`, `32e9d2b3`); the
  spike first set it in `sidecar_entry.py`, and an end-to-end rebuild with only the Swift wiring read
  8 of 8 frames. It matters beyond Vision: any system framework that caches under the home directory
  would be refused writes in the inherited child. Patch:
  `experiments/screen-text/sidecar-vision-spike.patch` (its `sidecar_entry.py` hunk is now redundant).
- **The sandbox refuses POSIX semaphores**, so `multiprocessing.Queue`/`Lock` fail with `EPERM` inside
  the sidecar. The screen-text job must stay in one process, which the spike's design already is.
- **Two things a long-running Vision loop needs, both measured.** Build each frame's `CGImage` from an
  `NSData` copy of the bytes, and wrap each call in `objc.autorelease_pool()`. With
  `CGDataProviderCreateWithData` over the Python buffer, memory grew by one whole frame per call
  (~8 MB at 1080p) with or without a pool; with the copy but no pool, the same. With both, memory
  stays flat at ~160–200 MB over 568 frames. A 5-hour project without them would have climbed into
  tens of GB.
- **The App Store question does not arise for Vision**: it is code that ships in the OS. RapidOCR's
  models are data and could be fetched on demand, but its code (OpenCV, shapely, pyclipper) would have
  to be bundled (§2.5.2, as `docs/design-redact-pii.md` sets out for spaCy). On the Mac there is no
  reason to carry it.
- **Vision fast is not a cheap Vision.** It scored 29% and garbles characters (`Get instsni benefws`).
  Use accurate.
- **Vision keeps a core busy**, not the Neural Engine as this doc first said: the end-to-end run's CPU
  time matched its OCR time (69 s each over 568 frames). One core for two minutes an hour of video is
  still cheap; the job should run at background priority all the same.
- **Languages.** Vision accurate on macOS 27 lists 33 recognition languages: every Bristlenose locale
  except Catalan (Latin script, so the Spanish or French models will mostly read it), with Portugal's
  Portuguese under `pt-BR`. German was read correctly under the default setting. CJK needs the
  recognition languages set from the project's language. Not measured on CJK here.
- **RapidOCR can be tuned, not transformed.** At 2 threads: the default model 2.16 s a frame and 96%;
  detection capped at 960 px on the long side 1.55 s and 95%; the PP-OCRv5 Latin mobile model 1.71 s
  and 96%; both 1.40 s but 86%. Skipping OCR on a sample whose edge map barely changed (diff < 0.1)
  skips 30–40% of samples and keeps ~95% of distinct lines. Together, about 1 s a sample on average,
  so 15 minutes per hour of video at a 4 s sample, 10 at 6 s. Non-default models are fetched at first
  use from modelscope.cn; a product would pin, hash and host them.

### 3.4 Where it surfaces

**Search.** The settled engine for project-wide search is SQLite FTS5 shared by CLI, SPA and MCP
(`docs/design-search.md` D1); slice 1 is TypeScript over data the SPA holds. Screen text should **not**
be shipped to the SPA wholesale: ~1 MB of text a project, most of it never searched, and all of it
personal-data-dense. It is a server-side search from the start, in a POST body (the search doc's §9:
query strings reach access logs). It does not need FTS to start: a linear folded scan over the 930
episodes of a 38-minute session takes under a millisecond in Python, so a 5-hour project is a few
milliseconds.

A hit is a **moment**, not a quote. The result row:

```
[320 px frame, the matched line outlined]   "Die Planung kann nicht geöffnet werden"
                                            On screen 20:40–20:56 · Session 1 · p3
                                            p3, 20:13: "…the paragraph being spoken at that moment…"
```

- The outline comes from the stored box, drawn over a frame extracted on demand.
- The third line is the transcript paragraph covering the moment's start, so the researcher sees what
  was on screen and what was said at once. Paragraphs are long: the one covering a moment often began
  30 s or more before it, so the row shows the paragraph's own time.
- **The jump** opens the transcript at that second (the existing `#t-<seconds>` fragment,
  `frontend/src/utils/reportHref.ts`) with the video player cued to the start of the episode.
- **Grouping, spiked against real queries.** One row per line gave 14–26 rows for a common word, most
  of them other lines on the same screen. Grouping overlapping intervals over-corrected: it chained
  eight minutes of different screens into one row. What works is two rules together: **a row is the
  screen a match appeared on** (keyed by the index's text-diff moments, several matching lines on one
  screen share it), and **the same text returning within 60 s rejoins its row** (a form label that
  flickers off under a popover listed six times otherwise), comparing text with a leading one- or
  two-character token dropped, because Vision reads a favicon or bullet as one. Result counts on the
  two sessions: specific phrases 1 row each, landing on the right moment; common words 1–7.
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
start, end, line), only filtered and redacted text, behind the per-project agent access switch.

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
3. **Index what changes, not what stays, judged per word at its place on screen.** A word that sits
   at the same position (2% buckets, ±1) on at least half of a session's text-dense frames is chrome,
   and is dropped before indexing. On the truth set this removes 16 of 19 personal targets (every
   name under a tile and six of seven bookmark titles) and **no page content**; the only other strings
   it removes are browser chrome (the restore banner, the URL, Safari's bookmarks). The first version
   of this rule worked on whole lines and removed only 12 of 19, because Vision reads the bookmark
   icons as stray letters and so groups the bookmark bar differently from frame to frame; and a
   text-only rule (anywhere on the frame, any place) also dropped product names the participant
   stayed on for half the session, which are exactly what a researcher searches for.
4. **Structured recognisers on what remains**, for personal data typed into the page: email, phone,
   card and IBAN already exist in stage 7 at the pattern floor; postcodes do not, and stage 7
   deliberately has no location entity. Typed values are the residual risk: the postcode and the
   delivery address are the two of three personal targets the word rule cannot see, and in search
   they surface inside ordinary lines (`Lieferung an …`, `Du hast … als deine Postleitzahl`). Whether
   to mask them in a private, local index at all is a question (§6); they matter most if text ever
   flows onward.
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

Mac figures are the end-to-end spike (`pipeline_spike.py`) on an M2 Max; the job follows the scene
strip's pattern (serve, background thread, after the report is readable, deferred while a run is in
progress, one session at a time).

| | Mac (Vision) | Linux/Windows (RapidOCR, 2 threads, tuned) |
|---|---|---|
| decode, 1 frame per 4 s, full res | runs alongside OCR on a pipe: ~1.1 ffmpeg CPU-min per hour of 1080p | same |
| OCR | 1.9–2.0 min wall per hour of video, about one core | ~15 min per hour at 4 s, ~10 at 6 s |
| 5-hour project, wall | **~10 minutes** | **~50–75 minutes** |
| text diff, episodes, stickiness | seconds | seconds |
| stored | ~1 MB JSON (~250 KB gzipped) | same |
| memory | ~200 MB (needs the §3.3 loop discipline) | ~1.3 GB |

A 4K, 120 fps screen capture is decode-bound: 5.5 minutes of wall time per hour of video on the Mac,
of which ffmpeg spent ~25 CPU-minutes per hour across cores, and Vision 0.27 s a frame.

## 4. What it would take to build

Spiked on 13 Oct 2026 (second pass), each against the real recordings unless marked: the end-to-end
sampler (`pipeline_spike.py`), Vision under the App Sandbox from frozen Python (a sandboxed probe
`.app`, synthetic frame), word-position stickiness (`sticky_eval.py`), result grouping
(`search_spike.py`), RapidOCR tuning (`rapid_levers.py`). What remains unproven is named in each step.

1. **`bristlenose/utils/screen_text.py`**, from `pipeline_spike.py`: one ffmpeg pass at 1 frame per
   4 s, full resolution, raw BGRA on a pipe with `showinfo` times (refuse to pair a count mismatch, as
   the strip does); Vision through pyobjc with the `NSData` copy and a per-frame autorelease pool;
   folded lines; episodes; text-diff moments (Jaccard < 0.6). **Change from the spike:** stickiness
   per word at its place (§3.5 item 3), applied after the session is read, since it needs the whole
   session. Write `<session>.json` whole and rename into place, cached by the recording's identity
   with a `VERSION` in the key. Background priority. *Unproven:* recordings with several video tracks,
   portrait mobile shares, and a 3-hour session's single-pass memory (the spike's longest was 38 min,
   flat).
2. **Serve job**: generalise `SceneStripJob` into one media-enhancement job that does strips, then
   screen text, per session, with the same deferral and rerun rules and a kill switch
   (`BRISTLENOSE_SCREEN_TEXT=0`). Never on the pipeline's path. Strips first, because they are cheap
   and the timeline wants them; screen text after.
3. **Search route**: `POST /api/projects/{id}/screen-text/search`, folded matching by the shared
   contract (`tests/fixtures/search-match-contract.json`), returning rows grouped as in §3.4 with the
   paragraph at each; classified server-only for export. A linear scan is fast enough; FTS5 when the
   search core lands (D1).
4. **SPA**: an "On screen" group in the results surface, the result row in §3.4, the jump, and the
   ticks on the timeline from their own route. *Unproven:* the row's on-demand 320 px frame with the
   box drawn on it (cheap by measurement, 0.11 s a seek, but not built).
5. **Packaging, Mac**: pyobjc (`pyobjc-core`, `-Cocoa`, `-Quartz`, `-Vision`) in the `apple` extra
   and the sidecar spec (PyInstaller picked all four up from the imports; no spec change was needed in
   the spike). `CFFIXED_USER_HOME` is already wired (§3.3). The job should expect a one-time model
   compile of tens of seconds on its first frame after each macOS update or app update and say
   nothing about it: it runs in the background. *Unproven:* a TestFlight-shaped
   build (Apple Distribution, Hardened Runtime on the host), and the privacy manifest's coverage of
   pyobjc's binaries; route both through the app-store-police agent.
6. **Packaging, elsewhere**, only if §6 says so: RapidOCR as an optional extra with pinned, hashed,
   self-hosted models, the 960 px detection cap, 2 threads, and the unchanged-frame gate.
7. **Tests**: synthetic frames with known text (rendered, never participant frames) for the sampler
   and the episode builder; a synthetic session with known chrome (a fixed bookmark bar and tile names
   over changing pages) for the stickiness rule, asserting chrome gone and content kept; the grouping
   rules on a synthetic index; a memory test that a few hundred frames leave RSS flat; and tests that
   the route is server-only and that nothing screen-text reaches the export, the MCP tools or any LLM
   prompt.

## 5. What this did not measure

CJK, Windows desktops, a real terminal session (the terminal frames were synthetic), Zoom's and
Meet's layouts (only Teams), mobile screen shares, a TestFlight-signed sidecar, and the CPU
and thermal cost of the job on a fan-less laptop during a call. Two sessions and one reader's targets:
directionally firm, not a benchmark. The stickiness rule's 0-content-lost result is on 146 targets in
two IKEA sessions; a session that stays on one page for most of its length would test it harder.

## 6. Open questions for the owner

1. **Build it at all?** The measurements say it works well on the Mac and cheaply. Is "find the moment
   by what was on screen" worth a new feature surface now?
2. **Decided 13 Oct 2026: Mac first, engine pluggable** (`design-screens.md`). Kept for the record: **Mac only, or every channel?** Vision on the Mac adds ~2 MB to the app and about ten minutes for a
   5-hour project. Everywhere else the honest choice is RapidOCR at ~75 MB of wheels and about an hour
   of background CPU for the same project, or nothing. A Mac-only feature is a parity break
   (`docs/design-modularity.md`); an optional extra on the CLI keeps parity in principle.
3. **On by default?** On the Mac it is cheap and stays in the project. Elsewhere it is heavy. And it is
   a new kind of reading of the participant's screen that they did not anticipate.
4. **Should screen text ever reach the LLM?** It would make the analysis better: the model could see
   that the participant's hesitation coincided with a dialog. It would also send screen PII to the
   provider. This proposal says no for the first build; is that the right line, and what would it take
   to cross it?
5. **Mask typed form values in a private local index?** Stickiness removes chrome; it cannot remove a
   postcode the participant typed. Locally the researcher already saw it. Leave it, or add postcode and
   address patterns now?
6. **Should the hover thumbnails take their frames from the text-diff moments?** They are the moments
   the screen changed in a way a person reads, and they would make one sampling pass serve both.
