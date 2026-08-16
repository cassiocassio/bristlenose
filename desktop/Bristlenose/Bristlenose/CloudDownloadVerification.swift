import Foundation

// The shared "prove the bytes arrived" core — §6's second honest-batch
// requirement, for all three platforms.
//
// Pure values, no I/O, no networking, so every rule here is testable without
// an account, a tenant or a network. That matters more than usual: the failure
// this file exists to prevent is *invisible at the moment it happens* and only
// surfaces hours later, in a different stage, as a wrong answer rather than an
// error.
//
// The failure, stated once. A fetch whose only success signal is not-throwing
// will happily write a 401 body into a `.mp4`. The loud version dies at stage 2
// with a codec error. **The quiet version is a truncated-but-valid MP4**:
// ffprobe accepts it, Whisper transcribes forty minutes of a sixty-minute
// interview, and the report presents a confident, internally consistent
// analysis of a session it only half read. Nothing anywhere says so.
//
// Field evidence that this is real rather than fastidious: a developer ran the
// leading open-source Zoom downloader over ~2,000 recordings and **880 wrote a
// 59-byte JSON error body to disk as a `.mp4`** — every one logged as a
// successful download. Two independent maintainers converged on byte-count
// verification; one deleted his completed-downloads log outright because it
// "often erroneously classif[ied] recordings as successfully downloaded".

// MARK: - What a platform promises about a file

/// What we know about a file *before* fetching it, from the listing.
///
/// Every field is optional because the three platforms know different things,
/// and the design's rule is that an absent figure must read as *unknown* rather
/// than as zero — a nil size that verified as 0 would fail every file, and a
/// nil size treated as "no check needed" is how the 880 got written.
struct ExpectedFile: Equatable {
    /// The listing's own byte count. **An independent second source**: it
    /// catches a redirect that served something else entirely, which
    /// `Content-Length` alone cannot, because a wrong response has a perfectly
    /// consistent `Content-Length` of its own.
    let sizeBytes: Int64?

    /// A content hash the platform supplied *before* the download.
    ///
    /// Microsoft is the only one of the three that does this — a `driveItem`
    /// returns `quickXorHash`, `sha1Hash` and `sha256Hash` alongside `size` in
    /// the listing — which lets verification be **exact rather than
    /// heuristic**. Business OneDrive has historically returned only
    /// `quickXorHash`, so the algorithm varies while the check survives.
    let hash: FileHash?

    /// What the bytes should turn out to be, for the magic-number check.
    let expectedFormat: MediaFormat?

    init(sizeBytes: Int64? = nil, hash: FileHash? = nil, expectedFormat: MediaFormat? = nil) {
        self.sizeBytes = sizeBytes
        self.hash = hash
        self.expectedFormat = expectedFormat
    }
}

struct FileHash: Equatable {
    enum Algorithm: String, Equatable { case sha256, sha1, quickXor }
    let algorithm: Algorithm
    let value: String

    /// Hex/base64 comparison is case- and whitespace-insensitive across the
    /// three vendors' renderings; normalising here stops a correct download
    /// failing on presentation.
    func matches(_ other: String) -> Bool {
        value.trimmingCharacters(in: .whitespacesAndNewlines).caseInsensitiveCompare(
            other.trimmingCharacters(in: .whitespacesAndNewlines)) == .orderedSame
    }
}

// MARK: - Magic numbers

/// Container formats identified by their leading bytes.
///
/// The check exists because **every failure mode in this file produces a file
/// of plausible length**. An HTML login page is a few KB; a JSON error is 59
/// bytes; a truncated MP4 is most of a real one. Only the first few bytes
/// distinguish "this is a video" from "this is an apology".
enum MediaFormat: Equatable {
    case mp4      // also M4A — same ISO base-media container
    case webm
    case webvtt
    case unknown

    /// ISO base media files put a 4-byte size then `ftyp` at offset 4. The
    /// leading size varies, so the brand box is the signature, not byte zero —
    /// a naive prefix compare fails on perfectly good files.
    private static let ftyp = Array("ftyp".utf8)
    private static let ebml: [UInt8] = [0x1A, 0x45, 0xDF, 0xA3]
    private static let vtt = Array("WEBVTT".utf8)

    static func detect(_ bytes: [UInt8]) -> MediaFormat {
        if bytes.count >= 8, Array(bytes[4..<8]) == ftyp { return .mp4 }
        if bytes.count >= 4, Array(bytes[0..<4]) == ebml { return .webm }
        if bytes.count >= 6, Array(bytes[0..<6]) == vtt { return .webvtt }
        // A UTF-8 BOM ahead of WEBVTT is legal and appears in real files.
        if bytes.count >= 9, Array(bytes[0..<3]) == [0xEF, 0xBB, 0xBF],
           Array(bytes[3..<9]) == vtt { return .webvtt }
        return .unknown
    }

    /// How many bytes the check needs. Deliberately tiny: this is read from the
    /// `.part` file's head, and reading more would mean holding a gigabyte to
    /// answer a question about nine bytes.
    static let probeLength = 16

