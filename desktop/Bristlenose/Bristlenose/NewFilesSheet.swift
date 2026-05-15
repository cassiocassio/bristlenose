import Foundation
import SwiftUI

// MARK: PII — UI-only, never log
// Filenames rendered here may identify participants. Don't write them to
// os_log, pipeline-events.jsonl, or any persisted channel.

/// Source that opened the sheet. `.copy` mirrors the original Phase 2 #11
/// drag-onto flow ("Added N interviews to X"); `.watcher` is the Phase 2 #14
/// Finder-side flow with the longer "These files aren't part of your
/// analysis yet." framing.
enum NewFilesSheetSource: Equatable {
    case copy(files: [URL])
    case watcher(newFiles: [URL], missingFiles: [URL])
}

/// Sheet identity carries the project ID + the file source so the user
/// can dismiss without losing context.
struct NewFilesSheetState: Identifiable {
    let id = UUID()
    let projectID: UUID
    let projectName: String
    let source: NewFilesSheetSource

    /// Convenience constructor preserving the pre-#14 call sites that pass
    /// just the copied URL list (drag-onto completion).
    init(projectID: UUID, projectName: String, files: [URL]) {
        self.projectID = projectID
        self.projectName = projectName
        self.source = .copy(files: files)
    }

    /// Watcher-mode constructor (Phase 2 #14).
    init(projectID: UUID, projectName: String, newFiles: [URL], missingFiles: [URL]) {
        self.projectID = projectID
        self.projectName = projectName
        self.source = .watcher(newFiles: newFiles, missingFiles: missingFiles)
    }

    /// Files shown in the scroll body, in display order.
    var files: [URL] {
        switch source {
        case .copy(let files):
            return files
        case .watcher(let new, let missing):
            return new + missing
        }
    }
}

struct NewFilesSheet: View {
    let state: NewFilesSheetState
    let onDismiss: () -> Void
    @EnvironmentObject var i18n: I18n

    private var heading: String {
        switch state.source {
        case .copy(let files):
            return String(
                format: i18n.t("desktop.chrome.addedInterviews"),
                files.count, state.projectName
            )
        case .watcher:
            return i18n.t("desktop.chrome.unanalysedSheetTitle",
                          ["project": state.projectName])
        }
    }

    private var footer: String? {
        if case .watcher = state.source {
            return i18n.t("desktop.chrome.unanalysedSheetFooter")
        }
        return nil
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
                            if let size = formattedSize(of: url) {
                                Text(size)
                                    .font(.caption)
                                    .foregroundStyle(.tertiary)
                            }
                        }
                        .font(.callout)
                    }
                }
            }
            .frame(minHeight: 120, idealHeight: 280, maxHeight: 500)
            if let footer {
                Text(footer)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            HStack {
                Spacer()
                Button(i18n.t("common.buttons.close"), action: onDismiss)
                    // .cancelAction — Escape dismisses; Mac convention is
                    // that a Close button is the dismissive action, not the
                    // affirmative (Return) one.
                    .keyboardShortcut(.cancelAction)
            }
        }
        .padding(20)
        .frame(width: 420)
    }

    private func formattedSize(of url: URL) -> String? {
        let values = try? url.resourceValues(forKeys: [.fileSizeKey])
        guard let bytes = values?.fileSize else { return nil }
        return ByteCountFormatter.string(
            fromByteCount: Int64(bytes), countStyle: .file
        )
    }
}
