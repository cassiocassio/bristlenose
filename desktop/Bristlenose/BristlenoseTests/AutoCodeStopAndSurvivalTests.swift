import AppKit
import Foundation
import Testing
@testable import Bristlenose

/// AutoCode landing plan Phase 5a, review fixes: Stop reaches AutoCode from ⌘. and the menus under
/// its own name; the × is acknowledged at once; the ended line survives a walk-away reap; a late
/// read never overwrites a newer one; the ring follows the appearance; and no test fleet writes
/// the app's defaults.

private func failedLine(_ framework: String = "uxr") -> AutoCodeEndedLine {
    AutoCodeEndedLine(outcome: .failed, failureKind: "out_of_credit", frameworkID: framework,
                      title: "Bristlenose UXR Codebook", processed: 48, total: 112,
                      key: "\(framework)|2026-11-23T10:00:00|failed")
}

private func failedJobsBody() -> [String: Any] {
    ["jobs": [["framework_id": "uxr", "title": "Bristlenose UXR Codebook", "status": "failed",
               "completed_at": NSNull(), "processed_quotes": 48, "total_quotes": 112,
               "failure_kind": "out_of_credit", "started_at": "2026-11-23T10:00:00"]]]
}

@MainActor
@Suite struct AutoCodeStopTargetTests {

    @Test func theRunWinsThenAutoCodeThenNothing() {
        let coding = AutoCodeProgress(done: 3, total: 9, frameworkID: "uxr")
        #expect(StopTarget.resolve(pipelineCanStop: true, autocode: coding, stopping: false) == .pipeline)
        #expect(StopTarget.resolve(pipelineCanStop: false, autocode: coding, stopping: false)
            == .autocode(framework: "uxr"))
        #expect(StopTarget.resolve(pipelineCanStop: false, autocode: nil, stopping: false) == .none)
        // already stopping: nothing more to stop
        #expect(StopTarget.resolve(pipelineCanStop: false, autocode: coding, stopping: true) == .none)
    }

    /// "Stop AutoCode" when AutoCode is what stops (owner's option B); "Stop Analysis" for a run.
    @Test func theLabelNamesWhatStops() throws {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        #expect(i18n.t(StopTarget.autocode(framework: "uxr").labelKey) == "Stop AutoCode")
        #expect(i18n.t(StopTarget.pipeline.labelKey) == "Stop Analysis")
    }

    /// ⌘. stays the run's: with AutoCode the only thing to stop it is not bound, because the
    /// report's Quotes lens binds ⌘. to the sidebars (lead's call, pending the owner).
    @Test func commandPeriodIsNeverStopAutoCodes() {
        #expect(!StopTarget.autocode(framework: "uxr").takesCommandPeriod)
        #expect(StopTarget.pipeline.takesCommandPeriod)
        let bridge = BridgeHandler()
        let study = Project(id: UUID(), name: "Study", path: NSTemporaryDirectory())
        bridge.mirrorSelectedProjectRun(project: study, state: .ready(Date()), data: nil,
                                        autocode: AutoCodeProgress(done: 3, total: 9, frameworkID: "uxr"))
        #expect(!bridge.selectedProjectStopTarget.takesCommandPeriod)
    }

    /// Project ▸ Stop lights for a running AutoCode pass and is named for it; the run wins.
    @Test func theMenuBarGateFollowsAutoCode() {
        let bridge = BridgeHandler()
        let study = Project(id: UUID(), name: "Study", path: NSTemporaryDirectory())
        let coding = AutoCodeProgress(done: 3, total: 9, frameworkID: "uxr")
        bridge.mirrorSelectedProjectRun(project: study, state: .ready(Date()), data: nil,
                                        autocode: coding)
        #expect(bridge.selectedProjectCanStop)
        #expect(bridge.selectedProjectStopTarget == .autocode(framework: "uxr"))
        bridge.mirrorSelectedProjectRun(project: study, state: .running, data: nil, autocode: coding)
        #expect(bridge.selectedProjectStopTarget == .pipeline)
        bridge.mirrorSelectedProjectRun(project: study, state: .ready(Date()), data: nil)
        #expect(!bridge.selectedProjectCanStop)
    }
}

@MainActor
@Suite struct AutoCodeStoppingAcknowledgementTests {

