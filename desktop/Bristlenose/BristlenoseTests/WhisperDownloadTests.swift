import Foundation
import Testing
@testable import Bristlenose

/// Apple-first transcription, Swift side (`docs/design-apple-first-transcription.md`):
/// the download job's line grammar and pacing, the environment the sidecar is
/// given, and the "Waiting for download" row. The Python side is
/// `tests/test_apple_speech.py`; the line grammar is Python's
/// (`bristlenose/preflight/whisper.py`).
@Suite struct WhisperDownloadLineTests {

    @Test func parsesEveryLineTheSidecarPrints() {
        #expect(WhisperDownloadLine.parse("@download-start mlx-community/whisper-large-v3-turbo 1614000000")
            == .start(repo: "mlx-community/whisper-large-v3-turbo", totalBytes: 1_614_000_000))
        #expect(WhisperDownloadLine.parse("@download 600000000 1614000000")
            == .progress(doneBytes: 600_000_000, totalBytes: 1_614_000_000))
        #expect(WhisperDownloadLine.parse("@download-done 3.9") == .done)
        #expect(WhisperDownloadLine.parse("@whisper-status cached org/model 74420620")
            == .status(.cached, repo: "org/model", bytesOnDisk: 74_420_620))
        #expect(WhisperDownloadLine.parse("@whisper-status partial org/model 0")
            == .status(.partial, repo: "org/model", bytesOnDisk: 0))
    }

    @Test func ignoresAnythingElse() {
        for line in ["", "Voice model ready", "@download x y", "@whisper-status sideways org/m 0",
                     "@download 1", "WARNING | something"] {
            #expect(WhisperDownloadLine.parse(line) == nil, "\(line)")
        }
    }
}

@Suite struct DownloadRateTests {

    @Test func noRateUntilTheWindowHasFilled() {
        var rate = DownloadRate()
        rate.add(time: 0, bytes: 0)
        rate.add(time: 4, bytes: 40_000_000)
        #expect(rate.bytesPerSecond == nil, "four seconds is a guess, not a rate")
        rate.add(time: 8, bytes: 80_000_000)
        #expect(rate.bytesPerSecond == 10_000_000)
    }

    @Test func theWindowSlides() {
        var rate = DownloadRate()
        for t in 0...20 { rate.add(time: TimeInterval(t), bytes: Int64(t) * 1_000_000) }
        // A burst at the end moves the rate; ancient samples do not hold it down.
        rate.add(time: 21, bytes: 100_000_000)
        let r = try! #require(rate.bytesPerSecond)
        #expect(r > 1_000_000 * 1.5)
        #expect(rate.samples.count < 12)
    }

    @Test func minutesRoundUpAndNeverFlickerUpward() {
        var rate = DownloadRate()
        rate.add(time: 0, bytes: 0)
        rate.add(time: 10, bytes: 100_000_000)  // 10 MB/s
        // 1.0 GB left at 10 MB/s = 100 s → 2 minutes, rounded up.
        #expect(rate.minutesLeft(done: 100_000_000, total: 1_100_000_000) == 2)
        // A small rise (2 → 3) is held; a fall is shown at once.
        rate.add(time: 20, bytes: 175_000_000)  // slows to 7.5 MB/s: 123 s, so 3
        #expect(rate.minutesLeft(done: 175_000_000, total: 1_100_000_000) == 2)
        rate.add(time: 30, bytes: 1_000_000_000)
        #expect(rate.minutesLeft(done: 1_000_000_000, total: 1_100_000_000) == 1)
    }

    @Test func aRestartFromZeroForgetsTheDeadAttemptsEstimate() {
        var rate = DownloadRate()
        rate.add(time: 0, bytes: 0)
        rate.add(time: 10, bytes: 1_000_000_000)  // 100 MB/s, nearly done
        #expect(rate.minutesLeft(done: 1_000_000_000, total: 1_100_000_000) == 1)
        // The network dropped; the job started again at zero.
        rate.add(time: 40, bytes: 0)
        #expect(rate.bytesPerSecond == nil, "a restart has no rate until its own window fills")
        #expect(rate.shownMinutes == nil, "and no minutes left carried over from the dead attempt")
        rate.add(time: 50, bytes: 100_000_000)  // 10 MB/s now
        // 1.0 GB left at 10 MB/s: the fresh figure, not the held "1".
        #expect(rate.minutesLeft(done: 100_000_000, total: 1_100_000_000) == 2)
    }

