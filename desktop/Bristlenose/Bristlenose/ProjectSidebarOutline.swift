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
/// complete; **inline rename** (cell-edit + reload-guard) is the one remaining
/// controller-track item — the context-menu "Rename" lands with it. See QA / TODO.
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

/// A clickable failure/partial subtitle glyph that opens the diagnostic popover
/// anchored to itself. Carries the project id so the controller's action resolves
/// the project + state. `cantFind` ("missing") glyphs are NOT this — that glyph is a
/// Locate affordance, rendered as a static image.
private final class DiagnosticGlyphButton: NSButton {
    var projectID: UUID?
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
    let onShowInFinder: (UUID) -> Void
    let canShowInFinder: (UUID) -> Bool
    let onRemoveProject: (UUID) -> Void
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
        // Refresh the callbacks each update so they capture the live binding —
        // the AppKit delegate does not fire for programmatic selection, so the
        // funnel is the SwiftUI binding itself (§2.5).
        controller.onSelectionChange = { newSelection in
            if selection != newSelection { selection = newSelection }
        }
        controller.onActivateLens = onActivateLens
        controller.onExternalDrop = onExternalDrop
        controller.onLocate = onLocate
        controller.onShowInFinder = onShowInFinder
        controller.canShowInFinder = canShowInFinder
        controller.onRemoveProject = onRemoveProject
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
    }
}

/// Owns the `NSScrollView` + `NSOutlineView` and acts as data source + delegate.
@MainActor
final class SidebarOutlineController: NSViewController, NSOutlineViewDataSource, NSOutlineViewDelegate, NSPopoverDelegate, NSMenuDelegate {
    let outlineView = NSOutlineView()
    private let scrollView = NSScrollView()
    private var roots: [OutlineNode] = []

    /// Native `NSPasteboard` type for internal project drags (decision 22 Jun:
    /// native, not `Transferable` — this migration removes the other SwiftUI drag
    /// sites). A distinct UTI so it never collides with `public.file-url` (the
    /// Finder-file drop) — the typed-payload lesson from the SwiftUI sidebar.
    static let projectDragType = NSPasteboard.PasteboardType("app.bristlenose.project-drag")

    weak var projectIndex: ProjectIndex?
    weak var i18n: I18n?
    weak var pipelineRunner: PipelineRunner?
    weak var liveData: PipelineLiveData?
    weak var copyMachinery: CopyMachinery?
    var lensItems: [LensItem] = LensItem.all
    var onSelectionChange: (Set<SidebarSelection>) -> Void = { _ in }
    var onActivateLens: (Tab) -> Void = { _ in }
    var onExternalDrop: (SidebarExternalDrop, [URL]) -> Void = { _, _ in }
    var onLocate: (UUID) -> Void = { _ in }
    var onShowInFinder: (UUID) -> Void = { _ in }
    var canShowInFinder: (UUID) -> Bool = { _ in false }
    var onRemoveProject: (UUID) -> Void = { _ in }
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

    /// The project/folder id of the right-clicked row, captured in `menuNeedsUpdate`
    /// and read by the menu actions (stable while the menu is open — you can't
    /// right-click a new row while a menu is up).
    private var menuClickedNodeID: UUID?

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
        // Two distinct destination types: `projectDragType` (internal reorder,
        // `.move`) and `.fileURL` (Finder folder-of-videos import, `.copy`). The
        // payload class disambiguates them at validate/accept time — a Finder drag
        // can't read as `projectDragType` and a project drag can't read as a file
        // URL — so the two never collide.
        outlineView.registerForDraggedTypes([Self.projectDragType, .fileURL])
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

        view = container
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    /// Live palette-change hook. Called on `.bristlenosePaletteChanged` (fired
    /// by `AppearanceSettingsView`'s `@AppStorage("palette")` `.onChange`).
    @objc private func paletteDidChange() {
        updatePaletteTint()
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
        outlineView.reloadData()

        // Expand groups (always) + non-collapsed folders.
        for group in roots where group.isGroup {
            outlineView.expandItem(group)
            for child in group.children where isFolderExpanded(child) {
                outlineView.expandItem(child)
            }
        }

        applySelection(selection)

        // Kick off the one-shot icon reveal for a freshly-created project, if any.
        maybeStartIconReveal()
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
            self.outlineView.reloadData()   // rebuild the cell with its icon visible (alpha 1)
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
            // re-enter applySelection mid-proposal (gruber's re-entrancy guard); guard
            // tab != activeTab so re-clicking the active lens is a no-op.
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
        guard let node = item as? OutlineNode, case .project(let id) = node.kind else { return nil }
        let pbItem = NSPasteboardItem()
        pbItem.setString(id.uuidString, forType: Self.projectDragType)
        return pbItem
    }

