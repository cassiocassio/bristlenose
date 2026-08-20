---
status: partial
last-trued: 2026-08-20
trued-against: uncommitted working tree @main on 2026-08-20
---

# Design: Keycaps — showing a key to press, everywhere

**Status:** **Decided** (19 Jul 2026) — the § Recommendation skin assignment is the committed design. **Partially implemented (20 Aug 2026): step 3 shipped**, Skin A only, in the welcome cells. Steps 1, 2, 4 and 5 pending (§ Implementation plan).
**Date:** 19 Jul 2026 · **Last trued:** 20 Aug 2026

## Changelog

- _2026-08-20_ — **Step 3 shipped: the SwiftUI cap graduated out of `#if DEBUG`, Skin A only.** `Keycap` now lives in `desktop/Bristlenose/Bristlenose/Keycap.swift` — **Skin A · Flat alone**, because the first consumer is the welcome cells' body copy and §2 names Flat as the inline-prose default; Raised (B) is for surfaces where the key *is* the content and would shout inside a paragraph. The gallery's six-skin primitive stays as the comparison harness, renamed `GalleryKeycap` so the shipping name is the unqualified one. Colours are byte-matched via `KeycapPalette`. **The flow problem §3 implied is real and is solved by rasterising, not by layout:** a cap is a `View` and cannot flow inside a wrapping `Text`, and rebuilding a sentence as a flow of word-views would lose truncation, `lineLimit` and `ViewThatFits` — all of which belong to `Text`. `KeycapInline` renders the cap once per (key, appearance) through `ImageRenderer` and interpolates it as an image, which flows and breaks lines natively. Appearance is passed **explicitly**: `ImageRenderer` resolves colours against the app appearance rather than the view's `colorScheme`, so an implicit read silently produces a light cap on a dark cell. Consumer + rationale: [`design-welcome-screen.md`](design-welcome-screen.md) §Cell 1 key-reference note.
**Mockups:** [`docs/mockups/keycap-gallery.html`](mockups/keycap-gallery.html) (web) · `desktop/Bristlenose/Bristlenose/KeycapGalleryView.swift` (native, Debug ▸ Keycap Gallery)
**Sibling:** [`design-keyboard-shortcuts.md`](design-keyboard-shortcuts.md) owns *which* shortcuts exist, platform detection, the help modal, and tooltips. **This doc owns the visual/implementation primitive** — the cap itself — shared by all of them.

## Problem

Telling a user "press Option-Command-L" in prose is slow to parse and platform-fragile. A *keycap* — a rounded box around a glyph — turns an instruction into something the eye reads instantly as "a key you press." We need this primitive in four places that don't share a rendering engine, and until now each has hardcoded its own answer (or has none):

| Surface | Today | Wanted |
|---|---|---|
| **SPA** (React) — help modal, tooltips | `help-overlay.css` `<kbd>`, flat-bottom shadow | Shared, refined cap |
| **Public web docs** — manual on bristlenose.app | nothing | Same cap, one CSS file |
| **CLI** — terminal help output | nothing | Bare glyph, no chrome |
| **Native macOS** — custom/teaching UI | glyph strings typed into `desktop.json` (`"…(⌘⌥L)"`) | SwiftUI cap + SF Symbols |

The goal: **one glyph map, one set of skins, rendered natively per surface** — solved once so we stop re-deriving it.

## Settled rules (recap — not re-litigated here)

From the Apple Style Guide + Gruber, already fixed in `design-keyboard-shortcuts.md`:

1. **Modifier order:** Fn → Control → Option → Shift → Command.
2. **Glyphs concatenate, no separator** (`⇧⌘S`); spelled-out words take `+` (`Ctrl+Shift+S`).
3. **Uppercase the key when modified** (`⇧J`, not `⇧j`); bare keys stay lowercase (`j`).

This doc is about the *skin*, not those rules.

## §1 — The glyph map (the one source of truth)

Every surface reads from this. The **Unicode glyph is the cross-platform constant**; the **SF Symbol is the native upgrade** (weight/scale control, optical alignment) with the Unicode glyph as its guaranteed fallback; the **non-Mac word** is the Windows/Linux spelling.

