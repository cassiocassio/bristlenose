import CryptoKit
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
///
/// **A second exception, of the same kind: a revoked read.** With Read shared
/// screens on (the default), every serve spawns with `BRISTLENOSE_SCREEN_TEXT=1`
/// and reads participants' shared screens in a background job
/// (`docs/design-screens.md`). Turning it off is the researcher withdrawing
/// that, and a lazy restart would leave every background serve reading screens
/// — OCR'ing them, caching stills — until someone fronts its window. Nobody has to be looking
/// for that to matter, so a serve still reading screens after the switch
/// restarts now, like an exposed one under Anonymise. Narrow on purpose: it
/// keys on the serve's own spawn-time env (`ServeManager.spawnedReadsScreens`),
/// so turning the preference ON stays lazy, and so does every other preference.
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
    ///   - readsWithdrawnScreens: was this serve spawned reading shared screens
    ///     that the new environment no longer allows? Eager for the same reason
    ///     as `isExposed`: the harm runs whether or not anyone is looking.
    ///   - isStarting: spawned but not yet `.running`. Nothing re-checks its
    ///     env when it reaches `.running`, so a stale one restarts now, before
    ///     anything is on screen (R35). Marking it stale instead would not do:
    ///     it is usually the fronted serve, so nothing fronts it again, and a
    ///     key, provider or Anonymise change made while a study opened stayed
    ///     off until some later preference change.
    ///   - spawnedOnCurrentEnv: a booting serve whose spawn env already equals
    ///     the env it would get now — spawned just after the change (first-run
    ///     consent posts, then starts the serve). Restarting it would throw a
    ///     cold boot away for nothing.
    static func action(project: UUID,
                       isRunning: Bool,
                       isFronted: Bool,
                       isExposed: Bool,
                       readsWithdrawnScreens: Bool = false,
                       isStarting: Bool = false,
                       spawnedOnCurrentEnv: Bool = false) -> Action {
        if isStarting { return spawnedOnCurrentEnv ? .nothing : .restartNow }
        guard isRunning else { return .nothing }
        if isFronted { return .restartNow }
        if isExposed { return .restartNow }
        if readsWithdrawnScreens { return .restartNow }
        return .restartOnNextFront
    }

    /// A digest of a sidecar env, for "was it spawned with the env it would get
    /// now?". Leaves out the `_`-prefixed variables, which are per-spawn
    /// plumbing (the MCP token, the host handshake), and hashes the rest so no
    /// API key is kept in the clear.
    static func fingerprint(_ env: [String: String]) -> String {
        let lines = env.filter { !$0.key.hasPrefix("_") }
            .sorted { $0.key < $1.key }
            .map { "\($0.key)=\($0.value)" }
            .joined(separator: "\n")
        return SHA256.hash(data: Data(lines.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}
