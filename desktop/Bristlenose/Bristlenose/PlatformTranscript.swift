import Foundation

// The transcript file the import writes beside a recording, and the arithmetic
// that puts it on the recording's clock.
//
// This is the Swift half of the contract in docs/design-cloud-import-transcripts.md
// §4. The other half is `bristlenose/stages/s03_parse_subtitles.py`, which reads
// what this writes — so the shape here is not a style choice but a wire format,
// pinned byte for byte by `PlatformTranscriptTests` against the golden files in
// `tests/fixtures/platform-transcripts/`, which pytest parses on the other side.
//
// Pure values and pure functions. No I/O, no networking, no AppKit — the
// adapter that owns the network (`GoogleMeetSource`) builds the cues, calls
// these, and writes the bytes; nothing here knows which platform it serves.

// MARK: - What a cue is

/// One line of what someone said, on the **media file's** clock.
///
/// `start`/`end` are seconds from the recording's t=0 once `rebase` has run.
/// Before that they are on whatever clock the platform used — a conference's
/// start on Meet, the vendor's own zero on Zoom — and the only thing that turns
/// one into the other is `PlatformTranscriptRebase`.
struct PlatformTranscriptCue: Equatable, Sendable {
    var start: TimeInterval
    var end: TimeInterval
    /// The platform's display name for the speaker, or nil for a cue nobody is
    /// named on. **Never an invented "Speaker 1"**: an unnamed cue is written
    /// without a `<v>` tag, and the pipeline's split gate reads that honestly.
    var speaker: String?
    var text: String

    init(start: TimeInterval, end: TimeInterval, speaker: String? = nil, text: String) {
        self.start = start
        self.end = end
        self.speaker = speaker
        self.text = text
    }
}

// MARK: - The provenance block

/// The `NOTE bristlenose-cloud-transcript 1` block — §4 item 4.
///
/// Every field is something the pipeline reads: `source` for the citation,
/// `media` + `media-duration` so a trimmed recording can refuse its stale
/// transcript, `rebased-by` + `dropped-outside-media` so a misaligned file can
/// be diagnosed from the file alone. `speakers` is **derived from the cues** by
/// the writer, never stated by a caller, so the NOTE cannot contradict the body.
struct PlatformTranscriptNote: Equatable, Sendable {
    enum Source: String, Sendable { case teams, meet, zoom }

    /// The contract's major version. `s03` accepts any `1.x`, refuses other
    /// majors loudly — bump this only with a reader change on the Python side.
    static let version = 1

    var source: Source
    /// BCP-47 as the platform reported it (`pt-BR`, `en-GB`), or nil when it
    /// said nothing. The pipeline reduces it to the primary subtag for Whisper.
    var language: String?
    /// The media file's **basename** — the file this transcript belongs to.
    var media: String
    /// The probed length of that file, in seconds.
    var mediaDuration: TimeInterval
    /// The shift applied to the platform's clock to reach the media's t=0.
    /// Zero when the two already agreed; negative when the recording began
    /// after the platform's zero (cues before it were dropped).
    var rebasedBy: TimeInterval
    /// Cues that fell wholly outside `[0, media-duration]` and were dropped.
    var droppedOutsideMedia: Int
}

// MARK: - The writer

/// Renders cues and their NOTE as the WebVTT the pipeline reads.
///
/// Always *our* bytes, never the vendor's verbatim (§4 item 2): one `<v>` per
/// cue or none, no `Name:` prefix left in the text, values on one line, `& < >`
/// escaped. The reader unescapes, so a participant called "Ponte & Filhos" or a
/// screen named `<Pagamentos>` round-trips exactly.
enum PlatformTranscriptWriter {

