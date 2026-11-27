import os
import SwiftUI

/// App-level engine for the on-device model setup flow (flow B, model-first).
///
/// Started from Settings ▸ LLM Provider ▸ Ollama (owner, 27 Nov 2026; until then
/// from the AI disclosure's "Use Ollama" button, now gone): the Model row's
/// button calls `start(tag:)` and opens the model picker in a popover; "Use …"
/// calls `useModel(tag:)`, which switches the provider to Ollama and then routes.
/// The stages show in Settings' Model card; with Settings closed, the toolbar
/// `OllamaDownloadPill` shows a download and a failure only (`isPillVisible`,
/// Whisper's rule). One instance, `shared`, read by both, as
/// `WhisperDownloadModel.shared` is by its Settings row and its pill.
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

    /// The one instance: the app, Settings and the pill all read this.
    static let shared = OllamaDownloadModel()

    /// Where the provider and model choice are written, and where the prefs
    /// change is posted. Injectable, so a test neither writes the app's
    /// preferences nor posts into another test's count.
    let defaults: UserDefaults
    let notifications: NotificationCenter

    init(defaults: UserDefaults = .standard, notifications: NotificationCenter = .default) {
        self.defaults = defaults
        self.notifications = notifications
    }

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

    /// The stage to put back if the picker closes without a choice (`start`).
    private var resume: (phase: Phase, tag: String?) = (.idle, nil)
    /// Whether "Use …" was pressed since the picker opened.
    private var committed = false

    /// Whether a setup is under way (anything but idle).
    var isActive: Bool { phase != .idle }

    /// Whether the toolbar pill shows: only while the download runs (bytes
    /// moving, or Ollama writing the model) and after a failure, until Retry.
    /// Gone once the model is on the Mac or after Cancel. Choosing, getting
    /// Ollama and waiting for it live in Settings. Whisper's rule
    /// (`WhisperDownloadModel.isPillVisible`), owner's decision 27 Nov 2026.
    var isPillVisible: Bool { Self.isPillVisible(phase) }

    nonisolated static func isPillVisible(_ phase: Phase) -> Bool {
        switch phase {
        case .downloading, .finishing, .failed: return true
        case .idle, .choosingModel, .needsOllama, .waitingForOllama: return false
        }
    }

    /// The stage alone, for Settings' height signature: one refit per change of
    /// stage, never per byte of progress (`LLMSettingsView.heightSignature`).
    nonisolated static func stage(_ phase: Phase) -> String {
        switch phase {
        case .idle: return "idle"
        case .choosingModel: return "choosing"
        case .needsOllama: return "needs"
        case .waitingForOllama: return "waiting"
        case .downloading: return "downloading"
        case .finishing: return "finishing"
        case .failed: return "failed"
        }
    }

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

    /// Opening the picker (the Model row's button in Settings). Model-first: the
    /// choice needs no daemon, so step 1 is universal. Probes the daemon in the
    /// background to annotate the picker (installed models / foreshadow). Writes
    /// nothing: the provider switch happens on "Use …" (`useModel(tag:)`).
    func start(tag: String) {
        // A stage with no task of its own (needs Ollama, failed) comes back if the
        // picker closes without a choice; anything else goes back to idle.
        switch phase {
        case .needsOllama, .failed: resume = (phase, currentTag)
        default: resume = (.idle, nil)
        }
        committed = false
        task?.cancel()
        currentTag = tag
        completedBytes = 0
        totalBytes = 0
        installedSnapshot = nil
        phase = .choosingModel
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

    /// Step 1 → commit ("Use …"): the full switch, then the setup. Switches the
    /// provider to Ollama with this model (the canonical triad: activeProvider,
    /// per-provider model, global model, then one prefs notification so
    /// ServeManager restarts on it), then routes on a fresh daemon snapshot:
    /// down → `needsOllama`; up & present → ready (no fetch); up & absent →
    /// `downloading`. The switch comes first, always: routing without it would
    /// download a model while analysis still went to the old provider, and a
    /// global model written while a cloud provider is active points that
    /// provider at an Ollama tag. What the sheet's "Use Ollama" button did
    /// (`activateLocalDefault`), minus the consent record, which is the sheet's.
    func useModel(tag: String) {
        committed = true
        if Self.activate(tag: tag, in: defaults) {
            notifications.post(name: .bristlenosePrefsChanged, object: nil)
        }
        currentTag = tag
        task?.cancel()
        task = Task { @MainActor in await self.route(tag: tag) }
    }

    /// The provider switch `useModel(tag:)` makes, as data: Ollama active, this
    /// model for Ollama and as the global model. True when anything changed, so
    /// re-using the same model does not restart the serve.
    @discardableResult
    nonisolated static func activate(tag: String, in defaults: UserDefaults) -> Bool {
        let wanted = [("activeProvider", LLMProvider.ollama.rawValue),
                      ("llmModel_\(LLMProvider.ollama.rawValue)", tag),
                      ("llmModel", tag)]
        var changed = false
        for (key, value) in wanted where defaults.string(forKey: key) != value {
            defaults.set(value, forKey: key)
            changed = true
        }
        return changed
    }

    /// The picker closed. Without "Use …" nothing was chosen, so the stage that
    /// was showing comes back (needs Ollama, failed) or the setup goes idle.
    /// After "Use …" the route `useModel` started carries on: the phase is still
    /// `.choosingModel` until its daemon probe returns, so closing must not cancel.
    func pickerDismissed() {
        guard phase == .choosingModel, !committed else { return }
        task?.cancel()
        phase = resume.phase
        currentTag = resume.tag
    }

    /// The person made another provider active. A setup still waiting on Ollama
    /// (or for its choice) has no deadline and nothing on screen once Settings
    /// leaves Ollama, so it stops; a running download, which has its pill and
    /// its Cancel, carries on.
    func activeProviderChanged(to rawValue: String) {
        guard rawValue != LLMProvider.ollama.rawValue else { return }
        switch phase {
        case .choosingModel, .needsOllama, .waitingForOllama: cancel()
        case .idle, .downloading, .finishing, .failed: break
        }
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
            if let pull = error as? LLMValidator.OllamaPullError {
                // The daemon's own sentence can name a path under the user's
                // home, so it is private; the kind of failure is not.
                Self.logger.error(
                    "Ollama download failed: the daemon said \(pull.message, privacy: .private)")
            } else {
                Self.logger.error(
                    "Ollama download failed: \(error.localizedDescription, privacy: .public)")
            }
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
        if let pull = error as? LLMValidator.OllamaPullError {
            // The daemon's own sentence (a full disk, a model it does not know).
            return .generic(pull.message)
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
