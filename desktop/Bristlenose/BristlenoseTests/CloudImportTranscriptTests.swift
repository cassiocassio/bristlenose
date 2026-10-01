import Foundation
import Testing

@testable import Bristlenose

// The transcript half of an import row: what it says, whether the row waits,
// and how the wait is got round. Design: docs/design-cloud-import-transcripts.md
// §0 item 2 (the wait) and §5e (the column and its states).
//
// NOT YET RUN ON A MAC — written in a cloud session with no Xcode (1 Oct 2026).
// The decisions are pinned here so the first Mac run tells us where the
// writing went wrong, rather than where the compiler did.

// MARK: - What the cell says

@Suite("Transcript availability")
struct TranscriptAvailabilityTests {

    /// One row of §5e's table. A kind of nil is the glyphless grey the
    /// vocabulary reserves for pending and plain states.
    struct Row: Sendable {
        let state: TranscriptAvailability
        let leaf: String
        let kind: MessageKind?
    }

    nonisolated static let table: [Row] = [
        Row(state: .available, leaf: "transcriptAvailable", kind: nil),
        Row(state: .expected, leaf: "transcriptExpected", kind: nil),
        Row(state: .notProvided, leaf: "transcriptNone", kind: .info),
        Row(state: .noSpeakerNames, leaf: "transcriptNoSpeakerNames", kind: .info),
        Row(state: .needsAdminApproval, leaf: "transcriptNeedsApproval", kind: nil),
        Row(state: .needsScope("meetings.space.readonly"), leaf: "statusNeedsAccess", kind: .warning),
        Row(state: .unavailable, leaf: "statusUnavailable", kind: .warning),
        Row(state: .notResolved, leaf: "statusNotResolved", kind: .warning),
        Row(state: .noLongerAvailable, leaf: "statusNoLongerAvailable", kind: .warning),
    ]

    @Test("Each state names its cell key and kind as §5e tabulates them", arguments: table)
    func cellCopy(row: Row) {
        #expect(row.state.cellKey == "desktop.cloudImport.\(row.leaf)")
        #expect(row.state.cellKind == row.kind)
    }

    @Test("Only Expected waits")
    func onlyExpectedWaits() {
        for row in Self.table {
            #expect(row.state.isWaiting == (row.state == .expected), "\(row.state)")
        }
    }

