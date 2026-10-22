import AppKit
import Foundation
import Network
import Testing
import WebKit
@testable import Bristlenose

/// The report view's download path, driven through real WebKit downloads
/// against a loopback server standing in for serve (20 Oct 2026).
///
/// - R75: an export the server answered with an error was offered to the save
///   panel and written to disk as though it were the report.
/// - R74: ticking Anonymise in the save panel cancelled the save and put up a
///   second save panel for the anonymised copy.
/// - R76: Export Report pressed again before the panel came up put up a
///   second save panel.
/// A loopback HTTP server standing in for serve. A download cannot go through
/// a `WKURLSchemeHandler` (WebKit fails it with -1002), so this is real HTTP.
private final class FakeServe: @unchecked Sendable {
    private let listener: NWListener
    /// Status for each request; the body names whether it was anonymised.
    /// Read and written on the main queue only, where the listener runs.
    var status: (URL) -> Int = { _ in 200 }
    /// How long the answer takes, as building a real export does.
    var delay: (URL) -> TimeInterval = { _ in 0 }
    /// Answers held until `release()`: an export still building for as long
    /// as the test needs, not for a fixed delay a held main actor can outlast.
    var hold: (URL) -> Bool = { _ in false }
    private var held: [() -> Void] = []
    private var released = false
    private(set) var requested: [URL] = []

    init() throws {
        let params = NWParameters.tcp
        params.requiredLocalEndpoint = NWEndpoint.hostPort(host: "127.0.0.1", port: 0)
        listener = try NWListener(using: params)
        listener.newConnectionHandler = { [weak self] connection in
            connection.start(queue: .main)
            connection.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { data, _, _, _ in
                guard let self else { connection.cancel(); return }
                let request = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
                let target = request.components(separatedBy: " ").dropFirst().first ?? "/"
                let url = URL(string: "http://127.0.0.1\(target)")!
                self.requested.append(url)
                let code = self.status(url)
                let anonymised = url.query?.contains("anonymise=true") == true
                let body = code == 200
                    ? (anonymised ? "<html>ANONYMISED</html>" : "<html>NAMED</html>")
                    : #"{"detail":"Export build missing"}"#
                var head = "HTTP/1.1 \(code) \(code == 200 ? "OK" : "Error")\r\n"
                head += "Content-Type: \(code == 200 ? "text/html" : "application/json")\r\n"
                if code == 200 { head += "Content-Disposition: attachment; filename=\"report.html\"\r\n" }
                head += "Content-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n"
                let answer = {
                    connection.send(content: Data((head + body).utf8),
                                    completion: .contentProcessed { _ in connection.cancel() })
                }
                if self.hold(url), !self.released {
                    self.held.append(answer)
                } else {
                    DispatchQueue.main.asyncAfter(deadline: .now() + self.delay(url), execute: answer)
                }
            }
        }
        listener.start(queue: .main)
    }

    var port: UInt16 { listener.port?.rawValue ?? 0 }

    /// Send every held answer, and hold none from now on. Main queue only.
    func release() {
        released = true
        let answers = held
        held = []
        answers.forEach { $0() }
    }

    func ready() async {
        let deadline = Date().addingTimeInterval(ExportRig.patience)
        while port == 0, Date() < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }

    func stop() { listener.cancel() }
}

@MainActor
private final class ExportRig {
    let serve: FakeServe
    let webView: WKWebView
    let coordinator = WebView.Coordinator(bridgeHandler: BridgeHandler(), i18n: I18n())
    let dir: URL
    var panels = 0
    var alerts: [NSAlert] = []
    /// What the researcher does at the panel: by default, Save as offered.
    var atPanel: (ExportAccessoryController?) -> Void = { _ in }

    init() throws {
        serve = try FakeServe()
        webView = WKWebView(frame: .zero)
        coordinator.webView = webView
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-export-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        coordinator.chooseSaveDestination = { [unowned self] _, accessory in
            self.panels += 1
            self.atPanel(accessory)
            return self.destination
        }
        coordinator.showAlert = { [unowned self] in self.alerts.append($0) }
    }

    var destination: URL { dir.appendingPathComponent("report.html") }

