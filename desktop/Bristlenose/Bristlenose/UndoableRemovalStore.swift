import Foundation
import SwiftUI

/// Tracks projects removed from the sidebar and still restorable via Undo.
///
/// HANDOFF §5: removal skips the confirm dialog because undo is available.
/// While a pending removal exists, the Edit > Undo command and Cmd+Z route to
/// `undoLastRemoval()` instead of the web-side undo, with the menu label
/// changing to "Undo Remove `<name>`" (single) or "Undo Remove `<N>` Projects"
/// (batch). The on-disk folder is untouched throughout — only the sidebar
/// entries go.
///
/// **There is no clock, as of 19 Aug 2026.** The undo used to expire after 8
/// seconds — and because Cmd+Z routes here, *the keyboard shortcut expired
/// too*, not just the toast that advertised it. That is a toast-shaped
/// constraint leaking into the model: a Mac user's one assumption about undo is
/// that it waits for them. Remove is already non-destructive, so the fuse
/// bought nothing and cost the guarantee. A pending removal now survives until
/// the next one supersedes it, which is what an undo stack does.
///
/// The toast that carried the Undo button is gone with it — see
/// `docs/design-analysis-lifecycle.md` §4.2 for why floating notifications are
/// not the feedback surface here. Edit ▸ Undo names the action, permanently,
/// where every Mac user already looks.
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
/// `MenuCommands.UndoRedoMenuContent`. Deliberately **not** `NSUndoManager`:
/// that would braid removal-undo with whatever responder chain holds focus,
/// and the report's WKWebView owns text-editing undo. `UndoRedoMenuContent`
/// already gates the whole Edit ▸ Undo item behind `!isEditing` for exactly
/// that reason. With the fuse gone, this route delivers what the system
/// manager would — an undo that names its action and waits — without the
/// braiding.
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

    private weak var projectIndex: ProjectIndex?

    /// Closure the store invokes when an undo restores a batch. The caller
    /// (ContentView) applies the prior selection set. Optional — wired via
    /// `setOnUndo` so the store doesn't reach into SwiftUI state directly.
    private var onUndo: ((Set<SidebarSelection>) -> Void)?

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

    /// Commit the pending removal, because a newer one is superseding it.
    /// After this the earlier batch is gone for good.
    ///
    /// Nothing else calls this — in particular no timer does. One level of
    /// undo, superseded by the next removal, is the whole model.
    func commitIfPending() {
        guard pending != nil else { return }
        pending = nil
    }
}

// MARK: - Notification names

extension Notification.Name {
    /// Posted by `UndoableRemovalStore.undoLastRemoval()` so ContentView can
    /// re-apply the captured selection set. `userInfo["selection"]` is a
    /// `Set<SidebarSelection>`.
    /// Posted synchronously **before** projects leave the model, so the sidebar
    /// can puff their rows while the rects still exist.
    /// `userInfo["ids"]` is a `[UUID]`.
    static let bristlenoseWillRemoveProjects =
        Notification.Name("bristlenoseWillRemoveProjects")

    static let undoableRemovalRestoredSelection =
        Notification.Name("bristlenoseUndoableRemovalRestoredSelection")
}
