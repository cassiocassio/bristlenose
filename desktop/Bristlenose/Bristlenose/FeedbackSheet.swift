import AppKit
import SwiftUI

/// Native "Send Feedback" sheet — the macOS rendering of the React
/// `FeedbackModal`, used when the SPA isn't mounted (the server-rendered status
/// page after a cancelled/failed run). Reached two ways, both when the SPA is
/// absent: the status page's "Send feedback" hands off via the navigation bridge
/// (`project-action: open-feedback`), and Help ▸ Send Feedback falls through to
/// here when it can't reach the in-page `window.__bristlenose` bridge.
///
/// A sheet, not a floating panel: it's a committed data-entry task with a text
/// field that must take key focus and a default Send button — the native default
/// for a menu-triggered modal task (HIG: Modality). All strings are the shared
/// `common.feedback.*` set — already translated in every locale, identical to
/// the web modal and the status-page form. Same `{version, rating, message}`
/// payload, same strict `{ok:true}` success predicate, same clipboard fallback.

// MARK: - View model

@MainActor
final class FeedbackSheetModel: ObservableObject {
    enum Phase { case loading, ready, sending }

    @Published var phase: Phase = .loading
    @Published var rating: FeedbackRating?
    @Published var message: String = ""
    @Published private(set) var config: FeedbackConfig = .unavailable

    private let port: Int
    private let i18n: I18n
    private let client: FeedbackClient
    private let bundleVersion: String

    init(
        port: Int,
        i18n: I18n,
        client: FeedbackClient = FeedbackClient(),
        bundleVersion: String = Bundle.main.infoDictionary?["CFBundleShortVersionString"]
            as? String ?? "unknown"
    ) {
        self.port = port
        self.i18n = i18n
        self.client = client
        self.bundleVersion = bundleVersion
    }

    func t(_ key: String) -> String { i18n.t("common.feedback.\(key)") }
    func label(_ rating: FeedbackRating) -> String { i18n.t("common.feedback.\(rating.labelKey)") }
    var cancelLabel: String { i18n.t("common.buttons.cancel") }

    /// Prefer the server's version (parity with the web payload, which sends
    /// `health.version`); fall back to the app bundle when health didn't answer.
    var version: String { config.version.isEmpty ? bundleVersion : config.version }

    private var trimmedMessage: String {
        message.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Send is offered as soon as a rating is chosen and health has resolved —
    /// it always produces a visible outcome (POST when the endpoint is reachable,
    /// clipboard otherwise), so it's never a dead button.
    var canSend: Bool { rating != nil && phase == .ready }

    func load() async {
        phase = .loading
        config = await FeedbackHealth.load(port: port)
        phase = .ready
    }

    /// Returns whether the sheet should dismiss (only on confirmed send) plus a
    /// toast. On any failure the sheet stays open, the typed message is kept
    /// (draft retention), and the outcome is copied to the clipboard — the toast
    /// is emitted **only** from the confirmed-success branch, never on dismiss.
    func send() async -> (dismiss: Bool, toast: String?) {
        guard let rating else { return (false, nil) }
        // No reachable/validated endpoint (disabled, unreachable, off-host) →
        // clipboard, honouring a disabled config without silently POSTing.
        guard let url = config.url else {
            return (false, copyToClipboard(rating: rating))
        }
        phase = .sending
        let payload = FeedbackPayload(
            version: version, rating: rating.rawValue, message: trimmedMessage
        )
        let result = await client.submit(payload, to: url)
        phase = .ready
        switch result {
        case .sent:
            return (true, t("sent"))
        case .failed:
            return (false, copyToClipboard(rating: rating))
        }
    }

    private func copyToClipboard(rating: FeedbackRating) -> String {
        var text = "Bristlenose feedback (v\(version))\nRating: \(label(rating))\n"
        if !trimmedMessage.isEmpty { text += "Message: \(trimmedMessage)\n" }
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        return pasteboard.setString(text, forType: .string)
            ? t("copiedToClipboard")
            : t("copyFailed")
    }
}

// MARK: - Sheet

struct FeedbackSheet: View {
    @StateObject private var model: FeedbackSheetModel
    @Environment(\.dismiss) private var dismiss
    private let onToast: (String) -> Void

    init(port: Int, i18n: I18n, onToast: @escaping (String) -> Void) {
        _model = StateObject(wrappedValue: FeedbackSheetModel(port: port, i18n: i18n))
        self.onToast = onToast
    }

    private let sheetWidth: CGFloat = 460

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(model.t("heading"))
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)

            if model.phase == .loading {
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
            } else {
                form
            }
        }
        .padding(20)
        .frame(width: sheetWidth)
        .task { await model.load() }
    }

    private var form: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Five-point affective scale as a native segmented control (labels,
            // not emoji). Optional binding ⇒ nothing preselected, so Send stays
            // disabled until the user makes an explicit choice.
            Picker("", selection: $model.rating) {
                ForEach(FeedbackRating.allCases) { rating in
                    Text(model.label(rating)).tag(Optional(rating))
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .disabled(model.phase == .sending)

            Text(model.t("helpUsImprove"))
                .font(.callout)
                .foregroundStyle(.secondary)

            TextField(
                "",
                text: $model.message,
                prompt: Text(model.t("placeholder")),
                axis: .vertical
            )
            .textFieldStyle(.roundedBorder)
            .lineLimit(3...6)
            .disabled(model.phase == .sending)

            Text(model.t("anonymous"))
                .font(.footnote)
                .foregroundStyle(.secondary)

            HStack {
                Spacer()
                Button(model.cancelLabel) { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button(model.t("send")) { Task { await submit() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(!model.canSend)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func submit() async {
        let outcome = await model.send()
        if let toast = outcome.toast { onToast(toast) }
        if outcome.dismiss { dismiss() }
    }
}
