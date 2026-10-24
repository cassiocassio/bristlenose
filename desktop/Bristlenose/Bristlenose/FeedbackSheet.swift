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
/// `common.feedback.*` set, identical to the web modal and the status-page
/// form. Same `{version, rating, message}` payload, same strict `{ok:true}`
/// success predicate, same clipboard fallback. A send that fails says so in
/// the sheet, with where to paste the copy (R80), as the web modal and the
/// status-page form do.

// MARK: - Mode

/// Which journey brought the person to the sheet
/// (`docs/design-feedback-native.md` § Feedback and problem reports).
/// Feedback is the person's own idea: Help ▸ Send Feedback…, the ladybug, a
/// footer link. A problem report is Bristlenose suggesting it after something
/// failed: the boot pane once a Retry has failed too, the report-crash pane
/// once its Retry has crashed too. Same sheet, same rating, same anonymity line;
/// a problem report has its own heading and field label, starts with what went
/// wrong already in the message, and is sent with `kind: "problem"`.
enum FeedbackSheetMode: Equatable {
    case feedback
    /// `initialMessage` is built by the door from strings the person can read
    /// on the failure pane. It must carry no path, folder name or engine output,
    /// because it is sent as their message.
    case problem(initialMessage: String)
}

extension FeedbackSheetMode {
    /// The longest prefill a page may hand the sheet; longer is cut, never
    /// refused. The same number as `PROBLEM_REPORT_MESSAGE_LIMIT` in
    /// `frontend/src/shims/bridge.ts`.
    static let problemMessageLimit = 1200

    /// `open-feedback`'s `data` as a journey. A problem report only for exactly
    /// `kind: "problem"` with a message that isn't blank; anything else, and no
    /// data at all (the status page's footer link), is feedback.
    static func fromBridge(_ data: [String: Any]?) -> FeedbackSheetMode {
        guard data?["kind"] as? String == "problem",
              let message = data?["message"] as? String,
              !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else { return .feedback }
        return .problem(initialMessage: String(message.prefix(problemMessageLimit)))
    }
}

// MARK: - View model

@MainActor
final class FeedbackSheetModel: ObservableObject {
    enum Phase { case loading, ready, sending }

    @Published var phase: Phase = .loading
    // An edit after a failed send takes the failure line away: it describes
    // the text as it was sent, so "it's on the clipboard" stops being true.
    @Published var rating: FeedbackRating? { didSet { failure = nil } }
    @Published var message: String = "" { didSet { failure = nil } }
    @Published private(set) var config: FeedbackConfig = .unavailable
    /// The sentence a failed send leaves in the sheet: it wasn't sent, where
    /// the copy is, and where to paste it (R80). Nil until a send fails;
    /// cleared when the next one starts. A cancelled send sets nothing.
    @Published private(set) var failure: String?

    /// Posts a payload and answers sent/failed. A seam so a test can hold a
    /// send in flight; the app always passes `FeedbackClient().submit`.
    typealias Sender = (FeedbackPayload, URL) async -> SubmissionResult

    private let port: Int
    private let i18n: I18n
    private let sender: Sender
    /// Writes the clipboard fallback and answers whether it took. A seam for
    /// the same reason; the app always writes `NSPasteboard.general`.
    private let copy: @MainActor (String) -> Bool
    private let bundleVersion: String
    /// True when `config` was supplied directly (no `/api/health` probe) — the
    /// serve-free path used by the expired-alpha `.dmg` flow.
    private let preresolved: Bool
    let mode: FeedbackSheetMode

    init(
        port: Int,
        i18n: I18n,
        mode: FeedbackSheetMode = .feedback,
        sender: @escaping Sender = { await FeedbackClient().submit($0, to: $1) },
        copy: @escaping @MainActor (String) -> Bool = FeedbackSheetModel.copyToPasteboard,
        bundleVersion: String = Bundle.main.infoDictionary?["CFBundleShortVersionString"]
            as? String ?? "unknown"
    ) {
        self.port = port
        self.i18n = i18n
        self.mode = mode
        self.sender = sender
        self.copy = copy
        self.bundleVersion = bundleVersion
        self.preresolved = false
        prefill()
    }

