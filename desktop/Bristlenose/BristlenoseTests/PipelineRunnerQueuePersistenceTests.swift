import Foundation
import Testing
@testable import Bristlenose

/// The run queue across Quit (R19 follow-up, 20 Oct 2026), driven through the
/// real `PipelineRunner` with the queue suite's launcher that starts nothing.
///
/// Until now the queue lived in memory and Quit dropped it (logged only). The
/// owner's decision: the queue is the researcher's intent, so the next launch
/// restores it in order, the run Quit stopped first, while it is under 92 hours
/// old and its studies are still there.
@MainActor
struct PipelineRunnerQueuePersistenceTests {
    typealias Rig = PipelineRunnerQueueTests.Rig

    static let now = Date(timeIntervalSince1970: 1_792_490_400)
    static let hour: TimeInterval = 60 * 60

    /// A rig whose runner keeps its queue in `store`, at a fixed clock.
    static func rig(store: InMemoryRunQueueStore = .init()) async -> Rig {
        let rig = Rig()
        rig.runner.queueJournal.now = { now }
        await rig.runner.restoreQueue(from: store, index: rig.index)
        return rig
    }

    /// A study folder holding a recording.
    static func study(_ rig: Rig, _ name: String) -> Project {
        let p = rig.project(name)
        FileManager.default.createFile(
            atPath: URL(fileURLWithPath: p.path).appendingPathComponent("interview.mp4").path,
            contents: Data("x".utf8)
        )
        return p
    }

    static func ids(_ store: InMemoryRunQueueStore) -> [UUID] {
        store.saved?.entries.map(\.projectID) ?? []
    }

    private func until(_ condition: () -> Bool, seconds: Double = PipelineRunnerQueueTests.patience) async {
        let deadline = Date().addingTimeInterval(seconds)
        while !condition(), Date() < deadline {
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    // MARK: - Kept as it changes

    @Test func theQueueIsKeptInOrderWithTheRunInFlightFirst() async {
        let store = InMemoryRunQueueStore()
        let rig = await Self.rig(store: store); defer { rig.cleanUp() }
        let a = Self.study(rig, "A"), b = Self.study(rig, "B"), c = Self.study(rig, "C")
        rig.runner.start(project: a)
        rig.runner.start(project: b, clean: true)
        rig.runner.start(project: c)

        #expect(store.saved?.entries == [
            .init(projectID: a.id, clean: false, enqueuedAt: Self.now, studyID: nil, inFlight: true),
            .init(projectID: b.id, clean: true, enqueuedAt: Self.now, studyID: nil, inFlight: false),
            .init(projectID: c.id, clean: false, enqueuedAt: Self.now, studyID: nil, inFlight: false),
        ])
    }

    @Test func aSecondAnalyseOnAWaitingStudyKeepsItsFirstRequestTime() async {
        let store = InMemoryRunQueueStore()
        let rig = await Self.rig(store: store); defer { rig.cleanUp() }
        let a = Self.study(rig, "A"), b = Self.study(rig, "B")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.queueJournal.now = { Self.now.addingTimeInterval(Self.hour) }
        rig.runner.start(project: b, clean: true)

        #expect(store.saved?.entries.last?.enqueuedAt == Self.now)
        #expect(store.saved?.entries.last?.clean == true)
    }

    @Test func removingAStudyFromTheQueueIsKept() async {
        let store = InMemoryRunQueueStore()
        let rig = await Self.rig(store: store); defer { rig.cleanUp() }
        let a = Self.study(rig, "A"), b = Self.study(rig, "B"), c = Self.study(rig, "C")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.start(project: c)
        rig.runner.cancel(project: b)

        #expect(Self.ids(store) == [a.id, c.id])
    }

    @Test func stopTakesTheRunOutAtOnceBeforeItHasEnded() async {
        let store = InMemoryRunQueueStore()
        let rig = await Self.rig(store: store); defer { rig.cleanUp() }
        let a = Self.study(rig, "A"), b = Self.study(rig, "B")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.cancel(project: a)

        #expect(rig.launches[0].running, "the run has not ended yet")
        #expect(Self.ids(store) == [b.id], "Stop then Quit must not bring the run back")
    }

