import Foundation

/// What "these projects are exposed to an agent" means, as one decision.
///
/// **The V1 rule:** scope = every open project window whose project has Agent
/// Access on. Nothing designates it, nothing persists it, nothing follows
/// focus. Widen by opening a window, narrow by closing one; ⌘` changes nothing.
///
/// Three properties this function exists to guarantee:
///
/// 1. **Derived from the window roster, never from serve liveness.**
///    `ServeReaping.defaultGrace` keeps a sidecar warm for 90 s after its last
///    window closes so ⌘W-then-Dock-click is free. Scope is a permission and
///    serve lifetime is a cache; if they shared a predicate then "close a
///    window to stop an agent reading it" would be false for ninety seconds.
///    The caller passes `shown` from `WindowRoster`, which is the one place
///    that knows.
///
/// 2. **Plural.** Stage 3b made the *serves* plural — one sidecar per project,
///    own port, own MCP-scoped token — and left the registry singular, so a
///    single `exposedProject` slot had to designate one winner. That slot is
///    what produced the flapping measured on 20 Aug: five states across five
///    calls (not-open, foo, IKEA, foo, not-open) as reaped sidecars dropped a
///    handshake the slot still pointed at. Derived state cannot flap, because
///    there is nothing to fall out of sync with.
///
/// 3. **The key is never computed here.** It arrives from each serve's
///    `/api/health`, where Python computes `sha256(realpath(input_dir))[:8]`.
///    Two implementations of one digest is a divergence that would break every
///    citation crossing the language boundary — and a citation is the only
///    thing standing between an agent and attributing study B's quotes to
///    study A.
///
/// Pure and substrate-free so the rule is testable without a window server, a
/// sidecar, or a filesystem — the same shape as `AgentAccessPolicy` and
/// `ExposureRestore` before it.
enum HandshakeExposure {

    /// One serve's offer: what it could contribute to the handshake.
    ///
    /// `instanceID` and `token` are optional because both are nil on every
    /// start until the first `/api/health` read lands — the gap that made the
    /// old badge over-claim. A candidate missing either is simply not ready.
    struct Candidate: Equatable {
        let path: String
        let name: String
        let state: ServeState
        let instanceID: String?
        let token: String?
        /// From `/api/health`'s `mcp.project_key`. Nil until the first read.
        let key: String?
    }

    /// One row of the handshake file.
    struct Entry: Equatable {
        let key: String
        let name: String
        let path: String
        let port: Int
        let token: String
        let instanceID: String
    }

    /// The projects an agent may currently reach.
    ///
    /// - Parameters:
    ///   - candidates: every running serve, keyed by project.
    ///   - shown: `WindowRoster.shownProjects` — projects a live window holds.
    ///     Minimised counts, deliberately: minimising is how a researcher keeps
    ///     a project in scope on a small screen while doing cross-project work.
    ///   - agentAccess: the persisted per-project permission. A closure rather
    ///     than a stored `ProjectIndex` so this stays ignorant of the sidebar
    ///     model — and so absent means off (a build that forgot the wiring
    ///     exposes nothing).
    ///
    /// Sorted by name so the file is stable: an unordered rewrite would churn
    /// the handshake's mtime and hand the proxy a spurious change on every poll.
    static func entries(candidates: [UUID: Candidate],
                        shown: Set<UUID>,
                        agentAccess: (UUID) -> Bool) -> [Entry] {
        candidates
            .filter { shown.contains($0.key) }
            .filter { agentAccess($0.key) }
            .compactMap { _, candidate -> Entry? in
                guard case .running(let port) = candidate.state,
                      let instanceID = candidate.instanceID,
                      let token = candidate.token,
                      let key = candidate.key else { return nil }
                return Entry(key: key,
                             name: candidate.name,
                             path: candidate.path,
                             port: port,
                             token: token,
                             instanceID: instanceID)
            }
            // (name, key) — never name alone. Folder basenames collide
            // routinely ("~/clients/acme/interviews", "~/clients/zeta/
            // interviews"), Dictionary iteration order is arbitrary, and
            // position 0 is load-bearing: the schema-1 fallback copies
            // `first`'s port and token. An unstable first entry re-points an
            // old proxy at a different study between two syncs, which is the
            // flapping this change exists to kill.
            .sorted {
                let byName = $0.name.localizedStandardCompare($1.name)
                return byName == .orderedSame ? $0.key < $1.key : byName == .orderedAscending
            }
    }

    /// Which projects should have their `/mcp` surface **live**.
    ///
    /// Deliberately NOT the same set as `entries`. A project can be in scope
    /// (window open, access on) while its serve is still starting and has no
    /// token yet — it belongs here the moment it is in scope, so that the gate
    /// is closed on everything else. Everything not in this set gets
    /// `PUT /api/agent-scope {readable: false}`, which is what makes closing a
    /// window safe *now* rather than when the sidecar is reaped, and safe
    /// against an agent holding a cached port and bearer rather than only
    /// against a proxy that politely re-reads the file.
    static func readableProjects(candidates: [UUID: Candidate],
                                 shown: Set<UUID>,
                                 agentAccess: (UUID) -> Bool) -> Set<UUID> {
        Set(candidates.filter { id, candidate in
            // `.failed` is excluded, and it is the one serve state that is not
            // a beat. A starting serve belongs here — that is the whole point
            // of the set being wider than `entries` — but a sidecar that
            // failed to spawn cannot answer anything, and leaving it in makes
            // the Settings register print it under "Readable now" for as long
            // as the window stays open. Closing the gate on it is a no-op for
            // the serve and a truthful subtraction for the audit surface.
            if case .failed = candidate.state { return false }
            return shown.contains(id) && agentAccess(id)
        }.keys)
    }
}
