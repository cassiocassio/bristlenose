import Foundation
import SwiftUI

/// Tracks projects that have been removed from the sidebar and can still be
/// restored via Undo (toast button or Cmd+Z) before the auto-dismiss window
/// elapses.
///
/// HANDOFF §5: removal skips the confirm dialog because undo is available.
/// While a pending removal exists, the Edit > Undo command and Cmd+Z route to
/// `undoLastRemoval()` instead of the web-side undo, with the menu label
/// changing to "Undo Remove `<name>`" (single) or "Undo Remove `<N>` Projects"
/// (batch). After the window elapses (default 8s), the projects are gone for
/// good (the on-disk folder is untouched — only the sidebar entries).
///
/// **Batch semantics.** A single `Pending` may carry one or many entries. The
/// multi-row case (Cmd+Backspace with N rows selected) creates ONE Pending
/// containing all N — undo restores all of them as a single transaction, and
/// the toast reads "N projects removed". If a second batch arrives while a
/// first is still pending, the first commits silently — only the most recent
/// batch is undoable. Two views with cardinality is plenty; a multi-deep queue
/// is a different feature.
///
/// **Cmd+Z routing.** Wired via the Edit menu's `keyboardShortcut("z")` in
/// `MenuCommands.UndoRedoMenuContent`. Not via `NSUndoManager` — the SwiftUI
/// menu interception is sufficient for the sidebar scope and avoids braiding
/// removal-undo with whatever responder chain happens to hold focus.
@MainActor
final class UndoableRemovalStore: ObservableObject {

    /// One entry inside a pending removal batch. Captures everything restore
    /// needs: the full `Project` snapshot (including `bookmarkData` for
    /// cantFind projects), folder membership, and position.
    struct Entry: Equatable {
        let project: Project
        let folderId: UUID?
        let position: Int

        static func == (lhs: Entry, rhs: Entry) -> Bool {
            lhs.project.id == rhs.project.id
        }
    }

    /// A pending batch awaiting either undo or auto-commit.
    struct Pending: Identifiable, Equatable {
        let id = UUID()
        let entries: [Entry]
        /// Sidebar selection at the moment of removal, so undo can restore it
        /// (acceptance criterion 1: "exact same row + folder + selection state").
        let priorSelection: Set<SidebarSelection>
        let removedAt: Date

        var count: Int { entries.count }

        /// Display name for the toast / Edit menu label when count == 1.
        /// Returns nil for batches > 1 (callers use `count` instead).
        var soleName: String? { count == 1 ? entries.first?.project.name : nil }

        static func == (lhs: Pending, rhs: Pending) -> Bool { lhs.id == rhs.id }
    }

    @Published private(set) var pending: Pending?

    /// Duration the toast stays on-screen and the undo window is open.
    /// Plan §5 picks 8s as a starting point; parameterised in case cohort
    /// feedback later says 8s feels rushed.
    let undoWindow: TimeInterval

    private var dismissTask: Task<Void, Never>?
    private weak var projectIndex: ProjectIndex?

    /// Closure the store invokes when an undo restores a batch. The caller
    /// (ContentView) applies the prior selection set. Optional — wired via
    /// `setOnUndo` so the store doesn't reach into SwiftUI state directly.
    private var onUndo: ((Set<SidebarSelection>) -> Void)?

    init(undoWindow: TimeInterval = 8) {
        self.undoWindow = undoWindow
    }

    func setProjectIndex(_ index: ProjectIndex) {
        self.projectIndex = index
    }

    /// Register the selection-restore callback. ContentView calls this once
    /// in `.onAppear` so undo can re-apply the captured `priorSelection`.
    func setOnUndo(_ handler: @escaping (Set<SidebarSelection>) -> Void) {
        self.onUndo = handler
    }

    /// True while an undo is available.
    var hasPending: Bool { pending != nil }

    /// Display name for the pending project when batch size is 1. Used by
    /// the Edit menu's "Undo Remove `<name>`" label.
    var pendingName: String? { pending?.soleName }

    /// Number of pending entries (0 when nothing is pending).
    var pendingCount: Int { pending?.count ?? 0 }

    /// Snapshot one or more projects, remove them from the index, and start
    /// the undo window. The whole batch is a single undoable transaction.
    /// If another batch is already pending, it commits silently first — the
    /// caller has no further chance to undo it.
    ///
    /// `priorSelection` is the sidebar selection at the moment of removal —
    /// restored on undo. Pass `[]` if the caller doesn't track it.
    func removeFromSidebar(_ projects: [Project], priorSelection: Set<SidebarSelection> = []) {
        guard let index = projectIndex, !projects.isEmpty else { return }
        commitIfPending()

        let entries = projects.map { project in
            Entry(project: project, folderId: project.folderId, position: project.position)
        }
        let batch = Pending(
            entries: entries,
            priorSelection: priorSelection,
            removedAt: Date()
        )
        pending = batch
        for project in projects {
            index.removeProject(id: project.id)
        }
        scheduleAutoDismiss()
    }

    /// Convenience overload for the single-project case (context-menu single
    /// row, ProjectRow trailing affordance).
    func removeFromSidebar(_ project: Project, priorSelection: Set<SidebarSelection> = []) {
        removeFromSidebar([project], priorSelection: priorSelection)
    }

    /// Restore the pending batch. No-op if nothing is pending.
    /// Re-applies the captured selection via the registered `onUndo` callback.
    func undoLastRemoval() {
        guard let batch = pending, let index = projectIndex else { return }
        dismissTask?.cancel()
        for entry in batch.entries {
            index.restoreProject(entry.project,
                                 folderId: entry.folderId,
                                 position: entry.position)
        }
        pending = nil
        if !batch.priorSelection.isEmpty {
            onUndo?(batch.priorSelection)
        }
    }

    /// Commit the pending removal (the user accepted, time ran out, or a new
    /// batch arrived). After this the projects are gone for good.
    func commitIfPending() {
        guard pending != nil else { return }
        dismissTask?.cancel()
        pending = nil
    }

    private func scheduleAutoDismiss() {
        dismissTask?.cancel()
        dismissTask = Task { [weak self] in
            guard let self else { return }
            try? await Task.sleep(for: .seconds(self.undoWindow))
            guard !Task.isCancelled else { return }
            await MainActor.run { self.commitIfPending() }
        }
    }
}

// MARK: - Notification names

extension Notification.Name {
    /// Posted by Project > Remove from Sidebar to remove the selected project(s)
    /// via the UndoableRemovalStore (with toast + undo window).
    static let removeSelectedProjectsFromSidebar =
        Notification.Name("bristlenoseRemoveSelectedProjectsFromSidebar")

    /// Posted by `UndoableRemovalStore.undoLastRemoval()` so ContentView can
    /// re-apply the captured selection set. `userInfo["selection"]` is a
    /// `Set<SidebarSelection>`.
    static let undoableRemovalRestoredSelection =
        Notification.Name("bristlenoseUndoableRemovalRestoredSelection")
}
