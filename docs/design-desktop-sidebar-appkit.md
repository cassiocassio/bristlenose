# Desktop sidebar — native AppKit source list (`NSOutlineView`)

**Status:** Active · **Alpha / TestFlight** — AppKit ships behind the opt-in `BristlenoseAppKitSidebar` flag, **default-off** through soak (the SwiftUI `List` is still the live default). The cutover — AppKit → default, SwiftUI path deleted — is the **confirmed direction** (22 Jun, supersedes the original Post-TestFlight scoping) but **not yet done**. · updated 23 Jun 2026
**Extends / closes:** `design-desktop-nav-toolbar-rearrangement.md` §2.2 (the parked "AppKit `NSOutlineView` rewrite") · the drag-drop "sidebar apocalypse" forensic (commit `7bf0e96`; gitignored handoff notes)
**Scope:** the macOS desktop **sidebar** — the project list **and** the lens rail (folded into the same `NSOutlineView` as group rows, §3.1). The toolbar (nav/toolbar spec) is untouched. **This is a framework switch, not a redesign:** every existing affordance is rescued verbatim — no UX is rethought.

**Shipped since (23 Jun 2026, `mac-app-layout-reorg`).** The body below predates these commits — its `*.swift:NN` line refs trail (the file grew ~40–130 lines), but the architecture in §2.5 / §3.1 / §6 is still accurate verbatim. What landed:

- **Cell port (Phase 4) complete** — `ProjectRow` ported to an AppKit cell verbatim (`28dae0d`, `52768b1`).
- **Context menus** (project + folder) shipped via `NSMenuDelegate.menuNeedsUpdate` per `clickedRow` — **not** the speculative `menu(for:)` §2.2/§6 anticipated. Project menu is conditional (Stop Analysis · Cancel Copy · Show Diagnostics · Locate, all state-gated · Show in Finder · Choose Icon · Move to → · Remove from Sidebar); folder menu is **2** items (Archive disabled · Delete). §6's "when menus land" is now closed (`96c31eb`).
- **Inline rename DEFERRED** — listed below as Phase-A parity, but explicitly not built this pass (`ProjectSidebarOutline.swift` header records the deferral).
- Failure/partial glyph → clickable `DiagnosticGlyphButton` (opens the diagnostic popover); default project icon `circle.fill` → open `circle` (`4e0c584`); Finder folder-of-videos drops wired via `SidebarExternalDrop` (3 cases — root/folder/project; empty-area folds to root, not a 4th case).

---

## 0. Why this exists

The nav/toolbar rearrangement shipped the sidebar lens rail + rebuilt toolbar. Visual QA against Mail / Photos / Notes / Finder surfaced that **neither** our SwiftUI lens rail **nor** our SwiftUI project `List` matches the native macOS **source-list** selection: a neutral grey ground with the selected row's icon **and** text tinted to the accent, *focus-stable* (it doesn't flip to a saturated accent fill when the table loses first-responder).

That look is **structurally unreachable from pure SwiftUI.** `List(selection:)` can only emit the *emphasized* table selection — a vivid accent fill with white content that flips vivid↔grey on focus. There is no public SwiftUI knob for `NSTableView.selectionHighlightStyle = .sourceList`.

Apple's own flagship apps keep their sidebars in **AppKit `NSOutlineView`** for exactly this reason. Verified this session: Notes / Photos / Finder all link `AppKit.framework` directly (not Catalyst — Maps is the Catalyst contrast, its SwiftUI coming from `/System/iOSSupport/`); all *also* link SwiftUI (so linkage alone proves nothing), but the **behavioural** proof is dispositive — source-list selection is AppKit-only, our SwiftUI `List` shows the emphasized style (the contrapositive), and Notes/Photos don't flip on focus. Their sidebars are `NSOutlineView`. Both apps predate SwiftUI (2012 / 2015).

**Posture (nav spec §0):** *"99% SwiftUI… targeted AppKit surgery where SwiftUI genuinely can't deliver — the exception, not a retreat."* This is that exception, earned by a visible defect on a flagship surface. **Bonus:** the same migration subsumes the long-parked drag-drop "sidebar apocalypse" — one `NSOutlineView` buys both the source-list look *and* the unified insertion model that fixes out-of-folder / between-folder drag.

---

## 1. The benchmark — the macOS source list (what we're matching)

> The whole look is produced by one switch: `NSOutlineView.selectionHighlightStyle = .sourceList`, inside an `NSScrollView`, in the `NavigationSplitView` sidebar column. Everything below falls out of that + `NSTableCellView` cells + `rowSizeStyle = .default`. **The spec rule throughout: these are system-drawn — we do not set colours, metrics, or selection fills.**

