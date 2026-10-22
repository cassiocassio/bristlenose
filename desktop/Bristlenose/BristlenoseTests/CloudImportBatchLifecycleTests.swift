import Foundation
import Testing

@testable import Bristlenose

// How a batch ends, when it does not end by landing every row.
//
// The sidebar's project row draws `store.batch` as "0 of N" for as long as it
// is set, and it is the only thing that can say "is it still going?" once the
// import window is closed. So every way a batch can end has to clear it, and
// only the batch that set it may: a batch that was stopped and replaced must
// not reach into its replacement on the way out.

@MainActor
@Suite("How a cloud batch ends")
struct CloudImportBatchLifecycleTests {

    /// Declines the grant, or holds each transfer until it is cancelled. The
    /// counters are locked because `fetch` runs off the main actor.
    private final class StubSource: CloudImportSource {
        let rows: [CloudImportRow]
        let declinesGrant: Bool
        private let lock = NSLock()
        private var _calls = 0
        private var _returns = 0

        init(rows: [CloudImportRow], declinesGrant: Bool = false) {
            self.rows = rows
            self.declinesGrant = declinesGrant
        }

        var calls: Int { lock.lock(); defer { lock.unlock() }; return _calls }
        var returns: Int { lock.lock(); defer { lock.unlock() }; return _returns }

        var accountEmail: String? { "researcher@example.com" }
        var accountTier: GoogleAccountTier { .unknown }
        func signIn() async throws {}

        struct Declined: Error {}