    @Test func aLargeRiseIsShown() {
        var rate = DownloadRate()
        rate.add(time: 0, bytes: 0)
        rate.add(time: 10, bytes: 100_000_000)
        #expect(rate.minutesLeft(done: 100_000_000, total: 1_100_000_000) == 2)
        rate.add(time: 20, bytes: 102_000_000)  // stalls
        let after = rate.minutesLeft(done: 102_000_000, total: 1_100_000_000)
        #expect((after ?? 0) >= 4)
    }

    @Test func noTimeWithoutARate() {
        var rate = DownloadRate()
        rate.add(time: 0, bytes: 0)
        #expect(rate.minutesLeft(done: 0, total: 1_000) == nil)
    }
}

@Suite struct WhisperProgressLineTests {

    /// Foundation composes the line (§3 H; measured 18 Oct 2026). Assert its
    /// shape, not its words: the words are Foundation's, in the app's language.
    @Test func bytesAloneUntilARateIsKnown() {
        let bare = WhisperDownloadModel.progressLine(
            done: 600_000_000, total: 1_614_000_000, bytesPerSecond: nil, minutesLeft: nil)
        let full = WhisperDownloadModel.progressLine(
            done: 600_000_000, total: 1_614_000_000, bytesPerSecond: 10_000_000, minutesLeft: 2)
        #expect(!bare.isEmpty)
        #expect(full.hasPrefix(bare), "the rate and time are added to the bytes, never instead of them")
        #expect(full.count > bare.count)
    }

    /// Build 6532: "Zero KB" read beside a bar that was already moving, before any byte or
    /// total had been reported. Nothing known says nothing.
    @Test func nothingReportedYetIsNotZeroKB() {
        #expect(WhisperDownloadModel.progressLine(
            done: 0, total: 0, bytesPerSecond: nil, minutesLeft: nil).isEmpty)
    }

    @Test func aRunDefersWhenTheDownloadWasDeclinedOrTheQuestionIsStillToCome() {
        typealias M = WhisperDownloadModel
        func defer_(_ build: Bool = true, pack: Bool = true, stopped: Bool, answered: Bool,
                    reachable: Bool) -> Bool {
            M.runMustDefer(whisperInBuild: build, packModelChosen: pack, stoppedByUser: stopped,
                           hasAnswered: answered, questionReachable: reachable)
        }
        #expect(defer_(stopped: true, answered: true, reachable: false))   // Not Now / Stop
        #expect(defer_(stopped: false, answered: false, reachable: true))  // question to come
        // The question can never be put (little disk, no sidecar): nothing waits for ever.
        #expect(!defer_(stopped: false, answered: false, reachable: false))
        #expect(!defer_(stopped: false, answered: true, reachable: true))  // said Download
        #expect(!defer_(false, stopped: true, answered: false, reachable: true))  // no Whisper
        // Another model is Python's to fetch, whatever was said about turbo.
        #expect(!defer_(pack: false, stopped: true, answered: true, reachable: true))
    }

    @Test func theQuestionIsReachableOnlyWhenItCanBePut() {
        typealias M = WhisperDownloadModel
        func reach(ask: Bool = true, sidecar: Bool = true, consent: Bool = true,
                   free: Int64? = nil) -> Bool {
            M.questionReachable(askIsWired: ask, sidecarPresent: sidecar, hasConsent: consent,
                                freeBytes: free)
        }
        #expect(reach())
        #expect(reach(free: M.autoStartFloorBytes))
        #expect(!reach(free: M.autoStartFloorBytes - 1))
        #expect(!reach(ask: false) && !reach(sidecar: false) && !reach(consent: false))
    }

    @Test func theTimeLeftGoesOnItsOwnLineWithoutTheDash() {
        #expect(WhisperDownloadModel.timeLeftOnItsOwnLine(
            "789.0 MB of 1.61 GB (10.0 MB/s) \u{2014} About 1 minute, 23 seconds remaining")
            == "789.0 MB of 1.61 GB (10.0 MB/s)\nAbout 1 minute, 23 seconds remaining")
        #expect(WhisperDownloadModel.timeLeftOnItsOwnLine("600.0 MB of 1.61 GB") == "600.0 MB of 1.61 GB",
                "a line with no spaced dash is left as Foundation wrote it")
    }

    @Test func noTotalFromTheServerStillCountsBytes() {
        let line = WhisperDownloadModel.progressLine(
            done: 600_000_000, total: 0, bytesPerSecond: nil, minutesLeft: nil)
        #expect(!line.isEmpty, "an unknown total must not read as nothing downloaded")
    }
}

@Suite struct AppleSpeechEnvironmentTests {

    private let bundled = SidecarMode.bundled(path: URL(fileURLWithPath:
        "/Applications/Bristlenose.app/Contents/Resources/bristlenose-sidecar/bristlenose-sidecar"))

