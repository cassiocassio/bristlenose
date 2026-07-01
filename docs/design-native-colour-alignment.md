# Native colour alignment — audit (default palette)

_1 Jul 2026. Audit only — nothing in this doc has been implemented. Companion to the SF Pro typography alignment already shipped in `tokens-desktop.css`._

## Scope and method

The typography work aligned the webview's type to the macOS AppKit ladder. This audit asks which **other** graphical elements could gently follow — colour and shape, default palette only (`colors/palette-default.css`; edo is out of scope). The reference is not the HIG in the abstract but what the app's own native chrome actually does: the SwiftUI/AppKit sidebar, settings window, and toasts were read for their real values, and the SPA theme was read for its current ones.

The goal is *gentle* alignment. The report is a document-like content surface, not a control panel; most of it should keep reading as content. The candidates below are the places where the webview renders **chrome** — navigation, selection, buttons, focus — and where a mismatched blue or radius reads as "web page" inside a native window.

## The mechanism (already exists)

`tokens-desktop.css` activates under `[data-platform="desktop"]:not([data-typography="inter"])`, set via `BRISTLENOSE_PLATFORM=desktop` → server emits the attribute on `<html>`. Any desktop-only *colour* value would ride the same gate — but note the current selector couples the gate to the typography opt-out. If colour overrides land, they should sit in a block gated on `[data-platform="desktop"]` alone (or a new `tokens-desktop-colour.css`), so a user who opts back to Inter doesn't silently lose native colours too.

## Native reference values

What the Mac app actually uses (file:line in `desktop/Bristlenose/Bristlenose/`):

