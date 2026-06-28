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
    // Connected-account identity (from /v1/oauth-token via the server). userName =
    // account holder; teamName = the workspace new boards land in. Both nil if the
    // sidecar predates the feature or Miro identity couldn't be fetched.
    @Published private(set) var userName: String?
    @Published private(set) var teamName: String?
    @Published private(set) var orgName: String?  // company — Enterprise only

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
    func dt(_ key: String, _ vars: [String: String]) -> String { i18n.t("desktop.miro.\(key)", vars) }

    /// "Account holder · Workspace" for the configure screen — whichever parts the
    /// server returned. nil when neither is known (older sidecar / fetch failed),
    /// so the Account row hides entirely rather than showing an empty label.
    func accountText() -> String? {
        // De-dupe: a personal/free account returns organization.name == team.name
        // ("martin · Dev team · Dev team"), so drop a part already shown
        // (case-insensitive, order preserved).
        var seen = Set<String>()
        let parts = [userName, teamName, orgName]
            .compactMap { $0?.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty && seen.insert($0.lowercased()).inserted }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    /// Upload notice — names the destination workspace when known ("Creates a new
    /// board in <team>. …") so the safety-critical fact sits right above Create
    /// board; falls back to the plain notice when the team isn't known. The team
    /// is picked out (semibold + primary) against the secondary notice. Built as
    /// an AttributedString so the emphasis lands only on the team run and honours
    /// each locale's word order (the {{team}} slot moves: "… dans {{team}}." /
    /// "{{team}}に…").
    func noticeText() -> AttributedString {
        let upload = AttributedString(t("uploadNotice"))
        guard let team = teamName, !team.isEmpty else { return upload }
        let template = dt("boardDestination")  // localised, contains "{{team}}"
        var line = AttributedString()
        if let r = template.range(of: "{{team}}") {
            line += AttributedString(String(template[..<r.lowerBound]))
            var teamRun = AttributedString(team)
            teamRun.font = .subheadline.weight(.semibold)
            teamRun.foregroundColor = .primary
            line += teamRun
            line += AttributedString(String(template[r.upperBound...]))
        } else {
            line += AttributedString(template.replacingOccurrences(of: "{{team}}", with: team))
        }
        line += AttributedString(" ")
        line += upload
        return line
    }

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
        let conn = await api.status()
        userName = conn.userName
        teamName = conn.teamName
        orgName = conn.orgName
        step = conn.connected ? .configure : .connect
    }

    func connect() async {
        let pasted = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !pasted.isEmpty else { return }
        busy = true
        error = nil
        do {
            let conn = try await api.connect(token: pasted)
            userName = conn.userName
            teamName = conn.teamName
            orgName = conn.orgName
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
        userName = nil
        teamName = nil
        orgName = nil
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
            Text(model.t("title")).font(.headline)
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
            Text(model.t("title")).font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)
            // Right-aligned colon labels + left-aligned controls (Pages Export-
            // dialog form). `.gridColumnAlignment(.trailing)` on the first cell
            // right-aligns the whole label column. Status + account lead so the
            // user confirms WHICH Miro account/workspace before creating a board.
            // The stand-alone Link-clips checkbox gets an empty label cell so it
            // indents to the control column (Pages' "Include comments" rows).
            Grid(alignment: .leading, horizontalSpacing: 8, verticalSpacing: 12) {
                GridRow(alignment: .firstTextBaseline) {
                    Text(model.dt("miroStatusLabel"))
                        .foregroundStyle(.secondary)
                        .gridColumnAlignment(.trailing)
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark.circle").foregroundStyle(.green)
                        Text(model.dt("connected"))
                        Spacer()
                        Button(model.t("disconnect")) { Task { await model.disconnect() } }
                            .controlSize(.small).disabled(model.busy)
                    }
                }
                if let account = model.accountText() {
                    GridRow(alignment: .firstTextBaseline) {
                        Text(model.dt("accountLabel")).foregroundStyle(.secondary)
                        Text(account)
                    }
                }
                GridRow(alignment: .firstTextBaseline) {
                    Text(model.dt("boardNameLabel"))
                        .foregroundStyle(.secondary)
                    TextField(model.t("boardNamePlaceholder"), text: $model.boardName)
                        .textFieldStyle(.roundedBorder)
                }
                GridRow(alignment: .firstTextBaseline) {
                    Text(model.dt("stickyColoursLabel"))
                        .foregroundStyle(.secondary)
                    Toggle(model.t("colourBySentiment"), isOn: $model.colourBySentiment)
                }
                GridRow(alignment: .top) {
                    Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                    VStack(alignment: .leading, spacing: 4) {
                        Toggle(model.t("linkClipsLabel"), isOn: $model.linkClips)
                        Text(model.t("linkClipsHint")).font(.subheadline).foregroundStyle(.secondary)
                        if model.linkClips {
                            TextField(model.t("clipsBasePlaceholder"), text: $model.clipsBase)
                                .textFieldStyle(.roundedBorder)
                        }
                    }
                }
            }
            Text(model.noticeText()).font(.subheadline).foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
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
