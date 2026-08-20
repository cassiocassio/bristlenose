import Combine
import Foundation

/// One serve per project, and the concerns that belong to the app rather than
/// to any single sidecar.
///
/// **The decomposition, corrected.** The plan said "make `ServeManager`
/// multi-instance", which read as untangling ~1,000 lines of singleton state.
/// It is the wrong framing: `ServeManager` already manages exactly one sidecar
/// correctly — spawn, readiness parse, generation guard, termination, teardown.
/// What was singleton was not the *manager*, it was that the app held one of
/// them. So the fleet holds one manager per project, and the manager barely
/// changes.
///
/// What genuinely does move up here is the small set of facts that are about
/// the app, not about a sidecar:
///
/// - **The MCP handshake.** One global file naming at most one project
///   (`design-mcp-extension.md` §5a-bis: *"only one row can carry it"*). Left on
///   the manager it would have seven delete edges per instance, so one
///   project's start would delete another's handshake — the defect `3ac773fa`
///   closed, rebuilt one layer up.
/// - **`mcpMounted`**, which answers "does this build have the `mcp` extra" and
///   is identical for every instance by construction.
/// - **Prefs / consent / termination observers.** One app, one notification;
///   the *action* becomes a fan-out (`ServeEnvStaleness`).
///
/// Keyed on `Project.ID`, never on the path: bookmark healing respells
/// `Project.path` while a manager holds the spawn-time spelling, so a
/// path-keyed fleet could mint two sidecars for one study — two ports, two
/// partitions, two windows on one project unable to share a `BroadcastChannel`.
@MainActor
final class ServeFleet: ObservableObject {

    /// One manager per project.
    ///
    /// Deliberately **not** `@Published`. `manager(for:)` mints on first use and
    /// is called from `body` (`ContentView.serveManager`, the detail pane), so a
    /// published write there would fire `objectWillChange` mid-view-update —
    /// *"Publishing changes from within view updates is not allowed; this will
    /// cause undefined behavior."* The `observations` fan-out already notifies
    /// on anything a view can see, so nothing is lost by dropping it.
    private(set) var managers: [UUID: ServeManager] = [:]

    /// The project whose serve is fronted — what app-level surfaces
    /// (`MenuCommands`, Settings ▸ MCP Agents) resolve "which instance" to.
    @Published var frontedProject: UUID?

    /// The project the MCP handshake names, or nil. Fleet-level: one file, one
    /// owner. `ServeReaping` and `ServeEnvStaleness` both read it.

    /// Whether this build mounted the MCP endpoint (the optional `mcp` extra).
    ///
    /// Fleet-level because it is per-**build**, not per-serve: every instance
    /// spawns the same sidecar binary, so the answer is identical for all of
    /// them. Per-instance it would force the sidebar's agent-access gate and the
    /// Settings pane to pick an instance and read `false` when none is running.
    @Published var mcpMounted: Bool = false

    /// The project path the MCP handshake currently names, or nil.
    ///
    /// Fleet-level for the sharper reason: the handshake is **one global file**
    /// with seven independent delete edges. Per-instance, one project's start
    /// would delete another's file while the first still published "exposed" —
    /// the antenna lying, which is the defect `3ac773fa` closed.
    /// The project paths the handshake currently names — the sidebar's solid
    /// antenna tier, and now a set rather than one designated winner.
    @Published private(set) var handshakeProjectPaths: Set<String> = []

    /// Seam for tests that need a derived set without a window server behind
    /// them. Production writes it only through `syncHandshake`.
    func setHandshakeProjectPathsForTest(_ paths: Set<String>) { handshakeProjectPaths = paths }

    /// When an agent last called a tool on the **exposed** serve, or nil.
    ///
    /// Fleet-level and read from the derived set for the same reason as
    /// `handshakeProjectPath`: exposure is singular, so activity is too. The
    /// fronted project is NOT the right source — you can be looking at one
    /// study while an agent reads the one you exposed, and the antenna that
    /// radiates has to be the exposed one or it is pointing at the wrong row.
    /// When an agent last asked about each project. A **map**, because scope
    /// is plural: a cross-study question lights several antennas in sequence,
    /// and collapsing it to one would pick an arbitrary winner.
    @Published private(set) var lastAgentCallAt: [UUID: Date] = [:]

    /// Nested `ObservableObject`s do not propagate through `@EnvironmentObject`,
    /// and the failure is silent — so every manager's change is re-published as
    /// the fleet's own. Same contract `ServeManager` holds over `ServeInstance`,
    /// one level up, and pinned by the same style of test.
    private var observations: [UUID: AnyCancellable] = [:]

