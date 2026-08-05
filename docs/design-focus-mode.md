---
status: current
last-trued: 2026-08-05
trued-against: HEAD@main on 2026-08-05 — the cursor-ring promotion, keyline de-duplication and starred-bar taming were uncommitted when trued and have since landed unchanged as "the cursor ring goes app-wide, and the starred bar stops shouting in dark" (333f494f) and "one thin line round the focused card, and three guards that couldn't fail" (69af7c6c)
---

# Focus mode

**Shipped in 0.24.0** (3 Aug 2026) — Phases 0, 1 and 3. Phase 2 (the palette × appearance tuning pass) is still owed; see § Phasing. Trued against shipped code 3 Aug 2026 by a `design-doc-review` pass, which is what caught the drift the in-session edits had left behind — the author had updated this doc six times across six design reversals and it read as settled while carrying claims from three superseded intermediate states.

**Sandpit: [`docs/mockups/focus-mode-lab.html`](mockups/focus-mode-lab.html)** — real quote-card markup over a baked copy of the shipped theme, all four palette × appearance cells side by side, with the rejected cursor cues still switchable. This produced the starred-border and keyboard-cursor reversals below. Re-bake its `.theme.css` from `load_default_css()` after any theme change or it silently shows the previous design.

> **Two known gaps in the lab, as of 5 Aug.** Its prose still frames the cursor cue as Focus-scoped, which stopped being true when the ring moved app-wide; and it has no starred-bar comparison cell, so the taming below can't be judged there. Turning Focus *off* in the HUD does exercise the ordinary-reading ring correctly — that part works.

Superseded mockup: [`docs/mockups/nightfall-focus.html`](mockups/nightfall-focus.html) — hand-rolled with its own hex values under the working title "Nightfall", so it shows *pre-decision* treatments and can't be used to judge contrast. Kept as history; don't read it as the design.

## What it is

A **distraction-free reading state** for the report: recess everything that isn't the signal so the researcher can read the quotes alone. Chrome — tag chips, sentiment badges, timecodes, hover hints, the card box itself — recedes to a faint outline; the quotes stay lit.

It is a **mode**, orthogonal to the **theme**. You can be in Focus in light, dark, default, or Edo. It is *not* dark mode and it is *not* a Reader view.

The lineage is iA Writer / Typora "Focus Mode" (dim the non-active content in place), not VS Code Zen (hide + re-center) or Safari Reader (reflow to an article column). We deliberately took the dim-in-place behaviour and the name that goes with it.

### The signal / noise line

Two axes, and they answer different questions. Conflating them is what produced the star bug corrected below.

**Axis 1 — what stays lit (content): keep the source's marks and the researcher's own; recede the machine's annotations.**

| Stays lit | Recedes to faint outline |
|---|---|
| Quote text | Tag chips / sentiment badges |
| Speaker code (`pN`) — whose voice | Timecodes |
| Star glyph — **always**, starred or not | Context line, hover hints |
| Selection + keyboard-focus state | Card background + border, **including the starred border** |
| Theme headings and descriptions (dim less — wayfinding) | |

**Axis 2 — what stays live (interaction): anything the researcher can act *through* stays fully interactive, and returns to full presence while engaged** — hover, keyboard focus, or active editing. **Receding is a resting state, not a disabled state.**

Axis 2 is what makes Focus safe to build without enumerating exceptions. The star is never receded; the hide button keeps its existing hover/focus reveal; a tag input opened with `t` is active editing, so it lights up with no special case; selection and the focus ring are the researcher's own live working state. Only chips at rest that nobody is touching are inert.

#### Corrected 3 Aug 2026 — stars are untouched by Focus

The first draft sent unstarred stars **fully dark**, reasoning that absence is information and the starred ones would then read as lit points. That was wrong, for two reasons found by reading the code:

1. **It removes the affordance for the mode's own primary activity.** You enter Focus to read quote text undistracted *so that you can star* — triage is the job. `.star-btn` ([`atoms/toggle.css:3`](../bristlenose/theme/atoms/toggle.css)) is the only always-present control on the card (its sibling `.hide-btn` is the hover/focus-revealed one). Darkening it darkens the one thing the mode exists to serve.
2. **The differential it was trying to create already exists, and is already quiet.** `--bn-colour-icon-idle` vs `--bn-colour-starred`: `#c9ccd1` → `#999` (default light), `#595959` → `#ccc` (default dark), `#b8ad91` → `#9e8b6e` (edo light). The resting unstarred star is already close to the floor against `#ffffff` / `#111111`. Zeroing it buys a marginal contrast gain and pays the affordance for it.

So there is **no Focus-specific star rule at all** — one fewer moving part, and the lit-points reading survives on the existing differential. This is consistent with the standing position that star contrast is a *state differential*, not an absolute target; Focus makes that differential maximal rather than introducing a new one.

**Second correction, same day — the starred *border* dissolves too.** The first fix kept `.starred` exempt from the border dissolve, on the same axis-1 reasoning. Seen on real data in the mockup, that was clearly wrong: `--bn-colour-starred` on a dissolved field was the loudest thing in the column, and it was shouting on *every* starred card at once. The star glyph and the heavier `--bn-weight-starred` body text (which Focus never touches) carry the mark perfectly well. Two cues, both in-content, neither shouting.

