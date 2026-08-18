import Foundation
import Testing

@testable import Bristlenose

// The already-in-this-project check, at the level where getting it wrong is
// invisible.
//
// Two opposite harms, and they are not symmetric. Missing a match costs a
// duplicate — which is the failure the whole check exists to prevent, because
// two copies of one interview become two participants whose identical quotes
// cluster *together* and read as corroboration. Inventing one is worse and
// quieter: `.imported` offers no tick and no override, so a wrongly-marked row
// is a recording silently withheld from a researcher who does not have it.
//
// So the tests below are mostly about the second: one file must never satisfy
// two rows, and a row we cannot measure must stay fetchable.

@Suite("Already in this project, by duration")
struct CloudImportLocalMatchTests {

    private func row(
        _ id: String,
        duration: TimeInterval?,
        local: ImportRowState = .notImported,
        video: ArtifactAvailability = .available,
        recorded: Bool = true
    ) -> CloudImportRow {
        CloudImportRow(
            id: id, title: id, startsAt: Date(), duration: duration, sizeBytes: nil,
            expiresAt: nil, attendees: [], localState: local,
            video: video, roster: .available, transcript: .available, organiser: nil,
            recordedAt: recorded ? Date() : nil
        )
    }

    private func file(_ name: String, _ duration: TimeInterval) -> LocalRecording {
        LocalRecording(name: name, duration: duration)
    }

    /// Meet unless stated: the platform this was designed against, and the one
    /// whose duration is the loosest of the three.
    private func held(
        _ rows: [CloudImportRow],
        _ local: [LocalRecording],
        platform: CloudPlatform = .meet
    ) -> Set<String> {
        CloudImportLocalMatch.alreadyPresent(rows: rows, local: local, platform: platform)
    }

    // MARK: - The case it exists for

    @Test("A hand-downloaded recording of the same length is recognised")
    func matchesWithinTolerance() {
        // The 99.9% route: downloaded by hand, renamed to something the
        // researcher can read, dropped in the folder. Nothing about the file
        // says where it came from — not the name, and on Meet not even a
        // creation time — so its length is the entire key.
        let rows = [row("a", duration: 3000)]
        #expect(held(rows, [file("P07 — session 3.mp4", 2997)]) == ["a"])
    }

    @Test("A recognised row is no longer fetchable")
    func recognisedRowStopsBeingSelectable() {
        // The point of the mark, not a restatement of it: `.imported` is what
        // takes the tick away, and the tick is what would otherwise pull a
        // second copy of a file already on disk.
        let marked = row("a", duration: 3000).markedAsAlreadyInProject()
        #expect(!marked.isSelectable)
        #expect(marked.drawsTicked(in: []))
    }

    @Test("A different recording of a different length is left alone")
    func doesNotMatchOutsideTolerance() {
        let rows = [row("a", duration: 3000)]
        #expect(held(rows, [file("other.mp4", 2900)]).isEmpty)
    }

    // MARK: - The expensive mistake

    @Test("One file cannot mark two rows as held")
    func oneFileSatisfiesAtMostOneRow() {
        // Two genuinely different interviews that happen to run the same
        // length — an hour booked, an hour used, twice. The researcher has
        // downloaded exactly one of them.
        //
        // Marking both would leave the *second* recording unfetchable, with no
        // tick to override it and nothing on screen explaining why. Only the
        // closer row may claim the file; the loser stays fetchable, which at
        // worst costs the duplicate this check was already going to catch on
        // the next visit.
        let rows = [row("a", duration: 3000), row("b", duration: 3004)]
        let outcome = held(rows, [file("one.mp4", 3003)])
        #expect(outcome == ["b"])
    }

    @Test("Two copies of one length still mark two rows")
    func twoFilesSatisfyTwoRows() {
        // The mirror of the above, and the reason the rule is one-to-one
        // rather than one-file-total: both were fetched last week, both are
        // here, and neither should be offered again.
        let rows = [row("a", duration: 3000), row("b", duration: 3004)]
        #expect(held(rows, [file("one.mp4", 3003), file("two.mp4", 2999)]) == ["a", "b"])
    }

