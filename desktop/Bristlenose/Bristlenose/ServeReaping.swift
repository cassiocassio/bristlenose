import Foundation

/// Which sidecars should still be running, given which projects have windows.
///
/// Stage 3b's teardown decision, pulled out as a pure function because the
/// review named refcounted teardown under SwiftUI's unordered `.onDisappear`
/// as the stage's largest remaining risk — and because a stranded sidecar is
/// ~140 MB and a live port, not a stale ordinal.
///
/// **Derived, not paired.** The obvious shape is acquire-on-open /
/// release-on-close, and it is the wrong one: it needs every `.onDisappear` to
/// fire exactly once, which is precisely what nobody can guarantee (a tab
/// merged into another window may not fire it at all — `design-workspace.md`
/// flags this and it is still unmeasured). A missed release then strands a
/// sidecar forever, silently.
///
/// So nothing is counted. `WindowRoster` already knows which projects are on
/// screen; this answers "what should be running" from that set every time it
/// changes. A missed notification delays a reap until the next roster change
/// rather than losing it — self-healing instead of accumulating.
///
/// **Reaped on a delay, not immediately** (§1e Q4). Stopping the instant the
/// last window closes reintroduces the multi-second cold boot that the warm
/// pool shipped to remove, on the commonest gesture in the app: one window,
/// ⌘W, Dock icon. The delay is the warm pool's one good idea, kept — a single
/// parked slot becoming a per-project grace period.
enum ServeReaping {

    /// What to do with one running instance.
    enum Verdict: Equatable {
        /// A window shows this project — keep it, and cancel any pending reap.
        case keep
        /// No window shows it. Reap when the grace period expires.
        case reapAfterGrace
        /// Grace expired, or memory pressure — stop it now.
        case reapNow
    }

    /// Default grace period. **A guess until measured** — pick it against how
    /// often testers close-and-reopen, not by taste. Long enough that ⌘W then
    /// Dock-click is free; short enough that a forgotten study is not holding
    /// ~140 MB an hour later.
    static let defaultGrace: Duration = .seconds(90)

    /// - Parameters:
    ///   - project: the instance's project.
    ///   - shownProjects: every project a live window is showing. From
    ///     `WindowRoster`, which is the one place that knows.
    ///   - unshownFor: how long it has had no window, or nil if it still has one
    ///     or has only just lost it.
    ///   - grace: the period before reaping.
    ///   - memoryPressure: true under system memory pressure — grace is skipped,
    ///     because a warm cache is not worth a swap storm.
    static func verdict(project: UUID,
                        shownProjects: Set<UUID>,
                        unshownFor: Duration?,
                        grace: Duration = defaultGrace,
                        memoryPressure: Bool = false) -> Verdict {
        if shownProjects.contains(project) { return .keep }
        if memoryPressure { return .reapNow }
        guard let unshownFor else { return .reapAfterGrace }
        return unshownFor >= grace ? .reapNow : .reapAfterGrace
    }

    /// The whole fleet at once — every running instance judged against the
    /// roster in a single pass, which is how the caller should use it: on any
    /// roster change, re-judge everything, rather than reacting to one window.
    static func sweep(running: [UUID: Duration?],
                      shownProjects: Set<UUID>,
                      grace: Duration = defaultGrace,
                      memoryPressure: Bool = false) -> [UUID: Verdict] {
        running.reduce(into: [:]) { out, entry in
            out[entry.key] = verdict(project: entry.key,
                                     shownProjects: shownProjects,
                                     unshownFor: entry.value,
                                     grace: grace,
                                     memoryPressure: memoryPressure)
        }
    }
}
