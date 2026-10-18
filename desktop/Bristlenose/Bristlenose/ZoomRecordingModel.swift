import Foundation

// Zoom cloud-recording model. Pure values — no networking, no UI.
//
// Design: docs/design-cloud-import.md. Sibling adapters: GoogleMeetModel.swift,
// CloudImportModel.swift (Teams). Shared spine: CloudImportRow, ImportRowState,
// ArtifactAvailability, JoinArithmetic.
//
// Zoom's shape differs from both others in one structural way that drives most
// of this file: **a single meeting returns many files**, not one. Teams and Meet
// each yield a video; Zoom yields up to three MP4s of the same conversation at
// different framings, plus an M4A, plus a VTT, plus chat, timeline, thumbnails
// and summaries. Choosing badly is not a rendering problem — ingesting two MP4s
// of one interview creates two sessions with identical transcripts, doubles the
// LLM spend, and corrupts cross-session theming, silently.
//
// So the selection ladder below is the most load-bearing type here.

// MARK: - File taxonomy

/// `recording_files[].file_type`, as Zoom actually emits it.
///
/// **Never validate against Zoom's published enum.** `TIMELINE` is described in
/// the docs, emitted in practice, and absent from the enum; `TB` and
/// `CHAT_MESSAGE` are in the enum and described nowhere in the 1.19 MB spec. An
/// adapter that rejects unknown values would drop real files, so the unknown
/// case is carried rather than refused.
enum ZoomFileType: Equatable {
    case mp4
    case m4a
    case transcript
    case closedCaption
    case chat
    case timeline
    case poll
    case summary
    case thumbnail
    case other(String)

    init(_ raw: String) {
        switch raw.uppercased() {
        case "MP4":                  self = .mp4
        case "M4A":                  self = .m4a
        case "TRANSCRIPT":           self = .transcript
        case "CC":                   self = .closedCaption
        case "CHAT", "CHAT_MESSAGE": self = .chat
        case "TIMELINE":             self = .timeline
        case "CSV":                  self = .poll
        case "SUMMARY":              self = .summary
        case "TB":                   self = .thumbnail
        default:                     self = .other(raw)
        }
    }

    /// Whether this file carries the conversation itself.
    var isMedia: Bool { self == .mp4 || self == .m4a }
}

/// `recording_files[].recording_type` — the *layout*, not the content.
///
/// The name is a template, not an observation: `shared_screen_with_speaker_view`
/// is emitted even when nothing was ever shared. Zoom staff have conceded the
/// published semantics are incomplete and partly wrong, so this enum ranks the
/// values rather than claiming to define them.
enum ZoomRecordingLayout: Equatable {
    case sharedScreenWithSpeakerView
    case sharedScreenWithGalleryView
    case activeSpeaker
    case galleryView
    case sharedScreen
    case audioOnly
    case audioTranscript
    case other(String)

    init(_ raw: String) {
        switch raw {
        case "shared_screen_with_speaker_view": self = .sharedScreenWithSpeakerView
        case "shared_screen_with_gallery_view": self = .sharedScreenWithGalleryView
        case "active_speaker":                  self = .activeSpeaker
        case "gallery_view":                    self = .galleryView
        case "shared_screen":                   self = .sharedScreen
        case "audio_only":                      self = .audioOnly
        case "audio_transcript":                self = .audioTranscript
        default:                                self = .other(raw)
        }
    }

    /// Preference order when several MP4s exist, best first.
    ///
    /// Screens before faces: Bristlenose's researcher is testing a digital
    /// product, so the screen is the evidence and the participant's face is the
    /// supporting witness. A layout that carries both wins; then any layout
    /// with the screen; then faces. (Faces came first until 18 Oct 2026, on an
    /// interview premise, which would drop the product for a host who records
    /// screen and speaker as separate files.) Lower is better; `nil` means
    /// "not a video layout".
    var videoRank: Int? {
        switch self {
        case .sharedScreenWithSpeakerView: return 0
        case .sharedScreenWithGalleryView: return 1
        case .sharedScreen:                return 2
        case .activeSpeaker:               return 3
        case .galleryView:                 return 4
        case .audioOnly, .audioTranscript: return nil
        case .other:                       return 5
        }
    }
}

/// One file inside a Zoom recording.
struct ZoomRecordingFile: Equatable {
    let id: String?
    let fileType: ZoomFileType
    let layout: ZoomRecordingLayout
    /// Absent on `CC` and `TIMELINE` files, which carry no `file_size` at all —
    /// so a "total bytes" figure must treat nil as unknown rather than zero, or
    /// the progress bar lies.
    let sizeBytes: Int64?
    let downloadURL: URL?
    let recordingStart: Date?
    /// Where this file's span ends. With `recordingStart` it is what tells the
    /// parts of a stopped-and-restarted meeting apart, and which transcript
    /// belongs to which part.
    var recordingEnd: Date? = nil

