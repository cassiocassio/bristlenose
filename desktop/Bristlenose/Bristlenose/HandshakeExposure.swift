import Foundation

/// What "this project is exposed to an agent" means, as one decision.
///
/// It exists because the answer was being computed twice. `ServeManager`
/// wrote the handshake on five conjuncts; the sidebar antenna went solid on
/// three of them (`agentAccess ∧ .running ∧ same path`), missing
/// `instanceID` and `token`. Those two are nil on every start, park and warm
/// re-point — refilled only by an `/api/health` read that lands *after*
/// `state` reaches `.running` — so the badge claimed an agent could reach a
/// project during every start and every switch, and kept claiming it if the
/// health read never succeeded. §5a-bis always specified "shared &&
/// handshake live"; the badge shipped with the weaker predicate.
///
/// One function, one answer. `ServeManager` publishes the result as
/// `handshakeProjectPath`; the sidebar reads that. Neither re-derives.
///
/// It also stops being one-serve-shaped: nothing here assumes a single
/// fronted sidecar, so a fleet keyed on project needs no change — each
/// instance answers for itself.
enum HandshakeExposure {

    /// Everything the handshake file needs, or nil when none should exist.
    struct Plan: Equatable {
        let path: String
        let port: Int
        let token: String
        let instanceID: String
    }

    /// The five conjuncts, in one place.
    ///
    /// `agentAccess` is a closure rather than a `Bool` so the caller need not
    /// resolve it before knowing whether the path exists — and so the
    /// resolver stays absent-means-off (a build that forgot the wiring
    /// exposes nothing).
    static func write(state: ServeState,
                      currentProjectPath: String?,
                      instanceID: String?,
                      token: String?,
                      agentAccess: (String) -> Bool) -> Plan? {
        guard case .running(let port) = state,
              let path = currentProjectPath,
              let instanceID,
              let token,
              agentAccess(path) else { return nil }
        return Plan(path: path, port: port, token: token, instanceID: instanceID)
    }
}