    @Test("The same folder and listing decide the same way twice")
    func tieBreakIsStable() {
        // Meet's two siblings of one call carry an identical duration when
        // Google omits the recording's own start time. An arbitrary winner
        // there would move between renders of the same list — a row that is
        // fetchable, then isn't, then is.
        let rows = [row("b", duration: 3000), row("a", duration: 3000)]
        let files = [file("x.mp4", 3000), file("y.mp4", 5000)]
        #expect(held(rows, files) == held(rows.reversed(), files.reversed()))
    }

    // MARK: - Rows that must never be claimed

    @Test("A row with no duration is never matched")
    func nilDurationNeverMatches() {
        // Someone else's meeting: we know the event, not the file. Every such
        // row carries a nil duration, and a nil read as zero would match any
        // zero-length file that ever landed in the folder.
        let rows = [row("a", duration: nil, video: .notOrganiser(organiser: "A. Bianchi"))]
        #expect(held(rows, [file("anything.mp4", 3000)]).isEmpty)
        #expect(held(rows, [file("empty.mp4", 0)]).isEmpty)
    }

    @Test("A row with nothing recorded is never matched")
    func rowsWithoutRecordingsNeverMatch() {
        // A meeting nobody recorded has no file behind it, so nothing in the
        // folder can be it — however well a length happens to line up.
        let rows = [row("a", duration: 1800, video: .notRecorded, recorded: false)]
        #expect(held(rows, [file("standup.mp4", 1800)]).isEmpty)
    }

    @Test("A row that already reports another local state is left as it is")
    func onlyNotImportedIsUpgraded() {
        // `.damaged` means present-but-wrong-size and genuinely should
        // re-fetch; `.notDownloaded` is a placeholder in the destination
        // cloud. Both already describe a *local* file more precisely than a
        // duration match could, and overwriting either would replace an
        // actionable state with a silent one.
        let damaged = [row("a", duration: 3000, local: .damaged)]
        #expect(held(damaged, [file("same.mp4", 3000)]).isEmpty)

        let placeholder = [row("a", duration: 3000, local: .notDownloaded(provider: "iCloud Drive"))]
        #expect(held(placeholder, [file("same.mp4", 3000)]).isEmpty)
    }

    @Test("An unmeasurable file claims nothing")
    func zeroLengthFilesClaimNothing() {
        // `scan` declines to report a file it could not measure — a cloud
        // placeholder, a truncated download — rather than reporting it as
        // zero. This pins the matcher's half of that contract: a zero that
        // reaches it anyway must not become a wildcard.
        let rows = [row("a", duration: 0), row("b", duration: 3000)]
        #expect(held(rows, [file("placeholder.mp4", 0)]).isEmpty)
    }

    // MARK: - Tolerance is a property of the platform, not a constant

    @Test("Each platform's tolerance matches where its duration came from")
    func toleranceFollowsProvenance() {
        // Teams serves the container's own duration in milliseconds — the same
        // measurement, so a match is near-exact and a 10s gap is a different
        // recording.
        let hour = [row("a", duration: 3000)]
        #expect(held(hour, [file("t.mp4", 3001)], platform: .teams) == ["a"])
        #expect(held(hour, [file("t.mp4", 3010)], platform: .teams).isEmpty)

        // Meet's is wall-clock between recording events, which brackets the
        // encode rather than measuring it. The same 10s gap is the same file.
        #expect(held(hour, [file("m.mp4", 3010)], platform: .meet) == ["a"])

        // Zoom reports whole minutes, so its quantisation error alone is up to
        // 30s before any real drift — nothing under a minute could ever match,
        // and scaling cannot help a number that arrives pre-rounded. Flat, and
        // never below its own granularity. Stated rather than fixed; see
        // `durationTolerance(forListed:)`.
        #expect(CloudPlatform.zoom.durationTolerance(forListed: 20) > 60)
        #expect(CloudPlatform.zoom.durationTolerance(forListed: 20)
                == CloudPlatform.zoom.durationTolerance(forListed: 3000))
    }

    @Test("A short recording gets a short window, which is where the flat one did harm")
    func toleranceScalesWithTheRecording() {
        // Measured on a real Meet account, 17 Aug 2026. The folder held two
        // copies of a 20.75s recording and no copy of the 30.25s one — and at
        // a flat 15s the 30.25s row was marked "already in this project",
        // which takes its tick away and offers no override. 9.5s apart is not
        // the same recording; on a 20-second file 15s is 75%.
        let short = [row("a", duration: 30.25)]
        #expect(held(short, [file("wrong.mp4", 20.75)]).isEmpty)

        // …while the correct match still lands.
        #expect(held(short, [file("right.mp4", 30.4)]) == ["a"])

        // And the long case, which the flat value got right, still is: a
        // 35-minute recording keeps a window measured in seconds, not
        // percentage points.
        let long = [row("b", duration: 2152.8)]
        #expect(held(long, [file("long.mp4", 2160)]) == ["b"])
        #expect(held(long, [file("other.mp4", 2100)]).isEmpty)
    }

    @Test("The four short recordings that collided no longer do")
    func realWorldShortRecordingsNoLongerCollide() {
        // The exact folder from that session: four Meet recordings, every one
        // of them inside 15s of every other. The one-to-one rule kept the
        // aggregate answer right only because all four happened to be present
        // — with any of them missing, the pairing was arbitrary and a row the
        // researcher did NOT have could be marked as held.
        let rows = [row("a", duration: 14), row("b", duration: 20.75),
                    row("c", duration: 28.25), row("d", duration: 30.25)]
        // Only two of the four are actually on disk.
        let onDisk = [file("one.mp4", 14), file("two.mp4", 28.25)]
        #expect(held(rows, onDisk) == ["a", "c"],
                "each file must claim its own row, not the nearest unclaimed one")
    }
}

