import Foundation
import Testing

@testable import Bristlenose

// §5c without a tenant: Meet's entries belong to the *call*; a recording is a
// sub-interval of it. These pin the slicing, the clock, and the four ways an
// assembled transcript is refused rather than written — each of which would
// otherwise read as a perfectly good transcript with every clip δ out, or half
// a conversation marked Imported.
//
// NOT YET RUN ON A MAC — written in a cloud session with no Xcode (1 Oct 2026).

@Suite("Meet transcript assembly")
struct MeetTranscriptAssemblyTests {

    private let t0 = Date(timeIntervalSince1970: 1_759_300_000)

    private func entry(_ from: TimeInterval, _ to: TimeInterval,
                       by participant: String? = "conferenceRecords/r/participants/p1",
                       text: String = "Hello", language: String? = "en-US") -> MeetTranscriptAssembly.Entry {
        MeetTranscriptAssembly.Entry(start: t0.addingTimeInterval(from), end: t0.addingTimeInterval(to),
                                     participant: participant, text: text, language: language)
    }

    private let names = ["conferenceRecords/r/participants/p1": "Priya Shah",
                         "conferenceRecords/r/participants/p2": "Tom Okafor"]

    // MARK: assemble

    @Test("Cues land on the recording's clock, named and sorted")
    func cuesOnTheRecordingsClock() {
        let result = MeetTranscriptAssembly.assemble(
            entries: [entry(30, 34, by: "conferenceRecords/r/participants/p2", text: "Second"),
                      entry(-12.4, -2, text: "Before the button"),
                      entry(2, 6, text: "First")],
            names: names, recordingStart: t0, recordingEnd: nil)
        #expect(result.cues.map(\.text) == ["Before the button", "First", "Second"])
        #expect(result.cues.map(\.speaker) == ["Priya Shah", "Priya Shah", "Tom Okafor"])
        #expect(result.cues[0].start == -12.4, "not yet clamped — the rebase does that")
        #expect(result.referencedSpeakers == 3)
        #expect(result.unresolvedSpeakers == 0)
        #expect(result.language == "en-US")
    }

    /// A stop-and-restart recording shares one transcript: the second
    /// recording's cues must not be written into the first recording's file.
    @Test("With the recording's end known, later entries are sliced away and counted")
    func slicesToTheRecordingWindow() {
        let end = t0.addingTimeInterval(600)
        let result = MeetTranscriptAssembly.assemble(
            entries: [entry(10, 20), entry(590, 605, text: "straddles"), entry(600, 610, text: "after"),
                      entry(900, 950, text: "much later")],
            names: names, recordingStart: t0, recordingEnd: end)
        #expect(result.cues.map(\.text) == ["Hello", "straddles"], "a cue that starts inside stays; the clamp trims it")
        #expect(result.slicedAfterEnd == 2)
    }

    @Test("Without an end nothing is sliced")
    func noEndNoSlice() {
        let result = MeetTranscriptAssembly.assemble(
            entries: [entry(10, 20), entry(9_000, 9_010)],
            names: names, recordingStart: t0, recordingEnd: nil)
        #expect(result.cues.count == 2)
        #expect(result.slicedAfterEnd == 0)
    }

    @Test("The language is the most common code among the kept entries")
    func languageIsTheMajority() {
        let result = MeetTranscriptAssembly.assemble(
            entries: [entry(0, 1, language: "pt-BR"), entry(1, 2, language: "pt-BR"),
                      entry(2, 3, language: "en-US"), entry(3, 4, language: nil), entry(4, 5, language: "")],
            names: names, recordingStart: t0, recordingEnd: nil)
        #expect(result.language == "pt-BR")
    }

    @Test("An entry naming a participant nobody listed is counted unresolved, not invented")
    func unresolvedSpeakersAreCounted() {
        let result = MeetTranscriptAssembly.assemble(
            entries: [entry(0, 1, by: "conferenceRecords/r/participants/ghost"),
                      entry(1, 2, by: nil),
                      entry(2, 3)],
            names: names, recordingStart: t0, recordingEnd: nil)
        #expect(result.cues.map(\.speaker) == [nil, nil, "Priya Shah"])
        #expect(result.referencedSpeakers == 2, "the unnamed entry referenced nobody")
        #expect(result.unresolvedSpeakers == 1)
    }

