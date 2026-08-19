import Combine
import Foundation
import Testing
@testable import Bristlenose

/// The fleet: one manager per project, plus the app-level facts.
@Suite("ServeFleet")
@MainActor
struct ServeFleetTests {

    private static let a = UUID()
    private static let b = UUID()

    @Test func oneManagerPerProject_andTheSameOneEachTime() {
        let fleet = ServeFleet()
        let first = fleet.manager(for: Self.a)
        let second = fleet.manager(for: Self.a)
        #expect(first === second)
        #expect(fleet.manager(for: Self.b) !== first)
        #expect(fleet.managers.count == 2)
    }

    /// Creating a manager must not read as "this project is running", or the
    /// reaping sweep would keep every project that was ever opened.
    @Test func creatingAManagerDoesNotStartASidecar() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a)
        #expect(fleet.isRunning(Self.a) == false)
        #expect(fleet.runningProjects.isEmpty)
    }

    /// The same silent-failure contract as `ServeManager` over `ServeInstance`,
    /// one level up: a nested ObservableObject does not propagate on its own.
    @Test func aManagersChangeReachesTheFleetsObservers() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        var notifications = 0
        let sink = fleet.objectWillChange.sink { _ in notifications += 1 }
        defer { sink.cancel() }

        manager.instance.state = .running(port: 5000)

        #expect(notifications >= 1)
        #expect(fleet.isRunning(Self.a))
        #expect(fleet.runningProjects == [Self.a])
    }

    @Test func discardingStopsObservingAndClearsDesignations() {
        let fleet = ServeFleet()
        let manager = fleet.manager(for: Self.a)
        fleet.frontedProject = Self.a
        fleet.setExposed(Self.a)

        fleet.discard(Self.a)

        #expect(fleet.managers[Self.a] == nil)
        #expect(fleet.frontedProject == nil)
        #expect(fleet.exposedProject == nil)

        var notifications = 0
        let sink = fleet.objectWillChange.sink { _ in notifications += 1 }
        defer { sink.cancel() }
        manager.instance.state = .running(port: 5001)
        #expect(notifications == 0)
    }

    @Test func discardingOneProjectLeavesTheOtherAlone() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a)
        let keep = fleet.manager(for: Self.b)
        fleet.frontedProject = Self.b

        fleet.discard(Self.a)

        #expect(fleet.managers[Self.b] === keep)
        #expect(fleet.frontedProject == Self.b)
    }

    /// Two studies serving at once is the entire point of the stage.
    @Test func twoProjectsRunSimultaneously() {
        let fleet = ServeFleet()
        fleet.manager(for: Self.a).instance.state = .running(port: 5000)
        fleet.manager(for: Self.b).instance.state = .running(port: 5001)
        #expect(fleet.runningProjects == [Self.a, Self.b])
        #expect(fleet.manager(for: Self.a).runningPort != fleet.manager(for: Self.b).runningPort)
    }

    /// Exposure follows turning Agent Access on, not fronting a window — the
    /// answer §1c gave and the review restored. Fronting must not move it.
    @Test func frontingAWindowDoesNotMoveExposure() {
        let fleet = ServeFleet()
        fleet.setExposed(Self.a)
        fleet.frontedProject = Self.b
        #expect(fleet.exposedProject == Self.a)
    }
}
