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
        /// Whether the AI disclosure has been acknowledged.
        var consented = true
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
        ///   - manifestRead / endStateTimeout / slowEndReread: the read that
        ///     settles a run's end, how long it may take, and the wait before
        ///     reading again when it timed out (R29).
        ///   - drainLimit: how long a failed run's verdict waits for its output.
        init(lookup: (@MainActor () -> Result<SidecarMode, SidecarResolveError>)? = nil,
             foreignPoll: Duration = .milliseconds(50), patience: Int = 15,
             manifestRead: (@Sendable (URL) async -> PipelineState)? = nil,
             endStateTimeout: Duration = .seconds(5),
             slowEndReread: Duration = .milliseconds(50),
             drainLimit: Duration = .seconds(1),
             escalationSleep: @escaping @Sendable (Duration) async -> Void = { _ in }) {
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
                hasConsent: { [weak self] in self?.consented ?? true },
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
                escalationSleep: escalationSleep,
                // Each run leads its own group, as Foundation makes every child.
                signalTarget: { -$0 },
                activeProvider: { [weak self] in self?.providerNow },
                noteRunSucceeded: { [weak self] in self?.noted.append($0) },
                sidecarLookup: lookup,
                outputDrainLimit: drainLimit,
                foreignRunPollInterval: foreignPoll,
                foreignRunPatience: patience,
                manifestRead: manifestRead ?? { await PipelineRunner.parseManifest(at: $0) },
                endStateTimeout: endStateTimeout,
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

    /// How long a wait for something that must happen may take. Every step
    /// the runner takes is a main-actor hop, and the full suite runs hundreds
    /// of main-actor tests beside these: on a 4-core guest the main actor was
    /// held for seconds at a time, and 3 s ceilings failed 30 tests together
    /// (20 Oct 2026, guest matrix). A green wait returns as soon as its
    /// condition holds, so the ceiling costs nothing unless the test is red.
    static let patience: Double = 30

    private func until(_ condition: () -> Bool, seconds: Double = patience) async {
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

    /// The backstop ends a stopping run 20 s in (`os._exit`, which takes none
    /// of its children); the next run starts at once and moves `generation`.
    /// SIGKILL at +30 s must still reach what the stopped run left behind.
    @Test func aWorkerLeftBehindIsStillKilledOnceTheNextRunHasStarted() async {
        let gate = LadderGate()
        let rig = Rig(escalationSleep: { _ in await gate.wait() }); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B")
        rig.onSignal = { launch, sig in
            if sig == SIGINT { launch.exit(.exited(code: 130), groupLingers: true) }
            if sig == SIGKILL { launch.groupAlive = false }
        }
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        let pidA = rig.launches[0].pid

        rig.runner.cancel(project: a)
        await until { rig.launches.count == 2 }
        #expect(rig.launches.count == 2, "B never started, so the generation never moved")
        await gate.open()
        await until { rig.signals.contains { $0.pid == -pidA && $0.sig == SIGKILL } }

        #expect(rig.signals.filter { $0.pid == -pidA }.map(\.sig) == [SIGINT, SIGTERM, SIGKILL])
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
        // The state settles in the same turn as the queue moves on, so once
        // it is not running, whether anything started is decided.
        await until { rig.runner.state[a.id] != .running }

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
        noteRunSucceeded: @escaping @MainActor (LLMProvider) -> Void = { _ in },
        manifestRead: @escaping @Sendable (URL) async -> PipelineState = {
            await PipelineRunner.parseManifest(at: $0)
        },
        endStateTimeout: Duration = .seconds(5),
        pollInterval: Duration = .seconds(2)
    ) async throws -> (PipelineRunner, Project, SignalRecorder, URL) {
        let recorder = SignalRecorder()
        let runner = PipelineRunner(
            notificationCenter: NotificationCenter(),
            sendSignal: { pid, sig in
                if sig == 0 {
                    // The ladder probes the group; the poll probes the run.
                    if pid < 0 { recorder.probes += 1 } else { recorder.leaderProbes += 1 }
                    let alive = pid < 0 ? recorder.groupAlive : recorder.leaderAlive
                    return alive ? 0 : ESRCH
                }
                recorder.sent.append((pid, sig))
                return sig == SIGINT ? recorder.sigintResult : 0
            },
            escalationSleep: { _ in },
            signalTarget: { $0 == getpid() ? -$0 : $0 },
            noteRunSucceeded: noteRunSucceeded,
            manifestRead: manifestRead,
            endStateTimeout: endStateTimeout,
            slowEndRereadInterval: .milliseconds(50),
            orphanPollInterval: pollInterval
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
        /// The ladder's probes of the run's group.
        var probes = 0
        /// The poll's probes of the run itself.
        var leaderProbes = 0
        var groupAlive = true
        var leaderAlive = true
        /// What Stop's SIGINT returns: ESRCH for a run already gone.
        var sigintResult: Int32 = 0
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

    /// A disk whose first `slow` reads of the manifest each take `delay`.
    static func slowDisk(_ reads: ReadLog, slow: Int, delay: Duration = .milliseconds(150))
        -> @Sendable (URL) async -> PipelineState {
        { url in
            if reads.next() <= slow { try? await Task.sleep(for: delay) }
            return await PipelineRunner.parseManifest(at: url)
        }
    }

    /// Where an attached run's PID file is, once the test knows.
    final class PIDFileBox: @unchecked Sendable {
        private let lock = NSLock()
        private var stored: URL?
        var url: URL? {
            get { lock.withLock { stored } }
            set { lock.withLock { stored = newValue } }
        }
    }

    /// A disk whose first read after an attached run has ended (its PID file
    /// gone: the end read) takes `delay`. The poll's reads before the end stay
    /// quick, and only reads after the end are counted in `endReads`.
    static func slowAtEnd(_ endReads: ReadLog, pidFile: PIDFileBox,
                          delay: Duration = .milliseconds(150))
        -> @Sendable (URL) async -> PipelineState {
        { url in
            if let f = pidFile.url, !FileManager.default.fileExists(atPath: f.path),
               endReads.next() <= 1 {
                try? await Task.sleep(for: delay)
            }
            return await PipelineRunner.parseManifest(at: url)
        }
    }

    /// R29: a run that succeeded on a disk too slow for the end-state read
    /// read "Not responding" for good. The termination path accepted the
    /// timed-out read, said the next passive scan would settle it, and there
    /// is no passive scan. It is read again, and a read slower than the wait
    /// is waited on again rather than thrown away, so a share that is always
    /// slower than the timeout still settles.
    @Test func aSuccessfulRunWhoseEndReadTimedOutIsReadAgain() async {
        let reads = ReadLog()
        // The end read is slower than every wait: the re-read waits on it.
        let rig = Rig(manifestRead: Self.slowDisk(reads, slow: 2),
                      endStateTimeout: .milliseconds(50))
        defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: 120)

        rig.launches[0].exit()
        await until {
            if case .ready = rig.runner.state[a.id] { return true }
            return false
        }

        guard case .ready = rig.runner.state[a.id] else {
            Issue.record("expected .ready, got \(String(describing: rig.runner.state[a.id]))"); return
        }
        // The run made an LLM call: as on the termination path, its provider's
        // out-of-credit verdict goes.
        #expect(rig.noted == [.claude])
        try? await Task.sleep(for: .milliseconds(300))
        #expect(reads.count == 1,
                "the re-read waited on the end read the time-out left, and started none of its own")
    }

    /// The re-read is the row's only while the row still says the read timed
    /// out: a run started meanwhile is not overwritten by it.
    @Test func aRereadDoesNotOverwriteARunStartedMeanwhile() async {
        // The end read is held, so the row stays on the time-out until the
        // test has started the study again; a fixed delay let a held main
        // actor miss that window in the full suite.
        let disk = HungDisk()
        let rig = Rig(manifestRead: disk.read,
                      endStateTimeout: .milliseconds(50), slowEndReread: .milliseconds(300))
        defer { disk.release(); rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: nil)

        rig.launches[0].exit()
        await until { rig.runner.state[a.id] == .unreachable(reason: .timedOut) }
        #expect(rig.runner.state[a.id] == .unreachable(reason: .timedOut))
        rig.runner.start(project: a)
        #expect(rig.runner.state[a.id] == .running)
        disk.release()

        try? await Task.sleep(for: .milliseconds(600))
        #expect(rig.runner.state[a.id] == .running)
        #expect(disk.reads == 1, "nothing read the finished run again once a new one held the row")
    }

    /// Stop on a slow disk: the same single read, the same "Not responding".
    @Test func aStoppedRunWhoseEndReadTimedOutIsReadAgain() async {
        let reads = ReadLog()
        let rig = Rig(manifestRead: Self.slowDisk(reads, slow: 1),
                      endStateTimeout: .milliseconds(50))
        defer { rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: 120)

        rig.runner.cancel(project: a)
        rig.launches[0].exit(.exited(code: 130))
        await until {
            if case .ready = rig.runner.state[a.id] { return true }
            return false
        }

        #expect(rig.runner.state[a.id] == .ready(Date(timeIntervalSince1970: 1_792_490_400)))
        #expect(rig.noted.isEmpty, "a stopped run proves nothing about credit")
        #expect(reads.count == 1, "the re-read waited on the end read, and started none of its own")
    }

    /// A Start that starts nothing (here, no AI consent) leaves the row as it
    /// was, so it must leave its re-read going too. It cancelled it first, and
    /// the row read "Not responding" for good.
    @Test func aStartThatStartsNothingKeepsTheReread() async {
        // Held until the refused start, so the re-read cannot settle the row
        // before it, which would pass this test without testing it.
        let disk = HungDisk()
        let rig = Rig(manifestRead: disk.read,
                      endStateTimeout: .milliseconds(50), slowEndReread: .milliseconds(300))
        defer { disk.release(); rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: nil)

        rig.launches[0].exit()
        await until { rig.runner.state[a.id] == .unreachable(reason: .timedOut) }
        #expect(rig.runner.state[a.id] == .unreachable(reason: .timedOut))
        rig.consented = false
        rig.runner.start(project: a)
        #expect(rig.launches.count == 1)
        disk.release()
        await until {
            if case .ready = rig.runner.state[a.id] { return true }
            return false
        }

        guard case .ready = rig.runner.state[a.id] else {
            Issue.record("still \(String(describing: rig.runner.state[a.id]))"); return
        }
    }

    /// The re-read finds a CLI run started on the study meanwhile: it reads as
    /// a scan's would, and is watched until it ends (R22), not left "Analysing".
    @Test func aRereadThatFindsACLIRunWatchesIt() async throws {
        // The end read is held until the CLI run is on disk: the re-read adopts
        // that read, which says what disk holds when it runs. Slowed by a fixed
        // delay instead, a held main actor could land the CLI run after it.
        let disk = HungDisk()
        let rig = Rig(manifestRead: disk.read,
                      endStateTimeout: .milliseconds(50), slowEndReread: .milliseconds(300))
        defer { disk.release(); rig.cleanUp() }
        let a = rig.project("A")
        rig.runner.start(project: a)
        rig.writeFinishedRun(in: a, tokens: nil)

        rig.launches[0].exit()
        await until { rig.runner.state[a.id] == .unreachable(reason: .timedOut) }
        try #require(rig.runner.state[a.id] == .unreachable(reason: .timedOut))
        let dir = URL(fileURLWithPath: a.path).appendingPathComponent("bristlenose-output/.bristlenose")
        try append(#"{"schema_version":5,"ts":"2026-10-20T11:00:00Z","event":"run_started","run_id":"cli-run","kind":"run","started_at":"2026-10-20T11:00:00Z"}"#, to: dir)
        try writePythonPID(getpid(), in: dir)
        disk.release()

        await until { rig.runner.state[a.id] == .running }
        try #require(rig.runner.state[a.id] == .running, "the re-read did not find the CLI run")
        try append(#"{"schema_version":5,"ts":"2026-10-20T12:00:00Z","event":"run_completed","run_id":"cli-run","kind":"run","started_at":"2026-10-20T11:00:00Z","ended_at":"2026-10-20T12:00:00Z","outcome":"completed","cause":null}"#, to: dir)
        await until({ rig.runner.state[a.id] != .running })

        guard case .ready = rig.runner.state[a.id] else {
            Issue.record("still \(String(describing: rig.runner.state[a.id])) after the CLI run finished")
            return
        }
    }

    /// A dead mount: every read of the manifest blocks until the test lets it
    /// go, and cancelling it does nothing, as with a read stuck in the kernel.
    final class HungDisk: @unchecked Sendable {
        private let lock = NSLock()
        private var waiting: [CheckedContinuation<Void, Never>] = []
        private var released = false
        private var n = 0
        private var done = 0
        var reads: Int { lock.withLock { n } }
        /// Reads that have come back from the disk.
        var landed: Int { lock.withLock { done } }
        var read: @Sendable (URL) async -> PipelineState {
            { [self] url in
                await withCheckedContinuation { (c: CheckedContinuation<Void, Never>) in
                    let go = lock.withLock { () -> Bool in
                        n += 1
                        if released { return true }
                        waiting.append(c)
                        return false
                    }
                    if go { c.resume() }
                }
                let state = await PipelineRunner.parseManifest(at: url)
                lock.withLock { done += 1 }
                return state
            }
        }
        func release() {
            let all = lock.withLock { () -> [CheckedContinuation<Void, Never>] in
                released = true
                defer { waiting = [] }
                return waiting
            }
            all.forEach { $0.resume() }
        }
    }

    /// R29 follow-up: on a hung mount the end-state read timed out and the run
    /// slot stayed held anyway, because the timeout's task group waited for
    /// the hung read before returning. The study queued behind never started.
    @Test func aHungEndReadStillFreesTheSlot() async {
        let disk = HungDisk()
        let rig = Rig(manifestRead: disk.read, endStateTimeout: .milliseconds(50))
        defer { disk.release(); rig.cleanUp() }
        let a = rig.project("A")
        let b = rig.project("B")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        #expect(rig.launches.count == 1)

        rig.launches[0].exit()
        await until { rig.launches.count == 2 }

        #expect(rig.launches.count == 2, "the next study never started: the hung read held the slot")
        #expect(rig.runner.state[a.id] == .unreachable(reason: .timedOut))
        #expect(rig.runner.state[b.id] == .running)
    }

    /// R29 on a reconnected run: its exit path read the end state once, so a
    /// read that timed out on a slow disk read "Not responding" until relaunch.
    @Test func anAttachedRunWhoseEndReadTimedOutIsReadAgain() async throws {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("orphan-r29-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let reads = ReadLog()
        let pidFile = PIDFileBox()
        var noted: [LLMProvider] = []
        let (runner, p, _, url) = try await attachedOrphan(
            path: root.path, providerLine: "openai",
            noteRunSucceeded: { noted.append($0) },
            manifestRead: Self.slowAtEnd(reads, pidFile: pidFile),
            endStateTimeout: .milliseconds(50)
        )
        pidFile.url = url
        defer { try? FileManager.default.removeItem(at: url) }

        Self.writeFinishedRun(at: root.path, runId: "orphan-run", tokens: 300)
        await until({
            if case .ready = runner.state[p.id] { return true }
            return false
        })

        guard case .ready = runner.state[p.id] else {
            Issue.record("expected .ready, got \(String(describing: runner.state[p.id]))"); return
        }
        #expect(noted == [.chatGPT])
        #expect(reads.count == 1,
                "one end read that timed out, waited on by the re-read, and none beside it")
    }

    /// A reconnected run on a dead mount: its 2 s poll read the folder with
    /// no time-out, so the first hung read stopped the poll before its next
    /// liveness check, and a run that then ended read "Analysing" until quit,
    /// holding the Mac awake.
    @Test func aReconnectedRunWhoseFolderHangsIsStillSeenToEnd() async throws {
        let disk = HungDisk()
        let (runner, p, recorder, url) = try await attachedOrphan(
            manifestRead: disk.read, endStateTimeout: .milliseconds(50),
            pollInterval: .milliseconds(100)
        )
        defer { disk.release(); try? FileManager.default.removeItem(at: url) }
        await until { disk.reads >= 1 }
        try #require(disk.reads >= 1, "the poll never read the folder")
        // Several ticks go by on the one hung read: each probes the run, and
        // none starts a read beside it.
        let probesBefore = recorder.leaderProbes
        await until { recorder.leaderProbes >= probesBefore + 3 }
        #expect(recorder.leaderProbes >= probesBefore + 3, "the poll stopped on the hung read")
        #expect(disk.reads == 1, "a tick started a second read beside the hung one")

        recorder.leaderAlive = false
        // The exit path drops the row to idle, then its end read (hung too)
        // times out.
        await until { runner.state[p.id] == .unreachable(reason: .timedOut) }

        #expect(runner.state[p.id] == .unreachable(reason: .timedOut),
                "the run's end was never noticed")
    }

    /// A reconnected run that ends while its poll holds a hung read (a dead
    /// mount): the end read used to start beside the held one, so the study
    /// held two blocked threads of the shared pool, not one. The held read is
    /// a snapshot from before the end and cannot stand in for the end state,
    /// so the end read waits for it to settle and then reads. Both routes to
    /// the exit path: the poll's liveness probe, and Stop finding the run gone.
    @Test(arguments: [false, true])
    func aReconnectedRunThatEndsDuringAHungReadHoldsOneRead(stoppedAfterItEnded: Bool)
        async throws {
        let disk = HungDisk()
        let (runner, p, recorder, url) = try await attachedOrphan(
            manifestRead: disk.read, endStateTimeout: .milliseconds(50),
            pollInterval: .milliseconds(100)
        )
        defer { disk.release(); try? FileManager.default.removeItem(at: url) }
        await until { disk.reads >= 1 }
        try #require(disk.reads == 1, "the poll never held a read")

        if stoppedAfterItEnded {
            recorder.sigintResult = ESRCH
            runner.cancel(project: p)
        } else {
            recorder.leaderAlive = false
        }
        await until { runner.state[p.id] == .unreachable(reason: .timedOut) }

        #expect(runner.state[p.id] == .unreachable(reason: .timedOut),
                "the run's end was never noticed")
        // Past the end read's time-out and several of the re-read's waits.
        try? await Task.sleep(for: .milliseconds(400))
        #expect(disk.reads == 1, "the end read started beside the poll's hung read")
    }

    /// The other half: a held read that does land (a slow disk, not a dead
    /// one) lets the end read go ahead, and the row settles from it.
    @Test func anEndReadWaitingOnAHeldReadReadsOnceItLands() async throws {
        let disk = HungDisk()
        let (runner, p, recorder, url) = try await attachedOrphan(
            manifestRead: disk.read, endStateTimeout: .milliseconds(50),
            pollInterval: .milliseconds(100)
        )
        defer { disk.release(); try? FileManager.default.removeItem(at: url) }
        await until { disk.reads >= 1 }
        try #require(disk.reads == 1, "the poll never held a read")

        recorder.leaderAlive = false
        await until { runner.state[p.id] == .unreachable(reason: .timedOut) }
        try #require(runner.state[p.id] == .unreachable(reason: .timedOut))
        disk.release()
        await until { runner.state[p.id] != .unreachable(reason: .timedOut) }

        #expect(runner.state[p.id] != .unreachable(reason: .timedOut),
                "the end state never settled once the disk answered")
        #expect(disk.reads == 2, "the end read never read once the held read landed")
    }

    /// And a re-read that gave up on the dead mount leaves no read behind for
    /// the mount to wake: the end read it was waiting on is cancelled, and
    /// does not read once the held read finally lands.
    @Test func aRereadThatGaveUpLeavesNoReadForTheMountToWake() async throws {
        let disk = HungDisk()
        let (runner, p, recorder, url) = try await attachedOrphan(
            manifestRead: disk.read, endStateTimeout: .milliseconds(50),
            pollInterval: .milliseconds(100)
        )
        defer { disk.release(); try? FileManager.default.removeItem(at: url) }
        await until { disk.reads >= 1 }
        try #require(disk.reads == 1, "the poll never held a read")

        recorder.leaderAlive = false
        await until { runner.state[p.id] == .unreachable(reason: .timedOut) }
        try #require(runner.state[p.id] == .unreachable(reason: .timedOut))
        // The time-out and the start of the re-reads are one main-actor turn
        // (`settleOrphanEndRead`), so they are under way by now. Wait for them
        // to give up rather than for a guess at how long their 12 tries take:
        // a loaded suite holds the main actor for seconds, and the mount woke
        // mid-try, where the read is still wanted (#141).
        try #require(runner.isRereadingSlowEnd(p.id), "the re-reads never started")
        await until { !runner.isRereadingSlowEnd(p.id) }
        try #require(!runner.isRereadingSlowEnd(p.id), "the re-reads never gave up")
        disk.release()
        // The held read is back, so the end read it was holding is now free to
        // go ahead or not. Give a stray read the time the old test gave it.
        await until { disk.landed >= 1 }
        try #require(disk.landed >= 1, "the held read never came back")
        try? await Task.sleep(for: .milliseconds(300))

        #expect(disk.reads == 1, "a read nobody waits on any more went ahead")
        #expect(runner.state[p.id] == .unreachable(reason: .timedOut))
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

    /// `slowEnd`: the end read times out and the re-read settles it (R29),
    /// which must judge credit against the same earlier terminus.
    @Test(arguments: [false, true])
    func anAttachedRunIsNotCreditedWithThePreviousRunsTokens(slowEnd: Bool) async throws {
        let root = URL(fileURLWithPath: NSTemporaryDirectory())
            .appendingPathComponent("orphan-prior-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        // The previous run finished with tokens; the attached one has not
        // written its own start yet, so that terminus is still the tail.
        Self.writeFinishedRun(at: root.path, runId: "earlier", tokens: 300)
        var noted: [LLMProvider] = []
        let endReads = ReadLog()
        let pidFile = PIDFileBox()
        let (runner, _, _, url) = try await attachedOrphan(
            path: root.path, providerLine: "openai",
            noteRunSucceeded: { noted.append($0) },
            manifestRead: slowEnd
                ? Self.slowAtEnd(endReads, pidFile: pidFile)
                : { await PipelineRunner.parseManifest(at: $0) },
            endStateTimeout: slowEnd ? .milliseconds(50) : .seconds(5)
        )
        pidFile.url = url
        defer { try? FileManager.default.removeItem(at: url) }

        // The poll reads ready (the earlier run's) and calls the run over.
        await until({ !FileManager.default.fileExists(atPath: url.path) })
        let ready = { runner.state.values.contains { if case .ready = $0 { true } else { false } } }
        await until(ready)

        #expect(ready(), "the attached run's end never settled")
        if slowEnd { #expect(endReads.count >= 1, "no end read was slowed") }
        // Credit is judged a hop after the row is written: give it the time.
        try? await Task.sleep(for: .milliseconds(300))
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
        await until({ !noted.isEmpty })

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
        await until({ rig.runner.state[p.id] != .running })

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
        await until({ rig.runner.state[p.id] != .running })

        #expect(rig.runner.state[p.id] == .stopped(stagesComplete: []))
    }

    @Test func aRunTheAppDoesNotOwnThatDiedReadsAsStranded() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)

        // Killed, no terminus written: run.pid names a process that is gone.
        try writePythonPID(999_999, in: dir)
        await until({ rig.runner.state[p.id] != .running })

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
        await until({ rig.runner.state[p.id] != .running })

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
        await until({ rig.runner.state[p.id] != .running })
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
        await until({ rig.runner.state[p.id] != .running })
        #expect(rig.runner.state[p.id] == .stopped(stagesComplete: []), "the watch did not outlive the torn read")
    }

    /// A `run.pid` gone for good (its run killed before writing one, say) is
    /// waited out, not watched for ever.
    @Test func aRunThatNeverSaysIsSettledAfterThePatienceRunsOut() async throws {
        let rig = Rig(patience: 4); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)
        try FileManager.default.removeItem(at: dir.appendingPathComponent(EventLogReader.pidFilename))

        await until({ rig.runner.state[p.id] != .running })

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

    // MARK: - RE#12: runs the app doesn't own (decisions #39, #40, #41)

    private func dotBristlenose(_ p: Project) throws -> URL {
        let dir = URL(fileURLWithPath: p.path).appendingPathComponent("bristlenose-output/.bristlenose")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    /// A study whose last run left `line` newest in its events log, scanned.
    private func studyEndedWith(_ rig: Rig, _ name: String, _ line: String) async throws -> (Project, URL) {
        let p = rig.project(name)
        let dir = try dotBristlenose(p)
        let started = #"{"schema_version":5,"ts":"2026-10-20T09:00:00Z","event":"run_started","run_id":"r1","kind":"run","started_at":"2026-10-20T09:00:00Z"}"#
        try Data((started + "\n" + line + "\n").utf8).write(to: dir.appendingPathComponent(EventLogReader.filename))
        rig.runner.scan(project: p)
        await until { ![nil, .scanning].contains(rig.runner.state[p.id]) }
        return (p, dir)
    }

    private static let cancelled = #"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_cancelled","run_id":"r1","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"cancelled","cause":null}"#
    private static let failedLine = #"{"schema_version":5,"ts":"2026-10-20T10:00:00Z","event":"run_failed","run_id":"r1","kind":"run","started_at":"2026-10-20T09:00:00Z","ended_at":"2026-10-20T10:00:00Z","outcome":"failed","cause":{"category":"unknown","message":"boom"}}"#
    private static let cliStarted = #"{"schema_version":5,"ts":"2026-10-20T11:00:00Z","event":"run_started","run_id":"cli-run","kind":"run","started_at":"2026-10-20T11:00:00Z"}"#

    /// #40: a CLI run begun after the row settled is read when the app comes
    /// forward, and then watched to its end. It read Ready until relaunch.
    @Test func comingForwardSeesACLIRunStartedAfterLaunch() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let p = rig.project("A")
        rig.writeFinishedRun(in: p, tokens: nil)
        rig.runner.scan(project: p)
        await until { if case .ready = rig.runner.state[p.id] { return true }; return false }
        let dir = try dotBristlenose(p)
        try append(Self.cliStarted, to: dir)
        try writePythonPID(getpid(), in: dir)

        rig.center.post(name: NSApplication.didBecomeActiveNotification, object: nil)
        await until { rig.runner.state[p.id] == .running }
        #expect(rig.runner.state[p.id] == .running, "the CLI run was not seen on coming forward")

        try append(#"{"schema_version":5,"ts":"2026-10-20T12:00:00Z","event":"run_completed","run_id":"cli-run","kind":"run","started_at":"2026-10-20T11:00:00Z","ended_at":"2026-10-20T12:00:00Z","outcome":"completed","cause":null}"#, to: dir)
        await until { rig.runner.state[p.id] != .running }
        guard case .ready = rig.runner.state[p.id] else {
            Issue.record("\(String(describing: rig.runner.state[p.id])) after the CLI run finished")
            return
        }
        #expect(rig.launches.isEmpty)
    }

    /// #40: a live run on disk is newer than the ending a row shows. A Stopped
    /// row kept "Stopped" through a CLI run and after it.
    @Test func aCLIRunReplacesTheEndingARowShows() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, dir) = try await studyEndedWith(rig, "A", Self.cancelled)
        try #require(rig.runner.state[p.id] == .stopped(stagesComplete: []))
        try append(Self.cliStarted, to: dir)
        try writePythonPID(getpid(), in: dir)

        rig.center.post(name: NSApplication.didBecomeActiveNotification, object: nil)
        await until { rig.runner.state[p.id] == .running }

        #expect(rig.runner.state[p.id] == .running)
    }

    /// #41: "Analysis stopped unexpectedly" is a read of disk, so a later read
    /// replaces it: here a CLI run that started and finished between scans.
    @Test func aStrandedRowIsReplacedByALaterRead() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, dir) = try await foreignRun(rig)
        try writePythonPID(999_999, in: dir)
        await until { rig.runner.state[p.id]?.isStranded == true }
        try #require(rig.runner.state[p.id]?.isStranded == true)

        rig.writeFinishedRun(in: p, runId: "cli-run-2", tokens: nil)
        rig.center.post(name: NSApplication.didBecomeActiveNotification, object: nil)
        await until { rig.runner.state[p.id]?.isStranded != true }

        guard case .ready = rig.runner.state[p.id] else {
            Issue.record("still \(String(describing: rig.runner.state[p.id])) over a fresh report")
            return
        }
    }

    /// #41 is the one exception: any other failure keeps its protection, so a
    /// manifest read never erases a diagnostic.
    @Test func anyOtherFailureIsKeptThroughALaterRead() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let (p, _) = try await studyEndedWith(rig, "A", Self.failedLine)
        guard case .failed = rig.runner.state[p.id] else {
            Issue.record("precondition: \(String(describing: rig.runner.state[p.id]))"); return
        }
        let before = rig.runner.state[p.id]

        rig.writeFinishedRun(in: p, runId: "r2", tokens: nil)
        let applied = rig.runner.activationReadsApplied
        rig.center.post(name: NSApplication.didBecomeActiveNotification, object: nil)
        await until { rig.runner.activationReadsApplied > applied }
        try #require(rig.runner.activationReadsApplied > applied, "the read was never applied")

        #expect(rig.runner.state[p.id] == before)
    }

    /// Review, 22 Oct 2026: on a share that is mounted but hung, a timed read
    /// gave up at 5 s and left its thread blocked; the study was free to be
    /// read again, so every ⌘-Tab added another blocked thread. The read on
    /// coming forward is untimed, and a study waits on its one read.
    @Test func aHungReadOnComingForwardIsNotStacked() async throws {
        final class Gate: @unchecked Sendable {
            var open = false
            var calls = 0
        }
        let gate = Gate()
        let rig = Rig(manifestRead: { url in
            gate.calls += 1
            while !gate.open { try? await Task.sleep(for: .milliseconds(20)) }
            return await PipelineRunner.parseManifest(at: url)
        })
        defer { gate.open = true; rig.cleanUp() }
        let p = rig.project("A")
        rig.runner.scan(project: p)
        await until { rig.runner.state[p.id] == .idle }
        try #require(rig.runner.state[p.id] == .idle)

        rig.center.post(name: NSApplication.didBecomeActiveNotification, object: nil)
        await until { gate.calls == 1 }
        try await Task.sleep(for: PipelineRunner.scanTimeout + .seconds(1))
        #expect(rig.runner.activationReadsApplied == 0, "the read was given up while still blocked")

        rig.center.post(name: NSApplication.didBecomeActiveNotification, object: nil)
        gate.open = true
        await until { rig.runner.activationReadsApplied > 0 }
        try? await Task.sleep(for: .milliseconds(200))
        #expect(gate.calls == 1, "a second read was stacked on the hung one")
        #expect(rig.runner.state[p.id] == .idle)
    }

    /// Review, 22 Oct 2026: a read in flight across the end of the app's own
    /// run saw its live `run.pid`; landing over the ending the run just wrote,
    /// it brought the run back as somebody else's. Only a read issued over the
    /// row as it stands may replace it.
    @Test func onlyAReadOfTheRowAsItStandsReplacesIt() {
        let stopped = PipelineState.stopped(stagesComplete: [])
        #expect(PipelineRunner.isReadOfThisRow(current: stopped, issuedOver: stopped))
        #expect(!PipelineRunner.isReadOfThisRow(current: stopped, issuedOver: .running), "issued while our run was live")
        #expect(!PipelineRunner.isReadOfThisRow(current: stopped, issuedOver: nil), "a read settling a run")
    }


    /// #40: what an activation rescan reads. Not a run or a queue place (the
    /// runner's, or watched), not a scan under way, not a folder that is away.
    @Test func whatComingForwardReadsAgain() {
        let reads = PipelineRunner.takesActivationRescan
        #expect(!reads(nil))
        #expect(!reads(.scanning))
        #expect(!reads(.running))
        #expect(!reads(.queued(position: 1)))
        #expect(!reads(.unreachable(reason: .folderMissing)))
        #expect(reads(.idle))
        #expect(reads(.ready(Date())))
        #expect(reads(.stopped(stagesComplete: [])))
        #expect(reads(.failed(EventLogReader.stranded, category: .unknown)))
    }

    /// #39: Stop is offered on the app's own run and queue, never on a run
    /// another process owns, where it sent nothing.
    @Test func stopIsOfferedOnlyWhereItCanReach() async throws {
        let rig = Rig(); defer { rig.cleanUp() }
        let a = rig.project("A"), b = rig.project("B")
        rig.runner.start(project: a)
        rig.runner.start(project: b)
        #expect(rig.runner.canStop(a.id), "the app's own run")
        #expect(rig.runner.canStop(b.id), "a place in the queue")

        let (cli, _) = try await foreignRun(rig)
        #expect(!rig.runner.canStop(cli.id), "a CLI run: Stop would send nothing")
        #expect(!rig.runner.canStop(rig.project("C").id), "nothing running")
    }

    // MARK: - R25: a failed run is judged on all of its output

    @Test func aFailureIsJudgedOnLinesStillInThePipeAtExit() async throws {
        // The pipe closes once the traceback is in, so a long limit costs
        // nothing; a 1 s one lost the race to a held main actor on a guest.
        let rig = Rig(drainLimit: .seconds(30)); defer { rig.cleanUp() }
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
        await until({ if case .failed = rig.runner.state[a.id] { return true }; return false })

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
        await until({ rig.launches.count == 2 })

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

/// Holds Stop's ladder until a test lets it go.
private actor LadderGate {
    private var isOpen = false
    func open() { isOpen = true }
    func wait() async {
        while !isOpen { try? await Task.sleep(for: .milliseconds(5)) }
    }
}