    // MARK: judge

    private func judge(_ result: MeetTranscriptAssembly.Result, duration: TimeInterval,
                       endKnown: Bool) -> MeetTranscriptAssembly.Refusal? {
        MeetTranscriptAssembly.judge(result, mediaDuration: duration, recordingEndKnown: endKnown).refusal
    }

    private func result(_ cues: [PlatformTranscriptCue], referenced: Int = 0, unresolved: Int = 0)
        -> MeetTranscriptAssembly.Result {
        MeetTranscriptAssembly.Result(cues: cues, language: nil, referencedSpeakers: referenced,
                                      unresolvedSpeakers: unresolved, slicedAfterEnd: 0)
    }

    private func cue(_ start: TimeInterval, _ end: TimeInterval) -> PlatformTranscriptCue {
        PlatformTranscriptCue(start: start, end: end, speaker: "Priya Shah", text: "…")
    }

    @Test("Nothing said inside the recording is refused")
    func noCues() {
        #expect(judge(result([]), duration: 600, endKnown: true) == .noCues)
        // Everything before the button: nothing survives the clamp either.
        #expect(judge(result([cue(-30, -10)]), duration: 600, endKnown: true) == .noCues)
    }

    /// `speakers: none` tells the pipeline to leave the interview unseparated,
    /// so a transcript whose names all failed to resolve is worse than none.
    @Test("Entries that named people, none of whom resolved, are refused")
    func noSpeakerResolved() {
        let cues = [cue(0, 300), cue(300, 590)]
        #expect(judge(result(cues, referenced: 2, unresolved: 2), duration: 600, endKnown: true) == .noSpeakerResolved)
        #expect(judge(result(cues, referenced: 2, unresolved: 1), duration: 600, endKnown: true) == nil,
                "one resolved name is a transcript with one unnamed voice, which the writer handles")
        #expect(judge(result(cues, referenced: 0, unresolved: 0), duration: 600, endKnown: true) == nil,
                "Meet named nobody at all: not a resolution failure")
    }

    /// §5c: without an API end to slice by, a tail running past the file is
    /// the only evidence that these are the wrong recording's words.
    @Test("The tail check runs only when no API end sliced the cues")
    func tailCheckOnlyWithoutAnEnd() {
        let cues = [cue(0, 300), cue(300, 605)]
        #expect(judge(result(cues), duration: 600, endKnown: false) == .tailPastMedia)
        #expect(judge(result(cues), duration: 600, endKnown: true) == nil,
                "sliced to the API end already; a 5 s tail is a clamp, not a mismatch")
        let justOver = [cue(0, 300), cue(300, 601.5)]
        #expect(judge(result(justOver), duration: 600, endKnown: false) == nil, "within the 2 s tolerance")
    }

    /// §1a: entries arrive truncated while Google is still writing them, and a
    /// transcript that stops before the midpoint is not one Google has finished.
    @Test("Cues covering less than half the recording are refused as sparse")
    func sparseCoverage() {
        let refusal = judge(result([cue(0, 100), cue(100, 200)]), duration: 1_000, endKnown: true)
        guard case .sparseCoverage(let fraction)? = refusal else {
            Issue.record("expected sparseCoverage, got \(String(describing: refusal))")
            return
        }
        #expect(abs(fraction - 0.2) < 0.001)
        #expect(judge(result([cue(0, 100), cue(100, 520)]), duration: 1_000, endKnown: true) == nil,
                "past the midpoint is accepted")
    }

    @Test("A sound transcript is rebased, not refused")
    func soundTranscript() {
        let (rebased, refusal) = MeetTranscriptAssembly.judge(
            result([cue(-12.4, 3), cue(3, 590), cue(590, 603)], referenced: 3, unresolved: 0),
            mediaDuration: 600, recordingEndKnown: true)
        #expect(refusal == nil)
        #expect(rebased.cues.count == 3)
        #expect(rebased.cues.first?.start == 0, "clamped to the file")
        #expect(rebased.cues.last?.end == 600)
        #expect(rebased.dropped == 0)
    }
}