    /// The column earns its place by carrying data. States about *this call's*
    /// transcript bring it; states about the account do not — those are one
    /// sentence, said once, and a column repeating them is the empty-column
    /// shape the Scheduled rule already refuses.
    @Test("Call-level states bring the column; account-level and absent ones do not")
    func bringsColumn() {
        #expect(TranscriptAvailability.available.bringsColumn)
        #expect(TranscriptAvailability.expected.bringsColumn)
        #expect(TranscriptAvailability.noSpeakerNames.bringsColumn)
        #expect(TranscriptAvailability.notResolved.bringsColumn)
        #expect(TranscriptAvailability.noLongerAvailable.bringsColumn)
        #expect(!TranscriptAvailability.notProvided.bringsColumn)
        #expect(!TranscriptAvailability.needsAdminApproval.bringsColumn,
                "Teams' admin wall is a banner's job, and until Phase 3 the Teams window is drawn as it ships")
        #expect(!TranscriptAvailability.needsScope("x").bringsColumn)
        #expect(!TranscriptAvailability.unavailable.bringsColumn)
    }

    @Test("After a fetch: Imported is success, Didn't arrive warns, Not imported is skipped")
    func outcomes() {
        let url = URL(fileURLWithPath: "/tmp/x.vtt")
        #expect(TranscriptOutcome.imported(at: url).cellKind == .success)
        #expect(TranscriptOutcome.imported(at: url).cellKey == "desktop.cloudImport.transcriptImported")
        #expect(TranscriptOutcome.didNotArrive.cellKind == .warning)
        #expect(TranscriptOutcome.didNotArrive.cellKey == "desktop.cloudImport.transcriptDidNotArrive")
        #expect(TranscriptOutcome.notImported.cellKind == .skipped)
        #expect(TranscriptOutcome.notImported.cellKey == "desktop.cloudImport.transcriptNotImported")
    }

    /// A row that read *No transcript* before Import must read it after: the
    /// "skipped" glyph is for the one choice the researcher made (going ahead
    /// while the transcript was still expected), never for an absence.
    @Test("A fetch that had nothing to fetch keeps the listing's word, as it stood", arguments: [
        TranscriptAvailability.notProvided, .noSpeakerNames, .needsAdminApproval,
        .needsScope("x"), .unavailable, .notResolved, .noLongerAvailable,
    ])
    func notFetchedKeepsTheListingWord(state: TranscriptAvailability) {
        let outcome = TranscriptOutcome.notFetched(state)
        #expect(outcome.cellKey == state.cellKey)
        #expect(outcome.cellKind == state.cellKind)
        #expect(outcome != .notImported)
    }

    @Test("The column follows the listing, not the platform")
    func columnFollowsTheListing() {
        func row(_ id: String, _ transcript: TranscriptAvailability) -> CloudImportRow {
            CloudImportRow(id: id, title: id, startsAt: Date(), duration: 600, sizeBytes: nil,
                           expiresAt: nil, attendees: [], localState: .notImported,
                           video: .available, roster: .available, transcript: transcript,
                           organiser: nil)
        }
        #expect(!CloudImportOutline.showsTranscriptColumn(for: []))
        #expect(!CloudImportOutline.showsTranscriptColumn(for: [row("a", .notProvided), row("b", .notProvided)]),
                "every row 'No transcript' means no column")
        #expect(!CloudImportOutline.showsTranscriptColumn(for: [row("a", .needsAdminApproval)]),
                "the shipped Teams listing gains no column")
        #expect(CloudImportOutline.showsTranscriptColumn(for: [row("a", .notProvided), row("b", .available)]),
                "one transcript among none is still a column")
        #expect(CloudImportOutline.showsTranscriptColumn(for: [row("a", .expected)]))
    }
}

// MARK: - The wait

@Suite("Waiting rows")
struct TranscriptWaitingRowTests {

    private func row(
        _ id: String = "r",
        transcript: TranscriptAvailability,
        local: ImportRowState = .notImported,
        video: ArtifactAvailability = .available,
        meeting: String? = nil
    ) -> CloudImportRow {
        CloudImportRow(id: id, title: "P05 Interview", startsAt: Date(), duration: 600,
                       sizeBytes: nil, expiresAt: nil, attendees: [], localState: local,
                       video: video, roster: .available, transcript: transcript,
                       organiser: nil, recordedAt: Date(), meetingID: meeting)
    }

    /// The design's whole argument: the wait is evident and hard to get round.
    /// A disabled box that still *exists* is what says "there is a recording
    /// here and it is not ready" — no box would say there is nothing to fetch.
    @Test("An expected transcript holds the row: disabled checkbox, still drawn, not ticked")
    func expectedHoldsTheRow() {
        let r = row(transcript: .expected)
        #expect(r.isWaitingForTranscript)
        #expect(!r.isSelectable)
        #expect(r.showsCheckbox)
        #expect(!r.drawsTicked(in: []))
        #expect(r.isSelectable(includingWaiting: true), "the footer's checkbox is the one way round")
    }

    /// "Final states are never gated" — an IT refusal must not stop work.
    @Test("Every final transcript state leaves the row tickable",
          arguments: [TranscriptAvailability.available, .notProvided, .noSpeakerNames,
                      .needsAdminApproval, .needsScope("x"), .unavailable, .notResolved,
                      .noLongerAvailable])
    func finalStatesAreNotGated(state: TranscriptAvailability) {
        let r = row(transcript: state)
        #expect(r.isSelectable, "\(state)")
        #expect(!r.isWaitingForTranscript)
    }

    @Test("A held row has nothing to wait for")
    func heldRowDoesNotWait() {
        #expect(!row(transcript: .expected, local: .imported).isWaitingForTranscript)
        #expect(!row(transcript: .expected, local: .notDownloaded(provider: "Dropbox")).isWaitingForTranscript)
        // The one held state that re-fetches waits like a fresh row: the
        // re-fetch is a fetch, and the transcript is coming for it too.
        #expect(row(transcript: .expected, local: .damaged).isWaitingForTranscript)
    }