    /// Zoom's per-file `status`. Read in one direction only.
    ///
    /// `completed` is **not** proof a file is ready: the main recordings page
    /// publishes `["completed"]` and nothing else, and reading it as readiness
    /// is how an importer downloads a transcript that does not exist yet.
    /// Readiness is the `TRANSCRIPT` file appearing in the listing.
    /// `GET /meetings/{id}/transcript` is **not** that check either: it serves
    /// the AI Companion transcript, a different artefact from the recording's
    /// VTT (Zoom's OpenAPI spec, read 30 Sep 2026).
    ///
    /// But `processing` and `failed` are documented on Zoom's account-level
    /// recordings pages (read 18 Oct 2026), and when present they can only make
    /// the import more careful: a meeting whose video is still processing must
    /// not be offered as audio, because the audio import would then match the
    /// video row as already imported and the video would never be offered.
    /// Absent means ready, as before.
    var status: String? = nil

    var isStillProcessing: Bool { status == "processing" }
    var hasFailed: Bool { status == "failed" }

    var isDownloadable: Bool { downloadURL != nil }
}

// MARK: - Selection

/// Picks what to actually import from a meeting's file set.
///
/// The rule that matters: **exactly one media file**, never two. Two MP4s of
/// one interview are the same conversation twice; ingesting both produces two
/// sessions with identical transcripts, doubles LLM spend on every stage, and
/// silently changes cross-session theming — stages 10 and 11 cluster *across*
/// sessions, so a duplicate does not add a row, it changes the answer.
enum ZoomFileSelection {

    struct Choice: Equatable {
        /// The single media file to fetch.
        let media: ZoomRecordingFile?
        /// The VTT, when Zoom made one.
        let transcript: ZoomRecordingFile?
        /// Media files deliberately not fetched. Surfaced rather than dropped,
        /// so "why did it only take one of my three recordings?" has an answer.
        let skippedMedia: [ZoomRecordingFile]
    }

    /// **The video, whenever Zoom made one; the audio only when it did not.**
    /// Bristlenose's premise is a researcher testing a digital product, so what
    /// was on screen is evidence: thumbnails, the scene timeline, screen text
    /// and the clips all come from the video. Until 18 Oct 2026 this took the
    /// M4A by default to save download time (~20 MB/hour against ~200), which
    /// quietly stripped every Zoom import of those. Stage 2 takes the audio out
    /// of the video itself, so nothing needs the M4A when a video exists.
    static func choose(from files: [ZoomRecordingFile]) -> Choice {
        let transcript = files.first { $0.fileType == .transcript }
        let audio = files.first { $0.fileType == .m4a }
        let videos = files
            .filter { $0.fileType == .mp4 }
            .sorted { ($0.layout.videoRank ?? 99) < ($1.layout.videoRank ?? 99) }

        let chosen = videos.first ?? audio

        let skipped = files
            .filter { $0.fileType.isMedia }
            .filter { $0 != chosen }

        return Choice(media: chosen, transcript: transcript, skippedMedia: skipped)
    }

    /// Whether a meeting's recording is not ready to offer: no media file yet
    /// (Zoom lists a call the moment recording starts), or any media file still
    /// processing. One media file processing holds back the whole meeting,
    /// deliberately: offering the finished audio while the video processes is
    /// how a researcher ends up with audio only, for good.
    static func isStillProcessing(_ files: [ZoomRecordingFile]) -> Bool {
        let media = files.filter { $0.fileType.isMedia && !$0.hasFailed }
        return media.isEmpty || media.contains(where: \.isStillProcessing)
    }

    /// One recording of a meeting. A host who stops and restarts recording
    /// gets one part per stretch, each with its own renditions and its own
    /// transcript.
    struct Part: Equatable {
        let choice: Choice
        let start: Date?
        let end: Date?
    }

    /// How far apart two media files' starts may sit and still be renditions
    /// of the same stretch. Every rendition of a part carried the identical
    /// `recording_start` string in the 2026 samples, so this only absorbs
    /// rounding. Widening it buys nothing and merges real parts: the next
    /// part's start is the previous part's start plus its length, so only a
    /// part shorter than this can be merged with the one after it.
    static let partTolerance: TimeInterval = 5

