---
status: current
last-trued: 2026-10-11
previous-trued: 2026-09-22
trued-against: HEAD@main on 2026-10-11 — status/handoff (every tool shipped), Tools 3–8 table, the Session timeline (tool 10), the curtain's blank start and snapped frames, the stylesheet-sourcing rule, Where things live
---

# Welcome screen — study-tools cell illustrations

> **Trued 2026-10-11 — nothing is left to build.** Video clips, Send to Miro and Ingest
> shipped on 20 Aug 2026 (native, webview, native; the last three screenshot imagesets
> are deleted), and a tenth illustration, the **Session timeline**, shipped on 9 Oct
> 2026 — see "Added tool — Session timeline" below. The brief text further down is kept
> as written; it read "three remaining" until this pass. Counts at HEAD: **10 webview
> templates** (`tests/test_welcome_curtain_contract.py` asserts the number) and **4
> native views** (SentimentFan, BookShelf, Ingest, Clips). The curtain changed on
> 11 Oct: see §"The curtain".

> **Trued 2026-07-26** — Codebooks (tool 2) shipped this session as the manual-tags
> illustration, and the seven-sentiments fan was halved in speed. Updated from
> "one shipped, seven remaining" to two shipped, six remaining.
>
> **Updated 1 Aug 2026** — Tag (3) and Star & hide (4) have shipped as webviews,
> and a NINTH cell was added and shipped: **Connect an AI agent** (a faked-up
> Claude Code session over the real `/mcp/` tool names — see its section below).
> Five cells now carry real illustrations; four of the original eight remain.
>
> **Updated 2 Aug 2026** — two decisions, and the pool is down to three.
> (1) **No screenshots long-term** (Martin) — the three remaining PNG slots
> (Video clips, Send to Miro, Ingest) convert to themed Swift or webviews;
> which of the two is still the per-tool call, but a baked screenshot is not an
> option for any of them. Resizing a screenshot is cheap, and an *allusion* to
> the tool is more interesting than a photograph of it — plus it's responsive.
> (2) **Redact PII is withheld from the desktop pool**, not merely unillustrated:
> `pii_enabled` is CLI-only and no desktop control exists — so the slot was
> teaching a tool the `.app` cannot *reach*. (This bullet also said Presidio and
> spaCy sit in the sidecar spec's `excludes=[]`. **That stopped being true on
> 12 Sep 2026** — they are bundled; only the `en_core_web_lg` weights are
> excluded. The withholding stands on the remaining half: nothing writes
> `piiEnabled`. Corrected 20 Sep 2026.) Commented out verbatim in `studyTools` as the reference copy;
> restore it when the capability ships on the Mac (tracked in the maintainer's
> private planning notes, §2 Broken ▸ Should).

**Handoff for a new session.** Replacing the static screenshots in the Welcome
screen's large "Study tools" cell with tiny looping illustrations, **one tool at
a time**. Tools 1–4 (AutoCode, Codebooks, Tag, Star & hide) plus the added
Connect-an-AI-agent cell are **built and shipped in-app**; this doc is the brief
for the **three remaining — Video clips, Send to Miro, Ingest**. (Redact PII was
the fourth; it is withheld from the desktop pool entirely — see the 2 Aug note.)

## Why we're doing this (Martin, 25 Jul 2026)

The study-tools cell (`studyTools` in `WelcomeHomeView.swift`) rotates through its
pool, and each slot originally carried a baked macOS screenshot (`image:`). Replace
each with a drawn illustration because:

1. **Themeable** — light/dark + palette for free (a PNG is baked light-mode).
2. **Responsive** — resizes with the cell (a PNG has one fixed size).
3. **No macOS chrome** — we stop shipping screenshots of our own UI; the idea is
   drawn, not photographed. Better all round.

Same playbook as the science cell (`docs/mockups/welcome-science-animations.html`
→ `WelcomeIllustrations.swift`): **prototype idea + motion + copy in an HTML mock
first, then build for real.**

## The build-target rule (per-tool; revised 2 Aug 2026)

- **Webview** when the illustration *reproduces actual report chrome* (real
  badges, quote cards, signal cards). It reuses the shipped CSS verbatim, so it
  **re-syncs when the report styling changes — no drift, no tech debt** — and
  sidesteps the whole platform-matching problem. Precedent: the science *Signals*
  and *Dignity* cells (`WelcomeIllustrationHTML.signal` / `.quote`).
