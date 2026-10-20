import Foundation

/// A reference-type node for the AppKit `NSOutlineView` sidebar.
///
/// `NSOutlineView` holds its items **by reference** and compares identity by
/// object pointer, while our model (`Project`/`Folder`) are value types whose
/// `@Published` array is wholesale-reassigned on every `save()`. So the tree is
/// rebuilt into `OutlineNode`s whose `id` is keyed off the model UUID — selection
/// and expansion are restored by matching `id` across reloads. This is the AppKit
/// manifestation of the UUID-stable identity the SwiftUI `List` got for free
/// (spec `design-desktop-sidebar-appkit.md` §2.5).
final class OutlineNode: NSObject {
    enum Kind: Equatable {
        case group(String)   // a section header row ("Projects"); also the lenses group
        case lens(Tab)       // a mode row — fires switchToTab, NOT a list selection
        case folder(UUID)
        case project(UUID)
    }

    let kind: Kind
    private(set) var children: [OutlineNode]
    private(set) weak var parent: OutlineNode?

    init(_ kind: Kind, children: [OutlineNode] = []) {
        self.kind = kind
        self.children = children
        super.init()
        for child in children { child.parent = self }
    }

    /// `NSOutlineView` matches items across reloads via `isEqual:`/`hash`. Key on
    /// the stable model-UUID `id` so selection + expansion survive a `reloadData`
    /// even though the nodes are rebuilt each update (the §2.5 identity contract;
    /// without this it falls back to pointer identity and drops state).
    override func isEqual(_ object: Any?) -> Bool {
        (object as? OutlineNode)?.id == id
    }

    override var hash: Int { id.hashValue }

    /// Stable identity for selection + expansion restore (keyed off the model UUID).
    var id: String {
        switch kind {
        case .group(let title):  "group:\(title)"
        case .lens(let tab):     "lens:\(tab.rawValue)"
        case .folder(let uuid):  "folder:\(uuid.uuidString)"
        case .project(let uuid): "project:\(uuid.uuidString)"
        }
    }

    var isGroup: Bool {
        if case .group = kind { return true }
        return false
    }

    var isLens: Bool {
        if case .lens = kind { return true }
        return false
    }

    /// Lens rows + group headers are not part of the project selection set
    /// (mode ≠ selection, spec §3.1).
    var isSelectable: Bool {
        switch kind {
        case .project, .folder: true
        case .group, .lens: false
        }
    }

    var isExpandable: Bool { !children.isEmpty || isGroup }

    /// The drag payload for this node, or `nil` if the row isn't draggable.
    /// Projects **and folders** are draggable — reorder within a scope, and (projects
    /// only) re-parent between scopes. Group headers and lens rows never are: a group
    /// is chrome, and a lens is a mode, not a thing with a place in a list.
    var dragItem: SidebarDragItem? {
        switch kind {
        case .project(let id): .project(id)
        case .folder(let id):  .folder(id)
        case .group, .lens:    nil
        }
    }

    /// The `SidebarSelection` this node maps to, if it participates in selection.
    var selection: SidebarSelection? {
        switch kind {
        case .project(let id): .project(id)
        case .folder(let id): .folder(id)
        case .group, .lens: nil
        }
    }
}

/// Builds the `OutlineNode` tree for the sidebar from the model. **Pure** — takes
/// value snapshots, returns the root nodes — so it's unit-tested in
/// `OutlineNodeTests` (the spec §5 tree-mapping seam). Mirrors
/// `ProjectIndex.sidebarItems` + `projectsInFolder`.
enum OutlineTree {
    /// Group-row keys. Code-internal (the "Projects" header's *display* string is
    /// localised separately in the cell). Shared by the producer (`build`) and the
    /// consumers (group-cell title + `SidebarExternalDrop.resolve`) so a rename
    /// can't silently desync drop-routing from the tree (review F36).
    static let lensesGroupKey = "Lenses"
    static let projectsGroupKey = "Projects"

    /// Root layout (spec §1.3 / §3.1): a **lenses** group (the mode rows) then a
    /// **"Projects"** group (mixed case) holding root projects + folders; folders
    /// disclose to their child projects. Built for more groups later.
    static func build(lenses: [LensItem],
                      projects: [Project],
                      folders: [Folder]) -> [OutlineNode] {
        var roots: [OutlineNode] = []

        if !lenses.isEmpty {
            let lensRows = lenses.map { OutlineNode(.lens($0.tab)) }
            roots.append(OutlineNode(.group(Self.lensesGroupKey), children: lensRows))
        }

        let rootProjectItems: [(pos: Int, node: OutlineNode)] = projects
            .filter { $0.folderId == nil }
            .map { ($0.position, OutlineNode(.project($0.id))) }
        let folderItems: [(pos: Int, node: OutlineNode)] = folders.map { folder in
            let kids = projects
                .filter { $0.folderId == folder.id }
                .sorted { $0.position < $1.position }
                .map { OutlineNode(.project($0.id)) }
            return (folder.position, OutlineNode(.folder(folder.id), children: kids))
        }
        let projectChildren = (rootProjectItems + folderItems)
            .sorted { $0.pos < $1.pos }
            .map(\.node)
        roots.append(OutlineNode(.group(Self.projectsGroupKey), children: projectChildren))

        return roots
    }
}

extension OutlineTree {
    /// The rows `roots` lays out, top to bottom: each node, then a group's
    /// children always, and a folder's when `isExpanded` says it is open. The
    /// rule `SidebarOutlineController.reloadAndRestore` expands by.
    static func rowKinds(_ roots: [OutlineNode],
                         isExpanded: (OutlineNode) -> Bool) -> [OutlineNode.Kind] {
        roots.flatMap { node -> [OutlineNode.Kind] in
            let open = node.isGroup || isExpanded(node)
            return [node.kind] + (open ? rowKinds(node.children, isExpanded: isExpanded) : [])
        }
    }

    /// The rows to redraw while the name field in `editing`'s row is open
    /// (R56): every row but that one, since a reload of the edited row tears
    /// its field editor down. Nil when the rows themselves differ (a study
    /// added, removed, moved, a folder opened), because then the rows would
    /// shift under the field; the list waits for the name, and the commit's
    /// full reload catches up.
    static func rowsToRefreshDuringRename(displayed: [OutlineNode.Kind?],
                                          next: [OutlineNode.Kind],
                                          editing: UUID) -> IndexSet? {
        guard displayed == next.map(Optional.some),
              let edited = next.firstIndex(where: { $0 == .project(editing) || $0 == .folder(editing) })
        else { return nil }
        var rows = IndexSet(integersIn: 0..<next.count)
        rows.remove(edited)
        return rows
    }
}
