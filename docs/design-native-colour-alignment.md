# Native colour alignment (default palette)

_Started as an audit 1 Jul 2026; trued to shipped reality 2 Jul 2026. Companion to the SF Pro typography alignment in `tokens-desktop.css`. Interactive side-by-side: [`docs/mockups/native-colour-alignment.html`](mockups/native-colour-alignment.html)._

## What this is for

The desktop app hosts the React SPA in a `WKWebView` next to native AppKit chrome (project sidebar, settings window, sheets, toasts). The goal is an **invisible seam**: a user on a default, modern-OS Mac running default Bristlenose should not be able to tell what's CSS and what's AppKit. This doc records the colour/shape decisions that serve that goal, what shipped, and — most importantly — the **principles future colour work must keep** (§Principles).

## Principles for future colour work (read this first)

Two durable rules govern every future change to the default (non-edo) palette. They outrank any local cleverness (this doc's own history is the cautionary tale — see the decision log).

1. **Align across the seam.** Credible-native comes from *ruthless* alignment of the things the eye compares across the AppKit↔webview boundary: **semantic text colours, the grid, corner radii, and selected-capsule foreground + background.** This is the central discipline and it holds *regardless of palette* — it's what makes even a branded colour-set (edo) read as one app. Colour identity sits on top; seam alignment underneath is what earns "plausibly macOS."

2. **Track the OS colours pragmatically, via ground truth.** The default palette **copies the system colours that ship in the current OS** — not a hand-tuned approximation. Apple publishes **no canonical hex** for these (they're dynamic: light/dark, accent, Increase Contrast, desktop tint, and they shift across releases; sidebar greys are drawn on vibrant materials, so a sample is a *composite*). So "keep it aligned" means a **ground-truth mechanism**, in order of preference:
   - **Best (bitrot-proof):** bridge the live `NSColor` from Swift into CSS variables at runtime — same mechanism as the appearance/typography bridge. Then the webview tracks *this* machine's OS automatically. This is also what makes **dynamic system-accent** work (match whatever accent the user actually set). Do accent + selection-grey together when this lands.
   - **Pragmatic (today):** sample with Digital Color Meter against the running app and hardcode the hex, with a comment saying so, and **re-sample at OS bumps.** Every sampled value in the palette carries that caveat.

   Corollary: perceptual truth beats the contrast math when they conflict. At button scale the eye reads even a hue-matched near-miss (`#0068D6`) as "not the OS blue" — so we copy Apple's blue verbatim and accept its tradeoffs (see decision log), rather than substitute a "more accessible" blue that breaks the seam.

## Decisions & status

| # | Decision | Scope | Status |
|---|---|---|---|
| 1 | **Accent = Apple system blue**, copied verbatim: `--bn-colour-accent` = `#007AFF`/`#0A84FF`. Whole accent-blue family moved with it (selection-border, focus-ring, glow, minimap, suggestion). Single token for now (buttons, links, focus, selection text, tab underline). | Shared palette, no web/desktop fork | ✅ Shipped `de788028` |
| 2 | **Sidebar nav selection = grey capsule + accent text/icon.** New shared token `--bn-nav-selection-bg` (`#EFEFEF`/`#2B2B2B`, sampled); `.toc-link.active` / `.session-entry.active` / `.signal-entry.active` backgrounds repointed off `--bn-colour-hover` onto it. Text/icon already ride `--bn-colour-accent`. | Shared (both palettes; edo gets a warm-grey analogue) | ✅ Shipped (this change) |
| 3 | **Nav-lozenge radius → 6px** (`--bn-radius-sm` → `--bn-radius-md` on `.toc-link`, `.session-entry`, `.signal-entry`). | Shared | ✅ Shipped (this change) |
| 4 | **Primary-button radius → 6px** (`.bn-btn` in `atoms/modal.css`). Also fixes an internal inconsistency — `.toolbar-btn` was already 6px. | Shared | ✅ Shipped (this change) |
| 5 | **Content selection stays blue** (`.bn-selected` quote cards). macOS content selection is blue, so this is already native-correct — do *not* grey it (that's nav selection only). | — | ✅ Correct as-is; inactive-dim fixed `85bb41bd` |

**No web/desktop fork.** The typography fork (`tokens-desktop.css`) exists only because SF Pro is Apple-licensed and the web can't ship it — colour has no such forcing function, so a single shared palette carries CLI-web and the embedded shell alike. (This reverses the original audit's desktop-only recommendation.) The one accepted cost: system-blue link text on white is 4.02:1 — below the 4.5:1 body-text bar, but it's Apple's own tradeoff (colour isn't the sole affordance) and buttons/rings/borders are UI components governed by 3:1, which it clears. If the link case ever bites, splitting a webbier `--bn-colour-link` (e.g. `#0071E3`, 4.70:1) off the accent is a cheap, one-token addition given the structure.

### Decision log (why, so it isn't relitigated)

- **Blue: `#2563eb` (Tailwind indigo) → `#007AFF` (Apple system).** An interim `#0068D6` (hue-matched, WCAG-safe, KISS single token) was considered and **rejected on perceptual grounds** — at button scale, beside a native `.borderedProminent` sheet button, the eye clocks even a same-hue near-miss as "not the OS blue." Apple is already telling us the right blue; the seam goal means copying it, not out-clevering it. Two-token chrome/link split deferred (trigger: shipping dynamic system-accent).
- **Selection grey: sampled, not guessed.** `unemphasizedSelectedContentBackgroundColor` sampled `#EFEFEF` light (Finder) / `#2B2B2B` dark (bn.app's own sidebar; Mail read `#2A2929` — same value, vibrancy composite). An earlier `#DCDCDC`/`#464646` guess was both wrong and put dark accent-on-capsule under 3:1; the sampled values clear it (light `#007AFF` on `#EFEFEF` = 3.5:1, dark `#0A84FF` on `#2B2B2B` = 3.9:1).
- **Exotic user accents are "on them."** A default modern-OS Mac shouldn't be able to tell CSS from AppKit; a user who sets a graphite/pink system accent and notices the webview stays blue is the edge case, addressed later by the dynamic-accent bridge, not by hedging the default now.

## Native reference values

What the Mac app actually uses (file:line in `desktop/Bristlenose/Bristlenose/`, captured 1 Jul 2026 — verify against current source):

| Element | Native value | Where |
|---|---|---|
| Accent | System accent (empty `AccentColor.colorset` — rides the user's System Settings choice; blue for most) | `Assets.xcassets` |
| Accent consumers | `Color.accentColor` (lens pill 0.14 opacity, icon-picker 0.2 fill + 1.5pt stroke, drop-target 2pt stroke), `controlAccentColor` (activity ring) | `LensRail.swift:64-66`, `IconPickerPopover.swift:168-175`, `ProjectRow.swift:142`, `SidebarActivityRing.swift:155` |
| Sidebar selection | Source-list capsule, **pinned unemphasized** grey in all focus states | `ProjectSidebarOutline.swift:204-210, 1240-1260` |
| Corner radii | **6pt** small pills (lens rail, icon picker), 8pt rows/toasts, 10pt empty-state cards | `LensRail.swift:64`, `ToastView.swift:76`, `WelcomeView.swift:209-220` |

macOS system blue ≈ `#007AFF` light / `#0A84FF` dark; `unemphasizedSelectedContentBackgroundColor` sampled `#EFEFEF` / `#2B2B2B`. No canonical Apple hex — see §Principles.

## Deferred (parked, with the predicate that unparks each)

| Element | Gap | Unpark when |
|---|---|---|
| **Dynamic user accent** | Static `#007AFF` won't match a non-default system accent | Bridge `controlAccentColor` (+ the selection `NSColor`) — do them together. Cohort tester with a non-blue accent notices, or we commit to the bridge. |
| **Link-blue split** | System-blue link text on white = 4.02:1 | If the web-export link contrast is flagged. Cheap: add `--bn-colour-link` (`#0071E3`). |
| **Hover vocabulary** | Nav hover is still blue-tinted `--bn-colour-hover`; native hover is neutral | Opportunistically, when those organisms are next open. Seam-discipline eventually wants neutral hover. |
| **Focus-ring weight** | 2px accent ring vs macOS's softer ~3.5px halo | If keyboard-nav work reopens `interactive.css`. |
| **`--bn-focus-shadow` dark variant** | Same `rgba(0,0,0,…)` both modes; dark needs a lighter lift | Low-risk polish. |

## Deliberately don't

| Element | Why not |
|---|---|
| **Materials / vibrancy** | A webview can't sample under-window content; a faked material reads as web-trying-too-hard — worse than honest opacity. |
| **Native control facsimiles** | The SPA's dropdowns/modals are correct web semantics; rebuilding AppKit controls in CSS is the uncanny valley. |
| **Hairline colours** | `#e5e7eb`/`#2d2d2d` already reads as a macOS hairline; chasing `separatorColor` exactly is churn. |
| **Sentiment / data colours** | Analytical, not chrome. Content owns its colour — never restyle to match window dressing. |
| **Scrollbars** | WKWebView already renders native overlay scrollbars. |

## Edo (branding — second concern, decided later)

Colour-sets are identity, not seam alignment. Aspiration: make edo an opinionated, unmistakably-Bristlenose palette (the way Obsidian's purple "could only be Obsidian"), possibly the *default* with "Like macOS" as a fallback — while keeping "like macOS" highly plausible. Either way the §Principles seam discipline still runs underneath edo (it fills the same contract, incl. the new `--bn-nav-selection-bg`). Not scheduled.

## See also

- Side-by-side lab (every candidate, light+dark, ★-marked decisions): [`docs/mockups/native-colour-alignment.html`](mockups/native-colour-alignment.html)
- Memory: `project_native_seam_alignment_discipline` (the durable principle)
- Commits: accent `de788028`; inactive-selection tokens `85bb41bd`; radii + selection capsule (this change)
- `TODO.md` → "Native colour/shape alignment"
- Precedent: `bristlenose/theme/CLAUDE.md` § "Inactive window dimming", § typography scale; `tokens-desktop.css`
