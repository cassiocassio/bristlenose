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

Pass `-BristlenoseDebugSidebarFit YES` as a launch argument (Xcode ▸ Edit
Scheme ▸ Run ▸ Arguments), then:

```bash
/usr/bin/log stream --predicate 'subsystem == "app.bristlenose" AND category == "sidebar-fit"'
```

**Not `defaults write`**: the app is sandboxed, and writing its preferences
from Terminal fails with *"Could not write domain …/Containers/app.bristlenose/…"*
(measured 25 Sep 2026). Each line pairs
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

---

## Session 4 — other approaches (read only, nothing built)

Written 25 Sep 2026, 17:10, independently of sessions 2 and 3, from the
code, the harness and the unified log. First what I read that the brief
does not yet say; then the approaches, ranked by cost.

### Three readings the brief does not have

**The "Invalid frame dimension" lead is attributable, and it is not the
report.** The only `.frame(width:)` in the app whose argument can go
negative is `WelcomeHomeView.swift:435` — `major.frame(width:
(geo.size.width - gutter) * phi)` inside a `GeometryReader`, which reports
0 on its first pass, so the Welcome pane's golden-ratio split logs a fault
per mount (the log shows them in bursts of 10 at launch timestamps, e.g.
16:07:35). `SidebarShimmerText:74` already guards with `max(1, …)`;
`WelcomeIllustrations:94` passes the size through unchanged. Session 3
reports bursts at **lens changes** too, which this does not explain — if
those are real, the cheap way to name the view is Xcode's *Runtime Issue*
breakpoint with the debugger already attached, which stops in the Swift
frames the log's backtrace lacks. Either way: close this as a lead for
S4–S7. A negative frame on Welcome cannot centre the report.

**S4 may be a measurement, not a defect.** On macOS 26/27 the sidebar is a
floating glass card **inset** from the column it sits in. A 180 pt column
shows a card of roughly 155–165 pt. If "~150–165" was read off the card
rather than the divider, the column is at its minimum and the modifier is
live. The trace's `sidebarW=` decides it in one line. If that is what it
is, the action is the opposite of H4's: raise `columnMin` so the *card*
meets the design's floor, and record that the range is a column range, not
a card range.

**A native fault is lens-blind; S6 is not.** `ContentView` does not know
which lens the SPA is showing, so a wrong web-view frame (H1) would produce
the *same* wrong picture on Signals and Codebooks. Martin saw two different
pictures: a white strip left of the panel on Signals, equal ~141 pt
margins on Codebooks. Either the two observations were at different
widths, or the shape has a web ingredient — each lens's CSS rendering the
same (native or web) width fault differently. Codebooks is
`.layout-no-right` (0 | 1fr | 0 in embedded), Signals has its own
`signals-layout` grid and a sticky left panel at x = 0; those would indeed
draw one fault two ways. So the H1/H2 split is probably not either/or, and
the decisive reading is the pair `webX/webW` **and** the `.layout` rect
from the same instant — which is what session 3's AX driver reads.

One more cheap discriminator for S6-Codebooks: "the toolbar's bottom
hairline spans only the centre". If that hairline is AppKit's toolbar
separator (drawn over whichever view scrolls under it), its span *is* the
WKWebView's width and S6 is native. If it is the SPA's own `h2`
`border-bottom` (`report.css:93`, a full-pane section divider), its span is
the `.center` column and S6 is web. Web Inspector, hide the `h2`: if the
line goes, it was web.

### Approaches

