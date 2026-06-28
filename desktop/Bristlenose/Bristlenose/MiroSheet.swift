import AppKit
import SwiftUI

/// Native "Send to Miro" sheet — the macOS rendering of the flow the web panel
/// (`MiroExportPanel.tsx`) presents. Presentation only: every call goes through
/// `MiroAPI` to the same Python REST endpoints (the agnostic board IR, layout,
/// validation, and egress boundary stay server-side). See docs/design-miro-bridge.md
/// "macOS native entry" + docs/mockups/miro-native-flow.html.
///
/// One constant size across steps (HIG: sheets aren't resized per step). The
/// 10–30s board push runs in a modal "Creating board…" state with Cancel
/// (stress-test gate: ~3000 stickies / <30s, else move to a background job).

// MARK: - View model

@MainActor
final class MiroSheetModel: ObservableObject {
    enum Step { case loading, connect, configure, creating, done }

    @Published var step: Step = .loading
    @Published var token = ""
    @Published var boardName: String
    @Published var colourBySentiment = true
    @Published var linkClips = false
    @Published var clipsBase = ""
    @Published var busy = false
    @Published var error: String?
    @Published private(set) var boardURL: String?
    @Published private(set) var stickies = 0

    private let api: MiroAPI
    private let i18n: I18n
    private var exportTask: Task<Void, Never>?

    init(port: Int, token: String?, projectName: String, i18n: I18n) {
        self.api = MiroAPI(port: port, token: token)
        self.i18n = i18n
        self.boardName = projectName  // prefilled, editable
    }

    func t(_ key: String) -> String { i18n.t("common.miro.\(key)") }

    /// Desktop-only override of a `miro.*` string — used where the native sheet
    /// must drop a web idiom the shared `common.miro` string carries (the `↗` /
    /// `✓` glyphs, the "Open in Miro…" ellipsis). Lives in `desktop.miro.*`.
    func dt(_ key: String) -> String { i18n.t("desktop.miro.\(key)") }

    /// "Board ready — N quote stickies placed", count-correct, with a fallback to
    /// the `_other` form for plural categories a locale doesn't define (e.g. cs `few`).
    func boardReadyText() -> String {
        let cat = i18n.pluralCategory(stickies)
        let key = "common.miro.boardReady_\(cat)"
        let s = i18n.t(key, ["count": String(stickies)])
        if s == key {
            return i18n.t("common.miro.boardReady_other", ["count": String(stickies)])
        }
        return s
    }

    func load() async {
        step = .loading
        error = nil
        step = await api.status() ? .configure : .connect
    }

    func connect() async {
        let pasted = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !pasted.isEmpty else { return }
        busy = true
        error = nil
        do {
            _ = try await api.connect(token: pasted)
            // Persist natively so it survives relaunch under the sandbox (Python
            // can't write the Keychain). Read back on launch by overlayMiroToken.
            // The session is live regardless, so a failed write warns (non-blocking)
            // rather than aborting — otherwise a silent "Connected" would lie at the
            // next launch when the env-injected key isn't there.
            if !KeychainHelper.set(provider: "miro", value: pasted) {
                self.error = dt("connectPersistWarning")
            }
            step = .configure
        } catch {
            self.error = (error as? MiroAPI.APIError)?.message ?? t("connectError")
        }
        busy = false
    }

    func disconnect() async {
        busy = true
        error = nil
        await api.disconnect()
        KeychainHelper.delete(provider: "miro")  // also clear the Swift-stored copy
        token = ""
        step = .connect
        busy = false
    }

    func createBoard() {
        step = .creating
        error = nil
        exportTask = Task {
            do {
                let result = try await api.export(
                    boardName: boardName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        ? nil : boardName.trimmingCharacters(in: .whitespacesAndNewlines),
                    colourBy: colourBySentiment ? "sentiment" : "none",
                    clipsBase: linkClips ? clipsBase.trimmingCharacters(in: .whitespacesAndNewlines) : ""
                )
                if Task.isCancelled { return }
                self.boardURL = result.boardURL
                self.stickies = result.stickies
                self.step = .done
            } catch is CancellationError {
                // User cancelled the wait; server-side push may still finish.
            } catch {
                self.error = (error as? MiroAPI.APIError)?.message ?? t("exportError")
                self.step = .configure
            }
        }
    }

    func cancelExport() { exportTask?.cancel() }

    func openBoard() {
        // board_url comes from the server (transitively from Miro's authenticated
        // API), but guard the scheme at the NSWorkspace.open sink anyway — this is
        // the native path, so it doesn't pass through WebView's scheme allowlist.
        guard let boardURL, let url = URL(string: boardURL),
              let scheme = url.scheme?.lowercased(), scheme == "https" || scheme == "http"
        else { return }
        NSWorkspace.shared.open(url)
    }

    func openTokenHelp() {
        if let url = URL(string: "https://bristlenose.app/docs/send-to-miro.html") {
            NSWorkspace.shared.open(url)
        }
    }
}

// MARK: - Sheet

struct MiroSheet: View {
    @StateObject private var model: MiroSheetModel
    @Environment(\.dismiss) private var dismiss

    init(port: Int, token: String?, projectName: String, i18n: I18n) {
        _model = StateObject(wrappedValue: MiroSheetModel(
            port: port, token: token, projectName: projectName, i18n: i18n
        ))
    }

