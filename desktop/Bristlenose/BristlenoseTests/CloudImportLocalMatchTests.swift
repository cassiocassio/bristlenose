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

    private func held(
        _ rows: [CloudImportRow],
        _ local: [LocalRecording],
        tolerance: TimeInterval = 15
    ) -> Set<String> {
        CloudImportLocalMatch.alreadyPresent(rows: rows, local: local, tolerance: tolerance)
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
        // measurement, so a match should be near-exact and a 10s gap is a
        // different recording.
        let teams = [row("a", duration: 3000)]
        #expect(held(teams, [file("t.mp4", 3001)], tolerance: CloudPlatform.teams.durationTolerance) == ["a"])
        #expect(held(teams, [file("t.mp4", 3010)], tolerance: CloudPlatform.teams.durationTolerance).isEmpty)

        // Meet's is wall-clock between recording events, which brackets the
        // encode rather than measuring it. The same 10s gap is the same file.
        #expect(held(teams, [file("m.mp4", 3010)], tolerance: CloudPlatform.meet.durationTolerance) == ["a"])

        // Zoom reports whole minutes, so nothing under a minute could ever
        // match. Stated rather than fixed — see `durationTolerance`.
        #expect(CloudPlatform.zoom.durationTolerance > 60)
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
