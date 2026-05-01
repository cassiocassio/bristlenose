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

        let proc = Process()
        self.process = proc
        proc.executableURL = executableURL
        // --port 0 → sidecar binds via bind(0); we read the actual port
        // from the "Report:" stdout line in handleLine(_:).
        proc.arguments = Self.arguments(for: mode, projectPath: projectPath)

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
        // Tells the sidecar to install the parent-death watcher (so it
        // self-terminates if this host process dies abnormally, instead
        // of leaving an orphan holding a port). CLI users don't get this
        // — they may legitimately nohup the server.
        env["_BRISTLENOSE_HOSTED_BY_DESKTOP"] = "1"
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

        // Ollama — hardwired to localhost in the desktop GUI (security
        // boundary; see LLMSettingsView.hardwiredOllamaURL). CLI users
        // and CI override via the parent process env var.
        if let envURL = ProcessInfo.processInfo.environment["BRISTLENOSE_LOCAL_URL"],
           !envURL.isEmpty {
            env["BRISTLENOSE_LOCAL_URL"] = envURL
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

    /// Key-shape redactor — defence against Python-side leakage of LLM API keys
    /// (Uvicorn env dumps on startup errors, pydantic tracebacks that echo a
    /// SecretStr, accidental `print(os.environ)` from a future change).
    ///
    /// Covers: Anthropic (`sk-ant-api/sid<NN>-<90+ chars>`), OpenAI (project-scoped
    /// `sk-proj-<48+>` + historical `sk-<48>`), Google (`AIza<35>`).
    ///
    /// Limitations:
    /// - Per-line only. If Python wraps a key across two log lines (e.g. in a
    ///   boxed stack trace) the redactor won't catch the split halves. Inherent
    ///   to line-based processing.
    /// - Azure deliberately NOT covered: 32-char hex false-positives on UUIDs
    ///   and SHA hashes are worse than the residual risk. Pre-beta audit
    ///   tracked in `docs/private/100days.md` §6 Risk → Should.
    /// - Does not catch provider-format changes after this code was written.
    /// - Does not catch misformatted keys the regex doesn't match by shape.
    ///
    /// This is defence in depth, not a substitute for avoiding key logs in the
    /// first place — see `check-logging-hygiene.sh` for the source-level gate.
    static let keyRedactionRegex = try! NSRegularExpression(
        pattern: [
            "sk-ant-(api|sid)[0-9]{2}-[A-Za-z0-9_\\-]{90,}",
            "sk-(proj|None)-[A-Za-z0-9_\\-]{48,}",
            "sk-[A-Za-z0-9]{48}",
            "AIza[A-Za-z0-9_\\-]{35}",
        ].joined(separator: "|"),
        options: []
    )

    /// Apply the key-shape redactor to a string. Exposed for testing.
    static func redactKeys(in line: String) -> String {
        keyRedactionRegex.stringByReplacingMatches(
            in: line,
            range: NSRange(line.startIndex..., in: line),
            withTemplate: "***REDACTED***"
        )
    }

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
        outputLines.append(Self.redactKeys(in: clean))

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
