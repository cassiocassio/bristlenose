import Foundation

/// One sidecar's observable state.
///
/// Extracted from `ServeManager` on the way to Stage 3b, where the app runs one
/// of these **per project** rather than one in total. Today the fleet holds
/// exactly one and every existing call site reads it through `ServeManager`'s
/// forwarding properties, so this step is behaviour-identical by construction.
///
/// **What is deliberately NOT here**, per the 19 Aug plan review — both were
/// misclassified as per-serve on the first pass:
///
/// - **`mcpMounted`** is per-*build*: it answers "does this sidecar have the
///   `mcp` extra", which is identical across every instance. Per-instance it
///   would force the sidebar's agent-access gate and the Settings pane to pick
///   an instance and read `false` when none is running.
/// - **`handshakeProjectPath`** is one global file. `dropHandshake()` fires on
///   seven independent lifecycle edges, so per-instance, instance B's *start*
///   would delete the file instance A wrote while A still published "exposed" —
///   the antenna lying again, which is the defect `3ac773fa` closed. One global
///   fact must have one owner.
///
/// The observation contract is the thing this step exists to prove: nested
/// `ObservableObject`s do **not** propagate through `@EnvironmentObject`, so the
/// fleet re-publishes this object's `objectWillChange`. If that forwarding is
/// wrong the symptom is silent — a boot spinner that never clears — which is
/// why it is proven here rather than discovered at N.
@MainActor
final class ServeInstance: ObservableObject {

    /// Lifecycle of this sidecar's process.
    @Published var state: ServeState = .idle

    /// Captured stdout/stderr, for the diagnostics pane and failure summaries.
    @Published var outputLines: [String] = []

    /// Bristlenose version from `/api/health`, shown in the About panel.
    @Published var serverVersion: String?

    /// True while an MCP agent has called a tool on this serve within
    /// `ServeManager.agentActivityWindow`.
    @Published var agentActiveNow: Bool = false

    /// Monotonic MCP tool-call count from the authed `/api/agent-activity`.
    /// The sidebar antenna animates on the EDGE (any increase), never on the
    /// absolute value — so a serve restart, which resets the server's counter
    /// to 0, must read as "new serve" rather than as a burst of activity.
    /// `noteAgentCallCount` owns that rule.
    @Published var agentCallCount: Int = 0

    /// The build of the `.mcpb` proxy that last called this serve, as it
    /// reported itself. Per-serve because it is a property of the agent
    /// talking to THIS sidecar, and it must not survive a project switch.
    @Published var agentProxyVersion: String?

    /// When the count last INCREASED. The sidebar's envelope is computed from
    /// this — a retriggerable hold, so a burst of calls is one animation
    /// rather than one per call. Nil = no activity observed on this serve.
    @Published var lastAgentCallAt: Date?

    /// Fold a fresh reading into `agentCallCount`, returning true if this was
    /// real activity. A decrease means the sidecar restarted and the server's
    /// counter went back to 0: adopt the new baseline silently, because
    /// animating there would claim an agent asked something when nothing did.
    func noteAgentCallCount(_ fresh: Int) -> Bool {
        defer { agentCallCount = fresh }
        guard fresh > agentCallCount else { return false }
        lastAgentCallAt = Date()
        return true
    }

    /// Bearer token for localhost API access control, parsed from stdout and
    /// injected into the WKWebView. Unscoped — it opens `/api/*`, so it is
    /// never what the handshake carries.
    @Published var authToken: String?

    /// The project this sidecar was spawned for. Holds the **spawn-time**
    /// spelling: bookmark healing can respell `Project.path` afterwards, which
    /// is why every comparison goes through `AgentActivity.samePath` rather
    /// than `==`.
    @Published var currentProjectPath: String?

    /// The MCP-scoped token this sidecar was spawned with — what the Connect
    /// Agent sheet hands out and what the handshake carries. Durable (Keychain,
    /// per project) normally; an *ephemeral process-lifetime scoped* token when
    /// the Keychain refuses. Never nil while a sidecar is spawned, and NEVER the
    /// unscoped `authToken`, which opens `/api/*`.
    ///
    /// Per-serve because it is per-*project*: two projects must not be able to
    /// read each other through one bearer.
    var mcpToken: String?

    /// This serve's `mcp.instance_id` from `/api/health`, minted fresh by the
    /// server each start, so the proxy can verify it is talking to *this* serve
    /// before the bearer leaves memory.
    ///
    /// Nil until the first health read lands — which is *after* `state` reaches
    /// `.running`, and the gap that made the antenna over-claim before
    /// `3ac773fa`.
    var mcpInstanceID: String?

    /// The sidecar process and the tasks draining it.
    var process: Process?
    var readTask: Task<Void, Never>?
    var timeoutTask: Task<Void, Never>?

    /// Epoch for this instance's start attempts. A late completion from a
    /// superseded attempt checks it before writing terminal state.
    ///
    /// **One counter per instance, and no second one** — `desktop/CLAUDE.md`'s
    /// standing rule against scattering ad-hoc cancellation checks. It becomes
    /// simpler at N, not harder: today one counter guards two distinct events (a
    /// cold start and a warm re-point), and the re-point is what Stage 3b
    /// deletes.
    var generation: Int = 0

    /// The kernel-assigned port while running (nil otherwise).
    var runningPort: Int? {
        guard case .running(let port) = state else { return nil }
        return port
    }
}
