---
status: partial
last-trued: 2026-08-06
trued-against: HEAD@main on 2026-07-26 (uncommitted Phase B change in-tree)
---

> **Truing status:** Partial — the h1 scheme, keyline token, radius tiers,
> and the Phase B geometry (B1 truth-measuring `syncToolbarInset`, B2 datum
> re-scope, B3 TOC treatment) have shipped as code (trued 2026-07-26); the
> Analysis pane variant and the `__bnLayoutAudit`/Playwright gate remain
> deferred. The **on-device acceptance pass** for the datum (Open question 3)
> is still pending — the residual-vs-52 HUD read and pixel tune haven't run.
> See the changelog and the annotated Sequencing list.

## Changelog

- _2026-08-20_ — **Codebook was never enrolled in the datum system, and now is.**
  The flush-to-datum rule requires a lens to render its zone title as the direct
  child of a `<section>` that is the direct child of `<main>`; Codebook rendered a
  bare fragment, so `.center > main > section:first-of-type > .section-heading`
  never matched and the lens opened **40px below** Sessions and Quotes for the whole
  life of the rule (measured 271 vs 231 in Chromium). The rule needed no widening —
  the lens needed a `<section>`. Sibling defect from the same construction: the
  title had been wrapped in a per-lens flex column (`.codebook-header`) so the
  Library button could sit beside it, which also drew the keyline only as wide as
  that column. Both fixed by making `.section-heading` **the row rather than the
  text** — a wrapper carrying the keyline, with the `<h1>` and an optional action
  inside, one shape on every lens whether or not it has an action. `.codebook-header`
  deleted. Step 5's gate is **no longer wholly deferred**: `e2e/tests/lens-datum.spec.ts`
  asserts per lens, on both engines, that the first zone title computes
  `margin-top: 0` — verified to go red on the pre-fix code. Anchors:
  `bristlenose/theme/atoms/section-heading.css`,
  `frontend/src/components/SectionHeading.tsx`,
  `frontend/src/islands/CodebookPanel.tsx`.
- _2026-08-06_ — added §"Sessions lens conformance pass": the Sessions lens
  was rebuilt as a container-query grid (`9f1f8058`), measured against the two
  invariants (no page-geometry drift found), and the remaining adoption specced
  as S1–S4 behind the still-missing `__bnLayoutAudit` gate.
- _2026-07-26_ — trued up: recorded Phase B shipping — sequencing step 1
  (residual `syncToolbarInset` + datum re-scope, `--bn-first-baseline`
  retired) and step 3 (TOC toolbar bleed) landed as code; marked §"Fix: stop
  pushing the phantom inset" shipped; flagged the datum acceptance pass as
  still-pending in Open questions. Anchors:
  `desktop/Bristlenose/Bristlenose/BridgeHandler.swift` `syncToolbarInset`,
  `bristlenose/theme/organisms/sidebar.css` §"First-baseline datum" + `.toc-sidebar`,
  `bristlenose/theme/tokens.css`.
- _2026-07-23_ — initial draft (measured audit + native-geometry diagnosis).

# Lens page template — one geometry, declared variation

*Design doc for unifying the five lens pages (Project, Sessions, Quotes,
Codebook, Analysis) under a single layout template: shared gutters, a shared
top datum, a shared h1 scheme, tokenised keylines and radii — so the lenses
cannot silently drift apart. Grew out of the 22 Jul 2026 measurement audit
(below), which found every lens on its own vertical rhythm and one lens
(Analysis) off-grid on all four sides.*

Status: **partially implemented** (26 Jul 2026). The measured audit and
native-geometry diagnosis are complete and verified against the real WKWebView
(Debug build `c2f68e47`). The h1 scheme, keyline token, radius tiers, and
Phase B geometry (sequencing steps 1 + 3) have shipped as code; the Analysis
pane variant (step 2) and the audit gate (step 5) are deferred; the datum
acceptance pass is pending. Implementation state is annotated at the foot.

## The two invariants

1. **Pages own zero page-level geometry.** The template (SidebarLayout + the
   shared PageHeader) owns gutters, top datum, and scroll architecture. Pages
   render pure content into the slot. Cards keep their internal padding —
   that's anatomy, not layout.
