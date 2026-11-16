import Foundation
import Testing
@testable import Bristlenose

/// The seam that decides how the Whisper model reaches this Mac
/// (`WhisperModelAcquirer.swift`, docs/private/background-assets-whisper-plan-2026-11.md §4).
@Suite struct WhisperAcquirerPickerTests {

    private typealias Pick = WhisperAcquirerPicker

    /// Every (OS, channel, kill switch, usable) cell. Background Assets only where all four hold.
    @Test func theWholeTable() {
        let channels: [DistributionChannel] = [.debug, .developerID, .appStoreOrTestFlight]
        for os in [14, 15, 25, 26, 27, 99] {
            for channel in channels {
                for kill in [true, false] {
                    for usable in [true, false] {
                        let want: WhisperAcquirerKind =
                            (os >= 26 && channel == .appStoreOrTestFlight && kill && usable)
                            ? .backgroundAssets : .sidecarFetch
                        #expect(
                            Pick.pick(osMajor: os, channel: channel, killSwitchOn: kill,
                                      backgroundAssetsUsable: usable) == want,
                            "os \(os) \(channel) kill \(kill) usable \(usable)")
                    }
                }
            }
        }
    }

    @Test func theNamedCases() {
        // macOS 15 store build: today's Hugging Face path.
        #expect(Pick.pick(osMajor: 15, channel: .appStoreOrTestFlight, killSwitchOn: true,
                          backgroundAssetsUsable: true) == .sidecarFetch)
        // macOS 26 store build: Background Assets.
        #expect(Pick.pick(osMajor: 26, channel: .appStoreOrTestFlight, killSwitchOn: true,
                          backgroundAssetsUsable: true) == .backgroundAssets)
        // The Developer-ID .dmg never gets one, on any OS.
        #expect(Pick.pick(osMajor: 27, channel: .developerID, killSwitchOn: true,
                          backgroundAssetsUsable: true) == .sidecarFetch)
        // Switched off, or failed and sent to the fallback: the fetch.
        #expect(Pick.pick(osMajor: 26, channel: .appStoreOrTestFlight, killSwitchOn: false,
                          backgroundAssetsUsable: true) == .sidecarFetch)
        #expect(Pick.pick(osMajor: 26, channel: .appStoreOrTestFlight, killSwitchOn: true,
                          backgroundAssetsUsable: false) == .sidecarFetch)
    }
}

@MainActor @Suite struct WhisperHostOwnsEnvironmentTests {

    /// The name is Python's (`bristlenose/preflight/whisper.py`, `_HOST_OWNS_ENV`);
    /// `tests/test_env_name_parity.py` fails if Swift sets one Python never reads.
    @Test func theMarkerIsExactlyWhatPythonReads() {
        #expect(WhisperDownloadModel.hostOwnsEnvironment == ["_BRISTLENOSE_WHISPER_HOST_OWNS": "1"])
    }

    @Test func aSidecarFetchThatNeverStartedNamesNoPid() {
        let acquirer = SidecarFetchAcquirer()
        #expect(acquirer.runEnvironment.isEmpty)
        #expect(!acquirer.isRunning)
    }
}

/// A stand-in for the thing that fetches, so the model's own rules are tested without a sidecar.
@MainActor
final class FakeAcquirer: WhisperModelAcquirer {
    var kind: WhisperAcquirerKind = .sidecarFetch
    var isAvailable = true
    var running = false
    var startWorks = true
    var env: [String: String] = [:]
    /// What a run is given when nothing is downloading (a pack already delivered, say).
    var idleEnv: [String: String] = [:]
    private(set) var stopCalls = 0
    private(set) var startCalls = 0
    private weak var events: WhisperAcquisitionEvents?

    var isRunning: Bool { running }
    var runEnvironment: [String: String] { running ? env : idleEnv }

    func start(events: WhisperAcquisitionEvents) -> Bool {
        startCalls += 1
        guard startWorks else { return false }
        self.events = events
        running = true
        return true
    }
    func stop() { stopCalls += 1 }
    func appWillTerminate() {}

