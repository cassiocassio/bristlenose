import os
import SwiftUI

/// App-level engine for the ambient local-model pull.
///
/// Hoisted out of the old `OllamaSetupSheet` (Beat 3): when the user clicks
/// "Use Ollama" on the consent sheet we apply the RAM-aware default model,
/// dismiss the sheet immediately, and pull the model in the background. This
/// object outlives the sheet (owned at app level via `@StateObject` in
/// `BristlenoseApp`, injected as an `@EnvironmentObject`) so the download
/// survives the dismissal and surfaces through the toolbar `OllamaDownloadPill`.
///
/// View-agnostic: it publishes a `Phase` + byte counts; the pill resolves all
/// user-facing strings via i18n at render time. Failure is carried as a typed
/// `Failure` so the pill can localise it (and distinguish runtime-install
/// failures from model-pull failures).
@MainActor
final class OllamaDownloadModel: ObservableObject {

    enum Phase: Equatable {
        case idle
        case installing
        case starting
        case downloading
        case finishing
        case failed(Failure)
    }

    /// Typed failure reasons, mapped to localized copy by the pill.
    enum Failure: Equatable {
        case runtimeDidNotStart
        case noInternet
        case timedOut
        case cantReach
        case generic(String)
    }

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var completedBytes: Int64 = 0
    @Published private(set) var totalBytes: Int64 = 0
    /// The tag currently being pulled — source of truth for the pill's model
    /// name and for `retry()`.
    @Published private(set) var currentTag: String?

    /// Whether the pill should be visible. The pill self-hides when idle.
    var isActive: Bool { phase != .idle }

    var downloadRatio: Double {
        guard totalBytes > 0 else { return 0 }
        return min(1, Double(completedBytes) / Double(totalBytes))
    }

    private static let logger = Logger(subsystem: "app.bristlenose", category: "ollama-download")
    /// Localhost only — the pull endpoint is never a user-supplied or remote
    /// host (security finding 12). Asserted in `run`.
    private static let baseURL = URL(string: "http://127.0.0.1:11434")!
    private static let urlSession = URLSession(configuration: .ephemeral)

    private var task: Task<Void, Never>?

    /// Internal marker so `classify` can map the daemon-timeout to the right
    /// failure copy without string-matching an NSError.
    private struct DaemonTimeout: Error {}

    // MARK: - Lifecycle

    func start(tag: String) {
        task?.cancel()
        currentTag = tag
        completedBytes = 0
        totalBytes = 0
        let work = Task { @MainActor in await self.run(tag: tag) }
        task = work
    }

    func retry() {
        guard let tag = currentTag else { return }
        start(tag: tag)
    }

    /// Cancel an in-flight pull and hide the pill. Also the guard for
    /// re-entrancy: `start` cancels any prior task before launching a new one,
    /// so switching provider mid-pull can't leave two pulls racing.
    func cancel() {
        task?.cancel()
        phase = .idle
    }

    // MARK: - Work

    private func run(tag: String) async {
        // Localhost contract — fail loud in debug if this ever drifts.
        assert(Self.baseURL.host == "127.0.0.1", "Ollama pull must target localhost")
        do {
            // Reachability first: if the daemon answers we don't care how it
            // got there (Homebrew, .app bundle, user-launched). Skip install.
            let alreadyReachable = await isDaemonReachable()
            if !alreadyReachable {
                phase = .installing
                Self.logger.info("Daemon unreachable; opening installer page")
                NSWorkspace.shared.open(URL(string: "https://ollama.com/download")!)
                phase = .starting
                try await waitForDaemon(timeout: 120)
            }

            phase = .downloading
            try await LLMValidator.pullModel(
                tag: tag, baseURL: Self.baseURL
            ) { [weak self] progress in
                self?.completedBytes = progress.completedBytes
                self?.totalBytes = progress.totalBytes
            }

            phase = .finishing
            Self.logger.info("Ollama model ready: \(tag, privacy: .public)")
            // ServeManager already restarted on the prefs notification posted
            // when the user clicked "Use Ollama"; the model is now on disk, so
            // there's nothing left to show — self-hide.
            phase = .idle
        } catch is CancellationError {
            phase = .idle
        } catch {
            Self.logger.error(
                "Ollama download failed: \(error.localizedDescription, privacy: .public)")
            phase = .failed(classify(error))
        }
    }

    private func waitForDaemon(timeout: TimeInterval) async throws {
        let deadline = Date().addingTimeInterval(timeout)
        while true {
            try Task.checkCancellation()
            if await isDaemonReachable() { return }
            if Date() > deadline { throw DaemonTimeout() }
            try await Task.sleep(for: .seconds(1))
        }
    }

    private func isDaemonReachable() async -> Bool {
        var req = URLRequest(
            url: URL(string: "\(Self.baseURL.absoluteString)/api/tags")!)
        req.httpMethod = "GET"
        req.timeoutInterval = 2
        do {
            let (_, response) = try await Self.urlSession.data(for: req)
            if let http = response as? HTTPURLResponse,
               (200..<300).contains(http.statusCode) {
                return true
            }
            return false
        } catch {
            return false
        }
    }

    private func classify(_ error: Error) -> Failure {
        if error is DaemonTimeout { return .runtimeDidNotStart }
        if let urlErr = error as? URLError {
            switch urlErr.code {
            case .notConnectedToInternet, .networkConnectionLost, .dataNotAllowed:
                return .noInternet
            case .timedOut:
                return .timedOut
            case .cannotConnectToHost, .cannotFindHost:
                return .cantReach
            default:
                break
            }
        }
        return .generic(error.localizedDescription)
    }
}