**Third correction, 5 Aug — the starred bar is tamed in dark *outside* Focus too.** Looking at the mode against a real study surfaced the same bar being wrong in ordinary reading. The failure is **ownership, not loudness**, and that distinction is the reusable part: at 10.84 contrast a 1px rule sitting in the gutter of a 2- or 3-column grid reads as a **divider between** two quotes rather than the **left bracket of** the one it belongs to, so on a wide screen you cannot tell which card it marks. Mixing it toward its own card's background pulls it back onto that card ([`molecules/quote-actions.css`](../bristlenose/theme/molecules/quote-actions.css)):

| | light (the reference) | dark, shipped | dark, tamed |
|---|---|---|---|
| default | 2.73 | 10.84 | **2.73** |
| edo | 2.72 | 7.08 | 2.22 |

Two things to know before touching the number. **39% is tuned to `default`**, which it matches exactly; edo lands gentler than parity and is **deliberately not chased** — one shared percentage cannot satisfy both (edo would want 49%), and edo is owed a colour pass of its own. A future author "splitting the difference" gets neither right. And **the star glyph is untouched**: `--bn-colour-starred` drives both the bar and the glyph, so taming the *token* rather than its border use would have collapsed the starred-vs-unstarred glyph differential from **4.36× to 1.10×** — destroying the very cue this section just established as the one Focus relies on.

## The one-ring rule

The two starred-border reversals and the keyboard-cursor decision are the same principle applied three times, so it is worth stating as a rule rather than re-deriving:

> **A mark that reads well on one object reads as noise on twenty.**

The starred left-line was *legible* — that was never in doubt. It was wrong because starred is a **plural** state: twenty cards can be starred at once, and twenty bright rules is a field, not a mark. The keyboard cursor gets the loudest treatment anywhere in the report — a 1px accent ring at 4–6.7 contrast, in ordinary reading as well as in Focus — for exactly the inverse reason: `.bn-focused` is **singular by definition**, so there is never more than one on screen.

Hence: **the ring is the cursor.** Selection keeps its background tint and its left edge; starred keeps its glyph and its text weight; neither may ever take the ring. Pinned by `TestOneRing` in `tests/test_focus_mode_css.py`, because the obvious future mistake is reaching for the ring to mark "selected" or "search match" — at which point the mode dies of rings.

## The keyboard cursor — why the cue is appearance-conditional

`.bn-focused` signals itself by dropping the card to the **page** colour and lifting it with `--bn-focus-shadow`. That is a *relative* idiom: it only says anything against neighbours that aren't focused. Focus Mode dissolves the neighbours to the page colour, removing the reference — so the same rule produces opposite results by appearance:

| | page | card | focused card becomes | shadow |
|---|---|---|---|---|
| default light | `#ffffff` | `#f9fafb` | the **brightest** surface | black on light — reads |
| edo light | `#fdfbf7` | `#f0e9d8` | the **brightest** surface, by more | black on light — reads |
| default dark | `#111111` | `#1a1a1a` | the **darkest** — as is everything else | black on `#111111` — nothing |
| edo dark | `#1a1816` | `#211e18` | same | same |

So light needs nothing added: the rule already makes the focused card the brightest ground on the page and the shadow reads against it. Dark needs an absolute cue, and the design system has exactly one channel with the contrast for it — accent, at 4.02–6.67 — because **every** surface option sits in a 1.04–1.29 band:

| | card surface | hover bg | selection bg | accent |
|---|---|---|---|---|
| default light | **1.045** | 1.146 | 1.106 | 4.02 |
| default dark | 1.085 | 1.291 | 1.263 | 5.18 |
| edo light | 1.171 | 1.215 | 1.197 | 6.67 |
| edo dark | 1.065 | 1.104 | 1.181 | 6.20 |

Rejected on those numbers: **card surface** (1.045 in default light — swaps an invisible cursor in dark for an invisible one in the *most common* configuration), **hover background** (best surface option, but a moused-over card and the cursor become indistinguishable), and **accent on the left border** — `--bn-selection-border` *is* the accent, so that renders identically to a selected card, and the left edge already carries selection, starred, and playback-active.

The shipped rule is additive, so light is untouched and dark resolves per palette for free:

```css
.bn-focus-mode blockquote.quote-card.bn-focused {
    box-shadow:
        var(--bn-focus-shadow),
        0 0 0 1px light-dark(transparent, var(--bn-colour-accent));
}
```

Deliberately **not** transitioned — a cursor must land the instant `j`/`k` moves it, not ease in over `--bn-focus-dur`.

### The cursor cue is app-wide, and lives outside this feature

The rule above is **not** in `templates/focus-mode.css` and is **not** scoped to `.bn-focus-mode`. It sits on `blockquote.quote-card.bn-focused` in [`atoms/interactive.css`](../bristlenose/theme/atoms/interactive.css), because the argument for it never depended on Focus Mode: in dark, dropping the card to the page colour is a weak cue against `#1a1a1a` neighbours and an invisible one against dissolved ones. Focus Mode only removed the last thing covering for it. `focus-mode.css` carries no cursor rule at all — a placeholder comment marks the spot and says why not to re-add one.

**The move fixed a bug, which is the argument for keeping it there.** At `.bn-focus-mode blockquote.quote-card.bn-focused` the ring scored (0,3,1) — identical to `.bn-window-inactive blockquote.quote-card.bn-focused`, but later in the concatenation, so the ring won and **kept glowing while the app was in the background**, against the macOS convention that affordances recede when the app isn't taking input. At (0,2,1) the inactive-window suppressor wins again. Pinned by `test_cursor_ring_recedes_when_the_window_is_inactive`, which fails any cursor rule carrying three or more classes.

