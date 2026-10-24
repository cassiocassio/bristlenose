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
    @EnvironmentObject private var i18n: I18n
    @State private var detailsExpanded = false

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

    private func failed(
        sentence: FailureMessage, rawCause: String?, category: PipelineFailureCategory,
        summary: PipelineSummary?
    ) -> some View {
        ContentUnavailableView {
            Label(i18n.t("desktop.chrome.failedTitle"), systemImage: "exclamationmark.triangle")
        } description: {
            Text(sentence.resolved(i18n)).lineLimit(3)
        } actions: {
            HStack(spacing: 12) {
                switch DetailPaneKind.FailureRemedy.of(category) {
                case .setUpProvider: setUpProviderButton
                case .retry: Button(i18n.t("desktop.boot.retry"), action: onAnalyse)
                case .none: EmptyView()
                }
                Button(i18n.t(detailsExpanded
                              ? "desktop.boot.hideDetails"
                              : "desktop.boot.showDetails")) {
                    detailsExpanded.toggle()
                }
            }
            if detailsExpanded {
                ScrollView {
                    Text(forensicRecord(rawCause: rawCause, category: category, summary: summary))
                        .font(.system(.caption, design: .monospaced))
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .padding(8)
                }
                .frame(maxWidth: 480, maxHeight: 140)
                .background(Color(nsColor: .textBackgroundColor).opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
    }

    /// The row popover's Copy details text: English, as forensic records are.
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
