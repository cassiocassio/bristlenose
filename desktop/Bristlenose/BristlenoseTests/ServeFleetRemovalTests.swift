import Foundation
import Testing
@testable import Bristlenose

/// Removing a project from the sidebar must stop that project's sidecar.
///
/// This is the successor to `dropParked(forPaths:)`, which is called from
/// **outside** `ServeManager` (`ContentView.swift:1212`, `:1238`) precisely so a
/// warm sidecar is not left serving a study the researcher deleted. Stage 3b
/// deletes the warm pool, and the obligation does not travel with it — it has
/// to be written.
///
/// It cannot ride on the reaping sweep either. `ServeReaping` answers from the
/// roster, and removal is not a window event: a removed project may still have
/// a window open on it at the instant of removal, so the sweep would say
/// `.keep`. Removal is its own trigger, and this pins that it exists.
@Suite("ServeFleet — project removal")
@MainActor
struct ServeFleetRemovalTests {

    private static let removed = UUID()
    private static let kept = UUID()

    @Test func removingAProjectDiscardsItsManager() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.removed).instance.state = .running(port: 5000)
        fleet.manager(for: Self.kept).instance.state = .running(port: 5001)

        fleet.discard(Self.removed)

        #expect(fleet.managers[Self.removed] == nil)
        #expect(fleet.runningProjects == [Self.kept])
    }

    /// The reason removal needs its own trigger rather than reusing the sweep.
    @Test func theReapingSweepAloneWouldKeepARemovedProjectThatStillHasAWindow() {
        let verdict = ServeReaping.verdict(
            project: Self.removed,
            shownProjects: [Self.removed],   // the window has not closed yet
            unshownFor: nil
        )
        #expect(verdict == .keep)
    }

    /// And removal must not take a neighbour with it — the failure that would
    /// look like "deleting one study killed the one I was reading".
    @Test func removingOneProjectLeavesTheOthersServing() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.removed).instance.state = .running(port: 5000)
        let survivor = fleet.manager(for: Self.kept)
        survivor.instance.state = .running(port: 5001)
        fleet.frontedProject = Self.kept

        fleet.discard(Self.removed)

        #expect(fleet.managers[Self.kept] === survivor)
        #expect(survivor.runningPort == 5001)
        #expect(fleet.frontedProject == Self.kept)
    }

    /// Removing the exposed project must clear exposure, or the handshake would
    /// keep naming a study that no longer exists.
    @Test func removingTheExposedProjectClearsExposure() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.removed)
        fleet.setExposed(Self.removed)

        fleet.discard(Self.removed)

        #expect(fleet.exposedProject == nil)
    }
}
