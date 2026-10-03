# The toolbar's AppKit move — what SwiftUI's toolbar cannot do, measured

**Status:** Parked, banked. Written 3 Oct 2026 at the end of a day that re-derived most of this the hard way; the point of the file is that the next person does not. Read this **before** touching toolbar search, toolbar overflow, or the `NSToolbar` migration — the 100days item that points here.
**Extends:** `docs/design-desktop-nav-toolbar-rearrangement.md` §4.3–4.4 (what shipped and why) · `docs/sidebar-column-diagnosis.md` § Session 4 option F (the migration, costed) · `desktop/CLAUDE.md` gotchas (`.searchable` column minimum; `ToolbarItem` priority)
**Mockup:** `docs/mockups/desktop-toolbar-and-footer-options.html` (decision record, rows 1–4)

---

## TL;DR

We wanted what Photos and NetNewsWire do when the toolbar is tight: the search field stays, the tools fold into `»`, the chevron sits *before* the magnifier, and an empty search collapses to a button that expands in place. **All four are properties of AppKit's `NSSearchToolbarItem` inside an `NSToolbar`.** Both apps are AppKit toolbars (verified below). SwiftUI's `.toolbar` reaches that item only via `.searchable`, and `.searchable` on our detail column **gives the column a minimum width the window can violate** (measured; the fit-to-width model's one forbidden thing). Everything else SwiftUI offers was tried the same day and is listed here with its measurement.

**The owner's verdict, 3 Oct 2026, recorded so the next session starts from it rather than re-earning it:** if the tentpole Mac apps and the best of the indies are not using SwiftUI's toolbar, the toolbar is not fit for a Mac app. Its `leading`/`trailing`/`.status` placements are a smart layout model for iPhone, iPad and the folding duo, clearly planned years ahead; the Mac implementation is not taken seriously (no item priority, no `NSSearchToolbarItem`, a search modifier that pins a split-view column). The move to `NSToolbar` is the right fix and **too much to implement now** — the research audience is better served by moderators and a first discussion lens. Banked here, with a 100days item.

**What ships instead** (commit `e7eed916`, 3 Oct 2026): the hand-rolled control in its own toolbar item, and a runtime probe that sets its `NSToolbarItem.visibilityPriority` to `.user`. It gets three of the four properties. The fourth — the chevron's position — needs the `NSToolbar` move. The owner's call: ship other features, bank this.

## What we wanted, property by property

| # | Photos / NetNewsWire behaviour | SwiftUI toolbar, as shipped | Gap |
|---|---|---|---|
| 1 | Search is the trailing item in its own glass | Yes — `ToolbarSpacer(.fixed)` on 26+, own `ToolbarItem` | none |
| 2 | When tight, the tools fold to `»` and the open field stays | Yes — `ToolbarItemPriority(.user)` probe | none |
| 3 | The chevron sits before the magnifier | **No** — `»` is drawn at the trailing edge; search sits to its left | AppKit special-cases `NSSearchToolbarItem` |
| 4 | An empty field collapses to a button and expands in place | Yes, hand-rolled (`expanded` state in `QuotesSearchToolbarControl`) | none, but it is our code, not the system's |

## Measurements, dated 3 Oct 2026, macOS 27, this Mac

### A. `.searchable` on the detail column → a column minimum the window can violate — REJECTED

Spike: `Color.clear.searchable(text:placement: .toolbar).searchFocused(...)` in a `.background` on `detail` (type-stable; the WKWebView was never remounted — `makeNSView` ×1 across five lens switches). It placed the field correctly, compiled at the 15.0 floor — and the detail column acquired a hard minimum of **938 pt**, the window's width at the moment `SidebarAutoCollapse` hid the projects column. `NSSplitView` then laid out sidebar 200 + detail 938 inside a 941-pt window and overflowed left: projects column off the window's edge, sidebar toggle gone, a blank band left of the lens rail once the window was wide again.

Trace (`-BristlenoseDebugSidebarFit YES`): `webW=938` on every line while `frameW` went 941 → 1138. `main` (`5bdb041e`) at the same widths: `webW` tracked the window. Full record: review log Finding 33/47; `desktop/CLAUDE.md` "`.searchable` on the detail column is a column minimum you never wrote".

**Do not retry this on the detail column.** If a native field is ever wanted, it is the `NSToolbar` move below, not `.searchable`.

### B. `ToolbarItem` has no priority; the trailing item folds first — WORKED AROUND

Apple, `NSToolbarItem.visibilityPriority` (read via the docs JSON feed, see § Tools): *"When a toolbar doesn't have enough space to fit all of its items, it pushes lower-priority items to the overflow menu first. When two or more items have the same priority, the toolbar removes them one at a time starting from the trailing edge."* `.high`: *"less likely … The toolbar moves items with [standard] priority to the overflow menu before it moves items with this priority."* `.user`: *"The highest priority for items in the toolbar. The toolbar pushes these items to the overflow menu last."*

SwiftUI sets every `ToolbarItem` to `.standard` and exposes nothing. So search, the trailing item, folded first — the screenshot that started the day.

Workaround that ships: `ToolbarItemPriority` (`QuotesToolbarControls.swift`), a zero-size `NSViewRepresentable` in the control's `.background`. On `viewDidMoveToWindow` (one main-queue hop later — the item list is populated after the view lands), it walks `window.toolbar.items`, finds the item whose `view` contains it, and sets `.user`. **Re-applied on `NSWindow.didResizeNotification` and `didEndLiveResizeNotification`** and on every SwiftUI update: a lens switch rebuilds the item and the priority was measured lost without this (the "search vanished, lozenge intact" screenshot). `.high` was tried first; `.user` is the documented top.

Verify with the toolbar trace line (`SidebarFitTrace.noteToolbar`, same flag): `… -46C1-458F-8479-79DDF2FAC4F5 p=2000 on x=412 w=194` — `p=2000` is `.user`, `on` means on the bar not in `»`. The sidebar toggle reads `p=1000` and SwiftUI's own `splitViewSeparator` `p=2000`; every lozenge item `p=0`.

### C. The chevron's position — NOT ACHIEVABLE in SwiftUI

AppKit draws `»` at the trailing edge of the toolbar. Photos and NetNewsWire show the magnifier *after* it because `NSSearchToolbarItem` is placed there by AppKit itself. No SwiftUI item gets that; it is the item class, not a property.

### D. `.status` placement — REJECTED

Tried as a guess that the zone might land after the chevron. On macOS 26 `.status` is the toolbar's **centre**; when tight it folds into `»` like anything else, and a magnifier inside a menu is inoperable. (The house rule already reserves `.status` for ambient state — Ollama download, out-of-credit, alpha expiry — so it was a misuse even if it had worked.)

### E. A width threshold that swaps the item for a magnifier + popover — REJECTED

Built and measured: a per-lens threshold (560 + 40 per action item) rendered the control as a magnifier below it, with the field in a popover. Two faults: it flipped too early on lenses with one action (Sessions, ~650 pt of detail, the field would have fit), and the owner's rule — popovers are not the idiom; Photos never resorts to one. Replaced by B.

### F. `searchToolbarBehavior(.minimize)` — NOT APPLICABLE

Apple's text (same feed): *"Configures the behavior for search in the toolbar… On iPhone, the search field in the bottom toolbar can be configured to appear as a button-like control when inactive."* `.minimize`: *"prefers rendering a search field as a button-like control. The search field is expanded when interacted with."* It is written around the iPhone's bottom bar, needs `.searchable` (A), and is macOS 26 only. Not a Mac answer.

### G. The sidebar `+⌄` — unaffected

`ToolbarItem(placement: .automatic)` with a `Menu`, on the sidebar column in `ContentView.splitViewCore` and built only while the sidebar is visible (c5c2a24d, c2630892). It was first put on `projectList`, the New Folder button's old slot, and did not show: that view is not rendered on the AppKit sidebar path. None of the above applies: it goes away with the column, and the column has no overflow problem.

## How Photos and NetNewsWire actually do it — verified, not inferred

- **NetNewsWire** (MIT, `Ranchero-Software/NetNewsWire`, `main`): the Mac app is AppKit throughout. `Mac/MainWindow/MainWindowController.swift` is an `NSWindowController` and `NSToolbarDelegate`; line **960** `let toolbarItem = NSSearchToolbarItem(itemIdentifier: .search)` with only a `toolTip` and `label` — nothing else set; line **1030** `toolbarWillAddItem` wires `searchItem.searchField.delegate/target/action`; line **906** `NSToolbarItem(itemIdentifier: .timelineTrackingSeparator)` — an `NSTrackingSeparatorToolbarItem` tying the toolbar sections to its split view. `moveFocusToSearchField` (597–606) is `window.makeFirstResponder(searchField)`.
- **Photos** (`/System/Applications/Photos.app`, macOS 27, binary dated 3 Sep): `nm -u` on the main executable lists `_OBJC_CLASS_$_NSSearchToolbarItem`, `_OBJC_CLASS_$_NSToolbar`, `_OBJC_CLASS_$_NSToolbarItem`, `_OBJC_CLASS_$_NSToolbarItemGroup`, `_OBJC_CLASS_$_NSSearchField`. It links SwiftUI too (`otool -L`), but its toolbar classes are AppKit's.
- **Apple's own description of the item**, `NSSearchToolbarItem` abstract: *"automatically resizes to accommodate typing when the focus switches to the toolbar item. When the toolbar is low on space, the system may collapse the search item into a button representation, which then expands to a full search field when the user clicks on it."* That sentence is properties 3 and 4 above, for free.

Nothing here is "stealing": these are public AppKit APIs and an MIT source. What it costs is owning the toolbar.

## The move, when it is made

**What it buys:** `NSSearchToolbarItem` (properties 3 and 4 as system behaviour; no probe, no hand-rolled expand/collapse); `visibilityPriority` on every item as a plain property; `NSTrackingSeparatorToolbarItem` so the toolbar sections follow the split's columns; and, per `docs/sidebar-column-diagnosis.md` option F, the window's minimum following the split's minimums automatically — the property whose absence in SwiftUI produced the 20 Sep overflow and forced `DetailFloor`'s "declare no minimum, decide ourselves" design.

**What it costs (from option F, still current):** the whole `.toolbar` in `ContentView` rehomed — leading: sidebar toggle (system), list toggle / sessions switcher, back/forward `ControlGroup`, title + subtitle (become `window.title`/`subtitle`, simpler); trailing: Export popover, Starred toggle, Tags, Library, Heatmap, search; the three `.status` pills with `withoutSharedBackground()`; the sidebar's `+⌄` `Menu`. `focusedSceneValue` plumbing through hosting views (should hold, unmeasured). The `SidebarFitHarnessTests` / `SidebarFitSPAHarnessTests` rewritten against an `NSSplitViewController`. The "keep `.toolbar` on child columns" rule (June Finding 27) becomes moot.

**Two things unmeasured, which decide whether the move is worth it** (option F's own list): (1) does AppKit re-expand a resize-collapsed sidebar item when the window widens, or leave that to the app as Mail may — if the app must, `SidebarAutoCollapse`'s ownership rules survive the migration; (2) does a `minimumThickness` change *without* a resize (a panel opening) collapse the sidebar in AppKit, or overflow as SwiftUI did. Both are a 30-line spike in the existing test host (`SidebarFitHarnessView`), and should run **before** choosing the move.

**Acceptance for the move:** the fit-to-width guard in full (`docs/design-sidebar-playground.md` § Fit to width; the plan's six checks) **and** properties 1–4 above at wide, tight and minimum widths, on macOS 15 and 26+.

## What ships meanwhile, and what to leave alone

- `QuotesSearchToolbarControl` — own `.primaryAction` item after `searchSeparator` (`ToolbarSpacer(.fixed)`, 26+), no fill of its own, clear button always laid out (the first-character width jump), shown on Quotes/Sessions/Codebook/Signals and inert off Quotes, push decision in `QuotesSearchPush.shouldPush` (tested).
- `ToolbarItemPriority(.user)` — leave the re-apply hooks in; they are why the priority survives a lens switch.
- `SidebarFitTrace.noteToolbar` — the per-item line; costs nothing when the flag is off.
- Do not add a width threshold, a popover, a `.status` placement, or `.searchable` back. Each is in this file with its measurement.

## Tools that made the measurements (reusable)

- **Apple's docs as JSON** — the HTML pages render client-side and fetch as a title only. The same content is at `https://developer.apple.com/tutorials/data/documentation/<framework>/<path>.json` (e.g. `appkit/nstoolbaritem/visibilitypriority-swift.property.json`, `swiftui/searchtoolbarbehavior/minimize.json`); walk the JSON for `"type": "text"` nodes.
- **Which classes a system app uses** — `nm -u <binary> | grep -F 'OBJC_CLASS_$_NS…'`; `otool -L` for frameworks. No disassembler needed.
- **The toolbar trace** — launch with `-BristlenoseDebugSidebarFit YES` and read `/usr/bin/log show --predicate 'subsystem == "app.bristlenose" AND category == "sidebar-fit"'`; the `toolbar |` line lists every item's priority, on/`»`, and frame. The `split/detail/webW` lines are the fit-to-width guard.
- **A trap that cost a cycle:** `for path in …` in the Bash tool's zsh clobbers `PATH` (`path` is the array behind it) — every command "not found". Name the variable anything else.