    private func defaults(_ choice: TranscriptionEngineChoice?) -> UserDefaults {
        let d = UserDefaults(suiteName: "WhisperDownloadTests-\(UUID().uuidString)")!
        if let choice { d.set(choice.rawValue, forKey: TranscriptionEngineChoice.key) }
        return d
    }

    @Test func aFallbackUILanguageIsNotTheResearchers() {
        // A Greek Mac: the app renders English because it cannot render Greek.
        #expect(!BristlenoseShared.uiLanguageIsResearchers(
            resolved: "en", explicit: nil, preferred: ["el-GR"]))
        #expect(BristlenoseShared.uiLanguageIsResearchers(
            resolved: "en", explicit: nil, preferred: ["el-GR", "en-GB"]))
        #expect(BristlenoseShared.uiLanguageIsResearchers(
            resolved: "de", explicit: "de", preferred: ["el-GR"]))
        let env = BristlenoseShared.appleSpeechEnvironment(
            for: bundled, defaults: defaults(nil), enabled: true, osAtLeast26: true,
            region: "GR", uiLanguageMatched: false)
        #expect(env["BRISTLENOSE_SPEECH_UI_MATCHED"] == nil)
    }

    @Test func nothingWhileTheFlagIsOff() {
        #expect(BristlenoseShared.appleSpeechEnvironment(
            for: bundled, defaults: defaults(nil), enabled: false, osAtLeast26: true, region: "GB"
        ).isEmpty)
    }

    @Test func theBundledSidecarGetsTheHelperBesideItsResources() {
        let env = BristlenoseShared.appleSpeechEnvironment(
            for: bundled, defaults: defaults(nil), enabled: true, osAtLeast26: true, region: "GB",
            uiLanguageMatched: true)
        #expect(env["BRISTLENOSE_SPEECH_UI_MATCHED"] == "1")
        #expect(env["BRISTLENOSE_EXPERIMENTAL_APPLE_SPEECH"] == "1")
        #expect(env["BRISTLENOSE_APPLE_SPEECH"] == "until-whisper")
        #expect(env["BRISTLENOSE_SPEECH_REGION"] == "GB")
        #expect(env["BRISTLENOSE_SPEECH_HELPER"]
            == "/Applications/Bristlenose.app/Contents/Helpers/bristlenose-speech")
    }

    /// *Whisper only* was removed. A researcher who had chosen it must not be
    /// left without Apple's model as a stand-in: the stored value now reads as
    /// the default.
    @Test func aStoredWhisperOnlyReadsAsTheDefault() {
        let suite = UserDefaults(suiteName: "WhisperDownloadTests.legacy.\(UUID().uuidString)")!
        suite.set("whisperOnly", forKey: TranscriptionEngineChoice.key)
        #expect(TranscriptionEngineChoice.current(suite) == .whisperWhenReady)
        let env = BristlenoseShared.appleSpeechEnvironment(
            for: bundled, defaults: suite, enabled: true, osAtLeast26: true, region: "GB")
        #expect(env["BRISTLENOSE_APPLE_SPEECH"] == "until-whisper")
        #expect(env["BRISTLENOSE_SPEECH_HELPER"] != nil)
    }

    @Test func appleMapsToPrefer() {
        let env = BristlenoseShared.appleSpeechEnvironment(
            for: bundled, defaults: defaults(.apple), enabled: true, osAtLeast26: true, region: nil)
        #expect(env["BRISTLENOSE_APPLE_SPEECH"] == "prefer")
        #expect(env["BRISTLENOSE_SPEECH_REGION"] == nil)
    }

    @Test func noHelperBelowMacOS26OrUnderADevSidecar() {
        let old = BristlenoseShared.appleSpeechEnvironment(
            for: bundled, defaults: defaults(nil), enabled: true, osAtLeast26: false, region: "GB")
        #expect(old["BRISTLENOSE_SPEECH_HELPER"] == nil)
        // The helper is signed sandbox + inherit; an unsandboxed dev sidecar
        // would launch it straight into exit 133.
        let dev = BristlenoseShared.appleSpeechEnvironment(
            for: .devSidecar(path: URL(fileURLWithPath: "/repo/.venv/bin/bristlenose")),
            defaults: defaults(nil), enabled: true, osAtLeast26: true, region: "GB")
        #expect(dev["BRISTLENOSE_SPEECH_HELPER"] == nil)
    }
}

@Suite struct WaitingForWhisperRowTests {

    private func summary(_ categories: [String]) throws -> PipelineSummary {
        let failed = categories.enumerated().map { i, c in
            #"{"session_id": "s\#(i + 1)", "cause": {"category": "\#(c)", "message": "m"}}"#
        }.joined(separator: ",")
        let json = #"{"transcripts": {"attempted": 2, "succeeded": 0, "failed": [\#(failed)]}}"#
        return try JSONDecoder().decode(PipelineSummary.self, from: Data(json.utf8))
    }

