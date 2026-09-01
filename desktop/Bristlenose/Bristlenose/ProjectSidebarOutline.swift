import SwiftUI
import AppKit

/// The native AppKit `NSOutlineView` source-list sidebar (spec
/// `design-desktop-sidebar-appkit.md`). Hosted in SwiftUI via
/// `NSViewControllerRepresentable`. Selection STATE stays in SwiftUI (`@Binding`)
/// — the existing serve/persist wiring (`ContentView.applySelectionChange`) is
/// reused untouched, which also sidesteps the §2.5 programmatic-selection trap:
/// the binding fires SwiftUI's `.onChange` for both user and programmatic writes.
///
/// **Status (22 Jun 2026):** flag-gated parallel component — SwiftUI sidebar is
/// the default; flip `BristlenoseFlags.appKitSidebar` to render this. Renders the
/// tree (lenses group · Projects group · folders) with source-list selection,
/// lens rows that fire `switchToTab`, folder expand/collapse, the rich cell
/// content (activity ring · copy progress · subtitle precedence), internal
/// project reorder (the `DropRouting` apocalypse fix), Finder folder-of-videos
/// import onto root / a folder / a project (routed to ContentView's drop handlers),
/// the hover-× run/copy cancel, the failure-glyph → diagnostic popover, the
/// right-click context menu (project + folder, ports `ProjectRow`/`FolderRow`
/// `.contextMenu`), and the Choose-Icon popover. The cell port (Phases 0–4) is
/// complete. **Inline rename SHIPPED (28 Jul 2026)** — cell-edit + the
/// `editingNodeID` reload guard, reachable four ways (context menu · menu bar ·
/// Return · slow-second-click) plus rename-on-create; the context-menu "Rename"
/// landed with it. Mechanism + the four guard-rails + invariants:
/// `docs/design-desktop-sidebar-appkit.md` §2.6. What remains on the
/// controller track: the flag cutover to default-on + SwiftUI-path deletion.
/// Where a Finder folder-of-videos drop landed in the outline. Routes to the
/// existing substrate-independent `ContentView` handlers (drop = analyse-unless-
/// done): `.root` → new project at root, `.folder` → new project inside it,
/// `.project` → add interviews to that project. The SwiftUI sidebar wires the
/// same three handlers via `.dropDestination`; this carries them to the AppKit
/// substrate so external drops work with the flag on.
enum SidebarExternalDrop: Equatable {
    case root
    case folder(UUID)
    case project(UUID)

    /// Resolve where a Finder folder/file drop lands, from the dropped-on outline
    /// node's kind. `nil` kind (empty area / non-node) → root; a project → that
    /// project (add interviews); a folder → that folder (new project inside); the
    /// Projects group → root; the Lenses group or a lens → **reject** (`nil`). Pure —
    /// table-tested in `OutlineNodeTests` (review F34: was nested + untestable).
    static func resolve(droppedOn kind: OutlineNode.Kind?) -> SidebarExternalDrop? {
        guard let kind else { return .root }
        switch kind {
        case .project(let id): return .project(id)
        case .folder(let id):  return .folder(id)
        case .group(let key):  return key == OutlineTree.projectsGroupKey ? .root : nil
        case .lens:            return nil
        }
    }
}

/// A clickable subtitle element — the leading glyph, or (for the data-drift
/// deltas, which have no glyph of their own) the subtitle text itself. Carries
/// the project id and the destination so the controller's action resolves both.
///
/// Was `DiagnosticGlyphButton`, when the popover was the only destination. It
/// gained the other two on 26 Aug 2026: `cantFind`'s glyph had described itself
/// as "a Locate affordance, rendered as a static image" — a signifier naming an
/// act it did not perform — and the unanalysed delta had lost its click entirely
/// in the AppKit cutover.
private final class SubtitleActionButton: NSButton {
    var projectID: UUID?
    var subtitleAction: SubtitleGlyphAction = .none
    // Clickable inline chrome → pointing hand on hover (native idiom, no underline).
    override func resetCursorRects() { addCursorRect(bounds, cursor: .pointingHand) }
}

struct ProjectSidebarOutline: NSViewControllerRepresentable {
    @ObservedObject var projectIndex: ProjectIndex
    @ObservedObject var i18n: I18n
    @Binding var selection: Set<SidebarSelection>
    let lenses: [LensItem]
    let activeTab: Tab?
    let lensesEnabled: Bool
    let onActivateLens: (Tab) -> Void
    /// Finder folder/file drop landed on the outline — routed by target to the
    /// existing `ContentView` drop handlers. Internal project-reorder drags are
    /// handled entirely inside the controller and never reach this.
    let onExternalDrop: (SidebarExternalDrop, [URL]) -> Void
    /// Right-click context-menu actions that live in `ContentView` (the controller
    /// owns the in-`projectIndex` ones — rename / move / icon / cancel — directly).
    /// Mirror the SwiftUI `ProjectRow`/`FolderRow` `.contextMenu` items.
    let onLocate: (UUID) -> Void
    /// Right-click ▸ Re-analyse…. Handed to `ContentView` rather than run
    /// here: the act is destructive and its confirmation belongs with the
    /// window that can present one.
    let onReAnalyse: (UUID) -> Void
    let onShowInFinder: (UUID) -> Void
    let canShowInFinder: (UUID) -> Bool
    /// Turn On/Off Agent Access gating: locatable AND analysed (policy in
    /// ContentView, like `canShowInFinder`). The item also needs the build
    /// to have MCP at all — `mcpMounted` below.
    let canShareWithAgents: (UUID) -> Bool
    /// False when the serving build lacks the `mcp` extra — the Agent
    /// Access item hides (genuinely impossible, permanently, §3.6a).
    let mcpMounted: Bool
    let onRemoveProject: (UUID) -> Void

    /// Open a study in a new window — the sidebar twin of `File ▸ Open in New
    /// Window`. Specced with the child-window work and unbuilt until now; it is
    /// what makes "that study, over there" one gesture.
    let onOpenInNewWindow: (UUID) -> Void

    /// Open the current study at a given lens in a new window — the gesture
    /// that makes "Quotes here, Codebook there" one step instead of
    /// open-then-navigate. Specced with the child-window work, unbuilt until
    /// the scene value could carry a lens.
    let onOpenLensInNewWindow: (Tab) -> Void
    let onRemoveFolder: (UUID) -> Void
    /// Live per-project run/copy data for the rich cell. `liveData` is
    /// `@ObservedObject` (Phase 3) so high-frequency progress ticks (ring fraction /
    /// ETA) re-render this representable → `updateNSViewController` → `reloadData`,
    /// advancing the ring + subtitle ladder during a run. (Full-reload churn is the
    /// §6-accepted Phase-A cost; targeted `reloadItem` is the deferred optimisation —
    /// evaluate at QA whether the per-tick reload reads janky.) `pipelineRunner` /
    /// `copyMachinery` stay plain refs — ContentView observes `pipelineRunner` for
    /// state transitions, and copy state is read live.
    let pipelineRunner: PipelineRunner
    @ObservedObject var liveData: PipelineLiveData
    let copyMachinery: CopyMachinery
    /// The one import coordinator, so a row can show a cloud batch after the
    /// window that started it is closed. Plain ref for the same reason as
    /// `copyMachinery` — the batch is read live, not observed for transitions.
    let cloudImport: CloudImportCoordinator
    /// Path of the project the MCP handshake currently names, or nil. The
    /// antenna badge's solid tier: exposed NOW means an agent can reach this
    /// project, which is exactly "a handshake exists naming it" (§5a-bis:
    /// exposure, not activity).
    ///
    /// This is `ServeFleet.handshakeProjectPaths` — the writer's own answer,
    /// not a re-derivation. It used to be "serve is up + fronted", which is
    /// the writer's predicate minus two conjuncts and went solid with no
    /// handshake on every start and switch. Value-typed so a change re-runs
    /// `updateNSViewController` → reload.
    let handshakeProjectPaths: Set<String>
    /// When an agent last called a tool on the fronted serve, or nil. Drives
    /// the antenna's radiating animation — see `AgentWave`. Value-typed so a
    /// new call re-runs `updateNSViewController`; the controller owns the
    /// frame clock from there, so SwiftUI sees one change per burst rather
    /// than one per animation frame.
    let lastAgentCallAt: [UUID: Date]
    /// Per-window "begin rename on the sole selected row", bumped by the
    /// menu-bar Project ▸ Rename items via this window's `WindowCommandSink`.
    ///
    /// A counter rather than a flag: two consecutive Rename presses have to be
    /// distinguishable, and there is no id to carry — the controller resolves
    /// the target from its own selection, which is the whole point of routing
    /// per window. Replaces the `.renameSelectedFolder` / `.renameSelectedProject`
    /// notifications this controller used to observe, which arrived in every
    /// open window at once.
    let renameRequest: Int

    func makeNSViewController(context: Context) -> SidebarOutlineController {
        let controller = SidebarOutlineController()
        controller.projectIndex = projectIndex
        controller.i18n = i18n
        return controller
    }

    func updateNSViewController(_ controller: SidebarOutlineController, context: Context) {
        controller.projectIndex = projectIndex
        controller.i18n = i18n
        controller.lensItems = lenses
        controller.pipelineRunner = pipelineRunner
        controller.liveData = liveData
        controller.copyMachinery = copyMachinery
        controller.cloudImport = cloudImport
        // Refresh the callbacks each update so they capture the live binding —
        // the AppKit delegate does not fire for programmatic selection, so the
        // funnel is the SwiftUI binding itself (§2.5).
        controller.onSelectionChange = { newSelection in
            if selection != newSelection { selection = newSelection }
        }
        controller.onActivateLens = onActivateLens
        controller.onExternalDrop = onExternalDrop
        controller.onLocate = onLocate
        controller.onReAnalyse = onReAnalyse
        controller.onShowInFinder = onShowInFinder
        controller.canShowInFinder = canShowInFinder
        controller.canShareWithAgents = canShareWithAgents
        controller.mcpMounted = mcpMounted
        controller.handshakeProjectPaths = handshakeProjectPaths
        controller.noteAgentCalls(lastAgentCallAt)
        controller.onRemoveProject = onRemoveProject
        controller.onOpenInNewWindow = onOpenInNewWindow
        controller.onOpenLensInNewWindow = onOpenLensInNewWindow
        controller.onRemoveFolder = onRemoveFolder
        controller.update(
            roots: OutlineTree.build(
                lenses: lenses,
                projects: projectIndex.projects,
                folders: projectIndex.folders
            ),
            selection: selection,
            activeTab: activeTab,
            lensesEnabled: lensesEnabled
        )
        // After `update` — the rows have to exist before a row can enter edit.
        controller.applyRenameRequest(renameRequest)
    }
}

/// `NSOutlineView` subclass that forwards Return / Enter to a closure so the
/// controller can begin inline rename on the selected row (the Finder idiom).
/// Falls through to `super` when unhandled, preserving default key behaviour
/// (type-select, arrow nav, ←/→ expand-collapse).
@MainActor
final class SidebarOutlineView: NSOutlineView {
    /// Returns true if the key was handled (rename began); false to fall through.
    var onCommandReturn: (() -> Bool)?

    override func keyDown(with event: NSEvent) {
        // 36 = Return, 76 = keypad Enter.
        if (event.keyCode == 36 || event.keyCode == 76), onCommandReturn?() == true {
            return
        }
        super.keyDown(with: event)
    }

    /// Let an editable name field (during inline rename) take first responder for
    /// keyboard editing. The default table implementation can refuse the field —
    /// leaving it visibly focused but with keystrokes falling through to type-select
    /// — so we approve editable text fields explicitly and defer everything else.
    /// Only rename makes a field editable, so this never affects normal selection.
    override func validateProposedFirstResponder(_ responder: NSResponder, for event: NSEvent?) -> Bool {
        if let field = responder as? NSTextField, field.isEditable { return true }
        return super.validateProposedFirstResponder(responder, for: event)
    }
}

/// Owns the `NSScrollView` + `NSOutlineView` and acts as data source + delegate.
@MainActor
final class SidebarOutlineController: NSViewController, NSOutlineViewDataSource, NSOutlineViewDelegate, NSPopoverDelegate, NSMenuDelegate, NSTextFieldDelegate {
    let outlineView = SidebarOutlineView()
    private let scrollView = NSScrollView()
    private var roots: [OutlineNode] = []

    /// Native `NSPasteboard` type for internal sidebar drags — projects *and* folders,
    /// kind-tagged by `SidebarDragItem` (decision 22 Jun: native, not `Transferable` —
    /// this migration removes the other SwiftUI drag sites). A distinct UTI so it never
    /// collides with `public.file-url` (the Finder-file drop) — the typed-payload lesson
    /// from the SwiftUI sidebar.
    static let sidebarDragType = NSPasteboard.PasteboardType("app.bristlenose.sidebar-drag")

    weak var projectIndex: ProjectIndex?
    weak var i18n: I18n?
    weak var pipelineRunner: PipelineRunner?
    weak var liveData: PipelineLiveData?
    weak var copyMachinery: CopyMachinery?
    weak var cloudImport: CloudImportCoordinator?
    var lensItems: [LensItem] = LensItem.all
    var onSelectionChange: (Set<SidebarSelection>) -> Void = { _ in }
    var onActivateLens: (Tab) -> Void = { _ in }
    var onExternalDrop: (SidebarExternalDrop, [URL]) -> Void = { _, _ in }
    var onLocate: (UUID) -> Void = { _ in }
    var onReAnalyse: (UUID) -> Void = { _ in }
    var onShowInFinder: (UUID) -> Void = { _ in }
    /// See the representable's `handshakeProjectPaths`.
    var handshakeProjectPaths: Set<String> = []
    var canShowInFinder: (UUID) -> Bool = { _ in false }
    /// See the representable's `canShareWithAgents` / `mcpMounted`.
    var canShareWithAgents: (UUID) -> Bool = { _ in false }
    var mcpMounted: Bool = false
    var onRemoveProject: (UUID) -> Void = { _ in }
    var onOpenInNewWindow: (UUID) -> Void = { _ in }
    var onOpenLensInNewWindow: (Tab) -> Void = { _ in }
    var onRemoveFolder: (UUID) -> Void = { _ in }

    /// Re-entrancy guard (spec §2.5): suppress the selection callback while we
    /// apply selection programmatically, so `selectRowIndexes` doesn't echo back.
    private var isApplyingProgrammatic = false

    /// The open row popover — diagnostic (failure glyph / menu) or icon-picker
    /// (menu). One at a time; held so opening another closes the prior. Anchored to
    /// the *outline view* (not the per-cell view), so a progress-tick `reloadData` —
    /// which rebuilds cells but keeps the outline view in the window — doesn't snap it
    /// shut. (A row moving under it via a structural change is the rare residual;
    /// transient dismissal covers it. The §2.5 targeted-`reloadItem` is the full fix.)
    private var activePopover: NSPopover?

    /// The lens of the right-clicked row, captured in `menuNeedsUpdate` for the
    /// same reason `menuClickedNodeID` is — the action fires after the menu has
    /// closed, when `clickedRow` is gone.
    private var menuClickedLens: Tab?

    /// The project/folder id of the right-clicked row, captured in `menuNeedsUpdate`
    /// and read by the menu actions (stable while the menu is open — you can't
    /// right-click a new row while a menu is up).
    private var menuClickedNodeID: UUID?

    /// The project/folder id whose name field is currently in inline edit, or nil.
    /// Load-bearing for the reload guard: `update()` calls a full `reloadData()` on
    /// every model tick (`liveData` fires at run frequency), which would tear down
    /// the active `NSText` field editor mid-type and eat keystrokes. While this is
    /// non-nil, `update()` / `paletteDidChange()` skip the reload; the commit path
    /// re-runs `update()` once editing ends (the rename mutation republishes).
    private var editingNodeID: UUID?

    /// Set true for the duration of an Escape-driven end so `controlTextDidEndEditing`
    /// reverts instead of committing (the field editor ends editing either way).
    private var cancellingEdit = false

