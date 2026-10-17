# Arrival flash: one landing cue for every in-app link

_Plan and as-built record, 17 Oct 2026. Status: **built on `main`, unreleased**; § As built records where the build departed from the plan after review. Governing docs: `docs/design-motion.md` (§4.2 Acknowledge,
§5 inventory), `docs/design-transcript-gutter.md` § Arrival, `bristlenose/theme/CLAUDE.md`._

## The ask

When a link lands you in a transcript, the paragraph it named flashes yellow and fades. The
owner: "really really useful to find your place with your foveance". Give every link going the
**other** way the same arrival, from the transcript and the surfaces next to it out to the rest
of the app. Tokenise it, so the colour, decay time and easing change everywhere at once.

## What exists (measured 17 Oct 2026)

- **CSS:** `@keyframes anchor-fade` plus `.transcript-segment.anchor-highlight { animation: anchor-fade 5s ease-out forwards }`
  in `theme/templates/transcript.css`. The colour is the palette token `--bn-colour-highlight`, which
  all six palettes define in light and dark (search's `<mark>` uses it too). The duration and easing
  are literals. It has no `prefers-reduced-motion` guard (design-motion §5.3 lists it as unguarded).
- **It is styled only on a transcript segment.** `useScrollToAnchor({highlight: true})` and the
  `navigateToSession` shim add `anchor-highlight` to *any* element, and on anything else it shows
  nothing. That is a latent defect today: no caller passes `highlight` except the shim, and no caller
  passes the shim an anchor.
- **The class is React-owned on the SPA's targets.** `TranscriptPage` adds `anchor-highlight` with
  `classList.add` to an element whose `className` React renders. frontend/CLAUDE.md, Video player:
  «Mark transcript words and segments with `data-*` attributes, never React-owned classes». A
  re-render that changes the className wipes the class mid-flash. It doesn't bite the transcript
  today because nothing re-renders the segment in the first 5 s, but it would bite a quote card that
  `QuotesArrival` is in the middle of un-hiding.
- **`forwards` leaves the background transparent.** That is harmless on a transparent segment and
  wrong on any target that has a background of its own: the card would lose its background for good.
- Frozen vanilla JS (`theme/js/transcript-names.js`, `global-nav.js`) writes `anchor-highlight` in the
  sealed static render. Leave it alone; the shared CSS may change under it.

## Catalogue

Paths are under `frontend/src/` unless absolute. "Flash?" describes behaviour today.

### Out of the transcript (and the surfaces next to it)

| # | Source | Click | Destination and target | Arrival code | Flash? | Target id today |
|---|---|---|---|---|---|---|
| O1 | `islands/transcript/GutterEntry.tsx` (quote mark); `TranscriptPage.tsx` `.bn-gutter-title` (section/theme label) | quote mark, or the section/theme label | `/report/quotes/?reveal=<dom_id>#section-<id>` or `#theme-<id>` (`utils/quotesLink.ts`) | `pages/QuotesArrival.tsx` scrolls to the group heading `h3#<anchor>`, `block:"start"`; the revealed quote is un-hidden and the filters relaxed, but nothing scrolls to its card | **No** | Heading `section-<id>` / `theme-<id>`; card `id={dom_id}` (`islands/QuoteCard.tsx`), unused as a target |
| O2 | `GutterEntry.tsx` (screen mark); `.bn-gutter-title.is-screen`; `GutterThumb.tsx` | screen mark, title or thumbnail | `/report/screens/?screen=<ref>&session=<sid>` (`islands/screens/screenModel.ts`) | `islands/screens/ScreensLens.tsx` reads the query once at mount and opens that screen; the navigator scrolls its `[aria-current="true"]` row to `nearest` | **No** | Navigator row: `aria-current`, no id |
| O3 | `GutterEntry.tsx` (question mark); `.bn-gutter-topic` | moderator question or its topic | `/report/discussion/?item=<id>&turn=<turnId>` (`islands/discussion/discussionLinks.ts`) | `islands/discussion/DiscussionLens.tsx` scrolls `.dl-ask[data-turn=…]` to centre | **No** | `data-turn`, no id. A parked preview lens |
| O4 | *(O1–O3)* `followInApp`, with `from` = `/report/sessions/<sid>#t-<sec>` | Back | the paragraph left from | `TranscriptPage.tsx` hash effect | **Yes** | `t-<sec>` |
| O5 | `Selector.tsx` (session dropdown in the transcript header); `SessionsSidebar.tsx` | another session | `/report/sessions/<sid>`, no hash | — | No | none: a whole transcript, no place to find |
| O6 | `TranscriptPage.tsx` journey chain | journey label | same page, `t-<sec>` | `handleIndexClick`, `scrollIntoView` | No | `t-<sec>` |
| O7 | **Back from a transcript to the Sessions grid** | browser Back / Mac back, after a row, `#N`, journey or timeline click | `/report/sessions/` | none: the grid opens at the top, with no trace of the row you left | **No** | Row: `data-session` only, no id |

The transcript's speaker badges, names and person picker, its margin tag badges and its timecodes
don't navigate (the timecode seeks the player). There is no People lens. The popout player sends no
navigation back.

### Into the transcript

| # | Source | Destination | Flash? |
|---|---|---|---|
| I1 | QuoteCard speaker badge; Signals quote timecode; Sessions-grid journey label; SessionTapestry flags, lanes, popover and timecode; TranscriptionDiagnostics; AutoCode proposal timecode | `/report/sessions/<sid>#t-<sec>` | Yes |
| I2 | Sessions-grid row click, `#N` link; Dashboard session `#N`; native `navigateToSession` | `/report/sessions/<sid>`, no hash | No: nothing to find |
| I3 | **Dashboard featured quote** (no-media fallback) and its speaker link (`islands/Dashboard.tsx` `FeaturedQuote`) | `#t-<sid>-<sec>`, e.g. `#t-s1-123` | **No, and should.** No element has that id, and the transcript's tolerant `/t-(\d+)$/` can't match it, so the page lands at the top. A bug |

### Other lenses (context, mostly out of scope)

- Dashboard section/theme names and the `sections`/`themes` stat cards, and Signals' location
  heading, all go to `/report/quotes/#…` through the same `QuotesArrival` as O1. **They get the
  flash for free** (heading target), and it's the same mechanism, so it stays in scope.
- Codebook tag bar → Quotes: solos a tag. Nothing to find. Out.
- Dashboard stat `signals:section-x-sentiment` → `scrollToAnchor` on an id the React Signals lens
  never renders, so it gives up after 5 s. A separate bug, spun off.
- `useKeyboardShortcuts.ts` `revealInTranscript` never fires: QuoteCard sets no `data-anchor`, and
  `data-participant` is a speaker code, not a session. A separate bug, spun off.

### Other flashes (stay separate, deliberately)

`badge-accept-flash` (0.4 s brightness) and the inspector teaching shimmer are **Acknowledge** cues
for an act you just did, on the thing you did it to. Arrival is a different event ("you are here"),
and it has a different time scale: seconds, because the eye is still travelling. Sharing tokens would
couple two tunings that ought to move independently. `badge-bulk-flash` is unused CSS (no TS
reference): noted, not touched. The playback glow follows the player, not a link.

## Design

### Kind and sibling (`/is-this-bristlenosey`)

Kind: a motion cue, a visual token set plus one shared atom, written by a DOM helper. Siblings:
the **thinking shimmer** (`atoms/shimmer.css`): structural motion tokens in `tokens.css`, keyframes
in an atom, a reduced-motion gate. **Focus Mode's** `--bn-focus-dur` / `--bn-focus-ease`, which set
the naming and the "structural, not palette-overridable" stance. For a destination learning it was
arrived at: the **address**, as `QuotesArrival` (`?reveal=…#…`), the transcript (`#t-N`) and Screens
(`?screen=…`) already do.

| Part | Proposal | Sibling | Verdict |
|---|---|---|---|
| Tokens | `--bn-arrival-colour`, `--bn-arrival-duration`, `--bn-arrival-easing` in `tokens.css` | `--bn-focus-dur/-ease`, `--bn-shimmer-period/-easing` | follows |
| Colour | `--bn-arrival-colour: var(--bn-colour-highlight)`, an alias, not a new contract entry | palettes own colour (`colors/_contract.css`); Focus tokens stay out of the contract | follows. Every palette already answers light and dark through `--bn-colour-highlight`; a palette *may* override the alias |
| Keyframes + rule | `atoms/arrival.css`, one `@keyframes bn-arrival` | `atoms/shimmer.css` | follows |
| Reduced motion | the same rule with a held step instead of a fade | shimmer degrades to static; `focus-mode.css` zeroes durations | departs: shimmer *drops* its cue under reduce; arrival *keeps* it static, because the cue is information (where you are), not decoration |
| DOM marker | `data-arrived` attribute | frontend/CLAUDE.md: «`data-*` attributes, never React-owned classes» | follows |
| Helper | `utils/arrival.ts` `markArrived(el)`; `useScrollToAnchor`'s `highlight` calls it | `useScrollToAnchor` already owns `highlight` | follows (generalised, no sibling hook) |
| Arrival signal | the address | gutter doc § Arrival: a plain click and a new tab arrive alike | follows. Router state is rejected because it doesn't survive a modifier-click into a new tab |
| Back-to-row | before leaving the grid, replace its entry with `#session-<sid>` | `followInApp(e, path, from)` replaces the page left with `#t-<sec>` | follows |

Verdict: Bristlenosey. Nothing is invented, and the single departure is argued.

### Tokens (`theme/tokens.css`, next to Focus and shimmer)

```css
/* Arrival — the "you are here" cue on the thing a link landed on
   (docs/design-arrival-flash.md). Structural: the colour is an alias of the
   palette's highlight, so every palette × appearance answers through the
   contract it already keeps, and a palette may override the alias. */
--bn-arrival-colour: var(--bn-colour-highlight);
--bn-arrival-duration: 5s;
--bn-arrival-easing: ease-out;
```

Same values as today, so nothing visible changes on the transcript. `tokens.css` is embedded in the
Mac welcome screen, so regenerate `WelcomeTimelineCSS.swift` (`scripts/gen-welcome-timeline.py`).

### Atom (`theme/atoms/arrival.css`, registered in `_THEME_FILES` after `shimmer.css`)

```css
@keyframes bn-arrival {
    from { background-color: var(--bn-arrival-colour); }
}
[data-arrived],
.transcript-segment.anchor-highlight {   /* the sealed static render's class */
    animation: bn-arrival var(--bn-arrival-duration) var(--bn-arrival-easing);
}
@media (prefers-reduced-motion: reduce) {
    [data-arrived],
    .transcript-segment.anchor-highlight {
        animation-timing-function: step-end;   /* held, then gone: no fade */
    }
}
```

- **No `to`, no `forwards`.** A keyframe with only `from` fades to the element's own computed
  background, whatever that is: transparent on a segment, the card's own background on a card. It
  never leaves a target without its background.
- `border-radius: var(--bn-radius-sm)` stays a transcript-only rule in `transcript.css`, so other
  targets keep their own radius.
- The keyframes and the `anchor-fade` rule leave `transcript.css`.
- The static render keeps its class, still qualified to the segment, so its behaviour is unchanged
  apart from the reduced-motion guard.

### Helper (`utils/arrival.ts`)

```ts
/** Flash the element a link landed on (theme/atoms/arrival.css). Restarts if already running. */
export function markArrived(el: Element): void
```

- **Restart:** remove the attribute, force a reflow, set it again.
- **Clear on its own `animationend`.** Check `e.target === el` and `animationName === "bn-arrival"`,
  because the event bubbles from children (a badge's `badge-fade-in`). A lingering attribute would
  replay the flash whenever React moves the node or a collapse re-displays it.
- `useScrollToAnchor`'s `highlight: true` calls `markArrived`. `TranscriptPage`'s hash effect calls it
  instead of `classList.add`.

### Destinations

| # | Target on arrival | Change |
|---|---|---|
| O1 / Dashboard / Signals → Quotes | **With `reveal`:** scroll to the quote card (`#<dom_id>`, `block:"center"`) and flash it. **Without:** scroll to the heading as now and flash it | `QuotesArrival`: the scroll target is `reveal` once it has been brought into view, else `anchor`, with `highlight: true`. The 5 s fallback (quotes slow to load) scrolls to and flashes the heading. If the card is revealed later it flashes then too, without a second scroll |
| O2 → Screens | the navigator row of the screen asked for (**built as the screen's title instead**, § As built) | `ScreensLens`: when the arrival opens a screen, record its key; `Navigator`'s current-row effect calls `markArrived` on that row once |
| O3 → Discussion | `.dl-ask[data-turn]` | `markArrived(el)` next to the existing `scrollIntoView` |
| O4 → Transcript (Back) | the segment | `TranscriptPage` uses `markArrived` (fixes the React-owned class) |
| O7 → Sessions grid (Back), **parked** (§ As built) | the row you left | `SessionsTable`: every route into a transcript from a row (row click, `#N`, journey, timeline, diagnostics) first replaces the grid's entry with `/report/sessions/#session-<sid>` (`followInApp`'s `from` pattern). The row gets `id="session-<sid>"`. On mount, a `#session-<sid>` hash scrolls to the row (`block:"center"`) and flashes it, once |
| I3 Dashboard featured quote | the segment | build `#t-<sec>`, not `#t-<sid>-<sec>` |

O5 and O6 are deliberately unchanged. O5 lands on a whole new transcript, with nothing to find. O6
is a scroll within one page under your own hand, where the journey bar already marks the active
label.

### Export mode (hash router, `file://`)

- Quotes and transcript arrival already read the hash router's inner `location.hash` and query.
- The Sessions grid uses `useLocation().hash` (the same thing under both routers). The replace uses
  `navigate({hash}, {replace: true})`, which is router-agnostic.
- Screens and Discussion don't exist in an export.
- CSS animation needs no server.

### What doesn't change

- The search `<mark>` colour (it reads `--bn-colour-highlight` directly).
- The acknowledge flashes.
- The frozen JS.
- The scroll mechanics (`scrollToLand`).

## As built (17 Oct 2026, after three plan reviews and the build)

Reviewed by code-review, ux-critique and Ockham. Where the build differs from the design above,
this section is what shipped:

- **The selector is `:root [data-arrived]`, not a bare attribute.** At (0,1,0) the flash lost
  `animation` to the player's `.bn-timecode-glow.bn-timecode-playing` pulse (0,2,0, `atoms/timecode.css`).
  So a paragraph or card the popout player was on showed no flash, which regressed from the old
  `.transcript-segment.anchor-highlight`. Now it is (0,2,0) and loads after `timecode.css`.
- **No reduced-motion override.** The plan's held `step-end` was rejected. A colour fade moves
  nothing, and a fade is what reduced motion replaces movement with (Apple HIG, Accessibility ▸
  Cognitive). A held peak that then snaps off would keep the brightest moment, which is the
  least-legible one in dark mode, five times longer, and the snap pulls the eye back.
  `design-motion.md` §5.3 records it as unguarded by decision.
- **Headings round their corners while flashing** (`h1`–`h3[data-arrived]`). They are full-width
  blocks with no padding, so the flash otherwise drew a hard-edged strip.
- **`markArrived` also clears on `animationcancel`.** A flash cut short by the element losing its
  box never fires `animationend`, and the attribute would replay the flash when the element is
  shown again.
- **Screens flashes the screen's title on the board (`h1`), not the navigator row.** The row is
  already marked as selected (selection background and accent border), so a flash there is a second
  "this one" on a side panel. With the navigator closed, the row flashed minutes later, when it was
  next opened. The board's title is where the eye lands. The flash waits until the board renders,
  so the loading shell's "Screens" heading is never the target.
- **The late-reveal flash was dropped.** When the 5 s fallback fires first, the heading flashes
  and the card doesn't.
- **O7, back to the Sessions-grid row, is parked** (TODO.md, Ideas). It is history handling, not a
  flash on a link that already lands: a hash replace before every exit from a row, a row id, a
  `followInApp` on the `#N` link, and a mount-time scroll. The TODO entry holds the design: one
  `openTranscript(sid, hash?)` helper, and `block: "nearest"` per the UX review, so Back doesn't
  re-centre a row that is already visible.
- **Naming:** the tokens follow `--bn-overlay-duration` and `--bn-shimmer-easing`, not Focus's
  `-dur`/`-ease`, as the sibling table above claimed.
- **Serve now uses the running theme CSS.** Since `2f612766` (same day), serve and export use the
  running version's theme CSS, not the copy baked at analysis. So `[data-arrived]` reaches projects
  analysed before this change. Before that commit, moving the transcript to the attribute would have
  cost every older project its flash.

### Judgement calls left open

- **The colour.** All six palettes' highlights are yellows or ochres. In dark mode, body text
  behind the flash's peak is under 4.5:1 in four of the six (UX review measurements, recorded in
  TODO.md). Search `<mark>` has the same problem. Whether arrival gets its own palette entry is the
  owner's call (TODO.md).
- **When the flash starts.** It starts with the scroll, not when it settles. A long Quotes jump
  can spend about 1 s of the ease-out before the card is still. Fixing that needs a "landed"
  callback from `scrollToLand`.
- **Programmatic jumps that don't flash.** O6 (the journey label) and the TOC sidebar don't flash,
  but Dashboard → the same Quotes heading does. A candidate rule: "a link to another place flashes;
  a jump within the page you are reading doesn't". Not written down yet.
- **A hidden quote's reveal can lose its flash to a remount.** A `/quotes` response that comes back
  still marked hidden unmounts the card mid-flash, and the re-mounted card has no mark (and
  `scrollToLand` stops correcting). The re-apply window makes it rare.

## Tests

**pytest:** `tests/test_arrival_css.py` reads the concatenated theme (`load_default_css()`). This is
the test that the tokens drive the animation:

- `@keyframes bn-arrival` reads `var(--bn-arrival-colour)` and has no `to` frame.
- Every rule animating `bn-arrival` reads `var(--bn-arrival-duration)` and `var(--bn-arrival-easing)`,
  with no literal time and no fill.
- The SPA marker is among them.
- The three tokens exist, and the colour aliases `--bn-colour-highlight`.

**vitest:**

- `utils/arrival.test.ts`: sets the attribute; restarts; clears on its own `animationend` or
  `animationcancel` only, not a child's and not another animation name.
- `useScrollToAnchor.test.ts`: `highlight` sets `data-arrived`.
- `TranscriptPage`: a `#t-` arrival sets `data-arrived` on the segment.
- `QuotesArrival`: with `reveal`, the card is the scroll target and flashes; without, the heading does.
- `ScreensLens`: an arrival flashes the screen's title on the board; an ordinary open flashes nothing.
- `DiscussionLens`: an arrival flashes the asking.
- `Dashboard`: a featured quote's link is `#t-<sec>`.

Each new test was proven to fail with its fix reverted (17 Oct 2026). The one exception is the
reflow in `markArrived`, which jsdom can't observe.

**Human QA** (CSS is baked per project; use `serve --dev` or a fresh project):
- Transcript gutter → quote / screen; Back to the paragraph.
- Sessions row → transcript → Back.
- Every palette in light and dark.
- macOS Reduce Motion on.

## Out of scope

- Signals stat anchor `section-x-sentiment` (the lens has no such id).
- `revealInTranscript` dead path, already logged in TODO.md (16 Oct).
- Unused `badge-bulk-flash`.
- O7, parked in TODO.md.