    /// The manager for `project`, creating one on first use.
    ///
    /// Creating is deliberately cheap and does **not** spawn: a manager with no
    /// sidecar is idle state, so "does this project have a manager" never means
    /// "is this project running". Ask `isRunning(_:)` for that.
    @discardableResult
    func manager(for project: UUID) -> ServeManager {
        if let existing = managers[project] { return existing }
        let created = ServeManager()
        created.agentAccessResolver = agentAccessResolver
        managers[project] = created
        created.onHandshakeDirty = { [weak self] in self?.syncHandshake() }
        observations[project] = created.objectWillChange.sink { [weak self] _ in
            guard let self else { return }
            self.objectWillChange.send()
            // The mirrored facts follow the managers rather than being pushed
            // from call sites, so no site can forget to update them.
            Task { @MainActor in self.refreshAppLevelFacts() }
        }
        return created
    }

    /// Stop a project's sidecar and drop its manager.
    ///
    /// **Stops first.** An earlier version left teardown to the caller and was
    /// bookkeeping only — which meant `ContentView`'s project-removal path
    /// (the successor to `dropParked`) forgot the manager while its sidecar
    /// kept running: ~140 MB and a live port serving a study the researcher had
    /// just deleted, with nothing reporting it. Strictly worse than the
    /// behaviour it replaced.
    func discard(_ project: UUID) {
        managers[project]?.stop()
        SharedConfigStore.shared.release(projectID: project)
        unshownSince[project] = nil
        managers[project] = nil
        observations[project] = nil
        if frontedProject == project { frontedProject = nil }
        // Through `setExposed`, not a bare assignment: the project is being
        // removed from the sidebar, so the stored id must go too or a later
        // launch would try to re-expose something that no longer exists.
        // The project is going; re-derive so its row leaves the handshake.
        syncHandshake()
    }

    /// The fronted project's manager, if there is one.
    ///
    /// For app-level windows — System Health, Run Inspector — and for the boot
    /// pane's log tail. They are about "the serve you are looking at", which is
    /// a real notion at N and the honest replacement for the app-wide
    /// `ServeManager` that used to be injected into them.
    var fronted: ServeManager? {
        frontedProject.flatMap { managers[$0] }
    }

    /// A never-started manager, handed to app-level surfaces when nothing is
    /// fronted.
    ///
    /// This is **not** the "null manager" the optional `ContentView.serveManager`
    /// exists to avoid. That one would have been a second source of truth about
    /// *a window's* serve. This one answers a different question — "what is the
    /// fronted serve doing?" — and when nothing is fronted, `.idle` is the
    /// truthful answer rather than a stand-in for one. It never spawns, and no
    /// window can reach it.
    private let idle = ServeManager()

    /// The fronted manager for surfaces that must always have one: the menu bar
    /// and Settings, which exist with no window open.
    var frontedOrIdle: ServeManager { fronted ?? idle }

    /// Injected once and applied to every manager the fleet creates — the
    /// handshake writer's policy input. Set on the fleet rather than on each
    /// manager so a project whose serve starts later cannot miss it.
    var agentAccessResolver: ((String) -> Bool)? {
        didSet { managers.values.forEach { $0.agentAccessResolver = agentAccessResolver } }
    }

    func isRunning(_ project: UUID) -> Bool {
        managers[project]?.runningPort != nil
    }

    /// Every project with a live sidecar.
    var runningProjects: Set<UUID> {
        Set(managers.filter { $0.value.runningPort != nil }.keys)
    }

    /// When each running project last had no window. `ServeReaping` turns this
    /// plus the roster into a verdict; nothing here is a refcount.
    private var unshownSince: [UUID: ContinuousClock.Instant] = [:]
    private var reapTask: Task<Void, Never>?

    /// Re-judge every running sidecar against the windows that exist now.
    ///
    /// Call on any roster change. It is a **sweep, not a reaction to one
    /// window**: the verdict is a function of `shownProjects`, so a missed
    /// `.onDisappear` delays an answer by one sweep instead of stranding a
    /// sidecar forever — which a paired acquire/release cannot promise, and a
    /// tab merged into another window may not fire at all.
    func sweep(shownProjects: Set<UUID>, memoryPressure: Bool = false) {
        // Scope is a function of this roster, so every sweep re-derives it.
        // Without this the only path to a re-derivation was some manager's
        // 20-second health poll, which made "closing a window is immediately
        // safe" mean "within twenty seconds, if that poll succeeds" — the
        // claim the whole change exists to make true. `deferred` so it runs
        // after the reaping decisions below, on every exit.
        defer { syncHandshake() }
        let now = ContinuousClock.now
        for id in runningProjects where !shownProjects.contains(id) {
            if unshownSince[id] == nil { unshownSince[id] = now }
        }
        for id in shownProjects { unshownSince[id] = nil }

        let running = Dictionary(uniqueKeysWithValues: runningProjects.map { id in
            (id, unshownSince[id].map { now - $0 })
        })
        let verdicts = ServeReaping.sweep(running: running,
                                          shownProjects: shownProjects,
                                          memoryPressure: memoryPressure)
        for (id, verdict) in verdicts where verdict == .reapNow {
            discard(id)
        }
        // Something is waiting out its grace period — come back and finish the
        // job. Without this the reap would only ever happen on the *next*
        // roster change, so closing the last window and walking away would
        // leave the sidecar up indefinitely: the timer is the decision.
        reapTask?.cancel()
        reapTask = nil
        if verdicts.values.contains(.reapAfterGrace) {
            reapTask = Task { [weak self] in
                try? await Task.sleep(for: ServeReaping.defaultGrace)
                guard !Task.isCancelled, let self else { return }
                // Re-read the roster rather than replaying the snapshot: a study
                // that regained a window during the grace period must not be
                // reaped out from under it.
                self.sweep(shownProjects: WindowRoster.shared.shownProjects)
            }
        }
    }

