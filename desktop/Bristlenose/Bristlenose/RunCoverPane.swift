import SwiftUI

/// The native pane over a stale status page (`DetailPaneKind.runCover`). The
/// stock `ContentUnavailableView`, as the other detail panes draw it, and the
/// row's own strings where the row has one, so the row and the pane state the
/// same fact (`docs/mockups/detail-pane-states.html`, owner, 24 Oct 2026).
///
/// Its own view because the analysing line follows the run's per-second
/// progress, which `ContentView` deliberately does not observe.
///
/// A stop gets its words and the way on: "Analysis stopped" and Resume
/// Analysis. A run the app's leaving cut short says so in one line. A failure
/// gets the row popover's sentence, the button its remedy allows, and Show
/// details for the forensic record.
struct RunCoverPane: View {
    let cover: DetailPaneKind.RunCover
    let project: Project
    @ObservedObject var liveData: PipelineLiveData
    let onAnalyse: () -> Void
    let onRetryStartup: () -> Void
    /// Opens with the forensic record showing. Only the Review Gallery sets
    /// it, so the expanded state can be reviewed without a click; a click
    /// still toggles it either way.
    var startsExpanded = false
    @EnvironmentObject private var i18n: I18n
    @State private var detailsToggled: Bool?
    private var detailsExpanded: Bool { detailsToggled ?? startsExpanded }

    var body: some View {
        switch cover {
        case .queued(let position):
            ContentUnavailableView(
                i18n.t("desktop.chrome.pipeline.queuedPosition", ["position": String(position)]),
                systemImage: "clock",
                description: Text(i18n.t("desktop.chrome.pipeline.queuedHint"))
            )
        case .analysing:
            analysing
        case .interrupted:
            ContentUnavailableView {
                Label(i18n.t("desktop.chrome.analysisInterrupted"),
                      systemImage: "exclamationmark.triangle")
            } description: {
                Text(i18n.t("desktop.chrome.analysisInterruptedHint"))
            } actions: {
                Button(i18n.t("desktop.chrome.resumeAnalysis"), action: onAnalyse)
            }
        case .stopped:
            ContentUnavailableView {
                Label(i18n.t("desktop.chrome.analysisStopped"), systemImage: "stop.circle")
            } description: {
                EmptyView()
            } actions: {
                Button(i18n.t("desktop.chrome.resumeAnalysis"), action: onAnalyse)
            }
        case .needsProvider:
            ContentUnavailableView {
                Label(i18n.t("desktop.chrome.providerNeeded"), systemImage: "key")
            } description: {
                Text(i18n.t("desktop.chrome.providerNeededHint"))
            } actions: {
                setUpProviderButton
            }
        case .failed(let sentence, let rawCause, let category, let summary):
            failed(sentence: sentence, rawCause: rawCause, category: category, summary: summary)
        }
    }

    /// The row's ring in the icon slot and the row's own line as the headline,
    /// so the pane and the row cannot disagree.
    private var analysing: some View {
        let p = liveData.progress[project.id]
        let stopping = p?.isStopping ?? false
        // Stopping outranks progress, as on the row (`ProjectRow`).
        let line = stopping ? i18n.t("desktop.chrome.pipeline.stopping") : RunProgressSubtitle.compose(
            stage: p?.stage,
            sessionsComplete: p?.sessionsComplete,
            sessionsTotal: p?.sessionsTotal,
            etaRemainingSeconds: p?.etaRemainingSeconds,
            resuming: p?.readsAsResuming ?? false,
            sessionsReadable: p?.sessionsReadable,
            separator: " · ",
            localize: { i18n.t($0, $1) },
            pluralize: { i18n.plural($0, count: $1) }
        )
        return ContentUnavailableView {
            Label {
                Text(line)
            } icon: {
                if let fraction = p?.ringFraction {
                    ProgressView(value: fraction)
                        .progressViewStyle(.circular)
                        .controlSize(.large)
                } else {
                    ProgressView()
                        .controlSize(.large)
                }
            }
        } description: {
            if !stopping {
                Text(i18n.t("desktop.chrome.pipeline.analysingHint"))
            }
        }
    }

