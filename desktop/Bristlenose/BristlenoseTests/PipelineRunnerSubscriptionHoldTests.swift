import Foundation
import Testing
@testable import Bristlenose

/// A run the app starts by itself (a restored queue, a Whisper re-run) that
/// the subscription check holds is kept and started once the subscription
/// allows it (review, 25 Nov 2026). It used to be dropped, and a restored
/// queue's saved copy erased with it: latent at submission, live from the
/// first lapse, a trial that does not convert about day 7.
@MainActor
struct PipelineRunnerSubscriptionHoldTests {
    typealias Rig = PipelineRunnerQueueTests.Rig
    typealias Persist = PipelineRunnerQueuePersistenceTests

    private func until(_ condition: () -> Bool) async {
        await PipelineRunnerQueueTests.until(condition)
    }

    /// A store whose state the test moves: lapsed (no entitlement, and no
    /// product in a test, so `.storeUnavailable`) until `accept` subscribes it.
    private func lapsedGate() async -> (SubscriptionGate, SubscriptionStore) {
        let store = SubscriptionStore(reads: .init(
            product: { nil }, eligible: { _ in false }, entitlements: { [] }, history: { [] }
        ))
        await store.refresh()
        #expect(store.state == .storeUnavailable)
        return (SubscriptionGate(channel: .appStoreOrTestFlight, store: store), store)
    }

    private func subscribe(_ store: SubscriptionStore) {
        store.accept(.init(productID: SubscriptionAccess.monthlyProductID, start: Date(),
                           expires: Date().addingTimeInterval(30 * 24 * 60 * 60), inTrial: false))
    }

    @Test func aLapseKeepsTheRestoredQueueAndItStartsWhenTheSubscriptionIsBack() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let (gate, store) = await lapsedGate()
        rig.runner.subscriptionGate = gate
        let x = Persist.study(rig, "X"), y = Persist.study(rig, "Y")
        let saved = PersistedRunQueue(entries: [
            .init(projectID: x.id, clean: true, enqueuedAt: Persist.now, studyID: nil, inFlight: true),
            .init(projectID: y.id, clean: false, enqueuedAt: Persist.now, studyID: nil, inFlight: false),
        ])
        let journal = InMemoryRunQueueStore(saved)
        rig.runner.queueJournal.now = { Persist.now }
        await rig.runner.restoreQueue(from: journal, index: rig.index)

        #expect(rig.launches.isEmpty, "a lapsed subscription starts nothing")
        #expect(gate.pending == nil, "an automatic start raises no sheet")
        #expect(journal.saved == saved, "the held queue was erased from what the next launch reads")

        subscribe(store)
        await until { rig.launches.count == 1 }
        #expect(rig.launches.map(\.project.id) == [x.id])
        #expect(rig.launches.first?.clean == true)
        #expect(rig.runner.state[y.id] == .queued(position: 1))
        #expect(journal.saved?.entries.map(\.projectID) == [x.id, y.id])
        #expect(journal.saved?.entries.map(\.enqueuedAt) == [Persist.now, Persist.now],
                "a retried study keeps the time it was first asked for")
    }

    @Test func aHeldStudyPastTheRestoreWindowIsNotStartedLater() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let (gate, store) = await lapsedGate()
        rig.runner.subscriptionGate = gate
        let x = Persist.study(rig, "X")
        let journal = InMemoryRunQueueStore(PersistedRunQueue(entries: [
            .init(projectID: x.id, clean: false, enqueuedAt: Persist.now, studyID: nil, inFlight: false),
        ]))
        var clock = Persist.now
        rig.runner.queueJournal.now = { clock }
        await rig.runner.restoreQueue(from: journal, index: rig.index)
        clock = Persist.now.addingTimeInterval(QueueRestorePolicy.window + 1)
        subscribe(store)
        try? await Task.sleep(for: .milliseconds(100))
        #expect(rig.launches.isEmpty)
    }

    @Test func aHeldWhisperReRunIsStillOwedAndStartsWhenTheSubscriptionIsBack() async throws {
        let waiting = PipelineState.completedPartial(summary: try JSONDecoder().decode(
            PipelineSummary.self,
            from: Data(#"{"transcripts": {"attempted": 1, "succeeded": 0, "failed": [{"session_id": "s1", "cause": {"category": "deferred", "message": "m"}}]}}"#.utf8)
        ))
        let rig = Rig(manifestRead: { _ in waiting }); defer { rig.cleanUp() }
        let p = Persist.study(rig, "P")
        rig.runner.start(project: p)
        let (gate, store) = await lapsedGate()
        rig.runner.subscriptionGate = gate
        rig.launches[0].exit()
        await until { PipelineRunner.isWaitingForWhisper(rig.runner.state[p.id] ?? .idle) }
        #expect(PipelineRunner.isWaitingForWhisper(rig.runner.state[p.id] ?? .idle))

        rig.runner.rerunDeferredProjects()
        #expect(rig.launches.count == 1, "a lapsed subscription starts nothing")
        #expect(rig.runner.whisperRerunsHeld == [p.id], "the held re-run was spent")

        subscribe(store)
        await until { rig.launches.count == 2 }
        #expect(rig.launches.count == 2)
        #expect(rig.launches.last?.project.id == p.id)
        #expect(rig.runner.whisperRerunsHeld.isEmpty)
    }
}
