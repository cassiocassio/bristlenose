import Foundation
import Testing
@testable import Bristlenose

/// The native Send to Miro sheet's Miro app route (owner, 9 Nov 2026;
/// docs/mockups/miro-board-file-route.html): it opens there, even for someone connected with a
/// token; Copy puts a board on the pasteboard that the Miro panel can read and says "Copied" until
/// a choice changes; Save writes the file where the researcher chose; a refusal is said in words;
/// each route has its own help page.
@MainActor
@Suite("Miro sheet — the Miro app route")
struct MiroSheetAppRouteTests {
    static let board = #"{"version":1,"title":"Kitchen study — Café","totals":{"quotes":112},"columns":[]}"#

    private func model(screens: Bool = false) -> MiroSheetModel {
        let m = MiroSheetModel(port: 0, token: nil, projectName: "Kitchen study", i18n: I18n(), screens: screens)
        m.fetchBoard = { _ in (Data(Self.board.utf8), 112) }
        return m
    }

    /// Wait for the board fetch the sheet started to finish.
    private func settle(_ m: MiroSheetModel) async {
        for _ in 0..<200 where m.fileBusy { try? await Task.sleep(nanoseconds: 5_000_000) }
    }

    @Test("opens on the Miro app route; the screens board has only the token route")
    func defaultRoute() {
        #expect(model().route == .app)
        #expect(model(screens: true).route == .token)
    }

    @Test("Copy writes a board the panel reads, then says Copied until a choice changes")
    func copyBoard() async throws {
        let m = model()
        var written: (html: String, json: String)?
        m.writePasteboard = { written = ($0, $1); return true }
        m.stickyShape = "square"
        var asked: FigJamAPI.Options?
        m.fetchBoard = { asked = $0; return (Data(Self.board.utf8), 112) }
        m.copyBoard()
        await settle(m)
        #expect(m.copied)
        #expect(asked == FigJamAPI.Options(boardName: "", locale: m.fileOptions().locale,
                                           splitLongQuotes: true, square: true, clipsBase: ""))
        let (html, json) = try #require(written)
        #expect(json == Self.board)
        // The attribute holds the board as base64 of its UTF-8 bytes (figjam-plugin/src/clipboard.ts).
        let b64 = try #require(html.firstMatch(of: /data-bristlenose-board="([A-Za-z0-9+\/=]+)"/)?.1)
        #expect(String(data: try #require(Data(base64Encoded: String(b64))), encoding: .utf8) == Self.board)
        m.stickyShape = "rectangle"
        #expect(!m.copied)  // a different board now
    }

    @Test("a pasteboard that refuses says the copy failed")
    func copyRefused() async {
        let m = model()
        m.writePasteboard = { _, _ in false }
        m.copyBoard()
        await settle(m)
        #expect(!m.copied)
        #expect(m.fileError == m.t("copyFailed"))
    }

    @Test("a board the server refuses is said in words, and nothing is copied")
    func refusal() async {
        let m = model()
        var wrote = false
        m.writePasteboard = { _, _ in wrote = true; return true }
        m.fetchBoard = { _ in
            throw FigJamAPI.APIError(message: "no", localeKey: "common.miro.errNoQuotesSelected")
        }
        m.copyBoard()
        await settle(m)
        #expect(!wrote)
        #expect(m.fileError == "common.miro.errNoQuotesSelected")  // a bare I18n returns the key
    }

    @Test("Save writes the board where the researcher chose, and says so")
    func save() async throws {
        let m = model()
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        var offered: String?
        m.chooseDestination = { offered = $0; return dir.appendingPathComponent($0) }
        m.saveBoard()
        await settle(m)
        #expect(offered == "Kitchen study-miro-board.json")
        let saved = try String(contentsOf: dir.appendingPathComponent("Kitchen study-miro-board.json"), encoding: .utf8)
        #expect(saved == Self.board)
        #expect(m.savedText() != nil)
        m.splitLongQuotes = false
        #expect(m.savedText() == nil)
    }

    @Test("a cancelled save panel says nothing")
    func saveCancelled() async {
        let m = model()
        m.chooseDestination = { _ in nil }
        m.saveBoard()
        await settle(m)
        #expect(m.savedText() == nil && m.fileError == nil)
    }

    @Test("each route opens its own help page")
    func help() {
        #expect(MiroSheetModel.helpURL(.app).absoluteString == "https://bristlenose.app/docs/miro-app.html")
        #expect(MiroSheetModel.helpURL(.token).absoluteString == "https://bristlenose.app/docs/send-to-miro.html")
    }

    @Test("the install link drops the web's arrow")
    func linkText() {
        let i18n = I18n()
        let m = MiroSheetModel(port: 0, token: nil, projectName: "p", i18n: i18n)
        #expect(!m.addAppLinkText().contains("↗"))
    }
}