    private func resolve(_ state: PipelineState) -> SubtitleVariant {
        ProjectSubtitle.resolve(
            availability: .ready, pipelineState: state, isStopping: false,
            addingCount: nil, copy: nil, importBatch: nil,
            lastRunAt: nil, missingCount: 0, unanalysedCount: 0)
    }

    @Test func everyFailureDeferredReadsAsWaiting() throws {
        let state = PipelineState.completedPartial(summary: try summary(["deferred", "deferred"]))
        #expect(resolve(state) == .waitingForWhisper)
        #expect(PipelineRunner.isWaitingForWhisper(state))
    }

    @Test func aRealFailureBesideADeferralKeepsTheWarning() throws {
        let state = PipelineState.completedPartial(summary: try summary(["deferred", "whisper"]))
        #expect(resolve(state) == .completedPartial(analysed: nil))
        // The re-run is still owed for the deferred one.
        #expect(PipelineRunner.isWaitingForWhisper(state))
    }

    @Test func noDeferralIsNotWaiting() throws {
        let state = PipelineState.completedPartial(summary: try summary(["whisper"]))
        #expect(!PipelineRunner.isWaitingForWhisper(state))
        #expect(!PipelineRunner.isWaitingForWhisper(.ready(Date())))
    }

    @Test func waitingIsInfoNoGlyphNoDoor() {
        #expect(SubtitleVariant.waitingForWhisper.glyphKind == nil)
        #expect(SubtitleVariant.waitingForWhisper.glyphAction == .none)
    }
}

/// The download starts in the background from launch (owner, 18 and 22 Oct
/// 2026): only after the AI disclosure, never over a remembered Stop, only for a
/// model missing or partial, and only with 10 GB free (unknown starts).
@Suite struct WhisperAutoStartTests {
    typealias Model = WhisperDownloadModel
    let plenty: Int64 = 100_000_000_000

    @Test func startsWhenMissingOrPartialAndThereIsRoom() {
        for phase in [Model.Phase.missing, .partial] {
            #expect(Model.autoStart(phase: phase, freeBytes: plenty, stoppedByUser: false, hasConsent: true, runIsLive: false, hasAnswered: true, whisperInBuild: true) == .start)
        }
    }

    @Test func waitsForTheDisclosure() {
        #expect(Model.autoStart(phase: .missing, freeBytes: plenty, stoppedByUser: false, hasConsent: false, runIsLive: false, hasAnswered: true, whisperInBuild: true) != .start)
    }

    @Test func notWhileAnAnalysisRuns() {
        #expect(Model.autoStart(phase: .missing, freeBytes: plenty, stoppedByUser: false, hasConsent: true, runIsLive: true, hasAnswered: true, whisperInBuild: true) != .start)
    }

    @Test func aStopIsRemembered() {
        #expect(Model.autoStart(phase: .missing, freeBytes: plenty, stoppedByUser: true, hasConsent: true, runIsLive: false, hasAnswered: true, whisperInBuild: true) != .start)
    }

    @Test func neverBelowTheFloorAndExactlyAtItIsEnough() {
        let floor = Model.autoStartFloorBytes
        #expect(floor == 10_000_000_000)
        #expect(Model.autoStart(phase: .missing, freeBytes: floor - 1, stoppedByUser: false, hasConsent: true, runIsLive: false, hasAnswered: true, whisperInBuild: true) != .start)
        #expect(Model.autoStart(phase: .missing, freeBytes: floor, stoppedByUser: false, hasConsent: true, runIsLive: false, hasAnswered: true, whisperInBuild: true) == .start)
    }

    @Test func unknownFreeSpaceStarts() {
        #expect(Model.autoStart(phase: .missing, freeBytes: nil, stoppedByUser: false, hasConsent: true, runIsLive: false, hasAnswered: true, whisperInBuild: true) == .start)
    }

    @Test func nothingToDoOnDiskDownloadingFailedOrUnasked() {
        for phase in [Model.Phase.onDisk, .downloading, .failed, .unknown] {
            #expect(Model.autoStart(phase: phase, freeBytes: plenty, stoppedByUser: false, hasConsent: true, runIsLive: false, hasAnswered: true, whisperInBuild: true) != .start, "\(phase)")
        }
    }