**A. Read the column from AppKit instead of inferring it (small, keeps
SwiftUI).** Every fixed defect (A, B, C) and hypothesis H4 come from
reconstructing `split − detail` through two geometry readers. The trace
already walks from the key window to the `NSSplitView` and reads the
item's `isCollapsed`, `minimumThickness` and the sidebar subview's frame;
the *decision* could read the same. A one-view `NSViewRepresentable` probe
placed in the sidebar column finds its enclosing `NSSplitView` in
`viewDidMoveToWindow`, subscribes to `NSSplitView.didResizeSubviewsNotification`
and KVO on the item's `isCollapsed`, and publishes the real column width,
the real collapsed state, and — because the notification fires per layout,
not per SwiftUI frame — a clean "animation finished" edge. `restingColumnWidth`
and its 180–300 filter go away; the version slack (`dividerSlack`) goes
away because the reading is whatever this OS lays out. `decide()` and the
ours-flag stay exactly as they are. Cost: ~60 lines, one representable, no
migration. This is the first thing I would try, because it removes the
whole class rather than the three instances.

**B. Bisect the app, not the harness (diagnosis, ~5 lines per switch).**
The harness is clean with three stand-ins; the app is broken with the real
things. Rather than guess which missing ingredient matters, remove them
from the *app* one at a time behind DEBUG launch arguments:
`-BristlenoseDebugDetail color` (the WebView becomes a `Color`, keeping
`.id(viewID)`, the `ZStack` and the boot overlay), `-BristlenoseDebugNoToolbar`,
`-BristlenoseDebugNoResizability` (drop `.windowResizability(.contentMinSize)`).
Run Martin's S6 steps under each; the first switch that clears it names the
cause. Meets the harness in the middle and needs no Accessibility grant.

**C. One-shot dump instead of a stream.** Diagnostics ▸ *Dump Layout*
writes, to one file, the NSView frame tree under the key window's content
view and the result of `evaluateJavaScript("innerWidth, .layout rect,
.center rect, SidebarStore.availableWidth")` from the same run-loop turn —
both halves of H1/H2 at the instant of the symptom, no timing to line up.
Zero-code variant: Xcode ▸ Debug ▸ View Debugging ▸ *Capture View
Hierarchy* while S6 is on screen; the WKWebView's frame and whether it is
centred are on the canvas. Session 3's AX driver is the same information
through a wider door; this is the narrower one if the grant is slow.

**D. Take the animation out of the resize path (one line, removes H3's
mechanism whatever the diagnosis).** `applySidebarAutoCollapse` writes
`columnVisibility` inside `withAnimation` from a geometry callback that
fires during a live window drag — the two-drivers shape H3 describes. Mail
does not animate a resize-collapse. Wrap the write in a `Transaction` with
`disablesAnimations = window.inLiveResize` (animate only the expand on a
programmatic or post-drag change). Cheap, safe, and it also removes one
candidate for "Publishing changes from within view updates", which is a
state write during layout by another name.

**E. Make the web side incapable of a stale width.** H2 exists because the
cascade is JS state fed by a `ResizeObserver` on one element; an observer
that stops firing (element remounted under it, effect deps unchanged) leaves
`availableWidth` frozen and nothing reports it. Container queries make the
fit a pure function of the width the engine is laying out *right now*:
`.layout { container-type: inline-size }` and `@container (max-width: …)`
rules closing the left panel, then tags, then minimap, with `lastOpened`
as a class the query respects. `wantedWidth` (the wish, posted to native)
stays JS, because it is computed from state, not from width. This kills S7's
class rather than the instance — but it is the biggest change of the cheap
ones, and only worth it if the readings pick H2.

