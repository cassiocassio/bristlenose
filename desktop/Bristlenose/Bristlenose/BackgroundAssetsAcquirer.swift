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

/// What the app remembers of a pack it has verified (names, sizes, times: see
/// `WhisperPackVerifier.fingerprint`). A pack is handed to the sidecar only while this matches
/// what is on disk now, so a pack the system delivered on its own, or one that failed its hash
/// and was left behind, is never trusted on names and sizes alone.
protocol WhisperPackStampStore: AnyObject {
    var verifiedFingerprint: String? { get set }
}

final class UserDefaultsPackStampStore: WhisperPackStampStore {
    private let defaults: UserDefaults
    private let key: String
    init(defaults: UserDefaults = .standard, key: String = "whisperPackVerifiedFingerprint") {
        self.defaults = defaults
        self.key = key
    }
    var verifiedFingerprint: String? {
        get { defaults.string(forKey: key) }
        set { defaults.set(newValue, forKey: key) }
    }
}

/// The first of several results wins; later ones are ignored. Lets Stop and the watchdog end an
/// attempt without waiting for a call that may never honour cancellation.
final class EnsureRace: @unchecked Sendable {
    enum End { case arrived, cancelled, failed }
    private let lock = NSLock()
    private var result: End?
    private var continuation: CheckedContinuation<End, Never>?

    /// True for the call that decided it.
    @discardableResult
    func finish(_ end: End) -> Bool {
        lock.lock()
        guard result == nil else { lock.unlock(); return false }
        result = end
        let waiting = continuation
        continuation = nil
        lock.unlock()
        waiting?.resume(returning: end)
        return true
    }

    func value() async -> End {
        await withCheckedContinuation { (cont: CheckedContinuation<End, Never>) in
            lock.lock()
            if let result { lock.unlock(); cont.resume(returning: result); return }
            continuation = cont
            lock.unlock()
        }
    }
}

@MainActor
final class BackgroundAssetsAcquirer: WhisperModelAcquirer {
    private static let logger = Logger(subsystem: "app.bristlenose", category: "whisper-download")

    let kind: WhisperAcquirerKind = .backgroundAssets
    private let adapter: WhisperPackAdapter
    private let manifest: WhisperPackManifest
    private let silenceLimit: Duration
    private let verify: @Sendable (URL, WhisperPackManifest) -> WhisperPackVerdict
    private let stamp: WhisperPackStampStore
    /// Whether the model the researcher chose is the one this pack holds. Another model is not
    /// the app's to deliver, so it is never marked host-owned.
    private let servesChosenModel: () -> Bool

    private var task: Task<Void, Never>?
    private var race: EnsureRace?
    private var stopRequested = false
    private weak var events: WhisperAcquisitionEvents?

    /// - silenceLimit: how long without a byte moving before the attempt is given up (plan §4:
    ///   60 s). Injected so a test does not wait a minute.
    init(adapter: WhisperPackAdapter, manifest: WhisperPackManifest = .largeV3Turbo,
         silenceLimit: Duration = .seconds(60),
         verify: @escaping @Sendable (URL, WhisperPackManifest) -> WhisperPackVerdict = {
             WhisperPackVerifier.verify(directory: $0, manifest: $1)
         },
         stamp: WhisperPackStampStore = UserDefaultsPackStampStore(),
         servesChosenModel: @escaping () -> Bool = { WhisperDownloadModel.chosenModelIsPackModel() }) {
        self.stamp = stamp
        self.servesChosenModel = servesChosenModel
        self.adapter = adapter
        self.manifest = manifest
        self.silenceLimit = silenceLimit
        self.verify = verify
    }

    var isAvailable: Bool { true }
    var isRunning: Bool { task != nil }

    /// The model directory the sidecar reads, and the marker that the app owns the model.
    /// Nothing unless the chosen model is this pack's. The marker alone while an attempt runs
    /// (the model is coming); with the directory only once a pack that this app has VERIFIED is
    /// on disk. An unverified pack (delivered by the system on its own, or left behind by a failed
    /// hash) gets neither, so a run that needs Whisper fetches it itself, as it always has, and
    /// the app verifies the pack the next time it starts an acquisition.
    var runEnvironment: [String: String] {
        guard servesChosenModel() else { return [:] }
        let dir = presentDirectory()
        guard isRunning || dir != nil else { return [:] }
        var env = WhisperDownloadModel.hostOwnsEnvironment
        if let dir { env["BRISTLENOSE_WHISPER_MODEL_DIR"] = dir.deletingLastPathComponent().path }
        return env
    }

    /// The pack's directory when it is all there AND this app verified exactly these bytes.
    /// Asked of the system fresh each time (the grant is per `url(for:)` request).
    func presentDirectory() -> URL? {
        guard let dir = try? adapter.directory(),
              WhisperPackVerifier.quickCheck(directory: dir, manifest: manifest) == .ok,
              let now = WhisperPackVerifier.fingerprint(directory: dir, manifest: manifest),
              stamp.verifiedFingerprint == now else { return nil }
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
        // Before the first byte there is no Progress to cancel, and the system call may not
        // honour task cancellation: do not wait for it.
        race?.finish(.cancelled)
        task?.cancel()
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
            if verdict == .ok {
                stamp.verifiedFingerprint = WhisperPackVerifier.fingerprint(directory: dir, manifest: manifest)
                return .succeeded
            }
            Self.logger.error("whisper pack did not verify (attempt \(attempt, privacy: .public)): \(String(describing: verdict), privacy: .public)")
            if attempt == 2 || stopRequested { return stopRequested ? .stopped : .failed(cause: nil) }
            stamp.verifiedFingerprint = nil
            do { try await adapter.remove() } catch {
                Self.logger.error("whisper pack could not be removed: \(error.localizedDescription, privacy: .public)")
                return .failed(cause: nil)
            }
            if stopRequested { return .stopped }
        }
        return .failed(cause: nil)
    }

    private typealias EnsureEnd = EnsureRace.End

    /// `ensure` raced against a watchdog that gives up when no byte has moved for `silenceLimit`,
    /// and against Stop. The first result wins and the rest are ignored; the call itself is told
    /// to cancel and is not waited for (it may take Apple's call a long time to notice, or never).
    private func ensureWithWatchdog() async -> EnsureEnd {
        let race = EnsureRace()
        self.race = race
        defer { self.race = nil }
        if stopRequested { return .cancelled }
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
        let ensureTask = Task.detached {
            do {
                try await adapter.ensure(report: report)
                race.finish(.arrived)
            } catch {
                race.finish(whisperEnsureWasCancelled(error) ? .cancelled : .failed)
            }
        }
        let watchdog = Task.detached {
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(200))
                if clock.silent(for: limit) { race.finish(.failed); return }
            }
        }
        let outcome = await race.value()
        watchdog.cancel()
        if outcome != .arrived {
            adapter.cancelEnsure()
            ensureTask.cancel()
        }
        return outcome
    }
}

/// When a byte last moved, readable from any thread.
final class SilenceClock: @unchecked Sendable {
    private let lock = NSLock()
    private var last = ContinuousClock.now
    private var bytes: Int64 = -1

    func touch(_ done: Int64) {
        lock.lock(); defer { lock.unlock() }
        if done != bytes { bytes = done; last = .now }
    }

    func silent(for limit: Duration) -> Bool {
        lock.lock(); defer { lock.unlock() }
        return ContinuousClock.now - last >= limit
    }
}
