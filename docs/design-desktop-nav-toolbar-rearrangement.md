# Desktop nav + toolbar rearrangement — UX spec

**Status:** Draft · Phase 1 · 21 Jun 2026 (rev 2 — folded the `/usual-suspects` Phase-1 review + user decisions)
**Accompanies:** `docs/mockups/desktop-nav-toolbar-rearrangement.html`
**Review:** Phase-1 plan-review run (5 review agents + parsimony pass); findings + dispositions logged locally (gitignored).
**Extends:** `docs/design-project-sidebar.md` (row anatomy, project index) · `desktop/CLAUDE.md` (toolbar morphing, bridge)
**Scope:** macOS desktop shell (`desktop/`) only. The shared React SPA and the CLI/browser `serve` path are untouched — see §2.1.

---

## 0. Posture — ride the platform, keep the floor

**Floor = macOS 15 (Sequoia)** — verified: the app/project deployment target is `15.0`; only the *Tests* target is `26.1` (`project.pbxproj`). We keep 15.0 for **install coverage** — Sequoia-and-earlier dwarf Tahoe's install base, and reach matters for a paid MVP. No floor bump.

**Adopt the latest, gracefully.** Build against the Xcode 26 SDK; native Liquid Glass + the new toolbar APIs render on macOS 26+; on Sequoia the app shows the **ordinary native Sequoia chrome** (no glass — *correct*, not broken). The new APIs (§6.2) are `if #available(macOS 26, *)`-gated; the fallback is mostly "the system draws its pre-glass standard," not custom work. And where the runtime *is* glass-capable, **lean in** — take advantage of the material rather than merely tolerating it: e.g. let the report content slide under the floating toolbar (§4.6). We **don't opt out of glass on capable OSes** (`DisableSolarium` broke in 26.2 anyway) and **don't fight native visuals on taste** — Apple is self-correcting (macOS 27 "Golden Gate" already pulls the menu-item icons). The budget goes to research features.

**99% SwiftUI by policy** — a Mac app for the future. Where SwiftUI genuinely can't deliver (e.g. `List` folder drag-and-drop), targeted AppKit surgery (`NSTableView`/`NSOutlineView` under the SwiftUI) is acceptable — the exception, not a retreat.

## 1. Problem

The desktop app inherited the web report's **horizontal tab strip** (Project · Sessions · Quotes · Codebook · Analysis) and renders it as a native segmented `Picker` in the toolbar centre (`ContentView.swift:1318`). That leaves **two navigation surfaces** competing: the tab strip across the top — always in the eyeline, *telling you what you already know* — and the project sidebar down the left, paying full width largely to switch projects. Things.app's lesson: **one sidebar carries both**, freeing the right pane to be *purely the report*.

## 2. The move (Phase 1)

Relocate the five tabs out of the toolbar **into the top of the sidebar** as a fixed "lenses" band; the scrollable project list sits below. The freed toolbar is rebuilt to the Tahoe toolbar HIG. **Native shell only — ~zero frontend change:** the lens rows fire the same `switchToTab` bridge call the `Picker` does today.

### 2.1 Platform fork
The SPA's `embedded` flag is the lever: **embedded** (in-app `WKWebView`) suppresses the web `NavBar`/`Header`/`Footer` the Swift shell supplies; **non-embedded** (CLI `serve` → browser) keeps them. Nothing here touches the browser/CLI experience.

