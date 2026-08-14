import Foundation

/// Route memory for the Sessions lens — "restore the view the user left".
///
/// Lives on the **Swift side** (design doc §Route memory): `switchToTab` keeps
/// one meaning — go to the tab root — and only the lens-activation affordances
/// (the sidebar lens rows, `LensRail`, View ▸ ⌘2) opt into restore, via
/// `BridgeHandler.activateLens`. The **All Sessions** popover row deliberately
/// calls plain `switchToTab`, so it always reaches the grid and the memory
/// cannot bounce it back to the remembered transcript.
///
/// Web storage was ruled out structurally: the WKWebView's data store is
/// `.nonPersistent()`, minted fresh per `makeNSView`, and the `.id` forces a
/// remount on every switch and warm re-point — `localStorage` would be wiped
/// constantly, and "fixing" that with a persistent store would be a genuine
/// cross-project leak.
///
/// ## Why the memory must be CLEARED, not validated
///
/// Session ids are positional (`s1`, `s2`…). A re-analysis that drops a session
/// **renumbers** the rest, so a remembered `s3` restores *successfully* to a
/// different participant's transcript — a wrong answer that looks right, worse
/// than a 404. Renumbering only happens via a pipeline run, so the memory is
/// cleared on the run-completion transition (and on project switch via
/// `BridgeHandler.reset()`). The benign 404 half (a session genuinely gone
/// without renumbering) lands on `TranscriptPage`'s error state, with the
/// toolbar switcher available as the way out.
struct SessionsRouteMemory {

    /// The remembered session id (`"s3"`), or nil when the user last saw the
    /// grid — restoring nil means the plain tab root.
    private(set) var restoreSessionID: String?

    /// Feed every route change through this; it only reacts to Sessions-lens
    /// paths. Visiting the grid RESETS the memory — "the view the user left"
    /// is the index in that case, not the transcript they saw an hour ago.
    mutating func observe(path: String) {
        guard let route = Self.sessionsRoute(fromPath: path) else { return }
        switch route {
        case .index: restoreSessionID = nil
        case .session(let id): restoreSessionID = id
        }
    }

    mutating func clear() {
        restoreSessionID = nil
    }

    // MARK: - Parsing

    enum Route: Equatable {
        case index
        case session(String)
    }

    /// Parse a bridge `route-change` path into a Sessions-lens route, or nil
    /// for any other lens. Only positional SPA session ids (`s<digits>`) count
    /// — the server also serves `transcript_*.html` files under the same
    /// prefix, and a non-session filename must never be remembered as a
    /// restore target.
    static func sessionsRoute(fromPath path: String) -> Route? {
        // Strip query/fragment; the bridge sends pathname but be tolerant.
        let clean = path.split(separator: "?", maxSplits: 1)[0]
            .split(separator: "#", maxSplits: 1)[0]
        let prefix = "/report/sessions"
        guard clean.hasPrefix(prefix) else { return nil }
        let rest = clean.dropFirst(prefix.count)
        if rest.isEmpty || rest == "/" { return .index }
        guard rest.hasPrefix("/") else { return nil }   // e.g. /report/sessionsfoo
        let id = rest.dropFirst()
        guard !id.contains("/"),
              id.first == "s",
              id.count > 1,
              id.dropFirst().allSatisfy(\.isNumber)
        else { return nil }
        return .session(String(id))
    }
}
