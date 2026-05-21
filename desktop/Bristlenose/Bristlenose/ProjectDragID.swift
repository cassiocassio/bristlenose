import Foundation
import UniformTypeIdentifiers
import CoreTransferable

/// Custom UTType for internal project drag — gives the drag payload a
/// strict UTI that `.dropDestination(for: URL.self)` cannot satisfy.
///
/// Without this, `.draggable(project.id.uuidString)` exposes the drag as a
/// String on the pasteboard, which SwiftUI auto-coerces to URL — so every
/// `.dropDestination(for: URL.self)` in the sidebar (project rows, the
/// List-level Finder drop) lights up and accepts the internal drag, then
/// routes it through the Finder-import path. The original plan considered
/// this typed payload and split it as a follow-up; QA on `sidebar-drop-
/// folder-row` surfaced the symptom (project rows highlight on internal
/// drag; drop triggers re-scan instead of move), so it's bundled here.
extension UTType {
    /// Explicitly anchored to `.data` so this UTI doesn't transitively
    /// conform to URL-adjacent types — `.dropDestination(for: URL.self)`
    /// in the sidebar (project rows, List-level Finder drop) must NOT
    /// match an internal project drag, or every row lights up as a drop
    /// target during the drag.
    static let bristlenoseProjectDragID = UTType(
        exportedAs: "app.bristlenose.project-id",
        conformingTo: .data
    )
}

struct ProjectDragID: Codable, Hashable, Transferable {
    let id: UUID

    static var transferRepresentation: some TransferRepresentation {
        CodableRepresentation(contentType: .bristlenoseProjectDragID)
    }
}
