import Foundation

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
/// Port allocation: `8150 + abs(projectPath.hashValue) % 1000` — deterministic
/// per project path, range 8150–9149.
@MainActor
final class ServeManager: ObservableObject {

    @Published var state: ServeState = .idle
    @Published var outputLines: [String] = []

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

    /// Start serving a project. Stops any existing serve process first.
    ///
    /// - Parameter projectPath: Absolute path to the project directory.
    func start(projectPath: String) {
        stop()

        generation += 1
        let currentGeneration = generation
        state = .starting
        outputLines = []

        let basePort = Self.stablePort(for: projectPath)
        // Find a free port starting from the stable base port.
        var port = basePort
        for offset in 0..<10 {
            port = basePort + offset
            if !Self.isPortOpen(port) { break }
            print("[ServeManager] port \(port) already in use, trying next")
        }

        guard let executableURL = findBristlenoseBinary() else {
            state = .failed(error: "Could not find bristlenose binary")
            return
        }

        let proc = Process()
        self.process = proc
        proc.executableURL = executableURL
        proc.arguments = ["serve", "--no-open", "--port", "\(port)", projectPath]

        // Inherit current environment (picks up API keys, PATH, etc.)
        proc.environment = ProcessInfo.processInfo.environment

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        let handle = pipe.fileHandleForReading

        // Read pipe on a detached task to avoid Sendable/actor-isolation issues.
        // Pattern from v0.1 ProcessRunner.swift — availableData blocks until
        // data arrives or EOF, breaking the loop on process termination.
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
                // Include last few output lines in error for debugging.
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

        // Timeout: if the server doesn't become ready within 15 seconds, fail.
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

    /// Stop the serve process and reset state.
    func stop() {
        timeoutTask?.cancel()
        timeoutTask = nil

        if let proc = process, proc.isRunning {
            proc.interrupt()  // SIGINT — lets Uvicorn shut down gracefully
        }
        readTask?.cancel()
        readTask = nil
        process = nil
        state = .idle
    }

    // MARK: - Private

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

        // Detect readiness: bristlenose serve prints "Report: http://..."
        // when the server is ready and the report has been rendered.
        // However, the HTTP port may not be accepting connections yet —
        // poll until it is before transitioning to .running.
        if case .starting = state, clean.contains("Report:") && clean.contains("http://") {
            timeoutTask?.cancel()
            Task {
                await self.waitForPort(port, timeout: 10)
                self.state = .running(port: port)
            }
        }
    }

    /// Poll until the port is accepting TCP connections, or timeout.
    private func waitForPort(_ port: Int, timeout: Int) async {
        for _ in 0..<(timeout * 10) {  // check every 100ms
            if Self.isPortOpen(port) {
                print("[ServeManager] port \(port) is accepting connections")
                return
            }
            try? await Task.sleep(for: .milliseconds(100))
        }
        print("[ServeManager] port \(port) poll timed out — proceeding anyway")
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

    /// Find the bristlenose binary for development use.
    /// Checks common locations in priority order.
    private func findBristlenoseBinary() -> URL? {
        let candidates = [
            // Worktree venv (when running from the macos-app worktree)
            NSString("~/Code/bristlenose_branch macos-app/.venv/bin/bristlenose")
                .expandingTildeInPath,
            // Main repo venv
            NSString("~/Code/bristlenose/.venv/bin/bristlenose").expandingTildeInPath,
            // Homebrew
            "/opt/homebrew/bin/bristlenose",
            "/usr/local/bin/bristlenose",
            // pipx / user install
            NSString("~/.local/bin/bristlenose").expandingTildeInPath,
        ]

        for path in candidates {
            let url = URL(fileURLWithPath: path)
            if FileManager.default.isExecutableFile(atPath: url.path) {
                return url
            }
        }
        return nil
    }
}
