import AppKit
import SwiftUI
import UniformTypeIdentifiers
import os

/// Native "Send to FigJam" sheet — the macOS rendering of `FigJamExportPanel.tsx`.
///
/// FigJam has no way for an outside app to write to a board, so this saves a
/// board file the Bristlenose FigJam plugin opens inside FigJam
/// (docs/design-board-integrations.md). No connection, so no connect step:
/// the choices, a save panel, then the three steps to finish in FigJam. The
/// choices are the Miro sheet's, on the same strings, so the two boards offer
/// the same things: the board name (filled with the project's), break long
/// quotes (on), sticky shape (square by default on FigJam), and clip links.
///
/// Presentation only: the file is built by `GET /export/figjam-board.json`,
/// the same route the web panel downloads. Parked behind
/// `BristlenoseFlags.figjamExport` until the plugin is published.

// MARK: - API

struct FigJamAPI {
    let port: Int
    let token: String?
    var projectID: Int = 1

    private static let log = Logger(subsystem: "app.bristlenose", category: "figjam")

    struct Options: Equatable {
        var boardName: String
        var locale: String
        var splitLongQuotes: Bool
        var square: Bool
        var clipsBase: String
    }

    /// A refusal the sheet says in the reader's language; `localeKey` is nil for
    /// anything the server did not name, which the sheet says generically.
    struct APIError: LocalizedError {
        let message: String
        var localeKey: String?
        var errorDescription: String? { message }
    }

    /// Server `reason` → the key that says it. Shared with the web panel.
    static let reasonKeys: [String: String] = [
        "no_quotes_selected": "common.miro.errNoQuotesSelected",
        "clips_base_not_http": "common.figjam.errClipsBase",
    ]

    private struct ErrorBody: Decodable { let detail: String?; let reason: String? }
    private struct Summary: Decodable {
        struct Totals: Decodable { let quotes: Int }
        let totals: Totals
    }

    func request(_ o: Options) -> URLRequest? {
        var c = URLComponents()
        c.scheme = "http"
        c.host = "127.0.0.1"
        c.port = port
        c.path = "/api/projects/\(projectID)/export/figjam-board.json"
        var items = [
            URLQueryItem(name: "board_name", value: o.boardName),
            URLQueryItem(name: "lang", value: o.locale),
            URLQueryItem(name: "split_long_quotes", value: o.splitLongQuotes ? "true" : "false"),
            URLQueryItem(name: "sticky_shape", value: o.square ? "square" : "rectangle"),
        ]
        if !o.clipsBase.isEmpty { items.append(URLQueryItem(name: "clips_base", value: o.clipsBase)) }
        c.queryItems = items
        guard let url = c.url else { return nil }
        var r = URLRequest(url: url)
        if let token { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        return r
    }

    /// The board file and how many quotes it holds.
    func fetchBoard(_ o: Options) async throws -> (data: Data, quotes: Int) {
        guard let req = request(o) else {
            throw APIError(message: "Bad request", localeKey: nil)
        }
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: req)
        } catch {
            throw APIError(message: "Could not reach the local server.",
                           localeKey: "common.miro.serverUnreachable")
        }
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 200 else {
            let body = try? JSONDecoder().decode(ErrorBody.self, from: data)
            Self.log.warning("figjam board refused status=\(status) reason=\(body?.reason ?? "-", privacy: .public)")
            throw APIError(message: body?.detail ?? "HTTP \(status)",
                           localeKey: body?.reason.flatMap { Self.reasonKeys[$0] })
        }
        guard let summary = try? JSONDecoder().decode(Summary.self, from: data) else {
            throw APIError(message: "Unreadable board file", localeKey: nil)
        }
        return (data, summary.totals.quotes)
    }
}

// MARK: - View model

@MainActor
final class FigJamSheetModel: ObservableObject {
    enum Step: Equatable { case configure, preparing, done }

