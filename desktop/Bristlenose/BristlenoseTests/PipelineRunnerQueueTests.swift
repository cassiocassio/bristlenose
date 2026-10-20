import AppKit
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
        /// Liveness probes (signal 0) the ladder has made: one before each
        /// step and one after SIGKILL, so a finished ladder has made three.
        var probes = 0
        let center = NotificationCenter()
        /// The provider a run would be spawned with now.
        var providerNow: LLMProvider? = .claude
        /// Providers whose out-of-credit verdict a finished run cleared.
        var noted: [LLMProvider] = []
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
                notificationCenter: center,
                sendSignal: { [weak self] pid, sig in
                    guard let self else { return ESRCH }
                    let launch = self.launches.first(where: { $0.pid == pid || -$0.pid == pid })
                    // Signal 0 is a liveness probe of the group, not a signal.
                    if sig == 0 {
                        self.probes += 1
                        return launch?.groupAlive == true ? 0 : ESRCH
                    }
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
                    return PipelineRunner.LaunchedRun(
                        pid: launch.pid, isRunning: { launch.running }
                    )
                },
                escalationSleep: { _ in },
                // Each run leads its own group, as Foundation makes every child.
                signalTarget: { -$0 },
                activeProvider: { [weak self] in self?.providerNow },
                noteRunSucceeded: { [weak self] in self?.noted.append($0) }
            )
            runner.setProjectIndex(index)
        }

        func project(_ name: String) -> Project {
            let dir = root.appendingPathComponent(name)
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            return index.addProject(name: name, path: dir.path)
        }

        /// What a run that finished leaves on disk: a manifest with render
        /// complete, and its own `run_completed`, with token totals when it
        /// called an LLM.
        func writeFinishedRun(in project: Project, runId: String = "run-1", tokens: Int?) {
            PipelineRunnerQueueTests.writeFinishedRun(at: project.path, runId: runId, tokens: tokens)
        }

        func cleanUp() {
            for launch in launches {
                try? FileManager.default.removeItem(at: PipelineRunner.pidFileURL(for: launch.project))
            }
            try? FileManager.default.removeItem(at: root)
        }
    }

    static func writeFinishedRun(at path: String, runId: String, tokens: Int?) {
        let dir = URL(fileURLWithPath: path)
            .appendingPathComponent("bristlenose-output/.bristlenose")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let manifest = #"{"stages":{"render":{"status":"complete","completed_at":"2026-10-20T10:00:00+00:00"}}}"#
        try? Data(manifest.utf8).write(to: dir.appendingPathComponent("pipeline-manifest.json"))
        let usage = tokens.map { #","input_tokens":\#($0),"output_tokens":7"# } ?? ""
        let lines = [
            #"{"schema_version":5,"ts":"2026-10-20T09:00:00Z","event":"run_started","run_id":"\#(runId)","kind":"run","started_at":"2026-10-20T09:00:00Z"}"#,
            #"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_completed","run_id":"\#(runId)","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"completed","cause":null\#(usage)}"#,
        ]
        try? Data((lines.joined(separator: "\n") + "\n").utf8)
            .write(to: dir.appendingPathComponent(EventLogReader.filename))
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
        // The ladder's first probe found the group gone, and it stopped there.
        await until { rig.probes >= 1 }

        #expect(rig.probes == 1)
        #expect(rig.signals.map(\.sig) == [SIGINT])
    }

    @Test func aSecondStopAddsNoSecondLadder() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)

        rig.runner.cancel(project: a)
        rig.runner.cancel(project: a)
        // A second ladder would start with a second SIGINT, sent at once.
        #expect(rig.signals.map(\.sig) == [SIGINT])
        // The ladder has finished: its probe after SIGKILL has been made.
        await until { rig.probes >= 3 }

        #expect(rig.probes == 3)
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

    // MARK: - Quit and attached orphans signal the group too

    @Test func quitSignalsTheOwnedRunsGroup() {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)

        rig.center.post(name: NSApplication.willTerminateNotification, object: nil)

        #expect(rig.signals.map(\.pid) == [-rig.launches[0].pid])
        #expect(rig.signals.map(\.sig) == [SIGINT])
    }

    /// An orphan attached the way a relaunch attaches one — this test process,
    /// recorded as a spawn records it — whose group the seam says it leads.
    /// Every signal goes through the recorder, so none reaches this process.
    private func attachedOrphan(
        path: String? = nil, providerLine: String? = nil,
        noteRunSucceeded: @escaping @MainActor (LLMProvider) -> Void = { _ in }
    ) async throws -> (PipelineRunner, Project, SignalRecorder, URL) {
        let recorder = SignalRecorder()
        let runner = PipelineRunner(
            notificationCenter: NotificationCenter(),
            sendSignal: { pid, sig in
                if sig == 0 {
                    recorder.probes += 1
                    let alive = pid < 0 ? recorder.groupAlive : recorder.leaderAlive
                    return alive ? 0 : ESRCH
                }
                recorder.sent.append((pid, sig))
                return 0
            },
            escalationSleep: { _ in },
            signalTarget: { $0 == getpid() ? -$0 : $0 },
            noteRunSucceeded: noteRunSucceeded
        )
        let p = Project(id: UUID(), name: "Orphan", path: path ?? "/p/orphan-\(UUID().uuidString)")
        let url = PipelineRunner.pidFileURL(for: p)
        try FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let start = try #require(EventLogReader.procStartTime(pid: getpid()))
        try Data("\(getpid())\n\(start)\n\(providerLine ?? "")".utf8).write(to: url, options: .atomic)
        runner.scan(project: p)
        await until { runner.state[p.id] == .running }
        try #require(runner.state[p.id] == .running, "the orphan was not attached")
        return (runner, p, recorder, url)
    }

    final class SignalRecorder {
        var sent: [(pid: pid_t, sig: Int32)] = []
        var probes = 0
        var groupAlive = true
        var leaderAlive = true
    }

    @Test func stopOnAnAttachedOrphanEscalatesOnItsGroup() async throws {
        let (runner, p, recorder, url) = try await attachedOrphan()
        defer { try? FileManager.default.removeItem(at: url) }

        runner.cancel(project: p)
        await until { recorder.probes >= 3 }

        #expect(recorder.sent.map(\.sig) == [SIGINT, SIGTERM, SIGKILL])
        #expect(recorder.sent.allSatisfy { $0.pid == -getpid() })
    }

    @Test func aLadderOnAnOrphanEndsWhenItsGroupIsGone() async throws {
        let (runner, p, recorder, url) = try await attachedOrphan()
        defer { try? FileManager.default.removeItem(at: url) }
        recorder.groupAlive = false

        runner.cancel(project: p)
        await until { recorder.probes >= 1 }

        #expect(recorder.sent.map(\.sig) == [SIGINT])
    }

    @Test func aWorkerTheOrphanLeftBehindStillGetsTheLadder() async throws {
        let (runner, p, recorder, url) = try await attachedOrphan()
        defer { try? FileManager.default.removeItem(at: url) }
        recorder.leaderAlive = false

        runner.cancel(project: p)
        await until { recorder.probes >= 3 }

        #expect(recorder.sent.map(\.sig) == [SIGINT, SIGTERM, SIGKILL])
    }

    @Test func quitSignalsAnAttachedOrphansGroup() async throws {
        let (runner, _, recorder, url) = try await attachedOrphan()
        defer { try? FileManager.default.removeItem(at: url) }

        runner.stopAllForQuit()

        #expect(recorder.sent.map(\.pid) == [-getpid()])
        #expect(recorder.sent.map(\.sig) == [SIGINT])
    }

    // MARK: - R40: a finished run clears its own provider's credit verdict

    @Test func aRunThatCalledAnLLMClearsTheProviderItWasSpawnedWith() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.providerNow = .chatGPT  // switched while the run went on
        rig.writeFinishedRun(in: a, tokens: 120)

        rig.launches[0].exit()
        await until { rig.runner.state[a.id] != .running }

        guard case .ready = rig.runner.state[a.id] else {
            Issue.record("expected .ready, got \(String(describing: rig.runner.state[a.id]))"); return
        }
        #expect(rig.noted == [.claude])
    }

    @Test func aRunFinishedFromCacheClearsNothing() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: nil)

        rig.launches[0].exit()
        await until { rig.runner.state[a.id] != .running }

        guard case .ready = rig.runner.state[a.id] else {
            Issue.record("expected .ready, got \(String(describing: rig.runner.state[a.id]))"); return
        }
        #expect(rig.noted.isEmpty)
    }

    @Test func aRunThatDidNotFinishClearsNothing() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: 120)

        rig.runner.cancel(project: a)
        rig.launches[0].exit(.exited(code: 130))
        await until { rig.runner.state[a.id] != .running }

        #expect(rig.runner.state[a.id] == .idle)
        #expect(rig.noted.isEmpty)
    }

    @Test func theRecordedProviderIsTheThirdLineOfThePIDFile() {
        #expect(PipelineRunner.recordedProvider(pidFileContents: "42\n1.2\nopenai") == .chatGPT)
        #expect(PipelineRunner.recordedProvider(pidFileContents: "42\n1.2\n") == nil)
        #expect(PipelineRunner.recordedProvider(pidFileContents: "42\n1.2") == nil, "a file from before")
    }

    @Test func onlyThisRunsCompletionWithTokensCounts() {
        func event(_ kind: String, _ id: String, _ tokens: Int?) -> EventLogReader.Event? {
            let usage = tokens.map { #","input_tokens":\#($0)"# } ?? ""
            let json = #"{"event":"\#(kind)","kind":"run","run_id":"\#(id)","started_at":"x"\#(usage)}"#
            return try? JSONDecoder().decode(EventLogReader.Event.self, from: Data(json.utf8))
        }
        #expect(PipelineRunner.runUsedAnLLM(terminus: event("run_completed", "new", 5), priorRunId: "old"))
        #expect(!PipelineRunner.runUsedAnLLM(terminus: event("run_completed", "old", 5), priorRunId: "old"))
        #expect(!PipelineRunner.runUsedAnLLM(terminus: event("run_completed", "new", nil), priorRunId: nil))
        #expect(!PipelineRunner.runUsedAnLLM(terminus: event("run_cancelled", "new", 5), priorRunId: nil))
        #expect(!PipelineRunner.runUsedAnLLM(terminus: nil, priorRunId: nil))
    }

    @Test func anAttachedRunThatFinishesClearsTheProviderItRecorded() async throws {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("orphan-r40-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        var noted: [LLMProvider] = []
        let (runner, p, _, url) = try await attachedOrphan(
            path: root.path, providerLine: "openai",
            noteRunSucceeded: { noted.append($0) }
        )
        defer { try? FileManager.default.removeItem(at: url) }

        // The run finishes: its poll reads the manifest as ready.
        Self.writeFinishedRun(at: root.path, runId: "orphan-run", tokens: 300)
        await until({ !noted.isEmpty }, seconds: 8)

        #expect(noted == [.chatGPT])
        _ = (runner, p)
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
