import Foundation
import os

// MARK: - Failure taxonomy

/// Categorises a pipeline failure so the UI can show a human summary + CTA
/// without leaking raw stderr. Regex-based heuristics today; would be replaced
/// by explicit error codes if the CLI gains structured progress output.
enum PipelineFailureCategory: String, Codable, Equatable {
    case auth
    case network
    case quota
    case disk
    case whisper
    case unknown
}

// MARK: - Neutral progress struct

/// What we know about a running pipeline. Display-agnostic by design — no
/// pill/chip/toast-shaped fields. See plan §Architecture "The discipline this
/// branch must hold".
struct PipelineProgress: Equatable {
    var stageIndex: Int = 0
    var stageName: String = ""
    var sessionsComplete: Int?
    var sessionsTotal: Int?
    var elapsed: TimeInterval = 0
    var lastLine: String = ""
    var startedAt: Date = Date()
}

// MARK: - Lifecycle state

/// Per-project pipeline lifecycle. Resolved asynchronously at app launch
/// (`.scanning` → concrete state) and mutated by start/cancel/attach.
enum PipelineState: Equatable {
    /// Initial state until the manifest read resolves during sidebar scan.
    case scanning
    /// No run in flight, no completed manifest (or manifest says never-run).
    case idle
    /// Waiting behind another project's run in the single-slot FIFO queue.
    case queued(position: Int)
    /// A subprocess is running (or we've attached to an orphan).
    case running
    /// Manifest reports all stages complete.
    case ready(Date)
    /// Last run failed — Retry/Change-provider CTAs.
    case failed(String, category: PipelineFailureCategory)
    /// Project can't be scanned (volume unmounted, path gone, permission denied).
    /// Distinct from `.failed` — nothing to retry, just unreachable right now.
    case unreachable(reason: String)
}

// MARK: - Progress parser protocol

/// Populates a `PipelineProgress` from some input source. Two impls planned:
/// `StdoutProgressParser` (spawned runs) and `ManifestPollingProgressParser`
/// (attached orphans, Slice 7). A third could consume a future
/// `--json-progress` CLI flag without touching display code.
protocol ProgressParser {
    mutating func consume(_ line: String, into progress: inout PipelineProgress)
}

/// Parses coarse stage markers from the Rich-formatted CLI output.
///
/// The CLI prints one `✓ stage name` line per completed stage
/// (`bristlenose/pipeline.py:_print_step()`). We treat that as an index++
/// signal and show the NEXT stage as "running"; the line is also captured
/// verbatim as `lastLine` for the popover's technical-details disclosure.
///
/// Deliberately kept minimal — the plan calls out that once the CLI gains
/// structured output, this parser gets replaced rather than extended.
struct StdoutProgressParser: ProgressParser {
    mutating func consume(_ line: String, into progress: inout PipelineProgress) {
        progress.lastLine = line

        // Rich strips ANSI for us upstream (BristlenoseShared.stripANSI).
        // Look for the CLI's checkmark-prefixed stage completion lines.
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        if trimmed.hasPrefix("✓ ") {
            progress.stageIndex += 1
            // Drop the "✓ " prefix and any trailing "(cached)" / timing suffix
            // in parens — the name is the human-readable stage label.
            var name = String(trimmed.dropFirst(2))
            if let parenStart = name.firstIndex(of: "(") {
                name = String(name[..<parenStart]).trimmingCharacters(in: .whitespaces)
            }
            progress.stageName = name
        }

        progress.elapsed = Date().timeIntervalSince(progress.startedAt)
    }
}

// MARK: - Live data store

/// High-frequency observable data for in-flight runs — progress and stdout
/// ring buffer. Split out from `PipelineRunner` so consumers that don't
/// need this data (notably the sidebar `ProjectRow`, which only renders
/// `state`) don't get woken up on every stdout line.
///
/// A typical Whisper stage emits thousands of lines; with the dicts lived
/// directly on the runner, every row in the sidebar re-bodied on each one
/// (see perf review on `port-v01-ingestion`). Keeping `state` on the
/// runner and the noisy data here isolates the observation surfaces.
@MainActor
final class PipelineLiveData: ObservableObject {