- **Webview also when the motion is bespoke** and HTML/CSS is simply the faster
  way to get the feel right. Precedents: *Emergent themes* (`EmergentThemesView`
  — a webview, despite the cell being a bespoke two-theme swoop) and, decisively,
  *Connect an AI agent*, which draws bespoke **Claude Code** chrome — no report CSS
  to sync at all — and still shipped as a webview, built straight in-app.
- **Native SwiftUI** when the shape is one SwiftUI draws well, or an *existing
  native view* can be reused. Precedent: the science *SentimentFan* and *BookShelf*
  cells (the only two native ones).

_What this revises:_ the rule previously read "native SwiftUI when it's a bespoke
drawing" and listed a "Shoal" cell among the native precedents. Both halves were
wrong — the emergent-themes cell is a webview, and the agent cell then shipped
bespoke-as-webview too. Five webviews and two native views now coexist; the call
is genuinely per-tool. What is *not* an option any more is a screenshot.

The mock is the design surface for *every* tool regardless — HTML iterates
fastest — with the agent cell as the one accepted exception (built in-app because
there was no report CSS to sync; backport a mock section only if it needs design
iteration).

## Tool 1 — AutoCode (DONE, the reference implementation)

Ships as a **webview** (report-chrome → webview). Study it as the template for the
others.

- **Mock:** `docs/mockups/welcome-studytools-animations.html` (has palette +
  light/dark switcher, roadmap, notes).
- **In-app:** `WelcomeIllustrationHTML.autocode(dark:palette:reduce:)` +
  `AutoCodeIllustrationView` in `WelcomeIllustrations.swift`; enum case `.autocode`
  in `WelcomeIllustration`; rendered by `illustrationView` in `WelcomeHomeView.swift`
  at `.frame(height: 160)`; the `studyTools` AutoCode slot carries
  `illustration: .autocode` (no `image:`). The HTML is baked into the Swift binary,
  so a plain **Cmd+R** reloads it — no sidecar rebuild.

**The animation (the grammar the others inherit):**
1. The quote **streams in** word-by-word (LLM / fast-human), with a caret.
2. `p1 · Participant` settles.
3. The **sentiment** tag appears (plain AI badge — context, not accept/deny'd;
   matches current UX, may be simplified away later).
4. The **proposed code** arrives — brighter flash + a gratuitous grow→settle pop
   (`.badge-proposed`: dashed `currentColor` + `bn-proposed-pulse`).
5. The real `[✗ ✓]` action pill **blinks in**.
6. **Accept** is "clicked" → the code goes **solid** (`badge-accept-flash`), the
   pill vanishes.
7. Rests on a **real `blockquote.quote-card`** (real type + spacing).

**Motion discipline (hold all tools to this):**
- Typing runs at normal speed; **everything after is paced 30% slower** (`PACE`
  constant) — it's a lot to take in.
- **3-play burst, then rest** for ≥ the burst duration (self-measured), then
  repeat (`BURST` constant). Grounded in WCAG 2.2.2 (Pause/Stop/Hide — no
  perpetual loop) and NN/g (finite, purposeful motion). Reduce-motion freezes to
  a finished still.
