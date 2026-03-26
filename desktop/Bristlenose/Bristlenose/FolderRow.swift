import SwiftUI

/// A folder row in the sidebar — collapsible group header with inline rename.
///
/// Shows the folder name with a folder.fill icon. Supports inline rename triggered by:
/// - `isRenaming` binding (menu-driven or context menu)
///
/// Commit on Return, cancel on Escape. Same pattern as `ProjectRow.swift`.
struct FolderRow: View {

    let folder: Folder
    @Binding var isRenaming: Bool
    let onRename: (String) -> Void
    let onDelete: () -> Void

    @EnvironmentObject var i18n: I18n
    @State private var editText: String = ""
    @FocusState private var isTextFieldFocused: Bool

    var body: some View {
        Label {
            if isRenaming {
                TextField("Folder name", text: $editText)
                    .textFieldStyle(.plain)
                    .focused($isTextFieldFocused)
                    .onSubmit {
                        commitRename()
                    }
                    .onExitCommand {
                        cancelRename()
                    }
                    .onAppear {
                        editText = folder.name
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
                Text(folder.name)
            }
        } icon: {
            Image(systemName: "folder.fill")
        }
    }

    // MARK: - Rename

    private func commitRename() {
        let trimmed = editText.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty && trimmed != folder.name {
            onRename(trimmed)
        }
        isRenaming = false
    }

    private func cancelRename() {
        isRenaming = false
    }
}
