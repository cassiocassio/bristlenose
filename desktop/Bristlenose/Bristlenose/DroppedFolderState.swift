import Foundation

/// Classifies a single folder dropped onto the sidebar by its relationship to
/// the project index, so the drop handler can route it to the right action.
///
/// The distinction that matters — and that the V1 taxonomy in
/// `docs/design-sidebar-drop-behaviour.md` originally collapsed — is between a
/// folder being *tracked* (a path entry exists in `projects.json`) and being
/// *analysed* (it carries a `bristlenose-output/…manifest` marker, i.e.
/// `LocateFlow.folderLooksAnalysed` is true). They usually coincide, but not
/// when a run was interrupted before output was written, or a project was
/// added and never run. Such a "tracked but unanalysed" folder is
/// substantively a source folder: drag-to-analyse must still fire for it,
/// otherwise re-dropping it is a permanent dead-end (the duplicate-drop alert
/// has no button that starts analysis).
enum DroppedFolderState: Equatable {
    /// No project tracks this path yet. Downstream creates one, then analyses
    /// or adopts per the folder's own analysed-ness.
    case untracked
    /// Tracked, but carries no analysis output marker. Drag-to-analyse fires.
    case trackedUnanalysed
    /// Tracked and analysed. Drop means "analyse these interviews unless I
    /// already did — then show me the analysis," so a re-drop here is purely a
    /// navigation gesture ("show me this one"): select + flash, never re-run.
    case trackedAnalysed

    /// Pure decision from two facts: whether the path is already in the index,
    /// and whether the folder looks analysed (`LocateFlow.folderLooksAnalysed`).
    static func classify(isTracked: Bool, folderLooksAnalysed: Bool) -> DroppedFolderState {
        guard isTracked else { return .untracked }
        return folderLooksAnalysed ? .trackedAnalysed : .trackedUnanalysed
    }
}