**Keylines don't double up.** The card has a 1px `border-left` and the ring is a 1px `box-shadow` drawn *outside* the border box, so a focused card would show 2px on the left in two colours and 1px on its other three sides. The focused card therefore sets `border-left-color: light-dark(var(--bn-colour-border), transparent)` — in dark the ring owns the whole outline at a uniform 1px; in light there is no ring, so the border stays and reverts to neutral. Either way **focus pre-empts** the starred bracket *and* `.quote-card.quote-active`'s playback edge (both (0,2,0)) rather than stacking with them. Colour only — no reflow.

> **Ownership.** `docs/design-keyboard-navigation.md` owns `.bn-focused` and already states "ring for focus, background for selection" as a design principle. That doc is the canonical home for the rule; this section keeps the *derivation* (the four-cell contrast table above is Focus-specific evidence) and should not be mirrored there.

**The focused+selected combination has to state its own left edge.** `blockquote.quote-card.bn-focused` (which blanks the border) and `blockquote.quote-card.bn-selected` (which colours it) are **both (0,2,1)**, so which one won was decided purely by their order in one file — and selection won, putting 2px of blue on the left against 1px of ring everywhere else, on the very card being worked on. So focus pre-empts *starred* and *playback-active* (both (0,2,0)) but **not** selection; the combined selector settles it explicitly: `light-dark(var(--bn-selection-border), transparent)`. Light keeps the selection edge (no ring there to double up with); dark goes transparent so the ring carries one thin line the whole way round. Pinned by `test_focused_and_selected_states_the_left_edge`.

**Latent bug this surfaced, not fixed here:** `--bn-focus-shadow` has no dark variant in either palette (`rgba(0,0,0,…)` default, `rgba(30,20,10,…)` edo — warm-tinted, but still a dark shadow), so the focus lift has never been visible in dark mode **anywhere in the app** — Focus Mode merely removed the background differential that was covering for it. **That is now exactly what shipped** — see § The cursor cue is app-wide below. This paragraph previously ended "whether `.bn-focused` should carry the ring in dark generally is an app-wide change, deliberately out of scope here", which was true for about a day.

## Non-goals

- **No reflow. Ever.** The quote under your gaze must not move. This is the whole point — see below.
- Not a theme switch. Toggling Focus never flips light/dark.
- Not "Reader" — no re-layout into a reading column (that name would promise reflow).
- **Not the sidebars.** Focus does not touch the TOC or tag sidebar, including their `--bn-colour-inspector-bg` chrome tint. A reader who wants less noise has already closed them, `[` and `]` do it in one key, and fading a whole panel's tint while its contents stay lit reads as a rendering fault rather than a mode. Foveating without jumping matters more than completeness here. Revisit only if the closed-sidebar path proves not to be what people actually do.

## Behaviour

### Zero reflow, by construction

The toggle touches **only** `opacity`, `color`, `background`, and `border-color` — never a layout property, and nothing leaves the DOM. If layout is never touched, reflow is *impossible*, not merely avoided. Receded chrome keeps its footprint (a quote may show a blank band where its chips were — that is the correct price of no-reflow; we never collapse the gap).

Consequence for accessibility: the DOM and reading order are unchanged, so for a screen-reader user Focus is close to a no-op. No `aria-live` announcement needed — just the toggle's pressed/checked state.

### Motion — dusk, not a light-switch

~320ms, `ease-in-out`, symmetric on the way back. No overshoot/bounce (wrong register for reading evidence). `opacity`/`color` transitions are GPU-composited, so this is also the performant path — the taste call and the engineering call agree.

`prefers-reduced-motion: reduce` → snap (duration ~0).

### Guards

- **Keyboard handler bails if focus is in an `<input>`, `<textarea>`, or `contenteditable`** — the report has search-as-you-type *and* inline quote/heading editing, so the bare `z` shortcut (below) must not fire mid-edit. `useKeyboardShortcuts.ts` already applies this `isEditing()` guard to its other bare keys.
- **`pointer-events: none` applies only to *resting decorative* chrome** — a receded tag chip nobody is touching. They must never reach a control. The first draft stated this as a blanket rule over "faded chrome", which would have made `t` open an invisible, unfocusable tag input: the keystroke appears to do nothing, which is a silent failure and the worst of the three possible behaviours. Axis 2 above is the general form of the fix; scope the rule, don't special-case the controls. **Only `pointer-events` shipped** — the receded chips are not removed from tab order, so a keyboard user can still tab to a badge button at 0.14 opacity. Open a11y gap, not a described behaviour.
- **No auto-exit on tagging.** A mode that exits itself on a keystroke you didn't aim at it is a surprise, and it discards the reading state you built. `t` works exactly as it does outside Focus. The chip it creates recedes at rest, but the already-shipped `.badge-bulk-flash` (0.8 s ring pulse) confirms it landed without you having to read it — a free confirmation channel that needs no design.

### Selection and keyboard focus stay live

Both are the researcher's own working state, not machine annotation, so Axis 1 keeps them lit. There is also a shipped precedent that settles it from the other direction: `.bn-window-inactive` dims selection to grey ([`atoms/interactive.css:137-145`](../bristlenose/theme/atoms/interactive.css)) precisely because the window is **not** accepting input. Focus Mode is the opposite signal — you are working harder, not less — so dimming selection there would invert an established meaning.

