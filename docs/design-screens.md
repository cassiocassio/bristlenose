---
status: proposal
updated: 14 Oct 2026
---

# Screens: where they went, what they said, what was on screen

**Status: the plan, 13 Oct 2026; a rough diagnostics build since 14 Oct (below).** Decided by the
owner today: **(1) screen text and the Screens lens are one project with one plan; (2) Mac first;
(3) the OCR engine is pluggable, so other platforms can join with another engine later.** Everything
else here is a proposal.

**14 Oct 2026: tested on real sessions.** Three IKEA sessions (UK site in a Teams call, German site
in Chrome, UK site on an iPad) were run end to end through a private prototype: screens derived,
quotes placed and pinned to elements, the board drawn with the shipped design system. What that
settled is in §3.5 (pinning a quote to an element), §3.6 (is it the same screen?) and §2's S5 (the
board). The owner's principle from that test: **the machine makes its best guess and the researcher
fixes it in one gesture**, rather than asking AI to be right about everything.

**14 Oct 2026, evening: a rough first build, behind Diagnostics.** Built for one trusted tester to
try on real studies and say what is wrong. It is not Phase 1–5 done; it is the shortest path to the
board on real data.

- **Where it is.** `bristlenose/screen_text/` (engine seam with Vision and a fake engine; the
  sampler and index; `screens.py`, which derives screens, places quotes and pins them by shared
  words), a serve job that indexes each recording after the scene strips
  (`server/screen_text_job.py`), two routes (`GET …/screens`, `GET …/screens/still`, both
  server-only in an export), and the lens at `/report/screens/` (`frontend/src/islands/screens/`).
- **How to turn it on.** Mac app: Settings ▸ Appearance ▸ Diagnostics. Switching it on restarts
  the server with `BRISTLENOSE_SCREEN_TEXT=1` and adds Screens to the lens rail (⌘7); the
  Diagnostics ▸ Screens Lens menu item that did this before is gone (14 Oct 2026). Switching it
  off restarts every running server that was reading screens, not only the one on screen.
  Browser: `serve --dev`, or `BRISTLENOSE_SCREEN_TEXT=1` plus the diagnostics flag. Off, the job
  never runs, `/screens` and `/screens/status` answer `enabled: false`, and the still route 404s.
- **What it does not do yet.** Pins are words only, so a German page with English quotes pins
  little (the prototype's meaning match is not shipped). No merge or peel: one key per screen by
  the §3.6 ladder, and a page with neither address nor title is not a screen. No not-screen-based
  gate. The rearranged board lives in the browser's storage, not the project. English only; no
  locale keys. Vision only, so the lens reports "unavailable" off the Mac.
- **Brought in line with its sibling, the Discussion lens** (15 Oct). It is a lens where lenses are
  counted (`LENS_IDS`, the nav, the shim's `TAB_ROUTES`, the bridge's active tab, the subtitle, the
  navigation announcement); its zone title sits on the shared datum (gated in
  `e2e/tests/lens-datum.spec.ts`); quotes are drawn by the Quotes lens's own `QuoteCard`, so the
  timecode plays and editing, focus and the tag path (un-hiding an eye-hidden group) are shared;
  the arrow keys carry Discussion's guards; the navigator is shown and hidden like Discussion's
  guide (`[`, ⌥⌘L, the rail button; `navPanel.ts`); failures arrive as reason codes rendered by
  one English map; the poll is capped and stops on `not_read`, and a run's completion re-reads.
  §6.8 is answered for now by the defaults: hover brings a quote forward, stacks are straight —
  the pickers are gone. §6.9 is still open: the arrangement is kept in this browser's storage, keyed by
  the page's project id — which is always "1" today, so in practice it separates by origin (the
  port) only, and two projects served on one port share arrangements. Where arrangements live is
  the owner's call.