| Key | Glyph | Unicode | SF Symbol | Non-Mac word |
|---|---|---|---|---|
| Command | ⌘ | U+2318 | `command` | — |
| Option / Alt | ⌥ | U+2325 | `option` | Alt |
| Shift | ⇧ | U+21E7 | `shift` | Shift |
| Control | ⌃ | U+2303 | `control` | Ctrl |
| Caps Lock | ⇪ | U+21EA | `capslock` | Caps Lock |
| Return | ↩ | U+21A9 | `return` | Enter |
| Enter (numpad) | ⌤ | U+2324 | `return` | Enter |
| Escape | ⎋ | U+238B | `escape` | Esc |
| Delete (back) | ⌫ | U+232B | `delete.left` | Backspace |
| Forward delete | ⌦ | U+2326 | `delete.right` | Delete |
| Tab | ⇥ | U+21E5 | **none** → use glyph | Tab |
| Space | ␣ | U+2423 | `space` | Space |
| Arrow up/down/left/right | ↑ ↓ ← → | U+2191–2193 | `arrow.up` … | ↑ ↓ ← → |
| Fn / Globe | 🌐 | U+1F310 | `globe` | Fn |

**Tab has no SF Symbol** — `arrow.right.to.line` is the usual stand-in but reads as "indent," not "Tab." Prefer the ⇥ glyph even in the SF-Symbol path.

### Font gotcha (load-bearing)

**Render modifier glyphs in `--bn-font-mono` (SF Mono) or the system font — never Inter.** Inter's coverage of ⌘⌥⇧⌃ is incomplete, so the proportional body font silently falls back *per glyph* to a different face, and caps in the same combo end up mismatched. Every cap uses the mono/system stack for its glyph. (SF Mono and SF Pro both contain the full Apple modifier set.)

## §2 — The six skins

Named A–F, identical in the web and native galleries. Every skin rides one base cap; only the surface treatment changes.

| Skin | Look | Use for |
|---|---|---|
| **A · Flat** | badge-bg fill, hairline border, no shadow | Inline prose, tooltips, table cells — the quiet default |
| **B · Raised** ⭐ | gradient face + bottom edge + inner top highlight (physical key) | Help modal, onboarding, "press this" — when the key *is* the content |
| **C · Outline** | transparent face, border only | Tinted panels (inspector, coloured callout) where a fill would fight the bg |
| **D · Solid** | inverted chip (dark on light / light on dark) | One hero shortcut per screen (empty state, command-palette prompt) |
| **E · Mono grid** ⭐ | uniform `ch`-width mono caps | Aligned help lists — single chars form a scannable column (iA Writer) |
| **F · Bare** | glyph only, muted colour, no box | Native menus/rows (macOS draws shortcuts this way) + CLI |

⭐ = recommended defaults.

### CSS (web + docs)

Base — one class, glyph-safe font:

```css
.cap {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 1.7em; height: 1.7em; padding: 0 0.42em;
  font-family: var(--bn-font-mono);      /* glyph-safe — NOT the body font */
  font-size: var(--bn-text-label); font-weight: 500; line-height: 1;
  color: var(--bn-colour-text); border-radius: 5px; vertical-align: middle;
}
/* `vertical-align: middle` is the web's answer to inline baseline alignment.
   The native side cannot use it and needs an explicit `baselineOffset` — see
   §3 decision 3. Fixing one seam does NOT fix the other. */
.combo         { display: inline-flex; align-items: center; }
.combo.joined  { gap: 0; }               /* menu-bar style */
.combo.split   { gap: 0.28rem; }         /* teachable */
```

Skins:

