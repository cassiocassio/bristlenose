---
status: current
last-trued: 2026-07-26
trued-against: HEAD on 2026-07-26
---

# Welcome screen — study-tools cell illustrations

> **Trued 2026-07-26** — Codebooks (tool 2) shipped this session as the manual-tags
> illustration, and the seven-sentiments fan was halved in speed. Updated from
> "one shipped, seven remaining" to two shipped, six remaining.
>
> **Updated 1 Aug 2026** — Tag (3) and Star & hide (4) have shipped as webviews,
> and a NINTH cell was added and shipped: **Connect an AI agent** (a faked-up
> Claude Code session over the real `/mcp/` tool names — see its section below).
> Five cells now carry real illustrations; four of the original eight remain.

**Handoff for a new session.** Replacing the 8 static screenshots in the Welcome
screen's large "Study tools" cell with tiny looping illustrations, **one tool at
a time**. Tools 1–4 (AutoCode, Codebooks, Tag, Star & hide) plus the added
Connect-an-AI-agent cell are **built and shipped in-app**; this doc is the brief
for the four remaining (Video clips, Send to Miro, Ingest, Redact PII).

## Why we're doing this (Martin, 25 Jul 2026)

The study-tools cell (`studyTools` in `WelcomeHomeView.swift`) rotates through 8
tools, each currently carrying a baked macOS screenshot (`image:`). Replace each
with a drawn illustration because:

1. **Themeable** — light/dark + palette for free (a PNG is baked light-mode).
2. **Responsive** — resizes with the cell (a PNG has one fixed size).
3. **No macOS chrome** — we stop shipping screenshots of our own UI; the idea is
   drawn, not photographed. Better all round.

Same playbook as the science cell (`docs/mockups/welcome-science-animations.html`
→ `WelcomeIllustrations.swift`): **prototype idea + motion + copy in an HTML mock
first, then build for real.**

## The build-target rule (LOCKED)

Decided with the science cells and confirmed for study tools:

- **Webview** when the illustration *reproduces actual report chrome* (real
  badges, quote cards, signal cards). It reuses the shipped CSS verbatim, so it
  **re-syncs when the report styling changes — no drift, no tech debt** — and
  sidesteps the whole platform-matching problem. Precedent: the science *Signals*
  and *Dignity* cells (`WelcomeIllustrationHTML.signal` / `.quote`).
- **Native SwiftUI** when it's a *bespoke drawing* or reuses an *existing native
  view*. Precedent: the science *SentimentFan*, *BookShelf*, and *Shoal* cells.

The mock is the design surface for *every* tool regardless — HTML iterates
fastest. The native-vs-webview call is made per tool at build time.

## Tool 1 — AutoCode (DONE, the reference implementation)

Ships as a **webview** (report-chrome → webview). Study it as the template for the
others.

- **Mock:** `docs/mockups/welcome-studytools-animations.html` (has palette +
  light/dark switcher, roadmap, notes).
- **In-app:** `WelcomeIllustrationHTML.autocode(dark:palette:reduce:)` +
  `AutoCodeIllustrationView` in `WelcomeIllustrations.swift`; enum case `.autocode`
  in `ScienceIllustration`; rendered by `illustrationView` in `WelcomeHomeView.swift`
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

## The shared visual grammar (so 7 more feel like ONE set)

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
| 5 | **Video clips** | a quote turns into a film frame with a play triangle / scrubber | native (bespoke drawing) likely |
| 6 | **Send to Miro** | quotes fly onto a board as sticky notes | native (bespoke) likely |
| 7 | **Ingest** | a folder drops, files fan out (audio/video/doc icons) → transcript → report | native (bespoke) likely |
| 8 | **Redact PII** | a name in a quote → a redaction bar sweeps over it (kin to the Dignity strike animation) | webview (report chrome) |

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
  system is decided (six skins, one glyph map; `docs/design-keycaps.md`) but
  unbuilt. Fake keycaps in the mock; decide build-vs-fake when those tools land.
- **Enum rename** — `ScienceIllustration` is now welcome-wide. Rename to
  `WelcomeIllustration` (mechanical: enum decl + `SlotItem.illustration` type +
  `illustrationView` signature/cases + `!= .none` checks in `WelcomeHomeView.swift`)
  before adding 7 more cases, so the name stops lying.
- **Frame heights** — each illustration sets its own `.frame(height:)` in
  `illustrationView`. AutoCode is 160; tune per tool against the real large cell
  (the mock's cell frame min-height was 172). Fixed height avoids φ-cell reflow.
- **Copy** — AutoCode's quote-2 wording is a working trim; Martin to finalise.
  Whether AutoCode ever shows the *deny* path (AI over-reach rejected) is open —
  currently always-accept.

## The animation baton (welcome-screen infra — every new illustration plugs in)

Only **one cell animates at a time**; the baton travels the golden spiral so focus
moves without competition (`WelcomeBaton.swift`). Contract for any new illustration:

1. **Read the gate.** `@Environment(\.welcomeAnimationActive) private var active` and
   animate only when `active && !reduceMotion`; otherwise show the still. Webviews:
   `reduce = reduceMotion || !active`, and put that in the `.id()` so it reloads.
   Native views: gate the loop (`.task(id:)` / timer `guard`).
2. **Declare a turn length** in `ScienceIllustration.welcomeTurn` (how long one turn
   runs before the baton passes). Continuous loops = a "showcase" length (a cut just
   freezes to the still); discrete plays (AutoCode) = one full run.
3. **The cell reports wants.** Via `SlotRotator(onCurrent:)` → `baton.report(slot,
   wants: item.illustration != .none, turn: item.illustration.welcomeTurn)`, and sets
   `.environment(\.welcomeAnimationActive, baton.isActive(slot))`.

Known tradeoff (v1, duration-declared handoff): a cell going inactive **reloads** its
webview to the still — a brief fade. Precise handoff (webview posts `"done"`) is the
later upgrade if it reads loose. AutoCode's in-app JS plays **once per turn** (random
quote) then holds — the baton owns the rhythm, so its standalone 3-burst-then-rest
loop (still in the mock) is not used in-app.

## Where things live

- Mock: `docs/mockups/welcome-studytools-animations.html`
- In-app illustrations: `desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift`
- Cell wiring: `desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift`
  (`studyTools`, `slotView`, `illustrationView`)
- Real tag/card CSS to copy from: `bristlenose/theme/atoms/badge.css`,
  `molecules/badge-row.css`, `organisms/blockquote.css`, `atoms/timecode.css`
- Science-cell precedent: `docs/mockups/welcome-science-animations.html`,
  `docs/design-welcome-screen.md`
