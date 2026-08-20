import Combine
import Foundation
import Testing
@testable import Bristlenose

/// Stage 3b's first structural step, and the one whose failure is silent.
///
/// `ServeManager` no longer stores its serve state — `ServeInstance` does, and
/// the manager forwards. A nested `ObservableObject` does **not** propagate
/// through `@EnvironmentObject`: without the explicit re-publish in
/// `ServeManager.init`, every `serveManager.state` read still returns the right
/// value and no view is ever told to re-read it. Nothing throws, nothing logs;
/// the boot spinner simply never clears.
///
/// So the forwarding gets a test rather than a comment. Delete the
/// `instanceObservation` sink and these fail; that is the whole point.
@Suite("ServeInstance observation forwarding")
@MainActor
struct ServeInstanceObservationTests {

    @Test func aStateChangeOnTheInstanceNotifiesTheManagersObservers() {
        let manager = ServeManager()
        var notifications = 0
        let sink = manager.objectWillChange.sink { _ in notifications += 1 }
        defer { sink.cancel() }

        manager.instance.state = .running(port: 51234)

        #expect(notifications == 1)
    }

    @Test func everyForwardedPropertyReachesTheManagersObservers() {
        let manager = ServeManager()
        var notifications = 0
        let sink = manager.objectWillChange.sink { _ in notifications += 1 }
        defer { sink.cancel() }

        manager.instance.outputLines = ["a line"]
        manager.instance.serverVersion = "0.26.0"
        manager.instance.agentActiveNow = true
        manager.instance.authToken = "tok"
        manager.instance.currentProjectPath = "/Users/x/study"

        #expect(notifications == 5)
    }

    /// The forwarders must read AND write through to the instance, or the ~50
    /// existing `serveManager.*` call sites silently diverge from the state the
    /// process machinery actually mutates.
    @Test func theManagersAccessorsAreTheInstancesValues() {
        let manager = ServeManager()

        manager.instance.state = .running(port: 4242)
        #expect(manager.state == .running(port: 4242))
        #expect(manager.runningPort == 4242)

        manager.state = .failed(error: "boom")
        #expect(manager.instance.state == .failed(error: "boom"))
        #expect(manager.runningPort == nil)

        manager.instance.currentProjectPath = "/p/A"
        #expect(manager.currentProjectPath == "/p/A")
    }

    /// `mcpMounted` answers "does this build have the mcp extra" and is
    /// identical across every instance; `projectKey` names one global
    /// file with seven independent delete edges. Both were misclassified as
    /// per-serve on the first pass — per-instance, the second would let one
    /// project's start delete another's handshake while the first still
    /// published "exposed", which is the defect `3ac773fa` closed.
    @Test func fleetLevelStateDidNotMoveOntoTheInstance() {
        let manager = ServeManager()
        #expect(manager.mcpMounted == false)
        #expect(manager.projectKey == nil)
    }
}
