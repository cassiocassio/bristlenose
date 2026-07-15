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
    /// True when `config` was supplied directly (no `/api/health` probe) — the
    /// serve-free path used by the expired-alpha `.dmg` flow.
    private let preresolved: Bool

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
        self.preresolved = false
    }

    /// Serve-free init: `config` supplied directly, no `/api/health` probe. For
    /// contexts with no running sidecar (the expired-alpha `.dmg` flow).
    init(
        config: FeedbackConfig,
        i18n: I18n,
        client: FeedbackClient = FeedbackClient(),
        bundleVersion: String = Bundle.main.infoDictionary?["CFBundleShortVersionString"]
            as? String ?? "unknown"
    ) {
        self.port = 0
        self.i18n = i18n
        self.client = client
        self.bundleVersion = bundleVersion
        self.config = config
        self.preresolved = true
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
        // Serve-free path: config already supplied, skip the health probe.
        if preresolved { phase = .ready; return }
        phase = .loading
        config = await FeedbackHealth.load(port: port)
        phase = .ready
    }

    /// Returns whether the sheet should dismiss (only on confirmed send) plus a
    /// toast. On any failure the sheet stays open, the typed message is kept
    /// (draft retention), and the outcome is copied to the clipboard. A toast is
    /// returned on BOTH outcomes — `t("sent")` on success, the clipboard-copy
    /// message on failure — never from `onDismiss`.
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
    /// Fired on confirmed send (before dismiss), so a caller can distinguish a
    /// successful submit from a plain cancel. Used by the expired-alpha flow to
    /// route to its "Thanks" step; nil for the normal Help ▸ Send Feedback path.
    private let onSent: (() -> Void)?

    init(port: Int, i18n: I18n, onToast: @escaping (String) -> Void, onSent: (() -> Void)? = nil) {
        _model = StateObject(wrappedValue: FeedbackSheetModel(port: port, i18n: i18n))
        self.onToast = onToast
        self.onSent = onSent
    }

    /// Serve-free init: config supplied directly (no `/api/health` probe). For
    /// contexts with no running sidecar (the expired-alpha `.dmg` flow).
    init(config: FeedbackConfig, i18n: I18n, onToast: @escaping (String) -> Void,
         onSent: (() -> Void)? = nil) {
        _model = StateObject(wrappedValue: FeedbackSheetModel(config: config, i18n: i18n))
        self.onToast = onToast
        self.onSent = onSent
    }

    private let sheetWidth: CGFloat = 520

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
            // Five-point affective scale as a row of SF Symbol + label cells
            // with radio semantics (nothing preselected ⇒ Send stays disabled
            // until an explicit choice). Native answer to the web modal's faces —
            // replaces the segmented control, which read as tab-switching and
            // collided with the toolbar's tab picker idiom.
            FeedbackScale(
                rating: $model.rating,
                isDisabled: model.phase == .sending,
                label: model.label
            )

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
            .lineLimit(5...14)
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
        // Suppress the redundant "sent" toast when a caller owns the success
        // confirmation itself (onSent wired → the expiry flow's "Thanks" step).
        // The clipboard-fallback toast on failure always fires — it's the only
        // signal the sheet gives on a failed send.
        if let toast = outcome.toast, !(outcome.dismiss && onSent != nil) {
            onToast(toast)
        }
        // `dismiss == true` only on a confirmed send — signal, then close.
        if outcome.dismiss { onSent?(); dismiss() }
    }
}

// MARK: - Affective scale

/// Five-point satisfaction scale: a row of SF Symbol + label cells with radio
/// semantics (single selection, nothing preselected).
///
/// Departure sentence (per §Native primitives first): the stock primitive is a
/// segmented / radio-group `Picker`. We depart because a segmented control reads
/// as *tab-switching* — and this app's own toolbar already uses a segmented
/// picker for exactly that (Project · Sessions · Quotes · …), so reusing it for
/// "rate your feeling" collides with the idiom the rest of the app teaches; and
/// a stock radio group can't carry the glyph-over-label column that mirrors the
/// web modal's affective faces. This is the native rendering of the shared
/// cross-surface taxonomy: same five points, same column layout, but SF Symbols
/// instead of the web's emoji (the sheet's existing "labels, not emoji" stance).
private struct FeedbackScale: View {
    @Binding var rating: FeedbackRating?
    let isDisabled: Bool
    let label: (FeedbackRating) -> String

    /// Phase 0: the five SPA emoji, rendered natively via Apple Color Emoji so
    /// the sheet mirrors the web modal 1:1 (same taxonomy, same faces). SF
    /// Symbols has no graduated face family, and the gauge/meter idiom tried
    /// here didn't read as an affective scale — parked, not dead, for a later
    /// pass at the native rendering.
    static func emoji(for rating: FeedbackRating) -> String {
        switch rating {
        case .hate: return "😠"     // angry
        case .dislike: return "😕"  // confused
        case .neutral: return "😐"  // neutral
        case .like: return "🙂"     // slight smile
        case .love: return "😊"     // warm smile
        }
    }

    var body: some View {
        HStack(spacing: 8) {
            ForEach(FeedbackRating.allCases) { cell($0) }
        }
        .frame(maxWidth: .infinity)
        .disabled(isDisabled)
    }

    private func cell(_ item: FeedbackRating) -> some View {
        let selected = rating == item
        return Button {
            rating = item
        } label: {
            VStack(spacing: 6) {
                Text(Self.emoji(for: item))
                    .font(.system(size: 30))
                Text(label(item))
                    .font(.caption)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .padding(.horizontal, 4)
            .foregroundStyle(selected ? Color.accentColor : Color.secondary)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(selected ? Color.accentColor.opacity(0.12) : Color.clear)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(selected ? Color.accentColor : Color.clear, lineWidth: 1)
            )
            .contentShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label(item))
        .accessibilityAddTraits(selected ? [.isSelected] : [])
    }
}