    /// The meeting's files, split into its parts, in the order they happened.
    ///
    /// **`choose` alone takes the first media file and the first transcript,
    /// so every part after the first was silently dropped.** Here the media
    /// files are grouped by start time, `choose` picks one rendition per group,
    /// and each transcript goes to the group it overlaps most.
    ///
    /// A meeting whose media files do not all carry a start has nothing to
    /// split on, and comes back as one part, exactly as `choose` saw it.
    static func parts(from files: [ZoomRecordingFile]) -> [Part] {
        let media = files.filter { $0.fileType.isMedia }
        let starts = media.compactMap(\.recordingStart)
        guard !media.isEmpty, starts.count == media.count else {
            let choice = choose(from: files)
            return [Part(choice: choice, start: choice.media?.recordingStart,
                         end: choice.media?.recordingEnd)]
        }

        var groups: [[ZoomRecordingFile]] = []
        for file in media.sorted(by: { $0.recordingStart! < $1.recordingStart! }) {
            if let anchor = groups.last?.first?.recordingStart,
               file.recordingStart!.timeIntervalSince(anchor) <= partTolerance {
                groups[groups.count - 1].append(file)
            } else {
                groups.append([file])
            }
        }
        let spans: [(start: Date, end: Date?)] = groups.map { group in
            (group.compactMap(\.recordingStart).min()!, group.compactMap(\.recordingEnd).max())
        }

        var transcriptFor: [Int: ZoomRecordingFile] = [:]
        let transcripts = files
            .filter { $0.fileType == .transcript }
            .sorted { ($0.recordingStart ?? .distantPast) < ($1.recordingStart ?? .distantPast) }
        for transcript in transcripts {
            guard let index = bestSpan(for: transcript, among: spans),
                  transcriptFor[index] == nil else { continue }
            transcriptFor[index] = transcript
        }

        return groups.enumerated().map { index, group in
            let choice = choose(from: group + [transcriptFor[index]].compactMap { $0 })
            return Part(choice: choice, start: spans[index].start, end: spans[index].end)
        }
    }

    /// The part a transcript belongs to: the one it overlaps most, else the
    /// one whose start is nearest within `partTolerance`. A transcript that
    /// fits none is left out rather than pinned to the wrong stretch of talk.
    private static func bestSpan(
        for transcript: ZoomRecordingFile,
        among spans: [(start: Date, end: Date?)]
    ) -> Int? {
        guard let tStart = transcript.recordingStart else {
            return spans.count == 1 ? 0 : nil
        }
        let tEnd = transcript.recordingEnd ?? tStart
        var best: (index: Int, overlap: TimeInterval)?
        for (index, span) in spans.enumerated() {
            let end = span.end ?? span.start
            let overlap = min(end, tEnd).timeIntervalSince(max(span.start, tStart))
            if overlap > 0, overlap > (best?.overlap ?? 0) { best = (index, overlap) }
        }
        if let best { return best.index }
        let nearest = spans.indices.min {
            abs(spans[$0].start.timeIntervalSince(tStart)) < abs(spans[$1].start.timeIntervalSince(tStart))
        }
        guard let nearest,
              abs(spans[nearest].start.timeIntervalSince(tStart)) <= partTolerance else { return nil }
        return nearest
    }
}

// MARK: - Transcript availability

/// What a Zoom row's Transcript cell says before anything is fetched.
///
/// Zoom has no "being produced" signal. The file appears in the listing when
/// it is ready, typically 15–30 minutes after the video and occasionally much
/// later, and is sometimes never produced at all. So *Expected* is inferred:
/// the account makes transcripts and the recording is recent enough for one to
/// still be coming.
enum ZoomTranscriptAvailability {
    /// How long after a recording ends a missing transcript is still waited
    /// for. Zoom's own figure for the slow case is "up to 24 hours".
    static let productionWindow: TimeInterval = 24 * 3600

    /// - Parameter audioTranscriptEnabled: the account's "Create audio
    ///   transcript" setting, nil when the preflight could not be read. Nil
    ///   waits for nothing: a row that waits on a setting nobody could read
    ///   could wait for a transcript that is never coming.
    static func decide(
        hasTranscript: Bool,
        audioTranscriptEnabled: Bool?,
        recordingEnded: Date?,
        now: Date
    ) -> TranscriptAvailability {
        if hasTranscript { return .available }
        guard audioTranscriptEnabled == true,
              let recordingEnded,
              now.timeIntervalSince(recordingEnded) < productionWindow
        else { return .notProvided }
        return .expected
    }
}

// MARK: - Expiry

