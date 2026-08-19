import Foundation

/// What to do with each running sidecar when a preference or the consent
/// state changes.
///
/// A sidecar bakes its provider, model, API key, anonymise and consent settings
/// into its environment **at spawn time**. Change any of them and every running
/// sidecar is stale until it restarts.
///
/// Today that is handled by `restartIfRunning()` restarting the fronted serve
/// and `drainParked()` killing the one background sidecar that can exist — and
/// killing it is silent *because a parked sidecar has no window*. Stage 3b
/// removes both halves of that: the warm pool goes, and every serve has a
/// window, so there is no silent place left to kill a stale-env sidecar.
///
/// Three arms were on the table and none is free:
///
/// - **Restart all N.** Correct, but N cold SPA remounts. `desktop/CLAUDE.md`
///   records the appearance preference's restart being *deleted* for exactly
///   that harm.
/// - **Restart the fronted one only.** Cheap, and leaves N−1 serves running
///   under a consent or anonymise setting the researcher just changed. That is
///   a governance failure, not a performance one.
/// - **Lazy — mark stale, restart when a window fronts that project.** Chosen.
///
/// **With one exception that is what makes lazy safe.** A stale background
/// instance is only harmless while nobody can read it — and exactly one project
/// is exposed to an external agent at a time. Anonymise is the sharp case: turn
/// it on, and an agent must not keep reading real names out of a sidecar nobody
/// is looking at. So the exposed instance restarts immediately; everything else
/// waits until someone looks at it.
enum ServeEnvStaleness {

    enum Action: Equatable {
        /// Restart now — this instance is reachable by an agent, or is the one
        /// on screen.
        case restartNow
        /// Mark stale; restart when a window next fronts this project.
        case restartOnNextFront
        /// Not running — nothing to do.
        case nothing
    }

    /// - Parameters:
    ///   - project: the instance's project.
    ///   - isRunning: whether it has a live sidecar.
    ///   - isFronted: whether a key window is showing it right now.
    ///   - exposedProject: the project the MCP handshake currently names, if
    ///     any. This is `ServeManager.handshakeProjectPath`'s project — the one
    ///     an external agent can read without anyone watching.
    static func action(project: UUID,
                       isRunning: Bool,
                       isFronted: Bool,
                       exposedProject: UUID?) -> Action {
        guard isRunning else { return .nothing }
        if isFronted { return .restartNow }
        if project == exposedProject { return .restartNow }
        return .restartOnNextFront
    }
}