    /// The whole file. Byte-identical to the golden fixtures for the same input.
    static func render(cues: [PlatformTranscriptCue], note: PlatformTranscriptNote) -> String {
        // Nothing said is not a cue. Filtered here rather than trusted to the
        // caller, because a blank payload line would end the cue block early
        // and the file would still parse — one empty caption, no error.
        let spoken = cues.filter { !$0.text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
        let named = spoken.contains { $0.speaker != nil }

        var header = "WEBVTT\n\nNOTE bristlenose-cloud-transcript \(PlatformTranscriptNote.version)\n"
        header += "source: \(note.source.rawValue)\n"
        header += "speakers: \(named ? "named" : "none")\n"
        if let language = note.language, !language.isEmpty {
            header += "language: \(noteValue(language))\n"
        }
        header += "media: \(noteValue(note.media))\n"
        header += "media-duration: \(seconds(note.mediaDuration))\n"
        header += "rebased-by: \(seconds(note.rebasedBy))\n"
        header += "dropped-outside-media: \(note.droppedOutsideMedia)\n"

        guard !spoken.isEmpty else { return header }
        let blocks = spoken.map { cue -> String in
            let payload = cue.speaker.map { "<v \(escape($0))>\(escape(cue.text))</v>" }
                ?? escape(cue.text)
            return "\(timestamp(cue.start)) --> \(timestamp(cue.end))\n\(payload)"
        }
        return header + "\n" + blocks.joined(separator: "\n\n") + "\n"
    }

    /// `HH:MM:SS.mmm`, hours always two digits — the long form every parser
    /// accepts, and the one the fixtures carry.
    static func timestamp(_ seconds: TimeInterval) -> String {
        let total = max(0, milliseconds(seconds))
        let h = total / 3_600_000
        let m = (total / 60_000) % 60
        let s = (total / 1_000) % 60
        let ms = total % 1_000
        return String(format: "%02d:%02d:%02d.%03d", h, m, s, ms)
    }

    /// `3131.420s`, `-12.400s`. Built from integer milliseconds rather than
    /// `%f`, so the decimal point is a point in every locale and the rounding
    /// is the same one `timestamp` uses.
    static func seconds(_ value: TimeInterval) -> String {
        let ms = milliseconds(value)
        let magnitude = abs(ms)
        return (ms < 0 ? "-" : "") + String(format: "%d.%03ds", magnitude / 1_000, magnitude % 1_000)
    }

    /// The three characters WebVTT reserves, then the two sequences that would
    /// break the *framing*: a newline ends a cue's payload, and `-->` inside a
    /// payload is what a lenient parser reads as a new timing line.
    static func escape(_ text: String) -> String {
        var out = text
            .replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
        out = oneLine(out)
        // `&gt;` has already replaced `>`, so the arrow can only survive as
        // `--&gt;`; strip that spelling too, or the escape would be the thing
        // that lets a timing line through.
        out = out.replacingOccurrences(of: "--&gt;", with: "")
        return out
    }

    /// A NOTE value stays on one line: the block ends at the first blank line
    /// and a second line would be read as the next key.
    static func noteValue(_ value: String) -> String { oneLine(value) }

    private static func oneLine(_ text: String) -> String {
        text.replacingOccurrences(of: "\r\n", with: " ")
            .replacingOccurrences(of: "\n", with: " ")
            .replacingOccurrences(of: "\r", with: " ")
            .trimmingCharacters(in: .whitespaces)
    }

    static func milliseconds(_ seconds: TimeInterval) -> Int {
        guard seconds.isFinite else { return 0 }
        return Int((seconds * 1_000).rounded())
    }
}

// MARK: - The clock

/// Puts cues on the media file's clock — §5c's rebase rule.
///
/// `s = S − t0`. A cue wholly outside `[0, D]` is dropped and counted, the rest
/// are clamped, and no time is ever negative. The arithmetic runs in integer
/// milliseconds so the file's `00:00:01.600` is decided once, here, rather than
/// by how `1.5999999999999996` happens to round at render time.
enum PlatformTranscriptRebase {

    struct Outcome: Equatable, Sendable {
        /// On the media's clock, clamped, strictly `end > start`, in input order.
        var cues: [PlatformTranscriptCue]
        /// Cues that fell wholly outside the media, or collapsed to nothing
        /// when clamped.
        var dropped: Int
    }

    /// How far past the media's end a cue may run before the whole transcript
    /// is refused rather than clamped (§5c). A second or two is the platform's
    /// own imprecision; forty seconds is the wrong recording.
    static let tailTolerance: TimeInterval = 2

    /// - Parameter shift: seconds added to every cue — `−t0` on the platform's
    ///   clock. Zero when the caller has already subtracted the media's start.
    /// - Parameter mediaDuration: the probed length of the media file, `D`.
    static func rebase(
        _ cues: [PlatformTranscriptCue],
        by shift: TimeInterval,
        mediaDuration: TimeInterval
    ) -> Outcome {
        let durationMs = PlatformTranscriptWriter.milliseconds(mediaDuration)
        var kept: [PlatformTranscriptCue] = []
        var dropped = 0
        for cue in cues {
            let startMs = PlatformTranscriptWriter.milliseconds(cue.start + shift)
            let endMs = PlatformTranscriptWriter.milliseconds(cue.end + shift)
            // Wholly before the record button, or wholly after the file ends.
            guard endMs > 0, startMs < durationMs else {
                dropped += 1
                continue
            }
            let clampedStart = max(0, startMs)
            let clampedEnd = min(durationMs, endMs)
            // A cue the clamp squeezed to nothing has no place in the media
            // either — and `end > start` is the contract.
            guard clampedEnd > clampedStart else {
                dropped += 1
                continue
            }
            var out = cue
            out.start = TimeInterval(clampedStart) / 1_000
            out.end = TimeInterval(clampedEnd) / 1_000
            kept.append(out)
        }
        return Outcome(cues: kept, dropped: dropped)
    }

    /// Whether the transcript's tail runs past the media by more than the
    /// tolerance — measured on the shifted cues **before** clamping, which is
    /// the check §0 found the first draft could never make (it looked after).
    ///
    /// True means refuse the transcript: a tail forty seconds long is not this
    /// recording's transcript, and clamping it would file the wrong session's
    /// words under this participant with every timing looking plausible.
    static func tailRunsPast(
        _ cues: [PlatformTranscriptCue],
        by shift: TimeInterval,
        mediaDuration: TimeInterval,
        tolerance: TimeInterval = tailTolerance
    ) -> Bool {
        guard let last = cues.map({ $0.end + shift }).max() else { return false }
        return last > mediaDuration + tolerance
    }
}