    @Test("A row with no reachable video is not 'waiting' — it has a bigger problem")
    func unreachableVideoDoesNotWait() {
        #expect(!row(transcript: .expected, video: .notRecorded).isWaitingForTranscript)
        #expect(!row(transcript: .expected, video: .needsScope("drive")).isWaitingForTranscript)
        #expect(!row(transcript: .expected, video: .needsScope("drive")).isSelectable(includingWaiting: true))
    }

    /// The outline counts fetchable rows with the plain predicate, so a
    /// waiting row is not "one you can fetch" until the checkbox lets it be.
    @Test("The outline does not count a waiting row as fetchable")
    func outlineDoesNotCountWaiting() {
        let result = CloudImportOutline.build(rows: [row("a", transcript: .available),
                                                     row("b", transcript: .expected)])
        #expect(result.recordings == 2)
        #expect(result.fetchable == 1)
        #expect(!result.withholding, "a wait is not a permissions problem")
    }

    /// The meeting header summarises what its children *draw*, and acts on
    /// the ones that can act — so a call with one half waiting still offers
    /// its box, and that box ticks only the half that is ready.
    ///
    /// With the ready half ticked the header reads **mixed**, not on: the
    /// waiting half draws an empty box directly beneath it, and a header that
    /// said "all" over an empty box would contradict the row (HIG: a parent
    /// checkbox summarises the state of its children). This is also the right
    /// distinction from a *held* child, which the header ignores — a held file
    /// is here and out of this batch for good; a waiting one can still join it
    /// through the footer, and *mixed* is what says there is more here to tick.
    /// Decided 1 Oct 2026 (review); the first draft of this test expected `.on`.
    @Test("A meeting header ticks the ready half, leaves the waiting half, and reads mixed")
    func headerReadsMixedOverWaitingChild() {
        let children = [row("a", transcript: .available, meeting: "m"),
                        row("b", transcript: .expected, meeting: "m")]
        let tick = CloudImportOutline.parentTick(for: children, ticked: [])
        #expect(tick.draw == .off)
        #expect(tick.isEnabled, "one child can still act")
        let after = CloudImportOutline.parentTick(for: children, ticked: ["a"])
        #expect(after.draw == .mixed, "the waiting child's empty box is beneath the header, so the header is not 'all'")
    }

    /// A call whose recordings are *all* waiting has a dead header for the
    /// wait, not because the files are already here — the view picks its
    /// tooltip from this predicate.
    @Test("A header over only-waiting children is dead and draws off")
    func headerOverOnlyWaitingChildren() {
        let children = [row("a", transcript: .expected, meeting: "m"),
                        row("b", transcript: .expected, meeting: "m")]
        let tick = CloudImportOutline.parentTick(for: children, ticked: [])
        #expect(tick.draw == .off)
        #expect(!tick.isEnabled)
        #expect(children.allSatisfy(\.isWaitingForTranscript))
    }

    @Test("A transcript's arrival is a new row value, not a mutation anyone else can make")
    func withTranscript() {
        let before = row(transcript: .expected)
        let after = before.withTranscript(.available)
        #expect(before.transcript == .expected)
        #expect(after.transcript == .available)
        #expect(after.isSelectable)
        #expect(after.id == before.id)
    }
}

// MARK: - The store

@Suite("Store: waiting rows and the footer checkbox")
@MainActor
struct TranscriptStoreTests {

    /// Lists what it is given; re-checks answer from a script; fetches land a
    /// media file and, for an available transcript, its `.vtt` beside it.
    private final class StubSource: CloudImportSource {
        let rows: [CloudImportRow]
        var recheckAnswer: [String: TranscriptAvailability] = [:]

        init(rows: [CloudImportRow]) { self.rows = rows }

        var accountEmail: String? { "researcher@example.com" }
        var accountTier: GoogleAccountTier { .unknown }
        func signIn() async throws {}

