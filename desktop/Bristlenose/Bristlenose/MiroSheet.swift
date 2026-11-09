import AppKit
import SwiftUI

/// Native "Send to Miro" sheet — the macOS rendering of the flow the web panel
/// (`MiroExportPanel.tsx`) presents. Presentation only: every call goes through
/// `MiroAPI` to the same Python REST endpoints (the agnostic board IR, layout,
/// validation, and egress boundary stay server-side). See docs/design-miro-bridge.md
/// "macOS native entry" + docs/archive/mockups/miro-native-flow.html.
///
/// Two routes for the quotes board, as a segmented control (owner, 9 Nov 2026;
/// docs/mockups/miro-board-file-route.html): **Miro app**, always the one it opens on, copies or
/// saves the board file the Bristlenose app inside Miro draws (miro-app/, no sign-in, no token);
/// **Developer access token** is the REST push below, unchanged. The screens board has only the
/// token route: a board file carries no screengrabs.
///
/// One constant size across steps (HIG: sheets aren't resized per step). The
/// board is built as a job on the server (both boards, since 18 Oct 2026): the
/// creating step says what is being counted, shows a bar once there is an honest
/// fraction and a time left once one is earned, and Cancel stops the build there.

// MARK: - View model

@MainActor
final class MiroSheetModel: ObservableObject {
    enum Step { case loading, connect, configure, creating, done }
    enum Route: Hashable { case app, token }

    @Published var step: Step = .loading
    /// The quotes board's route. Always opens on the Miro app, even for someone connected with a
    /// token: it is the better route (owner, 9 Nov 2026). The screens board is token-only.
    @Published var route: Route
    /// The Miro app route: what was last copied or saved, kept with the choices it was made under,
    /// so "Copied" and the saved line hold only while those choices still do.
    @Published private(set) var copiedFor: String?
    @Published private(set) var savedFor: (choices: String, quotes: Int)?
    @Published private(set) var fileBusy = false
    @Published var fileError: String?
    @Published var token = ""
    @Published var boardName: String
    /// Flat by default on every board (owner, 19 Oct 2026); sentiment is offered.
    @Published var colourBySentiment = false
    @Published var linkClips = false
    /// On by default and shown, so a researcher arriving at the board knows why a long quote runs
    /// over two or three stickies (owner, 17 Oct 2026).
    @Published var splitLongQuotes = true
    /// Rectangle by default: a dense board, a quote in longer lines; square is offered.
    @Published var stickyShape = "rectangle"
    @Published var clipsBase = ""
    @Published var busy = false
    @Published var error: String?
    @Published private(set) var boardURL: String?
    @Published private(set) var stickies = 0
    /// Screens the screens board could not show; said under the done line.
    @Published private(set) var skipped = 0
    /// How far the build has got, from the server's job status; nil before the first read.
    @Published private(set) var build: MiroBoardBuild?
    // Connected-account identity (from /v1/oauth-token via the server). userName =
    // account holder; teamName = the workspace new boards land in. Both nil if the
    // sidecar predates the feature or Miro identity couldn't be fetched.
    @Published private(set) var userName: String?
    @Published private(set) var teamName: String?
    @Published private(set) var orgName: String?  // company — Enterprise only

    private let api: MiroAPI
    private let i18n: I18n
    private let projectName: String
    /// The board file and its quote count (the FigJam export's route). Injected so a test needs
    /// no server.
    var fetchBoard: (FigJamAPI.Options) async throws -> (data: Data, quotes: Int)
    /// Where a saved board file goes: the stock save panel, which also grants the sandbox write.
    var chooseDestination: (String) async -> URL?
    /// Puts the board on the pasteboard; false if it could not. Injected so a test can read it.
    var writePasteboard: (_ html: String, _ json: String) -> Bool = MiroSheetModel.generalPasteboard
    private var fileTask: Task<Void, Never>?
    /// Readable so a test can wait for a build to end (`MiroSheetStatusTests`).
    private(set) var exportTask: Task<Void, Never>?
    /// Opened on the Screens lens: the board is the screens, a frame per screengrab
    /// (docs/design-screens-export.md §6), not the quotes in section columns.
    let screens: Bool
    /// Clip links are parked (`BristlenoseFlags.boardClipLinks`): off, the choice is not shown
    /// and no folder is sent.
    let clipLinksOffered: Bool

