# Type & Colour Parity — Mac App ⇌ WKWebView

Terse notes. Goal: WKWebView contents and native AppKit chrome look like one app, not two stapled together. CLI HTML stays as-is — "good enough for freeware."

## Scope

| Target | Aligned? | Font stack | Notes |
|---|---|---|---|
| Mac app native chrome | Yes | SF Pro (system) | Toolbar, sidebar, menus |
| Mac app WKWebView | Yes | SF Pro via `-apple-system` | Must match native chrome |
| CLI / browser HTML | No | Inter + fallbacks | Freeware tier; looks good, not native-matched |
| Static render export | No | Inter + fallbacks | Same as CLI |

Single CSS, two outcomes: in WKWebView `-apple-system` resolves to SF Pro with optical sizing and Apple's tracking; everywhere else it falls through to Inter. Don't fork CSS.

## Font stack (single source)

```css
font-family:
  -apple-system, BlinkMacSystemFont,       /* SF Pro in WKWebView / Safari on Mac */
  "Inter", "Inter var",                    /* Everywhere else, self-hosted */
  system-ui, sans-serif;
```

- Self-host Inter (woff2) so CLI/Chrome/Firefox render it deterministically. Don't rely on Google Fonts at runtime.
- Keep `font-optical-sizing: auto` (the default). Don't set it.
- `-webkit-font-smoothing: auto` — not `antialiased`. Let the OS decide. (Biggest single cause of "web view looks thinner than native.")

## Type scale — HIG-aligned

Native-side is fixed by Apple. Web-side maps 1:1 onto it. Line heights as absolute values (`16/13`, not `1.5`).

| Token | Native (HIG) | CSS (px/px) | Weight | Use |
|---|---|---|---|---|
| `type/large-title` | 26 / 32 | 26/32 | 400 | Hero headers (rare) |
| `type/title-1` | 22 / 26 | 22/26 | 400 | Page titles |
| `type/title-2` | 17 / 22 | 17/22 | 400 | Section headers |
| `type/title-3` | 15 / 20 | 15/20 | 400 | Sub-sections |
| `type/headline` | 13 / 16 | 13/16 | 600 | Emphasised body |
| `type/body` | 13 / 16 | 13/16 | 400 | Default |
| `type/callout` | 12 / 15 | 12/15 | 400 | Secondary body |
| `type/subheadline` | 11 / 14 | 11/14 | 400 | — |
| `type/footnote` | 10 / 13 | 10/13 | 400 | Fine print |
| `type/caption-1` | 10 / 13 | 10/13 | 400 | Labels |
| `type/caption-2` | 10 / 13 | 10/13 | 500 | Stronger labels |

pt ≈ px at 1× Retina. Aim for perceptual identity, not byte identity.

Copy Apple's per-size tracking (letter-spacing) into CSS — SF applies it automatically, Inter doesn't. Biggest closable gap after font-smoothing.

## Audit discipline

- Every style in `bristlenose/theme/tokens/` maps to exactly one HIG row. Orphans → delete, don't invent an 12th native style.
- Two sizes of semibold, not three. Two sizes of caption, not four.
- Deliberate overrides OK with a `/* HIG override: reason */` comment. Undocumented drift is the target.

## Colour — semantic, not hex

Native semantic names are the source of truth. CSS tokens bind to them; hex values are computed, not authored.

| CSS token | HIG semantic | Notes |
|---|---|---|
| `--bn-text-primary` | `labelColor` | |
| `--bn-text-secondary` | `secondaryLabelColor` | |
| `--bn-text-tertiary` | `tertiaryLabelColor` | |
| `--bn-border` | `separatorColor` | |
| `--bn-bg-window` | `windowBackgroundColor` | |
| `--bn-bg-content` | `textBackgroundColor` | |
| `--bn-accent` | `controlAccentColor` | **Must be user-configurable** — injected from Swift |

In CSS, prefer `-apple-system-*` / `system-ui` colour keywords and `color-scheme: light dark` over hex. Hex is the audit target.

### Accent injection (Mac app only)

WKWebView doesn't inherit `NSColor.controlAccentColor`. Plumb it from Swift:

```swift
webView.evaluateJavaScript(
  "document.documentElement.style.setProperty('--bn-accent', '\(accentHexP3)')"
)
```

Convert to P3 hex (not sRGB) to match native rendering on P3 displays. Without this, accent colour is the dead giveaway even when type parity is perfect.

In CLI / browser: fall back to a fixed brand accent. Freeware doesn't get native accent sync.

