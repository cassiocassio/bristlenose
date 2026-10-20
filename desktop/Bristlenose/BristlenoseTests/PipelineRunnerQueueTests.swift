import Foundation
import Testing
@testable import Bristlenose

/// The run slot, the queue behind it, and Stop, driven through the real
/// `PipelineRunner` with a launcher that starts nothing (20 Oct 2026).
///
/// - R18: Re-analyse while another study ran queued the id alone, so the
///   queued run went without `--clean`, resumed, and ended "ready" on the old
///   report.
/// - R20: Stop on the app's own run sent SIGINT and nothing more, so a run in
///   a long transcription call sat on "Stopping…" for minutes.
/// - R23: the slot was freed before a finished run's end state was read, so a
///   study started in that moment took it, and the finished one stayed
///   "Analysing" for good.
/// - R63: Analyse ran against a folder that was no longer there.
@MainActor
struct PipelineRunnerQueueTests {

    /// One launch the runner asked for.
    final class Launch {
        let project: Project
        let clean: Bool
        let pid: pid_t
        let onExit: @Sendable (ProcessOutcome) -> Void
        var running = true
        /// Whether anything in the run's process group is still alive — the
        /// run itself, or a worker it left behind.
        var groupAlive = true
        init(project: Project, clean: Bool, pid: pid_t,
             onExit: @escaping @Sendable (ProcessOutcome) -> Void) {
            self.project = project
            self.clean = clean
            self.pid = pid
            self.onExit = onExit
        }
        func exit(_ outcome: ProcessOutcome = .exited(code: 0), groupLingers: Bool = false) {
            running = false
            groupAlive = groupLingers
            onExit(outcome)
        }
    }

    @MainActor
    final class Rig {
        var launches: [Launch] = []
        var signals: [(pid: pid_t, sig: Int32)] = []
        /// What a run does when it gets a signal: by default nothing (a run
        /// wedged in a C call).
        var onSignal: (Launch, Int32) -> Void = { _, _ in }
        /// The errno each signal returns; 0 unless a test says otherwise.
        var signalResult: (Int32) -> Int32 = { _ in 0 }
        let root: URL
        let index: ProjectIndex
        var runner: PipelineRunner!
        // Above any pid macOS hands out, so no signal can reach a real process.
        private var nextPID: pid_t = 900_000

        init() {
            root = URL(fileURLWithPath: NSTemporaryDirectory())
                .appendingPathComponent("runner-queue-\(UUID().uuidString)")
            try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
            index = ProjectIndex(fileURL: root.appendingPathComponent("projects.json"))
            runner = PipelineRunner(
                notificationCenter: NotificationCenter(),
                sendSignal: { [weak self] pid, sig in
                    guard let self else { return ESRCH }
                    let launch = self.launches.first(where: { $0.pid == pid || -$0.pid == pid })
                    // Signal 0 is a liveness probe of the group, not a signal.
                    if sig == 0 { return launch?.groupAlive == true ? 0 : ESRCH }
                    self.signals.append((pid, sig))
                    let err = self.signalResult(sig)
                    if err == 0, let launch { self.onSignal(launch, sig) }
                    return err
                },
                hasConsent: { true },
                keyReadiness: { .keyless(provider: "local") },
                launcher: { [weak self] project, clean, onExit in
                    guard let self else { throw CancellationError() }
                    self.nextPID += 1
                    let launch = Launch(project: project, clean: clean, pid: self.nextPID, onExit: onExit)
                    self.launches.append(launch)
                    // A group leader, as Foundation makes every child.
                    return PipelineRunner.LaunchedRun(
                        pid: launch.pid, isRunning: { launch.running }, processGroup: launch.pid
                    )
                },
                escalationSleep: { _ in }
            )
            runner.setProjectIndex(index)
        }

        func project(_ name: String) -> Project {
            let dir = root.appendingPathComponent(name)
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            return index.addProject(name: name, path: dir.path)
        }

        func cleanUp() {
            for launch in launches {
                try? FileManager.default.removeItem(at: PipelineRunner.pidFileURL(for: launch.project))
            }
            try? FileManager.default.removeItem(at: root)
        }
    }

    private func until(_ condition: () -> Bool, seconds: Double = 3) async {
        let deadline = Date().addingTimeInterval(seconds)
        while !condition(), Date() < deadline {
            try? await Task.sleep(for: .milliseconds(10))
        }
    }

    // MARK: - R18