    /// The size question (App Review 4.2.3): asked, once, wherever the app
    /// would otherwise start by itself; never where it would not.
    @Test func asksFirstUntilTheResearcherHasAnswered() {
        func decide(_ phase: Model.Phase = .missing, stopped: Bool = false, consent: Bool = true,
                    live: Bool = false, answered: Bool, inBuild: Bool = true) -> Model.AutoStart {
            Model.autoStart(phase: phase, freeBytes: plenty, stoppedByUser: stopped, hasConsent: consent,
                            runIsLive: live, hasAnswered: answered, whisperInBuild: inBuild)
        }
        // Not asked yet: ask, for a model missing or partial.
        #expect(decide(answered: false) == .ask)
        #expect(decide(.partial, answered: false) == .ask)
        // Download was the answer: start, as before.
        #expect(decide(answered: true) == .start)
        // Not Now was the answer: it is a remembered Stop, so nothing.
        #expect(decide(stopped: true, answered: true) == .nothing)
        // Never asked where the app would not start: before the disclosure,
        // during a run, with Whisper on disk, below the floor.
        #expect(decide(consent: false, answered: false) == .nothing)
        #expect(decide(live: true, answered: false) == .nothing)
        #expect(decide(.onDisk, answered: false) == .nothing)
        #expect(Model.autoStart(phase: .missing, freeBytes: Model.autoStartFloorBytes - 1, stoppedByUser: false,
                                hasConsent: true, runIsLive: false, hasAnswered: false, whisperInBuild: true) == .nothing)
        // A build without Whisper neither asks nor starts.
        #expect(decide(answered: false, inBuild: false) == .nothing)
        #expect(decide(answered: true, inBuild: false) == .nothing)
    }

    @Test func aRunIsToldOnlyWhileTheDownloadRuns() {
        #expect(Model.whisperFetchEnvironment(pid: nil).isEmpty)
        #expect(Model.whisperFetchEnvironment(pid: 4321) == ["_BRISTLENOSE_WHISPER_FETCH_PID": "4321"])
    }
}


/// Apple-first transcription graduated on 22 Oct 2026: on by default, and the
/// defaults key is only a kill switch for a tester who hits trouble.
@Suite struct AppleSpeechSwitchTests {
    private func defaults() -> UserDefaults {
        let name = "AppleSpeechSwitchTests-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    @Test func onWhenNothingIsWritten() {
        #expect(BristlenoseFlags.appleSpeech(in: defaults()))
    }

    @Test func writtenOffIsTheKillSwitch() {
        let d = defaults()
        d.set(false, forKey: BristlenoseFlags.appleSpeechKey)
        #expect(!BristlenoseFlags.appleSpeech(in: d))
    }
}

// MARK: - Why a download failed

/// The messages are the ones the real sidecar wrote on clean macOS 15, 26 and 27 guests
/// (30 Oct 2026), not invented ones.
@Suite struct WhisperFailureCauseTests {
    private func cause(_ line: String) -> WhisperFailureCause? {
        WhisperFailureCause.classify([line])
    }

    @Test func aFullDiskIsNamedWhetherCaughtBeforeOrDuringTheDownload() {
        #expect(cause("Disk full: the Whisper model needs ~2.6 GB and only ~1.8 GB is free there, "
                      + "not counting space macOS can clear (~/.cache/huggingface/hub). "
                      + "Free some space and try again.") == .disk)
        #expect(cause("huggingface_hub snapshot_download 'mlx-community/whisper-large-v3-turbo' "
                      + "failed: [Errno 28] No space left on device") == .disk)
    }

    @Test func aDroppedConnectionIsNamed() {
        #expect(cause("huggingface_hub snapshot_download 'x' failed: "
                      + "[Errno 8] nodename nor servname provided, or not known") == .network)
        #expect(cause("snapshot_download 'x' failed: Connection reset by peer (os error 54)") == .network)
        #expect(cause("The cached snapshot for 'x' (revision 'main') is incomplete: "
                      + "1 file(s) are missing") == .network)
    }

    @Test func aCertificateIsNotMistakenForADroppedConnection() {
        // Arrives wrapped in "ConnectError", which is a network word.
        #expect(cause("huggingface_hub snapshot_download 'x' failed: Got: ConnectError: "
                      + "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
                      + "self-signed certificate in certificate chain (_ssl.c:1010)") == .certificate)
    }

    @Test func aFullDiskWinsOverAWordInTheSamePath() {
        // "huggingface" paths carry no network word, but order is the contract: disk, certificate, network.
        #expect(WhisperFailureCause.classify([
            "[Errno 28] No space left on device", "error sending request",
        ]) == .disk)
    }

    @Test func whatItCannotReadItLeavesAlone() {
        #expect(cause("snapshot_download 'x' failed: [Errno 13] Permission denied: '/Users/a/ro/hf'") == nil)
        #expect(cause("snapshot_download 'x' failed: Got: ConnectError: [Errno 61] Connection refused") == nil)
        #expect(cause("Expecting value: line 1 column 1 (char 0)") == nil)
        #expect(WhisperFailureCause.classify([]) == nil)
    }

    @Test func theLineShownIsTheCauseWhenThereIsOneAndTheOldSentenceWhenThereIsNot() {
        #expect(WhisperFailureCause.lineKey(for: .disk) == "desktop.modelDownload.causeDisk")
        #expect(WhisperFailureCause.lineKey(for: nil) == "desktop.transcriptionSettings.whisperFailed")
    }
}

