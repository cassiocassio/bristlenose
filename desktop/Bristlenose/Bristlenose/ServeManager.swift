// AppKit is here for exactly one symbol — `NSApplication.willTerminateNotification`,
// which this object observes so the sidecar's shutdown belongs to the object that
// owns the process rather than to whichever view happens to be on screen. Nothing
// else in this file touches UI; keep it that way.
import AppKit
import Combine
import Darwin
import Foundation
import OSLog

private let log = Logger(subsystem: "app.bristlenose", category: "serve")

/// State machine for the `bristlenose serve` subprocess.
enum ServeState: Equatable {
    case idle
    case starting
    case running(port: Int)
    case failed(error: String)
}

/// Manages the `bristlenose serve` subprocess lifecycle.
///
/// Starts the Python serve process for a given project path, monitors stdout
/// for the "Report: http://..." readiness signal, parses the kernel-assigned
/// port from that URL, and exposes the serve URL as a published property for
/// the WKWebView to load.
///
/// Sidecar resolution happens once at `init()` via `SidecarMode.resolve`:
/// the resolved `mode` is stored and every downstream call site switches on
/// it. See `SidecarMode.swift` for the three modes + the Debug-only dev
/// env vars, and `desktop/CLAUDE.md` "Dev workflow" for the scheme table.
///
/// Port allocation: the host passes `--port 0` and the sidecar binds via
/// `bind(0)` (kernel-assigned). The actual port is read from the
/// "Report: http://127.0.0.1:NNNN/" stdout line. This means every host
/// launch gets a fresh port — orphan-sidecar cleanup is delegated to the
/// sidecar itself (parent-death watcher, see lifecycle.py), so the host
/// never has to enumerate processes (impossible under sandbox anyway).
@MainActor
final class ServeManager: ObservableObject {

    /// The one sidecar, today. Stage 3b turns this into a dictionary keyed on
    /// `Project.ID`; everything below forwards, so the ~50 existing call sites
    /// do not move when it does.
    ///
    /// Its `objectWillChange` is re-published by `init` — a nested
    /// `ObservableObject` does NOT propagate through `@EnvironmentObject` on
    /// its own, and the failure is silent (a boot spinner that never clears).
    @Published private(set) var instance = ServeInstance()
    private var instanceObservation: AnyCancellable?

    var state: ServeState {
        get { instance.state }
        set { instance.state = newValue }
    }
    var outputLines: [String] {
        get { instance.outputLines }
        set { instance.outputLines = newValue }
    }

    /// Bristlenose version from `/api/health` — fetched after server starts.
    /// Shown in the About panel alongside the Xcode build number.
    var serverVersion: String? {
        get { instance.serverVersion }
        set { instance.serverVersion = newValue }
    }
    /// Whether this sidecar mounted the MCP endpoint (the optional `mcp`
    /// extra). Drives the Connect Agent sheet's unavailable state.
    @Published var mcpMounted: Bool = false
    /// True while an MCP agent has called a tool on the fronted sidecar
    /// within `Self.agentActivityWindow`. Stateless HTTP has no connection
    /// to observe, so "connected" is defined as recent tool activity —
    /// drives the sidebar's antenna badge.
    var agentActiveNow: Bool {
        get { instance.agentActiveNow }
        set { instance.agentActiveNow = newValue }
    }

    /// Tool-call freshness (seconds) that still counts as "connected".
    /// Wider than the poll so a conversation with thinking gaps between
    /// tool calls doesn't flicker the badge.
    static let agentActivityWindow = 120
    private var agentPollTask: Task<Void, Never>?

    /// Bearer token for localhost API access control.
    /// Parsed from stdout line: `[bristlenose] auth-token: <token>`
    /// Injected into WKWebView via WKUserScript.
    var authToken: String? {
        get { instance.authToken }
        set { instance.authToken = newValue }
    }

    /// See `ServeInstance.mcpToken`. Forwarded so `MCPAgentsSettingsView` and
    /// the handshake writer keep one spelling while the state moves.
    private(set) var mcpToken: String? {
        get { instance.mcpToken }
        set { instance.mcpToken = newValue }
    }

    /// See `ServeInstance.mcpInstanceID`.
    private(set) var mcpInstanceID: String? {
        get { instance.mcpInstanceID }
        set { instance.mcpInstanceID = newValue }
    }

    /// May this instance write or delete the handshake file?
    ///
    /// There is **one** handshake naming **one** project, so exactly one manager
    /// may own it — `ServeFleet` designates. Without this, `syncHandshake`'s
    /// else-arm runs from every instance's 20-second activity poll, so a second
    /// running, non-exposed project deletes the exposed project's file within
    /// 20 seconds, repeatedly. Defaults to true so a lone manager (tests, the
    /// CLI-shaped path) behaves exactly as before.
    var handshakeOwner: Bool = true {
        didSet { if handshakeOwner != oldValue { syncHandshake() } }
    }

    /// The project path the MCP handshake currently names, or nil when no
    /// handshake exists. **Written by `syncHandshake()` and nowhere else** —
    /// it is that function's own answer, published rather than re-derived.
    ///
    /// The sidebar antenna's solid tier reads this. It used to read
    /// "serve is up + this is the fronted project", which is `syncHandshake`'s
    /// predicate minus `mcpInstanceID` and `mcpToken` — and `mcpInstanceID` is
    /// nilled on every start, park and warm re-point, refilled only by an
    /// `/api/health` read that lands *after* `state` reaches `.running`. So the
    /// badge went solid with no handshake on every start and every switch, and
    /// stayed that way if the health read kept failing. §5a-bis always
    /// specified "shared && handshake live"; this is that value.
    ///
    /// Publishing it also makes the badge correct when there is more than one
    /// serve, which is why the independent-windows stage needs nothing here.
    @Published private(set) var handshakeProjectPath: String?

    /// Injected at app level: does the project at this path have Agent
    /// Access on? Kept as a closure so ServeManager doesn't grow a
    /// ProjectIndex dependency. Unset (nil) reads as access-off: no
    /// handshake is ever written on a build that forgot the wiring.
    var agentAccessResolver: ((String) -> Bool)?

    /// Observer for Agent Access flips (Turn On/Off Agent Access) — re-syncs
    /// the handshake so turning access off deletes the file immediately.
    private var agentAccessObserver: Any?