    @Test func aStopIsAcknowledgedAtOnceAndClearsWithItsCount() {
        let store = ScreenReadingStore()
        let id = UUID()
        var asked: [(UUID, String)] = []
        store.onStopAutoCode = { asked.append(($0, $1)) }
        store.setAutoCode(AutoCodeProgress(done: 3, total: 9, frameworkID: "uxr"), for: id)

        store.stopAutoCode(id, framework: "uxr")
        store.stopAutoCode(id, framework: "uxr")             // a second click while stopping
        #expect(asked.count == 1)
        #expect(store.autocodeStopping[id] == "uxr")

        store.setAutoCode(AutoCodeProgress(done: 4, total: 9, frameworkID: "uxr"), for: id)
        #expect(store.autocodeStopping[id] == "uxr", "a read of the same run cleared the Stop")
        store.setAutoCode(nil, for: id)
        #expect(store.autocodeStopping[id] == nil)
    }

    @Test func aFailedStopBringsTheCrossBack() {
        let store = ScreenReadingStore()
        let id = UUID()
        store.stopAutoCode(id, framework: "uxr")
        store.autoCodeStopFailed(for: id)
        #expect(store.autocodeStopping[id] == nil)
    }

    /// No server to ask: the fleet says so at once, so the row does not sit on "Stopping…".
    @Test func aStopWithNoServerFailsAtOnce() {
        let store = ScreenReadingStore()
        let fleet = ServeFleet(screenReading: store)
        let id = UUID()
        store.stopAutoCode(id, framework: "uxr")
        #expect(store.autocodeStopping[id] == nil)
        _ = fleet
    }

    @Test func theRowReadsStoppingUntilTheCountGoes() {
        let v = ProjectSubtitle.resolve(
            availability: .ready, pipelineState: nil, isStopping: false, addingCount: nil,
            copy: nil, importBatch: nil, autocode: (3, 9), autocodeStopping: true,
            lastRunAt: nil, missingCount: 0, unanalysedCount: 0)
        #expect(v == .stopping)
    }
}

/// The walk-away case (correctness #1): the window is closed, the run fails, the server is reaped,
/// and the line is still there after a relaunch.
@MainActor
@Suite struct AutoCodeWalkAwayTests {

    private func suite() -> UserDefaults {
        let name = "AutoCodeWalkAwayTests-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    private func running(_ manager: ServeManager) {
        manager.instance.state = .running(port: 5000)
        manager.instance.authToken = "tok"
    }

    @Test func aForcedReadIgnoresTheVisibilityGuard() async {
        let m = ServeManager(resolvedMode: .success(.external(port: 5000)))
        running(m)
        m.autoCodeWindowVisible = { false }                 // nobody is looking
        var asked = 0
        m.autoCodeJobsReader = { _ in asked += 1; return (200, failedJobsBody()) }
        var answers: [AutoCodeEndedAnswer] = []
        m.onAutoCodeEnded = { answers.append($0) }
        await m.pollAutoCode()
        #expect(asked == 0, "an unforced read asked with no window on screen")
        await m.pollAutoCode(force: true)
        #expect(asked == 1)
        #expect(answers == [.listed([failedLine()])])
    }

    /// Paid work ending (busy true → false) reads AutoCode at once, window or not.
    @Test func paidWorkEndingReadsTheEndedLine() async {
        let m = ServeManager(resolvedMode: .success(.external(port: 5000)))
        running(m)
        m.autoCodeWindowVisible = { false }
        m.autoCodeJobsReader = { _ in (200, failedJobsBody()) }
        var answers: [AutoCodeEndedAnswer] = []
        m.onAutoCodeEnded = { answers.append($0) }
        m.backgroundWorkReader = { _ in ["busy": true, "kinds": ["autocode"], "progress": 5] }
        await m.pollBackgroundWork()
        #expect(answers.isEmpty)
        m.backgroundWorkReader = { _ in ["busy": false, "kinds": [], "progress": 5] }
        await m.pollBackgroundWork()
        #expect(answers == [.listed([failedLine()])])
    }

