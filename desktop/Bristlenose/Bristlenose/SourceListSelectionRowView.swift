import AppKit

/// Forces the **unemphasized** source-list selection (grey ground + accent-tinted
/// content) in ALL focus states. The default `.sourceList` selection flips to a
/// vivid-blue fill / white text when the table is first responder + key; real
/// source lists (Finder/Photos) are focus-stable, so we pin `isEmphasized`.
///
/// Shared by BOTH source-list surfaces — the project sidebar
/// (`ProjectSidebarOutline`, where the active lens is kept genuinely selected so
/// the TABLE draws its capsule) and the sessions popover
/// (`SessionsPopoverList`). The capsule is drawn by the table's internal
/// source-list rendering — exact colour / margin / radius, all of which a
/// hand-placed view cannot match (the source-list selection colour is internal
/// to the table and matches no public UI-element-colour token — verified by
/// sampling all of them). Sharing one row view is what guarantees the two
/// surfaces can never diverge.
///
/// The `isEmphasized` pin is the focus-stability attempt; it's largely inert on
/// the current macOS draw path (both surfaces show the native two-state the
/// user accepted as matching Mail), kept as the single shared emphasis
/// behaviour.
final class SourceListSelectionRowView: NSTableRowView {
    override var isEmphasized: Bool {
        get { false }
        set { }
    }
}