```css
.cap--flat    { background: var(--bn-colour-badge-bg); border: 1px solid var(--bn-colour-border); }
.cap--raised  { background: linear-gradient(var(--bn-cap-face), var(--bn-cap-face-lo));
                border: 1px solid var(--bn-colour-border-hover);
                box-shadow: 0 1.5px 0 0 var(--bn-cap-edge),
                            inset 0 1px 0 0 var(--bn-cap-highlight); }
.cap--outline { background: transparent; border: 1px solid var(--bn-colour-border-hover); }
.cap--solid   { background: var(--bn-cap-chip-bg); color: var(--bn-cap-chip-text);
                border: 1px solid transparent; font-weight: 600; }
.cap--grid    { background: var(--bn-colour-badge-bg); border: 1px solid var(--bn-colour-border);
                min-width: 2.2ch; padding: 0 0.3em; }
.cap--bare    { background: transparent; border: 0; padding: 0; min-width: 0;
                color: var(--bn-colour-muted); }
/* non-Mac words: .cap--word { font-family: var(--bn-font-body); min-width: 0; padding: 0 0.5em; } */
```

New tokens to add to `tokens.css` (light / dark via `light-dark()`), each a hair off `badge-bg` so the raised top edge catches light:

| Token | Light | Dark |
|---|---|---|
| `--bn-cap-face` | `#fbfbfc` | `#2c2c2e` |
| `--bn-cap-face-lo` | `#f0f1f3` | `#232325` |
| `--bn-cap-highlight` | `rgba(255,255,255,0.9)` | `rgba(255,255,255,0.06)` |
| `--bn-cap-edge` | `#cfd2d7` | `#000000` |
| `--bn-cap-chip-bg` | `#1a1a1a` | `#e5e7eb` |
| `--bn-cap-chip-text` | `#f4f4f5` | `#1a1a1a` |

### SwiftUI (native)

The cap is a small `View`; the skin owns the decoration, the token owns the glyph source. Full working reference in `KeycapGalleryView.swift`. The load-bearing shapes:

```swift
// Raised: bottom edge behind a gradient face.
ZStack {
    RoundedRectangle(cornerRadius: 5).fill(capEdge).offset(y: 1.5)
    RoundedRectangle(cornerRadius: 5)
        .fill(LinearGradient(colors: [capFace, capFaceLo], startPoint: .top, endPoint: .bottom))
        .overlay(RoundedRectangle(cornerRadius: 5).strokeBorder(borderStrong))
}
```

Palette colours are **byte-matched to `colors/palette-default.css`** via a dynamic `NSColor(name: nil) { appearance in … }` provider so the native cap and the CSS cap sit on the same seam (`Color.token(_:)` in the gallery). Don't reach for `NSColor.controlBackgroundColor` et al. for the cap surfaces — they won't match the web.

## §3 — Native decisions (nailed down)

These are the choices that were previously unmade on the Swift side.

1. **Unicode glyph vs SF Symbol — default to the Unicode glyph via `Text`.** On macOS it renders from SF Pro and matches the menu bar exactly; it's one string, no per-key symbol lookup, and it's the same value the web/CLI use. Reach for SF Symbols (`Image(systemName:)`) only when you need per-symbol weight/scale control or you're mixing keys with other symbols in a row — then compose an `HStack` of `Image` + `Text`. Both paths are wired in the gallery; toggle "SF Symbols" to compare. (Tab has no symbol — see §1.)

2. **Caps are for teaching surfaces; native menus get bare glyphs.** This is the native-primitives rule applied to keys: **there is no stock "keycap view," so a drawn cap (A–E) is a justified custom primitive for help/onboarding/teaching UI. But `NSMenu`/`NSMenuItem` already renders shortcuts as bare right-aligned grey glyphs — never draw a cap there.** Skin F documents exactly what the OS does; use it for any list-row or menu-style hint, and let real `NSMenuItem`s render their own `keyboardShortcut`. Departing from bare-glyph inside a menu context would be uncanny-valley.

3. **An inline cap MUST be baseline-corrected; it does not sit right by default.** `Text` aligns an interpolated image's **bottom edge** to the text baseline, so a cap dropped into a sentence rides high by its own descender space plus half its vertical centring slack — visibly floating above the line, which reads as a rendering bug rather than a key. The correction is `Text(cap).baselineOffset(-d)` where `d` is the distance from the cap's bottom edge up to the baseline of the glyph **inside** it:

   ```swift
   let f = NSFont.monospacedSystemFont(ofSize: fontSize, weight: .medium)
   let lineHeight = f.ascender - f.descender      // descender is negative
   let topInset = (box - lineHeight) / 2          // Text is centred in the cap
   let d = box - (topInset + f.ascender)          // 5.19pt at fontSize 11
   ```

   Derive it from `NSFont` metrics, never eyeball a constant — the number moves with `fontSize` and a hardcoded one silently rots. `KeycapInline.run(_:dark:)` returns the cap **already corrected**, and callers should use it in preference to `image(_:dark:)`: the correction is not optional, and pre-applying it is the only way a caller cannot forget. This is the native counterpart of the CSS's `vertical-align: middle` — same problem, different mechanism, so the two seams need separate fixes and neither implies the other.