### 1.1 Selection
- **Ground:** neutral grey / translucent rounded-rect behind the selected row — *not* an accent fill. Drawn by `NSTableRowView`.
- **Content:** the selected row's **icon** tints to the user's accent colour; the **label** takes the system's selected-content colour (a high-contrast neutral), **not** accent. *(Don't chase accent-coloured text — forcing it fights the `backgroundStyle` behaviour we came for. Verify the exact tint against the live SDK on a real `NSOutlineView`.)*
- **Focus-stable** — the differentiator vs SwiftUI:
  - Window key **+** table first responder → full accent tint on content; grey ground at full strength.
  - Window key, focus **elsewhere** (e.g. the web report pane) → **persists** — grey ground + accent content largely unchanged. *(SwiftUI's emphasized selection de-emphasizes here; that's the bug.)*
  - Window **not** key → ground desaturates to a quiet grey, accent softens. System-drawn — don't fight it.
- **Rule:** selection colour is *system state*, never a colour we own (`feedback_state_via_semantic_colour_emphasis_via_neutral_ladder`; HIG color §App-accent-colors). The exact `NSColor` resolution is system-internal — **do not hardcode constants.**

### 1.2 Spacing · alignment · the icon column
- **Uniform icon column** — every row's icon occupies the same leading column; labels align regardless of glyph width. *(This is today's wonky-alignment bug — `person.2` shoving "Sessions" right — gone for free with a cell template.)*
- **Row size tracks General ▸ Sidebar icon size** (Small / Medium / Large): row height, glyph size, text size all follow the system setting. Keeps `macos-ux-checklist.md`'s "row-height follows icon-size ✓" true after the rewrite.
- Metrics (row height ≈24pt medium, icon ≈16pt, icon→text gap, leading inset) are **system-provided — we do not set them.**
- **Free native behaviours the SwiftUI `List` lacked, all system-drawn — retired from our code:** **type-to-select** ("ik" → IKEA — the headline win), **keyboard expand/collapse** (←/→ on folders) + arrow nav, **no row separators** (hairlines read as "settings table"), **per-level icon-column alignment** (`indentationPerLevel` — code sets 14pt, `ProjectSidebarOutline.swift:108`), **right-click highlight ring**, **select-all-on-rename**, and the **blue insertion-line** drop affordance (which *deletes* today's hand-drawn `RoundedRectangle.stroke` highlight).

### 1.3 Structure
- **Multi-group source list** (Finder-style): a **lenses** group (the 5 mode rows, §3.1) · a **"Projects"** group (mixed case, Finder-style — *not* all-caps) holding project + folder rows · **built for more groups** (more headers are coming). ≤2 levels of project hierarchy (HIG); one folder level today, deeper nesting becomes free.
  - **Future (user, 22 Jun — "one day"): a bottom-pinned "Archive" / "Trash" group**, always last regardless of `position`. This is the Notes "Recently Deleted" / Mail Trash *destination* pattern — a row you navigate **to** — which is native and **distinct** from the deprecated bottom +/−/gear *action* strip (`feedback_no_bottom_of_sidebar_actions`); the ban is on bottom *actions*, not bottom *destinations*. Open choice for that day: **Archive** (keep-but-hidden) vs **Trash** (delete-with-grace-period) — two different concepts, pick then. The multi-group structure accommodates it cheaply.
- **Native disclosure triangles**; **floating/pinned group headers** (`floatsGroupRows = true`).

### 1.4 Material / glass (macOS 26)
- The sidebar glass/vibrancy is owned by the `NavigationSplitView` sidebar column; the AppKit content renders *into* it. **We add no `NSVisualEffectView`** (double material = wrong). Standard system components adopt the material automatically (HIG materials). **But the column's glass is not *quite* free:** the one material thing we *do* set is a **removal** — `scrollView.drawsBackground = false` + clear `NSOutlineView` background — or the scroll/table's default opaque `controlBackgroundColor` paints a slab over the column's vibrancy (the opposite failure from double-material, equally wrong). QA under **Reduce-Transparency** specifically. Selection / groups / disclosure / row-sizing are all **floor-level (Sequoia 15)**; only the surrounding glass is 26-era — `#available`-gate chrome only, per the nav spec meta-rule.

---

## 2. The least-bespoke AppKit recipe

```
NavigationSplitView { ProjectSidebarOutline() } detail: { … }

struct ProjectSidebarOutline: NSViewControllerRepresentable {  // controller, not view — real lifecycle
    func makeNSViewController(context:) -> SidebarOutlineController
    func updateNSViewController(_:context:)                     // push model snapshot + @Binding in
    // the controller IS the dataSource + delegate (no separate Coordinator)
}

// Inside the controller:
NSScrollView(hasVerticalScroller: true)
└─ NSOutlineView
     selectionHighlightStyle = .sourceList   // ← buys the whole look
     style = .automatic                        // resolves to source-list in a sidebar; `.sourceList` enum case is soft-deprecated — verify vs live SDK
     floatsGroupRows = true                     // pinned headers
     rowSizeStyle = .default                     // tracks the icon-size setting
     headerView = nil                            // sidebars have no column header
     allowsMultipleSelection = true              // preserve today's Cmd/Shift multi-select
```

`NSViewControllerRepresentable` (not `…ViewRepresentable`) — the outline owns real lifecycle: scroll view, data-source/delegate objects, menu + first-responder wiring. The controller (itself the dataSource + delegate — **no separate Coordinator**) reports user selection out via the `@Binding`; selection state + restore stay in SwiftUI (§2.5).

### 2.1 What AppKit draws — DO NOT reimplement
| Behaviour | Mechanism |
|---|---|
| Grey selection ground + focus-stability | `selectionHighlightStyle = .sourceList` |
| Accent tint of selected **icon** (label takes system selected-content colour, not accent) | `NSTableRowView` sets `backgroundStyle` → `NSTableCellView` forwards to its `imageView`/`textField` (automatic) |
| Row height / glyph / text tracking the icon-size setting | `rowSizeStyle = .default` |
| Disclosure triangles | native `NSOutlineView` |
| Group-row styling ("Projects" header) | delegate `isGroupItem` + a plain `NSTextField` cell (system applies group attributes) |
| Floating/pinned headers | `floatsGroupRows = true` |
| Sidebar vibrancy / glass | the `NavigationSplitView` sidebar column |

### 2.2 What we must provide (unavoidable content)
- **Data source** — `numberOfChildrenOfItem` / `child:ofItem:` / `isItemExpandable`.
- **Delegate `viewFor:`** — a configured `NSTableCellView` per row (set `imageView.image`, `textField.stringValue`).
- **Selection bridge** (the controller) — push user selection out by writing the `@Binding` (`onSelectionChange`); render external/programmatic selection in via `applySelection` (§2.5).
- **Drag / drop + reorder** — `NSOutlineViewDataSource` pasteboard methods. *This is also the apocalypse fix (§3.3 Phase B).*
- **Context menu** (`NSMenu` via `menu(for:)`) + **inline rename** (editable `textField`).

### 2.3 Over-bespoke traps — the scope fence
1. **The one rule: use `NSTableCellView`, never a bare `NSView` cell.** The moment you abandon it you lose automatic `backgroundStyle` forwarding and must hand-write accent-tinting + selected-text colour — *exactly the system behaviour we switched to AppKit to get.* Extra content (trailing status glyph) → **subclass** `NSTableCellView`, add outlets; never replace it.
2. **Don't hardcode `rowHeight`** — breaks icon-size tracking. Use `rowSizeStyle = .default`.
3. **Don't add an `NSVisualEffectView`** — the column supplies the material.
4. **Don't draw a custom selection fill or disclosure triangle** — both native.
5. **Don't build a custom group-header view** — a plain string cell gets group styling automatically.
6. **Trailing status stays plain AppKit (`NSImageView` + `NSProgressIndicator`) — never an `NSHostingView` of the SwiftUI indicator.** Hosting a SwiftUI island in the cell re-introduces the cell-reuse + `backgroundStyle`-forwarding + popover-anchoring problems the whole migration exists to escape (trap #1, one level down). The cell carries **two image views with opposite tint policies**: the leading identity `imageView` *inherits* accent via `backgroundStyle`; the trailing status glyph sets `contentTintColor` *explicitly* to its semantic colour. `backgroundStyle didSet` is hand-implemented **per-subview** — the "automatic forwarding" (§2.1) only covers the standard `imageView`/`textField`, not the rich subviews.

### 2.4 The cell — bn.app's row on `NSTableCellView`
`ProjectRow`'s content becomes an `NSTableCellView` subclass:
- `imageView` (leading identity icon; `contentTintColor = nil` → **inherits accent via `backgroundStyle`**; SF Symbol via `NSImage(systemSymbolName:)` + a **scale-based** `NSImageSymbolConfiguration` so the glyph rides row size — never an absolute `pointSize`).
- `textField` (project name; editable for inline rename).
- **Extra subviews** (the rich content): trailing **session count**; the **activity indicator** (running spinner / copy determinate ring / failure glyph → diagnostic popover); the **subtitle line** (`ProjectSubtitle.resolve`, kept as a pure testable helper); the **availability / iCloud qualifier**.
- **Trailing status slot sets `contentTintColor` explicitly** to its semantic state colour (it must *not* inherit accent) — the `leading = identity / trailing = state` row-anatomy rule (`feedback_sidebar_row_anatomy`).

### 2.5 Selection funnel + reload contract — the spine (read before §3.4)

> **The load-bearing asymmetry — and how Phase A sidestepped it.** SwiftUI's `List(selection:)` is a *value binding* — assigning to it **is** the side-effect channel, so serve-switch / persist / bridge ride it for free, for programmatic writes *and* user clicks alike. A raw `NSOutlineView` has **no binding** (`outlineViewSelectionDidChange(_:)` fires on user clicks but **not** on `selectRowIndexes(_:)`). The original plan in this section was to rebuild that side-effect channel by hand in AppKit; **what shipped keeps the SwiftUI binding instead.** Selection STATE stays in a SwiftUI `@Binding var selection` (`ProjectSidebarOutline.swift:22`); the controller only *renders* it and *reports* user changes back. So the existing serve/persist/consent wiring (`ContentView.applySelectionChange`, `:365-370,572-632`) is **reused untouched**, and the programmatic-selection trap is sidestepped, not paid (`ProjectSidebarOutline.swift:5-9`).

**Item identity (the foundation).** `Project`/`Folder` are value types; `NSOutlineView` holds items **by reference**, and `@Published var projects` is wholesale-reassigned on every `save()`. Feed `Project` values directly → the outline drops selection and collapses folders on every mutation. **A UUID-keyed reference node** (`final class OutlineNode` with `isEqual`/`hash` off a stable `id` string keyed on the model UUID — `OutlineNode.swift:35-49`) makes identity survive array swaps — the AppKit manifestation of the `Identifiable`/UUID-stability the SwiftUI `List` got free. Foundation, not refinement.

**The funnel IS the binding.** Two directions, both through `@Binding var selection`:
- **User click →** `outlineViewSelectionDidChange` builds the `SidebarSelection` set from `selectedRowIndexes` (lens/group rows map to `nil`, filtered out) and calls `onSelectionChange`, which writes the binding (`ProjectSidebarOutline.swift:346-361`, closure set at `:42-44`). SwiftUI then fires `.onChange(of: selection)` → `ContentView.applySelectionChange` → the existing ordered side-effects (`bridgeHandler.reset()` → sole-selection branch → `persistedProjectID` → `updateLastOpened` → **consent+availability gate** → `switchProject`, single `switchTask`+`generation` discipline, `ContentView.swift:572-632`).
- **Programmatic →** set the binding; SwiftUI pushes it in via `updateNSViewController` → `applySelection`, which wraps `selectRowIndexes` in `isApplyingProgrammatic = true` (`:158-160`) so the delegate's echo is suppressed (the `outlineViewSelectionDidChange` guard, `:347`).

- **Re-entrancy guard (`isApplyingProgrammatic`) is mandatory** — without it `selectRowIndexes` re-enters the delegate → loop / double serve-start.
- **No "~15 programmatic sites to enumerate" gate** (the original plan here) — because state lives in the binding, every `selection =` site (new-project, drop-onto-existing, undo-restore, locate-success, context-menu navigate, deselect-to-empty) already rides `.onChange` exactly as under the SwiftUI `List`. That is the *point* of keeping the binding: the BUG-3 "highlights but serves nothing" class can't reappear per-site, because no site writes the outline directly.
- **Consent+availability gate stays in `applySelectionChange`** (co-located with `switchProject`), **never** in `shouldSelectItem` — that delegate only reports selectability (`:216-230`, see its DEAD-END note).

**`@AppStorage("selectedProjectID")` restore** is the existing SwiftUI `.onAppear` path (`ContentView.swift:396-402`), gated `selection.isEmpty && projects.contains(id)` with the stale-deleted-ID guard — unchanged by this migration (it writes the binding; the outline renders it). No AppKit `hasRestored`-after-`reloadData` dance was needed.

**Reload contract — Phase A is deliberately blunt.** `update()` calls full `reloadData()` on **every** model push (`ProjectSidebarOutline.swift:130`), then re-expands groups/folders and re-applies selection. Simple and correct; the cost is churn (§6 "Deferred: `reloadData` on every `update`"). The targeted-`reloadItem` contract below is the **Phase-B-or-later optimisation, not shipped:**

| Mutation / live signal | Targeted reload (future) |
|---|---|
| rename | `reloadItem(node)` |
| move project | `reloadItem(oldParent, reloadChildren: true)` + new parent |
| remove / restore | animated `removeItems`/`insertItems`, else `reloadData()` (avoid dangling-item crash) |
| live `unanalysed` / `pipelineRunner.state` / copy fraction | sink → `reloadItem(node(forProjectID:))` — else the activity ring freezes + count goes stale (the WAL count-blank class) |
| folder collapse | `autosaveExpandedItems` + `autosaveName`, else manual `folder.collapsed` |

---

## 3. Scope, phasing, what stays

### 3.1 The lens rail — folded into the outline as group rows (DECIDED 22 Jun)
The 5 lenses become **non-selectable rows in the same `NSOutlineView`** — a group at the top, above the "Projects" group. They fire `switchToTab` (mode); they do **not** join the project selection set. One real source list, no SwiftUI/AppKit seam. The active lens shows the source-list selected-state **system-drawn** — it's kept genuinely in the table's `selectedRowIndexes` (`applySelection` + `selectionIndexesForProposedSelection`) but carries no `SidebarSelection` (lens nodes return `nil`, filtered in `outlineViewSelectionDidChange`, so **serve never sees it**), so the table renders its capsule **identically** to a selected project — exact colour / margin / radius. The selection colour is internal to the table and matches **no public UI-element-colour token** (verified 22 Jun by sampling every token via a throwaway probe, not retained), which is *why* genuine selection, not a hand-placed capsule, is the only exact path (the earlier flat-fill / `NSVisualEffectView` attempts are retired). Mode-vs-selection is the orthogonal split: lens rows switch mode (and are **dimmed + inert when no report is showing** — `lensesEnabled`, restoring the old LensRail's `isEnabled` gating), project rows drive serve.
  - **Future enhancement (user, 22 Jun — post-TF): remember per-project view state.** Switching projects loads the new report at its overview route, so the lens resets to **Project** each time (fine for TF). Post-TF: remember **each project's last-selected lens** *and* **the scroll position within each lens**, so returning to a project restores exactly where you were (per-project × per-lens state). Ties into the retained-WebView work (`design-desktop-switch-performance.md` Phase C). The outline is a multi-group source list (lenses · Projects · future groups, §1.3). The `VStack`-not-a-`List` constraint that previously forced the rail out of the list is **removed by this migration** (the positional finders retire, §3.2).

### 3.2 The project list — the migration
SwiftUI `List` + `ProjectRow` + `FolderRow` + `SidebarDrop` + the `DisclosureGroup`s + the two positional-`NSTableView` finders (`SidebarDeselectMonitor`, `focusProjectsList`) → **one `NSOutlineView` source list.**

### 3.3 Phasing — A & B together (DECIDED 22 Jun)
The whole migration in one effort:
- **Phase A — parity.** Replace the project `List` with the `NSOutlineView`, rescuing **every** current affordance verbatim (§3.4) — project icons, right-click menu, folders, rename, pickable icons, status line, progress ring, copy indicator, multi-select. Retire the two positional finders. The rich cell content is the bulk of the work.
- **Phase B — drag, working.** The unified `NSOutlineViewDataSource` insertion-point model so drag **between folders and to the top level** actually works (the currently-broken "apocalypse" cases — a *required* outcome, not a bonus). The data source written for A *is* the drag model, so it's built once. Gated by the `DropRouting.resolve(...)` table test (§5).
  - **Within-scope manual reorder (`toIndex`) — DEFERRED future enhancement (user, 22 Jun).** Dragging a project/folder to a new *position* within its scope, with the other rows **animating into place, Finder-style**. Today sort order is the `position` Int (ascending; root projects+folders interleaved, children by position; auto-assigned at creation, back-filled from `createdAt`), and it's effectively **fixed at creation** — `DropRouting` computes `toIndex` (unit-tested) but `acceptDrop` wires only `toFolder`, `moveProject` leaves `position` untouched, and the SwiftUI `.onMove` reorder was not ported. To deliver: renumber `position` on drop + animated `moveItem(at:to:)` on the outline. **Not in the parity push** — explicit user-requested enhancement, noted for later.
- The lenses ride the **same** outline (§3.1) — no separate rail.

### 3.4 Integration mapping — every behaviour → AppKit equivalent
*(Source: the full sidebar inventory. This table is the Phase-A acceptance checklist. The spine rows — selection→serve, restore, live indicators — point at §2.5: Phase A **keeps the SwiftUI selection binding**, so the existing `applySelectionChange` / `.onAppear` wiring is reused and most "unchanged" cells genuinely hold. "Coordinator" below = the controller; "funnel" = the binding's `.onChange`.)*

| Current (SwiftUI) | file:line | AppKit equivalent |
|---|---|---|
| `@State selection: Set<SidebarSelection>` + `List(selection:)` | `ContentView.swift:164,1434` | `NSOutlineView` selection ↔ controller, written back to the **same `@Binding`** → `Set<SidebarSelection>` |
| Multi-select (Cmd/Shift) | native | `allowsMultipleSelection = true` |
| Selection → serve start/switch/stop + consent gate | `ContentView.swift:572-632` | **reused unchanged** — the binding's `.onChange` → `applySelectionChange` (§2.5); no per-site rewiring |
| `@AppStorage("selectedProjectID")` restore | `:159,398-402` | **reused unchanged** — existing `.onAppear` restore writes the binding; the outline renders it (§2.5). No AppKit `hasRestored` dance |
| `selectedProject`/`soleSelection` derivations | `:228-238` | **unchanged** (pure computed) |
| `ProjectRow` content (icon/name/count/subtitle/activity/copy/availability) | `ProjectRow.swift:82-244` | `NSTableCellView` subclass (§2.4); `ProjectSubtitle.resolve` stays pure |
| `FolderRow` (collapsible, rename) | `FolderRow.swift:9-78` | outline item + native disclosure; editable `textField` |
| Inline rename (project/folder) | `:171`, `FolderRow:22-44` | editable `textField`, Return commits / Esc cancels / blur commits |
| Context menu (8 project / 3 folder items, conditional visibility) | `ContentView.swift:1570-1851` | `NSMenu` built per clicked row; same conditional items |
| 11 menu/undo notifications (`.createNewProject`…`.focusProjects`) | `:446-485,1959+` | drive the controller; **undo-restore writes the `selection` binding** → the outline renders it (§2.5) |
| Finder-file drops on rows / empty | `:1485,1549,1767` | `NSOutlineViewDataSource` pasteboard (validateDrop/acceptDrop) |
| Internal project drag → folder; root + per-folder reorder | `:1457,1522,SidebarDrop.swift` | unified insertion model (Phase B fixes the gaps) |
| Empty-click deselect (`SidebarDeselectMonitor`) | `:36-80` | **native** — monitor retired; but **keep the deselect → §2.5 funnel → `serveManager.stop()` side effect** (verify auto-deselect on both floors) |
| ⌘0 focus (`focusProjectsList`, positional finder) | `:247-259` | `makeFirstResponder(outlineView)` directly — **no positional finder** |
| Folder collapse state (`folder.collapsed`) | `ProjectIndex` | `outlineView(shouldExpandItem:)` + persist on expand/collapse |
| Activity / copy / failure indicators, session-count refresh | `ProjectRow*`, `:1779+` | **future (only session-count shipped)** — Phase A reloads via full `reloadData()`; the §2.5 targeted-`reloadItem` contract is the later optimisation. In-row **buttons** re-target to controller callbacks — a dead glyph = no failure cause |
| Icon-picker + diagnostic **popovers** | `:1821-1863,400-408` | anchored to the row via the **controller** (`NSPopover.show(relativeTo:of:)`), torn down on reload — NOT welded to a recycled cell |
| Cmd+Delete remove + plain-Delete reserved | `MenuCommands.swift:470,552` | the outline becomes a new first responder — decide responder vs menu-notification routing; keep plain Delete free (`feedback_delete_key_layering`) |
| Type-to-select ("ik" → IKEA) | — | **free native win** the SwiftUI `List` lacked — `textField.stringValue` makes it work; acceptance check |
| New-Project affordance | `:1439-1445` | stays in-list / `⌘N` / menu — **must NOT become a pinned bottom outline row** (`feedback_no_bottom_of_sidebar_actions`) |
| Multi-select → serve teardown (if kept — Q5) | `:622-631` | bridge emits the same `Set<SidebarSelection>` shape on Cmd/Shift-click so the stop-serve default arm fires |

---

## 4. Decided (22 Jun 2026 — settled; do not relitigate)
1. **Lens rail → real AppKit group rows in the same outline** (§3.1). Not a separate SwiftUI control.
2. **Group header → "Projects" (mixed case, Finder-style)** — and the outline is built for **multiple group headers** (more are coming, §1.3).
3. **Phasing → A & B together** (§3.3). One migration; drag between folders + to the top level must work.
4. **Cell → verbatim port.** Rescue **every** existing affordance (project icons · right-click menu · folders · rename · drag between folders + to top level · pickable icons · status line · progress ring · copy indicator). **No redesign, no simplification** — framework switch only.
5. **Multi-select → kept** (existing functionality; verbatim rescue).
6. **Drag vocabulary → native `NSPasteboard` UTTypes** (the migration removes the other SwiftUI drag sites; idiom call, no user-visible difference).
7. **Cutover → AppKit becomes the default for alpha/TestFlight** (22 Jun — *not* deferred to post-TF; supersedes the header's original scoping). The flag stays an escape hatch through soak; the SwiftUI sidebar (`List` / `ProjectRow` / `FolderRow` / `SidebarDrop` / `SidebarDeselectMonitor` / `focusProjectsList`) is deleted at cutover. "Forward to the finish line — not going back to SwiftUI."

## 5. Test strategy
The project's rule fits — but the pure mappings below **cover none of the §2.5 silent failures** (a round-trip test asserting indexes↔set passes whether or not the funnel fired serve). So the gate is two tiers:

**Pure helpers (necessary, not sufficient):**
- **Data-source tree mapping** as a *pure function of `ProjectIndex` state* — `OutlineTree.build(lenses:projects:folders:) -> [OutlineNode]` (`OutlineNode.swift:90`), `isGroup`, expandability. Assert the **output** (`[.folder(f1), .project(p1)]`), NOT that the `NSOutlineViewDataSource` delegate was *called* (don't lock AppKit protocol shape, or a future agent cargo-cults call-count tests).
- **`@AppStorage` restore** lookup for a stored UUID, incl. the stale-deleted-ID case → no selection.
- `ProjectSubtitle.resolve` + existing pure helpers stay.

**Side-effecting round-trip — the real Phase-A acceptance gate** (with a `ServeManager` spy; replaces "verifiable by eyeball"):
- **Push:** set the `selection` binding to B → outline's `selectedRowIndexes` resolves to B **and** the `.onChange`→`applySelectionChange` spy recorded `switchProject(to: B.path)` once. *(Catches the §2.5 spine: highlight without serve.)*
- **Pull:** simulated user click → `selection` updated **and** `persistedProjectID == id` **and** spy fired once. *(Catches stale `selectedProject`.)*
- **Idempotence:** re-applying the same selection / a `reloadItem`-triggering rename → spy fires **zero** extra times. *(Catches double-start + reload re-fire.)*

**Phase B — `DropRouting.resolve(...)` exhaustive table test** (the apocalypse fix's real gate; the routing produces *silent wrong placement*): `(dragged, target/location, tree) -> insertionDecision` over ~12 cases — out-of-folder, into-folder, between-folder, root-reorder, folder→folder, invalid targets. Factor the helper (static-shaped on a value type, no `NSOutlineView`) **before** Phase B ships.

**Visual** (selection look, spacing, focus-stability, glass) → cohort + developer-eye on **both floors** {Sequoia 15, Tahoe 26}, Light/Dark, **Reduce-Transparency**, Increase-Contrast — not an automated matrix. No XCUITest / snapshot earned (the look is a one-line `.sourceList` toggle; a snapshot proves unchanged pixels, not correct tint — Hoare's test).

## 6. Risks
- **Surface area** — the rich cell content (rings, subtitle precedence, qualifiers, rename, copy progress) is the bulk; faithful port is non-trivial.
- **Re-wiring** drag-drop / context-menu / rename to AppKit idioms while not regressing the known-working paths.
- **Serve-on-selection timing** + the `@AppStorage` restore must fire at the same moments.
- **macOS-26 glass interplay** — verify the AppKit content sits correctly in the column's material on both floors (and the §1.4 `drawsBackground = false` removal actually lets the vibrancy through).
- **Focus traversal across the SwiftUI-rail ↔ AppKit-outline seam** — Tab / ⌘0 between the (still-SwiftUI) lens rail and the AppKit outline view is a new boundary. Acceptance: ⌘0 focuses the outline, Tab traverses the seam sanely. (Don't design the responder chain in the plan; flag it for the build.)
- *Mitigation:* Phase A is **parity** — the §3.4 table is the acceptance checklist, verifiable against current behaviour; Phase B is additive.

### Selection-machinery review findings (22 Jun — code-review + gruber)
Genuine-selection (active lens forced into `selectedRowIndexes` for the pixel-exact capsule) is sound for exactness but **overloads one selection set with two orthogonal meanings** (project selection ∪ active-lens decoration) — the standing source of the "knife-fight" (capsule itself stayed perfect throughout). The 22 Jun fixes **consolidated** the machinery: the **proposed-selection set is the single source of truth** for what was clicked (it carries the clicked lens row even though it's unselectable), so `selectionIndexesForProposedSelection` alone routes every click (project → honour · lens → keep project + activate · empty → deselect), and `composedSelection` alone owns the lens-injection invariant. **Fewer interception points than the original four** → lower knife-fight risk.

**Fixed (22 Jun):** (1) type-select excludes lens/group rows (typing "c" jumped to the **Codebook** lens); (2) **lens click no longer drops the project** — the original `clickedRow`/`currentEvent` gate misfired (on a real lens click `currentEvent` isn't a mouse-down, so it read −1 and the proposal resolved to *deselect*, leaving "No Project Selected"); replaced by reading the **proposed-selection set directly** (it already contains the clicked lens row — the table's own truth, no event-gating); (3) **lens click now switches mode** — activation moved out of `shouldSelectItem` (which is **not consulted** once `selectionIndexesForProposedSelection` overrides the proposal — proven by live `os_log` trace) into the proposal handler, the one delegate reliably called with the clicked lens; deferred off its call stack + `!isApplyingProgrammatic` guard (re-entrancy); (4) lens-injection deduped into `composedSelection`. Capsule follows the route **honestly** (`activeTab` → `applySelection`), not optimistically (see below). Tests **398/0** (as of `6ce71f7`, 22 Jun — the three new files `OutlineNodeTests`/`LensItemTests`/`DropRoutingTests` add ~17 cases, so the live count runs higher; treat 398 as a point-in-time figure); the temporary `sidebar-sel` `os_log` instrumentation has been **removed** (it earned its keep — the trace pinned bugs 2 & 3 exactly).

**Deferred — decisions for the user / before TestFlight:**
- **Capsule-follows-async-route lag — RESOLVED 22 Jun: honest.** The active-lens capsule pins to `activeTab`, which updates only after `switchToTab`'s JS round-trip, so on a lens click it lags one cycle. Shipped the **honest** path (single source = `activeTab`); the **optimistic** alternative (pre-select the clicked lens row) was rejected because `update()` re-runs `applySelection` many times/sec and would snap an optimistic capsule back to the *stale* `activeTab`'s lens before the route lands — a flicker. Coupled to "`reloadData` on every `update`" below: if that churn is gated, optimistic pinning becomes viable again. Reconsider only if the one-cycle lag reads as sluggish in TF feedback.
- **A11y gap (flag before TF).** Because the lens is *genuinely* selected, VoiceOver announces TWO selected rows ("Codebook, selected" + the project) — incoherent (a row announced selected that can't be selected). Needs an AX-role override (lens row as `.radioButton` / "current view", not selected) OR the escape hatch below. **Don't ship to TestFlight unflagged.**
- **`reloadData` on every `update`.** Every model touch (count tick, rename) does a full `reloadData` + collapse/re-expand + re-select — visible churn + reopens the stale-lens window during runs. Consider gating reload to structural changes.
- **Context-menu demux (when menus land).** Right-click sets `clickedRow` to a possibly-non-selectable lens row; the menu builder must route on `node.kind` (show nothing / a mode menu for `.lens` / `.group`).

**The escape hatch (gruber) — still in reserve.** The 22 Jun bugs (2 & 3 above) hit the "more bugs in the overloaded set" threshold, but the **consolidation** (proposed-set as the single source of truth, activation in one delegate) resolved them by *reducing* interception points rather than adding one — so the hatch stayed shut and the user signed off. It remains the fallback: if the overload bites *again* after consolidation, stop overloading `selectedRowIndexes` and move the lenses to their own mode control (segmented / separate single-row table, as the SwiftUI `LensRail` already does) so the project outline means one thing — which also yields correct VoiceOver semantics (the A11y gap above) for free. **The A11y gap is the most likely forcing function before TF.**

## 7. References
- `design-desktop-nav-toolbar-rearrangement.md` (§0 posture, §2.2 parked rewrite, §3.1 lens-vs-selection)
- The sidebar-apocalypse forensic analysis (gitignored handoff notes; commit `7bf0e96`) — the drag-drop structural analysis this fixes
- `docs/design-project-sidebar.md` (row anatomy, project index)
- The diagnosis distillation (gitignored review notes) — the chain that led here
- Apple sample: **"Navigating Hierarchical Data Using Outline and Split Views"** (the canonical `NSOutlineView` source-list + split-view sample)
- API: `NSOutlineView`, `NSOutlineViewDelegate` (`isGroupItem`, `viewFor:`), `NSTableView.selectionHighlightStyle/.sourceList`, `.floatsGroupRows`, `.rowSizeStyle`, `NSTableCellView`/`backgroundStyle`, `NSViewControllerRepresentable`
- HIG: Sidebars (size-tracking + accent-icon rules), Materials (Liquid Glass / sidebar layer), Color (App accent colors)