/// The size question's strings exist in English and the size reaches the body.
/// The other 20 locales are translated (17 Nov 2026), not verified by native speakers.
@Suite @MainActor struct WhisperAskStringsTests {
    @Test func theQuestionReadsInEnglish() throws {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        let size = i18n.t("desktop.modelDownload.askSize")
        #expect(size == "1.6 GB")
        #expect(i18n.t("desktop.modelDownload.askBody", ["size": size]).hasPrefix("About 1.6 GB."))
        for key in ["askTitle", "askDownload", "askNotNow"] {
            let full = "desktop.modelDownload.\(key)"
            #expect(i18n.t(full) != full, "\(key)")
        }
    }
}

/// Which Whisper controls Settings ▸ Transcription carries: none at all in a
/// build that ships no Whisper, whatever the Mac could otherwise offer.
@Suite struct TranscriptionPaneLayoutTests {
    @Test func noWhisperBuildOffersNoWhisperControl() {
        #expect(TranscriptionPaneLayout.of(appleSpeech: true, whisperInBuild: false) == .noWhisper)
        #expect(TranscriptionPaneLayout.of(appleSpeech: false, whisperInBuild: false) == .noWhisper)
    }

    @Test func withWhisperTheChoiceFollowsApplesModel() {
        #expect(TranscriptionPaneLayout.of(appleSpeech: true, whisperInBuild: true) == .engineChoice)
        #expect(TranscriptionPaneLayout.of(appleSpeech: false, whisperInBuild: true) == .whisperOnly)
    }
}

/// The re-run owed to a project waiting for Whisper: once Whisper is on disk,
/// once per project per process, and whatever deferred it (Apple's model or
/// a run that met the app's own download), so on macOS 15 too.
@Suite struct WhisperRerunTests {
    let a = UUID(), b = UUID()

    @Test func owedOnceWhisperIsOnDisk() {
        #expect(PipelineRunner.owesWhisperRerun(whisperPhase: .onDisk, waiting: [a], alreadyRerun: []))
        for phase in [WhisperDownloadModel.Phase.downloading, .missing, .partial, .failed, .unknown] {
            #expect(!PipelineRunner.owesWhisperRerun(whisperPhase: phase, waiting: [a], alreadyRerun: []), "\(phase)")
        }
    }

    @Test func onceEachAndNothingWithNobodyWaiting() {
        #expect(!PipelineRunner.owesWhisperRerun(whisperPhase: .onDisk, waiting: [a], alreadyRerun: [a]))
        #expect(PipelineRunner.owesWhisperRerun(whisperPhase: .onDisk, waiting: [a, b], alreadyRerun: [a]))
        #expect(!PipelineRunner.owesWhisperRerun(whisperPhase: .onDisk, waiting: [], alreadyRerun: []))
    }
}

/// The transcription model as a state machine. States: the model's phase, plus what is
/// remembered (answered, stopped) and what is read live (consent, free space, a run). Every
/// decision the app makes about the model is a pure function of those, so the whole product is
/// enumerated here and the invariants that must hold in every cell are asserted; the picture is
/// in `docs/design-whisper-delivery.md` § State machine.
@MainActor @Suite struct WhisperStateMachineTests {
    typealias M = WhisperDownloadModel
    static let phases: [M.Phase] = [.unknown, .missing, .partial, .downloading, .onDisk, .failed]
    static let frees: [Int64?] = [nil, 1_000_000_000, 9_999_999_999, 10_000_000_000, 100_000_000_000]

