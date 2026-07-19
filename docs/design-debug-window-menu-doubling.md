# Menu-structure audit — debug windows doubled into the Window menu

_19 Jul 2026 · desktop macOS shell · analysis + proposed fix + doc reconciliation_

> **Status: fixes applied (19 Jul 2026).** Issues 1, 2, 5 and the keybinding
> decision (issue 7) are landed:
> - `.commandsRemoved()` on all four debug `Window` scenes
>   (`BristlenoseApp.swift`) — stops the Window-menu doubling.
> - Ellipses dropped from the open-window Debug items + "Open Admin Panel"
>   (`MenuCommands.swift`).
> - `⌃⌘T` removed from Type Parity; **Run Inspector keeps `⌃⌘R` as the sole
>   diagnostics-window shortcut** (it's the only one that ships to users).
> - Rule recorded for robots (`desktop/CLAUDE.md`) and humans
>   (`docs/design-keyboard-shortcuts.md` § "Diagnostics windows";
>   `docs/design-diagnostics-menu.md` § "Menu-item mechanics" + Phase 1/2).
> - Website (`bristlenose-website/docs-src/keyboard-shortcuts.md`) lists `⌃⌘R`
>   as a macOS-only shortcut — **hold the deploy** until Run Inspector actually
>   ships to users (DEBUG-only today; see issue 3 / the diagnostics-menu plan).
>
> Issues 3, 6, 8 remain as forward follow-ups on the diagnostics-menu plan.
> Needs a Cmd+R build to visually confirm the Window menu is clean.

## TL;DR

The four items in your screenshot — **Type Parity Inspector**, **Run Inspector**,
**Shoal Screensaver**, **Shimmer Tuner** — appear in the **Window menu** because
SwiftUI **auto-injects a Window-menu entry for every titled `Window` scene**. They
*also* appear in the channel-gated **Debug menu**, where they belong. So each is
listed twice. Your instinct is right: none of them belong in the Window menu. But
the doubling is not a hand-authored mistake in the Debug menu — it's an
**unsuppressed SwiftUI default** on the `Window` scene declarations. The newest one
(Shimmer Tuner, still uncommitted in your working tree) just followed the same
pattern and doubled the same way.

**Fix:** add `.commandsRemoved()` to each debug `Window` scene. One line per scene.
**Systemic fix:** write the rule down — the diagnostics-menu redesign is about to
ship non-DEBUG `Window` scenes (Run Inspector, Shoal animation) to **every channel
including App Store**, and without the rule those will leak stray Window-menu
entries to end users.

---

## 1. How the doubling happens (mechanism)

`desktop/Bristlenose/Bristlenose/BristlenoseApp.swift:138-172` declares four
auxiliary windows, all inside `#if DEBUG`:

```swift
Window("Type Parity Inspector", id: "type-parity") { TypeParityView() … }
Window("Run Inspector",         id: "run-inspector") { RunInspectorView() … }
Window("Shoal Screensaver",     id: "shoal") { ShoalDebugView() … }
Window("Shimmer Tuner",         id: "shimmer-tuner") { ShimmerTunerView() … }   // ← new, uncommitted
```

SwiftUI's default behaviour: **any titled, single `Window` scene contributes an
"open this window" command to the standard Window menu** (the same machinery that
lets you reopen a closed auxiliary window). Nothing suppresses it, so all four land
in the Window menu as plain titles.

Separately and deliberately, `MenuCommands.swift:114-175` (`DebugMenuContent`,
`#if DEBUG`) hand-writes buttons that open the same scenes by id:

```swift
Button("Type Parity Inspector…") { openWindow(id: "type-parity") }
    .keyboardShortcut("t", modifiers: [.command, .control])
Button("Run Inspector…")         { openWindow(id: "run-inspector") }
    .keyboardShortcut("r", modifiers: [.command, .control])
Button("Shoal Screensaver…")     { openWindow(id: "shoal") }
Button("Shimmer Tuner…")         { openWindow(id: "shimmer-tuner") }
```

**The screenshot tell** confirms which is which: the Window-menu copies have **no
ellipsis and no shortcut** (SwiftUI-generated), while the Debug-menu copies have
**"…" + ⌃⌘T / ⌃⌘R** (hand-authored). Two independent surfaces, same four scenes.

### Why it "doubled up"
It was never a one-off slip. Using a titled `Window` scene for a debug window
*always* produces a Window-menu entry unless you opt out. The Debug-menu buttons
were added to give the windows a discoverable, channel-gated home with shortcuts —
but the auto-injected Window-menu twins were never suppressed. This is a
**pre-existing structural artefact** dating to whenever the first debug `Window`
scene was added; the current Shimmer Tuner WIP simply added the fourth instance of
it. (Note: because the scenes are `#if DEBUG`, the duplicates exist only in Debug
builds today — see §4 for why that stops being true soon.)

---

## 2. Which users / distros get which tools (per the canonical docs)

Two docs govern this. The audience-sort is authoritative:
`docs/design-diagnostics-menu.md` (14 Jul 2026) buckets every debug affordance by
**who it's for**, with a gate per tier:

| Tier | Audience | Gate | Ships to |
|---|---|---|---|
| **A — Always-on** | user | none | every channel |
| **U — User diagnostics** | user | `showDiagnosticsMenu` pref (off by default) | every channel |
| **V — Developer tools** | developer | `DistributionChannel.exposesDebugTools` | Developer-ID `.dmg` beta + local DEBUG only — **never** App Store/TestFlight |
| **D — Developer magic** | nobody | `#if DEBUG` / build-time env | dev machines only |

Where our four items land in that scheme:

| Item | Doc verdict | Tier | Ships? |
|---|---|---|---|
| **Type Parity Inspector** | "Internal typography QA" | **D** | Never |
| **Shimmer Tuner** | _(newer than the doc — not listed)_ but same shape: animation/typography QA harness mirroring a mockup | **D** (by analogy) | Never |
| **Shoal Screensaver** | The `shoal` window today = `ShoalDebugView` (tuning sliders + FPS probe) → **tuning is Tier V**. The bare *animation* is a **planned new Tier-U** `shoal-view` scene | **V today** (tuning); U later (animation) | Beta+dev today |
| **Run Inspector** | "understand your run" tool → **Tier U, Section 1, ships to everyone** (endpoints are `/api/`-token-authed, read-only) | **U** | Every channel (planned) |

**Channel gate** (`DistributionChannel.swift`): `exposesDebugTools` is `true` for
`.debug` (local Xcode) and `.developerID` (the direct-notarised `.dmg` beta),
`false` for `.appStoreOrTestFlight`. It's a **compile-time** flag
(`DEVELOPER_ID_BETA` in `SWIFT_ACTIVE_COMPILATION_CONDITIONS`), fail-closed by
construction — App Store and TestFlight are byte-identical and never expose.

**None of the four belong in the Window menu under any of these tiers.** The Window
menu is for the user's real windows.

---

## 3. Target design vs. today

`design-diagnostics-menu.md` specifies **one** `CommandMenu("Diagnostics")`, shown
only when a `showDiagnosticsMenu` preference (Appearance tab, off by default) is on,
with three **compounding** sections inside the single menu:

- **Section 1** (always): Run Inspector, Reveal `.bristlenose/`, Open Log, Copy
  Provenance, Shoal animation.
- **Section 2** (`exposesDebugTools`): Open Admin Panel (SQL), Shoal tuning, `/info`.
- **Section 3** (`#if DEBUG`): the current harness — Type Parity, fixtures, Ollama
  pill (and Shimmer Tuner would slot here).

The standalone `#if DEBUG CommandMenu("Debug")` is explicitly slated for **deletion**
(folded in as Section 3). So the current Debug menu is transitional. Today's state
(committed 14 Jul) is the admin-panel `BetaDebugMenuContent` step; the single
Diagnostics menu is **planned, not built**.

**Reconciliation:** your ask ("all of these belong in the Debug menu") matches the
plan's direction — but the deeper point is that the *Window-menu appearance is an
unintended SwiftUI auto-injection independent of whichever debug menu exists*. It
persists regardless of Debug→Diagnostics renaming. It has to be fixed at the
**scene** declaration, not the menu.

---

## 4. Why this is a latent *shipping* defect, not just dev cosmetics

Today the four scenes are `#if DEBUG`, so their Window-menu twins exist only in Debug
builds. **The diagnostics-menu plan changes that.** Phase 1–2 move:

- **Run Inspector** → a **non-DEBUG** `Window` scene (Tier U, Section 1, **ships to
  every channel including App Store**).
- **Shoal animation** → a **new non-DEBUG** `shoal-view` `Window` scene (Tier U,
  ships to TestFlight for hardware feedback).

If those ship as titled `Window` scenes **without** suppressing the auto-injection,
**App Store / TestFlight users will see stray "Run Inspector" / "Shoal" entries in
their Window menu** — reachable even with the Diagnostics pref *off*, because the
Window-menu entry is a property of the *scene*, not the pref-gated menu. That's a
review-surface and polish defect on the shipping build. Fixing the pattern now (and
writing the rule) closes it before it ships.

---

## 5. Canonical rules for macOS menu management — current state + the gap

**What's already written down:**
- `MenuCommands.swift:16` — canonical menu order: _Bristlenose · File · Edit · View
  · Project · Codes · Quotes · Video · Window · Help_.
- `MenuCommands.swift` doc-comment + `desktop/CLAUDE.md` "Menu bar" — the
  `View`-inside-`Commands` pattern (`@ObservedObject` unreliable directly in
  `Commands.body`); dim-never-hide contextual items; responder-chain rules (don't
  touch `.pasteboard`; Undo/Redo hidden during `isEditing`); no bare-key shortcuts.
- `CLAUDE.md` gotcha — `CommandsBuilder` caps at **10** top-level elements
  (why the four custom menus are grouped into `CustomMenus`).
- `design-diagnostics-menu.md` — the audience-tier model + one-Diagnostics-menu
  structure + HIG "menu items are commands only, no instructional rows".

**The gap (this is the systematic hole):** **nothing documents that a titled
`Window` scene auto-populates the Window menu, or that debug/auxiliary window scenes
must opt out with `.commandsRemoved()`.** Every future debug `Window` scene will
re-introduce the doubling — exactly as Shimmer Tuner just did. Per the
"systematise at the enforcement altitude" principle, the durable fix is a written
rule (gotcha in `desktop/CLAUDE.md`), not just patching the four instances.

---

## 6. Proposed fix

**A. Immediate (stops the doubling):** append `.commandsRemoved()` to each debug
`Window` scene in `BristlenoseApp.swift`. This strips the SwiftUI-auto-generated
Window-menu command; the scene stays openable via the Debug menu's `openWindow(id:)`
buttons (programmatic open is unaffected by `.commandsRemoved()`).

```swift
Window("Type Parity Inspector", id: "type-parity") { … }
    .defaultSize(width: 1200, height: 820)
    .commandsRemoved()          // ← suppress auto Window-menu entry
```

…and the same on `run-inspector`, `shoal`, `shimmer-tuner`.

**B. Systemic (prevents recurrence):** add a `desktop/CLAUDE.md` gotcha:
> _A titled `Window`/`WindowGroup` scene auto-injects an entry into the standard
> Window menu. Debug/auxiliary/diagnostic windows opened from their own menu must
> append `.commandsRemoved()` to the scene, or they double up (Window menu +
> their own menu). This matters for shipping Tier-U windows (Run Inspector, Shoal
> animation) too — without it the entry ships to App Store users._

**C. Forward (bake into the diagnostics-menu build):** the Phase-1/2 non-DEBUG
`shoal-view` and promoted `run-inspector` scenes must carry `.commandsRemoved()`
from the moment they leave `#if DEBUG`. Add it to the plan's acceptance checklist.

**Out of scope / not touched:** the `Window > Bristlenose` reopen item
(`ShowMainWindowMenuContent`, `MenuCommands.swift:64`) is correct — that's the
*main* window, which genuinely belongs in the Window menu.

---

## 7. Issues to address (ranked — Gruber's crit folded in)

1. **[HIGH · fix] Suppress the four auto Window-menu entries** — `.commandsRemoved()`
   on each debug `Window` scene (BristlenoseApp.swift:141/150/159/167). ~4 lines.
   Gruber: this is the documented single-purpose seam; `.windowResizability` /
   `MenuBarExtra` / hand-rolled `NSWindow` are all wrong. Ship it.
2. **[HIGH · rule] Make `.commandsRemoved()` a standing rule for diagnostics windows**
   — document the `Window`-scene → Window-menu auto-injection in `desktop/CLAUDE.md`
   AND add the line-item to `design-diagnostics-menu.md` Phase 1 + Phase 2. The auto
   entry exists whenever the scene is *declared* — NOT gated by the scene being open,
   NOT gated by the `showDiagnosticsMenu` pref (the pref gates the `CommandMenu`, not
   the scene). Enforcement-altitude fix.
3. **[HIGH · shipping risk] Guard the diagnostics-menu redesign** — Run Inspector +
   Shoal animation move to non-DEBUG `Window` scenes reaching App Store/TestFlight;
   without `.commandsRemoved()` they ship stray Window-menu rows **even with the
   Diagnostics toggle OFF**. Reviewer-visible. Bake into the Phase-1/2 checklist.
4. **[MEDIUM · confirmed] The doubling is a genuine native-idiom offence** — Window
   menu = the user's open/singleton windows (your `Window > Bristlenose` reopen is the
   *correct* use of that category); debug tool windows belong in a dedicated
   functional menu (Safari _Develop_ / Xcode _Debug_). #1 makes it the sole home.
