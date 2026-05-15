import SwiftUI

/// Stub sheet shown after a drag-onto-project copy completes. Plan §11:
/// "Deliberate action → richer feedback." Cohort 1 sees the basename list
/// only; #14 will replace this with a watcher-sourced sheet that includes
/// suggested-action affordances (Analyse Now, Hide, Ignore Pattern, …).
///
/// Sheet identity carries the project ID + the copied paths so the user
/// can dismiss without losing context.
struct NewFilesSheetState: Identifiable {
    let id = UUID()
    let projectID: UUID
    let projectName: String
    /// Destination URLs that were just copied (basenames are shown).
    let files: [URL]
}

struct NewFilesSheet: View {
    let state: NewFilesSheetState
    let onDismiss: () -> Void
    @EnvironmentObject var i18n: I18n

    private var heading: String {
        // Reuse the existing "Added N interviews to X" key.
        String(
            format: i18n.t("desktop.chrome.addedInterviews"),
            state.files.count, state.projectName
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(heading)
                .font(.headline)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(state.files, id: \.self) { url in
                        HStack(spacing: 8) {
                            Image(systemName: "doc")
                                .foregroundStyle(.secondary)
                            Text(url.lastPathComponent)
                                .lineLimit(1)
                                .truncationMode(.middle)
                            Spacer()
                        }
                        .font(.callout)
                    }
                }
            }
            .frame(maxHeight: 280)
            HStack {
                Spacer()
                Button(i18n.t("common.buttons.close"), action: onDismiss)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(width: 420)
    }
}