2. **Variation is declared, not styled.** Which flanking columns a lens has
   (left panel, minimap, tag sidebar, inspector) and which scroll model it
   uses are entries in one table in `AppLayout.tsx` — never per-page CSS.

Everything below serves these two.

## Measured audit — the evidence (22 Jul 2026)

Headless Chromium against `bristlenose serve` on the IKEA trial project,
embedded mode emulated (`__BRISTLENOSE_EMBEDDED__` + `setToolbarInset(52)`),
1440px viewport. Verified byte-identical numbers in the real WKWebView via the
Web Inspector probe (`{inset: "52px", bodyPadTop: "84px", firstInk: 84}` on
Sessions).

### Vertical: first content from webview top

| Lens | First ink | Element | vs 84px base |
|---|---:|---|---:|
| Project | 84 (tile box) / 97 (text) | stat-tile row | ±0 |
| Sessions | 84 | "Moderated by …" | ±0 |
| Quotes | **8** | "Sections" h2 | **−76** (datum lift) |
| Codebook | 84 | "Codebook" h1 | ±0 |
| Analysis | **148** | "Sentiment signals" h2 | **+64** |

The 84px base = `--bn-toolbar-inset` (52) + `--bn-space-xl` (32) from the
embedded body rule (`templates/report.css`). The −76 on Quotes is the
cross-seam first-baseline rule (`organisms/sidebar.css`); the +64 on Analysis
is `.analysis-center` padding (24) + `section-heading` margin (40).

### Horizontal: content edges (1440 viewport)

Canonical edge: x = 56 (24 body + 32 `.center`), right edge 1384. Project,
Sessions, Codebook, Quotes all sit on it (Quotes' narrower right edge is the
minimap column — by design). **Analysis sits at 80/1360** — indented 24px on
both sides by `.analysis-center { padding: var(--bn-space-lg) }`
(`organisms/inspector.css`), inside the already-padded `.center`.

### Corner radii

Token system (`sm 3 / md 6 / lg 8 / pill 999`) is real and mostly obeyed:
dashboard panes, featured quotes, coverage box, codebook groups all `lg`;
badges/speaker codes `sm`; buttons `md`; quote cards deliberately asymmetric
(`0 6 6 0` — square keyline edge, `organisms/blockquote.css`). Two defects,
both in Analysis: `.signal-card` at `sm` (badge-tier corners on the largest
cards in the app, `organisms/analysis.css:15`) with its inner quotes box at
`md` — **inverted nesting** (child rounder than parent). Two micro-nits:
`framework-toggle` hand-rolled 11px and `badge-action-pill` 8px — both
half-height pills that should say `--bn-radius-pill`.

### Headings

| Lens | h1 | h2 |
|---|---|---|
| Project | — | — (h3 card titles only) |
| Sessions | — | — |
| Quotes | — | "Sections" · "Themes" |
| Codebook | "Codebook" | — |
| Analysis | — | "Sentiment signals" · "Tag signals" |

One h1 in the whole app; two lenses with no headings at all; the footer's h3
("General") is the first heading a screen reader meets on Project and Sessions.

## Native geometry — ground truth (23 Jul 2026, red-background test)

The embedded CSS was written for the translucent-chrome spike model: WKWebView
extends up behind the unified toolbar, bridge pushes the titlebar+toolbar
delta (52px) as `--bn-toolbar-inset`, body pads `inset + space-xl` so first
content clears the frost.

**Both halves of the idiom already exist — natively — and the CSS pad
double-counts one of them.** Established by two observations on the live
webview (`document.documentElement.style.background = 'red'` + scrolling):

- The webview's **paint region extends under the toolbar**: scrolled content
  is visible ghosted up in the toolbar band, dimmed by the system's
  scroll-edge scrim (whose hard-edge style reads as a sharp clip line — it
  is the scrim's boundary, not the webview's).
- The webview's **layout viewport is inset below the toolbar**: the red
  background, scroll-position-0 content, and every
  `getBoundingClientRect()` number all start at the toolbar's bottom —
  macOS's automatic content-inset behaviour for obscured chrome.

