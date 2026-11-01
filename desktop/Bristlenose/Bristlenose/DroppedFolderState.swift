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

/// A single folder dropped on the empty "+ New Project" placeholder: it becomes
/// the placeholder's folder, unless another row already holds it. Then the drop
/// means what it means on any other door (`processDroppedURLs`): that row is the
/// one to show, and to analyse if it never was. Adopting it anyway made a second
/// row on one folder and started a second run on one database (N157).
///
/// Pure over the index, so it has a test without a window or a drop.
enum PlaceholderDrop: Equatable {
    /// No other row holds the folder: the placeholder takes it.
    case adopt
    /// This row already holds it, under any spelling (a path, a symlink, another
    /// mount point's name for it).
    case existing(UUID)

    @MainActor
    static func resolve(folder: URL, placeholder: UUID, in index: ProjectIndex) -> PlaceholderDrop {
        if let holder = index.otherProject(holding: folder, excluding: placeholder) {
            return .existing(holder.id)
        }
        return .adopt
    }
}

/// Whether a row still carries the name Bristlenose gave a new project, so a drop
/// that adopts an analysed study may name the row for its folder, and a name the
/// researcher typed is left alone (ruling 10, 31 Oct 2026: the row's name is
/// Bristlenose's own thing and never follows the folder). The default is the
/// localised "New Project", with the " 2", " 3" suffix `ProjectIndex.uniqueName`
/// adds when one already exists. A name that no longer matches the current language
/// reads as typed, which is the safe direction.
enum PlaceholderName {
    static func isDefault(_ name: String, base: String) -> Bool {
        if name == base { return true }
        guard name.hasPrefix(base + " "),
              let number = Int(name.dropFirst(base.count + 1))
        else { return false }
        return number >= 2
    }
}
