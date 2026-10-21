import Foundation
import Testing
import WebKit
@testable import Bristlenose

/// The menu gates that restate what a command can actually reach, decided on
/// `BridgeHandler` so they are testable without a menu bar. Each one was a
/// command that stayed live and did nothing (wave-2 reliability, 20 Oct 2026).
@Suite("Menu gates")
@MainActor
struct MenuGateTests {

    private func data(sessions: Int?) -> UnanalysedState {
        UnanalysedState(newFiles: [], missingFiles: [], sessionCount: sessions,
                        totalDurationSeconds: nil, ingestableFileCount: 1)
    }

    /// A bridge with a live channel and the SPA on the far end, on `path`.
    private func liveBridge(on path: String = "/report/quotes") -> (BridgeHandler, WKWebView) {
        let bridge = BridgeHandler()
        let webView = WKWebView()
        bridge.webView = webView
        bridge.handleMessage(["type": "ready"])
        bridge.handleMessage(["type": "route-change", "url": path])
        return (bridge, webView)
    }

    // MARK: R64 — Re-analyse follows the run

    /// The pipeline-state path mirrored Stop but not Re-analyse, so a first
    /// analysis left Re-analyse dimmed until the study was reselected.
    @Test func reAnalyseLightsWhenAFirstAnalysisFinishes() {
        let bridge = BridgeHandler()
        let study = Project(id: UUID(), name: "Study", path: NSTemporaryDirectory())

        bridge.mirrorSelectedProjectRun(project: study, state: .running, data: data(sessions: nil))
        #expect(bridge.selectedProjectIsRunning)
        #expect(!bridge.selectedProjectIsAnalysed)

        // The run ends, then the session count lands — the same writer twice.
        bridge.mirrorSelectedProjectRun(project: study, state: .ready(Date()), data: data(sessions: nil))
        #expect(!bridge.selectedProjectIsRunning)
        bridge.mirrorSelectedProjectRun(project: study, state: .ready(Date()), data: data(sessions: 6))
        #expect(bridge.selectedProjectIsAnalysed, "Re-analyse stayed dimmed after the run finished")
    }

    /// R63's menu-bar half rides the same mirror: an analysed study on an
    /// ejected drive keeps `.ready` and its count, and must still dim.
    @Test func reAnalyseDimsForAStudyOnAnEjectedDrive() {
        let bridge = BridgeHandler()
        let ejected = Project(id: UUID(), name: "Study",
                              path: "/Volumes/BN-ejected-\(UUID().uuidString)/study")
        #expect(!ejected.isAvailable)

        bridge.mirrorSelectedProjectRun(project: ejected, state: .ready(Date()), data: data(sessions: 6))
        #expect(!bridge.selectedProjectIsAnalysed)
    }

    // MARK: R47 follow-up — Add Files… dims on a study that can't take files

    /// The panel opened on a running study, took the pick and did nothing.
    @Test func addFilesDimsWhileTheStudyCannotTakeFiles() {
        let bridge = BridgeHandler()
        let study = Project(id: UUID(), name: "Study", path: NSTemporaryDirectory())

        bridge.mirrorSelectedProjectRun(project: study, state: .idle, data: data(sessions: nil))
        #expect(bridge.selectedProjectTakesFiles)
        for busy in StudyFinderDropTests.busy {
            bridge.mirrorSelectedProjectRun(project: study, state: busy, data: data(sessions: nil))
            #expect(!bridge.selectedProjectTakesFiles, "Add Files… stayed lit on \(busy)")
        }
        bridge.mirrorSelectedProjectRun(project: study, state: .ready(Date()), data: data(sessions: 6))
        #expect(bridge.selectedProjectTakesFiles, "Add Files… stayed dimmed after the run")

        bridge.reset()
        #expect(!bridge.selectedProjectTakesFiles)
    }

    /// A study on an ejected drive keeps `.ready`, so its state alone would
    /// light Add Files… over a folder that isn't there.
    @Test func addFilesDimsForAStudyOnAnEjectedDrive() {
        let bridge = BridgeHandler()
        let ejected = Project(id: UUID(), name: "Study",
                              path: "/Volumes/BN-ejected-\(UUID().uuidString)/study")
        #expect(!ejected.isAvailable)

        bridge.mirrorSelectedProjectRun(project: ejected, state: .ready(Date()), data: data(sessions: 6))
        #expect(!bridge.selectedProjectTakesFiles)
    }

    // MARK: R70 — report commands need the channel

