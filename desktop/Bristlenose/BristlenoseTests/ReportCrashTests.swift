import AppKit
import Foundation
import Testing

@testable import Bristlenose

/// The whole-report crash on the Mac (decision #2, 21 Oct 2026; spec
/// `docs/mockups/report-crash-fallback.html`): the `/report` boundary posts
/// `report-error`, the window keeps it, the sidebar row lights a warning glyph
/// that opens the popover, and Copy details carries the route, the error and
/// the frames out. Pure helpers only — the row's precedence, the variant's
/// kind and door, the bridge's parse and its clearing, the paste.
@MainActor
@Suite struct ReportCrashTests {

    private let crash = ReportCrash(
        route: "/report/quotes",
        message: "TypeError: Cannot read properties of undefined (reading 'quotes')",
        frames: ["at QuoteSections (report-abc.js:1:48211)", "at renderWithHooks (report-abc.js:1:9120)"]
    )
    private let summary = PipelineSummary(transcripts: nil, topics: nil, quotes: nil, themes: nil)

    private func resolve(_ state: PipelineState?, availability: ProjectAvailability = .ready,
                         addingCount: Int? = nil, copy: CopyDisplay? = nil,
                         importBatch: (done: Int, total: Int)? = nil,
                         screens: (done: Int, total: Int)? = nil,
                         missingCount: Int = 0, unanalysedCount: Int = 0, databaseForked: Bool = false,
                         crash: ReportCrash?) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: availability, pipelineState: state, isStopping: false,
            addingCount: addingCount, copy: copy, importBatch: importBatch, screens: screens,
            reportCrash: crash, lastRunAt: nil, missingCount: missingCount,
            unanalysedCount: unanalysedCount, databaseForked: databaseForked
        )
    }

    // MARK: - The variant

    @Test("A report crash is a warning with a door to the diagnostic popover")
    func kindAndDoor() {
        let v = SubtitleVariant.reportError(crash)
        #expect(v.glyphKind == .warning)
        #expect(v.glyphAction == .diagnostics)
        #expect(v.isDiagnostic)
    }

    // MARK: - Precedence

    @Test("Running outranks it; so do the causes — a failed run, a partial completion, an unreachable folder")
    func verbLedStatesWin() {
        #expect(resolve(.running, crash: crash) == .running)
        #expect(resolve(.failed(.passthrough("boom"), category: .unknown), crash: crash)
                == .failed(message: .passthrough("boom")))
        #expect(resolve(.failedWithDiagnostic(summary: summary), crash: crash) == .failedDiagnostic)
        #expect(resolve(.unreachable(reason: .timedOut), crash: crash)
                == .unreachable(reason: .timedOut))
        // A partial run is a plausible cause, and its bucket breakdown must
        // stay reachable (right-click ▸ Show Diagnostics opens the state's popover).
        #expect(resolve(.completedPartial(summary: summary), crash: crash) == .completedPartial)
    }

    @Test("It outranks ready, idle, a queued run, a stopped run, a partial run and a project never run")
    func restingStatesYield() {
        #expect(resolve(.ready(Date()), crash: crash) == .reportError(crash))
        #expect(resolve(.idle, crash: crash) == .reportError(crash))
        #expect(resolve(.scanning, crash: crash) == .reportError(crash))
        #expect(resolve(nil, crash: crash) == .reportError(crash))
        // Queued may not start for hours; the stack has no other door meanwhile.
        #expect(resolve(.queued(position: 2), crash: crash) == .reportError(crash))
        #expect(resolve(.stopped(stagesComplete: []), crash: crash) == .reportError(crash))
        #expect(resolve(.partial(kind: "transcribe-only", stagesComplete: []), crash: crash) == .reportError(crash))
    }

    @Test("In the idle tier the researcher's own acts keep the line: adding, a cloud batch, a copy, a cancel")
    func idleActivitiesWin() {
        #expect(resolve(.ready(Date()), addingCount: 3, crash: crash) == .addingInterviews(count: 3))
        #expect(resolve(.ready(Date()), importBatch: (done: 1, total: 4), crash: crash)
                == .importingBatch(done: 1, total: 4))
        #expect(resolve(.ready(Date()), copy: .copying(fraction: 0.5), crash: crash) == .copying(fraction: 0.5))
        #expect(resolve(.ready(Date()), copy: .cancelling, crash: crash) == .copyCancelling)
    }

    @Test("An error-kind delta keeps the line; the warning and info deltas and screen reading yield")
    func deltasAgainstTheCrash() {
        // A forked database is error by the 18 Jun rule and a plausible cause.
        #expect(resolve(.ready(Date()), databaseForked: true, crash: crash) == .deltaOnly(.databaseForked))
        #expect(resolve(.ready(Date()), missingCount: 2, crash: crash) == .reportError(crash))
        #expect(resolve(.ready(Date()), unanalysedCount: 2, crash: crash) == .reportError(crash))
        #expect(resolve(.ready(Date()), screens: (done: 1, total: 4), crash: crash) == .reportError(crash))
        // And without a crash the chain is as it was.
        #expect(resolve(.ready(Date()), missingCount: 2, crash: nil) == .deltaOnly(.missing(count: 2)))
        #expect(resolve(.ready(Date()), screens: (done: 1, total: 4), crash: nil)
                == .readingScreens(done: 1, total: 4))
    }

    @Test("A project that can't be found keeps its own line")
    func cantFindWins() {
        #expect(resolve(.ready(Date()), availability: .cantFind(reason: .moved), crash: crash)
                == .cantFind(reason: .moved))
    }

    @Test("No crash, no change: the resting chain is untouched")
    func noCrashIsNoop() {
        #expect(resolve(.ready(Date()), crash: nil) == .placeholder)
        #expect(resolve(.completedPartial(summary: summary), crash: nil) == .completedPartial)
    }

    // MARK: - The bridge payload

    @Test("The payload lands, bounded")
    func parseBounded() {
        let long = String(repeating: "x", count: 2_000)
        let frames = (0..<20).map { "at f\($0) (\(long))" }
        let parsed = ReportCrash.fromBridge([
            "type": "report-error", "route": "/report/quotes", "message": long, "frames": frames,
        ])
        #expect(parsed?.route == "/report/quotes")
        #expect(parsed?.message.count == ReportCrash.messageLimit)
        #expect(parsed?.frames.count == ReportCrash.frameLimit)
        #expect(parsed?.frames.allSatisfy { $0.count <= ReportCrash.frameLength } == true)
    }

    @Test("A payload with no route or no message is not a crash")
    func parseRefusesEmpty() {
        #expect(ReportCrash.fromBridge(["type": "report-error", "message": "x"]) == nil)
        #expect(ReportCrash.fromBridge(["type": "report-error", "route": "/report/"]) == nil)
        #expect(ReportCrash.fromBridge(["type": "report-error", "route": "", "message": "x"]) == nil)
        #expect(ReportCrash.fromBridge(["type": "report-error", "route": "/r", "message": "m"])
                == ReportCrash(route: "/r", message: "m", frames: []))
    }

    @Test("Frames that are not strings are ignored, not fatal")
    func parseTolerantFrames() {
        let parsed = ReportCrash.fromBridge([
            "type": "report-error", "route": "/r", "message": "m", "frames": NSNull(),
        ])
        #expect(parsed?.frames == [])
    }

    // MARK: - The window keeps it, and lets it go

    @Test("report-error lights the window; a malformed one does not")
    func bridgeSets() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "report-error", "route": "/report/quotes",
                              "message": crash.message, "frames": crash.frames])
        #expect(bridge.reportCrash == crash)
        let other = BridgeHandler()
        other.handleMessage(["type": "report-error", "message": "no route"])
        #expect(other.reportCrash == nil)
    }

    @Test("The next successful render clears it: the route change the fresh layout posts")
    func bridgeClearsOnRender() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "report-error", "route": "/report/quotes", "message": "m"])
        #expect(bridge.reportCrash != nil)
        bridge.handleMessage(["type": "route-change", "url": "/report/sessions/"])
        #expect(bridge.reportCrash == nil)
    }

    @Test("ready does not clear it: a crash and a ready can belong to one document")
    func readyKeepsTheCrash() {
        // `ready` is posted by the layout's effect, and fabricated by the web
        // view two seconds after any load, so it says nothing about whether
        // the layout rendered. The row stays lit until a route change.
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "report-error", "route": "/report/quotes", "message": "m"])
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.reportCrash == crashNamed("m"))
    }

    @Test("A crash lifts the boot veil and keeps a lens queued before it, replayed by the retry's ready")
    func crashLiftsVeilAndKeepsIntent() {
        let bridge = BridgeHandler()
        bridge.reset()
        bridge.lensesAvailable = true
        bridge.activateLens(.quotes)
        #expect(bridge.pendingLensIntent == .quotes)
        #expect(!bridge.isReady)
        bridge.handleMessage(["type": "report-error", "route": "/report/", "message": "m"])
        #expect(bridge.isReady, "the fallback is on screen, so the pane uncovers")
        #expect(bridge.pendingLensIntent == .quotes, "the click waits for the document a Retry mounts")
        #expect(bridge.documentState == .loading, "a first-mount crash installed no shims")
        // Retry succeeded: the fresh layout posts ready, and the click lands.
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.pendingLensIntent == nil)
        #expect(bridge.lensIntentReplayed)
    }

    @Test("A lens clicked after the crash queues the same way, and lands on the same ready")
    func clickAfterCrashQueuesAlike() {
        let bridge = BridgeHandler()
        bridge.reset()
        bridge.lensesAvailable = true
        bridge.handleMessage(["type": "report-error", "route": "/report/", "message": "m"])
        bridge.activateLens(.sessions)
        #expect(bridge.pendingLensIntent == .sessions)
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.pendingLensIntent == nil)
        #expect(bridge.lensIntentReplayed)
    }

    private func crashNamed(_ message: String) -> ReportCrash {
        ReportCrash(route: "/report/quotes", message: message, frames: [])
    }

    // MARK: - The popover's state

    @Test("The popover opens for a crash on a project the pipeline never touched")
    func popoverStateFallsBackToIdle() {
        #expect(ReportCrash.popoverState(pipelineState: nil, crash: crash) == .idle)
        #expect(ReportCrash.popoverState(pipelineState: nil, crash: nil) == nil)
        #expect(ReportCrash.popoverState(pipelineState: .completedPartial(summary: summary), crash: crash)
                == .completedPartial(summary: summary))
        // And `.idle` yields to the crash, so the popover is the crash's.
        #expect(resolve(.idle, crash: crash) == .reportError(crash))
    }

    // MARK: - Which row

    @Test("Only the row of the project whose document crashed lights")
    func onlyTheCrashedProjectsRowLights() {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("BristlenoseTests-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let index = ProjectIndex(fileURL: dir.appendingPathComponent("projects.json"))
        let a = index.addProject(name: "Rockclimbing", path: "")
        let b = index.addProject(name: "Checkout study", path: "")
        // Held locally: the controller's `i18n` is weak.
        let i18n = I18n()
        let controller = SidebarOutlineController()
        controller.projectIndex = index
        controller.i18n = i18n
        _ = controller.view
        controller.reportCrash = (projectID: a.id, crash: crash)
        controller.update(
            roots: OutlineTree.build(lenses: LensItem.all, projects: index.projects, folders: index.folders),
            selection: [], activeTab: nil, lensesEnabled: true
        )
        func height(_ id: UUID) -> CGFloat? {
            for row in 0..<controller.outlineView.numberOfRows {
                if let node = controller.outlineView.item(atRow: row) as? OutlineNode, node.kind == .project(id) {
                    return controller.outlineView(controller.outlineView, heightOfRowByItem: node)
                }
            }
            return nil
        }
        // A crash line is a two-line row; a clean project says nothing (Schema E).
        #expect(height(a.id) == ProjectCellSpec.rowHeight(twoLine: true))
        #expect(height(b.id) == ProjectCellSpec.rowHeight(twoLine: false))
    }

    @Test("A status page or a project switch clears it: it never outlives the document")
    func bridgeClearsOnReplacement() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "report-error", "route": "/report/quotes", "message": "m"])
        bridge.handleMessage(["type": "status-page", "outcome": "in-progress"])
        #expect(bridge.reportCrash == nil)

        let switched = BridgeHandler()
        switched.handleMessage(["type": "report-error", "route": "/report/quotes", "message": "m"])
        switched.reset()
        #expect(switched.reportCrash == nil)
    }

    @Test("A route change without a url clears nothing")
    func routeChangeNeedsAUrl() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "report-error", "route": "/report/quotes", "message": "m"])
        bridge.handleMessage(["type": "route-change"])
        #expect(bridge.reportCrash != nil)
    }

    // MARK: - Copy details

    @Test("The paste carries route, error, frames, project and version, and redacts the path")
    func plaintext() {
        let text = ProjectDiagnosticPopover.formatReportCrashPlaintext(
            crash: ReportCrash(route: crash.route, message: crash.message,
                               frames: crash.frames + ["at x (file:///Users/me/Research/Rockclimbing/y.js)"]),
            projectName: "Rockclimbing", projectPath: "/Users/me/Research/Rockclimbing"
        )
        let lines = text.components(separatedBy: "\n")
        #expect(lines[0].hasPrefix("Bristlenose "))
        #expect(lines[0].contains(" on "))
        #expect(lines.contains("Project: Rockclimbing"))
        #expect(lines.contains("Outcome: \(MessageKind.warning.glyph) Report couldn't be shown"))
        #expect(lines.contains("Where: /report/quotes"))
        #expect(lines.contains("Error: \(crash.message)"))
        #expect(lines.contains("    at QuoteSections (report-abc.js:1:48211)"))
        #expect(lines.contains("    at renderWithHooks (report-abc.js:1:9120)"))
        #expect(!text.contains("/Users/me/Research/Rockclimbing"))
        #expect(text.contains("<project>"))
    }

    @Test("A crash with no frames pastes no frame lines")
    func plaintextNoFrames() {
        let text = ProjectDiagnosticPopover.formatReportCrashPlaintext(
            crash: ReportCrash(route: "/report/", message: "Error: x", frames: []),
            projectName: "P", projectPath: ""
        )
        #expect(text.components(separatedBy: "\n").last == "Error: Error: x")
    }
}
