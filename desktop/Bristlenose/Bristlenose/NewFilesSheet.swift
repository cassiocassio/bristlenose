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
// **One mode left (22 Oct 2026).** The `.copy` mode ("Added N interviews to
// X") was the drag-onto acknowledgement for a loose-file study, which never
// auto-ran; that study shape was retired on 22 Oct 2026, and a drop onto a
// folder study runs, so the run is the acknowledgement. What remains is
// `.watcher` — the files on disk that are not in the analysis — opened from
// the SwiftUI sidebar row (`ContentView.openUnanalysedSheet`, the flag-off
// path). The AppKit sidebar shows the same list in `ProjectFilesPopover`,
// anchored to the row's ⓘ / ⚠ glyph (27 Aug 2026): a context menu shows
// verbs and *cannot show a list*, and a modal is the wrong price to pay for
// reading three filenames. So this sheet goes when the SwiftUI sidebar does.

/// Source that opened the sheet: the Phase 2 #14 Finder-side flow, with the
/// "These files aren't part of your analysis yet." framing.
enum NewFilesSheetSource: Equatable {
    case watcher(newFiles: [URL], missingFiles: [URL])
}

/// Sheet identity carries the project ID + the file source so the user
/// can dismiss without losing context.
struct NewFilesSheetState: Identifiable {
    let id = UUID()
    let projectID: UUID
    let projectName: String
    let source: NewFilesSheetSource

    /// Watcher-mode constructor (Phase 2 #14).
    init(projectID: UUID, projectName: String, newFiles: [URL], missingFiles: [URL]) {
        self.projectID = projectID
        self.projectName = projectName
        self.source = .watcher(newFiles: newFiles, missingFiles: missingFiles)
    }

    /// Files shown in the scroll body, in display order.
    var files: [URL] {
        switch source {
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
    /// act. `nil` when the project cannot run right now (already running,
    /// say), in which case the sheet
    /// stays informational rather than dimming a control it can never enable —
    /// the context-menu rule, applied to a sheet.
    var onAnalyse: (() -> Void)?
    @EnvironmentObject var i18n: I18n

    private var heading: String {
        switch state.source {
        case .watcher:
            return i18n.t("desktop.chrome.unanalysedSheetTitle",
                          ["project": state.projectName])
        }
    }

    private var footer: String? {
        switch state.source {
        case .watcher:
            return i18n.t("desktop.chrome.unanalysedSheetFooter")
        }
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