**Implementation trap — the dissolve must exclude the interactive states explicitly.** `.bn-focused` and `.bn-selected` both express themselves through `background` ([`atoms/interactive.css:52-57, 62-93, 99-108`](../bristlenose/theme/atoms/interactive.css)), which is the same property the card dissolve sets to `transparent`. `blockquote.quote-card.bn-selected` is specificity (0,2,1) — exactly what a naive `.bn-focus-mode blockquote.quote-card` rule also scores. At equal specificity the later file in the concatenation wins, so Focus Mode would silently blind selection, and the failure only shows when someone tries to multi-select. Write the dissolve as `:not(.bn-selected):not(.bn-focused)`. (Same trap `bristlenose/theme/CLAUDE.md` documents under "CSS specificity vs source order in concatenated theme".)

Getting that right pays a dividend: in Focus, the **only** cards with a visible box are the ones you have selected. The group you are assembling for a bulk star reads as lit slabs on a quiet page — the mode's core activity, rendered by state machinery that already exists.

## Token model — how it survives palette × appearance

The hard part is not the POC; it's that the transform must compose with every palette (`default`, `edo`, future) and appearance (light/dark) without naming a colour. It does, because almost the entire transform is palette-agnostic:

- **Chrome → faint:** `opacity: var(--bn-focus-ghost-opacity)` (default `0.14`). No colour — correct in every palette.
- **Card dissolve:** `background: transparent` + `border-left-color: color-mix(in srgb, var(--bn-colour-border) 40%, transparent)`. Reads the *resolved* border token, so it's right in Edo-dark for free.
- **Signal stays lit:** uses the existing `--bn-colour-text` / `--bn-colour-starred` — already per-palette-correct.

### Recede-only in every appearance — the ground is never touched

**Settled 3 Aug 2026, replacing the `--bn-colour-bg-focus` contract token.** Focus never changes the ground colour, in any appearance. The first draft kept an optional dark-mode ground-deepen; it is deleted, and with it the new token, the palette edits, and the whole seam-negotiation problem.

Three reasons, in order of force:

1. **In the desktop app there is no webview ground to change.** The translucent detail column shipped: [`WebView.swift:136`](../desktop/Bristlenose/Bristlenose/WebView.swift) sets `drawsBackground = false` and [`report.css:35`](../bristlenose/theme/templates/report.css) makes `html[data-embedded="true"] body` transparent. Native owns the ground; the report samples through it. To deepen it, the body would have to become opaque again — destroying the vibrancy that work deliberately introduced. That is a regression, not a tuning problem.
2. **Contrast is relative to a fixed ground anyway.** Every recede in this design is expressed against whatever the ground is. Moving the ground *and* the chrome moves both ends of the relationship for no gain — the readability of the lit quote text is unchanged, and the calm the mode is after comes from the recede, not the darkness.
3. **It was never the essence.** The draft already called it "dark-mode flavour riding along" and had already ruled it out in light mode ("darkening light mode reads as dirty, not calm"). Extending recede-only to dark costs nothing the feature actually needs.

Consequence: the transform is now **entirely palette-agnostic**. No contract token, no palette files touched, nothing for a future palette author to fill in. It also tightens the zero-reflow guarantee into a zero-*ground* guarantee — touch only `opacity`, `color` and `border-color`, never `background` on the page, and Focus becomes structurally incapable of disturbing the vibrancy seam.

> **Correction to a claim in the first draft.** It asserted that `_contract.css` + `test_color_contract.py` "already force every palette to define every token in both the plain block and the `@supports light-dark()` block." They do not. [`tests/test_color_contract.py:60-68`](../tests/test_color_contract.py) takes a set difference over *every* `--bn-*:` declaration in the file, so a token defined in only one of the two blocks passes clean. The "O(1) per palette, mechanically enforced" claim was overstated. Moot for Focus now that the token is gone, but it is a live false belief that would mislead the next author of a contract token — either fix the doc that repeats it or tighten the test.

Global knobs (structural, non-overridable — live in `tokens.css`, not the contract):
`--bn-focus-ghost-opacity` (0.14), `--bn-focus-heading-opacity` (0.4), `--bn-focus-dur` (320ms), `--bn-focus-ease`.

**`--bn-focus-ghost-opacity` still needs settling against the prose (Phase 2).** At 0.14 a chip carrying `--bn-colour-badge-bg` (`#f3f4f6` on `#ffffff`) is *gone*, not "receded to a faint outline" — the number and the sentence disagree. It shipped at 0.14 with the prose unreconciled; settle it in the lab and make the losing one follow.

## Affordances across surfaces

One taxonomy, three renderings. The surfaces do **not** have equal claim: Focus is a reading-time view state, so the SPA owns the toggle, the Mac app owns a native command that drives it, the CLI owns only the boot default.

| Surface | Primitive | Entry point | State shown by |
|---|---|---|---|
| **SPA** (serve + export) | Toolbar toggle + bare `z` | Moon button in the report toolbar | `aria-pressed` / active styling |
| **Mac app** | View menu item + `⌘⌥F` | View ▸ Focus Mode — see § below | Menu state — webview is source of truth |
| **CLI** | — | none shipped | — (see § State & persistence: the boot-default key was designed, then not wired) |

**The moon button does not exist in the Mac app.** [`islands/Toolbar.tsx:63`](../frontend/src/islands/Toolbar.tsx) returns `null` when embedded — the whole web toolbar is suppressed there, its jobs having moved to the native toolbar. So the View-menu item is not a convenience duplicate of a web affordance; it is the app's **only** discoverable entry point, with bare `z` as the undiscoverable one. That raises the bar on getting the menu item right and is the reason the label question below got the attention it did.

### Menu placement (settled)

