import Foundation

/// Which document the detail WKWebView is actually hosting — the ground truth
/// behind lens availability.
///
/// The native side used to *predict* this from pipeline state
/// (`selectedProjectShowsReport`), and the prediction drifted from the serve's
/// own decision (`status_page.detect_status` on the Python side) — a failed
/// folder project lit every lens over a status page that could answer none of
/// them. Now the document identifies itself: the React SPA posts
/// `{type: "ready"}` when it mounts (`postReady`, bridge.ts), and the
/// server-rendered status page posts `{type: "status-page", outcome: …}` at
/// parse time (`_IDENTITY_SCRIPT`, status_page.py). `.loading` is the honest
/// in-between, resolved by whichever message arrives.
///
/// Written in exactly three places: the two identity messages
/// (`BridgeHandler.handleMessage`) and the loading resets —
/// `BridgeHandler.reset()` on project switch, and
/// `WebView.Coordinator.didStartProvisionalNavigation` when a new main-frame
/// document begins loading (reload-on-completion, renderer-crash recovery,
/// serve restart). Don't add further writers.
///
/// A document that never identifies itself — a served bundle predating the
/// bridge code, or a future server page missing its identity script — stays
/// `.loading` for ever, deliberately (design decision D2, 1 Sep 2026): the
/// only people who can produce that state are developers on mismatched
/// builds, and a permanently pessimistic lens rail is the alarm working.
/// `WebView.didFinish` logs it loudly after the readiness timeout.
enum DocumentState: Equatable {
    /// No document has identified itself yet — nothing loaded, a load in
    /// flight, or a document that carries no identity script.
    case loading
    /// The React SPA is mounted and interactive (`ready` received).
    case spa
    /// The server-rendered status page — no SPA, no navigation shims, nothing
    /// for a lens activation to reach.
    case statusPage(StatusPageOutcome)
}

/// Why the serve intercepted the SPA — the `outcome` field of the status
/// page's identity message.
///
/// Raw values are the wire vocabulary emitted by
/// `bristlenose/server/status_page.py` (`StatusInfo.outcome`), pinned by
/// `tests/test_status_page_identity_parity.py`. An unrecognised value decodes
/// as `.unknown` so a newer serve can add outcomes without crashing an older
/// shell — the page is still a status page, only the reason goes unnamed.
enum StatusPageOutcome: String, Equatable {
    case noRun = "no-run"
    case failed = "failed"
    case cancelled = "cancelled"
    case unknown = "unknown"

    /// Tolerant decode for the bridge message: absent or unrecognised → `.unknown`.
    init(bridgeValue: String?) {
        self = bridgeValue.flatMap(StatusPageOutcome.init(rawValue:)) ?? .unknown
    }
}
