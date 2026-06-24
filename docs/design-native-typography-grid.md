# Native Typography & Grid — Consolidated Design

**Status:** Active design (Jun 2026). Consolidates and supersedes the typography/grid
decisions previously scattered across `docs/design-theme-divergence.md` (Layer I),
`docs/design-fonts.md`, and `docs/design-type-colour-parity.md`. Those docs remain
the deep references for icons/chrome (theme-divergence), the two-typeface vision
(fonts), and the WKWebView seam checklist (type-colour-parity). Where they disagree
with this doc on typography/grid mechanics, **this doc wins**.

## Goal

Make the embedded macOS app *believably* one native experience — not "a SwiftUI shell
and a CSS WebKit view glued together" — while the CLI-driven browser build (free tier)
stays on Inter as a strong cross-platform target. The user should not be able to feel
the seam between native AppKit chrome and the WKWebView contents.

We do this **without forking the codebase**: a single React SPA and a single stylesheet,
with presentation switched by attributes on `<html>` resolved in the CSS cascade. This
respects the no-fork principle in `docs/design-modularity.md` — the divergence is
*presentation*, not *logic*.

## The three orthogonal axes

Theming is modularised onto three independent attributes on `<html>`, set by
`_html_root_attrs()` in `bristlenose/server/app.py` and read by CSS selectors + the
`frontend/src/utils/platform.ts` helpers. They compose freely — any combination is valid.

| Axis | Attribute | Controls | Values today |
|---|---|---|---|
| **1. Type system** (font + grid) | `data-platform` | Font family, type scale, **and the spacing grid** | `desktop` \| (unset = web) |
| **2. Colour set** | `data-color-theme` | The 31-token semantic palette | `default` \| `edo` \| (future: named palettes) |
| **3. Light/dark** | `data-theme` + `color-scheme` | `light-dark()` resolution within a palette | `auto` \| `light` \| `dark` |

This is exactly the "font and grid on one variable; colour set and light/dark on another"
model. Axis 1 bundles **font + grid** together (a complete typographic identity); axes 2
and 3 are the colour story, independent of it. Adding "Edo dark" is axis 2 × axis 3; it
needs nothing from axis 1.

> **Naming note (open):** axis 1 is *named* `data-platform` but *means* "type system."
> Today desktop is the only non-web identity, so the conflation is harmless. If we ever
> want an Apple-native look outside the desktop shell, or a third type system, rename to
> `data-type-system` (`web` \| `native-apple`) with platform detection setting only the
> *default*. Cheap now, touches CSS + Swift→server→React later. **Recommendation: keep
> `data-platform` as the trigger for now; revisit only if a second trigger appears.**

## Decisions (this session)

1. **Font model: SF Pro UI swap only, single-slot.** The native variant swaps one font
   slot — `--bn-font-body` — from Inter to `-apple-system` (→ SF Pro on macOS). The
   two-typeface "tool voice / participant voice" vision (`--bn-font-ui` sans +
   `--bn-font-verbatim` Sentinel serif) from `design-fonts.md` is **deferred to a later,
   independently-gated phase** because it is blocked on a Hoefler&Co redistribution
   licence that has not been secured. It must not block native feel, which works today
   with the single slot.

2. **Grid: fork the spacing grid to an Apple point grid.** Axis 1 overrides spacing —
   not just type. Under `[data-platform="desktop"]` the spacing tokens snap to a 4/8-pt
   rhythm so the native build *feels* native in its whitespace, not just its letterforms.
   (This is net-new: today `tokens-desktop.css` overrides font + type scale only; the
   grid in `tokens.css` is shared.)

3. **Colour is independent — with a curated default pairing.** Axes are *mechanically*
   fully independent. But the Mac app ships a **default pairing** (SF Pro type system +
   a chosen colour theme) so the out-of-box look is curated, not SF-Pro-on-stark-default.
   The pairing is a *default*, overridable by the user, not a hard binding.
   > **Confirm:** this is my interpretation of the "something else" answer on axis
   > coupling. The current code hard-defaults desktop → Edo in `app.py`
   > (`if not color_theme and platform == "desktop": color_theme = "edo"`). The intent
   > here is to keep that as a *default only*, expose a picker, and let users land on any
   > (type-system × colour × light/dark) combination. Correct me if you meant a tighter
   > or looser coupling.