### 2.2 Hard scope guard — the project list is reused, NOT rebuilt
**The existing left-hand project list (folders, drag-and-drop, reorder, rename, context menus, selection, the in-list New-Project row) is lifted and shifted VERBATIM from the current `ContentView.swift`. This work does NOT touch, refactor, or fix the drag-drop.** Its known bugs — drag-out-of-a-folder to top level; folder-to-folder project move — are *parked, out of scope*. The SwiftUI-`List` drag-drop failure has been forensically investigated more than once (the **"sidebar apocalypse"**, commit `7bf0e96` + the cross-linked drag-drop docs); **do not reopen it.** The real fix is a future AppKit `NSTableView`/`NSOutlineView` rewrite (or an upstream macOS fix) — a *separate* effort, now specced in `design-desktop-sidebar-appkit.md` (which also delivers the native source-list selection SwiftUI can't emit); we support Sequoia-up regardless. *"Anything but that."*

**Build hierarchy:**
1. **Drag-drop / folders / selection machinery → NEVER touched.** Reuse verbatim.
2. **The project `List` structurally → reused.** The lenses go in a **separate control *above* the `List`** (§3.1), never a section inside it — so the fragile `List` is never modified and the lens rail sidesteps the macOS-26 `List` gotchas (it isn't a `List`).
3. **Project-row presentation polish** (variable-height §3.2, outline `circle` §5, trailing-slot order) → *optional*, only as a trivial presentation delta on the existing row; if it would mean restructuring the row/`List`, **defer it.**

**Scope is exactly two things: relocate the tabs into the sidebar (as the separate lens rail), and rebuild the toolbar.** Nothing in the project list itself.

## 3. Sidebar

### 3.1 Selection model — a separate lens rail above an untouched project List
Per the §2.2 guard, the project `List` (its `@State Set<SidebarSelection>` selection, drag-drop, folders) is **reused untouched**. So the lenses are **not** a section inside it, and we do **not** add a `.lens(Tab)` case (that would modify the fragile List). Instead:

- **The lens band is its own control** — a fixed `VStack` (or small non-`List` rail) of five toggle-rows above the project list, with its own simple `@State activeLens` driving `switchToTab`. It is a *mode rail*, not a peer `List` selection; render it a deliberately *different, lighter* weight than a project row (accent-tinted symbol / medium-weight label — toolbar-toggle language) so a lit lens + a lit project never read as a stuck multi-select. Framing: *one project selection (the existing List) + one persistent mode (the rail)*. Bonus: the rail isn't a `List`, so it sidesteps the macOS-26 `List` gotchas entirely.
- **Empty state:** the rail is **dimmed/disabled until a project is selected** — the same affordance today's tab `Picker` gives via `.disabled(selectedProject == nil || !isReady)` (`:1322`). The dimming *is* the "pick a project first" teaching. With zero projects, `WelcomeView.firstRun` owns the detail pane.
- *(The existing List is already a multi-`Set`, so a one-List `.lens(Tab)` approach is technically possible — but §2.2 rules it out: keep the List untouched. The separate rail is also what the review preferred.)*

### 3.2 Row anatomy — *absence is information*
Variable height, not the current always-reserved two-line band:
- **Idle row** → single tight line (icon · name · count). **Live row** → a second line appears *only* while there is status (run progress). Animate the height change — but **guard `@Environment(\.accessibilityReduceMotion)`** (instant resize when on), and **never reflow a row under an active pointer or during a drag-reorder** (spatial-stability: don't shove a row out from under the reader's cursor).
- **Title-line trailing order** (resolves the collision with the same-day-trued `design-project-sidebar.md` "Row anatomy"): the **session count** is the default occupant; the **storage/sync qualifier** (iCloud arrow, external-drive hint) *replaces* it when the project is unavailable/syncing. Precedence: in-flight scan > failure glyph > availability qualifier > count. The activity/copy ring keeps the *subtitle* trailing slot during runs.

### 3.3 Top controls + New
- **Sidebar show/hide** → standard `sidebar.left` at the sidebar's top-trailing (auto-provided by `NavigationSplitView`). Nothing else in the traffic-light strip.
- **New Project** → a **`+ New project` row at the top of the projects list** — a plain `+ New project` row, **no inline `⌘N` hint** (on the Mac, shortcuts are learned from the menu bar, not list rows; the `+ …⌘N` inline hint is a web/Electron habit). The shortcut lives in File ▸ New Project (`⌘N`). *Not* the toolbar, *not* the traffic-light strip. Not Mac-purist, but pervasive — and it keeps the toolbar clean for the report. (Supersedes the sidebar-top `+` in rev 1, and reconciles with `design-project-sidebar.md` §"New Project placement".)
- **New Folder** → File ▸ New Folder (`⇧⌘N`) + the list's right-click menu. Infrequent; no dedicated row.

## 4. Toolbar

### 4.1 Action inventory → homes
| Action (symbol) | Today | New home |
|---|---|---|
| 5-tab picker | centre `.principal` | **→ sidebar** (the lenses) |
| Back / Forward (`chevron.backward/forward`) | leading | **content leading** — grouped pair |
| Sidebar toggle (`sidebar.left`) | auto | **sidebar top-trailing** — standard icon |
| Left panel: Contents/Codes/Signals (`list.bullet`) | leading | **inspector toggle** · Quotes·Codebook·Analysis |
| Tags (`sidebar.right`) | trailing | **inspector toggle** · Quotes |
| Heatmap (`square.grid.2x2`) | trailing | **inspector toggle** · Analysis |
| **Export (`square.and.arrow.up`)** | trailing | **visible trailing menu** — see §4.2 |
| Search (`magnifyingglass`) | trailing | **trailing — rightmost** (see §4.4) |
| Ollama pill (custom) | `.status` | **`.status`** — unchanged |
| New Project / New Folder | sidebar bar / File menu | **in-list `+` row + File menu** (§3.3) |

### 4.2 Export — a visible menu, named *Export*
**Export, not Share.** Bristlenose produces *standalone artefacts the recipient opens without installing Bristlenose* (`design-export-sharing.md`) — that's Export. Share (the macOS share sheet) sends a *pointer* via apps/people; we don't. The codebase already uses the Export verb. Icon: `square.and.arrow.up` (the universal send-out glyph the `.app` already uses).

It stays a **visible trailing toolbar `Menu`** (a researcher's primary output). **Rename, Move, Show in Finder are *not* toolbar items** — they live in the project row's right-click menu and the menu bar (File / Project), where they already are. The title carries **no** menu (no `ToolbarTitleMenu`).

**A menu now; maybe a popover one day.** Today it's a SwiftUI `Menu` pull-down (already is). A richer share-sheet-style popover (recent destinations, etc.) is a someday, not now.

**Submenu — mirror the web/CLI report's set** (the `.app` is behind; wire toward parity, morphing per tab as it does today):

| Item | Web/CLI | `.app` today |
|---|---|---|
| Export Report… (offline HTML, preserves stars/tags/edits) | ✓ | ✓ (`⇧⌘E`) |
| Export Anonymised… | ✓ | — |
| Copy Quotes as CSV (clipboard) | ✓ | partial |
| Quotes → spreadsheet (CSV / XLS) | ✓ | — |
| Video clips | ✓ | — |
| Slides → PPTX | ✓ | — |
| Send to Miro | ✓ | — |

`ExportMenuButton` already morphs ("Export Report…" universal; Quotes-CSV on the Quotes tab; Signal-Cards-PPTX planned for Analysis) — extend it toward the web set above.

### 4.3 Grouping & responsive collapse
**Decision: keep the shipped spatial split** — each panel toggle sits *near the panel it controls*, because for a high-frequency control the proximity mapping beats oval-economy:
- **Leading:** back/forward (history capsule) · the **left-panel toggle** (Contents/Codes/Signals, `list.bullet`) near the left web panel · title + subtitle.
- **Trailing:** the **right-side inspector** (tags / heatmap) near the right panel · **Export** · **Search** (rightmost).

The **tag inspector keeps `sidebar.right`** (the right-panel glyph), deliberately *not* a tag glyph — the Codebook *lens* now owns `tag`, so a second tag would clash. This runs more than the ≤3-capsule ideal, accepted on purpose. **Rely on the system overflow** — never hand-roll a More menu, never overflow at default width (HIG). Pinned: sidebar toggle, back/forward, search, title (truncates); the trailing inspector folds into the auto `»` first, then Export.

### 4.4 Search — a port, not a restyle
`searchToolbarBehavior(.minimize)` / `DefaultToolbarItem(kind: .search)` need a real `.searchable` field. **Today search is a custom `Button` firing `menuAction("find")` into the web bar — no SwiftUI search field**, so the minimise treatment is a no-op until that migrates. Decide at spec→code: keep the custom button (drop the minimise claim) or build a native `.searchable` that forwards to the web layer. Either way, search stays trailing-rightmost.

### 4.5 Title — avoid the duplicate-item trap
Show project name + subtitle (`N participants · Hh MMm`), truncating with the subtitle preserved (Photos pattern); clip the **subtitle** before the name when tight (identity outranks metadata). **This reopens a documented fence:** `.navigationTitle` on the detail injects a *duplicate* toolbar title item — which is exactly why the prior in-toolbar project chip was removed "by user request" and the name routed to `NSWindow.title` via `WindowTitleManager` (`desktop/CLAUDE.md:409`, `ContentView.swift:1262-1270`). The new title must be a **single explicit `ToolbarItem`**, *not* `.navigationTitle`, and must not sit where the system back affordance lives. This spec is the design pass that removal comment anticipated.

### 4.6 Content under the toolbar — lean into glass
On macOS 26+, take advantage of the material: the report content (quotes, codebook, …) **slides under the floating toolbar** instead of stopping at a hard boundary — edge-to-edge content, translucent chrome, the glass bar blurring whatever passes beneath it. This is the look to lean into where the OS supports it.

**Implementation reality (spec→code):** the WKWebView extends **under** the toolbar (full-size content view), and the report needs a **top content inset** so its first row isn't clipped — set natively on the web view's scroll if reachable, else a small *embedded-mode* top padding in the SPA (the one place this bends "~zero frontend change"; conditional on `embedded` + glass-capable). Note: `scrollEdgeEffectStyle` is a SwiftUI-scrollview effect and won't auto-apply to a WKWebView — the slide-under comes from the toolbar's own glass translucency over the extended web view, not the system blur.

**Cheap bonus — chrome colour-tint (the Safari trick).** Safari warms its sidebar/toolbar to the page's background colour (ft.com's pink bleeds into the chrome). We can do the same with *no* pixel-mirroring: `WKWebView` exposes `themeColor` (the page's `<meta name="theme-color">`) and `underPageBackgroundColor`, both KVO-observable — read either and tint the native glass. **Reality check:** our report is mostly white, so the automatic tint is near-neutral — which is exactly why bn.app reads like Notes/Bear, not like FT. A *visible* tint is then a deliberate choice: the SPA sets a faint brand `theme-color` (a one-line `<meta>`), optional. The dramatic colourful bleed (Maps-style) still needs the extend-under plumbing and only pays off on colour-dense lenses (the heatmap) — post-MVP.

> **Build toward:** the planned **edo theme** is a subtle washi-paper off-white (not pure white) — its paper colour will warm the chrome and let the report extend *seamlessly* under the sidebar/toolbar (no white-vs-glass seam). So wire the Phase-1 chrome to **read `themeColor`** — one theme token drives both the web background *and* the native tint — and **never hardcode** a colour natively. The paper theme then lights it up for free, and so does any future theme (shared token, rendered native per surface).

**Sequoia (15):** solid toolbar boundary, content stops below it. Graceful — no slide-under, no breakage.

## 5. Icon set
| Item | SF Symbol | Note |
|---|---|---|
| Project | `target` | **settled** — its concentric rings deliberately echo the project-row `circle` ("the circle come alive" once you're inside the project), binding the lens icons to the row vocabulary |
| Sessions | `person.2` | **two people** — "Sessions" is plural; one person under-reads (drops `person.wave.2`) |
| Quotes | `text.quote` | settled |
| Codebook | `tag` | settled |
| Analysis | `square.grid.3x3` | grid clash with the heatmap toggle (`square.grid.2x2`) is **parked** — the heatmap feature + its icon need a redesign pass |
| Project row | `circle` | **default only** — per-project `IconPickerPopover` choices still win |
| Sidebar toggle | `sidebar.left` | system standard |

All lenses share one outline family; monochrome, borderless. **Locked**, bar the `3×3`/`2×2` grid-density clash (parked with the heatmap redesign, §7).

## 6. Liquid Glass

### 6.1 Restraint = riding native (not defence)
Lean on system materials and semantics — monochrome **borderless** SF Symbols, **≤ 3 groups**, **no custom backgrounds or tints**, one prominent action max. Not as a defence against the (real, widely-noted) weakness of the Mac's first Liquid-Glass expression, but because riding the system means Apple's improvements land for free. The innovation budget belongs in the report, not the chrome.

### 6.2 Toolkit (macOS 26+ — `#available`-gated)
`ToolbarSpacer(.fixed/.flexible)` (split glass capsules; adjacency fuses) · `sharedBackgroundVisibility(.hidden)` · `searchToolbarBehavior(.minimize)` (once §4.4 lands) · `DefaultToolbarItem(kind:)` · `scrollEdgeEffectStyle(_:for:)` · `buttonStyle(.glass/.glassProminent)`. **All macOS 26.0+** — wrap each in `if #available(macOS 26, *)`. The Sequoia (15.0) fallback is automatic for system controls (standard pre-glass toolbar: contiguous items, no glass grouping, search in its old spot); for any custom glass surface the stand-in is `.background(.regularMaterial)`. The look diverges by floor **on purpose** — test both.

### 6.3 Bug guardrails (open as of mid-2026)
- **Avoid `toolbar(id:)` customisable toolbars** — a conditionally-rendered ID'd item + a second window crashes the app (FB15513599, ~14 months open). We want no toolbar customisation, so use plain `.toolbar { ToolbarItem }` without `id:` and toggle *visibility*; the crash is then unreachable.
- **Keep `.toolbar` on the child columns** (sidebar vs detail), **never on the `NavigationSplitView`** — `.toolbar(id:)` on the split throws `NSToolbar … splitViewSeparator` duplicate-identifier.
- **No glass-on-glass**; `.glassEffect()` no-ops if the view already has a background. Three ways content reaches the chrome, only one blocked: **real pixels under the glass** (toolbar slide-under, §4.6 — *yes*); **colour-tint from the page's `themeColor`** (§4.6 — *yes, cheap; near-neutral until the SPA sets a brand colour*); and the **`backgroundExtensionEffect` mirror** that reflects the detail pane under the sidebar (*no* — can't sample a WKWebView). Don't conflate them.
- `scrollEdgeEffectStyle` attaches to the **project-list scroll view**, never an ancestor that would pull the WKWebView into the blur.

### 6.4 Verification — manual checklist + one unit test
Per the test review, §6's appearance concerns are **taste the cohort and the developer's eyes cover** — not an automated matrix. Pre-TestFlight **manual checklist**, on **both floors {Sequoia 15, Tahoe 26}** (the chrome diverges): Reduce-Transparency on → lenses legible; new window + this toolbar → no crash; search stays put; Light/Dark. The **one automated test**: factor the lens→`Tab` mapping into a pure helper (`LensItem.tab`, mirroring `ProjectSubtitle.resolve`) and unit-test it — the single silent-regression seam this change introduces.

### 6.5 Implementation notes
Lens rows are **named `View` structs** (`LensRow`), not inline closures (diffing identity). Subtitle updates fire on **stage-boundary events**, not sub-second ticks (verify `RunProgressSubtitle` isn't already churning before adding a throttle). Confirm "lens" stays a **code-internal** term (the product says "tabs"; a user-facing "lens" string would need a `glossary.md` entry).

## 7. Open decisions
1. **Native search migration** — port to a native `.searchable` field now, or keep the web-routed button for now (§4.4). *A spec→code timing question, not a design call.*

**Decided:** floor **Sequoia 15.0** for coverage + adopt-latest-with-graceful-degradation (§0); Export = visible toolbar menu, Rename/Move/Show → context menu + menu bar not the toolbar (§4.2); inspectors = **spatial split**, tag inspector keeps `sidebar.right` (§4.3); New Project = in-list `+` row + `⌘N` (§3.3); Sessions = `person.2`, **Project = `target` kept** (rings echo the project-row `circle` — "the circle come alive") (§5); selection = one List + `.lens(Tab)`, lens-as-mode, dimmed-until-project (§3.1). **Parked:** the `3×3`/`2×2` grid-density clash (heatmap feature + icon need redesign).

## 8. Sources
- Apple HIG — [Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars) · [Sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars) · [Materials](https://developer.apple.com/design/human-interface-guidelines/materials)
- WWDC25 — [323 Build a SwiftUI app with the new design](https://developer.apple.com/videos/play/wwdc2025/323/) · [219 Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)
- Apple docs — `ToolbarSpacer`, `sharedBackgroundVisibility`, `ToolbarTitleMenu`, `searchToolbarBehavior`, `DefaultToolbarItem`, `scrollEdgeEffectStyle`, [Adopting Liquid Glass](https://developer.apple.com/documentation/TechnologyOverviews/adopting-liquid-glass)
- Platform is self-correcting — Gruber, [macOS 27 Golden Gate removes the dumb icons from menu items](https://daringfireball.net/2026/06/macos_27_golden_gate_removes_the_dumb_icons_from_menu_items) · [SwiftUI only makes it easy to develop bad apps](https://daringfireball.net/2026/06/swiftui_only_makes_it_easy_to_develop_bad_apps)
- Reception / engineering (rev 1) — Snell, Gruber, NN/g, Troughton-Smith, JuniperPhoton, Donny Wals; Apple DF [772096](https://developer.apple.com/forums/thread/772096) (`toolbar(id:)` crash) / [763829](https://developer.apple.com/forums/thread/763829) (split-view duplicate)

## 9. References
- `docs/design-project-sidebar.md` — row anatomy (this spec updates §"Row anatomy" trailing order + supersedes §"New Project placement"); project index
- `desktop/CLAUDE.md` — toolbar morphing, `switchToTab` bridge, `.status` Ollama pill, the `.navigationTitle` duplicate-item gotcha (`:409`)
- `docs/design-export-{html,quotes,clips,slides}.md`, `docs/design-miro-bridge.md` — the export type set (§4.2)
- `docs/mockups/desktop-nav-toolbar-rearrangement.html` — the interactive mockup
- Phase-1 `/usual-suspects` review — findings + dispositions logged locally (gitignored)

---

## 10. Experience surfaces — decide before the build

> The mockup is *layout*; these are the **behaviours, states, and system integrations** that bite in Swift and that a static mockup never forces you to decide. **Meta-rule (from the sample-code sweep): every mechanism below exists at the macOS 15 floor — only the Liquid-Glass *presentation* is 26-only. Build the behaviour once; `#available`-gate the chrome.** Architectural enabler throughout: route commands through the **responder chain** (`sendAction(_:to:nil:from:)`, nil target) so one verb fires on whichever surface has focus — the NetNewsWire pattern; it underpins keyboard nav, context menus, and Quick Look.

**10.1 Focus & keyboard — highest bite, because of the web boundary.**
- **Web-boundary focus — settled principle:** the report is **one tab-stop** in the native loop by default (Tab past it → next native control; you enter its internals by click or the single-key scheme), and **there is always a native-intercepted command that returns focus to the chrome** — a ⌘ "Move focus to Projects" in the View menu. ⌘-shortcuts hit native *before* the web view, so it works even if WebKit's boundary handback or a web focus-trap fails: *the keyboard user is never trapped.* The exact Full-Keyboard-Access descent/handback tuning is a build-time decision (test against real FKA); the no-trap guarantee is fixed now.
- `List(selection:)` gives arrow-keys + Return for free; use `.keyboardShortcut(.defaultAction/.cancelAction)`, not hardcoded keys. Enable/disable menu commands from the focused window via `.focusedSceneValue` + `@FocusedValue` ("Rename" greys out with no selection).
- **Decide (product):** single-key review shortcuts on the **Quotes** lens (`space` = advance, `j`/`k`, `s` = star, `h` = hide) — the "process-a-pile" pattern; lives in the web layer, coordinated with native chrome. [Simmons; HIG Full Keyboard Access]

**10.2 Window & state restoration.** `@SceneStorage` (floor) restores per-window UI state — selected project, active lens, sidebar visibility, search text; window frame is automatic via the system setting. Define the set now. **Multi-window:** the video popout is our one window today (memory rule); treat open-project-in-new-window as *future* but don't architect it out — one serve-sidecar-per-project complicates N-windows-on-one-project. [Apple: Restoring State; Bringing Multiple Windows]

**10.3 Undo.** Define `UndoManager` scope (per-window) and which sidebar mutations register (rename, reorder, delete, choose-icon), named via `setActionName` ("Undo Rename"). Build the actions undo-aware now even if reorder ships later — the discipline is *every* mutation goes through it so `canUndo` is truthful. Web-side report edits keep their own undo (the existing `isEditing` → WKWebView handoff). [HIG; `@Environment(\.undoManager)`, floor]

**10.4 Long-run feedback when backgrounded — *direction recorded; post-TF, not a TF gate.*** TestFlight ships on the existing in-app surfaces (the sidebar row flips to done); the background-alerting below is a vibes-call-for-the-record, built later. When built, and bn.app is **not frontmost** at completion: a **Notification Centre banner** + sound (click → open the project) as the primary signal, **plus a single *informational* Dock bounce** (`NSApp.requestUserAttention(.informationalRequest)` — bounces once and stops; the gentle "done", *not* the bounce-til-you-click `.criticalRequest`). **No badge** — runs rarely pile up and a count isn't meaningful. **Dock-icon progress during the run = future / luxury**, not now. Opt-in / sensible default; fires only on genuine completion (never a blanket toast — this *is* the native "surface it, don't toast it"). **Trap:** `scenePhase` is unreliable on macOS for foreground/background — gate on AppKit `NSApp.isActive` / `NSApplication.didResignActiveNotification`. VoiceOver: `AccessibilityNotification.Announcement("Analysis complete").post()`. Technical scope (permission flow, APIs, stdout redaction) already worked through in private build notes. [NetNewsWire; Jesse Squires]

**10.5 Context menus, drag-reorder, in-place edit — and two parked items this unblocks.**
- **Context menus + rename → reused as-is** (§2.2), *not* re-gestured for this work. (The `.contextMenu(forSelectionType:primaryAction:)` route that would unblock the parked slow-double-click rename touches the rows, so it's a safe *separate* follow-up, not bundled here.) [SerialCoder]
- **Drag-to-reorder → reused as-is, NOT built/fixed/touched** (§2.2). The known folder-drag bugs ("sidebar apocalypse") stay parked; the hover-handle / AppKit-`NSOutlineView` rewrite is the *separate future* fix, not this work. [Nil Coalescing]

**10.6 Quick Look (nice-to-have).** Spacebar-preview session/clip files via `.quickLookPreview`. Trap: `NSTextView` hijacks the panel while focused — resign first responder before invoking (threatens the transcript-editing surface). [Apple; DevGypsy]

**10.7 Accessibility — design in, don't bolt on.** VoiceOver row recipe (it falls straight out of our existing rules): `.accessibilityLabel(name)` (identity) · `.accessibilityValue(statusSubtitle)` (state) · `.accessibilityAddTraits(.isSelected)` · decorative glyph `.accessibilityHidden(true)` · per-row verbs via `.accessibilityAction(named:)` (not in-row chrome). The web pane is a VoiceOver discontinuity — verify the handoff. Add **`performAccessibilityAudit`** as a CI gate (macOS-supported). **Sidebar row height follows the user's General-settings sidebar-icon size** — our variable-height rows (§3.2) must respect it. [SwiftLee; WWDC25 s229; HIG]

**10.8 The web pane API — floor vs 26.** macOS 26 ships a first-party SwiftUI `WebView` + `@Observable WebPage` (find-on-page, back/forward, context menu, custom schemes); **at the 15 floor we keep `NSViewRepresentable` + `WKWebView`.** Apple's *Building a cross-platform web browser* sample is the behaviour guide regardless of which API backs it. Note: native find-on-page (`.findNavigator`) is a candidate answer for the §4.4 search-port. [Apple: WebKit for SwiftUI]

**Reading list (pin these):** Brent Simmons, "Implementing Single-Key Shortcuts in NetNewsWire" (the responder-chain pattern) · "Mac-Assed Mac Apps" (Daring Fireball) · Hansmeyer / Troughton-Smith native-feel checklist · Apple **Landmarks** (Liquid Glass) + **cross-platform web browser** samples · WWDC25 s229 "Make your Mac app more accessible." Full sweep (HIG corpus + indie patterns + Apple samples) captured in the review notes.

**TF triage — what of §10 is actually TestFlight build work:** just the focus model — §10.1's no-trap ⌘ "focus Projects" command + the standard keyboard/menu wiring — plus keeping the §3.2 row animation reduce-motion-safe. **Direction-recorded, post-TF / beta:** background alerting (§10.4); Quick Look (§10.6); and the `performAccessibilityAudit` gate + the native→web Dynamic-Type curve (§10.7 — with the beta a11y pass, which genuinely needs the running app to tune). **Reused-as-is, NOT touched (§2.2):** drag-to-reorder and the project rows' rename/context-menus — the slow-double-click rename unblock touches the rows, so it's a safe *separate* follow-up, not bundled into this nav/toolbar work.
