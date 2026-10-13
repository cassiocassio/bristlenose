---
status: proposal
updated: 13 Oct 2026
---

# Screens: where they went, what they said, what was on screen

**Status: the plan, 13 Oct 2026. Nothing is built except one enabling fix (§3.4).** Decided by the
owner today: **(1) screen text and the Screens lens are one project with one plan; (2) Mac first;
(3) the OCR engine is pluggable, so other platforms can join with another engine later.** Everything
else here is a proposal.

This doc owns the plan. The evidence lives in two records, which it does not repeat:

- [`design-screen-text-search.md`](design-screen-text-search.md) — reading the shared screen:
  engines measured, frame sampling, the index, the chrome filter, PII, the Mac sandbox findings.
  Method: [`experiments/screen-text/README.md`](../experiments/screen-text/README.md).
- [`design-screens-lens.md`](design-screens-lens.md) — turning readings into screens: prior art,
  the address bar as the screen key, flows, the lens layout. Method:
  [`experiments/screens-lens/README.md`](../experiments/screens-lens/README.md). Mockups:
  [`mockups/screens-lens.html`](mockups/screens-lens.html),
  [`mockups/screens-lens-speculative.html`](mockups/screens-lens-speculative.html).

## 1. The idea

Every moment of a usability session has three facts, and Bristlenose knows only one of them today:

| fact | source | today |
|---|---|---|
| **what they said** | transcript, quotes, tags, sentiment | built |
| **what was on screen** | OCR of the shared screen, every 4 s | measured, not built |
| **which screen they were on** | screens derived from what was on screen (address bar first, text second) | measured, not built |

All three share one clock, the session's timeline, so they join by time with no guessing. The
product is the join: **what people said, on which screen, while looking at what.** Each fact alone
is weaker. Screen text alone is a search index; screens alone are a sitemap; quotes alone are what
the report already has. The UX below is chosen for surfaces that use at least two of them.

## 2. The surfaces, ranked

Ordered by value for effort and by dependency; Phase 0 (§5) decides which earn a place and in what
order. Each line names the facts it joins.

**S1. A quote knows its screen** (*said × screen*). Every quote card gains a quiet line, *On: Checkout
· Delivery*, with the screen's still on hover. It works wherever quote cards already appear (Quotes,
Signals drill-downs, Codebook, the transcript), it asks nothing of the researcher, and it is the
cheapest thing here once screens exist. Measured: report sections are mostly said on one page (14 of
17, 12 of 15), so the line usually confirms and sometimes contradicts the section, which is the
interesting case.

**S2. Search reaches the screen** (*said × shown × screen*), inside the search field that already
exists, with the grammar it already has (typed words, plus tokens with a meaning menu, from
[`design-search.md`](design-search.md) D4–D6). Two new token kinds:

- **Screen token** — typing a screen's name offers it, like a person or a tag: *on: Warenkorb*.
  Meanings: *said on* (quotes said while that screen was up), *not on*. This is the Screens lens's
  question asked from the search field: "what did people say at checkout?"
- **Shown token** — typed words that appear on screen are offered as *shown: "Weiter als Gast"*.
  Meanings: *said while shown* (quotes said while that text was on screen), *not while shown*, and
  **Show the moments** — a list of every time it appeared, grouped by screen and session (the
  grouping rules measured in `design-screen-text-search.md` §3.4), each row jumping to the transcript
  at that second with the video cued. The moments list is for the case nobody spoke: *"did anyone
  see the out-of-stock dialog?"* is answered by the count alone — **shown in 3 of 8 sessions** — which
  is itself a finding.

Search stays quick find: no meaning, no AI (search doc, 4 Oct 2026). Screen text is searched on the
server, in a POST body, never shipped to the page wholesale.

**S3. The transcript reads with its screens** (*said × screen × shown*). The transcript margin marks
each screen change with the screen's name and a still on hover; a paragraph can show what was on
screen as it was spoken, folded by default. From any quote, *show the moment* opens this.

**S4. The session timeline gains a screens lane** (*screen*). Under the tapestry tracks, each visit a
named bar; search matches as ticks.

**S5. The Screens lens** (*screen × said*). Step-column flow, paths, grid
(`design-screens-lens.md` §5): select a screen to see every quote said there by every participant,
everything said there, and the tag sidebar scoped to it. Friction as evidence (counts, back-steps,
time on screen), never a score. Corrections (rename, merge, split, hide) are part of the design.

