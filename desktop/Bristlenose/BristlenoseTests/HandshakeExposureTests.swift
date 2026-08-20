import Foundation
import Testing
@testable import Bristlenose

/// The V1 scope rule, at the two points where the obvious answer and the
/// correct one differ.
///
/// Both were found by using the app rather than reading it. A single
/// `exposedProject` slot produced five different answers across five
/// consecutive tool calls (not-open, foo, IKEA, foo, not-open) because reaped
/// sidecars dropped a handshake the slot still pointed at. And exposure tied
/// to serve liveness would have left a closed window readable for the 90 s of
/// `ServeReaping.defaultGrace`.
struct HandshakeExposureTests {

    private let foo = UUID()
    private let ikea = UUID()

    private func candidate(_ name: String, port: Int = 8150,
                           ready: Bool = true, running: Bool = true) -> HandshakeExposure.Candidate {
        HandshakeExposure.Candidate(
            path: "/Users/r/\(name)",
            name: name,
            state: running ? .running(port: port) : .idle,
            instanceID: ready ? "inst-\(name)" : nil,
            token: ready ? "tok-\(name)" : nil,
            key: ready ? "key-\(name)" : nil
        )
    }

    // MARK: - Scope follows windows, not serves

    @Test func aWindowlessProjectIsOutOfScopeEvenWhileItsServeRuns() {
        // The 90-second grace period exists so ⌘W-then-Dock-click is free. It
        // must not also mean "readable for 90 seconds after you closed it".
        let entries = HandshakeExposure.entries(
            candidates: [foo: candidate("foo")],
            shown: [],                       // window closed; sidecar still warm
            agentAccess: { _ in true })
        #expect(entries.isEmpty)
    }

    @Test func permissionWithoutAWindowIsNotScope() {
        let entries = HandshakeExposure.entries(
            candidates: [foo: candidate("foo")],
            shown: [],
            agentAccess: { _ in true })
        #expect(entries.isEmpty)
    }

    @Test func aWindowWithoutPermissionIsNotScope() {
        // Open on screen and invisible to the agent. Open is not shared.
        let entries = HandshakeExposure.entries(
            candidates: [foo: candidate("foo")],
            shown: [foo],
            agentAccess: { _ in false })
        #expect(entries.isEmpty)
    }

    @Test func bothConjunctsMakeItReachable() {
        let entries = HandshakeExposure.entries(
            candidates: [foo: candidate("foo")],
            shown: [foo],
            agentAccess: { _ in true })
        #expect(entries.map(\.name) == ["foo"])
        #expect(entries.first?.key == "key-foo")
    }

    // MARK: - Plural

    @Test func twoOpenPermittedProjectsAreBothExposed() {
        // The whole point of the model: the slot is gone, so there is no
        // winner to designate and nothing to flap between.
        let entries = HandshakeExposure.entries(
            candidates: [foo: candidate("foo", port: 1), ikea: candidate("ikea", port: 2)],
            shown: [foo, ikea],
            agentAccess: { _ in true })
        #expect(entries.count == 2)
        #expect(Set(entries.map(\.port)) == [1, 2])
    }

    @Test func theFileIsOrderedSoItDoesNotChurn() {
        // An unordered rewrite changes the file on every poll and hands the
        // proxy a spurious change each time.
        let a = HandshakeExposure.entries(
            candidates: [foo: candidate("foo"), ikea: candidate("ikea")],
            shown: [foo, ikea], agentAccess: { _ in true })
        let b = HandshakeExposure.entries(
            candidates: [ikea: candidate("ikea"), foo: candidate("foo")],
            shown: [ikea, foo], agentAccess: { _ in true })
        #expect(a == b)
        #expect(a.map(\.name) == ["foo", "ikea"])
    }

    // MARK: - Not-ready is not exposed

    @Test func aServeWithNoTokenYetIsNotWrittenIntoTheHandshake() {
        // instanceID and token are nil on every start until the first health
        // read lands. Writing an entry then would advertise an address with no
        // credential — the gap that made the old badge over-claim.
        let entries = HandshakeExposure.entries(
            candidates: [foo: candidate("foo", ready: false)],
            shown: [foo], agentAccess: { _ in true })
        #expect(entries.isEmpty)
    }

    @Test func aStoppedServeIsNotWrittenEvenWhenItsWindowIsOpen() {
        let entries = HandshakeExposure.entries(
            candidates: [foo: candidate("foo", running: false)],
            shown: [foo], agentAccess: { _ in true })
        #expect(entries.isEmpty)
    }

    // MARK: - The readable set is deliberately wider than the handshake

    /// A project that is in scope but whose serve has not finished starting
    /// still belongs in the readable set: the point of that set is to name
    /// everything the gate must NOT close, and closing the gate on a serve
    /// that is about to become reachable would make it refuse its own first
    /// question.
    @Test func readableIncludesAnInScopeServeThatIsNotReadyYet() {
        let readable = HandshakeExposure.readableProjects(
            candidates: [foo: candidate("foo", ready: false)],
            shown: [foo], agentAccess: { _ in true })
        #expect(readable == [foo])
    }

    @Test func readableExcludesEverythingOutOfScope() {
        let readable = HandshakeExposure.readableProjects(
            candidates: [foo: candidate("foo"), ikea: candidate("ikea")],
            shown: [foo],
            agentAccess: { _ in true })
        #expect(readable == [foo])
    }

    @Test func readableExcludesAnOpenProjectWithoutPermission() {
        let readable = HandshakeExposure.readableProjects(
            candidates: [foo: candidate("foo")],
            shown: [foo],
            agentAccess: { _ in false })
        #expect(readable.isEmpty)
    }
}
