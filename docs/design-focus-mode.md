# Focus mode

Status: design settled, unbuilt. Mockup: [`docs/mockups/nightfall-focus.html`](mockups/nightfall-focus.html) (built under the working title "Nightfall").

## What it is

A **distraction-free reading state** for the report: recess everything that isn't the signal so the researcher can read the quotes alone. Chrome — tag chips, sentiment badges, timecodes, hover hints, the card box itself — recedes to a faint outline; the quotes stay lit.

It is a **mode**, orthogonal to the **theme**. You can be in Focus in light, dark, default, or Edo. It is *not* dark mode and it is *not* a Reader view.

The lineage is iA Writer / Typora "Focus Mode" (dim the non-active content in place), not VS Code Zen (hide + re-center) or Safari Reader (reflow to an article column). We deliberately took the dim-in-place behaviour and the name that goes with it.

### The signal / noise line

The rule that decides what survives: **keep the source's marks and the researcher's own; recede the machine's annotations.**

| Stays lit | Recedes to faint outline |
|---|---|
| Quote text | Tag chips / sentiment badges |
| Speaker code (`pN`) — whose voice | Timecodes |
| Star — *if starred* (the researcher's mark) | Context line, hover hints |
| Theme headings (dim less — wayfinding) | Card background + border |

Unstarred stars go **fully dark** — absence is information, so the starred quotes read as lit points across the page. Only marks you made stay lit.

## Non-goals

- **No reflow. Ever.** The quote under your gaze must not move. This is the whole point — see below.
- Not a theme switch. Toggling Focus never flips light/dark.
- Not "Reader" — no re-layout into a reading column (that name would promise reflow).

## Behaviour

### Zero reflow, by construction

The toggle touches **only** `opacity`, `color`, `background`, and `border-color` — never a layout property, and nothing leaves the DOM. If layout is never touched, reflow is *impossible*, not merely avoided. Receded chrome keeps its footprint (a quote may show a blank band where its chips were — that is the correct price of no-reflow; we never collapse the gap).

Consequence for accessibility: the DOM and reading order are unchanged, so for a screen-reader user Focus is close to a no-op. No `aria-live` announcement needed — just the toggle's pressed/checked state.

### Motion — dusk, not a light-switch

~320ms, `ease-in-out`, symmetric on the way back. No overshoot/bounce (wrong register for reading evidence). `opacity`/`color` transitions are GPU-composited, so this is also the performant path — the taste call and the engineering call agree.

`prefers-reduced-motion: reduce` → snap (duration ~0).

### Guards

- **Keyboard handler bails if focus is in an `<input>`, `<textarea>`, or `contenteditable`** — the report has search-as-you-type *and* inline quote/heading editing, so the bare `z` shortcut (below) must not fire mid-edit. `useKeyboardShortcuts.ts` already applies this `isEditing()` guard to its other bare keys.
- Faded chrome must drop out of **tab order and hit-testing** (`pointer-events: none`, and un-tabbable) — you can't tab into an invisible chip.

## Token model — how it survives palette × appearance

The hard part is not the POC; it's that the transform must compose with every palette (`default`, `edo`, future) and appearance (light/dark) without naming a colour. It does, because almost the entire transform is palette-agnostic:

- **Chrome → faint:** `opacity: var(--bn-focus-ghost-opacity)` (default `0.14`). No colour — correct in every palette.
- **Card dissolve:** `background: transparent` + `border-color: color-mix(in srgb, var(--bn-colour-border) 40%, transparent)`. Reads the *resolved* border token, so it's right in Edo-dark for free.
- **Signal stays lit:** uses the existing `--bn-colour-text` / `--bn-colour-starred` — already per-palette-correct.

The **one** thing that isn't free is the optional dark-mode ground-deepen. It drops into the existing palette pattern as a single new contract token:

```css
--bn-colour-bg-focus: light-dark(var(--bn-colour-bg), /* deepened dark ground */);
```

- **Light mode: `--bn-colour-bg-focus == --bn-colour-bg`** — no darkening. Darkening light mode reads as dirty, not calm. Light-mode Focus is recede-only.
- **Dark mode:** may deepen slightly — dark-mode flavour riding along, not the essence of the feature.

Because `_contract.css` + `test_color_contract.py` already force every palette to define every token in both the plain block and the `@supports light-dark()` block, **adding Focus is O(1) per palette**: one token, in the two places the contract already makes authors touch. A future palette gets Focus by filling one line — or nothing, if the `light-dark()` default looks right.

Global knobs (structural, non-overridable — live in `tokens.css`, not the contract):
`--bn-focus-ghost-opacity` (0.14), `--bn-focus-heading-opacity` (0.4), `--bn-focus-dur` (320ms), `--bn-focus-ease`.

## Affordances across surfaces

One taxonomy, three renderings. The surfaces do **not** have equal claim: Focus is a reading-time view state, so the SPA owns the toggle, the Mac app owns a native command that drives it, the CLI owns only the boot default.

| Surface | Primitive | Entry point | State shown by |
|---|---|---|---|
| **SPA** (serve + export) | Toolbar toggle + bare `z` | Moon button in the report toolbar | `aria-pressed` / active styling |
| **Mac app** | View menu item + `⌘⌥F` | View ▸ Focus Mode (checkmarked toggle) | Menu checkmark — webview is source of truth |
| **CLI** | Settings default | `report.default_view` in shared Settings | — (not an interactive surface) |

**The shortcut splits by layer — bare key on web, Cmd-combo in the native menu, both dispatching the same toggle.** This is the established house pattern (web `[` ≠ native `⌘⌥S`, deliberately), and two verified constraints ruled out a unified `⌘\`:

1. **`\` belongs to the sidebar family.** Bare `\` already toggles both web sidebars (TOC + tags); `⌘⌥\` is the reserved native sidebar fallback (Notion / 1Password precedent). Any `\` combo reads as "sidebar" in this app.
2. **The native menu bar intercepts every Cmd-combo before the WKWebView sees the keydown** (`NSMenuItem` key equivalents — the same reason the web layer uses bare keys throughout, and why `⌘F` had to be reclaimed natively). A `⌘`-shortcut in `useKeyboardShortcuts.ts` works in the browser but is swallowed in the embedded app.

So: **web** registers bare `z` in `useKeyboardShortcuts.ts` (behind the existing `isEditing()` guard), passing through identically in browser and WKWebView; **native** binds `⌘⌥F` on the View ▸ Focus Mode item, dispatching `menuAction("focusMode")` over the bridge (mirrors `⌘F` → `menuAction("find")`). They need not match. The webview holds the state and reports back so the checkmark stays honest. The CLI gets **no `run` flag** — a flag mutating a downstream viewer's state is the `--static`/`--no-serve` conflation again; its only honest contribution is the boot default, a shared Settings key.

Why bare `z` for web (not `f`, not `⌘`-anything): no mainstream browser (Safari/Chrome/Edge/Firefox on Mac/Win/Linux) reserves a **bare letter** — they reserve modifier combos (`Cmd/Ctrl+[` back was the cautionary case), function keys, and Firefox's bare `/` + `'` type-ahead. A bare letter is therefore the only key that's free *and* behaves identically across OSes (no Cmd-vs-Ctrl divergence). `z` is free in the browsers and in our bound set (`? / [ ] \ m x h s t r j k`), is layout-robust (a letter fires regardless of AZERTY/Dvorak position — unlike backtick, a dead key on several EU layouts), sits out on the bottom-left rim clear of the typing flow, and carries a mild zen/quiet mnemonic. `⌘⌥F` is free natively (`⌘⌥S`/`⌘⌥L`/`⌘⌥T` are taken, `F` isn't) and menu-advertised, so it needn't be find-contested. Both easy to swap if they grate.

## Embedded seam negotiation (the genuinely hard axis)

Standalone (browser / export): the webview background *is* the window — Focus darkens (dark mode) or not (light) freely.

Embedded (`data-platform="desktop"`, native window behind the WKWebView): if Focus changes the ground colour, the native window background must change in lockstep or a light AppKit gutter shows around a darkened webview — the seam breaks.

Mechanism: **reuse the existing seam-alignment bridge.** On toggle — and on any theme change *while* in Focus — the webview posts its resolved `--bn-colour-bg-focus` (`getComputedStyle`) to native; native sets the `NSWindow`/container background to match. Native stays palette-blind: it just matches a colour. Light-mode embedded sends `bg == bg-focus`, so nothing at the seam moves — correct by construction.

## State & persistence

- **Serve:** SPA settings store.
- **Embedded:** same store; native menu checkmark mirrors it via the bridge.
- **Export:** self-contained — `localStorage`, seeded at export time with the baked `report.default_view` default (no server, no native side).

Persistence rule: remember the last choice per instance, but a freshly-opened project boots in normal view — Focus is a lean-in action, not a default state. The Settings default overrides this for handoff/kiosk use.

## Phasing

Phases 0–2 ship the SPA + export together (visual, fast). Phase 3 is the native track (Apple-slow). The CLI piece is trivial and rides Phase 1.

- **Phase 0 — token model (unblocks all).** Add `--bn-colour-bg-focus` to `_contract.css` + both palette files (both blocks each); extend `test_color_contract.py`. Add the global knobs to `tokens.css`. Author the `.bn-focus-mode` rules as formulas over existing tokens. Acceptance: default light+dark and Edo all render Focus with **≤1 override** and zero hardcoded colours.
- **Phase 1 — SPA behaviour, non-embedded.** `.bn-focus-mode` on the report root; React state in the settings store; toolbar moon button + bare `z` (behind `isEditing()`); boot from `report.default_view`; works in both `serve` and export. Browser-testable via `serve --dev`.
- **Phase 2 — matrix hardening.** Playground rendering palette × appearance × focus; tune per-palette `--bn-colour-bg-focus` where `light-dark()` misfires (Edo's warm dark ground is the likely one); verify palette/appearance switches *while* in Focus don't jank.
- **Phase 3 — embedded / native.** Extend the seam bridge to re-post the resolved ground on toggle + theme-change-in-focus; View ▸ Focus Mode item + `⌘⌥F` with checkmark mirroring the webview; verify no light-mode seam gap.
- **Phase 4 — tests + this doc trued.**

## Testing — invariants, not a 16-cell snapshot matrix

Three invariants carry it; don't screenshot every palette × appearance × context × state cell:

1. **Toggling changes no element geometry** across palettes (the zero-reflow guarantee, asserted on bounding boxes).
2. **Signal elements retain full opacity/colour** and receded chrome drops to the ghost opacity, in every palette (the contract test already guarantees `--bn-colour-bg-focus` exists everywhere).
3. **Embedded seam colour equals the webview ground** after toggle.

## Open decisions (settled unless reopened)

- Name: **Focus Mode** — settled. (Rejected: Nightfall — smuggles luminance; Reader — promises reflow.)
- Shortcut: **bare `z` (web) + `⌘⌥F` (native View menu)** — settled. (Rejected: `⌘\` — `\` is the sidebar family + native menus eat Cmd-combos before the WKWebView; bare `f` — find-contested; `⌘§` — ISO-keyboard-only, absent on US/most layouts, and may be the system window-cycle key on UK boards; backtick — dead key on several EU layouts.)
- Light-mode ground: **recede-only** (`bg-focus == bg`) — settled.
- Embedded ground: **drive native to match via the seam bridge** — settled.
- Report-wide only for v1; per-section Focus (a moon on the section header) deferred until it's demonstrably missed.

## Changelog draft — HELD until ship

Ready to drop into `CHANGELOG.md` under the shipping version **once Phase 0–2 actually land**. Not in the changelog now because the feature is unbuilt — a user-facing entry for something users can't use would be a promise (no-promises rule). Follows the `0da3cb40` precedent (parked launch copy held for ship day). Trim the affordance list to whatever actually shipped before pasting.

> **Focus Mode — quiet everything but the quotes.** A new reading state for the report. Press `z` — or the moon button in the toolbar, or View ▸ Focus Mode (`⌘⌥F`) in the desktop app — and the chrome recedes: tag chips, sentiment badges, timecodes, the card boxes themselves all sink to a faint outline, leaving just the quote, the speaker code, and the stars you set. Nothing moves. The toggle only fades opacity and colour, never layout, so the quote under your eye stays pinned to the pixel while everything around it drops away — you keep your bearings, the target just becomes unmistakable. Unstarred stars fade out entirely, so the quotes you've marked read as lit points across the page. It's a *mode*, not a theme: it composes with Default and Edo, light and dark, and in the desktop app it deepens the ground to match the native window with no seam. Dusk, not a light-switch — a ~320 ms fade that respects Reduce Motion. Ships on PyPI and in the desktop app.

