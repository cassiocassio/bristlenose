import Foundation
import Testing

@testable import Bristlenose

// §5e's Meet column, pinned without a tenant: what the transcripts Google
// lists for a call say about one recording's transcript.
//
// NOT YET RUN ON A MAC — written in a cloud session with no Xcode (1 Oct 2026).

@Suite("Meet transcript decision")
struct MeetTranscriptDecisionTests {

    private let now = Date(timeIntervalSince1970: 1_759_300_000)
    private var callStart: Date { now.addingTimeInterval(-3 * 3600) }
    private var recordingStart: Date { callStart.addingTimeInterval(120) }
    private var recordingEnd: Date { callStart.addingTimeInterval(2_040) }

    private func transcript(_ state: MeetTranscriptSummary.State,
                            from: TimeInterval? = 60, to: TimeInterval? = 2_100,
                            name: String = "conferenceRecords/r/transcripts/t") -> MeetTranscriptSummary {
        MeetTranscriptSummary(name: name, state: state,
                              startedAt: from.map { callStart.addingTimeInterval($0) },
                              endedAt: to.map { callStart.addingTimeInterval($0) })
    }

    private func decide(_ transcripts: [MeetTranscriptSummary],
                        start: Date? = nil, end: Date? = nil,
                        callEnded: Bool = true, at: Date? = nil) -> TranscriptAvailability {
        MeetTranscriptDecision.availability(
            recordingStart: start ?? recordingStart, recordingEnd: end ?? recordingEnd,
            callEnded: callEnded, transcripts: transcripts, now: at ?? now)
    }

    @Test("A generated transcript over the recording is Available")
    func generatedIsAvailable() {
        #expect(decide([transcript(.fileGenerated)]) == .available)
    }

    /// The certain signal (§1a): Meet lists the resource before the file exists.
    @Test("A transcript still being produced is Expected")
    func inProgressIsExpected() {
        #expect(decide([transcript(.started)]) == .expected)
        #expect(decide([transcript(.ended)]) == .expected)
    }

    @Test("No transcript resource on an ended call is No transcript")
    func noneOnEndedCall() {
        #expect(decide([]) == .notProvided)
    }

    @Test("No transcript resource on a call still in progress is Expected")
    func noneOnLiveCall() {
        #expect(decide([], callEnded: false) == .expected)
    }

    /// Waiting too long costs a minute's patience; giving up too early costs
    /// the speaker names. So the wait errs long, and still ends.
    @Test("Expected becomes No transcript after a day")
    func expectedExpires() {
        let stuck = [transcript(.ended, from: 60, to: 2_100)]
        #expect(decide(stuck) == .expected)
        let aDayLater = now.addingTimeInterval(MeetTranscriptDecision.patience + 60)
        #expect(decide(stuck, at: aDayLater) == .notProvided)
    }

    /// §5c: without the recording's own start there is no clock to put the
    /// words on, and a guess would land every timing δ out while reading well.
    @Test("A generated transcript with no recording start cannot be matched")
    func noStartCannotBeMatched() {
        // Both halves nil: the recording resource carried no `startTime`.
        #expect(MeetTranscriptDecision.availability(
            recordingStart: nil, recordingEnd: nil, callEnded: true,
            transcripts: [transcript(.fileGenerated)], now: now) == .notResolved)
    }

    /// A stopped-and-restarted transcription is several resources; a recording
    /// pairs with the ones that overlap it and ignores the ones that do not.
    @Test("Only transcripts that overlap the recording count")
    func overlapDecides() {
        // Ended before the record button: not this recording's.
        let before = transcript(.fileGenerated, from: 0, to: 100, name: "t-before")
        // Started after the recording stopped: not this one's either.
        let after = transcript(.started, from: 2_500, to: nil, name: "t-after")
        #expect(decide([before, after]) == .notProvided,
                "neither overlaps, so for this recording there is none")
        let overlapping = transcript(.fileGenerated, from: 1_000, to: 3_000, name: "t-over")
        #expect(decide([before, after, overlapping]) == .available)
        // And a transcript with no clock of its own cannot be excluded.
        let unclocked = transcript(.started, from: nil, to: nil, name: "t-unclocked")
        #expect(decide([before, unclocked]) == .expected)
    }

    @Test("Generated wins over an in-progress sibling")
    func generatedWinsOverStarted() {
        #expect(decide([transcript(.started, name: "t-1"),
                        transcript(.fileGenerated, name: "t-2")]) == .available)
    }

    /// A state this adapter has not met reads as "not generated" — waited for,
    /// then given up on — never as a transcript we claim to have.
    @Test("An unknown state is not generated")
    func unknownStateIsNotGenerated() {
        #expect(MeetTranscriptSummary.State("SOMETHING_NEW") == .unknown)
        #expect(MeetTranscriptSummary.State(nil) == .unknown)
        #expect(decide([transcript(.unknown)]) == .expected)
    }

    @Test("The wire strings map to their states")
    func stateStrings() {
        #expect(MeetTranscriptSummary.State("STARTED") == .started)
        #expect(MeetTranscriptSummary.State("ENDED") == .ended)
        #expect(MeetTranscriptSummary.State("FILE_GENERATED") == .fileGenerated)
    }
}
