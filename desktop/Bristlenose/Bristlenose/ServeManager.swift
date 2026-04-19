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
/// for the "Uvicorn running on" readiness signal, and exposes the serve URL
/// as a published property for the WKWebView to load.
///
/// Sidecar resolution happens once at `init()` via `SidecarMode.resolve`:
/// the resolved `mode` is stored and every downstream call site switches on
/// it. See `SidecarMode.swift` for the three modes + the Debug-only dev
/// env vars, and `desktop/CLAUDE.md` "Dev workflow" for the scheme table.
///
/// Port allocation: `8150 + djb2(projectPath) % 1000` — deterministic
/// per project path, range 8150–9149.
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

    /// On init, resolve the sidecar mode and kill any orphaned serve
    /// processes from previous app crashes. Bristlenose owns the 8150–9149
    /// port range — anything there is a zombie unless we're in
    /// external-server mode (the dev terminal server is intentional).
    init() {
        // The env-var string literals for the dev escape hatch live only
        // inside `#if DEBUG`-guarded code so the Release Mach-O has no
        // reference to them. `desktop/scripts/check-release-binary.sh`
        // verifies this at archive time.
        #if DEBUG
        let externalPortRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_EXTERNAL_PORT"]
        let sidecarPathRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_SIDECAR_PATH"]
        let userIntendedExternal = externalPortRaw != nil
        #else
        let externalPortRaw: String? = nil
        let sidecarPathRaw: String? = nil
        let userIntendedExternal = false
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

        // Skip the 8150–9149 kill-sweep when the user pointed us at an
        // externally-running server — we don't own that process. Also skip
        // when resolution failed but the user *intended* external mode
        // (e.g. invalid port value); killing what they were trying to
        // reach would compound the error.
        //
        // Asymmetric on purpose: dev-sidecar mode spawns a subprocess on
        // 8150–9149 that *we* own, so any zombie there is still our
        // responsibility to reap even if a later resolve failed.
        let skipCleanup: Bool
        switch self.mode {
        case .external: skipCleanup = true
        case .bundled, .devSidecar: skipCleanup = false
        case .none: skipCleanup = userIntendedExternal
        }
        if !skipCleanup {
            Self.killOrphanedServeProcesses()
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

    /// Start serving a project. Stops any existing serve process first.
    ///
    /// - Parameter projectPath: Absolute path to the project directory.
    func start(projectPath: String) {
        stop()

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

        let basePort = Self.stablePort(for: projectPath)
        var port = basePort
        for offset in 0..<10 {
            port = basePort + offset
            if !Self.isPortOpen(port) { break }
            log.debug("port \(port, privacy: .public) already in use, trying next")
        }

        let proc = Process()
        self.process = proc
        proc.executableURL = executableURL
        proc.arguments = Self.arguments(for: mode, port: port, projectPath: projectPath)

        // Minimal environment — only what the sidecar needs. Avoids leaking
        // DYLD_* vars, Xcode debug vars, etc. to the subprocess.
        // API keys are fetched from Keychain in Swift (host process) and
        // injected as BRISTLENOSE_*_API_KEY env vars — Python never touches
        // Keychain directly, so it works under App Sandbox without any
        // Security.framework dep on the Python side.
        var env: [String: String] = [:]
        let parentEnv = ProcessInfo.processInfo.environment
        for key in ["PATH", "HOME", "TMPDIR", "USER", "SHELL",
                     "LANG", "LC_ALL", "LC_CTYPE", "VIRTUAL_ENV"] {
            if let val = parentEnv[key] { env[key] = val }
        }
        Self.overlayPreferences(into: &env)
        Self.overlayAPIKeys(into: &env, using: KeychainHelper.liveStore)
        proc.environment = env

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
                        await self?.handleLine(line, port: port)
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
    private static func arguments(for mode: SidecarMode, port: Int, projectPath: String) -> [String] {
        let flags = ["--no-open", "--port", "\(port)", projectPath]
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
    func restartIfRunning() {
        guard case .running = state, let path = currentProjectPath else { return }
        log.info("preferences changed — restarting serve")
        start(projectPath: path)
    }

    /// Overlay UserDefaults preferences as environment variables for the
    /// `bristlenose serve` subprocess. Only sets vars that differ from defaults
    /// to avoid overriding `.env` file or Keychain values unnecessarily.
    private static func overlayPreferences(into env: inout [String: String]) {
        let defaults = UserDefaults.standard

        // LLM provider & model
        if let provider = defaults.string(forKey: "activeProvider") {
            env["BRISTLENOSE_LLM_PROVIDER"] = provider
        }
        if let model = defaults.string(forKey: "llmModel") {
            env["BRISTLENOSE_LLM_MODEL"] = model
        }

        // Temperature & concurrency (only if user has explicitly set them)
        if defaults.object(forKey: "llmTemperature") != nil {
            env["BRISTLENOSE_LLM_TEMPERATURE"] = String(defaults.double(forKey: "llmTemperature"))
        }
        if defaults.object(forKey: "llmConcurrency") != nil {
            env["BRISTLENOSE_LLM_CONCURRENCY"] = String(Int(defaults.double(forKey: "llmConcurrency")))
        }

        // Whisper transcription
        if let backend = defaults.string(forKey: "whisperBackend"), backend != "auto" {
            env["BRISTLENOSE_WHISPER_BACKEND"] = backend
        }
        if let model = defaults.string(forKey: "whisperModel") {
            env["BRISTLENOSE_WHISPER_MODEL"] = model
        }

        // Language
        if let lang = defaults.string(forKey: "language"), lang != "en" {
            env["BRISTLENOSE_WHISPER_LANGUAGE"] = lang
        }

        // Azure-specific
        if let endpoint = defaults.string(forKey: "azureEndpoint"), !endpoint.isEmpty {
            env["BRISTLENOSE_AZURE_ENDPOINT"] = endpoint
        }
        if let deployment = defaults.string(forKey: "azureDeployment"), !deployment.isEmpty {
            env["BRISTLENOSE_AZURE_DEPLOYMENT"] = deployment
        }
        if let apiVersion = defaults.string(forKey: "azureAPIVersion"), !apiVersion.isEmpty {
            env["BRISTLENOSE_AZURE_API_VERSION"] = apiVersion
        }

        // Ollama
        if let localURL = defaults.string(forKey: "localURL"), !localURL.isEmpty {
            env["BRISTLENOSE_LOCAL_URL"] = localURL
        }
    }

    /// Fetch LLM API keys from Keychain and overlay them as `BRISTLENOSE_<PROVIDER>_API_KEY`
    /// env vars on the subprocess environment dict.
    ///
    /// This is the sandbox-compatible credential path: the Swift host reads Keychain
    /// (Security.framework, no Python dep), the sidecar reads env vars via
    /// pydantic-settings. No `/usr/bin/security` subprocess call needed by Python,
    /// so the sidecar works under App Sandbox without `keychain-access-groups`
    /// or any Security.framework linkage on the Python side.
    ///
    /// Residual risk: env vars are visible to same-UID processes via `ps -E`.
    /// Under that threat model the attacker can also call SecItemCopyMatching
    /// directly, so net attack-surface delta is small. Documented in
    /// `docs/design-desktop-python-runtime.md`.
    ///
    /// - Parameter env: env dict to mutate
    /// - Parameter store: Keychain-abstracted store (`KeychainHelper.liveStore` in
    ///   production, `InMemoryKeychain` in tests)
    static func overlayAPIKeys(into env: inout [String: String], using store: any KeychainStore) {
        // Iterate LLM providers only. Miro descoped from alpha (see c3 plan).
        let providers = ["anthropic", "openai", "azure", "google"]
        for provider in providers {
            guard let value = store.get(provider: provider), !value.isEmpty else {
                continue
            }
            let envKey = "BRISTLENOSE_\(provider.uppercased())_API_KEY"
            env[envKey] = value
            log.info("injected API key for provider=\(provider, privacy: .public)")
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

    private func handleLine(_ line: String, port: Int) {
        let clean = Self.ansiRegex.stringByReplacingMatches(
            in: line,
            range: NSRange(line.startIndex..., in: line),
            withTemplate: ""
        )
        outputLines.append(clean)

        // Parse auth token — printed before "Report:" readiness line.
        // Format: [bristlenose] auth-token: <token>
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

        // Detect readiness: bristlenose serve prints "Report: http://..."
        // when the server is ready and the report has been rendered.
        // However, the HTTP port may not be accepting connections yet —
        // poll until it is before transitioning to .running.
        if case .starting = state, clean.contains("Report:") && clean.contains("http://") {
            timeoutTask?.cancel()
            // Belt-and-braces: the state check alone catches most stop/start
            // races, but a rapid stop() + start() between "Report:" arrival
            // and port-poll completion could have state back at .starting
            // for the *next* run. The generation guard distinguishes them.
            let readyGeneration = self.generation
            Task { [weak self] in
                await self?.waitForPort(port, timeout: 10)
                await MainActor.run {
                    guard let self, self.generation == readyGeneration,
                          case .starting = self.state else { return }
                    self.state = .running(port: port)
                    Task { await self.fetchServerVersion(port: port) }
                }
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

    /// Stable port derived from project path. Uses a simple djb2-style hash
    /// so the same path always maps to the same port across app launches.
    /// (Swift's `String.hashValue` is randomized per process since Swift 4.2.)
    static func stablePort(for path: String) -> Int {
        var hash: UInt64 = 5381
        for byte in path.utf8 {
            hash = hash &* 33 &+ UInt64(byte)
        }
        return 8150 + Int(hash % 1000)
    }

    /// Kill orphaned `bristlenose serve` processes left behind by previous
    /// app crashes (SIGKILL from Xcode stop button, force-quit, etc.).
    ///
    /// Uses `lsof` to find PIDs listening on the Bristlenose port range
    /// (8150–9149), then sends SIGINT for graceful Uvicorn shutdown.
    /// Runs synchronously but fast (~10ms) — safe to call from init().
    private nonisolated static func killOrphanedServeProcesses() {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        // Also scan :5173 — Vite dev server spawned by `bristlenose serve --dev`.
        // Survives SIGKILL because atexit cleanup doesn't fire.
        proc.arguments = ["-ti", ":5173,8150-9149"]

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = FileHandle.nullDevice

        do {
            try proc.run()
            proc.waitUntilExit()
        } catch {
            return  // lsof not available — nothing we can do
        }

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let output = String(data: data, encoding: .utf8) else { return }

        let pids = output
            .components(separatedBy: "\n")
            .compactMap { Int32($0.trimmingCharacters(in: .whitespaces)) }

        for pid in pids {
            log.info("killing orphaned serve process (PID \(pid, privacy: .public))")
            kill(pid, SIGINT)
        }
    }
}
