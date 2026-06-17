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
    // Phase 1f Slice 4 — additive. Names match Python `CauseCategoryEnum`
    // exactly (snake_case round-trips through `String` rawValue). No
    // existing case is renamed — the Swift/Python boundary is contractually
    // stable. See docs/design-pipeline-resilience.md §"Cross-boundary naming".
    case userSignal = "user_signal"
    case apiRequest = "api_request"
    case apiServer = "api_server"
    case missingDep = "missing_dep"
    case missingInput = "missing_input"
    case missingBinary = "missing_binary"
    /// CLI refused to re-run because `bristlenose-output/` already exists.
    /// Distinct from a real failure — the *project* is fine, the *attempt
    /// to re-analyse* was blocked. UX surfaces this with a "Re-analyse
    /// (replaces existing output)" CTA that spawns with `--clean`.
    case outputExists = "output_exists"
    /// Quote extraction produced more output than the model's cap allows,
    /// even after the pipeline split the session into smaller chunks.
    /// Recovery is a larger-output model or manual pre-segmentation.
    case outputTruncated = "output_truncated"
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
    /// Determinate ring fill in [0, asymptote cap], or nil for the
    /// indeterminate spinner (uncalibrated first run before any measured
    /// signal). Populated from `run_progress` events via `RunProgressMath`,
    /// already monotonic + asymptote-clamped so the view renders it directly.
    var ringFraction: Double?
    /// Stage id + ETA from the event. `predictedTotalSeconds` feeds the
    /// time-based ring fill; `stage` / `etaRemainingSeconds` are stored for the
    /// deferred subtitle text ("Transcribing · 7 of 8 · ~1 min left" — the text
    /// tier is the next piece). Not yet rendered.
    var stage: String?
    var etaRemainingSeconds: Double?
    var predictedTotalSeconds: Double?
    var elapsed: TimeInterval = 0
    var lastLine: String = ""
    var startedAt: Date = Date()
    /// True when this run was attached from an existing PID at app
    /// launch (orphan recovery), false for runs we spawned ourselves.
    /// Drives popover copy ("Resuming…" vs "Starting up…") and lets
    /// the orphan poll task tail the log file off disk for the
    /// technical-details surface.
    var attachedFromOrphan: Bool = false
    /// True between the user clicking Stop and the subprocess
    /// actually exiting. Lets the pill / popover acknowledge the
    /// click immediately ("Stopping…", disabled button) so the user
    /// doesn't keep clicking Stop while SIGINT/SIGTERM/SIGKILL play
    /// out (can take 1–8s on a wedged subprocess).
    var isStopping: Bool = false
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
    /// A `transcribe-only` run completed cleanly — transcripts present,
    /// no analysis. Phase 1f Slice 4 — surface "Continue (analyse)".
    /// `stagesComplete` derived from the manifest at display time.
    case partial(kind: String, stagesComplete: [String])
    /// User cancelled the prior run via SIGINT/SIGTERM. Resume / Re-analyse…
    /// `stagesComplete` derived from the manifest at display time.
    case stopped(stagesComplete: [String])
    /// `run_completed` terminus AND ≥1 session failed in some stage. A
    /// report was written but at reduced fidelity. Pill + popover surface
    /// the per-stage breakdown via `PipelineSummary`.
    /// See `docs/design-pipeline-diagnostic-popover.md`.
    case completedPartial(summary: PipelineSummary)
    /// `run_failed` terminus with a populated `summary` (A4-stage-cache-
    /// honesty cohort onward). The run was abandoned mid-pipeline; no
    /// usable report on disk. Distinct from `.failed`, which is the older
    /// summary-less path retained for forwards-compat with logs from
    /// before the summary started landing on failures.
    case failedWithDiagnostic(summary: PipelineSummary)
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

    #if DEBUG
    /// Debug-only state override for the diagnostic-popover fixture harness.
    /// Used by `_applyDebugFixture(to:)` (called from `ContentView`). Not
    /// compiled into Release builds.
    func _debugSetState(_ state: PipelineState, for projectID: UUID) {
        self.state[projectID] = state
    }

    /// Debug-only: apply fixture override for one project (called from
    /// ContentView when the selection changes). Idempotent per project.
    private var _debugFixtureApplied = Set<UUID>()
    func _applyDebugFixture(to projectID: UUID) {
        guard !_debugFixtureApplied.contains(projectID) else { return }
        let result = DiagnosticFixture.loadIfEnabled()
        switch result {
        case .none, .clean:
            return
        case .partial(let s):
            self.state[projectID] = .completedPartial(summary: s)
        case .failed(let s):
            self.state[projectID] = .failedWithDiagnostic(summary: s)
        case .noSummary(let message, let category):
            // We just inject the state here. The deleted toolbar pill used to
            // write a synthetic log for this path so its popover could show
            // "Show Log"; with the pill gone no synthetic log is written, so
            // the `failed_no_summary` debug scenario's popover omits Show Log
            // (the button is gated on a real log file existing). Acceptable —
            // debug-only path; real runs always have a log.
            self.state[projectID] = .failed(message, category: category)
        case .simpleState(let injected):
            self.state[projectID] = injected
        }
        _debugFixtureApplied.insert(projectID)
    }
    #endif

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

    /// Phase 0b: per-project task polling `pipeline-events.jsonl` for
    /// `run_progress` while a run is live, so the determinate ring updates
    /// during quiet stages (a long transcription emits little stdout).
    /// Populates the ring only — run *exit* is detected by
    /// `terminationHandler` / the orphan `kill` poll, so this task never
    /// decides liveness (which is why no separate "liveness floor" is needed).
    private var progressPollTasks: [UUID: Task<Void, Never>] = [:]

    /// Byte offset into `<output>/.bristlenose/bristlenose.log` for each
    /// orphan-attached project. The poll task seeks here and reads new
    /// bytes only — avoids re-streaming the whole log on every 2s tick.
    /// Cleared in `handleOrphanExit`.
    private var orphanLogOffsets: [UUID: UInt64] = [:]

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

    /// Terminal stage name in the Python pipeline. Must match
    /// `bristlenose/manifest.py` `STAGE_RENDER` — the last entry of
    /// `STAGE_ORDER`. Load-bearing: presence of this stage in a manifest
    /// is the canonical "pipeline finished" signal for `parseManifest`.
    private static let terminalStage = "render"

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

        // Pre-set .scanning so the sidebar row has a defined state during the
        // off-main manifest read. Callers other than `scanAllProjects` (e.g.
        // post-drop ingest of an already-analysed folder) skip the launch-
        // time scan and would otherwise leave state[projectID] = nil during
        // the async hop — invisible on local SSD but multi-second on a slow
        // disk / network mount. Idempotent: scanAllProjects already does the
        // same nil-check before calling scan, so this is a no-op there.
        if state[projectID] == nil {
            state[projectID] = .scanning
        }

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
    /// Start the events-file progress poll for a spawned run (Phase 0b). Reads
    /// the newest `run_progress` off-main every ~1s and folds it into the ring
    /// via `RunProgressMath`. Guarded by `generation` so a superseded run's
    /// poll exits; cancelled in `handleTermination`.
    private func startProgressPoll(for project: Project, generation gen: Int) {
        let projectID = project.id
        let eventsURL = Self.eventsURL(for: project)
        progressPollTasks[projectID]?.cancel()
        progressPollTasks[projectID] = Task { @MainActor [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                guard let self, self.generation == gen else { return }
                await self.applyEventProgress(from: eventsURL, for: projectID)
            }
        }
    }

    /// Read the newest `run_progress` event off-main and fold it into the
    /// project's `PipelineProgress` (ring fill + counts + ETA). No-op until the
    /// first progress line lands (→ the indicator keeps the spinner). Shared by
    /// the spawned-run poll and the orphan poll.
    private func applyEventProgress(from eventsURL: URL, for projectID: UUID) async {
        // Read the newest progress AND the current run's id (the newest
        // run_started) in one detached hop. The events file is append-only —
        // NOT truncated on resume — so the newest progress line could belong to
        // the *previous* run (e.g. during the new run's 30–60s model load before
        // it emits anything). Gate on run_id so a stale prior-run line can't
        // drive the ring (it would otherwise jump it to ~97%). Works for both
        // spawned and orphan-attach paths — the current run's run_started is
        // always the newest lifecycle event while the run is live.
        let (event, currentRunId) = await Task.detached {
            (EventLogReader.latestProgress(at: eventsURL),
             EventLogReader.tailEvent(at: eventsURL)?.runId)
        }.value
        guard let event, event.runId == currentRunId,
              let current = liveData.progress[projectID] else { return }
        let updated = RunProgressMath.apply(
            stage: event.stage,
            sessionsComplete: event.sessionsComplete,
            sessionsTotal: event.sessionsTotal,
            stageFraction: event.stageFraction,
            etaRemainingSeconds: event.etaRemainingSeconds,
            predictedTotalSeconds: event.predictedTotalSeconds,
            to: current,
            startedAt: current.startedAt,
            now: Date()
        )
        // Only publish on a real change — avoids waking every observing sidebar
        // row at 1 Hz when nothing moved (Finding 10).
        if updated != current {
            liveData.setProgress(updated, for: projectID)
        }
    }

    private func attachOrphan(project: Project, pid: pid_t) {
        guard attachedOrphanPIDs[project.id] == nil else { return }
        Self.logger.info(
            "attaching to orphan project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
        )
        attachedOrphanPIDs[project.id] = pid
        state[project.id] = .running
        var initial = PipelineProgress(startedAt: Date())
        initial.attachedFromOrphan = true
        liveData.setProgress(initial, for: project.id)
        liveData.clearOutput(for: project.id)
        // Start at end-of-file so we don't dump the entire prior-run log
        // into the popover. Subsequent polls only surface lines written
        // after we attached.
        let logURL = Self.logFileURL(for: project)
        if let attrs = try? FileManager.default.attributesOfItem(
            atPath: logURL.path
        ), let size = attrs[.size] as? UInt64 {
            orphanLogOffsets[project.id] = size
        } else {
            orphanLogOffsets[project.id] = 0
        }

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

                // Tail the CLI log file off disk so the popover technical
                // details has real progress lines, not "Polling…" placeholder.
                let priorOffset = self.orphanLogOffsets[projectID] ?? 0
                let (newLines, newOffset) = await Task.detached {
                    Self.readLogTail(url: logURL, offset: priorOffset)
                }.value
                if !newLines.isEmpty {
                    self.orphanLogOffsets[projectID] = newOffset
                    for line in newLines {
                        // Same redaction as handleLine — the on-disk CLI log can
                        // carry a key-shaped echo, and this feeds the same
                        // clipboard-copyable popover buffer.
                        self.liveData.appendOutput(
                            BristlenoseShared.redactKeys(in: line), for: projectID
                        )
                    }
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
                self.liveData.mutateProgress(for: projectID) { p in
                    p.elapsed = Date().timeIntervalSince(p.startedAt)
                    if let last = newLines.last {
                        p.lastLine = last
                    }
                }

                // Phase 0b: fold the newest run_progress into the ring too.
                await self.applyEventProgress(
                    from: Self.eventsURL(for: project), for: projectID
                )
            }
        }
        orphanPollTasks[project.id] = task
    }

    private func handleOrphanExit(projectID: UUID, project: Project) {
        attachedOrphanPIDs[projectID] = nil
        orphanPollTasks[projectID]?.cancel()
        orphanPollTasks[projectID] = nil
        orphanLogOffsets[projectID] = nil
        Self.removePIDFile(for: project)

        // Drop out of .running so the manifest re-read can settle the
        // final state. applyScanResult guards against overwriting
        // .running (passive scans must not clobber active runs), but
        // handleOrphanExit IS the "run is over" signal — without this
        // transition, the pill stays "Running" after the subprocess
        // dies and the user thinks Stop didn't take.
        if case .running = state[projectID] {
            state[projectID] = .idle
        }

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
        case .running, .queued, .stopped, .partial, .failed,
             .completedPartial, .failedWithDiagnostic:
            // .running/.queued: live state owned by the runner, not the manifest.
            // .stopped / .partial: terminal runner-owned states (user cancelled,
            // or transcribe-only completed) — a passive manifest re-scan must
            // not flicker them, which would jitter the sidebar activity glyphs.
            // .failed / .completedPartial / .failedWithDiagnostic: a stale
            // manifest must not erase a fresh diagnostic summary (and its
            // Retry / Copy / Email CTAs) just because the prior run wrote
            // .ready before crashing — or because the debug-fixture harness
            // just injected a synthesized diagnostic for visual evaluation.
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

    /// Location of a project's CLI log. Per CLAUDE.md "Logging" — the
    /// CLI writes INFO-level lines here regardless of `-v`. We tail
    /// this on the orphan-attach path (no stdout to parse).
    static func logFileURL(for project: Project) -> URL {
        URL(fileURLWithPath: project.path)
            .appendingPathComponent("bristlenose-output")
            .appendingPathComponent(".bristlenose")
            .appendingPathComponent("bristlenose.log")
    }

    /// Location of a project's run-event log (`pipeline-events.jsonl`). The
    /// `run_progress` lines here drive the determinate ring (Phase 0b).
    static func eventsURL(for project: Project) -> URL {
        URL(fileURLWithPath: project.path)
            .appendingPathComponent("bristlenose-output")
            .appendingPathComponent(".bristlenose")
            .appendingPathComponent(EventLogReader.filename)
    }

    /// Read new bytes from `url` starting at `offset`, return `(lines,
    /// newOffset)`. Returns empty + same offset if file missing or
    /// unchanged. Off-main: pure I/O, no actor state. Capped at 64 KB
    /// per read so a misbehaving log can't block the poll task — older
    /// runs that produced megabytes of log are caught up over many polls.
    nonisolated static func readLogTail(
        url: URL, offset: UInt64
    ) -> (lines: [String], newOffset: UInt64) {
        guard let handle = try? FileHandle(forReadingFrom: url) else {
            return ([], offset)
        }
        defer { try? handle.close() }
        guard let endOffset = try? handle.seekToEnd(), endOffset > offset else {
            return ([], offset)
        }
        let readFrom = max(offset, endOffset > 65_536 ? endOffset - 65_536 : 0)
        guard (try? handle.seek(toOffset: readFrom)) != nil else {
            return ([], offset)
        }
        let data = (try? handle.readToEnd()) ?? Data()
        guard let text = String(data: data, encoding: .utf8) else {
            return ([], endOffset)
        }
        let lines = text
            .split(whereSeparator: { $0 == "\n" || $0 == "\r" })
            .map { String($0) }
            .filter { !$0.isEmpty }
        return (lines, endOffset)
    }

    /// Read a manifest file with a hard timeout. Maps to a `PipelineState`:
    /// - file missing → `.idle`
    /// - terminal `render` stage present and `complete`, all other present
    ///   stages also `complete` → `.ready(completed_at)`
    /// - any stage non-`complete`, OR `render` stage absent → `.idle` (run
    ///   was interrupted before finishing; the manifest is written
    ///   incrementally so absence of the last stage is the canonical
    ///   "pipeline never finished" signal — see manifest.py STAGE_ORDER)
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

    /// Read `stages` from the manifest and return names of those marked complete.
    /// Derive stages-complete from a parsed manifest dict. Used to compute
    /// `stagesComplete` for `.partial` and `.stopped` states (the events log
    /// doesn't store this — manifest is the single source of truth for stage
    /// state per the design doc).
    nonisolated static func stagesCompleteFromStages(_ stages: [String: Any]) -> [String] {
        var out: [String] = []
        for (name, raw) in stages {
            guard let stage = raw as? [String: Any],
                  let status = stage["status"] as? String,
                  status == "complete" else {
                continue
            }
            out.append(name)
        }
        return out.sorted()
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

        // Read manifest once and reuse for both the events-log and fallback
        // paths — avoids a duplicate Data(contentsOf:) when 50 sidebar
        // projects scan in parallel at launch.
        let manifestData: Data
        let stages: [String: Any]
        do {
            manifestData = try Data(contentsOf: url)
            guard let json = try JSONSerialization.jsonObject(with: manifestData)
                    as? [String: Any],
                  let parsedStages = json["stages"] as? [String: Any] else {
                return .unreachable(reason: "Project file is damaged.")
            }
            stages = parsedStages
        } catch {
            return .unreachable(reason: "Can't read this project.")
        }

        // Phase 1f Slice 4 — prefer the events log when present. Falls back
        // to the strict manifest inference below for projects that predate
        // the events log (backward compatibility).
        let dotBristlenose = url.deletingLastPathComponent()
        let eventsURL = dotBristlenose.appendingPathComponent(EventLogReader.filename)
        let pidURL = dotBristlenose.appendingPathComponent(EventLogReader.pidFilename)
        if fm.fileExists(atPath: eventsURL.path) {
            let stagesComplete = stagesCompleteFromStages(stages)
            if let derived = EventLogReader.deriveState(
                eventsURL: eventsURL,
                pidURL: pidURL,
                stagesComplete: stagesComplete,
            ) {
                return derived
            }
            // Events log present but unreadable — fall through to strict
            // manifest inference rather than block the user.
        }

        var latestCompleted: Date?
        var renderComplete = false
        for (name, raw) in stages {
            guard let stage = raw as? [String: Any],
                  let status = stage["status"] as? String else {
                return .idle
            }
            if status != "complete" {
                return .idle
            }
            if name == Self.terminalStage {
                renderComplete = true
            }
            if let ts = stage["completed_at"] as? String,
               let date = Self.iso8601.date(from: ts) {
                if latestCompleted == nil || date > latestCompleted! {
                    latestCompleted = date
                }
            }
        }

        guard renderComplete else { return .idle }
        return .ready(latestCompleted ?? Date())
    }

    // MARK: - Public API

    /// Request a pipeline run for `project`. If nothing is running, spawns
    /// immediately; otherwise enqueues.
    ///
    /// Consent guard is defence-in-depth — the primary enforcement is the
    /// non-dismissable `AIConsentView` sheet in ContentView. The `hasAIConsent`
    /// guard below runs BEFORE the subprocess environment is built, so no API
    /// key is injected without consent (and Ollama/keyless providers inject
    /// nothing at all). Don't lean on "the key lives in Keychain behind a
    /// prompt" — under App Sandbox the host injects the key as an env var, so
    /// the guard ordering is the real backstop, not a Keychain dialog.
    /// Start a `bristlenose run` for this project.
    ///
    /// - Parameter clean: when true, pass `--clean` to the CLI, which deletes
    ///   `bristlenose-output/` before running. Used by the `outputExists`
    ///   re-analyse CTA in the failed-popover. Destructive — caller must
    ///   confirm with the user first. Default false.
    func start(project: Project, clean: Bool = false) {
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
            spawn(project: project, clean: clean)
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
        // Acknowledge the click immediately on the UI so the user
        // doesn't keep mashing Stop while signals propagate.
        liveData.mutateProgress(for: project.id) { p in
            p.isStopping = true
        }
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
                //
                // Schedule signal escalation: SIGINT alone won't cut
                // through whisper/torch model loads (Python signal
                // handler can only run between bytecodes, blocked
                // during long C calls). At 5s escalate to SIGTERM, at
                // 8s SIGKILL — the user's "Stop" must always succeed.
                scheduleOrphanCancelEscalation(pid: pid, projectID: project.id)
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

    /// Escalate from SIGINT to SIGTERM to SIGKILL if the orphan won't
    /// die. Whisper / torch / ctranslate2 hold the GIL during long C
    /// calls, so a Python signal handler can be deferred 30–60s during
    /// model load. The user clicked Stop; their contract is "this
    /// stops". Bail out at any step if the PID is already dead or the
    /// attach has changed (project was re-cancelled with a new run, or
    /// orphan poll task already ran handleOrphanExit).
    private func scheduleOrphanCancelEscalation(pid: pid_t, projectID: UUID) {
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(5))
            guard let self else { return }
            guard kill(pid, 0) == 0 else { return }
            guard self.attachedOrphanPIDs[projectID] == pid else { return }
            kill(pid, SIGTERM)
            Self.logger.warning(
                "SIGTERM escalation pid=\(pid, privacy: .public) project=\(projectID.uuidString, privacy: .public) — SIGINT didn't take in 5s"
            )

            try? await Task.sleep(for: .seconds(3))
            guard kill(pid, 0) == 0 else { return }
            guard self.attachedOrphanPIDs[projectID] == pid else { return }
            kill(pid, SIGKILL)
            Self.logger.error(
                "SIGKILL escalation pid=\(pid, privacy: .public) project=\(projectID.uuidString, privacy: .public) — SIGTERM didn't take in 3s"
            )
        }
    }

    // MARK: - Spawn

    /// Spawn the subprocess. When `clean` is true, `--clean` is added — used
    /// by the Re-analyse CTA on `outputExists` failures. Queued spawns
    /// (`startNextQueued`) don't preserve the flag; the queue + Re-analyse
    /// interaction is a follow-up if it surfaces.
    private func spawn(project: Project, clean: Bool = false) {
        // Resolve the sidecar binary the same way ServeManager does. Three
        // shapes of failure: external-server scheme has no binary to spawn,
        // resolver itself can fail (bundle missing, dev path invalid), and
        // both surface as `.failed` state on the project so the GUI shows
        // something actionable.
        let binary: URL
        let resolvedMode: SidecarMode
        #if DEBUG
        let externalPortRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_EXTERNAL_PORT"]
        let sidecarPathRaw = ProcessInfo.processInfo.environment["BRISTLENOSE_DEV_SIDECAR_PATH"]
        #else
        let externalPortRaw: String? = nil
        let sidecarPathRaw: String? = nil
        #endif
        // TODO: `.unknown` is the wrong category for both branches below — the
        // external-scheme path is a developer config error, the resolver-failure
        // path is bundle/environment. No fitting case in `PipelineFailureCategory`
        // today; revisit when the enum next grows (or a third miscategorised
        // call site appears).
        let resolved = SidecarMode.resolve(
            externalPortRaw: externalPortRaw,
            sidecarPathRaw: sidecarPathRaw,
            bundleResourceURL: Bundle.main.resourceURL
        )
        switch resolved {
        case .success(let mode):
            switch mode {
            case .bundled(let path), .devSidecar(let path):
                binary = path
                resolvedMode = mode
                Self.logger.info(
                    "spawn binary resolved: \(mode.logDescription, privacy: .public) project=\(project.id.uuidString, privacy: .public)"
                )
            case .external:
                let message = "Pipeline runs can't use the external-server dev mode. Unset BRISTLENOSE_DEV_EXTERNAL_PORT (or use BRISTLENOSE_DEV_SIDECAR_PATH instead) and try again."
                Self.logger.error(
                    "spawn refused: external-server scheme has no binary project=\(project.id.uuidString, privacy: .public)"
                )
                state[project.id] = .failed(message, category: .unknown)
                return
            }
        case .failure(let err):
            Self.logger.error(
                "spawn binary resolve failed: \(err.localizedDescription, privacy: .public) project=\(project.id.uuidString, privacy: .public)"
            )
            state[project.id] = .failed(err.localizedDescription, category: .unknown)
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
        startProgressPoll(for: project, generation: gen)

        let proc = Process()
        proc.executableURL = binary
        // --no-serve makes `bristlenose run` exit after the pipeline completes
        // instead of auto-starting a serve and waiting for Ctrl-C. Without it
        // the subprocess never terminates → terminationHandler never fires →
        // state stays .running indefinitely (QA, 20 Apr 2026). The desktop's
        // ServeManager.start() runs the serve on the Mac side separately, per
        // the plan's "pipeline first, then serve" policy. (Pre-A3 the same
        // flag was spelled `--static` and conflated with the static-render
        // surface; A3 dropped `--static` and kept `--no-serve` as the honest
        // hidden flag — see bristlenose/cli.py.)
        var args = ["run", project.path, "--no-serve"]
        if clean { args.append("--clean") }
        proc.arguments = args
        // Complete subprocess environment — minimal var allowlist, prefs, TLS
        // certs, bundled FFmpeg/ffprobe, the active provider's API key, and the
        // `_BRISTLENOSE_HOSTED_BY_DESKTOP` host-gate handshake (read by
        // desktop/sidecar_entry.py — third-party callers of the bundled binary
        // don't set it; we do). Single source of truth shared with ServeManager
        // so the two spawn sites can't drift. The run path historically omitted
        // the API-key overlay here, which broke `bristlenose run` under App
        // Sandbox (Python can't read Keychain itself). See
        // BristlenoseShared.childEnvironment.
        proc.environment = BristlenoseShared.childEnvironment(for: resolvedMode)

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
                await self?.handleTermination(
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
        // Redact key-shaped substrings before buffering — this buffer is shown
        // in the diagnostic popover and copied by "Copy error details", so a
        // Python-side key echo (pydantic SecretStr in a traceback, SDK debug
        // line) must not ferry the injected BRISTLENOSE_*_API_KEY out via the
        // clipboard / a pasted bug report. Mirrors ServeManager.handleLine.
        liveData.appendOutput(BristlenoseShared.redactKeys(in: clean), for: projectID)

        // Parser consumes the unredacted line — progress markers (`✓ stage`)
        // never contain key-shaped substrings, and redaction could corrupt them.
        liveData.mutateProgress(for: projectID) { p in
            currentParser.consume(clean, into: &p)
        }
    }

    private func handleTermination(
        projectID: UUID, status: Int32, generation gen: Int
    ) async {
        guard gen == generation else { return }

        let project = projectIndex?.projects.first(where: { $0.id == projectID })
        if let project {
            Self.removePIDFile(for: project)
        }
        currentProcess = nil
        currentReadTask?.cancel()
        currentReadTask = nil
        progressPollTasks[projectID]?.cancel()
        progressPollTasks[projectID] = nil
        currentlyRunning = nil
        currentProject = nil
        // NOTE: state[projectID] stays `.running` until the manifest-read
        // await below resolves. cancel() guards on `proc.isRunning`, so a
        // Stop click during this window is a clean no-op (no signal sent,
        // no crash). The spinner-into-the-void is a sub-5s papercut on
        // slow disks; flipping to a transient state here would race with
        // any concurrent passive sidebar scan that preserves .running.

        // Cancellation only takes effect on a non-zero exit — if the sidecar
        // raced the cancel and finished cleanly anyway, we keep the result.
        if status != 0, cancellationRequested {
            cancellationRequested = false
            state[projectID] = .idle
            Self.logger.info(
                "run cancelled project=\(projectID.uuidString, privacy: .public)"
            )
            startNextQueued()
            return
        }

        let lines = status == 0 ? [] : liveData.snapshotOutput(for: projectID)
        // looksLikeSuccess on a non-zero exit is a *trigger to re-derive*,
        // not a verdict. (Sidecar exits 1 after SIGINT even on a clean run
        // — uvicorn graceful shutdown.) Combine with exit-0 into a single
        // "sidecar believes it succeeded" signal; the pure decision function
        // below picks the right final state from disk evidence.
        let sidecarReportedSuccess = (status == 0) || Self.looksLikeSuccess(lines: lines)

        let derived: PipelineState
        if sidecarReportedSuccess {
            derived = await resolveTerminationState(
                projectID: projectID, project: project
            )
            guard gen == generation else { return }
        } else {
            // Non-zero exit + no success markers — skip the disk read.
            derived = .idle
        }

        let decision = Self.decideTermination(
            exitStatus: status,
            sidecarReportedSuccess: sidecarReportedSuccess,
            derived: derived
        )

        switch decision {
        case .accept(let final):
            state[projectID] = final
            if case .ready = final {
                Self.logger.info(
                    """
                    run succeeded project=\(projectID.uuidString, privacy: .public) \
                    status=\(status)
                    """
                )
            }
        case .treatAsFailure:
            state[projectID] = deriveFailureState(
                projectID: projectID, project: project,
                status: status, lines: lines
            )
        }

        startNextQueued()
    }

    /// Pure decision: given exit status + log-marker result + the
    /// derived-from-disk state, what should the runner write?
    ///
    /// Extracted from `handleTermination` to make the branch table
    /// unit-testable without standing up a full `PipelineRunner` harness.
    /// No I/O, no actor state — caller computes `derived` (async) and
    /// passes it in.
    ///
    /// **Honesty invariant:** `.ready` is only ever returned when disk
    /// derivation confirmed `.ready`. Exit code 0 alone is never sufficient.
    enum TerminationDecision: Equatable {
        case accept(PipelineState)   // write this state directly
        case treatAsFailure          // caller categorises via deriveFailureState
    }

    nonisolated static func decideTermination(
        exitStatus: Int32,
        sidecarReportedSuccess: Bool,
        derived: PipelineState
    ) -> TerminationDecision {
        if sidecarReportedSuccess {
            // Sidecar said it worked. Trust the disk derivation:
            //   .ready  → accept (real success)
            //   .idle/.partial/.stopped → accept (botched run, honest signal)
            //   .unreachable → accept (slow disk; sidebar will self-correct
            //                  on next passive scan)
            // When exit was non-zero AND log markers passed but disk says
            // not-ready, that's a real failure (log markers lied) — fall
            // through to categorisation rather than write a misleading state.
            if case .ready = derived {
                return .accept(derived)
            }
            if exitStatus == 0 {
                return .accept(derived)
            }
            return .treatAsFailure
        }
        return .treatAsFailure
    }

    /// Read the post-termination disk state. Thin wrapper around
    /// `readManifestState` that also logs a warning if the sidecar claimed
    /// success but the manifest doesn't confirm — a Python-side bug to chase.
    ///
    /// Timeout is 5s (vs 2s on the passive scan path): termination runs once
    /// per run completion, and 2s lost to a successful-but-slow disk would
    /// flip exit-0 to `.unreachable` for users with audio on network shares.
    private func resolveTerminationState(
        projectID: UUID, project: Project?
    ) async -> PipelineState {
        guard let project else { return .idle }
        let url = Self.manifestURL(for: project)
        let derived = await Self.readManifestState(
            at: url, timeout: .seconds(5)
        )
        if case .ready = derived {
            return derived
        }
        Self.logger.warning(
            """
            sidecar reported success but manifest derivation did not \
            confirm ready project=\(projectID.uuidString, privacy: .public) \
            derived=\(String(describing: derived), privacy: .public)
            """
        )
        return derived
    }

    /// Categorise a non-zero exit into `.failed(summary, category:)`. Extracted
    /// so both the "log-tail says success but manifest disagrees" path and the
    /// original "log-tail also looks bad" path can share this logic.
    private func deriveFailureState(
        projectID: UUID, project: Project?,
        status: Int32, lines: [String]
    ) -> PipelineState {
        // Prefer the structured cause emitted by the Python abandon path
        // (`pipeline-events.jsonl` → `run_failed` → `cause.{category,message}`).
        // Stdout regex is a best-effort fallback for older Python versions
        // and crash-style failures that exit before writing a terminus event.
        let derived = project.flatMap { Self.deriveFailureFromEvents(project: $0) }
        // The run used whatever provider was active when it spawned; unless the
        // user switched since exit (rare, and harmless), that's still the live
        // `activeProvider`. Same source `overlayAPIKeys` reads at spawn time.
        let activeProvider = UserDefaults.standard.string(forKey: "activeProvider")
            .flatMap(LLMProvider.init(rawValue:))
        let category: PipelineFailureCategory
        let summary: String
        if let (cat, msg) = derived {
            category = cat
            summary = msg ?? Self.humanSummary(for: cat, provider: activeProvider)
        } else {
            category = Self.categoriseFailure(
                lines: lines, exitStatus: status, projectName: project?.name
            )
            summary = Self.humanSummary(for: category, provider: activeProvider)
        }
        Self.logger.warning(
            """
            run failed project=\(projectID.uuidString, privacy: .public) \
            status=\(status) category=\(category.rawValue, privacy: .public)
            """
        )
        // Persist the (already key-redacted) stderr tail so a mislabelled
        // category isn't the only forensic trace. The classifier is a guess;
        // this file is the ground truth. Greppable at
        // `<output>/.bristlenose/last-run-failure.log`.
        if let project, !lines.isEmpty {
            Self.captureFailureLog(
                project: project, status: status, category: category, lines: lines
            )
        }
        return .failed(summary, category: category)
    }

    /// Write the redacted stderr tail of a failed run to
    /// `bristlenose-output/.bristlenose/last-run-failure.log` and emit the tail
    /// to the unified log. Best-effort — never throws into the failure path.
    private static func captureFailureLog(
        project: Project, status: Int32,
        category: PipelineFailureCategory, lines: [String]
    ) {
        let tail = lines.suffix(50).joined(separator: "\n")
        Self.logger.error(
            """
            failure stderr tail category=\(category.rawValue, privacy: .public) \
            status=\(status):
            \(tail, privacy: .private)
            """
        )
        // Path mirrors the default output location. The desktop host never
        // passes `--output`, so `bristlenose-output/.bristlenose` is always the
        // real run dir; if a caller ever relocates output, derive this from
        // OutputPaths instead of hardcoding.
        let dir = URL(fileURLWithPath: project.path)
            .appendingPathComponent("bristlenose-output")
            .appendingPathComponent(".bristlenose")
        let header = "category=\(category.rawValue) status=\(status)\n"
        do {
            try FileManager.default.createDirectory(
                at: dir, withIntermediateDirectories: true
            )
            try (header + tail + "\n").write(
                to: dir.appendingPathComponent("last-run-failure.log"),
                atomically: true, encoding: .utf8
            )
        } catch {
            // Don't fail the failure path — but don't swallow silently either.
            // The tail is in the unified log above, so the forensic file
            // failing to write is greppable rather than invisible.
            Self.logger.warning(
                "captureFailureLog: could not write last-run-failure.log: \(error.localizedDescription, privacy: .public)"
            )
        }
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

        // Output-exists check first — the CLI message contains the project
        // name in some locales, and we want it classified before the broader
        // "model" / "whisper" matches accidentally fire on unrelated output.
        if matches(tail, #"output directory already exists"#) { return .outputExists }
        if matches(tail, #"401|invalid api key|authentication"#) { return .auth }
        if matches(tail, #"rate limit|quota|insufficient_quota|429"#) { return .quota }
        if matches(tail, #"connection refused|timed out|dns|could not resolve"#) {
            return .network
        }
        if matches(tail, #"no space|enospc|disk full"#) { return .disk }
        // LLM provider errors BEFORE whisper. A provider/model-mismatch 404
        // prints "model: gemini-2.5-flash" / "not_found_error", which the old
        // broad whisper pattern (bare "model") mis-grabbed — surfacing an LLM
        // 404 as "Transcription failed" (5 Jun 2026 ghost-debugging session).
        if matches(tail, #"provider says|not_found_error|no such model|model not found"#) {
            return .apiRequest
        }
        // Whisper requires a REAL error signature, never the benign preflight
        // block — `bristlenose run` always prints "✓ Transcription mlx-whisper"
        // + "Whisper model … not cached", so bare "whisper"/"model" would match
        // healthy output. Match install/download/native-lib failures instead.
        if matches(tail, #"packageinstallerror|snapshot_download|metallib|libjaccl|faster_whisper"#) {
            return .whisper
        }
        return .unknown
    }

    /// Detect a successful `bristlenose run` from its stdout tail.
    ///
    /// On success the CLI prints a `Done` line followed by `Report:` with
    /// the report URL/path. On failure it prints `Finished with errors`.
    /// We require both success markers and the absence of the failure
    /// marker — a partial match (e.g. `Report:` from a stale earlier run)
    /// shouldn't be enough to override a non-zero exit.
    nonisolated static func looksLikeSuccess(lines: [String]) -> Bool {
        let tail = lines.suffix(50).joined(separator: "\n")
        if tail.contains("Finished with errors") { return false }
        let hasDone = tail.range(of: #"\bDone\b"#, options: .regularExpression) != nil
        let hasReport = tail.contains("Report:")
        return hasDone && hasReport
    }

    /// Read the structured `cause` from `<project>/bristlenose-output/.bristlenose/
    /// pipeline-events.jsonl` if a `run_failed` terminus is present. Returns
    /// `(category, message)` or `nil` when the events log is missing, the most
    /// recent event isn't `run_failed`, or the line can't be decoded.
    private static func deriveFailureFromEvents(
        project: Project
    ) -> (PipelineFailureCategory, String?)? {
        let eventsURL = URL(fileURLWithPath: project.path)
            .appendingPathComponent("bristlenose-output")
            .appendingPathComponent(".bristlenose")
            .appendingPathComponent(EventLogReader.filename)
        guard let event = EventLogReader.tailEvent(at: eventsURL),
              event.event == "run_failed",
              let cause = event.cause else {
            return nil
        }
        return (cause.category, cause.message)
    }

    /// Human-readable one-liner for a failure category. When `provider` is
    /// supplied, LLM-related categories name it ("Claude rejected the request.")
    /// instead of the generic "LLM provider …" — the cause classifier can't
    /// always recover a structured message, and a named provider is the
    /// difference between an actionable summary and a shrug. Non-LLM categories
    /// (disk, whisper, …) ignore `provider`.
    static func humanSummary(
        for category: PipelineFailureCategory,
        provider: LLMProvider? = nil
    ) -> String {
        // `subject` reads in subject position ("Claude rate limit reached"),
        // `object` in object position ("Couldn't reach Claude" / "the LLM
        // provider"). Both collapse to the provider's display name when known.
        let subject = provider?.displayName ?? "LLM provider"
        let object = provider?.displayName ?? "the LLM provider"
        switch category {
        case .auth:       return "Your \(subject) key isn't working."
        case .network:    return "Couldn't reach \(object)."
        case .quota:      return "\(subject) rate limit reached."
        case .disk:       return "Not enough disk space to finish."
        case .whisper:    return "Transcription failed — the speech model didn't load."
        case .userSignal: return "Run was stopped."
        case .apiRequest: return "\(subject) rejected the request."
        case .apiServer:  return "\(subject) is unavailable — try again shortly."
        case .missingDep: return "Setup needed — a required tool isn't installed."
        case .missingInput: return "A required input file is missing."
        case .missingBinary: return "FFmpeg couldn't be found."
        case .outputExists: return "Already analysed — re-analysing would replace the existing results."
        case .outputTruncated: return "This session is too dense for \(subject)'s output limit — try a model with a larger output, or split the recording."
        case .unknown:    return "Something went wrong during analysis."
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
