import AppKit
import SwiftUI

/// Toast that surfaces a pending "Remove from Sidebar" with an Undo affordance.
///
/// Shares the `ToastSurface` molecule with the informational `ToastOverlay`,
/// so the two visual surfaces stay in lockstep. The undoable variant has an
/// action button and a longer (8s) timeline. Posts a VoiceOver announcement
/// on appear (WCAG 4.1.3) so non-sighted users learn the remove happened plus
/// the Cmd+Z hint.
///
/// Attach via `.overlay { RemoveToast() }` on the root view.
struct RemoveToast: View {
    @EnvironmentObject var store: UndoableRemovalStore
    @EnvironmentObject var i18n: I18n
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack {
            Spacer()
            if let pending = store.pending {
                ToastSurface(
                    message: message(for: pending),
                    action: ToastSurface.Action(
                        label: i18n.t("desktop.toast.undo"),
                        handler: { store.undoLastRemoval() }
                    ),
                    tooltip: tooltipText(for: pending)
                )
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .padding(.bottom, 16)
            }
        }
        .animation(
            reduceMotion ? nil : .easeInOut(duration: 0.25),
            value: store.pending
        )
        .allowsHitTesting(store.pending != nil)
        .onChange(of: store.pending) { _, newValue in
            guard let pending = newValue else { return }
            postAccessibilityAnnouncement(for: pending)
        }
    }

    /// Toast copy. "Project removed." for single; "N projects removed." for
    /// batches. Apple Mail/Notes pattern — the visible text disambiguates by
    /// cardinality; the tooltip + name carries the per-row detail.
    private func message(for pending: UndoableRemovalStore.Pending) -> String {
        if pending.count > 1 {
            return String(format: i18n.t("desktop.toast.removedBatch"), pending.count)
        }
        return i18n.t("desktop.toast.removed")
    }

    /// Hover tooltip: project name + tildified path, so the user can verify
    /// which row was removed before clicking Undo. For batches, lists the
    /// names; tildified paths would be too noisy.
    private func tooltipText(for pending: UndoableRemovalStore.Pending) -> String {
        if pending.count == 1, let entry = pending.entries.first {
            return tildified(name: entry.project.name, path: entry.project.lastSeenPath)
        }
        // Batch — list names, newline-separated. Tooltip wraps cleanly.
        return pending.entries.map { $0.project.name }.joined(separator: "\n")
    }

    private func tildified(name: String, path rawPath: String) -> String {
        let path = rawPath.isEmpty ? "" : rawPath
        guard !path.isEmpty else { return name }
        let home = NSHomeDirectory()
        let display = path.hasPrefix(home) ? "~" + path.dropFirst(home.count) : path
        return "\(name)\n\(display)"
    }

    /// Post a VoiceOver announcement so non-sighted users learn the remove
    /// happened plus how to undo it. NSAccessibility.post is the macOS path
    /// (UIAccessibility.post is iOS-only). Priority `.high` jumps the queue
    /// because the 8s window doesn't wait for the regular speech buffer.
    private func postAccessibilityAnnouncement(for pending: UndoableRemovalStore.Pending) {
        let body: String
        if pending.count > 1 {
            body = String(
                format: i18n.t("desktop.toast.removedBatchAnnouncement"),
                pending.count
            )
        } else {
            body = String(
                format: i18n.t("desktop.toast.removedAnnouncement"),
                pending.soleName ?? ""
            )
        }
        guard let window = NSApp.mainWindow else { return }
        NSAccessibility.post(
            element: window,
            notification: .announcementRequested,
            userInfo: [
                .announcement: body,
                .priority: NSAccessibilityPriorityLevel.high.rawValue,
            ]
        )
    }
}