- **Owed before it leaves Diagnostics** (security review, 14 Oct). The Diagnostics switch does not
  yet say it reads shared screens (§4.7's sentence; the help text is a 21-locale change). The index
  stores every line as read, chrome and full addresses included, where §4.3 drops chrome and
  query strings at rest; off-task screens (§4.5) are not hidden. Stills are cached on disk under
  the session's id, so the pipeline's per-session prune removes a withdrawn participant's, but
  turning Diagnostics off does not delete them.
- **14 Oct 2026, later: reasons are codes, and a progress route.** Why something cannot be read is a code,
  never a sentence: `unavailable` is `not_macos` · `vision_missing` · `no_job`, and `failed[sid]` is
  `unreadable` · `cloud_downloading` · `ffprobe_failed` · `read_failed` · `not_read` (Literals in
  `bristlenose/screen_text/__init__.py`; detail goes to the log). `not_read` means the job is idle,
  no analysis is in progress, and nothing is about to read that recording, so the lens's poll
  always ends; during an analysis the answer is "waiting", because the run's completion starts the
  next pass (a review caught the first version saying `not_read` through every first analysis).
  `GET …/screens/status` is the Mac sidebar's row (counts, seconds from the database, this pass's
  reading rate; never derives). Off, `/screens` and `/screens/status` answer 200 with
  `enabled: false`; only `/screens/still` answers 404.
- **14 Oct 2026, later: a lens where lenses are counted.** Screens is a lens on both sides, beside
  Discussion: the SPA's lens lists, route shims, bridge and announce; the Mac's `Tab`, rail row (⌘7)
  and remembered-lens handling, all gated on the Diagnostics preference. Its cards are the shipped
  `QuoteCard`, so timecodes play and tags, stars and hides take the report's own paths. The Mac
  sidebar's status line reads *Screens · N of M* while the job reads (21 locales; time left only
  in the tooltip, and only once this pass has measured its rate). Turning Diagnostics off restarts
  every server that was reading screens, not just the one on screen.
