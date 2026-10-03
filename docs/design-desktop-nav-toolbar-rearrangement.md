# Desktop nav + toolbar rearrangement — UX spec

**Status:** Shipped (Phase 1), 22 Jun 2026 — the lens rail + rebuilt toolbar landed (`LensRail.swift` + the `ContentView.swift` toolbar; the centre tab `Picker` is gone). The planning voice below is now historical intent. **NB:** §2.2's "project list reused verbatim" premise was overtaken by the AppKit `NSOutlineView` sidebar rewrite (flag-gated, default-off today) — see `design-desktop-sidebar-appkit.md` and the §2.2 note. (Orig: Draft · Phase 1 · 21 Jun 2026, rev 2 — folded the `/usual-suspects` review + user decisions.)

**The mockup is the primary record of the UX logic** — `docs/mockups/desktop-toolbar-and-footer-options.html` carries every chosen and rejected option as a frame, with the reasons; this section mirrors it.

**Rev 3 — 3 Oct 2026 (decided, not yet built):** New Project / New Folder move to a `+⌄` in the sidebar's own toolbar (§3.3); the trailing toolbar is one actions capsule plus Search on its own (§4.3); Search becomes the native `.searchable` field (§4.4); §4.5 trued to the shipped title and per-lens subtitle. Visuals: `docs/mockups/desktop-toolbar-and-footer-options.html`.
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

The desktop app inherited the web report's **horizontal tab strip** (Project · Sessions · Quotes · Codebook · Analysis) and *used to render* it as a native segmented `Picker` in the toolbar centre. (Shipped 22 Jun: that Picker is removed; the lenses now live in the sidebar `LensRail` — `ContentView.swift:1469`.) That left **two navigation surfaces** competing: the tab strip across the top — always in the eyeline, *telling you what you already know* — and the project sidebar down the left, paying full width largely to switch projects. Things.app's lesson: **one sidebar carries both**, freeing the right pane to be *purely the report*.

## 2. The move (Phase 1)

Relocate the five tabs out of the toolbar **into the top of the sidebar** as a fixed "lenses" band; the scrollable project list sits below. The freed toolbar is rebuilt to the Tahoe toolbar HIG. **Native shell only — ~zero frontend change:** the lens rows fire the same `switchToTab` bridge call the `Picker` does today.

### 2.1 Platform fork
The SPA's `embedded` flag is the lever: **embedded** (in-app `WKWebView`) suppresses the web `NavBar`/`Header`/`Footer` the Swift shell supplies; **non-embedded** (CLI `serve` → browser) keeps them. Nothing here touches the browser/CLI experience.

