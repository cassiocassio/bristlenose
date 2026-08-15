import Foundation
import Testing

@testable import Bristlenose

// The shared download path's verification rules.
//
// Every test here pins a case where the file that lands on disk is *plausible*
// — right-ish length, right extension, opens in QuickTime — and wrong. That is
// the whole reason the checks exist: the loud failures were never the problem.

// MARK: - Response inspection

@Suite("Download response inspection")
struct DownloadResponseTests {

    @Test("An HTML page with a 200 is refused")
    func htmlWithTwoHundred() {
        // The documented Zoom shape, and the one that produced 880 error
        // bodies saved as .mp4 in a single real run.
        let verdict = CloudDownloadVerification.inspectResponse(
            status: 200, contentType: "text/html; charset=utf-8")
        #expect(verdict == .notMedia(contentType: "text/html; charset=utf-8"))
        #expect(!verdict.isUsable)
    }

    @Test("A JSON error body with a 200 is refused")
    func jsonWithTwoHundred() {
        // 59 bytes of {"status":false,"errorCode":124,…} — indistinguishable
        // from a real file to anything that only checks the status line.
        #expect(!CloudDownloadVerification.inspectResponse(
            status: 200, contentType: "application/json").isUsable)
    }

    @Test("A VTT served as text/plain is allowed through")
    func vttIsNotAnError() {
        // The counterweight. Some servers send WebVTT as text/plain, and a
        // blanket text/plain refusal would reject every real transcript — the
        // same lie in the other direction.
        #expect(CloudDownloadVerification.inspectResponse(
            status: 200, contentType: "text/plain; charset=utf-8; format=vtt").isUsable)
    }

    @Test("Real media passes")
    func mediaPasses() {
        #expect(CloudDownloadVerification.inspectResponse(
            status: 200, contentType: "video/mp4").isUsable)
        #expect(CloudDownloadVerification.inspectResponse(
            status: 206, contentType: "audio/mp4").isUsable)
    }

    @Test("A 4xx is refused whatever it claims to contain")
    func badStatus() {
        #expect(CloudDownloadVerification.inspectResponse(
            status: 403, contentType: "video/mp4") == .badStatus(403))
    }
}

// MARK: - Magic numbers

@Suite("Media format detection")
struct MediaFormatTests {

    /// `ftyp` at offset 4, not offset 0 — the leading four bytes are a size.
    private var mp4Head: [UInt8] {
        [0x00, 0x00, 0x00, 0x20] + Array("ftypisom".utf8)
    }

    @Test("An ISO base-media file is detected by its brand box, not byte zero")
    func mp4Detected() {
        // A naive prefix compare against "ftyp" fails on every real MP4,
        // because the file starts with a box length.
        #expect(MediaFormat.detect(mp4Head) == .mp4)
    }

    @Test("WebM and WebVTT are detected")
    func othersDetected() {
        #expect(MediaFormat.detect([0x1A, 0x45, 0xDF, 0xA3, 0x00]) == .webm)
        #expect(MediaFormat.detect(Array("WEBVTT\n\n".utf8)) == .webvtt)
    }

    @Test("A UTF-8 BOM before WEBVTT still reads as WebVTT")
    func bomTolerated() {
        // Legal, and it appears in real files. Rejecting it would fail a
        // perfectly good transcript.
        let bom: [UInt8] = [0xEF, 0xBB, 0xBF]
        #expect(MediaFormat.detect(bom + Array("WEBVTT".utf8)) == .webvtt)
    }

    @Test("An HTML page is unknown — which is what condemns it")
    func htmlIsUnknown() {
        #expect(MediaFormat.detect(Array("<!DOCTYPE html>".utf8)) == .unknown)
        #expect(!MediaFormat.unknown.satisfies(.mp4))
    }

    @Test("A short read cannot masquerade as a format")
    func tooShort() {
        #expect(MediaFormat.detect([0x00, 0x00]) == .unknown)
        #expect(MediaFormat.detect([]) == .unknown)
    }

    @Test("MP4 and WebM satisfy each other")
    func containersInterchange() {
        // A platform switching container is a change to survive, not to
        // reject; only .unknown must ever fail.
        #expect(MediaFormat.webm.satisfies(.mp4))
        #expect(MediaFormat.mp4.satisfies(.webm))
    }
}

