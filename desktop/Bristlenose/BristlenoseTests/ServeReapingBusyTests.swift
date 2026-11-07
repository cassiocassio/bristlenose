import Foundation
import Testing
@testable import Bristlenose

// A study's server that reports paid or unrecoverable work in flight is held, not reaped
// (bristlenose/server/busy.py; docs/design-perf-ledger.md). The rule, the parse, and the fleet.

@Suite("Reaping holds a busy study's server")
@MainActor
struct ServeReapingBusyTests {

    private static let a = UUID()
    private static let b = UUID()
    private static let grace = ServeReaping.defaultGrace
    private static let ceiling = ServeReaping.busyCeiling

    private func verdict(shown: Set<UUID> = [], unshownFor: Duration? = .seconds(120),
                         memoryPressure: Bool = false, busyFor: Duration? = nil) -> ServeReaping.Verdict {
        ServeReaping.verdict(project: Self.a, shownProjects: shown, unshownFor: unshownFor,
                             memoryPressure: memoryPressure, busyFor: busyFor)
    }

    // MARK: the pure rule

    @Test func aBusyStudyPastItsGraceIsHeldNotReaped() {
        #expect(verdict(busyFor: .zero) == .keepWhileBusy)
        #expect(verdict(busyFor: .seconds(600)) == .keepWhileBusy)
    }

    @Test func anIdleStudyPastItsGraceIsReapedAsBefore() {
        #expect(verdict(busyFor: nil) == .reapNow)
    }

    @Test func aBusyStudyStillWaitsOutTheGraceFirst() {
        #expect(verdict(unshownFor: .seconds(10), busyFor: .zero) == .reapAfterGrace)
        #expect(verdict(unshownFor: nil, busyFor: .zero) == .reapAfterGrace)
    }

    @Test func aHeldStudyIsReapedOnceTheCeilingPasses() {
        #expect(verdict(busyFor: Self.ceiling - .seconds(1)) == .keepWhileBusy)
        #expect(verdict(busyFor: Self.ceiling) == .reapNow)   // a wedged job must not hold a server for ever
    }

    @Test func memoryPressureBeatsBusy() {
        #expect(verdict(memoryPressure: true, busyFor: .zero) == .reapNow)
    }

    @Test func aWindowBeatsBusy() {
        #expect(verdict(shown: [Self.a], busyFor: .zero) == .keep)
    }

    @Test func theCeilingIsFiniteAndTheRecheckIsShorterThanIt() {
        #expect(ServeReaping.busyRecheck < ServeReaping.busyCeiling)
        #expect(ServeReaping.busyCeiling <= .seconds(60 * 60))
    }

    @Test func theSweepHoldsOnlyTheBusyOne() {
        let running: [UUID: Duration?] = [Self.a: .seconds(120), Self.b: .seconds(120)]
        let out = ServeReaping.sweep(running: running, shownProjects: [], busyFor: [Self.a: .zero])
        #expect(out[Self.a] == .keepWhileBusy)
        #expect(out[Self.b] == .reapNow)
    }

    // MARK: the parse

    @Test func theBusyAnswerIsReadFromTheServersReply() {
        #expect(AgentActivity.parseBackgroundBusy(["busy": true, "kinds": ["autocode"]]) == true)
        #expect(AgentActivity.parseBackgroundBusy(["busy": false, "kinds": []]) == false)
        #expect(AgentActivity.parseBackgroundBusy(["kinds": []]) == nil)      // not that shape: leave the last reading
        #expect(AgentActivity.parseBackgroundBusy(["busy": "yes"]) == nil)
    }

    // MARK: the fleet

