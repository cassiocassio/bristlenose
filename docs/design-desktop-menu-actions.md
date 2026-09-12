---
status: partial
last-trued: 2026-07-25
trued-against: working tree @main on 2026-07-25
last-trued-sections: [checkSystemHealth row (2026-07-28), retired-actions section (2026-07-28), find family + channel gate (2026-09-12, c9688b44), Codes menu section (2026-09-12)]
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

_Added 2026-07-28; `find`, `jumpToSelection` and the six Codes commands added 2026-09-12._ The action
names below appear in this catalogue's history but are **dispatched by nothing
today**. (The preamble used to open "Eight action names"; the table has grown
twice since and the number was wrong both times. It is the table that is
authoritative, not a count in front of it.) They are listed together because they share one
failure mode: a contributor finds the row, writes a `case` for it in
`AppLayout.tsx`, and ships dead code. That is exactly how `checkSystemHealth` and
`pageSetup`/`print` became silent no-ops in the first place.

| Action | Status | Why |
|---|---|---|
| `pageSetup`, `print` | **Now native, not bridge** | `PrintActions.pageSetup()` / `PrintActions.print(webView:window:)`. `window.print()` in a WKWebView can't raise the macOS print panel, so the bridge was never the right target. |
| `checkSystemHealth` | **Now native** | Opens the Health window (`openWindow(id: "health")` → `DoctorReportView` → `GET /api/doctor`). |
| `mergeCode` / `mergeCodes` | **Withdrawn 28 Jul 2026; deleted 12 Sep 2026** | Merging needs a source *and* a target and the codebook has no multi-select. Commented out in `CodesMenuContent` in July, removed outright with the other five Codes commands in September; locale keys pruned from all 21 full locales. _(The "Codes menu" section below listed this as **Shipped (bridge)** until 12 Sep 2026 — the two tables contradicted each other for six weeks. Code agrees with this one.)_ |
| `find` | **Now native, not bridge** _(12 Sep 2026)_ | ⌘F never reaches the SPA. `requestSearchFocus()` bumps the published counter `BridgeHandler.focusSearchRequests`, which `QuotesSearchToolbarControl` observes to expand and focus. A counter, not a `Bool` — ⌘F must work twice in a row. The old `case "find"` is deleted; it had dispatched cleanly into `focusSearchInput()` and done nothing, in every project, on every lens, since it shipped. |
| `findNext`, `findPrevious` | **Withdrawn** _(12 Sep 2026)_ | Unimplemented, not ungated — and the plumbing was never the problem. ⌘E writes the find pasteboard, ⌘G reads it back and dispatches with that text, and the handler sets the query that is already set: same filter, identical result. Search here **filters** the quote grid, so every visible card is already a match and nothing renders a `<mark>`; "next" presupposes a cursor stepping through occurrences in content that stays put, and a filter has neither. Stepping through results is list navigation (`j`, arrows). Restore **with transcript search**, where a document has real matches to step between. Commented out in `FindMenuContent`; 21 locale keys kept, `AppLayout.tsx` cases survive orphaned. |
| `jumpToSelection` | **Withdrawn** _(12 Sep 2026)_ | Unimplemented, not ungated — the distinction this table exists to preserve. The `AppLayout.tsx` case is an explicit `break` behind a comment claiming the native layer handles it; no native handler ever existed. It could not have reached WKWebView as `centerSelectionInVisibleRect:` either — a SwiftUI `.keyboardShortcut` installs an NSMenu key equivalent, matched *before* the responder chain. Commented out in `FindMenuContent` rather than dimmed, because a `.disabled` that will never go live is a lie that reads as diligence. Blocking question: what does "jump to selection" mean in a quote grid? The 21 locale keys are kept so restore is one line. **The `AppLayout.tsx` case survives orphaned.** |
| `renameCodeGroup`, `deleteCodeGroup`, `toggleCodeGroup` / `showHideCodeGroup`, `renameCode`, `deleteCode` | **Retired** _(12 Sep 2026)_ | **Not deferred — a category error**, and the reason to read this row before writing a `case`. They spent six weeks in a five-arm warn-stub (*"requires native focus context — not yet wired"*), which reads as *blocked on plumbing*; it was never plumbing. `docs/design-codebook-v2.md` pins selection as **single**, living **in the master list**, with the detail pane *"a pure function of it … no second place a thing can be 'current'"* (29 Aug) — and the master list selects a **codebook**, so a command naming one group or one tag has no target the model permits. Each is already direct manipulation on the lens: click a name to rename, a per-chip delete, drag to merge. Show/Hide was never a codebook command at all — **D7** puts the eye in `TagSidebar` / `TagGroupCard` on the **Quotes** lens and confirms hide *"was never a third axis here"*, which closes that doc's **G7**/**Q11** with a third answer the registers did not list. Swift, the `AppLayout.tsx` stub and the `desktop.menu.codes.*` keys in all 21 full locales are all gone — **no orphans left behind**, unlike the rows above. Restoring any of them means reopening the 29 Aug pin, not adding a handler. `createCodeGroup` and `createCode` stay: creation needs no target. **Reasoning corrected the same day** — see `design-codebook-focus.md`: focus is a separate axis from selection, and with a focus cursor these four have a target after all. Proposed, not decided; the commands are still gone. `toggleCodeGroup` is unaffected (D7, wrong lens). |
| `toggleDarkMode` | **Removed from the View menu** | Appearance is owned by Settings ▸ Appearance. **The frontend handler survives orphaned in `AppLayout.tsx` — nothing dispatches it.** |
| `exportAnonymised` | **Retired** | Anonymise is a **checkbox on the export save panel** (`ExportAccessoryView`, attached as the NSSavePanel `accessoryView` in `WebView.swift`) — it re-points the download at `?anonymise=…`. A second menu item offering the same choice was redundant. Its `AppLayout.tsx` case is now orphaned; `desktop.menu.file.exportAnonymised` is orphaned across 20 locales. |
| `filterByTag` | **Retired** | Superseded by the tag sidebar (View ▸ Show Tags). |
| `exportQuotesCSV` | **Never existed** | No Swift dispatch, no frontend case. |
| `showHelp`, `showKeyboardShortcuts`, `showReleaseNotes` | **Native** | Help menu opens browser docs directly; no bridge hop. |

