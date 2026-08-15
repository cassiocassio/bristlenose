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
    /// Faces before screens: a research interview's value is in the person, and
    /// `shared_screen` alone is a slide deck with a voice over it. Lower is
    /// better; `nil` means "not a video layout".
    var videoRank: Int? {
        switch self {
        case .sharedScreenWithSpeakerView: return 0
        case .activeSpeaker:               return 1
        case .sharedScreenWithGalleryView: return 2
        case .galleryView:                 return 3
        case .sharedScreen:                return 4
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

    /// Deliberately NOT modelled: `status`. Its published enum is `["completed"]`
    /// and nothing else, so it can never indicate "not ready" — reading it as a
    /// readiness signal is how an importer downloads a transcript that does not
    /// exist yet. Readiness comes from `GET /meetings/{id}/transcript`'s
    /// `can_download`, which distinguishes NOT_READY from NO_TRANSCRIPT_DATA.
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

    /// - Parameter preferAudioOnly: take the M4A over the MP4 when both exist.
    ///
    ///   Default **true**, and it is a real optimisation rather than a
    ///   preference: Bristlenose's stage 2 extracts audio and discards the
    ///   video anyway, and Zoom's own figures put video at ~200 MB/hour against
    ///   ~20 MB/hour for screen share. Over a twelve-session study that is the
    ///   difference between a coffee break and a lunch break, on a transfer the
    ///   researcher is watching.
    ///
    ///   Set false when the video is wanted for its own sake — thumbnails, and
    ///   the timecode deep-links the report offers.
    static func choose(
        from files: [ZoomRecordingFile],
        preferAudioOnly: Bool = true
    ) -> Choice {
        let transcript = files.first { $0.fileType == .transcript }
        let audio = files.first { $0.fileType == .m4a }
        let videos = files
            .filter { $0.fileType == .mp4 }
            .sorted { ($0.layout.videoRank ?? 99) < ($1.layout.videoRank ?? 99) }

        let chosen: ZoomRecordingFile?
        if preferAudioOnly, let audio {
            chosen = audio
        } else {
            chosen = videos.first ?? audio
        }

        let skipped = files
            .filter { $0.fileType.isMedia }
            .filter { $0 != chosen }

        return Choice(media: chosen, transcript: transcript, skippedMedia: skipped)
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
    /// - Parameter monthDays: 30 rather than a calendar month. Zoom documents
    ///   "a month" without defining it, and 30 days is inside every reading —
    ///   an off-by-one at the boundary would drop a day silently, which is the
    ///   whole class of bug this type exists to prevent.
    static func chunks(
        covering interval: DateInterval,
        monthDays: Int = 30,
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

    /// A speaker prefix is only believed when it looks like a display name:
    /// short, no sentence punctuation. Prevents "So, honestly: I gave up" from
    /// registering a speaker.
    static func splitSpeaker(_ payload: String) -> Cue {
        guard let colon = payload.firstIndex(of: ":") else {
            return Cue(speaker: nil, text: payload)
        }
        let candidate = String(payload[..<colon]).trimmingCharacters(in: .whitespaces)
        let rest = String(payload[payload.index(after: colon)...])
            .trimmingCharacters(in: .whitespaces)

        // A display name starts with a capital and is a few words at most.
        // Length and punctuation alone are not enough: "the ratio was 3:1"
        // clears both and would register a speaker called "the ratio was 3" —
        // silently, on real interview content, for the whole session.
        //
        // Digits are deliberately allowed: "Participant 04" and "P07" are
        // exactly the display names a research study uses.
        let firstIsCapital = candidate.first.map {
            $0.isUppercase || ($0.isLetter == false && $0.isNumber)
        } ?? false
        let wordCount = candidate.split(separator: " ").count

        let plausible = !candidate.isEmpty
            && !rest.isEmpty
            && firstIsCapital
            && wordCount <= 5
            && candidate.count <= 48
            && !candidate.contains(".")
            && !candidate.contains("?")
            && !candidate.contains("!")
            && !candidate.contains(",")

        return plausible ? Cue(speaker: candidate, text: rest)
                         : Cue(speaker: nil, text: payload)
    }
}