    /// Ring-buffer cap for `outputLines` per project. Generous enough to
    /// diagnose a failure via `Copy error details`; the full log still goes
    /// to `<project>/.bristlenose/bristlenose.log` via the CLI logger.
    static let outputLineCap = 1000

    @Published private(set) var progress: [UUID: PipelineProgress] = [:]
    @Published private(set) var outputLines: [UUID: [String]] = [:]

    func setProgress(_ value: PipelineProgress?, for projectID: UUID) {
        progress[projectID] = value
    }

    func mutateProgress(for projectID: UUID, _ mutate: (inout PipelineProgress) -> Void) {
        guard var p = progress[projectID] else { return }
        mutate(&p)
        progress[projectID] = p
    }

    func clearOutput(for projectID: UUID) {
        outputLines[projectID] = []
    }

    /// Append with single-element FIFO eviction once the cap is hit. Bulk
    /// `removeFirst(N)` is O(N) on the remaining buffer — replaced after
    /// the perf review caught it as the hottest main-thread path.
    func appendOutput(_ line: String, for projectID: UUID) {
        var lines = outputLines[projectID] ?? []
        lines.append(line)
        if lines.count > Self.outputLineCap {
            lines.removeFirst()
        }
        outputLines[projectID] = lines
    }

    func snapshotOutput(for projectID: UUID) -> [String] {
        outputLines[projectID] ?? []
    }
}

// MARK: - PipelineRunner

/// Manages `bristlenose run` subprocess lifecycle, mirroring ServeManager.
///
/// MVP policy: at most one `Process()` runs at a time app-wide. Additional
/// starts enter a FIFO queue and surface as `.queued(position:)`.
@MainActor
final class PipelineRunner: ObservableObject {

    private static let logger = Logger(
        subsystem: "app.bristlenose", category: "pipeline"
    )

    @Published private(set) var state: [UUID: PipelineState] = [:]

    /// Noisy progress data + stdout ring buffer. See `PipelineLiveData` for
    /// why this lives in a separate `ObservableObject`.
    let liveData = PipelineLiveData()

    /// FIFO queue of project IDs waiting to run. `currentlyRunning` holds the
    /// active run; any new `start()` while that's set enqueues.
    private var queue: [UUID] = []
    private var currentlyRunning: UUID?

    /// The current live `Process()`, if any. Cleared in the termination
    /// handler and by `cancel()`.
    private var currentProcess: Process?
    private var currentReadTask: Task<Void, Never>?
    private var currentProject: Project?

    /// Looked up via `setProjectIndex(_:)` from the App layer once the
    /// shared `@StateObject` graph is wired. Used by `startNextQueued()` to
    /// resolve a queued ID back into a `Project`. Weak to avoid a retain
    /// cycle with the App-level `@StateObject`.
    private weak var projectIndex: ProjectIndex?

    /// Tracks attached orphan runs (project ID → PID). Populated by
    /// `attachOrphan(project:pid:)`; consumed by `cancel()` so Stop sends
    /// SIGINT to the right process even though we never spawned it ourselves.
    private var attachedOrphanPIDs: [UUID: pid_t] = [:]

    /// Manifest-polling tasks for attached orphans (project ID → task).
    /// Cancelled when the orphan finishes or the user clicks Stop.
    private var orphanPollTasks: [UUID: Task<Void, Never>] = [:]

    /// Incremented on each spawn — termination handlers from previous runs
    /// check this to avoid overwriting the new run's state. Same pattern as
    /// ServeManager's generation counter.
    private var generation: Int = 0

    /// Parser for the current run. One instance per run; recreated on each
    /// spawn so stage indices don't leak between projects.
    private var currentParser: any ProgressParser = StdoutProgressParser()

    /// Set by `cancel()` on the owned-process path so `handleTermination`
    /// routes the non-zero exit status to `.idle` (user asked) rather than
    /// `.failed` (pipeline errored). Cleared on each `spawn`.
    private var cancellationRequested: Bool = false