    /// Serve-free init: `config` supplied directly, no `/api/health` probe. For
    /// contexts with no running sidecar (the expired-alpha `.dmg` flow).
    init(
        config: FeedbackConfig,
        i18n: I18n,
        mode: FeedbackSheetMode = .feedback,
        sender: @escaping Sender = { await FeedbackClient().submit($0, to: $1) },
        copy: @escaping @MainActor (String) -> Bool = FeedbackSheetModel.copyToPasteboard,
        bundleVersion: String = Bundle.main.infoDictionary?["CFBundleShortVersionString"]
            as? String ?? "unknown"
    ) {
        self.port = 0
        self.i18n = i18n
        self.mode = mode
        self.sender = sender
        self.copy = copy
        self.bundleVersion = bundleVersion
        self.config = config
        self.preresolved = true
        prefill()
    }

    /// A problem report opens with what went wrong already in the message, a
    /// blank line under it, and the cursor there; the person can read, edit or
    /// delete it before sending. The trailing lines are trimmed on send.
    private func prefill() {
        if case .problem(let initial) = mode { message = initial + "\n\n" }
    }

    var isProblem: Bool {
        if case .problem = mode { return true }
        return false
    }

    /// The heading and field label are the only words that change.
    var headingKey: String { isProblem ? "problemHeading" : "heading" }
    var fieldLabelKey: String { isProblem ? "problemLabel" : "helpUsImprove" }
    /// On the wire only for a problem report; feedback sends no `kind`.
    var payloadKind: String? { isProblem ? "problem" : nil }

    func t(_ key: String) -> String { i18n.t("common.feedback.\(key)") }
    func label(_ rating: FeedbackRating) -> String { i18n.t("common.feedback.\(rating.labelKey)") }
    var cancelLabel: String { i18n.t("common.buttons.cancel") }
    var reportIssueLabel: String { i18n.t("common.footer.reportIssue") }

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
    /// toast, which only a confirmed send has (`t("sent")`). On any failure
    /// the sheet stays open, the typed message is kept (draft retention), the
    /// text is copied to the clipboard, and `failure` says so in the sheet
    /// itself: a toast drawn behind a sheet is not where anyone is looking.
    func send() async -> (dismiss: Bool, toast: String?) {
        // Cancelled before it began: nothing at all, the clipboard included.
        if Task.isCancelled { return (false, nil) }
        guard let rating else { return (false, nil) }
        failure = nil
        // No reachable/validated endpoint (disabled, unreachable, off-host) →
        // clipboard, honouring a disabled config without silently POSTing.
        guard let url = config.url else {
            copyToClipboard(rating: rating)
            return (false, nil)
        }
        phase = .sending
        let payload = FeedbackPayload(
            version: version, rating: rating.rawValue, message: trimmedMessage,
            kind: payloadKind
        )
        let result = await sender(payload, url)
        phase = .ready
        // Cancelled while it was out (Cancel, Esc, the sheet closing): the
        // person has left, so nothing is shown and the clipboard is not
        // touched. A request the server already had cannot be recalled; only
        // what follows it here is dropped.
        if Task.isCancelled { return (false, nil) }
        switch result {
        case .sent:
            return (true, t("sent"))
        case .failed:
            copyToClipboard(rating: rating)
            return (false, nil)
        }
    }

    /// The send in flight, owned here so Cancel can stop it (`cancelSend`).
    private(set) var sendTask: Task<Void, Never>?

    /// Send, and hand the outcome to `deliver`. Cancelled first
    /// (`cancelSend`), the outcome is empty: no toast, no dismiss, and
    /// `send` has written nothing to the clipboard.
    /// One at a time: a second press before the first send has begun (Send
    /// is disabled only once it has) is ignored rather than orphaning it.
    func startSend(then deliver: @escaping @MainActor ((dismiss: Bool, toast: String?)) -> Void) {
        guard sendTask == nil else { return }
        sendTask = Task {
            deliver(await send())
            sendTask = nil
        }
    }

    /// Stop the send in flight, if any, so it has no visible after-effects.
    func cancelSend() {
        sendTask?.cancel()
    }

    private func copyToClipboard(rating: FeedbackRating) {
        let title = isProblem ? "Bristlenose problem report" : "Bristlenose feedback"
        var text = "\(title) (v\(version))\nRating: \(label(rating))\n"
        if !trimmedMessage.isEmpty { text += "Message: \(trimmedMessage)\n" }
        failure = copy(text) ? t("sendFailed") : t("sendFailedNotCopied")
    }

