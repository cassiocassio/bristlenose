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

    @Test func whisperOnlyWithholdsTheHelper() {
        let env = BristlenoseShared.appleSpeechEnvironment(
            for: bundled, defaults: defaults(.whisperOnly), enabled: true, osAtLeast26: true, region: "GB")
        #expect(env["BRISTLENOSE_APPLE_SPEECH"] == "never")
        #expect(env["BRISTLENOSE_SPEECH_HELPER"] == nil)
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
        #expect(resolve(state) == .completedPartial)
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
