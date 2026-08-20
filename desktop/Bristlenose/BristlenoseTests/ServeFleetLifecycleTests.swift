import Foundation
import Testing
@testable import Bristlenose

/// The wiring, not the decisions.
///
/// `ServeReaping` and `ServeEnvStaleness` had tests from the day they were
/// written and were called from nowhere — a green suite asserting functions
/// nobody ran. These pin that the fleet actually acts on them, which is the
/// difference between a decision and a behaviour.
@Suite("ServeFleet lifecycle wiring")
@MainActor
struct ServeFleetLifecycleTests {

    private static let a = UUID()
    private static let b = UUID()

    @Test func aStudyWithNoWindowIsNotReapedImmediately() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)

        fleet.sweep(shownProjects: [])

        // Grace, not instant teardown: closing the last window and reopening it
        // must not cost a multi-second cold boot.
        #expect(fleet.managers[Self.a] != nil)
        #expect(fleet.isRunning(Self.a))
    }

    @Test func memoryPressureReapsWithoutWaiting() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)

        fleet.sweep(shownProjects: [], memoryPressure: true)

        #expect(fleet.managers[Self.a] == nil)
    }

    @Test func aSweepNeverTouchesAStudyThatStillHasAWindow() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)
        fleet.manager(for: Self.b).instance.state = .running(port: 5001)

        fleet.sweep(shownProjects: [Self.a, Self.b], memoryPressure: true)

        #expect(fleet.runningProjects == [Self.a, Self.b])
    }

    /// The sweep is a function of the roster, so calling it repeatedly with the
    /// same input must not accumulate anything. This is what makes a missed
    /// `.onDisappear` survivable rather than fatal.
    @Test func repeatedSweepsAreIdempotent() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)
        for _ in 0..<5 { fleet.sweep(shownProjects: [Self.a]) }
        #expect(fleet.runningProjects == [Self.a])
    }

    /// Discard must STOP, not merely forget. Forgetting a running manager
    /// strands ~140 MB and a live port serving a study that was just deleted.
    @Test func discardingAProjectStopsItsSidecar() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        manager.instance.state = .running(port: 5000)

        fleet.discard(Self.a)

        #expect(fleet.managers[Self.a] == nil)
        #expect(manager.runningPort == nil, "discard left the sidecar running")
    }

    /// The prefs/consent fan-out. Asserts the ROUTING, not the restart: the
    /// restart itself is async (`shutdown` then `start`), so an immediate state
    /// read would be testing the clock. What is new here is which instance is
    /// told to go now and which is told to wait.
    @Test func anEnvChangeDefersABackgroundInstanceButNotTheExposedOne() {
        let fleet = ServeFleet()
        for (id, port) in [(Self.a, 5000), (Self.b, 5001)] {
            let m = fleet.manager(for: id)
            m.instance.state = .running(port: port)
            m.instance.currentProjectPath = "/p/\(id)"
        }
        fleet.setExposed(Self.a)
        fleet.frontedProject = nil

        fleet.applyEnvChange()

        // `a` is reachable by an agent with nobody watching, so it goes now —
        // the exception that makes lazy safe. Turn Anonymise on and it must not
        // keep serving real names out of a window no one is looking at.
        #expect(fleet.staleProjects.contains(Self.a) == false)
        // `b` is only reachable by looking at it, so it waits rather than
        // costing a cold report remount nobody asked for.
        #expect(fleet.staleProjects.contains(Self.b))
    }

    /// The other half: a deferred instance must actually be restarted when
    /// someone looks at it, or "lazy" is just "never".
    @Test func frontingAStaleStudyClearsItsStaleness() {
        let fleet = ServeFleet()
        let m = fleet.manager(for: Self.b)
        m.instance.state = .running(port: 5001)
        m.instance.currentProjectPath = "/p/b"
        fleet.applyEnvChange()
        #expect(fleet.staleProjects.contains(Self.b))

        fleet.front(Self.b)

        #expect(fleet.staleProjects.contains(Self.b) == false)
        #expect(fleet.frontedProject == Self.b)
    }

    /// The fleet must designate exactly one handshake owner, or a second
    /// running project's 20-second poll deletes the exposed project's file.
    @Test func onlyTheExposedManagerOwnsTheHandshake() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a)
        fleet.manager(for: Self.b)

        fleet.setExposed(Self.a)

        #expect(fleet.manager(for: Self.a).handshakeOwner)
        #expect(fleet.manager(for: Self.b).handshakeOwner == false)
    }
}