    /// The report's mirrors outlive a dead sidecar; `commandTab` does not.
    @Test func aDeadChannelTakesTheLensAwayFromCommands() {
        let (bridge, webView) = liveBridge(on: "/report/quotes")
        #expect(bridge.commandTab == .quotes)

        bridge.webView = nil  // `dismantleNSView`, after the sidecar died
        #expect(bridge.activeTab == .quotes, "precondition: the mirror outlives the channel")
        #expect(bridge.commandTab == nil)
        withExtendedLifetime(webView) {}
    }

    /// A status page has a channel and no `window.__bristlenose`.
    @Test func aStatusPageHasNoLensForCommands() {
        let (bridge, _) = liveBridge(on: "/report/quotes")
        bridge.handleMessage(["type": "status-page", "outcome": "failed"])
        #expect(bridge.documentState != .spa, "precondition: the status page announced itself")
        #expect(bridge.hasChannel)
        #expect(bridge.commandTab == nil)
        // Its `lensReadiness` resets to `.all`, so this is the half that dims Export.
        #expect(!bridge.canExportReport)
    }

    // MARK: R61 — Export Report waits for the whole report

    /// The SPA refuses a partial report; the menu must say so by dimming.
    @Test func exportReportDimsWhileALensIsWithheld() {
        let (bridge, _) = liveBridge(on: "/report/sessions")
        #expect(bridge.canExportReport)

        bridge.handleMessage(["type": "lens-availability",
                              "lenses": ["sessions": true, "quotes": false, "signals": false]])
        #expect(bridge.canDispatch, "precondition: the channel is live")
        #expect(!bridge.canExportReport, "Export Report was live on a partial report")

        bridge.handleMessage(["type": "lens-availability",
                              "lenses": ["sessions": true, "quotes": true, "signals": true]])
        #expect(bridge.canExportReport)
    }

    @Test func exportReportDimsWithoutAChannel() {
        let (bridge, webView) = liveBridge()
        #expect(bridge.canExportReport, "precondition: a whole report on a live channel exports")
        bridge.webView = nil
        #expect(!bridge.canExportReport)
        withExtendedLifetime(webView) {}
    }

    // MARK: R62 — Send to Miro / FigJam need the report server

    /// The sheet drives serve's REST endpoints, and `perform` drops the press
    /// without a port; the menu item stayed live and did nothing.
    @Test func sendToMiroDimsWithoutTheReportServer() {
        #expect(!MiroSheet.offered(hasKeyWindow: true, runningPort: nil))
        #expect(MiroSheet.offered(hasKeyWindow: true, runningPort: 8176))
        #expect(!MiroSheet.offered(hasKeyWindow: false, runningPort: 8176))
    }

    @Test func sendToFigJamDimsWithoutTheReportServer() {
        #expect(!FigJamSheet.offered(hasKeyWindow: true, runningPort: nil))
        #expect(FigJamSheet.offered(hasKeyWindow: true, runningPort: 8176))
        #expect(!FigJamSheet.offered(hasKeyWindow: false, runningPort: 8176))
    }

    /// The gate is the key window's own serve, not the fronted one. The menu
    /// read `serveFleet.frontedOrIdle`, and `front` runs only for a window with
    /// a study: window A on a running study, window B in front with none, and
    /// the items lit off A's port while B's `perform` dropped the press.
    @Test func sendToABoardFollowsTheKeyWindowsOwnServer() {
        let fleet = ServeFleet()
        let running = UUID(), notRunning = UUID()
        fleet.manager(for: running).instance.state = .running(port: 8176)
        fleet.frontedProject = running
        #expect(fleet.frontedOrIdle.runningPort != nil, "precondition: another window's serve is up")

        let bridge = BridgeHandler()
        let offered = {
            (MiroSheet.offered(hasKeyWindow: true, runningPort: bridge.reportServerPort),
             FigJamSheet.offered(hasKeyWindow: true, runningPort: bridge.reportServerPort))
        }

        bridge.mirrorReportServer(nil)  // a window with no study
        #expect(offered() == (false, false), "lit in a window with no study")

        bridge.mirrorReportServer(fleet.manager(for: notRunning))
        #expect(offered() == (false, false), "lit over a study whose server is not up")

        bridge.mirrorReportServer(fleet.manager(for: running))
        #expect(offered() == (true, true))

        fleet.manager(for: running).instance.state = .idle
        bridge.mirrorReportServer(fleet.manager(for: running))
        #expect(offered() == (false, false), "stayed lit after the server stopped")
    }

    /// No window in front: the stand-in the menu bar reads has no server.
    @Test func theUnattachedBridgeHasNoReportServer() {
        #expect(BridgeHandler.unattached.reportServerPort == nil)
    }
}
