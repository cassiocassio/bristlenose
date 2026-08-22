---
status: experimental
last-trued: 2026-08-20
trued-against: WelcomeHomeView.swift + WelcomeIllustrations.swift @main, bristlenose-website/content/index.html
---

# Transferring the Welcome-screen content to the public website

**Status: experiment / playground. This does NOT replace the live homepage.** Nothing here
is a commitment to ship. The output so far is one throwaway mockup —
`docs/mockups/website-bento-welcome.html` — plus the gap analysis below.

## 0. Why bother

The macOS Welcome screen has quietly become the best-written description of Bristlenose we
own. It was built under three constraints the marketing site never had:

1. **A hard character budget.** Fixed φ-geometry, no reflow, copy cut editorially to fit.
   Every line had to survive at 13pt in a small cell, so the padding got written out.
2. **A "no sales pitch" rule.** §1 of `design-welcome-screen.md`: the reader has already
   installed. So the copy explains rather than persuades — and explanation converts better
   for a sceptical UR audience than persuasion does.
3. **One idea per slot.** 41 content slots, each teaching exactly one thing, each with its
   own CTA and its own illustration.

The site's homepage, by contrast, is a single scroll of feature rows written at different
times. It is *longer* and says *less*: several rows describe a screenshot rather than a
capability, and the whole intellectual-credibility argument — the thing a user researcher
actually evaluates us on — is absent from it.

## 1. The two corpora

| | Welcome screen | Homepage |
|---|---|---|
| Where | `WelcomeHomeView.swift` `WelcomeContent` | `bristlenose-website/content/index.html` |
| Units | 41 slots (8 study tools · 5 science · 25 tips · 3 AI) | 13 feature rows + 5 prose blocks |
| Illustrations | 13 looping illustrations (9 already HTML) | 13 static screenshots |
| Register | explanatory, one idea per slot | promotional, feature-row |
| Docs coverage | links 25 of the 34 docs pages | links ~3 |
| i18n | deliberately English-only, held pending layout settling | English-only |

**One withheld slot to keep withheld:** Redact PII is commented out of `studyTools` because
the `.app` cannot run it. On the *website* that constraint does not apply — the CLI can, and
`docs-src/redact-pii.md` exists. So the website may use it; the desktop pool must not. Do not
"restore" it in Swift as a side effect of this work.

## 2. Why the Welcome wording usually wins — with receipts

Head-to-head on the same capability:

| Capability | Homepage | Welcome | Verdict |
|---|---|---|---|
| Ingest | "Point Bristlenose at your recordings — audio, video, or transcripts from Zoom, Teams, or Google Meet — and it handles the mechanical part." (28 words, buried in a closing prose block) | "Drop a folder of recordings or transcripts — Bristlenose transcribes, analyses and reports back." (13 words) | **Welcome**, plus the site's source list as a follow-up line |
| AutoCode | "AutoCode proposes tags from the AI; you set a confidence threshold and review the borderline cases." | "Let AutoCode propose tags across every quote — you Accept or Deny." | **Welcome** — leads with the user's agency, not the setting |
| Agent access | "Connect Claude, Claude Code, ChatGPT or Codex to an analysed project and ask about it in the agent's own window, on your own subscription." | "Chat to your data from Claude Code, Claude Desktop, or any MCP agent." | **Welcome** for the headline; **site** for the "cites quote IDs / read-only / per project" follow-up |
| Star & hide | "Star the key quotes, hide the noise" | "Press `s` to keep the quotes that matter, `h` to hide the rest." | **Welcome** — the keys make it a demonstration, not a claim |
| Signals | "Signal cards group the patterns: three participants, same form, same problem." | "A signal is a score that combines the strength of participants' opinions or feelings, their level of focus on an area or theme, and a measure of their agreement." | **Both, in that order** — the site's example, then the Welcome definition. The site never defines the term it sells. |
| Send to Miro | "Push your quotes onto a new Miro board as sticky notes, grouped by section and theme, coloured by sentiment. Each sticky carries a participant code and timecode, not a name." | "Send quotes to a Miro board." | **Site** — the only clear win for the homepage, and it wins on the privacy detail |
| Share offline | "Export the whole report as a single HTML file … no server, no internet, nothing to install." | "Share one self-contained HTML file — no install needed." | **Site** for body, **Welcome** for the headline |

