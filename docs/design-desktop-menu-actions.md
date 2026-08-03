---
status: partial
last-trued: 2026-07-25
trued-against: working tree @main on 2026-07-25
last-trued-sections: [checkSystemHealth row (2026-07-28), retired-actions section (2026-07-28)]
---

> **Do not honour the "recently trued, skip" short-circuit on this doc.** The
> `2026-07-28` date it previously carried covered **one row**. A 28 Jul audit found
> five rows naming actions that exist on neither side of the bridge, three section
> counts wrong, seven shipped actions missing entirely, and **0 of 12
> `MenuCommands.swift:N` line anchors still resolving**. The date has been rolled
> back to the last genuinely whole-doc pass. Re-anchor to struct names
> (`FileMenuContent`, `CodesMenuContent`, …) when next edited — line numbers here
> rot within days.

> **Trued 2026-06-15 (`per-project-activity` @ `518e6d3`):** the Project menu + row context menu
> gained **Stop Analysis** (⌘. on the Project menu) and **Show Diagnostics…**; the toolbar pill that
> previously carried Retry was deleted. Only the §"Project operations" alpha-gap callout changed; the
> rest of the catalogue is untouched by this branch.

> **Truing status:** Trued. Project-ops table rewritten with NotificationCenter / bridge split; old contradicting Future-only table removed. Keyboard shortcuts added throughout. `openInNewWindow` corrected (Shipped, not Future). Help, View, and Codes menus given dedicated sub-sections. Alpha gap (no Analyse/Resume/Retry in context menu) called out inline. See changelog.

## Retired actions — do not re-wire

_Added 2026-07-28._ Eight action names appear in this catalogue's history but are
**dispatched by nothing today**. They are listed together because they share one
failure mode: a contributor finds the row, writes a `case` for it in
`AppLayout.tsx`, and ships dead code. That is exactly how `checkSystemHealth` and
`pageSetup`/`print` became silent no-ops in the first place.

| Action | Status | Why |
|---|---|---|
| `pageSetup`, `print` | **Now native, not bridge** | `PrintActions.pageSetup()` / `PrintActions.print(webView:window:)`. `window.print()` in a WKWebView can't raise the macOS print panel, so the bridge was never the right target. |
| `checkSystemHealth` | **Now native** | Opens the Health window (`openWindow(id: "health")` → `DoctorReportView` → `GET /api/doctor`). |
| `mergeCode` | **Withdrawn** | Commented out in `CodesMenuContent` — merging needs a source *and* target and the codebook has no multi-select. |
| `toggleDarkMode` | **Removed from the View menu** | Appearance is owned by Settings ▸ Appearance. **The frontend handler survives orphaned in `AppLayout.tsx` — nothing dispatches it.** |
| `exportAnonymised` | **Retired** | Anonymise is a **checkbox on the export save panel** (`ExportAccessoryView`, attached as the NSSavePanel `accessoryView` in `WebView.swift`) — it re-points the download at `?anonymise=…`. A second menu item offering the same choice was redundant. Its `AppLayout.tsx` case is now orphaned; `desktop.menu.file.exportAnonymised` is orphaned across 20 locales. |
| `filterByTag` | **Retired** | Superseded by the tag sidebar (View ▸ Show Tags). |
| `exportQuotesCSV` | **Never existed** | No Swift dispatch, no frontend case. |
| `showHelp`, `showKeyboardShortcuts`, `showReleaseNotes` | **Native** | Help menu opens browser docs directly; no bridge hop. |

**One more unconsumed action — but not a broken feature.** `set-appearance` is
pushed by `BridgeHandler.syncAppearance()` on every `ready` and has **zero**
consumers (it routes via `menuAction`, so it needs a `case` in AppLayout's switch;
there is none — unlike its sibling `syncAnalysisAnimation`, which uses the
`window.__bristlenose.setX()` namespace pattern and does work).