## Dark mode & accessibility

- `color-scheme: light dark` on `html` — gives form controls native dark without restyling.
- `@media (prefers-color-scheme: dark)` → swap token values, not hand-rolled dark styles.
- `@media (prefers-contrast: more)` → honour Increase Contrast.
- `@media (prefers-reduced-transparency)` → kill blurs/translucency.
- Audit dark mode first — light mode hides mismatches, dark exposes every hardcoded `#fff`.

## Renderer differences — what actually diverges

In WKWebView vs native AppKit (same machine, same Core Text):

- **Line height**: 0.5–1px off from native at same pt. Usually invisible.
- **Subpixel positioning**: rightmost glyph edge can land 1px apart.
- **Font smoothing**: `antialiased` makes web text look thinner than adjacent native. Use `auto`.
- **Optical sizing**: works in WKWebView with `-apple-system`. Don't override.
- **Tracking**: SF applies Apple's table automatically; CSS doesn't. Copy values per size.
- **Colour profile**: hex in CSS = sRGB; `NSColor` = P3. Accent blue visibly shifts on P3 displays if hex-authored.
- **Form controls**: WebKit's approximations ≠ native. Restyle from scratch or accept mismatch.
- **Scrollbars**: don't style. WebKit's default matches native.
- **SF Symbols**: unavailable to CSS. If native chrome uses a real symbol, don't fake it in the web view at the seam.

In Safari / Chrome on non-Mac: engine differences dominate. Accept them. CLI target is "looks good," not "looks native."

## Parity page (Figma)

Native control rendered with a style, next to web equivalent rendered with same style. Screenshots from real builds, not mocks. Squint at arm's length:

- Visible gap → token is wrong, fix the mapping.
- Only visible at 400% zoom → leave it, rabbit hole.

## What stays out

- Don't fork CSS per target. One stylesheet, one fallback chain.
- Don't reimplement form controls to pixel-match native. Bristlenose isn't that app.
- Don't ship SF Pro as a web font. Licence risk + pointless in WKWebView where it's already system.
- Don't chase Chrome-on-Mac parity. CLI tier.

## CSS checklist — don't lose these

Consolidated list of CSS choices that matter for the seam. Each one is a known failure mode.

- [ ] **Font stack**: `-apple-system, BlinkMacSystemFont, "Inter", "Inter var", system-ui, sans-serif` — in that order.
- [ ] **Self-host Inter** (woff2, `font-display: swap`). No Google Fonts at runtime.
- [ ] **`-webkit-font-smoothing: auto`** — never `antialiased`. (Thins web text relative to native.)
- [ ] **`font-optical-sizing: auto`** — the default; don't override.
- [ ] **Line heights as absolute values** (`line-height: 16px` or unitless ratio computed from absolute — `calc(16/13)`). Not `1.5`.
- [ ] **Letter-spacing per size** — copy Apple's tracking table. SF applies it automatically; Inter doesn't.
- [ ] **`color-scheme: light dark`** on `html`. Gives native form-control dark mode free.
- [ ] **Semantic colour tokens only** — no hex literals in component CSS. Hex lives in the token file, computed from HIG semantics.
- [ ] **`--bn-accent` injected from Swift** in the Mac app; fixed brand accent in CLI. Never hardcoded blue.
- [ ] **Accent hex in P3**, not sRGB, when injecting from Swift.
- [ ] **`@media (prefers-color-scheme: dark)`** — token swaps, not hand-rolled dark styles.
- [ ] **`@media (prefers-contrast: more)`** — honour Increase Contrast.
- [ ] **`@media (prefers-reduced-transparency)`** — kill blurs.
- [ ] **`@media (prefers-reduced-motion)`** — kill non-essential transitions.
- [ ] **Don't style scrollbars**. WebKit default matches native.
- [ ] **Don't restyle form controls to pixel-match native**. Accept WebKit's approximation or fully own them in React.
- [ ] **Don't fake SF Symbols** in CSS where native chrome uses the real thing at the seam.
- [ ] **Audit dark mode first** — light mode hides mismatches.

## Order of work

1. Audit `bristlenose/theme/tokens/` type + colour — current values, proposed HIG mapping, orphans.
2. Rewrite tokens against the audit. Update callers.
3. Self-host Inter. Update font stack. Fix `font-smoothing: auto`. Add tracking per size.
4. Wire Swift → CSS accent injection in WKWebView.
5. Dark mode audit.
6. Figma parity page once tokens are stable.

Step 1 is the real design work. Everything else is mechanical.
