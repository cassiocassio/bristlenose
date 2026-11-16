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
    var isAvailable = true
    var running = false
    var startWorks = true
    var env: [String: String] = [:]
    private(set) var stopCalls = 0
    private(set) var startCalls = 0
    private weak var events: WhisperAcquisitionEvents?

    var isRunning: Bool { running }
    var runEnvironment: [String: String] { env }

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
        return (WhisperDownloadModel(defaults: defaults, makeAcquirer: { fake }), defaults)
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
        let m = WhisperDownloadModel(defaults: defaults, makeAcquirer: { current })
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
    @Test func theRunEnvironmentIsOnlyGivenWhileDownloading() {
        let fake = FakeAcquirer(); fake.env = ["_X": "1"]
        let (m, _) = model(fake)
        #expect(m.runEnvironment.isEmpty)
        m.downloadNow()
        #expect(m.runEnvironment == ["_X": "1"])
        fake.end(.failed(cause: nil))
        #expect(m.runEnvironment.isEmpty)
    }
}