The pattern: **Welcome wins headlines and verbs; the site wins the qualifying detail.** That's
the merge rule for the whole transfer — take the Welcome line as the first sentence, the site's
row as the second.

## 3. Layout: a small/medium/large grid, not the spiral

The φ-spiral is a *desktop-pane* solution — it exists because five cells had to tile one fixed
rectangle above a drop card. On a scrolling page it buys nothing and costs a lot (it can't
reflow, and it caps you at five slots).

Take the *content model* and drop the geometry. The mockup uses a **12-column bento** with
three block sizes, which maps onto the three pools almost exactly:

| Block | Span | Carries | Pool |
|---|---|---|---|
| **Large** | 6 cols, 2 rows | tag · headline · line · follow-up · illustration · 2 CTAs | the 2–3 hero study tools (Ingest, Connect an agent) |
| **Medium** | 4 cols | tag · headline · line · illustration · 1 CTA | the rest of the study tools, and every science card |
| **Small** | 3 cols | line · CTA, no illustration | the 25 tips, and short capability rows |

Three bands, in this order:

1. **What you do with it** — the 8 study tools + the site's own capability rows (transcripts,
   spreadsheet, offline file, languages) folded in as smalls.
2. **Why the analysis holds up** — the 5 science cells. Currently absent from the site entirely.
3. **Things worth knowing** — the tip curriculum, all at once instead of rotating.

The rotation mechanism does not transfer. On the desktop, rotation is the whole point (learn one
thing per visit, over a month you map the docs). A homepage visitor arrives once — so the pools
**flatten**: every tip renders, and the docs curriculum becomes a visible sitemap instead of an
ambient one. That flattening is what makes the tips band worth having: it links 25 docs pages
from the homepage, where today the homepage links about three.

Whitespace: the desktop cells are cramped by necessity. On the web they shouldn't be — the
mockup runs 24px gutters, ~30px cell padding and ~100px band separation, and the copy is capped
at 46ch so a medium cell never becomes a wall.

## 4. Animation transfer ledger

This is the cheap part, and it is much cheaper than it looks. **Nine of the thirteen
illustrations are already web pages.** `WelcomeIllustrationHTML` in `WelcomeIllustrations.swift`
is a set of `static func`s returning complete `<!doctype html>` documents that the app renders in
a `WKWebView` — themselves ported from `docs/mockups/welcome-science-animations.html` and
`welcome-studytools-animations.html`.

| Illustration | Today | Transfer cost |
|---|---|---|
| Dignity quote (`.quote`) | HTML/CSS | **~free** — a CSS transition on `max-width`; lift verbatim |
| Signal card (`.signal`) | HTML/CSS/JS | **~free**, and it *is* the React analysis card — arguably belongs on the web more than in the app |
| Emergent themes (`.emergentThemes`) | HTML/CSS/JS | **~free** |
| AutoCode (`.autocode`) | HTML/CSS/JS | **~free** |
| Manual tags (`.manualTags`) | HTML/CSS/JS | **~free** |
| Tag (`.tag`) | HTML/CSS/JS | **~free** |
| Star & hide (`.starHide`) | HTML/CSS/JS | **~free** |
| Agent chat (`.agentChat`) | HTML/CSS/JS | **~free** |
| Miro stickies (`.miro`) | HTML/CSS | **~free** |
| Seven sentiments (`.sentimentFan`) | native SwiftUI | **rebuild** — a staggered deal-out; trivial in CSS |
| Book shelf (`.books`) | native SwiftUI | **rebuild** — needs the cover images too (they live in `Assets.xcassets`, not the web tree) |
| Ingest (`.ingest`) | native SwiftUI | **rebuild** — SF Symbols don't exist on the web; needs a different icon set |
| Video clips (`.clips`) | native SwiftUI | **rebuild** — it animates a real macOS menu, which is off-idiom on a web page anyway |

