import Foundation
import Testing
@testable import Bristlenose

/// The Swift half of the document-identity wire contract, plus the
/// BridgeHandler transitions the two identity messages drive. The Python half
/// lives in tests/test_server_status_page.py; the two vocabularies are held
/// together by tests/test_status_page_identity_parity.py, which reads both
/// sources as text (a fixture would be a third copy to drift).
struct StatusPageOutcomeTests {

    /// Raw values ARE the wire vocabulary — pin them as literals, so a rename
    /// here fails a named test instead of silently decoding to `.unknown`.
    @Test func rawValuesMatchTheWireVocabulary() {
        #expect(StatusPageOutcome.noRun.rawValue == "no-run")
        #expect(StatusPageOutcome.failed.rawValue == "failed")
        #expect(StatusPageOutcome.cancelled.rawValue == "cancelled")
        #expect(StatusPageOutcome.unknown.rawValue == "unknown")
    }

    @Test func decodeIsTolerant() {
        #expect(StatusPageOutcome(bridgeValue: "no-run") == .noRun)
        #expect(StatusPageOutcome(bridgeValue: "failed") == .failed)
        #expect(StatusPageOutcome(bridgeValue: "cancelled") == .cancelled)
        // A newer serve's outcome an older shell doesn't know: still a status
        // page, only the reason goes unnamed. Never a crash, never `.spa`.
        #expect(StatusPageOutcome(bridgeValue: "some-future-outcome") == .unknown)
        #expect(StatusPageOutcome(bridgeValue: nil) == .unknown)
    }
}

/// BridgeHandler's documentState transitions — the three writers and only
/// those three: `ready`, `status-page`, and `reset()`.
@MainActor
struct BridgeHandlerDocumentStateTests {

    @Test func startsLoading() {
        #expect(BridgeHandler().documentState == .loading)
    }

    @Test func readyMessageIdentifiesTheSPA() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.documentState == .spa)
    }

    @Test func statusPageMessageIdentifiesTheStatusPage() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "status-page", "outcome": "failed"])
        #expect(bridge.documentState == .statusPage(.failed))
    }

    @Test func statusPageMessageWithoutOutcomeStillIdentifies() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "status-page"])
        #expect(bridge.documentState == .statusPage(.unknown))
    }

    @Test func resetReturnsToLoading() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "ready"])
        bridge.reset()
        #expect(bridge.documentState == .loading)
    }

    /// The full D1-C reconciliation cycle at the message level: switch away
    /// (reset → loading), land on a failed project (status-page), switch to a
    /// good one (reset → loading), SPA arrives (ready).
    @Test func projectSwitchCycle() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.documentState == .spa)
        bridge.reset()
        #expect(bridge.documentState == .loading)
        bridge.handleMessage(["type": "status-page", "outcome": "no-run"])
        #expect(bridge.documentState == .statusPage(.noRun))
        bridge.reset()
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.documentState == .spa)
    }
}
