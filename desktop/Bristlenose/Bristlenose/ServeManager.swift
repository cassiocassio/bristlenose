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

    @Published var state: ServeState = .idle
    @Published var outputLines: [String] = []

    /// Bristlenose version from `/api/health` — fetched after server starts.
    /// Shown in the About panel alongside the Xcode build number.
    @Published var serverVersion: String?

    /// Bearer token for localhost API access control.
    /// Parsed from stdout line: `[bristlenose] auth-token: <token>`
    /// Injected into WKWebView via WKUserScript.
    @Published var authToken: String?

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

        prefsObserver = NotificationCenter.default.addObserver(
            forName: .bristlenosePrefsChanged,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.restartIfRunning()
            }
        }
    }

    /// The URL to load in WKWebView when serve is running.
    var serveURL: URL? {
        guard case .running(let port) = state else { return nil }
        return URL(string: "http://127.0.0.1:\(port)/report/")
    }

    private var process: Process?
    private var readTask: Task<Void, Never>?
    private var timeoutTask: Task<Void, Never>?
    /// Incremented on each start() AND on each warm re-point — late completions
    /// (a superseded readiness wait) check this before writing terminal state.
    private var generation: Int = 0

    /// Last project path passed to start() — used by restartIfRunning() and the
    /// DEBUG menu's reveal/log/provenance actions (the served project is the one
    /// whose report is on screen). Read-only outside ServeManager.
    private(set) var currentProjectPath: String?

    /// The most-recently-fronted project's sidecar, kept warm so switching
    /// back is an instant hand-off (Phase A2 warm-sidecar pool, single-slot).
    /// At most one. See `ParkedSidecar.swift` for the design + why one slot.
    private var parked: ParkedSidecar?

    /// Observer for preference changes that require a serve restart.
    private var prefsObserver: Any?

    /// Start serving a project. Callers must call `stop()` or
    /// `shutdown(timeout:)` first if a sidecar is already running — `start()`
    /// only forwards to `stop()` defensively when a `process` reference
    /// lingers. Direct callers without a prior sidecar (cold launch,
    /// post-Locate resume, post-failure retry) skip the teardown entirely.
    /// `switchProject(to:)` is the orchestrator for the prior-running case.
    ///
    /// - Parameter projectPath: Absolute path to the project directory.
    func start(projectPath: String) {
        if process != nil {
            stop()
        }

        guard let mode = self.mode else {
            // Resolution failed at init; state is already .failed.
            return
        }

        currentProjectPath = projectPath
        generation += 1
        state = .starting
        outputLines = []

        // External mode: no subprocess. Just point at the existing server.
        if case .external(let port) = mode {
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
        proc.environment = BristlenoseShared.childEnvironment(for: mode)

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
        if case .running(let port) = state, let proc = process, let path = currentProjectPath {
            let entry = ParkedSidecar(
                projectPath: path, port: port, authToken: authToken,
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

    /// Fetch the Bristlenose version from the serve health endpoint.
    /// Non-critical — if it fails, `serverVersion` stays nil.
    private func fetchServerVersion(port: Int) async {
        guard let url = URL(string: "http://127.0.0.1:\(port)/api/health") else { return }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let version = json["version"] as? String {
                self.serverVersion = version
            }
        } catch {
            // Non-critical — About panel shows build number only
        }
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