// MARK: - The store applies it once, for everyone

@MainActor
@Suite("The destination scan reaches the fetch, not just the drawing")
struct CloudImportDestinationScanTests {

    /// The failure this pins is a split, not a miscalculation: the outline used
    /// to be built from a marked copy of the rows while `fetchOrder` read the
    /// listing directly. Nothing looks wrong until the two disagree — and then
    /// the window draws a row as already held while the batch fetches it
    /// anyway, producing exactly the duplicate the mark exists to prevent.
    ///
    /// So this asserts through the *store*, and on the fetch side: a ticked row
    /// that the destination turns out to hold must drop out of `fetchOrder`.
    @Test("A row the destination already holds drops out of the batch")
    func markedRowsLeaveTheFetchOrder() async throws {
        let store = CloudImportStore(source: FixtureCloudSource(scenario: .populated))
        await store.load()

        store.selectAllVisible()
        let before = store.fetchOrder
        let victim = try #require(before.first { ($0.duration ?? 0) > 0 })

        // One file, exactly one recording's length. Everything downstream —
        // the mark, the lost tick, the shorter batch — follows from this.
        store.applyDestinationScan(
            [LocalRecording(name: "held.mp4", duration: victim.duration ?? 0)])

        let after = store.fetchOrder
        #expect(after.count == before.count - 1,
                "one file may claim one row, so exactly one tick leaves the batch")

        // And the row that left is the one drawn as held. If these two ever
        // disagree, the window is telling the researcher one thing while the
        // batch does another — which is the split this suite exists for.
        let dropped = try #require(before.first { row in !after.contains { $0.id == row.id } })
        #expect(store.rows.first { $0.id == dropped.id }?.localState == .imported)
    }

    @Test("The window's ticks and the batch never disagree about what is held")
    func drawnStateAndFetchOrderAgree() async {
        let store = CloudImportStore(source: FixtureCloudSource(scenario: .populated))
        await store.load()
        store.selectAllVisible()

        // The returning researcher's folder: a file for every recording in the
        // listing that has a measurable length.
        let before = store.fetchOrder.count
        let lengths = store.rows.compactMap(\.duration).filter { $0 > 0 }
        store.applyDestinationScan(
            lengths.enumerated().map { LocalRecording(name: "f\($0.offset).mp4", duration: $0.element) })

        // The setup has to bite, or the loop below proves nothing.
        #expect(store.rows.contains { $0.localState == .imported })
        #expect(store.fetchOrder.count < before)

        // Everything the batch would fetch, looked up in what the window
        // *drew*. Asserting on the batch row's own `localState` would be
        // asserting the mechanism: under the split those rows come straight
        // off the listing, so they report `.notImported` whatever is on
        // screen, and the check could never fail. Comparing the two lists
        // against each other is the only form of this that catches a window
        // and a batch disagreeing.
        for row in store.fetchOrder {
            let drawn = store.rows.first { $0.id == row.id }
            #expect(drawn?.localState != .imported,
                    "\(row.id) is drawn as already held, yet the batch would fetch it")
            #expect(drawn?.isSelectable == true)
        }
    }

    @Test("A folder of transcripts and notes measures nothing")
    func scanIgnoresEverythingWithoutADuration() async throws {
        // The scan opens files to measure them, so what it declines to open
        // matters: a `.vtt` beside the recordings is a transcript, and
        // `bristlenose-output` holds clips cut *from* the sources rather than
        // the sources themselves.
        let folder = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-scan-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: folder) }

        for name in ["notes.txt", "p1.vtt", "p1.srt", "brief.docx", "._p1.mp4"] {
            try Data("x".utf8).write(to: folder.appendingPathComponent(name))
        }
        try FileManager.default.createDirectory(
            at: folder.appendingPathComponent("bristlenose-output"),
            withIntermediateDirectories: true)

        #expect(await CloudImportLocalMatch.scan(folder: folder).isEmpty)
    }

    @Test("A folder we cannot read leaves every row fetchable")
    func unreadableFolderYieldsNoMatches() async {
        // The sandbox case, and the one that must fail in the safe direction:
        // a folder with no grant behind it enumerates as empty, which is
        // indistinguishable from a folder with nothing in it. Both answer "we
        // hold none of these", so nothing is withheld.
        let missing = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("bn-absent-\(UUID().uuidString)", isDirectory: true)
        #expect(await CloudImportLocalMatch.scan(folder: missing).isEmpty)
    }
}


