import Foundation

/// A bounded, non-writing check, separate from the server and its WebViews.
/// Output goes to a private temporary file so neither pipe backpressure nor
/// an inherited pipe can strand Retry. Only the first 8 KiB is ever decoded.
@MainActor
final class StudyStartupProbe {
    enum Result: Equatable { case admitted, refused(StudyStartupRefusal), unavailable }
    private let process = Process()
    private var deadline: Task<Void, Never>?
    private var timedOut = false
    private var output: FileHandle?
    private var outputURL: URL?
    private var completion: ((Result) -> Void)?

    func start(executable: URL, arguments: [String], environment: [String: String],
               timeout: Duration = .seconds(30), completion: @escaping (Result) -> Void) {
        self.completion = completion
        let url = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-startup-check-\(UUID().uuidString).log")
        outputURL = url
        guard FileManager.default.createFile(atPath: url.path, contents: nil,
                                             attributes: [.posixPermissions: 0o600]) else {
            finish(.unavailable)
            return
        }
        do {
            let handle = try FileHandle(forWritingTo: url)
            output = handle
            process.executableURL = executable
            process.arguments = arguments
            process.environment = environment
            process.standardOutput = handle
            process.standardError = handle
            process.standardInput = FileHandle.nullDevice
            process.terminationHandler = { [weak self] process in
                let outcome = ProcessOutcome(status: process.terminationStatus, reason: process.terminationReason)
                Task { @MainActor in self?.terminated(outcome) }
            }
            try process.run()
            deadline = Task { [weak self] in
                do { try await Task.sleep(for: timeout) } catch { return }
                guard let self, self.process.isRunning else { return }
                self.timedOut = true
                self.process.terminate()
                try? await Task.sleep(for: .milliseconds(500))
                if self.process.isRunning { kill(self.process.processIdentifier, SIGKILL) }
            }
        } catch { finish(.unavailable) }
    }

    private func terminated(_ outcome: ProcessOutcome) {
        guard !timedOut else { finish(.unavailable); return }
        switch outcome {
        case .exited(code: 0): finish(.admitted)
        case .exited(code: StudyStartupRefusal.exitCode):
            var facts: StudyStartupRefusal?
            if let url = outputURL, let handle = try? FileHandle(forReadingFrom: url) {
                defer { try? handle.close() }
                let bytes = (try? handle.read(upToCount: 8192)) ?? Data()
                var lines = ProcessOutputLines()
                for line in lines.append(bytes) + [lines.finish()].compactMap({ $0 }) {
                    if let parsed = StudyStartupRefusal.fromLine(line) { facts = parsed }
                }
            }
            finish(.refused(facts ?? .unverified))
        default: finish(.unavailable)
        }
    }

    private func finish(_ result: Result) {
        deadline?.cancel()
        deadline = nil
        try? output?.close()
        output = nil
        if let outputURL { try? FileManager.default.removeItem(at: outputURL) }
        outputURL = nil
        let callback = completion
        completion = nil
        callback?(result)
    }
}
