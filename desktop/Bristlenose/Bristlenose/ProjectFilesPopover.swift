import AppKit
import SwiftUI

/// The row's detail surface for **data drift** — the folder and the analysis
/// disagree, and this enumerates how.
///
/// Sibling of `ProjectDiagnosticPopover`, and deliberately the same shape: the
/// sidebar row earns a glance, the popover holds the detail behind it. It
/// replaces `NewFilesSheet`'s watcher mode, which was a modal.
///
/// **Why a popover and not the sheet it replaces.** Three of the project's own
/// artefacts had already called the sheet wrong — its own header ("TF
/// scaffolding … data views belong in the React SPA"),
/// `docs/design-cloud-import.md` ("the codebase's worked example of a data view
/// wrongly living in native chrome"), and `incremental-analysis-flows.html` §7
/// ("modal … rejected as friction the user doesn't need"). The operative reason
/// is simpler than any of them: a **context menu shows verbs and cannot show a
/// list**, so this content has no other home, and a modal is the wrong price to
/// pay for reading four filenames.
///
/// **The scope rule this establishes** (settled 27 Aug 2026, superseding
/// `design-analysis-lifecycle.md`'s "the popover is reserved for failure
/// diagnostics" — that line described where the popover had got to, not where it
/// may go): the popover is the row's non-modal detail surface — *attention plus
/// detail that has no other home*. It may act on **the thing it is showing** and
/// nothing else. General project verbs (Rename, Move To, Re-analyse…) stay in
/// right-click, which is what keeps this from becoming a second menu.
///
/// PII: filenames may identify participants. Rendered only — never logged, never
/// written to `pipeline-events.jsonl`, never into an accessibility string that
/// isn't already on screen. Same rule `NewFilesSheet` carried.
struct ProjectFilesPopover: View {
    /// Files present in the folder that the last analysis never read.
    let newFiles: [URL]
    /// Files the analysis read that are no longer on disk.
    let missingFiles: [URL]
    /// Starts the run **and** closes the popover — the caller owns both.
    ///
    /// `nil` when a run can't start right now (already running, or a file-subset
    /// project the CLI can't scope). Absent rather than dimmed — the
    /// context-menu rule, applied to a popover.
    ///
    /// Closing is the caller's job because **`@Environment(\.dismiss)` is inert
    /// here**: this view is hosted in an AppKit `NSPopover` via
    /// `NSHostingController`, so there is no SwiftUI presentation for `dismiss`
    /// to act on — the controller holds the popover and must close it.
    /// `IconPickerPopover` already works this way. `ProjectDiagnosticPopover`
    /// does not: its `showLog()` calls `dismiss()`, which does nothing, masked
    /// only by `.transient` closing on the focus change when Console opens.
    /// Noted, not fixed here — different surface, and unverified.
    let onAnalyse: (() -> Void)?
    @EnvironmentObject var i18n: I18n

    /// Matches `ProjectDiagnosticPopover` so the two read as one surface.
    static let width: CGFloat = 360
    static let ceiling: CGFloat = 320
    private static let inset: CGFloat = 16

    /// Height follows content, capped at `ceiling`. **The greedy candidate goes
    /// last** — a `ScrollView` "fits" every proposal, so leading with it kills
    /// the ladder and silently rebuilds the fixed box. Same trap, same fix, same
    /// reasoning as `ProjectDiagnosticPopover`; see it for the long version.
    var body: some View {
        ViewThatFits(in: .vertical) {
            shell { content }
            shell { ScrollView { content } }
        }
        .frame(width: Self.width)
        .frame(maxHeight: Self.ceiling)
    }

    private func shell(@ViewBuilder _ inner: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            header
            inner()
        }
        .padding(Self.inset)
    }

    /// Title + the single act, as a small bordered button.
    ///
    /// Deliberately **not** `.borderedProminent`. Analyse is the point of opening
    /// this, but a prominent button turns a detail surface into a dialog and
    /// invites the next verb to join it. Matched to `Show Log`'s weight in the
    /// diagnostic popover, which is the surface this is a sibling of.
    private var header: some View {
        HStack(spacing: 8) {
            Text(title).font(.headline)
            Spacer()
            if let onAnalyse {
                Button(i18n.t("desktop.menu.project.analyse"), action: onAnalyse)
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
    }

    /// Names the dominant condition. `pickDelta`'s precedence — missing beats
    /// unanalysed — so the popover's title agrees with the row's glyph rather
    /// than the two disagreeing about what this row is about.
    private var title: String {
        missingFiles.isEmpty
            ? i18n.t("desktop.chrome.filesPopover.unanalysedTitle")
            : i18n.t("desktop.chrome.filesPopover.missingTitle")
    }

    @ViewBuilder
    private var content: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Missing first when both are present: source that has vanished is
            // the more urgent fact, and it is the one the row's glyph is about.
            if !missingFiles.isEmpty {
                section(files: missingFiles,
                        label: i18n.plural("desktop.chrome.missingSubtitle", count: missingFiles.count),
                        footer: i18n.t("desktop.chrome.filesPopover.missingFooter"),
                        kind: .warning)
            }
            if !newFiles.isEmpty {
                section(files: newFiles,
                        label: i18n.plural("desktop.chrome.unanalysedSubtitle", count: newFiles.count),
                        footer: i18n.t("desktop.chrome.unanalysedSheetFooter"),
                        kind: .info)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private func section(files: [URL], label: String, footer: String,
                         kind: MessageKind) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            // The section label carries the kind's glyph, so a popover showing
            // both conditions distinguishes them the same way the row does.
            HStack(spacing: 5) {
                Image(systemName: kind.symbolName)
                    .foregroundStyle(kind.tint)
                    .imageScale(.small)
                Text(label).font(.subheadline.weight(.medium))
            }
            ForEach(files, id: \.self) { url in
                HStack(spacing: 8) {
                    Image(systemName: "doc")
                        .foregroundStyle(.secondary)
                        .imageScale(.small)
                    Text(url.lastPathComponent)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .textSelection(.enabled)
                    Spacer(minLength: 8)
                    if let size = Self.formattedSize(of: url) {
                        Text(size).font(.caption).foregroundStyle(.tertiary)
                    }
                }
                .font(.callout)
            }
            Text(footer)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// A missing file has no size to read — `resourceValues` throws and this
    /// returns nil, which is the honest rendering (no "0 bytes", which would
    /// look like a file that exists and is empty).
    static func formattedSize(of url: URL) -> String? {
        guard let bytes = (try? url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize
        else { return nil }
        return ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }
}