    /// Every cell of the product, with the three decisions made in it.
    private func forEachCell(_ body: (_ phase: M.Phase, _ free: Int64?, _ stopped: Bool, _ consent: Bool,
                                      _ run: Bool, _ answered: Bool, _ low: Bool, _ auto: M.AutoStart,
                                      _ mustDefer: Bool) -> Void) {
        for phase in Self.phases { for free in Self.frees { for stopped in [false, true] {
            for consent in [false, true] { for run in [false, true] { for answered in [false, true] {
                let low = M.lowDiskBlocked(phase: phase, freeBytes: free, stoppedByUser: stopped,
                                           hasConsent: consent, whisperInBuild: true)
                let auto = M.autoStart(phase: phase, freeBytes: free, stoppedByUser: stopped,
                                       hasConsent: consent, runIsLive: run, hasAnswered: answered,
                                       whisperInBuild: true)
                let reachable = M.questionReachable(askIsWired: true, sidecarPresent: true,
                                                    hasConsent: consent, freeBytes: free)
                let mustDefer = M.runMustDefer(whisperInBuild: true, packModelChosen: true,
                                               stoppedByUser: stopped, hasAnswered: answered,
                                               questionReachable: reachable,
                                               noRoomToFetch: M.noRoomToFetch(phase: phase, freeBytes: free, hasConsent: consent, whisperInBuild: true))
                body(phase, free, stopped, consent, run, answered, low, auto, mustDefer)
            } } } } } }
    }

    /// The warning exists exactly when room alone is what stops the app: never beside a start or
    /// a question, never over the researcher's own Not Now or Stop, never before consent, never
    /// for a model that is here, coming, or failed (the failure has its own pill).
    @Test func theWarningIsTheCaseTheFloorAloneBlocks() {
        forEachCell { phase, free, stopped, consent, run, _, low, auto, _ in
            if low {
                #expect(auto == .nothing, "never a warning beside an ask or a start: \(phase) \(String(describing: free))")
                #expect(!stopped && consent, "a decline or a missing disclosure is not a warning")
                #expect(phase == .missing || phase == .partial)
            }
            if consent && !stopped && !run && (phase == .missing || phase == .partial) {
                #expect((auto == .nothing) == low, "nothing happens only because of the floor, and then it says so")
            }
        }
    }