    func outlineView(_ outlineView: NSOutlineView, validateDrop info: NSDraggingInfo,
                     proposedItem item: Any?, proposedChildIndex index: Int) -> NSDragOperation {
        // Finder folder/file import takes precedence over the internal-reorder
        // path (the two payload types are mutually exclusive on the pasteboard).
        if pasteboardHasFileURLs(info.draggingPasteboard) {
            guard let target = externalDropTarget(item: item) else { return [] }
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

        guard let moves = decideDrop(info: info, item: item, index: index),
              let projectIndex else { return false }
        // Folder membership is the structural Phase-B fix (out-of-folder,
        // between-folder, into-folder). Within-scope ordering by `toIndex` is a
        // refinement — `moveProject` sets `folderId`; position reorder is TODO.
        for move in moves {
            projectIndex.moveProject(projectId: move.projectID, toFolder: move.toFolder)
        }
        return true
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
    private func externalDropTarget(item: Any?) -> SidebarExternalDrop? {
        SidebarExternalDrop.resolve(droppedOn: (item as? OutlineNode)?.kind)
    }

    private func decideDrop(info: NSDraggingInfo, item: Any?, index: Int) -> [ProjectMove]? {
        let ids = draggedProjectIDs(from: info)
        let at = index == NSOutlineViewDropOnItemIndex ? DropRouting.append : index
        let decision = DropRouting.resolve(
            draggedProjectIDs: ids, onto: dropParent(for: item), at: at,
            isProjectID: { id in self.projectIndex?.projects.contains { $0.id == id } ?? false }
        )
        if case .move(let moves) = decision { return moves }
        return nil
    }

    private func dropParent(for item: Any?) -> DropParent {
        guard let node = item as? OutlineNode else { return .root }
        switch node.kind {
        case .folder(let id): return .folder(id)
        case .group, .project, .lens: return .root
        }
    }

    private func draggedProjectIDs(from info: NSDraggingInfo) -> [UUID] {
        (info.draggingPasteboard.pasteboardItems ?? []).compactMap { item in
            item.string(forType: Self.projectDragType).flatMap { UUID(uuidString: $0) }
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
            // No subtitle (`.placeholder`, or a defensive nil) → single-line collapse,
            // the deliberate divergence (ProjectCellSpec). Reuse the single-line iconCell.
            guard let subtitle else {
                return hideIconIfRevealing(
                    iconCell(symbol: symbol, text: project.name, trailing: count), id: id)
            }
            let prefix = subtitlePrefixGlyph(for: variant, availability: project.availability)
            let diagnosticsID = variant.isDiagnostic ? id : nil
            return hideIconIfRevealing(
                projectTwoLineCell(symbol: symbol, name: project.name, count: count,
                                   subtitle: subtitle, available: project.availability.isReady,
                                   prefixGlyph: prefix, diagnosticsProjectID: diagnosticsID,
                                   rightSlot: cellRightSlot(for: project)),
                id: id)
        }
    }

    // MARK: - Cells

    private func lensLabel(_ tab: Tab) -> String {
        if let i18n { return tab.fullLocalizedLabel(i18n) }
        return tab.label
    }

    private func iconCell(symbol: String, text: String, dimmed: Bool = false, trailing: String? = nil) -> NSTableCellView {
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
                countField.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -4),
                countField.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            ]
        } else {
            constraints.append(textField.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -4))
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

    /// Subtitle PREFIX glyph (symbol + tint) for a variant, or nil. Mirrors the glyph
    /// choices in `ProjectRow.subtitleContent` (`:229-254`): cantFind → reason-aware
    /// glyph in orange; failed/diagnostic → the `MessageKind.error` glyph; partial →
    /// `MessageKind.warning`. The failure glyph's clickability (→ diagnostics) is
    /// Phase 4 — here it renders static.
    private func subtitlePrefixGlyph(for variant: SubtitleVariant,
                                     availability: ProjectAvailability) -> (symbol: String, color: NSColor)? {
        switch variant {
        case .cantFind:
            return (availability.sfSymbolName ?? "questionmark.folder", NSColor(Color.orange))
        case .failed, .failedDiagnostic:
            return (MessageKind.error.symbolName, NSColor(MessageKind.error.tint))
        case .completedPartial:
            return (MessageKind.warning.symbolName, NSColor(MessageKind.warning.tint))
        default:
            return nil
        }
    }