    /// Whether a detected format satisfies an expectation.
    ///
    /// `.mp4` and `.webm` are interchangeable for our purposes — Zoom serves
    /// MP4, Meet serves MP4, and a platform switching container on us is a
    /// change we want to survive rather than reject. What must never pass is
    /// `.unknown`, which is where every error page lands.
    func satisfies(_ expected: MediaFormat) -> Bool {
        if self == expected { return true }
        let video: Set<MediaFormat> = [.mp4, .webm]
        return video.contains(self) && video.contains(expected)
    }
}

// MARK: - The verdict

/// Why a download is or is not usable. One type, so no call site can invent a
/// fourth answer or forget the third.
enum DownloadVerdict: Equatable {
    case usable

    /// The response was an error wearing a success status. Carries the type so
    /// the message can say *what* arrived instead.
    case notMedia(contentType: String)

    case badStatus(Int)

    /// Fewer bytes than promised. The truncation case.
    case shortRead(expected: Int64, received: Int64)

    /// More bytes than promised — rarer, and a stronger signal that the
    /// response is not the file at all rather than a partial one.
    case sizeMismatch(expected: Int64, received: Int64)

    case hashMismatch(algorithm: FileHash.Algorithm)

    /// The bytes are not the format they claim. This is the check that catches
    /// an HTML page whose length happens to look plausible.
    case wrongFormat(detected: MediaFormat)

    var isUsable: Bool { self == .usable }

    /// A sentence for the row, in the researcher's terms. Never a status code:
    /// the Status column is read by someone deciding what to do next, and
    /// "HTTP 403" is not a decision.
    var rowMessage: String? {
        switch self {
        case .usable:
            return nil
        case .notMedia:
            // Platform-neutral by necessity: this type is shared by all three
            // adapters, and it previously named Zoom in every verdict — so a
            // Graph failure sent the reader to look at the wrong vendor.
            return "The server sent a web page, not a recording"
        case .badStatus:
            return "The download was refused"
        case .shortRead:
            return "Only part of the file arrived"
        case .sizeMismatch:
            return "The file didn't match its listing"
        case .hashMismatch:
            return "The file arrived damaged"
        case .wrongFormat:
            return "That file isn't a recording"
        }
    }

    /// Whether re-trying could plausibly help. A truncation is worth another
    /// go; an error page means something upstream said no and will say no
    /// again.
    var isRetryable: Bool {
        switch self {
        case .shortRead, .badStatus: return true
        case .usable, .notMedia, .sizeMismatch, .hashMismatch, .wrongFormat: return false
        }
    }
}

// MARK: - The checks

/// Every verification rule the three adapters share, in the order they run.
///
/// Order is not cosmetic. The response check happens **before the destination
/// file is opened**, so a refusal never creates a file at all; the byte and
/// format checks happen on the `.part` file, so nothing half-written is ever
/// visible under the real name.
enum CloudDownloadVerification {

    /// Step 1, before a single byte is written.
    ///
    /// - Parameter contentType: from the response head.
    static func inspectResponse(
        status: Int,
        contentType: String?
    ) -> DownloadVerdict {
        guard (200...299).contains(status) else { return .badStatus(status) }
        let type = (contentType ?? "").lowercased()
        // The three shapes an error takes while wearing a 200. Note `text/html`
        // is the common one and `application/json` the 59-byte one.
        for marker in ["text/html", "application/json", "text/plain"] where type.contains(marker) {
            // text/plain is a real content type for VTT on some servers, so it
            // only condemns a response that was supposed to be media.
            if marker == "text/plain" && type.contains("vtt") { continue }
            return .notMedia(contentType: type)
        }
        return .usable
    }

    /// Step 2, once the bytes are down but still in `.part`.
    ///
    /// Checks in increasing order of cost: size (free), format (16 bytes),
    /// hash (a full re-read). A file that fails the cheap check never pays for
    /// the expensive one.
    static func verifyPayload(
        received: Int64,
        head: [UInt8],
        expected: ExpectedFile,
        computedHash: String? = nil
    ) -> DownloadVerdict {
        if let promised = expected.sizeBytes, promised > 0 {
            if received < promised {
                return .shortRead(expected: promised, received: received)
            }
            if received > promised {
                return .sizeMismatch(expected: promised, received: received)
            }
        }

        if let format = expected.expectedFormat {
            let detected = MediaFormat.detect(head)
            guard detected.satisfies(format) else {
                return .wrongFormat(detected: detected)
            }
        }

        if let hash = expected.hash, let computedHash {
            guard hash.matches(computedHash) else {
                return .hashMismatch(algorithm: hash.algorithm)
            }
        }

        return .usable
    }

    /// Whether there is room before a byte moves.
    ///
    /// §9 requires this because both Graph and Zoom carry file size in the
    /// listing, so it costs nothing — and a network fetch that hits `ENOSPC`
    /// mid-batch has already burned real transfer time on an expiry-limited
    /// remote read.
    ///
    /// The headroom is not superstition: a `.part` file and its final name
    /// coexist for the instant of the rename, and a disk with exactly enough
    /// room fails at the last file rather than the first.
    static func hasRoom(
        forBytes needed: Int64,
        available: Int64?,
        headroomFraction: Double = 0.05
    ) -> Bool {
        guard let available else { return true }   // unknown: don't block
        let headroom = Int64(Double(needed) * headroomFraction)
        return available > needed + headroom
    }
}