    /// True while a drop's row animation owns the view's order. Sibling of the
    /// `editingNodeID` guard and for the same reason: `update()` reloads on every model
    /// tick, and a `reloadData` mid-slide snaps the rows into place, killing the very
    /// animation that makes a reorder feel native. `update()` still *stores* the fresh
    /// tree while suppressed; `reloadReleaseWork` reloads against it once the slide ends.
    private var reloadSuppressed = false

    /// Lifts `reloadSuppressed` when the drop animation settles. Held so a second drop
    /// mid-animation cancels the first release rather than lifting the guard early.
    private var reloadReleaseWork: DispatchWorkItem?

    /// The last selection pushed by `update()`. Held so the post-animation reload can
    /// restore it without needing SwiftUI to push another update.
    private var lastSelection: Set<SidebarSelection> = []

    /// True when the click currently being delivered CHANGED the selection. Set in
    /// `outlineViewSelectionDidChange`, consumed by the click action. The slow-second-
    /// click gesture only arms on a click landing on an ALREADY-selected row, so a
    /// click that moved the selection is a plain select and must never arm rename
    /// (this is the "block rename right after a selection change" guard, expressed as
    /// state rather than a timing threshold — exact, not heuristic).
    private var selectionChangedByCurrentClick = false

    /// Pending slow-second-click rename. Armed by a click on an already-sole-selected
    /// project/folder row, fires after `NSEvent.doubleClickInterval` elapses with no
    /// second click. A double-click cancels it (that gesture means open, not rename).
    /// The interval is READ FROM THE SYSTEM, never hard-coded — it's a user-tunable
    /// Accessibility setting (Settings ▸ Accessibility ▸ Pointer Control).
    private var renameArmTimer: Timer?

    /// The current mode/lens. Drives which lens row is genuinely selected (so the
    /// table draws its capsule) — stored on each `update`. Mode, not selection (§3.1).
    private var activeTab: Tab?

    /// Whether the lenses are interactive — true iff a report is showing. When
    /// false (no project / no report), lens rows are dimmed and clicking one is a
    /// no-op (a mode switch is meaningless without a report). Restores the SwiftUI
    /// LensRail's `isEnabled` gating that the AppKit port initially dropped.
    private var lensesEnabled = false

    // MARK: - Icon reveal (one-shot split-flap on project creation)

    /// The project currently playing its icon reveal, or nil. While set, `viewFor`
    /// hides that row's real icon so it doesn't double up with the overlay.
    private var animatingRevealID: UUID?
    /// Reveals already played this session — guards against replaying when the
    /// outline reloads during the ~2s animation (`reloadData` fires per progress tick).
    private var revealedIDs: Set<UUID> = []
    /// The live overlay image view (a subview of `outlineView`, document coords), or nil.
    private weak var revealOverlay: NSImageView?

    override func loadView() {
        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("main"))
        column.resizingMask = .autoresizingMask
        outlineView.addTableColumn(column)
        outlineView.outlineTableColumn = column
        outlineView.headerView = nil
        outlineView.style = .sourceList
        // `style = .sourceList` alone rendered the *emphasized* (vivid-blue, white
        // text) selection on test — the SwiftUI look we're escaping. The
        // deprecated-but-functional `selectionHighlightStyle` is what actually
        // yields the unemphasized source-list selection (grey ground + accent-
        // tinted content, focus-stable). Keep both; the deprecation is accepted.
        outlineView.selectionHighlightStyle = .sourceList
        outlineView.floatsGroupRows = true
        // `.custom` is REQUIRED for `heightOfRowByItem` to be consulted — any other
        // rowSizeStyle (.default/.small/.medium/.large) pins a fixed style height and
        // ignores the delegate, which silently made the variable-height + native-pitch
        // work inert (rows stayed cramped). We size icons explicitly (`iconSymbolConfig`),
        // so we don't need the style's automatic icon sizing.
        outlineView.rowSizeStyle = .custom
        outlineView.allowsMultipleSelection = true
        outlineView.allowsEmptySelection = true
        outlineView.indentationPerLevel = 14
        outlineView.dataSource = self
        outlineView.delegate = self
        outlineView.autoresizingMask = [.width, .height]
        // Two distinct destination types: `sidebarDragType` (internal reorder /
        // re-parent, `.move`) and `.fileURL` (Finder folder-of-videos import, `.copy`).
        // The payload class disambiguates them at validate/accept time — a Finder drag
        // can't read as `sidebarDragType` and a sidebar drag can't read as a file URL —
        // so the two never collide.
        outlineView.registerForDraggedTypes([Self.sidebarDragType, .fileURL])
        outlineView.setDraggingSourceOperationMask(.move, forLocal: true)
        // Right-click context menu — rebuilt per click for the `clickedRow`'s node
        // (`menuNeedsUpdate`). Ports the SwiftUI `ProjectRow`/`FolderRow` `.contextMenu`.
        let contextMenu = NSMenu()
        contextMenu.delegate = self
        contextMenu.autoenablesItems = false   // honour our explicit `isEnabled`
        outlineView.menu = contextMenu

        scrollView.documentView = outlineView
        scrollView.hasVerticalScroller = true
        scrollView.drawsBackground = false   // let the column's vibrancy through (§1.4)
        scrollView.automaticallyAdjustsContentInsets = true

        // Container built so we can layer a palette-paper tint under the
        // scrollView (the Edo half of Plan D "sidebar four"). On Default the
        // tint layer is hidden, so the sidebar renders as it did with a plain
        // `view = scrollView` — SwiftUI's NavigationSplitView provides the
        // sidebar material behind us.
        //
        // MERGE NOTE (spike → main, 3 Jul 2026): spike also carried an
        // `if BristlenoseFlags.shoalSidebar { … }` branch (SKView + frost)
        // that main had already reverted in 22c92f6f. Dropped at merge —
        // the shoal-behind-sidebar spike is not being reintroduced. See the
        // reverted commit + docs/private/design-shoal-ambient-future.md §C
        // if you want to resurrect it; requires re-adding `import SpriteKit`,
        // a `shoalSKView` stored property, and the flag in `BristlenoseFlags`.
        let container = NSView()
        container.autoresizingMask = [.width, .height]

        // Palette paper tint — plain NSView with a solid layer background at
        // low alpha. Sits above the material and below the scrollView, so a
        // parchment overlay shifts the whole sidebar hue toward Edo without
        // blocking the vibrancy signal. Hidden on Default, active on Edo,
        // toggled at runtime by `updatePaletteTint()`.
        let paletteTint = PaletteTintView()
        paletteTint.wantsLayer = true
        paletteTint.frame = container.bounds
        paletteTint.autoresizingMask = [.width, .height]
        paletteTint.onAppearanceChange = { [weak self] in
            // NSColor is dynamic and re-resolves per draw, but `.cgColor`
            // snapshots the current appearance — the CALayer background
            // otherwise stays stuck on the previous variant across a system
            // light↔dark toggle.
            self?.updatePaletteTint()
        }
        container.addSubview(paletteTint)
        self.paletteTintView = paletteTint
        updatePaletteTint()

        scrollView.frame = container.bounds
        scrollView.autoresizingMask = [.width, .height]
        container.addSubview(scrollView)   // front — rows on top

