---
status: proposal
updated: 15 Oct 2026
---

# Screens: where they went, what they said, what was on screen

**Status: the plan, 13 Oct 2026; built since 14 Oct, and out of Diagnostics since the night of
14 Oct (below).** Decided by the
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
- **How to turn it on.** _Superseded the night of 14 Oct — see "Out of Diagnostics" below._ Mac
  app: Settings ▸ Transcription ▸ **Read shared screens**, on by default. CLI: `serve --dev`, or
  `BRISTLENOSE_SCREEN_TEXT=1`. Off, the job never runs, `/screens` and `/screens/status` answer
  `enabled: false`, and the still route 404s.
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
- **Owed before it leaves Diagnostics** (security review, 14 Oct). _Paid the night of 14 Oct except where "Out of Diagnostics" below lists it as still owed._ The Diagnostics switch does not
  yet say it reads shared screens (§4.7's sentence; the help text is a 21-locale change). The index
  stores every line as read, chrome and full addresses included, where §4.3 drops chrome and
  query strings at rest; off-task screens (§4.5) are not hidden. Stills are cached on disk under
  the session's id, so the pipeline's per-session prune removes a withdrawn participant's, but
  turning Diagnostics off does not delete them.
- **14 Oct 2026, late: the data half of that list is paid.** At rest the index keeps no query
  strings, no fragments but an app's routes, and no chrome (§4.3, as now written); `INDEX_VERSION`
  is 3, so every older index is read again and replaced. Turning reading off deletes (§4.8): the
  Mac app passes `BRISTLENOSE_SCREEN_TEXT=0`, and a serve started with exactly that deletes the
  project's `intermediate/screen-text/` (indexes and stills) before anything can read it; unset,
  the CLI's default, deletes nothing, and `--dev` does not turn an explicit off back on.
  `GET …/screens/status` now says `has_screens`, so the lens is shown only where there is
  something to show; the rule is in the route's docstring. Still owed: the switch's one sentence
  (§4.7), off-task screens (§4.5), and a URL's **path** is kept whole, because product and
  category IDs in it key screens — a token in a path is stored.
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
- **Owed before it leaves Diagnostics** (accessibility review, 14 Oct). _Paid the night of 14 Oct except where "Out of Diagnostics" below lists it as still owed._ Below AA as built: the
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

- **14 Oct 2026, night: out of Diagnostics.** Diagnostics gates Screens nowhere, on either side.
  - **The switch** is Settings ▸ Transcription ▸ *Read shared screens*, on by default, with §4.7's
    sentence under it (21 locales). Every serve gets `BRISTLENOSE_SCREEN_TEXT` from it (`1`/`0`),
    and turning it off restarts every serve that was reading and deletes what each had read (§4.8).
  - **When the lens appears:** reading is on, an engine is available, and the study has screens
    or a first read is under way — `enabled && unavailable == null && (has_screens || (total > 0
    && (running || done < total)))` from `GET …/screens/status`. Three copies of that rule
    (`routes/screens.py`'s docstring, `frontend/src/islands/screens/availability.ts`,
    `ScreenReading.isAvailable`) each carry their own tests; a talking-head study reads, finds
    nothing, and the lens never shows. On the Mac a window on Screens moves to Project when the
    lens goes, and only a 404 from the status route counts as "gone" (a 5xx during a re-analyse
    keeps it).
  - **Localised:** `common.json` `screens.*` and `nav.screens`, the Mac's toolbar and View-menu
    rows (`desktop.toolbar.screens`, `menu.view.show/hideScreens`), glossary rows; every reason
    code a whole sentence per language.
  - **Accessibility, landed:** focus survives a board change (to the current navigator link, the
    pressed participant — since 15 Oct the checked version badge — or the board's title), and Tidy and the right-click menu return focus
    rather than drop it; every card and Tidy are on the keyboard; one live region, outside the
    board, carries only reading progress; the arrow keys leave an open dropdown or menu alone; a
    move is said once, not twice; leaders at full strength (1.4.11) and the menu's highlight no
    longer white on accent (1.4.3).
  - **At rest:** addresses lose query strings (localhost, IPs, intranet hosts and any slashed
    path included) and every fragment but an app route without a percent-encoded value; chrome
    is not stored where there are dense frames to find it (§4.3); `INDEX_VERSION` 3, and an index
    from an older version is deleted with its stills at serve start and at each pass, as are
    stills from before they were named by session.
  - **Still owed** (none blocks release; each is recorded where it belongs): navigator links read
    a bare number; no "On screen: …" text per pinned card; no narrow-width layout (1.4.10) —
    _15 Oct: below one column the linked cards now sit in rows with their leaders (S5, "Rows"); not
    yet measured at 320px_; cards
    cannot be rearranged from the keyboard; off-task screens (§4.5); typed values (§4.4); a
    global delete when reading is turned off (per project today, at that project's next serve);
    the visibility rule served by the route rather than copied three times. Before the release
    that ships it: a signed build with pyobjc through the `.pkg` gates and `altool --validate-app`
    (no signed build has carried pyobjc yet), a Team-ID sweep over the sidecar's `.so` files, and
    a line in the App Review notes that *Read shared screens* reads recordings and asks for no
    screen-recording permission.

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

_The owner's feedback round of 15 Oct 2026 (evening) changed several rules below; each says what it
reverses. Earlier wording is kept where it explains why._

- **The navigator** is a list of every screen: a thumbnail (stacked when several participants saw
  it) and the page's own title (its tallest heading; for a session keyed by tab title, the title).
  - **Built like Discussion's guide** (the owner: *"navigation grey bar visually appears to go all
    the way to the top in Discussion lens (correct) but does not in Screens"*): a grey pane the
    full height, to the left edge and, in the app, up to the toolbar seam, with no white gutter
    above or beside it (`.dl-lens .dl-nav`'s construction). _Reverses the inset box._
  - **Resizable**, by the guide's mechanism: the shipped `.drag-handle` on its edge, a
    keyboard-operable `role="separator"` (←/→ by 10px, Home, End), Discussion's floor and step
    (`discussion/split.ts`), the width remembered per viewer on release. Below 240px of width the
    thumbnails drop and the names stay (a container query).
  - **The address, the participants' codes and the quote count are kept and not shown**
    (`NAV_DETAILS` in `ScreensLens.tsx`): the owner, *these may belong on the board, as context for
    the screen showing, not in the list of screens.*
  - **The board's info line carries the screen's path and nothing to count** (the owner, 15 Oct
    2026): "10 quotes from 2 participants" added nothing — the participants are the badges at the
    top right and the rough number of quotes is plain from the cards. Parked behind
    `featureFlags.screensQuoteCount`, its strings kept. The hidden counter and the Arrangement
    control stay on that line.
- **A screen is one place for everything about it** (the owner, 15 Oct 2026). Every quote believed
  to be about the screen, from every participant's version of it (X, X′, X″), is on its board, and
  the set does not change with the version showing. _Reverses the prototype's stack flipped by
  person badges, where each participant's view carried only its own quotes and others' were dashed._
  - **Which version: one unit on the heading line**, ranged right where the title's actions go:
    `[15:04] ‹ [p1] [p3] ›` — the house timecode of the showing version's moment (it plays), ‹ ›
    (*Previous/Next version*, 25px targets) to step, and the participants' badges as a single-choice
    **radio group** (one tab stop, ←/→ within it, each radio named *"p3's screen"* — a radio says its
    own position — the group *Versions of this screen*; the timecode is its own link). The checked
    badge wears the shared "you are here" style, `.bn-person-badge-here` (moved from Discussion's
    `.dl-here` into `theme/molecules/person-badge.css`; since the 15 Oct review it meets 4.5:1 and
    carries the emphasis weight as a non-colour cue, in both lenses). Past five versions the badges
    collapse to `‹ p3 · 2 of 8 ›` (that button's name does say the position), the badge opening a
    menu of versions as `menuitemradio`s, opening on the checked one, with Home/End. It opens on the
    version that links the most quotes (`default_tab`). Focus stays on ‹ › and on the collapsed
    button, so they work again and again from the keyboard, and the new version's name is
    announced; on a badge, focus follows the checked one, which says it; from anywhere else the
    change is announced with where and when ("p2's screen at 00:40 · 2 of 3"). **Changing version is
    a cross-fade only**: the cards take their places on the new version without gliding from the
    old one's (15 Oct, review). **Nothing for choosing a version sits on the screengrab.** _Reverses the same morning's carousel: its caption, its page dots, its hover
    chevrons over the screengrab, and its fixed name and key hint (the radio group carries them)._ A
    horizontal swipe over the screengrab still changes version (nothing is drawn for it). Only the
    showing version and its neighbours are fetched and mounted, the stills in a small LRU (24 board,
    96 thumbnails), and they cross-fade in one frame. `frontend/src/islands/screens/carousel.ts`.
  - **No person chips and no dimming by person.** _Reverses the morning's chips (p1 · p2 · p3, which
    dimmed the others' cards)._ Whose quotes may come back as search tokens, as on Quotes; not built.
  - **Linked means on the visible screengrab.** A quote is linked — highlight and leader — only when
    its words are on the version showing (that version's pins, which link every participant's quote
    whose words are on it). An unlinked quote still shows, in the list, and when another version
    links it the card offers *On p2's screen*, which shows that version and focuses the card there.
  - **Where they go.** Every linked quote, whoever said it, goes in the margins; the rest go in the
    list under the screengrab, in time order. Several quotes about one line share one highlight and
    one anchor; their cards sit together at it and their leaders fan into the point.
- **Every quote is the shipped quote card**, with the star, tag and hide controls, the hidden counter
  ranged right on the sub line as on the Quotes lens. Quotes not pinned to an element sit under the
  screengrab with **no heading and no different treatment**: they are not lesser, only unmatched.
  - **One card, one width** (the owner, 15 Oct 2026, preferring the list's wider measure):
    `CARD_W` = 340px sets the margin cards and the list's alike, and the list is a grid of fixed
    columns of that width from the left, not newspaper columns. _Reverses 270px columns beside a
    260px-ish newspaper list._ A card-layout lab may change the number.
  - **No "[When asked…]" line on this lens** — QuoteCard's `showResearcherContext={false}`; the
    owner: *"interesting but new… hide here for the moment"*. The Quotes lens and the code keep it.
  - **No sequence badge.** _Reverses the morning's per-person sequence (p1 ①②③): the timecode
    already says the order._ Time order still breaks ties along an edge and is the list's order; it
    is never drawn.
- **Cards sit around the screengrab, never over it.** This reverses the prototype, whose cards
  overlapped the screengrab's edge by 24px. The owner, 14 Oct 2026: the screengrab is the artefact
  the comments are about, and *"if you got real stickies and put them over a printout of the screen
  so you couldn't see the actual design being discussed, that's a bit weird"*. So automatic
  placement never covers it, and when the stage narrows **the screengrab shrinks; the cards and the
  gutter keep their size.** A column is a card and its widest stagger (`COLUMN_W` = 364px) across a
  gutter of `--bn-space-xl` that the leader visibly crosses. Two columns from 1272px of stage; one,
  on the right, from 876px; below that, rows. Those thresholds keep the screengrab at least 480px
  wide (`MIN_SHOT_W`, `layout.ts`); they follow from `CARD_W`. A column with no cards takes no room.
  A card the researcher drags may go anywhere, over the screengrab included: that is their choice.
- **Placement is boundary labelling** (the owner, 15 Oct 2026): annotations all around the artefact,
  as on an architect's drawing or a UX redline. `layout.ts` (`edgeFor`, `composeBoard`).
  - **Four edges.** A linked card goes to the band nearest its line: left for a line in the left
    half (a left nav), right for the right, top for a header or search box, bottom for a footer.
    The top and bottom bands are kept to clear cases — a line in the top or bottom 15% of the page
    and in its middle 60% — so most cards still go to the sides.
  - **Ordering**: linked cards take the prominent places, ordered along each edge by their lines'
    positions, which breaks time order where it must; time order only breaks ties. Line priorities,
    in order: **no leader over a card, then no crossings, then the shortest lines.** A leader leaves
    its card's facing edge into the gutter, so it does not cross a card in its own column; ordering
    by the lines keeps leaders from crossing; a drafting leader (straight where the line is level
    with or under the card, else a shoulder and one straight run) keeps them short. The one place
    the first rule can fail is a band long enough to wrap onto a second line, where a first-line
    card's leader passes the second line's cards; rare by the band rule, and not yet solved.
  - **A card is never over the screengrab**: columns and bands are their own grid tracks, each a
    gutter (`COLUMN_GUTTER`) from it, and a band reserves its whole height; on a custom board an edge
    card is held its distance out from its edge, never less than none. What gates it, exactly:
    `layout.test.ts` checks the composition against a model of the grid in every mode — it catches a
    band that under-reserves its height, but places the side columns by construction (the model is
    the grid's, so it cannot see the grid itself go wrong) — and checks that a custom edge card never
    covers the screengrab at any size; the lens test checks, at four widths with a stubbed
    measurement, that every linked card gets a spot in a column or band track and never in the
    screengrab's or the free layer (jsdom lays nothing out, so not the pixels); and the pixels were
    measured on two real studies at 1440, 1100 and 800px windows: 0 automatic cards over the
    screengrab, every leader starting outside it.
  - **Rows.** Below the side-column threshold the side bands become rows above and below the
    screengrab (a line in the top half above, the rest below), in order along the edge, with short
    vertical leaders; the unlinked list stays below everything. _Replaces "the pinned cards lead the
    list under the screengrab", which cut every narrow-width card off from its line._ **A custom
    board is shown as these rows too** below the threshold (15 Oct, review: its side columns would
    otherwise push the page sideways at 320px, WCAG 1.4.10). Its arrangement is kept, untouched, and
    shows again once the stage is wide enough; while it is shown as rows nothing is moved by hand
    (the grips and ⌥-arrows rest), and Tidy still offers the way back.
  - **The layout changes only at a threshold, with hysteresis**: narrowing switches at the line
    (the screengrab's floor is never breached), widening waits until the stage is 24px past it, so
    a stage resting on a threshold — where the layout's own height change brings the page scrollbar
    in and out — does not flip back and forth. At a change each card glides from its old place to
    its new one (FLIP); under reduced motion it moves at once; the leaders are measured again when
    the glide ends.
  - **Stacks are internal, and cascade** (the owner, 15 Oct 2026: *"as the original Mac windows did
    in 1984"* — you can see how many there are, they read as separate elements, and each card's
    left-edge grip stays exposed). When a column runs past the screengrab its cards overlap, evenly
    stepped down, and each later card steps `STAGGER_STEP` (8px) away from the screengrab — the left
    column leftward, the right rightward — cascading three steps and starting again; the column is
    sized for the widest step, so no card enters the gutter. Bands wrap onto a further line rather
    than overlap, so they never stagger. Nothing else marks a stack. _Reverses "stacks are straight"
    (the diagonal was prototyped and dropped on 14 Oct) and every stack-only visual._
- **Moving a card from the keyboard** (WCAG 2.1.1, 15 Oct, review): **⌥ + an arrow** moves the
  focused card one step (`MOVE_STEP`, 24px): ↑/↓ along its edge beside the screengrab, ←/→ along a
  band above or below it, ←/→ beside it to the other side; a card dropped over the screengrab moves
  either way. The same model as a drag: the first move freezes the board into custom; each move is
  undoable as *Move Quote* and announced (*Quote moved*). The lens's own ↑↓←→ and the report's
  handler both leave ⌥ chords alone.
- **One shadow for every floating card** — in a column, in a band, or placed by hand — on the
  card's wrapper, softer and tighter than before (`0 1px 2px` plus a half-strength `0 2px 6px`, in
  the palette's shadow colour) so two overlapping cards read as two clean edges. Cards in the list
  carry none, as on the Quotes lens (the owner, 14 Oct 2026: shadows in spurious places). A first
  value; a lab will tune it.
- **Focus and selection are the Quotes lens's, exactly** (the owner, 15 Oct 2026: what is learnt on
  one lens carries to the other, and a future change to the focus model reaches both with nothing
  re-implemented). The only visuals are the shared `.bn-focused` / `.bn-selected`
  (`theme/atoms/interactive.css`); the board adds stacking order — the focused card in front of
  anything it overlaps, and its line lit — and nothing else. A click focuses a card, as on Quotes.
  **Any press anywhere on a card brings it to the front** — its body, star, eye, tag or timecode —
  and it stays in front until another card is pressed or focused (the owner, 15 Oct 2026). A click
  on the grip that does not become a drag selects that card alone and focuses it, as a click on a
  Quotes card does; a dropped card is focused and in front. Stacking only, `is-front`.
  _Reverses the board's own "lifted" selection, its press-to-raise state, and the dimming by colour
  of every other card; the old raised-card shadow also hid the shared dark-mode focus ring._ Gated by
  `tests/test_screens_css.py`: no colour, background, shadow, border or outline on any rule naming a
  focus or selection state in `screens.css`. **A card is what it is: one size, always** — nothing
  changes its size or the board's layout (the owner, 14 Oct 2026: *"they should be what they are"*);
  the same file holds every focused, selected, hovered or edited state to properties that cannot
  move anything, and no quote is clamped.
- **Keys: shared with Quotes** (the owner, 15 Oct 2026). The lens registers its **reading order** —
  the margins as they sit (top to bottom, then left to right), then the list in time order
  (`narrative.ts`) — and the report's shared handler does J/K, ⇧J/K, ⇧-click ranges and ⌘A over it,
  exactly as on Quotes, with s/h/t/r/x/Enter scoped to the same cards. Focusing a card by J/K brings
  it to the front and lights its line, as a click does. The lens keeps only **↑/↓ (another screen)
  and ←/→ (another version)**: on Screens `useKeyboardShortcuts` returns early for the arrow keys
  alone. _Reverses the morning's lens-owned J/K in time order, filtered by chip._ `?` opens the
  shortcuts page on bristlenose.app, which lives in the website repo; the Screens pair belongs there.
- **Menus and quote actions** (the owner, 15 Oct 2026: *"we also have the Quotes menu, and I would
  expect star and hide and tag to work the same"*).
  - **Quote actions work on Screens.** Quotes ▸ Star, Hide, Add Tag, Apply Last Tag, Reveal in
    Transcript, Play, Next/Previous Quote, Extend Selection and Toggle Selection enable on Screens as
    on Quotes (`MenuCommands.swift` `onCardLens`), and so do the bare keys. They act only on a card
    this lens renders (`useKeyboardShortcuts` `scopedFocus`/`scopedSelection`, against the order the
    lens registers), never on a selection or cursor carried over from Quotes. Export stays on Quotes.
  - **Discussion is not a card lens**: it renders transcript turns with its own focus, not the
    shared QuoteCard under FocusContext, so the quote actions stay off there (verified, not assumed).
  - **View menu**: one Next/Previous pair that follows the lens — *Next/Previous Screen* on
    Screens, *Next/Previous Question* on Discussion (which steps the navigator through the asked
    questions, wrapping), dimmed elsewhere and reading Screen (`LensStep`); *Next/Previous
    Screenshot* (the version) on Screens; and **Tidy**, enabled only while the board is custom
    (`screens-arrangement` bridge message). No bare-key equivalents: a bare menu key steals typing.
    Labels are `desktop.menu.view.*` in 21 locales. Catalogue: `docs/design-desktop-menu-actions.md`.
- **The arrangement: automatic, or the researcher's** (the owner, 15 Oct 2026: *"when I drag a card
  I'm saying leave all the other cards where they are and move this one… Tidy is the
  get-out-of-jail card… losing custom positioning is a choice"*). _Reverses the 14 Oct rule that the
  cards the researcher did not touch re-flow round the placed ones (and its "placed cards win",
  partial arrangements and corner mark)._ `layout.ts`.
  - **Automatic** is the default: the layout places everything and re-flows on any change.
  - **The first drag switches the whole board to custom.** At that moment every card on the board
    is frozen where automatic layout had it, and only the dragged card moves; nothing else jumps.
  - **In custom nothing ever re-flows.** A drag moves only its card. A card that arrives later (a
    re-read, or one shown that had no spot) waits in the list under the board until Tidy.
  - **Intent, relative to the screengrab**, so a window resize **scales** the arrangement: a card
    beside, above or below it keeps which edge, how far along it (a fraction of the screengrab's
    height or width) and how far out (px, the gutter and any stagger, which does not scale — so a
    card frozen beside the screengrab never slides onto it); a card dropped over it keeps its
    top-left as fractions. **A card that was in the list freezes as a bottom-edge card**: its left as
    a fraction of the screengrab's width from the screengrab's left (negative where the list starts
    left of it), its distance below the screengrab in px. Shrinking may make cards overlap one
    another; that is accepted. A custom board holds its columns and bands open for the cards on each
    edge, whatever the width.
  - **Tidy is the only way back to automatic**, everything gliding home at once (instant under
    reduced motion), from three places: the arrangement control on the sub line (*Arrangement:
    Custom*, reading **Tidy** on hover and keyboard focus, one accessible sentence), the right-click
    menu, and View ▸ Tidy on the Mac (`bn:menu-action` "tidy"). *Tidy* is the owner's word.
  - **Undo**, through the report's one stack: every drag is *Undo/Redo Move Quote*
    (`undo.undo.moveQuote`, 21 locales), and undoing the drag that switched the board returns it to
    automatic; Tidy is *Undo Tidy*. **Return to automatic**, on one card of a custom board (the
    right-click menu), means *back to where Tidy would put it*: a linked card to its automatic spot
    on its edge, frozen there so nothing else moves; any other card to the list. It is an undoable
    *Move Quote* too.
  - **Never lost involuntarily.** Arrangements are kept per **version** — the screen's key and the
    participant's session, not the still's moment, which a re-read may pick differently — so a
    re-read, a change of version and back, or a card hidden and shown again all find the
    arrangement as it was. The 14 Oct store (`session@t`) migrates once per version on first view,
    its placed cards keeping their spots, **and the rest of the board frozen where automatic puts
    it**, as a first drag freezes it — or the linked cards it never placed would drop into the list
    and read as "my cards disappeared" (15 Oct, review). Entries for a `session@t` no version now
    shows (a still moment a re-read replaced) are orphans: left in the old store, never read and
    never deleted. Kept in this browser's storage (§6.9 is still open).
  - **An undo out of sight shows its board first.** Undoing or redoing a *Move Quote* or a *Tidy*
    whose screen or version is not showing switches to that screen and version, then applies, so the
    change is seen (15 Oct, review).
  - **Measured one way.** The screengrab is measured once — its box in the board, border included —
    and that one measure places the cards, freezes them, reads a drop and computes Tidy's spots, so
    a freeze moves nothing by a pixel (the build before measured the image's outer box in one place
    and its inner box in another, so the first drag nudged right- and bottom-edge cards by the
    border). Tidy's bottom-edge spots start under the taller of the screengrab and its side columns,
    as the grid's band does.
- **A live window resize** (utils/liveResize.ts: native's exact start and end on the Mac, a 200ms
  settle in a browser): the board is not recomposed or re-measured while it lasts; it holds at its
  last settled width and **scales as one unit** with a CSS transform, so no card can drift onto the
  screengrab mid-resize. When it ends it recomposes once and every card glides to its new place
  (instantly under reduced motion); a custom board rescales and does not re-flow. A board that
  mounts mid-resize lays itself out first and scales from there; no card glides from a place it
  was never drawn at. A card that held keyboard focus and moved to another parent (a mode change,
  Tidy from the Mac's menu, ⌘Z of a move) gets focus back on the same control.
- **The researcher says which pages are one screen** (§3.6): drag one screen's thumbnail onto
  another, or right-click; *Not the same screen*, beside the participant badges, peels the showing
  participant's page off into a screen of its own, one at a time, which works for any number of
  participants. Prototyped, not designed: needs real prototyping before it is built.
- **No new tokens.** Every colour is a palette token (default and Edo) or an accent tint at a
  percentage the theme already mixes (6%, 15%, 30%).

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

**The owner's position, 14 Oct 2026.** Reading the text on a shared screen does not cross a line:
the researcher already holds the video, watched that screen live on the call, and the participant
consented to the recording. OCR makes searchable what they can already read; it reveals nothing
new to them. The ethical relationship is **between the researcher and their participant** —
Bristlenose is the researcher's tool, and its part is to tell the researcher plainly what it does
(the sentence in Settings, item 7) so they can be honest with participants in their own consent
material. It is not a declaration to Apple: nothing leaves the Mac or reaches us, so the App Store
privacy label is unchanged ("Data Not Collected" holds); the only Apple-facing item is the
technical one of whether pyobjc's bundled libraries need privacy-manifest entries. **The line that
matters is onward flow**, and it stays closed (item 2). Consequently typed values (item 4) and
off-task screens (item 5) are follow-ups, not release blockers: they stay on the researcher's Mac.

One model for the whole project, combining both evidence docs:

1. **Everything stays in the project**, like `transcripts-raw/`: the index, the screens, the stills.
2. **It never leaves**: not in the HTML export, anonymised outputs, clip or quote exports, MCP, the
   chat lens, support bundles, **and never sent to the LLM**. The analysis is a cloud call; screens
   carry bookmarks, colleagues' names and typed addresses. Screen names borrow the report's
   LLM-made section names (made from the transcript) rather than sending screens to name them.
3. **Chrome is not stored** (a line on at least half of a recording's text-dense frames, 25 lines
   or more: names under call tiles, bookmarks). The filter can only see chrome where there are
   dense frames to count from: a recording with none (a talking head, a sparse app) has nothing
   flagged, so its call-tile names are stored. That stays on the Mac, like the video that shows
   them; it is not a gap in onward flow. **An address is read before
   that filter** and stored, because it keys the screen — but never whole: every address in a line,
   the address bar's or one shown on the page, loses its query string, and its fragment unless the
   fragment is a single-page app's route (`#/planner` and `#/summary` are how such an app's screens
   are told apart), which is kept with digit runs of four or more and long opaque tokens masked.
   An OAuth `#access_token=…` or an in-page anchor is never kept (`screen_text/address.py`).
4. **What the filters cannot see stays in the local index**: typed values (postcodes, addresses,
   an email or phone typed into a form), a token in an address's **path** (kept whole, because
   product and category IDs in it key screens), a search engine's terms where they show in the
   page rather than the query, toasts and notifications, and the chrome of sparse recordings
   (item 3). PII redaction (stage 7) works on the transcript and does not touch screen text.
   None of it leaves (item 2); masking is a follow-up, and needed before any onward use.
5. **Off-task screens** (an inbox, a bank) seen by one participant on another host should be hidden
   but counted, and revealable. **Not built yet**; a follow-up, since they never leave the Mac.
6. **No cloud vision**, for naming or merging screens. A local model, or a new consent decision.
7. **One sentence where it is switched on** (Settings ▸ Transcription ▸ *Read shared screens*,
   `desktop.transcriptionSettings.readScreensHint`): *"Reads the text on screens shared in
   recordings, on this Mac, and keeps it with small pictures of each screen in the project’s
   folder. Never sent to the AI, and not included in exports."* It says where the data lives
   rather than "never leaves your Mac", because the project folder may be synced, and it does not
   mention that turning it off deletes: what was read can be read again (owner's call, 14 Oct).
8. **On by default on the Mac; off deletes.** The Mac app reads shared screens unless the researcher
   turns that off. Off, it starts each serve with `BRISTLENOSE_SCREEN_TEXT=0`, and the serve deletes
   what was read for that project — indexes and cached stills — before anything else runs; a project
   not opened again keeps its data until it is. The screens themselves are derived in memory and
   never written. The CLI reads nothing unless asked (`=1` or `serve --dev`), and leaving the
   variable unset deletes nothing: a CLI serve of a project the Mac app read leaves it alone.
   An index written by an older `INDEX_VERSION` is deleted, with its session's stills, at the
   start of each pass (`index.purge_stale`), so a recording that can no longer be read again does
   not keep an index that held more than the current rules allow.

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
2. ~~**On by default on the Mac,** or switched on per project?~~ Settled 14 Oct 2026: on by
   default on the Mac, one app-wide setting; off deletes (§4.8).
3. **Sections and screens:** keep both concepts when screens exist, ground one in the other (S6), or
   let screens replace speech-derived sections where they are observed?
4. **Page-level screens for v1,** with dialogs as researcher-marked states, or wait for a detector?
5. ~~**Typed values:** mask postcode and address patterns in the local index now, or leave them?~~
   Settled 14 Oct 2026: leave them for now; they stay on the Mac (§4, item 4). A follow-up.
6. **Ever in the export?** v1 keeps it all out; a screen map without stills is plausible later.
7. **Should the hover thumbnails share the sampling?** The text-diff moments are where the screen
   changed in a way a person reads.
8. ~~**On the board, hover or click to bring a quote to the front, and straight or diagonal stacks?**~~
   Settled 14 Oct 2026: click, and straight (§2, S5).
9. **Whose arrangement is it?** A rearranged board is a researcher edit; is it saved per project like
   other edits, and does it reach the export one day?
