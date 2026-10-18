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

    @Test("The video is taken whenever there is one")
    func prefersVideo() {
        // What was on screen is the evidence in a test of a digital product:
        // thumbnails, the scene timeline, screen text and clips all need the
        // video. The M4A was the default until 18 Oct 2026, and every Zoom
        // import arrived without them.
        let choice = ZoomFileSelection.choose(from: typicalMeeting)
        #expect(choice.media?.fileType == .mp4)
        #expect(choice.skippedMedia.contains { $0.fileType == .m4a })
    }

    @Test("Of the videos, the screen with the speaker beside it wins")
    func videoRanking() {
        let choice = ZoomFileSelection.choose(from: typicalMeeting)
        // The product on screen and the person reacting to it, in one file.
        #expect(choice.media?.layout == .sharedScreenWithSpeakerView)
    }

    @Test("Recorded as separate files, the screen beats the face")
    func screenBeatsFace() {
        // "Record active speaker, gallery view and shared screen separately"
        // gives no combined layout. The screen is the evidence in a test of a
        // digital product; a face-first order dropped it.
        let choice = ZoomFileSelection.choose(from: [
            file("MP4", "active_speaker", size: 500_000_000),
            file("MP4", "gallery_view", size: 600_000_000),
            file("MP4", "shared_screen", size: 300_000_000),
            file("M4A", "audio_only", size: 60_000_000),
        ])
        #expect(choice.media?.layout == .sharedScreen)
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
        #expect(chunks.count == 4)
        #expect(chunks.first?.start == start)
        #expect(chunks.last?.end == end)
    }

    @Test("No chunk asks Zoom for more than 30 inclusive dates")
    func thirtyInclusiveDates() {
        // `from` and `to` are inclusive; a chunk 30 days long asked for 31.
        let end = Date()
        let start = Calendar.current.date(byAdding: .day, value: -90, to: end)!
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(secondsFromGMT: 0)!
        let day = DateFormatter()
        day.dateFormat = "yyyy-MM-dd"
        day.timeZone = utc.timeZone
        for chunk in ZoomListWindow.chunks(covering: DateInterval(start: start, end: end)) {
            let from = day.date(from: chunk.fromString)!, to = day.date(from: chunk.toString)!
            let dates = utc.dateComponents([.day], from: from, to: to).day! + 1
            #expect(dates <= 30, "\(chunk.fromString)…\(chunk.toString) is \(dates) dates")
        }
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

    @Test("Real display names with punctuation are names")
    func punctuatedNames() {
        // Written unnamed, these kept "Dr. Patel:" inside the quote text,
        // because the pipeline trusts a cloud transcript and never re-guesses.
        #expect(ZoomTranscript.splitSpeaker("Dr. Patel: How long has it hurt?").speaker == "Dr. Patel")
        #expect(ZoomTranscript.splitSpeaker("Patel, Anita: About a week").speaker == "Patel, Anita")
        #expect(ZoomTranscript.splitSpeaker("Seán O'Brien (Guest): Hi").speaker == "Seán O'Brien (Guest)")
        #expect(ZoomTranscript.splitSpeaker("Participant 04: Yes").speaker == "Participant 04")
    }

    @Test("Names in scripts without case are names")
    func uncasedScripts() {
        // A capital-letter rule rejected every one of these, so a Japanese or
        // Chinese call lost all its speaker names.
        let cue = ZoomTranscript.splitSpeaker("田中 花子：はい、そうです")
        #expect(cue.speaker == "田中 花子")
        #expect(cue.text == "はい、そうです")
        #expect(ZoomTranscript.splitSpeaker("王伟: 我同意").speaker == "王伟")
    }

    @Test("A word that opens a sentence is not a speaker")
    func discourseWords() {
        #expect(ZoomTranscript.splitSpeaker("Honestly: I gave up").speaker == nil)
        #expect(ZoomTranscript.splitSpeaker("Note: this is recorded").speaker == nil)
        #expect(ZoomTranscript.splitSpeaker("Suharto: Welcome").speaker == "Suharto")
        #expect(ZoomTranscript.splitSpeaker("Okay. So the thing: it broke").speaker == nil)
    }

    @Test("A surname that is also a stop word is still a name")
    func stopWordSurnames() {
        // Oh and So are Korean surnames. A first-word check without the comma
        // dropped every cue such a participant spoke.
        #expect(ZoomTranscript.splitSpeaker("Oh Minji: Yes, that one").speaker == "Oh Minji")
        #expect(ZoomTranscript.splitSpeaker("So Yeon Kim: I agree").speaker == "So Yeon Kim")
    }

    @Test("A name of six words is a name, as in the pipeline")
    func sixWordName() {
        let name = "Anita Patel (UX Research, Acme Labs)"
        #expect(ZoomTranscript.splitSpeaker("\(name): Hello").speaker == name)
        #expect(ZoomTranscript.splitSpeaker("One Two Three Four Five Six Seven: Hi").speaker == nil)
    }

    @Test("A recurring lowercase clause is not a handle")
    func recurringLowercaseClause() {
        let vtt = (1...3).map { i in
            "00:00:0\(i).000 --> 00:00:0\(i).500\nso i think: it works"
        }.joined(separator: "\n\n")
        let cues = ZoomTranscript.cues(fromVTT: "WEBVTT\n\n" + vtt)
        #expect(cues.count == 3)
        #expect(cues.allSatisfy { $0.speaker == nil })
    }

    @Test("Zoom's Unknown Speaker label is no one, and its words are kept")
    func unknownSpeaker() {
        let cue = ZoomTranscript.splitSpeaker("Unknown Speaker: Okay.")
        #expect(cue.speaker == nil)
        #expect(cue.text == "Okay.")
    }

    @Test("A lowercase handle that recurs is a name; a one-off fragment is not")
    func recurringLowercaseHandle() {
        // A real 2025 call: `stay` and `nutzipper` were display names on 227
        // of 505 cues, and a capital-letter rule alone dropped every one.
        let vtt = """
            WEBVTT

            00:00:01.000 --> 00:00:02.000
            stay: Hello

            00:00:03.000 --> 00:00:04.000
            stay: Around the world.

            00:00:05.000 --> 00:00:06.000
            stay: Okay.

            00:00:07.000 --> 00:00:08.000
            the ratio was 3:1 in the end
            """
        let cues = ZoomTranscript.cues(fromVTT: vtt)
        #expect(cues.prefix(3).allSatisfy { $0.speaker == "stay" })
        #expect(cues[3].speaker == nil)
        #expect(cues[3].text == "the ratio was 3:1 in the end")
    }

    @Test("A CJK name with an ideographic space is one name")
    func ideographicSpace() {
        #expect(ZoomTranscript.splitSpeaker("田中\u{3000}花子: はい").speaker == "田中\u{3000}花子")
    }

    @Test("The stop words mirror the pipeline's, word for word")
    func stopWordsMirrorThePipeline() throws {
        // The pipeline trusts this file's names, so the two lists are one
        // decision. Read from the Python source rather than copied into a
        // fixture, so neither side can move alone.
        let source = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("bristlenose/stages/s03_parse_subtitles.py")
        let python = try String(contentsOf: source, encoding: .utf8)
        let block = try #require(python.range(of: "_NOT_SPEAKER_WORDS = frozenset({"))
        let tail = python[block.upperBound...]
        let end = try #require(tail.range(of: "})"))
        let regex = try NSRegularExpression(pattern: #""([^"]+)""#)
        let body = String(tail[..<end.lowerBound])
        let words = Set(regex.matches(in: body, range: NSRange(body.startIndex..., in: body)).compactMap {
            Range($0.range(at: 1), in: body).map { String(body[$0]) }
        })
        #expect(words.count > 50, "the Python list did not parse")
        #expect(words == ZoomTranscript.notSpeakerWords)
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
        // Basic-plan and recording-disabled accounts have nothing in the cloud
        // at all, so the notice stands in for the list rather than sitting
        // over an empty one that reads "no recordings this month".
        #expect(preflight.notice == .zoomCloudRecordingOff)
        #expect(preflight.notice?.replacesListing == true)
    }

    @Test("Transcript off is a caveat, not a block")
    func transcriptOff() {
        let preflight = ZoomPreflight(cloudRecordingEnabled: true,
                                      audioTranscriptEnabled: false,
                                      autoDeleteEnabled: false, autoDeleteDays: nil)
        // The recordings are fetchable; only the VTT is missing. Blocking here
        // would refuse a perfectly usable import.
        #expect(preflight.notice == .zoomTranscriptOff)
        #expect(preflight.notice?.replacesListing == false)
    }

    @Test("Everything on is silent")
    func allGood() {
        let preflight = ZoomPreflight(cloudRecordingEnabled: true,
                                      audioTranscriptEnabled: true,
                                      autoDeleteEnabled: true, autoDeleteDays: 30)
        #expect(preflight.notice == nil)
    }
}

// MARK: - The sign-in that never returns

@MainActor
@Suite("Sign-in that yields no account")
struct SignInIncompleteTests {

    @Test("A consent flow that returns no account is not treated as signed in")
    func noAccountMeansIncomplete() async {
        // The Zoom pre-approval wall's real shape: enabled by DEFAULT on every
        // multi-seat account, enforced on Zoom's own consent screen before any
        // redirect, so the flow completes without error and without an account.
        // Left unhandled the window spins forever; called "cancelled" it sends
        // the researcher to try again, forever, against a wall only their
        // admin can remove.
        let store = CloudImportStore(
            source: FixtureCloudSource(scenario: .signInIncomplete, platform: .zoom))
        store.signIn()

        for _ in 0..<40 where store.phase == .signingIn {
            try? await Task.sleep(for: .milliseconds(50))
        }
        #expect(store.phase == .signInIncomplete)
        #expect(store.accountEmail == nil)
    }

    @Test("Only the admin-gated platforms mention an administrator")
    func copyIsPlatformAware() {
        // Zoom and Teams both have a default-shaped org gate. Google does not,
        // so telling a Google user their admin might be the problem would be a
        // guess dressed as help.
        #expect(CloudPlatform.zoom.signInMayAwaitAdminApproval)
        #expect(CloudPlatform.teams.signInMayAwaitAdminApproval)
        #expect(!CloudPlatform.meet.signInMayAwaitAdminApproval)
    }
}

// MARK: - Parts of a stopped-and-restarted meeting

@Suite("Zoom recording parts")
struct ZoomRecordingPartsTests {

    private let t0 = Date(timeIntervalSince1970: 1_790_000_000)

    private func file(_ type: String, _ layout: String,
                      from start: TimeInterval?, to end: TimeInterval?) -> ZoomRecordingFile {
        ZoomRecordingFile(
            id: "\(type)-\(layout)-\(start ?? -1)",
            fileType: ZoomFileType(type),
            layout: ZoomRecordingLayout(layout),
            sizeBytes: 1_000,
            downloadURL: URL(string: "https://zoom.us/rec/download/x"),
            recordingStart: start.map { t0.addingTimeInterval($0) },
            recordingEnd: end.map { t0.addingTimeInterval($0) })
    }

    /// Two stretches ten minutes apart, each with a video, an audio file and a
    /// transcript — the shape a host gets by pressing Stop, then Record again.
    private var restarted: [ZoomRecordingFile] {
        [
            file("MP4", "shared_screen_with_speaker_view", from: 0, to: 600),
            file("M4A", "audio_only", from: 0, to: 600),
            file("TRANSCRIPT", "audio_transcript", from: 0, to: 600),
            file("MP4", "shared_screen_with_speaker_view", from: 1200, to: 1500),
            file("M4A", "audio_only", from: 1200, to: 1500),
            file("TRANSCRIPT", "audio_transcript", from: 1200, to: 1500),
        ]
    }

    @Test("Every part is kept, not only the first")
    func everyPartKept() {
        // `choose` alone takes the first media file and the first transcript,
        // so the second stretch of the interview silently never arrived.
        let parts = ZoomFileSelection.parts(from: restarted)
        #expect(parts.count == 2)
        #expect(parts.map { $0.start } == [t0, t0.addingTimeInterval(1200)])
        #expect(parts.allSatisfy { $0.choice.media?.fileType == .mp4 })
    }

    @Test("Each transcript goes to the part it overlaps")
    func transcriptsPairByOverlap() {
        // Listing order is Zoom's, not chronological; pairing by position
        // would put the second stretch's words under the first's audio.
        let parts = ZoomFileSelection.parts(from: restarted.reversed())
        #expect(parts[0].choice.transcript?.recordingStart == t0)
        #expect(parts[1].choice.transcript?.recordingStart == t0.addingTimeInterval(1200))
    }

    @Test("Renditions of one stretch stay one part")
    func renditionsAreOnePart() {
        let parts = ZoomFileSelection.parts(from: [
            file("MP4", "gallery_view", from: 0, to: 600),
            file("MP4", "active_speaker", from: 1, to: 600),
            file("M4A", "audio_only", from: 0, to: 600),
        ])
        #expect(parts.count == 1)
        #expect(parts[0].choice.skippedMedia.count == 2)
    }

    @Test("A part with no transcript of its own gets none")
    func partWithoutTranscript() {
        let files = restarted.filter {
            !($0.fileType == .transcript && $0.recordingStart == t0.addingTimeInterval(1200))
        }
        let parts = ZoomFileSelection.parts(from: files)
        #expect(parts[0].choice.transcript != nil)
        #expect(parts[1].choice.transcript == nil)
    }

    @Test("Media without start times is one part, as before")
    func noStartsIsOnePart() {
        let parts = ZoomFileSelection.parts(from: [
            file("MP4", "active_speaker", from: nil, to: nil),
            file("M4A", "audio_only", from: nil, to: nil),
            file("TRANSCRIPT", "audio_transcript", from: nil, to: nil),
        ])
        #expect(parts.count == 1)
        #expect(parts[0].choice.transcript != nil)
    }
}

// MARK: - Transcript availability

@Suite("Zoom transcript availability")
struct ZoomTranscriptAvailabilityTests {

    private let ended = Date(timeIntervalSince1970: 1_790_000_000)

    @Test("A listed transcript is Available whatever the setting says")
    func listedIsAvailable() {
        #expect(ZoomTranscriptAvailability.decide(
            hasTranscript: true, audioTranscriptEnabled: false,
            recordingEnded: ended, now: ended) == .available)
    }

    @Test("Setting on and a recent call: Expected")
    func recentIsExpected() {
        // The transcript lands 15–30 minutes after the video. Reading its
        // absence as "none" an hour after the call would import without it.
        #expect(ZoomTranscriptAvailability.decide(
            hasTranscript: false, audioTranscriptEnabled: true,
            recordingEnded: ended, now: ended.addingTimeInterval(3600)) == .expected)
    }

    @Test("Past a day, the wait ends with No transcript")
    func oldIsNotProvided() {
        // Zoom sometimes never produces one; a wait must end with an answer.
        #expect(ZoomTranscriptAvailability.decide(
            hasTranscript: false, audioTranscriptEnabled: true,
            recordingEnded: ended, now: ended.addingTimeInterval(25 * 3600)) == .notProvided)
    }

    @Test("Setting off, or unread, waits for nothing")
    func offOrUnknownWaitsForNothing() {
        #expect(ZoomTranscriptAvailability.decide(
            hasTranscript: false, audioTranscriptEnabled: false,
            recordingEnded: ended, now: ended) == .notProvided)
        #expect(ZoomTranscriptAvailability.decide(
            hasTranscript: false, audioTranscriptEnabled: nil,
            recordingEnded: ended, now: ended) == .notProvided)
    }
}