// MARK: - Payload verification

@Suite("Download payload verification")
struct DownloadPayloadTests {

    private var mp4Head: [UInt8] { [0x00, 0x00, 0x00, 0x20] + Array("ftypisom".utf8) }

    @Test("A truncated file is caught — the quiet failure")
    func truncation() {
        // The one that matters most. ffprobe accepts a truncated MP4, Whisper
        // transcribes forty minutes of sixty, and the report presents a
        // confident analysis of a session it half read.
        let verdict = CloudDownloadVerification.verifyPayload(
            received: 400_000_000,
            head: mp4Head,
            expected: ExpectedFile(sizeBytes: 800_000_000, expectedFormat: .mp4)
        )
        #expect(verdict == .shortRead(expected: 800_000_000, received: 400_000_000))
        // Worth another go — unlike an error page, which will say no again.
        #expect(verdict.isRetryable)
    }

    @Test("More bytes than promised is a mismatch, not a bonus")
    func overLongIsSuspicious() {
        let verdict = CloudDownloadVerification.verifyPayload(
            received: 900_000, head: mp4Head,
            expected: ExpectedFile(sizeBytes: 800_000, expectedFormat: .mp4))
        #expect(verdict == .sizeMismatch(expected: 800_000, received: 900_000))
        #expect(!verdict.isRetryable)
    }

    @Test("Right length, wrong content is still caught")
    func rightSizeWrongBytes() {
        // The case size alone cannot catch: a redirect served something else
        // entirely and it happens to be the same length. Magic bytes are the
        // only thing standing between this and a .mp4 full of HTML.
        let html = Array("<!DOCTYPE html><html>".utf8)
        let verdict = CloudDownloadVerification.verifyPayload(
            received: 1_000, head: html,
            expected: ExpectedFile(sizeBytes: 1_000, expectedFormat: .mp4))
        #expect(verdict == .wrongFormat(detected: .unknown))
    }

    @Test("An absent expected size reads as unknown, never as zero")
    func nilSizeSkipsTheCheck() {
        // Zoom's CC and TIMELINE files genuinely carry no file_size. Treating
        // nil as 0 would fail every one of them.
        #expect(CloudDownloadVerification.verifyPayload(
            received: 5_000, head: mp4Head,
            expected: ExpectedFile(sizeBytes: nil, expectedFormat: .mp4)) == .usable)
    }

    @Test("A supplied hash makes verification exact")
    func hashChecked() {
        let good = ExpectedFile(
            sizeBytes: 12, hash: FileHash(algorithm: .sha256, value: "ABC123"),
            expectedFormat: .mp4)
        // Case-insensitive: the three vendors render hex differently and a
        // correct download must not fail on presentation.
        #expect(CloudDownloadVerification.verifyPayload(
            received: 12, head: mp4Head, expected: good, computedHash: "abc123") == .usable)
        #expect(CloudDownloadVerification.verifyPayload(
            received: 12, head: mp4Head, expected: good,
            computedHash: "deadbeef") == .hashMismatch(algorithm: .sha256))
    }

    @Test("Everything right passes")
    func happyPath() {
        #expect(CloudDownloadVerification.verifyPayload(
            received: 800_000, head: mp4Head,
            expected: ExpectedFile(sizeBytes: 800_000, expectedFormat: .mp4)) == .usable)
    }
}

// MARK: - Free space

@Suite("Free-space precheck")
struct FreeSpaceTests {

    @Test("A batch bigger than the disk is refused before a byte moves")
    func refusesWhenFull() {
        // §9: both Graph and Zoom carry size in the listing, so this costs
        // nothing — and a mid-batch ENOSPC has already burned real transfer
        // time on an expiry-limited remote read.
        #expect(!CloudDownloadVerification.hasRoom(
            forBytes: 10_000_000_000, available: 8_000_000_000))
    }

    @Test("Exactly enough is not enough — headroom is required")
    func headroom() {
        // A .part file and its final name coexist for the instant of the
        // rename, so a disk with exactly enough room fails on the last file
        // rather than the first.
        #expect(!CloudDownloadVerification.hasRoom(forBytes: 1_000, available: 1_000))
        #expect(CloudDownloadVerification.hasRoom(forBytes: 1_000, available: 2_000))
    }

    @Test("Unknown free space does not block")
    func unknownDoesNotBlock() {
        // A volume that won't report capacity is not a reason to refuse an
        // import the researcher asked for.
        #expect(CloudDownloadVerification.hasRoom(forBytes: 1_000, available: nil))
    }
}

