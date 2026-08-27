import Foundation
import SwiftUI

// MARK: PII — UI-only, never log
// Filenames rendered here may identify participants. Don't write them to
// os_log, pipeline-events.jsonl, or any persisted channel.

// MARK: TF scaffolding — migrate to React SPA project dashboard
// This sheet is a *data view* (a list of project source files) that sits in
// native chrome. Native chrome should own navigation / status / system
// integration; data views belong in the React SPA's project dashboard.
// Retire when EITHER (a) incremental processing lands (no "+N unanalysed"
// exception state to surface), OR (b) the SPA dashboard grows an
// "unanalysed files" panel that subsumes this. Sidebar count + delta in
// `ProjectRow` stays — that's chrome and belongs in native.
//
// **Half of it is already gone (27 Aug 2026).** The `.watcher` mode — the
// "pulse-to-pill-to-sheet" path this header used to describe as the cohort's
// first visible proof of incremental detection — is now `ProjectFilesPopover`,
// anchored to the row's ⓘ / ⚠ glyph. The argument was not the one above: a
// context menu shows verbs and *cannot show a list*, so the file list has no
// other home, and a modal is the wrong price to pay for reading three
// filenames. Only `.copy` still has a live route, and it is a completion
// acknowledgement that probably wants `ToastStore` rather than a sheet at all.
// So this file is one mode from deletable, and neither (a) nor (b) has to
// happen first.

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
    /// The act the sheet is describing, when it is available.
    ///
    /// The sheet used to end in **Close** and nothing else — it reported files
    /// that were not in the analysis and offered no way to put them there,
    /// which is a dead end at exactly the moment the researcher has decided to
    /// act. `nil` when the project cannot run right now (already running, or
    /// a file-subset project the CLI cannot scope), in which case the sheet
    /// stays informational rather than dimming a control it can never enable —
    /// the context-menu rule, applied to a sheet.
    var onAnalyse: (() -> Void)?
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
                if let onAnalyse {
                    // Same key as the context menu and the empty-project pane,
                    // so all three say one word. Trailing and default: Return
                    // does the thing the sheet exists to offer, and the run is
                    // stoppable and leaves curation intact, so it is not the
                    // kind of act that wants a confirmation in front of it.
                    Button(i18n.t("desktop.menu.project.analyse")) {
                        onAnalyse()
                        onDismiss()
                    }
                    .keyboardShortcut(.defaultAction)
                }
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