// MARK: - Reconstructing what we fetched, from the bytes alone

// The per-project record, and the argument for not having one.
//
// The plan called for a persisted artefact — what we fetched, what never
// arrived, what was in flight when the app quit — with a schema, a migration
// story and a privacy question, since it would name meetings and platforms.
// It is not needed. `CloudDownloader` verifies every transfer while the bytes
// are still in the system temp directory and publishes with an atomic rename,
// so the destination folder cannot hold a plausible-looking file that never
// really arrived. The folder *is* the record; a ledger could only be a second,
// staler copy, and the one that disagrees the moment a researcher moves a file.
//
// What the folder cannot answer by itself is which broken file belongs to
// which row, and that is what these pin.
@Suite("What the destination folder can be asked")
struct CloudImportGoodnessTests {

    private func row(_ id: String, title: String, at: Date,
                     ordinal: Int? = nil) -> CloudImportRow {
        CloudImportRow(
            id: id, title: title, startsAt: at, duration: 600, sizeBytes: nil,
            expiresAt: nil, attendees: [], localState: .notImported,
            video: .available, roster: .available, transcript: .available,
            organiser: nil, recordedAt: at, siblingOrdinal: ordinal)
    }

    /// The name the downloader would have written for this row.
    private func writtenName(_ row: CloudImportRow, ext: String = "mp4") -> String {
        CloudDownloadNaming.filename(
            title: row.title, startsAt: row.startsAt,
            fileExtension: ext, part: row.siblingOrdinal)
    }

    @Test("A file we wrote that will not open marks its row damaged")
    func unreadableOwnFileIsDamaged() {
        let subject = row("a", title: "P07 Interview", at: Date(timeIntervalSince1970: 1_760_000_000))
        let scan = LocalScan(unreadable: [writtenName(subject)])
        #expect(CloudImportLocalMatch.damaged(rows: [subject], scan: scan) == ["a"])
    }

    @Test("Zoom's audio-only rendition matches the same row as an mp4 would")
    func extensionDoesNotDecideTheMatch() {
        // The extension is chosen at fetch time from whatever Zoom offers, so
        // it is not knowable from the row. Matching on the stem is what keeps
        // the `.m4a` case working without the row having to predict it.
        let subject = row("a", title: "P07 Interview", at: Date(timeIntervalSince1970: 1_760_000_000))
        let scan = LocalScan(unreadable: [writtenName(subject, ext: "m4a")])
        #expect(CloudImportLocalMatch.damaged(rows: [subject], scan: scan) == ["a"])
    }

    @Test("A broken file that is not ours is left alone")
    func unrelatedBrokenFileIsNotClaimed() {
        // A researcher's own corrupt download of the same meeting, under their
        // own name. We have no basis to speak about it, and a row wrongly
        // marked damaged sends them to re-fetch a recording they already have
        // a good copy of somewhere else.
        let subject = row("a", title: "P07 Interview", at: Date(timeIntervalSince1970: 1_760_000_000))
        let scan = LocalScan(unreadable: ["interview-final-FINAL.mp4"])
        #expect(CloudImportLocalMatch.damaged(rows: [subject], scan: scan).isEmpty)
    }