4. **Web stays on Inter — and must.** Not just taste: SF Pro's licence forbids use off
   Apple platforms, and `-apple-system` only resolves to SF *on Apple devices*. Inter is
   therefore the correct cross-platform target for browser/free users, and the split is
   load-bearing, not cosmetic.

## The critical gap: the switch is built but unplugged

`tokens-desktop.css` already contains the full SF Pro + Apple-HIG type scale, gated on
`[data-platform="desktop"]`. The server already emits that attribute when
`BRISTLENOSE_PLATFORM=desktop` is set. **But nothing sets that env var.** The Swift
subprocess environment factory `BristlenoseShared.childEnvironment(for:)` injects the
parent-death handshake, SSL paths, ffmpeg paths, and API keys — but not
`BRISTLENOSE_PLATFORM`. Net effect: **all the SF Pro work ships dark — it never activates
in the actual Mac app.**

The single highest-leverage change in this whole effort is one line in
`childEnvironment`:

```swift
env["BRISTLENOSE_PLATFORM"] = "desktop"
```

Everything downstream — server attribute injection, CSS selector, React `isDesktop()` —
is already in place. (Caveat per `desktop/CLAUDE.md`: a sidecar rebuild + clean build is
required to see it; a Cmd+R alone reuses the stale bundle. Use the **Dev Sidecar** scheme
for a fast loop.)

## Reconciling the source docs

Three pre-existing docs describe overlapping, partly-divergent plans. This is the debt
this consolidation pays down:

| Topic | `design-fonts.md` says | `design-theme-divergence.md` / code says | **Reconciled decision** |
|---|---|---|---|
| Font tokens | `--bn-font-ui` + `--bn-font-verbatim` (rename `--bn-font-body`) | code uses `--bn-font-body` / `--bn-font-mono` | **Keep `--bn-font-body` single-slot now.** Adopt `--bn-font-ui`/`--bn-font-verbatim` only when the Sentinel phase lands; until then `design-fonts.md`'s token rename is *aspiration, not spec*. |
| Verbatim serif | Sentinel for all quotes/transcripts | not implemented | **Deferred phase**, licence-gated. |
| Heading font | new `--bn-font-heading` Display token | not present; `-apple-system` auto-switches Text↔Display at 20pt | **No separate heading token.** Rely on `-apple-system` optical switch — simpler and correct. |
| Type scale fidelity | density-tuned rem scale | `type-colour-parity.md` wants literal HIG pt + absolute line-heights + per-size tracking | **Move toward literal HIG** for the desktop scale (absolute leading, add tracking tokens). See fidelity section below. |

After this doc lands, `true-the-docs` should mark the font-token rename in
`design-fonts.md` as deferred, and point its typography mechanics at this doc.

## Typography fidelity — where "believable" actually lives

These are the details that separate "native" from "webby" and are **not yet** in
`tokens-desktop.css`:

- **Letter-spacing (tracking).** SF applies Apple's per-size tracking table automatically
  *only in native controls*; in CSS you must copy the values. There are zero
  `letter-spacing` tokens in the desktop file today. `type-colour-parity.md` flags this as
  the single biggest closable gap after font-smoothing.
- **`-webkit-font-smoothing: auto`** (never `antialiased`). Antialiased thins web text
  relative to adjacent native text — the classic "web view looks thinner" tell. Confirm
  the report root isn't forcing it.
- **Absolute line-heights, not ratios.** The desktop scale uses ratios (`1.45`, `1.3`);
  Apple specifies absolute leading. Express desktop leading as `calc(N/size)` from the
  HIG pairs so it doesn't drift.
- **P3 accent injection.** WKWebView doesn't inherit `controlAccentColor`. Swift injects
  `--bn-accent` as **P3** hex via `evaluateJavaScript` (per `type-colour-parity.md`).
  Without this, the accent is the dead giveaway even when type parity is perfect. CLI
  falls back to a fixed brand accent.
- **Literal-ladder nit.** The current desktop map has `body 15px = "Apple callout"`, but
  Apple callout is 16pt; the scale was tuned for reading density, not strict HIG. Decide
  consciously: literal HIG ladder vs density-tuned approximation. This doc leans literal
  for the *native* axis (web keeps its density tuning).