    @Test func reAnalyseQueuedBehindAnotherRunRunsClean() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B")
        rig.runner.start(project: a)
        rig.runner.start(project: b, clean: true)
        #expect(rig.runner.state[b.id] == .queued(position: 1))

        rig.launches[0].exit()
        await until { rig.launches.count == 2 }

        #expect(rig.launches.count == 2, "B was never started")
        #expect(rig.launches.last?.project.id == b.id)
        #expect(rig.launches.last?.clean == true, "the queued Re-analyse lost --clean")
    }

    @Test func reAnalyseOfAStudyAlreadyQueuedIsKeptAndNeverUndone() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B"), c = rig.project("C")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.start(project: c)
        rig.runner.start(project: b, clean: true)
        rig.runner.start(project: b)
        #expect(rig.runner.state[b.id] == .queued(position: 1), "B kept its place")

        rig.launches[0].exit()
        await until { rig.launches.count == 2 }

        #expect(rig.launches.last?.project.id == b.id)
        #expect(rig.launches.last?.clean == true)
    }

    // MARK: - R23

    @Test func aRunFinishingAsAnotherStartsSettlesAndTheQueueKeepsItsOrder() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B"), c = rig.project("C")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        let pidFile = PipelineRunner.pidFileURL(for: a)
        try #require(FileManager.default.fileExists(atPath: pidFile.path), "no PID file to gate on")

        rig.launches[0].exit()
        // The termination handler removes the PID file and then awaits the
        // end-state read. Hold here until it has done the first, so the start
        // below lands inside the await.
        for _ in 0..<1000 where FileManager.default.fileExists(atPath: pidFile.path) {
            await Task.yield()
        }
        try #require(!FileManager.default.fileExists(atPath: pidFile.path), "the exit was never handled")
        try #require(rig.runner.state[a.id] == .running, "A resolved before C could be started")

        rig.runner.start(project: c)
        await until { rig.runner.state[a.id] != .running && rig.launches.count >= 2 }

        #expect(rig.runner.state[a.id] == .idle, "A was left \(String(describing: rig.runner.state[a.id]))")
        #expect(rig.launches.map(\.project.name) == ["A", "B"], "B was queued first")
        #expect(rig.runner.state[c.id] == .queued(position: 1))
    }

    @Test func startingTheStudyThatIsFinishingRunsItAgainAfter() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        let pidFile = PipelineRunner.pidFileURL(for: a)
        try #require(FileManager.default.fileExists(atPath: pidFile.path), "no PID file to gate on")

        rig.launches[0].exit()
        for _ in 0..<1000 where FileManager.default.fileExists(atPath: pidFile.path) {
            await Task.yield()
        }
        try #require(rig.runner.state[a.id] == .running)

        // A drop onto A in its last moment.
        rig.runner.start(project: a)
        #expect(rig.launches.count == 1, "the start spawned over the run still being resolved")
        await until { rig.launches.count == 2 }

        #expect(rig.launches.count == 2, "the second Analyse of A was dropped")
        #expect(rig.runner.state[a.id] == .running)
    }

    // MARK: - R20

    @Test func stopOnAWedgedRunEscalatesToKill() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        let pid = rig.launches[0].pid

        rig.runner.cancel(project: a)
        await until { rig.signals.count >= 3 }

        #expect(rig.signals.map(\.sig) == [SIGINT, SIGTERM, SIGKILL])
        #expect(rig.signals.allSatisfy { $0.pid == -pid }, "Stop goes to the run's process group")
    }

    @Test func stopThatTakesSendsNothingMore() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.onSignal = { launch, sig in
            if sig == SIGINT { launch.running = false; launch.groupAlive = false }
        }
        rig.runner.start(project: a)

        rig.runner.cancel(project: a)
        await until({ rig.signals.count > 1 }, seconds: 0.3)

        #expect(rig.signals.map(\.sig) == [SIGINT])
    }

    @Test func aSecondStopAddsNoSecondLadder() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)

        rig.runner.cancel(project: a)
        rig.runner.cancel(project: a)
        // The whole ladder first, then long enough for a second one to show.
        await until { rig.signals.count >= 3 }
        await until({ rig.signals.count > 3 }, seconds: 0.3)

        #expect(rig.signals.map(\.sig) == [SIGINT, SIGTERM, SIGKILL])
    }

    @Test func aKilledRunEndsTheStopAndTheQueueMovesOn() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B")
        rig.onSignal = { launch, sig in
            if sig == SIGKILL { launch.exit(.signalled(signal: SIGKILL)) }
        }
        rig.runner.start(project: a)
        rig.runner.start(project: b)

        rig.runner.cancel(project: a)
        await until { rig.launches.count == 2 }

        #expect(rig.runner.state[a.id] == .idle)
        #expect(rig.launches.last?.project.id == b.id)
    }

    @Test func aWorkerLeftBehindByTheRunStillGetsTheLadder() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.onSignal = { launch, sig in
            if sig == SIGINT { launch.exit(.exited(code: 130), groupLingers: true) }
            if sig == SIGKILL { launch.groupAlive = false }
        }
        rig.runner.start(project: a)

        rig.runner.cancel(project: a)
        await until { rig.signals.count >= 3 }

        #expect(rig.signals.map(\.sig) == [SIGINT, SIGTERM, SIGKILL])
    }

    @Test func aStopWhoseSignalFailedCanBeTriedAgain() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.signalResult = { _ in EPERM }
        rig.runner.start(project: a)

        rig.runner.cancel(project: a)
        rig.signalResult = { _ in 0 }
        rig.runner.cancel(project: a)
        await until { rig.signals.count >= 4 }

        #expect(rig.signals.map(\.sig) == [SIGINT, SIGINT, SIGTERM, SIGKILL])
    }

    @Test func stopOnAStudyQueuedBehindItsOwnFinishingRunTakesItOut() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        let pidFile = PipelineRunner.pidFileURL(for: a)
        try #require(FileManager.default.fileExists(atPath: pidFile.path))

        rig.launches[0].exit()
        for _ in 0..<1000 where FileManager.default.fileExists(atPath: pidFile.path) {
            await Task.yield()
        }
        try #require(rig.runner.state[a.id] == .running)
        rig.runner.start(project: a)
        rig.runner.cancel(project: a)
        await until({ rig.runner.state[a.id] != .running && rig.launches.count > 1 }, seconds: 1)

        #expect(rig.launches.count == 1, "the run Stop took out of the queue started anyway")
        #expect(rig.runner.state[a.id] == .idle)
    }

    @Test func aStudyRemovedWhileQueuedDoesNotBlockTheQueue() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B"), c = rig.project("C")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.start(project: c)
        rig.index.removeProject(id: b.id)

        rig.launches[0].exit()
        await until { rig.launches.count == 2 }

        #expect(rig.launches.map(\.project.name) == ["A", "C"])
    }

    // MARK: - R63

    @Test func aStudyWhoseFolderIsGoneIsNotRun() {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        try? FileManager.default.removeItem(atPath: a.path)

        rig.runner.start(project: a)

        #expect(rig.launches.isEmpty, "a run was started against a missing folder")
        #expect(rig.runner.state[a.id] == .unreachable(reason: .folderMissing))
    }

    @Test func aQueuedStudyWhoseFolderWentIsSkipped() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B"), c = rig.project("C")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.start(project: c)
        try? FileManager.default.removeItem(atPath: b.path)

        rig.launches[0].exit()
        await until { rig.launches.count == 2 }

        #expect(rig.launches.map(\.project.name) == ["A", "C"])
        #expect(rig.runner.state[b.id] == .unreachable(reason: .folderMissing))
    }

    // MARK: - The pure parts

    @Test func theQueueKeepsOrderAndCleanIsSticky() {
        let a = UUID(), b = UUID()
        var q = RunQueue()
        q.enqueue(a, clean: false)
        q.enqueue(b, clean: false)
        q.enqueue(a, clean: true)
        q.enqueue(a, clean: false)
        #expect(q.ids == [a, b])
        #expect(q.entries.first == .init(id: a, clean: true))
        let first = q.popFirst()
        q.pushFront(first!)
        #expect(q.entries.first == .init(id: a, clean: true), "re-inserted as it was")
        let removed = q.remove(b), removedAgain = q.remove(b)
        #expect(removed)
        #expect(!removedAgain)
        #expect(q.ids == [a])
    }

    @Test func stopSignalsTheRunsOwnGroupAndNeverTheApps() {
        #expect(PipelineRunner.ownedSignalTarget(pid: 500, processGroup: 500, ownGroup: 42) == -500)
        #expect(PipelineRunner.ownedSignalTarget(pid: 500, processGroup: 42, ownGroup: 42) == 500)
        #expect(PipelineRunner.ownedSignalTarget(pid: 500, processGroup: -1, ownGroup: 42) == 500)
        #expect(PipelineRunner.ownedSignalTarget(pid: 42, processGroup: 42, ownGroup: 42) == 42)
    }
}