/// Zoom's per-recording expiry, and the honesty about its absence.
///
/// **This is the one thing Zoom does that Google cannot.** The list response
/// carries `auto_delete` and `auto_delete_date` per meeting — an absolute date,
/// no second call — so §9's "expires in N days" countdown, and the
/// soonest-expiring-first fetch order it justifies, are buildable here exactly
/// as the Teams design imagined them.
///
/// Three states, and the middle one is the trap.
enum ZoomExpiry: Equatable {
    /// Auto-delete is on and the date is known.
    case on(Date)
    /// Auto-delete is off for this recording.
    ///
    /// **This does NOT mean "never expires".** The host simply has not enabled
    /// the setting; an admin can enable it tomorrow, account-level retention
    /// can still apply, and storage-quota pressure removes recordings by other
    /// means. Rendering this as "never" would be the one claim in the column a
    /// researcher might actually rely on, and it is the one we cannot make.
    case notSet
    /// Already in the trash. Recoverable for a period Zoom does not expose —
    /// there is no `permanent_delete_date` field, so a countdown here would be
    /// invented.
    case trashed(deletedAt: Date?)

    init(autoDelete: Bool?, autoDeleteDate: Date?, deletedTime: Date?) {
        if let deletedTime {
            self = .trashed(deletedAt: deletedTime)
        } else if autoDelete == true, let autoDeleteDate {
            self = .on(autoDeleteDate)
        } else {
            self = .notSet
        }
    }

    var date: Date? {
        if case .on(let date) = self { return date }
        return nil
    }
}

// MARK: - API outcomes

/// What a Zoom API response means, as distinct from what its status says.
///
/// Zoom's overloads are its own. The two that matter:
///
/// - **A 200 with `total_records: 0` is the most likely failure**, and it is
///   not an error at all — see `ZoomListWindow`. The default date window is
///   *one day*, so an unparameterised call reports an empty account.
/// - **A 200 with an HTML body** is a documented download failure mode. Bytes
///   that are `text/html` must never reach a `.mp4`.
enum ZoomAPIOutcome: Equatable {
    case ok
    case needsReauthentication
    /// The plan does not include cloud recording. Terminal — no consent, no
    /// retry, and no amount of waiting fixes it.
    case planDoesNotInclude
    case scopeNotGranted
    case notFound
    case rateLimited(retryAfter: TimeInterval?)
    case transient(status: Int)
    case unexpected(status: Int, code: Int?)

    enum RetryPolicy: Equatable {
        case never
        case onceAfterReauthentication
        case backoff(after: TimeInterval?)
    }

    var retryPolicy: RetryPolicy {
        switch self {
        case .ok, .planDoesNotInclude, .scopeNotGranted, .notFound:
            return .never
        case .needsReauthentication:
            return .onceAfterReauthentication
        case .rateLimited(let after):
            return .backoff(after: after)
        case .transient:
            return .backoff(after: nil)
        case .unexpected:
            return .never
        }
    }
}

enum ZoomResponseClassifier {
    private struct Envelope: Decodable {
        let code: Int?
        let message: String?
    }

    /// Zoom error codes that carry meaning here. Zoom's `code` is its own
    /// numbering, independent of the HTTP status.
    enum Code {
        static let invalidAccessToken = 124
        /// "Invalid access token, does not contain scopes."
        static let missingScopes = 4700
        /// "This user is not allowed to access this resource."
        static let notAllowed = 3001
        /// "There is no recording for this meeting/session." Genuinely empty,
        /// not a refusal — though Zoom staff note it is *also* what an
        /// account-level recording restriction can look like.
        static let noRecording = 3301
        /// The overloaded one. Appears as a body code alongside HTTP **200**
        /// meaning "You do not have the right permissions", and separately
        /// alongside 401 and 429. Never branch on this number alone.
        static let noPermissionInBody = 200
    }

    /// The admin-imposed download block, which Zoom reports in prose only and
    /// only at download time — there is no discovery-time signal for it,
    /// because lock state is invisible to a non-admin token.
    private static func mentionsAdminBlock(_ message: String) -> Bool {
        let m = message.lowercased()
        return m.contains("disabled by the administrator")
            || m.contains("do not have the right permissions")
            || m.contains("not allowed to access")
    }

