import Foundation
import Testing

@testable import Bristlenose

// The step the feature was missing: a batch that lands files has to hand them
// to the pipeline.
//
// Until 18 Aug 2026 it did not. `CloudImportStore` finished its transfers,
// cleared the sidebar ring and stopped — the MP4s sat in the destination folder
// and nothing read them. The whole feature reads as working right up to the
// point it matters, which is why nothing caught it: every layer below this was
// green, the bytes really did arrive, and the defect is entirely in what did
// *not* happen next.
//
// Nothing here touches a tenant, a network or a subprocess. `decide` is pure,
// and the store suite drives an instant stub source — the four decline branches
// are otherwise unreachable, since each needs a live download to land into a
// project that happens to be in one particular pipeline state.

@Suite("What happens to a project after a cloud batch lands")
struct CloudImportHandoffTests {

    // MARK: - The ordinary path

    @Test("A folder-shaped project analyses what just arrived")
    func folderShapedAnalyses() {
        #expect(CloudImportHandoff.decide(landed: 4, shape: .folder, state: .idle) == .analyse)
    }

    @Test("An already-analysed project folds them in rather than declining")
    func analysedProjectStillRuns() {
        // The incremental case, and the one most tempting to guard against:
        // "it's already been analysed, don't touch it" would leave four new
        // interviews sitting in a finished study, which is precisely the
        // outcome the researcher imported them to avoid. `handleDropOnProject`
        // made the same call for dragged files — analysed or not, a
        // folder-shaped project rescans at run time.
        #expect(CloudImportHandoff.decide(
            landed: 1, shape: .folder, state: .ready(Date())) == .analyse)
    }

    @Test("A project nobody has scanned yet analyses")
    func unknownStateAnalyses() {
        // `state[id]` is nil until the launch scan resolves it. Treating an
        // unresolved state as a reason to decline would make the behaviour
        // depend on how quickly the sidebar finished scanning — a race, and one
        // that would drop the run silently.
        #expect(CloudImportHandoff.decide(landed: 2, shape: .folder, state: nil) == .analyse)
    }

    @Test("A partial batch is still worth analysing")
    func partialBatchRuns() {
        // Settled: "Process a partial batch — incremental analysis makes that
        // ordinary." Two of six landing is two interviews' worth of findings,
        // and the four that failed stay ticked for Retry.
        #expect(CloudImportHandoff.decide(landed: 2, shape: .folder, state: .idle) == .analyse)
    }

    // MARK: - Nothing landed

    @Test("A batch that landed nothing starts nothing")
    func nothingLandedDeclines() {
        // "Never hand a certainly-failing situation forward." Every row failed,
        // or Stop was pressed before the first one settled: there is no new
        // material, so a run would re-do the existing study for no reason and
        // bill for it.
        #expect(CloudImportHandoff.decide(landed: 0, shape: .folder, state: .idle)
                == .nothing(.nothingLanded))
    }

    @Test("Nothing landed outranks every other input")
    func nothingLandedOutranksShape() {
        // Checked first deliberately — a file-subset project with an empty
        // batch must not reach `registerOnly` and record zero paths as though
        // something had happened.
        #expect(CloudImportHandoff.decide(landed: 0, shape: .fileSubset, state: nil)
                == .nothing(.nothingLanded))
    }

    // MARK: - The four states where a run would be wrong

    @Test("A project already running is left alone")
    func runningDeclines() {
        // Its inputs were fixed when it started, so these files belong to the
        // next run, not this one.
        #expect(CloudImportHandoff.decide(landed: 3, shape: .folder, state: .running)
                == .nothing(.runInProgress))
    }

    @Test("A queued project is left alone")
    func queuedDeclines() {
        #expect(CloudImportHandoff.decide(landed: 3, shape: .folder, state: .queued(position: 1))
                == .nothing(.runInProgress))
    }

    @Test("A project whose last run failed is not re-run unbidden")
    func failedDeclines() {
        // Re-running a known-broken pipeline burns LLM spend repeating the same
        // failure. Retry is a button the researcher presses.
        #expect(CloudImportHandoff.decide(
            landed: 3, shape: .folder,
            state: .failed("boom", category: .unknown)) == .nothing(.previousRunFailed))
    }

    @Test("The diagnostic failure shape declines too, not just the older one")
    func failedWithDiagnosticDeclines() {
        // The case a `.failed`-only guard would miss, and it is the *common*
        // one: `.failedWithDiagnostic` is what a modern abandoned run resolves
        // to, so matching only `.failed` would auto-re-run exactly the projects
        // whose failure is best understood. Two enum cases, one meaning —
        // pinned separately because the compiler will not ask.
        #expect(CloudImportHandoff.decide(
            landed: 3, shape: .folder,
            state: .failedWithDiagnostic(summary: PipelineSummary())) == .nothing(.previousRunFailed))
    }

    @Test("An unreachable project is left alone")
    func unreachableDeclines() {
        #expect(CloudImportHandoff.decide(
            landed: 3, shape: .folder,
            state: .unreachable(reason: "volume gone")) == .nothing(.projectUnreachable))
    }

    // MARK: - File-subset projects

    @Test("A file-subset project records the paths but starts nothing")
    func fileSubsetRegistersOnly() {
        // The CLI has no `--files`, so it cannot scope a run to just the
        // additions. Recording them is what makes the next full run see them.
        #expect(CloudImportHandoff.decide(landed: 2, shape: .fileSubset, state: .idle)
                == .registerOnly)
    }

    @Test("A busy file-subset project declines rather than registering")
    func fileSubsetRespectsRunState() {
        // Shape is decided last, after the run-state guards — otherwise a
        // file-subset project would have its `inputFiles` rewritten underneath
        // a run that had already read them.
        #expect(CloudImportHandoff.decide(landed: 2, shape: .fileSubset, state: .running)
                == .nothing(.runInProgress))
    }

    // MARK: - Who tells the researcher

    @Test("Only a starting run marks the landed files as known")
    func seedsOnlyWhenAnalysing() {
        #expect(CloudImportHandoff.seedsWatcher(.analyse))
    }

    @Test("Every decline leaves the files for the watcher to surface")
    func declinesDoNotSeed() {
        // The asymmetry that saves this path from inventing a toast, a sheet or
        // a verb. Seeding suppresses the project row's new-files count pill; on
        // a decline that pill is the honest thing on screen — real files
        // arrived in a real folder and nothing is going to read them — and it
        // works from the sidebar with the import window closed, which is the
        // case this whole feature keeps having to answer for.
        #expect(!CloudImportHandoff.seedsWatcher(.registerOnly))
        #expect(!CloudImportHandoff.seedsWatcher(.nothing(.nothingLanded)))
        #expect(!CloudImportHandoff.seedsWatcher(.nothing(.runInProgress)))
        #expect(!CloudImportHandoff.seedsWatcher(.nothing(.previousRunFailed)))
        #expect(!CloudImportHandoff.seedsWatcher(.nothing(.projectUnreachable)))
    }
}

