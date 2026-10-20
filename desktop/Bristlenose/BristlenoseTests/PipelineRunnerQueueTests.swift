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
/// - R22: a run the app doesn't own (a CLI run) read "Analysing" until quit.
/// - R25: a failed run was judged before its last lines had been read.
/// - R28: no test reached the sidecar lookup, so its failure path was unpinned.
@MainActor
struct PipelineRunnerQueueTests {

    /// One launch the runner asked for.
    final class Launch {
        let project: Project
        let clean: Bool
        let pid: pid_t
        let onExit: @Sendable (ProcessOutcome) -> Void
        /// The run's output, as its pipe would carry it.
        let output: AsyncStream<String>
        let lines: AsyncStream<String>.Continuation
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
            (output, lines) = AsyncStream<String>.makeStream()
        }
        /// The run ends. Its pipe closes with it unless `pipeStaysOpen`: a
        /// test then writes what was still in flight, or leaves it open as a
        /// child the run left behind would.
        func exit(_ outcome: ProcessOutcome = .exited(code: 0), groupLingers: Bool = false,
                  pipeStaysOpen: Bool = false) {
            running = false
            groupAlive = groupLingers
            onExit(outcome)
            if !pipeStaysOpen { lines.finish() }
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

        /// - Parameter lookup: where the sidecar is, when a test asks the
        ///   runner to look (R28).
        ///   - foreignPoll / patience: the watch on a run another process owns.
        ///   - endStateRead / slowEndReread: the read that settles a finished
        ///     run, and the wait before reading again when it timed out (R29).
        init(lookup: (@MainActor () -> Result<SidecarMode, SidecarResolveError>)? = nil,
             foreignPoll: Duration = .milliseconds(50), patience: Int = 15,
             endStateRead: (@Sendable (URL) async -> PipelineState)? = nil,
             slowEndReread: Duration = .milliseconds(50)) {
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
                        pid: launch.pid, isRunning: { launch.running }, output: launch.output
                    )
                },
                escalationSleep: { _ in },
                // Each run leads its own group, as Foundation makes every child.
                signalTarget: { -$0 },
                activeProvider: { [weak self] in self?.providerNow },
                noteRunSucceeded: { [weak self] in self?.noted.append($0) },
                sidecarLookup: lookup,
                outputDrainLimit: .seconds(1),
                foreignRunPollInterval: foreignPoll,
                foreignRunPatience: patience,
                endStateRead: endStateRead ?? {
                    await PipelineRunner.readManifestState(at: $0, timeout: .seconds(5))
                },
                slowEndRereadInterval: slowEndReread
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

    /// Reads of the end state, counted across the threads they run on.
    final class ReadLog: @unchecked Sendable {
        private let lock = NSLock()
        private var n = 0
        /// The number of this read, from 1.
        func next() -> Int { lock.lock(); defer { lock.unlock() }; n += 1; return n }
        var count: Int { lock.lock(); defer { lock.unlock() }; return n }
    }

    /// R29: a run that succeeded on a disk too slow for the 5 s end-state read
    /// read "Not responding" for good. The termination path accepted the
    /// timed-out read, said the next passive scan would settle it, and there
    /// is no passive scan. It is read again until it answers.
    @Test func aSuccessfulRunWhoseEndReadTimedOutIsReadAgain() async {
        let reads = ReadLog()
        // The end read and the first re-read both time out; the next answers.
        let rig = Rig(endStateRead: { url in
            if reads.next() <= 2 { return .unreachable(reason: .timedOut) }
            return await PipelineRunner.readManifestState(at: url, timeout: .seconds(5))
        })
        defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: nil)

        rig.launches[0].exit()
        await until {
            if case .ready = rig.runner.state[a.id] { return true }
            return false
        }

