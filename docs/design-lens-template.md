# Lens page template — one geometry, declared variation

*Design doc for unifying the five lens pages (Project, Sessions, Quotes,
Codebook, Analysis) under a single layout template: shared gutters, a shared
top datum, a shared h1 scheme, tokenised keylines and radii — so the lenses
cannot silently drift apart. Grew out of the 22 Jul 2026 measurement audit
(below), which found every lens on its own vertical rhythm and one lens
(Analysis) off-grid on all four sides.*

Status: **agreed direction, not yet implemented** (23 Jul 2026). The measured
audit and native-geometry diagnosis are complete and verified against the real
WKWebView (Debug build `c2f68e47`); implementation is sequenced at the foot.

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

### PageHeader and the h1 scheme

A shared `PageHeader` component (h1 + optional subtitle) opens every lens
except Project:

| Lens | h1 | Notes |
|---|---|---|
| Project | **none** | project title lives in the titlebar on both surfaces (native toolbar / browser Header). Tile-box top sits on the shared start line |
| Sessions | "Sessions" | key exists (`nav.sessions`) |
| Quotes | "Sections" + "Themes" | the two content zones promote in place; two h1s is an honest description of the page (screen readers mildly prefer one — accepted) |
| Codebook | "Codes" | text change from "Codebook"; QDA register |
| Analysis | "Signals" | key exists (`analysis.signals`); existing h2s stay below it |

One embedded datum rule on the shared h1 class replaces the Quotes-only
selector; the datum is **web-internal** (a token measured from the webview
top) rather than cross-seam, per the native ground truth above. The value is
tuned by eye in the real app — the current accidental Quotes position (8px
below the toolbar) is the reference the eye already approved.

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
   together (they're coupled through the datum).
2. **Analysis pane variant** — scroll container into SidebarLayout, gutter
   fix, `.signal-card` radius fix. (`git branch -f checkpoint` first — the
   riskiest step.)
3. **TOC sidebar treatment.**
4. **Keyline token + playground toggle.**
5. **`__bnLayoutAudit` + Playwright alignment gate** — locks it all in.

Trunk throughout; each step an independently-green commit. (The former
"frost quest" step is gone — scroll-underlap turned out to already work
natively; see Native geometry. The only frost residue is the scroll-0
solid band, an accepted platform limitation shared with Xcode.)

## Open questions

- **Project tile row**: box-top on the shared start line (recommended,
  calmer for a card row) vs tile-number baselines on the datum.
- ~~**Stat tile radius**: stay `md` or join `lg`.~~ **Decided 25 Jul: stays
  `md`** — `lg` too big at tile scale.
- **The datum value itself**: the eye-approved reference is today's
  accidental Quotes position (~8px below the toolbar); confirm or re-tune
  during step 1's acceptance pass in the real app.
- **Keyline scope**: lens-page section rules only (as specced) or also table
  chrome.
