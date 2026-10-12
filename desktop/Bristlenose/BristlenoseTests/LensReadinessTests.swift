import Foundation
import Testing
@testable import Bristlenose

/// Progressive lenses, the native half (docs/design-progressive-lenses.md
/// Phase 0 step 3): the SPA posts `lens-availability`; the rail, the outline,
/// the ⌘-number menu and `activateLens` read `BridgeHandler.lensReadiness`.
@MainActor
struct LensReadinessTests {

    // MARK: - Parsing the message

    @Test func onlyAnExplicitFalseWithholdsALens() {
        let readiness = LensReadiness(message: [
            "sessions": true, "quotes": false, "signals": false, "project": "no",
        ])
        #expect(readiness.unavailable == [.quotes, .signals])
        #expect(readiness.allows(.sessions))
        #expect(readiness.allows(.project), "a string is not a refusal")
        #expect(readiness.allows(.discussion), "a lens the message does not name stays allowed")
        // No numeric case: a JS `0` arrives over WKWebView as NSNumber, which
        // bridges to Bool, so a test literal here would pin the test, not the wire.
    }

    @Test func unknownLensIdsAreIgnored() {
        #expect(LensReadiness(message: ["specimen": false, "nonsense": false]) == .all)
    }

    @Test func allAllowsEveryLens() {
        for tab in Tab.allCases { #expect(LensReadiness.all.allows(tab)) }
    }

    // MARK: - The bridge

    @Test func theMessageSetsReadinessAndResetClearsIt() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "lens-availability",
                              "lenses": ["sessions": true, "quotes": false, "signals": false]])
        #expect(bridge.lensReadiness.unavailable == [.quotes, .signals])

        // A selection change: the next document says what it withholds.
        bridge.reset()
        #expect(bridge.lensReadiness == .all)
    }

    @Test func aStatusPageClearsTheSPAsLastPost() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "lens-availability", "lenses": ["quotes": false]])
        bridge.handleMessage(["type": "status-page", "outcome": "in-progress"])
        #expect(bridge.lensReadiness == .all)
    }

    @Test func aMalformedMessageWithholdsNothing() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "lens-availability", "lenses": "not a dictionary"])
        #expect(bridge.lensReadiness == .all)
    }

    /// While the document loads, an activation is queued (`LensActivation`), which
    /// is observable here; once the SPA is up it becomes a JS call this test cannot
    /// see. So the floor is pinned on the queue: a withheld lens is never queued,
    /// and an allowed one still is (the guard is per lens, not a blanket refusal).
    @Test func aWithheldLensIsNeverQueued() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "lens-availability", "lenses": ["quotes": false]])
        bridge.activateLens(.quotes)
        #expect(bridge.pendingLensIntent == nil)
        bridge.activateLens(.sessions)
        #expect(bridge.pendingLensIntent == .sessions)
    }
}
