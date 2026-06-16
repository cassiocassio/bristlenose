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
    /// Incremented on each start() — termination handlers from previous
    /// runs check this to avoid overwriting the new run's state.
    private var generation: Int = 0

    /// Last project path passed to start() — used by restartIfRunning().
    private var currentProjectPath: String?

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

        let currentGeneration = generation

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

        // Read pipe on a detached task to avoid Sendable/actor-isolation issues.
        readTask = Task.detached { [weak self] in
            let fileHandle = handle
            while true {
                let data = fileHandle.availableData
                if data.isEmpty { break }  // EOF

                if let chunk = String(data: data, encoding: .utf8) {
                    let lines = chunk.components(separatedBy: "\n")
                    for line in lines where !line.isEmpty {
                        await self?.handleLine(line)
                    }
                }
            }
        }

        proc.terminationHandler = { [weak self] p in
            let status = p.terminationStatus
            Task { @MainActor in
                guard let self, self.generation == currentGeneration else { return }
                self.timeoutTask?.cancel()
                let lastLines = self.outputLines.suffix(5).joined(separator: "\n")
                if case .running = self.state {
                    self.state = .failed(error: "Server exited with code \(status)\n\(lastLines)")
                } else if case .starting = self.state {
                    self.state = .failed(error: "Server exited before becoming ready (code \(status))\n\(lastLines)")
                }
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

    /// Switch the loaded project. Tears down the current sidecar with signal
    /// escalation, starts a new one pointed at `path`, and resolves when the
    /// new sidecar reports ready (or fails).
    ///
    /// **Choreography:**
    /// 1. (caller) UI skeleton — sidebar selection updates immediately;
    ///    detail pane shows `BootView(phase: .startingSidecar)` while
    ///    `state == .starting`. This is the SwiftUI `.id(project.id)` reset
    ///    on `WebView`, which fully tears down the old WKWebView.
    /// 2. (here) Tear down current sidecar — `shutdown(timeout:)` above.
    /// 3. (caller) Resolve new bookmark + acquire `ProjectBookmarkLease` —
    ///    if it throws, mark project `cantFind` and don't call this.
    /// 4. (here) Spawn new sidecar via existing `start(projectPath:)`.
    /// 5. (automatic) WKWebView reload — when `selectedProject.id` changes,
    ///    SwiftUI rebuilds `WebView` with a fresh `WKWebsiteDataStore`
    ///    (`.nonPersistent()` returns a new partition every call). This
    ///    drops all `localStorage`, `sessionStorage`, cookies, and HTTP
    ///    cache from the previous project. No explicit `resetDataStore()`
    ///    call is required.
    ///
    /// **Cache leak defence:** the server adds `Cache-Control: no-store` to
    /// every `/api/projects/*` response (see `bristlenose/server/app.py`).
    /// Belt-and-braces against any cache layer between WKWebView and the
    /// sidecar that the data-store reset doesn't cover.
    ///
    /// - Parameter path: filesystem path to the project root.
    /// - Returns: when the new sidecar reaches `.running` or `.failed`.
    ///   Does NOT throw — callers inspect `state` (`@Published`) afterwards;
    ///   the `.failed` case flows through SwiftUI to `BootView(.failed)` in
    ///   `ContentView.detail`. No explicit caller-side error handling needed.
    ///
    /// **Security-scoped bookmark lifecycle.** `ProjectIndex.syncWatchers()`
    /// holds a `ProjectBookmarkLease` for every `.ready` project across the
    /// app's lifetime, so the sidecar inherits an already-open security
    /// scope on the project's folder for as long as it runs. No explicit
    /// lease handoff is needed here.
    func switchProject(to path: String) async {
        log.info("switching project — shutting down current sidecar")
        await shutdown(timeout: .seconds(2))
        // A newer switch may have superseded us while we awaited teardown. The
        // caller (applySelectionChange) cancels the prior switch Task before
        // spawning the next, so bail HERE — before start() — when cancelled.
        // Without this guard the superseded switch would still call start(),
        // whose defensive `if process != nil { stop() }` would SIGINT the
        // winning switch's freshly-spawned sidecar (the rapid-switch fail-open).
        // shutdown()'s `try? await Task.sleep` swallows CancellationError, so
        // the explicit Task.isCancelled check is what actually honours the cancel.
        guard !Task.isCancelled else {
            log.info("switchProject superseded — abandoning before start()")
            return
        }
        log.info("starting new sidecar")
        start(projectPath: path)
        // Wait for transition out of .starting (to .running or .failed) so
        // callers can await the switch completing. Bounded by start()'s own
        // 15s timeout — it transitions to .failed if the sidecar never prints
        // the Report line. Also bail if a newer switch cancels us mid-wait.
        let deadline = ContinuousClock.now.advanced(by: .seconds(20))
        while case .starting = state, !Task.isCancelled, ContinuousClock.now < deadline {
            try? await Task.sleep(for: .milliseconds(50))
        }
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

    private func handleLine(_ line: String) {
        let clean = Self.ansiRegex.stringByReplacingMatches(
            in: line,
            range: NSRange(line.startIndex..., in: line),
            withTemplate: ""
        )

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
