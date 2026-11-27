import Foundation
import Testing
@testable import Bristlenose

/// The Whisper download's failure routes, each driven to the failure and then through the control
/// the researcher (or App Review, guideline 2.1) would use to try again, ending with a new attempt
/// actually started. The pill's Retry, Settings' Retry and Settings' Download Now all call
/// `downloadNow()` (`WhisperDownloadPill.swift`, `TranscriptionSettingsView.swift`; that wiring is
/// by code reading, no view is hosted here), so the tests call that; whether the pill draws Retry
/// at all is its own decision, `offersRetry`, which the popover's body uses. Causes are
/// handed to the model ready-classified: reading them off the sidecar's stderr is
/// `WhisperFailureCauseTests`; every acquirer here but the real `BackgroundAssetsAcquirer` in the
/// last test is a stand-in. The routes are `docs/design-whisper-delivery.md` §6 and §6a.
@MainActor @Suite struct WhisperRetryRouteTests {

    private static let stoppedKey = "whisperDownloadStoppedByUser"
    private typealias Detail = WhisperDownloadDetail

    private func scratchDefaults() -> UserDefaults {
        let suite = "bn-whisper-retry-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: suite)!
        d.removePersistentDomain(forName: suite)
        return d
    }

    /// Free space and consent pinned, so nothing depends on this Mac's disk.
    private func model(_ defaults: UserDefaults, free: Int64? = nil,
                       make: @escaping @MainActor (Bool) -> WhisperModelAcquirer) -> WhisperDownloadModel {
        let m = WhisperDownloadModel(defaults: defaults, makeAcquirer: make)
        m.freeDiskBytes = { free }
        m.hasAIConsent = { true }
        return m
    }

    private func offersRetry(_ m: WhisperDownloadModel) -> Bool {
        Detail.offersRetry(phase: m.phase, cause: m.failureCause)
    }

    /// A Hugging Face fetch fails for a reason Retry can mend: the pill shows the failure with
    /// Retry, and Retry starts a fresh attempt with the old cause gone.
    @Test(arguments: [WhisperFailureCause?.some(.network), .some(.certificate), .none])
    func aFetchFailureRetryCanMendIsOfferedRetryAndRetryStartsAgain(cause: WhisperFailureCause?) {
        var current = FakeAcquirer()
        let first = current
        let m = model(scratchDefaults()) { _ in current }
        m.downloadNow()
        first.end(.failed(cause: cause))
        #expect(m.phase == .failed && m.failureCause == cause && m.isPillVisible)
        #expect(offersRetry(m))

        current = FakeAcquirer()
        m.downloadNow()
        #expect(current.startCalls == 1, "Retry started a new attempt")
        #expect(m.phase == .downloading && m.failureCause == nil)
    }

    /// A full disk part-way through: the pill offers no Retry (its button opens Transcription
    /// Settings), and Settings' Retry starts the download even below the floor, because the
    /// researcher asked.
    @Test func aFullDiskDuringTheFetchIsRetriedFromSettingsEvenBelowTheFloor() {
        let fake = FakeAcquirer()
        let m = model(scratchDefaults(), free: 1_000_000_000) { _ in fake }
        m.downloadNow()
        fake.end(.failed(cause: .disk))
        #expect(m.phase == .failed && m.isPillVisible)
        #expect(Detail.diskProblem(phase: m.phase, cause: m.failureCause, lowDisk: m.lowDisk))
        #expect(!offersRetry(m))
        m.downloadNow()
        #expect(fake.startCalls == 2)
    }

    /// A full disk before anything starts: the warning pill, no Retry, and Download Now in
    /// Settings is not held by the floor. The phase is set directly (`debugApply`): how a launch
    /// reaches the warning is `WhisperStateMachineTests`.
    @Test func aFullDiskBeforeTheStartIsWarnedAndDownloadNowStillStarts() {
        let fake = FakeAcquirer()
        let m = model(scratchDefaults(), free: 1_000_000_000) { _ in fake }
        m.debugApply(.missing)
        #expect(m.lowDisk && m.isPillVisible)
        #expect(Detail.diskProblem(phase: m.phase, cause: m.failureCause, lowDisk: m.lowDisk))
        #expect(!offersRetry(m))
        m.downloadNow()
        #expect(fake.startCalls == 1)
        #expect(m.phase == .downloading && !m.lowDisk)
    }

    /// The researcher's Stop is remembered (no pill, nothing starts by itself), and Download Now
    /// forgets it and starts again (`docs/design-whisper-delivery.md` §6, "Researcher presses Stop").
    /// On Background Assets the Stop is also forgotten as a reason not to fall back: a failure of
    /// the new attempt still goes to Hugging Face, not to "the researcher stopped it".
    @Test func stopThenDownloadNowForgetsTheStopAndStartsAgain() {
        let d = scratchDefaults()
        let ba = FakeAcquirer(); ba.kind = .backgroundAssets
        let fetch = FakeAcquirer()
        let m = model(d) { usable in usable ? ba : fetch }
        m.downloadNow()
        m.stop()
        ba.end(.stopped)
        #expect(d.bool(forKey: Self.stoppedKey))
        #expect(!m.isPillVisible, "a deliberate Stop shows no pill")
        m.downloadNow()
        #expect(!d.bool(forKey: Self.stoppedKey), "Download Now forgets the Stop")
        #expect(ba.startCalls == 2)
        ba.end(.failed(cause: nil))
        #expect(fetch.startCalls == 1, "the earlier Stop does not block the fallback")
        #expect(m.phase == .downloading)
    }