    func progress(_ done: Int64, _ total: Int64) { events?.acquisitionProgress(done: done, total: total, from: self) }
    func end(_ outcome: WhisperAcquisitionOutcome) { running = false; events?.acquisitionEnded(outcome, from: self) }
}

/// The model's rules over an acquirer: the same whichever one it is.
@MainActor @Suite struct WhisperModelOverAnAcquirerTests {

    private func model(_ fake: FakeAcquirer) -> (WhisperDownloadModel, UserDefaults) {
        let suite = "bn-whisper-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defaults.removePersistentDomain(forName: suite)
        return (WhisperDownloadModel(defaults: defaults, makeAcquirer: { _ in fake }), defaults)
    }

    @Test func downloadNowStartsTheAcquirerAndShowsProgress() {
        let fake = FakeAcquirer()
        let (m, _) = model(fake)
        m.downloadNow()
        #expect(m.phase == .downloading)
        fake.progress(500, 1000)
        #expect(m.doneBytes == 500 && m.totalBytes == 1000)
        #expect(fake.startCalls == 1)
        m.downloadNow()  // single-flight
        #expect(fake.startCalls == 1)
    }

    @Test func aFailureIsShownWithItsCause() {
        let fake = FakeAcquirer()
        let (m, _) = model(fake)
        m.downloadNow()
        fake.end(.failed(cause: .network))
        #expect(m.phase == .failed)
        #expect(m.failureCause == .network)
    }

    @Test func anAcquirerThatCannotStartIsAFailureNotASilentNothing() {
        let fake = FakeAcquirer(); fake.startWorks = false
        let (m, _) = model(fake)
        m.downloadNow()
        #expect(m.phase == .failed)

        let gone = FakeAcquirer(); gone.isAvailable = false
        let (m2, _) = model(gone)
        m2.downloadNow()
        #expect(m2.phase == .failed)
        #expect(gone.startCalls == 0)
    }

    /// Stop after the job has already exited must not leave a remembered "stopped by you":
    /// that would stop the app trying again until Download Now (review of M2a, 16 Nov).
    @Test func aStopThatFindsNothingRunningRemembersNothing() {
        let fake = FakeAcquirer()
        let (m, defaults) = model(fake)
        m.downloadNow()
        fake.running = false  // exited; its end has not been delivered yet
        m.stop()
        #expect(fake.stopCalls == 0)
        #expect(defaults.bool(forKey: "whisperDownloadStoppedByUser") == false)
    }

    @Test func aStopWhileRunningIsRememberedAndPassedOn() {
        let fake = FakeAcquirer()
        let (m, defaults) = model(fake)
        m.downloadNow()
        m.stop()
        #expect(fake.stopCalls == 1)
        #expect(defaults.bool(forKey: "whisperDownloadStoppedByUser") == true)
    }

    /// A late event from an acquirer that is no longer the current one is ignored.
    @Test func aStaleEndDoesNotClearTheCurrentAttempt() {
        let first = FakeAcquirer()
        var current = first
        let suite = "bn-whisper-test-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        let m = WhisperDownloadModel(defaults: defaults, makeAcquirer: { _ in current })
        m.downloadNow()
        first.end(.failed(cause: nil))      // attempt one ends: failed
        #expect(m.phase == .failed)
        current = FakeAcquirer()
        m.downloadNow()                      // attempt two begins
        #expect(m.phase == .downloading)
        first.end(.failed(cause: .disk))     // a stale end from attempt one
        #expect(m.phase == .downloading, "the stale end must not touch attempt two")
        #expect(m.failureCause == nil)
    }

    /// A run only waits on the download while it is running, whichever acquirer it is.
    @Test func theRunEnvironmentIsTheAcquirersAndOnlyWhileItRuns() {
        let fake = FakeAcquirer(); fake.env = ["_X": "1"]
        let (m, _) = model(fake)
        #expect(m.runEnvironment.isEmpty)
        m.downloadNow()
        #expect(m.runEnvironment == ["_X": "1"])
        fake.end(.failed(cause: nil))
        #expect(m.runEnvironment.isEmpty)
    }
}

// MARK: - The pack verifier