    /// Manifest timestamps include fractional seconds
    /// (`2026-04-17T00:37:27.480978+00:00`), which the default
    /// `ISO8601DateFormatter` does not parse.
    private static let iso8601: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    /// Per-project manifest read timeout. A dead network mount shouldn't
    /// leave a sidebar row throbbing forever — after this we fall to
    /// `.unreachable`.
    static let scanTimeout: Duration = .seconds(5)

    init() {
        Self.logger.info("PipelineRunner initialised")
    }

    /// Inject the shared `ProjectIndex` so `startNextQueued()` can resolve a
    /// queued UUID back into a `Project`. Call once from the App layer's
    /// `.onAppear`, after both `@StateObject`s exist.
    func setProjectIndex(_ index: ProjectIndex) {
        self.projectIndex = index
    }

    private nonisolated static func runCapturing(
        executable: String, arguments: [String]
    ) -> String? {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: executable)
        proc.arguments = arguments
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = FileHandle.nullDevice
        do {
            try proc.run()
            proc.waitUntilExit()
        } catch {
            return nil
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8)
    }

    // MARK: - Progressive sidebar scan

    /// Kick off a per-project manifest read for every project in the index.
    /// Each scan runs in its own detached task with a 5s timeout; the window
    /// appears immediately and rows flip from `.scanning` to their resolved
    /// state as manifests come in.
    ///
    /// Safe to call multiple times — already-resolved projects are re-scanned,
    /// which is cheap (local file read ~1 ms) and keeps sidebar state fresh
    /// after external tools write the manifest (e.g. a CLI run completed).
    func scanAllProjects(_ projects: [Project]) {
        for project in projects {
            // Only mark .scanning if we have no reactive state yet — otherwise
            // a running/queued project would get its state clobbered.
            if state[project.id] == nil {
                state[project.id] = .scanning
            }
            scan(project: project)
        }
    }

    /// Result of an off-main scan — either an orphan to attach to, or a
    /// resolved manifest state.
    private enum ScanOutcome {
        case orphan(pid: pid_t)
        case manifest(PipelineState)
    }

    /// Scan a single project's manifest, with orphan-attach taking priority
    /// if a live `bristlenose run` for this project is found.
    ///
    /// All filesystem I/O (PID file read, `/bin/ps` exec for uid/argv
    /// verification, manifest JSON parse) runs on a detached task. Only the
    /// final state mutation hops back to MainActor.
    func scan(project: Project) {
        let projectID = project.id
        let manifestURL = Self.manifestURL(for: project)

        Task.detached { [weak self] in
            let outcome = await Self.performScan(project: project, manifestURL: manifestURL)
            await self?.applyScan(outcome: outcome, project: project, projectID: projectID)
        }
    }

    private nonisolated static func performScan(
        project: Project, manifestURL: URL
    ) async -> ScanOutcome {
        if let pid = aliveOwnedRunPID(for: project) {
            return .orphan(pid: pid)
        }
        // No live orphan — sweep any stale PID file and fall through to a
        // normal manifest read.
        removePIDFile(for: project)
        let resolved = await readManifestState(
            at: manifestURL, timeout: scanTimeout, allowTimeout: true
        )
        return .manifest(resolved)
    }

    private func applyScan(outcome: ScanOutcome, project: Project, projectID: UUID) {
        switch outcome {
        case .orphan(let pid):
            attachOrphan(project: project, pid: pid)
        case .manifest(let state):
            applyScanResult(state, for: projectID)
        }
    }

    // MARK: - Orphan attach (Slice 7)

    /// Read `<project.path>/.bristlenose/pipeline.pid`, verify the PID is
    /// (a) alive, (b) owned by the current uid, (c) running an argv that
    /// contains `bristlenose run`. Returns the PID iff all three pass.
    /// Removes the file silently if the PID is dead, foreign, or wrong-argv.
    private nonisolated static func aliveOwnedRunPID(for project: Project) -> pid_t? {
        let url = pidFileURL(for: project)
        guard let data = try? Data(contentsOf: url),
              let str = String(data: data, encoding: .utf8),
              let pid = pid_t(str.trimmingCharacters(in: .whitespacesAndNewlines)),
              pid > 0 else {
            return nil
        }
        // (a) alive — kill(pid, 0) returns 0 if the process exists and we
        // can signal it; ESRCH means no such process.
        guard kill(pid, 0) == 0 else {
            try? FileManager.default.removeItem(at: url)
            return nil
        }
        // (b) uid match — ps -p <pid> -o uid=
        guard let uidStr = runCapturing(
            executable: "/bin/ps", arguments: ["-p", String(pid), "-o", "uid="]
        )?.trimmingCharacters(in: .whitespacesAndNewlines),
              let uid = uid_t(uidStr), uid == getuid() else {
            // PID was reused by some other user's process — leave the foreign
            // process alone and remove our stale file.
            try? FileManager.default.removeItem(at: url)
            return nil
        }
        // (c) argv contains `bristlenose run` — guards against PID reuse by
        // an unrelated process owned by the same user.
        guard let argv = runCapturing(
            executable: "/bin/ps", arguments: ["-p", String(pid), "-o", "args="]
        ), argv.contains("bristlenose run") else {
            try? FileManager.default.removeItem(at: url)
            return nil
        }
        return pid
    }

    /// Attach to a live orphan: surface as `.running` with the same UI as a
    /// freshly-spawned run, but drive progress from manifest polling rather
    /// than stdout. Atomic stage commits make this safe — see
    /// `docs/design-pipeline-resilience.md`.
    private func attachOrphan(project: Project, pid: pid_t) {
        guard attachedOrphanPIDs[project.id] == nil else { return }
        Self.logger.info(
            "attaching to orphan project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
        )
        attachedOrphanPIDs[project.id] = pid
        state[project.id] = .running
        liveData.setProgress(PipelineProgress(startedAt: Date()), for: project.id)

        let projectID = project.id
        let manifestURL = Self.manifestURL(for: project)

        let task = Task { @MainActor [weak self] in
            // Poll every 2s until the manifest reports all-complete or the
            // orphan dies (kill(pid,0) fails) or we're cancelled.
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(2))
                guard let self else { return }
                guard self.attachedOrphanPIDs[projectID] == pid else { return }

                // Did the orphan die between polls?
                if kill(pid, 0) != 0 {
                    self.handleOrphanExit(projectID: projectID, project: project)
                    return
                }

                // Read manifest off-main; map to PipelineState. We trust the
                // local disk on these in-poll reads — no timeout machinery.
                let resolved = await Self.readManifestState(
                    at: manifestURL, timeout: Self.scanTimeout, allowTimeout: false
                )
                if case .ready = resolved {
                    self.handleOrphanExit(projectID: projectID, project: project)
                    return
                }
                // Update the lastLine so the popover technical-details shows
                // "polling manifest…" rather than blank — cheap signal of life.
                self.liveData.mutateProgress(for: projectID) { p in
                    p.elapsed = Date().timeIntervalSince(p.startedAt)
                    p.lastLine = "Polling project manifest (attached run)"
                }
            }
        }
        orphanPollTasks[project.id] = task
    }

    private func handleOrphanExit(projectID: UUID, project: Project) {
        attachedOrphanPIDs[projectID] = nil
        orphanPollTasks[projectID]?.cancel()
        orphanPollTasks[projectID] = nil
        Self.removePIDFile(for: project)

        // Re-read the manifest one final time to derive .ready vs .idle.
        // Brief delay so a clean SIGINT exit has time to flush atexit
        // handlers (manifest write); a SIGKILL/crash won't benefit but won't
        // be made worse either.
        Task.detached { [weak self] in
            try? await Task.sleep(for: .milliseconds(500))
            let resolved = await Self.readManifestState(
                at: Self.manifestURL(for: project), timeout: Self.scanTimeout
            )
            await self?.applyScanResult(resolved, for: projectID)
        }
    }

    // MARK: - PID file

    /// `~/Library/Application Support/Bristlenose/pids/<project.id>.pid` —
    /// written by `spawn()`, removed by `handleTermination` and the
    /// orphan-attach lifecycle.
    ///
    /// Lives in App Support (not next to the project manifest) so it stays
    /// writable under TestFlight's App Sandbox without bookmark juggling —
    /// the App Support container is always granted to the app. The PID file
    /// is a Swift-internal recovery hint that Python doesn't read, so the
    /// "lives next to manifest" symmetry costs us nothing to give up.
    private nonisolated static func pidFileURL(for project: Project) -> URL {
        pidsDirectory().appendingPathComponent("\(project.id.uuidString).pid")
    }

    private nonisolated static func pidsDirectory() -> URL {
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first ?? URL(fileURLWithPath: NSTemporaryDirectory())
        return appSupport
            .appendingPathComponent("Bristlenose")
            .appendingPathComponent("pids")
    }

    private nonisolated static func writePIDFile(for project: Project, pid: pid_t) {
        let url = pidFileURL(for: project)
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true
        )
        try? Data("\(pid)".utf8).write(to: url, options: .atomic)
    }

    private nonisolated static func removePIDFile(for project: Project) {
        try? FileManager.default.removeItem(at: pidFileURL(for: project))
    }

    /// Apply a scan result, but don't clobber a live `.running` / `.queued`
    /// state — those come from the runner, not the manifest. (The manifest
    /// polling strategy for attached orphans lands in Slice 7.)
    private func applyScanResult(_ resolved: PipelineState, for projectID: UUID) {
        switch state[projectID] {
        case .running, .queued, .failed:
            // .running/.queued: live state owned by the runner, not the manifest.
            // .failed: a stale manifest must not erase a fresh failure summary
            //          (and its Retry CTA) just because the prior run wrote
            //          .ready before crashing.
            return
        default:
            state[projectID] = resolved
        }
    }

    /// Location of a project's pipeline manifest on disk.
    /// `<project.path>/bristlenose-output/.bristlenose/pipeline-manifest.json`
    /// matches the CLI's default output layout (root `CLAUDE.md` §Output
    /// directory structure).
    static func manifestURL(for project: Project) -> URL {
        URL(fileURLWithPath: project.path)
            .appendingPathComponent("bristlenose-output")
            .appendingPathComponent(".bristlenose")
            .appendingPathComponent("pipeline-manifest.json")
    }

    /// Read a manifest file with a hard timeout. Maps to a `PipelineState`:
    /// - file missing → `.idle`
    /// - all stages `complete` → `.ready(completed_at)`
    /// - any stage non-`complete` → `.idle` (treat partial as "ready to run
    ///   again"; orphan-attach comes in Slice 7)
    /// - read error / timeout → `.unreachable(reason:)`
    /// - Parameter allowTimeout: when `true`, a 5 s hard timeout via
    ///   `withThrowingTaskGroup` guards against a dead network mount; when
    ///   `false`, skip the timeout machinery entirely (in-poll reads against
    ///   trusted local disk don't need it, and creating a sleep-task per
    ///   poll cycle was a real wakeup amplifier — see perf review).
    static func readManifestState(
        at url: URL, timeout: Duration, allowTimeout: Bool = true
    ) async -> PipelineState {
        guard allowTimeout else {
            return await parseManifest(at: url)
        }
        do {
            return try await withThrowingTaskGroup(
                of: PipelineState.self
            ) { group in
                group.addTask {
                    await parseManifest(at: url)
                }
                group.addTask {
                    try await Task.sleep(for: timeout)
                    throw CancellationError()
                }
                guard let first = try await group.next() else {
                    return .unreachable(reason: "Scan failed")
                }
                group.cancelAll()
                return first
            }
        } catch is CancellationError {
            return .unreachable(reason: "Taking too long to respond.")
        } catch {
            return .unreachable(reason: "Can't read this project.")
        }
    }

    private static func parseManifest(at url: URL) async -> PipelineState {
        let fm = FileManager.default
        let parentDir = url.deletingLastPathComponent()
            .deletingLastPathComponent()  // strip .bristlenose/, keep bristlenose-output/
            .deletingLastPathComponent()  // strip bristlenose-output/, keep project.path

        // Distinguish "project folder missing" (→ unreachable) from "never
        // analysed" (→ idle). The manifest-file-missing case is expected on
        // new projects.
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: parentDir.path, isDirectory: &isDir),
              isDir.boolValue else {
            return .unreachable(reason: "Can't find this folder.")
        }

        guard fm.fileExists(atPath: url.path) else {
            return .idle
        }

        do {
            let data = try Data(contentsOf: url)
            guard let json = try JSONSerialization.jsonObject(with: data)
                    as? [String: Any],
                  let stages = json["stages"] as? [String: Any] else {
                return .unreachable(reason: "Project file is damaged.")
            }

            // All stages must be "complete" for .ready; otherwise .idle.
            var latestCompleted: Date?
            for (_, raw) in stages {
                guard let stage = raw as? [String: Any],
                      let status = stage["status"] as? String else {
                    return .idle
                }
                if status != "complete" {
                    return .idle
                }
                if let ts = stage["completed_at"] as? String,
                   let date = Self.iso8601.date(from: ts) {
                    if latestCompleted == nil || date > latestCompleted! {
                        latestCompleted = date
                    }
                }
            }

            return .ready(latestCompleted ?? Date())
        } catch {
            return .unreachable(reason: "Can't read this project.")
        }
    }

    // MARK: - Public API

    /// Request a pipeline run for `project`. If nothing is running, spawns
    /// immediately; otherwise enqueues.
    ///
    /// Consent guard is defence-in-depth — the primary enforcement is the
    /// non-dismissable `AIConsentView` sheet in ContentView. If somehow the
    /// guard below fails, the subprocess still can't send data anywhere
    /// because API keys live in Keychain behind a user prompt.
    func start(project: Project) {
        guard Self.hasAIConsent else {
            Self.logger.warning(
                "start blocked — no AI consent (project=\(project.id.uuidString, privacy: .public))"
            )
            // Defence-in-depth — the modal sheet is the real gate. If we ever
            // get here, log and no-op rather than synthesising a fake failure
            // (the user can't "Retry" their way out of consent).
            return
        }

        // If this project is currently an attached orphan (.running but
        // owned by a stray subprocess), don't spawn a competing writer.
        if attachedOrphanPIDs[project.id] != nil {
            Self.logger.warning(
                "start ignored — orphan attached for project=\(project.id.uuidString, privacy: .public)"
            )
            return
        }

        if currentlyRunning == nil {
            spawn(project: project)
        } else if currentlyRunning != project.id, !queue.contains(project.id) {
            queue.append(project.id)
            renumberQueue()
        }
    }

    /// Cancel the current run (if it's for `project`) or remove it from the
    /// queue. SIGINT for graceful Python shutdown — the CLI flushes manifest
    /// writes in its `atexit` handlers, so cancelled runs are still safe to
    /// resume.
    func cancel(project: Project) {
        if currentlyRunning == project.id {
            if let proc = currentProcess, proc.isRunning {
                cancellationRequested = true
                proc.interrupt()
            }
            // The termination handler will clear currentlyRunning and dequeue.
        } else if let pid = attachedOrphanPIDs[project.id] {
            // Stop an attached orphan. Trust the attach: we only set
            // attachedOrphanPIDs for PIDs that aliveOwnedRunPID confirmed
            // were ours. Send SIGINT directly and interpret errno —
            // re-verifying via /bin/ps was racy (PID-file write delays,
            // ps exec hiccups) and the silent skip path was the
            // Stop-is-a-lie alpha blocker (24 Apr 2026).
            let result = kill(pid, SIGINT)
            if result == 0 {
                Self.logger.info(
                    "SIGINT to attached orphan project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
                )
                liveData.mutateProgress(for: project.id) { p in
                    p.lastLine = "Stopping…"
                }
                // Don't clear state here — the orphan poll task
                // (kill(pid,0) every 2s) will detect the exit and call
                // handleOrphanExit, which tears down attachedOrphanPIDs,
                // removes the PID file, and resolves the final state
                // from the manifest. ≤2s pill lag is acceptable.
            } else if errno == ESRCH {
                // Process already gone (raced our cancel). Treat as
                // success and run the same teardown the poll task would.
                Self.logger.info(
                    "orphan already exited project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
                )
                handleOrphanExit(projectID: project.id, project: project)
            } else if errno == EPERM {
                // Not ours after all — leave state intact, surface in log.
                // Should not happen given attach-time ownership check.
                Self.logger.error(
                    "SIGINT denied (EPERM) project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
                )
            } else {
                Self.logger.error(
                    "SIGINT failed errno=\(errno, privacy: .public) project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
                )
            }
        } else if let idx = queue.firstIndex(of: project.id) {
            queue.remove(at: idx)
            state[project.id] = .idle
            renumberQueue()
        }
    }

    // MARK: - Spawn

    private func spawn(project: Project) {
        guard let binary = BristlenoseShared.findBristlenoseBinary() else {
            state[project.id] = .failed(
                "Couldn't find the bristlenose binary.", category: .unknown
            )
            return
        }

        generation += 1
        let gen = generation
        currentlyRunning = project.id
        currentProject = project
        currentParser = StdoutProgressParser()
        cancellationRequested = false
        state[project.id] = .running
        liveData.setProgress(PipelineProgress(startedAt: Date()), for: project.id)
        liveData.clearOutput(for: project.id)

        let proc = Process()
        proc.executableURL = binary
        // --static (alias for --no-serve) makes `bristlenose run` exit after
        // rendering instead of auto-starting a serve and waiting for Ctrl-C.
        // Without this the subprocess never terminates → terminationHandler
        // never fires → state stays .running indefinitely (QA, 20 Apr 2026).
        // ServeManager.start() starts the serve on the Mac side after pipeline
        // success per the plan's "pipeline first, then serve" policy.
        proc.arguments = ["run", project.path, "--static"]
        proc.environment = BristlenoseShared.buildChildEnvironment()

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe
        let handle = pipe.fileHandleForReading

        let projectID = project.id
        currentReadTask = Task.detached { [weak self] in
            let fh = handle
            // Accumulate across read boundaries so a `✓ stage name` line
            // straddling two `availableData` chunks is delivered intact.
            var buffer = ""
            while true {
                let data = fh.availableData
                if data.isEmpty {
                    // EOF — flush any unterminated final line.
                    if !buffer.isEmpty {
                        await self?.handleLine(buffer, for: projectID, generation: gen)
                    }
                    break
                }
                guard let chunk = String(data: data, encoding: .utf8) else { continue }
                buffer.append(chunk)
                while let nl = buffer.firstIndex(of: "\n") {
                    let line = String(buffer[..<nl])
                    buffer = String(buffer[buffer.index(after: nl)...])
                    if !line.isEmpty {
                        await self?.handleLine(line, for: projectID, generation: gen)
                    }
                }
            }
        }

        proc.terminationHandler = { [weak self] p in
            let status = p.terminationStatus
            Task { @MainActor in
                self?.handleTermination(
                    projectID: projectID, status: status, generation: gen
                )
            }
        }

        do {
            try proc.run()
            currentProcess = proc
            // Tiny race here: if the app crashes between proc.run() returning
            // and writePIDFile completing, the orphan exists but is
            // unattachable on next launch. Window is single-process-spawn
            // wide (~ms); accepted rather than working around it with a
            // separate `lsof`-style argv sweep on launch.
            Self.writePIDFile(for: project, pid: proc.processIdentifier)
            Self.logger.info(
                "spawned bristlenose run project=\(projectID.uuidString, privacy: .public) pid=\(proc.processIdentifier, privacy: .public)"
            )
        } catch {
            currentlyRunning = nil
            currentProject = nil
            currentProcess = nil
            currentReadTask?.cancel()
            currentReadTask = nil
            state[projectID] = .failed(
                "Failed to launch: \(error.localizedDescription)",
                category: .unknown
            )
            startNextQueued()
        }
    }

    private func handleLine(_ line: String, for projectID: UUID, generation gen: Int) {
        // Drop lines from a stale generation — the terminationHandler from a
        // previous run can fire after we've spawned the next one.
        guard gen == generation else { return }

        let clean = BristlenoseShared.stripANSI(line)
        liveData.appendOutput(clean, for: projectID)

        liveData.mutateProgress(for: projectID) { p in
            currentParser.consume(clean, into: &p)
        }
    }

    private func handleTermination(projectID: UUID, status: Int32, generation gen: Int) {
        guard gen == generation else { return }

        if let project = projectIndex?.projects.first(where: { $0.id == projectID }) {
            Self.removePIDFile(for: project)
        }
        currentProcess = nil
        currentReadTask?.cancel()
        currentReadTask = nil
        currentlyRunning = nil
        currentProject = nil

        if status == 0 {
            state[projectID] = .ready(Date())
            Self.logger.info(
                "run succeeded project=\(projectID.uuidString, privacy: .public)"
            )
        } else if cancellationRequested {
            cancellationRequested = false
            state[projectID] = .idle
            Self.logger.info(
                "run cancelled project=\(projectID.uuidString, privacy: .public)"
            )
        } else {
            let lines = liveData.snapshotOutput(for: projectID)
            let projectName = projectIndex?.projects
                .first(where: { $0.id == projectID })?.name
            let category = Self.categoriseFailure(
                lines: lines, exitStatus: status, projectName: projectName
            )
            let summary = Self.humanSummary(for: category)
            state[projectID] = .failed(summary, category: category)
            Self.logger.warning(
                """
                run failed project=\(projectID.uuidString, privacy: .public) \
                status=\(status) category=\(category.rawValue, privacy: .public)
                """
            )
        }

        startNextQueued()
    }

    private func startNextQueued() {
        guard !queue.isEmpty else { return }
        let nextID = queue.removeFirst()
        renumberQueue()

        guard let index = projectIndex,
              let project = index.projects.first(where: { $0.id == nextID }) else {
            // Index not wired or project disappeared — keep the ID visible as
            // queued so we don't silently drop the user's request, and log so
            // a missing setProjectIndex() call shows up.
            Self.logger.error(
                "startNextQueued: no projectIndex or project=\(nextID.uuidString, privacy: .public) missing — leaving queued"
            )
            queue.insert(nextID, at: 0)
            renumberQueue()
            return
        }
        spawn(project: project)
    }

    // MARK: - Queue management

    private func renumberQueue() {
        for (offset, id) in queue.enumerated() {
            state[id] = .queued(position: offset + 1)
        }
    }

    // MARK: - Failure categorisation

    /// Regex-based mapping from stderr tail + exit status to a
    /// `PipelineFailureCategory`. Keep heuristics here so display code stays
    /// category-only.
    static func categoriseFailure(
        lines: [String], exitStatus: Int32, projectName: String? = nil
    ) -> PipelineFailureCategory {
        var tail = lines.suffix(50).joined(separator: "\n").lowercased()
        // Strip the project name so "401-bug-repro" or "Whisper Test" can't
        // hijack the categoriser via filename echo.
        if let name = projectName?.lowercased(), !name.isEmpty {
            tail = tail.replacingOccurrences(of: name, with: "")
        }

        if matches(tail, #"401|invalid api key|authentication"#) { return .auth }
        if matches(tail, #"rate limit|quota|insufficient_quota|429"#) { return .quota }
        if matches(tail, #"connection refused|timed out|dns|could not resolve"#) {
            return .network
        }
        if matches(tail, #"no space|enospc|disk full"#) { return .disk }
        if matches(tail, #"whisper|faster_whisper|(speech )?model"#) { return .whisper }
        return .unknown
    }

    static func humanSummary(for category: PipelineFailureCategory) -> String {
        switch category {
        case .auth:    return "Your LLM provider key isn't working."
        case .network: return "Couldn't reach the LLM provider."
        case .quota:   return "LLM provider rate limit reached."
        case .disk:    return "Not enough disk space to finish."
        case .whisper: return "Transcription failed — the speech model didn't load."
        case .unknown: return "Something went wrong during analysis."
        }
    }

    private static func matches(_ haystack: String, _ pattern: String) -> Bool {
        haystack.range(of: pattern, options: .regularExpression) != nil
    }

    // MARK: - Consent

    /// Mirror of `ContentView.hasConsent` — same UserDefaults key the AppStorage
    /// property wraps. Pipeline guard is defence-in-depth; the real gate is
    /// the modal-blocking AIConsentView sheet.
    private static var hasAIConsent: Bool {
        UserDefaults.standard.integer(forKey: "aiConsentVersion")
            >= AIConsentView.currentVersion
    }
}