    init(port: Int, token: String?, projectName: String, i18n: I18n, screens: Bool = false,
         clipLinksOffered: Bool = BristlenoseFlags.boardClipLinks) {
        self.api = MiroAPI(port: port, token: token)
        self.i18n = i18n
        self.screens = screens
        self.clipLinksOffered = clipLinksOffered
        self.projectName = projectName
        self.route = screens ? .token : .app
        let fileAPI = FigJamAPI(port: port, token: token)
        self.fetchBoard = { try await fileAPI.fetchBoard($0) }
        self.chooseDestination = FigJamSheetModel.savePanel
        // Prefilled with what the board would be called anyway, editable (owner, 17 Oct 2026).
        self.boardName = screens
            ? "\(projectName) · \(i18n.t("common.screens.title"))" : projectName
    }

    func t(_ key: String) -> String { i18n.t("common.miro.\(key)") }

    /// An `APIError`'s sentence in the reader's language: its key when the
    /// sentence is ours, its raw `message` when it is the server's own detail,
    /// and `nil` when it is not an `APIError` at all — which leaves the caller's
    /// own fallback in place, as before.
    static func text(for error: Error, _ i18n: I18n) -> String? {
        guard let api = error as? MiroAPI.APIError else { return nil }
        guard let key = api.localeKey else { return api.message }
        let text = i18n.t(key, api.localeVars)
        // A partial board carries its own address in `vars.url`. The localised
        // sentence says to open it; without the address that is an instruction
        // nobody can follow, and the raw `detail` used to carry it. Append it
        // rather than interpolate — the key has no `{{url}}` slot, and adding
        // one is a 21-locale change for a link that reads the same in each.
        if let url = api.localeVars["url"], !url.isEmpty { return text + " " + url }
        return text
    }

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
        let upload = AttributedString(t(screens ? "screensUploadNotice" : "uploadNotice"))
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

    /// "Board ready — N quote stickies placed", count-correct. Plural selection
    /// and the `_other` fallback for an absent stem both live in `I18n.plural`.
    func boardReadyText() -> String {
        i18n.plural(screens ? "common.export.screens.done" : "common.miro.boardReady", count: stickies)
    }

    /// "Screengrabs written: 7 of 9", when a screen's still could not be made; nil otherwise.
    func partialText() -> String? {
        guard skipped > 0 else { return nil }
        return i18n.t("common.export.screens.partial",
                      ["written": String(stickies), "total": String(stickies + skipped)])
    }