    // Constant size across every step (HIG: sheets keep one size through a flow —
    // cf. Pages' Export dialog, which stays fixed across all 7 tabs and lets the
    // sparse tabs show whitespace). Sized to the tallest step (configure with the
    // clips field + an error line, longest locale); shorter steps centre/​top-align
    // within it and pin their buttons to the bottom. minHeight (not fixed) so an
    // unusually long localisation grows rather than clips.
    private let sheetWidth: CGFloat = 460
    private let sheetMinHeight: CGFloat = 400

    var body: some View {
        Group {
            switch model.step {
            case .loading: loading
            case .connect: connect
            case .configure: configure
            case .creating: creating
            case .done: done
            }
        }
        .padding(20)
        .frame(width: sheetWidth)
        .frame(minHeight: sheetMinHeight)
        .task { await model.load() }
    }

    // MARK: states

    private var loading: some View {
        VStack(spacing: 10) {
            Spacer()
            ProgressView()
            Text(model.t("checkingConnection")).font(.subheadline).foregroundStyle(.secondary)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    private var connect: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(model.t("title")).font(.title2).fontWeight(.bold)
                .frame(maxWidth: .infinity, alignment: .center)
            Text(model.t("connectIntro")).font(.callout).foregroundStyle(.secondary)
            SecureField(model.t("tokenPlaceholder"), text: $model.token)
                .textFieldStyle(.roundedBorder)
            if let error = model.error {
                Text(error).font(.callout).foregroundStyle(.red)
            }
            Spacer(minLength: 16)
            HStack {
                // Footer help (Pages Export-dialog pattern) — opens the token docs;
                // the old inline link's text becomes the hover tooltip.
                HelpLink { model.openTokenHelp() }
                    .help(model.dt("howToGetToken"))
                Spacer()
                Button(model.t("cancel")) { dismiss() }.keyboardShortcut(.cancelAction)
                Button(model.t("connect")) { Task { await model.connect() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(model.busy || model.token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var configure: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(model.t("title")).font(.title2).fontWeight(.bold)
                .frame(maxWidth: .infinity, alignment: .center)
            HStack(spacing: 5) {
                Text(model.dt("connected")).font(.subheadline).foregroundStyle(.secondary)
                Text(verbatim: "·").font(.subheadline).foregroundStyle(.secondary)
                Button(model.t("disconnect")) { Task { await model.disconnect() } }
                    .buttonStyle(.plain).font(.subheadline).foregroundStyle(.secondary)
                    .inlineLinkCursor().disabled(model.busy)
            }
            .frame(maxWidth: .infinity, alignment: .center)
            VStack(alignment: .leading, spacing: 4) {
                Text(model.t("boardNameLabel")).font(.subheadline).foregroundStyle(.secondary)
                TextField(model.t("boardNamePlaceholder"), text: $model.boardName)
                    .textFieldStyle(.roundedBorder)
            }
            Toggle(model.t("colourBySentiment"), isOn: $model.colourBySentiment)
            VStack(alignment: .leading, spacing: 4) {
                Toggle(model.t("linkClipsLabel"), isOn: $model.linkClips)
                Text(model.t("linkClipsHint")).font(.subheadline).foregroundStyle(.secondary)
                if model.linkClips {
                    TextField(model.t("clipsBasePlaceholder"), text: $model.clipsBase)
                        .textFieldStyle(.roundedBorder)
                }
            }
            Text(model.t("uploadNotice")).font(.subheadline).foregroundStyle(.secondary)
            if let error = model.error {
                Text(error).font(.callout).foregroundStyle(.red)
            }
            Spacer(minLength: 16)
            HStack {
                HelpLink { model.openTokenHelp() }
                    .help(model.dt("howToGetToken"))
                Spacer()
                Button(model.t("cancel")) { dismiss() }.keyboardShortcut(.cancelAction)
                Button(model.t("createBoard")) { model.createBoard() }
                    .keyboardShortcut(.defaultAction).disabled(model.busy)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var creating: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(model.t("creatingBoard")).font(.headline)
            Spacer()
            ProgressView().frame(maxWidth: .infinity)
            Spacer()
            HStack {
                Spacer()
                Button(model.t("cancel")) { model.cancelExport(); dismiss() }
                    .keyboardShortcut(.cancelAction)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var done: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "checkmark.circle")
                .font(.system(size: 34))
                .foregroundStyle(.green)
            Text(model.boardReadyText())
                .font(.headline).fontWeight(.regular)
                .multilineTextAlignment(.center)
            Spacer()
            HStack {
                Spacer()
                Button(model.t("done")) { dismiss() }.keyboardShortcut(.cancelAction)
                Button(model.dt("openInMiro")) { model.openBoard(); dismiss() }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Inline clickable-text affordance

private extension View {
    /// Native inline-link affordance per the no-web-idioms rule: a pointing-hand
    /// cursor on hover, no anchor-blue, no underline, no background fill. Pair with
    /// `.buttonStyle(.plain)` on text buttons that open help / disconnect.
    func inlineLinkCursor() -> some View {
        onHover { inside in
            if inside { NSCursor.pointingHand.push() } else { NSCursor.pop() }
        }
    }
}
