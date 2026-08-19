import Foundation
import Testing
@testable import Bristlenose

/// Stage 3b's teardown decision. The review called refcounted teardown under
/// unordered `.onDisappear` the stage's largest remaining risk; these pin the
/// shape chosen to defuse it — derived from the roster, never counted.
@Suite("ServeReaping")
struct ServeReapingTests {

    private static let a = UUID()
    private static let b = UUID()

    @Test func aProjectWithAWindowIsKept() {
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [Self.a, Self.b], unshownFor: nil) == .keep)
    }

    /// The §1e Q4 revision. Reaping the moment the last window closes brings
    /// back the multi-second cold boot on ⌘W-then-Dock-click, which is the
    /// commonest gesture in the app.
    @Test func losingItsLastWindowDoesNotReapImmediately() {
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [], unshownFor: nil) == .reapAfterGrace)
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [], unshownFor: .seconds(5)) == .reapAfterGrace)
    }

    @Test func graceExpiryReaps() {
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [], unshownFor: .seconds(90)) == .reapNow)
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [], unshownFor: .seconds(600)) == .reapNow)
    }

    /// Reopening within the grace period must be free — that is the entire
    /// reason the grace period exists.
    @Test func aWindowReopeningDuringGraceCancelsTheReap() {
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [Self.a], unshownFor: .seconds(60)) == .keep)
    }

    /// A warm cache is not worth a swap storm.
    @Test func memoryPressureSkipsGrace() {
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [], unshownFor: nil,
            memoryPressure: true) == .reapNow)
    }

    @Test func memoryPressureStillKeepsAProjectSomeoneIsLookingAt() {
        #expect(ServeReaping.verdict(
            project: Self.a, shownProjects: [Self.a], unshownFor: nil,
            memoryPressure: true) == .keep)
    }

    /// The property that makes a missed `.onDisappear` survivable: the verdict
    /// is a function of the roster, so a lost notification delays the next
    /// sweep's answer rather than losing it. Two identical sweeps agree.
    @Test func theSweepIsAFunctionOfTheRosterNotOfEventHistory() {
        let running: [UUID: Duration?] = [Self.a: nil, Self.b: .seconds(120)]
        let first = ServeReaping.sweep(running: running, shownProjects: [Self.a])
        let second = ServeReaping.sweep(running: running, shownProjects: [Self.a])
        #expect(first == second)
        #expect(first[Self.a] == .keep)
        #expect(first[Self.b] == .reapNow)
    }

    /// Two studies open is the whole point of the stage — neither may reap the
    /// other.
    @Test func twoShownProjectsAreBothKept() {
        let verdicts = ServeReaping.sweep(
            running: [Self.a: nil, Self.b: nil], shownProjects: [Self.a, Self.b])
        #expect(verdicts[Self.a] == .keep)
        #expect(verdicts[Self.b] == .keep)
    }

    @Test func anEmptySweepIsNotACrash() {
        #expect(ServeReaping.sweep(running: [:], shownProjects: [Self.a]).isEmpty)
    }
}