    static func classify(
        status: Int,
        body: Data?,
        retryAfter: TimeInterval? = nil
    ) -> ZoomAPIOutcome {
        let envelope = body.flatMap { try? JSONDecoder().decode(Envelope.self, from: $0) }
        let message = envelope?.message ?? ""

        switch status {
        case 200...299:
            // **Zoom can deliver a permission denial as HTTP 200 carrying
            // `"code": 200` in the body.** Documented on
            // `GET /meetings/{id}/recordings` as *"You do not have the right
            // permissions."* — with a 200 status line.
            //
            // This is the worst failure shape in the whole adapter, and it is
            // why this function exists rather than a `response.ok` check. A
            // client that branches on the status treats the denial as success,
            // finds no `recording_files`, and renders "no recordings for this
            // meeting" — the researcher concludes the session was never
            // recorded, and the expiry clock they came here to beat keeps
            // running. Same family as the Teams 401-that-means-no-licence: a
            // status code is not a remedy.
            //
            // The admin-block message ("Download has been disabled by the
            // administrator") arrives the same way, and only at download time.
            if let code = envelope?.code, code != 0 {
                // Message before code, always. Code 200-in-a-200 is the generic
                // bucket Zoom uses for several unrelated refusals, so matching
                // it first would swallow the specific ones — a plan refusal
                // would render as "ask your admin for permission", sending the
                // researcher to a person who cannot help.
                if mentionsPlan(message) { return .planDoesNotInclude }
                if mentionsAdminBlock(message) || code == Code.noPermissionInBody {
                    return .scopeNotGranted
                }
                return .unexpected(status: status, code: code)
            }
            return .ok

        case 400, 401:
            // 124 is Zoom's "invalid access token" and arrives as both 400 and
            // 401 depending on endpoint. Matching the code rather than the
            // status is what keeps a plan refusal from being retried forever as
            // if it were an expired token.
            if envelope?.code == Code.invalidAccessToken { return .needsReauthentication }
            if mentionsPlan(message) { return .planDoesNotInclude }
            return .needsReauthentication

        case 403:
            if mentionsPlan(message) { return .planDoesNotInclude }
            return .scopeNotGranted

        case 404:
            return .notFound

        case 429:
            return .rateLimited(retryAfter: retryAfter)

        case 500...599:
            return .transient(status: status)

        default:
            return .unexpected(status: status, code: envelope?.code)
        }
    }

    /// Zoom states the plan requirement in prose rather than in a code:
    /// "Must have a Pro or a higher plan."
    private static func mentionsPlan(_ message: String) -> Bool {
        let m = message.lowercased()
        return m.contains("pro or a higher plan")
            || m.contains("higher plan")
            || m.contains("plan does not")
            || m.contains("not available for your plan")
    }
}

// MARK: - The date window

/// Zoom's `from`/`to` window, and the two rules that make it lie.
///
/// **Rule 1 — the default is one day, not everything.** Omit `from`/`to` and
/// Zoom answers for today only. An unparameterised call against a busy account
/// returns `total_records: 0`, which reads as "you have no recordings" and is
/// the single most reported confusion in the developer forum.
///
/// **Rule 2 — the maximum range is one month.** A 90-day look-back is three
/// sequential calls, not one wider one. Silently, a wider request does not
/// error — so an importer that asks for 90 days and renders what comes back has
/// simply lost two thirds of the study.
///
/// Both produce a *shorter list*, which is this feature's designed output as
/// well as its failure mode. Hence a type, rather than two string parameters.
struct ZoomListWindow: Equatable {
    let start: Date
    let end: Date

    /// Splits an arbitrary interval into Zoom-legal month-long chunks.
    ///
    /// - Parameter monthDays: 29, so a chunk's dates span 30 inclusive days.
    ///   Zoom documents "a month" without defining it, and its `from`/`to` are
    ///   inclusive dates (a meeting on a boundary day comes back from both
    ///   chunks, measured 18 Oct 2026). At 30, every chunk asked for 31 dates;
    ///   if Zoom trims to 30 it drops the oldest day of each chunk silently,
    ///   which is the whole class of bug this type exists to prevent.
    static func chunks(
        covering interval: DateInterval,
        monthDays: Int = 29,
        calendar: Calendar = .current
    ) -> [ZoomListWindow] {
        guard interval.duration > 0 else {
            return [ZoomListWindow(start: interval.start, end: interval.end)]
        }
        var windows: [ZoomListWindow] = []
        var cursor = interval.start
        while cursor < interval.end {
            let next = calendar.date(byAdding: .day, value: monthDays, to: cursor) ?? interval.end
            windows.append(ZoomListWindow(start: cursor, end: min(next, interval.end)))
            cursor = next
        }
        return windows
    }

    /// `yyyy-MM-dd`, UTC — Zoom's documented format for these two parameters.
    /// A local-timezone rendering shifts the boundary by up to a day and drops
    /// meetings at each edge, which is the same hazard the Teams design found
    /// in `calendarView`.
    var fromString: String { Self.formatter.string(from: start) }
    var toString: String { Self.formatter.string(from: end) }

