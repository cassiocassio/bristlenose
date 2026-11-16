import Foundation
import os

// Apple Background Assets as a way to acquire the Whisper model (store build, macOS 26+).
//
// The acquirer is plain Swift over a small adapter. The adapter is the only thing that touches
// `AssetPackManager` (`AssetPackManagerAdapter.swift`, behind a compile flag), so everything
// decided here is tested with a fake: the order of steps, the watchdog, the verification, the
// one remove-and-ensure-again, and what each ending reports.
//
// Owner rules (16 Nov 2026): the app trusts the system's contract and does not hand-roll around
// it, builds no recovery that depends on how the system behaves after a failure, and promises
// nothing about resume in anything it shows. A failed attempt ends as `.failed`; the model then
// hands this launch to the sidecar fetch, and the next launch (or Download Now) asks Background
// Assets again.

/// The system's pack manager, as this app uses it. One pack, one directory.
protocol WhisperPackAdapter: Sendable {
    /// Start the download and wait for it. A fresh status subscription each call (a subscription
    /// does not survive a failure). `report` gets (done, total) bytes. Throws when it fails.
    func ensure(report: @escaping @Sendable (Int64, Int64) -> Void) async throws
    /// Cancel the attempt in flight, if any. The `ensure` then throws.
    func cancelEnsure()
    /// Where the pack's directory is, asked every time and never kept: the system says this path
    /// is only good for the life of the process. It returns a path for a file that is not there.
    func directory() throws -> URL
    func remove() async throws
}

/// Why an `ensure` call ended without the pack: the one fact the acquirer needs is whether it
/// was a cancellation, which the system reports as NSURLErrorCancelled (-999).
func whisperEnsureWasCancelled(_ error: Error) -> Bool {
    if error is CancellationError { return true }
    let ns = error as NSError
    return ns.domain == NSURLErrorDomain && ns.code == NSURLErrorCancelled
}

@MainActor
final class BackgroundAssetsAcquirer: WhisperModelAcquirer {
    private static let logger = Logger(subsystem: "app.bristlenose", category: "whisper-download")

    let kind: WhisperAcquirerKind = .backgroundAssets
    private let adapter: WhisperPackAdapter
    private let manifest: WhisperPackManifest
    private let silenceLimit: Duration
    private let verify: @Sendable (URL, WhisperPackManifest) -> WhisperPackVerdict

    private var task: Task<Void, Never>?
    private var stopRequested = false
    private weak var events: WhisperAcquisitionEvents?

    /// - silenceLimit: how long without a byte moving before the attempt is given up (plan §4:
    ///   60 s). Injected so a test does not wait a minute.
    init(adapter: WhisperPackAdapter, manifest: WhisperPackManifest = .largeV3Turbo,
         silenceLimit: Duration = .seconds(60),
         verify: @escaping @Sendable (URL, WhisperPackManifest) -> WhisperPackVerdict = {
             WhisperPackVerifier.verify(directory: $0, manifest: $1)
         }) {
        self.adapter = adapter
        self.manifest = manifest
        self.silenceLimit = silenceLimit
        self.verify = verify
    }

    var isAvailable: Bool { true }
    var isRunning: Bool { task != nil }

    /// The model directory the sidecar reads, and the marker that the app owns the model: given
    /// while an attempt runs, and when a complete pack is on disk. Otherwise nothing, so a run
    /// that needs Whisper and has no pack fetches it itself, as it always has.
    var runEnvironment: [String: String] {
        guard isRunning || presentDirectory() != nil else { return [:] }
        var env = WhisperDownloadModel.hostOwnsEnvironment
        if let dir = presentDirectory() {
            env["BRISTLENOSE_WHISPER_MODEL_DIR"] = dir.deletingLastPathComponent().path
        }
        return env
    }

    /// The pack's directory when names and sizes say it is all there. Asked fresh each time.
    func presentDirectory() -> URL? {
        guard let dir = try? adapter.directory(),
              WhisperPackVerifier.quickCheck(directory: dir, manifest: manifest) == .ok else { return nil }
        return dir
    }