That combination IS the Notes/Mail idiom, provided by the platform: at rest,
content sits clear of the toolbar; scrolling slides it underneath. (The
"solid band until you scroll" at rest matches the spike's own recorded
accepted limitation — Xcode behaves identically.)

Consequences:

- **The bridge's 52px push double-counts the native inset.** The layout
  viewport is already past the toolbar; the CSS pads again on top. Every
  lens carries 52px of dead space — the visible gap below the toolbar on
  Sessions/Codebook/Project is 84px where 32px was designed.
- **Quotes' pleasing position is two bugs cancelling**: the −76px datum lift
  (tuned for a window-top coordinate space) × a layout viewport that starts
  at the toolbar bottom = "Sections" lands 8px below the toolbar by
  accident.
- The cross-seam datum concept (align web baselines to the native sidebar's
  "Project" row) is unrealisable — that native baseline sits above the
  layout viewport's origin. The datum re-scopes to web-internal.
- The separate "frost quest" largely **dissolves**: scroll-underlap already
  works. What doesn't exist is frost sampling at scroll-0 (nothing is behind
  the toolbar at rest) — the Xcode-style accepted limitation, unchanged.

### Fix: stop pushing the phantom inset

> **Shipped 2026-07-26** (code in-tree, on-device acceptance pending) —
> `syncToolbarInset` now pushes `max(0, toolbarRegion − webView.safeAreaInsets.top)`
> = 0 in today's geometry; the CSS datum re-scoped to web-internal and
> `--bn-first-baseline` was retired. The residual-reads-0 HUD confirmation and
> full-screen check are the outstanding acceptance step. Diagnosis below is
> preserved as the rationale.

`BridgeHandler.syncToolbarInset` pushes
`window.frame.height − contentLayoutRect.height` — the chrome's height,
assuming the webview's layout origin is the window top. It isn't; the system
insets it already. The bridge should push the **residual** the CSS actually
needs: the chrome overlap not already absorbed by the native content inset —
measurable by comparing the layout viewport's window position against
`contentLayoutRect`, and in today's geometry **0**. Keep the plumbing (a
future window configuration could legitimately produce a residual); change
what flows through it.

**Coupling:** with inset 0, the current Quotes lift computes −44px and pulls
the heading into the underlap region — behind the toolbar at rest. The Swift
fix and the CSS datum re-scope must land in the same change — which is this
template work.

## The template

### Variants table (already centralised in AppLayout — grows one column)

| Lens | Left panel | Minimap | Tags | Inspector | Scroll |
|---|---|---|---|---|---|
| Project | none | – | – | – | body |
| Sessions | SessionsSidebar | – | – | – | body |
| Quotes | TocSidebar | ✓ | ✓ | – | body |
| Codebook | CodebookSidebar | – | – | – | body |
| Analysis | AnalysisSidebar | – | – | ✓ | **pane** |

The `scroll: pane` variant becomes a SidebarLayout feature: the template
renders the scroll container and applies the shared gutter tokens to it.
Analysis's private wrapper (and its 24px double-gutter) dies; a future lens
needing a fixed bottom panel gets the variant for free. Shadow/focus-ring
clipping at the scroller edge is handled with the negative-margin + matching
padding idiom the tag sidebar already uses.

### The h1 scheme (built 25 Jul, `5c611310`)

**The rule: one h1 per top-level *content zone*, named for the zone, never the
lens.** The academic one-h1-per-document convention assumes a page with no
navigation chrome; we have a lit-up nav item (and the titlebar) already telling
the user which lens they're on, so an h1 that repeats the lens name tells them
nothing — the h1 has to earn its place by naming the *zone*. They clicked
"Quotes"; the page answers *what kind?* → "Sections" and "Themes".

