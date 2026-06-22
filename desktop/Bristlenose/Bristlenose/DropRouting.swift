import Foundation

/// The proposed drop parent in the outline.
enum DropParent: Equatable {
    case root
    case folder(UUID)
}

/// A resolved move of one project: which folder it lands in (`nil` = root) and
/// the target order index within that scope (`DropRouting.append` = end).
struct ProjectMove: Equatable {
    let projectID: UUID
    let toFolder: UUID?
    /// Computed + unit-tested, but **not yet consumed at runtime** — `acceptDrop`
    /// currently wires only `toFolder` (the structural fix). Within-scope position
    /// ordering by `toIndex` is the refinement TODO.
    let toIndex: Int
}

enum DropDecision: Equatable {
    case move([ProjectMove])
    case invalid
}

/// Pure resolution of a project drag-and-drop onto the outline into concrete
/// moves. This is the **unified insertion model** that fixes the "sidebar
/// apocalypse" structural gaps — out-of-folder, between-folder, into-folder,
/// reorder — all through one routing instead of the SwiftUI `.onMove` per-island
/// model that couldn't cross container boundaries (spec §3.3 Phase B). Unit-tested
/// exhaustively in `DropRoutingTests` (the spec §5 gate).
enum DropRouting {
    /// Index meaning "append / drop directly onto the container". `NSOutlineView`
    /// passes `NSOutlineViewDropOnItemIndex` (`-1`) for a drop-on; we normalise to
    /// this constant.
    static let append = -1

    /// Resolve a drag of one or more projects onto a target.
    /// - Parameters:
    ///   - draggedProjectIDs: the projects being dragged (drag order preserved).
    ///   - parent: the proposed drop parent (root, or a folder).
    ///   - index: child index within `parent`, or `append` for drop-on-folder.
    ///   - isProjectID: whether a dragged UUID is a known project (guards folder
    ///     drags / stray pasteboard items — those route elsewhere).
    static func resolve(draggedProjectIDs: [UUID],
                        onto parent: DropParent,
                        at index: Int,
                        isProjectID: (UUID) -> Bool) -> DropDecision {
        guard !draggedProjectIDs.isEmpty,
              draggedProjectIDs.allSatisfy(isProjectID) else { return .invalid }

        let targetFolder: UUID?
        switch parent {
        case .root: targetFolder = nil
        case .folder(let id): targetFolder = id
        }

        let moves = draggedProjectIDs.enumerated().map { offset, pid in
            ProjectMove(
                projectID: pid,
                toFolder: targetFolder,
                toIndex: index == append ? append : index + offset
            )
        }
        return .move(moves)
    }
}
