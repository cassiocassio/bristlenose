# Design brief — content density (compact / normal / spacious)

**Status:** Design brief, pre-implementation. Captures a design conversation + prior-art
research + live-codebase calibration. No code written yet. Pick up from "Decisions" and
"Open questions" below.

**Update (3 Jul 2026):** Home confirmed — density is a **Settings ▸ General / Appearance**
preset sitting beside Appearance (light/dark), Colour palette (Default/Edo), and Typography
(SF Pro/Inter). The §9 note about palette/typography living off-`main` is now **stale**: the
Edo palette (`PALETTES = ["default", "edo"]`, `data-color-theme`) is on `main` and wired into
`SettingsModal.tsx`, so density joins an existing Appearance surface. **Open Q1 resolved:**
density is the macOS size control; `⌘±` / `WKWebView.pageZoom` stays the *browser / off-Mac*
path — acceptable there, wrong on macOS (it scales the web chrome and mismatches native
AppKit, which is the whole problem in §1). Ship the density preset first; defer the continuous
`⌘±` content-zoom axis. The §4 spacing-grid rebase is **bundled into the same piece of work**
(density's compact/normal/spacious spacing columns presuppose the `--bn-space-*` ladder is
grid-snapped), tracked as one item in the launch inventory under Quality of Life. Mockups
already validated the mechanism — treat as scoped, not speculative.

**Scope:** A user-facing **content density** control for the report surface — quotes,
transcripts, signal cards — that scales the *reading content* independently of the chrome
(sidebar, toolbar, headings), which stays at system scale. Primarily a macOS-desktop
concern; the CSS mechanism is channel-agnostic.

---

## 1. The problem

`⌘+` / `⌘−` in the desktop app drives `WKWebView` page zoom, which scales *everything
inside the web view* — including the web-rendered tag sidebar and rails — while the native
AppKit sidebar and SwiftUI toolbar stay put. The zoom control is effectively an x-ray of
the architecture: anything that grows under `⌘+` is web, anything that stays is native. The
result reads as a mismatch.

We don't want to "fix zoom" to cross the native/web boundary (you can't — AppKit has no
matching zoom). We want a **content-only density control**: the reading content scales; all
chrome (native *and* web) stays at system scale. That's the consistent baseline, with one
deliberate content-scoped exception.

The real driver of density is **not** aesthetic comfort — it's **information density for the
comparison task**: fit enough quotes in the viewport to judge them against each other
without scrolling. Its true inputs are human and physical: **eyesight** (age, acuity) and
**screen size** (generous on a 24" iMac, frugal on a 14" MacBook). That framing is why
density must be able to change **font size**, not just whitespace.

---

## 2. Prior art (macOS + web-in-native-shell)

Researched across native macOS apps, the macOS system, Apple HIG, and Electron apps.

### The native idiom is content-only scaling
Mail, Messages, Notes, Xcode, BBEdit, Craft, and Safari (text-only mode) all scale
reading/content text and leave chrome (sidebar, toolbar, window controls, menus) fixed.
`⌘+` / `⌘−` / `⌘0` is the near-universal shortcut, paired with **View → Zoom In / Zoom Out
/ Actual Size**. Reset (`⌘0`, or `⇧⌘0` where `⌘0` is taken) is an expected companion.

### macOS system mechanisms
| Mechanism | Set by | Scales | Notes |
|---|---|---|---|
| Accessibility → Display → **Text Size** ("Use Preferred Reading Size") | User | Content text (+ sidebars) | Apple's own content-only feature. Adopting apps: Calendar, Finder, Mail, Messages, Notes. **No public AppKit API to opt in** — third parties can't read or observe the slider. |
| Displays → **"Larger Text"** (scaled resolution) | User | Everything (whole UI) | HiDPI logical-resolution change. Global, blunt. |
| Appearance → **Sidebar icon size** (S/M/L) | User | Chrome (source-list sidebars) | Stored as `NSTableViewDefaultSizeMode` in `NSGlobalDomain`. |
| `NSControl.controlSize`, `NSTableView.rowSizeStyle` | Developer (`.default` defers to user) | One control / table rows | `rowSizeStyle = .default` follows the Sidebar icon-size preference. |

