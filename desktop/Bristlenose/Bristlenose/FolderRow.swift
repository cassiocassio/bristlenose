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
        // Stretch to full row width with a hittable shape so drag-and-drop
        // targets the whole row, not just the icon+text Label extent. Without
        // this, drops over the empty space right of the folder name fall
        // through to the DisclosureGroup (no drop handler) and spring back.
        .frame(maxWidth: .infinity, alignment: .leading)
        // Extend hit region vertically into the SwiftUI List inter-row gap.
        // SidebarDropDelegate hit-tests via the row's rendered frame, so
        // padding here (before contentShape) widens the captured rectangle
        // — the List-level URL dropDestination becomes a true fallback for
        // the empty area below the last row, instead of stealing drops that
        // landed in the gap above a folder the user was aiming at.
        .padding(.vertical, 2)
        .contentShape(Rectangle())
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