    @Test func theFleetHoldsABusyServeAndReapsItOnceItIsIdle() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)
        manager.instance.noteBackgroundBusy(true)

        fleet.sweep(shownProjects: [], grace: .zero)
        #expect(fleet.managers[Self.a] != nil, "a busy study's server was reaped")

        manager.instance.noteBackgroundBusy(false)
        fleet.sweep(shownProjects: [], grace: .zero)
        #expect(fleet.managers[Self.a] == nil, "an idle one was not")
    }

    @Test func aHeldServeIsReapedAnywayPastTheCeiling() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)
        manager.instance.noteBackgroundBusy(true)

        fleet.sweep(shownProjects: [], grace: .zero, busyCeiling: .zero)   // the ceiling is already spent
        #expect(fleet.managers[Self.a] == nil)
    }

    @Test func memoryPressureReapsABusyServe() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)
        manager.instance.noteBackgroundBusy(true)

        fleet.sweep(shownProjects: [], memoryPressure: true)
        #expect(fleet.managers[Self.a] == nil)
    }

    @Test func aStudyThatRegainsAWindowIsNotHeldOrReaped() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)
        manager.instance.noteBackgroundBusy(true)

        fleet.sweep(shownProjects: [], grace: .zero)            // held
        fleet.sweep(shownProjects: [Self.a], grace: .zero)      // looked at again
        manager.instance.noteBackgroundBusy(false)
        fleet.sweep(shownProjects: [Self.a], grace: .zero)
        #expect(fleet.managers[Self.a] != nil)
    }

    @Test func aHeldServeIsLookedAtAgainOnItsOwnAndReapedOnceIdle() async throws {
        // The timer is the decision: nothing else sweeps after the last window closes.
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)
        manager.instance.noteBackgroundBusy(true)

        fleet.sweep(shownProjects: [], grace: .zero, busyRecheck: .milliseconds(50))
        #expect(fleet.managers[Self.a] != nil, "held first")
        manager.instance.noteBackgroundBusy(false)
        // A hang bound, not a speed claim: under a loaded full suite the 50 ms recheck can take
        // seconds to come round (7 Nov 2026), so wait for the reap instead of for a fixed 400 ms.
        for _ in 0..<600 where fleet.managers[Self.a] != nil {
            try await Task.sleep(for: .milliseconds(50))
        }
        #expect(fleet.managers[Self.a] == nil, "the recheck never came back to reap it")
    }

    @Test func aWindowInTheMiddleRestartsTheCeiling() async throws {
        // The ceiling bounds one continuous window-less hold. A study looked at again, then closed,
        // is a fresh hold: it must not be reaped for time spent before the window came back.
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)
        manager.instance.noteBackgroundBusy(true)
        let ceiling = Duration.milliseconds(150)

        fleet.sweep(shownProjects: [], grace: .zero, busyCeiling: ceiling)         // held, clock starts
        try await Task.sleep(for: .milliseconds(250))                              // the ceiling is now spent
        fleet.sweep(shownProjects: [Self.a], grace: .zero, busyCeiling: ceiling)   // looked at again
        fleet.sweep(shownProjects: [], grace: .zero, busyCeiling: ceiling)         // closed again
        #expect(fleet.managers[Self.a] != nil, "the ceiling counted time from before the window came back")
    }

    @Test func aNewServeStartsNotBusy() {
        let manager = ServeManager(resolvedMode: .success(.external(port: 1)))
        manager.instance.noteBackgroundBusy(true)
        manager.start(projectPath: "/studies/a")
        #expect(manager.instance.backgroundBusy == false)
    }

    // MARK: the poll

    private func running(port: Int = 5000) -> ServeManager {
        let m = ServeManager(resolvedMode: .success(.external(port: port)))
        m.instance.state = .running(port: port)
        m.instance.authToken = "tok"
        return m
    }

    @Test func aBusyReadingMarksTheServeBusyAndAnIdleOneClearsIt() async {
        let m = running()
        m.backgroundWorkReader = { _ in ["busy": true, "kinds": ["signals"]] }
        await m.pollBackgroundWork()
        #expect(m.instance.backgroundBusy == true)
        m.backgroundWorkReader = { _ in ["busy": false, "kinds": []] }
        await m.pollBackgroundWork()
        #expect(m.instance.backgroundBusy == false)
    }

    @Test func aFailedOrMalformedReadingLeavesTheLastOneStanding() async {
        let m = running()
        m.instance.noteBackgroundBusy(true)
        m.backgroundWorkReader = { _ in nil }
        await m.pollBackgroundWork()
        #expect(m.instance.backgroundBusy == true)
        m.backgroundWorkReader = { _ in ["kinds": []] }
        await m.pollBackgroundWork()
        #expect(m.instance.backgroundBusy == true)
    }

    @Test func theReadingCarriesTheBearerToAnAuthedRoute() async {
        let m = running(port: 5123)
        var seen: URLRequest?
        m.backgroundWorkReader = { request in seen = request; return ["busy": false] }
        await m.pollBackgroundWork()
        #expect(seen?.url?.absoluteString == "http://127.0.0.1:5123/api/background-work")
        #expect(seen?.value(forHTTPHeaderField: "Authorization") == "Bearer tok")
    }

    @Test func aReadingThatLandsAfterTheServeWasReplacedIsIgnored() async {
        let m = running(port: 5000)
        m.backgroundWorkReader = { _ in
            m.instance.state = .running(port: 6000)      // a restart took a new port mid-request
            return ["busy": true]
        }
        await m.pollBackgroundWork()
        #expect(m.instance.backgroundBusy == false)
    }

    @Test func noTokenNoReading() async {
        let m = ServeManager(resolvedMode: .success(.external(port: 5000)))
        m.instance.state = .running(port: 5000)
        var asked = false
        m.backgroundWorkReader = { _ in asked = true; return ["busy": true] }
        await m.pollBackgroundWork()
        #expect(asked == false)
    }
}