        func list(window: DateInterval) async -> MeetingListing {
            MeetingListing(
                rows: rows,
                arithmetic: JoinArithmetic(eventsInWindow: rows.count, fetchable: rows.count,
                                           organisedByOthers: 0, outcome: .exhausted),
                window: window)
        }

        func fetch(
            row: CloudImportRow,
            destination: URL,
            progress: @escaping @Sendable (FetchProgress) -> Void
        ) async -> FetchOutcome {
            let media = destination.appendingPathComponent("\(row.id).mp4")
            let transcript: TranscriptOutcome
            switch row.transcript {
            case .available: transcript = .imported(at: destination.appendingPathComponent("\(row.id).vtt"))
            case .expected:  transcript = .notImported
            default:         transcript = .notFetched(row.transcript)
            }
            return .imported(bytes: 1_024, at: media, transcript: transcript)
        }

        func recheckTranscripts(rowIDs: [String]) async -> [String: TranscriptAvailability] {
            recheckAnswer.filter { rowIDs.contains($0.key) }
        }
    }

    private func row(_ id: String, _ transcript: TranscriptAvailability,
                     meeting: String? = nil) -> CloudImportRow {
        CloudImportRow(id: id, title: id, startsAt: Date(), duration: 600, sizeBytes: 1_024,
                       expiresAt: nil, attendees: [], localState: .notImported,
                       video: .available, roster: .available, transcript: transcript,
                       organiser: nil, recordedAt: Date(), meetingID: meeting)
    }

    private func settle(_ store: CloudImportStore) async {
        for _ in 0..<2_000 where store.isFetching { await Task.yield() }
    }

    @Test("A waiting row refuses a click until the footer includes it")
    func clickNeedsTheCheckbox() async {
        let store = CloudImportStore(source: StubSource(rows: [row("ready", .available),
                                                               row("wait", .expected)]))
        await store.load()
        #expect(store.waitingCount == 1)
        #expect(!store.toggle("wait"), "refused, so the keyboard path beeps")
        #expect(store.ticked.isEmpty)

        store.includeWaiting = true
        #expect(store.toggle("wait"))
        #expect(store.fetchOrder.map(\.id) == ["wait"], "included, it is in the batch")
        #expect(store.tickedCount == 1)
    }

    @Test("Turning the checkbox off unticks the waiting rows it let in")
    func offAgainUnticks() async {
        let store = CloudImportStore(source: StubSource(rows: [row("ready", .available),
                                                               row("wait", .expected)]))
        await store.load()
        store.includeWaiting = true
        store.toggle("wait")
        store.toggle("ready")
        store.includeWaiting = false
        #expect(store.ticked == ["ready"], "the ready row's tick is the researcher's and survives")
        #expect(store.fetchOrder.map(\.id) == ["ready"])
    }

    /// §0 item 2: "Off each time the window opens, never remembered." A
    /// re-list is a new batch to decide, so the checkbox falls back off with
    /// it rather than silently applying to rows the researcher has not seen.
    @Test("A fresh listing resets the footer checkbox")
    func reloadResetsTheCheckbox() async {
        let store = CloudImportStore(source: StubSource(rows: [row("wait", .expected)]))
        await store.load()
        store.includeWaiting = true
        await store.load()
        #expect(!store.includeWaiting)
    }

    /// A row the researcher has included and ticked has stopped waiting: it
    /// must not be counted as waiting, and it must not draw as waiting. The
    /// store's predicate is what the view reads for both.
    @Test("A row fetched this batch is no longer 'waiting', whatever the listing says")
    func fetchedRowStopsWaiting() async {
        let store = CloudImportStore(source: StubSource(rows: [row("wait", .expected)]))
        await store.load()
        #expect(store.isWaiting(store.rows[0]))
        store.includeWaiting = true
        store.toggle("wait")
        store.startFetch(destination: URL(fileURLWithPath: "/tmp/bn-test"), projectID: UUID())
        await settle(store)
        #expect(!store.isWaiting(store.rows[0]), "its outcome is showing; there is nothing to wait for")
        #expect(store.waitingCount == 0)
    }

