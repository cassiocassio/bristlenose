import os
import SwiftUI

/// App-level engine for the on-device model setup flow (flow B, model-first).
///
/// Hoisted out of the old `OllamaSetupSheet` (Beat 3): when the user clicks
/// "Use Ollama" on the consent sheet we set provider=local and call `start(tag:)`,
/// which opens the model picker. This object outlives the sheet (owned at app
/// level via `@StateObject` in `BristlenoseApp`, injected as an
/// `@EnvironmentObject`) so the setup survives the dismissal and surfaces
/// through the toolbar `OllamaDownloadPill`.
///
/// ## One observable bit
///
/// Bristlenose can observe exactly one thing — whether the local Ollama daemon
/// answers `GET http://127.0.0.1:11434/api/tags`. Everything the UI shows is
/// built honestly on that. `daemonSnapshot()` returns the reachability AND the
/// installed-model list in one round-trip (`nil` = unreachable). Animation is a
/// truth signal: a moving indicator means *Bristlenose is moving bytes*; while
/// we wait for the human to install/launch Ollama the pill shows a static
/// hourglass, never a spinner, and there is no give-up timer.
///
/// See `docs/design-ollama-setup.md` for the full spec.
@MainActor
final class OllamaDownloadModel: ObservableObject {

    enum Phase: Equatable {
        case idle
        case choosingModel        // step 1 — pick the model FIRST; needs no daemon
        case needsOllama          // step 2 — model chosen, daemon down → go get Ollama
        case waitingForOllama     // step 3 — polling; PASSIVE (human installing)
        case downloading          // daemon up; fetching the chosen model — BN working
        case finishing
        case failed(Failure)
    }

    /// Typed failure reasons, mapped to localized copy by the pill. Daemon
    /// absence is NOT a failure (it's a normal `needsOllama`/`waitingForOllama`
    /// state), so there is no `runtimeDidNotStart` case.
    enum Failure: Equatable {
        case noInternet
        case timedOut
        case cantReach
        case generic(String)
    }

    /// A model already on disk per `/api/tags` — `name` matches an Ollama tag.
    struct InstalledModel: Equatable {
        let name: String
        let sizeBytes: Int64
    }

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var completedBytes: Int64 = 0
    @Published private(set) var totalBytes: Int64 = 0
    /// The tag the user committed to — source of truth for the pill's model
    /// name, the download, and `retry()`.
    @Published private(set) var currentTag: String?
    /// Result of the most recent `daemonSnapshot()` taken while choosing:
    /// `nil` = daemon down (or not yet probed), `[…]` = installed models. Drives
    /// the picker's "Already on this Mac" grouping and foreshadow line.
    @Published private(set) var installedSnapshot: [InstalledModel]?
    /// One-shot token: the pill auto-presents the picker once when it first
    /// appears post-consent, then calls `consumeAutoPresent()`.
    @Published var pendingAutoPresent = false

    /// Whether the pill should be visible. The pill self-hides when idle.
    var isActive: Bool { phase != .idle }

    var downloadRatio: Double {
        guard totalBytes > 0 else { return 0 }
        return min(1, Double(completedBytes) / Double(totalBytes))
    }

    private static let logger = Logger(subsystem: "app.bristlenose", category: "ollama-download")
    /// Localhost only — the pull/probe endpoint is never a user-supplied or
    /// remote host (security finding 12). Asserted in `download`.
    private static let baseURL = URL(string: "http://127.0.0.1:11434")!
    private static let installPageURL = URL(string: "https://ollama.com/download")!
    private static let urlSession = URLSession(configuration: .ephemeral)

    private var task: Task<Void, Never>?

    #if DEBUG
    /// Rolling cursor for `debugCycleNext()`. DEBUG-only — see the harness
    /// extension at the bottom of this file.
    private var debugSceneIndex = 0
    #endif

    // MARK: - Lifecycle

    /// Entry point from `AIConsentView.activateLocalDefault()` (or a Settings
    /// re-entry). Always routes to the model picker first (model-first): the
    /// choice needs no daemon, so step 1 is universal. Probes the daemon in the
    /// background to annotate the picker (installed models / foreshadow).
    func start(tag: String) {
        task?.cancel()
        currentTag = tag
        completedBytes = 0
        totalBytes = 0
        installedSnapshot = nil
        phase = .choosingModel
        pendingAutoPresent = true
        task = Task { @MainActor in
            let snapshot = await self.daemonSnapshot()
            // Cancellation is cooperative: a re-entry (another start/confirm/
            // cancel) cancels this task, but the await still resolves. Without
            // this guard a stale snapshot would clobber @Published state after
            // the next flow has begun.
            guard !Task.isCancelled else { return }
            self.installedSnapshot = snapshot
        }
    }

    /// The pill calls this after auto-presenting the picker once.
    func consumeAutoPresent() {
        pendingAutoPresent = false
    }