    /// Resolved sidecar mode for this process. Decided once at init from env
    /// + bundle layout. If resolution fails, `mode` is nil and `state` is
    /// `.failed` — every downstream call becomes a no-op.
    let mode: SidecarMode?

    /// On init, resolve the sidecar mode. Orphan cleanup is delegated to
    /// the sidecar — see `desktop/CLAUDE.md` "Zombie process cleanup".
    init() {
        // The env-var string literals for the dev escape hatch live only
        // inside `#if DEBUG`-guarded code so the Release Mach-O has no
        // reference to them. `desktop/scripts/check-release-binary.sh`
        // verifies this at archive time.
        #if DEBUG
        let externalPortRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_EXTERNAL_PORT"]
        let sidecarPathRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_SIDECAR_PATH"]
        #else
        let externalPortRaw: String? = nil
        let sidecarPathRaw: String? = nil
        #endif

        let resolved = SidecarMode.resolve(
            externalPortRaw: externalPortRaw,
            sidecarPathRaw: sidecarPathRaw,
            bundleResourceURL: Bundle.main.resourceURL
        )
        switch resolved {
        case .success(let resolvedMode):
            self.mode = resolvedMode
            log.info("Mode: \(resolvedMode.logDescription, privacy: .public)")
            #if DEBUG
            if case .devSidecar(let path) = resolvedMode {
                log.warning(
                    "spawning dev sidecar from env var: \(path.path, privacy: .public)"
                )
            }
            #endif
        case .failure(let error):
            self.mode = nil
            log.error("sidecar mode resolution failed: \(error.description, privacy: .public)")
            self.state = .failed(error: error.localizedDescription)
        }

        // Re-publish the instance's changes as our own. A nested
        // `ObservableObject` does NOT propagate through `@EnvironmentObject`:
        // without this every `serveManager.state` read still returns the right
        // value, but no view is ever told to re-read it. The failure is silent
        // — boot spinner never clears, antenna never updates, toolbar never
        // enables — which is why the forwarding is established here, at one
        // instance, rather than discovered at N.
        //
        // Placed after the `mode` switch, not at the top: Swift forbids using
        // `self` before every stored property is initialised, and the switch's
        // failure arm writes `self.state`, which is itself a forwarder.
        instanceObservation = instance.objectWillChange.sink { [weak self] _ in
            self?.objectWillChange.send()
        }

        // One long-lived poll, not per-start tasks: it re-reads `state` each
        // cycle, so serve lifecycle churn can't leak or race it (the same
        // reasoning as the single `generation` token — one owner, no epochs).
        agentPollTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(20))
                await self?.pollAgentActivity()
            }
        }

        // NO per-instance prefs observer. One existed here while there was one
        // manager; with one per project it becomes "restart all N" — N cold
        // report remounts in windows nobody is looking at, which is precisely
        // the arm `ServeEnvStaleness` declines. The fan-out is the fleet's
        // (`ServeFleet.applyEnvChange`), which restarts the fronted and exposed
        // instances now and marks the rest to restart when someone looks at them.

        agentAccessObserver = NotificationCenter.default.addObserver(
            forName: .bristlenoseAgentAccessChanged,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.syncHandshake()
            }
        }

        // Stop the sidecar on quit. This lived on `ContentView` until 16 Aug
        // 2026, which was survivable while a window was always open — but the
        // serve now deliberately outlives its windows (closing the last one
        // keeps it up, so reopening is instant), and with no window there is no
        // ContentView to run the handler. Quitting from that state left the
        // teardown to the sidecar's own parent-death watcher: a backstop, not a
        // shutdown path. The object that owns the process owns its shutdown.
        terminationObserver = NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.stop() }
        }

        // Sweep a SIGKILL leftover (force quit, OOM, the Xcode stop button —
        // none of which run the delete-on-stop path). Gated on `handshakeOwner`:
        // it was unconditional while there was one manager per app, and with one
        // per project it meant minting a second project's manager deleted the
        // FIRST project's live handshake. Only the designated owner may touch
        // the file — one global fact, one writer.
        if handshakeOwner { dropHandshake() }
    }

    /// The URL to load in WKWebView when serve is running.
    var serveURL: URL? {
        guard case .running(let port) = state else { return nil }
        return URL(string: "http://127.0.0.1:\(port)/report/")
    }

    /// The kernel-assigned port when serve is running (nil otherwise). Used by
    /// native localhost API clients (e.g. `MiroAPI`) alongside `authToken`.
    var runningPort: Int? { instance.runningPort }

    private var process: Process? {
        get { instance.process }
        set { instance.process = newValue }
    }
    private var readTask: Task<Void, Never>? {
        get { instance.readTask }
        set { instance.readTask = newValue }
    }
    private var timeoutTask: Task<Void, Never>? {
        get { instance.timeoutTask }
        set { instance.timeoutTask = newValue }
    }
    /// Incremented on each start() AND on each warm re-point — late completions
    /// (a superseded readiness wait) check this before writing terminal state.
    private var generation: Int {
        get { instance.generation }
        set { instance.generation = newValue }
    }

    /// Last project path passed to start() — used by restartIfRunning() and the
    /// DEBUG menu's reveal/log/provenance actions (the served project is the one
    /// whose report is on screen). Read-only outside ServeManager.
    /// **Observable since 19 Aug 2026, and it has to be.** Peer windows sync
    /// their selection from this, and it was a plain stored property — the sync
    /// appeared to work only because `state` happens to be written in the same
    /// synchronous block. That is a coincidence, not a design, and the first
    /// reordering of those two lines would have broken every sibling window
    /// silently. Now stored on `ServeInstance`, whose change notification the
    /// fleet re-publishes; the observability survives the move.
    private(set) var currentProjectPath: String? {
        get { instance.currentProjectPath }
        set { instance.currentProjectPath = newValue }
    }

    /// The most-recently-fronted project's sidecar, kept warm so switching
    /// back is an instant hand-off (Phase A2 warm-sidecar pool, single-slot).
    /// At most one. See `ParkedSidecar.swift` for the design + why one slot.
    private var parked: ParkedSidecar?

    /// Observer for preference changes that require a serve restart.
    private var prefsObserver: Any?

    /// Observer for app termination — stops the sidecar. Held so it lives as
    /// long as this object does, which is the app's lifetime.
    private var terminationObserver: Any?

    deinit {
        // ServeManager is app-lifetime today, but the poll loop shouldn't
        // outlive its owner if that ever changes.
        agentPollTask?.cancel()
    }

    /// Start serving a project. Callers must call `stop()` or
    /// `shutdown(timeout:)` first if a sidecar is already running — `start()`
    /// only forwards to `stop()` defensively when a `process` reference
    /// lingers. Direct callers without a prior sidecar (cold launch,
    /// post-Locate resume, post-failure retry) skip the teardown entirely.
    /// `switchProject(to:)` is the orchestrator for the prior-running case.
    ///
    /// - Parameter projectPath: Absolute path to the project directory.
    func start(projectPath: String) {
        // Expired alpha `.dmg` builds never start the sidecar (AlphaBuild is a
        // no-op on Debug / App Store / TestFlight). The expiry flow blocks the
        // window with modals, but guard here too so no start path — launch
        // restore, consent grant, retry — can serve behind them.
        guard !AlphaBuild.isExpired() else {
            log.notice("serve start refused — alpha build expired")
            return
        }
        // **Already serving, or starting, exactly this project? Nothing to do.**
        //
        // This guard used to live in `switchProject(to:)`, whose comment said
        // plainly that re-pointing at the same project "is actively harmful".
        // Stage 3b deleted `switchProject` — a window observes a different
        // manager rather than switching one — and the guard did not come with
        // it, which put the harm back with nothing to catch it.
        //
        // Reachable the moment two windows show one study: each window's
        // selection path calls `start()` on the SAME manager, and the second
        // call hits the `stop()` below, SIGINTs a sidecar that is still booting,
        // and the first window's readiness watcher reports the corpse —
        // "Server exited before becoming ready (code 2)". Observed on screen
        // 20 Aug 2026.
        //
        // `.failed` and `.idle` deliberately fall through: Retry must work, and
        // so must a first start. `samePath` because bookmark healing can respell
        // `Project.path` while this holds the spawn-time spelling.
        if let current = currentProjectPath,
           AgentActivity.samePath(current, projectPath) {
            switch state {
            case .running, .starting: return
            case .idle, .failed: break
            }
        }

        if process != nil {
            stop()
        }

        guard let mode = self.mode else {
            // Resolution failed at init; state is already .failed.
            return
        }

        currentProjectPath = projectPath
        // Old project's agent activity must not light the new project's
        // badge for a poll tick (same class as the authToken reset below).
        agentActiveNow = false
        generation += 1
        state = .starting
        outputLines = []
        // Clean slate for this sidecar's stdout captures. Critical for the cold
        // path of switchProject(to:), which *parks* the outgoing sidecar rather
        // than stop()-ing it — so `process` is nil here, the defensive stop()
        // above doesn't fire, and a non-nil authToken from the previous sidecar
        // would make handleLine's `if authToken == nil` guard SKIP the new
        // sidecar's `[bristlenose] auth-token:` line. The native MiroAPI then
        // sends the stale bearer to the fresh sidecar → 401 Unauthorized (the
        // WebView survives on cookie auth, masking it). The warm re-point path
        // sets authToken directly via adoptFronted and never reaches here.
        authToken = nil
        serverVersion = nil
        // The old sidecar's handshake names an instance that is going away;
        // remove it now so the proxy reports honestly during the boot gap.
        // The new one is written when this serve reaches .running and its
        // instance_id has been read from /api/health (syncHandshake).
        mcpInstanceID = nil
        dropHandshake()

        // External mode: no subprocess. Just point at the existing server.
        // No handshake either — we didn't spawn it, so we don't know its
        // scoped token; a stale `mcpToken` from a previous bundled serve
        // must not be advertised against a server that would 401 it.
        if case .external(let port) = mode {
            mcpToken = nil
            log.info("connecting to external server on port \(port, privacy: .public)")
            state = .running(port: port)
            return
        }

        let executableURL: URL
        switch mode {
        case .bundled(let path), .devSidecar(let path):
            executableURL = path
        case .external:
            return  // handled above
        }

        let proc = Process()
        self.process = proc
        proc.executableURL = executableURL
        // --port 0 → sidecar binds via bind(0); we read the actual port
        // from the "Report:" stdout line in handleLine(_:).
        proc.arguments = Self.arguments(for: mode, projectPath: projectPath)

        // Complete subprocess environment — minimal var allowlist, prefs, TLS
        // certs, bundled FFmpeg/ffprobe, parent-death handshake, and the active
        // provider's API key. Single source of truth shared with PipelineRunner
        // so the two spawn sites can't drift. See BristlenoseShared.childEnvironment.
        var env = BristlenoseShared.childEnvironment(for: mode)

        // Stable per-project MCP bearer token, SCOPED: the server validates
        // /mcp against _BRISTLENOSE_MCP_TOKEN alone, so the one credential
        // that leaves the trust boundary (handshake file, agent configs)
        // opens the four read-only tools and nothing else — not /api/*
        // writes, not participant names. The server's own rotating auth
        // token keeps gating /api as before. Durable across restarts
        // because the value comes from the Keychain, so an agent config
        // made today doesn't 401 tomorrow. Keychain refusal (always on
        // ad-hoc builds, -34018) mints an EPHEMERAL scoped token instead —
        // never fall back to `authToken`: the handshake writer publishes
        // this value into a file another vendor's process reads, and the
        // unscoped token would open /api/* on every local QA build
        // (design §3.1, review Finding 3). Cost of the ephemeral path is
        // durability only.
        mcpToken = MCPTokenStore.token(forProjectPath: projectPath)
            ?? MCPTokenStore.mintEphemeral()
        env["_BRISTLENOSE_MCP_TOKEN"] = mcpToken
        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        let handle = pipe.fileHandleForReading
        // Identity token for routing this process's stdout/termination. Stays
        // valid when the process later moves to the parked slot — handleLine
        // and handleTermination compare it against the *current* fronted vs
        // parked process to decide the role dynamically. ObjectIdentifier is
        // Sendable (Process is not), so it's safe to carry into the detached read.
        let procID = ObjectIdentifier(proc)

        // Read pipe on a detached task to avoid Sendable/actor-isolation issues.
        readTask = Task.detached { [weak self] in
            let fileHandle = handle
            while true {
                let data = fileHandle.availableData
                if data.isEmpty { break }  // EOF

                if let chunk = String(data: data, encoding: .utf8) {
                    let lines = chunk.components(separatedBy: "\n")
                    for line in lines where !line.isEmpty {
                        await self?.handleLine(line, fromProcessID: procID)
                    }
                }
            }
        }

        proc.terminationHandler = { [weak self] p in
            // Runs off-main. Carry only Sendable values across to MainActor
            // (status + the process identity) — never the non-Sendable Process.
            let status = p.terminationStatus
            let terminatedID = ObjectIdentifier(p)
            Task { @MainActor in
                self?.handleTermination(processID: terminatedID, status: status)
            }
        }

        do {
            try proc.run()
        } catch {
            state = .failed(error: "Failed to launch: \(error.localizedDescription)")
            return
        }

        timeoutTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(15))
            guard !Task.isCancelled else { return }
            await MainActor.run {
                guard let self, case .starting = self.state else { return }
                self.state = .failed(error: "Server failed to start within 15 seconds")
                self.process?.terminate()
            }
        }
    }

    /// Build the argument list for the sidecar subprocess.
    ///
    /// - Bundled: `sidecar_entry.py` auto-injects "serve", so pass flags only.
    /// - Dev sidecar: user's venv-installed `bristlenose`, needs "serve"
    ///   prepended.
    ///
    /// `--port 0` triggers the sidecar's `bind(0)` path; the kernel-assigned
    /// port is read from the "Report:" stdout line by `handleLine(_:)`.
    private static func arguments(for mode: SidecarMode, projectPath: String) -> [String] {
        let flags = ["--no-open", "--port", "0", projectPath]
        switch mode {
        case .bundled:
            return flags
        case .devSidecar:
            return ["serve"] + flags
        case .external:
            return []
        }
    }

    /// Stop the serve process and reset state.
    func stop() {
        timeoutTask?.cancel()
        timeoutTask = nil
        drainParked()  // tear down any warm sidecar (Cmd+Q, folder/empty selection)

        // The serve is going away — an agent must not find a live-looking
        // handshake naming a port about to be freed.
        mcpInstanceID = nil
        dropHandshake()

        // External mode: no subprocess was spawned — just reset state.
        if case .external = mode, process == nil {
            readTask?.cancel()
            readTask = nil
            state = .idle
            serverVersion = nil
            authToken = nil
            return
        }

        if let proc = process, proc.isRunning {
            proc.interrupt()  // SIGINT — lets Uvicorn shut down gracefully
        }
        readTask?.cancel()
        readTask = nil
        process = nil
        state = .idle
        serverVersion = nil
        authToken = nil
    }

    /// Restart the serve process if one is running, using the same project path.
    /// Called when user preferences change (provider, model, API key, etc.).
    /// Uses the same escalating teardown as `switchProject(to:)` so a Whisper-wedged
    /// sidecar doesn't survive a prefs save (William's parsimony pass, Finding 32).
    func restartIfRunning() {
        // A parked sidecar baked its provider/model/API-key/prefs env at spawn
        // time (BristlenoseShared.childEnvironment). A prefs OR consent change
        // (both post .bristlenosePrefsChanged) makes that env stale, so the
        // warm slot must be invalidated — otherwise switching back would
        // re-point to a sidecar serving with the old config (review F6/F7).
        drainParked()
        guard case .running = state, let path = currentProjectPath else { return }
        log.info("preferences changed — restarting serve")
        Task { @MainActor in
            await shutdown(timeout: .seconds(2))
            start(projectPath: path)
        }
    }

    /// Synchronously kill the running sidecar with signal escalation.
    /// SIGINT first (Uvicorn graceful shutdown), wait up to `timeout` seconds,
    /// then SIGKILL if the process is still alive.
    ///
    /// Async because the wait is non-blocking. Safe to call when no process
    /// is running (no-op).
    ///
    /// This is the teardown half of `switchProject(to:)`. `stop()` is the
    /// fire-and-forget version used by Cmd+Q and selection-cleared paths —
    /// it sends SIGINT and returns immediately without waiting for exit.
    func shutdown(timeout: Duration) async {
        timeoutTask?.cancel()
        timeoutTask = nil
        drainParked()  // a full teardown reclaims the warm slot too

        // Ownership token captured at entry. If a newer start() (a superseding
        // switch, or restartIfRunning) bumps `generation` while we await teardown
        // below, our terminal state-writes must NOT clobber the new owner's
        // process/state/readTask. Same counter that start()/terminationHandler
        // use. Only the post-await main path needs this — the early-return arms
        // run synchronously from entry, before any owner change can interleave.
        let myGeneration = generation

        // Full teardown — the handshake must not outlive the serve it names.
        // Safe before the supersession guard below: a superseding start()
        // already removed + will rewrite its own on .running.
        mcpInstanceID = nil
        dropHandshake()

        if case .external = mode, process == nil {
            readTask?.cancel()
            readTask = nil
            state = .idle
            serverVersion = nil
            authToken = nil
            currentProjectPath = nil
            return
        }

        guard let proc = process, proc.isRunning else {
            readTask?.cancel()
            readTask = nil
            process = nil
            state = .idle
            serverVersion = nil
            authToken = nil
            currentProjectPath = nil
            return
        }

        // Polite signal — Uvicorn handles SIGINT as graceful shutdown.
        proc.interrupt()

        // Wait up to `timeout`, polling every 50ms. Uvicorn typically exits
        // in <100ms; the timeout protects against a wedged event loop or a
        // C extension holding the GIL through the shutdown signal.
        let deadline = ContinuousClock.now.advanced(by: timeout)
        while proc.isRunning && ContinuousClock.now < deadline {
            try? await Task.sleep(for: .milliseconds(50))
        }

        if proc.isRunning {
            // SIGKILL — bypasses Python signal handling entirely; always wins.
            // Side effect: no `sidecar_exit` log line (handler never runs).
            log.warning("sidecar didn't exit within timeout; sending SIGKILL")
            kill(proc.processIdentifier, SIGKILL)
            // Best-effort grace for kernel to reap. The `generation` counter
            // protects state writes against a late terminationHandler callback
            // if the kernel hasn't yet reaped by the time we clear `process`
            // below — see `start()` for that guard.
            try? await Task.sleep(for: .milliseconds(100))
        }

        // A newer owner took over while we awaited teardown — leave its
        // process/state/readTask intact and bail. Our captured `proc` was
        // already SIGINT'd above, which is correct: it's the one being torn
        // down. Closes Finding 18 (a superseded switch's shutdown could
        // otherwise overwrite the winner's process=proc/state=.starting with
        // nil/.idle → orphaned sidecar, detail pane stuck on the boot spinner);
        // also bounds the restartIfRunning-vs-switch terminal-state clobber
        // (Finding 19). Reuses the existing `generation` token — no second epoch.
        guard generation == myGeneration else {
            log.info("shutdown superseded mid-teardown — leaving published state to the new owner")
            return
        }
        readTask?.cancel()
        readTask = nil
        process = nil
        state = .idle
        serverVersion = nil
        authToken = nil
        currentProjectPath = nil
    }

    /// Switch the loaded project. **Warm-pool fast path (Phase A2):** if the
    /// most-recently-fronted project is still parked + alive, this is a near
    /// hand-off — park the outgoing sidecar, re-point to the warm one, no
    /// teardown+restart. Otherwise it parks the outgoing sidecar and cold-starts
    /// a fresh one (the previous behaviour, minus the teardown of the project
    /// you might switch straight back to).
    ///
    /// Crucially the fast path does **no teardown on the hot path** — that is
    /// what dissolves the rapid-switch crash race (a switch-N teardown racing a
    /// switch-N+1 boot). The race survives ONLY for cold starts (a 3rd distinct
    /// project, or one whose warm slot was evicted), where the existing
    /// `generation`-guarded supersession (A1) still applies. So the reliability
    /// win is total for warm hits, partial for cold — see the review log F13.
    ///
    /// **Choreography:**
    /// 1. (caller) UI skeleton — sidebar selection updates immediately.
    /// 2. (here) `detachFronted()` parks the outgoing sidecar (no signal).
    /// 3. (caller) Resolve new bookmark + `ProjectBookmarkLease` — if it throws,
    ///    mark project `cantFind` and don't call this.
    /// 4. (here) Re-point to the warm slot, or `start()` a fresh sidecar.
    /// 5. (automatic) WKWebView re-mount — `ContentView` keys the WebView on
    ///    `project.id` + serve port, so a re-point (port change) forces a fresh
    ///    `makeNSView` with a fresh `WKWebsiteDataStore.nonPersistent()` AND
    ///    re-injects the warm sidecar's own bearer token. Keying on id alone
    ///    would NOT re-mount on a same-project switch-back at a new port, which
    ///    would reuse the previous project's token → silent 401s (review F1).
    ///
    /// **Cache leak defence:** the server adds `Cache-Control: no-store` to
    /// every `/api/projects/*` response (`bristlenose/server/app.py`).
    ///
    /// - Parameter path: filesystem path to the project root.
    /// - Returns: when the sidecar reaches `.running` or `.failed`. Does NOT
    ///   throw — callers inspect `state`; `.failed` flows to `BootView(.failed)`.
    ///
    /// **Security-scoped bookmark lifecycle.** `ProjectIndex.syncWatchers()`
    /// holds a `ProjectBookmarkLease` for every `.ready` project for the app's
    /// lifetime, so every (fronted or parked) sidecar inherits an already-open
    /// security scope. No explicit lease handoff is needed here.
    func switchProject(to path: String) async {
        // Already serving exactly this? Then there is nothing to switch, and
        // doing it anyway is actively harmful: a re-point mints a new port, and
        // every window's web view is keyed on the port (`ServeSession.viewID`),
        // so all of them remount and land back on the Project dashboard.
        //
        // Reachable the moment a second window exists — a new window restores
        // the same project and asks for it again — which is exactly how
        // multi-window first behaved: opening a window reset every other window
        // to the dashboard (16 Aug 2026). Preference changes take
        // `restartIfRunning()`, not this path, so a same-path no-op loses
        // nothing.
        if case .running = state, currentProjectPath == path { return }

        let decision = RepointDecision.evaluate(
            target: path,
            parkedPath: parked?.projectPath,
            parkedAlive: parked?.isAlive ?? false
        )

        if case .repoint = decision, let incoming = parked {
            // Warm fast path. Take the warm entry out of the slot, park the
            // outgoing sidecar in its place (instant A↔B keeps both warm), and
            // hand off. Bump `generation` FIRST: the re-point is a fronted-state
            // write, so a late in-flight cold-start readiness completion (gated
            // on `generation`, handleLine) must not be able to land afterward
            // and clobber us with its stale port (review F2).
            parked = nil
            let outgoing = detachFronted()
            generation += 1
            state = .starting  // brief — the liveness probe is a sub-100ms localhost round-trip

            // Liveness backstop: `isRunning` (already checked by .evaluate) does
            // not catch a wedged-but-alive or about-to-die sidecar. A short
            // /api/health probe does (connection-refused = dead, timeout =
            // wedged). On failure, drop the stale entry and cold-start so the
            // user sees a real boot, never a silent blank pane (review F1/F3).
            let alive = await probeHealth(port: incoming.port, token: incoming.authToken)
            guard !Task.isCancelled else {
                // Superseded mid-probe — don't leak either candidate's process.
                tearDownEntry(incoming)
                if let outgoing { tearDownEntry(outgoing) }
                return
            }
            if alive {
                adoptFronted(incoming, path: path)
                parked = outgoing  // the project we just left stays warm
                log.info("sidecar_repointed project=\(path, privacy: .public) port=\(incoming.port, privacy: .public) health=ok")
                Task { await self.fetchServerVersion(port: incoming.port) }
                return
            }
            log.info("sidecar_repointed project=\(path, privacy: .public) health=failed — cold starting")
            tearDownEntry(incoming)
            parked = outgoing
            start(projectPath: path)
        } else {
            // Cold start. Park the outgoing sidecar (evicting any *other* warm
            // entry — single slot), then spawn fresh. detachFronted() clears
            // `process` first, so start()'s defensive stop() won't fire and the
            // freshly-parked slot survives.
            guard !Task.isCancelled else {
                log.info("switchProject superseded — abandoning before start()")
                return
            }
            if let outgoing = detachFronted() {
                if let existing = parked {
                    log.info("sidecar_evicted project=\(existing.projectPath, privacy: .public) reason=park")
                    tearDownEntry(existing)
                }
                parked = outgoing
            }
            log.info("starting new sidecar")
            start(projectPath: path)
        }

        // Wait for transition out of .starting (to .running or .failed) so
        // callers can await the switch. Bounded by start()'s 15s timeout (cold)
        // or the probe (warm-failed→cold). Bail if a newer switch cancels us.
        let deadline = ContinuousClock.now.advanced(by: .seconds(20))
        while case .starting = state, !Task.isCancelled, ContinuousClock.now < deadline {
            try? await Task.sleep(for: .milliseconds(50))
        }
    }

    // MARK: - Warm-sidecar pool (single parked slot, Phase A2)

    /// Detach the current fronted sidecar so it can be parked WITHOUT signalling
    /// it. Returns a `ParkedSidecar` when the fronted sidecar was `.running`
    /// (worth keeping warm); otherwise tears down any half-started process and
    /// returns nil. Does not write `state` — the caller transitions it.
    private func detachFronted() -> ParkedSidecar? {
        timeoutTask?.cancel()
        timeoutTask = nil
        // The outgoing project stops being fronted; its handshake goes with
        // it ("delete on adoptFronted for the outgoing project"). v1 scope:
        // the handshake follows the fronted serve only — a parked-but-alive
        // sidecar is deliberately not advertised (design §3.6 records the
        // parked-badge question as scope for the UI pass).
        mcpInstanceID = nil
        dropHandshake()
        if case .running(let port) = state, let proc = process, let path = currentProjectPath {
            let entry = ParkedSidecar(
                projectPath: path, port: port, authToken: authToken,
                mcpToken: mcpToken,
                serverVersion: serverVersion, process: proc, readTask: readTask, buffer: outputLines
            )
            log.info("sidecar_parked project=\(path, privacy: .public) port=\(port, privacy: .public)")
            process = nil
            readTask = nil  // ownership moves to the entry; the task keeps draining
            return entry
        }
        // Not running (idle / starting / failed) — not worth keeping warm.
        if let proc = process {
            tearDownProcess(proc, readTask: readTask, label: currentProjectPath ?? "")
        }
        process = nil
        readTask = nil
        return nil
    }

    /// Promote a parked sidecar back to fronted, restoring its port, token, and
    /// version atomically before the WebView re-mounts. `generation` is bumped
    /// by the caller before the liveness probe.
    private func adoptFronted(_ entry: ParkedSidecar, path: String) {
        agentActiveNow = false
        // Restore the token the parked sidecar was SPAWNED with — not a
        // fresh Keychain read. On the Keychain-refusal path the spawn-time
        // value is an ephemeral mint; re-minting here would produce a token
        // the parked process's env doesn't hold, and every handshake this
        // instance then advertises would 401.
        mcpToken = entry.mcpToken
        // instance_id is re-read from /api/health (fetchServerVersion below
        // the re-point) — syncHandshake writes the adopted project's
        // handshake once it lands.
        mcpInstanceID = nil
        process = entry.process
        readTask = entry.readTask
        authToken = entry.authToken
        serverVersion = entry.serverVersion
        currentProjectPath = path
        outputLines = entry.buffer
        state = .running(port: entry.port)
    }

    /// Tear down a parked entry: cancel its read task, SIGINT → (bounded wait)
    /// → SIGKILL. Silent to the user — never writes `state`, never surfaces
    /// `.failed`, never a toast (it's housekeeping for a project the user isn't
    /// looking at, review F12). The host-side `sidecar_evicted` log line is
    /// emitted by the caller *before* this, so even the SIGKILL branch — which
    /// produces no Python `sidecar_exit` line — leaves a trace (review F8).
    private func tearDownEntry(_ entry: ParkedSidecar) {
        tearDownProcess(entry.process, readTask: entry.readTask, label: entry.projectPath)
    }

    private func tearDownProcess(_ proc: Process, readTask: Task<Void, Never>?, label: String) {
        readTask?.cancel()
        guard proc.isRunning else { return }
        proc.interrupt()  // SIGINT — Uvicorn graceful shutdown
        // Escalate to SIGKILL off the hot path. A GIL-wedged sidecar
        // (whisper/torch mid-call) ignores SIGINT; without escalation it would
        // leak as an orphan the sandboxed host can never enumerate (review F5).
        // Runs on MainActor (sleeps yield) but switchProject does not await it.
        Task { @MainActor in
            for _ in 0..<40 {  // up to ~2s, polling every 50ms
                if !proc.isRunning { return }
                try? await Task.sleep(for: .milliseconds(50))
            }
            if proc.isRunning {
                log.warning("parked sidecar didn't exit; SIGKILL project=\(label, privacy: .public)")
                kill(proc.processIdentifier, SIGKILL)
            }
        }
    }

    /// Tear down the warm slot, if any. Used by stop()/shutdown() (Cmd+Q,
    /// folder selection) and restartIfRunning() (prefs/consent change — parked
    /// env is stale, review F6/F7). Silent.
    func drainParked() {
        guard let entry = parked else { return }
        log.info("sidecar_evicted project=\(entry.projectPath, privacy: .public) reason=drain")
        tearDownEntry(entry)
        parked = nil
    }

    /// Tear down the warm slot iff it serves one of `paths`. Called when a
    /// project is removed from the sidebar so a warm sidecar isn't left serving
    /// an explicitly-deleted project (review F16).
    func dropParked(forPaths paths: Set<String>) {
        guard let entry = parked, paths.contains(entry.projectPath) else { return }
        log.info("sidecar_evicted project=\(entry.projectPath, privacy: .public) reason=removed")
        tearDownEntry(entry)
        parked = nil
    }

    /// Liveness probe for a re-point: confirm the warm sidecar is actually
    /// serving (not dead, not wedged) before handing the WebView to it. NOTE:
    /// `/api/health` is auth-EXEMPT (`bristlenose/server/middleware.py`), so this
    /// validates *liveness*, not the token — token correctness on re-point is
    /// guaranteed structurally (the WebView re-mounts on the port change and
    /// re-injects the restored per-instance token; pinned by RepointDecision
    /// tests). The bearer header is attached anyway so the probe upgrades for
    /// free if /api/health ever becomes auth-required.
    private func probeHealth(port: Int, token: String?, timeout: TimeInterval = 3) async -> Bool {
        guard let url = URL(string: "http://127.0.0.1:\(port)/api/health") else { return false }
        var req = URLRequest(url: url, timeoutInterval: timeout)
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        do {
            let (_, resp) = try await URLSession.shared.data(for: req)
            guard let http = resp as? HTTPURLResponse else { return false }
            return (200..<300).contains(http.statusCode)
        } catch {
            return false  // connection refused (dead) or timeout (wedged)
        }
    }

    /// Route a process's termination by identity to the fronted-death path
    /// (transition `state` to `.failed`) or the parked-death path (drop the warm
    /// slot silently, review F9). A process that is neither (already superseded
    /// and torn down) is a no-op — identity subsumes the old generation guard.
    private func handleTermination(processID procID: ObjectIdentifier, status: Int32) {
        if let fronted = process, ObjectIdentifier(fronted) == procID {
            timeoutTask?.cancel()
            // The serve died — its handshake must not keep naming the freed
            // port. (The sidecar deletes its own on a graceful exit; this
            // covers the crash where its atexit never ran.)
            mcpInstanceID = nil
            dropHandshake()
            let lastLines = outputLines.suffix(5).joined(separator: "\n")
            if case .running = state {
                state = .failed(error: "Server exited with code \(status)\n\(lastLines)")
            } else if case .starting = state {
                state = .failed(error: "Server exited before becoming ready (code \(status))\n\(lastLines)")
            }
        } else if let entry = parked, ObjectIdentifier(entry.process) == procID {
            // Death-while-parked: drop the stale slot so a later switch-back
            // cold-starts instead of re-pointing into a dead port.
            log.info("sidecar_parked_died project=\(entry.projectPath, privacy: .public) port=\(entry.port, privacy: .public)")
            entry.readTask?.cancel()
            parked = nil
        }
        // else: stale process from a superseded run — nothing to do.
    }

    // MARK: - Private

    /// One immediate badge poll — called when the researcher copies a
    /// config, the moment they are most likely to be watching the sidebar.
    func refreshAgentActivity() async {
        await pollAgentActivity()
    }

    /// One poll cycle for the sidebar's antenna badge. Quiet at runtime —
    /// a failed health read just clears the badge (absence is information;
    /// the serve dying has its own, louder signals). Deliberately NOT gated
    /// on `mcpMounted`: this poll re-reads `mcp.mounted` every cycle, so a
    /// raced or failed startup fetch self-corrects within one tick instead
    /// of leaving the Connect sheet claiming "not available in this build"
    /// for the whole session.
    private func pollAgentActivity() async {
        guard case .running(let port) = state,
              let url = URL(string: "http://127.0.0.1:\(port)/api/health") else {
            if agentActiveNow { agentActiveNow = false }
            return
        }
        var parsed: (mounted: Bool, active: Bool) = (mcpMounted, false)
        if let (data, _) = try? await URLSession.shared.data(from: url),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            parsed = AgentActivity.parse(json)
            if let iid = AgentActivity.instanceID(json) {
                mcpInstanceID = iid
            }
            // Self-heal UNCONDITIONALLY, not only on an instance_id change:
            // a one-off write failure at the .running transition (dir
            // momentarily unwritable) would otherwise be terminal for the
            // whole serve, because the id never changes again. The sync is
            // idempotent and the file is sub-1KB — a 20s rewrite is free.
            syncHandshake()
        }
        if parsed.mounted != mcpMounted { mcpMounted = parsed.mounted }
        if parsed.active != agentActiveNow { agentActiveNow = parsed.active }
    }

    /// Fetch the Bristlenose version (and MCP availability) from the serve
    /// health endpoint. Non-critical — if it fails, both stay at their
    /// defaults. `/api/health` is auth-exempt, so this needs no token.
    private func fetchServerVersion(port: Int) async {
        guard let url = URL(string: "http://127.0.0.1:\(port)/api/health") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                // A completion that arrives after a project switch must not
                // write the OLD serve's identity over the new one — with the
                // handshake in play that would advertise the new port under
                // the old instance_id (proxy reads it as stale → "isn't
                // open" until the 20s poll heals it). Port equality is the
                // ownership check: only the still-fronted serve may land.
                guard case .running(let current) = self.state, current == port else { return }
                if let version = json["version"] as? String {
                    self.serverVersion = version
                }
                self.mcpMounted = AgentActivity.parse(json).mounted
                // This runs right after .running (cold start or warm
                // re-point) — the moment the handshake becomes writable:
                // port answering, instance_id known. Write-on-.running is
                // the §5b corollary ("handshake exists" implies "port
                // answers").
                self.mcpInstanceID = AgentActivity.instanceID(json)
                self.syncHandshake()
            }
        } catch {
            // Degraded, not broken: version stays nil (About shows build
            // number only) and mcpMounted stays put until the 20s badge
            // poll re-reads it. Logged because a silent miss here used to
            // pin the Connect sheet on "unavailable" for a whole session.
            log.info("health fetch failed (poll will retry): \(error.localizedDescription, privacy: .public)")
        }
    }

    /// Delete the handshake file AND clear the path the sidebar reads. One
    /// function because the two must not drift: a bare `MCPHandshake.remove()`
    /// would leave the antenna solid for a project no agent can reach, which is
    /// the exact defect publishing the path was meant to close. Every lifecycle
    /// edge that used to call `remove()` directly calls this.
    private func dropHandshake() {
        guard handshakeOwner else { return }
        MCPHandshake.remove()
        if handshakeProjectPath != nil { handshakeProjectPath = nil }
    }

    /// Reconcile the MCP handshake file with the current serve state: write
    /// it when the fronted project is `.running` with Agent Access on and
    /// the serve's `instance_id` is known; delete it otherwise. Idempotent —
    /// safe to call from every lifecycle edge and the 20s poll.
    ///
    /// The predicate lives in `HandshakeExposure.write` so the sidebar and
    /// this writer cannot hold different opinions about what "exposed" means
    /// — the badge reads `handshakeProjectPath`, which only this function
    /// sets, from that one decision.
    ///
    /// The gate order is deliberate: `mcpToken` here is always the SCOPED
    /// token (`start()` never leaves it nil while a sidecar is spawned, and
    /// never falls back to `authToken`), so nothing this writes can open
    /// `/api/*`. No `mcpMounted` gate: on a build without the mcp extra the
    /// proxy's health probe / 404 path produces the honest "built without
    /// agent support" sentence, which beats a missing-file "isn't open".
    private func syncHandshake() {
        guard handshakeOwner else { return }
        guard let plan = HandshakeExposure.write(
            state: state,
            currentProjectPath: currentProjectPath,
            instanceID: mcpInstanceID,
            token: mcpToken,
            agentAccess: { agentAccessResolver?($0) ?? false }
        ) else {
            dropHandshake()
            return
        }
        MCPHandshake.write(port: plan.port, token: plan.token, instanceID: plan.instanceID)
        if handshakeProjectPath != plan.path { handshakeProjectPath = plan.path }
    }

    /// Strip ANSI escape sequences and OSC 8 hyperlinks for clean display.
    private static let ansiRegex = try! NSRegularExpression(
        pattern: "\\x1b\\[[0-9;]*m|\\x1b\\]8;;[^\\x1b]*\\x1b\\\\",
        options: []
    )

    /// Regex captures the kernel-assigned port from a "Report: http://..."
    /// stdout line (e.g. `  Report: http://127.0.0.1:54321/report/`). The
    /// port is whatever the OS handed the sidecar via `bind(0)`, and it
    /// changes every launch — never cache it across runs.
    private static let reportPortRegex = try! NSRegularExpression(
        // Anchored to start of line — a Python traceback containing
        // the literal substring `Report: http://...` shouldn't be
        // mistaken for the canonical readiness print.
        pattern: #"^\s*Report:\s*http://127\.0\.0\.1:(\d+)/"#,
        options: [.anchorsMatchLines]
    )

    private func handleLine(_ line: String, fromProcessID procID: ObjectIdentifier) {
        let clean = Self.ansiRegex.stringByReplacingMatches(
            in: line,
            range: NSRange(line.startIndex..., in: line),
            withTemplate: ""
        )

        // Route by identity. A line from a PARKED (or already-superseded)
        // process must NOT run any fronted logic — not token capture, not the
        // published `outputLines`, not readiness/state. Otherwise a late stdout
        // line from the parked sidecar could overwrite the fronted instance's
        // auth token (the same 401 class as the re-point token bug, review F10).
        // Parked lines are buffered on their own entry (capped) so the pipe
        // keeps draining and can't block the writer.
        guard let fronted = process, ObjectIdentifier(fronted) == procID else {
            if var entry = parked, ObjectIdentifier(entry.process) == procID {
                entry.buffer.append(BristlenoseShared.redactKeys(in: clean))
                if entry.buffer.count > 50 { entry.buffer.removeFirst(entry.buffer.count - 50) }
                parked = entry
            }
            return
        }

        // Parse auth token FIRST — before redaction. The token format is
        // base64url (secrets.token_urlsafe), extremely unlikely to match the
        // key shapes above, but we want the unredacted source regardless so
        // the parser's exact-prefix match is never interfered with.
        if authToken == nil, clean.hasPrefix("[bristlenose] auth-token: ") {
            let token = String(clean.dropFirst("[bristlenose] auth-token: ".count))
                .trimmingCharacters(in: .whitespaces)
            // Validate URL-safe characters only (safety invariant from secrets.token_urlsafe)
            if token.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil {
                authToken = token
                // .private redacts in Release unified logging; still visible
                // in Debug for local inspection.
                log.info("captured auth token (prefix=\(token.prefix(8), privacy: .private))")
            }
        }

        // Redact key-shaped substrings for everything published downstream:
        // outputLines (displayed, exposed in error messages, suffix used in
        // termination failure reporting).
        outputLines.append(BristlenoseShared.redactKeys(in: clean))

        // Detect readiness AND extract the port: bristlenose serve prints
        // "  Report: http://127.0.0.1:NNNN/report/" *after* the socket is
        // bound (when --port 0 is in use), so the port is guaranteed open
        // by the time we see this line. Poll briefly anyway as belt-and-
        // braces against any future ordering changes.
        guard case .starting = state else { return }
        let range = NSRange(clean.startIndex..., in: clean)
        guard let match = Self.reportPortRegex.firstMatch(in: clean, range: range),
              match.numberOfRanges >= 2,
              let portRange = Range(match.range(at: 1), in: clean),
              let parsedPort = Int(clean[portRange]) else {
            return
        }

        timeoutTask?.cancel()
        let readyGeneration = self.generation
        Task { [weak self] in
            await self?.waitForPort(parsedPort, timeout: 10)
            await MainActor.run {
                guard let self, self.generation == readyGeneration,
                      case .starting = self.state else { return }
                self.state = .running(port: parsedPort)
                Task { await self.fetchServerVersion(port: parsedPort) }
            }
        }
    }

    /// Poll until the port is accepting TCP connections, or timeout.
    private func waitForPort(_ port: Int, timeout: Int) async {
        for _ in 0..<(timeout * 10) {  // check every 100ms
            if Self.isPortOpen(port) {
                log.debug("port \(port, privacy: .public) is accepting connections")
                return
            }
            try? await Task.sleep(for: .milliseconds(100))
        }
        log.warning("port \(port, privacy: .public) poll timed out — proceeding anyway")
    }

    /// Quick TCP connect check to see if a port is accepting connections.
    private static func isPortOpen(_ port: Int) -> Bool {
        let sock = socket(AF_INET, SOCK_STREAM, 0)
        guard sock >= 0 else { return false }
        defer { close(sock) }

        var addr = sockaddr_in()
        addr.sin_family = sa_family_t(AF_INET)
        addr.sin_port = UInt16(port).bigEndian
        addr.sin_addr.s_addr = inet_addr("127.0.0.1")

        let result = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                Darwin.connect(sock, sockPtr, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        return result == 0
    }

    // Zombie cleanup + djb2 port allocation moved out of this file
    // (Apr 2026, A6 redesign). See `bristlenose/server/lifecycle.py` and
    // `desktop/CLAUDE.md` "Zombie process cleanup".
}
