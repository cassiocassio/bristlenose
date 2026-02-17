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
        var buffer = Data()

        handle.readabilityHandler = { [weak self] fh in
            let data = fh.availableData
            if data.isEmpty {
                // EOF — flush remaining buffer
                handle.readabilityHandler = nil
                if !buffer.isEmpty, let line = String(data: buffer, encoding: .utf8) {
                    let trimmed = line
                    Task { @MainActor in
                        self?.appendLine(trimmed)
                    }
                }
                return
            }

            buffer.append(data)

            // Split on newlines
            while let range = buffer.range(of: Data("\n".utf8)) {
                let lineData = buffer.subdata(in: buffer.startIndex..<range.lowerBound)
                buffer.removeSubrange(buffer.startIndex..<range.upperBound)

                if let line = String(data: lineData, encoding: .utf8) {
                    let captured = line
                    Task { @MainActor in
                        self?.appendLine(captured)
                    }
                }
            }
        }

        proc.terminationHandler = { [weak self] p in
            Task { @MainActor in
                self?.isRunning = false
                self?.exitCode = p.terminationStatus
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
        outputLines.append(line)

        // The pipeline prints the report path as a file:// URL on the last
        // meaningful line. Capture it so the "View Report" button can use it.
        if line.contains("file://") {
            // Extract the file path from the URL
            if let range = line.range(of: "file://") {
                let urlString = String(line[range.lowerBound...]).trimmingCharacters(
                    in: .whitespaces)
                if let url = URL(string: urlString) {
                    reportPath = url.path
                }
            }
        }
    }
}