    /// Step 1 → commit. Persists the (possibly changed) choice, then routes on a
    /// fresh daemon snapshot: down → `needsOllama`; up & present → active
    /// (no fetch); up & absent → `downloading`.
    func confirmModel(tag: String) {
        if tag != currentTag {
            currentTag = tag
            // Mirror the canonical prefs triad: per-provider model, global
            // model, notify so ServeManager injects the right model.
            UserDefaults.standard.set(tag, forKey: "llmModel_local")
            UserDefaults.standard.set(tag, forKey: "llmModel")
            NotificationCenter.default.post(name: .bristlenosePrefsChanged, object: nil)
        }
        task?.cancel()
        task = Task { @MainActor in await self.route(tag: tag) }
    }

    /// Step 2 → open ollama.com and begin the passive wait. Polling has no
    /// deadline; it ends only when the daemon appears or the user cancels.
    func getOllama() {
        NSWorkspace.shared.open(Self.installPageURL)
        phase = .waitingForOllama
        task?.cancel()
        task = Task { @MainActor in await self.pollThenDownload() }
    }

    func retry() {
        guard let tag = currentTag else { return }
        task?.cancel()
        task = Task { @MainActor in await self.download(tag: tag) }
    }

    /// Cancel whatever is in flight (snapshot probe / poll / pull) and hide the
    /// pill. Also the re-entrancy guard: every launcher cancels `task` first, so
    /// switching provider mid-flight can't leave two operations racing.
    func cancel() {
        task?.cancel()
        phase = .idle
    }

    // MARK: - Routing

    private func route(tag: String) async {
        let snapshot = await daemonSnapshot()
        // A cancel() during the probe must not let a late phase write reverse
        // the .idle the cancel installed (which would re-show the pill).
        guard !Task.isCancelled else { return }
        guard let snapshot else {
            phase = .needsOllama
            return
        }
        if snapshot.contains(where: { $0.name == tag }) {
            // Already on disk — instant active, no fetch. ServeManager already
            // restarted on the prefs notification; nothing left to show.
            phase = .idle
        } else {
            await download(tag: tag)
        }
    }

    private func pollThenDownload() async {
        guard let tag = currentTag else { return }
        while !Task.isCancelled {
            if let snapshot = await daemonSnapshot() {
                guard !Task.isCancelled else { return }
                if snapshot.contains(where: { $0.name == tag }) {
                    phase = .idle
                } else {
                    await download(tag: tag)
                }
                return
            }
            do {
                try await Task.sleep(for: .seconds(2))
            } catch {
                return  // cancelled
            }
        }
    }

    private func download(tag: String) async {
        // Localhost contract — fail loud in debug if this ever drifts.
        assert(Self.baseURL.host == "127.0.0.1", "Ollama pull must target localhost")
        completedBytes = 0
        totalBytes = 0
        phase = .downloading
        do {
            try await LLMValidator.pullModel(
                tag: tag, baseURL: Self.baseURL
            ) { [weak self] progress in
                guard let self else { return }
                self.completedBytes = progress.completedBytes
                self.totalBytes = progress.totalBytes
                // Bytes are in; the daemon is verifying the digest / writing the
                // manifest while the stream stays open. Honest spinner — work is
                // happening (we're reading the stream), it's just no longer
                // byte-moving, and it's not the human's turn.
                if Self.isFinalizing(progress.statusLine), self.phase != .finishing {
                    self.phase = .finishing
                }
            }
            Self.logger.info("Ollama model ready: \(tag, privacy: .public)")
            // Model on disk; serve restarted on the prefs notification — self-hide.
            phase = .idle
        } catch is CancellationError {
            phase = .idle
        } catch {
            Self.logger.error(
                "Ollama download failed: \(error.localizedDescription, privacy: .public)")
            phase = .failed(Self.classify(error))
        }
    }

    // MARK: - Signal

    /// `GET /api/tags` → reachability + installed-model list in one round-trip.
    /// `nil` = daemon unreachable; `[]` = up, no models; `[…]` = up, these
    /// models on disk. We cross-reference our curated catalogue only (§4).
    func daemonSnapshot() async -> [InstalledModel]? {
        var req = URLRequest(
            url: URL(string: "\(Self.baseURL.absoluteString)/api/tags")!)
        req.httpMethod = "GET"
        req.timeoutInterval = 2
        do {
            let (data, response) = try await Self.urlSession.data(for: req)
            guard let http = response as? HTTPURLResponse,
                  (200..<300).contains(http.statusCode) else { return nil }
            let decoded = try JSONDecoder().decode(TagsResponse.self, from: data)
            return decoded.models.map {
                InstalledModel(name: $0.name, sizeBytes: $0.size)
            }
        } catch {
            return nil
        }
    }

    private struct TagsResponse: Decodable {
        struct Entry: Decodable {
            let name: String
            let size: Int64
        }
        let models: [Entry]
    }