    /// The acquirer could not start at all (the sidecar's process failed to launch): the pill shows
    /// the failure with Retry, and Retry is not dead afterwards.
    @Test func aStartThatIsRefusedLeavesRetryWorking() {
        let fake = FakeAcquirer(); fake.startWorks = false
        let m = model(scratchDefaults()) { _ in fake }
        m.downloadNow()
        #expect(m.phase == .failed && offersRetry(m))
        fake.startWorks = true
        m.downloadNow()
        #expect(fake.startCalls == 2)
        #expect(m.phase == .downloading)
    }

    /// Background Assets fails (pack missing, offline, silent), this launch falls to Hugging Face,
    /// and that fails too: the pill offers Retry, and Retry goes back to Background Assets first,
    /// not straight to the fetch that just failed.
    @Test func backgroundAssetsThenTheFallbackFailAndRetryStartsWithBackgroundAssets() {
        let ba = FakeAcquirer(); ba.kind = .backgroundAssets
        let fetch = FakeAcquirer()
        let m = model(scratchDefaults()) { usable in usable ? ba : fetch }
        m.downloadNow()
        ba.end(.failed(cause: nil))
        #expect(fetch.startCalls == 1 && m.phase == .downloading)
        fetch.end(.failed(cause: .network))
        #expect(m.phase == .failed && offersRetry(m))
        m.downloadNow()
        #expect(ba.startCalls == 2, "Retry asks Background Assets again")
        #expect(fetch.startCalls == 1)
        #expect(m.failureCause == nil)
    }

    /// A pack that never passes `WhisperPackVerifier`, through the real acquirer: the model falls
    /// back to the fetch for this launch and never trusts the pack; after the fetch fails, Retry
    /// asks the system for the pack again and, when it fails again, falls back again. A bad pack
    /// never leaves Retry dead.
    @Test func aPackThatNeverVerifiesFallsBackAndRetryRunsTheRouteAgain() async throws {
        let manifest = WhisperPackManifest(
            assetPackID: "p", directory: "large-v3-turbo",
            files: [.init(name: "config.json", bytes: 2, sha256: "x"),
                    .init(name: "weights.safetensors", bytes: 7, sha256: "y")])
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-ba-retry-\(UUID().uuidString)/large-v3-turbo")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try Data("{}".utf8).write(to: dir.appendingPathComponent("config.json"))
        try Data("tensors".utf8).write(to: dir.appendingPathComponent("weights.safetensors"))
        let adapter = FakeAdapter([], dir: dir)  // every request arrives
        let stamp = MemoryStamp()
        let ba = BackgroundAssetsAcquirer(
            adapter: adapter, manifest: manifest, silenceLimit: .seconds(60),
            verify: { _, _ in .wrongHash("weights.safetensors") }, stamp: stamp, servesChosenModel: { true })
        let fetch = FakeAcquirer()
        let m = model(scratchDefaults()) { usable in usable ? ba as WhisperModelAcquirer : fetch }

        m.downloadNow()
        await waitUntil { fetch.startCalls == 1 }
        #expect(fetch.startCalls == 1, "a pack that does not verify: this launch falls to the fetch")
        #expect(stamp.verifiedFingerprint == nil, "a pack that failed its hash is never trusted")
        let requestsBefore = adapter.ensureCalls
        fetch.end(.failed(cause: nil))
        #expect(m.phase == .failed && offersRetry(m))

        m.downloadNow()
        await waitUntil { fetch.startCalls == 2 }
        #expect(adapter.ensureCalls > requestsBefore, "Retry asked the system for the pack again")
        #expect(fetch.startCalls == 2)
        #expect(stamp.verifiedFingerprint == nil)
    }

    /// The system cancels the Background Assets request (nobody here asked), through the real
    /// acquirer: this launch falls to Hugging Face at once and the pill stays, instead of the pill
    /// vanishing with nothing said; a failure of that fetch then offers Retry.
    @Test func aSystemCancelFallsBackAndThePillStays() async throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("bn-ba-cancel-\(UUID().uuidString)/large-v3-turbo")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let adapter = FakeAdapter([.throwError(NSError(domain: NSURLErrorDomain, code: NSURLErrorCancelled))], dir: dir)
        let ba = BackgroundAssetsAcquirer(
            adapter: adapter, manifest: .largeV3Turbo, silenceLimit: .seconds(60),
            verify: { _, _ in .ok }, stamp: MemoryStamp(), servesChosenModel: { true })
        let fetch = FakeAcquirer()
        let d = scratchDefaults()
        let m = model(d) { usable in usable ? ba as WhisperModelAcquirer : fetch }

        m.downloadNow()
        await waitUntil { fetch.startCalls == 1 }
        #expect(fetch.startCalls == 1, "a system cancel falls to the fetch for this launch")
        #expect(m.phase == .downloading && m.isPillVisible)
        #expect(!d.bool(forKey: Self.stoppedKey), "not remembered as the researcher's Stop")
        fetch.end(.failed(cause: nil))
        #expect(offersRetry(m))
    }

    /// Waits on a fake's counter (`RecordingEvents.waitForEnd` waits on an acquirer's outcome,
    /// which the model, not the test, receives here). The deadline only turns a hang into a failed
    /// expectation; a green run never pays it.
    private func waitUntil(seconds: Double = 120, _ done: () -> Bool) async {
        let deadline = ContinuousClock.now + .seconds(seconds)
        while !done(), ContinuousClock.now < deadline { try? await Task.sleep(for: .milliseconds(10)) }
    }
}