@Suite struct WhisperPackVerifierTests {

    private func pack(_ files: [String: String]) throws -> (URL, WhisperPackManifest) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-pack-\(UUID().uuidString)/large-v3-turbo")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        for (name, text) in files { try Data(text.utf8).write(to: dir.appendingPathComponent(name)) }
        func entry(_ name: String, _ text: String) -> WhisperPackManifest.File {
            let url = dir.appendingPathComponent(name)
            return .init(name: name, bytes: Int64(text.utf8.count),
                         sha256: WhisperPackVerifier.sha256(of: url) ?? "")
        }
        return (dir, WhisperPackManifest(
            assetPackID: "p", directory: "large-v3-turbo",
            files: [entry("config.json", "{}"), entry("weights.safetensors", "tensors")]))
    }

    private let good = ["config.json": "{}", "weights.safetensors": "tensors"]

    @Test func anIntactPackPassesBothChecks() throws {
        let (dir, m) = try pack(good)
        #expect(WhisperPackVerifier.quickCheck(directory: dir, manifest: m) == .ok)
        #expect(WhisperPackVerifier.verify(directory: dir, manifest: m) == .ok)
    }

    @Test func aMissingFileIsNamed() throws {
        let (dir, m) = try pack(good)
        try FileManager.default.removeItem(at: dir.appendingPathComponent("weights.safetensors"))
        #expect(WhisperPackVerifier.quickCheck(directory: dir, manifest: m) == .missing("weights.safetensors"))
        let (_, m2) = try pack(good)
        let nowhere = URL(fileURLWithPath: "/nonexistent/\(UUID().uuidString)")
        #expect(WhisperPackVerifier.quickCheck(directory: nowhere, manifest: m2) == .missing("large-v3-turbo"))
    }

    @Test func aWrongSizeFailsTheQuickCheck() throws {
        let (dir, m) = try pack(good)
        try Data("short".utf8).write(to: dir.appendingPathComponent("weights.safetensors"))
        #expect(WhisperPackVerifier.quickCheck(directory: dir, manifest: m) == .wrongSize("weights.safetensors"))
    }

    @Test func aFileTheAllowlistDoesNotNameIsRefused() throws {
        let (dir, m) = try pack(good)
        try Data("x".utf8).write(to: dir.appendingPathComponent("weights.npz"))
        #expect(WhisperPackVerifier.verify(directory: dir, manifest: m) == .unexpected("weights.npz"))
        // A file system dot file is not the pack's.
        try FileManager.default.removeItem(at: dir.appendingPathComponent("weights.npz"))
        try Data("x".utf8).write(to: dir.appendingPathComponent(".DS_Store"))
        #expect(WhisperPackVerifier.verify(directory: dir, manifest: m) == .ok)
    }

    /// Same size, different bytes: only the hash can tell.
    @Test func sameSizeDifferentBytesFailsTheFullCheckOnly() throws {
        let (dir, m) = try pack(good)
        try Data("TENSORS".utf8).write(to: dir.appendingPathComponent("weights.safetensors"))
        #expect(WhisperPackVerifier.quickCheck(directory: dir, manifest: m) == .ok)
        #expect(WhisperPackVerifier.verify(directory: dir, manifest: m) == .wrongHash("weights.safetensors"))
    }

    @Test func thePinnedManifestMatchesTheBuildScriptAllowlist() {
        let m = WhisperPackManifest.largeV3Turbo
        #expect(m.assetPackID == "whisper-large-v3-turbo")
        #expect(m.directory == "large-v3-turbo")
        #expect(m.files.map(\.name) == ["config.json", "weights.safetensors"])
        #expect(m.files.allSatisfy { $0.sha256.count == 64 && $0.bytes > 0 })
    }
}

// MARK: - The Background Assets acquirer over a fake adapter

final class FakeAdapter: WhisperPackAdapter, @unchecked Sendable {
    enum Behaviour { case succeed, throwError(Error), hang }
    private let lock = NSLock()
    private var behaviours: [Behaviour]
    private var cancelled = false
    private(set) var ensureCalls = 0
    private(set) var removeCalls = 0
    private(set) var directoryCalls = 0
    let dir: URL

