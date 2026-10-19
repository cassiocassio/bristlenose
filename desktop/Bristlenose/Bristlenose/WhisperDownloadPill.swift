import SwiftUI

/// The Whisper download, in the toolbar's `.status` zone
/// (`docs/design-apple-first-transcription.md` §4.2). App-global, so it sits
/// with the Ollama and out-of-credit pills on the shared `StatusPill` envelope.
/// It shows while bytes move and after a failure (with Retry, as the Ollama
/// pill does), and is gone once Whisper is on disk or after a deliberate Stop.
///
/// The popover: what is happening, Foundation's own progress line (bytes, rate
/// and time left, in the app's language, nothing invented before the rate is
/// known), one sentence of why, and Stop Download — with the note that it
/// starts again from the beginning, because there is no resume and a plain
/// Cancel would hide that loss.
struct WhisperDownloadPill: View {
    @ObservedObject var model: WhisperDownloadModel
    @EnvironmentObject var i18n: I18n
    @State private var showingDetail = false

    private var failed: Bool { model.phase == .failed }

    var body: some View {
        if model.isPillVisible {
            StatusPill(
                isPresented: $showingDetail,
                accessibilityLabel: i18n.t(failed ? "desktop.modelDownload.failedTitle"
                                                  : "desktop.modelDownload.title")
            ) {
                if failed {
                    Image(systemName: "xmark.circle.fill")
                        .imageScale(.small)
                        .foregroundStyle(.red)
                    Text(i18n.t("desktop.modelDownload.failedTitle"))
                        .font(.system(.caption).weight(.medium))
                        .lineLimit(1)
                } else {
                    Image(systemName: "arrow.down.circle")
                        .imageScale(.small)
                        .foregroundStyle(.secondary)
                    Text(i18n.t("desktop.modelDownload.title"))
                        .font(.system(.caption).weight(.medium))
                        .lineLimit(1)
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
                WhisperDownloadDetail(model: model)
                    .environmentObject(i18n)
            }
            .accessibilityValue(failed ? "" : model.progressLine)
        }
    }
}

/// The pill's popover body.
struct WhisperDownloadDetail: View {
    @ObservedObject var model: WhisperDownloadModel
    @EnvironmentObject var i18n: I18n

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if model.phase == .failed {
                Text(i18n.t("desktop.modelDownload.failedTitle"))
                    .font(.system(.callout).weight(.semibold))
                Text(i18n.t("desktop.transcriptionSettings.whisperFailed"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(i18n.t("desktop.modelDownload.why"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
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
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(i18n.t("desktop.modelDownload.stopNote"))
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 8)
                    Button(i18n.t("desktop.modelDownload.stop")) { model.stop() }
                        .controlSize(.small)
                }
            }
        }
        .padding(16)
        .frame(width: 300)
    }
}