A section of one in `ViewMenuContent` ([`MenuCommands.swift:686-691`](../desktop/Bristlenose/Bristlenose/MenuCommands.swift)), reusing the divider already sitting above Zoom In and adding one below:

```
All Quotes                    ← Toggle, checkmark, radio pair
Starred Quotes Only           ← Toggle, checkmark, radio pair
──────────────────────────
Focus Mode                    ← this item
──────────────────────────
Zoom In                   ⌘=
Zoom Out                  ⌘-
Actual Size               ⌘0
```

The section may later gain other appearance-related items, but it should not be *designed* around hypothetical members — let it stay a section of one until a second earns its place.

A third checkmark directly beneath a checkmarked radio pair is not confusable here, and this was verified rather than assumed: Mail's View menu carries radio groups, standalone checkmarks and the whole `Show …` verb-swap family in one menu, with dividers doing the grouping; Finder does the same (view-mode radio group, divider, `Use Groups` as a standalone checkbox). Three things make our case safer still — the phrasing isn't parallel (`All Quotes` / `Starred Quotes Only` are noun phrases answering *which quotes*; `Focus Mode` is a named mode), it carries a shortcut and they don't, and the divider is the platform's grouping mechanism.

### Label and shortcut (settled)

**`Focus Mode`, bare title with a checkmark, `⌘⌥F`.** A SwiftUI `Toggle` matching the pair above it, with `set:` ignoring the new value and dispatching `bridgeHandler.menuAction("focusMode")` — the SPA owns the state, mirrored back. See § Decisions for the reasoning and the rejected alternatives.

Three details for the wiring:

- **Derive the checkmark from a published `BridgeHandler` property, never local `@State`.** Two reload paths would desync a local flag: a project switch (the WebView re-mounts on `.id("\(project.id)-\(port)")`) and `ContentView.scheduleReportReloadOnCompletion` → `reloadWebView()` after a run finishes. Shipped as an effect keyed `[embedded, focusModeActive]` ([`AppLayout.tsx:273-277`](../frontend/src/layouts/AppLayout.tsx)), which fires on mount and so re-syncs after either reload, plus a native reset in `BridgeHandler.reset()`. Not the `ready`-hook this originally prescribed.
- **No `systemImage`.** `All Quotes` and `Actual Size` carry none. While there: `All Quotes` has no icon but `Starred Quotes Only` has `systemImage: "star"` — a radio pair should be symmetric, so drop it or give both one. Small, free, and the kind of asymmetry that reads as nobody having looked.
- **Two i18n keys**, both across the 20 full locales and correctly absent from `zh-Hant-HK`: `desktop.menu.view.focusMode` (menu) and `toolbar.focusMode` (the web moon button). "Focus Mode" is registered in `bristlenose/locales/glossary.csv` with an explicit note that it is **not** Apple's system Focus — Italian renders that "Full Immersion", which would be actively wrong here.