- Tag + card CSS is **copied verbatim** from `badge.css` / `badge-row.css` /
  `blockquote.css` / `timecode.css` (only adaptation: dark-mode selector from
  `[data-theme]`/`prefers-color-scheme` → the illustration's `data-appearance`).

**Content:** versions of two real study quotes (11:30, 13:08), **brand references
removed** (no "Ikea"). Quote 2 trimmed 37 → ~19 words. Final wording lives in the
`QUOTES` array in the mock and the Swift string — keep quote 2 ≤ ~20 words so it
streams and settles without clipping. Codes: `visible options` (blue),
`platform convention` (violet), sentiment Satisfaction.

## The shared visual grammar (so the whole set feels like ONE set)

- The **quote-card unit** (streaming quote + real `.badge` chips) is the base
  motif. Reuse it wherever the tool acts on a quote (Tag, Star & hide).
- Same **motion tempo** (typing speed, the 30% post-typing pace) and the
  **burst-then-rest** cadence.
- **Restraint** — quiet, must not out-shout the science cells or the real Shoal.
- Everything is **decorative**: `accessibilityHidden`, inert, reduce-motion still.

## Tool 2 — Codebooks / manual tags (DONE, second reference)

Shipped as the **manual-tags** illustration — the human counterpart to AutoCode. A
researcher hand-builds a codebook group (title + description + codes typed via the
real `+ → type → commit → chip` flow) in the real codebook OKLCH colours (ux 250 /
opp 75). Two groups — a *designed A/B experiment* and a *brief-driven commercial
dive* (participant on a rival tool) — make the point auto-coding can't originate:
intent the human set before the data existed.

- **In-app:** `WelcomeIllustrationHTML.manualTags(...)` + `ManualTagsIllustrationView`
  (enum `.manualTags`), rendered at `.frame(height: 176)`, wired to the Codebooks
  `studyTools` slot (its "Code by hand →" CTA). Baton turn 13 s; **one group per
  turn** (the baton alternates the two across turns, like AutoCode alternates quotes).
- **Mock:** the *Manual tags* section of `docs/mockups/welcome-studytools-animations.html`
  keeps the standalone two-group slide sequence (accumulate-then-slide, for design).

## Tools 3–8 — concept seeds + likely build target

React to these as we go; lock nothing until it's mocked.

| # | Tool | Concept seed | Likely target |
|---|------|--------------|---------------|
| 3 | **Tag** | ~~select quotes, press `t` (keycap), a code chip attaches~~ **DONE** — shipped as webview (`.tag`) | webview + keycap |
| 4 | **Star & hide** | ~~`s` stars, `h` collapses a row away~~ **DONE** — shipped as webview (`.starHide`) | webview + keycap |
| 5 | **Video clips** | ~~a quote turns into a film frame with a play triangle / scrubber~~ **DONE** (20 Aug 2026) — native (`ClipsIllustrationView`): the real Export-menu row clicked, three clips land with filenames assembling | themed Swift |
| 6 | **Send to Miro** | ~~quotes fly onto a board as sticky notes~~ **DONE** (20 Aug 2026) — webview (`.miro`): just the stickies, appearing in order | webview |
| 7 | **Ingest** | ~~a folder drops, files fan out (audio/video/doc icons) → transcript → report~~ **DONE** (20 Aug 2026) — native (`IngestIllustrationView`): one example of every importable kind, surtitled | themed Swift |
| 8 | ~~**Redact PII**~~ | ~~a name in a quote → a redaction bar sweeps over it~~ **WITHHELD** — the capability isn't in the `.app` (see the 2 Aug note); the strike-animation seed is worth keeping for whenever it lands | — |

_(Done 20 Aug 2026: all three converted and their imagesets deleted; the `2 quote(s)` bug is gone — the Miro sticky now lifts `common.miro.boardQuoteCount`. Kept as written.)_ **These three are the last screenshots in the app, and they go.** Today they ship
as light-mode `@2x` PNGs (`welcome-clips`, `welcome-miro`, `welcome-ingest`) with
no dark variant — and they're not even Bristlenose UI: two are Finder lists and
one is a Miro canvas complete with Miro's logo, which sits badly next to the
decision two cells away to avoid real provider logos for trademark reasons. The
clips shot also bakes in a system-blue Finder selection row (wrong under Edo) and
a copy error (`Ive`), and the Miro shot bakes in a `2 quote(s)` programmer plural
that is a genuine bug in `bristlenose/miro_board.py:149`. Each one converted
should **delete its imageset in the same commit** — as the first four already did
(`welcome-{autocoding,codes,tag,star}` deleted 2 Aug 2026, ~196 KB of dead
screenshots of our own UI that had sat orphaned with zero Swift references since
their slots moved to illustrations). Only `welcome-clips`, `welcome-miro` and
`welcome-ingest` remain, plus the four `welcome-book-*` covers the shelf uses.

**The build target is per-tool, and webview is no longer "report chrome only".**
The rule below was written as *native for a bespoke drawing, webview for real
report chrome* — but the ninth cell overturned the first half in practice:
**Connect an AI agent draws bespoke Claude Code chrome and shipped as a webview**,
built straight in-app. So for these three — none of which reproduces report CSS —
the honest framing is: webview when the motion wants HTML/CSS and iterating in the
mock is the fast path, themed SwiftUI when it's a shape SwiftUI draws well or an
existing native view can be reused. Both are legitimate; five webviews and three
native views already coexist. What is *not* legitimate is a screenshot.

## Added tool — Connect an AI agent (DONE, 1 Aug 2026)

A ninth slot, added when the MCP extension shipped (not one of the original 8
screenshots). A **faked-up Claude Code session** in a drawn terminal panel — no
window chrome, no screenshot: the question types in at a dim `>` prompt and
commits (Claude Code transcript style), a coral `✻ Thinking…` shimmer resolves
into the green-dot tool call, the result line lands, and a cited answer streams
back word-by-word.

- **Grounded in the real MCP surface**: the tool line reads
  `⏺ bristlenose · search_quotes (MCP)(query: "checkout")` — `search_quotes` is
  the actual tool `/mcp/` exposes (`bristlenose/server/mcp_server.py`). The
  demo study is the same checkout narrative the Dignity and AutoCode cells use;
  the answer ends on its quote with a BN-accent `[11:30 · p2]` citation (the
  payoff: answers point back into the report).
- **Claude Code's own scheme, following the app appearance** (decided with
  Martin, 1 Aug): light = ink on terminal white; dark = warm near-black
  `#262624`, warm-white text, `#d97757` spinner, `#4eba65` tool dot. Only the
  citation uses the BN palette accent. Edo overrides carry through like every
  other webview cell.