        guard case .ready = rig.runner.state[a.id] else {
            Issue.record("expected .ready, got \(String(describing: rig.runner.state[a.id]))"); return
        }
        #expect(reads.count == 3)
    }

    /// The second read is the row's only while the row still says the read
    /// timed out: a run started meanwhile is not overwritten by it.
    @Test func aRereadDoesNotOverwriteARunStartedMeanwhile() async {
        let reads = ReadLog()
        let rig = Rig(endStateRead: { url in
            if reads.next() == 1 { return .unreachable(reason: .timedOut) }
            return await PipelineRunner.readManifestState(at: url, timeout: .seconds(5))
        }, slowEndReread: .milliseconds(300))
        defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: nil)

        rig.launches[0].exit()
        await until { rig.runner.state[a.id] == .unreachable(reason: .timedOut) }
        #expect(rig.runner.state[a.id] == .unreachable(reason: .timedOut))
        rig.runner.start(project: a)
        #expect(rig.runner.state[a.id] == .running)

        try? await Task.sleep(for: .milliseconds(600))
        #expect(rig.runner.state[a.id] == .running)
        #expect(reads.count == 1, "nothing read the finished run again once a new one held the row")
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

        // A stopped run's row says what it left on disk, here a finished
        // report, as a reconnected run's does (R21; it was always `.idle`).
        // Stopped, it proves nothing about credit.
        #expect(rig.runner.state[a.id] == .ready(Date(timeIntervalSince1970: 1_792_490_400)))
        #expect(rig.noted.isEmpty)
    }

    @Test func aPreviousRunsCompletionIsNotThisRunsCall() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.writeFinishedRun(in: a, runId: "earlier", tokens: 120)
        rig.runner.start(project: a)

        // Exits without writing a terminus of its own; the disk still reads ready.
        rig.launches[0].exit()
        await until { rig.runner.state[a.id] != .running }

        guard case .ready = rig.runner.state[a.id] else {
            Issue.record("expected .ready, got \(String(describing: rig.runner.state[a.id]))"); return
        }
        #expect(rig.noted.isEmpty, "credited the earlier run's tokens to this one")
    }

    @Test func anAttachedRunIsNotCreditedWithThePreviousRunsTokens() async throws {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("orphan-prior-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        // The previous run finished with tokens; the attached one has not
        // written its own start yet, so that terminus is still the tail.
        Self.writeFinishedRun(at: root.path, runId: "earlier", tokens: 300)
        var noted: [LLMProvider] = []
        let (runner, _, _, url) = try await attachedOrphan(
            path: root.path, providerLine: "openai",
            noteRunSucceeded: { noted.append($0) }
        )
        defer { try? FileManager.default.removeItem(at: url) }

        // The poll reads ready (the earlier run's) and calls the run over.
        await until({ !FileManager.default.fileExists(atPath: url.path) }, seconds: 6)
        await until({ runner.state.values.contains { if case .ready = $0 { true } else { false } } }, seconds: 3)

        #expect(noted.isEmpty, "credited the earlier run's tokens to the attached one")
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

        // The run finishes: its terminus lands, and the poll reads it as ready.
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

    // MARK: - R22: a run the app doesn't own settles from disk

    /// A run another process owns, as a CLI run on a sidebar study leaves it:
    /// its own `run_started`, and Python's `run.pid` naming a live process
    /// (this one). The app has no PID file of its own for it.
    private func foreignRun(_ rig: Rig, _ name: String = "CLI",
                            pid: pid_t = getpid()) async throws -> (Project, URL) {
        let p = rig.project(name)
        let dir = URL(fileURLWithPath: p.path).appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let started = #"{"schema_version":5,"ts":"2026-10-20T09:00:00Z","event":"run_started","run_id":"cli-run","kind":"run","started_at":"2026-10-20T09:00:00Z"}"#
        try Data((started + "\n").utf8).write(to: dir.appendingPathComponent(EventLogReader.filename))
        try writePythonPID(pid, in: dir)
        rig.runner.scan(project: p)
        await until { rig.runner.state[p.id] == .running }
        try #require(rig.runner.state[p.id] == .running, "the CLI run was not read as running")
        return (p, dir)
    }

    private func writePythonPID(_ pid: pid_t, in dir: URL) throws {
        let start = EventLogReader.procStartTime(pid: pid) ?? "0.0"
        let json = #"{"pid":\#(pid),"start_time":"\#(start)","run_id":"cli-run"}"#
        try Data(json.utf8).write(to: dir.appendingPathComponent(EventLogReader.pidFilename))
    }

    private func append(_ line: String, to dir: URL) throws {
        let h = try FileHandle(forWritingTo: dir.appendingPathComponent(EventLogReader.filename))
        defer { try? h.close() }
        try h.seekToEnd()
        try h.write(contentsOf: Data((line + "\n").utf8))
    }

    @Test func aRunTheAppDoesNotOwnSettlesWhenItFinishes() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)

        try append(#"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_completed","run_id":"cli-run","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"completed","cause":null}"#, to: dir)
        await until({ rig.runner.state[p.id] != .running }, seconds: 5)

        guard case .ready = rig.runner.state[p.id] else {
            Issue.record("still \(String(describing: rig.runner.state[p.id])) after the CLI run finished")
            return
        }
        #expect(rig.launches.isEmpty)
    }

    /// The case as it is met: the CLI run is outside the app's sandbox, which
    /// refuses signal 0 to it. Another process of this user's stands in for it
    /// (`EventLogReaderTests.processOutsideTheSandbox`).
    @Test func aCLIRunOutsideTheSandboxReadsAsRunningAndThenSettles() async throws {
        let outside = try #require(await EventLogReaderTests.processOutsideTheSandbox())
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig, pid: outside)

        try append(#"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_cancelled","run_id":"cli-run","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"cancelled","cause":null}"#, to: dir)
        await until({ rig.runner.state[p.id] != .running }, seconds: 5)

        #expect(rig.runner.state[p.id] == .stopped(stagesComplete: []))
    }

    @Test func aRunTheAppDoesNotOwnThatDiedReadsAsStranded() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)

        // Killed, no terminus written: run.pid names a process that is gone.
        try writePythonPID(999_999, in: dir)
        await until({ rig.runner.state[p.id] != .running }, seconds: 5)

        #expect(rig.runner.state[p.id] == .failed(
            .keyed("desktop.pipeline.failure.stranded"), category: .unknown))
    }

    @Test func aRunTheAppDoesNotOwnStaysRunningWhileItRuns() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, _) = try await foreignRun(rig)

        try? await Task.sleep(for: .milliseconds(400))  // several polls

        #expect(rig.runner.state[p.id] == .running)
    }

    /// The passive rescan half: a scan after the run ended settles it too.
    /// The watch is slowed right down, so only the rescan can.
    @Test func aRescanSettlesARunTheAppDoesNotOwn() async throws {
        let rig = Rig(foreignPoll: .seconds(60)); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)
        try writePythonPID(999_999, in: dir)

        rig.runner.scan(project: p)
        await until({ rig.runner.state[p.id] != .running }, seconds: 2)

        #expect(rig.runner.state[p.id] != .running)
    }

    /// A long run's progress lines push its `run_started` far back in the log:
    /// past the first 64 KB the reader looks at, it read as never started.
    @Test func aLongRunsProgressDoesNotEndItsWatch() async throws {
        // Short patience: a run_started not found reads "can't tell", which
        // would settle the row within the wait below.
        let rig = Rig(patience: 2); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)
        let pad = String(repeating: "x", count: 300)
        let progress = (0..<400).map { i in
            #"{"schema_version":5,"ts":"2026-10-20T09:00:00Z","event":"run_progress","run_id":"cli-run","kind":"run","started_at":"2026-10-20T09:00:00Z","stage":"transcribe","sessions_complete":\#(i),"note":"\#(pad)"}"#
        }
        try append(progress.joined(separator: "\n"), to: dir)
        let size = try FileManager.default.attributesOfItem(
            atPath: dir.appendingPathComponent(EventLogReader.filename).path)[.size] as? Int ?? 0
        try #require(size > 65_536 * 2, "the progress does not reach past the first window")

        try? await Task.sleep(for: .milliseconds(400))
        #expect(rig.runner.state[p.id] == .running, "a live run read as over")

        try append(#"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_completed","run_id":"cli-run","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"completed","cause":null}"#, to: dir)
        await until({ rig.runner.state[p.id] != .running }, seconds: 5)
        guard case .ready = rig.runner.state[p.id] else {
            Issue.record("\(String(describing: rig.runner.state[p.id])) after the run finished")
            return
        }
    }

    /// A read that can't tell (`run.pid` torn mid-write) is not an end, and
    /// the watch outlives it.
    @Test func aReadThatCannotTellDoesNotEndTheRun() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)
        let pidURL = dir.appendingPathComponent(EventLogReader.pidFilename)
        try Data("{\"pid\":".utf8).write(to: pidURL)

        try? await Task.sleep(for: .milliseconds(300))   // ~6 polls, under the patience
        #expect(rig.runner.state[p.id] == .running, "a torn read ended a live run")

        try writePythonPID(getpid(), in: dir)
        try append(#"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_cancelled","run_id":"cli-run","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"cancelled","cause":null}"#, to: dir)
        await until({ rig.runner.state[p.id] != .running }, seconds: 5)
        #expect(rig.runner.state[p.id] == .stopped(stagesComplete: []), "the watch did not outlive the torn read")
    }

    /// A `run.pid` gone for good (its run killed before writing one, say) is
    /// waited out, not watched for ever.
    @Test func aRunThatNeverSaysIsSettledAfterThePatienceRunsOut() async throws {
        let rig = Rig(patience: 4); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)
        try FileManager.default.removeItem(at: dir.appendingPathComponent(EventLogReader.pidFilename))

        await until({ rig.runner.state[p.id] != .running }, seconds: 5)

        #expect(rig.runner.state[p.id] == .failed(
            .keyed("desktop.pipeline.failure.stranded"), category: .unknown))
    }

    /// Stop on a run the app can't signal sends nothing, so it must not read
    /// "Stopping…", even over progress an earlier run of ours left.
    @Test func stopOnARunTheAppDoesNotOwnClaimsNothing() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, _) = try await foreignRun(rig)
        rig.runner.liveData.setProgress(PipelineProgress(startedAt: Date()), for: p.id)

        rig.runner.cancel(project: p)

        #expect(rig.runner.liveData.progress[p.id]?.isStopping == false)
        #expect(rig.signals.isEmpty)
        #expect(rig.runner.state[p.id] == .running)
    }

    /// Analyse over a CLI run would only fail ("another run is in progress")
    /// and pin that failure over the CLI run's own end.
    @Test func analyseOverARunTheAppDoesNotOwnStartsNothing() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, _) = try await foreignRun(rig)

        rig.runner.start(project: p)

        #expect(rig.launches.isEmpty)
        #expect(rig.runner.state[p.id] == .running)
    }

    /// The app's own run keeps "Analysing" through a rescan, whatever disk says.
    @Test func aRescanLeavesTheAppsOwnRunRunning() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        try? FileManager.default.removeItem(at: PipelineRunner.pidFileURL(for: a))

        rig.runner.scan(project: a)
        try? await Task.sleep(for: .milliseconds(300))

        #expect(rig.runner.state[a.id] == .running)
    }

    // MARK: - R25: a failed run is judged on all of its output

    @Test func aFailureIsJudgedOnLinesStillInThePipeAtExit() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)

        let run = rig.launches[0]
        run.exit(.exited(code: 1), pipeStaysOpen: true)
        // The termination handler gets there first; the traceback is still
        // being handed over.
        try? await Task.sleep(for: .milliseconds(100))
        run.lines.yield("Traceback (most recent call last):")
        run.lines.yield("openai.RateLimitError: Error code: 429 - rate limit reached")
        run.lines.finish()
        await until({ if case .failed = rig.runner.state[a.id] { return true }; return false }, seconds: 3)

        guard case .failed(_, let category) = rig.runner.state[a.id] else {
            Issue.record("not failed: \(String(describing: rig.runner.state[a.id]))")
            return
        }
        #expect(category == .quota, "judged before the traceback was read")
        let log = URL(fileURLWithPath: a.path)
            .appendingPathComponent("bristlenose-output/.bristlenose/last-run-failure.log")
        #expect((try? String(contentsOf: log, encoding: .utf8))?.contains("429") == true)
    }

    /// A child the run left behind can hold the pipe open: the verdict waits a
    /// bounded time, then the queue moves on.
    @Test func aPipeLeftOpenDelaysTheVerdictOnlySoLong() async {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B")
        rig.runner.start(project: a)
        rig.runner.start(project: b)

        rig.launches[0].exit(.exited(code: 1), pipeStaysOpen: true)
        await until({ rig.launches.count == 2 }, seconds: 3)

        #expect(rig.launches.count == 2, "the queue waited on a pipe that never closed")
        if case .failed = rig.runner.state[a.id] {} else {
            Issue.record("A is \(String(describing: rig.runner.state[a.id]))")
        }
    }

    // MARK: - R28: a failed sidecar lookup moves the queue on

    @Test func aFailedSidecarLookupFailsThatStudyAndTheNextOneRuns() async {
        var lookups = 0
        let rig = Rig(lookup: {
            lookups += 1
            return lookups == 2
                ? .failure(.bundledSidecarMissing(expectedPath: "/nowhere/bristlenose-sidecar"))
                : .success(.bundled(path: URL(fileURLWithPath: "/nowhere/bristlenose-sidecar")))
        })
        defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B"), c = rig.project("C")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        rig.runner.start(project: c)

        rig.launches[0].exit()
        await until { rig.launches.count == 2 }

        #expect(lookups == 3, "the lookup was never asked")
        #expect(rig.launches.map(\.project.name) == ["A", "C"])
        if case .failed(_, .unknown) = rig.runner.state[b.id] {} else {
            Issue.record("B is \(String(describing: rig.runner.state[b.id]))")
        }
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