    init(_ behaviours: [Behaviour], dir: URL) { self.behaviours = behaviours; self.dir = dir }

    func ensure(report: @escaping @Sendable (Int64, Int64) -> Void) async throws {
        let behaviour: Behaviour = {
            lock.lock(); defer { lock.unlock() }
            ensureCalls += 1; cancelled = false
            return behaviours.isEmpty ? .succeed : behaviours.removeFirst()
        }()
        switch behaviour {
        case .succeed: report(10, 100); report(100, 100)
        case .throwError(let e): throw e
        case .hang:
            while true {
                try await Task.sleep(for: .milliseconds(20))
                lock.lock(); let c = cancelled; lock.unlock()
                if c { throw NSError(domain: NSURLErrorDomain, code: NSURLErrorCancelled) }
            }
        }
    }
    func cancelEnsure() { lock.lock(); cancelled = true; lock.unlock() }
    func directory() throws -> URL { lock.lock(); directoryCalls += 1; lock.unlock(); return dir }
    func remove() async throws { lock.lock(); removeCalls += 1; lock.unlock() }
}

@MainActor
final class RecordingEvents: WhisperAcquisitionEvents {
    var outcome: WhisperAcquisitionOutcome?
    var progress: [Int64] = []
    func acquisitionTotal(_ bytes: Int64, from: WhisperModelAcquirer) {}
    func acquisitionProgress(done: Int64, total: Int64, from: WhisperModelAcquirer) { progress.append(done) }
    func acquisitionEnded(_ outcome: WhisperAcquisitionOutcome, from: WhisperModelAcquirer) { self.outcome = outcome }

    func waitForEnd(seconds: Double = 5) async {
        let deadline = ContinuousClock.now + .seconds(seconds)
        while outcome == nil, ContinuousClock.now < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }
}

@MainActor @Suite struct BackgroundAssetsAcquirerTests {

    private let manifest = WhisperPackManifest(
        assetPackID: "p", directory: "large-v3-turbo",
        files: [.init(name: "config.json", bytes: 2, sha256: "x"), .init(name: "weights.safetensors", bytes: 7, sha256: "y")])

    private func dir(complete: Bool) throws -> URL {
        let d = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-ba-\(UUID().uuidString)/large-v3-turbo")
        try FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        if complete {
            try Data("{}".utf8).write(to: d.appendingPathComponent("config.json"))
            try Data("tensors".utf8).write(to: d.appendingPathComponent("weights.safetensors"))
        }
        return d
    }

    private func make(_ behaviours: [FakeAdapter.Behaviour], verdicts: [WhisperPackVerdict] = [.ok],
                      silence: Duration = .seconds(60), complete: Bool = true)
        throws -> (BackgroundAssetsAcquirer, FakeAdapter, RecordingEvents) {
        let adapter = FakeAdapter(behaviours, dir: try dir(complete: complete))
        let queue = VerdictQueue(verdicts)
        let acquirer = BackgroundAssetsAcquirer(
            adapter: adapter, manifest: manifest, silenceLimit: silence, verify: { _, _ in queue.next() })
        return (acquirer, adapter, RecordingEvents())
    }

    @Test func aPackThatArrivesAndVerifiesSucceeds() async throws {
        let (a, adapter, ev) = try make([.succeed])
        #expect(a.start(events: ev))
        await ev.waitForEnd()
        #expect(ev.outcome == .succeeded)
        #expect(adapter.ensureCalls == 1 && adapter.removeCalls == 0)
        #expect(!a.isRunning)
    }

    @Test func aPackThatFailsVerificationIsRemovedAndAskedForOnceMore() async throws {
        let (a, adapter, ev) = try make([.succeed, .succeed], verdicts: [.wrongHash("weights.safetensors"), .ok])
        _ = a.start(events: ev)
        await ev.waitForEnd()
        #expect(ev.outcome == .succeeded)
        #expect(adapter.ensureCalls == 2 && adapter.removeCalls == 1)
    }

