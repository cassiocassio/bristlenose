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
/// instance is only harmless while nobody can read it. Anonymise is the sharp
/// case: turn it on, and an agent must not keep reading real names out of a
/// sidecar nobody is looking at. So every in-scope instance restarts
/// immediately; everything else waits until someone looks at it.
///
/// **That exception is plural, and was written when it was not.** Until
/// `037b371e` scope was one designated project, and this comment asserted
/// "exactly one project is exposed to an external agent at a time" as the
/// premise the lazy strategy rested on. Derived scope made it false the same
/// week: N projects can be in scope at once, so the governance case this
/// comment makes covers N instances, not one. The fan-out already does —
/// `ServeFleet.applyEnvChange()` asks per project and `isExposed(_:)` reads
/// the plural `handshakeProjectPaths` — so the *code* was never singular after
/// `037b371e`; only this paragraph was, for a day, which is long enough for a
/// reader to act on it. Trued 22 Aug 2026; the premise is the thing to check
/// if the exposure model changes again.
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
    ///   - isExposed: is THIS project reachable by an agent right now? Plural
    ///     since 037b371e — every member of the exposed set earns the eager
    ///     restart, because an in-scope serve left on the old environment goes
    ///     on answering with real participant names after Anonymise is turned
    ///     on, unattended, until someone fronts its window. Previously this
    ///     any. This is `ServeManager.handshakeProjectPath`'s project — the one
    ///     an external agent can read without anyone watching.
    static func action(project: UUID,
                       isRunning: Bool,
                       isFronted: Bool,
                       isExposed: Bool) -> Action {
        guard isRunning else { return .nothing }
        if isFronted { return .restartNow }
        if isExposed { return .restartNow }
        return .restartOnNextFront
    }
}