| Element | Native value | Where |
|---|---|---|
| Accent | System accent (empty `AccentColor.colorset` — rides the user's System Settings choice; blue for most users) | `Assets.xcassets` |
| Accent consumers | `Color.accentColor` at 0.14 opacity (lens pill), 0.2 fill + 1.5pt stroke (icon picker), 2pt stroke (drop target), `controlAccentColor` (activity ring) | `LensRail.swift:64-66`, `IconPickerPopover.swift:168-175`, `ProjectRow.swift:142`, `SidebarActivityRing.swift:155` |
| Sidebar selection | System-drawn source-list capsule, **pinned unemphasized** (grey, never accent-filled) in all focus states | `ProjectSidebarOutline.swift:204-210, 1240-1260` |
| Greys | Semantic only: `.secondary`/`.tertiary`/`.quaternary`, `secondaryLabelColor`, `tertiaryLabelColor`, `separatorColor`. No custom greys anywhere | throughout |
| Buttons | Semantic styles only: `.borderedProminent` (primary), `.bordered` (secondary), `.plain`/`.borderless` (inline). No custom button colours | `AIConsentView.swift:172`, `WelcomeView.swift:96`, etc. |
| Corner radii | **6pt** small pills (lens rail, icon picker), **8pt** rows/toasts/drop targets, **10pt** empty-state cards | `LensRail.swift:64`, `ToastView.swift:76`, `WelcomeView.swift:209-220` |
| Materials | `.regularMaterial` toast, `.quaternary` capsule search field | `ToastView.swift:76`, `QuotesToolbarControls.swift:53` |

macOS system blue resolves to approximately `#007AFF` light / `#0A84FF` dark; `unemphasizedSelectedContentBackgroundColor` to a mid grey around `#DCDCDC` light / `#464646` dark. **Sample with Digital Color Meter on the running app before implementing** — these shift across macOS releases and the native side uses semantic names, not constants.

## Current SPA values (default palette)

| Slot | Token | Light | Dark | Defined |
|---|---|---|---|---|
| Accent / links / primary buttons / focus / selection border | `--bn-colour-accent` | `#2563eb` | `#60a5fa` | `palette-default.css:16,94` |
| Nav + card selection bg | `--bn-selection-bg` | `#eef4fc` (blue tint) | `#1a2838` | `:71,143` |
| Nav hover | `--bn-colour-hover` | `#e8f0fe` (blue tint) | `#1e293b` | `:17,95` |
| Neutral hover overlay | `--bn-hover-bg` | `rgba(0,0,0,0.04)` | `rgba(255,255,255,0.06)` | `:67,147` |
| Hairlines | `--bn-colour-border` | `#e5e7eb` | `#2d2d2d` | `:15,93` |
| Radii | `--bn-radius-sm/md/lg/pill` | 3px / 6px / 8px / 999px | same | `tokens.css:175-178` |

Key consumers: `.toc-link.active`, `.session-entry.active`, `.signal-entry.active` (sidebar nav, `organisms/sidebar.css:467-471, 735-736, 888-895`); `.bn-selected` (quote cards, `atoms/interactive.css:51-60`); `.bn-btn-primary` (accent bg, **3px** radius, `atoms/modal.css:128-136`); `.toolbar-btn` (6px radius, `atoms/button.css:57-75`); `.bn-tab.active` underline (`organisms/global-nav.css:35`).

## Findings — tiered

### Tier 1 — align now

| # | Element | Current | Native counterpart | Recommended scope | Notes |
|---|---|---|---|---|---|
| 1 | **Accent blue** (links, primary buttons, tab underline, focus, selection border — all one token) | `#2563eb` / `#60a5fa` (Tailwind blues) | system blue ≈ `#007AFF` / `#0A84FF` | **Desktop-only** override of `--bn-colour-accent` | `#007AFF` on white is ≈4.0:1 contrast — fails WCAG AA for body-size text, so it should not become the shared web default; `#2563eb` (≈5.2:1) stays for browsers. Single-token blast radius: one override aligns links, buttons, focus rings and selection borders together — which is also native-consistent, so acceptable. |
| 2 | **Sidebar nav selection** (`.toc-link.active`, `.session-entry.active`, `.signal-entry.active`) | Blue tint `#eef4fc`/`#1a2838` + accent text | Unemphasized grey capsule (the native sidebar deliberately pins grey in all focus states) | **Desktop-only**: repoint the three nav selectors at a new `--bn-nav-selection-bg` slot; grey on desktop, current blue tint as the shared default | Distinguish **nav selection** (grey, matches the native sidebar one pane to the left) from **content selection** — `.bn-selected` on quote cards should stay accent-tinted; macOS content selection is blue, so the current card behaviour is already the native-correct one. |
| 3 | **Selection-lozenge radius** | Nav entries use `--bn-radius-sm` (3px) | Native pill vocabulary starts at 6pt (lens rail, icon picker) | **Shared**: change the consuming sites (`sidebar.css:450,728` etc.) from `radius-sm` to `radius-md` | Achromatic and subtle — fine everywhere. Change which token the nav rows consume; do **not** change `--bn-radius-sm` itself (badges and inputs use it correctly at 3px). |
| 4 | **Primary button radius** | `.bn-btn`/`.bn-btn-primary` at `--bn-radius-sm` (3px) | macOS push buttons ≈5–6pt; the SPA's own `.toolbar-btn` is already 6px | **Shared**: modal buttons `radius-sm` → `radius-md` | Also fixes an internal inconsistency: toolbar buttons and modal buttons currently disagree (6px vs 3px) for no stated reason. |

### Tier 2 — align later (parked, with the predicate that unparks each)

| # | Element | Gap | Why parked |
|---|---|---|---|
| 5 | **Dynamic user accent** | A user with a graphite/pink system accent gets blue webview chrome | Needs the bridge to pass `controlAccentColor` (env var → `data-accent` or injected CSS var, same pattern as typography). Static system blue is right for the large majority; unpark if a cohort tester with a non-blue accent notices. |
| 6 | **Hover vocabulary** | Two competing systems: blue-tinted `--bn-colour-hover` vs neutral `--bn-hover-bg` overlays. Native hovers are neutral (quaternary fills) | Converging nav hovers to the neutral overlay would match native but touches many call sites for a subtle gain. Do it opportunistically when those organisms are next open. |
| 7 | **Focus-ring weight** | 2px accent outline / 12–20% shadow ring vs macOS's softer, wider (~3.5px halo) keyboard ring | Low payoff; revisit if keyboard-navigation work reopens `interactive.css`. |
| 8 | **Window-focus selection dimming** | The plumbing exists (`.bn-window-inactive`, toggled from `AppLayout.tsx`) but its tokens are undefined — see Defects | Fix the defect first (spawned as its own task); full emphasized/unemphasized parity is then already achieved for content selection. |

### Tier 3 — deliberately don't

| Element | Why not |
|---|---|
| **Materials / vibrancy** (frosted toasts, translucent sidebars) | A webview can't sample under-window content; `backdrop-filter` only blurs the page itself. A faked material reads as web-trying-too-hard — worse than an honest opaque surface. |
| **Native control facsimiles** (segmented controls, radio groups, sheets) | The SPA's dropdowns and modals are correct web semantics; rebuilding AppKit controls in CSS is the uncanny valley. The native side keeps real controls. |
| **Hairline colours** | `#e5e7eb`/`#2d2d2d` already reads as a macOS hairline. Chasing `separatorColor`'s exact value is churn with no perceptible gain. |
| **Sentiment colours** | Analytical data colours, not chrome. Content owns its colour; never restyle to match window dressing. |
| **Scrollbars** | WKWebView already renders native overlay scrollbars. Nothing to do. |

## Defects found in passing (independent of alignment)

1. **`--bn-selection-bg-inactive` / `--bn-selection-border-inactive` are consumed but never defined** — `atoms/interactive.css:90-107`, `organisms/settings.css:380-384`. Invalid at computed-value time, so the inactive-window dimming never renders as designed. `theme/CLAUDE.md:55` wrongly documents them as defined in `tokens.css`. Spawned as its own task.
2. **`--bn-focus-shadow` has no dark variant** — same `rgba(0,0,0,…)` values both modes (`palette-default.css`); dark mode needs lighter shadow values for the lift to read.
3. **`HelloIsland.tsx:16,29`** — hardcoded `#c00` and `borderRadius: "6px"` inline; should be `--bn-colour-danger` and `--bn-radius-md`.

## Implementation sketch (non-binding)

If Tier 1 proceeds: a small `[data-platform="desktop"]` colour block (decoupled from the typography opt-out, per §Mechanism) overriding `--bn-colour-accent` and a new `--bn-nav-selection-bg` slot; two token-consumption edits for the radii. Add the new slot to `colors/_contract.css` and both palettes. Sample the exact system values from the running app (Digital Color Meter) at implementation time rather than trusting the approximations in this doc. Verify per the bundled-`.app` CSS gotcha in the root `CLAUDE.md` — an already-rendered project serves its stale baked `bristlenose-theme.css`, so test against a freshly-imported project.