    private var setUpProviderButton: some View {
        Button(i18n.t("desktop.pipeline.diagnostic.action.setUpProvider")) {
            SettingsWindow.shared.show(pane: .llm)
        }
    }

    @ViewBuilder
    private func failed(
        sentence: FailureMessage, rawCause: String?, category: PipelineFailureCategory,
        summary: PipelineSummary?
    ) -> some View {
        if let refusal = sentence.startupRefusal {
            ContentUnavailableView {
                Label(refusal.headline(using: i18n), systemImage: "exclamationmark.triangle")
            } description: {
                VStack(spacing: 12) {
                    Text(refusal.detail(using: i18n))
                    Text(refusal.consequence(using: i18n))
                }
            } actions: {
                Button(i18n.t("desktop.boot.retry"), action: onRetryStartup)
                    .keyboardShortcut(.defaultAction)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            ContentUnavailableView {
                Label(i18n.t("desktop.chrome.failedTitle"), systemImage: "exclamationmark.triangle")
            } description: {
                Text(sentence.resolved(i18n)).lineLimit(3)
            } actions: {
                // Our own row in the stock actions slot: the slot splits a plain
                // HStack's width equally and a Button ellipsizes ("Show Det…",
                // 9 Nov 2026). Each button keeps its label's width instead.
                // The slot lays its children out in a row, so the details go in
                // a column with the buttons: they open underneath, and the
                // buttons stay where they were clicked (14 Nov 2026).
                VStack(spacing: 12) {
                    HStack(spacing: 12) {
                        switch DetailPaneKind.FailureRemedy.of(category) {
                        case .setUpProvider: setUpProviderButton
                        case .retry: Button(i18n.t("desktop.boot.retry"), action: onAnalyse)
                        case .none: EmptyView()
                        }
                        Button(i18n.t(detailsExpanded
                                      ? "desktop.boot.hideDetails"
                                      : "desktop.boot.showDetails")) {
                            detailsToggled = !detailsExpanded
                        }
                    }
                    .fixedSize(horizontal: true, vertical: false)
                    if detailsExpanded {
                        ScrollView {
                            Text(forensicRecord(rawCause: rawCause, category: category, summary: summary))
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                                .padding(8)
                        }
                        .frame(width: FailureDetailsBox.width)
                        .frame(maxHeight: 140)
                        .background(Color(nsColor: .textBackgroundColor).opacity(0.5))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                }
            }
        }
    }

    /// The row popover's Copy details text: English, as forensic records are.
    /// (The details box's width lives in `FailureDetailsBox`, shared with BootView.)
    private func forensicRecord(
        rawCause: String?, category: PipelineFailureCategory, summary: PipelineSummary?
    ) -> String {
        if let summary {
            return ProjectDiagnosticPopover.formatDiagnosticPlaintext(
                summary: summary, projectName: project.name,
                projectPath: project.path, abandoned: true
            )
        }
        return ProjectDiagnosticPopover.formatDiagnosticPlaintextDegraded(
            cause: rawCause ?? "", category: category, projectName: project.name,
            projectPath: project.path,
            stdoutTail: Array((liveData.outputLines[project.id] ?? []).suffix(20))
        )
    }
}

/// The Show Details box on the failure panes (this file and `BootView`).
///
/// The record is CLI output, written for an 80-column terminal, so the box is
/// 80 columns of its own font wide, plus its 8pt padding each side and a scroll
/// bar. A width, not a ceiling: the `ContentUnavailableView` actions slot
/// proposes only the buttons' width, and under `maxWidth: 480` the record
/// wrapped at about 240pt (14 Nov 2026). Measured: 80 columns of caption
/// monospace is 495pt, so the box is about 530pt.
enum FailureDetailsBox {
    static let columns = 80

    static let width: CGFloat = {
        let size = NSFont.preferredFont(forTextStyle: .caption1).pointSize
        let font = NSFont.monospacedSystemFont(ofSize: size, weight: .regular)
        let column = ("0" as NSString).size(withAttributes: [.font: font]).width
        let scroller = NSScroller.scrollerWidth(for: .regular, scrollerStyle: .legacy)
        return (column * CGFloat(columns)).rounded(.up) + 16 + scroller
    }()
}
