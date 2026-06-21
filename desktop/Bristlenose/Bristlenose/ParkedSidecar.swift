import Foundation

/// A serve sidecar kept warm after the user switched away from its project,
/// so switching *back* is an instant hand-off instead of a teardown+restart.
///
/// This is the single-slot ("Option B") realization of the Phase A2
/// warm-sidecar direction: `ServeManager` holds at most ONE `ParkedSidecar`
/// (the most-recently-fronted project). A capacity-N LRU pool was considered
/// and rejected — the only observed repro is rapid A↔B switching, which one
/// parked slot solves, and a single slot minimizes churn in the
/// concurrency-critical `ServeManager`. See
/// `.claude/plans/warm-sidecar-pool-implementation.md` §Review outcomes and
/// `docs/private/reviews/warm-sidecar-pool.md` Finding 15 for the decision.
///
/// A parked sidecar is a *dormant fronted sidecar*, not an inert handle: it is
/// still a live `bristlenose serve` process holding its own kernel-assigned
/// port, its own per-instance bearer token, an imported project DB, and an
/// event watcher. It keeps its `readTask` draining (so its stdout pipe buffer
/// can't fill and block the writer) and honours the same parent-death-watcher
/// contract as any sidecar (self-terminates on host death — see
/// `bristlenose/server/lifecycle.py`).
struct ParkedSidecar {
    /// Filesystem path of the project this sidecar serves. Re-point key.
    let projectPath: String
    /// Kernel-assigned port (`bind(0)`) this sidecar is serving on.
    let port: Int
    /// This sidecar's own bearer token (captured from its `[bristlenose]
    /// auth-token:` stdout line while it was fronted). Per-instance and
    /// immutable for the process's lifetime — restoring it on re-point is what
    /// keeps the re-mounted WebView talking to the right sidecar.
    let authToken: String?
    /// Server version reported by this sidecar's `/api/health`, if fetched.
    let serverVersion: String?
    /// The live process. `isRunning` is the first (necessary, not sufficient)
    /// liveness gate before a re-point; a `/api/health` probe is the backstop.
    let process: Process
    /// The detached stdout-drain task for `process`. Kept alive while parked.
    let readTask: Task<Void, Never>?
    /// Recent stdout lines (capped), carried so the fronted `outputLines` can
    /// be restored on re-point. Parked lines are buffered here and NEVER run
    /// the fronted token-capture/state logic (token-isolation, review F10).
    var buffer: [String]

    /// Whether the parked process is still alive at the OS level. Necessary
    /// but not sufficient — a wedged-but-alive process passes this, so the
    /// re-point path also runs a `/api/health` probe (review F3).
    var isAlive: Bool { process.isRunning }
}

/// Pure decision for whether a project switch can re-point to the parked
/// sidecar or must cold-start. Extracted as a free function (the project's
/// "decision → testable helper" convention) so the policy is unit-testable
/// without a `Process`. The lifecycle integration in `ServeManager` is the
/// untestable-headlessly part (no `Process` seam) and is covered by human QA.
enum RepointDecision: Equatable {
    /// The parked slot holds the target project and it's alive — hand off.
    case repoint
    /// No usable parked entry for the target — spawn a fresh sidecar.
    case coldStart

    /// - Parameters:
    ///   - target: project path being switched to.
    ///   - parkedPath: project path of the parked sidecar, if any.
    ///   - parkedAlive: whether that parked sidecar is still alive.
    static func evaluate(target: String, parkedPath: String?, parkedAlive: Bool) -> RepointDecision {
        guard let parkedPath, parkedPath == target, parkedAlive else { return .coldStart }
        return .repoint
    }
}