// MARK: - The store's half of the seam

@MainActor
@Suite("A settled batch announces what it landed")
struct CloudImportBatchSettlementTests {

    /// Lands the rows it is told to and fails the rest, with no sleeps — the
    /// fixture source simulates a 2-second transfer per row, which is honest
    /// on screen and useless in a test.
    private final class StubSource: CloudImportSource {
        let rows: [CloudImportRow]
        let failing: Set<String>
        init(rows: [CloudImportRow], failing: Set<String> = []) {
            self.rows = rows
            self.failing = failing
        }

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
            if failing.contains(row.id) {
                return .failed(reason: "stubbed failure", isRetryable: true)
            }
            return .imported(bytes: 1_024,
                             at: destination.appendingPathComponent("\(row.id).mp4"))
        }
    }

    private func row(_ id: String) -> CloudImportRow {
        CloudImportRow(
            id: id, title: id, startsAt: Date(), duration: 600, sizeBytes: 1_024,
            expiresAt: nil, attendees: [], localState: .notImported,
            video: .available, roster: .available, transcript: .available,
            organiser: nil, recordedAt: Date())
    }

    /// Bounded rather than open-ended, so a batch that never settles fails as a
    /// timeout instead of hanging the suite.
    private func settle(_ store: CloudImportStore) async {
        for _ in 0..<2_000 where store.isFetching { await Task.yield() }
    }

    @Test("The landed files are announced with the project they landed in")
    func announcesLandedFiles() async {
        let store = CloudImportStore(
            source: StubSource(rows: [row("a"), row("b")]), platform: .teams)
        await store.load()
        store.selectAllVisible()

        let projectID = UUID()
        var announced: CloudImportBatchResult?
        store.onBatchSettled = { announced = $0 }

        store.startFetch(destination: URL(fileURLWithPath: "/tmp/bn-test"), projectID: projectID)
        await settle(store)

        #expect(announced?.projectID == projectID,
                "the batch must name the project it was aimed at — it is the only thing that knows")
        #expect(Set(announced?.landed.map { $0.lastPathComponent } ?? []) == ["a.mp4", "b.mp4"])
    }

    @Test("Only the rows that actually landed are announced")
    func failedRowsAreNotAnnounced() async {
        // The seeding downstream is keyed on these names. A failed row reported
        // as landed would be seeded as "known", suppressing the count pill for
        // a file that is not there — a row claiming to hold a recording it
        // never received.
        let store = CloudImportStore(
            source: StubSource(rows: [row("a"), row("b"), row("c")], failing: ["b"]),
            platform: .teams)
        await store.load()
        store.selectAllVisible()

        var announced: CloudImportBatchResult?
        store.onBatchSettled = { announced = $0 }
        store.startFetch(destination: URL(fileURLWithPath: "/tmp/bn-test"), projectID: UUID())
        await settle(store)

        #expect(Set(announced?.landed.map { $0.lastPathComponent } ?? []) == ["a.mp4", "c.mp4"])
    }

    @Test("A batch where everything failed still announces, so the decision is made in one place")
    func emptyBatchStillAnnounces() async {
        // It would be easy to skip the callback when nothing landed. Then
        // "nothing landed" would be decided in the store by omission and every
        // other case in `CloudImportHandoff` — which is where a future reader
        // will look for it, and where `nothingLanded` is written down.
        let store = CloudImportStore(
            source: StubSource(rows: [row("a")], failing: ["a"]), platform: .teams)
        await store.load()
        store.selectAllVisible()

        var announced: CloudImportBatchResult?
        store.onBatchSettled = { announced = $0 }
        store.startFetch(destination: URL(fileURLWithPath: "/tmp/bn-test"), projectID: UUID())
        await settle(store)

        #expect(announced != nil, "the batch settled; something has to say so")
        #expect(announced?.landed.isEmpty == true)
    }

    @Test("A live window is wired to the pipeline; a fixture window is not")
    func onlyLiveSessionsAreWired() {
        // The composition, and the two ways it can be wrong — both silent.
        //
        // Unwired: the download works perfectly and nothing happens next, which
        // is the defect this whole change fixes and is invisible from every
        // layer below. `openLive` has five `store =` assignments across three
        // early returns, so the `defer` doing the wiring is asserted here
        // rather than trusted.
        //
        // Wired to a fixture: the Diagnostics menu starts a real, billable
        // pipeline run against a project that gained nothing, because the
        // fixture source simulates transfers and writes no bytes.
        //
        // Deliberately synchronous — the coordinator observes the process-wide
        // disconnect notification on the main queue, so a body with no `await`
        // cannot be interleaved by a sibling suite's post.
        let live = CloudImportCoordinator()
        live.openLive(.teams, preselecting: nil)
        #expect(live.store?.onBatchSettled != nil,
                "a live batch that lands files must have somewhere to hand them")

        let fixture = CloudImportCoordinator()
        fixture.openFixture(.teams, .populated, preselecting: nil)
        #expect(fixture.store?.onBatchSettled == nil,
                "a Diagnostics scenario writes no bytes and must not start a run")
    }

    @Test("A retry announces what the retry landed, not the whole session")
    func retryAnnouncesOnlyItsOwnBatch() async {
        // `startFetch` clears `outcomes`, so this holds by construction rather
        // than by bookkeeping — pinned because the construction is easy to
        // change and the consequence is invisible: the second announcement
        // would re-seed and re-register files the first run already handled.
        let store = CloudImportStore(
            source: StubSource(rows: [row("a"), row("b")], failing: ["b"]), platform: .teams)
        await store.load()
        store.selectAllVisible()

        var announcements: [CloudImportBatchResult] = []
        store.onBatchSettled = { announcements.append($0) }
        let projectID = UUID()
        store.startFetch(destination: URL(fileURLWithPath: "/tmp/bn-test"), projectID: projectID)
        await settle(store)

        // "a" landed and stopped being tickable; "b" failed and stays ticked,
        // which is what Retry acts on.
        store.startFetch(destination: URL(fileURLWithPath: "/tmp/bn-test"), projectID: projectID)
        await settle(store)

        #expect(announcements.count == 2)
        #expect(announcements.last?.landed.isEmpty == true,
                "the retry re-fetched only the row that failed, and it failed again")
    }
}