        // Live palette switch (Settings ▸ Appearance ▸ Palette). Rebuilds every
        // visible row so per-cell text/tint colours pick up the new palette and
        // updates the paper tint layer's fill in the same tick. Runs on the
        // main queue (delegate methods are @MainActor).
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(paletteDidChange),
            name: .bristlenosePaletteChanged,
            object: nil
        )

        // Fired synchronously by `ContentView` just before rows leave the
        // model, so their rects are still computable. App-wide rather than
        // per-window on purpose: only the window actually showing a given row
        // finds a non-zero rect, so every other window's handler is a no-op.
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleWillRemoveProjects(_:)),
            name: .bristlenoseWillRemoveProjects,
            object: nil
        )

        // Menu-bar "Rename …" (Project menu) arrives per window as
        // `renameRequest` on the representable — see `applyRenameRequest`. It
        // used to be two `NotificationCenter` observers, which meant Rename in
        // one window opened an editor in every window.

        // Return / Enter on a selected row begins rename (the Finder idiom — in
        // this sidebar selection already "opens", so Return is free to mean rename).
        outlineView.onCommandReturn = { [weak self] in self?.beginRenameSelected() ?? false }

        // Slow-second-click rename (Photos' sidebar idiom: click an already-selected
        // album, pause, click again → rename). Note the action fires for EVERY click
        // including the first of a double-click, which is why arming is deferred by
        // `doubleClickInterval` and cancelled by `doubleAction`.
        outlineView.target = self
        outlineView.action = #selector(outlineViewClicked(_:))
        outlineView.doubleAction = #selector(outlineViewDoubleClicked(_:))

        view = container
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
        // `renameArmTimer` is deliberately NOT invalidated here — it's a non-Sendable
        // stored property and this deinit is nonisolated. Harmless: the timer captures
        // `weak self`, so a late fire after teardown no-ops.
    }

    /// Live palette-change hook. Called on `.bristlenosePaletteChanged` (fired
    /// by `AppearanceSettingsView`'s `@AppStorage("palette")` `.onChange`).
    @objc private func paletteDidChange() {
        updatePaletteTint()
        guard editingNodeID == nil else { return }   // don't tear down an active edit
        guard !reloadSuppressed else { return }      // don't snap a mid-slide drop
        outlineView.reloadData()
    }

    /// The paper tint layer, held weakly. `nil` after teardown; `updatePaletteTint`
    /// no-ops in that case. Its NSView subclass captures the appearance-change
    /// callback so we can re-snapshot the dynamic `CGColor` on light↔dark.
    private weak var paletteTintView: PaletteTintView?

    /// Paints the Edo paper tint on the sidebar overlay layer, or hides it on
    /// Default. Alpha is a taste value — 0.35 is a first pass; expect dark
    /// mode to want ≤ 0.20 after eyeballing. Tune live without rebuilding:
    ///   defaults write app.bristlenose BristlenoseSidebarTintAlpha -float 0.22
    /// then post `.bristlenosePaletteChanged` (any palette flip in Settings).
    private func updatePaletteTint() {
        guard let tint = paletteTintView else { return }
        if let color = SidebarPalette.paperTint {
            let d = UserDefaults.standard
            let alpha: CGFloat = d.object(forKey: "BristlenoseSidebarTintAlpha") != nil
                ? CGFloat(d.float(forKey: "BristlenoseSidebarTintAlpha"))
                : 0.35
            tint.layer?.backgroundColor = color.withAlphaComponent(alpha).cgColor
            tint.isHidden = false
        } else {
            tint.isHidden = true
            tint.layer?.backgroundColor = nil
        }
    }

    /// Push a fresh tree + selection + active lens. Rebuilds the outline, restores
    /// expansion (groups always; folders per `collapsed`), and reflects selection.
    func update(roots: [OutlineNode], selection: Set<SidebarSelection>, activeTab: Tab?,
                lensesEnabled: Bool) {
        self.roots = roots
        self.activeTab = activeTab
        self.lensesEnabled = lensesEnabled
        self.lastSelection = selection

        // Reload guard: a `reloadData` while a name field is being edited destroys
        // its field editor and drops the in-flight keystrokes. Freeze the table
        // (model is already stored above) until the edit commits — the commit path
        // republishes and re-enters `update()` with `editingNodeID == nil`.
        guard editingNodeID == nil else { return }
        // Same shape, different owner: a drop animation is mid-slide and the view's row
        // order is ahead of the tree. The release work item reloads against whatever
        // tree landed while suppressed.
        guard !reloadSuppressed else { return }

        reloadAndRestore()
    }

    /// Reload the table and put back everything a `reloadData` drops: expansion,
    /// selection, and the two one-shot gestures. Extracted from `update()` so the
    /// post-drop-animation release can re-run exactly the same tail.
    private func reloadAndRestore() {
        outlineView.reloadData()

        // Expand groups (always) + non-collapsed folders.
        for group in roots where group.isGroup {
            outlineView.expandItem(group)
            for child in group.children where isFolderExpanded(child) {
                outlineView.expandItem(child)
            }
        }

        applySelection(lastSelection)

        // Kick off the one-shot icon reveal for a freshly-created project, if any.
        maybeStartIconReveal()

        // Begin inline rename for a just-created folder / a menu-triggered rename.
        maybeStartRename()
    }

    // MARK: - Icon reveal

    /// Start the split-flap reveal for `projectIndex.pendingIconReveal`, if there is
    /// one we haven't played. The overlay is a subview of `outlineView` (document
    /// coords) so it scrolls with the row and survives the per-tick `reloadData` that
    /// would destroy a cell-level animation. Falls back to a static reveal (just
    /// consume the trigger) under Reduce Motion or when the row is offscreen.
    private func maybeStartIconReveal() {
        guard animatingRevealID == nil,
              let index = projectIndex,
              let id = index.pendingIconReveal,
              !revealedIDs.contains(id),
              let project = index.projects.first(where: { $0.id == id }),
              let symbol = project.icon else { return }

        if NSWorkspace.shared.accessibilityDisplayShouldReduceMotion {
            revealedIDs.insert(id)
            index.consumeIconReveal(id)
            return
        }

        guard let row = projectRow(forID: id),
              let cell = outlineView.view(atColumn: 0, row: row, makeIfNecessary: true) as? NSTableCellView,
              let iconView = cell.imageView else {
            revealedIDs.insert(id)
            index.consumeIconReveal(id)
            return
        }

        // Force layout BEFORE reading the icon's frame — right after reloadData the
        // cell exists but Auto Layout hasn't resolved, so iconView.frame is still
        // .zero and the overlay would be 0×0 (invisible). Without this the real icon
        // is hidden, the overlay shows nothing, then the icon "pops" in at the end.
        outlineView.layoutSubtreeIfNeeded()
        let iconRect = iconView.convert(iconView.bounds, to: outlineView)
        guard iconRect.width > 1, iconRect.height > 1 else {
            // Still no usable frame — fall back to a static reveal rather than a blank.
            index.consumeIconReveal(id)
            return
        }

        animatingRevealID = id
        revealedIDs.insert(id)
        iconView.alphaValue = 0   // hide the real icon; viewFor keeps it hidden on rebuilds

        let overlay = NSImageView(frame: iconRect)
        overlay.imageScaling = .scaleProportionallyUpOrDown
        overlay.symbolConfiguration = ProjectCellSpec.iconSymbolConfig
        overlay.contentTintColor = project.availability.isReady ? .labelColor : .secondaryLabelColor
        overlay.wantsLayer = true
        outlineView.addSubview(overlay)   // appended → top of z-order, above the rows
        revealOverlay = overlay

        Task { @MainActor [weak self] in
            await SidebarIconFlip.play(on: overlay, settlingOn: symbol, tint: overlay.contentTintColor)
            guard let self else { overlay.removeFromSuperview(); return }
            self.animatingRevealID = nil
            // Reload guard: don't tear down an in-flight inline rename on a different
            // row (a 2s icon flip can outlast the start of a rename). The stale-hidden
            // icon self-heals on the rename commit's reload.
            if self.editingNodeID == nil {
                self.outlineView.reloadData()   // rebuild the cell with its icon visible (alpha 1)
            }
            overlay.removeFromSuperview()    // reveal the identical static icon underneath
            if self.revealOverlay === overlay { self.revealOverlay = nil }
            index.consumeIconReveal(id)
        }
    }

    /// The outline row currently displaying project `id`, or nil if absent/offscreen.
    private func projectRow(forID id: UUID) -> Int? {
        for r in 0..<outlineView.numberOfRows {
            if case .project(let pid)? = (outlineView.item(atRow: r) as? OutlineNode)?.kind, pid == id {
                return r
            }
        }
        return nil
    }

    /// Hide a project cell's icon while its reveal overlay is animating, so the two
    /// don't double up. No-op for every other project / when nothing is revealing.
    private func hideIconIfRevealing(_ cell: NSTableCellView, id: UUID) -> NSTableCellView {
        if animatingRevealID == id { cell.imageView?.alphaValue = 0 }
        return cell
    }

    // MARK: - Inline rename (editable name field — the view-based-table idiom)

    /// Consume a pending rename trigger (`projectIndex.pendingRename`) after a
    /// reload, opening the row's editable name field. Mirrors `maybeStartIconReveal`
    /// — the single seam all four rename entry points feed (create · menu bar ·
    /// context menu · Return).
    private func maybeStartRename() {
        guard editingNodeID == nil,
              let index = projectIndex,
              let id = index.pendingRename else { return }
        index.consumeRename(id)          // one-shot: clear even if the row is offscreen
        beginRename(nodeID: id)
    }

    /// Begin inline editing of a project/folder row's name field. The stock
    /// view-based-table recipe (mattrajca / Apple SourceView): flip the display
    /// `NSTextField` label into an edit box, become first responder, `selectText`
    /// to select the whole name (type-to-replace). No-op if already editing or the
    /// row is offscreen.
    private func beginRename(nodeID id: UUID) {
        guard editingNodeID == nil, let row = row(forNodeID: id), row >= 0 else { return }
        outlineView.scrollRowToVisible(row)
        guard let cell = outlineView.view(atColumn: 0, row: row, makeIfNecessary: true) as? NSTableCellView,
              let field = cell.textField else { return }
        editingNodeID = id
        field.isEditable = true
        field.isSelectable = true
        field.isBordered = true
        field.isBezeled = true
        field.bezelStyle = .squareBezel
        field.drawsBackground = true
        field.delegate = self
        // Canonical view-based begin: `editColumn` engages the table's editing
        // session, installs the window field editor as first responder, and selects
        // all. (`makeFirstResponder(field)` + `selectText` alone leaves the OUTLINE
        // as first responder — the field draws its selection but keystrokes fall
        // through to NSOutlineView type-select, so typing "does nothing".)
        outlineView.editColumn(0, row: row, with: nil, select: true)
        guard field.currentEditor() != nil else {
            // Editing didn't engage (e.g. no key window) — roll back rather than
            // freeze the table on a stuck `editingNodeID` (reload guard never lifts).
            editingNodeID = nil
            restoreLabelChrome(field)
            return
        }
    }

    /// Return-key / menu-triggered rename of the sole selected renamable row.
    @discardableResult
    private func beginRenameSelected() -> Bool {
        let ids = selectedRenamableNodeIDs()
        guard ids.count == 1, let id = ids.first else { return false }
        beginRename(nodeID: id)
        return true
    }

    /// Menu-bar Project ▸ Rename … — begins rename on the sole selected row.
    ///
    /// Driven by the representable's `renameRequest` counter, which only this
    /// window's `WindowCommandSink` bumps. The initial value is 0 on both sides,
    /// so a freshly-created controller never fires; every later change is a
    /// genuine press. The menu items are already selection-gated in
    /// `MenuCommands`; `beginRenameSelected` is the safety net.
    func applyRenameRequest(_ request: Int) {
        guard request != lastRenameRequest else { return }
        lastRenameRequest = request
        beginRenameSelected()
    }

    /// Last `renameRequest` acted on — see `applyRenameRequest`.
    private var lastRenameRequest = 0

    // MARK: - Slow-second-click rename (Photos' sidebar idiom)

    /// Every click in the outline. Arms rename only for the Finder/Photos gesture:
    /// a click landing on an **already sole-selected** project/folder row, with no
    /// second click inside the system double-click interval.
    ///
    /// Three guards, each closing a real misfire:
    ///  1. `selectionChangedByCurrentClick` — the click that *made* the selection
    ///     must not also arm rename (that's a plain select).
    ///  2. sole-selection — never rename out of a multi-row selection.
    ///  3. the deferred timer — the action fires for the first click of a
    ///     double-click too, so arming waits out `doubleClickInterval` and
    ///     `outlineViewDoubleClicked` cancels it.
    @objc private func outlineViewClicked(_ sender: Any?) {
        let changedSelection = selectionChangedByCurrentClick
        selectionChangedByCurrentClick = false
        renameArmTimer?.invalidate()
        renameArmTimer = nil

        guard !changedSelection, editingNodeID == nil else { return }
        let row = outlineView.clickedRow
        guard row >= 0 else { return }   // empty space

        // D3 (Finder model): clicking the ACTIVE lens re-activates it —
        // `activateLens` routes a same-lens activation to the lens root, so a
        // transcript's Sessions click returns to the grid. This click action
        // is the reliable delegate for that case: the active lens row is
        // already part of the genuine selection, so a click on it may not
        // re-propose a selection change and `selectionIndexesForProposed-
        // Selection` (which handles every OTHER lens click) never fires.
        // Disjoint by construction — the proposal path is gated
        // `tab != activeTab`, this one `tab == activeTab` — so no click can
        // fire both. Lens rows never arm rename either way.
        if let lensNode = outlineView.item(atRow: row) as? OutlineNode,
           case .lens(let tab) = lensNode.kind {
            if lensesEnabled, tab == activeTab {
                DispatchQueue.main.async { [weak self] in self?.onActivateLens(tab) }
            }
            return
        }

        // Sole-selection among the renamable rows. `selectedRowIndexes` can also
        // carry the active lens (composed capsule), so filter to selectable rows
        // rather than testing `.count == 1` on the raw set.
        let selectable = selectableRows(in: outlineView.selectedRowIndexes)
        guard selectable.count == 1, selectable.contains(row) else { return }

        guard let node = outlineView.item(atRow: row) as? OutlineNode else { return }
        let id: UUID
        switch node.kind {
        case .project(let pid): id = pid
        case .folder(let fid): id = fid
        case .lens, .group: return
        }

        // Clicking the disclosure triangle expands/collapses — never renames.
        if case .folder = node.kind {
            let triangle = outlineView.frameOfOutlineCell(atRow: row)
            let point = outlineView.convert(NSApp.currentEvent?.locationInWindow ?? .zero, from: nil)
            if triangle.contains(point) { return }
        }

        renameArmTimer = Timer.scheduledTimer(
            withTimeInterval: NSEvent.doubleClickInterval, repeats: false
        ) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                self.renameArmTimer = nil
                self.beginRename(nodeID: id)
            }
        }
    }

    /// A double-click means open, not rename — cancel any armed rename. (The
    /// open-in-its-own-window action lands here when multi-window ships.)
    @objc private func outlineViewDoubleClicked(_ sender: Any?) {
        renameArmTimer?.invalidate()
        renameArmTimer = nil
    }

    /// The project/folder ids in the current selection (excludes lens/group rows).
    private func selectedRenamableNodeIDs() -> [UUID] {
        outlineView.selectedRowIndexes.compactMap { r -> UUID? in
            guard let node = outlineView.item(atRow: r) as? OutlineNode else { return nil }
            switch node.kind {
            case .project(let id), .folder(let id): return id
            default: return nil
            }
        }
    }

    /// The outline row displaying project/folder `id`, or nil if absent/offscreen.
    private func row(forNodeID id: UUID) -> Int? {
        for r in 0..<outlineView.numberOfRows {
            guard let node = outlineView.item(atRow: r) as? OutlineNode else { continue }
            switch node.kind {
            case .project(let pid) where pid == id: return r
            case .folder(let fid) where fid == id: return r
            default: continue
            }
        }
        return nil
    }

    /// The model name of a project/folder node, for revert-on-cancel/empty.
    private func currentName(forNodeID id: UUID) -> String? {
        if let f = projectIndex?.folders.first(where: { $0.id == id }) { return f.name }
        if let p = projectIndex?.projects.first(where: { $0.id == id }) { return p.name }
        return nil
    }

    /// Route a committed name to the right model mutator (folder or project). Both
    /// de-duplicate and persist; the republish re-enters `update()` → `reloadData`.
    private func applyRename(id: UUID, newName: String) {
        guard let index = projectIndex else { return }
        if index.folders.contains(where: { $0.id == id }) {
            index.renameFolder(id: id, newName: newName)
        } else if index.projects.contains(where: { $0.id == id }) {
            index.renameProject(id: id, newName: newName)
        }
    }

    /// Restore a cell's name field from edit box back to a display label.
    private func restoreLabelChrome(_ field: NSTextField) {
        field.isEditable = false
        field.isSelectable = false
        field.isBordered = false
        field.isBezeled = false
        field.drawsBackground = false
        field.delegate = nil
    }

    // MARK: NSTextFieldDelegate (rename commit / cancel)

    func controlTextDidBeginEditing(_ obj: Notification) {
        // Defensive: if editing began without `beginRename` (future slow-second-
        // click path), stamp the edited node so the reload guard + commit resolve it.
        guard editingNodeID == nil, let field = obj.object as? NSTextField else { return }
        let row = outlineView.row(for: field)
        guard row >= 0, let node = outlineView.item(atRow: row) as? OutlineNode else { return }
        switch node.kind {
        case .project(let id), .folder(let id): editingNodeID = id
        default: break
        }
    }

    func controlTextDidEndEditing(_ obj: Notification) {
        guard let field = obj.object as? NSTextField else { return }
        let id = editingNodeID
        let typed = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        let cancelled = cancellingEdit
        // Clear edit state BEFORE mutating the model — the rename republishes and
        // re-enters `update()`, which must see `editingNodeID == nil` to reload.
        editingNodeID = nil
        cancellingEdit = false
        restoreLabelChrome(field)

        guard let id else { return }
        let model = currentName(forNodeID: id)
        if !cancelled, !typed.isEmpty, typed != model {
            applyRename(id: id, newName: typed)   // commit → publish → update() → reload
        } else {
            // Cancel / empty / unchanged: revert the visible label to the model
            // (Finder keeps the folder + its prior name; never writes a blank label).
            field.stringValue = model ?? field.stringValue
            // ...and reload, because this branch mutates nothing. `update()`
            // *stores* every model tick that arrives during an edit but skips
            // the reload (the guard above — a `reloadData` would tear down the
            // live field editor). The commit branch gets its reload for free
            // from the rename republishing; this one has no such republish, so
            // anything that landed mid-edit — a watcher delta, a session count,
            // a run reaching its terminus — stays undrawn until some unrelated
            // tick happens by. Escape out of a rename and the row could sit
            // stale indefinitely.
            reloadAndRestore()
        }
    }

    func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        if selector == #selector(NSResponder.cancelOperation(_:)) {   // Escape
            cancellingEdit = true
            // Resigning first responder ends editing → controlTextDidEndEditing reverts.
            textView.window?.makeFirstResponder(outlineView)
            return true
        }
        return false
    }

    private func isFolderExpanded(_ node: OutlineNode) -> Bool {
        guard case .folder(let id) = node.kind else { return false }
        let collapsed = projectIndex?.folders.first { $0.id == id }?.collapsed ?? false
        return !collapsed
    }

    private func applySelection(_ selection: Set<SidebarSelection>) {
        isApplyingProgrammatic = true
        defer { isApplyingProgrammatic = false }
        var projectRows = IndexSet()
        for node in allSelectableNodes() {
            if let sel = node.selection, selection.contains(sel) {
                let row = outlineView.row(forItem: node)
                if row >= 0 { projectRows.insert(row) }
            }
        }
        // Compose with the active lens row (genuine-selection: the SYSTEM draws its
        // source-list capsule — exact, internal to the table; §3.1). The lens carries
        // `selection == nil`, so it's filtered out of SidebarSelection in
        // `outlineViewSelectionDidChange` and never reaches serve.
        let rows = composedSelection(projectRows: projectRows)
        outlineView.selectRowIndexes(rows, byExtendingSelection: false)
    }

    /// The outline row of the active lens, or nil. Lets us keep the active lens
    /// genuinely selected (so the table draws its capsule) without it ever joining
    /// the `SidebarSelection` set — serve/persist read `node.selection`, which is nil
    /// for lenses. Lens rows live one level under the (always-expanded) Lenses group.
    private func activeLensRow() -> Int? {
        guard let activeTab else { return nil }
        for group in roots {
            for child in group.children {
                if case .lens(let tab) = child.kind, tab == activeTab {
                    let row = outlineView.row(forItem: child)
                    return row >= 0 ? row : nil
                }
            }
        }
        return nil
    }

    private func allSelectableNodes() -> [OutlineNode] {
        var result: [OutlineNode] = []
        func walk(_ nodes: [OutlineNode]) {
            for node in nodes {
                if node.isSelectable { result.append(node) }
                walk(node.children)
            }
        }
        walk(roots)
        return result
    }

    // MARK: - NSOutlineViewDataSource

    func outlineView(_ outlineView: NSOutlineView, numberOfChildrenOfItem item: Any?) -> Int {
        node(from: item)?.children.count ?? roots.count
    }

    func outlineView(_ outlineView: NSOutlineView, child index: Int, ofItem item: Any?) -> Any {
        (node(from: item)?.children ?? roots)[index]
    }

    func outlineView(_ outlineView: NSOutlineView, isItemExpandable item: Any) -> Bool {
        (item as? OutlineNode)?.isExpandable ?? false
    }

    // MARK: - NSOutlineViewDelegate

    func outlineView(_ outlineView: NSOutlineView, isGroupItem item: Any) -> Bool {
        (item as? OutlineNode)?.isGroup ?? false
    }

    func outlineView(_ outlineView: NSOutlineView, shouldSelectItem item: Any) -> Bool {
        guard let node = item as? OutlineNode else { return false }
        // This method ONLY reports selectability. Lens + group rows aren't part of the
        // project selection set, so they're not click-selectable on their own; the
        // active lens's genuine source-list capsule is composed programmatically in
        // applySelection (programmatic selectRowIndexes bypasses this method anyway).
        //
        // DEAD END — do NOT fire lens activation (onActivateLens / switchToTab) from
        // here. It's the obvious-looking home for a row-click side effect, and it WAS
        // here first — but on a lens click it is NEVER CALLED once
        // selectionIndexesForProposedSelection overrides the proposal to keep the
        // project: AppKit doesn't consult shouldSelectItem for a row that won't end up
        // selected. The activation silently never ran (zero `shouldSelect` lines in the
        // live os_log trace on a lens click). Activation lives in the proposal handler
        // below, the one delegate reliably called with the clicked lens.
        return node.isSelectable
    }

    /// Exclude mode rows (lenses) + group headers from type-select, so typing "c"
    /// jumps to a project, not the "Codebook" lens — the lens labels were in the
    /// type-select corpus, a guaranteed-reachable wrong selection on plain keyboard
    /// use (gruber). Selectable rows return their name so type-select still works.
    func outlineView(_ outlineView: NSOutlineView,
                     typeSelectStringFor tableColumn: NSTableColumn?, item: Any) -> String? {
        guard let node = item as? OutlineNode else { return nil }
        switch node.kind {
        case .project(let id): return projectIndex?.projects.first { $0.id == id }?.name
        case .folder(let id): return projectIndex?.folders.first { $0.id == id }?.name
        case .lens, .group: return nil
        }
    }

    /// Maintain the invariant `selectedRowIndexes = {active lens} ∪ {project selection}`
    /// against the table's natural click behaviour:
    ///  - click a LENS / group (non-selectable) → it's a mode switch, NOT a selection
    ///    change → **keep the current project selection** (the lens swap rides
    ///    `activeTab` → `applySelection`). Without this, a lens click proposes an
    ///    EMPTY selection (the clicked row is unselectable), dropping the project →
    ///    "No Project Selected" — the bug.
    ///  - click a project / arrow-nav / empty-space → honour the proposed project rows.
    /// Then always pin the active lens (when enabled) so its capsule stays drawn. This is
    /// also the ONE place lens activation fires — the only delegate reliably called with
    /// the clicked lens (see the DEAD END note on `shouldSelectItem`).
    ///
    /// TWO MORE DEAD ENDS — both looked right, both shipped a bug; do not re-introduce:
    ///  1. Using `clickedRow` + `NSApp.currentEvent` to tell a lens-click from
    ///     empty-space. Seductive (it's how you'd disambiguate a click elsewhere) and it
    ///     was tried — but at the instant THIS delegate runs, `currentEvent` is NOT a
    ///     `.leftMouseDown` on a genuine lens click, so the event-gate read
    ///     `clickedRow == -1` and fell through to *deselect* → dropped the project. The
    ///     reliable signal is the **proposed set itself**: AppKit puts the clicked (even
    ///     unselectable) lens row INTO `proposedSelectionIndexes`, so we read the
    ///     mode-click from that — no event introspection. (gruber suggested the
    ///     event-gate as keyboard safety; it turned out to BE the bug. Read the table's
    ///     own truth; don't reconstruct intent from `NSApp.currentEvent`.)
    ///  2. Optimistically selecting the clicked lens row for instant capsule feedback.
    ///     `update()` re-runs `applySelection` many times/sec, recomposing the capsule
    ///     from the *current* `activeTab` — which hasn't caught up to the just-clicked
    ///     lens yet → the optimistic capsule snaps back to the old lens for a frame, then
    ///     forward → flicker. So the capsule follows `activeTab` HONESTLY (one-cycle lag,
    ///     no flicker). Revisit only if `reloadData`-on-every-`update` churn is gated.
    func outlineView(_ outlineView: NSOutlineView,
                     selectionIndexesForProposedSelection proposedSelectionIndexes: IndexSet) -> IndexSet {
        if isApplyingProgrammatic { return proposedSelectionIndexes }
        // Project component of the new selection.
        let selectableProposed = selectableRows(in: proposedSelectionIndexes)
        let projectRows: IndexSet
        if !selectableProposed.isEmpty {
            // A project click or arrow-nav proposing a project → honour it.
            projectRows = selectableProposed
        } else if let lensRow = proposedSelectionIndexes.first(where: {
            (outlineView.item(atRow: $0) as? OutlineNode)?.isLens == true
        }) {
            // A lens row IS in the proposed set — the table includes the clicked row in
            // the proposal even though it's unselectable. This is a MODE switch, not a
            // selection change, so: (1) keep the current project (its capsule stays);
            // (2) fire the activation HERE — this is the one delegate reliably called
            // with the clicked lens (shouldSelectItem is not, when this method overrides
            // the proposal). The lens capsule moves when switchToTab updates
            // activeTab → applySelection (honest: capsule follows the route). We
            // deliberately do NOT optimistically select the clicked lens row — update()
            // re-runs applySelection many times/sec and would snap an optimistic capsule
            // back to the stale activeTab's lens before the route lands, a flicker.
            // Defer the activation off this call stack so switchToTab's state write can't
            // re-enter applySelection mid-proposal (gruber's re-entrancy guard). The
            // `tab != activeTab` gate is DEDUPE plumbing, not policy: re-clicking the
            // active lens is handled by `outlineViewClicked` (the click action), because
            // a click on the already-selected active row may never re-propose and so
            // never reaches this delegate. Same-lens semantics (return to lens root, D3)
            // live in `BridgeHandler.activateLens` for every caller.
            projectRows = selectableRows(in: outlineView.selectedRowIndexes)
            if case .lens(let tab)? = (outlineView.item(atRow: lensRow) as? OutlineNode)?.kind,
               lensesEnabled, tab != activeTab {
                DispatchQueue.main.async { [weak self] in self?.onActivateLens(tab) }
            }
        } else {
            // Truly empty proposal → empty-space / keyboard deselect.
            projectRows = IndexSet()
        }
        return composedSelection(projectRows: projectRows)
    }

    /// The single place the `selected = {project rows} ∪ {active lens}` invariant is
    /// composed — gruber: don't reassert the lens-injection rule at every call site.
    private func composedSelection(projectRows: IndexSet) -> IndexSet {
        var result = projectRows
        if lensesEnabled, let lensRow = activeLensRow() { result.insert(lensRow) }
        return result
    }

    /// The selectable (project/folder) subset of an index set — excludes lens + group rows.
    private func selectableRows(in indexes: IndexSet) -> IndexSet {
        var result = IndexSet()
        for row in indexes where (outlineView.item(atRow: row) as? OutlineNode)?.isSelectable == true {
            result.insert(row)
        }
        return result
    }

    func outlineView(_ outlineView: NSOutlineView, rowViewForItem item: Any) -> NSTableRowView? {
        // All rows — including the genuinely-selected active lens — use the shared
        // source-list row view, so the table draws every selection (project + active
        // lens) identically with its own internal rendering. The source-list
        // selection colour is internal to the table and matches no public token
        // (verified by sampling every UI-element-colour), so a hand-placed capsule
        // can't match — genuine selection is the only exact path.
        SourceListSelectionRowView()
    }

    func outlineViewSelectionDidChange(_ notification: Notification) {
        if isApplyingProgrammatic { return }
        // A user-driven selection change. If a click caused it, that click is a plain
        // select and must not also arm the slow-second-click rename (consumed, and
        // reset, by `outlineViewClicked`). Programmatic selection returns above, so
        // `update()`'s re-selection churn can't spuriously suppress the gesture.
        selectionChangedByCurrentClick = true
        // Keyboard nav (arrow keys) moves selection without a click action, so a
        // rename armed on the previous row would fire against a row the user has
        // since left. Drop it — the gesture is click-initiated only.
        renameArmTimer?.invalidate()
        renameArmTimer = nil
        var selection = Set<SidebarSelection>()
        for row in outlineView.selectedRowIndexes {
            if let node = outlineView.item(atRow: row) as? OutlineNode,
               let sel = node.selection {
                selection.insert(sel)
            }
        }
        onSelectionChange(selection)
    }

    // MARK: - Drag and drop (the unified insertion model — apocalypse fix)

    func outlineView(_ outlineView: NSOutlineView, pasteboardWriterForItem item: Any) -> NSPasteboardWriting? {
        // `dragItem` is nil for group headers and lens rows — chrome and modes have no
        // place in the order, so they aren't draggable. Projects and folders both are.
        guard let node = item as? OutlineNode, let dragItem = node.dragItem else { return nil }
        let pbItem = NSPasteboardItem()
        pbItem.setString(dragItem.pasteboardString, forType: Self.sidebarDragType)
        return pbItem
    }

    func outlineView(_ outlineView: NSOutlineView, validateDrop info: NSDraggingInfo,
                     proposedItem item: Any?, proposedChildIndex index: Int) -> NSDragOperation {
        // Finder folder/file import takes precedence over the internal-reorder
        // path (the two payload types are mutually exclusive on the pasteboard).
        if pasteboardHasFileURLs(info.draggingPasteboard) {
            guard let target = externalDropTarget(item: item) else { return [] }
            // Answer during the drag, not after it. Returning `[]` makes AppKit
            // draw no row highlight, swap the pointer to operation-not-allowed,
            // and spring the item back — the whole refusal, in every language,
            // for free. Until Aug 2026 this returned `.copy` for any project
            // row and left the question to `ContentView`, which could then only
            // answer with a toast three seconds after the researcher had
            // already let go. `docs/design-analysis-lifecycle.md` §4.2.
            if case .project(let id) = target,
               !Self.acceptsFinderDrop(state: pipelineRunner?.state[id]) {
                return []
            }
            // Retarget the highlight to match where the drop will actually land:
            // a project/folder row (drop-on) or the whole list (root). Without
            // this the outline draws an insertion line mid-list for a drop that
            // semantically means "new project at root".
            switch target {
            case .root:
                outlineView.setDropItem(nil, dropChildIndex: NSOutlineViewDropOnItemIndex)
            case .folder, .project:
                outlineView.setDropItem(item, dropChildIndex: NSOutlineViewDropOnItemIndex)
            }
            return .copy
        }
        // A folder can't nest — retarget to a root insertion line rather than refuse.
        if let retarget = folderNestingRetarget(info: info, item: item) {
            outlineView.setDropItem(retarget.parent, dropChildIndex: retarget.index)
            return .move
        }
        return decideDrop(info: info, item: item, index: index) == nil ? [] : .move
    }

    func outlineView(_ outlineView: NSOutlineView, acceptDrop info: NSDraggingInfo,
                     item: Any?, childIndex index: Int) -> Bool {
        // Finder folder/file import — route by target to the substrate-independent
        // ContentView handlers (which own all the drop policy: dedupe, analyse-
        // unless-done, state guards). The AppKit side just collects URLs + target.
        if pasteboardHasFileURLs(info.draggingPasteboard) {
            guard let target = externalDropTarget(item: item) else { return false }
            let urls = readFileURLs(from: info.draggingPasteboard)
            guard !urls.isEmpty else { return false }
            onExternalDrop(target, urls)
            return true
        }

        guard let plan = decideDrop(info: info, item: item, index: index),
              let projectIndex else { return false }
        performDrop(plan, in: projectIndex)
        return true
    }

    /// Commit a drop: mutate the model, then slide the rows into their new places.
    ///
    /// `NSOutlineView.moveItem` is what makes a reorder feel native — the insertion line
    /// during the drag comes free, the settle on drop does not, and a `reloadData` snaps.
    /// But `moveItem` is a *view* instruction that assumes the data source already
    /// agrees, so the ordering here is load-bearing:
    ///
    /// 1. resolve the final order against the **pre-move** scope (`plan.atIndex` is in
    ///    those coordinates);
    /// 2. suppress the reload, so the republish this mutation triggers can't snap the
    ///    rows mid-slide;
    /// 3. mutate the model, and immediately re-derive `roots` from it — `update()` is
    ///    suppressed and would otherwise leave the data source a step behind the row
    ///    moves, which is how you earn an AppKit consistency exception;
    /// 4. move the rows, and release the guard once the slide settles.
    private func performDrop(_ plan: DropPlan, in index: ProjectIndex) {
        let before: [UUID] = plan.toFolder
            .map { index.projectsInFolder($0).map(\.id) } ?? index.sidebarItems.map(\.id)
        let finalOrder = DropRouting.reordered(
            scope: before, inserting: plan.items.map(\.id), at: plan.atIndex)

        reloadSuppressed = true
        index.apply(plan)
        roots = OutlineTree.build(lenses: lensItems,
                                  projects: index.projects,
                                  folders: index.folders)

        animateRowMoves(plan, finalOrder: finalOrder)

        // Lift the guard once the slide has settled and reload against the tree stored
        // meanwhile — model and view already agree, so it's visually a no-op. It still
        // has to happen, or the next structural change diffs against a tree the table
        // never loaded.
        reloadReleaseWork?.cancel()
        let release = DispatchWorkItem { [weak self] in
            guard let self else { return }
            self.reloadSuppressed = false
            guard self.editingNodeID == nil else { return }
            self.reloadAndRestore()
        }
        reloadReleaseWork = release
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.dropAnimationSettle, execute: release)
    }

    /// Animate the moved rows to their final slots. Walking them in final order and
    /// moving each to its final index is the standard `moveItem` idiom: AppKit re-bases
    /// its own child indices after each call, so reading `childIndex(forItem:)` inside
    /// the loop is self-correcting and needs no index bookkeeping.
    ///
    /// The nodes come from the freshly-rebuilt tree while the outline still holds the
    /// pre-move ones — `OutlineNode` compares by model id, so AppKit matches them and
    /// `childIndex`/`parent` correctly report the row's *current* (source) place.
    private func animateRowMoves(_ plan: DropPlan, finalOrder: [UUID]) {
        let parentNode = plan.toFolder.flatMap { node(for: .folder($0)) } ?? projectsGroupNode
        guard let destinationParent = parentNode else { return }

        outlineView.beginUpdates()
        for item in plan.items {
            guard let node = node(for: item),
                  let destination = finalOrder.firstIndex(of: item.id) else { continue }
            // -1 for a row inside a collapsed folder, whose children the outline hasn't
            // loaded. Nothing to animate; the release reload shows the new order.
            let source = outlineView.childIndex(forItem: node)
            guard source >= 0 else { continue }
            outlineView.moveItem(at: source,
                                 inParent: outlineView.parent(forItem: node),
                                 to: destination,
                                 inParent: destinationParent)
        }
        outlineView.endUpdates()
    }

    /// How long to hold the reload guard after a drop. Comfortably longer than
    /// AppKit's own row-move animation, short enough that a suppressed progress tick
    /// isn't noticeable (the ring/subtitle resume on the release reload).
    private static let dropAnimationSettle: TimeInterval = 0.35

    /// The "Projects" group node — the parent of the root-scope rows, and so the
    /// `inParent:` for any root-level `moveItem`.
    private var projectsGroupNode: OutlineNode? {
        roots.first { $0.kind == .group(OutlineTree.projectsGroupKey) }
    }

    /// The live node for a dragged item. One level of nesting, so root children and
    /// their folder children are the whole search space.
    private func node(for item: SidebarDragItem) -> OutlineNode? {
        guard let group = projectsGroupNode else { return nil }
        for child in group.children {
            if child.dragItem == item { return child }
            for grandchild in child.children where grandchild.dragItem == item {
                return grandchild
            }
        }
        return nil
    }

    /// A folder dragged over a folder row, retargeted to an insertion line *above* that
    /// row in the root sequence. `OutlineNode` models one level (folder → project), so
    /// nesting is refused in `DropRouting.resolve` — but refusing at the highlight stage
    /// too would give a refuse cursor over exactly the rows a user aims at when
    /// rearranging folders. Retargeting keeps the gesture landing somewhere sensible.
    private func folderNestingRetarget(info: NSDraggingInfo, item: Any?)
        -> (parent: OutlineNode, index: Int)? {
        guard draggedItems(from: info).contains(where: \.isFolder),
              let node = item as? OutlineNode,
              case .folder = node.kind,
              let parent = node.parent,
              let index = parent.children.firstIndex(where: { $0 === node })
        else { return nil }
        return (parent, index)
    }

    // MARK: - External (Finder) drop routing

    /// Whether the drag carries Finder file URLs (vs an internal project drag).
    private func pasteboardHasFileURLs(_ pasteboard: NSPasteboard) -> Bool {
        pasteboard.canReadObject(forClasses: [NSURL.self],
                                 options: [.urlReadingFileURLsOnly: true])
    }

    /// Read the dragged Finder file URLs. Filtering (accepted media types, OS
    /// metadata sidecars, analysed-folder guards) is the ContentView handlers' job.
    private func readFileURLs(from pasteboard: NSPasteboard) -> [URL] {
        (pasteboard.readObjects(forClasses: [NSURL.self],
                                options: [.urlReadingFileURLsOnly: true]) as? [URL]) ?? []
    }

    /// Resolve where an external drop lands (pure logic in `SidebarExternalDrop.resolve`).
    /// Whether a Finder drop on a project can be accepted, decided from the
    /// state alone so `validateDrop` can answer mid-drag.
    ///
    /// The same three refusals `ContentView` used to make after the drop, moved
    /// to where the HIG puts them. `.failed` is a policy refusal rather than a
    /// physical one — copying is possible, but the run would not start and the
    /// files would sit unanalysed — and it is kept as-is here: this change swaps
    /// the *grammar* of the refusal, not the set of things refused. Whether a
    /// failed project should accept files at all is a separate question.
    nonisolated static func acceptsFinderDrop(state: PipelineState?) -> Bool {
        switch state {
        case .running, .queued, .failed, .failedWithDiagnostic, .unreachable:
            return false
        default:
            return true
        }
    }

    private func externalDropTarget(item: Any?) -> SidebarExternalDrop? {
        SidebarExternalDrop.resolve(droppedOn: (item as? OutlineNode)?.kind)
    }

    private func decideDrop(info: NSDraggingInfo, item: Any?, index: Int) -> DropPlan? {
        let model = projectIndex
        let at = index == NSOutlineViewDropOnItemIndex ? DropRouting.append : index
        let decision = DropRouting.resolve(
            dragged: draggedItems(from: info), onto: dropParent(for: item), at: at,
            isKnown: { dragged in
                guard let model else { return false }
                switch dragged {
                case .project(let id): return model.projects.contains { $0.id == id }
                case .folder(let id):  return model.folders.contains { $0.id == id }
                }
            }
        )
        if case .move(let plan) = decision { return plan }
        return nil
    }

    /// The model scope a proposed drop target represents. A **project** row resolves to
    /// its container, not to root: AppKit proposes the leaf under the cursor, and the
    /// meaningful destination is the scope that leaf sits in — otherwise a drop aimed
    /// between two projects inside a folder would silently route to root.
    private func dropParent(for item: Any?) -> DropParent {
        guard let node = item as? OutlineNode else { return .root }
        switch node.kind {
        case .folder(let id):
            return .folder(id)
        case .project:
            if let parent = node.parent, case .folder(let id) = parent.kind { return .folder(id) }
            return .root
        case .group, .lens:
            return .root
        }
    }

    private func draggedItems(from info: NSDraggingInfo) -> [SidebarDragItem] {
        (info.draggingPasteboard.pasteboardItems ?? []).compactMap { item in
            item.string(forType: Self.sidebarDragType).flatMap(SidebarDragItem.init(pasteboardString:))
        }
    }

    func outlineView(_ outlineView: NSOutlineView, viewFor tableColumn: NSTableColumn?, item: Any) -> NSView? {
        guard let node = item as? OutlineNode else { return nil }
        switch node.kind {
        case .group(let key):
            // Lens group sits at the top with no label ("lens" is code-internal);
            // other groups show their mixed-case title via i18n (chrome convention).
            let title: String
            switch key {
            case OutlineTree.lensesGroupKey:   title = ""
            case OutlineTree.projectsGroupKey: title = i18n?.t("desktop.chrome.projects") ?? key
            default:         title = key
            }
            return groupCell(text: title)
        case .lens(let tab):
            let lens = lensItems.first { $0.tab == tab }
            return iconCell(symbol: lens?.systemImage ?? "circle", text: lensLabel(tab),
                            dimmed: !lensesEnabled)
        case .folder(let id):
            let name = projectIndex?.folders.first { $0.id == id }?.name ?? "Folder"
            return iconCell(symbol: "folder", text: name)
        case .project(let id):
            guard let project = projectIndex?.projects.first(where: { $0.id == id }) else {
                return iconCell(symbol: "circle", text: "Project")
            }
            let symbol = project.icon ?? IconPickerPopover.defaultIcon
            let count = projectIndex?.unanalysed[id]?.sessionCount.map { String($0) }
            let variant = subtitleVariant(for: project)
            let subtitle = i18n.flatMap {
                SidebarSubtitleText.text(for: variant, availability: project.availability,
                                         progress: liveData?.progress[id], i18n: $0)
            }
            // Hover carries what the single-line subtitle had to drop. Computed
            // for BOTH cell shapes — the Schema E clean row returns early below,
            // and it is a legitimate tooltip case (session count with no delta).
            let tip = i18n.flatMap {
                SidebarSubtitleText.tooltip(for: variant, data: projectIndex?.unanalysed[id],
                                            progress: liveData?.progress[id], i18n: $0)
            }
            // No subtitle (Schema E's clean row — the DEFAULT since 29 Jul —
            // or a defensive nil) → single-line collapse (ProjectCellSpec).
            // The agent badge must survive that collapse: exposure is
            // permanent state on an otherwise-idle row, so a clean shared
            // project is EXACTLY the case that must show it (§5a-bis). The
            // ring/cloud slots can't reach here — both always carry
            // subtitle text — so only `.agent` crosses over.
            guard let subtitle else {
                var exposed: Bool?
                if case .agent(let now) = cellRightSlot(for: project) { exposed = now }
                return hideIconIfRevealing(
                    withTooltip(tip,
                                iconCell(symbol: symbol, text: project.name, trailing: count,
                                         agentExposedNow: exposed,
                                         agentProjectID: id)), id: id)
            }
            let prefix = subtitlePrefixGlyph(for: variant, availability: project.availability)
            let glyphAction = variant.glyphAction
            return hideIconIfRevealing(
                withTooltip(tip,
                    projectTwoLineCell(symbol: symbol, name: project.name, count: count,
                                       subtitle: subtitle,
                                       // `.unreachable` dims too, not just
                                       // `.cantFind` — both mean "this project
                                       // can't be opened right now", and
                                       // `design-pipeline-diagnostic-popover.md:303`
                                       // specified a greyed row for it all along.
                                       available: project.availability.isReady
                                           && !variant.isUnreachable,
                                       prefixGlyph: prefix,
                                       subtitleAction: glyphAction,
                                       subtitleActionProjectID: glyphAction == .none ? nil : id,
                                       agentProjectID: id,
                                       rightSlot: cellRightSlot(for: project),
                                       shimmer: shimmerSubtitle(for: variant))),
                id: id)
        }
    }

    // MARK: - Cells

    /// Attach the composed hover tooltip to a built cell, or leave it unset.
    ///
    /// `nil` leaves `toolTip` alone rather than writing an empty string — an
    /// empty tooltip still shows a bubble on some AppKit paths, and a project
    /// with nothing to add should have no bubble at all. Applied to the cell
    /// view (not the row) so the tracking area matches the drawn content, and
    /// applied to BOTH cell shapes through this one function so the single-line
    /// and two-line rows cannot drift apart on whether they answer a hover.
    /// Generic over the cell type so the concrete `NSTableCellView` survives —
    /// a plain `NSView` return would erase it and `hideIconIfRevealing` (which
    /// takes the cell) stops compiling.
    private func withTooltip<V: NSView>(_ tip: String?, _ view: V) -> V {
        if let tip, !tip.isEmpty { view.toolTip = tip }
        return view
    }

    private func lensLabel(_ tab: Tab) -> String {
        if let i18n { return tab.fullLocalizedLabel(i18n) }
        return tab.label
    }

    // MARK: - Agent activity animation (the antenna radiates)

    /// Envelope for the antenna's radiating animation.
    ///
    /// The unit is the BURST, not the call. Measured traffic (bristlenose.log,
    /// 30 Jul) shows one question firing six tool calls inside a single second,
    /// and another spreading three over ten seconds — so a per-call animation
    /// would either stack six deep or chop one question into three. `hold` is
    /// therefore **retriggerable**: every call restarts it, and the sign-off
    /// fires once, when the agent has actually stopped asking.
    ///
    /// The two taps at the end are that sign-off. They are the informative
    /// moment — not "a call happened" (you already knew, the antenna was
    /// radiating) but "it has finished reading".
    enum AgentWave {
        static let hold: TimeInterval = 4.0      // retriggerable
        static let tail: TimeInterval = 0.5      // radiate through the decay
        static let gap: TimeInterval = 0.9       // silence before the sign-off
        static let tap: TimeInterval = 0.65
        static let tapGap: TimeInterval = 0.45
        /// One frame of the flipbook. `antenna.radiowaves.left.and.right` has
        /// exactly THREE variable-value renderings (measured 20 Aug: edges at
        /// 0.0 / 0.05 / 0.55 — mast, mast+inner, mast+both), so a "sweep" is
        /// 3 frames at this period, not a continuous ramp.
        static let framePeriod: TimeInterval = 0.3

        static var duration: TimeInterval { hold + tail + gap + tap + tapGap + tap }

        /// Is the antenna radiating `e` seconds after the last tool call?
        static func radiating(at e: TimeInterval) -> Bool {
            if e < 0 { return false }
            if e < hold + tail { return true }              // hold + decay tail
            var c = hold + tail + gap
            if e < c { return false }
            if e < c + tap { return true }                  // sign-off tap 1
            c += tap + tapGap
            if e < c { return false }
            return e < c + tap                             // sign-off tap 2
        }

        /// Seconds since the current radiating segment began, so each tap
        /// restarts the flipbook at the mast rather than resuming mid-sweep.
        static func segmentElapsed(at e: TimeInterval) -> TimeInterval {
            if e < hold + tail { return e }
            let firstTap = hold + tail + gap
            if e < firstTap + tap { return e - firstTap }
            return e - (firstTap + tap + tapGap)
        }
    }

    /// The three measured frames, built once. Index 2 (both arc pairs) is the
    /// REST state, so an idle animated row is pixel-identical to a row that
    /// never animates — the animation departs from rest and returns to it,
    /// and introduces no new resting appearance.
    private static let agentWaveFrames: [NSImage?] = {
        let cfg = ProjectCellSpec.subtitleGlyphConfig
        return [0.0, 0.3, 1.0].map {
            NSImage(systemSymbolName: "antenna.radiowaves.left.and.right",
                    variableValue: $0, accessibilityDescription: nil)?
                .withSymbolConfiguration(cfg)
        }
    }()

    private var agentCallAt: [UUID: Date] = [:]
    private var agentWaveTimer: Timer?
    /// The live badge for the radiating project, so the flipbook can advance
    /// without a `reloadData` — which at ~3fps would be both wasteful and
    /// destructive (it tears down an open inline rename).
    /// The live badge per animating project. A map, because scope is plural:
    /// a cross-study question lights several antennas in sequence, and the
    /// sidebar is replicated in every window, so the row that radiates has to
    /// be chosen by project rather than by "the one exposed project".
    private var agentAntennaViews: [UUID: NSImageView] = [:]

    /// Adopt fresh per-project call times and run the envelope to completion.
    func noteAgentCalls(_ calls: [UUID: Date]) {
        guard calls != agentCallAt else { return }
        agentCallAt = calls
        guard !calls.isEmpty else { return stopAgentWave() }
        // Reduce Motion: the exposure tiers still carry everything that
        // MATTERS (can be reached / is reachable now). Activity is the
        // additive nicety, so dropping it costs no information.
        guard !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion else { return }
        guard agentWaveTimer == nil else { return }   // retrigger: envelope reads the new times
        let timer = Timer(timeInterval: AgentWave.framePeriod, repeats: true) { [weak self] timer in
            MainActor.assumeIsolated {
                guard let self else { return timer.invalidate() }
                self.tickAgentWave()
            }
        }
        RunLoop.main.add(timer, forMode: .common)   // .common: keep radiating during a scroll
        agentWaveTimer = timer
        tickAgentWave()
    }

    private func tickAgentWave() {
        let now = Date()
        var anyLive = false
        for (id, view) in agentAntennaViews {
            guard let start = agentCallAt[id] else {
                view.image = Self.agentWaveFrames[2]
                continue
            }
            let e = now.timeIntervalSince(start)
            guard e < AgentWave.duration else {
                view.image = Self.agentWaveFrames[2]
                continue
            }
            anyLive = true
            let frame = AgentWave.radiating(at: e)
                ? min(2, Int(AgentWave.segmentElapsed(at: e) / AgentWave.framePeriod) % 3)
                : 2
            view.image = Self.agentWaveFrames[frame]
        }
        // Also true when no row is on screen: the timer must not outlive the
        // envelope just because the researcher scrolled the row out of view.
        if !anyLive, !agentCallAt.values.contains(where: { now.timeIntervalSince($0) < AgentWave.duration }) {
            stopAgentWave()
        }
    }

    private func stopAgentWave() {
        agentWaveTimer?.invalidate()
        agentWaveTimer = nil
        for view in agentAntennaViews.values { view.image = Self.agentWaveFrames[2] }
    }

    /// The frame a freshly-built badge should show, so a cell rebuilt mid-
    /// animation (the sidebar reloads on every progress tick) lands on the
    /// current frame instead of snapping back to rest.
    /// The frame a freshly-built badge should show, so a cell rebuilt mid-
    /// animation (the sidebar reloads on every progress tick) lands on the
    /// current frame instead of snapping back to rest.
    private func currentAgentWaveFrame(for id: UUID?) -> NSImage? {
        guard agentWaveTimer != nil, let id, let start = agentCallAt[id] else {
            return Self.agentWaveFrames[2]
        }
        let e = Date().timeIntervalSince(start)
        guard AgentWave.radiating(at: e) else { return Self.agentWaveFrames[2] }
        let i = min(2, Int(AgentWave.segmentElapsed(at: e) / AgentWave.framePeriod) % 3)
        return Self.agentWaveFrames[i]
    }

    /// The agent-access antenna, built once for both cell layouts so the
    /// two can't drift. Solid (secondary, the quiet ambient family the
    /// iCloud glyph belongs to) = exposed now; pale (tertiary) = shared but
    /// the project isn't open. Never a control — status is attention, not
    /// affordance (§5a-bis, the Mail model).
    private func agentBadgeView(exposedNow: Bool, projectID: UUID?) -> NSImageView {
        let tooltip = i18n?.t("desktop.mcpAgents.badgeTooltip")
        let antenna = NSImageView()
        // Only the solid tier animates, and it takes the CURRENT frame rather
        // than the rest glyph: the sidebar reloads on every progress tick, so
        // a cell rebuilt mid-sweep would otherwise snap back to rest and read
        // as a stutter. Pale rows (exposed but not open) can't be reached by
        // an agent, so there is nothing for them to radiate about.
        antenna.image = exposedNow
            ? currentAgentWaveFrame(for: projectID)
            : NSImage(systemSymbolName: "antenna.radiowaves.left.and.right",
                      accessibilityDescription: tooltip)
        antenna.symbolConfiguration = ProjectCellSpec.subtitleGlyphConfig
        antenna.contentTintColor = exposedNow ? .secondaryLabelColor : .tertiaryLabelColor
        antenna.toolTip = tooltip
        antenna.translatesAutoresizingMaskIntoConstraints = false
        antenna.setContentHuggingPriority(.required, for: .horizontal)
        antenna.setContentCompressionResistancePriority(.required, for: .horizontal)
        // Last solid badge built wins the animation. There is at most one —
        // the handshake names a single project — and a rebuild replaces the
        // weak reference for free, so view churn needs no bookkeeping.
        // Registered on the way in, pruned on the way out — the map holds
        // STRONG references to cell subviews, and cells are rebuilt on every
        // progress tick, so an add-only map would retain a detached view per
        // project ever exposed in this window.
        if let projectID {
            if exposedNow { agentAntennaViews[projectID] = antenna }
            else { agentAntennaViews[projectID] = nil }
        }
        return antenna
    }

    /// - Parameter agentExposedNow: nil = no agent access (no badge, the
    ///   absence-is-information state); true/false = the solid/pale tiers.
    ///   Only project rows pass it — lens and folder rows can't be shared.
    private func iconCell(symbol: String, text: String, dimmed: Bool = false,
                          trailing: String? = nil,
                          agentExposedNow: Bool? = nil,
                          agentProjectID: UUID? = nil) -> NSTableCellView {
        let cell = NSTableCellView()
        let imageView = NSImageView()
        imageView.image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil)
        imageView.symbolConfiguration = ProjectCellSpec.iconSymbolConfig
        // Normally no explicit tint: SF Symbols are template images, so the system
        // tints icon + label via `backgroundStyle` (selected → accent, else label) —
        // identical for a selected project and the genuinely-selected active lens.
        // `dimmed` (a disabled lens — no project / no report) paints both secondary
        // so the row reads inactive, restoring the old LensRail's disabled look.
        // Edo forces Accent (Prussian) on non-dimmed icons for palette consistency;
        // Default palette leaves it nil so system backgroundStyle tinting still fires.
        imageView.contentTintColor = dimmed ? .secondaryLabelColor : SidebarPalette.accentOverride
        imageView.translatesAutoresizingMaskIntoConstraints = false
        let textField = NSTextField(labelWithString: text)
        if dimmed {
            textField.textColor = .secondaryLabelColor
        } else if let ink = SidebarPalette.inkOverride {
            textField.textColor = ink
        }
        textField.lineBreakMode = .byTruncatingTail
        textField.translatesAutoresizingMaskIntoConstraints = false
        cell.imageView = imageView
        cell.textField = textField
        cell.addSubview(imageView)
        cell.addSubview(textField)
        var constraints: [NSLayoutConstraint] = [
            imageView.leadingAnchor.constraint(equalTo: cell.leadingAnchor),
            imageView.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            imageView.widthAnchor.constraint(equalToConstant: ProjectCellSpec.iconWidth),
            textField.leadingAnchor.constraint(equalTo: imageView.trailingAnchor, constant: 6),
            textField.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
        ]
        // Trailing edge, outermost: the agent badge when present. Status
        // takes the row's right edge in both layouts — on a two-line row
        // the ring/antenna sit at the trailing edge of the subtitle line,
        // so keeping the glyph outermost here means the collapse doesn't
        // move it. The count then sits inboard of it.
        var trailingAnchorView: NSView = cell
        var trailingInset: CGFloat = -4
        if let agentExposedNow {
            let antenna = agentBadgeView(exposedNow: agentExposedNow, projectID: agentProjectID)
            cell.addSubview(antenna)
            constraints += [
                antenna.trailingAnchor.constraint(equalTo: cell.trailingAnchor,
                                                  constant: -ProjectCellSpec.trailingInset),
                antenna.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            ]
            trailingAnchorView = antenna
            trailingInset = -ProjectCellSpec.subtitleInternal
        }

        if let trailing {
            // Trailing session count — Finder's right column (ProjectRow's title
            // right-slot: footnote / tertiary, system-sized). The name truncates
            // before the count, so the count stays visible on a narrow sidebar.
            let countField = NSTextField(labelWithString: trailing)
            countField.font = .preferredFont(forTextStyle: .footnote)
            countField.textColor = .tertiaryLabelColor
            countField.translatesAutoresizingMaskIntoConstraints = false
            countField.setContentHuggingPriority(.required, for: .horizontal)
            countField.setContentCompressionResistancePriority(.required, for: .horizontal)
            cell.addSubview(countField)
            constraints += [
                textField.trailingAnchor.constraint(lessThanOrEqualTo: countField.leadingAnchor, constant: -6),
                countField.trailingAnchor.constraint(
                    equalTo: trailingAnchorView === cell
                        ? cell.trailingAnchor : trailingAnchorView.leadingAnchor,
                    constant: trailingInset),
                countField.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            ]
        } else {
            constraints.append(textField.trailingAnchor.constraint(
                equalTo: trailingAnchorView === cell
                    ? cell.trailingAnchor : trailingAnchorView.leadingAnchor,
                constant: trailingInset))
        }
        NSLayoutConstraint.activate(constraints)
        return cell
    }

    // MARK: - Project cell (rich, two-line) — Phase 1+

    /// Variable row height: a project shows two lines unless its state collapses
    /// to `.placeholder` (the deliberate divergence). Non-project rows + the
    /// collapsed case use the single-line height. Uses the same nil-subtitle
    /// criterion as `viewFor` so height + content can't disagree.
    func outlineView(_ outlineView: NSOutlineView, heightOfRowByItem item: Any) -> CGFloat {
        guard let node = item as? OutlineNode, case .project(let id) = node.kind,
              let project = projectIndex?.projects.first(where: { $0.id == id }), let i18n
        else {
            return ProjectCellSpec.rowHeight(twoLine: false)
        }
        let variant = subtitleVariant(for: project)
        let twoLine = SidebarSubtitleText.text(for: variant, availability: project.availability,
                                               progress: liveData?.progress[id], i18n: i18n) != nil
        return ProjectCellSpec.rowHeight(twoLine: twoLine)
    }

    /// Whether the status line should shimmer (design-motion §4.7.1): only a live
    /// run (`.running`), and only when the "Show animation while analysing" toggle
    /// is on AND Reduce Motion is off — the native twin of the web CSS two-gate.
    /// Off → the plain static subtitle label.
    private func shimmerSubtitle(for variant: SubtitleVariant) -> Bool {
        guard variant == .running else { return false }
        let on = UserDefaults.standard.object(forKey: "showAnalysisAnimation") as? Bool ?? true
        return on && !NSWorkspace.shared.accessibilityDisplayShouldReduceMotion
    }

    /// The arbitrated subtitle state — mirrors `ProjectRow.subtitleVariant`
    /// (`ProjectRow.swift:491-501`), pulling the same inputs from the controller's
    /// observed sources.
    private func subtitleVariant(for project: Project) -> SubtitleVariant {
        let id = project.id
        return ProjectSubtitle.resolve(
            availability: project.availability,
            pipelineState: pipelineRunner?.state[id],
            isStopping: liveData?.progress[id]?.isStopping ?? false,
            addingCount: pipelineRunner?.addingInterviews[id],
            copy: copyDisplay(for: project),
            importBatch: importBatchDisplay(for: project),
            lastRunAt: project.lastPipelineRunAt,
            missingCount: projectIndex?.unanalysed[id]?.missingFiles.count ?? 0,
            unanalysedCount: projectIndex?.unanalysed[id]?.newFiles.count ?? 0
        )
    }

    /// Per-project copy display — mirrors `ContentView.swift:1784-1790`.
    private func copyDisplay(for project: Project) -> CopyDisplay? {
        guard let f = copyMachinery?.inFlight, f.projectID == project.id else { return nil }
        switch f.phase {
        case .copying: return .copying(fraction: f.progress)
        case .cancelling: return .cancelling
        }
    }

    /// Per-project cloud-import batch, or nil when none is landing here.
    ///
    /// The whole point of the sidebar ring: once the import window is closed,
    /// this is the only thing that can answer "is it still going?". Matched on
    /// the destination project so a batch landing in *another* study does not
    /// light up this row.
    private func importBatchDisplay(for project: Project) -> (done: Int, total: Int)? {
        guard let batch = cloudImport?.store?.batch, batch.projectID == project.id
        else { return nil }
        return (done: batch.done, total: batch.total)
    }

    /// Subtitle PREFIX glyph (symbol + tint) for a variant, or nil. Mirrors the glyph
    /// choices in `ProjectRow.subtitleContent` (`:229-254`): cantFind → reason-aware
    /// glyph in orange; failed/diagnostic → the `MessageKind.error` glyph; partial →
    /// `MessageKind.warning`. Clickability is decided separately, by
    /// `SubtitleVariant.glyphAction`.
    ///
    /// **Exhaustive, no `default` — and it was the `default` that caused the bug
    /// this function was audited for (26 Aug 2026).** Three sibling switches
    /// classify the same enum and all three carry a written comment forbidding a
    /// `default` arm — `SubtitleVariant.glyphAction` ("so a new variant forces an
    /// explicit decision here rather than silently rendering an inert glyph"),
    /// `ProjectRowActivityIndicator.Kind.from`, and `pipelineIsFree`. This one,
    /// the only one that decides whether the user sees a glyph at all, had
    /// `default: return nil`. So `.unreachable` — five English sentences on the
    /// row — drew no glyph, had nothing to click, and no compiler error ever
    /// asked. `.deltaOnly(.missing)` fell through the same arm, despite the
    /// 18 Jun rulings table classifying missing source files as `warning`
    /// ("beyond neutral — files gone").
    ///
    /// Don't reintroduce the `default`. The point of the enumeration is that
    /// adding a case here is a *decision*, not an omission.
    private func subtitlePrefixGlyph(for variant: SubtitleVariant,
                                     availability: ProjectAvailability) -> (symbol: String, color: NSColor)? {
        guard let kind = variant.glyphKind else { return nil }
        // `.cantFind` is the one state whose picture isn't its kind's: an
        // unmounted volume, an unreachable host and a moved folder are three
        // different situations and get three different symbols. The *colour*
        // still comes from the kind, so it can't drift from the rest.
        if case .cantFind = variant {
            return (availability.sfSymbolName ?? "questionmark.folder", NSColor(kind.tint))
        }
        return (kind.symbolName, NSColor(kind.tint))
    }

    /// A subtitle element was clicked — route by its declared destination.
    /// `SubtitleVariant.glyphAction` decided this; the cell only carries it.
    @objc private func subtitleActionClicked(_ sender: SubtitleActionButton) {
        guard let id = sender.projectID else { return }
        switch sender.subtitleAction {
        case .diagnostics:
            showDiagnosticsPopover(sender)
        case .files:
            presentFilesPopover(projectID: id,
                                anchorRect: sender.convert(sender.bounds, to: outlineView))
        case .none:
            break
        }
    }

    /// The subtitle failure glyph → diagnostic popover, anchored to the glyph's frame.
    private func showDiagnosticsPopover(_ sender: SubtitleActionButton) {
        guard let id = sender.projectID else { return }
        presentDiagnosticPopover(projectID: id, anchorRect: sender.convert(sender.bounds, to: outlineView))
    }

    /// Build + show the read-only diagnostic popover (status headline + per-stage
    /// breakdown + Show Log / Copy), mirroring `ProjectRow`'s failure-glyph affordance.
    /// `rect` is in outline-view coords (the glyph frame for a click, the row frame
    /// for the context-menu item).
    private func presentDiagnosticPopover(projectID id: UUID, anchorRect rect: NSRect) {
        guard let project = projectIndex?.projects.first(where: { $0.id == id }),
              let state = pipelineRunner?.state[id],
              let liveData, let i18n else { return }
        // No frame, no padding: the popover owns its own size. The hosting
        // controller reports it through `fittingSize`, which is what NSPopover
        // sizes from — `.preferredContentSize` set explicitly so the controller
        // publishes that size rather than inheriting an ambient one.
        // `docs/design-pipeline-popover-sizing.md`.
        let content = ProjectDiagnosticPopover(project: project, state: state, liveData: liveData)
            .environmentObject(i18n)
        let host = NSHostingController(rootView: content)
        host.sizingOptions = .preferredContentSize
        showRowPopover(host, at: rect)
    }

    /// Build + show the data-drift popover — which files are new, which have
    /// vanished, and the one act on them. Sibling of `presentDiagnosticPopover`;
    /// both go through `showRowPopover`, so anchoring and dismissal can't drift.
    ///
    /// **Analyse is resolved here, not passed in from `ContentView`.** The gate
    /// is `analyseIsOffered` — the same predicate the context menu asks — so the
    /// popover's button and the menu item cannot disagree about whether a run
    /// can start. `nil` hides the button rather than dimming it.
    private func presentFilesPopover(projectID id: UUID, anchorRect rect: NSRect) {
        guard let project = projectIndex?.projects.first(where: { $0.id == id }),
              let data = projectIndex?.unanalysed[id],
              let i18n else { return }
        // The variant was resolved at render time and this reads the watcher
        // again at click time; a rescan in between could have cleared the drift.
        // An empty popover is worse than none.
        guard !data.newFiles.isEmpty || !data.missingFiles.isEmpty else { return }
        let offered = Self.analyseIsOffered(
            isFolderShaped: project.inputFiles == nil,
            hasPath: !project.path.isEmpty,
            state: pipelineRunner?.state[id],
            data: data)
        let analyse: (() -> Void)? = offered
            ? { [weak self] in
                self?.pipelineRunner?.start(project: project)
                self?.activePopover?.close()
              }
            : nil
        let content = ProjectFilesPopover(newFiles: data.newFiles,
                                          missingFiles: data.missingFiles,
                                          onAnalyse: analyse)
            .environmentObject(i18n)
        let host = NSHostingController(rootView: content)
        host.sizingOptions = .preferredContentSize
        showRowPopover(host, at: rect)
    }

    /// Build + show the icon-picker popover (context-menu "Choose Icon…"); a pick
    /// writes through `projectIndex.setIcon` and dismisses.
    private func presentIconPopover(projectID id: UUID, anchorRect rect: NSRect) {
        guard let project = projectIndex?.projects.first(where: { $0.id == id }),
              let projectIndex else { return }
        let content = IconPickerPopover(selectedIcon: project.icon) { [weak self] icon in
            projectIndex.setIcon(id: id, icon: icon)
            self?.activePopover?.close()
        }
        showRowPopover(NSHostingController(rootView: content), at: rect)
    }

    /// Show a popover anchored to the OUTLINE VIEW at `rect` (survives the per-tick
    /// `reloadData`), replacing any currently-open one.
    private func showRowPopover(_ content: NSViewController, at rect: NSRect) {
        activePopover?.close()
        let popover = NSPopover()
        popover.behavior = .transient
        popover.delegate = self
        popover.contentViewController = content
        activePopover = popover
        popover.show(relativeTo: rect, of: outlineView, preferredEdge: .maxY)
    }

    /// Drop the strong `activePopover` ref on transient dismissal, so the hosting
    /// controller (the diagnostic one observes `liveData` at ~1 Hz) is torn down at
    /// close rather than lingering until the next open. (Review F30.)
    func popoverDidClose(_ notification: Notification) {
        activePopover = nil
    }

    // MARK: - Context menu (right-click) — ports ProjectRow / FolderRow `.contextMenu`

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        let row = outlineView.clickedRow
        guard row >= 0, let node = outlineView.item(atRow: row) as? OutlineNode else {
            menuClickedNodeID = nil
            return
        }
        switch node.kind {
        case .project(let id): menuClickedNodeID = id; buildProjectMenu(menu, projectID: id)
        case .folder(let id):  menuClickedNodeID = id; buildFolderMenu(menu, folderID: id)
        case .lens(let tab):
            menuClickedNodeID = nil
            menuClickedLens = tab
            // Only when the lenses are actually live. Lens rows are always
            // present and merely *dimmed* when no report is showing — so
            // without this you could right-click a visibly-dimmed Quotes row on
            // the Welcome screen and get a window on a study you never named.
            // A context menu shows what is relevant; a dimmed row has nothing.
            if lensesEnabled { buildLensMenu(menu) }
        case .group:           menuClickedNodeID = nil   // no menu on group headers
        }
    }

    private func menuItem(_ key: String, _ action: Selector, enabled: Bool = true) -> NSMenuItem {
        let mi = NSMenuItem(title: i18n?.t(key) ?? key, action: action, keyEquivalent: "")
        mi.target = self
        mi.isEnabled = enabled
        return mi
    }

    /// One item, deliberately. A lens row's only useful context action is to
    /// take that lens somewhere else; everything else about a lens belongs to
    /// the study.
    private func buildLensMenu(_ menu: NSMenu) {
        menu.addItem(menuItem("desktop.menu.file.openInNewWindow",
                              #selector(menuOpenLensInNewWindow(_:))))
    }

    @objc private func menuOpenFolderInNewWindows(_ sender: NSMenuItem) {
        guard let id = menuClickedNodeID, let index = projectIndex else { return }
        _ = index
        // Sidebar order, so the windows arrive in the order the researcher sees
        // them rather than whatever the model iterates in.
        for project in index.projects
        where project.folderId == id
        {
            onOpenInNewWindow(project.id)
        }
    }

    @objc private func menuOpenLensInNewWindow(_ sender: NSMenuItem) {
        if let tab = menuClickedLens { onOpenLensInNewWindow(tab) }
    }

    private func buildProjectMenu(_ menu: NSMenu, projectID id: UUID) {
        let state = pipelineRunner?.state[id]
        let availability = projectIndex?.projects.first { $0.id == id }?.availability

        // Run / copy lifecycle first (ProjectRow order). Hidden, not dimmed, when N/A.
        if isRunningOrQueued(state) {
            menu.addItem(menuItem("desktop.menu.project.stopAnalysis", #selector(menuStopAnalysis(_:))))
            menu.addItem(.separator())
        }
        if let f = copyMachinery?.inFlight, f.projectID == id, f.phase == .copying {
            menu.addItem(menuItem("desktop.menu.project.cancelCopy", #selector(menuCancelCopy(_:))))
            menu.addItem(.separator())
        }
        if isFailureState(state) {
            menu.addItem(menuItem("desktop.menu.project.showDiagnostics", #selector(menuShowDiagnostics(_:))))
            menu.addItem(.separator())
        }
        if canAnalyse(id, state: state) {
            menu.addItem(menuItem("desktop.menu.project.analyse", #selector(menuAnalyse(_:))))
            menu.addItem(.separator())
        }
        // Present or absent — never dimmed. The menu-bar twin in
        // `ProjectMenuContent` dims instead, which is the rule this file's
        // lifecycle block already states.
        if canReAnalyse(id, state: state) {
            menu.addItem(menuItem("desktop.menu.project.reAnalyse", #selector(menuReAnalyse(_:))))
            menu.addItem(.separator())
        }
        if case .cantFind = availability {
            menu.addItem(menuItem("desktop.chrome.locate", #selector(menuLocate(_:))))
            menu.addItem(.separator())
        }
        // Hidden, not dimmed, when N/A — the context-menu rule the file's
        // lifecycle block above already follows (a menu-*bar* item would
        // dim instead). Fixes the pre-existing `enabled:` gating here
        // (design-mcp-extension §3.6a's "two corrections to shipped code").
        // **Open first, and in its own group.** Clicking the row already opens
        // the study in *this* window, so this is the variant of the row's own
        // purpose — the primary action, and primary goes first. Finder does the
        // same, leading with its open verbs and pushing reveal-elsewhere down.
        //
        // Separated from Show in Finder deliberately: sharing a group claimed
        // the two were the same kind of thing, and they are not. This one
        // navigates inside Bristlenose; that one hands off to another app.
        //
        // Short form, as Finder uses for a folder — you can only right-click a
        // project row or a lens row, never both, so context does the
        // disambiguating that a longer label would.
        menu.addItem(menuItem("desktop.menu.file.openInNewWindow",
                              #selector(menuOpenInNewWindow(_:))))
        menu.addItem(.separator())
        if canShowInFinder(id) {
            menu.addItem(menuItem("desktop.menu.project.showInFinder", #selector(menuShowInFinder(_:))))
        }
        menu.addItem(menuItem("desktop.menu.project.rename", #selector(menuRename(_:))))
        menu.addItem(menuItem("desktop.menu.project.chooseIcon", #selector(menuChooseIcon(_:))))

        // "Move to" → submenu (No Folder + each folder), mirroring ProjectRow.
        if let folders = projectIndex?.folders, !folders.isEmpty {
            let project = projectIndex?.projects.first { $0.id == id }
            let moveItem = NSMenuItem(
                title: i18n?.t("desktop.menu.project.moveTo") ?? "Move to", action: nil, keyEquivalent: "")
            let sub = NSMenu()
            sub.autoenablesItems = false
            let noFolder = menuItem("desktop.menu.project.noFolder", #selector(menuMoveToRoot(_:)),
                                    enabled: project?.folderId != nil)
            sub.addItem(noFolder)
            sub.addItem(.separator())
            for folder in folders {
                let fi = NSMenuItem(title: folder.name, action: #selector(menuMoveToFolder(_:)), keyEquivalent: "")
                fi.target = self
                fi.representedObject = folder.id
                fi.isEnabled = project?.folderId != folder.id
                sub.addItem(fi)
            }
            moveItem.submenu = sub
            menu.addItem(moveItem)
        }

        // Turn On/Off Agent Access — its own group, below the housekeeping
        // block, above Remove from Sidebar (§3.6a: adjacent to Show in
        // Finder it would assert an equivalence between revealing files
        // locally and letting a vendor read them). Verb swap, not a
        // checkmark — an unchecked checkmark item is indistinguishable from
        // an ordinary action. Hidden (never dimmed) when we genuinely know
        // it is impossible: not analysed/locatable, or a build without MCP.
        // "No agent installed" is NOT knowable and NOT a reason to hide —
        // this is a permission, not a connection.
        if mcpMounted, canShareWithAgents(id) {
            menu.addItem(.separator())
            let accessOn = projectIndex?.projects.first { $0.id == id }?.agentAccess ?? false
            menu.addItem(menuItem(
                accessOn ? "desktop.menu.project.turnOffAgentAccess"
                         : "desktop.menu.project.turnOnAgentAccess",
                #selector(menuToggleAgentAccess(_:))))
        }

        menu.addItem(.separator())
        // Hidden while the project is running — you cannot remove it, and the
        // menu is the place to say so. It used to be offered, refused, and
        // explained by a toast. Context menus hide; the Project-menu twin dims.
        if !Self.isRunningOrQueued(pipelineRunner?.state[id]) {
            menu.addItem(menuItem("desktop.menu.project.removeFromSidebar", #selector(menuRemoveProject(_:))))
        }
    }

    private func buildFolderMenu(_ menu: NSMenu, folderID id: UUID) {
        // Plural, Safari's shape for a bookmark folder — and **no confirmation**,
        // deliberately. Researchers select-all-and-open in Finder, InDesign and
        // Photoshop without being asked, and a dialog counting servers at them
        // would offload our resource management onto them. Lazy sidecar start is
        // what makes it honest: twelve windows, one or two serves, the rest
        // starting when they are looked at.
        //
        // Only when the folder actually holds more than one study; a folder of
        // one is served by the project row's own item.
        if (projectIndex?.projects.filter { $0.folderId == id }.count ?? 0) > 1 {
            menu.addItem(menuItem("desktop.menu.file.openAllInNewWindows",
                                  #selector(menuOpenFolderInNewWindows(_:))))
            menu.addItem(.separator())
        }
        menu.addItem(menuItem("desktop.menu.folder.rename", #selector(menuRename(_:))))
        menu.addItem(menuItem("desktop.menu.folder.archive", #selector(menuNoop(_:)), enabled: false))  // Phase 5
        menu.addItem(.separator())
        menu.addItem(menuItem("desktop.menu.folder.delete", #selector(menuRemoveFolder(_:))))
    }

    private func isRunningOrQueued(_ state: PipelineState?) -> Bool {
        switch state { case .running, .queued: return true; default: return false }
    }

    /// A folder-shaped project with files on disk but no finished report, and
    /// not currently running — the stopped / failed / never-analysed cases. The
    /// files belong to the project, so offer "Analyse" rather than dead-end on
    /// the "No interviews to analyse yet" empty state. Excludes analysed
    /// projects (`.ready` / `.completedPartial` — Re-analyse is a separate,
    /// destructive action) and bare "New Project" placeholders (empty path).
    /// Whether **Analyse** is worth offering — i.e. whether running it would
    /// visibly do anything.
    ///
    /// Three questions, in order: is this the right kind of project, is the
    /// pipeline free, and *is there work to do*. The third was missing, so the
    /// item appeared highlighted on an empty project beside a pane reading
    /// "Add interview recordings or transcripts to get started", and again on a
    /// fully-analysed project where it is a measured 0.1s of cache hits and a
    /// re-render — teaching the researcher the button is broken rather than
    /// that they picked the wrong one.
    ///
    /// The matrix this implements is `docs/design-analysis-lifecycle.md` §4.1.
    private func canReAnalyse(_ id: UUID, state: PipelineState?) -> Bool {
        guard let p = projectIndex?.projects.first(where: { $0.id == id })
        else { return false }
        return Self.reAnalyseIsOffered(
            isFolderShaped: p.inputFiles == nil,
            hasPath: !p.path.isEmpty,
            state: state,
            data: projectIndex?.unanalysed[id]
        )
    }

    private func canAnalyse(_ id: UUID, state: PipelineState?) -> Bool {
        guard let p = projectIndex?.projects.first(where: { $0.id == id })
        else { return false }
        return Self.analyseIsOffered(
            isFolderShaped: p.inputFiles == nil,
            hasPath: !p.path.isEmpty,
            state: state,
            data: projectIndex?.unanalysed[id]
        )
    }

    /// The whole predicate, pure — so every surface that offers **Analyse**
    /// asks one question rather than re-deriving three.
    ///
    /// The unanalysed sheet is the second caller: it lists files that are not
    /// in the analysis, so its primary action is the same verb the context menu
    /// offers, and the two must agree about when that verb is available. A
    /// second copy of "folder-shaped, has a path, pipeline free" is how they
    /// would come to disagree — the same failure the pane and the menu had
    /// about whether there was anything to analyse at all.
    /// Whether **Re-analyse…** is worth offering: there is an analysis to
    /// throw away, and the pipeline is free to rebuild it.
    ///
    /// The mirror image of `analyseIsOffered`. Analyse asks "is there work to
    /// do"; Re-analyse asks "is there a *result* to replace", which is why
    /// "analysed, nothing new" — the one state where Analyse is a no-op — is
    /// exactly the state this belongs in.
    ///
    /// Deliberately does NOT require `newFiles` to be empty: re-analysing a
    /// drifted project is legitimate (it picks the new files up as well), it is
    /// just the expensive way to do it. Offering both and letting the labels
    /// distinguish them is honest; hiding this one would leave a researcher who
    /// wants a clean rebuild with no route to it.
    /// Whether a project is mid-run. Shared by the menus so "you cannot remove
    /// this right now" is one question, asked once.
    nonisolated static func isRunningOrQueued(_ state: PipelineState?) -> Bool {
        switch state {
        case .running, .queued: return true
        default: return false
        }
    }

    /// Whether the pipeline is free to start a run for this project — the shared
    /// gate under both **Analyse** and **Re-analyse…**, so the two cannot drift
    /// apart about when a run is possible.
    ///
    /// **Exhaustive, no `default`** — same convention as
    /// `SubtitleVariant.isDiagnostic`. The allowlist this replaced named four
    /// terminal states and silently refused every other one, which is how
    /// `.ready` — a finished analysis, the single state `reAnalyseIsOffered`
    /// exists to serve — came to offer neither verb. `a1de4e51`'s own message
    /// names that state as the target ("the one state where Analyse is a
    /// measured no-op … is exactly the state this belongs in") while its switch
    /// excluded it; `.completedPartial` and `.partial` were excluded the same
    /// way. A new state must now be classified here rather than inheriting a
    /// refusal by falling through a `default`.
    ///
    /// Refuses exactly the four states where a run cannot start: `.scanning`
    /// (the manifest read hasn't resolved, so we don't yet know what we'd be
    /// doing), `.running` / `.queued` (the single-slot FIFO is occupied), and
    /// `.unreachable` (the folder isn't there). Every *terminal* state — ready,
    /// partial, stopped, failed — can start one.
    nonisolated static func pipelineIsFree(_ state: PipelineState?) -> Bool {
        switch state ?? .idle {
        case .idle, .ready, .partial, .completedPartial,
             .stopped, .failed, .failedWithDiagnostic:
            return true
        case .scanning, .running, .queued, .unreachable:
            return false
        }
    }

    nonisolated static func reAnalyseIsOffered(
        isFolderShaped: Bool, hasPath: Bool,
        state: PipelineState?, data: UnanalysedState?
    ) -> Bool {
        guard isFolderShaped, hasPath else { return false }
        guard pipelineIsFree(state) else { return false }
        return (data?.sessionCount ?? 0) > 0
    }

    nonisolated static func analyseIsOffered(
        isFolderShaped: Bool, hasPath: Bool,
        state: PipelineState?, data: UnanalysedState?
    ) -> Bool {
        guard isFolderShaped, hasPath else { return false }
        guard pipelineIsFree(state) else { return false }
        return hasWorkToDo(data)
    }

    /// The "is there work to do" half of `canAnalyse`, pure so it can be tested
    /// without an outline view.
    ///
    /// `nil` means no watcher is running yet (project not ready, or the first
    /// scan hasn't landed) — **not** "nothing to do". Unknown resolves to
    /// *offer*: wrongly showing a control the researcher can retry costs a
    /// click, wrongly hiding one leaves them with no way forward at all.
    nonisolated static func hasWorkToDo(_ data: UnanalysedState?) -> Bool {
        guard let data else { return true }
        guard data.hasIngestableFiles else { return false }
        let alreadyAnalysed = (data.sessionCount ?? 0) > 0
        return !alreadyAnalysed || !data.newFiles.isEmpty
    }

    private func isFailureState(_ state: PipelineState?) -> Bool {
        switch state { case .failed, .failedWithDiagnostic, .completedPartial: return true; default: return false }
    }

    /// Puff the rows that are about to be removed.
    ///
    /// Must run **before** the model loses them — a rect is only computable
    /// while the row still exists — which is why this is driven by a
    /// *will*-remove notification rather than by noticing rows vanish.
    ///
    /// `NSAnimationEffect.poof` is the system idiom the drag-and-drop HIG names
    /// for exactly this: *"scale up and fade out to give the impression of the
    /// item evaporating."* The row used to just blink out of existence, which
    /// gives the eye nothing to follow and no sense that anything reversible
    /// happened.
    @objc private func handleWillRemoveProjects(_ note: Notification) {
        guard let ids = note.userInfo?["ids"] as? [UUID],
              let window = outlineView.window else { return }
        for id in ids {
            let rect = rowRect(forNodeID: id)
            guard rect != .zero else { continue }
            let inWindow = outlineView.convert(rect, to: nil)
            let onScreen = window.convertToScreen(inWindow)
            NSAnimationEffect.poof.show(
                centeredAt: NSPoint(x: onScreen.midX, y: onScreen.midY),
                size: .zero
            ) {}
        }
    }

    /// The row rect (outline-view coords) of the project/folder node with `id`, for
    /// anchoring a popover opened from the context menu. `.zero` if not displayed.
    private func rowRect(forNodeID id: UUID) -> NSRect {
        for r in 0..<outlineView.numberOfRows {
            guard let node = outlineView.item(atRow: r) as? OutlineNode else { continue }
            switch node.kind {
            case .project(let pid) where pid == id: return outlineView.rect(ofRow: r)
            case .folder(let fid) where fid == id:  return outlineView.rect(ofRow: r)
            default: continue
            }
        }
        return .zero
    }

    // MARK: - Context-menu actions (read `menuClickedNodeID`)

    @objc private func menuStopAnalysis(_ sender: NSMenuItem) {
        guard let id = menuClickedNodeID,
              let project = projectIndex?.projects.first(where: { $0.id == id }) else { return }
        pipelineRunner?.cancel(project: project)
    }

    @objc private func menuAnalyse(_ sender: NSMenuItem) {
        guard let id = menuClickedNodeID,
              let project = projectIndex?.projects.first(where: { $0.id == id }) else { return }
        pipelineRunner?.start(project: project)
    }

    /// Re-analyse is destructive, so this asks the *window* rather than
    /// starting anything: `--clean` is `rmtree(output_dir)`, and the
    /// confirmation lives with the window that can present a sheet.
    @objc private func menuReAnalyse(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { onReAnalyse(id) }
    }

    @objc private func menuCancelCopy(_ sender: NSMenuItem) {
        copyMachinery?.cancel()
    }

    @objc private func menuShowDiagnostics(_ sender: NSMenuItem) {
        guard let id = menuClickedNodeID else { return }
        presentDiagnosticPopover(projectID: id, anchorRect: rowRect(forNodeID: id))
    }

    @objc private func menuLocate(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { onLocate(id) }
    }

    @objc private func menuShowInFinder(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { onShowInFinder(id) }
    }

    @objc private func menuToggleAgentAccess(_ sender: NSMenuItem) {
        // Direct model write — the flag is host-side (projects.json) and
        // ProjectIndex posts the notification ServeManager syncs the
        // handshake from. Succeeds with no agent installed: a permission,
        // not a connection.
        guard let id = menuClickedNodeID,
              let project = projectIndex?.projects.first(where: { $0.id == id }) else { return }
        projectIndex?.setAgentAccess(id: id, enabled: !project.agentAccess)
    }

    @objc private func menuChooseIcon(_ sender: NSMenuItem) {
        guard let id = menuClickedNodeID else { return }
        presentIconPopover(projectID: id, anchorRect: rowRect(forNodeID: id))
    }

    @objc private func menuMoveToRoot(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { projectIndex?.moveProject(projectId: id, toFolder: nil) }
    }

    @objc private func menuMoveToFolder(_ sender: NSMenuItem) {
        guard let id = menuClickedNodeID, let folderID = sender.representedObject as? UUID else { return }
        projectIndex?.moveProject(projectId: id, toFolder: folderID)
    }

    @objc private func menuRemoveProject(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { onRemoveProject(id) }
    }

    @objc private func menuOpenInNewWindow(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { onOpenInNewWindow(id) }
    }

    @objc private func menuRemoveFolder(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { onRemoveFolder(id) }
    }

    @objc private func menuRename(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { beginRename(nodeID: id) }
    }

    @objc private func menuNoop(_ sender: NSMenuItem) {}   // disabled Archive (Phase 5)

    /// What the subtitle-right slot shows, by `ProjectRow.subtitleRightSlot`'s
    /// precedence (`:327-360`) plus the agent badge: run activity > in-flight
    /// copy > agent-access antenna > iCloud glyph > empty.
    /// `onStop` (Phase 4) is the hover-× cancel — run cancel / copy cancel; nil
    /// during the cancel-rollback spinner (you can't cancel a cancel).
    ///
    /// Known hole, accepted deliberately (§5a-bis): during a run the ring
    /// takes this slot and wins, so an exposed project shows no antenna —
    /// exposure stays true, just invisible while the run lasts.
    private enum RightSlot {
        case ring(fraction: Double?, onStop: (() -> Void)?)  // arc/spinner + hover-× cancel
        /// Agent Access is ON — exposure, not activity (§5a-bis). Solid
        /// while the project's serve is up (reachable NOW), pale while it
        /// is not open (reachable the moment it is). Off = no badge at
        /// all: absence is the information.
        case agent(exposedNow: Bool)
        case cloud
        case none
    }

    private func cellRightSlot(for project: Project) -> RightSlot {
        let id = project.id
        let activity = ProjectRowActivityIndicator.Kind.from(
            pipelineState: pipelineRunner?.state[id], progress: liveData?.progress[id])
        switch activity {
        case .running(let fraction):
            // `pipelineRunner.cancel` is idempotent + acks immediately (sets
            // isStopping → "Stopping…"); the × stays through stopping since the
            // run is `.running` until the process exits (ProjectRow parity).
            return .ring(fraction: fraction,
                         onStop: { [weak self] in self?.pipelineRunner?.cancel(project: project) })
        case .copying(let fraction):
            // `Kind.from` never produces `.copying` (copy isn't a PipelineState);
            // the real copy ring is the `copyDisplay` path below. Defensive.
            return .ring(fraction: fraction, onStop: nil)
        case .none:
            break
        }
        // The cloud batch reuses the copy ring exactly — `Kind.ring` already
        // means "a determinate, cancellable transfer into this project", which
        // is precisely what a download is. Nothing new is drawn.
        if let batch = importBatchDisplay(for: project) {
            let fraction = batch.total > 0
                ? Double(batch.done) / Double(batch.total)
                : 0
            return .ring(fraction: fraction,
                         onStop: { [weak self] in self?.cloudImport?.store?.stopFetch() })
        }
        if let copy = copyDisplay(for: project) {
            switch copy {
            case .copying(let fraction):
                return .ring(fraction: fraction,
                             onStop: { [weak self] in self?.copyMachinery?.cancel() })
            case .cancelling:
                return .ring(fraction: nil, onStop: nil)   // spinner during rollback, no ×
            }
        }
        if project.agentAccess {
            return .agent(exposedNow: handshakeProjectPaths.contains { AgentActivity.samePath($0, project.path) })
        }
        if case .inCloud = project.availability { return .cloud }
        return .none
    }

    /// The two-line project cell: icon (baseline-aligned to the title line) · name
    /// · session count on the title line; status text on the subtitle line. Layout
    /// constants per `ProjectCellSpec` (traceable to `ProjectRow`). Prefix/failure
    /// glyphs + the trailing ring + buttons land in Phases 2–4. `.placeholder` rows
    /// never reach here (collapsed to the single-line `iconCell` in `viewFor`).
    private func projectTwoLineCell(symbol: String, name: String, count: String?,
                                    subtitle: String, available: Bool,
                                    prefixGlyph: (symbol: String, color: NSColor)?,
                                    subtitleAction: SubtitleGlyphAction,
                                    subtitleActionProjectID: UUID?,
                                    agentProjectID: UUID?,
                                    rightSlot: RightSlot,
                                    shimmer: Bool) -> NSTableCellView {
        let cell = NSTableCellView()
        let imageView = NSImageView()
        imageView.image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil)
        imageView.symbolConfiguration = ProjectCellSpec.iconSymbolConfig
        // Edo forces Accent on available projects (Prussian for palette consistency);
        // Default leaves nil so system backgroundStyle tinting still fires.
        imageView.contentTintColor = available ? SidebarPalette.accentOverride : .secondaryLabelColor
        imageView.translatesAutoresizingMaskIntoConstraints = false

        let nameField = NSTextField(labelWithString: name)
        nameField.font = ProjectCellSpec.titleFont
        // `available ? .labelColor` was the existing forced-labelColor baseline —
        // preserve on Default via the `?? .labelColor` fallback; Edo shifts to Ink.
        nameField.textColor = available
            ? (SidebarPalette.inkOverride ?? .labelColor)
            : .secondaryLabelColor
        nameField.lineBreakMode = .byTruncatingTail
        nameField.translatesAutoresizingMaskIntoConstraints = false
        // Name yields before the count under pressure (count stays visible).
        nameField.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        // Running rows shimmer the status line ("Identifying speakers") — the
        // native rendering of the thinking spec (design-motion §4.7.1), hosting
        // the shared SwiftUI `ShimmerText`. `shimmer` is pre-gated by the caller
        // on `showAnalysisAnimation && !reduceMotion`; off → plain static label.
        let subtitleField: NSView
        if shimmer {
            let host = NSHostingView(rootView: ShimmerText(
                text: subtitle,
                rest: Color(nsColor: .secondaryLabelColor),
                font: Font(ProjectCellSpec.subtitleFont as CTFont),
                lineLimit: 1))
            host.translatesAutoresizingMaskIntoConstraints = false
            // Yield (truncate) before pushing the trailing ring/glyph off-edge —
            // the plain field does this via lineBreakMode; the host needs it set.
            host.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
            host.setContentHuggingPriority(.defaultLow, for: .horizontal)
            subtitleField = host
        } else if subtitleAction != .none, let subtitleActionProjectID {
            // **The glyph and its status text are one control** — wherever there
            // is a door, both open it.
            //
            // Three reasons, and the first is the strongest: the glyph is a
            // **10pt** target, which is small on a trackpad and unkind at any
            // accessibility setting, while the text beside it is a comfortable
            // one. Second, they are one message — splitting the hit region
            // between them is an implementation artefact, not a design. Third,
            // ⓘ-style disclosure treats its label as part of the control
            // everywhere else on the platform.
            //
            // Was `subtitleAction == .files` for one day, which is how the row
            // came to have two targets for `+3 unanalysed` and one for
            // `Partial completion`. Nothing produced that inconsistency on
            // purpose: the text became a target while the delta had no glyph,
            // then it gained a ⓘ and nobody went back.
            //
            // Accepted cost: this strip stops being row-selection area, so
            // clicking "Run failed" opens the popover rather than selecting the
            // project. Someone aiming at those words is asking why — and the
            // title line, the larger half of the row, is still the row's target.
            //
            // Styled to be indistinguishable from the plain label below: no
            // underline, no tint. The pointing-hand cursor on hover is the whole
            // affordance, per "attention, not affordance".
            let button = SubtitleActionButton(title: subtitle,
                                              target: self,
                                              action: #selector(subtitleActionClicked(_:)))
            button.projectID = subtitleActionProjectID
            button.subtitleAction = subtitleAction
            button.isBordered = false
            button.setButtonType(.momentaryChange)
            button.alignment = .left          // NSButton centres by default.
            let para = NSMutableParagraphStyle()
            para.lineBreakMode = .byTruncatingTail
            para.alignment = .left
            button.attributedTitle = NSAttributedString(string: subtitle, attributes: [
                .font: ProjectCellSpec.subtitleFont,
                .foregroundColor: NSColor.secondaryLabelColor,
                .paragraphStyle: para,
            ])
            button.setAccessibilityLabel(subtitle)
            button.translatesAutoresizingMaskIntoConstraints = false
            button.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
            button.setContentHuggingPriority(.defaultLow, for: .horizontal)
            subtitleField = button
        } else {
            let field = NSTextField(labelWithString: subtitle)
            field.font = ProjectCellSpec.subtitleFont
            field.textColor = .secondaryLabelColor
            field.lineBreakMode = .byTruncatingTail
            field.translatesAutoresizingMaskIntoConstraints = false
            subtitleField = field
        }

        cell.imageView = imageView
        cell.textField = nameField
        cell.addSubview(imageView)
        cell.addSubview(nameField)
        cell.addSubview(subtitleField)

        var constraints: [NSLayoutConstraint] = [
            imageView.leadingAnchor.constraint(equalTo: cell.leadingAnchor),
            imageView.widthAnchor.constraint(equalToConstant: ProjectCellSpec.iconWidth),
            // Icon sits on the TITLE line (centred on the name), not the whole row —
            // ProjectRow's `.firstTextBaseline` ("belongs to the project name", :115-119).
            imageView.centerYAnchor.constraint(equalTo: nameField.centerYAnchor),
            nameField.leadingAnchor.constraint(equalTo: imageView.trailingAnchor,
                                               constant: ProjectCellSpec.iconToText),
            nameField.topAnchor.constraint(equalTo: cell.topAnchor,
                                           constant: ProjectCellSpec.verticalInset),
            subtitleField.topAnchor.constraint(equalTo: nameField.bottomAnchor,
                                               constant: ProjectCellSpec.titleToSubtitle),
        ]

        // Subtitle leading — after the prefix glyph (cantFind ⚠/❓, failure/partial)
        // when present, else aligned with the name. A failure/partial glyph
        // (`diagnosticsProjectID != nil`) is a clickable button → diagnostic popover;
        // cantFind stays a static image (its action is Locate, a separate door).
        if let prefixGlyph {
            let glyphImage = NSImage(systemSymbolName: prefixGlyph.symbol, accessibilityDescription: nil)?
                .withSymbolConfiguration(ProjectCellSpec.subtitleGlyphConfig)
            let glyph: NSView
            if subtitleAction != .none, let subtitleActionProjectID {
                let button = SubtitleActionButton(image: glyphImage ?? NSImage(),
                                                  target: self,
                                                  action: #selector(subtitleActionClicked(_:)))
                button.projectID = subtitleActionProjectID
                button.subtitleAction = subtitleAction
                button.isBordered = false
                button.bezelStyle = .regularSquare
                button.imagePosition = .imageOnly
                button.contentTintColor = prefixGlyph.color
                // The diagnostic glyph reuses its menu twin's key, so the two
                // read identically to VoiceOver. `.files` has no menu twin —
                // the subtitle already says "3 files missing", which is the
                // better label than anything invented for it.
                switch subtitleAction {
                case .diagnostics:
                    button.setAccessibilityLabel(i18n?.t("desktop.menu.project.showDiagnostics"))
                case .files, .none:
                    button.setAccessibilityLabel(subtitle)
                }
                glyph = button
            } else {
                let imageView = NSImageView()
                imageView.image = glyphImage
                imageView.contentTintColor = prefixGlyph.color
                glyph = imageView
            }
            glyph.translatesAutoresizingMaskIntoConstraints = false
            glyph.setContentHuggingPriority(.required, for: .horizontal)
            glyph.setContentCompressionResistancePriority(.required, for: .horizontal)
            cell.addSubview(glyph)
            constraints += [
                glyph.leadingAnchor.constraint(equalTo: nameField.leadingAnchor),
                glyph.centerYAnchor.constraint(equalTo: subtitleField.centerYAnchor),
                subtitleField.leadingAnchor.constraint(equalTo: glyph.trailingAnchor,
                                                        constant: ProjectCellSpec.subtitleInternal),
            ]
        } else {
            constraints.append(subtitleField.leadingAnchor.constraint(equalTo: nameField.leadingAnchor))
        }

        // Subtitle-right — run/copy ring (Phase 3) takes precedence, then the iCloud
        // status glyph, then nothing (ProjectRow.subtitleRightSlot :327-360). The
        // ring carries its Phase-4 hover-× cancel via `onStop`.
        switch rightSlot {
        case .ring(let fraction, let onStop):
            let ring = SidebarActivityRing(fraction: fraction, onStop: onStop)
            ring.setContentHuggingPriority(.required, for: .horizontal)
            ring.setContentCompressionResistancePriority(.required, for: .horizontal)
            cell.addSubview(ring)
            constraints += [
                ring.trailingAnchor.constraint(equalTo: cell.trailingAnchor,
                                               constant: -ProjectCellSpec.trailingInset),
                ring.centerYAnchor.constraint(equalTo: subtitleField.centerYAnchor),
                ring.widthAnchor.constraint(equalToConstant: SidebarActivityRing.side),
                ring.heightAnchor.constraint(equalToConstant: SidebarActivityRing.side),
                subtitleField.trailingAnchor.constraint(lessThanOrEqualTo: ring.leadingAnchor,
                                                        constant: -ProjectCellSpec.subtitleInternal),
            ]
        case .agent(let exposedNow):
            // Exposure, not activity (§5a-bis). Same builder as the
            // single-line collapse, so the two layouts can't drift.
            let antenna = agentBadgeView(exposedNow: exposedNow, projectID: agentProjectID)
            cell.addSubview(antenna)
            constraints += [
                antenna.trailingAnchor.constraint(equalTo: cell.trailingAnchor,
                                                  constant: -ProjectCellSpec.trailingInset),
                antenna.centerYAnchor.constraint(equalTo: subtitleField.centerYAnchor),
                subtitleField.trailingAnchor.constraint(lessThanOrEqualTo: antenna.leadingAnchor,
                                                        constant: -ProjectCellSpec.subtitleInternal),
            ]
        case .cloud:
            let cloud = NSImageView()
            cloud.image = NSImage(systemSymbolName: "icloud", accessibilityDescription: nil)
            cloud.symbolConfiguration = ProjectCellSpec.subtitleGlyphConfig
            cloud.contentTintColor = .secondaryLabelColor
            cloud.translatesAutoresizingMaskIntoConstraints = false
            cloud.setContentHuggingPriority(.required, for: .horizontal)
            cloud.setContentCompressionResistancePriority(.required, for: .horizontal)
            cell.addSubview(cloud)
            constraints += [
                cloud.trailingAnchor.constraint(equalTo: cell.trailingAnchor,
                                                constant: -ProjectCellSpec.trailingInset),
                cloud.centerYAnchor.constraint(equalTo: subtitleField.centerYAnchor),
                subtitleField.trailingAnchor.constraint(lessThanOrEqualTo: cloud.leadingAnchor,
                                                        constant: -ProjectCellSpec.subtitleInternal),
            ]
        case .none:
            constraints.append(subtitleField.trailingAnchor.constraint(equalTo: cell.trailingAnchor,
                                                                       constant: -ProjectCellSpec.trailingInset))
        }
        if let count {
            let countField = NSTextField(labelWithString: count)
            countField.font = ProjectCellSpec.countFont
            countField.textColor = .tertiaryLabelColor
            countField.translatesAutoresizingMaskIntoConstraints = false
            countField.setContentHuggingPriority(.required, for: .horizontal)
            countField.setContentCompressionResistancePriority(.required, for: .horizontal)
            cell.addSubview(countField)
            constraints += [
                nameField.trailingAnchor.constraint(lessThanOrEqualTo: countField.leadingAnchor,
                                                    constant: -ProjectCellSpec.titleInternal),
                countField.trailingAnchor.constraint(equalTo: cell.trailingAnchor,
                                                     constant: -ProjectCellSpec.trailingInset),
                countField.firstBaselineAnchor.constraint(equalTo: nameField.firstBaselineAnchor),
            ]
        } else {
            constraints.append(nameField.trailingAnchor.constraint(
                lessThanOrEqualTo: cell.trailingAnchor, constant: -ProjectCellSpec.trailingInset))
        }
        NSLayoutConstraint.activate(constraints)
        return cell
    }

    private func groupCell(text: String) -> NSTableCellView {
        let cell = NSTableCellView()
        let textField = NSTextField(labelWithString: text)
        textField.translatesAutoresizingMaskIntoConstraints = false
        cell.textField = textField
        cell.addSubview(textField)
        NSLayoutConstraint.activate([
            textField.leadingAnchor.constraint(equalTo: cell.leadingAnchor),
            textField.trailingAnchor.constraint(equalTo: cell.trailingAnchor),
            textField.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
        ])
        return cell
    }

    private func node(from item: Any?) -> OutlineNode? {
        item as? OutlineNode
    }
}

// SourceListSelectionRowView moved to its own file (SourceListSelectionRowView.swift)
// when the sessions popover became its second consumer — one shared row view is
// what stops the sidebar's and the popover's selection treatment drifting.

/// The paper tint overlay view — a plain layer-backed NSView that also
/// forwards the AppKit `viewDidChangeEffectiveAppearance` callback so the
/// controller can re-snapshot the dynamic `NSColor` → `CGColor` on a system
/// light↔dark toggle. Without the callback the CALayer's `backgroundColor`
/// (which is a static CGColor) sticks on the previous appearance's variant.
private final class PaletteTintView: NSView {
    var onAppearanceChange: (() -> Void)?

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        onAppearanceChange?()
    }
}