    func start(events: WhisperAcquisitionEvents) -> Bool {
        guard task == nil else { return false }
        self.events = events
        stopRequested = false
        task = Task { [weak self] in
            guard let self else { return }
            let outcome = await self.run()
            self.finish(outcome)
        }
        return true
    }

    func stop() {
        guard task != nil else { return }
        stopRequested = true
        adapter.cancelEnsure()
        task?.cancel()  // before the first byte there is no Progress to cancel
    }

    func appWillTerminate() {}

    // MARK: The attempt

    private func finish(_ outcome: WhisperAcquisitionOutcome) {
        task = nil
        events?.acquisitionEnded(outcome, from: self)
    }

    private func run() async -> WhisperAcquisitionOutcome {
        // The one repair: a pack that arrives wrong is removed and asked for again, once.
        for attempt in 1...2 {
            switch await ensureWithWatchdog() {
            case .cancelled:
                return .stopped
            case .failed:
                return .failed(cause: nil)
            case .arrived:
                break
            }
            guard let dir = try? adapter.directory() else { return .failed(cause: nil) }
            let verdict = await Task.detached { [verify, manifest] in verify(dir, manifest) }.value
            if verdict == .ok { return .succeeded }
            Self.logger.error("whisper pack did not verify (attempt \(attempt, privacy: .public)): \(String(describing: verdict), privacy: .public)")
            if attempt == 2 || stopRequested { return stopRequested ? .stopped : .failed(cause: nil) }
            do { try await adapter.remove() } catch {
                Self.logger.error("whisper pack could not be removed: \(error.localizedDescription, privacy: .public)")
                return .failed(cause: nil)
            }
        }
        return .failed(cause: nil)
    }

    private enum EnsureEnd { case arrived, cancelled, failed }

    /// `ensure` raced against a watchdog that gives up when no byte has moved for `silenceLimit`.
    private func ensureWithWatchdog() async -> EnsureEnd {
        let clock = SilenceClock()
        let report: @Sendable (Int64, Int64) -> Void = { [weak self] done, total in
            clock.touch(done)
            Task { @MainActor in
                guard let self, let events = self.events else { return }
                events.acquisitionProgress(done: done, total: total, from: self)
            }
        }
        let adapter = self.adapter
        let limit = silenceLimit
        let outcome: EnsureEnd = await withTaskGroup(of: EnsureEnd.self) { group in
            group.addTask {
                do { try await adapter.ensure(report: report); return .arrived } catch {
                    return whisperEnsureWasCancelled(error) ? .cancelled : .failed
                }
            }
            group.addTask {
                while !Task.isCancelled {
                    try? await Task.sleep(for: .milliseconds(200))
                    if clock.silent(for: limit) { clock.markTimedOut(); adapter.cancelEnsure(); return .failed }
                }
                return .cancelled
            }
            let first = await group.next() ?? .failed
            group.cancelAll()
            return first
        }
        // The watchdog's own cancel makes `ensure` throw "cancelled" too, and either can finish
        // first: a give-up is a failure whichever did. A cancel nobody here asked for is the
        // system's, and the model treats it as a stop.
        return clock.timedOut ? .failed : outcome
    }
}

/// When a byte last moved, readable from any thread.
final class SilenceClock: @unchecked Sendable {
    private let lock = NSLock()
    private var last = ContinuousClock.now
    private var bytes: Int64 = -1
    private var gaveUp = false

    var timedOut: Bool { lock.lock(); defer { lock.unlock() }; return gaveUp }
    func markTimedOut() { lock.lock(); gaveUp = true; lock.unlock() }

    func touch(_ done: Int64) {
        lock.lock(); defer { lock.unlock() }
        if done != bytes { bytes = done; last = .now }
    }

    func silent(for limit: Duration) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return ContinuousClock.now - last >= limit
    }
}