    /// The subtitle failure glyph → diagnostic popover, anchored to the glyph's frame.
    @objc private func diagnosticGlyphClicked(_ sender: DiagnosticGlyphButton) {
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
        let content = ProjectDiagnosticPopover(project: project, state: state, liveData: liveData)
            .environmentObject(i18n)
            .padding(16)
            .frame(width: 360, height: 320)
        showRowPopover(NSHostingController(rootView: content), at: rect)
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
        case .group, .lens:    menuClickedNodeID = nil   // no menu on group headers / lens rows
        }
    }

    private func menuItem(_ key: String, _ action: Selector, enabled: Bool = true) -> NSMenuItem {
        let mi = NSMenuItem(title: i18n?.t(key) ?? key, action: action, keyEquivalent: "")
        mi.target = self
        mi.isEnabled = enabled
        return mi
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
        if case .cantFind = availability {
            menu.addItem(menuItem("desktop.chrome.locate", #selector(menuLocate(_:))))
            menu.addItem(.separator())
        }
        menu.addItem(menuItem("desktop.menu.project.showInFinder", #selector(menuShowInFinder(_:)),
                              enabled: canShowInFinder(id)))
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

        menu.addItem(.separator())
        menu.addItem(menuItem("desktop.menu.project.removeFromSidebar", #selector(menuRemoveProject(_:))))
    }

    private func buildFolderMenu(_ menu: NSMenu, folderID id: UUID) {
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
    private func canAnalyse(_ id: UUID, state: PipelineState?) -> Bool {
        guard let p = projectIndex?.projects.first(where: { $0.id == id }),
              p.inputFiles == nil, !p.path.isEmpty else { return false }
        switch state ?? .idle {
        case .idle, .stopped, .failed, .failedWithDiagnostic: return true
        default: return false
        }
    }

    private func isFailureState(_ state: PipelineState?) -> Bool {
        switch state { case .failed, .failedWithDiagnostic, .completedPartial: return true; default: return false }
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

    @objc private func menuRemoveFolder(_ sender: NSMenuItem) {
        if let id = menuClickedNodeID { onRemoveFolder(id) }
    }

    @objc private func menuNoop(_ sender: NSMenuItem) {}   // disabled Archive (Phase 5)

    /// What the subtitle-right slot shows, by `ProjectRow.subtitleRightSlot`'s
    /// precedence (`:327-360`): run activity > in-flight copy > iCloud glyph > empty.
    /// `onStop` (Phase 4) is the hover-× cancel — run cancel / copy cancel; nil
    /// during the cancel-rollback spinner (you can't cancel a cancel).
    private enum RightSlot {
        case ring(fraction: Double?, onStop: (() -> Void)?)  // arc/spinner + hover-× cancel
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
        if let copy = copyDisplay(for: project) {
            switch copy {
            case .copying(let fraction):
                return .ring(fraction: fraction,
                             onStop: { [weak self] in self?.copyMachinery?.cancel() })
            case .cancelling:
                return .ring(fraction: nil, onStop: nil)   // spinner during rollback, no ×
            }
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
                                    diagnosticsProjectID: UUID?,
                                    rightSlot: RightSlot) -> NSTableCellView {
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

        let subtitleField = NSTextField(labelWithString: subtitle)
        subtitleField.font = ProjectCellSpec.subtitleFont
        subtitleField.textColor = .secondaryLabelColor
        subtitleField.lineBreakMode = .byTruncatingTail
        subtitleField.translatesAutoresizingMaskIntoConstraints = false

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
            if let diagnosticsProjectID {
                let button = DiagnosticGlyphButton(image: glyphImage ?? NSImage(),
                                                   target: self,
                                                   action: #selector(diagnosticGlyphClicked(_:)))
                button.projectID = diagnosticsProjectID
                button.isBordered = false
                button.bezelStyle = .regularSquare
                button.imagePosition = .imageOnly
                button.contentTintColor = prefixGlyph.color
                button.setAccessibilityLabel(i18n?.t("desktop.menu.project.showDiagnostics"))
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

/// Forces the **unemphasized** source-list selection (grey ground + accent-tinted
/// content) in ALL focus states. The default `.sourceList` selection flips to a
/// vivid-blue fill / white text when the outline is first responder + key; real
/// source lists (Finder/Photos) are focus-stable, so we pin `isEmphasized`.
/// The row view for ALL source-list rows — project, folder, and the genuinely-
/// selected active lens. The active lens is kept in `selectedRowIndexes`
/// (`applySelection` + `selectionIndexesForProposedSelection`) precisely so the
/// TABLE draws its capsule with the same internal source-list rendering as a
/// selected project — exact colour / margin / radius, all of which a hand-placed
/// view cannot match (the source-list selection colour is internal to the table and
/// matches no public UI-element-colour token — verified by sampling all of them).
/// The `isEmphasized` pin is the focus-stability attempt; it's largely inert on the
/// current macOS draw path (project + lens both show the native two-state the user
/// accepted as matching Mail), kept as the single shared emphasis behaviour so the
/// two can never diverge.
private class SourceListSelectionRowView: NSTableRowView {
    override var isEmphasized: Bool {
        get { false }
        set { }
    }
}

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