- **In-app:** `WelcomeIllustrationHTML.agentChat(...)` + `AgentChatIllustrationView`
  (enum `.agentChat`), natural height 160, baton turn 13 s — one play then hold;
  reduce-motion renders the finished conversation. Slot sits after Send to Miro:
  title "Connect an AI agent", CTA "Connect an agent →" → `connect-an-agent.html`.
- **Build note:** built directly in-app (the mock-first step was deliberately
  skipped — the panel reproduces Claude Code chrome, not report chrome, so there
  was no report CSS to sync); backport a section to
  `docs/mockups/welcome-studytools-animations.html` only if it needs design
  iteration.

## Dependencies / open items

- **Keycaps** — Tag (`t`) and Star & hide (`s`/`h`) show keypresses. The keycap
  system is decided (six skins, one glyph map; `docs/design-keycaps.md`).
  _(Built 20 Aug 2026: Skin A caps ship in the welcome cells.)_
- ~~**Enum rename**~~ **DONE (2 Aug 2026)** — `ScienceIllustration` → `WelcomeIllustration`
  (it stopped being science-only five cases ago). Blast radius was exactly three
  files — `WelcomeIllustrations.swift` (decl), `WelcomeHomeView.swift`
  (`SlotItem.illustration` type + both switch signatures), `WelcomeBaton.swift`
  (the `welcomeTurn` extension); no test referenced it. Same pass renamed the
  `.shoal` case to **`.emergentThemes`**: it renders `EmergentThemesView`, and the
  real `ShoalView` boids are *deliberately not used* here (see
  `design-welcome-screen.md` §Cell 2), so the old name asserted the opposite of
  the decision. The three `case` switches were re-aligned to the new longest label.
