import SwiftUI

/// The Whisper download, in the toolbar's `.status` zone
/// (`docs/design-apple-first-transcription.md` §4.2). App-global, so it sits
/// with the Ollama and out-of-credit pills on the shared `StatusPill` envelope.
/// It shows while bytes move and after a failure (with Retry, as the Ollama
/// pill does), and is gone once Whisper is on disk or after a deliberate Stop.
///
/// The popover: what is happening, Foundation's own progress line (bytes, rate
/// and time left, in the app's language, nothing invented before the rate is
/// known, the time left on its own line), one sentence of why, and Stop.
struct WhisperDownloadPill: View {
    @ObservedObject var model: WhisperDownloadModel
    @EnvironmentObject var i18n: I18n
    @State private var showingDetail = false

    private var failed: Bool { model.phase == .failed }
    /// The warning, not a failure: nothing was tried (`WhisperDownloadModel.lowDisk`).
    private var lowDisk: Bool { model.lowDisk }

    var body: some View {
        if model.isPillVisible {
            StatusPill(
                isPresented: $showingDetail,
                accessibilityLabel: i18n.t(failed ? "desktop.modelDownload.failedTitle"
                                                  : lowDisk ? "desktop.modelDownload.lowDiskPill"
                                                  : "desktop.modelDownload.title")
            ) {
                if lowDisk {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .imageScale(.small)
                        .foregroundStyle(.orange)
                    Text(i18n.t("desktop.modelDownload.lowDiskPill"))
                        .font(.system(.caption).weight(.medium))
                        .fixedSize(horizontal: true, vertical: false)  // a pill's label never truncates
                } else if failed {
                    Image(systemName: "xmark.circle.fill")
                        .imageScale(.small)
                        .foregroundStyle(.red)
                    Text(i18n.t("desktop.modelDownload.failedTitle"))
                        .font(.system(.caption).weight(.medium))
                        .fixedSize(horizontal: true, vertical: false)  // a pill's label never truncates
                } else {
                    Image(systemName: "arrow.down.circle")
                        .imageScale(.small)
                        .foregroundStyle(.secondary)
                    Text(i18n.t("desktop.modelDownload.title"))
                        .font(.system(.caption).weight(.medium))
                        .fixedSize(horizontal: true, vertical: false)  // a pill's label never truncates
                    // One width whether or not the total is known, so the
                    // toolbar does not jump when it arrives.
                    Group {
                        if let fraction = model.fractionDone {
                            ProgressView(value: fraction)
                        } else {
                            ProgressView()
                        }
                    }
                    .progressViewStyle(.linear)
                    .frame(width: 58)
                    if let fraction = model.fractionDone {
                        Text(fraction.formatted(.percent.precision(.fractionLength(0))))
                            .font(.caption)
                            .monospacedDigit()
                            .foregroundStyle(.secondary)
                    }
                }
            } detail: {
                WhisperDownloadDetail(model: model, close: { showingDetail = false })
                    .environmentObject(i18n)
            }
            .accessibilityValue(failed || lowDisk ? "" : model.progressLine)
        }
    }
}

/// The pill's popover body.
struct WhisperDownloadDetail: View {
    @ObservedObject var model: WhisperDownloadModel
    @EnvironmentObject var i18n: I18n
    /// Closes the popover before another window is raised.
    var close: () -> Void = {}

    /// A full disk, whether it stopped the app from starting or stopped a download part-way:
    /// Retry cannot help, Transcription Settings can (other models, Download Now once there is room).
    private var diskProblem: Bool {
        Self.diskProblem(phase: model.phase, cause: model.failureCause, lowDisk: model.lowDisk)
    }

    nonisolated static func diskProblem(
        phase: WhisperDownloadModel.Phase, cause: WhisperFailureCause?, lowDisk: Bool
    ) -> Bool {
        phase == .failed ? cause.map { !$0.retryCanWork } ?? false : lowDisk
    }

    /// The popover's Retry button is drawn exactly when the download failed and the cause is not a
    /// full disk. It calls `downloadNow()`, as Settings' Retry and Download Now do.
    nonisolated static func offersRetry(phase: WhisperDownloadModel.Phase, cause: WhisperFailureCause?) -> Bool {
        phase == .failed && !diskProblem(phase: phase, cause: cause, lowDisk: false)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if diskProblem {
                Text(i18n.t("desktop.modelDownload.lowDiskTitle"))
                    .font(.system(.callout).weight(.semibold))
                Text(i18n.t("desktop.modelDownload.lowDiskBody", [
                    "floor": ByteCountFormatter.string(
                        fromByteCount: WhisperDownloadModel.autoStartFloorBytes, countStyle: .file),
                    "size": i18n.t("desktop.modelDownload.askSize"),
                ]))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                HStack {
                    Spacer()
                    Button(i18n.t("desktop.modelDownload.transcriptionSettings")) {
                        close()
                        SettingsWindow.shared.show(pane: .transcription)
                    }
                    .keyboardShortcut(.defaultAction)
                    .fixedSize(horizontal: true, vertical: false)  // a button's label never truncates
                }
                .padding(.top, 2)
            } else if Self.offersRetry(phase: model.phase, cause: model.failureCause) {
                Text(i18n.t(WhisperFailureCause.titleKey(for: model.failureCause)))
                    .font(.system(.callout).weight(.semibold))
                Text(i18n.t(WhisperFailureCause.lineKey(for: model.failureCause)))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                if model.failureCause == .certificate {
                    Text(i18n.t("desktop.modelDownload.causeCertificateHint"))
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack {
                    Spacer()
                    Button(i18n.t("common.buttons.retry")) { model.downloadNow() }
                        .keyboardShortcut(.defaultAction)
                }
                .padding(.top, 2)
            } else {
                Text(i18n.t("desktop.modelDownload.title"))
                    .font(.system(.callout).weight(.semibold))
                Group {
                    if let fraction = model.fractionDone {
                        ProgressView(value: fraction)
                    } else {
                        ProgressView()
                    }
                }
                .progressViewStyle(.linear)
                Text(model.progressLine)
                    .font(.callout)
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(i18n.t("desktop.modelDownload.why"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Divider().padding(.top, 2)
                HStack {
                    Spacer(minLength: 8)
                    Button(i18n.t("desktop.modelDownload.stop")) { model.stop() }
                        .controlSize(.small)
                        .fixedSize(horizontal: true, vertical: false)  // a button's label never truncates
                }
            }
        }
        .padding(16)
        .frame(width: 300)
    }
}
