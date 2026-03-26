import SwiftUI

/// A single project row in the sidebar.
///
/// Shows the project name with a document icon. Supports inline rename triggered by:
/// - `isRenaming` binding (menu-driven or [+] button)
/// - Slow double-click (first click selects, second click 0.3–1.0s later activates rename)
///
/// Commit on Return, cancel on Escape.
///
/// Uses `simultaneousGesture` for slow-double-click so the List's built-in
/// selection still fires on every click — `onTapGesture` would swallow it.
struct ProjectRow: View {

    let project: Project
    @Binding var isRenaming: Bool
    let onRename: (String) -> Void

    @State private var editText: String = ""
    @FocusState private var isTextFieldFocused: Bool

    /// Track the last click time for slow double-click detection.
    @State private var lastClickTime: Date?

    var body: some View {
        Label {
            if isRenaming {
                TextField("Project name", text: $editText)
                    .textFieldStyle(.plain)
                    .focused($isTextFieldFocused)
                    .onSubmit {
                        commitRename()
                    }
                    .onExitCommand {
                        cancelRename()
                    }
                    .onAppear {
                        editText = project.name
                        // Delay focus slightly so the TextField is fully mounted.
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                            isTextFieldFocused = true
                        }
                    }
                    // Commit when focus leaves (e.g. clicking elsewhere).
                    .onChange(of: isTextFieldFocused) { _, focused in
                        if !focused && isRenaming {
                            commitRename()
                        }
                    }
            } else {
                Text(project.name)
            }
        } icon: {
            Image(systemName: "doc.text")
        }
        // simultaneousGesture lets the List selection fire AND tracks
        // slow-double-click timing for inline rename.
        .simultaneousGesture(
            TapGesture().onEnded {
                guard !isRenaming else { return }
                handleTap()
            }
        )
    }

    // MARK: - Slow double-click

    /// Detect a slow double-click: a second tap 0.3–1.0s after the first.
    /// The first tap selects the row (handled by the List selection binding).
    /// The second tap triggers inline rename.
    private func handleTap() {
        let now = Date()
        if let last = lastClickTime {
            let interval = now.timeIntervalSince(last)
            if interval >= 0.3 && interval <= 1.0 {
                // Slow double-click — activate rename.
                lastClickTime = nil
                isRenaming = true
                return
            }
        }
        lastClickTime = now
    }

    // MARK: - Rename

    private func commitRename() {
        let trimmed = editText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty && trimmed != project.name {
            onRename(trimmed)
        }
        isRenaming = false
    }

    private func cancelRename() {
        isRenaming = false
    }
}
