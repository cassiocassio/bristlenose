---
status: open
date: 25 Sep 2026
area: desktop — projects column (NavigationSplitView) + report web view
---

# The projects column and the report beside it — diagnosis

A brief for other sessions: **confirm or refute this diagnosis, and propose
fixes against it.** Nothing below the "Open" heading has been fixed. The
measurements are all from **macOS 27** (this Mac is Darwin 27) — the app ships
a **15.0** floor, and nothing here has run on 15 or 26.

Code: `ContentView.splitViewCore` (the split view and its two geometry
readers), `DetailFloor.swift` (`SidebarAutoCollapse`), the report pane
(`ContentView`, `case .running(let port):` → `WebView`), the SPA's fit cascade
(`frontend/src/contexts/SidebarStore.ts`, `fitPanels` / `wantedWidth`;
`SidebarLayout.tsx` → `setLayoutContext`). Model and history:
`docs/design-sidebar-playground.md` § Fit to width.

## The model in one paragraph

Native owns the window width and the projects column; the web owns its own
panels. The column collapses on **window resize only**, when window − column
would leave the report below `minWidth` (content floor + the panels the
researcher *wants* + minimap, posted by the SPA over `panel-state`), and comes
back when it fits — but only if the logic took it. The **Welcome pane has no
floor** (`DetailFloor.resolve` → nil off the report), so on Welcome the
column never auto-collapses. That is by design, not a symptom.

## Fixed (ca00e7c8), with the evidence

Found with `SidebarFitHarnessTests` — a real NavigationSplitView in an
NSWindow in the test host, wired as ContentView wires it — and each pinned by
a test that fails if it returns.

| | Defect | Evidence |
|---|---|---|
| A | The detail reports width 0 as it mounts; the column (inferred as split − detail) was remembered as the **whole window**, so a taken column never fitted again | s03, s10 |
| B | "We hid it" was cleared only by `onChange(of: columnVisibility)`; a collapse and expand inside one update never fire it, so a column the researcher later hid was **given back** on the next resize | s13 (launch path; a same-turn resize pair did not reproduce) |
| C | Hide/show animation frames (1, 2, 4 … pt) were recorded as the column width; the toolbar button animates **before** the binding flips, so a toolbar show kept the hide's frames (220 → 182) | s15, s17, s18 |
| — | `.navigationSplitViewColumnWidth(180/220/300)` sat on the split view, where it is **inert** (AppKit: min 140, no max) | s00 |

Fix: modifier onto the sidebar column; `restingColumnWidth` ignores readings
outside 180–300 (+2 pt divider slack); the ours-flag is set at the write
(`autoCollapsed(after:was:)`); the width is re-measured when the column
becomes visible. Residual kept on purpose (s15): a toolbar *hide* still records
in-range frames, read only while hidden, when the column is never ours.

**Not a finding — do not re-derive.** The harness's first round reported
"the column comes back at 0 pt" and "the toolbar toggle desyncs SwiftUI".
Both were artefacts: a synchronous `RunLoop.run` in a test body holds the main
queue and every SwiftUI animation freezes at frame 0 (`desktop/CLAUDE.md`).
The harness is async now; those results did not survive it.

## Open — reported by Martin after ca00e7c8

Unknown whether these are new with ca00e7c8 or were always there.

| | Symptom | Where seen |
|---|---|---|
| S4 | The column comes back **narrow**, ~150–165 pt, below the declared 180 minimum | Signals, after show |
| S5 | The column shows the **resize cursor** at the seam but **cannot be dragged** | Codebooks |
| S6 | After a hide, the page does not fill the detail: a **white strip** left of the Contents panel (Signals); on Codebooks the page sits **centred between ~141 pt margins on both sides**, and the toolbar's bottom hairline spans only that centre | Signals, Codebooks |
| S7 | On Codebooks the web **left panel does not come back** when the window is wide again | Codebooks |

### What the harness rules out

Every one of these is clean in the harness (s19, s20), across **SwiftUI
`List` sidebar and an outline-shaped `NSViewControllerRepresentable`
stand-in** (zero-frame autoresizing container, as `SidebarOutlineController.loadView`
builds it) × **both modifier placements** × **a real `WKWebView` detail**
wired with `.ignoresSafeArea(.container, edges: .top)`:

- AppKit thickness 180…300 on the column; the divider moves to 260 and 190.
- Toolbar and menu hide/show: the web view starts exactly at the column's
  edge (220, 0, 260), its leading safe area is 0, and a page panel at
  `left: 0` stays at 0.

So the cause lives in what the harness does **not** have: the SPA itself, the
real toolbar, `WindowGroup` + `.windowResizability(.contentMinSize)`, the
`ZStack` / `.id(viewID)` around the report, and the bridge (`panel-state` →
`detailMinWidth`).

### Hypotheses, ranked, each with the reading that decides it