    @Test func aPackThatFailsVerificationTwiceIsAFailure() async throws {
        let (a, adapter, ev) = try make([.succeed, .succeed],
                                        verdicts: [.wrongHash("w"), .wrongHash("w")])
        _ = a.start(events: ev)
        await ev.waitForEnd()
        #expect(ev.outcome == .failed(cause: nil))
        #expect(adapter.ensureCalls == 2 && adapter.removeCalls == 1, "one repair, not a loop")
    }

    @Test func aDroppedConnectionIsAFailureNotAStop() async throws {
        let (a, _, ev) = try make([.throwError(NSError(domain: NSURLErrorDomain, code: -1005))])
        _ = a.start(events: ev)
        await ev.waitForEnd()
        #expect(ev.outcome == .failed(cause: nil))
    }

    @Test func offlineAtStartIsAFailure() async throws {
        // `assetPack(withID:)` itself throws when the server cannot be reached.
        let (a, _, ev) = try make([.throwError(NSError(domain: "ManagedBackgroundAssetsXPC.ErrorCoding", code: 1))])
        _ = a.start(events: ev)
        await ev.waitForEnd()
        #expect(ev.outcome == .failed(cause: nil))
    }

    @Test func stopCancelsTheAttemptAndEndsAsStopped() async throws {
        let (a, _, ev) = try make([.hang])
        _ = a.start(events: ev)
        try await Task.sleep(for: .milliseconds(100))
        a.stop()
        await ev.waitForEnd()
        #expect(ev.outcome == .stopped)
    }

    /// The watchdog's own cancel makes `ensure` throw "cancelled" as well: that is a give-up.
    @Test func silenceIsAFailureEvenThoughItCancelsTheAttempt() async throws {
        let (a, _, ev) = try make([.hang], silence: .milliseconds(300))
        _ = a.start(events: ev)
        await ev.waitForEnd()
        #expect(ev.outcome == .failed(cause: nil))
    }

    @Test func progressIsPassedOn() async throws {
        let (a, _, ev) = try make([.succeed])
        _ = a.start(events: ev)
        await ev.waitForEnd()
        try await Task.sleep(for: .milliseconds(50))
        #expect(ev.progress.contains(100))
    }

    /// The sandboxed child's access to the pack is granted per `url(for:)` request, made by the
    /// process that spawns it (measured 16 Nov 2026: a child spawned after a request for the
    /// weights alone got ENOENT on config.json). So every environment built for a spawn asks for
    /// the DIRECTORY, fresh, even when the pack is absent, and never reuses an earlier answer.
    @Test func everyEnvironmentAsksTheSystemForTheDirectoryAgain() throws {
        let (a, adapter, _) = try make([.succeed])
        _ = a.runEnvironment
        _ = a.runEnvironment
        #expect(adapter.directoryCalls >= 2)
        let (absent, adapterAbsent, _) = try make([.succeed], complete: false)
        _ = absent.runEnvironment
        #expect(adapterAbsent.directoryCalls == 1, "asked even when nothing is there yet")
    }

    @Test func theEnvironmentNamesThePackOnlyWhenItIsHereOrComing() async throws {
        // Absent and idle: nothing, so a run that needs Whisper fetches it itself.
        let (absent, _, _) = try make([.succeed], complete: false)
        #expect(absent.runEnvironment.isEmpty)
        // Present and idle: the marker and the parent of the pack's directory.
        let (present, adapter, _) = try make([.succeed])
        let env = present.runEnvironment
        #expect(env["_BRISTLENOSE_WHISPER_HOST_OWNS"] == "1")
        #expect(env["BRISTLENOSE_WHISPER_MODEL_DIR"] == adapter.dir.deletingLastPathComponent().path)
        // Coming (an attempt runs, nothing there yet): the marker alone.
        let (coming, _, ev) = try make([.hang], complete: false)
        _ = coming.start(events: ev)
        #expect(coming.runEnvironment == ["_BRISTLENOSE_WHISPER_HOST_OWNS": "1"])
        coming.stop()
        await ev.waitForEnd()
    }
}

