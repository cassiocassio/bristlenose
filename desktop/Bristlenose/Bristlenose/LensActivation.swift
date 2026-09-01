import Foundation

/// What activating a lens should DO, given the document's state — the policy
/// half of `BridgeHandler.activateLens`, pulled into a pure function per the
/// house convention so the intent semantics (design review 1 Sep 2026, P3/D3)
/// are table-tested rather than implied by call-site plumbing.
///
/// The contract, in rows:
/// - **Re-activating the current lens goes to its root** (D3, the Finder
///   model: a sidebar item is a location — clicking Documents from three
///   folders deep goes to Documents). Deliberately bypasses the sessions
///   route memory, which exists for *returning* to a lens, not re-clicking
///   it; the memory itself is kept, so leave-and-return still restores.
/// - **A different lens on a live SPA dispatches now** — Sessions through
///   its route memory, everything else to the lens root.
/// - **A different lens while the document is loading queues** — one slot,
///   replayed by `BridgeHandler` when the SPA posts `ready`, discarded if
///   the document turns out to be the status page. Reachability is the
///   affordance gates' job (the sidebar rows, rail, and menu all dim on
///   `LensAvailability`) — deliberately NOT re-checked here: the mirror the
///   bridge holds can lag the lit rows by a render, and a second gate that
///   can only produce false negatives silently ate clicks (1 Sep 2026).
///   A queued intent from a race is harmless — discarded on status-page or
///   switch, and replay requires the `ready` a truly dim rail never gets.
/// - **A status page ignores** — the controls are dimmed everywhere by
///   `LensAvailability`; anything that still reaches here has nothing to
///   act on.
enum LensActivation: Equatable {
    /// Navigate to the lens root (`switchToTab`).
    case root(Tab)
    /// Navigate to the remembered sessions transcript (`navigateToSession`).
    case restore(sessionID: String)
    /// Hold as the one pending intent, replayed on `ready`.
    case queue(Tab)
    /// Nothing to do.
    case ignore

    static func decide(
        tab: Tab,
        activeTab: Tab?,
        documentState: DocumentState,
        restoreSessionID: String?
    ) -> LensActivation {
        if tab == activeTab {
            // Root-return needs a live SPA; `activeTab` derives from the
            // SPA's own route-change messages, so a non-SPA document with a
            // non-nil activeTab is a stale echo — nothing to return to.
            return documentState == .spa ? .root(tab) : .ignore
        }
        switch documentState {
        case .spa:
            if tab == .sessions, let sid = restoreSessionID {
                return .restore(sessionID: sid)
            }
            return .root(tab)
        case .loading:
            return .queue(tab)
        case .statusPage:
            return .ignore
        }
    }
}