**The shortcut splits by layer — bare key on web, Cmd-combo in the native menu, both dispatching the same toggle.** This is the established house pattern (web `[` ≠ native `⌘⌥S`, deliberately), and two verified constraints ruled out a unified `⌘\`:

1. **`\` belongs to the sidebar family.** Bare `\` already toggles both web sidebars (TOC + tags); `⌘⌥\` is the reserved native sidebar fallback (Notion / 1Password precedent). Any `\` combo reads as "sidebar" in this app.
2. **The native menu bar intercepts every Cmd-combo before the WKWebView sees the keydown** (`NSMenuItem` key equivalents — the same reason the web layer uses bare keys throughout, and why `⌘F` had to be reclaimed natively). A `⌘`-shortcut in `useKeyboardShortcuts.ts` works in the browser but is swallowed in the embedded app.

So: **web** registers bare `z` in `useKeyboardShortcuts.ts` (behind the existing `isEditing()` guard), passing through identically in browser and WKWebView; **native** binds `⌘⌥F` on the View ▸ Focus Mode item, dispatching `menuAction("focusMode")` over the bridge (mirrors `⌘F` → `menuAction("find")`). They need not match. The webview holds the state and reports back so the checkmark stays honest. The CLI gets **no `run` flag** — a flag mutating a downstream viewer's state is the `--static`/`--no-serve` conflation again; its only honest contribution is the boot default, a shared Settings key.

Why bare `z` for web (not `f`, not `⌘`-anything): no mainstream browser (Safari/Chrome/Edge/Firefox on Mac/Win/Linux) reserves a **bare letter** — they reserve modifier combos (`Cmd/Ctrl+[` back was the cautionary case), function keys, and Firefox's bare `/` + `'` type-ahead. A bare letter is therefore the only key that's free *and* behaves identically across OSes (no Cmd-vs-Ctrl divergence). `z` is free in the browsers and in our bound set (`? / [ ] \ m x h s t r j k`), is layout-robust (a letter fires regardless of AZERTY/Dvorak position — unlike backtick, a dead key on several EU layouts), sits out on the bottom-left rim clear of the typing flow, and carries a mild zen/quiet mnemonic. `⌘⌥F` is free natively (`⌘⌥S`/`⌘⌥L`/`⌘⌥T` are taken, `F` isn't) and menu-advertised, so it needn't be find-contested. Both easy to swap if they grate.

## Embedded seam — dissolved, not negotiated

**Rewritten 3 Aug 2026.** The first draft called this "the genuinely hard axis" and specified a mechanism: on toggle, the webview posts its resolved `--bn-colour-bg-focus` to native, which sets the `NSWindow` background to match. That is now both unnecessary and impossible to build honestly.

- **Unnecessary**, because recede-only never moves the ground, so there is nothing for the seam to fall out of step with.
- **Inverted**, because native already owns the ground (see above) — the webview has no resolved ground colour to post.
- **Against a standing decision**, because it would mean adding a colour channel to the bridge. The `set-appearance` message was *deleted* on 30 Jul 2026 for being consumed by nothing, with the note: *"Don't re-add a second channel for a fact the platform already carries"* ([`BridgeHandler.swift:259-264`](../desktop/Bristlenose/Bristlenose/BridgeHandler.swift)). Appearance rides `NSApp.appearance` → window → WKWebView → `prefers-color-scheme`, with no message at all.

So: **no bridge work for Focus.** The surviving geometry channel (`syncToolbarInset`) is untouched. The hardest section of the original design is now the shortest.

One consequence for the palette matrix: the desktop pins `BRISTLENOSE_COLOR_THEME = "default"`, so Edo is not reachable in the app. Any Edo tuning is browser/CLI work, not a desktop acceptance item.

## State & persistence

**Nothing is persisted, anywhere.** `FocusModeStore` is module state ([`FocusModeStore.ts:40`](../frontend/src/contexts/FocusModeStore.ts)) — it survives route changes within the report and resets on reload. Identical in serve, embedded and export; there is no storage layer and no seed.

That satisfies the rule this section was written to express: *remember the last choice while you're working, but a freshly-opened project boots in normal view* — Focus is a lean-in action, not a default state. Module state gives exactly that, and adding `localStorage` would break the boot half rather than improve on it.

- **Serve / export:** the store, and nothing else.
- **Embedded:** the same store; the native menu checkmark mirrors it via the `focus-mode` bridge message. Native holds no state of its own — `BridgeHandler.reset()` clears `focusModeActive` on project switch.

> **Corrected 3 Aug 2026.** This section previously described three mutually incompatible schemes in the space of three lines: a `localStorage`-seeded export, a `report.default_view` Settings key overriding the boot rule, and (further down, under § Decisions) no persistence at all. Only the last was ever built. The first two were pre-build design that survived the truing passes because each edit fixed the section it was looking at. **`report.default_view` does not exist** — no CLI key, no Settings entry, no reader. If the handoff/kiosk case turns out to be real, it's new work, not wiring-up.

## Phasing

Phases 0–2 ship the SPA + export together (visual, fast). Phase 3 is the native track (Apple-slow). The CLI piece was expected to ride Phase 1 and did not — nothing CLI-side shipped (see § State & persistence).

**Phases 0 and 3 both collapsed on 3 Aug 2026** — dropping the ground-deepen removed the contract token from one and the whole bridge extension from the other.

- **Phase 0 — knobs + CSS. ✅ Built.** Four global knobs in `tokens.css`; `bristlenose/theme/templates/focus-mode.css` registered in `_THEME_FILES` after `report.css`. No contract token, no palette file touched, zero colour literals — the transform is a formula over existing tokens throughout.
- **Phase 1 — SPA behaviour. ✅ Built.** `frontend/src/contexts/FocusModeStore.ts` (module store + `useSyncExternalStore`, matching SidebarStore) owns the state and the DOM class; toolbar moon button; bare `z`. Works in `serve` and export — the export inlines the theme CSS, so Focus rides along with no export-specific work.
- **Phase 2 — matrix hardening. ⬜ Outstanding.** Render palette × appearance × focus on the specimen lens; **tune `--bn-focus-ghost-opacity` against the prose** (see the note in § Token model — 0.14 may be below what "faint outline" promises); verify palette/appearance switches *while* in Focus don't jank. Browser/CLI only — Edo isn't reachable on desktop. This is a looking-at-it phase, not a coding one.
- **Phase 3 — native menu item. ✅ Built.** `View ▸ Focus Mode` (`⌘⌥F`) as a checkmarked `Toggle` in `ViewMenuContent`; `focusModeActive` mirrored from the SPA over a new `focus-mode` bridge message. No seam work, no colour channel.
- **Phase 4 — tests + this doc trued. ✅ Done.** `tests/test_focus_mode_css.py` (13 invariants), `frontend/src/contexts/FocusModeStore.test.ts` (4), and three `z`-key cases in `useKeyboardShortcuts.test.ts`.

### Decisions taken during the build

- **Two DOM hooks, not one.** `.bn-focus-ready` is added once when the SPA mounts and never removed; `.bn-focus-mode` is toggled. The transitions hang off `.bn-focus-ready` because a transition declared alongside the toggled class **disappears with it** — the fade would play going in and snap coming out, breaking the doc's own "symmetric on the way back". It also confines the transition overrides to SPA surfaces, so the static render is untouched by this file. Pinned by `test_transitions_hang_off_the_always_present_hook`.
- **Recede leaf elements, not containers that already animate.** `.quote-card .badges` carries an existing `opacity: 0.9 → 1` hover on `--bn-transition-fast`. Focus dims the same element but declares its own transition under `.bn-focus-ready`, so the two compose rather than one clobbering the other's timing.
- **Print always gets the full report.** A printout is a deliverable someone else reads; faded tags on paper are a defect, not a mode. `@media print` restores every receded value — same reasoning as `print.css` forcing the light colour-scheme.
- **Ephemeral state, no persistence** — see § State & persistence for the full reconciliation, including which of the three schemes this doc used to describe was the real one.
- **`z` needs two guards the sibling bare keys don't.** Modifiers (⌘Z is Undo — and the report has inline editing, where Undo is most wanted just *after* a commit, when `isEditing()` is already false and guards nothing) and route (see below). Both pinned in `useKeyboardShortcuts.test.ts`.

## Testing — invariants, not a 16-cell snapshot matrix

Three invariants carry it; don't screenshot every palette × appearance × context × state cell:

1. **Toggling changes no element geometry** across palettes — the zero-reflow guarantee. **NOT BUILT.** This was described as "asserted on bounding boxes" and Phase 4 was marked done over it; no such assertion exists in `tests/`, `e2e/` or `frontend/src`. The guarantee currently rests on construction (the CSS touches no layout property) and on review, not on a test. It is the doc's own headline invariant, so this is the most worthwhile gap in the suite — an e2e bounding-box comparison across a `z` toggle would close it.
2. **Signal elements retain full opacity/colour** and receded chrome drops to the ghost opacity, in every palette.
3. **Selection and keyboard focus survive Focus** — a card with `.bn-selected` keeps a visibly distinct background in Focus, in every palette. This is the specificity trap above, and it is the one failure that would otherwise ship looking fine: the mode renders correctly and only breaks when someone tries to multi-select.

Invariant 3 replaces the original "embedded seam colour equals the webview ground", which no longer has a referent — recede-only never moves the ground, and native owns it in the app regardless.

## Decisions

### Settled

- Name: **Focus Mode**. (Rejected: Nightfall — smuggles luminance; Reader — promises reflow.)
- Menu label: **bare `Focus Mode` with a checkmark** (SwiftUI `Toggle`, matching the pair above it). The checkmark carries the state, so the label is the thing rather than the act.
- Native shortcut: **`⌘⌥F`**, with the Find-and-Replace foreclosure below accepted as a known trade rather than overlooked. Cheap to revisit — it's a one-line change and nothing else depends on it.
- Ground: **recede-only in every appearance.** No `--bn-colour-bg-focus`, no palette edits.
- Embedded: **no seam work, no new bridge channel.**
- Stars: **untouched by Focus**, starred or not.
- Sidebars: **out of scope for v1.**
- Selection and keyboard focus: **stay live and visible.**
- Web shortcut: **bare `z`.** Re-verified 3 Aug 2026 against the bound set in `useKeyboardShortcuts.ts` (`? [ ] \ m / j k x h s t r Enter`, arrows, Escape, plus ⌘-combos and ⌃⇧P/⌃⇧U) — still free. (Rejected: `⌘\` — `\` is the sidebar family and native menus eat Cmd-combos before the WKWebView; bare `f` — find-contested; `⌘§` — ISO-only; backtick — a dead key on several EU layouts.)
- Report-wide only for v1; per-section Focus (a moon on the section header) deferred until it's demonstrably missed.

### How the label was chosen (and one precedent that didn't survive checking)

> **Correction, same day.** An earlier version of this section cited "Apple Mail ships a View-menu item called Focus Mode" as the decisive precedent. The **strings are genuinely in the shipped nib** — `strings -a /System/Applications/Mail.app/Contents/Resources/Base.lproj/MainMenu.nib` returns `Enable Focus Mode`, `Mail.menuBar.viewMenu.enableFocusMode`, `toggleFocusMode:`, and the menu also carries `moon.circle` — but **the item is not exposed in Mail's actual View menu**, as direct observation confirms. Unexposed or conditionally-gated nib items are ordinary; extracting a string is not evidence that a feature ships. Treat what follows as a signal about Apple's internal naming register, not as shipped precedent. The arguments that don't depend on Mail are marked below.

The three candidates:

| | Form | Standing |
|---|---|---|
| A | `Turn On Focus Mode` / `Turn Off Focus Mode` | Matches our shipped `Turn On/Off Agent Access`, so the register is already translated across 20 locales. But Apple uses `Turn On X` for capabilities, not view states — across `/System/Applications` the only instance is Photos' "Turn On Live Photo". Argument against reuse: `Turn On/Off` is currently a meaningful signal in this app for *permissions that keep working while you are not looking*; spending it on a display state dilutes it. |
| B | `Enter Focus Mode` / `Exit Focus Mode` | **Rejected.** Enter/Exit is the environment-replacement idiom — *independent of Mail*, a sweep of ~18 Apple apps returns only Enter/Exit Full Screen and Enter Time Machine as modes; everything else (`Enter Password`, `Enter Link`, `Enter Selection`) isn't a mode at all. It means the OS or app environment is replaced and you must explicitly leave it: Full Screen removes the menu bar, Time Machine replaces the desktop. Focus touches four CSS properties and guarantees zero reflow — it would borrow the vocabulary's strongest connotation for its weakest change. |
| C | `Focus Mode` + checkmark | **Chosen.** Matches the two items directly above; the checkmark carries the state so the label can be the thing rather than the act. |

One finding worth keeping so nobody re-derives it:

**`Enable/Disable` is not Windows-ish — that earlier rejection was overturned.** It's a real, current, small Apple register: `Enable Message Filter` in Mail, `Enable Messages in iCloud` in Messages, and iA Writer's own docs word ⌘D as "Enable or disable Focus Mode." (None of those depend on the unexposed Mail item.) The reason not to take it is narrower than "it's Windowsy": `✓ Enable Focus Mode` reads as a contradiction, Apple's `Enable` cluster is a *set-up* register — configure once per account — whereas ours is a lean-in flip you might do twenty times a session, and our View menu already has a bare-attribute register to join (`All Quotes`, `Starred Quotes Only`) and no `Enable` register.

**Shortcut — `⌘⌥F` chosen; the risk below is accepted, not overlooked.**

Constraints confirmed: `⌘F` is routed to the report search bar, `⌃⌘F` is the system Enter Full Screen, `⇧⌘F` is find-in-project in most editors. There is **no cross-app convention to honour** — iA Writer uses `⌘D` (root of a deliberate D-for-display family: `⌘D` Focus, `⇧⌘D` Syntax Highlight, `⌥⇧⌘D` Style Checking), Ulysses uses `⌥⌘T` for Typewriter Mode, and Apple's own Mail Focus Mode item had no extractable key equivalent. The space is genuinely free.

The live risk is **foreclosure, not contention**: `⌘⌥F` is the canonical Find and Replace binding (Pages, Numbers, Keynote, Xcode, BBEdit, Nova; Safari uses it to focus the search field), and our Edit menu already ships the complete `NSTextFinder` cluster *minus that one member* — `⌘F`, `⌘G`, `⇧⌘G`, `⌘E`, `⌘J` at [`MenuCommands.swift:471-493`](../desktop/Bristlenose/Bristlenose/MenuCommands.swift). Find and Replace is plausible here rather than hypothetical: the report has inline editing of quote text, headings and participant names, and hand-anonymising a client name across forty quotes is exactly the job. Taking `⌘⌥F` forecloses it.

Accepted on the grounds that Find and Replace is a *possible* future rather than a planned one, and that reassigning the shortcut later is a one-line change with nothing depending on it. If it's ever wanted, the fallbacks already assessed are `⌘⌥Z` (rhymes with the web layer's bare `z` — one letter across both surfaces; keeps the `⌘⌥` family reading as view toggles, S/L/T/Z; unbound) or no key equivalent at all (matching `All Quotes` / `Starred Quotes Only`, which have none — but that loses the ability to toggle while focus is in the native sidebar, which is a real job).

Ergonomics were checked by hand: `⌃⌘F` (Enter Full Screen) followed by `⌘⌥F` is a workable sequence — pinky plus first and second finger for `⌘⌥`, right middle finger for `F` both times.

**Shortcut research — there is no cross-app convention to honour.** iA Writer uses `⌘D`, the root of a deliberate D-for-display family (`⌘D` Focus, `⇧⌘D` Syntax Highlight, `⌥⇧⌘D` Style Checking). Ulysses uses `⌥⌘T` for Typewriter Mode. Three apps, three unrelated answers, so the space is genuinely free and the choice rests on internal consistency and foreclosure rather than on matching anyone.

**Lens scoping — built quotes-only, provisionally.** Focus's entire signal/noise vocabulary is quote-card vocabulary, so all three affordances are scoped to the Quotes lens and agree with each other: the menu item is `.disabled(activeTab != .quotes)` matching its neighbours, `z` is route-guarded to `/report/quotes` the way `m` is to `/report/analysis`, and the toolbar mounts only in `QuotesTab` so the moon button can't appear elsewhere. All three had to move together — a menu that says "unavailable" while the key still works is worse than either behaviour alone.

Provisional because it's the honest v1, not necessarily the right end state: a live-but-inert menu item is a lie, whereas un-dimming later, once the other lenses have a defined transform, is a free upgrade. Worth revisiting after using it — if reaching for `z` on Sessions or Analysis feels like it *should* work, that's the signal to define the transform there rather than to un-dim an empty one.

## Changelog draft — SHIPPED, kept as a delta record

**The live entry is `CHANGELOG.md` under 0.24.0 (3 Aug 2026).** That is the text users read; this draft is history.

> **Corrected 3 Aug 2026.** This section said "Not in the changelog now because the feature is unbuilt" *below* a truing note added the same day — the note fixed the star and ground promises in the draft body and left the "unbuilt" framing standing above it. Classic patched-but-aspirational: anyone following a pointer here and reading the fresh-looking banner would have passed it. It also gated release on "once Phase 0–2 actually land"; Phase 2 never landed and it shipped regardless, which was the right call (Phase 2 is tuning, not function) but makes the gate counterfactual.

Two differences worth keeping, because they show what the draft got wrong before contact with the shipped feature:

- The draft omitted the **Quotes-lens-only** scope. The shipped entry carries it. A changelog promising a report-wide mode for a quotes-scoped one is exactly the over-promise the no-promises rule exists to prevent — and the draft would have shipped it.
- The draft still described stars dimming and the ground deepening, both reversed during the build.

Kept below verbatim as the pre-ship state. **Do not paste it anywhere** — `CHANGELOG.md` is the source of truth.

Trued 3 Aug 2026 — the original draft promised darkened stars and a deepened desktop ground, neither of which the feature now does.

> **Focus Mode — quiet everything but the quotes.** A new reading state for the report. Press `z` — or the moon button in the toolbar, or View ▸ Focus Mode (`⌘⌥F`) in the desktop app — and the chrome recedes: tag chips, sentiment badges, timecodes, the card boxes themselves all sink to a faint outline, leaving just the quote, the speaker code, and your stars. Nothing moves. The toggle only fades opacity and colour, never layout, so the quote under your eye stays pinned to the pixel while everything around it drops away — you keep your bearings, the target just becomes unmistakable. Starring, selecting and tagging all keep working, so it's a reading state you can act from, not just look at: quiet the page, read the words, mark what matters. It's a *mode*, not a theme — it composes with Default and Edo, light and dark, and never touches the page's ground colour. Dusk, not a light-switch: a ~320 ms fade that respects Reduce Motion. Ships on PyPI and in the desktop app.