    /// A run never fetches into a full disk (whatever the phase says: unknown while the launch
    /// probe is out, or a failure left over), and never waits without a way out: whenever it defers
    /// for any reason other than the researcher's own Stop, an exit exists that the researcher can
    /// see (the warning pill, whose button opens Download Now; or the size question).
    @Test func aRunWaitsOnlyWhenThereIsAWayOut() {
        forEachCell { phase, free, stopped, consent, _, answered, low, _, mustDefer in
            let noRoom = M.noRoomToFetch(phase: phase, freeBytes: free, hasConsent: consent, whisperInBuild: true)
            if noRoom { #expect(mustDefer, "no fetch into a full disk: \(phase) \(String(describing: free))") }
            if low { #expect(noRoom, "the warning always holds the run") }
            if stopped { #expect(mustDefer) }
            if mustDefer && !stopped && !noRoom {
                #expect(!answered && consent && (free == nil || free! >= M.autoStartFloorBytes),
                        "the only other wait is for a question that can be put")
            }
            // Nothing is held for a model that is here or on its way.
            if phase == .onDisk || phase == .downloading { #expect(!noRoom) }
        }
    }

    /// An unanswered or unfinished probe, or a leftover failure, is not licence to fetch into a
    /// full disk behind the pill.
    @Test func aRunOnAFullDiskDefersInEveryPhaseButHereAndComing() {
        for phase in [M.Phase.unknown, .missing, .partial, .failed] {
            let m = model(free: 1_000_000_000)
            m.debugApply(phase)
            #expect(m.runEnvironment == M.hostOwnsEnvironment, "\(phase)")
        }
        for phase in [M.Phase.onDisk, .downloading] {
            let m = model(free: 1_000_000_000)
            m.debugApply(phase)
            #expect(m.runEnvironment != M.hostOwnsEnvironment, "\(phase)")
        }
    }

    /// Only the app's own model is the app's to warn about; another is Python's to fetch.
    @Test func noWarningForAnotherModel() {
        let defaults = scratchDefaults()
        let m = model(free: 1_000_000_000, defaults: defaults)
        m.debugApply(.missing)
        #expect(m.lowDisk)
        defaults.set("small", forKey: "whisperModel")
        m.updateLowDisk()
        #expect(!m.lowDisk)
    }

    @Test func theFloorIsExactlyTenGigabytes() {
        #expect(M.autoStartFloorBytes == 10_000_000_000)
        #expect(M.lowDiskBlocked(phase: .missing, freeBytes: 9_999_999_999, stoppedByUser: false, hasConsent: true, whisperInBuild: true))
        #expect(!M.lowDiskBlocked(phase: .missing, freeBytes: 10_000_000_000, stoppedByUser: false, hasConsent: true, whisperInBuild: true))
        #expect(!M.lowDiskBlocked(phase: .missing, freeBytes: nil, stoppedByUser: false, hasConsent: true, whisperInBuild: true))
        #expect(!M.lowDiskBlocked(phase: .missing, freeBytes: 0, stoppedByUser: false, hasConsent: true, whisperInBuild: false))
    }

    /// A full disk is not retried; every other cause is, and each has its own title.
    @Test func eachCauseHasATitleAndOnlyADiskHasNoRetry() {
        #expect(WhisperFailureCause.titleKey(for: .network) == "desktop.modelDownload.causeNetworkTitle")
        #expect(WhisperFailureCause.titleKey(for: .certificate) == "desktop.modelDownload.causeCertificateTitle")
        #expect(WhisperFailureCause.titleKey(for: .disk) == "desktop.modelDownload.lowDiskTitle")
        #expect(WhisperFailureCause.titleKey(for: nil) == "desktop.modelDownload.failedTitle")
        #expect(!WhisperFailureCause.disk.retryCanWork)
        #expect(WhisperFailureCause.network.retryCanWork && WhisperFailureCause.certificate.retryCanWork)
    }

    private func scratchDefaults() -> UserDefaults {
        let suite = "whisper-state-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: suite)!
        defaults.removePersistentDomain(forName: suite)
        return defaults
    }

    private func model(free: Int64?, consent: Bool = true, defaults: UserDefaults? = nil,
                       fake: FakeAcquirer? = nil) -> M {
        let acquirer = fake ?? FakeAcquirer()
        let m = M(defaults: defaults ?? scratchDefaults(), makeAcquirer: { _ in acquirer })
        m.freeDiskBytes = { free }
        m.hasAIConsent = { consent }
        return m
    }

    @Test func theWarningFollowsTheDiskAndClearsWhenRoomAppears() {
        var free: Int64? = 3_000_000_000
        let m = model(free: free)
        m.freeDiskBytes = { free }
        m.debugApply(.missing)
        #expect(m.lowDisk && m.isPillVisible)
        free = 50_000_000_000
        m.updateLowDisk()
        #expect(!m.lowDisk && !m.isPillVisible)
    }

    @Test func noWarningBeforeConsentOrOnceTheModelIsHere() {
        let noConsent = model(free: 1, consent: false)
        noConsent.debugApply(.missing)
        #expect(!noConsent.lowDisk)
        let here = model(free: 1)
        here.debugApply(.onDisk)
        #expect(!here.lowDisk && !here.isPillVisible)
        here.debugApply(.missing)
        #expect(here.lowDisk)
        here.debugApply(.downloading)
        #expect(!here.lowDisk && here.isPillVisible)  // the progress pill, not the warning
    }

    @Test func aRunHeldByTheWarningIsToldToWait() {
        let m = model(free: 1_000_000_000)
        m.debugApply(.missing)
        #expect(m.runEnvironment == M.hostOwnsEnvironment)
    }

    /// Room appears: the launch decision is made again, so the researcher who frees space is
    /// asked, or the download they already agreed to begins, with no relaunch.
    @Test func whatTheLaunchCheckWouldDoWithRoomIsDoneWhenRoomAppears() async {
        let defaults = scratchDefaults()
        let fake = FakeAcquirer()
        var free: Int64? = 3_000_000_000
        let m = model(free: free, defaults: defaults, fake: fake)
        m.freeDiskBytes = { free }
        defaults.set(true, forKey: "whisperDownloadAsked")
        m.debugApply(.missing)
        await m.applyAutoStart()
        #expect(fake.startCalls == 0, "no room: nothing starts, the pill says why")
        free = 50_000_000_000
        await m.applyAutoStart()
        #expect(fake.startCalls == 1, "room: the download the researcher agreed to begins")
    }

    @Test func noRoomIsNotAnAnswerSoTheQuestionWaitsForRoom() async {
        var asked = 0
        let m = model(free: 3_000_000_000)
        m.askToDownload = { asked += 1; return false }
        m.debugApply(.missing)
        await m.applyAutoStart()
        #expect(asked == 0)
        m.freeDiskBytes = { 50_000_000_000 }
        await m.applyAutoStart()
        #expect(asked == 1)
    }

    /// An Apple-engine run is not a reason to start 1.6 GB into a full disk.
    @Test func aRunDoesNotStartTheDownloadIntoAFullDisk() {
        guard BristlenoseFlags.appleSpeechAvailable else { return }
        let defaults = scratchDefaults()
        defaults.set(true, forKey: "whisperDownloadAsked")
        let fake = FakeAcquirer()
        let m = model(free: 3_000_000_000, defaults: defaults, fake: fake)
        m.debugApply(.partial)
        m.startIfNeeded()
        #expect(fake.startCalls == 0)
        m.freeDiskBytes = { 50_000_000_000 }
        m.startIfNeeded()
        #expect(fake.startCalls == 1)
    }
}