final class VerdictQueue: @unchecked Sendable {
    private let lock = NSLock()
    private var items: [WhisperPackVerdict]
    init(_ items: [WhisperPackVerdict]) { self.items = items }
    func next() -> WhisperPackVerdict {
        lock.lock(); defer { lock.unlock() }
        return items.count > 1 ? items.removeFirst() : (items.first ?? .ok)
    }
}

// MARK: - The model over a Background Assets acquirer

@MainActor @Suite struct WhisperModelFallbackTests {

    private func defaults() -> UserDefaults {
        let suite = "bn-whisper-test-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: suite)!
        d.removePersistentDomain(forName: suite)
        return d
    }

    /// Background Assets failed: this launch goes to the sidecar fetch at once, and a later
    /// Download Now asks Background Assets again.
    @Test func aFailureFallsBackAndTheNextDownloadNowTriesAgain() {
        let ba = FakeAcquirer(); ba.kind = .backgroundAssets
        let fetch = FakeAcquirer()
        var usableAsked: [Bool] = []
        var queue = [ba, fetch, ba]
        let m = WhisperDownloadModel(defaults: defaults(), makeAcquirer: { usable in
            usableAsked.append(usable)
            return queue.removeFirst()
        })
        m.downloadNow()                              // Background Assets starts
        #expect(ba.startCalls == 1)
        ba.end(.failed(cause: nil))                  // ...fails
        #expect(fetch.startCalls == 1, "this launch falls to the sidecar fetch")
        #expect(m.phase == .downloading)
        #expect(usableAsked == [true, false])
        fetch.end(.succeeded)
        queue = [ba]
        m.downloadNow()                              // the researcher asks again
        #expect(usableAsked.last == true, "Download Now gives Background Assets another go")
    }

    /// A failed sidecar fetch is a failure: only Background Assets falls back.
    @Test func aSidecarFailureDoesNotFallBackToItself() {
        let fetch = FakeAcquirer()
        let m = WhisperDownloadModel(defaults: defaults(), makeAcquirer: { _ in fetch })
        m.downloadNow()
        fetch.end(.failed(cause: .disk))
        #expect(m.phase == .failed && m.failureCause == .disk)
        #expect(fetch.startCalls == 1)
    }

    /// The system cancelled it (nobody here asked): that is remembered as a stop.
    @Test func aCancelThatWasNotOursIsRememberedAsAStop() {
        let ba = FakeAcquirer(); ba.kind = .backgroundAssets
        let d = defaults()
        let m = WhisperDownloadModel(defaults: d, makeAcquirer: { _ in ba })
        m.downloadNow()
        ba.end(.stopped)
        #expect(d.bool(forKey: "whisperDownloadStoppedByUser") == true)
    }

    @Test func aStopWeAskedForIsNotDoubleCounted() {
        let fetch = FakeAcquirer()
        let d = defaults()
        let m = WhisperDownloadModel(defaults: d, makeAcquirer: { _ in fetch })
        m.downloadNow()
        m.stop()
        d.set(false, forKey: "whisperDownloadStoppedByUser")  // forget it, to see whether `.stopped` sets it again
        fetch.end(.stopped)
        #expect(d.bool(forKey: "whisperDownloadStoppedByUser") == false)
    }
}

@Suite struct BackgroundAssetsKillSwitchTests {
    @Test func onUnlessWrittenOff() {
        let suite = "bn-flag-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: suite)!
        #expect(BristlenoseFlags.backgroundAssets(in: d) == true)
        d.set(false, forKey: BristlenoseFlags.backgroundAssetsKey)
        #expect(BristlenoseFlags.backgroundAssets(in: d) == false)
        d.removePersistentDomain(forName: suite)
    }

    @Test func theCompileFlagAndTheHelperAgree() {
        // Dark until the extension target (M4) defines BA_WHISPER for the store configuration;
        // the helper must say exactly what the compile condition says.
        #if BA_WHISPER && !DEVELOPER_ID_BETA
        #expect(WhisperDownloadModel.backgroundAssetsCompiledIn == true)
        #else
        #expect(WhisperDownloadModel.backgroundAssetsCompiledIn == false)
        #endif
    }
}