    /// §0 item 2: "Bulk ticks (⌘A, a meeting's header checkbox) never include
    /// a waiting row" — with the checkbox on as well as off.
    @Test("Select All and the meeting header never sweep a waiting row in")
    func bulkGesturesSkipWaiting() async {
        let store = CloudImportStore(source: StubSource(rows: [row("a", .available, meeting: "m"),
                                                               row("w", .expected, meeting: "m")]))
        await store.load()
        store.includeWaiting = true
        store.selectAllVisible()
        #expect(store.ticked == ["a"])
        store.clearTicks()
        #expect(store.toggleMeeting(rowIDs: ["a", "w"]))
        #expect(store.ticked == ["a"])
    }

    @Test("A transcript that arrives turns its row Available and ticks it")
    func arrivalTicksTheRow() async {
        let store = CloudImportStore(source: StubSource(rows: [row("ready", .available),
                                                               row("wait", .expected)]))
        await store.load()
        store.applyTranscriptChanges(["wait": .available])
        #expect(store.rows.first { $0.id == "wait" }?.transcript == .available)
        #expect(store.ticked.contains("wait"), "the row ticks itself")
        #expect(store.waitingCount == 0)
        #expect(store.tickedCount == 1)
    }

    /// The arrival tick is for a row the researcher can see and has not dealt
    /// with. A row the filter hides is not one they are acting on, so it moves
    /// to Available and is left unticked — the same rule `toggle` keeps.
    @Test("An arrival on a filtered-out row updates it but does not tick it")
    func arrivalOnHiddenRowDoesNotTick() async {
        let store = CloudImportStore(source: StubSource(rows: [row("P05 wait", .expected),
                                                               row("P06 ready", .available)]))
        await store.load()
        store.filterText = "P06"
        #expect(store.visibleRows.map(\.id) == ["P06 ready"])
        store.applyTranscriptChanges(["P05 wait": .available])
        #expect(store.rows.first { $0.id == "P05 wait" }?.transcript == .available)
        #expect(!store.ticked.contains("P05 wait"), "hidden, so not ticked under the researcher")
    }

    @Test("A transcript that stops being expected for another reason frees the row but does not tick it")
    func nonArrivalFreesWithoutTicking() async {
        let store = CloudImportStore(source: StubSource(rows: [row("wait", .expected)]))
        await store.load()
        store.applyTranscriptChanges(["wait": .notProvided])
        let freed = store.rows.first { $0.id == "wait" }
        #expect(freed?.isSelectable == true)
        #expect(!store.ticked.contains("wait"), "Bristlenose will transcribe — but that is the researcher's tick to make")
    }

    @Test("A re-check that reports nothing changes nothing")
    func quietRecheckIsInert() async {
        let store = CloudImportStore(source: StubSource(rows: [row("wait", .expected)]))
        await store.load()
        let generation = store.outlineGeneration
        store.applyTranscriptChanges([:])
        store.applyTranscriptChanges(["wait": .expected])
        #expect(store.outlineGeneration == generation, "no publish for no change")
        #expect(store.waitingCount == 1)
    }

    @Test("A landed transcript is announced beside its media")
    func landedTranscriptIsAnnounced() async {
        let store = CloudImportStore(source: StubSource(rows: [row("a", .available),
                                                               row("b", .notProvided)]))
        await store.load()
        store.selectAllVisible()
        var announced: CloudImportBatchResult?
        store.onBatchSettled = { announced = $0 }
        store.startFetch(destination: URL(fileURLWithPath: "/tmp/bn-test"), projectID: UUID())
        await settle(store)
        #expect(Set(announced?.landed.map(\.lastPathComponent) ?? []) == ["a.mp4", "a.vtt", "b.mp4"])
        #expect(store.terminus?.imported == 2, "the pair is one row, imported once")
    }

    @Test("The re-check cadence is the design's: 30 s on Teams, 60 s elsewhere")
    func recheckInterval() {
        #expect(CloudImportStore.transcriptRecheckInterval(for: .teams) == .seconds(30))
        #expect(CloudImportStore.transcriptRecheckInterval(for: .meet) == .seconds(60))
        #expect(CloudImportStore.transcriptRecheckInterval(for: .zoom) == .seconds(60))
    }
}