4. **Menu titles stay English; the cap is chrome, not data.** Consistent with the SwiftUI `CommandMenu` limitation already documented — the glyph map is UI chrome rendered per-surface, not translated content.

## §4 — CLI

The terminal can't box-draw a cap cleanly, so the CLI renders **skin F only — the bare Unicode glyph** (`⌘F`, `⇧⌘E`). This is legible, unambiguous, and needs no library. CLI is English-only in alpha, so no non-Mac word path is needed there. If a future CLI wants platform-aware output, it reuses the same glyph map + the non-Mac word column, not a new one.

## §5 — Joined vs split

Orthogonal to skin, chosen per surface:

- **Joined** (`⇧⌘S`, no gap) — menu-bar truth, compact. Default for glyph combos; matches how macOS renders shortcuts.
- **Split** (`⇧ ⌘ S`, small gap) — teachable, each key discrete. Use for first-time onboarding and always for spelled-out non-Mac words (`Ctrl + S`), where fusing would be unreadable.

## Recommendation

- **B · Raised** — default keycap (help modal, teaching, docs section headers).
- **A · Flat** — inline prose and tooltips.
- **E · Mono grid** — the aligned help list (this is also Phase 4 of `design-keyboard-shortcuts.md`).
- **F · Bare** — native menus/rows and the CLI.
- **C / D** — situational (tinted panels; single hero prompt).

All six are one CSS file + one SwiftUI file, driven by the §1 glyph map.

## Implementation plan (when built)

The extraction the shortcuts doc anticipated (`design-keyboard-shortcuts.md` line ~453 — "keep `KeyCombo` extractable so a Swift consumer can read the same definitions") lands here:

1. **Promote the cap CSS** out of `help-overlay.css` into `atoms/kbd.css` (a real atom in `_THEME_FILES`), add the six skins + the new tokens. `help-overlay.css` then consumes `.cap` instead of styling `<kbd>` itself.
2. **React `Kbd` component** wrapping `.cap`, driven by the existing `KeyCombo` model in `ShortcutsSection.tsx`, `isMac()`/`isDesktop()`-aware. Docs site imports the same CSS.
3. ~~**Swift `Keycap` view** — graduate `KeycapGalleryView.swift`'s primitive out of `#if DEBUG` into a shipping helper for teaching UI; the gallery stays as the harness.~~ ✅ **Done 20 Aug 2026** — `Keycap.swift`, Skin A only (add further skins when a surface actually needs one, not speculatively). Gallery primitive renamed `GalleryKeycap` and retained. Inline flow via `KeycapInline` + `ImageRenderer`; see the changelog entry above for why rasterising beats a flow layout here.
4. **CLI helper** — a tiny formatter mapping the glyph map to bare glyphs for terminal help.
5. **Kill the hand-typed glyph strings** in `desktop.json` (`"…(⌘⌥L)"`) once native menu items carry real `keyboardShortcut`s + the shared formatter — removes the 20-locale drift risk.

## Cross-references

- [`design-keyboard-shortcuts.md`](design-keyboard-shortcuts.md) — which shortcuts exist, platform display paths, help modal, tooltips, the four display contexts, Phase 4 (mono grid, "or" connector, sort-by-key).
- `bristlenose/theme/molecules/help-overlay.css` — today's `<kbd>` (essentially skin B with a flat shadow).
- `desktop/CLAUDE.md` § Native primitives first — why a drawn cap is a justified custom primitive but a menu cap is not.
- `frontend/src/components/about/ShortcutsSection.tsx` — `KeyCombo` model + `renderKeyCombo()` the React `Kbd` will consume.
