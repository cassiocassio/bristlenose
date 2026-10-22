import Foundation
import Testing

@testable import Bristlenose

/// A first run's speech-model download (R32). The run reports it as stage
/// `download` with the fraction of bytes received; the ring follows the bytes
/// while it runs and times the analysis alone once it ends. Before, the ~1.6 GB
/// download ran under a ring timed for the analysis, which climbed to near full
/// and sat there, and the row said only "Analysing".
///
/// Each test replays the events a first run writes, at the 1 Hz poll's cadence
/// where it matters: the poller re-applies the newest event every tick.
@Suite struct RunProgressDownloadTests {

    private let start = Date(timeIntervalSince1970: 1_000)

    private func at(_ p: PipelineProgress, _ t: Double, stage: String?,
                    fraction: Double? = nil, predicted: Double? = nil) -> PipelineProgress {
        RunProgressMath.apply(
            stage: stage, sessionsComplete: nil, sessionsTotal: nil,
            stageFraction: fraction, etaRemainingSeconds: predicted,
            predictedTotalSeconds: predicted, to: p, startedAt: start,
            now: start.addingTimeInterval(t)
        )
    }

    /// The analysis is estimated at 10 minutes; the download takes 15.
    private func throughDownload() -> PipelineProgress {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 2, stage: nil, predicted: 600)             // the estimate
        p = at(p, 10, stage: "download", fraction: 0)
        p = at(p, 450, stage: "download", fraction: 0.5)
        return p
    }

    @Test func duringTheDownloadTheRingFollowsTheBytesNotTheClock() {
        var p = throughDownload()
        #expect(p.ringFraction == 0.5)
        // Ten minutes later the poll still holds the half-way event: the ring
        // waits for bytes. Timed, it would be deep in the overrun creep.
        p = at(p, 1_050, stage: "download", fraction: 0.5)
        #expect(p.ringFraction == 0.5)
    }

    @Test func afterTheDownloadTheRingTimesTheAnalysisAlone() {
        var p = throughDownload()
        p = at(p, 900, stage: "download", fraction: 1)
        p = at(p, 901, stage: "transcribe", predicted: 600)
        #expect(p.ringFraction == 0)                         // a new phase
        // Five minutes into a ten-minute analysis: half the estimate, not the
        // 20 minutes since the run started (which would read as overrun). The
        // run sends predicted totals in this frame too: it leaves the download
        // out of them (`Pipeline._analysis_elapsed`).
        p = at(p, 1_201, stage: "transcribe", predicted: 600)
        let expected = 300.0 / 600 * RunProgressMath.expectedCompletionMark
        #expect(abs((p.ringFraction ?? -1) - expected) < 1e-9)
        #expect(p.timeBaseline == start.addingTimeInterval(901))
    }

    /// A first run on a new Mac has no timing history, so no estimate: after
    /// the download the ring is the spinner until a measured fraction arrives,
    /// not an empty ring frozen through transcription (R32 review).
    @Test func withNoEstimateTheAnalysisStartsAsASpinner() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 10, stage: "download", fraction: 0.4)
        p = at(p, 900, stage: "download", fraction: 1)
        p = at(p, 901, stage: "transcribe")
        #expect(p.ringFraction == nil)
        p = at(p, 1_200, stage: "transcribe", fraction: 0.5)   // first recording done
        #expect(p.ringFraction == 0.5)
    }

    @Test func aDownloadOfUnknownSizeIsASpinner() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 2, stage: nil, predicted: 600)
        p = at(p, 10, stage: "download", fraction: nil)
        #expect(p.ringFraction == nil)
    }

    @Test func aRunWithTheModelAlreadyHereIsTimedFromItsStart() {
        var p = PipelineProgress(startedAt: start)
        p = at(p, 2, stage: nil, predicted: 600)
        p = at(p, 300, stage: "transcribe", predicted: 600)
        #expect(p.timeBaseline == nil)
        let expected = 300.0 / 600 * RunProgressMath.expectedCompletionMark
        #expect(abs((p.ringFraction ?? -1) - expected) < 1e-9)
    }

    // MARK: - The row's words

    private func compose(stage: String?, complete: Int? = nil, total: Int? = nil,
                         eta: Double? = nil) -> String {
        let templates = [
            "desktop.chrome.pipeline.stage.download": "Downloading speech model",
            "desktop.chrome.pipeline.stage.transcribe": "Transcribing",
            "desktop.chrome.pipeline.sessionsCount": "{{complete}} of {{total}}",
            "desktop.chrome.pipeline.etaMinutes": "~{{count}} min left",
            "desktop.chrome.pipeline.analysing": "Analysing…",
        ]
        let localize: (String, [String: String]) -> String = { key, args in
            var s = templates[key] ?? key
            for (k, v) in args { s = s.replacingOccurrences(of: "{{\(k)}}", with: v) }
            return s
        }
        return RunProgressSubtitle.compose(
            stage: stage, sessionsComplete: complete, sessionsTotal: total,
            etaRemainingSeconds: eta, separator: " · ",
            localize: localize,
            pluralize: { key, n in localize(key, ["count": String(n)]) }
        )
    }

    @Test func theRowSaysItIsDownloadingAndNothingStale() {
        // The ETA carried in is the analysis estimate, frozen while the bytes
        // arrive; no session count belongs to the download either.
        #expect(compose(stage: "download", complete: 0, total: 8, eta: 600)
            == "Downloading speech model")
    }

    @Test func theDownloadVerbHasAKeyInEveryLocale() {
        #expect(RunProgressSubtitle.stageVerbKey("download")
            == "desktop.chrome.pipeline.stage.download")
    }
}