**F. Hand the whole split to `NSSplitViewController` (the large option).**
Session 1's question 4. What it buys that A does not: the detail floor
becomes `detailItem.minimumThickness = webMinWidth`, the collapse-on-resize
becomes `sidebarItem.canCollapseFromWindowResize` (already `true`), and
the window's minimum **follows the split's minimums automatically** — which
is precisely the property whose absence in SwiftUI produced the 20 Sep
overflow and forced the "declare no minimum, decide ourselves" design.
`SidebarAutoCollapse.decide` would not need to exist. What it costs: the
toolbar (`NSToolbar` + `NSTrackingSeparatorToolbarItem`, and every
`ToolbarItem` in `ContentView` rehomed), title/subtitle (direct on the
window — simpler), `focusedSceneValue` plumbing through hosting views
(should hold, unmeasured), and the whole harness rewritten. **Two things
are unmeasured and decide whether it is worth it:** (1) whether AppKit
re-expands a resize-collapsed item when the window widens again, or leaves
that to the app as Mail may do — if the app still has to do it, the
ours-flag survives the migration; (2) whether a `minimumThickness` change
*without* a resize (a panel opening) collapses the sidebar in AppKit, or
overflows exactly as SwiftUI did — the design's "the window is the only
trigger" rule was written against the SwiftUI behaviour and may be AppKit's
too. Both are a 30-line AppKit spike in the existing test host, and I would
run that spike before choosing F over A.

### Order I would take

Readings first: `sidebarW=` (settles S4 for or against the card inset),
the `h2` test (settles which side S6 is on for Codebooks), then session 3's
paired frame/DOM read. Then D regardless, because it is free. Then A if the
readings say the column's width is still being misread, E if they say the
page's is. F only after its two spikes come back, and only if A leaves a
defect standing.

### Converged across sessions 2, 3 and 4 (17:40, 25 Sep 2026)

Each reached independently, then compared. Readings are from the **real
app** (session 3's live trace, pid 91553) and the **unified log** (session
2's two-day count) unless marked otherwise.

| | Verdict | Evidence |
|---|---|---|
| "Invalid frame dimension" | **Closed as a lead.** Welcome pane, not the report | Static source `WelcomeHomeView.swift:435`; 320 faults in two days, ten within 1 s of every launch, one late burst after a new window opened |
| H3 | **Closed for the shipped app** | The only layout-loop guard in two days (pid 48754, 12:02) has `SidebarFitRig.settle` → `runUntilDate:` at the bottom of its backtrace: the harness's own synchronous round. No real pid ever hit it |
| H4 | **Refuted on this build** | Live trace during a 1197→1054→1156 resize: `thickness=180…300 sidebarW=180`, split − detail = 180 on every frame. The modifier is live |
| S5 | **Not reproduced on the real app** (session 3, AX) | A real mouse drag of the seam on Signals works and clamps at exactly 180 — which also refutes H4 by drag, not only by thickness |
| S6 on Signals, one path | **Did not reproduce** (session 3, AX, 91553) | Toolbar hide at 900 wide: web area x=0 w=900, TOC entry at 13, `.center` at 240 w=660, splitter −1 ↔ 180 across hide/show. `webSafeLeft` 5–8 only during the show animation. Floor on Signals is 608 (368 + 240, no right column). Codebooks and the 1400→760 range still to run |
| S4 | **Leading explanation: the glass card, not the column** | On 26/27 the sidebar card is inset from its column; a 180 column shows ~155–165. Pending session 3's paired column/card read. If confirmed, the action is to raise `columnMin` so the card meets the floor |
| macOS 27 column autosave (session 2's mechanism) | **No evidence here** | Container Preferences dir empty; no split/column/sidebar key in any domain. A mechanism, not a lead, unless a repro relaunch writes one |
| Launch first pass (session 3, new) | **A real-app lead, not one of S4–S7** | First trace lines on a fresh instance: `split=1000 detail=0 … appKit=no-key-window` — the WindowGroup's `defaultSize(1000)` pass before frame restore, and `applySidebarAutoCollapse` runs on it. Quotes with both panels wished is 1008, so a report collapses the column against a width the window never has; it should return on the restore (a resize, column marked ours). Cheap guard: no decision until AppKit has a window |

Still open, and what decides each: S5 (a seam drag with `AXSplitter` settable
read, session 3; or the divider's legal range min == max from session 2's
harness), S6 and S7 (session 2's real-SPA harness rows pairing the WKWebView
frame with the `.layout`/`.center` rects; session 3's AX read of the same via
`AXDOMClassList`). Session 3 is blocked on the Accessibility grant for the
Claude app.