    /// Ollama's post-download stream stages — verifying the sha256 digest,
    /// writing the manifest, removing unused layers, success. Bytes are already
    /// in by this point, so these map to `.finishing`. Deliberately does NOT
    /// match the initial "pulling manifest" or the byte-moving "pulling <digest>"
    /// lines, which stay `.downloading`.
    nonisolated static func isFinalizing(_ statusLine: String) -> Bool {
        let s = statusLine.lowercased()
        return s.hasPrefix("verifying")
            || s.hasPrefix("writing")
            || s.hasPrefix("removing")
            || s == "success"
    }

    nonisolated static func classify(_ error: Error) -> Failure {
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

#if DEBUG
// MARK: - Debug state harness (never compiled into Release)
//
// Lets a developer render every pill/popover state live — including the four
// failure variants and both download sub-states — WITHOUT a real Ollama daemon
// or contrived network conditions. Two entry points:
//
//   1. `BRISTLENOSE_DEBUG_OLLAMA_PHASE=<scene>` in the run scheme → the pill
//      appears in that state at launch (no consent dance needed). Keep the
//      scheme row `isEnabled = "NO"` when committing (desktop CLAUDE.md gotcha).
//   2. Right-click the pill → "Force state (DEBUG)" → jump to any scene, or
//      "Cycle ▸ next" to walk the gallery without relaunching.
//
// Each scene cancels the real probe/pull task first, so the forced state is
// stable — nothing races in behind it.
extension OllamaDownloadModel {

    enum DebugScene: String, CaseIterable, Hashable {
        case choosing
        case needsOllama
        case waiting
        case downloadingDeterminate
        case downloadingIndeterminate
        case finishing
        case failNoInternet
        case failTimedOut
        case failCantReach
        case failGeneric

        var label: String {
            switch self {
            case .choosing: "Choosing model"
            case .needsOllama: "Needs Ollama"
            case .waiting: "Waiting for Ollama"
            case .downloadingDeterminate: "Downloading (33%)"
            case .downloadingIndeterminate: "Downloading (indeterminate)"
            case .finishing: "Finishing"
            case .failNoInternet: "Failed — no internet"
            case .failTimedOut: "Failed — timed out"
            case .failCantReach: "Failed — can't reach"
            case .failGeneric: "Failed — generic"
            }
        }

        /// Lenient parse for the env-var bootstrap — accepts the raw case name
        /// or a few friendly aliases.
        init?(envValue raw: String) {
            switch raw.lowercased() {
            case "choosing", "choosingmodel", "picker": self = .choosing
            case "needsollama", "needs": self = .needsOllama
            case "waiting", "waitingforollama": self = .waiting
            case "downloading", "downloadingdeterminate": self = .downloadingDeterminate
            case "downloadingindeterminate", "downloading-indeterminate": self = .downloadingIndeterminate
            case "finishing": self = .finishing
            case "failnointernet", "failed.nointernet", "nointernet": self = .failNoInternet
            case "failtimedout", "failed.timedout", "timedout": self = .failTimedOut
            case "failcantreach", "failed.cantreach", "cantreach": self = .failCantReach
            case "failgeneric", "failed.generic", "generic", "failed": self = .failGeneric
            default: return nil
            }
        }
    }

    /// Force the model into a scene, bypassing the daemon probe and pull.
    func debugApply(_ scene: DebugScene) {
        task?.cancel()
        if currentTag == nil {
            // A curated tag so popovers humanise the name (e.g. "Gemma 4 E4B")
            // rather than showing an empty model slot.
            currentTag = OllamaCatalog.tagForRAM(OllamaCatalog.systemRAMGB)
        }
        switch scene {
        case .choosing:
            installedSnapshot = nil        // foreshadow visible, no grouping
            phase = .choosingModel
        case .needsOllama:
            phase = .needsOllama
        case .waiting:
            phase = .waitingForOllama
        case .downloadingDeterminate:
            totalBytes = 412_000_000
            completedBytes = 137_000_000
            phase = .downloading
        case .downloadingIndeterminate:
            totalBytes = 0
            completedBytes = 0
            phase = .downloading
        case .finishing:
            totalBytes = 412_000_000
            completedBytes = 412_000_000
            phase = .finishing
        case .failNoInternet: phase = .failed(.noInternet)
        case .failTimedOut: phase = .failed(.timedOut)
        case .failCantReach: phase = .failed(.cantReach)
        case .failGeneric: phase = .failed(.generic("Ollama exited (exit code 1)"))
        }
    }

    /// Advance to the next scene in the gallery (wraps). Drives the pill's
    /// "Cycle ▸ next" menu item.
    func debugCycleNext() {
        let all = DebugScene.allCases
        debugSceneIndex = (debugSceneIndex + 1) % all.count
        debugApply(all[debugSceneIndex])
    }

    /// Called once at app launch: if `BRISTLENOSE_DEBUG_OLLAMA_PHASE` is set,
    /// open the pill in that scene. No-op when the env var is absent.
    func debugBootstrapFromEnv() {
        guard let raw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEBUG_OLLAMA_PHASE"],
              !raw.isEmpty, let scene = DebugScene(envValue: raw) else { return }
        debugApply(scene)
    }
}
#endif