    @Published var step: Step = .configure
    @Published var boardName: String
    @Published var splitLongQuotes = true
    /// Square by default on FigJam, rectangle on Miro (owner, 17 Oct 2026, for density).
    @Published var square = true
    @Published var linkClips = false
    @Published var clipsBase = ""
    /// Clip links are parked (`BristlenoseFlags.boardClipLinks`): off, the choice is not shown
    /// and no folder is sent.
    let clipLinksOffered: Bool
    @Published var error: String?
    @Published private(set) var quotes = 0

    private let api: FigJamAPI
    private let i18n: I18n
    private let projectName: String
    /// Where the bytes go once the researcher has chosen a place. Injected so a
    /// test can stand in for the save panel.
    var chooseDestination: (String) async -> URL?
    /// The board file and its quote count. Injected so a test needs no server.
    var fetchBoard: (FigJamAPI.Options) async throws -> (data: Data, quotes: Int)

    init(port: Int, token: String?, projectName: String, i18n: I18n,
         clipLinksOffered: Bool = BristlenoseFlags.boardClipLinks) {
        let api = FigJamAPI(port: port, token: token)
        self.api = api
        self.clipLinksOffered = clipLinksOffered
        self.i18n = i18n
        self.projectName = projectName
        self.boardName = projectName  // filled, editable — nothing arrives untitled
        self.chooseDestination = FigJamSheetModel.savePanel
        self.fetchBoard = { try await api.fetchBoard($0) }
    }

    func t(_ key: String) -> String { i18n.t(key) }

    func options() -> FigJamAPI.Options {
        FigJamAPI.Options(
            boardName: boardName.trimmingCharacters(in: .whitespacesAndNewlines),
            locale: i18n.locale,
            splitLongQuotes: splitLongQuotes,
            square: square,
            clipsBase: clipLinksOffered && linkClips
                ? clipsBase.trimmingCharacters(in: .whitespacesAndNewlines) : ""
        )
    }

    /// The name the save panel offers: the board's, else the project's.
    func suggestedFilename() -> String {
        let name = boardName.trimmingCharacters(in: .whitespacesAndNewlines)
        let base = name.isEmpty ? projectName : name
        let safe = base.replacingOccurrences(of: "/", with: "-").replacingOccurrences(of: ":", with: "-")
        return "\(safe.isEmpty ? "Bristlenose" : safe)-figjam-board.json"
    }

    /// Build the file, ask where it goes, write it. "Done" only once it is on
    /// disk: a cancelled save panel goes back to the choices, saying nothing.
    func save() async {
        error = nil
        step = .preparing
        do {
            let board = try await fetchBoard(options())
            guard let url = await chooseDestination(suggestedFilename()) else {
                step = .configure
                return
            }
            try board.data.write(to: url, options: .atomic)
            quotes = board.quotes
            step = .done
        } catch let e as FigJamAPI.APIError {
            error = i18n.t(e.localeKey ?? "common.figjam.error")
            step = .configure
        } catch {
            self.error = i18n.t("common.figjam.error")
            step = .configure
        }
    }

    func savedText() -> String { i18n.plural("common.figjam.saved", count: quotes) }

    /// The stock save panel — which is also what grants the sandbox write. It
    /// attaches to the window the FigJam sheet is on and takes its appearance
    /// (`PanelHost`): out-of-process under the sandbox, it would otherwise
    /// follow the system's.
    static func savePanel(_ filename: String) async -> URL? {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = filename
        panel.allowedContentTypes = [.json]
        panel.canCreateDirectories = true
        let host = PanelHost.window
        panel.adoptHostAppearance(host)
        let response: NSApplication.ModalResponse
        if let host {
            response = await withCheckedContinuation { done in
                panel.beginSheetModal(for: host) { done.resume(returning: $0) }
            }
        } else {
            response = await panel.begin()
        }
        return response == .OK ? panel.url : nil
    }
}

// MARK: - View

struct FigJamSheet: View {
    @StateObject private var model: FigJamSheetModel
    @Environment(\.dismiss) private var dismiss

    init(port: Int, token: String?, projectName: String, i18n: I18n) {
        _model = StateObject(wrappedValue: FigJamSheetModel(
            port: port, token: token, projectName: projectName, i18n: i18n
        ))
    }