    @Test func aFailureSeenAtTheEndSurvivesTheReapAndARelaunch() async throws {
        let d = suite()
        let store = ScreenReadingStore(defaults: d)
        let fleet = ServeFleet(screenReading: store, makeManager: {
            ServeManager(resolvedMode: .success(.external(port: 5000)))
        })
        let id = UUID()
        let m = fleet.manager(for: id)
        running(m)
        m.autoCodeJobsReader = { _ in (200, failedJobsBody()) }
        m.backgroundWorkReader = { _ in ["busy": true, "kinds": ["autocode"], "progress": 5] }
        await m.pollBackgroundWork()
        m.backgroundWorkReader = { _ in ["busy": false, "kinds": [], "progress": 5] }
        await m.pollBackgroundWork()                        // the run failed; nobody was looking

        fleet.sweep(shownProjects: [], grace: .zero)        // window gone: reap
        for _ in 0..<200 where fleet.managers[id] != nil { try await Task.sleep(for: .milliseconds(10)) }
        #expect(fleet.managers[id] == nil, "the idle server was never reaped")
        #expect(ScreenReadingStore(defaults: d).autocodeEnded[id] == failedLine(),
                "the failure was lost with the server")
    }

    /// The reap's own final read catches a run that ended between polls.
    @Test func theReapReadsOnceMoreBeforeItGoes() async throws {
        let store = ScreenReadingStore()
        let fleet = ServeFleet(screenReading: store, makeManager: {
            ServeManager(resolvedMode: .success(.external(port: 5000)))
        })
        let id = UUID()
        let m = fleet.manager(for: id)
        running(m)
        m.autoCodeJobsReader = { _ in (200, failedJobsBody()) }
        fleet.sweep(shownProjects: [], grace: .zero)
        for _ in 0..<200 where fleet.managers[id] != nil { try await Task.sleep(for: .milliseconds(10)) }
        #expect(fleet.managers[id] == nil)
        #expect(store.autocodeEnded[id] == failedLine())
    }
}

/// A slow reply must not overwrite a newer one (correctness #6).
@MainActor
@Suite struct AutoCodeReadOrderTests {

    @MainActor
    final class Gate {
        var continuation: CheckedContinuation<Void, Never>?
        func wait() async { await withCheckedContinuation { continuation = $0 } }
        func open() { continuation?.resume(); continuation = nil }
    }

    @Test func aLateReplyIsDropped() async throws {
        let m = ServeManager(resolvedMode: .success(.external(port: 5000)))
        m.instance.state = .running(port: 5000)
        m.instance.authToken = "tok"
        let gate = Gate()
        var call = 0
        m.autoCodeJobsReader = { _ in
            call += 1
            if call == 1 {
                await gate.wait()
                return (200, failedJobsBody())                    // the old answer
            }
            return (200, ["jobs": []])                            // the newer answer
        }
        var answers: [AutoCodeEndedAnswer] = []
        m.onAutoCodeEnded = { answers.append($0) }
        let first = Task { @MainActor in await m.pollAutoCode(force: true) }
        while gate.continuation == nil { try await Task.sleep(for: .milliseconds(5)) }
        await m.pollAutoCode(force: true)
        gate.open()
        await first.value
        #expect(answers == [.listed([])], "a late reply overwrote a newer one")
    }

    @Test func a404ClearsWhatWasListedButNotWhatWasSeen() async {
        let m = ServeManager(resolvedMode: .success(.external(port: 5000)))
        m.instance.state = .running(port: 5000)
        m.instance.authToken = "tok"
        m.autoCodeJobsReader = { _ in (404, nil) }
        var answers: [AutoCodeEndedAnswer] = []
        m.onAutoCodeEnded = { answers.append($0) }
        await m.pollAutoCode(force: true)
        #expect(answers == [.unavailable])
    }
}

@MainActor
@Suite struct AutoCodeRingAndHygieneTests {

    /// The arc's colours are resolved in the view's appearance, again when it changes mid-run.
    @Test func theRingFollowsTheAppearance() throws {
        let ring = SidebarActivityRing(fraction: 0.5)
        ring.appearance = NSAppearance(named: .aqua)
        let light = ring.strokeColorsForTesting
        ring.appearance = NSAppearance(named: .darkAqua)
        let dark = ring.strokeColorsForTesting
        #expect(light.count == 2 && dark.count == 2)
        #expect(light[0] != dark[0], "the track kept its light colour in Dark")
    }

    /// A fleet made by a test never shares the app's store, whose lines live in `.standard`.
    @Test func aFleetsDefaultStoreIsNotTheApps() {
        #expect(ServeFleet().screenReading !== ScreenReadingStore.shared)
    }
}