// MARK: - Reading Zoom's VTT

@Suite("Zoom VTT parsing")
struct ZoomVTTParsingTests {

    private let sample = """
        WEBVTT

        1
        00:00:01.120 --> 00:00:04.500
        Priya Shah: So, tell me how you plan a trip.

        2
        00:00:05.000 --> 00:00:09.250
        Participant 04: Usually the ratio is 3:1 —
        flights first, then hotels.

        3
        00:01:10.000 --> 00:01:12.000
        the ratio was 3:1 &amp; it showed

        """

    @Test("Cues come back with times, names and joined lines")
    func parsesCues() {
        let cues = ZoomTranscript.cues(fromVTT: sample)
        #expect(cues.count == 3)
        #expect(cues[0].start == 1.12 && cues[0].end == 4.5)
        #expect(cues[0].speaker == "Priya Shah")
        #expect(cues[0].text == "So, tell me how you plan a trip.")
        #expect(cues[1].speaker == "Participant 04")
        #expect(cues[1].text == "Usually the ratio is 3:1 — flights first, then hotels.")
    }

    @Test("Dialogue with a colon is not a speaker, and entities are read once")
    func colonInDialogue() {
        let cue = ZoomTranscript.cues(fromVTT: sample)[2]
        #expect(cue.speaker == nil)
        // Left as `&amp;`, the writer would escape it again and the pipeline
        // would read a literal "&amp;" into the participant's words.
        #expect(cue.text == "the ratio was 3:1 & it showed")
        #expect(cue.start == 70)
    }