Four things that do **not** transfer with the markup, and each is a real decision:

1. **Four illustrations are extracted from Swift, so the Swift becomes a second copy.** Today
   `WelcomeIllustrationHTML` is already a fork of the mockups. A third copy on the website makes
   three. Either the website imports from a shared directory, or accept the fork and say so.
2. **The tempo is tuned for a launch surface, not a scroll.** `WelcomeTempo` runs everything at
   0.6 speed with a **3-second lead-in** resting on the opening frame. On a homepage, three
   seconds of stillness after an element scrolls into view reads as *broken*, not calm. The web
   versions want the lead-in near zero and the pace back toward 1.0.
3. **There is no baton on the web.** `WelcomeBaton` guarantees exactly one illustration animates
   at a time — that's why the desktop pane feels quiet. A page with twelve simultaneous loops is
   a fairground. The web equivalent is an `IntersectionObserver` that only runs what's on screen,
   and probably only one per viewport.
4. **SF Symbols are not licensed for the web.** Anything native that leans on them (`.ingest`
   especially) needs a redraw, not a port.

Reduce-motion *does* transfer: the HTML illustrations already carry `data-reduce` and a
`prefers-reduced-motion` block.

## 5. Gap analysis A — Welcome has it, the site doesn't

Ranked by how much a sceptical user researcher would care.

| # | Content | Where it lives | Site status | Why it matters |
|---|---|---|---|---|
| 1 | **The whole scientific-background cell** — Braun & Clarke, Scherer, Russell, Norman, Nielsen | `science` pool, 5 slots + 4 book covers | **absent** | This is the credibility argument. The site names frameworks in a feature row and never says the method rests on anything. |
| 2 | **What a signal actually is** | `science` slot 4 | **absent** — the site sells "signal cards" without ever defining a signal | We coined the term; nobody else will define it for us |
| 3 | **Dignity without distortion** | `science` slot 5 | **absent** | The single strongest ethical differentiator, and the one with the best animation |
| 4 | **Keyboard-first working** (`t`, `s`, `h`) | study tools 3–4 | site says "star / hide" with no keys | Turns a claim into a demonstration |
| 5 | **The twelve-stage pipeline + caching** | tip 16 | **absent** | Directly answers "what will a re-run cost me?" |
| 6 | **Skip transcription with .srt/.vtt/.docx** | tip 21 | **absent** | Removes the biggest adoption objection for people who already have transcripts |
| 7 | **`p1.srt` next to `p1.mp4` merges** | tip 22 | **absent** | Concrete, memorable, and the kind of thing that wins trust |
| 8 | **Everything lands in one folder — yours to keep** | tip 23 | implied by "on your laptop", never stated | The owned-artefact argument |
| 9 | **Ollama as a free, no-account route** | tip 3 | one parenthetical in the privacy block | A whole audience segment |
| 10 | **Cloud-or-local as a *choice* you make** | tip 17 | mixed into a privacy paragraph | Deserves its own block |
| 11 | **The data model** (sessions · participants · quotes · sections · themes) | tip 12 | **absent** | Answers "what is this thing going to do to my data" |
| 12 | **Appearance / palette / typography** | tip 24 | **absent** | Small, but it's a Mac-audience signal |
| 13 | **Configuration has sensible defaults** | tip 19 | **absent** | Defuses "how much setup?" |
| 14 | **22 docs pages, linked** | the tip curriculum | homepage links ~3 | Pure SEO and orientation value, free |

## 6. Gap analysis B — the site has it, Welcome doesn't

These stay, and the transfer must not lose them. Welcome has no reason to carry them (the reader
already installed) — the website absolutely does.