    /// Start the export download as the SPA's link does, minus the click.
    func export(query: String = "locale=en") async {
        await serve.ready()
        // As the app's report view is wired: the coordinator decides its
        // navigations, and the serve it loaded is this one.
        webView.navigationDelegate = coordinator
        coordinator.lastLoadedURL = URL(string: "http://127.0.0.1:\(serve.port)/report/")
        let url = URL(string: "http://127.0.0.1:\(serve.port)/api/projects/1/export?\(query)")!
        webView.startDownload(using: URLRequest(url: url)) { [coordinator] download in
            // As `navigationAction(_:didBecome:)` hands the SPA's link over.
            coordinator.adoptDownload(download, requestURL: url)
        }
    }

    /// How long a wait for something that must happen may take. The full
    /// suite runs hundreds of main-actor tests beside these, and every step of
    /// an export is a main-actor hop: an 8 s ceiling failed in the full suite
    /// on 20 Oct 2026 and beside a 15 s main-thread hold. A green wait returns
    /// as soon as its condition holds.
    nonisolated static let patience: Double = 30

    func until(_ condition: () -> Bool, seconds: Double = patience) async {
        let deadline = Date().addingTimeInterval(seconds)
        while !condition(), Date() < deadline {
            try? await Task.sleep(for: .milliseconds(20))
        }
    }

    var saved: String? { try? String(contentsOf: destination, encoding: .utf8) }

    func cleanup() {
        serve.stop()
        try? FileManager.default.removeItem(at: dir)
    }
}

@MainActor
@Suite("Export save flow", .serialized)
struct ExportSaveFlowTests {

    /// The control: a 200 is offered to the panel and written where chosen.
    @Test func aGoodExportIsSavedWhereChosen() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        await rig.export()
        await rig.until { rig.saved == "<html>NAMED</html>" }