    /// A preference or the consent state changed, so every running sidecar's
    /// baked environment is stale. Fan out per `ServeEnvStaleness`.
    ///
    /// Restarting all N would be N cold report remounts in windows nobody is
    /// looking at; restarting only the fronted one would leave the rest serving
    /// under a consent the researcher just changed. So: lazy, except the
    /// exposed instance, which an agent can read while unattended.
    func applyEnvChange() {
        for (id, manager) in managers {
            switch ServeEnvStaleness.action(project: id,
                                            isRunning: manager.runningPort != nil,
                                            isFronted: id == frontedProject,
                                            isExposed: isExposed(id)) {
            case .restartNow:          manager.restartIfRunning()
            case .restartOnNextFront:  staleProjects.insert(id)
            case .nothing:             break
            }
        }
    }

    /// Marked stale by `applyEnvChange`, restarted when a window fronts them.
    private(set) var staleProjects: Set<UUID> = []

    /// Call when a window adopts `project`. Restarts it if its environment went
    /// stale while nobody was looking.
    func front(_ project: UUID) {
        frontedProject = project
        if staleProjects.remove(project) != nil {
            managers[project]?.restartIfRunning()
        }
    }

    /// Is this project reachable by an agent right now?
    ///
    /// EVERY member of the exposed set deserves the eager restart, not one
    /// arbitrary member: an in-scope serve left on the old environment keeps
    /// answering with real participant names after the researcher turned
    /// Anonymise on, unattended, until someone fronts its window.
    func isExposed(_ project: UUID) -> Bool {
        guard let path = managers[project]?.currentProjectPath else { return false }
        return handshakeProjectPaths.contains(path)
    }

    /// Re-derive the handshake from the window roster and write it.
    ///
    /// One file, one writer, and no owner to designate. Called whenever any
    /// manager's contribution may have changed and on every roster sweep —
    /// derivation is cheap and cannot drift, which a designated slot could and
    /// did (five different answers across five consecutive tool calls, 20 Aug).
    func syncHandshake() {
        let shown = WindowRoster.shared.shownProjects
        var candidates: [UUID: HandshakeExposure.Candidate] = [:]
        for (id, manager) in managers {
            guard let path = manager.currentProjectPath else { continue }
            candidates[id] = HandshakeExposure.Candidate(
                path: path,
                name: URL(fileURLWithPath: path).lastPathComponent,
                state: manager.state,
                instanceID: manager.mcpInstanceID,
                token: manager.mcpToken,
                key: manager.projectKey)
        }
        let resolver = agentAccessResolver
        let access: (UUID) -> Bool = { id in
            guard let path = candidates[id]?.path else { return false }
            return resolver?(path) ?? false
        }

        let entries = HandshakeExposure.entries(
            candidates: candidates, shown: shown, agentAccess: access)
        if entries.isEmpty {
            MCPHandshake.remove()
        } else {
            MCPHandshake.write(entries: entries)
        }

        let paths = Set(entries.map(\.path))
        if paths != handshakeProjectPaths { handshakeProjectPaths = paths }

        // The gate. This is what makes closing a window safe NOW rather than
        // when the sidecar is reaped 90 s later — and safe against an agent
        // holding a cached port and bearer, not only against a proxy that
        // politely re-reads the file.
        let readable = HandshakeExposure.readableProjects(
            candidates: candidates, shown: shown, agentAccess: access)
        for (id, manager) in managers {
            manager.setAgentScope(readable: readable.contains(id))
        }
    }

    /// Mirror the facts that are about the app rather than a sidecar.
    ///
    /// They are `@Published` on the fleet and read by the sidebar, and they had
    /// **no writer at all** when the fleet first landed — so `mcpMounted` was
    /// permanently false, which hides *Turn On Agent Access* entirely, and the
    /// antenna could never go solid. A declared-and-read-but-never-written
    /// property reads exactly like a truthful "no", which is why it survived a
    /// green suite.
    func refreshAppLevelFacts() {
        // Per-build, so any instance answers for all of them.
        let mounted = managers.values.contains { $0.mcpMounted }
        if mounted != mcpMounted { mcpMounted = mounted }

        var calls: [UUID: Date] = [:]
        for (id, manager) in managers where manager.lastAgentCallAt != nil {
            calls[id] = manager.lastAgentCallAt
        }
        if calls != lastAgentCallAt { lastAgentCallAt = calls }
    }
}
