import SwiftUI

/// A single project row in the sidebar.
///
/// Shows the project name with a document icon. Supports inline rename triggered by:
/// - `isRenaming` binding (menu-driven, context menu, or [+] button)
///
/// Slow-double-click rename is parked — `simultaneousGesture(TapGesture())` and
/// `onTapGesture` both break List selection on macOS 26. See 100days.md.
///
/// Commit on Return, cancel on Escape.
struct ProjectRow: View {

    let project: Project
    @Binding var isRenaming: Bool
    let onRename: (String) -> Void
    let onShowInFinder: () -> Void
    let onDelete: () -> Void

    @EnvironmentObject var i18n: I18n
    @State private var editText: String = ""
    @FocusState private var isTextFieldFocused: Bool

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
