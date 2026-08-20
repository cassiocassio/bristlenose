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

    /// One manager per project. `@Published` so views can observe the *set*
    /// changing; individual managers are observed through `observations`.
    @Published private(set) var managers: [UUID: ServeManager] = [:]

    /// The project whose serve is fronted — what app-level surfaces
    /// (`MenuCommands`, Settings ▸ MCP Agents) resolve "which instance" to.
    @Published var frontedProject: UUID?

    /// The project the MCP handshake names, or nil. Fleet-level: one file, one
    /// owner. `ServeReaping` and `ServeEnvStaleness` both read it.
    @Published private(set) var exposedProject: UUID?

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
    @Published var handshakeProjectPath: String?

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
        observations[project] = created.objectWillChange.sink { [weak self] _ in
            self?.objectWillChange.send()
        }
        return created
    }

    /// Drop a project's manager and stop observing it. The caller stops the
    /// sidecar first — this is bookkeeping, not teardown.
    func discard(_ project: UUID) {
        managers[project] = nil
        observations[project] = nil
        if frontedProject == project { frontedProject = nil }
        if exposedProject == project { exposedProject = nil }
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

    /// Designate which project the handshake names. Exposure follows a
    /// deliberate act — turning Agent Access on — never an incidental one like
    /// fronting a window, which would silently re-point an external agent at a
    /// different study because someone pressed ⌘\`.
    func setExposed(_ project: UUID?) {
        exposedProject = project
    }
}