    private static let formatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd"
        f.timeZone = TimeZone(secondsFromGMT: 0)
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()
}

// MARK: - Identifiers

enum ZoomIdentifier {
    /// Percent-encodes a meeting UUID for use in a path.
    ///
    /// **Double-encoded when it starts with `/` or contains `//`** — Zoom's own
    /// documented requirement, and the reason a base64 UUID like
    /// `/ajXp112QmuoKj4854875==` returns a 404 that reads as "meeting not
    /// found" rather than "you encoded it wrong". Base64 UUIDs routinely
    /// contain `/` and `+`, so this is the common case, not the exotic one.
    static func encodedUUID(_ uuid: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-._~"))
        let once = uuid.addingPercentEncoding(withAllowedCharacters: allowed) ?? uuid
        guard uuid.hasPrefix("/") || uuid.contains("//") else { return once }
        return once.addingPercentEncoding(withAllowedCharacters: allowed) ?? once
    }
}

// MARK: - Transcript

/// Parses a Zoom `audio_transcript.vtt`.
///
/// Zoom puts the speaker in the cue *payload* as a `Name: ` prefix, not in the
/// WebVTT `<v>` voice tag — undocumented, and established from working parsers
/// rather than from a spec. Two consequences the naive version gets wrong:
///
/// - **Split on the FIRST colon only.** "the ratio was 3:1" is dialogue, not a
///   speaker change, and a greedy split turns a sentence into a speaker named
///   "the ratio was 3".
/// - **Attribution is best-effort.** Cues arrive without names often enough
///   that an importer which assumes them will produce sessions with one speaker
///   called by the first word of the interview. Absent names fall through to
///   Bristlenose's own speaker-identification stage.
enum ZoomTranscript {

    struct Cue: Equatable {
        let speaker: String?
        let text: String
    }

    /// A speaker prefix is only believed when it looks like a display name.
    ///
    /// **This is the only name check a Zoom transcript gets.** The file it
    /// feeds is a cloud transcript, and `s03_parse_subtitles.py` trusts a
    /// cloud transcript's `<v>` tags rather than re-guessing — so a name this
    /// rejects keeps its `Name:` prefix inside the quote, and a phrase this
    /// accepts becomes a participant. It therefore follows the pipeline's own
    /// `_looks_like_speaker_name`: letters in any script, the punctuation real
    /// names carry (`Dr. Patel`, `Patel, Anita`, `O'Brien`, `(Guest)`), the
    /// ASCII or full-width colon, and the same list of words that open a
    /// sentence and take a colon.
    ///
    /// Three departures, all deliberate. **Digits are allowed** — "Participant
    /// 04" and "P07" are exactly the display names a study uses. **A name in a
    /// cased script must start with a capital**, which is what keeps "the
    /// ratio was 3:1" from registering a speaker now that digits pass; a
    /// script without case (Japanese, Chinese, Arabic) has no capital to need,
    /// and a lowercase label is believed only when it recurs (below). And **a
    /// stop word followed by a comma or full stop rejects the whole prefix**
    /// ("Honestly, I gave up"), which the pipeline's whole-name check lets
    /// through. Only the digits accept anything the pipeline would refuse.
    ///
    /// - Parameter recurring: lowercase labels this file uses often enough to
    ///   be display names (`cues(fromVTT:)` finds them). A handle like `stay`
    ///   or `nutzipper` is a real Zoom display name; a sentence fragment does
    ///   not open three cues.
    static func splitSpeaker(_ payload: String, recurring: Set<String> = []) -> Cue {
        guard let (candidate, rest) = prefix(of: payload),
              !rest.isEmpty,
              looksLikeName(candidate) || recurring.contains(candidate)
        else {
            return Cue(speaker: nil, text: payload)
        }
        // Zoom's own label for speech it could not attribute. Not a person:
        // the words are kept, unnamed, so the pipeline's split gate sees them
        // honestly rather than as a participant called "Unknown Speaker".
        if candidate.caseInsensitiveCompare("Unknown Speaker") == .orderedSame {
            return Cue(speaker: nil, text: rest)
        }
        return Cue(speaker: candidate, text: rest)
    }

    /// The text before the first colon, and the text after it, trimmed.
    private static func prefix(of payload: String) -> (String, String)? {
        guard let colon = payload.firstIndex(where: { $0 == ":" || $0 == "：" }) else { return nil }
        return (String(payload[..<colon]).trimmingCharacters(in: .whitespaces),
                String(payload[payload.index(after: colon)...]).trimmingCharacters(in: .whitespaces))
    }

    /// How many cues a lowercase label must open before it is believed.
    static let recurringLabelMinimum = 3