        func prepareBatch(rowIDs: [String]) async throws {
            if declinesGrant { throw Declined() }
        }

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
            lock.lock(); _calls += 1; lock.unlock()
            defer { lock.lock(); _returns += 1; lock.unlock() }
            // Long enough to outlast every assertion, short enough that a
            // transfer nothing can cancel (the defect below) cannot hang the
            // suite.
            do {
                try await Task.sleep(nanoseconds: 5_000_000_000)
            } catch {
                // A cancelled download does not return at once: the session
                // task has to tear down first. Modelled, because that latency
                // is what lets a replacement batch register its own transfer
                // of the same row before the stopped one settles. A cancelled
                // `Task.sleep` alone returns instantly and hides it.
                await withCheckedContinuation { done in
                    DispatchQueue.global().asyncAfter(deadline: .now() + 0.05) { done.resume() }
                }
                return .cancelled
            }
            return .imported(bytes: 1_024,
                             at: destination.appendingPathComponent("\(row.id).mp4"),
                             transcript: .notFetched(row.transcript))
        }
    }

    private func row(_ id: String) -> CloudImportRow {
        CloudImportRow(
            id: id, title: id, startsAt: Date(), duration: 600, sizeBytes: 1_024,
            expiresAt: nil, attendees: [], localState: .notImported,
            video: .available, roster: .available, transcript: .available,
            organiser: nil, recordedAt: Date())
    }

    private let destination = URL(fileURLWithPath: "/tmp/bn-test")

    /// Bounded, so a condition that never comes true fails as an assertion
    /// rather than hanging the suite.
    private func until(_ condition: () -> Bool) async {
        for _ in 0..<500 where !condition() {
            try? await Task.sleep(nanoseconds: 2_000_000)
        }
    }

    // MARK: - A declined grant

    @Test("A declined grant clears the sidebar's batch ring")
    func declinedGrantClearsBatch() async {
        // Google's Picker grant is per batch, and the researcher can decline
        // it or close the window. Every row is then marked "access not
        // granted" and the batch is over — but the ring was left set, so the
        // project row went on saying "0 of 2" with nothing transferring, for
        // the life of the app.
        let store = CloudImportStore(
            source: StubSource(rows: [row("a"), row("b")], declinesGrant: true))
        await store.load()
        store.selectAllVisible()

        store.startFetch(destination: destination, projectID: UUID())
        #expect(store.batch != nil, "premise: Import puts the ring up")
        await until { !store.isFetching }

        #expect(!store.isFetching, "premise: the batch ended")
        #expect(store.outcomes["a"] == .failed(reason: .accessNotGranted, isRetryable: true),
                "premise: it ended on the declined grant")
        #expect(store.batch == nil, "a batch that is over must not leave its ring on the sidebar")
    }

    // MARK: - A stopped batch, replaced before it settled

    /// Import, Stop, Import again — the second Import before the stopped
    /// transfer has settled, which is the ordinary pace of a researcher who
    /// stopped by mistake. Waits until the stopped batch's transfer has
    /// returned and its coordinator has had time to finish.
    ///
    /// The wait for the coordinator is time, not a signal: nothing outside the
    /// store can see it finish, and the defect *is* what it does on the way
    /// out. The red run against the unfixed store is what shows the wait is
    /// long enough to see it.
    private func supersededBatch() async -> (CloudImportStore, StubSource, UUID) {
        let source = StubSource(rows: [row("a")])
        let store = CloudImportStore(source: source)
        await store.load()
        store.selectAllVisible()

        store.startFetch(destination: destination, projectID: UUID())
        await until { source.calls == 1 }
        #expect(source.calls == 1, "premise: the first batch's transfer is under way")

        // No `await` between these: the stopped transfer cannot settle in
        // between, so the replacement is genuinely running when it does.
        store.stopFetch()
        let replacement = UUID()
        store.startFetch(destination: destination, projectID: replacement)
        #expect(store.isFetching, "premise: the replacement started")

        await until { source.calls == 2 && source.returns == 1 }
        #expect(source.returns == 1, "premise: the stopped transfer has returned")
        try? await Task.sleep(nanoseconds: 200_000_000)
        return (store, source, replacement)
    }

    @Test("A stopped batch settling late does not end the one that replaced it")
    func supersededBatchLeavesReplacementFetching() async {
        // `isFetching` drives the window's Stop button and gates the next
        // Import. The stopped batch cleared it on the way out, so the
        // replacement read as finished mid-transfer: no Stop, and a second
        // Import allowed over the top of it.
        let (store, _, replacement) = await supersededBatch()

        #expect(store.isFetching, "the replacement is still transferring")
        #expect(store.batch?.projectID == replacement)

        store.stopFetch()
    }

    @Test("A stopped batch settling late does not count toward, or orphan, the replacement's row")
    func supersededBatchLeavesReplacementRowAlone() async {
        // The same row is in both batches (Stop leaves it ticked, so Import
        // picks it up again). The stopped transfer, settling, counted itself
        // into the replacement's ring — "1 of 1" with the file still moving —
        // and dropped the replacement's handle on that row, so the row's own
        // stop button, and Stop, could no longer reach the transfer.
        let (store, source, _) = await supersededBatch()

        #expect(store.batch?.done == 0, "nothing in the replacement has settled")

        store.cancelRow("a")
        await until { source.returns == 2 }
        #expect(source.returns == 2, "stopping the row reaches the transfer actually running")

        store.stopFetch()
    }

    // MARK: - A stopped batch's grant, landing during the next batch's

    /// Holds every grant until the test ends it, the way a consent window sits
    /// in the researcher's browser. The continuation is deliberately not
    /// cancellation-aware: Stop cancels the coordinator's `Task`, and that does
    /// not reach into an `ASWebAuthenticationSession` either.
    private final class HeldGrantSource: CloudImportSource {
        let rows: [CloudImportRow]
        private let lock = NSLock()
        private var held: [CheckedContinuation<Void, Error>] = []
        private var _returned = 0

        init(rows: [CloudImportRow]) { self.rows = rows }

        var asked: Int { lock.lock(); defer { lock.unlock() }; return held.count }
        var returned: Int { lock.lock(); defer { lock.unlock() }; return _returned }

        var accountEmail: String? { "researcher@example.com" }
        var accountTier: GoogleAccountTier { .unknown }
        func signIn() async throws {}

        struct Declined: Error {}

        func prepareBatch(rowIDs: [String]) async throws {
            defer { lock.lock(); _returned += 1; lock.unlock() }
            try await withCheckedThrowingContinuation { (grant: CheckedContinuation<Void, Error>) in
                lock.lock(); held.append(grant); lock.unlock()
            }
        }

        /// Ends the `index`th grant asked for: granted, or dismissed.
        func end(_ index: Int, granted: Bool) {
            lock.lock(); let grant = held[index]; lock.unlock()
            if granted { grant.resume() } else { grant.resume(throwing: Declined()) }
        }

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
            .cancelled
        }
    }

    @Test("A stopped batch's grant, landing late, leaves the next batch waiting for its own",
          arguments: [true, false])
    func supersededGrantLeavesReplacementAwaiting(stoppedGrantIsGranted: Bool) async {
        // Import opens a consent window; Stop; Import again opens a second.
        // The first window cannot be closed by Stop, so the researcher can
        // still grant or dismiss it — and the stopped batch, returning, cleared
        // "waiting for you to grant access" while the replacement was still
        // blocked on exactly that.
        let source = HeldGrantSource(rows: [row("a")])
        let store = CloudImportStore(source: source)
        await store.load()
        store.selectAllVisible()

        store.startFetch(destination: destination, projectID: UUID())
        await until { source.asked == 1 }
        #expect(source.asked == 1, "premise: the first batch is waiting on its grant")

        store.stopFetch()
        store.startFetch(destination: destination, projectID: UUID())
        await until { source.asked == 2 }
        #expect(source.asked == 2, "premise: the replacement is waiting on its own grant")
        #expect(store.isAwaitingGrant, "premise: the replacement's rows say so")

        source.end(0, granted: stoppedGrantIsGranted)
        await until { source.returned == 1 }
        #expect(source.returned == 1, "premise: the stopped batch's grant has returned")
        // The coordinator's next line runs on the main actor after the grant
        // returns, and nothing outside the store can see it run. Time, as in
        // `supersededBatch()`; the red run against the unguarded store is
        // what shows it is long enough.
        try? await Task.sleep(nanoseconds: 100_000_000)

        #expect(store.isAwaitingGrant,
                "the replacement is still waiting for the researcher to grant access")

        store.stopFetch()
        source.end(1, granted: false)
        await until { source.returned == 2 }
    }
}