        #expect(rig.panels == 1)
        #expect(rig.saved == "<html>NAMED</html>")
        #expect(rig.alerts.isEmpty)
    }

    // MARK: - R75

    @Test func aServerErrorIsNeverSavedAsTheReport() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        rig.serve.status = { _ in 500 }
        await rig.export()
        await rig.until { !rig.alerts.isEmpty || rig.saved != nil || rig.panels > 0 }
        // Give a wrongly-offered save time to land, so a pass is not a race.
        try? await Task.sleep(for: .milliseconds(300))

        #expect(rig.serve.requested.count == 1, "the server was never asked")
        #expect(rig.panels == 0, "the save panel was offered an error response")
        #expect(rig.saved == nil, "the error body was saved as the report")
        #expect(rig.alerts.count == 1, "the failure was not said")
        #expect(rig.alerts.first?.informativeText == HTTPURLResponse.localizedString(forStatusCode: 500),
                "the alert came from somewhere other than the status check")
    }

    // MARK: - R74

    @Test func tickingAnonymiseSavesOnceToTheChosenPlace() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        rig.atPanel = { $0?.anonymise = true }
        await rig.export()
        await rig.until { rig.saved == "<html>ANONYMISED</html>" || rig.panels > 1 }
        try? await Task.sleep(for: .milliseconds(300))

        #expect(rig.panels == 1, "a second save panel asked again")
        #expect(rig.saved == "<html>ANONYMISED</html>")
        #expect(rig.serve.requested.last?.query?.contains("anonymise=true") == true)
        #expect(rig.serve.requested.last?.query?.contains("locale=en") == true,
                "the anonymised request dropped the export's other parameters")
        #expect(rig.alerts.isEmpty)
    }

    @Test func anAnonymisedCopyTheServerRefusesIsSaidAndNotSaved() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        rig.serve.status = { $0.query?.contains("anonymise=true") == true ? 500 : 200 }
        rig.atPanel = { $0?.anonymise = true }
        await rig.export()
        await rig.until { !rig.alerts.isEmpty || rig.saved != nil || rig.panels > 1 }
        try? await Task.sleep(for: .milliseconds(300))

        #expect(rig.serve.requested.count == 2, "the anonymised copy was never asked for")
        #expect(rig.panels == 1)
        #expect(rig.saved == nil)
        #expect(rig.alerts.count == 1)
        #expect(rig.alerts.first?.informativeText == HTTPURLResponse.localizedString(forStatusCode: 500))
    }

    // MARK: - R76

    @Test func exportReportPressedTwiceAsksOnce() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        // The export is still building when the second press lands: its
        // answer is held until both presses are in.
        rig.serve.hold = { _ in true }
        await rig.export()
        await rig.export()
        rig.serve.release()
        await rig.until { rig.saved == "<html>NAMED</html>" }
        await rig.until { !rig.coordinator.hasPendingReportExport }
        // Give a second panel time to come up, so a pass is not a race.
        try? await Task.sleep(for: .milliseconds(500))

        #expect(rig.panels == 1, "the second press put up a second save panel")
        #expect(rig.saved == "<html>NAMED</html>")
        #expect(rig.alerts.isEmpty, "a dropped second press is not a failure")
    }

    /// The export after a finished one, a cancelled one, or an error is not
    /// taken for a second press.
    @Test func eachExportAfterTheLastHasEndedAsksAgain() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        await rig.export()
        await rig.until { rig.saved != nil && !rig.coordinator.hasPendingReportExport }

        var cancelled = false
        rig.coordinator.chooseSaveDestination = { _, _ in rig.panels += 1; cancelled = true; return nil }
        await rig.export()
        await rig.until { cancelled }

        rig.serve.status = { _ in 500 }
        await rig.export()
        await rig.until { !rig.alerts.isEmpty }

        rig.serve.status = { _ in 200 }
        await rig.export()
        await rig.until { rig.panels == 3 }

        #expect(rig.panels == 3, "an export after one had ended was dropped")
        #expect(rig.alerts.count == 1)
    }

    // MARK: - #24: the row says "Exporting…" until the panel

    /// From the press, through the seconds the server spends building the
    /// file, to the save panel — and not a moment past it (decision #24).
    @Test func exportingIsSaidFromThePressUntilThePanel() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        let bridge = rig.coordinator.bridgeHandler
        var atPanel: Bool?
        rig.atPanel = { _ in atPanel = bridge.isExportingReport }
        rig.serve.hold = { _ in true }

        bridge.reportExportPressed()          // as `menuAction("exportReport")` does
        #expect(bridge.isExportingReport, "the press was not answered")
        await rig.export()
        await rig.until { rig.serve.requested.count == 1 }
        // The server is still building it.
        try? await Task.sleep(for: .milliseconds(200))
        #expect(bridge.isExportingReport, "the line went before the panel came up")

        rig.serve.release()
        await rig.until { rig.saved != nil }
        #expect(atPanel == false, "the save panel came up over \"Exporting…\"")
        #expect(!bridge.isExportingReport)
    }

    /// A refused export ends it too: the alert, not "Exporting…", is next.
    @Test func aServerErrorEndsExporting() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        let bridge = rig.coordinator.bridgeHandler
        rig.serve.status = { _ in 500 }
        bridge.reportExportPressed()
        await rig.export()
        await rig.until { !rig.alerts.isEmpty }
        #expect(!rig.alerts.isEmpty)
        #expect(!bridge.isExportingReport, "a refused export still said Exporting…")
    }

    /// A press the page never turns into a download — a partial report it
    /// refuses, or a script that never ran — lets go on its own.
    @Test func aPressThatStartsNoDownloadLetsGo() async throws {
        let bridge = BridgeHandler()
        bridge.reportExportStartPatience = .milliseconds(100)
        bridge.reportExportPressed()
        #expect(bridge.isExportingReport)
        let deadline = Date().addingTimeInterval(ExportRig.patience)
        while bridge.isExportingReport, Date() < deadline {
            try? await Task.sleep(for: .milliseconds(20))
        }
        #expect(!bridge.isExportingReport, "Exporting… stayed up with no export behind it")
    }

    /// Once the download has begun, its own ends clear the line: the
    /// fallback must not cut a slow export's "Exporting…" short.
    @Test func aBegunDownloadOutlastsTheFallback() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        let bridge = rig.coordinator.bridgeHandler
        bridge.reportExportStartPatience = .milliseconds(100)
        rig.serve.hold = { _ in true }
        bridge.reportExportPressed()
        await rig.export()
        await rig.until { rig.serve.requested.count == 1 }
        try? await Task.sleep(for: .milliseconds(400))
        #expect(bridge.isExportingReport, "the fallback cleared a download still building")
        rig.serve.release()
        await rig.until { rig.saved != nil }
        #expect(!bridge.isExportingReport)
    }

    /// A second press after the panel, while the saved copy is still being
    /// fetched, is dropped — and so is its "Exporting…", at once, not after
    /// the fallback (review of ce125ffc).
    @Test func aPressDroppedAfterThePanelLetsGoAtOnce() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        let bridge = rig.coordinator.bridgeHandler
        bridge.reportExportStartPatience = .seconds(60)
        rig.atPanel = { $0?.anonymise = true }
        rig.serve.hold = { $0.query?.contains("anonymise=true") == true }
        bridge.reportExportPressed()
        await rig.export()
        await rig.until { rig.serve.requested.count == 2 }
        #expect(!bridge.isExportingReport, "precondition: the panel has been and gone")

        #expect(bridge.reportExportPressed())
        await rig.export()
        await rig.until({ !bridge.isExportingReport }, seconds: 5)
        #expect(!bridge.isExportingReport, "a dropped press kept Exporting… up")
        rig.serve.release()
        await rig.until { rig.saved == "<html>ANONYMISED</html>" }
    }

    /// A second press before the panel is dropped too, but the first export
    /// is still building: its "Exporting…" stays.
    @Test func aPressDroppedBeforeThePanelKeepsTheFirstExporting() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        let bridge = rig.coordinator.bridgeHandler
        bridge.reportExportStartPatience = .seconds(60)
        rig.serve.hold = { _ in true }
        bridge.reportExportPressed()
        await rig.export()
        await rig.until { rig.serve.requested.count == 1 }
        #expect(!bridge.reportExportPressed(), "a press while pending changes nothing")
        await rig.export()
        try? await Task.sleep(for: .milliseconds(300))
        #expect(bridge.isExportingReport, "the dropped press cleared the first export's line")
        rig.serve.release()
        await rig.until { rig.saved != nil }
        #expect(!bridge.isExportingReport)
    }

    /// The press is answered from `menuAction`, the one door File ▸ Export
    /// Report… and the toolbar both use — and a script that never ran lets go.
    @Test func menuActionExportReportSaysExporting() async throws {
        let bridge = BridgeHandler()
        bridge.reportExportStartPatience = .seconds(60)
        let webView = WKWebView()       // no report loaded: the script call fails
        bridge.webView = webView
        bridge.menuAction("exportReport")
        #expect(bridge.isExportingReport, "the press through menuAction said nothing")
        let deadline = Date().addingTimeInterval(ExportRig.patience)
        while bridge.isExportingReport, Date() < deadline {
            try? await Task.sleep(for: .milliseconds(20))
        }
        #expect(!bridge.isExportingReport, "a press whose script failed kept Exporting… up")
        withExtendedLifetime(webView) {}
    }

    /// Ticking Anonymise hands the pending export to the refetch: a press
    /// while it is fetched is still a second press.
    @Test func aPressWhileTheAnonymisedCopyIsFetchedAsksNothing() async throws {
        let rig = try ExportRig(); defer { rig.cleanup() }
        rig.atPanel = { $0?.anonymise = true }
        // Hold the anonymised copy up until the second press is in.
        rig.serve.hold = { $0.query?.contains("anonymise=true") == true }
        await rig.export()
        await rig.until { rig.serve.requested.count == 2 }
        await rig.export()
        rig.serve.release()
        await rig.until { rig.saved == "<html>ANONYMISED</html>" }
        try? await Task.sleep(for: .milliseconds(500))

        #expect(rig.panels == 1)
        #expect(rig.saved == "<html>ANONYMISED</html>")

        // Saved: the export is over, and the next press asks again.
        await rig.until { !rig.coordinator.hasPendingReportExport }
        rig.atPanel = { _ in }
        await rig.export()
        await rig.until { rig.panels == 2 }
        #expect(rig.panels == 2, "the anonymised export never let go")
    }
}
