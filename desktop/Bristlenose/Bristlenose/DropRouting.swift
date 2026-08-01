import Foundation

/// A sidebar item being dragged — a project or a folder. **One kind-tagged payload
/// covers both**, so a mixed multi-select drag needs a single pasteboard reader
/// rather than one per type (and a folder drag can't be mistaken for a Finder
/// `URL` drag, which is what a bare-`String` payload used to allow).
enum SidebarDragItem: Equatable, Hashable {
    case project(UUID)
    case folder(UUID)

    var id: UUID {
        switch self {
        case .project(let id), .folder(let id): id
        }
    }

    var isFolder: Bool {
        if case .folder = self { return true }
        return false
    }

    // MARK: - Pasteboard codec

    /// `"project:<uuid>"` / `"folder:<uuid>"` — round-trips through
    /// `init?(pasteboardString:)`.
    var pasteboardString: String {
        switch self {
        case .project(let id): "project:\(id.uuidString)"
        case .folder(let id):  "folder:\(id.uuidString)"
        }
    }

    init?(pasteboardString: String) {
        let parts = pasteboardString.split(separator: ":", maxSplits: 1,
                                           omittingEmptySubsequences: false)
        guard parts.count == 2, let id = UUID(uuidString: String(parts[1])) else { return nil }
        switch parts[0] {
        case "project": self = .project(id)
        case "folder":  self = .folder(id)
        default:        return nil
        }
    }
}

/// The proposed drop parent in the outline.
enum DropParent: Equatable {
    case root
    case folder(UUID)
}

/// A resolved drop: which items move, into which scope, at which index.
///
/// **One plan per drag, not one move per item.** The dragged items always land as a
/// contiguous run at `atIndex`, so a per-item index is redundant state that has to be
/// kept consistent with the run — which the previous `[ProjectMove]` shape did by
/// computing `index + offset` and then discarding it.
struct DropPlan: Equatable {
    /// The dragged items, in drag order — which is also their final order.
    let items: [SidebarDragItem]
    /// Destination scope. `nil` = root (the interleaved folder-and-project sequence).
    let toFolder: UUID?
    /// Insertion index within the destination scope, in that scope's **pre-move**
    /// coordinates — the insertion line the user is looking at.
    /// `DropRouting.append` = end of the scope.
    let atIndex: Int
}

enum DropDecision: Equatable {
    case move(DropPlan)
    case invalid
}

/// Pure resolution of a sidebar drag-and-drop into a concrete plan. This is the
/// **unified insertion model** that fixes the "sidebar apocalypse" structural gaps —
/// out-of-folder, between-folder, into-folder, reorder — all through one routing
/// instead of the SwiftUI `.onMove` per-island model that couldn't cross container
/// boundaries (spec §3.3 Phase B). Unit-tested in `DropRoutingTests`.
enum DropRouting {
    /// Index meaning "append / drop directly onto the container". `NSOutlineView`
    /// passes `NSOutlineViewDropOnItemIndex` (`-1`) for a drop-on; we normalise to
    /// this constant.
    static let append = -1

    /// Resolve a drag of one or more sidebar items onto a target.
    /// - Parameters:
    ///   - dragged: the items being dragged, in drag order.
    ///   - parent: the proposed drop parent (root, or a folder).
    ///   - index: child index within `parent`, or `append` for a drop-on.
    ///   - isKnown: whether a dragged item still exists in the model (guards stale
    ///     pasteboard payloads — a drag whose subject was removed mid-gesture).
    static func resolve(dragged: [SidebarDragItem],
                        onto parent: DropParent,
                        at index: Int,
                        isKnown: (SidebarDragItem) -> Bool) -> DropDecision {
        guard !dragged.isEmpty, dragged.allSatisfy(isKnown) else { return .invalid }

        let toFolder: UUID?
        switch parent {
        case .root:            toFolder = nil
        case .folder(let id):  toFolder = id
        }

        // One level only: `OutlineNode` models `.folder` → `.project`, full stop. A
        // folder dropped into a folder is refused here; the outline delegate retargets
        // the drop highlight to a root insertion line so the gesture still lands
        // somewhere sensible instead of showing a refuse cursor.
        if toFolder != nil, dragged.contains(where: \.isFolder) { return .invalid }

        return .move(DropPlan(items: dragged, toFolder: toFolder, atIndex: index))
    }

    /// Apply a drop to one scope's ordered id list: remove the dragged ids (they may
    /// or may not already live in this scope), then re-insert them as a contiguous run
    /// at `index`.
    ///
    /// `index` is in **pre-removal** coordinates, so it's adjusted down by however many
    /// removed items sat before it — the classic reorder off-by-N.
    ///
    /// Shared deliberately by the two consumers that must agree on the result: the
    /// model (`ProjectIndex.apply(_:)` renumbers `position` from it) and the outline's
    /// drop animation (which reads each row's final index from it). One implementation
    /// of the arithmetic, so they agree by construction rather than by two parallel
    /// copies that can drift.
    static func reordered(scope: [UUID], inserting: [UUID], at index: Int) -> [UUID] {
        let moved = Set(inserting)
        let survivors = scope.filter { !moved.contains($0) }
        guard index != append else { return survivors + inserting }

        let clamped = min(max(index, 0), scope.count)
        let removedBefore = scope.prefix(clamped).filter { moved.contains($0) }.count
        let insertAt = min(max(clamped - removedBefore, 0), survivors.count)
        return Array(survivors[..<insertAt]) + inserting + Array(survivors[insertAt...])
    }
}