**S6. Sections grounded in screens** (*said × screen*). The report's speech-derived sections show
where they were said, and flag the quotes said on a different page from their section. The smaller
alternative to S5 (`design-screens-lens.md` §10.1); both need the same data.

Not in this plan: screen text in the chat lens or MCP, and screen text sent to the LLM (§4).

## 3. One architecture

### 3.1 The pipeline

```
recording ─► sampler ─► ScreenTextEngine ─► lines + boxes
              (ffmpeg pipe, 1 frame / 4 s,      (vision | rapidocr | fake)
               real times from showinfo)
                                  │
                                  ▼
           moments (text diff) ─► episodes ─► URL capture ─► chrome filter (word at place)
                                  │
                                  ▼
                    screen-text index, per session
                                  │       + transcript, quotes, sections
                                  ▼
       screens derivation: visits ─► page keys (URL template, else text) ─► screens across
                           sessions ─► quote join ─► section link ─► overrides applied
                                  │
                                  ▼
                 routes (server-only) ─► SPA surfaces S1–S6 ─► native search menu (bridge)
```

Everything except the box named `ScreenTextEngine` is engine-agnostic Python, measured in the two
evidence docs, and testable on any platform.

### 3.2 The engine seam

```python
class ScreenTextEngine(Protocol):
    name: str            # "vision", "rapidocr", "fake" — recorded in the index
    version: str         # engine + model version — part of the cache key

    def available(self) -> Availability: ...              # ok, or a reason a person can act on
    def recognize(self, frame: Frame) -> list[Line]: ...  # Line = text, confidence, box (0–1, top-left)
```

- **Selection mirrors transcription.** A setting `screen_text_engine: auto | vision | rapidocr | off`,
  shaped like `whisper_backend: auto | mlx | faster-whisper` (`config.py`, `utils/hardware.py`).
  `auto` picks Vision on macOS, RapidOCR where its extra is installed, and otherwise *off*. `doctor`
  reports the engine and why, the way it reports the transcription backend.
- **The UI follows availability, not platform.** Where no engine is available the surfaces simply
  are not there (absence is information); there is no Mac-only code in the SPA.
- **The index records the engine per session**, and the cache key is the recording's identity plus
  the engine's name and version plus the pipeline's own version, so a better engine re-reads.
- **A `fake` engine** returns the known text of synthetic frames. With it, everything outside the
  seam is tested on Linux CI with no OCR at all. A **conformance suite** runs the same rendered frames
  through every engine installed on the machine (Vision on the Mac cells), so a second engine joins
  by passing it.

### 3.3 Data, in one place

| what | where | written by |
|---|---|---|
| screen-text index (episodes, moments, engine) | `<output>/.bristlenose/intermediate/screen-text/<session>.json` | serve job |
| screens (screens, visits, keys, names and their sources) | `<output>/.bristlenose/intermediate/screens/screens.json` | serve job |
| researcher corrections (rename, merge, split, hide) | SQLite, like other researcher edits | the lens |
| stills | never stored; extracted on demand (0.11 s a seek) | routes |

Routes: `POST …/screen-text/search`, `GET …/screens`, `GET …/screens/{id}/still`,
`GET …/sessions/{id}/still?t=`. All classified `SERVER_ONLY_PATH_TEMPLATES`
(`server/routes/export.py`; `tests/test_serve_export_coverage.py` forces the choice).

Everything runs in **serve, in the background, after the report is readable**, as one media job that
already exists for scene strips (`server/scene_strips.py`): strips, then screen text, then screens,
per session, deferring while a run is in progress. Never on the pipeline's path.

### 3.4 What the Mac already has

- **Vision works in the real sandboxed sidecar**, and the one blocker is fixed: `childEnvironment`
  sets `CFFIXED_USER_HOME` to the container (`32e9d2b3`), proven end to end with 8 of 8 frames.
- **Measured costs:** ~2 minutes per hour of 1080p video, ~200 MB, pyobjc ~2 MB in the bundle. The
  first frame after each app or macOS update pays a ~40 s model compile, once, in the background.
- **Two loop rules:** copy each frame into `NSData` and read it inside `objc.autorelease_pool()`, or
  memory grows a frame per call. **One process:** the sandbox refuses POSIX semaphores.