    func load() async {
        step = .loading
        error = nil
        let conn: MiroAPI.Connection
        do {
            conn = try await api.status()
        } catch is CancellationError {
            return
        } catch {
            // The sheet closed mid-load: URLSession throws on our own cancel, and an
            // "unreachable" line written now would be for nobody (as in `follow`).
            if Task.isCancelled { return }
            // Could not tell is not signed out (R78): Connect stays, and its error line says why.
            step = .connect
            self.error = Self.text(for: error, i18n) ?? t("connectError")
            return
        }
        userName = conn.userName
        teamName = conn.teamName
        orgName = conn.orgName
        // Cache the display line for Settings ▸ Accounts, which cannot fetch it
        // — the identity is an HTTP call through a running sidecar, and that
        // pane can be open with no serve at all. Display strings only.
        MiroConnectionStore.remember(conn)
        step = conn.connected ? .configure : .connect
        // A board still being built when the sheet was closed is picked up again, not lost.
        if conn.connected, await api.boardIsBuilding(screens: screens) {
            route = .token  // its progress belongs to the token route
            follow { api, onProgress in try await api.resumeBoard(screens: self.screens, onProgress: onProgress) }
        }
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
            MiroConnectionStore.remember(conn)
            step = .configure
        } catch {
            self.error = Self.text(for: error, i18n) ?? t("connectError")
        }
        busy = false
    }

    /// Disconnect through the one shared sequence.
    ///
    /// This was four steps inline — API, Keychain, identity, prefs-changed —
    /// duplicating `MiroConnectionStore.disconnect` step for step. Two surfaces
    /// performing one irreversible act must not be two sequences: the fourth
    /// step was missing here until 18 Aug 2026, and a running serve kept
    /// exporting to the board the researcher had just disconnected from. The
    /// reasoning for each step now lives once, at the shared implementation.
    ///
    /// The caller dismisses the sheet afterwards — see `MiroSheet`.
    func disconnect() async {
        busy = true
        error = nil
        await MiroConnectionStore.disconnect(api: api)
        token = ""
        userName = nil
        teamName = nil
        orgName = nil
        step = .connect
        busy = false
    }

    func createBoard() {
        // Read the locale here, not inside the Task: `I18n` is `@MainActor` and
        // the board should carry the language the sheet was filled in with.
        let locale = i18n.locale
        let name = boardName.trimmingCharacters(in: .whitespacesAndNewlines)
        let colourBy = colourBySentiment ? "sentiment" : "none"
        let clips = clipLinksOffered && linkClips
            ? clipsBase.trimmingCharacters(in: .whitespacesAndNewlines) : ""
        let (screens, split, shape) = (self.screens, splitLongQuotes, stickyShape)
        follow { api, onProgress in
            screens
                ? try await api.exportScreens(boardName: name.isEmpty ? nil : name, colourBy: colourBy,
                                              locale: locale, splitLongQuotes: split, stickyShape: shape,
                                              onProgress: onProgress)
                : try await api.export(boardName: name.isEmpty ? nil : name, colourBy: colourBy,
                                       clipsBase: clips, locale: locale, splitLongQuotes: split,
                                       stickyShape: shape, onProgress: onProgress)
        }
    }

    /// Run a build — a new one or one already running — showing its progress until it ends.
    private func follow(_ run: @escaping (MiroAPI, @escaping MiroAPI.ProgressHandler) async throws
                        -> MiroAPI.ExportResult) {
        step = .creating
        error = nil
        build = nil
        let api = self.api
        exportTask = Task {
            do {
                let result = try await run(api) { [weak self] b in self?.build = b }
                if Task.isCancelled { return }
                self.boardURL = result.boardURL
                self.stickies = result.stickies
                self.skipped = result.skipped
                self.step = .done
            } catch is CancellationError {
                // Our own Cancel: the server was asked to stop after the call in hand, the board
                // keeps what it has, and the sheet is going away. A stop nobody here asked for (the
                // build stopped elsewhere, or the sidecar restarted and forgot it) hands the form
                // back rather than leaving the bar frozen.
                if !Task.isCancelled { self.step = .configure }
            } catch {
                // Our own Cancel during a request: URLSession throws URLError(.cancelled), not
                // CancellationError, and an error written now would be for a sheet that is gone.
                if Task.isCancelled { return }
                self.error = Self.text(for: error, i18n) ?? t("exportError")
                self.step = .configure
            }
        }
    }

    /// The creating step's line, bar and time left (`MiroBoardBuildText`, shared with the web).
    func buildLine() -> String { MiroBoardBuildText.line(build) { self.i18n.t($0, $1) } }
    func buildFraction() -> Double? { MiroBoardBuildText.fraction(build) }
    func buildETA() -> String? {
        MiroBoardBuildText.eta(build, localize: { self.i18n.t($0, $1) },
                               pluralize: { self.i18n.plural($0, count: $1) })
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

    // MARK: Miro app route

    /// The Bristlenose app's install page on Miro (its Installation URL): pick a team, Add &
    /// allow. A company admin approves the app by the client ID in it. Same as the web panel's.
    static let miroAppInstallURL = URL(string:
        "https://miro.com/app-install/?response_type=code&client_id=3458764676772092122&redirect_uri=%2Fapp-install%2Fconfirm%2F")!

    /// Each route's help page, opened by the sheet's HelpLink.
    static func helpURL(_ route: Route) -> URL {
        URL(string: route == .app ? "https://bristlenose.app/docs/miro-app.html"
                                  : "https://bristlenose.app/docs/send-to-miro.html")!
    }

    func openHelp() { NSWorkspace.shared.open(Self.helpURL(route)) }

    /// The choices a board file is made under: a change makes a different board.
    var fileChoices: String { "\(splitLongQuotes)|\(stickyShape)|\(i18n.locale)" }
    var copied: Bool { copiedFor == fileChoices }
    func savedText() -> String? {
        guard let saved = savedFor, saved.choices == fileChoices else { return nil }
        return i18n.plural("common.figjam.saved", count: saved.quotes)
    }

    /// The board file the in-Miro app reads: named after the project (an empty name), with the two
    /// choices it honours, and no clip links (parked).
    func fileOptions() -> FigJamAPI.Options {
        FigJamAPI.Options(boardName: "", locale: i18n.locale, splitLongQuotes: splitLongQuotes,
                          square: stickyShape == "square", clipsBase: "")
    }

    /// A sentence with a slot or two ("Once: {{link}}", "Either {{download}} or {{copy}}"),
    /// split on its placeholders so each language can put the controls where its grammar wants
    /// them. Even indices are text, odd ones slot names.
    static func slots(_ template: String) -> [String] {
        var parts: [String] = []
        var rest = Substring(template)
        while let open = rest.range(of: "{{"), let close = rest.range(of: "}}", range: open.upperBound..<rest.endIndex) {
            parts.append(String(rest[..<open.lowerBound]))
            parts.append(String(rest[open.upperBound..<close.lowerBound]))
            rest = rest[close.upperBound...]
        }
        parts.append(String(rest))
        return parts
    }

    /// The install link's words without the web's ↗: a native link needs no glyph to say it opens
    /// the browser (the `desktop.miro.*` overrides drop the same glyph elsewhere in this sheet).
    func addAppLinkText() -> String {
        t("appAddLink").replacingOccurrences(of: "↗", with: "").trimmingCharacters(in: .whitespaces)
    }

    func copyBoard() {
        runFile { model, board in
            guard let json = String(data: board.data, encoding: .utf8),
                  model.writePasteboard(Self.pasteboardHTML(json: json, title: model.projectName), json)
            else {
                model.fileError = model.t("copyFailed")
                return
            }
            model.copiedFor = model.fileChoices
        }
    }

    func saveBoard() {
        runFile { model, board in
            guard let url = await model.chooseDestination(model.suggestedFilename()) else { return }
            do {
                try board.data.write(to: url, options: .atomic)
                model.savedFor = (model.fileChoices, board.quotes)
            } catch {
                model.fileError = model.i18n.t("common.figjam.error")
            }
        }
    }

    /// The name the save panel offers.
    func suggestedFilename() -> String {
        let safe = projectName.replacingOccurrences(of: "/", with: "-").replacingOccurrences(of: ":", with: "-")
        return "\(safe.isEmpty ? "Bristlenose" : safe)-miro-board.json"
    }

    func cancelFile() { fileTask?.cancel() }

    /// The Mac's word for the download, as the FigJam sheet says it: a save panel follows.
    func saveBoardFileTitle() -> String { i18n.t("desktop.figjam.saveBoardFile") }

    /// Fetch the board under the current choices, then hand it on; a refusal is said in words.
    private func runFile(_ then: @escaping @MainActor (MiroSheetModel, (data: Data, quotes: Int)) async -> Void) {
        fileError = nil
        copiedFor = nil
        savedFor = nil
        fileBusy = true
        let options = fileOptions()
        fileTask = Task { [weak self] in
            guard let self else { return }
            defer { self.fileBusy = false }
            do {
                let board = try await self.fetchBoard(options)
                if Task.isCancelled { return }
                await then(self, board)
            } catch let e as FigJamAPI.APIError {
                if Task.isCancelled { return }
                self.fileError = self.i18n.t(e.localeKey ?? "common.figjam.error")
            } catch {
                if Task.isCancelled { return }
                self.fileError = self.i18n.t("common.figjam.error")
            }
        }
    }

    /// The HTML flavour the Miro panel and the FigJam plugin read
    /// (`figjam-plugin/src/clipboard.ts`): the board JSON, base64 of its UTF-8 bytes, in a
    /// `data-bristlenose-board` attribute, with the title as the visible text. The same as the web
    /// panel's `boardClipboard.ts`; the plain flavour carries the bare JSON, which both read too.
    static func pasteboardHTML(json: String, title: String) -> String {
        let b64 = Data(json.utf8).base64EncodedString()
        let escaped = title.replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;").replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
        return "<meta charset=\"utf-8\"><div data-bristlenose-board=\"\(b64)\">\(escaped)</div>"
    }

    static func generalPasteboard(html: String, json: String) -> Bool {
        let pb = NSPasteboard.general
        pb.clearContents()
        return pb.setString(html, forType: .html) && pb.setString(json, forType: .string)
    }
}