| Lens | h1(s) | Why |
|---|---|---|
| Quotes | "Sections" · "Themes" | two peer organising schemes → two h1s |
| Analysis | "Sentiment signals" · "Tag signals" | two peer analyses → two h1s |
| Codebook | "Codes" *(rename pending)* | one zone; h1 + description, the description carries the new info |
| Sessions | "Sessions" | one zone, titled like every other titled lens — **superseded 6 Aug 2026**, see note below |
| Project | **none** | dashboard/overview, name's in the titlebar; no titled content zone |

> **Superseded 6 Aug 2026 (Martin).** Sessions now carries a "Sessions" h1 with the
> full `.section-heading` treatment, matching Quotes and Analysis. The original
> reasoning — *"'Sessions' would just echo the nav"* — is preserved above because it is
> still the right test for a *new* lens; it was outweighed here by cross-lens
> consistency: four of five lenses carry a titled, ruled zone, and Sessions reading
> differently was the more visible cost. The "Moderated by …" line stays, now as the
> zone's intro *under* the title rather than in place of one. Reuses the `nav.sessions`
> locale key (identical word, already reviewed in 20 locales) rather than minting
> `sessions.heading`.
>
> Same pass fixed **Codebook**: its `<h1>` carried no `.section-heading` class at all, so
> it had the right type (inherited) and no rule. Three render states, all three missing
> it. See §"Systematising the heading" for why that defect is structural, not a typo.

Multiple h1s per page is legal HTML and screen-reader-survivable (the two are
far apart). **Semantics and graphic size are separate knobs:** `.section-
heading` is self-contained (owns the full-pane keyline + padding so it works on
an `<h1>`, which has no border of its own) but deliberately does *not* set
font-size/weight — those inherit from the element, so the h1's *size* stays
tunable independently of its *level*. Currently 28/700 (display/strong,
inherited); tune on the specimen lens if two-per-page reads too heavy.

First zone-title on a lens flushes to the datum (`margin-top: 0` via
`section:first-of-type` / `.analysis-center > :first-of-type`); subsequent ones
keep 2.5rem separation. **App caveat:** the old `[data-embedded]` datum lift in
`sidebar.css` still targets `> h2` and is now dead (h2→h1) — Phase B (the
toolbar-inset re-scope) owns rewriting it; the absolute top position in the app
rides that fix.

### Keylines — reversible invisibility

The lens-page rules are borders, not `<hr>`s: base h2 underline (2px,
`templates/report.css`), `.section-heading` full-pane 1px variant, codebook
`.framework-section-header`. New token `--bn-colour-keyline: transparent`
consumed by those three sites. `transparent` still paints the 1–2px box, so
geometry is untouched and the revert is a one-line token flip (or a
playground toggle for live A/B). Table chrome (thead underlines, row
separators) is data-grid anatomy and keeps `--bn-colour-border` — out of
scope unless decided otherwise. This walks toward the already-deferred D7
(retiring border-on-capped-h2) in `design-improvement-opportunities.md`.

### Radius tiers

Pane = `lg` · card-within-pane = `md` · chip/badge = `sm` · half-height pill
= `pill` · quote-card asymmetry documented as the deliberate exception.
Done: `.signal-card` `sm` → `lg` (un-inverts the nesting for free, `be1835b7`).
Remaining nits: `framework-toggle` (11px) and `badge-action-pill` (8px) →
`--bn-radius-pill` (both coincidentally-correct pills today — hand-rolled
numbers that would break on a height change). Decided (25 Jul): **Project stat
tiles stay `md`** — `lg` reads too big at tile scale; they're mini-panes, not
full panes.

Note: radii are **not** native-calibrated — only typography is
(`tokens-desktop.css`, via the Type Parity Inspector). Tahoe's system corners
run rounder (~10–12px on cards), so a desktop radius override parallel to the
type work is a real open question, tracked separately from these web fixes.

### TOC sidebar (contents menu)

The tag sidebar has the full embedded treatment (toolbar bleed, re-inset
header, datum rule); the TOC sidebar has none — `sticky; top: 0; 100vh`
inside the body's padded flow, so its panel starts a full pad below the
toolbar and overflows the bottom by the same amount. Mirror the tag sidebar's
treatment onto `.toc-sidebar`. (With the inset at 0 the bleed calc collapses
to just `--bn-space-xl` — simpler than the tag sidebar's current form, which
shrinks to match in the same pass.)