    @Test("CRLF files and short timestamps parse the same")
    func crlfAndShortTimes() {
        let crlf = "WEBVTT\r\n\r\n01:02.500 --> 01:04.000 align:start\r\nAlex: Hi\r\n"
        let cues = ZoomTranscript.cues(fromVTT: crlf)
        #expect(cues.count == 1)
        #expect(cues[0].start == 62.5)
        #expect(cues[0].end == 64)
        #expect(cues[0].speaker == "Alex")
    }

    @Test("A blank line holding spaces still ends a cue")
    func whitespaceBlankLine() {
        let vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nAlex: One\n  \n00:00:03.000 --> 00:00:04.000\nSam: Two\n"
        let cues = ZoomTranscript.cues(fromVTT: vtt)
        #expect(cues.map(\.speaker) == ["Alex", "Sam"])
    }

    @Test("A timing line that does not parse drops its cue")
    func badTimingDropped() {
        let bad = "WEBVTT\n\n00:00:xx --> 00:00:02.000\nAlex: Hi\n\n00:00:03.000 --> 00:00:02.000\nAlex: Backwards\n"
        #expect(ZoomTranscript.cues(fromVTT: bad).isEmpty)
    }
}

// MARK: - When the call was booked

@Suite("Zoom booking")
struct ZoomScheduleTests {