// MARK: - Naming

@Suite("Download naming")
struct DownloadNamingTests {

    private var when: Date {
        DateComponents(calendar: .current, year: 2026, month: 8, day: 12,
                       hour: 14, minute: 0).date!
    }

    @Test("Date leads so Finder sorts chronologically; title follows so it means something")
    func shape() {
        let name = CloudDownloadNaming.filename(
            title: "P07 Interview — ward handover", startsAt: when, fileExtension: "mp4")
        // Neither platform gives both: Teams leads with the title and sorts
        // alphabetically by topic; Zoom dropped the title in Mar 2021 and sorts
        // chronologically but carries no meaning.
        #expect(name.hasPrefix("2026-08-12 1400"))
        #expect(name.contains("P07 Interview"))
        #expect(name.hasSuffix(".mp4"))
    }

    @Test("Path separators in a remote title cannot escape the folder")
    func pathTraversal() {
        // §9: a third party controls meeting titles, so this is untrusted
        // input becoming a path component.
        let name = CloudDownloadNaming.filename(
            title: "../../etc/passwd", startsAt: when, fileExtension: "mp4")
        #expect(!name.contains("/"))
        #expect(!name.contains(".."))
    }

    @Test("A leading dot cannot hide the file from Finder")
    func leadingDot() {
        // A hidden file reads as a failed import — a silent disappearance.
        let name = CloudDownloadNaming.filename(
            title: ".hidden", startsAt: when, fileExtension: "mp4")
        #expect(name.contains("hidden"))
        #expect(!name.hasPrefix("."))
    }

    @Test("A pasted-agenda title is capped rather than rejected")
    func longTitle() {
        let name = CloudDownloadNaming.filename(
            title: String(repeating: "long ", count: 100), startsAt: when, fileExtension: "mp4")
        #expect(name.count < 130)
        #expect(name.hasSuffix(".mp4"))
    }

    @Test("An empty title still yields a usable name")
    func emptyTitle() {
        let name = CloudDownloadNaming.filename(
            title: "   ", startsAt: when, fileExtension: "mp4")
        #expect(name == "2026-08-12 1400.mp4")
    }

    @Test("The .part sibling keeps the same stem")
    func partNaming() {
        // Same directory, so the final rename never crosses a volume — a
        // cross-device rename is a copy, and a copy is not atomic.
        #expect(CloudDownloadNaming.partFilename(for: "a.mp4") == "a.mp4.part")
    }
}

// MARK: - Transfer policy

@Suite("Per-platform transfer policy")
struct TransferPolicyTests {

    @Test("Zoom drops the Authorization header across its CDN redirect")
    func zoomStrips() {
        // download_url redirects to a pre-signed URL on ssrweb.zoom.us that
        // carries its own credentials; arriving with both has been reported to
        // 403. URLSession re-attaches by default, so this must be explicit —
        // Python's requests strips it automatically, which is why so much
        // shipped Zoom code works by accident.
        #expect(!CloudTransferPolicy.zoom.keepAuthorizationAcrossRedirect)
        #expect(CloudTransferPolicy.zoom.authorization == .bearer)
    }

    @Test("Teams sends no header at all — the URL is the credential")
    func teamsPreAuthorized() {
        // Graph's downloadUrl carries tempauth= in the query string. That is
        // also why §9 forbids logging these URLs.
        #expect(CloudTransferPolicy.teams.authorization == .preAuthorizedURL)
    }

    @Test("Google keeps its bearer token")
    func meetKeepsHeader() {
        #expect(CloudTransferPolicy.meet.keepAuthorizationAcrossRedirect)
        #expect(CloudTransferPolicy.meet.authorization == .bearer)
    }

    @Test("Every platform has a policy")
    func allCovered() {
        for platform in CloudPlatform.allCases {
            _ = CloudTransferPolicy.for(platform)
        }
    }
}