    /// Whether Send to FigJam is offered: the same gate as `MiroSheet.offered`,
    /// since this sheet also needs the report server (R62).
    static func offered(hasKeyWindow: Bool, runningPort: Int?) -> Bool {
        WindowCommand.showFigJam.isEnabled(hasKeyWindow: hasKeyWindow) && runningPort != nil
    }

    // One size through the flow, like the Miro sheet (HIG: sheets keep one size).
    private let sheetWidth: CGFloat = 460
    private let sheetMinHeight: CGFloat = 400

    var body: some View {
        Group {
            switch model.step {
            case .configure, .preparing: configure
            case .done: done
            }
        }
        .padding(20)
        .frame(width: sheetWidth)
        .frame(minHeight: sheetMinHeight)
    }

    private var configure: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(model.t("common.figjam.title")).font(.headline)
                .frame(maxWidth: .infinity, alignment: .center)
            Text(model.t("common.figjam.intro")).font(.callout).foregroundStyle(.secondary)
            // The Miro sheet's form: right-aligned colon labels, left-aligned controls.
            Grid(alignment: .leading, horizontalSpacing: 8, verticalSpacing: 12) {
                GridRow(alignment: .firstTextBaseline) {
                    Text(model.t("desktop.miro.boardNameLabel"))
                        .foregroundStyle(.secondary)
                        .gridColumnAlignment(.trailing)
                    TextField("", text: $model.boardName)
                        .textFieldStyle(.roundedBorder)
                }
                GridRow(alignment: .firstTextBaseline) {
                    Text(model.t("desktop.figjam.stickyShapeLabel")).foregroundStyle(.secondary)
                    Picker("", selection: $model.square) {
                        Text(model.t("common.miro.stickyShapeSquare")).tag(true)
                        Text(model.t("common.miro.stickyShapeRectangle")).tag(false)
                    }
                    .pickerStyle(.radioGroup)
                    .horizontalRadioGroupLayout()
                    .labelsHidden()
                }
                GridRow(alignment: .firstTextBaseline) {
                    Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                    Toggle(model.t("common.miro.splitLongQuotes"), isOn: $model.splitLongQuotes)
                }
                if model.clipLinksOffered {
                GridRow(alignment: .top) {
                    Color.clear.gridCellUnsizedAxes([.horizontal, .vertical])
                    VStack(alignment: .leading, spacing: 4) {
                        Toggle(model.t("common.miro.linkClipsLabel"), isOn: $model.linkClips)
                        Text(model.t("common.miro.linkClipsHint")).font(.subheadline).foregroundStyle(.secondary)
                        if model.linkClips {
                            TextField(model.t("common.miro.clipsBasePlaceholder"), text: $model.clipsBase)
                                .textFieldStyle(.roundedBorder)
                        }
                    }
                }
                }
            }
            Text(model.t("common.figjam.notice")).font(.subheadline).foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            if let error = model.error {
                Text(error).font(.callout).foregroundStyle(.red)
            }
            Spacer(minLength: 16)
            HStack {
                if model.step == .preparing { ProgressView().controlSize(.small) }
                Spacer()
                Button(model.t("common.miro.cancel")) { dismiss() }.keyboardShortcut(.cancelAction)
                Button(model.t("desktop.figjam.saveBoardFile")) { Task { await model.save() } }
                    .keyboardShortcut(.defaultAction)
                    .disabled(model.step == .preparing)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var done: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "checkmark.circle").foregroundStyle(.green)
                Text(model.savedText()).font(.headline).fontWeight(.regular)
            }
            Text(model.t("common.figjam.nextSteps")).foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 6) {
                Text("1. " + model.t("common.figjam.step1"))
                Text("2. " + model.t("common.figjam.step2"))
                Text("3. " + model.t("common.figjam.step3"))
            }
            Spacer()
            HStack {
                Spacer()
                Button(model.t("common.miro.done")) { dismiss() }.keyboardShortcut(.defaultAction)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