On "Apple could change the ladder/font": a non-issue for believability. We match a
*snapshot* and pair it with the *real system font*. Users don't diff our tracking against
this year's HIG; internal consistency + SF Pro + correct smoothing sells the illusion.

## Colour orthogonality — ready, with two caveats

The colour axis is the cleanest part of the system and genuinely already orthogonal:
31-token contract in `colors/_contract.css`, isolated `palette-*.css` files, data-driven
registration in `theme_assets.py`, and a pytest contract test. Adding "Edo dark" or
terminal-inspired palettes is a **CSS-only, additive** operation.

Caveats:
- **No picker UI.** Colour theme is CLI/env-only today; the React `SettingsModal` exposes
  only light/dark. To "offer colour themes in the Mac app," add a picker that writes
  `data-color-theme` + persists to `localStorage` — copy the existing dark/light pattern.
- **Edo dark variants unfinished**, and the Edo accent choice (Prussian Blue vs Verdigris)
  is still open per `design-theme-divergence.md` Phase E.

**Terminal colour inheritance** (the "inherit colour sets from terminals" idea): a WebKit
view cannot read Terminal.app/iTerm palettes itself. Two routes — (a) Swift reads the
terminal's prefs and injects palette values as CSS vars (the same mechanism as P3 accent
injection) — fragile, every terminal stores prefs differently, and "the user's terminal"
is ill-defined for a GUI app; or (b) ship a curated set of recognisable named palettes
(Solarized, Nord, Gruvbox, Dracula) as palette files. **Recommendation: (b).** Cheap,
~90% of the emotional payoff, framed as "terminal-inspired themes," not literal
inheritance.

## Implementation sequence (no code yet — plan only)

Cheap and high-confidence first; nothing here is started until the open questions below
are settled.

1. **Activate the switch.** Add `BRISTLENOSE_PLATFORM=desktop` to
   `BristlenoseShared.childEnvironment(for:)`; rebuild sidecar + clean build. The existing
   SF Pro type scale turns on. (One line + build.)
2. **True the docs.** Reconcile `design-fonts.md` (mark token rename / Sentinel deferred)
   and point its mechanics here.
3. **Fork the grid.** Add a `[data-platform="desktop"]` spacing block (4/8-pt rhythm) +
   absolute line-heights + tracking tokens in `tokens-desktop.css`.
4. **Fidelity pass.** `-webkit-font-smoothing: auto`, P3 accent injection from Swift,
   literal-HIG type values.
5. **Decouple + default pairing.** Keep desktop→Edo as a *default*; add the React colour
   picker + `localStorage` persistence so all axis combinations are reachable.
6. **(Later, gated) Two-typeface phase.** Only if/when the Sentinel licence lands:
   introduce `--bn-font-ui` / `--bn-font-verbatim`, apply serif to verbatim content.
7. **(Later) Curated terminal-inspired palettes** as additional `palette-*.css` files.

## Maintenance notes

- **Archive sprawl.** `tokens-desktop-v1.css`, `tokens-typography-v1.css`,
  `tokens-typography-v2.css` live *in* `bristlenose/theme/` alongside active files. Only
  the canonical ones are in `_THEME_FILES`. Consider moving archives to an `archive/`
  subdir so nobody re-imports a `-v2`.
- **No-fork intact.** This is a presentation fork (a CSS attribute), not a code fork —
  compatible with `design-modularity.md`. The only future *channel* difference is bundling
  Sentinel `.woff2`, which the modularity model already accommodates.
- **CJK.** The desktop SF stack keeps Hiragino / Apple-SD-Gothic fallbacks (good). The
  deferred Sentinel serif has no CJK coverage — an open question for that phase only.

## Open questions

1. **Axis-coupling interpretation** — confirm the "independent + curated default pairing"
   reading in Decision 3.
2. **Axis-1 naming** — keep `data-platform` or generalise to `data-type-system`?
3. **HIG literalness** — literal Apple ladder for the desktop scale, or keep the
   density-tuned approximation?
4. **Grid values** — exact 4/8-pt step mapping for the desktop spacing tokens (needs a
   short design pass against the current rem scale).
5. (Inherited, unchanged) Sentinel licence outcome; terminal-palette route; Edo accent &
   dark variants.
