import Foundation
import Testing

@testable import Bristlenose

/// How a remembered position is applied, which differs by lens.
///
/// The case worth pinning hardest is **Sessions**: its position is a route, not
/// a scroll offset, so restoring it means navigating. Everything else on the
/// lens list scrolls, and getting Sessions wrong would look like the anchor
/// silently doing nothing rather than like a bug. Decision #182, option B
/// (9 Nov 2026): each lens returns to the element the reader was on.
@Suite("Lens anchor")
struct LensAnchorTests {

    @Test("Quotes, Codebook and Signals scroll to the element")
    func scrollingLenses() {
        #expect(LensAnchor.action(lens: .quotes, anchor: "q-p1-10") == .scroll("q-p1-10"))
        #expect(LensAnchor.action(lens: .quotes, anchor: "theme-billing")
                == .scroll("theme-billing"))
        #expect(LensAnchor.action(lens: .codebook, anchor: "code-12") == .scroll("code-12"))
        // Until 9 Nov 2026 Signals came back at the top (decided 16 Aug).
        #expect(LensAnchor.action(lens: .signals, anchor: "signal-theme-theme-3--frustration")
                == .scroll("signal-theme-theme-3--frustration"))
    }

    @Test("Sessions navigates instead of scrolling")
    func sessionsNavigates() {
        // A transcript is a route. Scrolling to an element called "s3" would
        // find nothing and quietly leave the reader on the grid.
        #expect(LensAnchor.action(lens: .sessions, anchor: "s3") == .session("s3"))
        // A place with a paragraph travels whole: the SPA reported it and the
        // SPA's own address arrival applies it.
        #expect(LensAnchor.action(lens: .sessions, anchor: "s1#t-66") == .session("s1#t-66"))
    }

    @Test("Project, Discussion and Screens land at the top")
    func lensesWithoutPositions() {
        // Decision #182 (9 Nov 2026), superseding 16 Aug. Passing an anchor
        // anyway — a stale one from another lens — must still land at the top
        // rather than be honoured.
        #expect(LensAnchor.action(lens: .discussion, anchor: "s2@01:40") == .top)
        #expect(LensAnchor.action(lens: .project, anchor: "theme-billing") == .top)
        #expect(LensAnchor.action(lens: .screens, anchor: "theme-billing") == .top)
    }

    @Test("nothing remembered means the top")
    func noAnchorMeansTop() {
        #expect(LensAnchor.action(lens: .quotes, anchor: nil) == .top)
        #expect(LensAnchor.action(lens: .quotes, anchor: "") == .top)
        #expect(LensAnchor.action(lens: nil, anchor: "theme-billing") == .top)
    }

    @Test("only the lenses that can restore a position record one")
    func remembersPosition() {
        // The gate on *writing*. Without it, switching to Analysis would leave
        // the Quotes anchor on disk, and the next open would try to apply it.
        #expect(LensAnchor.remembersPosition(.quotes))
        #expect(LensAnchor.remembersPosition(.codebook))
        #expect(LensAnchor.remembersPosition(.sessions))
        #expect(LensAnchor.remembersPosition(.signals))
        #expect(!LensAnchor.remembersPosition(.discussion))
        #expect(!LensAnchor.remembersPosition(.project))
        #expect(!LensAnchor.remembersPosition(.screens))
        #expect(!LensAnchor.remembersPosition(nil))
    }

    @Test("every lens that records a position can also apply one")
    func recordAndApplyAgree() {
        // The two halves are separate switches over the same list, and a lens
        // added to one but not the other would store a position it then ignores
        // — silent, and only visible as "restore doesn't work on that lens".
        for tab in Tab.allCases {
            let applies = LensAnchor.action(lens: tab, anchor: "x") != .top
            #expect(applies == LensAnchor.remembersPosition(tab), "\(tab) disagrees")
        }
    }
}

/// The Sessions place the window remembers, and what a finished run does to it
/// (decision #182, 9 Nov 2026). Through the real message handler, the way the
/// SPA's `anchor-change` and `route-change` reach it.
@MainActor
@Suite("Lens anchor, through the bridge")
struct LensAnchorBridgeTests {

    @Test("a paragraph reported on a transcript is the place remembered")
    func theReportedParagraphIsThePlace() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "route-change", "url": "/report/sessions/s1"])
        #expect(bridge.restoreSessionID == "s1", "the session alone, before any report")
        bridge.handleMessage(["type": "anchor-change", "lens": "sessions", "anchor": "s1#t-66"])
        #expect(bridge.restoreSessionID == "s1#t-66")
        // Back at the top of the transcript: the session alone again.
        bridge.handleMessage(["type": "anchor-change", "lens": "sessions", "anchor": NSNull()])
        #expect(bridge.restoreSessionID == "s1")
    }

    @Test("another lens's anchor, or another transcript's paragraph, is not the place")
    func onlyThisTranscriptsParagraphCounts() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "route-change", "url": "/report/sessions/s2"])
        bridge.handleMessage(["type": "anchor-change", "lens": "quotes", "anchor": "q-p1-10"])
        #expect(bridge.restoreSessionID == "s2")
        // A paragraph from s1 still standing in the beat after moving to s2.
        bridge.handleMessage(["type": "anchor-change", "lens": "sessions", "anchor": "s1#t-66"])
        #expect(bridge.restoreSessionID == "s2")
    }

    @Test("a remembered Sessions place restores one way, bare or with a paragraph")
    func sessionsRestoreHasOnePath() {
        // `ContentView` restores straight after `activateLens`, whose
        // `switchToTab` goes out from a Task. A bare `s3` sent by the direct
        // shim call went out first, and the `switchToTab` then took the reader
        // to the grid; both forms go through `goToPlace` now.
        #expect(BridgeHandler.sessionsRestorePlace("s3").path == "/report/sessions/s3")
        #expect(BridgeHandler.sessionsRestorePlace("s1#t-66").path == "/report/sessions/s1#t-66")
        #expect(BridgeHandler.sessionsRestorePlace("s1#t-66").anchor == nil)
        #expect(BridgeHandler.sessionsRestorePlace("s3").play == nil)
    }

    @Test("a finished run forgets the reported position, for every lens")
    func runCompletionForgetsTheReportedPosition() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "route-change", "url": "/report/sessions/s1"])
        bridge.handleMessage(["type": "anchor-change", "lens": "sessions", "anchor": "s1#t-66"])
        bridge.clearSessionsRouteMemory()
        #expect(bridge.restoreSessionID == nil)
        #expect(bridge.currentAnchor == nil)

        bridge.handleMessage(["type": "anchor-change", "lens": "quotes", "anchor": "q-p1-10"])
        bridge.clearSessionsRouteMemory()
        #expect(bridge.currentAnchor == nil)
        #expect(bridge.currentAnchorLens == nil)
    }
}