5. **[LOW · free while you're in here] Drop the ellipses** from the open-window Debug
   items ("Type Parity Inspector…" etc.) AND "Open Admin Panel…" — an ellipsis means
   "needs more input before it completes"; opening a window that *is* the thing takes
   none (cf. "Show Fonts", Xcode "Devices and Simulators"). The hand-written buttons
   added the "…" by hand and got it wrong; the auto entries correctly have none.
6. **[hygiene] Shimmer Tuner is uncommitted WIP** — classify Tier D (same as Type
   Parity); confirm `#if DEBUG` + `.commandsRemoved()` when committed.
7. **[LOW · defer] Re-examine `⌃⌘R` / `⌃⌘T`** when Run Inspector ships to users —
   Control-modified shortcuts break the Cmd > Shift > Option > Control ladder; harmless
   while DEBUG-only, but `⌃⌘R` rides into a user-reachable surface at promotion. A
   user-facing "understand your run" tool arguably wants no default shortcut. Phase-2.
8. **[LOW · future] Utility-panel styling** if the Shimmer/Shoal *tuner* windows are
   ever promoted to testers — an inspector reads more native as a non-activating
   `NSPanel` than a peer `Window`. Not now.

### Gruber's verdict on naming / tier model (Shape B — no action)
"Diagnostics" is the parsimonious, least-alarming, Apple-register word (cf. Wireless
Diagnostics.app) — better than "Debug"/"Develop" for a researcher audience. The
apparent register clash (safe word over a raw PII/SQL browser) is already dissolved
by the audience gating: Section 2 is `exposesDebugTools`-gated *inside* the menu, so
a user or App Store reviewer who flips the toggle never sees it. The three-tier
compound is more machinery than a flat menu, but every gate already exists — composing
primitives, not inventing them. No taste objection.

---

_Appendix — files touched by this analysis:_
`desktop/Bristlenose/Bristlenose/BristlenoseApp.swift`,
`desktop/Bristlenose/Bristlenose/MenuCommands.swift`,
`desktop/Bristlenose/Bristlenose/DistributionChannel.swift`,
`docs/design-diagnostics-menu.md`,
`docs/design-desktop-debug-admin-panel.md`.
