import Foundation
import Testing

@testable import Bristlenose

// Zoom's traps are different from Google's, and every one of these pins a case
// where the plausible implementation produces a *confident wrong answer*
// rather than an error.

// MARK: - The HTTP-200 denial

@Suite("Zoom response classification")
struct ZoomResponseClassifierTests {

    private enum Fixture {
        /// The worst response in the whole adapter: a permission denial
        /// delivered with an HTTP **200** status line. Documented by Zoom on
        /// `GET /meetings/{id}/recordings`.
        static let denialAsTwoHundred = Data(
            #"{"code":200,"message":"You do not have the right permissions."}"#.utf8)

        /// The admin download block. Arrives only at download time — lock state
        /// is invisible to a non-admin token, so there is no discovery-time
        /// signal for it at all.
        static let adminBlocked = Data(
            #"{"code":200,"message":"Download has been disabled by the administrator"}"#.utf8)

        static let expiredToken = Data(
            #"{"code":124,"message":"Access token is expired."}"#.utf8)

        static let planTooLow = Data(
            #"{"code":200,"message":"Must have a Pro or a higher plan."}"#.utf8)

        static let missingScopes = Data(
            #"{"code":4700,"message":"Invalid access token, does not contain scopes."}"#.utf8)

        /// A genuine, healthy, empty result. Must NOT classify as an error —
        /// "you have no recordings in this window" is a real answer.
        static let emptyButFine = Data(
            #"{"meetings":[],"total_records":0,"page_size":300}"#.utf8)
    }

    @Test("A 200 carrying a denial is not success")
    func twoHundredDenial() {
        // A client branching on `response.ok` reads this as success, finds no
        // recording_files, and tells the researcher the session was never
        // recorded — while the expiry clock they came to beat keeps running.
        let outcome = ZoomResponseClassifier.classify(status: 200, body: Fixture.denialAsTwoHundred)
        #expect(outcome != .ok)
        #expect(outcome == .scopeNotGranted)
    }

    @Test("The admin download block is recognised, not swallowed")
    func adminBlock() {
        let outcome = ZoomResponseClassifier.classify(status: 200, body: Fixture.adminBlocked)
        #expect(outcome == .scopeNotGranted)
        #expect(outcome.retryPolicy == .never)
    }

    @Test("A genuinely empty result stays OK")
    func emptyIsNotAnError() {
        // The counterweight to the two tests above: if the body check were too
        // eager, every healthy empty window would render as a permission
        // failure, which is the same lie in the other direction.
        #expect(ZoomResponseClassifier.classify(status: 200, body: Fixture.emptyButFine) == .ok)
    }

    @Test("A plan refusal never retries; an expired token retries once")
    func planVersusToken() {
        let plan = ZoomResponseClassifier.classify(status: 200, body: Fixture.planTooLow)
        #expect(plan == .planDoesNotInclude)
        #expect(plan.retryPolicy == .never)

        let token = ZoomResponseClassifier.classify(status: 401, body: Fixture.expiredToken)
        #expect(token == .needsReauthentication)
        #expect(token.retryPolicy == .onceAfterReauthentication)
    }

    @Test("Missing scopes is not an expired token")
    func scopesVersusToken() {
        // Both arrive as 401. Refreshing a token that was never granted the
        // scope yields a valid token that fails identically, forever.
        let outcome = ZoomResponseClassifier.classify(status: 403, body: Fixture.missingScopes)
        #expect(outcome == .scopeNotGranted)
    }
}

// MARK: - File selection

@Suite("Zoom file selection")
struct ZoomFileSelectionTests {

    private func file(
        _ type: String,
        _ layout: String,
        size: Int64 = 1_000_000
    ) -> ZoomRecordingFile {
        ZoomRecordingFile(
            id: "\(type)-\(layout)",
            fileType: ZoomFileType(type),
            layout: ZoomRecordingLayout(layout),
            sizeBytes: size,
            downloadURL: URL(string: "https://zoom.us/rec/archive/download/x"),
            recordingStart: nil
        )
    }

    /// A realistic meeting: three MP4 framings, an M4A, a VTT, chat, timeline.
    private var typicalMeeting: [ZoomRecordingFile] {
        [
            file("MP4", "gallery_view", size: 900_000_000),
            file("MP4", "shared_screen_with_speaker_view", size: 800_000_000),
            file("MP4", "shared_screen", size: 400_000_000),
            file("M4A", "audio_only", size: 60_000_000),
            file("TRANSCRIPT", "audio_transcript", size: 40_000),
            file("CHAT", "chat_file", size: 2_000),
            file("TIMELINE", "timeline", size: 0),
        ]
    }

    @Test("Exactly one media file is chosen, never two")
    func neverTwoMedia() {
        let choice = ZoomFileSelection.choose(from: typicalMeeting)
        // Two MP4s of one interview are the same conversation twice. Ingesting
        // both creates two sessions with identical transcripts, doubles LLM
        // spend on every stage, and — because stages 10 and 11 cluster ACROSS
        // sessions — changes the themes rather than adding a row.
        #expect(choice.media != nil)
        #expect(choice.skippedMedia.count == 3)
        #expect(!choice.skippedMedia.contains { $0 == choice.media })
    }

    @Test("Audio is preferred by default — the pipeline discards the video anyway")
    func prefersAudio() {
        let choice = ZoomFileSelection.choose(from: typicalMeeting)
        #expect(choice.media?.fileType == .m4a)
        // ~60 MB instead of ~800 MB, for input that stage 2 would have reduced
        // to audio regardless.
        #expect((choice.media?.sizeBytes ?? 0) < 100_000_000)
    }

    @Test("When video is wanted, faces beat screens")
    func videoRanking() {
        let choice = ZoomFileSelection.choose(from: typicalMeeting, preferAudioOnly: false)
        // `shared_screen` alone is a slide deck with a voice over it; the value
        // of a research interview is the person.
        #expect(choice.media?.layout == .sharedScreenWithSpeakerView)
    }

    @Test("A transcript is picked up alongside, not instead of, the media")
    func transcriptIsSeparate() {
        let choice = ZoomFileSelection.choose(from: typicalMeeting)
        #expect(choice.transcript?.fileType == .transcript)
        #expect(choice.media?.fileType != .transcript)
    }

    @Test("An audio-only meeting still yields a choice")
    func audioOnlyMeeting() {
        let choice = ZoomFileSelection.choose(from: [file("M4A", "audio_only")])
        #expect(choice.media?.fileType == .m4a)
        #expect(choice.skippedMedia.isEmpty)
    }

    @Test("Unknown file types are carried, never rejected")
    func unknownTypesSurvive() {
        // Zoom's own enum omits TIMELINE (which it emits) and includes TB and
        // CHAT_MESSAGE (which it never describes). An adapter that validated
        // against the published enum would drop real files.
        #expect(ZoomFileType("TIMELINE") == .timeline)
        #expect(ZoomFileType("SOMETHING_NEW") == .other("SOMETHING_NEW"))
        #expect(!ZoomFileType("SOMETHING_NEW").isMedia)
    }
}

// MARK: - The date window

@Suite("Zoom list window")
struct ZoomListWindowTests {

    @Test("A 90-day range is split into month-sized chunks")
    func splitsIntoChunks() {
        // Zoom caps a query at one month and does NOT error on a wider one — it
        // simply answers for less. A single 90-day call loses two thirds of the
        // study, silently.
        let end = Date()
        let start = Calendar.current.date(byAdding: .day, value: -90, to: end)!
        let chunks = ZoomListWindow.chunks(covering: DateInterval(start: start, end: end))
        #expect(chunks.count == 3)
        #expect(chunks.first?.start == start)
        #expect(chunks.last?.end == end)
    }

    @Test("Chunks are contiguous and leave no gap")
    func noGaps() {
        let end = Date()
        let start = Calendar.current.date(byAdding: .day, value: -75, to: end)!
        let chunks = ZoomListWindow.chunks(covering: DateInterval(start: start, end: end))
        for (a, b) in zip(chunks, chunks.dropFirst()) {
            // A gap here drops every meeting on the boundary day, which is
            // exactly the invisible-shorter-list failure the design fears.
            #expect(a.end == b.start)
        }
    }

    @Test("A short range is one chunk")
    func shortRange() {
        let end = Date()
        let start = Calendar.current.date(byAdding: .day, value: -7, to: end)!
        #expect(ZoomListWindow.chunks(covering: DateInterval(start: start, end: end)).count == 1)
    }

    @Test("Dates render as yyyy-MM-dd in UTC")
    func utcFormat() {
        // A local-timezone rendering shifts the boundary by up to a day and
        // drops meetings at each edge — the same hazard the Teams design found
        // in calendarView.
        let window = ZoomListWindow(start: Date(timeIntervalSince1970: 0),
                                    end: Date(timeIntervalSince1970: 86_400))
        #expect(window.fromString == "1970-01-01")
        #expect(window.toString == "1970-01-02")
    }
}

// MARK: - Expiry

@Suite("Zoom expiry")
struct ZoomExpiryTests {

    @Test("Auto-delete on yields a real countdown")
    func autoDeleteOn() {
        let date = Date().addingTimeInterval(30 * 86_400)
        let expiry = ZoomExpiry(autoDelete: true, autoDeleteDate: date, deletedTime: nil)
        #expect(expiry == .on(date))
        #expect(expiry.date == date)
    }

    @Test("Auto-delete off is NOT 'never expires'")
    func autoDeleteOff() {
        let expiry = ZoomExpiry(autoDelete: false, autoDeleteDate: nil, deletedTime: nil)
        #expect(expiry == .notSet)
        // The distinction that matters: the host simply has not enabled the
        // setting. An admin can enable it tomorrow, account retention still
        // applies, and quota pressure removes recordings by other means. "Never"
        // would be the one claim in that column a researcher might rely on, and
        // it is the one we cannot make.
        #expect(expiry.date == nil)
    }

    @Test("A trashed recording carries no invented countdown")
    func trashed() {
        let deleted = Date()
        let expiry = ZoomExpiry(autoDelete: true, autoDeleteDate: Date(), deletedTime: deleted)
        #expect(expiry == .trashed(deletedAt: deleted))
        // There is no permanent_delete_date field, so any trash countdown would
        // be a guess dressed as data.
        #expect(expiry.date == nil)
    }
}

// MARK: - Identifiers

@Suite("Zoom UUID encoding")
struct ZoomIdentifierTests {

    @Test("A UUID starting with a slash is double-encoded")
    func doubleEncoded() {
        // Zoom's documented requirement, and the reason a base64 UUID returns a
        // 404 that reads as "meeting not found" rather than "you encoded it
        // wrong". Base64 UUIDs routinely start with / or contain //, so this is
        // the common case.
        let encoded = ZoomIdentifier.encodedUUID("/ajXp112QmuoKj4854875==")
        #expect(encoded.contains("%252F"))
        #expect(!encoded.contains("/"))
    }

    @Test("A UUID containing a double slash is double-encoded")
    func containsDoubleSlash() {
        #expect(ZoomIdentifier.encodedUUID("abc//def").contains("%252F"))
    }

    @Test("An ordinary UUID is encoded once")
    func singleEncoded() {
        let encoded = ZoomIdentifier.encodedUUID("abcDEF123==")
        #expect(encoded.contains("%3D"))
        #expect(!encoded.contains("%253D"))
    }
}

// MARK: - Transcript parsing

@Suite("Zoom VTT speaker attribution")
struct ZoomTranscriptTests {

    @Test("A speaker prefix is lifted out")
    func speakerPrefix() {
        let cue = ZoomTranscript.splitSpeaker("Sarah Chen: So tell me about that")
        #expect(cue.speaker == "Sarah Chen")
        #expect(cue.text == "So tell me about that")
    }

    @Test("A colon inside dialogue is not a speaker")
    func colonInDialogue() {
        // The naive split(':') turns this sentence into a speaker named
        // "the ratio was 3" — and does it silently, on real interview content.
        let cue = ZoomTranscript.splitSpeaker("the ratio was 3:1 in the end")
        #expect(cue.speaker == nil)
        #expect(cue.text == "the ratio was 3:1 in the end")
    }

    @Test("A sentence-shaped prefix is rejected")
    func sentencePrefix() {
        let cue = ZoomTranscript.splitSpeaker("Honestly, I gave up: it was too slow")
        #expect(cue.speaker == nil)
    }

    @Test("A cue with no speaker degrades rather than inventing one")
    func noSpeaker() {
        // Zoom does not always emit names. An importer that assumes them ends
        // up with a session whose sole speaker is the first phrase of the
        // interview.
        let cue = ZoomTranscript.splitSpeaker("just the words, no name")
        #expect(cue.speaker == nil)
        #expect(cue.text == "just the words, no name")
    }
}

// MARK: - Preflight

@Suite("Zoom preflight")
struct ZoomPreflightTests {

    @Test("Cloud recording off blocks, and says what still works")
    func cloudRecordingOff() {
        let preflight = ZoomPreflight(cloudRecordingEnabled: false,
                                      audioTranscriptEnabled: false,
                                      autoDeleteEnabled: false, autoDeleteDays: nil)
        let reason = try? #require(preflight.blockingReason)
        // Basic-plan and recording-disabled accounts have nothing in the cloud
        // at all — but local recordings still exist on their Mac, and saying so
        // turns a dead end into a next step.
        #expect(reason?.contains("Finder") == true)
    }

    @Test("Transcript off is a caveat, not a block")
    func transcriptOff() {
        let preflight = ZoomPreflight(cloudRecordingEnabled: true,
                                      audioTranscriptEnabled: false,
                                      autoDeleteEnabled: false, autoDeleteDays: nil)
        // The recordings are fetchable; only the VTT is missing. Blocking here
        // would refuse a perfectly usable import.
        #expect(preflight.blockingReason == nil)
        #expect(preflight.transcriptCaveat != nil)
    }

    @Test("Everything on is silent")
    func allGood() {
        let preflight = ZoomPreflight(cloudRecordingEnabled: true,
                                      audioTranscriptEnabled: true,
                                      autoDeleteEnabled: true, autoDeleteDays: 30)
        #expect(preflight.blockingReason == nil)
        #expect(preflight.transcriptCaveat == nil)
    }
}

// MARK: - Download guard

@Suite("Zoom download guard")
struct ZoomDownloadGuardTests {

    private func response(_ status: Int, _ contentType: String) -> HTTPURLResponse? {
        HTTPURLResponse(url: URL(string: "https://ssrweb.zoom.us/x")!,
                        statusCode: status, httpVersion: nil,
                        headerFields: ["Content-Type": contentType])
    }

    @Test("HTML with a 200 is refused")
    func htmlIsNotMedia() {
        // A documented Zoom failure shape: a permission or session problem
        // answers with a login page and a 200. Written to disk it becomes a
        // 3 KB file named .mp4 that ffprobe rejects hours later at stage 2 —
        // long after the researcher stopped watching.
        #expect(!ZoomDownloadGuard.isUsableMedia(response: response(200, "text/html; charset=utf-8")))
    }

    @Test("A JSON error body is refused")
    func jsonIsNotMedia() {
        #expect(!ZoomDownloadGuard.isUsableMedia(response: response(200, "application/json")))
    }

    @Test("Real media passes")
    func mediaPasses() {
        #expect(ZoomDownloadGuard.isUsableMedia(response: response(200, "video/mp4")))
        #expect(ZoomDownloadGuard.isUsableMedia(response: response(200, "audio/mp4")))
    }

    @Test("A 403 is refused whatever its content type claims")
    func statusStillCounts() {
        #expect(!ZoomDownloadGuard.isUsableMedia(response: response(403, "video/mp4")))
    }
}

// MARK: - Byte verification

@Suite("Zoom byte verification")
struct ZoomByteVerificationTests {

    @Test("A short read is caught, not written")
    func shortRead() {
        // The 880-error-bodies case: expected 239 MB, received 41 KB of HTML.
        // Size is an independent second source, so it catches a redirect that
        // served something else entirely — not merely a truncated stream.
        let verdict = ZoomDownloadGuard.verify(received: 41_000, expected: 239_000_000)
        #expect(verdict == .shortRead(expected: 239_000_000, received: 41_000))
    }

    @Test("An exact match passes")
    func exactMatch() {
        #expect(ZoomDownloadGuard.verify(received: 1_234, expected: 1_234) == .usable)
    }

    @Test("An absent expected size reads as unknown, not as zero")
    func unknownSize() {
        // CC and TIMELINE files genuinely carry no file_size. Treating nil as 0
        // would fail every one of them.
        #expect(ZoomDownloadGuard.verify(received: 5_000, expected: nil) == .usable)
        #expect(ZoomDownloadGuard.verify(received: 5_000, expected: 0) == .usable)
    }
}
