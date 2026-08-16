import Foundation
import Testing
import WebKit

@testable import Bristlenose

/// The storage-partition sharing rules. These are the two properties that
/// matter and neither is visible from reading the call site: siblings on one
/// serve must get the *same instance* (BroadcastChannel and WebKit process
/// consolidation both key off instance identity, not equality), and anything
/// else must not.
@Suite("Shared config store")
@MainActor
struct SharedConfigStoreTests {

    private func freshStore() -> SharedConfigStore {
        // The app uses the singleton; tests want isolation, and the initialiser
        // is private, so exercise the singleton and clear between cases.
        let store = SharedConfigStore.shared
        store.release(projectID: projectA)
        store.release(projectID: projectB)
        return store
    }

    private let projectA = UUID()
    private let projectB = UUID()

    @Test("sibling windows on one serve share a partition")
    func siblingsShareInstance() {
        let store = freshStore()
        let session = ServeSession(projectID: projectA, port: 8150)

        let first = store.dataStore(for: session)
        let second = store.dataStore(for: session)

        #expect(first === second, "identity, not equality — sharing is what enables BroadcastChannel")
    }

    @Test("different projects never share a partition")
    func projectsAreIsolated() {
        let store = freshStore()

        let a = store.dataStore(for: ServeSession(projectID: projectA, port: 8150))
        let b = store.dataStore(for: ServeSession(projectID: projectB, port: 8151))

        #expect(a !== b, "security rule 4 — no cross-project cookie/sessionStorage leakage")
    }

    @Test("a new port for the same project gets a fresh partition")
    func repointGetsFreshPartition() {
        let store = freshStore()

        let before = store.dataStore(for: ServeSession(projectID: projectA, port: 8150))
        let after = store.dataStore(for: ServeSession(projectID: projectA, port: 8151))

        // Cookies ignore port and every sidecar is 127.0.0.1, so reusing the
        // partition across a restart would replay the previous sidecar's cookie
        // at the new one.
        #expect(before !== after)
    }

    @Test("the superseded partition is dropped, not accumulated")
    func supersededPartitionIsReleased() {
        let store = freshStore()

        _ = store.dataStore(for: ServeSession(projectID: projectA, port: 8150))
        let afterFirst = store.partitionCount
        _ = store.dataStore(for: ServeSession(projectID: projectA, port: 8151))
        let afterSecond = store.dataStore(for: ServeSession(projectID: projectA, port: 8152))

        _ = afterSecond
        // One project, one live partition — however many times its sidecar has
        // restarted. Without the sweep these leak for the app's lifetime.
        #expect(store.partitionCount == afterFirst)
    }

    @Test("viewID is stable and distinguishes both axes")
    func viewIDIdentity() {
        let a = ServeSession(projectID: projectA, port: 8150)
        let samePortOtherProject = ServeSession(projectID: projectB, port: 8150)
        let sameProjectOtherPort = ServeSession(projectID: projectA, port: 8151)

        #expect(a.viewID == ServeSession(projectID: projectA, port: 8150).viewID)
        #expect(a.viewID != samePortOtherProject.viewID)
        #expect(a.viewID != sameProjectOtherPort.viewID,
                "the port must be in the view identity — a warm re-point has to re-mount")
    }
}
