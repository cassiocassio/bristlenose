import SwiftUI

/// A single project row in the sidebar.
///
/// Shows the project name with a document icon. Supports inline rename triggered by:
/// - `isRenaming` binding (menu-driven, context menu, or [+] button)
///
/// When a project is unavailable (volume ejected, folder moved), the row shows
/// grey text with a secondary line explaining why. Moved/deleted projects get
/// a `questionmark.folder` icon; volume-not-mounted projects keep `doc.text` greyed.
///
/// Slow-double-click rename is parked — `simultaneousGesture(TapGesture())` and
/// `onTapGesture` both break List selection on macOS 26. See 100days.md.
///
/// Commit on Return, cancel on Escape.
struct ProjectRow: View {

    let project: Project
    @Binding var isRenaming: Bool
    var isDropTarget: Bool = false
    let onRename: (String) -> Void
    let onShowInFinder: () -> Void
    let onDelete: () -> Void
    let onLocate: (() -> Void)?

    @EnvironmentObject var i18n: I18n
    @State private var editText: String = ""
    @FocusState private var isTextFieldFocused: Bool

    private var available: Bool { project.isAvailable }
    private var reason: Project.UnavailabilityReason? { project.unavailabilityReason }

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
                VStack(alignment: .leading, spacing: 1) {
                    if available {
                        Text(project.name)
                    } else {
                        Text(project.name)
                            .foregroundStyle(.secondary)
                    }

                    if !available {
                        switch reason {
                        case .volumeNotMounted(let hint):
                            Text(hint)
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                        case .movedOrDeleted:
                            Text(i18n.t("desktop.chrome.locate"))
                                .font(.caption)
                                // No explicit foregroundStyle — inherits primary (deselected)
                                // or white (selected) from the List selection environment.
                        case nil:
                            EmptyView()
                        }
                    }
                }
            }
        } icon: {
            if case .movedOrDeleted = reason {
                Image(systemName: "questionmark.folder")
                    .foregroundStyle(.secondary)
            } else {
                if available {
                    Image(systemName: project.icon ?? IconPickerPopover.defaultIcon)
                } else {
                    Image(systemName: project.icon ?? IconPickerPopover.defaultIcon)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(Color.accentColor, lineWidth: 2)
                .opacity(isDropTarget ? 1 : 0)
        )
    }

    // MARK: - Accessibility

    private var accessibilityLabel: String {
        var label = project.name
        if !available {
            switch reason {
            case .volumeNotMounted(let hint):
                label += ", \(i18n.t("desktop.chrome.projectUnavailable")), \(hint)"
            case .movedOrDeleted:
                label += ", \(i18n.t("desktop.chrome.projectMoved"))"
            case nil:
                break
            }
        }
        return label
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
