import Foundation
import Testing
@testable import Bristlenose

/// The design review's switch matrix (1 Sep 2026, D1-C), executable.
///
/// Each scenario drives a REAL `BridgeHandler` through the message sequence
/// the shell would see, and asserts the lens availability at every beat by
/// deriving from the bridge's actual `documentState` — so these tests break
/// if either half of the reconciliation (the prior, or the identity messages)
/// stops behaving as the matrix promises. Pane and prior inputs are supplied
/// per beat exactly as `ContentView` computes them for the states named.
@MainActor
struct LensSwitchMatrixTests {

    private func availability(
        _ bridge: BridgeHandler,
        pane: DetailPaneKind = .report,
        serve: ServeState = .running(port: 8150),
        prior: Bool
    ) -> LensAvailability {
        LensAvailability.derive(
            pane: pane,
            serveState: serve,
            documentState: bridge.documentState,
            priorPredictsViewableDocument: prior
        )
    }

    /// Welcome → good project: dim on Welcome (rows present, teaching the
    /// layout), lit from the instant of the click, lit through the boot, lit
    /// on confirmation. No blink at any beat.
    @Test func welcomeToGoodProjectNeverBlinks() {
        let bridge = BridgeHandler()

        // At rest on Welcome: no project, rows dim.
        #expect(availability(bridge, pane: .noProject, serve: .idle, prior: false)
                == .unavailable(.noProject))

        // Click a known-good project: reset() fires, serve starts booting —
        // the prior answers, and it says lit. (D1: disabled means "not
        // applicable", not "not yet".)
        bridge.reset()
        #expect(availability(bridge, serve: .starting, prior: true) == .available)

        // Serve up, document loading: still lit on the prior.
        #expect(availability(bridge, prior: true) == .available)

        // SPA confirms: lit on identity now, prior irrelevant.
        bridge.handleMessage(["type": "ready"])
        #expect(availability(bridge, prior: false) == .available)
    }

    /// Anything → broken project: dim from the click, confirmed dim by the
    /// status page. The failure pane explains why; the lenses never lie lit.
    @Test func switchToFailedProjectIsDimFromTheClick() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "ready"])  // leaving a healthy project

        bridge.reset()
        // Failed folder project: pane stays on the serve surface (it carries
        // the cause), prior says status page → dim while loading…
        #expect(availability(bridge, prior: false) == .unavailable(.awaitingDocument))

        // …and the status page confirms. Same behaviour, named reason.
        bridge.handleMessage(["type": "status-page", "outcome": "failed"])
        #expect(availability(bridge, prior: false) == .unavailable(.statusPage))
    }

    /// Broken → good project: the prior is per-project, so the rail lights
    /// the moment the selection changes — no dim carry-over from the failed
    /// project the user just left.
    @Test func failedToGoodProjectLightsAtTheClick() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "status-page", "outcome": "failed"])

        bridge.reset()
        #expect(availability(bridge, serve: .starting, prior: true) == .available)
        bridge.handleMessage(["type": "ready"])
        #expect(availability(bridge, prior: true) == .available)
    }

    /// The rare, expensive walk-back: a good prior lit the rail, the document
    /// turns out to be a status page (boot crash, events/DB skew). The dim
    /// lands in the same beat as the failure pane appearing — coherent, and
    /// the only lit→dim transition the matrix permits.
    @Test func litThenStatusPageWalksBackToDim() {
        let bridge = BridgeHandler()
        bridge.reset()
        #expect(availability(bridge, prior: true) == .available)

        bridge.handleMessage(["type": "status-page", "outcome": "unknown"])
        #expect(availability(bridge, prior: true) == .unavailable(.statusPage))
    }

    /// The cheap walk-back: a pessimistic prior dims the rail, the serve
    /// surprises us with a report (P5's world: failed re-run, last good
    /// report served). Dim→lit reads as "it loaded" — a promise kept late.
    @Test func dimThenReadyWalksUpToLit() {
        let bridge = BridgeHandler()
        bridge.reset()
        #expect(availability(bridge, prior: false) == .unavailable(.awaitingDocument))

        bridge.handleMessage(["type": "ready"])
        #expect(availability(bridge, prior: false) == .available)
    }

    /// Mid-session document turnover without a project switch (serve restart,
    /// renderer-crash recovery): `didStartProvisionalNavigation` returns the
    /// document to `.loading` — the prior answers again until the new
    /// document identifies itself. (The navigation delegate write is
    /// identity-guarded in WebView; here we assert the state semantics.)
    @Test func documentTurnoverReturnsToThePrior() {
        let bridge = BridgeHandler()
        bridge.handleMessage(["type": "ready"])
        #expect(availability(bridge, prior: true) == .available)

        // What the didStartProvisionalNavigation hook writes:
        bridge.documentState = .loading
        #expect(availability(bridge, prior: true) == .available)
        #expect(availability(bridge, prior: false) == .unavailable(.awaitingDocument))

        bridge.handleMessage(["type": "ready"])
        #expect(availability(bridge, prior: false) == .available)
    }
}