- Hero value proposition and the **Download for Mac** CTA
- Platform requirements: macOS 15+, Apple Silicon; Homebrew and pip for CLI
- **Cost** — "$0.40 per hour of interview audio with Claude"
- Free / open source / AGPL / **built by a practising user researcher**
- The 25-second product video
- **Zoom, Teams, Google Meet** as recording sources
- Word-synced transcripts and the video player (Welcome has no slot for either)
- API keys in the OS keychain
- "Follow along" / social
- Every screenshot (Welcome deliberately deleted all of its screenshots — see §Cell 1 of
  `design-welcome-screen.md`. The website should **keep** screenshots: a prospect wants to see
  the product; an installed user doesn't need to.)

## 7. Gap analysis C — neither has it, and we'd have to write it

Genuinely missing content, surfaced by putting the two side by side:

1. **What Bristlenose is *not*.** No page says "this doesn't replace Dovetail / doesn't do
   recruitment / doesn't run the session". Both corpora describe capabilities; neither draws
   the boundary, and the boundary is what a buyer asks second.
2. **The first ten minutes.** The site says "two to five minutes" for a run; nothing describes
   what setup costs before that first run (provider key, model choice, permissions).
3. **What happens to a re-run.** The pipeline tip mentions caching; nothing states the
   incremental-analysis behaviour a returning user actually meets.
4. **Who it's for, in their own words.** No audience line beyond "user researchers". Nothing
   about team size, solo practice, or agency-vs-in-house.
5. **Two docs pages have no Welcome tip and no site mention** — `read-transcripts.md` and
   `recording-permissions.md`. The tip curriculum claims to be one-tip-per-page minus a stated
   skip list, and neither is on that skip list, so this is drift, not design. Fixing it is a
   two-line change to `WelcomeContent.tips` and belongs in the desktop repo regardless of
   whether the website work goes ahead.
6. **Provider setup pages for ChatGPT / Gemini / Azure** are collapsed to a single "Set up
   Claude" tip on the desktop (a deliberate curation), but the *website* has no reason to
   collapse them — it should link all five.

## 8. Experimental plan

Deliberately staged so each step is independently binnable.

**Phase 0 — the playground (done).** `docs/mockups/website-bento-welcome.html`: bento grid,
merged copy, cheap CSS stand-ins for ten of the thirteen illustrations, plus a provenance toggle
that colour-codes every block by where its wording came from (Welcome / site / merged). Judge the
*shape* from this, not the pixels.

**Phase 1 — decide the merge rule.** Walk the mockup with the provenance toggle on. The proposed
rule is §2's: Welcome line first, site detail second. If that survives a read-through, the rest
is mechanical.

**Phase 2 — extract the nine HTML illustrations** out of `WelcomeIllustrationHTML` into standalone
files, parameterless (no `PACE`/`LEAD`/palette interpolation), and re-tempo them for scroll.
Decide the fork question (§4 item 1) *here*, before there are three copies.

**Phase 3 — rebuild the four natives** in CSS. Sentiment fan and clips are easy; the book shelf
needs the cover art moved into the website tree; ingest needs a non-SF icon set.

**Phase 4 — write the Phase-C gaps** (§7). This is the only step that needs new prose rather than
moved prose.

**Phase 5 — a real page**, built by the website's `build.py`, reviewed as a candidate. Nothing
before this touches the live site.

**Costs to be honest about:** the animations are ~free to move and *not* free to own — three
copies of the same illustration is the failure mode this plan can most plausibly create. And a
homepage carrying twelve loops needs the `IntersectionObserver` discipline from day one, or it
will be slower and noisier than the page it replaced.

## 9. References

- `desktop/Bristlenose/Bristlenose/WelcomeHomeView.swift` — the four content pools
- `desktop/Bristlenose/Bristlenose/WelcomeIllustrations.swift` — `WelcomeIllustrationHTML`, the nine web-ready illustrations
- `docs/design-welcome-screen.md` — the canonical spec for all of it
- `docs/mockups/welcome-science-animations.html`, `welcome-studytools-animations.html` — the original animation reference
- `docs/mockups/website-bento-welcome.html` — this experiment
- `bristlenose-website/content/index.html`, `bristlenose-website/docs-src/` — the current site