    static func looksLikeName(_ candidate: String, allowingLowercase: Bool = false) -> Bool {
        guard let first = candidate.first,
              first.isLetter || first.isNumber,
              allowingLowercase || !first.isLowercase,
              candidate.count <= 60
        else { return false }
        let words = candidate.split(whereSeparator: { $0 == " " || $0 == "\u{3000}" })
        guard words.count <= maxNameWords else { return false }
        for character in candidate {
            if character.isLetter || character.isNumber || namePunctuation.contains(character) {
                continue
            }
            return false
        }
        if notSpeakerWords.contains(candidate.lowercased()) { return false }
        // A stop word that opens a clause: "Honestly, I gave up" or "Okay. So
        // the thing" — its comma or full stop would otherwise let it through as
        // a name. Only with that punctuation, or on a lowercase label: "Oh
        // Minji" and "So Yeon Kim" are people, and Oh and So are surnames.
        guard let firstRaw = words.first else { return true }
        let firstWord = firstRaw.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: ".,"))
        let opensClause = firstRaw.last == "," || firstRaw.last == "." || first.isLowercase
        return !(opensClause && notSpeakerWords.contains(firstWord))
    }

    /// `_MAX_NAME_TOKENS` in `s03_parse_subtitles.py`.
    static let maxNameWords = 6

    /// `_NAME_PUNCTUATION` and `_NAME_JOINERS` in `s03_parse_subtitles.py`.
    private static let namePunctuation: Set<Character> = [
        " ", ".", "'", "’", ",", "-", "(", ")", "/", "|", "&", "\u{200C}", "\u{200D}",
        // The ideographic space, between family and given name in CJK display
        // names ("田中　花子"), seen in real Zoom transcripts.
        "\u{3000}",
    ]

    /// `_NOT_SPEAKER_WORDS` in `s03_parse_subtitles.py`, verbatim. Discourse
    /// words, labels and URL schemes only — never anyone's given name.
    /// `ZoomTranscriptTests.stopWordsMirrorThePipeline` keeps the two equal.
    static let notSpeakerWords: Set<String> = [
        "honestly", "note", "notes", "also", "well", "okay", "ok", "yes", "no", "right", "basically",
        "actually", "example", "warning", "question", "answer", "summary", "update", "edit",
        "reminder", "important", "ps", "nb", "re", "fwd", "subject", "translation", "transcript",
        "caption", "captions", "anyway", "because", "however", "meanwhile", "finally", "obviously",
        "clearly", "frankly", "seriously", "listen", "wait", "hmm", "hm", "oh", "ah", "mm",
        "mhm", "huh", "hey", "hi", "hello", "thanks", "sorry", "please", "cheers", "maybe",
        "perhaps", "probably", "certainly", "sure", "exactly", "totally", "absolutely", "definitely",
        "really", "truly", "yep", "nope", "nah", "um", "uh", "yeah", "like", "so", "then",
        "http", "https", "mailto", "tel", "gern", "hinweis", "anmerkung", "beispiel", "frage",
        "antwort", "achtung", "wichtig", "genau", "übrigens", "ähm", "nota", "ejemplo", "exemplo",
        "exemple", "pregunta", "respuesta", "resposta", "réponse", "atención", "atenção", "attention",
        "bueno", "pues", "alors", "donc", "voilà", "enfin", "bref", "então", "pois",
    ]

    /// Every cue in a Zoom VTT, with the `Name:` prefix moved out of the text.
    ///
    /// Times stay on the file's own clock, which on Zoom is already the
    /// recording's. What comes back goes through `PlatformTranscriptRebase`
    /// and `PlatformTranscriptWriter`, so the file Bristlenose writes is
    /// always its own bytes, never Zoom's.
    ///
    /// A block with no timing line (the header, a `NOTE`, a `STYLE`) is
    /// skipped; a timing line that does not parse drops its cue rather than
    /// guessing a time.
    static func cues(fromVTT text: String) -> [PlatformTranscriptCue] {
        let normalised = text
            .replacingOccurrences(of: "\r\n", with: "\n")
            .replacingOccurrences(of: "\r", with: "\n")
        var timed: [(start: TimeInterval, end: TimeInterval, payload: String)] = []
        // A blank line may hold stray spaces; it still ends the cue.
        let blocks = normalised.replacingOccurrences(
            of: "\n[ \t]+\n", with: "\n\n", options: .regularExpression)
        for block in blocks.components(separatedBy: "\n\n") {
            let lines = block.split(separator: "\n", omittingEmptySubsequences: true)
            guard let timing = lines.firstIndex(where: { $0.contains("-->") }) else { continue }
            let halves = lines[timing].components(separatedBy: "-->")
            guard halves.count == 2,
                  let start = timestamp(halves[0]),
                  let endToken = halves[1].split(separator: " ").first,
                  let end = timestamp(String(endToken)),
                  end > start
            else { continue }
            let payload = lines[(timing + 1)...]
                .map { $0.trimmingCharacters(in: .whitespaces) }
                .joined(separator: " ")
            timed.append((start, end, unescape(payload)))
        }

        // Real transcripts carry lowercase handles as display names — measured
        // on a 2025 call where `stay` and `nutzipper` opened 227 of 505 cues
        // and the capital-letter rule dropped every one. A label that opens
        // several cues is a name whatever its case.
        var counts: [String: Int] = [:]
        for cue in timed {
            guard let (candidate, rest) = prefix(of: cue.payload), !rest.isEmpty,
                  candidate.first?.isLowercase == true,
                  looksLikeName(candidate, allowingLowercase: true) else { continue }
            counts[candidate, default: 0] += 1
        }
        let recurring = Set(counts.filter { $0.value >= recurringLabelMinimum }.keys)

        return timed.compactMap { cue in
            let split = splitSpeaker(cue.payload, recurring: recurring)
            guard !split.text.isEmpty else { return nil }
            return PlatformTranscriptCue(start: cue.start, end: cue.end,
                                         speaker: split.speaker, text: split.text)
        }
    }

    /// `HH:MM:SS.mmm` or `MM:SS.mmm`, as WebVTT allows. Nil on anything else.
    static func timestamp(_ raw: String) -> TimeInterval? {
        let fields = raw.trimmingCharacters(in: .whitespaces).split(separator: ":")
        guard (2...3).contains(fields.count) else { return nil }
        var total: TimeInterval = 0
        for field in fields {
            guard let value = Double(field), value >= 0 else { return nil }
            total = total * 60 + value
        }
        return total
    }

    /// The three entities WebVTT text uses. The writer escapes them again, so
    /// leaving them escaped here would double them in the file it writes.
    private static func unescape(_ text: String) -> String {
        text.replacingOccurrences(of: "&lt;", with: "<")
            .replacingOccurrences(of: "&gt;", with: ">")
            .replacingOccurrences(of: "&amp;", with: "&")
    }
}

