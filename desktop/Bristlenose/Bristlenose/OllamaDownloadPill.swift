import SwiftUI

/// Toolbar pill for the ambient local-model pull (Beat 3). Self-hides when
/// the `OllamaDownloadModel` is idle. Mirrors `CopyProgressPill`'s visual
/// envelope (Capsule + secondary stroke) so the two pills read as the same
/// surface.
///
/// One cancel path: the pill is a click target that opens a popover carrying
/// the byte detail + a Stop button (or, on failure, the error detail + Retry).
/// No inline buttons on the pill itself — actions live in the popover.
struct OllamaDownloadPill: View {
    @ObservedObject var model: OllamaDownloadModel
    @EnvironmentObject var i18n: I18n
    @State private var showingDetail = false

    var body: some View {
        if model.isActive {
            Button {
                showingDetail.toggle()
            } label: {
                pillBody
            }
            .buttonStyle(.plain)
            .popover(isPresented: $showingDetail, arrowEdge: .bottom) {
                detailPopover
            }
        }
    }

    // MARK: - Pill

    @ViewBuilder
    private var pillBody: some View {
        HStack(spacing: 6) {
            icon
            Text(statusText)
                .font(.system(.caption).weight(.medium))
                .lineLimit(1)
            progressAccessory
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Capsule().fill(Color.secondary.opacity(0.08)))
        .overlay(Capsule().stroke(Color.secondary.opacity(0.25), lineWidth: 0.5))
        .contentShape(Capsule())
    }

    @ViewBuilder
    private var icon: some View {
        if case .failed = model.phase {
            Image(systemName: "exclamationmark.triangle.fill")
                .imageScale(.small)
                .foregroundStyle(.orange)
        } else {
            Image(systemName: "arrow.down.circle")
                .imageScale(.small)
                .foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private var progressAccessory: some View {
        switch model.phase {
        case .downloading where model.totalBytes > 0:
            ProgressView(value: model.downloadRatio)
                .progressViewStyle(.linear)
                .frame(width: 70)
            Text(model.downloadRatio.formatted(.percent.precision(.fractionLength(0))))
                .font(.caption)
                .monospacedDigit()
                .foregroundStyle(.secondary)
        case .installing, .starting, .finishing, .downloading:
            // Indeterminate phases (and a download we don't yet have byte
            // totals for) get a spinner, not a fake determinate bar.
            ProgressView()
                .controlSize(.small)
        case .failed, .idle:
            EmptyView()
        }
    }

    // MARK: - Popover

    @ViewBuilder
    private var detailPopover: some View {
        VStack(alignment: .leading, spacing: 10) {
            if case .failed(let failure) = model.phase {
                Text(i18n.t("desktop.ollamaSetup.pullFailedTitle"))
                    .font(.headline)
                Text(failureDetail(failure))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                HStack {
                    Spacer()
                    Button(i18n.t("common.buttons.retry")) {
                        model.retry()
                        showingDetail = false
                    }
                    .keyboardShortcut(.defaultAction)
                }
            } else {
                Text(statusText)
                    .font(.headline)
                if case .downloading = model.phase, model.totalBytes > 0 {
                    Text(byteString)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .monospacedDigit()
                }
                HStack {
                    Spacer()
                    Button(i18n.t("common.buttons.cancel")) {
                        model.cancel()
                        showingDetail = false
                    }
                }
            }
        }
        .padding(16)
        .frame(width: 280)
    }

    // MARK: - Strings

    private var statusText: String {
        switch model.phase {
        case .installing:
            return i18n.t("desktop.ollamaSetup.installingRuntime")
        case .starting:
            return i18n.t("desktop.ollamaSetup.startingRuntime")
        case .downloading:
            return String(
                format: i18n.t("desktop.ollamaSetup.downloadingModel"), modelName)
        case .finishing:
            return i18n.t("desktop.ollamaSetup.finishingUp")
        case .failed:
            return i18n.t("desktop.ollamaSetup.pullFailedTitle")
        case .idle:
            return ""
        }
    }

    /// Humanised model name from the catalog (e.g. "Gemma 4 E4B"), falling
    /// back to the raw tag for custom values.
    private var modelName: String {
        let tag = model.currentTag ?? ""
        return OllamaCatalog.model(for: tag)?.displayName ?? tag
    }

    private var byteString: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        let done = formatter.string(fromByteCount: model.completedBytes)
        let total = formatter.string(fromByteCount: model.totalBytes)
        return String(format: i18n.t("desktop.ollamaSetup.bytesProgress"), done, total)
    }

    private func failureDetail(_ failure: OllamaDownloadModel.Failure) -> String {
        switch failure {
        case .runtimeDidNotStart:
            return i18n.t("desktop.ollamaSetup.runtimeDidNotStart")
        case .noInternet:
            return i18n.t("desktop.ollamaSetup.errorNoInternet")
        case .timedOut:
            return i18n.t("desktop.ollamaSetup.errorTimedOut")
        case .cantReach:
            return i18n.t("desktop.ollamaSetup.errorCantReach")
        case .generic(let message):
            return String(format: i18n.t("desktop.ollamaSetup.errorGeneric"), message)
        }
    }
}