### 2.2 Hard scope guard — the project list is reused, NOT rebuilt
**The existing left-hand project list (folders, drag-and-drop, reorder, rename, context menus, selection, the in-list New-Project row) is lifted and shifted VERBATIM from the current `ContentView.swift`. This work does NOT touch, refactor, or fix the drag-drop.** Its known bugs — drag-out-of-a-folder to top level; folder-to-folder project move — are *parked, out of scope*. The SwiftUI-`List` drag-drop failure has been forensically investigated more than once (the **"sidebar apocalypse"**, commit `7bf0e96` + the cross-linked drag-drop docs); **do not reopen it.** The real fix is a future AppKit `NSTableView`/`NSOutlineView` rewrite (or an upstream macOS fix) — a *separate* effort, now specced in `design-desktop-sidebar-appkit.md` (which also delivers the native source-list selection SwiftUI can't emit); we support Sequoia-up regardless. *"Anything but that."*

> **Superseded-at-cutover (22 Jun 2026):** that "future" AppKit rewrite shipped the *next day* (`ProjectSidebarOutline.swift`, `OutlineNode.swift`) and is now the **confirmed alpha default** (`design-desktop-sidebar-appkit.md` — cutover, not post-TF). It stays **flag-gated and default-off** for soak (`BristlenoseFlags.appKitSidebar`), so this section's verbatim-reuse path is still *literally* what ships today — but the SwiftUI `List` / `ProjectRow` / `SidebarDrop` it preserves are slated for deletion at cutover. Read this guard as "true for the flag-OFF build, superseded when the flag flips." The lens band itself did fold into that outline as real `.lens(Tab)` rows there (the one-List approach §3.1 ruled out for the SwiftUI build).

**Build hierarchy:**
1. **Drag-drop / folders / selection machinery → NEVER touched.** Reuse verbatim.
2. **The project `List` structurally → reused.** The lenses go in a **separate control *above* the `List`** (§3.1), never a section inside it — so the fragile `List` is never modified and the lens rail sidesteps the macOS-26 `List` gotchas (it isn't a `List`).
3. **Project-row presentation polish** (variable-height §3.2, outline `circle` §5, trailing-slot order) → *optional*, only as a trivial presentation delta on the existing row; if it would mean restructuring the row/`List`, **defer it.**

**Scope is exactly two things: relocate the tabs into the sidebar (as the separate lens rail), and rebuild the toolbar.** Nothing in the project list itself.

## 3. Sidebar

### 3.1 Selection model — a separate lens rail above an untouched project List
Per the §2.2 guard, the project `List` (its `@State Set<SidebarSelection>` selection, drag-drop, folders) is **reused untouched**. So the lenses are **not** a section inside it, and we do **not** add a `.lens(Tab)` case (that would modify the fragile List). Instead:

- **The lens band is its own control** — a fixed `VStack` (or small non-`List` rail) of five toggle-rows above the project list, with its own simple `@State activeLens` driving `switchToTab`. It is a *mode rail*, not a peer `List` selection; render it a deliberately *different, lighter* weight than a project row (accent-tinted symbol / medium-weight label — toolbar-toggle language) so a lit lens + a lit project never read as a stuck multi-select. Framing: *one project selection (the existing List) + one persistent mode (the rail)*. Bonus: the rail isn't a `List`, so it sidesteps the macOS-26 `List` gotchas entirely.
- **Empty state:** the rail is **dimmed/disabled until a project is selected** — the same affordance the old tab `Picker` gave via `.disabled(...)` — shipped as `LensRail(... isEnabled: selectedProject != nil && bridgeHandler.isReady)` (`ContentView.swift:1472`) — **superseded 1 Sep 2026** (`lens availability: document identity over prediction, one truth for every surface`): the rail no longer runs its own formula, it reads `LensAvailability` (`ContentView.swift:2448`), the same truth the AppKit lens rows and ⌘1–⌘5 use. `isReady` was the wrong signal — it is force-set 2 s after *any* load, status page included, so the two sidebars could disagree. The dimming *is* the "pick a project first" teaching. With zero projects, `WelcomeView.firstRun` owns the detail pane.
- *(The existing List is already a multi-`Set`, so a one-List `.lens(Tab)` approach is technically possible — but §2.2 rules it out: keep the List untouched. The separate rail is also what the review preferred.)*

### 3.2 Row anatomy — *absence is information*
Variable height, not the current always-reserved two-line band:
- **Idle row** → single tight line (icon · name · count). **Live row** → a second line appears *only* while there is status (run progress). Animate the height change — but **guard `@Environment(\.accessibilityReduceMotion)`** (instant resize when on), and **never reflow a row under an active pointer or during a drag-reorder** (spatial-stability: don't shove a row out from under the reader's cursor).
- **Title-line trailing order** (resolves the collision with the same-day-trued `design-project-sidebar.md` "Row anatomy"): the **session count** is the default occupant; the **storage/sync qualifier** (iCloud arrow, external-drive hint) *replaces* it when the project is unavailable/syncing. Precedence: in-flight scan > failure glyph > availability qualifier > count. The activity/copy ring keeps the *subtitle* trailing slot during runs.

### 3.3 Top controls + New — *rev 3, 3 Oct 2026*
**Decided (not yet built):** the sidebar's own toolbar carries two controls, NetNewsWire-style:
- **Sidebar show/hide (`sidebar.left`) beside the traffic lights — the system's, untouched.** `NavigationSplitView` already places it there on macOS 26/27, and `SidebarAutoCollapse` (`DetailFloor.swift`) plus `SidebarFitHarnessTests` drive it through AppKit's `toggleSidebar:`. Rev 3 does **not** place a toggle of its own; the earlier draft's "hide the system one and place ours" was withdrawn in the plan review (3 Oct 2026, Finding 38: a hand-placed toggle lives in the sidebar column and vanishes with it).
- **`+⌄` trailing in the sidebar's toolbar**, a plain menu of **New Project…** and **New Folder…** (the shipped `desktop.menu.file.newProject` / `newFolder` strings). The icon-only control's tooltip and VoiceOver label is **"Add"** (`desktop.toolbar.add`, decided 3 Oct 2026: one new key, each locale's value taken from Apple's own `Add`). Reusing "New Project…" (the menu also holds New Folder) or the panel prompt `chrome.addFilesPrompt` (couples two surfaces) was rejected. It takes the slot of the existing New Folder button (`folder.badge.plus`, `ContentView.swift:2743`, there since Phase 1): same `ToolbarItem(placement: .automatic)` on `projectList`, the `Button` swapped for a `Menu`. Nothing else moves. It goes away with the sidebar, as that button does; what happens at a narrow sidebar is whatever the system does with the slot (observed, not engineered). The shortcuts stay in the File menu: New Project ⌘N, New Folder ⇧⌘N.
- **The AppKit sidebar (flag-off) has no toolbar item today and gets none in rev 3** — adding one there means attaching `.toolbar` to the representable that carries the §1.4 top-edge fix (`design-desktop-sidebar-appkit.md`), untested; a follow-up for that sidebar's cutover.

**This replaces the rev-2 in-list `+ New project` row.** That row shipped grey (`.secondary`) and scrolled away with the list; the AppKit sidebar has no equivalent. Its removal is a separate commit, proven against the macOS-26 `Section` trap its comment names.

**Evidence:** in a user interview, a Windows user did not find New. She would not drag and drop, expected to create a project before giving it interviews, and did not explore the Mac menus.

**How the decision was reached, 3 Oct 2026** (all options drawn in the mockup). The conversation went B → C → D → E:
- **B, a labelled sidebar footer** (Notes, Reminders; Mail's `+ −` under a list) — proposed first; the HIG's warning about crucial controls at the bottom of a window was weighed against ⌘N and the Welcome window still existing. Set aside once E was chosen: its label repeats the New Project prompt the main area shows. *(That premise was corrected the same afternoon: since `399d5da1` the no-selection main window shows a drop-only card; B stays rejected on E's merits.)*
- **C, B plus Things' explaining menu** (a one-line description under New Project / New Folder) — rejected as too verbose; the user's problem was finding New, not telling a project from a folder.
- **D, B plus a Settings gear** (Things' sliders; Mail's `?`) — rejected: ⌘, and the app menu are where Settings lives on a Mac, and the Welcome AI cell covers day one. If a gear ever ships, use `gearshape`, not sliders: sliders mean "adjust this view". The owner's verdict on the B+C+D stack: "too apologetic".
- **E, the purist default** — NetNewsWire's `+⌄` in the sidebar's toolbar, chosen; **plain menu, not `Menu(primaryAction:)`**, so a click reveals New Folder (decided later the same day).

**Click behaviour — decided 3 Oct 2026:** a plain `Menu`, as in NetNewsWire. A click opens New Project… / New Folder…, which makes New Folder discoverable rather than hidden behind a chevron. **Still open (build check):** the toolbar placement inside the AppKit sidebar, which is hosted differently.

**Related — the empty project gets a button, decided 3 Oct 2026.** After New Project, the detail pane (`dragInterviewsPane`) says "Drag Interviews Here" and offers no button, a dead end for anyone who doesn't drag. It gains a primary **Choose Interviews…** button: one new locale key, in the 21 full locales. The button opens a picker that accepts files and folders. Today's `addFilesToSelectedProject` takes files only, so the button needs a picker that also accepts directories. Dropping still works. The pane's title and description are unchanged.

New Folder also stays in the list's right-click menu.

## 4. Toolbar

### 4.1 Action inventory → homes
| Action (symbol) | Today | New home |
|---|---|---|
| 5-tab picker | centre `.principal` | **→ sidebar** (the lenses) |
| Back / Forward (`chevron.backward/forward`) | leading | **content leading** — grouped pair |
| Sidebar toggle (`sidebar.left`) | auto | ~~sidebar top-trailing~~ → **against the traffic lights** (§3.3, rev 3) |
| Left panel: Contents/Codes/Signals (`list.bullet`) | leading | **inspector toggle** · Quotes·Codebook·Analysis |
| Tags (`sidebar.right`) | trailing | **inspector toggle** · Quotes |
| Heatmap (`square.grid.2x2`) | trailing | **inspector toggle** · Analysis |
| **Export (`square.and.arrow.up`)** | trailing | **visible trailing menu** — see §4.2 |
| Search (`magnifyingglass`) | trailing | **trailing — rightmost** (see §4.4) |
| Ollama pill (custom) | `.status` | **`.status`** — unchanged |
| New Project / New Folder | sidebar bar / File menu | ~~in-list `+` row~~ → **`+⌄` in the sidebar's toolbar + File menu** (§3.3, rev 3) |

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

### 4.3 Grouping & responsive collapse — *rev 3, 3 Oct 2026*
**Leading, unchanged:** the lens's left-panel toggle (`list.bullet`) near the left web panel, then the back/forward group with its current behaviour, then title + subtitle.

**Trailing: one actions capsule, then Search on its own.**
- **The actions capsule, as today:** Export first, then the lens's own buttons. Quotes: Export · Starred · Tags. Codebook: Export · Library. Signals: Export · Heatmap. Project and Sessions: Export alone.
- **Search is always the rightmost item, on its own.** In a wide window it has room for a real input field; in a narrow window it is still its own control, and focusing it expands it there. Multi-lens search is next, so search's prominence will only grow.

The tag inspector keeps `sidebar.right`, deliberately not a tag glyph, because the Codebook lens owns `tag`.

**Narrow windows:** rely on the system overflow; never hand-roll a More menu. The actions capsule folds into the `»` chevron, Export included, since it is part of the capsule, until the capsule is just `»`. Search stays: it shrinks to a magnifier button on its own and expands in place when focused.

### 4.4 Search — *rev 3, 3 Oct 2026*
**Native `.searchable` was decided in the morning and REJECTED in the afternoon, by measurement.** A spike attached it to the detail column (a zero-size carrier in `.background`, so the detail's type never changed). It placed the field correctly, never remounted the web view, and gave the **detail column a hard minimum width** — 938 pt, the window's width at the moment the projects column collapsed — which `NSSplitView` honoured by overflow: the projects column pushed off the window's left edge, exactly the failure `DetailFloor` exists to prevent (`docs/sidebar-column-diagnosis.md`). `main` at the same widths was clean. The field's placement is a contract with the split view we cannot see or override, so **`.searchable` is not used on the detail column**, now or later.

**What ships instead (built and measured 3 Oct 2026):** the existing `QuotesSearchToolbarControl` (magnifier → expanding field), moved out of the actions capsule into its own glass at the far right (`ToolbarSpacer(.fixed)` on macOS 26+; together on 15), with its grey `.quaternary` fill removed so the system glass is the only chrome, the clear button always laid out (adding it on the first character widened the item), and shown on all four searchable lenses (inert off Quotes). Toolbar-only; no column geometry is touched — traced against `main` at 1198→700 pt with Tags open, `webW` tracking the window throughout.

**When the toolbar is tight — the least-worst we can get without `NSToolbar`, decided 3 Oct 2026.** Apple's rule (`NSToolbarItem.visibilityPriority` docs): lower-priority items go to `»` first, equal priorities from the trailing edge. SwiftUI gives every item the same priority and no API to change it, so search — the trailing item — folded first. `ToolbarItemPriority` (`QuotesToolbarControls.swift`) is targeted AppKit surgery: a zero-size probe finds its own `NSToolbarItem` in the window's toolbar and sets `visibilityPriority = .user` ("pushed to the overflow menu last"), re-applied on every resize and toolbar rebuild. Result: the actions capsule folds into `»` first and the open field stays, as Photos does. **The one deviation from Photos and NetNewsWire: the chevron sits at the trailing edge and search before it.** Both of those apps are AppKit toolbars with an `NSSearchToolbarItem` (verified: NetNewsWire `MainWindowController.swift:960`; Photos' binary imports `_OBJC_CLASS_$_NSSearchToolbarItem`), and AppKit places that item class after the chevron and collapses it to a button itself. SwiftUI reaches it only through `.searchable`, rejected above. Tried and rejected the same afternoon: a width threshold that swapped the item for a magnifier + popover (too early on lenses with one action, and popovers are not the idiom); `.status` placement (it is the toolbar's centre on macOS 26 and folds into `»` with the magnifier inoperable inside a menu). **Banked for later, not now:** owning the toolbar as an `NSToolbar` + `NSSearchToolbarItem` + `NSTrackingSeparatorToolbarItem` — option F in `docs/sidebar-column-diagnosis.md`, which also costs it. The original native-field rationale follows, kept because it still describes the look being aimed at:
- **The look.** Today's capsule draws its own `.quaternary` fill, and macOS 26 wraps it in the shared glass capsule with Export and the lens buttons, so it reads as a dirty grey pill inside a glass pill. The system field is the clean, light glass that NetNewsWire and Photos get, and it picks up whatever sits behind it.
- **The behaviour.** The native field collapses to a magnifier and expands when focused — the hand-rolled control already does this.

The wiring stays as it is today:
- typing is debounced 150 ms, then sent with `setQuotesSearch`;
- a query pushed from the store is mirrored into the field;
- ⌘F focuses the field (`requestSearchFocus`).

**By lens, today:**
- **Quotes:** live.
- **Sessions, Codebook, Signals:** the control is present but does not respond yet, and its placeholder stays "Search". This replaces the disabled `SearchComingSoonButton`; the owner accepted it on 3 Oct 2026 because multi-lens search is next. An interim placeholder ("Search isn't available in this view yet", the deleted button's tooltip) was proposed in the plan review and **rejected the same day**: alpha, no interim redesign. Only `desktop.toolbar.searchComingSoon` loses its reader and is deleted (`searchClear` stays read by the control).
- **Project:** no search, unchanged. It gets one when project-wide search (⌥⌘F) ships.

### 4.5 Title — *trued 3 Oct 2026*
The project name is `.navigationTitle` and the subtitle is `.navigationSubtitle`, both on the detail column. The custom `.navigation` title `ToolbarItem` and `WindowTitleManager` described here in rev 2 were removed on 23 Jun 2026; having both was what produced the duplicate title. The subtitle is already per lens: the SPA sends each lens's subtitle over the bridge (`lensSubtitle`), and Sessions computes its own count. An in-flight run outranks the subtitle, and a name clash prefixes the folder (`WindowSubtitle.swift`). Rev 3 changes nothing here.

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
1. ~~Native search migration~~ — **decided 3 Oct 2026, then reversed by the spike the same day: NOT `.searchable`; the existing control, own capsule, no grey fill** (§4.4).
2. ~~The `+⌄` click behaviour~~ — **decided: a plain menu** (§3.3). Its placement inside the AppKit sidebar is a build check.
3. ~~The empty project's button~~ — **decided: Choose Interviews…**, with a picker that accepts files and folders (§3.3).

**Decided (rev 3, 3 Oct 2026):**
- New Project / New Folder live in a `+⌄` in the sidebar's toolbar, with the sidebar toggle against the traffic lights (§3.3).
- The trailing toolbar is one actions capsule, with Export first, then Search on its own at the far right (§4.3).
- Search is the existing control in its own capsule, grey fill removed; native `.searchable` was spiked and rejected the same day — it gives the detail column a minimum width (§4.4).

**Decided (rev 2):** floor **Sequoia 15.0** for coverage + adopt-latest-with-graceful-degradation (§0); Export = visible toolbar menu, Rename/Move/Show → context menu + menu bar not the toolbar (§4.2); inspectors = **spatial split**, tag inspector keeps `sidebar.right` (§4.3); New Project = in-list `+` row + `⌘N` (§3.3); Sessions = `person.2`, **Project = `target` kept** (rings echo the project-row `circle` — "the circle come alive") (§5); selection = separate `LensRail` (lens-as-mode), the `List` left untouched, dimmed-until-project (§3.1 — the SwiftUI build deliberately does *not* add a `.lens(Tab)` case; that one-List fold happened later in the AppKit `NSOutlineView` rewrite). **Parked:** the `3×3`/`2×2` grid-density clash (heatmap feature + icon need redesign).

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