// MARK: - Sheet

struct MiroSheet: View {
    @StateObject private var model: MiroSheetModel
    @Environment(\.dismiss) private var dismiss
    /// The sheet loads its connection when shown; one handed a model leaves that to its driver.
    private let loadsOnAppear: Bool

    init(port: Int, token: String?, projectName: String, i18n: I18n, screens: Bool = false) {
        _model = StateObject(wrappedValue: MiroSheetModel(
            port: port, token: token, projectName: projectName, i18n: i18n, screens: screens
        ))
        loadsOnAppear = true
    }

    /// The sheet over a model someone else drives — the live board test renders the creating step
    /// at the states a real build passed through (`MiroSheetLiveTests`).
    init(model: MiroSheetModel) {
        _model = StateObject(wrappedValue: model)
        loadsOnAppear = false
    }

    /// Whether Send to Miro is offered: a project window in front, and its report
    /// server up, since the sheet drives serve's endpoints and the window drops
    /// the press without a port (R62).
    static func offered(hasKeyWindow: Bool, runningPort: Int?) -> Bool {
        WindowCommand.showMiro.isEnabled(hasKeyWindow: hasKeyWindow) && runningPort != nil
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
            // A board being built, or just built, has the sheet to itself: no route to switch to.
            case .creating: creating
            case .done: done
            default:
                VStack(alignment: .leading, spacing: 12) {
                    header
                    if model.route == .app {
                        appRoute
                    } else {
                        switch model.step {
                        case .loading: loading
                        case .connect: connect
                        default: configure
                        }
                    }
                }
            }
        }
        .padding(20)
        .frame(width: sheetWidth)
        .frame(minHeight: sheetMinHeight)
        .task { if loadsOnAppear { await model.load() } }
        .onDisappear { model.cancelFile() }
    }

    /// The title, then (quotes board only) the system segmented control that switches route.
    private var header: some View {
        VStack(spacing: 12) {
            Text(model.t(model.screens ? "title" : "quotesTitle")).font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)
            if !model.screens {
                Picker(model.t("quotesTitle"), selection: $model.route) {
                    Text(model.t("tabApp")).tag(MiroSheetModel.Route.app)
                    Text(model.t("tabToken")).tag(MiroSheetModel.Route.token)
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .fixedSize()
                .frame(maxWidth: .infinity, alignment: .center)
            }
        }
    }

    // MARK: Miro app route

    /// The choices first, then the rule, then how to get the board into Miro (owner, 9 Nov 2026):
    /// once add the app, either save or copy the board, then open it from Tools in a board.
    private var appRoute: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle(isOn: $model.splitLongQuotes) {
                Text(model.t("splitLongQuotes")).fixedSize(horizontal: false, vertical: true)
            }
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(model.t("stickyShape")).foregroundStyle(.secondary)
                Picker(model.t("stickyShape"), selection: $model.stickyShape) {
                    Text(model.t("stickyShapeRectangle")).tag("rectangle")
                    Text(model.t("stickyShapeSquare")).tag("square")
                }
                .pickerStyle(.radioGroup)
                .horizontalRadioGroupLayout()
                .labelsHidden()
            }
            Divider()
            slotted(model.t("appStep1")) { _ in
                AnyView(Link(model.addAppLinkText(), destination: MiroSheetModel.miroAppInstallURL))
            }
            slotted(model.t("appEitherOr")) { slot in
                slot == "copy" ? AnyView(copyButton) : AnyView(saveButton)
            }
            Text(model.t("appStep3")).fixedSize(horizontal: false, vertical: true)
            if let saved = model.savedText() {
                Text(saved).font(.subheadline).foregroundStyle(.secondary)
            }
            if let error = model.fileError {
                Text(error).font(.callout).foregroundStyle(.red)
            }
            Spacer(minLength: 16)
            HStack {
                HelpLink { model.openHelp() }
                Spacer()
                Button(model.t("done")) { dismiss() }.keyboardShortcut(.cancelAction)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// Copy is the default button: fewer steps than a file (owner, 9 Nov 2026). It says "Copied"
    /// in its own place, both titles stacked so the button keeps the wider one's width.
    private var copyButton: some View {
        Button { model.copyBoard() } label: {
            ZStack {
                Text(model.t("copyBoard")).opacity(model.copied ? 0 : 1)
                Text(model.t("copied")).opacity(model.copied ? 1 : 0)
            }
        }
        .keyboardShortcut(.defaultAction)
        .disabled(model.fileBusy)
        .accessibilityLabel(model.t(model.copied ? "copied" : "copyBoard"))
    }

    private var saveButton: some View {
        Button(model.saveBoardFileTitle()) { model.saveBoard() }
            .disabled(model.fileBusy)
    }

    /// A line whose placeholders are controls, in the order the language puts them. On one line
    /// when it fits; stacked when a language's words and buttons would not (no control is ever
    /// squeezed or cut).
    private func slotted(_ template: String, _ control: @escaping (String) -> AnyView) -> some View {
        let parts = MiroSheetModel.slots(template)
        let pieces = ForEach(Array(parts.enumerated()), id: \.offset) { i, part in
            if i % 2 == 1 {
                control(part)
            } else if !part.trimmingCharacters(in: .whitespaces).isEmpty {
                Text(part.trimmingCharacters(in: .whitespaces)).fixedSize()
            }
        }
        // Stacked, each control keeps the words before it on its line ("Either [Save]" / "or
        // [Copy]"); words after the last control get a line of their own.
        let rows = stride(from: 1, to: parts.count, by: 2).map { (words: parts[$0 - 1], slot: parts[$0]) }
        let tail = parts.last ?? ""
        return ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline, spacing: 6) { pieces }.fixedSize()
            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        let words = row.words.trimmingCharacters(in: .whitespaces)
                        if !words.isEmpty { Text(words) }
                        control(row.slot)
                    }
                }
                if !tail.trimmingCharacters(in: .whitespaces).isEmpty {
                    Text(tail.trimmingCharacters(in: .whitespaces))
                }
            }
        }
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
                        // Dismiss after: disconnecting restarts the serve on a
                        // fresh kernel-assigned port, so this sheet's `MiroAPI`
                        // — built with the old one at init — is dead the moment
                        // it returns. Leaving the sheet up would offer a Connect
                        // field posting into a closed port.
                        Button(model.t("disconnect")) {
                            Task { await model.disconnect(); dismiss() }
                        }
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
                GridRow(alignment: .firstTextBaseline) {
                    Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                    // Long labels wrap rather than truncate (the grid column would cut them to one
                    // line, "Break long quotes into multi…"); the same for the clip-link hint below.
                    Toggle(isOn: $model.splitLongQuotes) {
                        Text(model.t("splitLongQuotes")).fixedSize(horizontal: false, vertical: true)
                    }
                }
                GridRow(alignment: .firstTextBaseline) {
                    Text(model.t("stickyShape")).foregroundStyle(.secondary)
                    Picker(model.t("stickyShape"), selection: $model.stickyShape) {
                        Text(model.t("stickyShapeRectangle")).tag("rectangle")
                        Text(model.t("stickyShapeSquare")).tag("square")
                    }
                    .pickerStyle(.radioGroup)
                    .horizontalRadioGroupLayout()
                    .labelsHidden()
                }
                // Clip links are a quotes-board option; the screens board's stickies carry none.
                // Parked on both (`BristlenoseFlags.boardClipLinks`).
                if !model.screens && model.clipLinksOffered {
                GridRow(alignment: .top) {
                    Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                    VStack(alignment: .leading, spacing: 4) {
                        Toggle(model.t("linkClipsLabel"), isOn: $model.linkClips)
                        Text(model.t("linkClipsHint")).font(.subheadline).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                        if model.linkClips {
                            TextField(model.t("clipsBasePlaceholder"), text: $model.clipsBase)
                                .textFieldStyle(.roundedBorder)
                        }
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
            Text(model.buildLine()).font(.headline)
                .accessibilityAddTraits(.updatesFrequently)
            Spacer()
            // A linear bar throughout, so the indeterminate phases (screenshots being made, the
            // board opening) turn determinate in place rather than swapping a spinner for a bar.
            Group {
                if let fraction = model.buildFraction() {
                    ProgressView(value: fraction)
                } else {
                    ProgressView()
                }
            }
            .progressViewStyle(.linear)
            .frame(maxWidth: .infinity)
            .accessibilityLabel(model.t("creatingBoard"))
            // The line keeps its height when empty, so the bar does not jump when a time arrives.
            Text(model.buildETA() ?? " ").font(.subheadline).foregroundStyle(.secondary)
                .accessibilityHidden(model.buildETA() == nil)
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
            if let partial = model.partialText() {
                Text(partial).font(.subheadline).foregroundStyle(.secondary)
            }
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
