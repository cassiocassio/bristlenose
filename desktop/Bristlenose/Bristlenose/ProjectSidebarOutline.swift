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
/// lens rows that fire `switchToTab`, and folder expand/collapse. The rich cell
/// content (activity ring · copy progress · subtitle precedence · diagnostic
/// popover), drag-and-drop (the `DropRouting` apocalypse fix), context menus, and
/// inline rename are the remaining work — see the QA / TODO notes.
struct ProjectSidebarOutline: NSViewControllerRepresentable {
    @ObservedObject var projectIndex: ProjectIndex
    @ObservedObject var i18n: I18n
    @Binding var selection: Set<SidebarSelection>
    let lenses: [LensItem]
    let activeTab: Tab?
    let lensesEnabled: Bool
    let onActivateLens: (Tab) -> Void
    /// Live per-project run/copy data for the rich cell port. Plain refs — the
    /// controller reads current state from these reference types, and ContentView's
    /// own `pipelineRunner` observation re-creates this representable on state
    /// transitions (→ `updateNSViewController` → reload). High-frequency progress
    /// *ticking* (ring fraction / ETA) gets explicit `@ObservedObject` observation
    /// when the ring lands (Phase 3) — deferred so we don't reload-churn before a
    /// cell actually renders the live signal.
    let pipelineRunner: PipelineRunner
    let liveData: PipelineLiveData
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
final class SidebarOutlineController: NSViewController, NSOutlineViewDataSource, NSOutlineViewDelegate {
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

    /// Re-entrancy guard (spec §2.5): suppress the selection callback while we
    /// apply selection programmatically, so `selectRowIndexes` doesn't echo back.
    private var isApplyingProgrammatic = false

    /// The current mode/lens. Drives which lens row is genuinely selected (so the
    /// table draws its capsule) — stored on each `update`. Mode, not selection (§3.1).
    private var activeTab: Tab?

    /// Whether the lenses are interactive — true iff a report is showing. When
    /// false (no project / no report), lens rows are dimmed and clicking one is a
    /// no-op (a mode switch is meaningless without a report). Restores the SwiftUI
    /// LensRail's `isEnabled` gating that the AppKit port initially dropped.
    private var lensesEnabled = false

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
        outlineView.rowSizeStyle = .default
        outlineView.allowsMultipleSelection = true
        outlineView.allowsEmptySelection = true
        outlineView.indentationPerLevel = 14
        outlineView.dataSource = self
        outlineView.delegate = self
        outlineView.autoresizingMask = [.width, .height]
        outlineView.registerForDraggedTypes([Self.projectDragType])
        outlineView.setDraggingSourceOperationMask(.move, forLocal: true)

        scrollView.documentView = outlineView
        scrollView.hasVerticalScroller = true
        scrollView.drawsBackground = false   // let the column's vibrancy through (§1.4)
        scrollView.automaticallyAdjustsContentInsets = true

        view = scrollView
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
        decideDrop(info: info, item: item, index: index) == nil ? [] : .move
    }

    func outlineView(_ outlineView: NSOutlineView, acceptDrop info: NSDraggingInfo,
                     item: Any?, childIndex index: Int) -> Bool {
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
            case "Lenses":   title = ""
            case "Projects": title = i18n?.t("desktop.chrome.projects") ?? key
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
            let project = projectIndex?.projects.first { $0.id == id }
            let count = projectIndex?.unanalysed[id]?.sessionCount
            return iconCell(symbol: project?.icon ?? "circle",
                            text: project?.name ?? "Project",
                            trailing: count.map { String($0) })
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
        imageView.symbolConfiguration = NSImage.SymbolConfiguration(scale: .medium)
        // Normally no explicit tint: SF Symbols are template images, so the system
        // tints icon + label via `backgroundStyle` (selected → accent, else label) —
        // identical for a selected project and the genuinely-selected active lens.
        // `dimmed` (a disabled lens — no project / no report) paints both secondary
        // so the row reads inactive, restoring the old LensRail's disabled look.
        imageView.contentTintColor = dimmed ? .secondaryLabelColor : nil
        imageView.translatesAutoresizingMaskIntoConstraints = false
        let textField = NSTextField(labelWithString: text)
        if dimmed { textField.textColor = .secondaryLabelColor }
        textField.lineBreakMode = .byTruncatingTail
        textField.translatesAutoresizingMaskIntoConstraints = false
        cell.imageView = imageView
        cell.textField = textField
        cell.addSubview(imageView)
        cell.addSubview(textField)
        var constraints: [NSLayoutConstraint] = [
            imageView.leadingAnchor.constraint(equalTo: cell.leadingAnchor),
            imageView.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
            imageView.widthAnchor.constraint(equalToConstant: 18),
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