// MARK: - When the call was booked

/// The booked time of the meeting a recording belongs to, from
/// `GET /meetings/{id}`.
///
/// Zoom meeting `type`: 1 instant, 2 scheduled, 3 recurring with no fixed
/// time, 4 personal meeting room, 8 recurring with a fixed time.
enum ZoomSchedule {

    struct Booking: Equatable {
        let start: Date
        let duration: TimeInterval?
    }

    /// How far a booking may sit from the recording and still be its booking.
    /// The store's listing window already allows three hours in the other
    /// direction, for the same reason: people start late, and early.
    static let tolerance: TimeInterval = 3 * 3600

    /// Zoom's "instant meeting" (New Meeting): started, never booked. The one
    /// type Bristlenose can label as such. A personal room has no booking either,
    /// but Zoom does not call it instant, so it gets no label.
    static func isInstant(type: Int?) -> Bool { type == 1 }

    /// Whether a booking is worth asking Zoom for: a scheduled meeting or a
    /// recurring one with fixed times. An unknown type is asked about too,
    /// since asking costs one call and guessing costs the column.
    static func mayHaveBooking(type: Int?) -> Bool {
        guard let type else { return true }
        return type == 2 || type == 8
    }

    /// The booking for a recording that started at `recordingStart`.
    ///
    /// **For a recurring meeting, the occurrence nearest the recording — never
    /// the top-level `start_time`.** Zoom's own forum reports that field as the
    /// last occurrence (or worse), so trusting it puts every session of a
    /// weekly study on one date. A booking further than `tolerance` from the
    /// recording is not its booking: a one-off meeting ID can be started days
    /// after the time it was booked for.
    static func booking(
        start: Date?,
        duration: TimeInterval?,
        occurrences: [Booking],
        near recordingStart: Date
    ) -> Booking? {
        let candidates = occurrences.isEmpty
            ? start.map { [Booking(start: $0, duration: duration)] } ?? []
            : occurrences
        guard let nearest = candidates.min(by: {
            abs($0.start.timeIntervalSince(recordingStart)) < abs($1.start.timeIntervalSince(recordingStart))
        }) else { return nil }
        return abs(nearest.start.timeIntervalSince(recordingStart)) <= tolerance ? nearest : nil
    }
}
