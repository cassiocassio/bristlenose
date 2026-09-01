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

/// The pending-intent lifecycle (P3): queued on a lit-but-loading rail,
/// replayed exactly once on `ready`, discarded by a status page, cleared by
/// a project switch. Dispatch itself is unobservable here (no WKWebView), so
/// these assert the slot and the replayed flag — the seams `ContentView`'s
/// memory restore yields to.
@MainActor
struct BridgeHandlerLensIntentTests {

    private func litLoadingBridge() -> BridgeHandler {
        BridgeHandler()  // fresh bridge: documentState .loading
    }

    @Test func clickWhileLoadingQueues() {
        let bridge = litLoadingBridge()
        bridge.activateLens(.quotes)
        #expect(bridge.pendingLensIntent == .quotes)
        #expect(!bridge.lensIntentReplayed)
    }

    @Test func lastClickWins() {
        let bridge = litLoadingBridge()
        bridge.activateLens(.quotes)
        bridge.activateLens(.analysis)
        #expect(bridge.pendingLensIntent == .analysis)
    }

    @Test func queueDoesNotConsultTheMirror() {
        // `lensesAvailable` dims the menu; it must NOT gate the queue — the
        // mirror can lag the lit rows by a render, and a stale-false mirror
        // was silently eating boot-window clicks (1 Sep 2026). Reachability
        // belongs to the affordance gates alone.
        let bridge = BridgeHandler()
        bridge.lensesAvailable = false
        bridge.activateLens(.quotes)
        #expect(bridge.pendingLensIntent == .quotes)
    }

    @Test func readyConsumesTheIntentOnce() {
        let bridge = litLoadingBridge()
        bridge.activateLens(.quotes)
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.pendingLensIntent == nil)
        #expect(bridge.lensIntentReplayed)
        #expect(bridge.documentState == .spa)
    }

    @Test func readyWithNoIntentDoesNotClaimAReplay() {
        // The flag gates ContentView's lens-memory restore — a plain ready
        // with nothing queued must leave the restore free to run.
        let bridge = litLoadingBridge()
        bridge.handleMessage(["type": "ready"])
        #expect(!bridge.lensIntentReplayed)
    }

    @Test func statusPageDiscardsTheIntent() {
        // Honouring "go to Quotes" against a failure page would be
        // meaningless — the queued intent dies with the lit state that
        // took it (the expensive walk-back, in full).
        let bridge = litLoadingBridge()
        bridge.activateLens(.quotes)
        bridge.handleMessage(["type": "status-page", "outcome": "failed"])
        #expect(bridge.pendingLensIntent == nil)
        #expect(!bridge.lensIntentReplayed)
    }

    @Test func projectSwitchClearsIntentAndReplayFlag() {
        let bridge = litLoadingBridge()
        bridge.activateLens(.quotes)
        bridge.handleMessage(["type": "ready"])
        #expect(bridge.lensIntentReplayed)
        bridge.reset()
        #expect(bridge.pendingLensIntent == nil)
        #expect(!bridge.lensIntentReplayed)
    }
}