- **Owed before it leaves Diagnostics** (accessibility review, 14 Oct). Below AA as built: the
  board is laid out for a pointer. Each is a blocker for shipping, none for a diagnostics build:
  focus is lost to the page when ↑/↓ or ←/→ changes the board under it; cards cannot be rearranged
  from the keyboard (only reset); the line a pinned quote is about exists only as a drawing (needs
  "On screen: …" text per pinned card, which also covers the leaders' 1.4.11 contrast); the
  reading and failure notes share one live region inside the remounting board; the navigator's
  links read a bare number; no narrow-width layout (1.4.10); and the shared quote card's hide and
  revert buttons stay invisible under keyboard focus, which bites harder here because `h` and `s`
  are gated to the Quotes lens. Landed now: a card rises when focused, alt text on the screengrab,
  screen and participant changes announced, ↑/↓ left alone with one screen, contrast of the
  participant buttons and the current navigator row.

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
· Delivery*, with the screen's still on hover. The owner's layering, in order: first confirm the
screen, then where it sits in the journey (*step 2 of 5*), then what on it was salient — a line of
the screen's own text the quote is pinned to (§3.5), such as a safety warning in the basket. It works wherever quote cards already appear (Quotes,
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

**S3. The transcript reads with its screens** (*said × screen × shown*). The transcript margin carries
a thumbnail of the screen at the moment the participant arrives on it, with the screen's name; a
paragraph can show what was on screen as it was spoken, folded by default. From any quote, *show
the moment* opens this. **Read-aloud highlights:** words a participant says that are also on the
screen at that moment get a gentle blue wash (the accent at 15%, a tint the theme already mixes).
Participants read out what their attention is on, so the wash shows where the talk is about the
page. Measured: 57% of participant paragraphs during a share contain a run of 2+ words that is on
screen at that moment (§3.5).

**S4. The session timeline gains a screens lane** (*screen*). Under the tapestry tracks, each visit a
named bar; search matches as ticks.

**S5. The Screens lens** (*screen × said*). After the real-data test the owner's preferred shape is a
**board**: a large screengrab with every quote said on that screen around it, the quotes pinned to
the elements they are about, like a research wall with stickies on a printout. Prototype template:
[`experiments/screen-text/screens_lens.html`](../experiments/screen-text/screens_lens.html), drawn by
`screens_board.py` from real indexes into a private page (real screengrabs and quotes never enter
the tree). What the prototype settled:

- **Navigation** is a list of every screen: a thumbnail (stacked when several participants saw it),
  the page's own title (its tallest heading; for a session keyed by tab title, the title), the
  address, the quote count, and micro participant codes that wrap and stop at twelve with *+N*.
- **A screen with several participants** is a stack of their screengrabs, flipped with the person
  badges top right (← →). Quotes from a participant whose element was matched on another's page are
  carried onto it, dashed.
- **Every quote is the shipped quote card** at the label size, with the star, tag and hide controls,
  the hidden counter ranged right on the sub line as on the Quotes lens. Quotes not pinned to an
  element sit under the screengrab with **no heading and no different treatment**: same size,
  shadow, gutter and behaviour. They are not lesser, only unmatched.
- **Cards sit beside the screengrab, never over it.** This reverses the prototype, whose cards
  overlapped the screengrab's edge by 24px. The owner, 14 Oct 2026: the screengrab is the artefact
  the comments are about, and *"if you got real stickies and put them over a printout of the screen
  so you couldn't see the actual design being discussed, that's a bit weird"* — overlaid, the screen
  feels cramped and disrespected. So automatic placement never covers it: a card column (270px)
  sits across a gutter of `--bn-space-xl` that the leader visibly crosses, and when the stage
  narrows **the screengrab shrinks; the cards and the gutter keep their size.** Two columns from
  1084px of stage, either side by which half of the page each element is in; one column, on the
  right, from 782px; below that, none — the screengrab takes the full width with its highlights, and
  its pinned quotes lead the list under it. Those thresholds keep the screengrab at least 480px wide
  (`MIN_SHOT_W`, the floor for legibility, in `frontend/src/islands/screens/layout.ts`). A column
  with no cards takes no room, so one card does not leave a wide empty margin opposite it. A card
  the researcher drags may go anywhere, over the screengrab included: that is their arrangement.
  Measured on both real sessions at 1800, 1280 and 900px windows: every column card 32px clear of
  the screengrab (24px over it before); at 900px the screengrab is full width where it was 104px
  wide behind the cards. Numbered markers on the screengrab, for the narrow case, belong to the
  coming composition work.
- **A real drop shadow** (the house tooltip's shape, in the palette's own shadow colour) keeps a
  card from merging into a white page. **Only a card that floats has one** — a pinned card in a
  column beside the screengrab, or one moved by hand; the quotes in the page's flow under it, and
  the navigator's thumbnails, read as the Quotes lens's do (the owner, 14 Oct 2026: shadows in
  spurious places).
- **A card is what it is: one size, always.** Every card shows its whole quote, as the Quotes lens's
  cards do; a long quote is a taller card. Nothing changes a card's size or the board's layout —
  not selecting it, not focusing it, not pointing at it (the owner, 14 Oct 2026: *"they should be
  what they are — we are allowing repositioning, and z-index re-ordering — selection brings to the
  front"*). The first build clamped every card to seven lines and unclamped the selected one; that
  is gone. **Selecting** a card (a press on it, or keyboard focus) raises it and shows the shipped
  focus treatment, and the others dim by colour, not opacity, so a stack stays opaque; Escape or a
  press anywhere else deselects. Never on hover: hover flickered, two ways — the unclamped card grew,
  its column re-placed, and in a stack a different card was then under the pointer (read in the
  placement code, not reproduced: the sessions measured never stacked); and every card on the board
  dimmed and undimmed as the pointer crossed them (11 times sweeping across 6 cards on a real
  session, 0 now). Measured on both real sessions at 1800 and 1280px windows, every card selected in
  turn (64 selections): no card on the board moved or changed size by a pixel. Gated by
  `tests/test_screens_css.py`: a selected, focused, hovered or edited state may set only properties
  that cannot move anything, and no quote is clamped.
- **A column that would run past the screengrab stacks**, evenly stepped, straight (the diagonal
  offset was prototyped and dropped), the later card over the earlier one's tail; selecting one
  brings it to the front of its stack.
- **The researcher can rearrange, and the board respects it** (the owner, 14 Oct 2026: *"if the
  user does nothing but resize, re-order automagically; if they reposition some or all cards,
  respect that work and intention but still re-organise the cards they didn't touch"*). A hand
  cursor on a card's top edge and the margin under its timecode; drag it anywhere on the board.
  A placed card is stored as **intent, not coordinates**: which side of the screengrab its centre
  fell on and how far down that edge, as a fraction of the screengrab's height — so it moves with
  the image as the stage resizes, and the researcher's order among their placed cards holds. In a
  column, **placed cards win**: each keeps its spot, and the untouched cards re-flow around them,
  each into the free slot nearest its own line, in the lines' order. Where a placed card's side has
  no column (one column, on the right), it goes to the right; with no columns it leads the list
  under the screengrab; it returns to its side when the width allows. A card dropped with its centre
  over the screengrab stays over it, where it was put (the researcher's choice; automatic placement
  never covers it). A placed card carries a faint mark at its corner, and right-click offers
  *Return to automatic* for that card. Kept in the browser's storage per screengrab
  (`layout.ts`); the first build's coordinates are converted once, then dropped. Measured on both
  real sessions: a card placed at the top left pushed the untouched one below it, the right column
  then took no room (the screengrab widened from 700 to 1002px), and resizing to 1280, 900 and back
  sent it to the right column, the head of the list, and back to its spot.
- **Arrangement and Tidy.** Nothing shows while the layout is automatic. Once any card is placed by
  hand, *Arrangement: Custom* sits ranged right on the sub line; on hover and on keyboard focus the
  same fixed-width slot reads **Tidy**, so nothing moves when the words swap, and its accessible name
  is one sentence, *Arrangement: Custom. Tidy*. Pressing it returns every card on this screengrab to
  automatic, with no confirm: it is undoable with ⌘Z (Edit ▸ Undo Tidy) through the report's one
  undo stack. Right-click on the board offers *Tidy* too, and the keyboard reaches it as the slot's
  own button. *Tidy* is the owner's word (one short action word; *Clean Up* sounded like toys going
  back in the box) and here means **return to automatic**; a gentler Tidy that keeps your sides and
  order and only evens out the spacing, like the Finder's, is a possible later variant. A View-menu
  row on the Mac belongs to the menu work.
- **The researcher says which pages are one screen** (§3.6): drag one screen's thumbnail onto
  another, or right-click; *Not the same screen*, beside the participant badges, peels the showing
  participant's page off into a screen of its own, one at a time, which works for any number of
  participants. Prototyped, not designed: needs real prototyping before it is built.
- **No new tokens.** Every colour is a palette token (default and Edo) or an accent tint at a
  percentage the theme already mixes (6%, 15%, 30%); lift is the shipped `.bn-focused` treatment.

Friction as evidence (counts, back-steps, time on screen), never a score. The earlier flow and grid
shapes (`design-screens-lens.md` §5) remain the overview; the board is what opens from them.

**S6. Sections grounded in screens** (*said × screen*). The report's speech-derived sections show
where they were said, with the screen's thumbnail in the section head, and flag the quotes said on a different page from their section. The smaller
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

### 3.5 Pinning a quote to an element

A quote is placed on a screen by its timecode. It is pinned to one line of on-screen text when it
shares a run of words with it (two or more, with a content word, or one rare word), or failing that
when a multilingual sentence model (LaBSE) says they mean the same thing. Measured on the three
sessions (`experiments/screen-text/README.md`, fourth pass):

- **Positions are per moment.** A line's box moves as the page scrolls, so a pin is matched on the
  still it is drawn on, re-read at that moment, not on the episode index.
- **47 quotes placed on a screen; 15 pinned by shared words, 8 by meaning, 24 left unpinned.**
- **Precision 17 of 23** against hand labels, once lines are limited to the web page (no call tiles,
  no browser bars) and page furniture is dropped (a line flagged sticky, or seen on 5+ screens of a
  session). A 3-screen bar for furniture also dropped real controls such as *Continue to checkout*.
- **Still wrong:** a cookie banner, a one-word button whose word happened to be said, a site welcome
  line matched by meaning, a heading chosen over the line actually discussed. Consent banners are
  the one place a small list of phrases would earn its keep; browser and call chrome is better
  removed by position (the crop) than by word lists.
- **Pins carry across languages:** a UK quote about the shopping bag lands on the German
  *Warenkorb* heading, matched by meaning and position.

### 3.6 Is it the same screen?

Stacking two participants' pages and combining their quotes is only right when it is the same page.
The first key, the URL template with product and category slugs masked (`/cat/*`), was wrong: it
stacked a UK jars category page with a German storage-furniture category page.
`experiments/screen-text/same_screen.py` measured the alternatives on labelled pairs (within one
session, the exact address is the label: 165 pairs, 12 the same page):

| key or signal | result |
|---|---|
| **Address with the slug cut to its ID** (`/cat/15950` ≠ `/cat/st001`) | exact where visible: same for home, cart and delivery across UK and German, different for both category pairs and the product pair |
| Tab or window title | works where shown; the only key on Safari's default (host-only) address bar |
| Page text, rare words in common | AUC 0.89; at a threshold of 0.35–0.50 finds 8 of 12 same-page pairs and wrongly joins 6–13 of 153 others |
| Whole lines in common, meaning | AUC 0.91 each |
| Layout of text, a 32×20 picture | AUC 0.78 each; the picture is wrecked by scrolling |
| The page heading | equal on 5 of 12 same-page pairs and on 12 of 149 different ones |
| Rare words + picture + layout or + meaning | AUC 0.92 |

A 90% text match does not work: OCR sees only the visible part of a page, and two views of the same
page in one session share a median 74% of their words. Across languages text shares nothing (the UK
and German carts share 1% of words), so there the address is the only key — a bonus, not the bar
for v1.

**The ladder for v1:** (1) the address with IDs, where the address bar shows a path; (2) the tab or
window title; (3) otherwise a combined score of words, lines, picture and layout as the machine's
best guess; and always (4) **the researcher fixes the guess** in one gesture (S5: merge by dragging
a thumbnail, *Not the same screen* to peel one off). Full-screen browsing, mobile Safari (host
only), native apps and prototypes all fall to rung 3. The next spikes there: a picture match that
tolerates scrolling, and the top of the screen alone (headers and app bars sit still), measured on
real mobile recordings, of which there is one.

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

**Phase 2 — screens and routes.** `utils/screens.py` (visits, page keys by the §3.6 ladder,
cross-session screens, quote join, element pins per §3.5, section link) as pure functions; the
overrides table (merge, peel, rename, hide, and the researcher's arrangement of a board); the
routes; export classification.
**Exit:** `GET …/screens` answers for the two measured sessions as the evidence doc predicts.

**Phase 3 — the first surfaces**, as Phase 0 ordered them. The likely first three: S1 (the quote's
screen), S3 (transcript markers), S2 (screen and shown tokens, the moments list). Browser and the
Mac's web view together; 21 locales; absent in export mode.

**Phase 4 — the Mac app and shipping.** The native search menu gains the two token kinds through the
bridge contract (`tests/fixtures/search-bridge-contract.json`; an older build ignores an unknown
kind); the switch and its sentence in Settings; a TestFlight-signed build, the privacy manifest's
coverage of pyobjc, and an app-store-police pass.

**Phase 5 — the Screens lens** (S5, the board) and sections grounding (S6), with corrections, and the labelled
set that dialog-level states need before any detector (`design-screens-lens.md` §4.2, §9).

**Phase 6 — other platforms.** A RapidOCR engine as an optional extra: pinned, hashed, self-hosted
models; the 960 px detection cap, 2 threads, the unchanged-frame gate; measured first on real amd64
Linux and Windows machines, since every number so far is from one Mac. It passes the conformance
suite and the surfaces appear: nothing above the seam changes.

**Not every study is screen-based.** The owner's rule: the lens should not appear for a study that
is plainly not a screen-based interview, even when there is video. The signal is unmeasured; the
candidate is the share of sampled frames that are text-dense with a browser or app frame present,
measured on talking-head interviews against these sessions. It belongs in Phase 1, since the index
can answer it cheaply, and decides whether S1–S6 appear at all.

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
8. ~~**On the board, hover or click to bring a quote to the front, and straight or diagonal stacks?**~~
   Settled 14 Oct 2026: click, and straight (§2, S5).
9. **Whose arrangement is it?** A rearranged board is a researcher edit; is it saved per project like
   other edits, and does it reach the export one day?