Unlike the rows above, **nothing is broken by this**: appearance reaches the report
through native inheritance — `ContentView.swift:393` `.preferredColorScheme(…)`
forces the window's appearance, the WKWebView inherits it, and the report's CSS
`prefers-color-scheme` follows. `set-appearance` is therefore **vestigial**, a
redundant round-trip that fires on every load and lands nowhere, not a dead menu
item. Recommended: **delete the emitter** — a second channel for a fact the platform
already carries is how two surfaces drift. Wire it only if the SPA ever needs
`data-theme` set explicitly (e.g. if "auto" must mean something other than "follow
system").

## Changelog

- _2026-07-28_ — `checkSystemHealth` row corrected: it is no longer a bridge dispatch (that action was dead — no frontend consumer). Wired to open the native Health window (`DoctorReportView`) via `openWindow(id: "health")` from Diagnostics ▸ Check Health; the window fetches the new `GET /api/doctor` endpoint (`bristlenose/server/routes/doctor.py`, `doctor.run_local_checks`). See `docs/fix-the-menus.md` and `docs/design-diagnostics-menu.md`.
- _2026-07-25_ — trued against the working-tree Welcome/sidebar change. **View menu:** `toggleSidebar` (static "Toggle Sidebar", responder-chain `NSSplitViewController.toggleSidebar`) became **`toggleProjectsSidebar`** — a dynamic **Hide/Show Projects** label routed through the NavigationSplitView `columnVisibility` binding via the `.toggleProjectsSidebar` notification (⌥⌘S unchanged). **Help menu:** gained **Welcome to Bristlenose** (7th item, no shortcut; posts `.showWelcome` → ContentView `selection = []`). Also corrected pre-existing drift in the Help table: items open **browser docs** (retired in-app Help modal), not a modal, and re-anchored the section from stale line numbers to the `HelpMenuContent` struct. Anchors are struct-named where possible (line numbers rot).
- _2026-06-21_ — re-confirmed fresh: the `project-status-line` + `warm-sidecar-pool` work (19–21 Jun) did **not** touch menu actions / `BridgeHandler.menuAction` — the catalogue still matches `MenuCommands.swift`. One new row-level affordance landed: a "Cancel copy" item on the project **row context menu** (`ProjectRow.swift`, `onCancelCopy`) — a context-menu action, not a `menuAction()` bridge dispatch, so it sits outside this catalogue's scope (noted for completeness).
- _2026-04-24_ — Tier 1 truing follow-up (post `design-doc-review` audit): deleted the stale Future-only project-ops table that contradicted the rewritten one above it; added Shortcut column to the rewritten project-ops table (⇧⌘R, ⌘N, ⇧⌘N, ⌘⌫, ⇧⌘O); corrected `openInNewWindow` from Future to Shipped (bridge); added `chooseIcon` and `aiPrivacy` rows; added new sub-sections for View menu (Cmd+1–5, toggleSidebar, heatmap toggle), Help menu (6 actions), and Codes menu (6 wired actions, `mergeCode` moved out of project-ops); added inline alpha-gap callout for missing Analyse/Resume/Retry in the project context menu; noted `playPause` triple-dispatch (Video / Quotes / kbd). Section heading count corrected from "(8)" to "(17)".
- _2026-04-23_ — trued up during port-v01-ingestion QA: rewrote §"Project operations — native-only or future" to reflect shipped NotificationCenter-based project ops (newProject, renameProject, deleteProject, locateProject, createNewFolder, renameFolder, deleteFolder, moveSelectedProject); kept `reAnalyse` (`.disabled(true)` per `MenuCommands.swift:397-400`) and `archive` (Phase 5) as Future; added missing entries (`openBlog`, `showAcknowledgements`, `mergeCode`); flagged `revealInFinder` label drift vs shipped `showInFinder`. Anchors: `MenuCommands.swift:355-360, 397-405, 433-466, 692-698`, `ContentView.swift:279-292, 1118-1176`. Commit: 3d9f43c.

# Desktop Menu Actions — Bridge Handler Cookbook

Reference for all menu actions wired through `BridgeHandler.menuAction()`. Working context (the 3-file chain, how to add a new handler) lives in `desktop/CLAUDE.md`.

> **Note (2026-04-23):** Project operations use **two wiring patterns** — actions affecting the native sidebar (project/folder CRUD, rename, move) post `Notification.Name` events that ContentView receives via `.onReceive`, while actions targeting the web layer (re-analyse, archive, codebook ops) dispatch through `bridgeHandler.menuAction()`. The catalogue below should be read with this distinction in mind. Detail in `desktop/CLAUDE.md` "Project menu actions use Notification.Name not bridge."

## Action catalogue

### Already handled — AppLayout (27 actions)

| Action | Handler |
|--------|---------|
| `toggleLeftPanel` | `sidebarAnimations.toggleToc()` |
| `toggleRightPanel` | `sidebarAnimations.toggleTags()` |
| `hideAllSidebars` | `sidebarAnimations.hideAll()` — explicit, not a toggle (native owns the direction; see `AllSidebars`) |
| `showAllSidebars` | `sidebarAnimations.showAll()` — restores the stashed arrangement |
| `toggleInspectorPanel` | `toggleInspector()` |
| `find` | Focus search input (expand + focus + select) |
| `useSelectionForFind` | Selection → search query + find pasteboard write |
| `findNext` | Find pasteboard text (from payload) → search query |
| `findPrevious` | Find pasteboard text (from payload) → search query |
| `jumpToSelection` | No-op (WKWebView native) |
| `exportReport` | `setExportOpen(true)` |
| `exportAnonymised` | Open ExportDialog with `initialAnonymise={true}` |
| `exportQuotesCSV` | Build CSV from all quotes → blob download |
| `copyAsCSV` | Copy focused/selected quotes as CSV to clipboard |
| `allQuotes` | Reset search + tag filter + view mode to defaults |
| `starredQuotesOnly` | `setViewMode("starred")` |
| `filterByTag` | Click tag filter dropdown trigger button |
| `showHelp` | Open help modal to "help" section |
| `showKeyboardShortcuts` | Open help modal to "shortcuts" section |
| `showReleaseNotes` | Open help modal to "about" section |
| `sendFeedback` | `setFeedbackOpen(true)` |
| `zoomIn` / `zoomOut` / `actualSize` | CSS `font-size` scaling (±10%, persisted to localStorage) |
| `toggleDarkMode` | Toggle `data-theme` attribute between light/dark |
| `browseCodebooks` | Dispatch `bn:codebook-browse` → CodebookPanel opens picker |
| `importFramework` | Dispatch `bn:codebook-browse` with `{ templateId }` payload → CodebookPanel opens preview |
| `removeFramework` | Dispatch `bn:codebook-remove` with `{ frameworkId }` → CodebookPanel shows confirm dialog |
| `createCodeGroup` | Dispatch `bn:codebook-create-group` → CodebookPanel creates group |
| `createCode` | Dispatch `bn:codebook-create-code` → CodebookPanel creates tag in first researcher group |

### Already handled — useKeyboardShortcuts (24 actions)

These are in the `handleMenuAction` switch inside `useKeyboardShortcuts.ts`, sharing closures with the keyboard handlers.

| Action | Handler |
|--------|---------|
| `star` | `handleStar()` — bulk-aware (uses focused/selected) |
| `hide` | `handleHide()` — bulk-aware, moves focus after |
| `addTag` | `handleTagOpen()` — opens TagInput on focused quote |
| `applyLastTag` | `handleQuickApply()` — quick-apply last-used tag |
| `playPause` | `sendCommand("playPause")` — toggle play/pause on open player |
| `skipForward5` / `skipBack5` | `sendCommand("skipRelative", { seconds: ±5 })` |
| `skipForward30` / `skipBack30` | `sendCommand("skipRelative", { seconds: ±30 })` |
| `speedUp` / `slowDown` | `sendCommand("speedStep", { delta: ±0.25 })` |
| `normalSpeed` | `sendCommand("setSpeed", { rate: 1 })` |
| `volumeUp` / `volumeDown` | `sendCommand("volumeStep", { delta: ±0.1 })` |
| `mute` | `sendCommand("toggleMute")` |
| `pictureInPicture` | `sendCommand("togglePip")` |
| `fullscreen` | `sendCommand("toggleFullscreen")` |
| `nextQuote` | `moveFocus(1)` |
| `previousQuote` | `moveFocus(-1)` |
| `extendSelectionDown` | `handleShiftMove(1)` |
| `extendSelectionUp` | `handleShiftMove(-1)` |
| `toggleSelection` | `toggleSelection(focusedId)` + anchor |
| `clearSelection` | `clearSelection()` |
| `revealInTranscript` | `navigate(/report/sessions/:pid#anchor)` |

Video player commands use `sendCommand()` from `PlayerContext` which posts `bristlenose-command` messages to the popout player window. The popout `player.html` handles all commands (skip, speed, volume, PiP, fullscreen). Bridge `getState()` reports live `hasPlayer` / `playerPlaying` from module-level getters in `PlayerContext.tsx` — Swift uses these to dim/enable the Video menu.

### Need new frontend implementation (0)

All Tier 2 actions are wired — moved to "Already handled — AppLayout" above.

### Project operations — native-side or future (17)

These are either native-only (Finder, print) or depend on features not yet built (re-analysis, archive).

> **Trued 2026-04-24.** Most "Future: project management" entries shipped during sidebar Phases 1–3 via the NotificationCenter pattern. Remaining true-Future items are `reAnalyse`, `archive`, `archiveFolder` (all `.disabled(true)` or unwired in `MenuCommands.swift`). Catalogue:
>
> | Action | Shortcut | Status | Notes |
> |---|---|---|---|
> | `showInFinder` | ⇧⌘R | **Shipped** (native) | `NSWorkspace.shared.selectFile` in `MenuCommands.swift:355-361`; also wired to ProjectRow context menu (`ContentView.swift:954-961`). _Doc previously named this `revealInFinder`._ |
> | `newProject` | ⌘N | **Shipped** (NotificationCenter) | `createNewProject` notification → ContentView handler (`MenuCommands.swift:113-116`) |
> | `createNewFolder` | ⇧⌘N | **Shipped** (NotificationCenter) | `createNewFolder` notification (`MenuCommands.swift:118-121`) |
> | `renameProject` | — | **Shipped** (NotificationCenter) | `renameSelectedProject` notification |
> | `renameFolder` | — | **Shipped** (NotificationCenter) | `renameSelectedFolder` notification |
> | `deleteProject` | ⌘⌫ | **Shipped** (NotificationCenter) | `deleteSelectedProject` notification — multi-select bug noted (only deletes focused row, alpha fix); `MenuCommands.swift:412` |
> | `deleteFolder` | ⌘⌫ | **Shipped** (NotificationCenter) | `deleteSelectedFolder` notification (`MenuCommands.swift:352`) |
> | `moveSelectedProject` | — | **Shipped** (NotificationCenter) | "Move to" submenu populated from folders + "No Folder" |
> | `locateProject` | — | **Shipped** (NotificationCenter) | NSOpenPanel for moved/deleted projects |
> | `openInNewWindow` | ⇧⌘O | **Shipped** (bridge) | `bridgeHandler.menuAction("openInNewWindow")` (`MenuCommands.swift:123-126`). Active, not `.disabled` |
> | `chooseIcon` | — | **Shipped** (project-row context menu) | SF Symbol picker via `IconPickerPopover` (`ContentView.swift:967-969`) |
> | `aiPrivacy` | — | **Shipped** (NotificationCenter) | Posts `.showAIConsentSheet` (`MenuCommands.swift:93-96`); opens AIConsentView |
> | `reAnalyse` | — | **Future (shipped as `.disabled(true)`)** | `MenuCommands.swift:397-400` with "Future — Phase 2+" comment. Will dispatch via bridge once incremental re-analyse pipeline lands |
> | `archive` (project) | — | Future | `MenuCommands.swift:402-405`, `.disabled(true)`, Phase 5 |
> | `archiveFolder` | — | Future | Phase 5 |
> | `checkSystemHealth` | — | **Shipped** (native window — no bridge) | No longer a `menuAction()` dispatch. Diagnostics ▸ **Check Health** → `openWindow(id: "health")` (`MenuCommands.swift` `DiagnosticsMenuContent`), opening the native Health window `DoctorReportView`, which fetches `GET /api/doctor` (local doctor checks, bearer-authed). The old bridge action was dead (no frontend consumer); wired 28 Jul 2026. See `docs/fix-the-menus.md`. |
> | `pageSetup` / `print` | ⌘P (print) | Bridge / future | NSPrintOperation on WKWebView snapshot |
>
> **Alpha gap (24 Apr 2026; partially closed 15 Jun 2026):** the Project menu and row context menu now
> include **Stop Analysis** (Project menu ⌘., `MenuCommands.swift`, gated on
> `BridgeHandler.selectedProjectIsRunning`; row context-menu, gated on run state) and **Show
> Diagnostics…** (locale keys `desktop.menu.project.stopAnalysis` / `.showDiagnostics`, all 7
> `desktop.json`). `Analyse` / `Resume` / `Retry` verbs remain **absent** as menu items. The per-project
> toolbar pill that previously carried Retry was **deleted** (commit `8ffa470`) — Stop now lives on the
> sidebar-row hover-× + the two menus above; the original `ContentView.swift:572` pill-Retry anchor is
> dead. Tracked in the private alpha-blocker shortlist (ingestion-lifecycle truing note, 23 Apr 2026).

### View menu (4)

| Action | Shortcut | Status | Notes |
|---|---|---|---|
| `toggleProjectsSidebar` | ⌥⌘S | **Shipped** (columnVisibility binding) | Dynamic **Hide Projects / Show Projects** label (flips on `bridgeHandler.sidebarVisible`). Posts `.toggleProjectsSidebar` → `ContentView` flips the NavigationSplitView `columnVisibility` binding — the same source of truth the auto toolbar sidebar button drives. Renamed 2026-07-25 from `toggleSidebar`/"Toggle Sidebar"; retired the `NSSplitViewController.toggleSidebar` responder-chain call (it left no reliable SwiftUI state for the dynamic label). Distinct from `toggleLeftPanel` (web sidebar). |
| Tab switch (Cmd+1…Cmd+5) | ⌘1–⌘5 | **Shipped** (bridge) | `bridgeHandler.switchToTab(tab)` — separate code path from `menuAction` (`MenuCommands.swift:235-243`) |
| `toggleInspectorPanel` (heatmap) | — | **Shipped** (bridge, tab-gated) | Disabled outside Analysis tab (`MenuCommands.swift:267-270`) |
| `hideAllSidebars` / `showAllSidebars` | ⌥⌘\ | **Shipped** (binding + bridge) | Dynamic **Hide All Sidebars / Show All Sidebars** label. The umbrella over the projects column *and* the two web panels — the only View item that drives both layers in one press, so it moves the `columnVisibility` binding itself **and** dispatches to the web. Direction is decided natively (`AllSidebars.anyShowing`) from the column plus the `panel-state` mirror, then sent as an explicit command; a web-side toggle would invert whenever the two layers disagreed. Web keeps bare `\` / `⌘.` / `§` for its own two panels. |

### Help menu (7)

All in `HelpMenuContent` (`MenuCommands.swift`). Order top→bottom: Bristlenose Help · **Welcome to Bristlenose** · Keyboard Shortcuts · ─ · Release Notes · Send Feedback… · ─ · Bristlenose on Substack · Acknowledgements. Most items open **browser docs** via `NSWorkspace` (the in-app Help modal is retired — "Help opens browser docs"), so they work whether or not the SPA is mounted.

| Action | Status | Notes |
|---|---|---|
| `bristlenoseHelp` | **Shipped** (native) | ⌘? — opens `bristlenose.app/docs/` in the browser (not a modal) |
| Welcome to Bristlenose | **Shipped** (native, 2026-07-25) | No shortcut (rare, unmemorable destination — discoverability comes from living in Help). Posts `.showWelcome` → ContentView `selection = []`, showing the app-level `WelcomeHomeView`. Same effect as clicking the sidebar's empty space. Reuses the vetted all-locale `chrome.welcomeTitle`. |
| `keyboardShortcuts` | **Shipped** (native) | Opens `docs/keyboard-shortcuts.html` in the browser |
| `releaseNotes` | **Shipped** (native) | Opens `docs/changelog.html` in the browser |
| `sendFeedback` | **Shipped** | `bridgeHandler.openFeedback()` → native `FeedbackSheet` (live-serve or `.serverless`) |
| `openBlog` | **Shipped** (bridge) | `bridgeHandler.menuAction("openBlog")` → Substack |
| `showAcknowledgements` | **Shipped** (native) | Opens `ACKNOWLEDGEMENTS.md` on GitHub in the browser |

### Codes menu (9)

5 stubs that need native focus context are catalogued separately under "Codebook operations" below. Wired actions:

| Action | Status | Notes |
|---|---|---|
| `browseCodebooks` | **Shipped** (bridge → CodebookPanel) | Dispatches `bn:codebook-browse` |
| `importFramework` | **Shipped** (bridge) | Dispatches `bn:codebook-browse` with `{ templateId }` |
| `removeFramework` | **Shipped** (bridge) | Dispatches `bn:codebook-remove` |
| `createCodeGroup` | **Shipped** (bridge) | Dispatches `bn:codebook-create-group` |
| `createCode` | **Shipped** (bridge) | Dispatches `bn:codebook-create-code` |
| `mergeCode` | **Shipped** (bridge) | Dispatched from Codes menu (`MenuCommands.swift:464-466`) |

### Quotes menu — `playPause` triple-dispatch note

`playPause` appears in three menu-source paths: the Video menu, the **Quotes menu** (`MenuCommands.swift:530-533`), and `useKeyboardShortcuts.ts`. All three resolve to `sendCommand("playPause")` via `PlayerContext`.

### Codebook operations — need native focus context (5 stubs)

These actions need to know WHICH group/code is targeted. Currently stubbed as console warnings in AppLayout.tsx. Wire when the native sidebar tracks focused codebook items.

| Action | Blocked on |
|--------|-----------|
| `toggleCodeGroup` | No expand/collapse state in CodebookPanel — groups are always expanded |
| `renameCodeGroup` | Native sidebar focus tracking (which group is selected) |
| `deleteCodeGroup` | Native sidebar focus tracking |
| `renameCode` | Native sidebar focus tracking (which code is selected) |
| `deleteCode` | Native sidebar focus tracking |

### Edit operations — partially handled (2)

| Action | Status |
|--------|--------|
| `undo` / `redo` | Stub (`canUndo: false` in `getState()`). Needs undo store |

### Internal (not from menu)

| Action | Notes |
|--------|-------|
| `set-appearance` | Sent by `BridgeHandler.syncAppearance()` on `ready`. Frontend applies theme |

## Payload conventions

Most actions are **stateless** — the action string is sufficient because the frontend reads current state from FocusContext/QuotesContext (which quote is focused, which are selected).

Actions that need **payloads** (the optional second argument to `menuAction`):

| Action | Payload shape | Example |
|--------|--------------|---------|
| `set-appearance` | `{ value: "dark" \| "light" \| "auto" }` | Already wired |
| `exportAnonymised` | `{ anonymise: true }` | Proposed |
| `importFramework` | `{ templateId: string }` | Wired — pre-selects template in picker |
| `removeFramework` | `{ frameworkId: string }` | Wired — opens confirm dialog in CodebookPanel |
| `findNext` / `findPrevious` | `{ text: string }` | Wired — reads from `NSPasteboard.find` |

**Rule:** if the frontend already knows the target (focused quote, active tab), don't pass it in the payload. Payloads are for data the native side has that the web side doesn't.

## getState() stubs

`bridge.ts` `getState()` has four hardcoded stubs:

| Property | Stub value | Wired when |
|----------|-----------|------------|
| `canUndo` | `false` | Undo store ships (tracks quote edits, tag changes) |
| `canRedo` | `false` | Same |
| `hasPlayer` | `false` | PlayerContext reports popout window state to bridge |
| `playerPlaying` | `false` | PlayerContext reports playback state to bridge |

These control menu item dimming in Swift. Until wired, the Undo/Redo and Video menus will dim correctly (items disabled when stubs are `false`).

## Recommended implementation order (remaining)

1. ~~**New frontend handlers, no new infra**~~ — Done. All 14 Tier 2 actions wired in `AppLayout.tsx`
2. ~~**Codebook**~~ — Done. 5 actions fully wired (browse, import, remove, create group, create code). 5 stubbed pending native focus context (toggle/rename/delete group, rename/delete code)
3. **Video** — requires PlayerContext bridge (popout window ↔ native state sync)
4. **Project operations** — requires project list feature
5. **Undo/Redo** — requires undo store design
