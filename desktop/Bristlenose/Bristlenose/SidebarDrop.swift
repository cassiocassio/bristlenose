import Foundation
import CoreTransferable

/// Wrapper Transferable for sidebar folder-row drops. Accepts both internal
/// project drags (typed `ProjectDragID` payload) and Finder URL drops.
/// Single drop closure dispatches by case.
///
/// Apple's canonical pattern for accepting multiple Transferable types on
/// one view — stacking `.dropDestination(for: T.self)` modifiers is
/// unsupported and silently fails to wire the second closure on List rows
/// and DisclosureGroup hosts (FB12980427; WWDC22 "Meet Transferable"
/// Session 10062).
///
/// Internal drag uses `ProjectDragID` (custom UTType) instead of String so
/// it can't be auto-coerced to URL on the pasteboard — see
/// `ProjectDragID.swift` for the rationale.
enum SidebarDrop: Transferable {
    case project(UUID)
    case url(URL)

    static var transferRepresentation: some TransferRepresentation {
        ProxyRepresentation { (id: ProjectDragID) in SidebarDrop.project(id.id) }
        ProxyRepresentation { (url: URL) in SidebarDrop.url(url) }
    }
}
