import Foundation
import Testing
@testable import Bristlenose

/// `ServeInstance.startedByRetry`, the bit that turns the boot pane's Retry into
/// Send Feedback… once a retry has failed (`BootView.failureAction`).
///
/// Set only by `start(projectPath:isRetry: true)`; cleared by every other start
/// and by reaching `.running`. A manager resolved to `.failure` stands in for a
/// retry that fails at once (no sidecar to run, so `start()` returns at the mode
/// guard and the state stays failed); one resolved to `.external(port:)` for a
/// retry that succeeds without spawning anything.
@Suite("ServeManager retry bit", .serialized)
@MainActor
struct ServeManagerRetryTests {

    private static let port = 9_997

    private func failing() -> ServeManager {
        ServeManager(resolvedMode: .failure(.bundledSidecarMissing(expectedPath: "/nowhere")))
    }

    private func external() -> ServeManager {
        ServeManager(resolvedMode: .success(.external(port: Self.port)))
    }

    private func isFailed(_ state: ServeState) -> Bool {
        if case .failed = state { return true }
        return false
    }

    @Test func aRetryThatFailsAtOnceKeepsTheBit() {
        let m = failing()
        #expect(isFailed(m.state), "precondition: a manager with no sidecar starts failed")
        #expect(!m.startedByRetry)

        m.start(projectPath: "/p/a", isRetry: true)

        #expect(isFailed(m.state))
        #expect(m.startedByRetry)
    }

    @Test func aRetryThatSucceedsClearsTheBit() {
        let m = external()
        m.instance.state = .failed(error: .passthrough("boom"))

        m.start(projectPath: "/p/a", isRetry: true)

        #expect(m.state == .running(port: Self.port))
        #expect(!m.startedByRetry)
    }

    @Test func aPlainStartClearsTheBit() {
        // The failing manager, so the start returns before any `.running` could
        // clear the bit: what clears it here is the start itself.
        let m = failing()
        m.instance.startedByRetry = true

        m.start(projectPath: "/p/a")

        #expect(isFailed(m.state))
        #expect(!m.startedByRetry)
    }

    @Test func aSamePathStartWhileARetryBootsLeavesTheBit() {
        // A second window re-fronting the study mid-boot returns early; the
        // retry it interrupted is still the attempt that is booting.
        let m = external()
        m.instance.currentProjectPath = "/p/a"
        m.instance.state = .starting
        m.instance.startedByRetry = true

        m.start(projectPath: "/p/a")

        #expect(m.state == .starting)
        #expect(m.startedByRetry)
    }

    // MARK: - The bit on the instance, through a real boot's states

    /// The shipping path: a retry spawns the sidecar (`.starting`) and it dies
    /// (`.failed`). Only `.running` may clear the bit, or Send Feedback… never
    /// appears after a bundled retry fails.
    @Test func aRetryThatBootsAndFailsKeepsTheBit() {
        let instance = ServeInstance()
        instance.startedByRetry = true

        instance.state = .starting
        #expect(instance.startedByRetry)
        instance.state = .failed(error: .passthrough("exit 1"))
        #expect(instance.startedByRetry)
    }

    /// A retry that succeeded and the serve died later: that failure is a first
    /// failure again, so the pane offers Retry.
    @Test func aRetryThatSucceededThenDiedOffersRetryAgain() {
        let instance = ServeInstance()
        instance.startedByRetry = true

        instance.state = .running(port: Self.port)
        #expect(!instance.startedByRetry)
        instance.state = .failed(error: .passthrough("exit 1"))
        #expect(!instance.startedByRetry)
        #expect(BootView.failureAction(startedByRetry: instance.startedByRetry) == .retry)
    }
}