- **Frame heights** — _(Superseded: each kind now has a natural-height **cap**,
  100–252 pt, in `illustrationNaturalHeight`, and self-scales below it; the stacked
  cell sizes to its tallest slot, which is the Session timeline at 240.)_ Each illustration sets its own `.frame(height:)` in
  `illustrationView`. AutoCode is 160; tune per tool against the real large cell
  (the mock's cell frame min-height was 172). Fixed height avoids φ-cell reflow.
- **Copy** — AutoCode's quote-2 wording is a working trim; Martin to finalise.
  Whether AutoCode ever shows the *deny* path (AI over-reach rejected) is open —
  currently always-accept.

## The animation baton (welcome-screen infra — every new illustration plugs in)

Only **one cell animates at a time**; the baton travels the golden spiral so focus
moves without competition (`WelcomeBaton.swift`).

### v2, 22 Sep 2026 — the illustration owns the clock

The "later upgrade if it reads loose" this section used to park is done, because it
read loose. v1 declared a turn LENGTH and slept for it, which meant **two clocks that
had to agree with nothing making them agree**: the declared turn, and the
illustration's own beat list. They never agreed. Measured across the six looping
illustrations:

| illustration | turn | one pass | passes/turn |
|---|---|---|---|
| quote | 22.7s | 23.3s | **0.97** — never completed once |
| signal | 24.3s | 18.7s | **1.30** |
| emergentThemes | 21.0s | 16.7s | **1.26** |
| sentimentFan | 24.3s | 13.3s | **1.83** |
| ingest | 26.0s | 16.4s | **1.58** |
| clips | 29.3s | 21.0s | **1.39** |

Not one is a whole number, so **every turn ended mid-play**, and a truncated pass was
the last thing on screen before the cell went still. All five Science slots were
loopers, which is why it read as concentrated there.

**Every illustration now plays exactly one pass**, holds its finished frame, drops its
curtain and reports; the baton passes then. `welcomeTurn` survives as a **watchdog
ceiling** — what to do when the report never arrives — not as a schedule, so the
hand-written estimates it is built from stopped being load-bearing.

### The curtain

One grammar, so a sequence has a visible beginning and end instead of being joined
already running:

    fade up → establish → play once → hold the finished frame → fade down to rest

- **The fade is the cue.** The opening frame used to sit inert for a flat three
  seconds; motion is the only thing that summons the eye in that grid, so the eye
  arrived *after* the beginning by design. Worse for Tag and Star&hide, which built
  their card *inside* the play function — the three seconds were an empty box, then a
  snap. Both build up front now.
- **The establish beat is per-illustration.** `WelcomeTempo.establish(for:)` — the
  long form for an opener that is a scene to read (Tag, Star&hide), the short one for
  the rest, which open on an empty stage.
- **The end hold is longer than the establish, deliberately.** The opening frame is a
  stage nobody has earned yet; the closing one is the result. Pinned by
  `WelcomeTempoTests` because someone will eventually tidy them to match.
- **Nothing paints until the cell says which it is (11 Oct 2026).** The body starts
  blank (`bn-blank`) and the **first** `setActive` decides: `true` paints the opening
  frame and fades up from blank with no dip; `false` paints the still and fades up to
  rest. A first `false` waits `GRACE` (200 ms), because a carousel claim reaches the
  baton on its next 100 ms tick and can land just after it; `FALLBACK` (1000 ms)
  paints the still for a host that never calls `setActive`. Reduce-motion paints the
  still at `register`, as before. **Why:** a slide reached with the chevrons is a fresh
  webview that is already the baton holder, so it painted its finished frame on load
  and then dipped it away to reach the opening one. Measured off a 120 fps recording:
  finished timeline at +0.20 s, dimmed out by +0.50 s, opening frame from +0.57 s.
- **Frames are jumped to, never animated to (11 Oct 2026).** `still` and `open` run
  inside `bn-snap` (every transition off), then a forced style flush. An illustration
  that reaches its opening frame by toggling a class with a CSS transition — Miro's
  stickies drop `.on`, a 0.32 s fade — was still mid-fade when the curtain lifted, and
  the stickies came back as a second flash. A probe of the Miro page measured them
  visible at 0–340 ms and again at 519–702 ms before the fix, and not at all until the
  play added the first after it.
- **Rest is a recession, not a blackout** (`WelcomeTempo.restOpacity`). The curtain
  needs somewhere to fall that is neither a hole in the grid nor — since the resting
  frame and the finished frame are the same picture — a blink. It earns its keep
  twice: it also makes "which cell is playing" visible, which nothing said before.

### Contract for any new illustration

1. **Read the gate.** `@Environment(\.welcomeAnimationActive) private var active` and
   animate only when `active && !reduceMotion`.
2. **Report when the pass is over.** `@Environment(\.welcomeTurnDone) private var
   turnDone`, called once the curtain is down. Webviews get this free by enrolling
   with `BN.register({still, open, play})`; natives call it after
   `WelcomeCurtain.pass(…)`.
3. **Register three frames, not one.** `still` = the finished frame, painted once the
   cell is told it is resting (it was painted at load until 11 Oct 2026 — see the
   curtain); `open` = the opening
   frame, painted *behind* the curtain so the establishing beat lands on the scene the
   pass is about to act on; `play` = one pass, which must not loop. Neither `still` nor
   `open` may depend on the other having run first: a slide reached by navigation is
   painted `open` straight from blank.
4. **Declare a watchdog** in `WelcomeIllustration.welcomeTurn`. Generous, not tight —
   a ceiling that trips during a healthy pass is the two-clock bug all over again.
5. **The cell wires both halves together** with `.batonCell(slot, baton)` — one
   modifier, because the environment default for `welcomeAnimationActive` is `true`
   and a cell that sets neither animates forever while reporting nothing.

`tests/test_welcome_curtain_contract.py` enrols a new illustration by its existence:
it reads the templates and fails one that does not embed the curtain, does not
register a `still` and a `play`, or starts an interval.

### Two channels for a webview, and the split is the point

`.id` carries what the illustration **is** — appearance, palette, language,
reduce-motion — and changing one still rebuilds the `WKWebView`. `active` carries what
it is **doing**, and rides a `WKScriptMessageHandler` channel instead. It used to be in
the `.id` too, so every baton handoff destroyed a webview and built another: the
opening frame arrived after an async `loadHTMLString` of unknowable length, and there
was a blank gap nothing could fade across. *(This section called that gap "a brief
fade". Nothing made that true — identity replacement has no transition.)*

### Paging a carousel takes the playhead with it

Moving a rotator to a new slide IS "show me this one". `SlotRotator.onCurrent` now
carries whether the researcher put it there, and a user-initiated change calls
`baton.claim(slot)`, which interrupts whatever was playing and restarts the new slide
from the top — and, since 11 Oct 2026, opens from blank without first showing its
finished frame. Without it a new slide sat on its still until the spiral came round —
most of a minute — which reads as a broken illustration. A claim for a cell with
nothing to animate is ignored, so paging the Tip cell never takes the baton off a
cell that is mid-play.

AutoCode's in-app JS plays **once per turn** (random quote, picked behind the curtain
so the establishing beat is on the card the pass is about) then holds — its standalone
3-burst-then-rest loop (still in the mock) is not used in-app.

## Added tool — Session timeline (DONE, 9–11 Oct 2026)

`.timeline`, `TimelineIllustrationView` + `WelcomeIllustrationHTML.timeline`, sixth in
the pool beside Video clips. Three beats: the row's chevron opens the slice and the
lanes fill in; the pointer parks on the speaker lane while the timeline **swipes under
it** with momentum, so each section's flag rises as its section arrives and holds an
absolute 0.8 s; then a quote opens off a Delight mark. Every word is an existing key
(lane labels, the four example sections, two example themes, the Tag picture's quote).

**It is the first illustration drawn with the shipped stylesheet, not a copy of it.**
The webview rule above says "reuses the shipped CSS verbatim, so it re-syncs" — for the
nine older templates that is a hand-copied subset of tokens with **no** drift gate.
The timeline instead interpolates `WelcomeTimelineCSS.shipped`, which
`scripts/gen-welcome-timeline.py` generates from `tokens.css`, the typography and
palette files, `badge.css` and `session-tapestry.css`; `tests/test_welcome_timeline.py`
fails while the two disagree. **Copy this pattern for the next illustration that
reproduces report chrome.** The same script's `--mockup` regenerates storyboard D of
`docs/mockups/welcome-tapestry-cell.html` from the Swift template, so the harness shows
the exact HTML the app loads at the Welcome window's real slot sizes.

Liberties it takes to fit a 105–240 pt slot, each recorded in the template: drawn ~2.2
slots wide (the lens opens fitted, but a timeline that fits its frame reads as a static
chart), one theme row instead of three, 34 pt of air around the sentiment axis instead
of 41/40, a one-row crop standing in for the Sessions grid row, and a drawn overlay
scroller. It scales down, never up, and a shorter slot gets a wider logical width.

## Where things live

- Session timeline: `docs/mockups/welcome-tapestry-cell.html` §D (generated),
  `scripts/gen-welcome-timeline.py`, `desktop/Bristlenose/Bristlenose/WelcomeTimelineCSS.swift`
  (generated), `tests/test_welcome_timeline.py`
- Curtain and baton: `WelcomeIllustrationHTML.curtain` (its doc comment is the spec),
  `desktop/Bristlenose/Bristlenose/WelcomeBaton.swift`, `tests/test_welcome_curtain_contract.py`
- Mock: `docs/mockups/welcome-studytools-animations.html`
- In-app illustrations: `desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift`
- Cell wiring: `desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift`
  (`studyTools`, `slotView`, `illustrationView`)
- Real tag/card CSS to copy from: `bristlenose/theme/atoms/badge.css`,
  `molecules/badge-row.css`, `organisms/blockquote.css`, `atoms/timecode.css`
- Science-cell precedent: `docs/mockups/welcome-science-animations.html`,
  `docs/design-welcome-screen.md`