### Apple HIG position
- HIG, verbatim: **"macOS doesn't support Dynamic Type."** `NSFont.preferredFont(forTextStyle:)`
  exists but is **not** wired to the accessibility slider, posts no change notification, and
  has no public read API. So there is **no "for free" system path** — you build the
  scaling layer yourself.
- App Store Connect **Larger Text** criteria explicitly sanction *"your own in-app font size
  control"* as a valid way to claim the accessibility label — reaching **200%** without
  overlap or severe truncation qualifies. That gives the content-zoom axis a concrete target.

### Web-in-native-shell (the closest analogues)
- **VS Code:** three independent axes — `editor.fontSize` (content only), `window.zoomLevel`
  (whole UI), `terminal.integrated.fontSize`. The cleanest content/chrome split.
- **Obsidian:** `⌘=` whole-UI zoom vs a separate editor font-size (`⌘⇧=` / Appearance).
- **Discord:** Chat Font Scaling (content) + Zoom Level (whole app) + Message Group Spacing
  (density) — three independent, multiplicative levers.
- **Slack / Notion:** whole-window zoom only + a layout-density toggle. The cautionary tales
  — they get criticised for having *no* content-only text control.

### Discrete vs continuous
- Continuous `⌘±` step-zoom + `⌘0` is the native idiom for **content size**.
- A literal **Small/Medium/Large segmented picker has no strong first-party macOS precedent**
  — it's an iOS/web pattern. Apple Books uses an **A/A stepper** (reading surfaces), not a
  3-way segmented control.
- Discrete presets are the idiom for **density/comfort** (a settings-pane preference, à la
  Discord/Slack), *not* for the size lever.

**Sources:**
- HIG Typography — https://developer.apple.com/design/human-interface-guidelines/typography
- Larger Text criteria — https://developer.apple.com/help/app-store-connect/manage-app-accessibility/larger-text-evaluation-criteria/
- Use Preferred Reading Size — https://support.apple.com/guide/mac-help/make-text-and-icons-bigger-mchld786f2cd/mac
- Safari zoom (all-content vs text-only) — https://support.apple.com/guide/safari/zoom-in-on-webpages-ibrw1068/mac
- WKWebView.pageZoom — https://developer.apple.com/documentation/webkit/wkwebview/pagezoom
- Dynamic Type on macOS (absent) — https://lickability.com/blog/dynamic-type-and-in-app-font-scaling/
- Sidebar icon size default — https://macos-defaults.com/finder/nstableviewdefaultsizemode.html

---

## 3. Decisions

1. **Two axes, both CSS-scoped to the content region — not `WKWebView.pageZoom`.**
   Because our web view holds *both* content *and* web chrome (tag sidebar, rails),
   `pageZoom` would scale the web chrome too. Scope both axes to a content root
   (`data-density` / `data-content-scale`) that excludes chrome.
   - **Content size** (continuous, "everything bigger"): `⌘+` / `⌘−` / `⌘0`, View menu, and
     an optional Apple-Books-style A/A toolbar stepper. Target 200% max for the Larger Text
     label; layout must reflow cleanly at that size.
   - **Density** (discrete preset compact/normal/spacious): a Settings/Appearance preference.

2. **`⌘+` / `⌘−` = content, never whole-window zoom.** No whole-window zoom in the app —
   that's the Electron contortion we don't need and the broken behaviour we're replacing.

3. **Density steps the macOS type ladder — it does move font size.** Chosen over the two
   rejected mechanisms (see §4). Because density's job is information density for
   comparison, spacing-only doesn't cut it; the font must move, a **full rung**, on the
   ladder.

4. **Build the scaling ourselves.** No Dynamic Type on macOS; `NSFont.preferredFont`
   won't auto-scale. Apple sanctions the custom control and rewards it with the Larger Text
   label at 200%.

5. **Honour the OS for native chrome; don't reinvent it.** Set the native project sidebar's
   `NSTableView.rowSizeStyle = .default` so it follows the system Sidebar-icon-size
   preference. Native chrome sits on the 13pt Mac baseline.

6. **React store is the source of truth**, persisted to `localStorage` (gives CLI/serve-mode
   parity for free). The native View menu is a mirror + remote control via the WKWebView
   message bridge (see `docs/design-wkwebview-messaging.md`).