    @Test func aRunThatFinishesLeavesTheQueueAndTheNextBecomesItsHead() async {
        let store = InMemoryRunQueueStore()
        let rig = await Self.rig(store: store); defer { rig.cleanUp() }
        let a = Self.study(rig, "A"), b = Self.study(rig, "B")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.queueJournal.now = { Self.now.addingTimeInterval(Self.hour) }
        rig.launches[0].exit()
        await until { rig.launches.count == 2 }

        #expect(store.saved?.entries.map(\.projectID) == [b.id])
        #expect(store.saved?.entries.first?.inFlight == true)
        #expect(store.saved?.entries.first?.enqueuedAt == Self.now,
                "moving up to run is not a new request: the 92 hours run from when B was asked for")
    }

    // MARK: - Quit is not a Stop

    @Test func quitKeepsTheRunItStoppedAtTheHeadOfTheQueue() async {
        let store = InMemoryRunQueueStore()
        let rig = await Self.rig(store: store); defer { rig.cleanUp() }
        let a = Self.study(rig, "A"), b = Self.study(rig, "B")
        rig.runner.start(project: a, clean: true)
        rig.runner.start(project: b)
        let before = store.saved

        rig.runner.stopAllForQuit()
        // The run takes the SIGINT and ends; the app is still finishing its
        // quit, and nothing that follows is the researcher's doing.
        rig.launches[0].exit(.exited(code: 130))
        try? await Task.sleep(for: .milliseconds(300))

        #expect(rig.signals.contains { $0.sig == SIGINT })
        #expect(store.saved == before)
        #expect(store.saved?.entries.first?.inFlight == true)
        #expect(store.saved?.entries.first?.clean == true)
    }

    // MARK: - Restored on the next launch

    @Test func aQueueFromFridayEveningRestartsOnMondayInOrder() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let x = Self.study(rig, "X"), y = Self.study(rig, "Y"), z = Self.study(rig, "Z")
        let friday = Self.now.addingTimeInterval(-64 * Self.hour)
        let store = InMemoryRunQueueStore(PersistedRunQueue(entries: [
            .init(projectID: x.id, clean: true, enqueuedAt: friday, studyID: nil, inFlight: true),
            .init(projectID: y.id, clean: false, enqueuedAt: friday, studyID: nil, inFlight: false),
            .init(projectID: z.id, clean: false, enqueuedAt: friday, studyID: nil, inFlight: false),
        ]))
        rig.runner.queueJournal.now = { Self.now }
        await rig.runner.restoreQueue(from: store, index: rig.index)

        #expect(rig.launches.map(\.project.id) == [x.id], "the head starts, nothing else")
        #expect(rig.launches.first?.clean == true, "a stopped Re-analyse stays a Re-analyse")
        #expect(rig.runner.state[y.id] == .queued(position: 1))
        #expect(rig.runner.state[z.id] == .queued(position: 2))
        // Kept with the time it was first asked for, so a queue reopened every
        // few days still lapses 92 hours after Friday.
        #expect(store.saved?.entries.map(\.enqueuedAt) == [friday, friday, friday])
        #expect(Self.ids(store) == [x.id, y.id, z.id])
    }

    @Test func lapsedGoneAndEmptyStudiesAreDroppedAndTheRestRun() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let old = Self.study(rig, "Old"), moved = Self.study(rig, "Moved")
        let empty = rig.project("Empty"), removed = Self.study(rig, "Removed")
        let fine = Self.study(rig, "Fine")
        try FileManager.default.removeItem(atPath: moved.path)
        rig.index.removeProject(id: removed.id)
        let fresh = Self.now.addingTimeInterval(-Self.hour)
        let store = InMemoryRunQueueStore(PersistedRunQueue(entries: [
            .init(projectID: old.id, clean: false,
                  enqueuedAt: Self.now.addingTimeInterval(-QueueRestorePolicy.window),
                  studyID: nil, inFlight: true),
            .init(projectID: moved.id, clean: false, enqueuedAt: fresh, studyID: nil, inFlight: false),
            .init(projectID: empty.id, clean: false, enqueuedAt: fresh, studyID: nil, inFlight: false),
            .init(projectID: removed.id, clean: false, enqueuedAt: fresh, studyID: nil, inFlight: false),
            .init(projectID: fine.id, clean: false, enqueuedAt: fresh, studyID: nil, inFlight: false),
        ]))
        rig.runner.queueJournal.now = { Self.now }
        await rig.runner.restoreQueue(from: store, index: rig.index)

        #expect(rig.launches.map(\.project.id) == [fine.id])
        #expect(Self.ids(store) == [fine.id])
        for gone in [old, moved, empty] {
            #expect(rig.runner.state[gone.id].map { if case .queued = $0 { true } else { false } } != true,
                    "a dropped study shows no queue state")
        }
    }

    @Test func aQueueThatHasAllLapsedIsClearedSoItIsNotReadAgain() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = Self.study(rig, "A")
        let store = InMemoryRunQueueStore(PersistedRunQueue(entries: [
            .init(projectID: a.id, clean: false,
                  enqueuedAt: Self.now.addingTimeInterval(-15 * 24 * Self.hour),
                  studyID: nil, inFlight: true),
        ]))
        rig.runner.queueJournal.now = { Self.now }
        await rig.runner.restoreQueue(from: store, index: rig.index)

        #expect(rig.launches.isEmpty)
        #expect(store.saved == .empty)
    }

    @Test func aFolderNowHoldingAnotherStudyIsNotRun() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = Self.study(rig, "A")
        let store = InMemoryRunQueueStore(PersistedRunQueue(entries: [
            .init(projectID: a.id, clean: false, enqueuedAt: Self.now,
                  studyID: "11111111-1111-1111-1111-111111111111", inFlight: true),
        ]))
        rig.runner.queueJournal.now = { Self.now }
        await rig.runner.restoreQueue(from: store, index: rig.index) { _ in
            .init(studyIDOnDisk: "22222222-2222-2222-2222-222222222222", inputs: .present)
        }

        #expect(rig.launches.isEmpty)
    }

    @Test func aRestoredRunWaitsForTheLaunchScanOfItsStudy() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = Self.study(rig, "A")
        rig.runner._debugSetState(.scanning, for: a.id)
        let store = InMemoryRunQueueStore(PersistedRunQueue(entries: [
            .init(projectID: a.id, clean: false, enqueuedAt: Self.now, studyID: nil, inFlight: true),
        ]))
        rig.runner.queueJournal.now = { Self.now }
        let restoring = Task { await rig.runner.restoreQueue(from: store, index: rig.index) }
        try? await Task.sleep(for: .milliseconds(300))
        #expect(rig.launches.isEmpty, "started while the scan was still reading its PID file")

        rig.runner._debugSetState(.stopped(stagesComplete: []), for: a.id)
        await restoring.value
        #expect(rig.launches.map(\.project.id) == [a.id])
    }

    @Test func aRestoredStudyWaitsForTheRunQuitStoppedToFinishStopping() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = Self.study(rig, "A"), b = Self.study(rig, "B")
        // Relaunched while the old run is still taking its SIGINT: the launch
        // scan reads it as a run this launch did not start.
        rig.runner._debugSetState(.running, for: a.id)
        let store = InMemoryRunQueueStore(PersistedRunQueue(entries: [
            .init(projectID: a.id, clean: false, enqueuedAt: Self.now, studyID: nil, inFlight: true),
            .init(projectID: b.id, clean: false, enqueuedAt: Self.now, studyID: nil, inFlight: false),
        ]))
        rig.runner.queueJournal.now = { Self.now }
        let restoring = Task { await rig.runner.restoreQueue(from: store, index: rig.index) }
        try? await Task.sleep(for: .milliseconds(300))
        #expect(rig.launches.isEmpty, "B jumped ahead, or A was turned away")

        rig.runner._debugSetState(.stopped(stagesComplete: []), for: a.id)
        await restoring.value
        #expect(rig.launches.map(\.project.id) == [a.id])
        #expect(rig.runner.state[b.id] == .queued(position: 1))
    }

    @Test func aSecondWindowDoesNotRestoreTheQueueAgain() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = Self.study(rig, "A")
        let saved = PersistedRunQueue(entries: [
            .init(projectID: a.id, clean: false, enqueuedAt: Self.now, studyID: nil, inFlight: true),
        ])
        rig.runner.queueJournal.now = { Self.now }
        await rig.runner.restoreQueue(from: InMemoryRunQueueStore(saved), index: rig.index)
        // The restored run ends, so a second restore would be free to start it.
        rig.launches[0].exit()
        await until { rig.runner.state[a.id].map { if case .running = $0 { false } else { true } } ?? true }
        #expect(rig.runner.state[a.id].map { if case .running = $0 { false } else { true } } ?? true,
                "precondition: the slot is free")
        await rig.runner.restoreQueue(from: InMemoryRunQueueStore(saved), index: rig.index)

        #expect(rig.launches.count == 1)
    }

    // MARK: - One copy of the app keeps the queue

    @Test func onlyOneHolderGetsTheQueueLock() throws {
        let url = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("run-queue-\(UUID().uuidString).lock")
        defer { try? FileManager.default.removeItem(at: url) }
        var first = RunQueueLock(url: url)
        #expect(first != nil)
        #expect(RunQueueLock(url: url) == nil, "a second copy of the app must not read or write the queue")
        first = nil
        #expect(RunQueueLock(url: url) != nil, "the lock goes with its holder")
    }

    @Test func theDefaultsStoreReadsBackWhatItWrote() throws {
        let suite = "queue-store-\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        let store = DefaultsRunQueueStore(defaults: defaults, lock: nil)
        let queue = PersistedRunQueue(entries: [
            .init(projectID: UUID(), clean: true, enqueuedAt: Self.now, studyID: "s", inFlight: true),
        ])
        store.save(queue)
        #expect(store.load() == queue)

        defaults.set(Data("not json".utf8), forKey: DefaultsRunQueueStore.key)
        #expect(store.load() == nil)
    }
}