    private let recorded = Date(timeIntervalSince1970: 1_760_000_000)

    @Test("A recurring series takes the occurrence nearest the recording")
    func nearestOccurrence() {
        // Zoom's top-level start_time on a recurring meeting is reported as
        // the LAST occurrence; trusting it dates every session of a weekly
        // study the same day.
        let week: TimeInterval = 7 * 86_400
        let booking = ZoomSchedule.booking(
            start: recorded.addingTimeInterval(3 * week),
            duration: 3600,
            occurrences: [
                .init(start: recorded.addingTimeInterval(-week), duration: 3600),
                .init(start: recorded.addingTimeInterval(-600), duration: 2700),
                .init(start: recorded.addingTimeInterval(week), duration: 3600),
            ],
            near: recorded)
        #expect(booking == .init(start: recorded.addingTimeInterval(-600), duration: 2700))
    }

    @Test("A booking far from the recording is not its booking")
    func tooFarIsNone() {
        // A one-off meeting ID can be started days after the time it was booked for.
        let booking = ZoomSchedule.booking(start: recorded.addingTimeInterval(-2 * 86_400),
                                           duration: 3600, occurrences: [], near: recorded)
        #expect(booking == nil)
    }

    @Test("A scheduled meeting uses its own start time")
    func scheduledUsesStart() {
        let booking = ZoomSchedule.booking(start: recorded.addingTimeInterval(-300),
                                           duration: 1800, occurrences: [], near: recorded)
        #expect(booking?.start == recorded.addingTimeInterval(-300))
    }