// MARK: - Naming what lands on disk

/// Synthesises the filename a recording gets locally.
///
/// **Never take the platform's filename**, for two independent reasons.
///
/// *Safety*: §9 — a third party controls meeting titles, so a remote name is
/// untrusted input becoming a path component. *Quality*: the three platforms
/// disagree about what a filename is for. Teams leads with the title
/// (`<Title>-<YYYYMMDD_HHMMSS>UTC-Meeting Recording.mp4`) so it sorts
/// alphabetically by topic; Zoom stopped including the title in Mar 2021
/// (`GMT20210427-141742_Recording_640x360.mp4`) so it sorts chronologically and
/// carries no meaning; Google documents no convention at all. And Zoom's own
/// staff advice is to synthesise from the JSON rather than trust the
/// `Content-Disposition` header, which is often bare.
///
/// So we take Zoom's sortability *and* Teams' identifiability, which neither
/// platform gives on its own.
enum CloudDownloadNaming {

    /// `2026-08-12 1400 — P07 Interview.mp4`
    ///
    /// Date first so a Finder listing is chronological, title second so the
    /// researcher can see which session it is. The separator is an em dash with
    /// spaces, which sorts after digits and reads as a break rather than as
    /// part of either field.
    /// - Parameter part: which recording of its call this is, when the call
    ///   produced more than one. Rendered as ` (2)`, Finder's own idiom.
    ///
    ///   **Not cosmetic.** Two halves of one interview carry the same title,
    ///   and — on the path where the platform omits the recording's own start
    ///   time — the same `startsAt`, so without this they produce byte-identical
    ///   names. `publish` deliberately overwrites its destination (a re-fetched
    ///   damaged file must replace the bad one), so one half silently
    ///   annihilated the other while both rows reported "Imported" and the
    ///   terminus said two. Nil for the ordinary single-recording call, which
    ///   keeps every existing name unchanged.
    static func filename(
        title: String,
        startsAt: Date,
        fileExtension: String,
        part: Int? = nil,
        calendar: Calendar = .current
    ) -> String {
        let stamp = Self.stampFormatter.string(from: startsAt)
        let safe = safeComponent(title)
        var stem = safe.isEmpty ? stamp : "\(stamp) — \(safe)"
        if let part { stem += " (\(part))" }
        return "\(stem).\(fileExtension)"
    }

    /// The `.part` sibling. Same directory, so the atomic rename never crosses
    /// a filesystem boundary — a cross-device rename is a copy, and a copy is
    /// not atomic, which would reintroduce the half-written file this whole
    /// mechanism exists to prevent.
    static func partFilename(for final: String) -> String { final + ".part" }

    /// Strips what must not reach a path, and what would merely be unpleasant.
    ///
    /// Path separators and the leading dot are safety; control characters,
    /// collapsed whitespace and the length cap are so a Finder window remains
    /// readable. The cap is generous but real — HFS/APFS allow 255 bytes, and a
    /// meeting titled by pasting an agenda will exceed it.
    static func safeComponent(_ raw: String, maxLength: Int = 80) -> String {
        var out = raw
            .components(separatedBy: .controlCharacters).joined()
            .replacingOccurrences(of: "/", with: "-")
            .replacingOccurrences(of: ":", with: "-")
            .replacingOccurrences(of: "\\", with: "-")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        // Collapse runs of whitespace so a pasted title doesn't become a wall.
        while out.contains("  ") { out = out.replacingOccurrences(of: "  ", with: " ") }
        // Collapse dot runs. Traversal is already impossible — the separators
        // are gone above, so `..` here is just two characters in a filename —
        // but leaving it means the safety property has to be argued rather than
        // read. A name that cannot contain `..` at all needs no argument, and
        // it also spares any downstream tool that parses paths less carefully
        // than we do.
        while out.contains("..") { out = out.replacingOccurrences(of: "..", with: ".") }
        // A leading dot hides the file from Finder — a silent disappearance
        // that reads as a failed import.
        while out.hasPrefix(".") { out.removeFirst() }
        // And a trailing one is invisible to the user but not to the
        // filesystem, so it would silently change the extension boundary.
        while out.hasSuffix(".") { out.removeLast() }
        out = out.trimmingCharacters(in: .whitespaces)
        if out.count > maxLength { out = String(out.prefix(maxLength)).trimmingCharacters(in: .whitespaces) }
        return out
    }

    private static let stampFormatter: DateFormatter = {
        let f = DateFormatter()
        // Local time, because the filename is read by a human who thinks in
        // their own zone — unlike the *window* arithmetic, which is pinned to
        // UTC precisely so it doesn't drift.
        f.dateFormat = "yyyy-MM-dd HHmm"
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()
}