## Enforcement — drift is CI-red

> **Trued 31 Aug 2026 — this section overstates what exists, and has since it
> was written.** Read it as the design, not the state. What actually ships:
>
> - **`window.__bnLayoutAudit()` does not exist.** The identifier appears only
>   in two comments inside `frontend/src/islands/GridSpecimen.tsx`. The visible
>   HUD half shipped; the callable probe never did — so the "one implementation,
>   two surfaces" claim below is unrealised, and the WKWebView cannot be measured
>   by the same ruler as Playwright.
> - **The alignment spec asserts one of its three claims.**
>   `e2e/tests/lens-datum.spec.ts` (106 lines, 5 lenses) checks `first-ink ==
>   datum` and nothing else. There is no horizontal (content-left == token)
>   assertion and no radius-tier assertion anywhere in `e2e/`.
> - **The Specimen lens is real**, as described.
>
> The doc's own §"Gate" ~150 lines below says all of this — but a cold reader
> meets *this* heading first, and a section titled "drift is CI-red" reading
> present-tense is exactly the false pass the truing ritual exists to catch.
> **Codebook v2 is a sixth titled lens** and is absent from the variants and
> h1-scheme tables below; it shipped 30 Aug with the precise datum defect this
> doc governs (fixed in *"codebook v2: the lens sat below the shared datum…"*)
> and was enrolled in the datum spec on 31 Aug.


- **`window.__bnLayoutAudit()`** — a small dev-gated probe in the SPA
  returning the audit numbers (inset received, first-ink top, content edges,
  per-class radii). One implementation, two surfaces: the Playwright gate
  calls it per route on **both engines** (Chromium + WebKit — the e2e stack
  already runs both, closing the engine-drift channel), and the same call
  pasted into the WKWebView's Web Inspector measures the app by the same
  ruler. Tier D in the diagnostics taxonomy
  (`design-diagnostics-menu.md`); candidate Tier V later if cohort calls
  need it.
- **Alignment spec** (`e2e/`): per route assert content-left == token,
  first-ink == datum, radius tier per component class. Same philosophy as the
  bundle-size and perf gates.
- **The Specimen debug lens** (`/report/specimen`, shipped 23 Jul 2026 —
  `frontend/src/islands/GridSpecimen.tsx`): test content on a visible grid —
  overlays for the content edges / gutters / datum / reading width, a live
  measurement HUD, and specimen type, quote cards, signal cards, and radius
  tiers rendered with production classes. Dev-gated NavBar tab in the
  browser; Diagnostics ▸ Grid Specimen (DEBUG harness) on desktop. The
  human-eye twin of the Playwright gate: every change in this plan is
  visually checkable there before and after.

## Sequencing