7. **Quotes stay sans.** Serif-for-user-voice is a deliberate *future* move pending type
   experimentation + licensing — not in scope here. (Some strong reading serifs are
   license-clean for prototyping: Charter, Source Serif, Apple's Iowan/New York.)

---

## 4. Density mechanism — why the type ladder, and how to snap to grid

Three mechanisms were prototyped and compared (interactive mockups, same six quotes at
compact/normal/spacious):

| Mechanism | Compact result (from body 15px) | Verdict |
|---|---|---|
| **1. Spacing only** (font fixed) | 15px, tighter gaps | Barely changes readable density — rejected. Fails the 14"-screen comparison task. |
| **2. Ratios** (× multiplier) | 14px, `pad 7.2→7`, `card 350` — **off-grid** | The dead zone: a ±1px change too small to perceive *and* off the macOS ladder. Dominated. |
| **3. Type ladder** (step the rung) | 13px `body`, 320px cards, on-grid | Only one that genuinely changes quotes-per-viewport while staying on ladder + grid. **Chosen.** |

### The font number: ±5% is the dead zone
At body 15px, `×0.95 → 14`, `×1.05 → 16`. That is imperceptible **and** off the macOS ladder
(rungs are 13 `body` / 15 `title3` / 17 `title2`). The real fork is **1.0 or a full rung**,
never ±5%. Since density is the size control on Mac, it steps a **full rung**.

### Don't multiply — index into ladders (no "jiggery-pokery")
A scalar multiplier guarantees off-grid output and forces rounding that is non-monotonic and
collapses distinctions. Instead, author **discrete, grid-snapped columns** and have the
preset pick a column. Every value lands on the 8/4 grid by construction.

**Font — step the macOS rung (not px scaling):**
| Content | Compact | Normal | Spacious |
|---|---|---|---|
| Quote / transcript body | 13 `body` | 15 `title3` | 17 `title2` |
| Signal title | 15 `title3` | 17 `title2` | 22 `title1` |
| Labels / meta (chrome) | 12 `callout` | 13 `body` | 13 `body` |

**Spacing — three grid-snapped columns (every cell ÷4, larger ÷8):**
| Token | Compact | Normal | Spacious |
|---|---|---|---|
| `--bn-space-xs` | 2 | 4 | 4 |
| `--bn-space-sm` | 4 | 8 | 12 |
| `--bn-space-md` | 8 | 12 | 16 |
| `--bn-space-lg` | 12 | 16 | 24 |
| `--bn-space-xl` | 16 | 24 | 32 |
| `--bn-grid-gap` | 12 | 20 | 28 |
| `--bn-quote-max-width` | 320 | 368 | 416 |

Rows scale *differently* on purpose — a uniform multiplier can't do that. The hairline barely
moves; the big gaps swing hard.

### Line-height is owned by the ladder + measure, not a density lever
Each rung owns its correct line-height. The only principled reason to deviate is **measure**
(line length). Density changes card width → measure → line-height shifts as a *consequence*
(compact ≈ 1.35, normal 1.40, spacious 1.45), derived not dialed.

### The type ladder already matches macOS; spacing does not (yet)
The desktop `--bn-text-*` tokens already map onto the AppKit ladder (label 13 = `body`, body
15 = `title3`, heading 17 = `title2`, title 22 = `title1`, display 26 = `largeTitle`). The
one deliberate deviation: reading text is bumped one rung above native `body` (13 → 15). **The
open work is re-basing the `--bn-space-*` scale onto the 8/4 grid** — today `xs` = 2.4px and
`sm` = 5.6px are off-grid rem-fraction artifacts. This is a real refactor (many consumers)
and should be done with visual diffing, not incidentally.

---

## 5. Calibration facts (verified against the codebase)

For anyone building the mockup or the feature — these are ground truth for "Normal must match
the shipping app":

- **WKWebView renders at 1.0** — no `pageZoom` / `magnification` / scale applied anywhere in
  `desktop/`.
- **Root font-size = 16px**, no zoom, no `-webkit-text-size-adjust`. `1rem = 16px`.
- **Quote body = 15px** (desktop `--bn-text-body` = 0.9375rem, macOS `title3`). Line-height 1.4.
- **`-webkit-font-smoothing: antialiased` is set on `<html>`** (`report.css`). This is
  critical for SF Pro perceived weight — a mockup that omits it renders noticeably heavier/
  larger. (It was the cause of an early mockup "too big/heavy" — the size was spec-correct; the
  missing smoothing made it read heavy.)
- **Weights: unstarred 420 (`--bn-weight-normal`), starred 520 (`--bn-weight-starred`).** Same
  numeric values on desktop (SF Pro) and web (Inter) — the weight axis is shared. Starred also
  resets timecode/speaker/badges back to 420.
- **Speaker codes render lowercase** ("p4", "p3") — data-driven, no `text-transform`.
- **Font stack (desktop):** `-apple-system, "SF Pro Text", "SF Pro", system-ui, …` (resolves
  to SF Pro on macOS). Web/CLI uses Inter. Toggle via `data-typography="inter"`.

---

## 6. Real quote-card anatomy (implementation reference)

DOM top-to-bottom (see `frontend/src/islands/QuoteCard.tsx`):
- **Hanging indent** — `.quote-row` is flex: timecode in a left gutter (`flex-shrink:0`,
  mono, accent blue, muted brackets), quote body `flex:1`. Timecode sits *beside* the text,
  not below.
- **Quote text** — smart quotes (`“ ”`), `--bn-text-body` (15px), weight 420 (520 + blue
  left border when starred).
- **Split speaker badge** (`PersonBadge`) — two-tone lozenge: mono gray code half + body-font
  white name half; code-only when name == code. Not per-speaker colour-coded.
- **Tags** (`.badges`): sentiment badge (`.badge-ai`, solid sentiment colour, mono),
  user/theme tags (`.badge-user`, solid fill), **proposed tags (`.badge-proposed`, dashed
  transparent, pulsing)**, and a dashed `+` add affordance.
- **Controls top-right** (absolute, in `padding-right: 4.5rem`): **star** (always visible,
  gold when starred), **hide** (eye-slash, opacity 0 → 1 on hover), **undo** (on edit).

Key files: `frontend/src/islands/QuoteCard.tsx`, `frontend/src/components/{Badge,PersonBadge,TimecodeLink}.tsx`,
`bristlenose/theme/organisms/blockquote.css`, `bristlenose/theme/molecules/{quote-actions,person-badge,badge-row}.css`,
`bristlenose/theme/atoms/{badge,toggle,button,timecode}.css`,
`bristlenose/theme/tokens.css`, `tokens-typography.css`, `tokens-desktop.css`.

---

## 7. Success metric

Not a taste call: **how many comparable quotes fit in one viewport, still readable for this
user.** Countable. Tune the rungs against it, and eyeball at real Retina scale in a 14"-vs-24"
frame — principle alone ("right in theory") can still look wrong.

---

## 8. Open questions (decide before building)

1. **Does Mac ship a separate content-zoom axis *in addition to* density?** This couples to
   the font decision: if density is the *only* Mac size control, it must move the rung (as
   decided). If a `⌘±` content-zoom also ships, density could be spacing-only and zoom owns
   font. Current lean: density is the primary Mac control; `⌘±` content-zoom is a fast-follow
   / the off-Mac (browser/CLI) path where PPI is unpredictable and users should own zoom.
2. **Where does the three-step window sit on the ladder?** Compact bottoms out at 13 `body`.
   If 13px reads too small at real scale, shift the window up (Compact 15 / Normal 17). Decide
   by looking, not by principle.
3. **Card-width swing** (320/368/416) drives column packing — tune columns-per-row against
   measure.
4. **Relationship to the `edo` palette + `bootPalette` work** (see note below) — density and
   the typography/palette option should be reconciled into one Appearance story, not two.

---

## 9. Note for whoever picks this up

The interactive exploration was done as chat mockups (not committed code). The *typography
tokens* this brief calibrates against (`tokens-desktop.css`) are identical to `main`. There is
separate palette/typography work (a `palette-edo.css` + `frontend/src/utils/bootPalette.ts`)
that lives in a non-`main` working copy and is *not* on `main` — if the "edo" typography
option is going to be a selectable Appearance choice alongside density, that work needs to be
reconciled onto `main` first, and this density brief should be folded into the same Appearance
surface.