**H1 — the detail is laid out at a stale width and centred (native).**
S6's equal margins on both sides are SwiftUI's signature for a view that got a
fixed size smaller than its container. ~632 pt ≈ the detail's width while the
column showed. *Decides it:* `SidebarFitTrace` after the hide — `webW` less
than the window width with `webX ≈ (window − webW)/2` is native.

**H2 — the page's fit cascade is working from a stale width (web).**
`SidebarLayout` reports its width through a `ResizeObserver` →
`setLayoutContext`; if that value is stale the cascade keeps the left panel
closed (S7) and the centre column (which has a max width and centres) floats
in a wide page (S6). *Decides it:* the trace shows `webX=0`, `webW` = the
detail's full width, while in Web Inspector (Develop ▸ Bristlenose ▸ the
page) `innerWidth` is full but `document.querySelector('.layout').getBoundingClientRect()`
is not — or `SidebarStore`'s `availableWidth` disagrees with `innerWidth`.

**H3 — two drivers of the window frame.** In the harness an animated
visibility write followed by a programmatic resize made
`NSHostingView.updateAnimatedWindowSize` (inside `windowDidLayout`) and the
resize fight until AppKit threw its layout-loop guard in
`-[NSWindow _postWindowNeedsUpdateConstraints]`. A shipped app logs and
swallows that exception, leaving a half-applied layout — which could pin the
column (S5) or freeze the detail (H1). *Decides it:*
`/usr/bin/log show --predicate 'process == "Bristlenose"' --last 1h | grep -i "constraints"`
after a reproduction.

**H4 — ca00e7c8's modifier move behaves differently in the real sidebar.**
S4's width is *below* the 180 minimum, which the column cannot reach if the
modifier is live. If it is inert in the real app, `restingColumnWidth` rejects
every reading and the collapse threshold is off by ~60 pt — a regression.
*Decides it:* the trace's `thickness=` field (`180…300` = live; `140…-1` =
inert), and a build of `2d4a8baa` (the commit before the fix) against the same
steps.

**Leads, unattributed.** The app's own log since 20 Sep 2026 carries
**"Invalid frame dimension (negative or non-finite)"** (120–680 a day) and
**"Publishing changes from within view updates"** (~100–220 a day) as SwiftUI
runtime faults. Neither names a view. A negative frame dimension is exactly
what a width computed as *container − something* produces when the something
is stale.

## How to capture

```bash
defaults write app.bristlenose BristlenoseDebugSidebarFit -bool YES
/usr/bin/log stream --predicate 'subsystem == "app.bristlenose" AND category == "sidebar-fit"'
```

(or `-BristlenoseDebugSidebarFit YES` as a launch argument). Each line pairs
SwiftUI's belief (`split detail last floor vis auto`) with AppKit's layout
(`itemCollapsed sidebarW thickness webX webW webSafeLeft`). Reproduce, note
the time, keep the stream. For the web half: Web Inspector on the report,
`innerWidth` and the `.layout` rect, before and after the hide.

## For the confirming sessions

1. Reproduce S4–S7 on a report, trace on. Which of H1–H4 do the readings pick?
2. Run the same steps on `2d4a8baa` — do S4/S5 predate ca00e7c8?
3. Propose fixes against the hypothesis the readings pick, not the one that
   reads best. Two design facts to respect: the window is the only trigger for
   the column (`design-sidebar-playground.md`), and nothing declares a column
   minimum the window's own minimum can violate (`desktop/CLAUDE.md`,
   "NSSplitView never clamps").
4. Say whether the fix should stay in SwiftUI or move the split view to AppKit
   (see below).

## The larger question — is this SwiftUI on the Mac?

Partly, and the evidence says which part. Every defect found so far comes
from **reconstructing, in SwiftUI, facts AppKit already has**: the column's
width (inferred as split − detail, from two readers that fire during mounts
and animations), whether a collapse is ours (a flag cleared by an `onChange`
that coalesced updates skip), and when an animation has finished (nothing
tells us). `NSSplitViewController` holds all three directly — the item's
thickness, `isCollapsed`, `canCollapseFromWindowResize` (already `true` on this
column), holding priorities — and, in pure AppKit, a split view's minimums
feed the window's minimum, which is the very overflow SwiftUI's two floors
created on 20 Sep. The sidebar's rows already moved to AppKit
(`ProjectSidebarOutline`) for the same class of reason; the split view
around them is the same argument one level up.

**The version risk is real and unmeasured.** macOS 26 floats the sidebar over
a full-width detail (split − detail is exactly the column — measured); a
classic split on the 15.0 floor puts a divider between them (the 2 pt slack
is an allowance, not a measurement). Everything here ran on 27. And
`BristlenoseTests` sits at a **26.1** deployment target, so this harness
cannot run on 15 as the suite is built — a 15 or 26 VM would need the test
target's floor lowered, or the harness in its own target.