1. **Truth-measuring `syncToolbarInset` + datum re-scope + PageHeader/h1
   scheme** — one coherent change; ships the 52px reclaim and the h1s
   together (they're coupled through the datum). **Shipped as code 2026-07-26**
   (h1 scheme earlier, `5c611310`; residual `syncToolbarInset` + datum
   re-scope + `--bn-first-baseline` retirement this pass). On-device datum
   acceptance/tune still pending (Open question 3).
2. **Analysis pane variant** — scroll container into SidebarLayout, gutter
   fix, `.signal-card` radius fix. (`git branch -f checkpoint` first — the
   riskiest step.) **Deferred** — `.signal-card` radius already landed
   (`be1835b7`); the scroll-pane → SidebarLayout structural move is post-Phase-B.
3. **TOC sidebar treatment.** **Shipped as code 2026-07-26** — `.toc-sidebar`
   mirrors the tag sidebar's toolbar bleed (`sidebar.css`). Colour tier
   followed 14 Aug 2026 — `.toc-sidebar` rides `--bn-colour-inspector-bg`
   like the tag sidebar; it had shipped on the editor `--bn-colour-bg`,
   invisible in light mode (2% delta) and near-black beside the native
   sidebar in dark.
4. **Keyline token + playground toggle.** Keyline token
   (`--bn-colour-keyline`) shipped; playground A/B toggle not yet wired.
5. **`__bnLayoutAudit` + Playwright alignment gate** — locks it all in.
   **Partially shipped 2026-08-20.** `e2e/tests/lens-datum.spec.ts` asserts, per
   titled lens on Chromium + WebKit, that the first `.section-heading` computes
   `margin-top: 0` — i.e. that the lens is enrolled in the datum system at all.
   That is the assertion that would have caught the Codebook regression; it was
   verified red against the pre-fix code before being trusted green.

   It deliberately does **not** assert the four lenses share a first-ink `y`.
   Measured in browser mode: sessions 231, codebook 231, quotes 270, analysis 262
   — and the two outliers are legitimate. Quotes carries a web `div.toolbar` above
   its first `<section>` (native chrome in the app, so absent there); Analysis
   renders an intro `<p class="description">` above its heading inside the padded
   `.analysis-center`. Asserting equal tops would encode that incidental chrome and
   go red on a legitimate change. `margin-top` is the contract; first-ink `y` is a
   consequence of it plus whatever the lens legitimately puts above the title.

   Still deferred: the `__bnLayoutAudit` probe itself, and the content-edge /
   radius-tier assertions. The **horizontal** half has no cheap gate — a keyline
   truncated by a wrapper is not distinguishable from a correctly-narrow parent
   without hard-coding the Analysis inset as an exception, so it rests on the
   atom being the only box that carries the rule.

   **Latent trap introduced by the same change, recorded not fixed:** the Analysis
   selector is `.analysis-center > .section-heading:first-of-type`, and
   `:first-of-type` is resolved by **tag**, not class. `.section-heading` is now a
   `<div>`, so that selector means "the first `div` child, if it carries the class".
   It matches today only because Analysis's preceding sibling is a `<p>`. Add any
   `<div>` above the heading in `.analysis-center` and Analysis silently drops off
   the datum exactly as Codebook did. `lens-datum.spec.ts` covers Analysis, so it
   would go red — which is the reason to leave the selector alone rather than
   invent a third one.

Trunk throughout; each step an independently-green commit. (The former
"frost quest" step is gone — scroll-underlap turned out to already work
natively; see Native geometry. The only frost residue is the scroll-0
solid band, an accepted platform limitation shared with Xcode.)

## Sessions lens conformance pass (spec, 6 Aug 2026)

The Sessions lens was rebuilt on 6 Aug (`9f1f8058`) from a raw `<table>` at
`table-layout:auto` into a container-query CSS grid — see
`bristlenose/theme/organisms/sessions-grid.css`. That rewrite was about
*responsive* behaviour and deliberately did not touch page-level geometry, so
this section specs the conformance work against the template above. It is
written after a measured pass, not a read-through; measurements below are from
`bristlenose serve` on the smoke fixture at a 1728px viewport, light, browser
(non-embedded).

### Measured conformance — what already passes

| Invariant | Measured | Verdict |
|---|---|---|
| Pages own zero page-level geometry | `.bn-session-table { margin: 0 }`; no page-level padding, gutters or width caps in `SessionsTable.tsx` | **pass** |
| Content left edge on the canonical line | 92 = 24 body + 36 rail + 32 `.center` | **pass** (browser form; 56 in embedded, no rails) |
| Content right edge symmetric | 1636, symmetric with left | **pass** (via the `layout-no-right` right-gutter balance, `4f4aae08`) |
| h1 scheme — Sessions has **none** | zero `h1`, zero `h2` in `.center` | **pass** |
| First content flushes to the datum | section `margin-top: 0`, section top == first-ink top | **pass** |
| Keyline scope | header rule + row separators use `--bn-colour-border`, not `--bn-colour-keyline` | **pass** — table chrome is data-grid anatomy and explicitly out of keyline scope |
| Radius tiers | grid furniture carries no rogue radii; `.bn-video-thumb` keeps `sm` | **pass** |

So the rewrite did not introduce page-geometry drift. The work below is the
*remaining* template adoption, plus one thing the rewrite newly makes possible.

### The work

**S1 — Move the Sessions intro line into the template's header slot.**
`.bn-session-moderators` ("Moderated by …" / "Observers: …") is rendered by
`SessionsTable.tsx` and styled in `templates/report.css`. Per the h1 scheme,
this line *is* Sessions' zone intro — the table names it as the reason Sessions
needs no h1. But it currently lives inside the island, so its spacing to the
datum is owned by the page, not the template — invariant 1 says the template
owns that. Move it to the shared `PageHeader` slot (the same slot that carries
zone titles + descriptions on other lenses), keeping the markup and the
`.bn-person-badge` usage. Acceptance: the intro line's top sits on the datum
with no page-level margin; deleting every rule in `report.css` matching
`.bn-session-moderators` changes vertical position by 0.

**S2 — Retire `.bn-session-meta`'s `min-width: 12rem` from the lens path.**
The Sessions grid already declines to use the class (see the comment at its
cell site), so the stopgap is inert *for this lens* — but it still sits in
`templates/report.css`, still applies to the sealed static render and the
Project-tab session list, and is a live trap for anyone adding a `.bn-cell-*`
rule (templates concatenate after organisms, so it wins on source order).
Scope it so it cannot reach the lens: `.bn-session-table table .bn-session-meta`
or move it into the static-render stylesheet. Acceptance: grep shows no
unscoped `.bn-session-meta`; the Project-tab list and static render are
unchanged by screenshot.

**S3 — Verify row rhythm on a multi-row fixture.** The smoke fixture has ONE
session, so `:last-child { border-bottom: none }` suppresses every separator
and the row rhythm is literally unobservable there — the measured
`0px none` above is correct behaviour, not a defect, and it means this pass
did **not** verify separators, row padding rhythm, or the head/body 2px→1px
step. Re-measure against a multi-session project (`trial-runs/project-ikea`).
Acceptance: separators resolve to `--bn-colour-border`; row block padding is
the `0.5rem` / head `0.6rem` pair the old `td`/`th` used.

**S4 — Declare Sessions' variant honestly in the variants table.** The table
above lists Sessions as `Left panel: SessionsSidebar`. Confirm that against
`AppLayout.tsx` after the rewrite and correct the row if it drifted. Invariant
2 means this table is the spec, not a description.

### Out of scope for this pass

- The **datum value itself** — still the open question below; a global tune,
  not a Sessions decision. Sessions should ride whatever `--bn-space-xl`
  settles at, not pin its own.
- **Embedded-mode measurement.** Everything above is browser-form. The datum
  and the rail-less edges differ in the `.app`, and the bundled sidecar is
  stale as of this writing, so an embedded pass needs a sidecar rebuild first.
- The responsive ladder and its thresholds — settled, shipped, and orthogonal
  to page geometry.

### Gate (blocks calling this done)

`window.__bnLayoutAudit()` **does not exist** — verified at runtime, not
inferred (`typeof window.__bnLayoutAudit === "function"` → `false`). Sequencing
step 5 is still deferred, so today the only enforcement is the Specimen lens
and the human eye, and the Sessions rewrite is exactly the kind of change it
was designed to catch. Build the probe and the per-route assertion **before**
S1–S4, so the conformance work lands against a ruler rather than a screenshot:
per route assert content-left == token, first-ink == datum, and radius tier per
component class, on both Chromium and WebKit.

## Open questions

- **Project tile row**: box-top on the shared start line (recommended,
  calmer for a card row) vs tile-number baselines on the datum.
- ~~**Stat tile radius**: stay `md` or join `lg`.~~ **Decided 25 Jul: stays
  `md`** — `lg` too big at tile scale.
- **The datum value itself** _(still open — this is the pending acceptance
  pass)_: the eye-approved reference is today's accidental Quotes position
  (~8px below the toolbar). Step 1 code shipped with the datum at
  `--bn-space-xl` (32px below the seam); the residual-reads-0 HUD read and the
  by-eye tune against the toolbar seam haven't run in the real app yet. Confirm
  or re-tune `--bn-space-xl` there.
- **Keyline scope**: lens-page section rules only (as specced) or also table
  chrome.