    @Test("A deleted occurrence was never held")
    func deletedOccurrenceIgnored() throws {
        let json = """
        {"type":8,"occurrences":[
          {"start_time":"2026-10-18T10:00:00Z","duration":60,"status":"deleted"},
          {"start_time":"2026-10-18T11:00:00Z","duration":45,"status":"available"}]}
        """
        let found = try JSONDecoder().decode(ZoomMeetingBooking.self, from: Data(json.utf8))
        #expect(found.occurrenceBookings.count == 1)
        #expect(found.occurrenceBookings.first?.duration == 2700)
    }

    @Test("Only Zoom's instant meeting is labelled instant")
    func instantIsTypeOne() {
        #expect(ZoomSchedule.isInstant(type: 1))
        // A personal room has no booking, but Zoom does not call it instant.
        #expect(!ZoomSchedule.isInstant(type: 4))
        #expect(!ZoomSchedule.isInstant(type: nil))
        #expect(!ZoomSchedule.mayHaveBooking(type: 1))
        #expect(!ZoomSchedule.mayHaveBooking(type: 4))
        #expect(ZoomSchedule.mayHaveBooking(type: 2))
        #expect(ZoomSchedule.mayHaveBooking(type: 8))
        #expect(ZoomSchedule.mayHaveBooking(type: nil))
    }
}