**One more unconsumed action — resolved 30 Jul 2026.** ~~`set-appearance` is
pushed by `BridgeHandler.syncAppearance()` on every `ready`~~ — **the emitter was
deleted on 30 Jul 2026** (`BridgeHandler.swift:517-518` records the removal), which
is precisely what the recommendation at the end of this note asked for. Neither the
action nor `syncAppearance()` exists today. The analysis below is kept because it
is the reasoning that justified the deletion, and because the same question recurs
every time someone proposes a second channel for a fact the platform already
carries.

_As it stood before the deletion:_ `set-appearance` had **zero** consumers (it
routed via `menuAction`, so it needed a `case` in AppLayout's switch; there was
none — unlike its sibling `syncAnalysisAnimation`, which uses the
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

**That recommendation was carried out on 30 Jul 2026.** Nothing above describes
live code; it is the argument, preserved.

## Changelog

- _2026-09-12_ — **Codes menu corrected: five actions documented as Shipped have been dispatched into nothing since 0.29.0.** All five send a `bn:codebook-*` CustomEvent; an exhaustive grep of `frontend/src` finds no listener for any of them. `42d06638` put those listeners in v1's `CodebookPanel`; `baa1aa0e` deleted the panel and took them with it — `git describe --contains` → `v0.29.0~3`, three commits before the tag, so the menu has been inert on all nine channels since the release whose headline was the codebook lens. `browseCodebooks` named `CodebookPanel` as its consumer, i.e. the row cited its own missing listener. Old claims preserved inline per never-silently-delete. **Not dimmed, deliberately** — gating an unimplemented command is the lie the `jumpToSelection` row refuses; re-homing the listeners in the v2 navigator versus withdrawing the menu is an untaken product call. Nothing was ever red: a `CustomEvent` with no listener resolves normally, so the bridge succeeds and the Swift `catch` never fires. `last-trued` again NOT bumped — section-scoped, recorded in `last-trued-sections`.
- _2026-09-12_ — **Trued against the Find sweep and the channel gate; front-matter deliberately NOT bumped.** New **Enablement** section — the doc modelled routing and never availability, while five items gated on `hasChannel` / `canDispatch` / `canSearch`, none of which appeared anywhere in it. `find` and `jumpToSelection` moved from the handled catalogue into **Retired actions** (⌘F is native end-to-end via `BridgeHandler.focusSearchRequests`; ⌘J withdrawn as unimplemented). Two self-contradictions closed: `mergeCode` read **Shipped (bridge)** in the Codes table while the Retired table read **Withdrawn** — the Retired table was right, and had been for six weeks; `hasPlayer`/`playerPlaying` were listed as stubs one section after the prose said they report live — the prose was right. `set-appearance` corrected in three places: the doc recommended deleting the emitter, the deletion happened **30 Jul 2026**, and the doc went on describing it in the present tense for six weeks. Section counts dropped rather than recounted (the AppLayout header claimed 27 over 28 rows / 30 names / 35 `case` arms, eleven of which the code does not have and seven of which this doc already called retired). **Known-stale, not fixed:** the `MenuCommands.swift:N` anchors — the 28 Jul banner asked for struct names and 0 of 5 spot-checked still resolve; new text here uses struct names, old rows do not. Anchors: `FindMenuContent`, `FileMenuContent`, `BridgeHandler.swift:135-149,262-285,517-518`, `AppLayout.tsx:409`, `Toolbar.tsx:63`; commit subjects `find: wire Cmd+F to the search that exists, dim it where none does` and `menus: gate bridge commands on a live channel, not on isReady`.
- _2026-07-28_ — `checkSystemHealth` row corrected: it is no longer a bridge dispatch (that action was dead — no frontend consumer). Wired to open the native Health window (`DoctorReportView`) via `openWindow(id: "health")` from Diagnostics ▸ Check Health; the window fetches the new `GET /api/doctor` endpoint (`bristlenose/server/routes/doctor.py`, `doctor.run_local_checks`). See `docs/fix-the-menus.md` and `docs/design-diagnostics-menu.md`.
- _2026-07-25_ — trued against the working-tree Welcome/sidebar change. **View menu:** `toggleSidebar` (static "Toggle Sidebar", responder-chain `NSSplitViewController.toggleSidebar`) became **`toggleProjectsSidebar`** — a dynamic **Hide/Show Projects** label routed through the NavigationSplitView `columnVisibility` binding via the `.toggleProjectsSidebar` notification (⌥⌘S unchanged). **Help menu:** gained **Welcome to Bristlenose** (7th item, no shortcut; posts `.showWelcome` → ContentView `selection = []`). Also corrected pre-existing drift in the Help table: items open **browser docs** (retired in-app Help modal), not a modal, and re-anchored the section from stale line numbers to the `HelpMenuContent` struct. Anchors are struct-named where possible (line numbers rot).
- _2026-06-21_ — re-confirmed fresh: the `project-status-line` + `warm-sidecar-pool` work (19–21 Jun) did **not** touch menu actions / `BridgeHandler.menuAction` — the catalogue still matches `MenuCommands.swift`. One new row-level affordance landed: a "Cancel copy" item on the project **row context menu** (`ProjectRow.swift`, `onCancelCopy`) — a context-menu action, not a `menuAction()` bridge dispatch, so it sits outside this catalogue's scope (noted for completeness).
- _2026-04-24_ — Tier 1 truing follow-up (post `design-doc-review` audit): deleted the stale Future-only project-ops table that contradicted the rewritten one above it; added Shortcut column to the rewritten project-ops table (⇧⌘R, ⌘N, ⇧⌘N, ⌘⌫, ⇧⌘O); corrected `openInNewWindow` from Future to Shipped (bridge); added `chooseIcon` and `aiPrivacy` rows; added new sub-sections for View menu (Cmd+1–5, toggleSidebar, heatmap toggle), Help menu (6 actions), and Codes menu (6 wired actions, `mergeCode` moved out of project-ops); added inline alpha-gap callout for missing Analyse/Resume/Retry in the project context menu; noted `playPause` triple-dispatch (Video / Quotes / kbd). Section heading count corrected from "(8)" to "(17)".
- _2026-04-23_ — trued up during port-v01-ingestion QA: rewrote §"Project operations — native-only or future" to reflect shipped NotificationCenter-based project ops (newProject, renameProject, deleteProject, locateProject, createNewFolder, renameFolder, deleteFolder, moveSelectedProject); kept `reAnalyse` (`.disabled(true)` per `MenuCommands.swift:397-400`) and `archive` (Phase 5) as Future; added missing entries (`openBlog`, `showAcknowledgements`, `mergeCode`); flagged `revealInFinder` label drift vs shipped `showInFinder`. Anchors: `MenuCommands.swift:355-360, 397-405, 433-466, 692-698`, `ContentView.swift:279-292, 1118-1176`. Commit: 3d9f43c.

# Desktop Menu Actions — Bridge Handler Cookbook

Reference for all menu actions wired through `BridgeHandler.menuAction()`. Working context (the 3-file chain, how to add a new handler) lives in `desktop/CLAUDE.md`.

> **Note (2026-04-23):** Project operations use **two wiring patterns** — actions affecting the native sidebar (project/folder CRUD, rename, move) post `Notification.Name` events that ContentView receives via `.onReceive`, while actions targeting the web layer (re-analyse, archive, codebook ops) dispatch through `bridgeHandler.menuAction()`. The catalogue below should be read with this distinction in mind. Detail in `desktop/CLAUDE.md` "Project menu actions use Notification.Name not bridge."

## Enablement — what gates a menu item

_Added 2026-09-12._ Until then this catalogue modelled *routing* and nothing
about *availability*, while five shipped items across three menus gated on
predicates it never named. The gap has a cost: the obvious signal to reach for is
`isReady`, and reaching for it is what `b06f923a` had to undo.

Three predicates, each answering a different question:

| Predicate | Means | Use it for |
|---|---|---|
| `hasChannel` | A web view is registered. A published mirror of `webView`, driven by its `didSet`, so a menu gate can never disagree with the `guard let webView` it stands in for. | Commands that hand the web view to AppKit and never dispatch JS — **Print** is the only one today. A status page is a real document and prints. |
| `canDispatch` | `hasChannel && documentState == .spa` — there is a channel *and* something on the far end that understands it. | Any command routed through `menuAction(...)`. **Export Report**, zoom. |
| `canSearch` | `canDispatch && activeTab == .quotes` (`FindMenuContent`). | The Find family. Search exists on one lens; the other three carry `SearchComingSoonButton`. |

**Why not `isReady`.** It is force-set true 2 s after *any* load, status page
included, and goes false only in `reset()` (a selection change). So it reads true
over a document with no `window.__bristlenose`, which is the failure it looks like
it prevents. A sidecar dying mid-session leaves `isReady` true over a nil web view.

**Why both halves of `canDispatch`.** They go false in different states.
`documentState` describes the *document* and stays `.spa` across a channel
teardown; `hasChannel` describes the *channel* and says nothing about what is
loaded.

**Why a lens gate needs `canDispatch` too.** `currentPath` survives an in-place
reload, so `activeTab` can still say `.quotes` over a freshly-loaded status page
with no SPA behind it.

**The hole in the mirror, so nobody has to rediscover it.** `didSet` fires on
*assignment* only. A weak reference zeroed by its referent deallocating runs no
observer, so a web view released without `dismantleNSView` assigning nil would
leave `hasChannel` reading true over a dead channel. The defined teardown does
assign — that is what makes the mirror safe today, not a property of `weak`.
Relatedly, `webView` is cleared by `WebView.dismantleNSView` under an identity
guard and **not** by `reset()`: two owners with no defined order were wiping a
registration a warm switch had just made.

**House rule: menus dim, toolbars morph.** They agree on availability and differ
only on presentation — so a menu item and its toolbar twin gate on the same
predicate. Export Report was ungated here while its toolbar twin gated on lens
availability; that split is what `b06f923a` closed.

**A `.disabled` that will never go live is a lie that reads as diligence.** An
item that is *unimplemented* rather than *ungated* is withdrawn — commented out
with its blocking question and its restore path — not dimmed. `mergeCode` and
`jumpToSelection` are the two precedents; both are in Retired actions above.

**Not every menu command is a `menuAction`.** There are four routes, not one:
the bridge (`menuAction`), a `Notification.Name` to `ContentView` (project ops),
straight to AppKit (`PrintActions`), and — since 12 Sep 2026 — **native to
native**, where the target is a native control and nothing crosses the bridge.
⌘F is the first: `requestSearchFocus()` bumps a published counter that
`QuotesSearchToolbarControl` observes. Reach for that route whenever the thing
the command operates on is already in Swift; routing it through the SPA and back
is how ⌘F came to spend its whole life dispatching cleanly into nothing.

## Action catalogue

### Already handled — AppLayout

_Count dropped 12 Sep 2026._ It read "(27 actions)" against a table of 28 rows
naming 30 actions, over 35 `case` arms, eleven of which the table names and the
code does not — seven of those eleven already declared retired in the table
above it. A count in prose is a count nothing recomputes; `grep -c 'case "'
AppLayout.tsx` is the answer and it is always current.

| Action | Handler |
|--------|---------|
| `toggleLeftPanel` | `sidebarAnimations.toggleToc()` |
| `toggleRightPanel` | `sidebarAnimations.toggleTags()` |
| `hideAllSidebars` | `sidebarAnimations.hideAll()` — explicit, not a toggle (native owns the direction; see `AllSidebars`) |
| `showAllSidebars` | `sidebarAnimations.showAll()` — restores the stashed arrangement |
| `toggleInspectorPanel` | `toggleInspector()` |
| `useSelectionForFind` | Selection → search query + find pasteboard write. The capsule surfaces the term via the `quotes-filter` push; its `focusSearchInput()` call is inert in embedded mode and correct in the browser. |

> **The Find family, corrected 12 Sep 2026.** `find`, `findNext`, `findPrevious`
> and `jumpToSelection` are all in **Retired actions** now; `useSelectionForFind`
> is the only row left here.
>
> It is gated natively on `canSearch = canDispatch && activeTab == .quotes`
> (`FindMenuContent`) — search exists on one lens, and `canDispatch` as well as
> the lens because `currentPath` survives an in-place reload, so `activeTab` can
> still say `.quotes` over a freshly-loaded status page.
>
> Its `focusSearchInput()` call (`AppLayout.tsx:409`) queries `.search-input`, an
> element `Toolbar` never renders in embedded mode (`Toolbar.tsx:63`). That is
> dead in the app and **correct in the browser**, where the SPA's own SearchBox
> is rendered — so it stays. The desktop path needs no focus of its own:
> ⌘E's job is to load the term, and the capsule expands and mirrors it when the
> SPA posts `quotes-filter` back (`BridgeHandler.swift:760`). macOS convention
> agrees — Safari and TextEdit do not open the find bar on ⌘E.

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
> | `openInNewWindow` | ~~⇧⌘O~~ | **RETIRED 20 Aug 2026** | Deleted from the menu bar. Its distinction from `File ▸ New Window` — "opens the SELECTED project" vs "another view of the one showing" — **has no referent in this app**: selecting a study in the sidebar IS how a window comes to show it, so both read one input, and the code agreed (both called `frontProjectID`). Worse, it *sometimes* revealed instead of opening, and only when its target had itself arrived by a reveal and never switched study — the unlearnable rule `design-workspace.md` rules out. **The three sidebar context-menu items survive** (project / lens / folder row), because a clicked row genuinely can be a study the window is not showing — arbitrary-target, which the menu bar has no equivalent for. That split is the reason not to "restore" this. ⇧⌘O is free. See `MenuCommands.swift` § the retirement comment |
> | `chooseIcon` | — | **Shipped** (project-row context menu) | SF Symbol picker via `IconPickerPopover` (`ContentView.swift:967-969`) |
> | `aiPrivacy` | — | **Shipped** (NotificationCenter) | Posts `.showAIConsentSheet` (`MenuCommands.swift:93-96`); opens AIConsentView |
> | `reAnalyse` | — | **Shipped 19 Aug 2026** | No longer a bridge action at all: it routes natively via `windowCommands?.perform(.reAnalyseProject)`, because it deletes a directory and spawns a subprocess and never touched the web view. The bridge event it used to send had no listener anywhere in `frontend/src`, which is plausibly why it stalled. See `docs/design-analysis-lifecycle.md` §6.1 |
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
| `openBlog` | **Shipped** (native, 2026-09-12) | `Self.open("https://blog.bristlenose.app")`. **Was bridge-routed and silently dead on the Welcome screen** — `bridgeHandler.menuAction` opens with `guard let webView`, and `webView` is a **weak** ref (`BridgeHandler.swift:231`), so with no project selected the WebView is deallocated, the call is dropped to the log (`menuAction(openBlog) dropped — no webView registered`) and the menu item does nothing. It was the last URL-opening item in this menu still going through the bridge; the other four were migrated to `Self.open` earlier and the comment in `AppLayout.tsx` recording that migration had simply not been extended to this one. Going native also picks up the scheme guard in `Self.open` and drops a JS round-trip for something `NSWorkspace` does directly. The web-side `case "openBlog"` is deleted — the native menu was its only dispatcher. |
| `showAcknowledgements` | **Shipped** (native) | Opens `ACKNOWLEDGEMENTS.md` on GitHub in the browser |

### Codes menu (9)

5 stubs that need native focus context are catalogued separately under "Codebook operations" below.

> **Corrected 12 Sep 2026 — the five "wired" actions are dispatched into nothing,
> and have been since 0.29.0.** Every row below read **Shipped (bridge)**. All five
> dispatch a `bn:codebook-*` CustomEvent and an exhaustive grep of `frontend/src`
> finds **no listener for any of them** — only the dispatch sites. `42d06638`
> ("wire codebook menu actions: **CodebookPanel listeners** for remove,
> create-group, create-code") put those listeners in the v1 panel; `baa1aa0e`
> ("codebook v2 becomes the codebook lens: **v1 deleted**") removed the panel and
> took them with it. `git describe --contains baa1aa0e` → **`v0.29.0~3`** — three
> commits before the tag, so the menu has been inert on all nine channels since
> the release whose headline feature was the codebook lens.
>
> **Nothing was red at any point.** A `CustomEvent` with no listener resolves
> normally, so the bridge succeeds, the Swift `catch` never fires, and the log
> stays clean. This is the "deleting a UI surface orphans the thing that was its
> only witness" gotcha in the root `CLAUDE.md`, one level out: it orphaned the
> **listeners**, and the dispatcher went on dispatching.
>
> **They are deliberately NOT dimmed.** Gating a command with no implementation is
> the lie the `jumpToSelection` row refuses. Re-homing the listeners in the v2
> navigator, or withdrawing the menu with the `mergeCode` idiom, is a product call
> and has not been taken. Measurements and the rejected options are in the
> maintainer's private review log, kept outside the public tree.

| Action | Status | Notes |
|---|---|---|
| `browseCodebooks` | **Orphaned** _(12 Sep 2026)_ | Dispatches `bn:codebook-browse` — **nothing listens**. _(Read **Shipped (bridge → CodebookPanel)** until 12 Sep 2026. `CodebookPanel` is the component `baa1aa0e` deleted, so the row named its own missing consumer.)_ |
| `importFramework` | **Orphaned** _(12 Sep 2026)_ | Dispatches `bn:codebook-browse` with `{ templateId }` — **nothing listens**. _(Read **Shipped (bridge)**.)_ |
| `removeFramework` | **Orphaned** _(12 Sep 2026)_ | Dispatches `bn:codebook-remove` — **nothing listens**. Currently `.disabled(!isCodeTab)`, so it is dimmed-and-dead off the lens and lit-and-dead on it. _(Read **Shipped (bridge)**.)_ |
| `createCodeGroup` | **Orphaned** _(12 Sep 2026)_ | Dispatches `bn:codebook-create-group` — **nothing listens**. _(Read **Shipped (bridge)**.)_ |
| `createCode` | **Orphaned** _(12 Sep 2026)_ | Dispatches `bn:codebook-create-code` — **nothing listens**. _(Read **Shipped (bridge)**.)_ |
| `mergeCode` | **Deleted** _(12 Sep 2026)_ | Withdrawn 28 Jul, removed from `CodesMenuContent` on 12 Sep with the other five Codes commands; see the Retired-actions table. _(This row said **Shipped (bridge)** until 12 Sep 2026, contradicting that table since 28 Jul. The web half `mergeCodebookTags` still works — it is the menu item that is gone.)_ |

### Quotes menu — `playPause` triple-dispatch note

`playPause` appears in three menu-source paths: the Video menu, the **Quotes menu** (`MenuCommands.swift:530-533`), and `useKeyboardShortcuts.ts`. All three resolve to `sendCommand("playPause")` via `PlayerContext`.

### Codebook operations — RETIRED 12 Sep 2026 (was "5 stubs, need native focus context")

**This section is kept as a correction, not a backlog.** The five commands are
gone; so is their `AppLayout.tsx` warn-stub and every `desktop.menu.codes.*` key
they owned. Full reasoning in **Retired actions** above.

| Action | Was "blocked on" | Actually |
|--------|------------------|----------|
| `toggleCodeGroup` | No expand/collapse state in CodebookPanel | Wrong axis and wrong lens. **D7**: hide and enable are different axes; the eye lives in `TagSidebar` / `TagGroupCard` on **Quotes**, and hide *"was never a third axis here"*. Closes `design-codebook-v2.md`'s **G7**/**Q11** |
| `renameCodeGroup` | Native sidebar focus tracking (which group is selected) | There is no such focus to track. Selection is **single** and lives in the **master list**, which selects a *codebook*; the detail pane is *"a pure function of it"*. Renaming is clicking the name |
| `deleteCodeGroup` | Native sidebar focus tracking | As above; deletion is the group card's own control |
| `renameCode` | Native sidebar focus tracking (which code is selected) | As above; renaming is clicking the chip |
| `deleteCode` | Native sidebar focus tracking | As above; deletion is the per-chip × |

The "blocked on" column is the thing to learn from: **it named a component that
`baa1aa0e` had already deleted (`CodebookPanel`) and a focus model the design
doc forbids.** A stub whose blocker is stated in terms of a surface that no
longer exists will sit in a backlog indefinitely, because nobody can tell it
apart from work that is merely not yet done.

### Edit operations — partially handled (2)

| Action | Status |
|--------|--------|
| `undo` / `redo` | Stub (`canUndo: false` in `getState()`). Needs undo store |

### Internal (not from menu)

| Action | Notes |
|--------|-------|
| ~~`set-appearance`~~ | **Removed 30 Jul 2026** — emitter deleted; appearance reaches the report by native inheritance, not over the bridge. See Retired actions. |

## Payload conventions

Most actions are **stateless** — the action string is sufficient because the frontend reads current state from FocusContext/QuotesContext (which quote is focused, which are selected).

Actions that need **payloads** (the optional second argument to `menuAction`):

| Action | Payload shape | Example |
|--------|--------------|---------|
| ~~`set-appearance`~~ | — | **Removed 30 Jul 2026** — no longer sent. |
| `exportAnonymised` | `{ anonymise: true }` | Proposed |
| `importFramework` | `{ templateId: string }` | Wired — pre-selects template in picker |
| `removeFramework` | `{ frameworkId: string }` | Wired — opens confirm dialog in CodebookPanel |
| ~~`findNext` / `findPrevious`~~ | ~~`{ text: string }`~~ | **Withdrawn 12 Sep 2026** — no longer dispatched. The payload shape is kept here for the transcript-search restore. |

**Rule:** if the frontend already knows the target (focused quote, active tab), don't pass it in the payload. Payloads are for data the native side has that the web side doesn't.

## getState() stubs

`bridge.ts` `getState()` has four hardcoded stubs:

| Property | Stub value | Wired when |
|----------|-----------|------------|
| `canUndo` | `false` | Undo store ships (tracks quote edits, tag changes) |
| `canRedo` | `false` | Same |

`hasPlayer` and `playerPlaying` were listed here as stubs until 12 Sep 2026.
They are **live** — `bridge.ts:295-298` reads them from
`deps.getHasPlayer()` / `deps.getPlayerPlaying()`, which is what the Video-player
paragraph above this section already said. The two statements contradicted each
other; the paragraph was right.

These control menu item dimming in Swift. Until wired, the **Undo/Redo** menu dims
correctly (items disabled when the stubs are `false`). The Video menu is no longer
part of that claim — it dims on live state.

## Recommended implementation order (remaining)

1. ~~**New frontend handlers, no new infra**~~ — Done. All 14 Tier 2 actions wired in `AppLayout.tsx`
2. ~~**Codebook**~~ — Done. 5 actions fully wired (browse, import, remove, create group, create code). 5 stubbed pending native focus context (toggle/rename/delete group, rename/delete code)
3. **Video** — requires PlayerContext bridge (popout window ↔ native state sync)
4. **Project operations** — requires project list feature
5. **Undo/Redo** — requires undo store design