    @Test("Nothing broken, nothing claimed")
    func cleanFolderClaimsNothing() {
        let subject = row("a", title: "P07 Interview", at: Date(timeIntervalSince1970: 1_760_000_000))
        #expect(CloudImportLocalMatch.damaged(rows: [subject], scan: LocalScan()).isEmpty)
    }

    @Test("Two recordings of one call are told apart by their sibling ordinal")
    func siblingsDoNotCollide() {
        // Two halves of one interview carry the same title and the same start,
        // so the ordinal is the only thing separating their filenames. Without
        // it a single damaged half would condemn both rows.
        let base = Date(timeIntervalSince1970: 1_760_000_000)
        let first = row("a", title: "P07 Interview", at: base)
        let second = row("b", title: "P07 Interview", at: base, ordinal: 2)
        let scan = LocalScan(unreadable: [writtenName(second)])
        let damaged = CloudImportLocalMatch.damaged(rows: [first, second], scan: scan)
        #expect(damaged == ["b"], "only the half that is actually broken")
    }

    @Test("An evicted recording is held, not missing")
    func evictedFileIsNotRefetched() {
        // The expensive confusion this exists to prevent: a project folder under
        // ~/Library/CloudStorage whose provider has dehydrated a recording to
        // reclaim space. With no evidence the row reads as never-imported and
        // the researcher re-downloads gigabytes they already own — spending an
        // expiry-limited remote read on a problem Dropbox can solve for free.
        let subject = row("a", title: "P07 Interview", at: Date(timeIntervalSince1970: 1_760_000_000))
        let scan = LocalScan(evicted: [writtenName(subject)], syncProvider: "Dropbox")
        #expect(CloudImportLocalMatch.evicted(rows: [subject], scan: scan) == ["a"])
    }

    @Test("An evicted file is never also reported as damaged")
    func evictedIsNotDamaged() {
        // The two are mutually exclusive and the ordering enforces it, but the
        // *reason* is worth a test: a placeholder cannot be opened by design,
        // so judging it would report every evicted recording as broken — the
        // most alarming possible reading of a perfectly healthy file.
        let subject = row("a", title: "P07 Interview", at: Date(timeIntervalSince1970: 1_760_000_000))
        let scan = LocalScan(evicted: [writtenName(subject)], syncProvider: "iCloud Drive")
        #expect(CloudImportLocalMatch.damaged(rows: [subject], scan: scan).isEmpty,
                "unreadable and evicted are different findings")
    }

    @Test("A damaged file is not mistaken for an evicted one")
    func damagedIsNotEvicted() {
        let subject = row("a", title: "P07 Interview", at: Date(timeIntervalSince1970: 1_760_000_000))
        let scan = LocalScan(unreadable: [writtenName(subject)])
        #expect(CloudImportLocalMatch.evicted(rows: [subject], scan: scan).isEmpty)
    }

    @Test("Only formats AVFoundation can judge are eligible for a damage verdict")
    func unsupportedContainersAreNotJudged() {
        // The false positive that would matter most. `mediaExtensions` accepts
        // mkv, webm and avi so their durations can be matched — but
        // AVFoundation cannot open any of them, so a perfectly healthy `.mkv`
        // probes as unreadable. Calling that damaged would accuse a
        // researcher's own material of being broken because Apple never
        // shipped a demuxer for it.
        for container in ["mkv", "webm", "avi"] {
            #expect(!CloudImportLocalMatch.judgeableExtensions.contains(container),
                    "\(container) cannot be judged by a failed AVFoundation open")
        }
        // And the formats we actually write must be judgeable, or the check is
        // decorative.
        #expect(CloudImportLocalMatch.judgeableExtensions.isSuperset(of: ["mp4", "m4a"]))
    }

    @Test("Every judgeable format is one the duration match already scans")
    func judgeableIsASubsetOfScanned() {
        // A format we would judge but never look at cannot produce a verdict,
        // and the mismatch would be invisible — the check would simply never
        // fire for it.
        #expect(CloudImportLocalMatch.mediaExtensions
                    .isSuperset(of: CloudImportLocalMatch.judgeableExtensions))
    }
}
