import Foundation
import Testing
@testable import Bristlenose

/// The native "Send to FigJam" sheet: what it asks the server for, and that it
/// says "saved" only once the file is on disk (docs/design-board-integrations.md).
@MainActor
@Suite("FigJam sheet")
struct FigJamSheetTests {

    private static func model(name: String = "Renfe kiosks") -> (FigJamSheetModel, I18n) {
        let i18n = I18n()
        let m = FigJamSheetModel(port: 8150, token: "t0k", projectName: name, i18n: i18n)
        return (m, i18n)
    }

    private static func query(_ r: URLRequest) -> [String: String] {
        let items = URLComponents(url: r.url!, resolvingAgainstBaseURL: false)?.queryItems ?? []
        return Dictionary(uniqueKeysWithValues: items.map { ($0.name, $0.value ?? "") })
    }

    @Test("arrives with the project's name, square stickies, long quotes broken")
    func defaults() {
        let (m, _) = Self.model()
        #expect(m.boardName == "Renfe kiosks")
        let o = m.options()
        #expect(o.square && o.splitLongQuotes && o.clipsBase.isEmpty)
    }

    @Test("asks the download route with the bearer and every choice")
    func request() throws {
        let api = FigJamAPI(port: 8150, token: "t0k")
        let r = try #require(api.request(.init(
            boardName: "Round 2", locale: "es", splitLongQuotes: false, square: false,
            clipsBase: "https://x.example/c")))
        #expect(r.url?.path == "/api/projects/1/export/figjam-board.json")
        #expect(r.url?.host == "127.0.0.1" && r.url?.port == 8150)
        #expect(r.value(forHTTPHeaderField: "Authorization") == "Bearer t0k")
        #expect(Self.query(r) == [
            "board_name": "Round 2", "lang": "es", "split_long_quotes": "false",
            "sticky_shape": "rectangle", "clips_base": "https://x.example/c",
        ])
    }

    @Test("clip links are parked: no folder is sent, ticked or not")
    func clipLinksParked() {
        let m = FigJamSheetModel(port: 8150, token: "t0k", projectName: "p", i18n: I18n(),
                                 clipLinksOffered: false)
        m.clipsBase = "https://x.example/c"
        m.linkClips = true
        #expect(m.options().clipsBase.isEmpty)
    }

    @Test("a clip folder is sent only when clip links are on")
    func clipsOnlyWhenOn() {
        let m = FigJamSheetModel(port: 8150, token: "t0k", projectName: "p", i18n: I18n(),
                                 clipLinksOffered: true)
        m.clipsBase = "https://x.example/c"
        #expect(m.options().clipsBase.isEmpty)
        m.linkClips = true
        #expect(m.options().clipsBase == "https://x.example/c")
    }

    @Test("both refusals the route sends have a sentence")
    func refusalsAreTranslated() {
        #expect(FigJamAPI.reasonKeys["no_quotes_selected"] == "common.miro.errNoQuotesSelected")
        #expect(FigJamAPI.reasonKeys["clips_base_not_http"] == "common.figjam.errClipsBase")
    }

    @Test("offers a file named after the board, without path separators")
    func filename() {
        let (m, _) = Self.model()
        m.boardName = "Kitchen / round: 2"
        #expect(m.suggestedFilename() == "Kitchen - round- 2-figjam-board.json")
        m.boardName = "  "
        #expect(m.suggestedFilename() == "Renfe kiosks-figjam-board.json")
    }

    @Test("writes the file, then says done — and only then")
    func savesThenDone() async throws {
        let (m, _) = Self.model()
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let dest = dir.appendingPathComponent("board.json")
        m.fetchBoard = { _ in (Data(#"{"totals":{"quotes":30}}"#.utf8), 30) }
        m.chooseDestination = { _ in dest }
        await m.save()
        #expect(m.step == .done)
        #expect(m.error == nil)
        #expect(FileManager.default.fileExists(atPath: dest.path))
    }

    @Test("a cancelled save panel goes back to the choices, saying nothing")
    func cancelledPanel() async {
        let (m, _) = Self.model()
        m.fetchBoard = { _ in (Data("{}".utf8), 3) }
        m.chooseDestination = { _ in nil }
        await m.save()
        #expect(m.step == .configure)
        #expect(m.error == nil)
    }

    @Test("a refusal is said in the dialog and nothing is saved")
    func refusal() async {
        let (m, i18n) = Self.model()
        var asked = false
        m.fetchBoard = { _ in
            throw FigJamAPI.APIError(message: "No quotes", localeKey: "common.miro.errNoQuotesSelected")
        }
        m.chooseDestination = { _ in asked = true; return nil }
        await m.save()
        #expect(m.step == .configure)
        #expect(m.error == i18n.t("common.miro.errNoQuotesSelected"))
        #expect(!asked)
    }

    @Test("parked: the flag reads off by default")
    func parkedByDefault() {
        let defaults = UserDefaults.standard
        let saved = defaults.object(forKey: BristlenoseFlags.figjamExportKey)
        defer {
            if let saved { defaults.set(saved, forKey: BristlenoseFlags.figjamExportKey) }
        }
        defaults.removeObject(forKey: BristlenoseFlags.figjamExportKey)
        #expect(!BristlenoseFlags.figjamExport)
    }
}