## 4. Privacy, merged

One model for the whole project, combining both evidence docs:

1. **Everything stays in the project**, like `transcripts-raw/`: the index, the screens, the stills.
2. **It never leaves**: not in the HTML export, anonymised outputs, clip or quote exports, MCP, the
   chat lens, support bundles, **and never sent to the LLM**. The analysis is a cloud call; screens
   carry bookmarks, colleagues' names and typed addresses. Screen names borrow the report's
   LLM-made section names (made from the transcript) rather than sending screens to name them.
3. **Chrome is dropped by position** (a word in the same place on half the share frames): 16 of 19
   personal targets removed, no page content lost. **URLs are read before that filter**, for screen
   keys, with queries dropped and digit runs masked.
4. **Typed values** (postcodes, addresses) are the residual risk the filter cannot see.
5. **Off-task screens** (an inbox, a bank) seen by one participant on another host are hidden but
   counted, and can be revealed.
6. **No cloud vision**, for naming or merging screens. A local model, or a new consent decision.
7. **One sentence where it is switched on**: Bristlenose reads text on shared screens and maps the
   screens participants visited, so you can search them; it stays in this project, is not sent to the
   AI provider and is not included in exports.

## 5. Phases, Mac first

Each phase ends usable and green. No estimates until Phase 0 has run.

**Phase 0 — prove the value before building.** On the owner's own studies with screen shares, list
ten questions from real research practice ("when did they first see the delivery cost?", "what did
people say at checkout?", "did anyone hit the error?") and answer each three ways: today's report,
the screen-text index, the screens join. Use the existing spike scripts and a private prototype over
real indexes; tracked mockups stay synthetic. **Exit:** the owner picks which of S1–S6 earn a place
and in what order.

**Phase 1 — the seam and the index** (Python; the Mac CLI and the sidecar run the same code; no UI).
The engine protocol, the Vision engine, the fake engine and conformance suite; the sampler,
moments, episodes, URL capture, chrome filter and index writer, from the spike scripts; the setting
and the `doctor` row; pyobjc in the `apple` extra and the sidecar spec. **Exit:** the media job
writes an index for a real project on the Mac; Linux CI is green on the fake engine.

**Phase 2 — screens and routes.** `utils/screens.py` (visits, page keys, cross-session screens,
quote join, section link) as pure functions; the overrides table; the routes; export classification.
**Exit:** `GET …/screens` answers for the two measured sessions as the evidence doc predicts.

**Phase 3 — the first surfaces**, as Phase 0 ordered them. The likely first three: S1 (the quote's
screen), S3 (transcript markers), S2 (screen and shown tokens, the moments list). Browser and the
Mac's web view together; 21 locales; absent in export mode.

**Phase 4 — the Mac app and shipping.** The native search menu gains the two token kinds through the
bridge contract (`tests/fixtures/search-bridge-contract.json`; an older build ignores an unknown
kind); the switch and its sentence in Settings; a TestFlight-signed build, the privacy manifest's
coverage of pyobjc, and an app-store-police pass.

**Phase 5 — the Screens lens** (S5) and sections grounding (S6), with corrections, and the labelled
set that dialog-level states need before any detector (`design-screens-lens.md` §4.2, §9).

**Phase 6 — other platforms.** A RapidOCR engine as an optional extra: pinned, hashed, self-hosted
models; the 960 px detection cap, 2 threads, the unchanged-frame gate; measured first on real amd64
Linux and Windows machines, since every number so far is from one Mac. It passes the conformance
suite and the surfaces appear: nothing above the seam changes.

## 6. Open questions for the owner

1. **After Phase 0: build it, and which surfaces first?**
2. **On by default on the Mac,** or switched on per project?
3. **Sections and screens:** keep both concepts when screens exist, ground one in the other (S6), or
   let screens replace speech-derived sections where they are observed?
4. **Page-level screens for v1,** with dialogs as researcher-marked states, or wait for a detector?
5. **Typed values:** mask postcode and address patterns in the local index now, or leave them?
6. **Ever in the export?** v1 keeps it all out; a screen map without stills is plausible later.
7. **Should the hover thumbnails share the sampling?** The text-diff moments are where the screen
   changed in a way a person reads.