    static func copyToPasteboard(_ text: String) -> Bool {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        return pasteboard.setString(text, forType: .string)
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

    /// `port` is the window's running serve, or nil for none (the serve-free
    /// `.serverless` config). One initialiser for both on purpose: the caller
    /// passes whatever the port is, so a serve starting or stopping while the
    /// sheet is up never swaps it for a different view, whose `onDisappear`
    /// would cancel a send nobody cancelled. The model is made once, from the
    /// port at opening.
    /// `mode` is the journey (`FeedbackSheetMode`), fixed for the sheet's life
    /// like the port.
    init(port: Int?, i18n: I18n, mode: FeedbackSheetMode = .feedback,
         onToast: @escaping (String) -> Void, onSent: (() -> Void)? = nil) {
        _model = StateObject(wrappedValue: port.map { FeedbackSheetModel(port: $0, i18n: i18n, mode: mode) }
            ?? FeedbackSheetModel(config: .serverless, i18n: i18n, mode: mode))
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
    /// A problem report puts the caret under its prefill, so typing adds to it
    /// rather than replacing it (a focused field otherwise selects all).
    @FocusState private var messageFocused: Bool
    @State private var messageSelection: TextSelection?
    @State private var caretPlaced = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(model.t(model.headingKey))
                .font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)

            if model.phase == .loading {
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
            } else {
                form
                if let failure = model.failure {
                    // Above the buttons, like MiroSheet's error line, and with
                    // the place to paste the copy as a link (R80).
                    VStack(alignment: .leading, spacing: 4) {
                        Text(failure)
                            .font(.callout)
                            .foregroundStyle(.red)
                            .fixedSize(horizontal: false, vertical: true)
                        Link(model.reportIssueLabel, destination: FeedbackEndpoint.issuesURL)
                            .font(.callout)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }

            // In every phase, so Cancel (and Esc, its shortcut) is there while
            // the sheet waits on `/api/health` too. It lived inside `form`, which
            // is not drawn until that probe answers, and a wedged serve kept the
            // sheet on a bare spinner for up to URLSession's 60 s (R81). Send
            // stays disabled until the probe resolves (`canSend`).
            buttons
        }
        .padding(20)
        .frame(width: sheetWidth)
        .task { await model.load() }
        // The form is drawn once the health probe answers, so focus waits for it.
        .onChange(of: model.phase) { _, phase in
            // Once: a failed send returns to `.ready` too, and must leave the
            // caret where the person put it.
            guard phase == .ready, model.isProblem, !caretPlaced else { return }
            caretPlaced = true
            // One turn later: this change also inserts the field, and a focus
            // or selection written in the pass that creates it can be dropped,
            // or overridden by the field selecting all as it takes focus.
            Task { @MainActor in
                messageFocused = true
                messageSelection = TextSelection(insertionPoint: model.message.endIndex)
            }
        }
        // VoiceOver does not read a line that appears on its own, and focus
        // stays on Send, so say the failure (the web modal's role="alert").
        .onChange(of: model.failure) { _, failure in
            if let failure { AccessibilityNotification.Announcement(failure).post() }
        }
        // However the sheet goes (Cancel, Esc, its window closing), a send
        // still out must not toast, copy or confirm after it.
        .onDisappear { model.cancelSend() }
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

            Text(model.t(model.fieldLabelKey))
                .font(.callout)
                .foregroundStyle(.secondary)

            TextField(
                "",
                text: $model.message,
                selection: $messageSelection,
                prompt: Text(model.t("placeholder")),
                axis: .vertical
            )
            .focused($messageFocused)
            .textFieldStyle(.roundedBorder)
            .lineLimit(5...14)
            .disabled(model.phase == .sending)

            Text(model.t("anonymous"))
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var buttons: some View {
        HStack {
            // The stock in-flight pattern: a small spinner and "Sending…"
            // beside the disabled Send, for as long as the request is out.
            // The wait is URLSession's default (up to 60 s): a shorter one
            // waits on the owner (decisions #49, #59), so R80 only makes the
            // waiting visible.
            if model.phase == .sending {
                ProgressView().controlSize(.small)
                Text(model.t("sending"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Button(model.cancelLabel) { model.cancelSend(); dismiss() }
                .keyboardShortcut(.cancelAction)
            Button(model.t("send")) { model.startSend(then: deliver) }
                .keyboardShortcut(.defaultAction)
                .disabled(!model.canSend)
        }
    }

    private func deliver(_ outcome: (dismiss: Bool, toast: String?)) {
        // Suppress the redundant "sent" toast when a caller owns the success
        // confirmation itself (onSent wired → the expiry flow's "Thanks" step).
        // A failed send has no toast: the sheet says it (`model.failure`).
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
