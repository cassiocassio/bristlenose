import SwiftUI

/// The native pane over a stale status page (`DetailPaneKind.runCover`). The
/// stock `ContentUnavailableView`, as the other detail panes draw it, and the
/// row's own strings where the row has one, so the row and the pane say the
/// same thing.
///
/// Its own view because the "Analysing…"/"Resuming…" verb follows the run's
/// per-second progress, which `ContentView` deliberately does not observe.
///
/// An outcome the researcher chose gets its words and nothing else: "Analysis
/// stopped" after Stop. One they didn't, the app leaving under the run, gets
/// "Analysis interrupted" and the Analyse that carries on (owner, 24 Oct 2026,
/// `docs/mockups/interrupted-run-pane.html`).
struct RunCoverPane: View {
    let cover: DetailPaneKind.RunCover
    let projectID: UUID
    @ObservedObject var liveData: PipelineLiveData
    let onAnalyse: () -> Void
    @EnvironmentObject private var i18n: I18n

    var body: some View {
        switch cover {
        case .queued(let position):
            ContentUnavailableView(
                i18n.t("desktop.chrome.pipeline.queuedPosition", ["position": String(position)]),
                systemImage: "clock"
            )
        case .analysing:
            let progress = liveData.progress[projectID]
            ContentUnavailableView(
                i18n.t(RunProgressSubtitle.coverKey(
                    stage: progress?.stage, resuming: progress?.readsAsResuming ?? false
                )),
                systemImage: "waveform"
            )
        case .interrupted:
            ContentUnavailableView {
                Label(i18n.t("desktop.chrome.analysisInterrupted"), systemImage: "stop.circle")
            } description: {
                EmptyView()
            } actions: {
                Button(i18n.t("desktop.menu.project.analyse"), action: onAnalyse)
            }
        case .stopped:
            ContentUnavailableView(
                i18n.t("desktop.chrome.analysisStopped"),
                systemImage: "stop.circle"
            )
        }
    }
}
