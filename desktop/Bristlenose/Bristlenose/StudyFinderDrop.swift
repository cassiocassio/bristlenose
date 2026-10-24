import Foundation

/// What a Finder drag over one study's sidebar row does: the answer both
/// sidebars give (R47).
///
/// The AppKit outline's `validateDrop` refuses two drags: one onto a study that
/// has failed or is unreachable, or whose folder `run` refuses by name (a
/// running or queued one takes files since decision #100;
/// `SidebarOutlineController.acceptsFinderDrop(state:folder:)`), and one carrying
/// nothing a study can ingest (`acceptsFinderFiles`, R48). AppKit then draws no
/// highlight and springs the drag back.
///
/// The SwiftUI row can't refuse that way. `.dropDestination(for:isEnabled:)`
/// arrives with macOS 26 and the floor is 15. Nor can the row drop its
/// destination for a busy study, because the List-level `.dropDestination`
/// behind it would take the drop and make a new study. So the row asks the
/// rules itself: before it lights (`highlight`, which sees the state but not
/// the files), and when the files are let go (`takesDrop`, whose `false`
/// springs them back). What it can't change is the pointer, which stays "+"
/// over a refused row on this path.
enum StudyFinderDrop {
    /// Whether a study in `state` takes a drop of `urls`. The SwiftUI drop
    /// closures call this and nothing else.
    @MainActor
    static func takesDrop(state: PipelineState?, folder: String, urls: [URL]) -> Bool {
        accepts(state: state, folder: folder) && SidebarOutlineController.acceptsFinderFiles(urls)
    }

    /// Whether the study takes files at all, from its state and its folder.
    static func accepts(state: PipelineState?, folder: String) -> Bool {
        SidebarOutlineController.acceptsFinderDrop(state: state, folder: folder)
    }

    /// Whether `run` refuses the study's folder by name: the home folder or a
    /// system root (`ScanSelection.refusal`, the port of `_refuse_reason`).
    /// An empty path (a study with no folder yet) is not refused. Two
    /// `realpath` calls, cheap enough for a drag's repeated validation.
    nonisolated static func folderIsRefused(_ folder: String) -> Bool {
        !folder.isEmpty && ScanSelection.refusal(for: URL(fileURLWithPath: folder)) != nil
    }

    /// The SwiftUI row's `isTargeted` reducer: which study is lit after the
    /// drag enters (`isOver`) or leaves this row. `current` is the study lit
    /// now, which may be another row's.
    ///
    /// SwiftUI asks only on enter and leave, so a study whose state changes
    /// while the pointer rests on it keeps the answer it got on entry until the
    /// pointer moves off. The drop itself is decided afresh by `takesDrop`.
    static func highlight(isOver: Bool, study: UUID, current: UUID?,
                          state: PipelineState?, folder: String) -> UUID? {
        guard isOver, accepts(state: state, folder: folder) else {
            return current == study ? nil : current
        }
        return study
    }
}
