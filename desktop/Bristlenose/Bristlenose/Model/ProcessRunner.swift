import Foundation

/// Spawns a bundled CLI binary and streams stdout line-by-line to the UI.
@MainActor
class ProcessRunner: ObservableObject {
    @Published var outputLines: [String] = []
    @Published var isRunning = false
    @Published var exitCode: Int32?

    /// The report file path, extracted from the last stdout line if it
    /// contains a `file://` URL.
    @Published var reportPath: String?

    private var process: Process?

    /// Launch a bundled executable with the given arguments and environment.
    func run(
        executableURL: URL,
        arguments: [String],
        environment: [String: String] = [:]
    ) {
        isRunning = true
        outputLines = []
        exitCode = nil
        reportPath = nil

        let proc = Process()
        self.process = proc
        proc.executableURL = executableURL
        proc.arguments = arguments

        // Inherit the current environment, then layer our overrides
        // (e.g. ANTHROPIC_API_KEY for the bundled fallback key).
        var env = ProcessInfo.processInfo.environment
        for (key, value) in environment {
            env[key] = value
        }
        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        let handle = pipe.fileHandleForReading

        // Use a dedicated Task to read from the pipe on a background thread,
        // then dispatch lines back to MainActor. This avoids the
        // readabilityHandler Sendable/actor-isolation issues in Swift 6.
        let readTask = Task.detached { [weak self] in
            let fileHandle = handle
            while true {
                let data = fileHandle.availableData
                if data.isEmpty { break }  // EOF

                if let chunk = String(data: data, encoding: .utf8) {
                    let lines = chunk.components(separatedBy: "\n")
                    for line in lines where !line.isEmpty {
                        await self?.appendLine(line)
                    }
                }
            }
        }
        _ = readTask  // suppress unused variable warning

        proc.terminationHandler = { [weak self] p in
            let status = p.terminationStatus
            Task { @MainActor in
                self?.isRunning = false
                self?.exitCode = status
            }
        }

        do {
            try proc.run()
        } catch {
            outputLines.append("Failed to launch: \(error.localizedDescription)")
            isRunning = false
        }
    }

    func cancel() {
        process?.terminate()
    }

    // MARK: - Private

    private func appendLine(_ line: String) {
        // Strip ANSI escape sequences for display
        let cleanLine = line.replacingOccurrences(
            of: "\\e\\[[0-9;]*m|\\e\\]8;;[^\\e]*\\e\\\\",
            with: "",
            options: .regularExpression
        )
        outputLines.append(cleanLine)

        // Extract report path. The CLI embeds a file:// URL inside an OSC 8
        // ANSI hyperlink: \e]8;;file:///path\e\\visible text\e]8;;\e\\
        // Match the file:// URL from the raw (unstripped) line.
        if line.contains("file://") {
            if let range = line.range(of: "file:///[^\\x1b\\x07]+",
                                      options: .regularExpression) {
                let urlString = String(line[range])
                if let url = URL(string: urlString) {
                    reportPath = url.path
                }
            }
        }

        // Fallback: match "Report:  filename.html" and build path from it.
        // The render command prints just the filename without a file:// link.
        if reportPath == nil, cleanLine.contains("Report:") {
            let parts = cleanLine.components(separatedBy: "Report:")
            if let filename = parts.last?.trimmingCharacters(in: .whitespaces),
               filename.hasSuffix(".html"),
               let args = process?.arguments,
               let folderArg = args.last {
                let folder = URL(fileURLWithPath: folderArg)
                let candidate = folder
                    .appendingPathComponent("bristlenose-output")
                    .appendingPathComponent(filename)
                if FileManager.default.fileExists(atPath: candidate.path) {
                    reportPath = candidate.path
                }
            }
        }
    }
}
