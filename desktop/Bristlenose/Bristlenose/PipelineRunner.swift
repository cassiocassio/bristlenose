// AppKit for one symbol, `NSApplication.willTerminateNotification` (see
// `stopAllForQuit`), as in ServeManager.
import AppKit
import Foundation
import os

// MARK: - Failure taxonomy

/// Categorises a pipeline failure so the UI can show a human summary + CTA
/// without leaking raw stderr. Regex-based heuristics today; would be replaced
/// by explicit error codes if the CLI gains structured progress output.
enum PipelineFailureCategory: String, Codable, Equatable {
    case auth
    /// Provider account out of credit (billing exhausted). Distinct from
    /// `quota` (transient rate-limit): re-running before a top-up fails
    /// identically, and the fix is out-of-band ("Add funds"), like `auth`.
    /// Mirrors Python `CauseCategoryEnum.OUT_OF_CREDIT`.
    case outOfCredit = "out_of_credit"
    case network
    /// Transient rate-limit / throttling ("rate limit reached" — retry).
    /// Billing exhaustion routes to `outOfCredit`, not here.
    case quota
    case disk
    case whisper
    case unknown


    // Phase 1f Slice 4 — additive. Names match Python `CauseCategoryEnum`
    // exactly (snake_case round-trips through `String` rawValue). No
    // existing case is renamed — the Swift/Python boundary is contractually
    // stable. See docs/design-pipeline-resilience.md §"Cross-boundary naming".
    /// One input file isn't in the report — declined by format, or accepted
    /// and then unreadable. Both halves share this category because they share
    /// a consequence; the specific reason rides in `Cause.message`. Mirrors
    /// Python `CauseCategoryEnum.UNUSABLE_INPUT` (`bristlenose/refusals.py`).
    case unusableInput = "unusable_input"
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
    /// No AI provider the run could use: the active cloud provider has no key,
    /// or none was ever chosen and the default has none. Mac-only, like
    /// `outputExists` — Python's setup check refuses before the run's lifecycle
    /// opens, so no terminus carries it. Usually nothing is spawned at all
    /// (`PipelineRunner.start` refuses first); `categoriseFailure` catches the
    /// cases the Keychain read can't see, such as an Azure endpoint left blank.
    case providerNotSetUp = "provider_not_set_up"
    /// Quote extraction produced more output than the model's cap allows,
    /// even after the pipeline split the session into smaller chunks.
    /// Recovery is a larger-output model or manual pre-segmentation.
    case outputTruncated = "output_truncated"

    /// Decode an unrecognised category as `.unknown` instead of throwing.
    ///
    /// Without this, a category added on the Python side and not yet mirrored
    /// here fails to decode — and because the category sits inside `Cause`
    /// inside the terminus event, the failure takes **the whole event** with
    /// it: no summary, no per-stage rows, no cause at all, for a run that
    /// merely used a newer word. The "schema-additive" contract this enum is
    /// documented under only holds if the reader tolerates what it has not
    /// heard of, and until Aug 2026 it did not. A stale label is a far smaller
    /// loss than a blank diagnostic.
    init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = PipelineFailureCategory(rawValue: raw) ?? .unknown
    }

    /// This category's leaf under `desktop.pipeline.failure`. The caller adds
    /// the namespace, and `Generic` when no provider is known.
    ///
    /// Spelled out rather than derived from `rawValue`, which is snake_case on
    /// the wire (`out_of_credit`) against camelCase in the locale files. A
    /// `switch` also makes a new category a **compile error** here instead of a
    /// key that quietly resolves to nothing — `PipelineFailureCategory` decodes
    /// an unknown raw value as `.unknown` by design, so nothing downstream would
    /// ever have complained.
    var localeLeaf: String {
        let leaf: String
        switch self {
        case .auth: leaf = "auth"
        case .outOfCredit: leaf = "outOfCredit"
        case .network: leaf = "network"
        case .quota: leaf = "quota"
        case .disk: leaf = "disk"
        case .whisper: leaf = "whisper"
        case .userSignal: leaf = "userSignal"
        case .apiRequest: leaf = "apiRequest"
        case .apiServer: leaf = "apiServer"
        case .missingDep: leaf = "missingDep"
        case .missingInput: leaf = "missingInput"
        case .missingBinary: leaf = "missingBinary"
        case .outputExists: leaf = "outputExists"
        case .providerNotSetUp: leaf = "providerNotSetUp"
        case .outputTruncated: leaf = "outputTruncated"
        case .unusableInput: leaf = "unusableInput"
        case .unknown: leaf = "unknown"
        }
        return leaf
    }

    /// The short noun phrase this category shows beside `Category:` in the
    /// diagnostic popover — "Out of credit", "Rate limited".
    ///
    /// It was `ProjectDiagnosticPopover.humanCategoryLabel`, and
    /// `desktop/CLAUDE.md` recorded it as blocked: the same function was said to
    /// feed the English-only "Copy error details" payload, so translating it
    /// would have broken the paste. **That stopped being true in `11435ddd`** —
    /// the payload prints `category.rawValue` (the wire name, `out_of_credit`),
    /// which is what a bug report wants anyway. One production caller, one view,
    /// no split needed.
    var labelKey: String { "desktop.pipeline.category." + localeLeaf }

    /// True when `localeLeaf`'s value interpolates `{{provider}}`. The provider
    /// is captured where the run's failure is classified, not where it is drawn
    /// — by display time the user may have switched, and naming the wrong one is
    /// worse than naming none.
    ///
    /// The set is deliberately narrow: a disk or FFmpeg failure has nothing to
    /// do with the provider, and a sentence that names one there would be a
    /// small lie. Pinned against the English values by
    /// `tests/test_pipeline_failure_keys.py`.
    var namesProvider: Bool {
        switch self {
        case .auth, .outOfCredit, .network, .quota, .apiRequest, .apiServer,
             .outputTruncated, .providerNotSetUp:
            return true
        case .disk, .whisper, .userSignal, .missingDep, .missingInput,
             .missingBinary, .outputExists, .unusableInput, .unknown:
            return false
        }
    }
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
    /// time-based ring fill; `stage` / `sessionsComplete` / `sessionsTotal` /
    /// `etaRemainingSeconds` feed the in-flight subtitle text
    /// ("Transcribing · 7 of 8 · ~1 min left"), composed by `RunProgressSubtitle`
    /// and rendered in `ProjectRow`.
    var stage: String?
    var etaRemainingSeconds: Double?
    var predictedTotalSeconds: Double?
    var elapsed: TimeInterval = 0
    var lastLine: String = ""
    var startedAt: Date = Date()
    /// Where the ring's time estimate starts counting, when not `startedAt`:
    /// the end of a first run's speech-model download, which the estimate
    /// never contains (R32). `elapsed` still counts from `startedAt`.
    var timeBaseline: Date?
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
    /// Sessions a first analysis has made readable so far (progressive lenses):
    /// the newest `sessions_readable` the run reported, never moving back. Nil
    /// on a run that delivers nothing early. The subtitle says it while
    /// sessions are still arriving.
    var sessionsReadable: Int?
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
    ///
    /// The message is a `FailureMessage`, not a sentence: the classifier runs
    /// where there is no `I18n` and no view, so resolving here would pin the
    /// wording to whatever language was in force when the run exited. Python's
    /// `cause.message` arrives as a passthrough (English on the wire by
    /// design); our own classification arrives as a key plus the provider we
    /// saw, and the row resolves it.
    case failed(FailureMessage, category: PipelineFailureCategory)
    /// Project can't be scanned (volume unmounted, path gone, permission denied).
    /// Distinct from `.failed` — nothing to retry, just unreachable right now.
    case unreachable(reason: UnreachableReason)
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

extension PipelineState {
    /// True while the run is actively executing — the window during which the
    /// machine must not idle-sleep (`RunSleepAssertion`). Only `.running`
    /// qualifies. `.queued` is deliberately excluded: the gap between one run's
    /// terminal write and the next dequeuing to `.running` is sub-second, far
    /// below any idle-system-sleep timer (minutes), so holding the assertion
    /// across queued work buys no real protection while risking a stuck-queued
    /// run holding it indefinitely. (Reviewers split here; this is the call —
    /// idle-sleep cadence makes the dequeue gap a non-issue.) The Stop window
    /// stays `.running` (stopping is a `PipelineProgress` sub-state), so the
    /// machine stays awake until the subprocess actually exits.
    var keepsMachineAwake: Bool {
        if case .running = self { return true }
        return false
    }

    /// The analysis couldn't start for want of an AI provider. The diagnostic
    /// popover offers Settings ▸ LLM Provider in `Show Log`'s place, as it
    /// offers Locate… for a folder it can't read: the one act that fixes what
    /// it is showing.
    var needsProvider: Bool {
        if case .failed(_, .providerNotSetUp) = self { return true }
        return false
    }
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

    @Published private(set) var state: [UUID: PipelineState] = [:] {
        didSet {
            syncSleepAssertion()
            rerunWaitingProjectsIfWhisperIsReady()
        }
    }

    /// Transient "Adding N interviews…" gesture counts, keyed by project. Set by
    /// the drop / Add-Files intake before copy starts and held for a ~2 s floor
    /// (so the message can't flash-and-vanish on a near-instant clonefile copy),
    /// then cleared. Read by `ProjectSubtitle.resolve` at the sidebar call sites;
    /// yields to the stage ladder once a run reaches `.running`. Phase 2.
    @Published private(set) var addingInterviews: [UUID: Int] = [:]

    /// How many of a running project's sessions have a readable transcript —
    /// a first analysis delivers them one by one, and the first one hands the
    /// pane from the shoal to the report (`DetailPaneKind.shoalTakesPane`).
    /// Published here rather than on `liveData` because it moves once per
    /// session, not once a second, and the window's pane reads it.
    @Published private(set) var sessionsReadable: [UUID: Int] = [:]

    /// Per project, the run that was newest in the events log when we spawned
    /// one: its progress lines are never the new run's
    /// (`EventLogReader.currentRunProgress`). Absent for an attached orphan,
    /// whose own `run_started` is already the newest.
    private var priorRunIds: [UUID: String] = [:]

    /// Show the "Adding N interviews…" ack for `projectID` and clear it no sooner
    /// than `floor` seconds from now (the visibility floor — the timer only bounds
    /// the *minimum* on-screen time; a run reaching `.running` overrides the
    /// message earlier via the resolver precedence).
    func beginAddingInterviews(projectID id: UUID, count: Int, floor: TimeInterval = 2) {
        guard count > 0 else { return }
        addingInterviews[id] = count
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(floor))
            self?.addingInterviews[id] = nil
        }
    }

    /// Keeps the system awake while any run is executing — see `RunSleepAssertion`.
    /// Driven off `state` (the single source of truth) rather than instrumented
    /// at every start/attach/exit site: `state` only mutates on coarse
    /// transitions (idle→running→terminal), and `setHeld` is idempotent, so this
    /// can't thrash on progress churn (progress lives in `liveData`, not `state`).
    private let sleepAssertion = RunSleepAssertion()

    private func syncSleepAssertion() {
        sleepAssertion.setHeld(state.values.contains(where: \.keepsMachineAwake))
    }

    #if DEBUG
    /// Debug-only state override for the diagnostic-popover fixture harness.
    /// Used by `_applyDebugFixture(to:)` (called from `ContentView`). Not
    /// compiled into Release builds.
    func _debugSetState(_ state: PipelineState, for projectID: UUID) {
        self.state[projectID] = state
    }

    /// Map a fixture `Result` onto a project's state. Shared by the launch-time
    /// env-var path and the live Debug-menu submenu. `.none`/`.clean` leave the
    /// state untouched.
    private func _applyFixtureResult(_ result: DiagnosticFixture.Result, to projectID: UUID) {
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
            self.state[projectID] = .failed(.passthrough(message), category: category)
        case .simpleState(let injected):
            self.state[projectID] = injected
        }
    }

    /// Debug-only: apply the env-var fixture override for one project (called
    /// from ContentView when the selection changes). Idempotent per project.
    private var _debugFixtureApplied = Set<UUID>()
    func _applyDebugFixture(to projectID: UUID) {
        guard !_debugFixtureApplied.contains(projectID) else { return }
        let result = DiagnosticFixture.loadIfEnabled()
        if case .none = result { return }   // don't mark applied; nothing injected
        if case .clean = result { return }
        _applyFixtureResult(result, to: projectID)
        _debugFixtureApplied.insert(projectID)
    }

    /// Debug-only: apply a named fixture live, from the Debug-menu submenu. An
    /// explicit user action, so it bypasses the once-per-project idempotency
    /// guard and re-applies on every pick (lets you flip scenes with no relaunch).
    func applyDebugFixture(named name: String, to projectID: UUID) {
        _applyFixtureResult(DiagnosticFixture.load(name: name), to: projectID)
    }
    #endif

    /// Noisy progress data + stdout ring buffer. See `PipelineLiveData` for
    /// why this lives in a separate `ObservableObject`.
    let liveData = PipelineLiveData()

    /// FIFO queue of studies waiting to run, each with its `--clean`.
    /// `currentlyRunning` holds the slot; any new `start()` while that's set
    /// enqueues. The slot is held from spawn until the run's end state has
    /// been written, not just while its process lives (R23).
    private var queue = RunQueue()
    private var currentlyRunning: UUID?

    /// The run in flight, if any: its process is live. Cleared when the
    /// termination handler starts, before the exit is resolved.
    private var currentRun: LaunchedRun?
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
    nonisolated private static let iso8601: ISO8601DateFormatter = {
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
    nonisolated private static let terminalStage = "render"

    /// How a signal reaches a run: 0, or the errno. `kill` in the app; a test
    /// records instead. The closure reads errno itself — Swift does not keep it
    /// across a closure's return.
    private let sendSignal: (pid_t, Int32) -> Int32
    private let hasConsent: @MainActor () -> Bool
    private let keyReadiness: @MainActor () -> BristlenoseShared.APIKeyReadiness
    private let launcher: RunLauncher?
    private let escalationSleep: @Sendable (Duration) async -> Void
    /// Where Stop's and Quit's signals for a run's pid go — its process group,
    /// by `ownedSignalTarget`. A test passes its own so the group case can be
    /// seen without a second process.
    private let signalTarget: (pid_t) -> pid_t
    private let activeProvider: @MainActor () -> LLMProvider?
    private let noteRunSucceeded: @MainActor (LLMProvider) -> Void
    private let sidecarLookup: (@MainActor () -> Result<SidecarMode, SidecarResolveError>)?
    private let outputDrainLimit: Duration
    private let foreignRunPollInterval: Duration
    private let foreignRunPatience: Int
    /// The read of a project's manifest that settles a finished or stopped
    /// run's state. A test passes a slow one.
    private let manifestRead: @Sendable (URL) async -> PipelineState
    /// How long that read may take at a run's end before the row says it
    /// timed out.
    private let endStateTimeout: Duration
    /// The wait between reads of a run whose end-state read timed out, and how
    /// long each read is waited on before the next wait (R29).
    private let slowEndRereadInterval: Duration

    /// A run this app neither spawned nor attached — a CLI run on a sidebar
    /// study — reads `.running` from its own `run.pid` (`EventLogReader.deriveState`),
    /// and disk is all there is to go on: there is no process to wait for and
    /// none we may signal. Re-read until disk says it is over (R22). It used to
    /// read "Analysing" until quit, holding the Mac awake.
    private var foreignRunWatches: [UUID: Task<Void, Never>] = [:]

    /// Re-reads of a run whose end-state read timed out (R29), and the token
    /// of the one in flight, so an older loop ending does not drop a newer
    /// one's handle.
    private var slowEndRereads: [UUID: Task<Void, Never>] = [:]
    private var slowEndRereadTokens: [UUID: UUID] = [:]

    /// Whether the project's live run is this app's: the one in the slot, or
    /// an attached orphan.
    private func ownsRun(_ projectID: UUID) -> Bool {
        currentlyRunning == projectID || attachedOrphanPIDs[projectID] != nil
    }

    /// The provider each run was spawned with — read back from the PID file
    /// for an attached orphan. A finished run clears an out-of-credit verdict
    /// on this one, not on whichever is active when it ends (R40).
    private var runProviders: [UUID: LLMProvider] = [:]
    /// For an attached run: the terminus already newest in its events log when
    /// it was attached, i.e. a previous run's. Its tokens are not this run's.
    private var orphanPriorTerminus: [UUID: String] = [:]

    /// A launched run, as the runner sees it once it is going.
    struct LaunchedRun {
        let pid: pid_t
        /// False once the process has exited and been reaped.
        let isRunning: () -> Bool
        /// The run's stdout and stderr a line at a time, finished when the
        /// pipe closes. Nil for a launch with nothing to read.
        var output: AsyncStream<String>? = nil
    }

    /// Starts a `bristlenose run` for a project, `--clean` or not, and calls
    /// `onExit` once when it ends. The app's own launches the sidecar; a test
    /// passes one that records the request and ends the run by hand, because
    /// the test host's bundle may hold a real sidecar, a 0-byte stub or none.
    typealias RunLauncher = @MainActor (
        _ project: Project, _ clean: Bool,
        _ onExit: @escaping @Sendable (ProcessOutcome) -> Void
    ) throws -> LaunchedRun

    /// - Parameters:
    ///   - notificationCenter: where Quit is observed. A test passes its own,
    ///     so posting Quit there reaches no other object in the test host.
    ///   - sendSignal: how a signal is sent to a run at Quit; returns 0 or the errno.
    ///   - hasConsent: whether the AI disclosure has been acknowledged.
    ///   - keyReadiness: what the key overlay would inject into a run now.
    ///     A test passes both so it can drive `start` without the app's own
    ///     defaults or Keychain.
    ///   - launcher: how a run is started. Nil, the app's, launches the sidecar.
    ///   - escalationSleep: the wait between Stop's signals; a test passes none.
    ///   - signalTarget: where a run's signals go, given its pid.
    ///   - activeProvider: the provider a run is spawned with.
    ///   - noteRunSucceeded: what a finished run that made an LLM call does to
    ///     its provider's out-of-credit verdict.
    ///   - sidecarLookup: where the sidecar is. Nil, the app's, resolves it
    ///     from the bundle, and only when no `launcher` is passed; a test passes
    ///     one beside its launcher to reach a failed lookup (R28).
    ///   - outputDrainLimit: how long a failed run's verdict waits for the
    ///     rest of its output (R25).
    ///   - foreignRunPollInterval: how often a run another process owns is
    ///     re-read from disk (R22).
    ///   - foreignRunPatience: how many reads in a row that can't tell whether
    ///     such a run has ended before the row takes what disk says.
    init(
        notificationCenter: NotificationCenter = .default,
        sendSignal: @escaping (pid_t, Int32) -> Int32 = { Darwin.kill($0, $1) == 0 ? 0 : errno },
        hasConsent: @escaping @MainActor () -> Bool = { PipelineRunner.hasAIConsent },
        keyReadiness: @escaping @MainActor () -> BristlenoseShared.APIKeyReadiness = {
            BristlenoseShared.apiKeyReadiness(using: KeychainHelper.liveStore)
        },
        launcher: RunLauncher? = nil,
        escalationSleep: @escaping @Sendable (Duration) async -> Void = {
            try? await Task.sleep(for: $0)
        },
        signalTarget: @escaping (pid_t) -> pid_t = {
            PipelineRunner.ownedSignalTarget(pid: $0, processGroup: getpgid($0), ownGroup: getpgrp())
        },
        activeProvider: @escaping @MainActor () -> LLMProvider? = {
            UserDefaults.standard.string(forKey: "activeProvider").flatMap(LLMProvider.init(rawValue:))
        },
        noteRunSucceeded: @escaping @MainActor (LLMProvider) -> Void = {
            OutOfCreditModel.noteRunSucceeded(provider: $0)
        },
        sidecarLookup: (@MainActor () -> Result<SidecarMode, SidecarResolveError>)? = nil,
        outputDrainLimit: Duration = .seconds(2),
        foreignRunPollInterval: Duration = .seconds(2),
        foreignRunPatience: Int = 15,
        manifestRead: @escaping @Sendable (URL) async -> PipelineState = {
            await PipelineRunner.parseManifest(at: $0)
        },
        endStateTimeout: Duration = .seconds(5),
        slowEndRereadInterval: Duration = .seconds(5)
    ) {
        self.foreignRunPatience = foreignRunPatience
        self.manifestRead = manifestRead
        self.endStateTimeout = endStateTimeout
        self.slowEndRereadInterval = slowEndRereadInterval
        self.sidecarLookup = sidecarLookup
        self.outputDrainLimit = outputDrainLimit
        self.foreignRunPollInterval = foreignRunPollInterval
        self.sendSignal = sendSignal
        self.hasConsent = hasConsent
        self.keyReadiness = keyReadiness
        self.launcher = launcher
        self.escalationSleep = escalationSleep
        self.signalTarget = signalTarget
        self.activeProvider = activeProvider
        self.noteRunSucceeded = noteRunSucceeded
        Self.logger.info("PipelineRunner initialised")
        // Whisper landed: every project with a session deferred to it (Apple's
        // first-run model, the wrong language) runs again, and the per-session
        // fingerprints mean only those sessions are transcribed
        // (docs/design-apple-first-transcription.md §2).
        whisperReadyObserver = NotificationCenter.default.addObserver(
            forName: .bristlenoseWhisperReady, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.rerunDeferredProjects() }
        }
        // The object that owns the process owns its shutdown (ServeManager's
        // rule). Synchronous: Quit exits straight after posting this.
        terminationObserver = notificationCenter.addObserver(
            forName: NSApplication.willTerminateNotification, object: nil, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.stopAllForQuit() }
        }
    }

    private var whisperReadyObserver: NSObjectProtocol?
    private var terminationObserver: NSObjectProtocol?

    /// The projects whose last run left a session waiting for Whisper.
    var projectsWaitingForWhisper: [UUID] {
        state.compactMap { id, s in Self.isWaitingForWhisper(s) ? id : nil }
    }

    /// True when the run finished with at least one session deferred to
    /// Whisper. Any other failure beside it keeps the row on its own glyph;
    /// the re-run is still owed.
    nonisolated static func isWaitingForWhisper(_ state: PipelineState) -> Bool {
        guard case .completedPartial(let summary) = state else { return false }
        return summary.allFailures.contains { $0.cause.category == .deferred }
    }

    /// Projects already re-run for Whisper in this process. Once each: with
    /// Whisper on disk the run sends a session Apple's model is unsure of to
    /// Whisper there and then, so a second "waiting" would be a defect, and a
    /// defect must not become a loop of paid runs.
    private var rerunForWhisper: Set<UUID> = []

    private func rerunDeferredProjects() {
        guard BristlenoseFlags.appleSpeechAvailable, let projects = projectIndex?.projects else { return }
        for id in projectsWaitingForWhisper where !rerunForWhisper.contains(id) {
            guard let project = projects.first(where: { $0.id == id }) else { continue }
            rerunForWhisper.insert(id)
            Self.logger.info(
                "re-running for deferred sessions project=\(id.uuidString, privacy: .public)"
            )
            start(project: project)
        }
    }

    /// Level, not edge: a project can reach "waiting" after Whisper has
    /// landed — the download finished while its run was still in the LLM
    /// stages, or a launch scan read it after the status probe. Checked on
    /// every state change, acted on a turn later (never inside `didSet`).
    private func rerunWaitingProjectsIfWhisperIsReady() {
        guard BristlenoseFlags.appleSpeechAvailable,
              WhisperDownloadModel.shared.phase == .onDisk,
              projectsWaitingForWhisper.contains(where: { !rerunForWhisper.contains($0) })
        else { return }
        Task { @MainActor [weak self] in self?.rerunDeferredProjects() }
    }

    /// Inject the shared `ProjectIndex` so `startNextQueued()` can resolve a
    /// queued UUID back into a `Project`. Call once from the App layer's
    /// `.onAppear`, after both `@StateObject`s exist.
    func setProjectIndex(_ index: ProjectIndex) {
        self.projectIndex = index
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
    enum ScanOutcome {
        case orphan(pid: pid_t)
        case manifest(PipelineState)
    }

    /// Scan a single project's manifest, with orphan-attach taking priority
    /// if a live `bristlenose run` for this project is found.
    ///
    /// All filesystem I/O (PID file read, libproc ownership check, manifest
    /// JSON parse) runs on a detached task. Only the final state mutation hops
    /// back to MainActor.
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

    nonisolated static func performScan(
        project: Project, manifestURL: URL,
        startTime: (pid_t) -> String? = EventLogReader.procStartTime
    ) async -> ScanOutcome {
        if let pid = aliveOwnedRunPID(for: project, startTime: startTime) {
            return .orphan(pid: pid)
        }
        // No live orphan. The PID file's fate was decided inside
        // `aliveOwnedRunPID`: removed on a definite `.stale`, KEPT on an
        // `.indeterminate` check. A second, unconditional sweep sat here until
        // 12 Oct 2026 and undid that keep one frame up — the callee logged
        // "keeping its PID file" and this line deleted it (review finding 1).
        let resolved = await readManifestState(
            at: manifestURL, timeout: scanTimeout, allowTimeout: true
        )
        return .manifest(resolved)
    }

    private func applyScan(outcome: ScanOutcome, project: Project, projectID: UUID) {
        switch outcome {
        case .orphan(let pid):
            // A rescan during a run THIS process owns finds its own PID file
            // and would attach to itself: progress reset, a second poller,
            // double resolution on exit. Reachable since rescans fire on
            // rename and bookmark heal, not only after Locate….
            if currentlyRunning == projectID || attachedOrphanPIDs[projectID] != nil {
                Self.logger.info("scan found our own live run for project=\(projectID.uuidString, privacy: .public) — not attaching")
                return
            }
            attachOrphan(project: project, pid: pid)
        case .manifest(let resolved):
            applyScanResult(resolved, for: projectID)
            if case .running = state[projectID], !ownsRun(projectID) {
                watchForeignRun(project)
            }
        }
    }

    /// Re-read a run another process owns until disk says it has ended (R22):
    /// its terminus, or `run.pid` naming a process that is gone
    /// (`EventLogReader.foreignRunVerdict`). Nothing else ends the watch: a
    /// read that can't tell (`run.pid` unreadable, no lifecycle line, the
    /// folder unreachable, a read that hangs) is polled again, and only after
    /// `foreignRunPatience` such polls in a row is the row settled to whatever
    /// disk then says, so a run that never says is not watched for ever. Ends early when the row stops being that run's (the app
    /// took the study over, or a scan settled it). One read at a time: a hung
    /// one is waited on again, not stacked.
    private func watchForeignRun(_ project: Project) {
        let projectID = project.id
        guard foreignRunWatches[projectID] == nil else { return }
        let manifestURL = Self.manifestURL(for: project)
        let dotBristlenose = manifestURL.deletingLastPathComponent()
        let eventsURL = dotBristlenose.appendingPathComponent(EventLogReader.filename)
        let pidURL = dotBristlenose.appendingPathComponent(EventLogReader.pidFilename)
        let interval = foreignRunPollInterval
        let patience = foreignRunPatience
        Self.logger.info(
            "a run this app does not own is live project=\(projectID.uuidString, privacy: .public) — watching it on disk"
        )
        foreignRunWatches[projectID] = Task { @MainActor [weak self] in
            var read: Task<(EventLogReader.ForeignRunVerdict, PipelineState), Never>?
            var undecided = 0
            while !Task.isCancelled {
                try? await Task.sleep(for: interval)
                guard let self, self.isForeignRunning(projectID) else { break }
                let pending = read ?? Task.detached {
                    let verdict = EventLogReader.foreignRunVerdict(eventsURL: eventsURL, pidURL: pidURL)
                    return (verdict, await Self.parseManifest(at: manifestURL))
                }
                read = pending
                guard let (verdict, resolved) = await Self.value(of: pending, within: Self.scanTimeout) else {
                    undecided += 1
                    Self.logger.notice("a read of a run this app does not own is taking long project=\(projectID.uuidString, privacy: .public)")
                    continue
                }
                read = nil
                guard self.isForeignRunning(projectID) else { break }
                if verdict == .live {
                    undecided = 0
                    continue
                }
                // Ended, and disk reads clearly: settle. Otherwise wait, and
                // once patience runs out take any answer but "running".
                if !(verdict == .ended && Self.isSettled(resolved)) {
                    undecided += 1
                    guard undecided >= patience, Self.isReadable(resolved) else { continue }
                }
                Self.logger.info(
                    "a run this app does not own has ended project=\(projectID.uuidString, privacy: .public) verdict=\(String(describing: verdict), privacy: .public) state=\(String(describing: resolved), privacy: .public)"
                )
                self.applyScanResult(resolved, for: projectID)
                break
            }
            self?.foreignRunWatches[projectID] = nil
        }
    }

    /// A read of disk that can end a watch: not "still going", and not "could
    /// not read".
    private nonisolated static func isSettled(_ state: PipelineState) -> Bool {
        if case .unreachable = state { return false }
        return isReadable(state)
    }

    /// Any answer but "still going".
    private nonisolated static func isReadable(_ state: PipelineState) -> Bool {
        switch state {
        case .running, .scanning: return false
        default: return true
        }
    }

    /// The task's value, or nil if it takes longer than `limit`. The task is
    /// left running, for the caller to wait on again.
    private nonisolated static func value<T: Sendable>(
        of task: Task<T, Never>, within limit: Duration
    ) async -> T? {
        await withCheckedContinuation { (done: CheckedContinuation<T?, Never>) in
            let once = ResumeOnce<T?>(done)
            Task { once.resume(await task.value) }
            Task {
                try? await Task.sleep(for: limit)
                once.resume(nil)
            }
        }
    }

    private func isForeignRunning(_ projectID: UUID) -> Bool {
        if case .running = state[projectID] { return !ownsRun(projectID) }
        return false
    }

    // MARK: - Orphan attach (Slice 7)

    /// What the PID file says about a run, judged against the live process
    /// table. Pure: the probes are injected so the table below is testable
    /// without a second process.
    enum OwnedRunVerdict: Equatable {
        /// A live run of ours. Attach to it.
        case alive(pid_t)
        /// Dead, foreign, or a reused pid. Remove the file.
        case stale
        /// The process is alive but the check could not finish (libproc
        /// refused). **Keep the file** — deleting it is how orphan attach
        /// became unreachable: `/bin/ps` failed under App Sandbox on every
        /// launch, the failure read as "not ours", and the file was removed,
        /// so a relaunch mid-run showed Analysing with an inert Stop while
        /// Analyse could spawn a second run against the same folder.
        case indeterminate
    }

    /// The PID file is `"<pid>\n<start_time>\n<provider>"` (the third line,
    /// since 20 Oct 2026, is read only by `recordedProvider`) — the start token is the
    /// libproc `"<tvsec>.<tvusec>"` string `EventLogReader.procStartTime`
    /// yields, recorded at spawn, so a pid the kernel has since reused fails
    /// the comparison instead of matching on argv. A file with no token (the
    /// pid-only shape of builds before 12 Oct 2026) is **stale**: without the
    /// token a reused pid matches on uid alone, and Stop would escalate to
    /// SIGKILL into whatever now holds that pid. A spawn whose libproc query
    /// failed writes `noStartToken` instead of nothing, which reads as
    /// `.indeterminate` — a verifier that cannot verify must never upgrade a
    /// pid to "ours", and must never read as a legacy file either.
    /// Second line of a PID file whose spawn could not read a start token.
    /// Non-empty on purpose: an empty second line is indistinguishable from
    /// the legacy pid-only shape, which is stale.
    nonisolated static let noStartToken = "no-start-token"

    nonisolated static func ownedRunVerdict(
        pidFileContents: String,
        isAlive: (pid_t) -> Bool,
        processUID: (pid_t) -> uid_t?,
        startTime: (pid_t) -> String?,
        currentUID: uid_t
    ) -> OwnedRunVerdict {
        let lines = pidFileContents
            .split(separator: "\n", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespaces) }
        guard let first = lines.first, let pid = pid_t(first), pid > 0 else { return .stale }
        guard isAlive(pid) else { return .stale }
        guard let uid = processUID(pid) else { return .indeterminate }
        guard uid == currentUID else { return .stale }
        let recorded = lines.count > 1 ? lines[1] : ""
        guard !recorded.isEmpty else { return .stale }
        guard recorded != noStartToken else { return .indeterminate }
        guard let live = startTime(pid) else { return .indeterminate }
        return live == recorded ? .alive(pid) : .stale
    }

    /// Read the app's PID file for `project` and verify the pid is (a) alive,
    /// (b) owned by the current uid, (c) the same process incarnation that
    /// was spawned (start-time token). Returns the pid iff all three pass.
    /// Removes the file only on a definite `.stale`; an `.indeterminate` check
    /// leaves it for the next scan.
    ///
    /// Everything is libproc (`kill(pid, 0)`, `proc_pidinfo`): App Sandbox
    /// blocks `Process()` exec of `/bin/ps` at the exec boundary (measured
    /// 12 Oct 2026, `Operation not permitted`), and both build configurations
    /// carry `ENABLE_APP_SANDBOX = YES`.
    nonisolated static func aliveOwnedRunPID(
        for project: Project,
        processUID: (pid_t) -> uid_t? = EventLogReader.procUID,
        startTime: (pid_t) -> String? = EventLogReader.procStartTime
    ) -> pid_t? {
        let url = pidFileURL(for: project)
        guard let data = try? Data(contentsOf: url),
              let str = String(data: data, encoding: .utf8) else {
            return nil
        }
        let verdict = ownedRunVerdict(
            pidFileContents: str,
            // kill(pid, 0) is 0 when the process exists and we may signal it;
            // ESRCH means no such process.
            isAlive: { kill($0, 0) == 0 },
            processUID: processUID,
            startTime: startTime,
            currentUID: getuid()
        )
        switch verdict {
        case .alive(let pid):
            return pid
        case .stale:
            try? FileManager.default.removeItem(at: url)
            return nil
        case .indeterminate:
            logger.warning("orphan check could not finish for project=\(project.id.uuidString, privacy: .public) — keeping its PID file")
            return nil
        }
    }

    /// Attach to a live orphan: surface as `.running` with the same UI as a
    /// freshly-spawned run, but drive progress from manifest polling rather
    /// than stdout. Atomic stage commits make this safe — see
    /// `docs/design-pipeline-resilience.md`.
    /// Start the events-file progress poll for a spawned run (Phase 0b). Reads
    /// the newest `run_progress` off-main every ~1s and folds it into the ring
    /// via `RunProgressMath`. Guarded by `generation` so a superseded run's
    /// poll exits; cancelled in `handleTermination`.
    /// A run we spawn begins: fresh progress, and the run newest in the events
    /// log recorded so its lines are never read as this run's. Called before
    /// the process starts, so the new run cannot have written its own start
    /// yet. A bounded tail read, once per Analyse.
    func beginSpawnedRun(_ project: Project) {
        state[project.id] = .running
        sessionsReadable[project.id] = nil
        priorRunIds[project.id] = EventLogReader.tailEvent(at: Self.eventsURL(for: project))?.runId
        liveData.setProgress(PipelineProgress(startedAt: Date()), for: project.id)
        liveData.clearOutput(for: project.id)
    }

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
    func applyEventProgress(from eventsURL: URL, for projectID: UUID) async {
        // The events file is append-only — NOT truncated on resume — so the
        // newest progress line can be the *previous* run's, which would jump
        // the ring to ~97% and hand the pane to the report. Matching the
        // newest run_started is not enough on its own: a spawned run takes
        // seconds to write its start, and until then both are the previous
        // run's. `currentRunProgress` also excludes the run that was newest
        // at spawn.
        let prior = priorRunIds[projectID]
        let event = await Task.detached {
            EventLogReader.currentRunProgress(at: eventsURL, priorRunId: prior)
        }.value
        guard let event, let current = liveData.progress[projectID] else { return }
        if let readable = event.sessionsReadable, readable > (sessionsReadable[projectID] ?? 0) {
            sessionsReadable[projectID] = readable
        }
        var updated = RunProgressMath.apply(
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
        updated.sessionsReadable = sessionsReadable[projectID]
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
        runProviders[project.id] = (try? String(contentsOf: Self.pidFileURL(for: project), encoding: .utf8))
            .flatMap(Self.recordedProvider(pidFileContents:))
        if let tail = EventLogReader.tailEvent(at: Self.eventsURL(for: project)),
           tail.event != "run_started" {
            orphanPriorTerminus[project.id] = tail.runId
        }
        state[project.id] = .running
        sessionsReadable[project.id] = nil
        priorRunIds[project.id] = nil
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
        let provider = runProviders.removeValue(forKey: projectID)
        let priorTerminus = orphanPriorTerminus.removeValue(forKey: projectID)
        let eventsURL = Self.eventsURL(for: project)
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

        // Read the manifest to derive .ready vs .idle, and again if that read
        // times out (`settleOrphanEndRead`, R29). Through the same seam and
        // timeout as a spawned run's end read.
        // Brief delay so a clean SIGINT exit has time to flush atexit
        // handlers (manifest write); a SIGKILL/crash won't benefit but won't
        // be made worse either.
        let read = manifestRead
        let timeout = endStateTimeout
        Task.detached { [weak self] in
            try? await Task.sleep(for: .milliseconds(500))
            let resolved = await Self.readManifestState(
                at: Self.manifestURL(for: project), timeout: timeout, read: read
            )
            await self?.settleOrphanEndRead(
                resolved, project: project, provider: provider, priorTerminus: priorTerminus
            )
            if case .ready = resolved {
                // `.ready` here came from the run's own terminus: with an
                // events log, a tail of `run_started` reads as running or
                // stranded, never ready (`EventLogReader.deriveState`).
                let terminus = EventLogReader.tailEvent(at: eventsURL)
                await self?.noteCreditIfTheRunUsedAnLLM(
                    provider: provider, project: project,
                    terminus: terminus, priorRunId: priorTerminus
                )
            }
        }
    }

    /// Write an attached run's end read, and read it again if it timed out, as
    /// a spawned run's is (R29): on a slow disk the row otherwise read "Not
    /// responding" until relaunch.
    private func settleOrphanEndRead(
        _ resolved: PipelineState, project: Project,
        provider: LLMProvider?, priorTerminus: String?
    ) {
        applyScanResult(resolved, for: project.id)
        if state[project.id] == .unreachable(reason: .timedOut) {
            rereadAfterSlowEnd(project, provider: provider, priorRunId: priorTerminus)
        }
    }

    /// A run that finished whole and made an LLM call on `provider` proves it
    /// has credit, so a sticky out-of-credit verdict on it can go (R40). A run
    /// that finished from cache made no call and proves nothing; its terminus
    /// carries no tokens. `priorRunId` is the run newest at spawn: a terminus
    /// with that id is not this run's.
    private func noteCreditIfTheRunUsedAnLLM(
        provider: LLMProvider?, project: Project?,
        terminus: EventLogReader.Event?, priorRunId: String?
    ) {
        guard let project else { return }
        guard let provider else {
            Self.logger.info(
                "run finished with its provider not on record project=\(project.id.uuidString, privacy: .public) — credit verdict left as it is"
            )
            return
        }
        guard Self.runUsedAnLLM(terminus: terminus, priorRunId: priorRunId) else {
            Self.logger.info(
                "run finished with no LLM call on record project=\(project.id.uuidString, privacy: .public) — credit verdict left as it is"
            )
            return
        }
        noteRunSucceeded(provider)
    }

    nonisolated static func runUsedAnLLM(
        terminus: EventLogReader.Event?, priorRunId: String?
    ) -> Bool {
        guard let terminus, terminus.event == "run_completed",
              terminus.runId != priorRunId else { return false }
        return (terminus.inputTokens ?? 0) + (terminus.outputTokens ?? 0) > 0
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
    nonisolated static func pidFileURL(for project: Project) -> URL {
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

    private nonisolated static func writePIDFile(
        for project: Project, pid: pid_t, provider: LLMProvider?
    ) {
        let url = pidFileURL(for: project)
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true
        )
        // pid, then the libproc start-time token — see `ownedRunVerdict`.
        let start: String
        if let token = EventLogReader.procStartTime(pid: pid) {
            start = token
        } else {
            logger.error("no start token for pid=\(pid, privacy: .public) at spawn — orphan attach for this run will be indeterminate")
            start = noStartToken
        }
        // Third line: the provider the run was spawned with, so a relaunch
        // that attaches the run still knows it (R40). `ownedRunVerdict` reads
        // only the first two; a file without it reads as "not known".
        try? Data("\(pid)\n\(start)\n\(provider?.rawValue ?? "")".utf8)
            .write(to: url, options: .atomic)
    }

    /// The provider a run's PID file records, if it records one.
    nonisolated static func recordedProvider(pidFileContents: String) -> LLMProvider? {
        let lines = pidFileContents.split(separator: "\n", omittingEmptySubsequences: false)
        guard lines.count > 2 else { return nil }
        return LLMProvider(rawValue: lines[2].trimmingCharacters(in: .whitespaces))
    }

    private nonisolated static func removePIDFile(for project: Project) {
        try? FileManager.default.removeItem(at: pidFileURL(for: project))
    }

    /// Apply a scan result, but don't clobber a live `.running` / `.queued`
    /// state the runner owns — those come from the runner, not the manifest.
    /// A `.running` that a scan read off another process's run is disk's, and
    /// disk may end it (R22).
    private func applyScanResult(_ resolved: PipelineState, for projectID: UUID) {
        switch state[projectID] {
        case .running where !ownsRun(projectID):
            // A run another process owns, read off disk in the first place:
            // disk is the only witness to its end (R22). Kept, this read
            // "Analysing" until quit.
            state[projectID] = resolved
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
    /// - Parameter allowTimeout: when `true`, a hard timeout (5 s on a scan)
    ///   guards against a dead network mount, and returns on time even when
    ///   the read never does; when
    ///   `false`, skip the timeout machinery entirely (in-poll reads against
    ///   trusted local disk don't need it, and creating a sleep-task per
    ///   poll cycle was a real wakeup amplifier — see perf review).
    static func readManifestState(
        at url: URL, timeout: Duration, allowTimeout: Bool = true,
        read: @escaping @Sendable (URL) async -> PipelineState = { await parseManifest(at: $0) }
    ) async -> PipelineState {
        guard allowTimeout else {
            return await read(url)
        }
        // Raced, not grouped. A task group waits for every child before it
        // returns, so a read hung on a dead mount held the caller past its own
        // timeout, and at a run's end the slot with it: the queue stopped
        // behind a study whose row already said "Not responding" (R29). The
        // losing read is cancelled and left behind; one blocked in the kernel
        // ignores that and stays blocked, which is the price of the slot.
        let reading = Task.detached { await read(url) }
        guard let state = await value(of: reading, within: timeout) else {
            reading.cancel()
            return .unreachable(reason: .timedOut)
        }
        return state
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

    /// Internal rather than private so `EventLogReaderTests` can pin the guard
    /// order below — the bug it had was in *reaching* `deriveState`, which the
    /// reader's own tests cannot see because they call it directly.
    ///
    /// `nonisolated` is load-bearing, not tidiness. Inherited from the class,
    /// this ran on the main actor — so `readManifestState`'s timeout could not
    /// guard a hung read (the read blocks the thread the timeout must resume
    /// on), and a main thread merely *busy* for longer than the timeout made a
    /// healthy manifest read as `.unreachable(.timedOut)` (both shown by a
    /// standalone probe, 28 Sep 2026). The second is the likely cause of the
    /// intermittent `PipelineRunnerTerminationTests` failures on CI runners,
    /// where window tests share the main thread — INFERRED: no failing CI run
    /// has yet shown the returned state; the tests now print it if one does.
    /// File I/O belongs off main in any case.
    nonisolated static func parseManifest(at url: URL) async -> PipelineState {
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
            return .unreachable(reason: .folderMissing)
        }

        let dotBristlenose = url.deletingLastPathComponent()
        let eventsURL = dotBristlenose.appendingPathComponent(EventLogReader.filename)
        let pidURL = dotBristlenose.appendingPathComponent(EventLogReader.pidFilename)

        guard fm.fileExists(atPath: url.path) else {
            // No manifest is not the same as no history, and this used to
            // return `.idle` without asking. `--clean` deletes the manifest,
            // and the pipeline does not write a new one until ingest has
            // finished (`pipeline.py` runs `ingest()` before `write_manifest`),
            // so every re-analysis passes through a window where `run_failed`
            // is on disk and the manifest is not — and ingest is where the
            // batch-killing failures live. Answering `.idle` there dropped the
            // failure on the floor: the row went silent, and `Show Diagnostics…`
            // is gated on the failure state, so the recorded cause became
            // unreachable through the UI at the same moment.
            //
            // `stagesComplete: []` because there is no manifest to read it
            // from. Only `.partial` / `.stopped` consult it, and neither is
            // reachable without a manifest.
            if fm.fileExists(atPath: eventsURL.path),
               let derived = EventLogReader.deriveState(
                   eventsURL: eventsURL,
                   pidURL: pidURL,
                   stagesComplete: [],
               ) {
                return derived
            }
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
                return .unreachable(reason: .damaged)
            }
            stages = parsedStages
        } catch {
            return .unreachable(reason: .unreadable)
        }

        // Phase 1f Slice 4 — prefer the events log when present. Falls back
        // to the strict manifest inference below for projects that predate
        // the events log (backward compatibility).
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
        // A new run owns the row: a re-read of the last run's end state must
        // not land on it (R29).
        slowEndRereads.removeValue(forKey: project.id)?.cancel()
        guard hasConsent() else {
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
        // Nor over a run another process owns (a CLI run): it holds the output
        // folder, so ours could only fail, as "another run is in progress",
        // and that failure would stick over the CLI run's own end (R22).
        if isForeignRunning(project.id) {
            Self.logger.warning(
                "start ignored — a run this app does not own is live for project=\(project.id.uuidString, privacy: .public)"
            )
            return
        }

        // No key to inject → the run could only fail, in Python's setup check,
        // after a sidecar launch. Say so now instead: the row takes the failure
        // glyph, its popover offers Settings ▸ LLM Provider, and Analyse retries
        // once a key is saved. Not for a project already running or queued:
        // starting one of those does nothing, and must not overwrite its state.
        let chosen = UserDefaults.standard.string(forKey: "activeProvider")
            .flatMap(LLMProvider.init(rawValue:))
        if currentlyRunning != project.id, !queue.contains(project.id),
           let refusal = Self.providerRefusal(keyReadiness(), chosen: chosen) {
            Self.logger.notice(
                "start refused — no API key for the active provider (project=\(project.id.uuidString, privacy: .public))"
            )
            state[project.id] = refusal
            return
        }

        if currentlyRunning == nil {
            spawn(project: project, clean: clean)
        } else if currentlyRunning != project.id || currentRun == nil {
            // The second case: this study's run has ended and its end state is
            // being read. A start now — a drop onto it in its last moment — is
            // a new request and waits its turn. Starting a study whose run is
            // live does nothing, as before.
            queue.enqueue(project.id, clean: clean)
            renumberQueue()
        }
    }

    /// Cancel the current run (if it's for `project`) or remove it from the
    /// queue. SIGINT for graceful Python shutdown — the CLI flushes manifest
    /// writes in its `atexit` handlers, so cancelled runs are still safe to
    /// resume — then SIGTERM and SIGKILL if the run does not end
    /// (`cancelLadder`).
    func cancel(project: Project) {
        // A run this app can't signal: nothing is sent, so nothing may read
        // "Stopping…" — a progress left by an earlier run of ours would.
        if isForeignRunning(project.id) {
            // A CLI run, say: App Sandbox refuses a signal to a process outside
            // it. What Stop should offer here is open (R22).
            Self.logger.notice(
                "Stop on a run this app does not own project=\(project.id.uuidString, privacy: .public) — nothing sent"
            )
            return
        }
        // Acknowledge the click immediately on the UI so the user
        // doesn't keep mashing Stop while signals propagate.
        liveData.mutateProgress(for: project.id) { p in
            p.isStopping = true
        }
        if currentlyRunning == project.id, let run = currentRun {
            // Once per run: a second click sends nothing more and starts no
            // second ladder.
            if run.isRunning(), !cancellationRequested {
                cancellationRequested = true
                // The run's whole process group, as `Process.interrupt()` did
                // (measured 20 Oct 2026: it reaches a forked child too), so
                // SIGKILL also takes the run's own children.
                let target = signalTarget(run.pid)
                let err = sendSignal(target, SIGINT)
                if err == 0 {
                    Self.logger.info(
                        "SIGINT to run project=\(project.id.uuidString, privacy: .public) target=\(target, privacy: .public)"
                    )
                } else if err != ESRCH {
                    // Nothing was sent: leave Stop free to try again.
                    Self.logger.error(
                        "SIGINT to run failed errno=\(err, privacy: .public) project=\(project.id.uuidString, privacy: .public) target=\(target, privacy: .public)"
                    )
                    cancellationRequested = false
                    return
                }
                // SIGINT alone waits for a long C call to return — Stop during
                // transcription sat on "Stopping…" for minutes (R20). The same
                // ladder as an attached orphan's. A hosted run already
                // stopping ignores SIGTERM (`run_lifecycle._signal_handler`);
                // SIGKILL needs no handler.
                let gen = generation
                let signal = sendSignal
                escalateCancel(
                    pid: target, projectID: project.id,
                    stillRunning: { [weak self] in
                        guard let self, self.generation == gen else { return false }
                        // A group outlives its leader while any member lives,
                        // and its id is not reused until then, so a worker the
                        // leader left behind still gets the rest of the ladder.
                        if target < 0 { return signal(target, 0) == 0 }
                        return self.currentRun?.isRunning() == true
                    },
                    send: { signal(target, $0) }
                )
            }
            // The termination handler will clear currentlyRunning and dequeue.
        } else if let pid = attachedOrphanPIDs[project.id] {
            // Stop an attached orphan. Trust the attach: we only set
            // attachedOrphanPIDs for PIDs that aliveOwnedRunPID confirmed
            // were ours. Send SIGINT directly and interpret errno —
            // re-verifying via /bin/ps was racy (PID-file write delays,
            // ps exec hiccups) and the silent skip path was the
            // Stop-is-a-lie alpha blocker (24 Apr 2026). The orphan was
            // spawned by an earlier launch, so it leads its own process group
            // as an owned run does, and the signals go to the group too.
            let target = signalTarget(pid)
            let err = sendSignal(target, SIGINT)
            if err == 0 {
                Self.logger.info(
                    "SIGINT to attached orphan project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public) target=\(target, privacy: .public)"
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
                scheduleOrphanCancelEscalation(pid: pid, target: target, projectID: project.id)
            } else if err == ESRCH {
                // Process already gone (raced our cancel). Treat as
                // success and run the same teardown the poll task would.
                Self.logger.info(
                    "orphan already exited project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
                )
                handleOrphanExit(projectID: project.id, project: project)
            } else if err == EPERM {
                // Not ours after all — leave state intact, surface in log.
                // Should not happen given attach-time ownership check.
                Self.logger.error(
                    "SIGINT denied (EPERM) project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
                )
            } else {
                Self.logger.error(
                    "SIGINT failed errno=\(err, privacy: .public) project=\(project.id.uuidString, privacy: .public) pid=\(pid, privacy: .public)"
                )
            }
        } else if queue.remove(project.id) {
            state[project.id] = .idle
            renumberQueue()
        }
    }

    /// Escalate from SIGINT to SIGTERM to SIGKILL if the orphan won't
    /// die. Bail out at any step once nothing is left: for a group, when no
    /// member is alive (its id is not reused until then, so a worker the run
    /// left behind still gets the ladder after `handleOrphanExit`); for a bare
    /// pid, when it is dead or the attach has changed (project was
    /// re-cancelled with a new run, or orphan poll task already ran
    /// handleOrphanExit).
    private func scheduleOrphanCancelEscalation(pid: pid_t, target: pid_t, projectID: UUID) {
        let signal = sendSignal
        escalateCancel(
            pid: target, projectID: projectID,
            stillRunning: { [weak self] in
                if target < 0 { return signal(target, 0) == 0 }
                return signal(pid, 0) == 0 && self?.attachedOrphanPIDs[projectID] == pid
            },
            send: { signal(target, $0) }
        )
    }

    /// Stop's ladder after SIGINT: SIGTERM at +5 s, SIGKILL 3 s later.
    /// Whisper / torch / ctranslate2 hold the GIL during long C calls, so a
    /// Python signal handler can be deferred 30–60s during model load. The
    /// user clicked Stop; their contract is "this stops".
    nonisolated static let cancelLadder: [(signal: Int32, after: Duration)] = [
        (SIGTERM, .seconds(5)), (SIGKILL, .seconds(3)),
    ]

    /// Run `cancelLadder`, checking before each step that the run is still
    /// the one Stop was for and still alive.
    private func escalateCancel(
        pid: pid_t, projectID: UUID,
        stillRunning: @escaping @MainActor () -> Bool,
        send: @escaping @MainActor (Int32) -> Int32
    ) {
        let sleep = escalationSleep
        Task { @MainActor in
            for step in Self.cancelLadder {
                await sleep(step.after)
                guard stillRunning() else { return }
                let err = send(step.signal)
                if err != 0 {
                    Self.logger.error(
                        "escalation signal=\(step.signal, privacy: .public) failed errno=\(err, privacy: .public) pid=\(pid, privacy: .public) project=\(projectID.uuidString, privacy: .public)"
                    )
                } else if step.signal == SIGKILL {
                    Self.logger.error(
                        "SIGKILL escalation pid=\(pid, privacy: .public) project=\(projectID.uuidString, privacy: .public) — SIGTERM didn't take"
                    )
                } else {
                    Self.logger.warning(
                        "SIGTERM escalation pid=\(pid, privacy: .public) project=\(projectID.uuidString, privacy: .public) — SIGINT didn't take"
                    )
                }
            }
            // SIGKILL cannot be caught, but a process in an uninterruptible
            // wait (a dataless iCloud read) takes it only when the wait ends.
            await sleep(.seconds(1))
            if stillRunning() {
                Self.logger.fault(
                    "run survived SIGKILL pid=\(pid, privacy: .public) project=\(projectID.uuidString, privacy: .public) — Stop cannot finish"
                )
            }
        }
    }

    /// Where Stop's signals go for a run this process spawned: its process
    /// group when it leads one (Foundation makes each child a group leader),
    /// never the app's own group, otherwise the pid alone.
    nonisolated static func ownedSignalTarget(
        pid: pid_t, processGroup: pid_t, ownGroup: pid_t
    ) -> pid_t {
        processGroup == pid && processGroup != ownGroup ? -pid : pid
    }

    // MARK: - Quit

    /// Quitting the app stops every run it knows about: the run it spawned and
    /// any orphan it attached to (`docs/design-subprocess-lifecycle.md`
    /// §Quit propagation, planned there as `stopAll`). Without this a run
    /// outlived the app until its next print — its stdout is a pipe to us, the
    /// write failed with EPIPE, and Python recorded `run_failed` — so a
    /// relaunch read "Resuming…" and then "CLI exited with code 1" (R19,
    /// 20 Oct 2026). SIGINT records `run_cancelled` instead, which reads
    /// "Stopped" and resumes from the cache, even with the pipe closing a
    /// moment later (measured against the real CLI, mid-transcription
    /// included).
    ///
    /// No escalation: the app is gone before a timer could fire, and a run
    /// wedged in a C call takes the signal when the call returns. The queue
    /// lives in memory and is not kept; it is logged so the loss is on record.
    func stopAllForQuit() {
        let owned = currentRun.flatMap { $0.isRunning() ? $0.pid : nil }
        let targets = Self.quitSignalTargets(
            owned: owned, orphans: Array(attachedOrphanPIDs.values)
        )
        // Each run's group, as Stop does, so a run's own children hear it too.
        for pid in targets {
            let target = signalTarget(pid)
            let err = sendSignal(target, SIGINT)
            if err == 0 {
                Self.logger.info("quit: SIGINT to run pid=\(pid, privacy: .public) target=\(target, privacy: .public)")
            } else if err == ESRCH {
                // Already gone between polls — the outcome Quit wanted.
                Self.logger.info("quit: run pid=\(pid, privacy: .public) already exited")
            } else {
                Self.logger.error("quit: SIGINT to run pid=\(pid, privacy: .public) target=\(target, privacy: .public) failed errno=\(err, privacy: .public)")
            }
        }
        if !queue.isEmpty {
            Self.logger.warning("quit: \(self.queue.count, privacy: .public) queued run(s) not kept across launches")
        }
    }

    /// Each live run once, in a stable order.
    nonisolated static func quitSignalTargets(owned: pid_t?, orphans: [pid_t]) -> [pid_t] {
        Set(orphans + (owned.map { [$0] } ?? [])).sorted()
    }

    // MARK: - Spawn

    /// Spawn the subprocess. When `clean` is true, `--clean` is added — used
    /// by Re-analyse. Queued spawns carry the flag through the queue (R18).
    private func spawn(project: Project, clean: Bool = false) {
        // A study whose folder has gone — a drive ejected while it waited, or
        // before Analyse — is not run against the missing path (R63). It reads
        // as a scan of that folder would (`parseManifest`), and the next study
        // in the queue goes ahead.
        if case .cantFind = project.availability {
            Self.logger.notice(
                "spawn refused — folder not found project=\(project.id.uuidString, privacy: .public)"
            )
            state[project.id] = .unreachable(reason: .folderMissing)
            startNextQueued()
            return
        }
        let sidecar: (binary: URL, mode: SidecarMode)?
        // A test passes a lookup beside its launcher to reach a failed one;
        // otherwise a launcher means there is no sidecar to find.
        if launcher == nil || sidecarLookup != nil {
            guard let resolved = resolveSidecar(for: project) else {
                startNextQueued()
                return
            }
            sidecar = resolved
        } else {
            sidecar = nil
        }

        generation += 1
        let gen = generation
        currentlyRunning = project.id
        currentProject = project
        currentParser = StdoutProgressParser()
        cancellationRequested = false
        let provider = activeProvider()
        runProviders[project.id] = provider
        beginSpawnedRun(project)
        startProgressPoll(for: project, generation: gen)

        let projectID = project.id
        let onExit: @Sendable (ProcessOutcome) -> Void = { [weak self] outcome in
            Task { @MainActor in
                await self?.handleTermination(
                    projectID: projectID, outcome: outcome, generation: gen
                )
            }
        }

        do {
            let run: LaunchedRun
            if let launcher {
                run = try launcher(project, clean, onExit)
            } else if let sidecar {
                run = try launchSidecar(
                    sidecar.binary, mode: sidecar.mode, project: project,
                    clean: clean, generation: gen, onExit: onExit
                )
            } else {
                preconditionFailure("spawn: no launcher and no sidecar")
            }
            currentRun = run
            if let output = run.output {
                currentReadTask = readOutput(output, for: projectID, generation: gen)
            }
            // Tiny race here: if the app crashes between the launch returning
            // and writePIDFile completing, the orphan exists but is
            // unattachable on next launch. Window is single-process-spawn
            // wide (~ms); accepted rather than working around it with a
            // separate `lsof`-style argv sweep on launch.
            Self.writePIDFile(for: project, pid: run.pid, provider: provider)
            Self.logger.info(
                "spawned bristlenose run project=\(projectID.uuidString, privacy: .public) pid=\(run.pid, privacy: .public)"
            )
        } catch {
            Self.logger.error(
                "launch failed project=\(projectID.uuidString, privacy: .public): \(error.localizedDescription, privacy: .public)"
            )
            currentlyRunning = nil
            currentProject = nil
            currentRun = nil
            currentReadTask?.cancel()
            currentReadTask = nil
            progressPollTasks[projectID]?.cancel()
            progressPollTasks[projectID] = nil
            runProviders[projectID] = nil
            state[projectID] = .failed(
                // `localizedDescription` is Foundation's, already in the user's
                // language — it passes through as a variable rather than being
                // re-described by us.
                FailureMessage.keyed(
                    "desktop.pipeline.failure.launchFailed",
                    vars: ["reason": error.localizedDescription]
                ),
                category: .unknown
            )
            startNextQueued()
        }
    }

    /// Resolve the sidecar binary the same way ServeManager does. Three
    /// shapes of failure: external-server scheme has no binary to spawn,
    /// resolver itself can fail (bundle missing, dev path invalid), and
    /// both surface as `.failed` state on the project so the GUI shows
    /// something actionable. Nil after writing that state.
    private func resolveSidecar(for project: Project) -> (binary: URL, mode: SidecarMode)? {
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
        let resolved = sidecarLookup?() ?? SidecarMode.resolve(
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
                // `.external` is unreachable in Release (the dev env-var reads above
                // are #if DEBUG-only, so resolve() never yields .external). Keep the
                // dev env-var NAMES out of the Release Mach-O — check-release-binary.sh
                // gates on their absence. Full dev advice stays in Debug.
                #if DEBUG
                let message = "Pipeline runs can't use the external-server dev mode. Unset BRISTLENOSE_DEV_EXTERNAL_PORT (or use BRISTLENOSE_DEV_SIDECAR_PATH instead) and try again."
                #else
                let message = "Pipeline runs can't use the external-server dev mode."
                #endif
                Self.logger.error(
                    "spawn refused: external-server scheme has no binary project=\(project.id.uuidString, privacy: .public)"
                )
                // Dev-scheme chrome — `.external` is unreachable in Release, so
                // this sentence can only be read by someone running from Xcode.
                // English by decision (`docs/design-i18n.md` §"Which surfaces").
                state[project.id] = .failed(.passthrough(message), category: .unknown)
                return nil
            }
        case .failure(let err):
            Self.logger.error(
                "spawn binary resolve failed: \(err.localizedDescription, privacy: .public) project=\(project.id.uuidString, privacy: .public)"
            )
            // `SidecarResolveError`'s own words. Three of its four cases are
            // dev-only; `bundledSidecarMissing` is not, and is still English —
            // registered in `docs/i18n-defects.md`, not fixed here, because it
            // needs the discriminator treatment its own siblings got.
            state[project.id] = .failed(
                .passthrough(err.localizedDescription), category: .unknown
            )
            return nil
        }
        return (binary, resolvedMode)
    }

    /// Launch the sidecar's `run` for `project`: the app's `RunLauncher`.
    private func launchSidecar(
        _ binary: URL, mode resolvedMode: SidecarMode, project: Project,
        clean: Bool, generation gen: Int,
        onExit: @escaping @Sendable (ProcessOutcome) -> Void
    ) throws -> LaunchedRun {
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
        // Defence in depth for the same failure. stdout/stderr are piped, but
        // stdin was inherited — under Xcode that is the console TTY, so any
        // prompt sees a terminal and waits for a human who cannot see it.
        // With /dev/null the read returns EOF and the run ends with an error
        // instead of hanging, whatever future prompt someone adds upstream.
        proc.standardInput = FileHandle.nullDevice
        let handle = pipe.fileHandleForReading

        // Read off-main into a stream the runner consumes (`readOutput`), so the
        // runner can tell when the last line has been delivered (R25).
        let (output, lines) = AsyncStream<String>.makeStream()
        Task.detached {
            let fh = handle
            // Accumulate across read boundaries so a `✓ stage name` line
            // straddling two `availableData` chunks is delivered intact.
            var buffer = ""
            while true {
                let data = fh.availableData
                if data.isEmpty {
                    // EOF — flush any unterminated final line.
                    if !buffer.isEmpty {
                        lines.yield(buffer)
                    }
                    break
                }
                guard let chunk = String(data: data, encoding: .utf8) else { continue }
                buffer.append(chunk)
                while let nl = buffer.firstIndex(of: "\n") {
                    let line = String(buffer[..<nl])
                    buffer = String(buffer[buffer.index(after: nl)...])
                    if !line.isEmpty {
                        lines.yield(line)
                    }
                }
            }
            lines.finish()
        }

        proc.terminationHandler = { p in
            // BOTH fields, always. terminationStatus carries the SIGNAL NUMBER
            // when the process was killed, and only terminationReason says
            // which of the two numbers this is. See ProcessOutcome.
            onExit(ProcessOutcome(status: p.terminationStatus, reason: p.terminationReason))
        }

        try proc.run()
        return LaunchedRun(
            pid: proc.processIdentifier,
            isRunning: { proc.isRunning },
            output: output
        )
    }

    /// Deliver a run's output to `handleLine` on the main actor, in order. The
    /// task ends when the pipe closes, which is how `handleTermination` knows
    /// the last line is in (R25).
    private func readOutput(
        _ output: AsyncStream<String>, for projectID: UUID, generation gen: Int
    ) -> Task<Void, Never> {
        Task { @MainActor [weak self] in
            for await line in output {
                self?.handleLine(line, for: projectID, generation: gen)
            }
        }
    }

    /// Wait for a run's output to be read to its end, but no longer than
    /// `outputDrainLimit`: a child the run left behind can hold the pipe open.
    private func waitForOutput(_ reader: Task<Void, Never>?) async {
        guard let reader else { return }
        let limit = outputDrainLimit
        await withCheckedContinuation { (done: CheckedContinuation<Void, Never>) in
            let once = ResumeOnce<Void>(done)
            Task { @MainActor in
                await reader.value
                once.resume(())
            }
            Task { @MainActor in
                try? await Task.sleep(for: limit)
                if !once.resumed {
                    Self.logger.notice("run output still open \(limit, privacy: .public) after exit — deciding without the rest")
                }
                once.resume(())
            }
        }
    }

    private func handleLine(_ line: String, for projectID: UUID, generation gen: Int) {
        // Drop lines from a stale generation — the terminationHandler from a
        // previous run can fire after we've spawned the next one.
        guard gen == generation else { return }

        let clean = BristlenoseShared.stripANSI(line)
        // The run's engine, printed once at its Whisper preflight. On Apple's
        // model the app fetches Whisper behind it; the run itself never does.
        if clean.hasPrefix("@transcription-engine ") {
            if clean.hasSuffix(" apple") {
                NotificationCenter.default.post(name: .bristlenoseAppleSpeechRunStarted, object: nil)
            }
            return
        }
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
        projectID: UUID, outcome: ProcessOutcome, generation gen: Int
    ) async {
        guard gen == generation else {
            Self.logger.error(
                "termination of a superseded run project=\(projectID.uuidString, privacy: .public) — ignored"
            )
            return
        }
        // Everything downstream has always keyed off this number; ProcessOutcome
        // adds the meaning the number was missing, it does not redefine it.
        let status = outcome.rawStatus

        let project = projectIndex?.projects.first(where: { $0.id == projectID })
        if let project {
            Self.removePIDFile(for: project)
        }
        let provider = runProviders.removeValue(forKey: projectID)
        currentRun = nil
        // Not cancelled: a failed run's verdict waits below for its last lines
        // (R25), and anything later still reaches the popover's output.
        let reader = currentReadTask
        currentReadTask = nil
        progressPollTasks[projectID]?.cancel()
        progressPollTasks[projectID] = nil
        // NOTE: state[projectID] stays `.running` until the manifest-read
        // await below resolves, and so does the slot (`currentlyRunning`):
        // a `start` in this window queues behind it rather than spawning.
        // Freed before the await, the slot went to whatever started next,
        // which moved `generation`, and the guard after the await then left
        // this study on "Analysing" for good — holding the sleep assertion
        // until quit (R23, 20 Oct 2026). cancel() finds no `currentRun`, so a
        // Stop click here is a clean no-op. The spinner-into-the-void is a
        // sub-5s papercut on slow disks; flipping to a transient state here
        // would race with any concurrent passive sidebar scan that preserves
        // .running.

        // Cancellation only takes effect on a non-zero exit — if the sidecar
        // raced the cancel and finished cleanly anyway, we keep the result.
        if status != 0, cancellationRequested {
            cancellationRequested = false
            // Say what the run left, as Stop on a reconnected run does
            // (`handleOrphanExit`): "Stopped" from its `run_cancelled`. This
            // wrote `.idle` until 20 Oct 2026, so the app's own Stop left the
            // row blank (R21). The slot is held across the read, as below (R23).
            var stopped = PipelineState.idle
            if let project {
                stopped = await Self.readManifestState(
                    at: Self.manifestURL(for: project), timeout: endStateTimeout,
                    read: manifestRead
                )
            }
            guard gen == generation else {
                Self.logger.error(
                    "stop superseded during its end-state read project=\(projectID.uuidString, privacy: .public) — state not written"
                )
                return
            }
            // The run has exited; nothing it left can make it running.
            if case .running = stopped { stopped = .idle }
            releaseSlot()
            state[projectID] = stopped
            if stopped == .unreachable(reason: .timedOut), let project {
                rereadAfterSlowEnd(project, priorRunId: priorRunIds[projectID])
            }
            Self.logger.info(
                "run cancelled project=\(projectID.uuidString, privacy: .public) state=\(String(describing: stopped), privacy: .public)"
            )
            startNextQueued()
            return
        }

        // The process can end before its last lines are read: the reader hands
        // them over one main-actor turn at a time, and a traceback is many
        // lines. Snapshotted at once, a run that died explaining why read
        // "Failed" (unknown), and the explanation landed a moment later
        // (R25, 20 Oct 2026: 16 of 30 real exits missed their last line).
        let lines: [String]
        if status == 0 {
            lines = []
        } else {
            await waitForOutput(reader)
            lines = liveData.snapshotOutput(for: projectID)
        }
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
            // Unreachable while the slot is held: nothing can spawn until
            // `releaseSlot` below. If it ever fires, a newer run owns the slot.
            guard gen == generation else {
                Self.logger.error(
                    "termination superseded during its end-state read project=\(projectID.uuidString, privacy: .public) — state not written"
                )
                return
            }
        } else {
            // Non-zero exit + no success markers — skip the disk read.
            derived = .idle
        }

        let decision = Self.decideTermination(
            exitStatus: status,
            sidecarReportedSuccess: sidecarReportedSuccess,
            derived: derived
        )
        releaseSlot()

        switch decision {
        case .accept(let final):
            state[projectID] = final
            if final == .unreachable(reason: .timedOut), let project {
                rereadAfterSlowEnd(project, provider: provider, priorRunId: priorRunIds[projectID])
            }
            if case .ready = final {
                noteCreditIfTheRunUsedAnLLM(
                    provider: provider, project: project,
                    terminus: project.flatMap { EventLogReader.tailEvent(at: Self.eventsURL(for: $0)) },
                    priorRunId: priorRunIds[projectID]
                )
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
                outcome: outcome, lines: lines
            )
        }

        startNextQueued()
    }

    /// Read a run's end state again after its read timed out (R29).
    ///
    /// The run ended; the disk was slow (a sleeping drive, a network share),
    /// so the 5 s read gave up and the row said "Not responding". The
    /// termination path accepted that on the promise of a later passive scan,
    /// and there is none: the row stayed until relaunch. Read again every
    /// `slowEndRereadInterval`, at most `slowEndRereadLimit` times. One read at
    /// a time: a read slower than the wait is waited on again, not discarded
    /// or stacked, so a share that always takes longer than the timeout still
    /// answers. Applied only while the row still shows the time-out; starting
    /// the study again cancels it (`start`). What it finds is applied as a
    /// scan's would be: a run another process owns gets its watch, and a run
    /// that finished whole clears a stale out-of-credit verdict for
    /// `provider`, as the termination path does on `.ready`. `priorRunId` is
    /// the terminus newest when the run began: `priorRunIds` for a spawned run,
    /// `orphanPriorTerminus` for an attached one. The attached run's exit path
    /// (`handleOrphanExit`) re-reads the same way.
    private func rereadAfterSlowEnd(
        _ project: Project, provider: LLMProvider? = nil, priorRunId: String?
    ) {
        let projectID = project.id
        let url = Self.manifestURL(for: project)
        let read = manifestRead
        let interval = slowEndRereadInterval
        let token = UUID()
        slowEndRereads[projectID]?.cancel()
        slowEndRereadTokens[projectID] = token
        slowEndRereads[projectID] = Task { @MainActor [weak self] in
            var pending: Task<PipelineState, Never>?
            for _ in 0..<Self.slowEndRereadLimit {
                try? await Task.sleep(for: interval)
                guard !Task.isCancelled,
                      self?.state[projectID] == .unreachable(reason: .timedOut) else { break }
                let reading = pending ?? Task.detached { await read(url) }
                pending = reading
                guard let resolved = await Self.value(of: reading, within: interval) else {
                    continue
                }
                pending = nil
                guard !Task.isCancelled, let self,
                      self.state[projectID] == .unreachable(reason: .timedOut) else { break }
                Self.logger.info(
                    "a run's end state read on a later try project=\(projectID.uuidString, privacy: .public) state=\(String(describing: resolved), privacy: .public)"
                )
                self.applyScanResult(resolved, for: projectID)
                if case .running = self.state[projectID], !self.ownsRun(projectID) {
                    self.watchForeignRun(project)
                }
                if case .ready = resolved {
                    self.noteCreditIfTheRunUsedAnLLM(
                        provider: provider, project: project,
                        terminus: EventLogReader.tailEvent(at: Self.eventsURL(for: project)),
                        priorRunId: priorRunId
                    )
                }
                break
            }
            if let self, self.slowEndRereadTokens[projectID] == token {
                if self.state[projectID] == .unreachable(reason: .timedOut) {
                    Self.logger.warning(
                        "a run's end state still did not read after \(Self.slowEndRereadLimit, privacy: .public) tries project=\(projectID.uuidString, privacy: .public)"
                    )
                }
                self.slowEndRereads[projectID] = nil
                self.slowEndRereadTokens[projectID] = nil
            }
        }
    }

    /// About a minute of re-reads at the default interval.
    static let slowEndRereadLimit = 12

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
            //   .unreachable → accept (slow disk; a timed-out read is read
            //                  again by `rereadAfterSlowEnd`, R29)
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
        let derived = await Self.readManifestState(
            at: Self.manifestURL(for: project), timeout: endStateTimeout, read: manifestRead
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
        outcome: ProcessOutcome, lines: [String]
    ) -> PipelineState {
        // Same number every branch here has always used; `outcome` carries the
        // extra fact of whether it is an exit code or a signal, for the logs.
        let status = outcome.rawStatus
        // Prefer the structured cause emitted by the Python abandon path
        // (`pipeline-events.jsonl` → `run_failed` → `cause.{category,message}`)
        // — but only when that terminus belongs to THIS attempt. The file is
        // append-only, so an attempt refused before the lifecycle opens finds a
        // previous run's cause sitting at the tail. Stdout regex is then the
        // fallback, as it already is for older Python versions and crash-style
        // failures that exit before writing a terminus at all.
        let liveProgress = liveData.progress[projectID]
        let derived = project.flatMap {
            Self.deriveFailureFromEvents(
                project: $0,
                spawnedAt: liveProgress?.startedAt,
                attachedFromOrphan: liveProgress?.attachedFromOrphan ?? false
            )
        }
        // The run used whatever provider was active when it spawned; unless the
        // user switched since exit (rare, and harmless), that's still the live
        // `activeProvider`. Same source `overlayAPIKeys` reads at spawn time.
        let activeProvider = UserDefaults.standard.string(forKey: "activeProvider")
            .flatMap(LLMProvider.init(rawValue:))
        let category: PipelineFailureCategory
        let summary: FailureMessage
        if let (cat, msg) = derived {
            category = cat
            // Python's own sentence wins when it has one — it is more specific
            // than anything a category can say — and passes through untouched,
            // English, as the events log is a forensic record.
            summary = msg.map(FailureMessage.passthrough)
                ?? FailureMessage.failure(for: cat, provider: activeProvider)
        } else {
            category = Self.categoriseFailure(
                lines: lines, exitStatus: status, projectName: project?.name,
                provider: activeProvider
            )
            summary = FailureMessage.failure(for: category, provider: activeProvider)
        }
        Self.logger.warning(
            """
            run failed project=\(projectID.uuidString, privacy: .public) \
            \(outcome.logDescription, privacy: .public) \
            category=\(category.rawValue, privacy: .public)\
            \(outcome.diagnosticHint.map { " " + $0 } ?? "", privacy: .public)
            """
        )
        // Persist the (already key-redacted) stderr tail so a mislabelled
        // category isn't the only forensic trace. The classifier is a guess;
        // this file is the ground truth. Greppable at
        // `<output>/.bristlenose/last-run-failure.log`.
        if let project, !lines.isEmpty {
            Self.captureFailureLog(
                project: project, outcome: outcome, category: category, lines: lines
            )
        }
        // Light the app-global out-of-credit pill immediately on a real run
        // that failed on billing (the pill reads LLMValidator's verdict cache,
        // which a run 402 wouldn't otherwise touch until Settings re-validates).
        // Keyed on the distinct billing category, and attributed to the run's
        // provider — a transient rate-limit (.quota) can't false-alarm.
        if category == .outOfCredit {
            OutOfCreditModel.recordActiveProviderOutOfCredit(provider: activeProvider)
        }
        return .failed(summary, category: category)
    }

    /// Write the redacted stderr tail of a failed run to
    /// `bristlenose-output/.bristlenose/last-run-failure.log` and emit the tail
    /// to the unified log. Best-effort — never throws into the failure path.
    private static func captureFailureLog(
        project: Project, outcome: ProcessOutcome,
        category: PipelineFailureCategory, lines: [String]
    ) {
        let tail = lines.suffix(50).joined(separator: "\n")
        Self.logger.error(
            """
            failure stderr tail category=\(category.rawValue, privacy: .public) \
            \(outcome.logDescription, privacy: .public):
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
        // `status=4` for a signalled death sent a reader to an exit-code table
        // that does not exist. Name the signal, and say where the OS put the
        // stack trace.
        var header = "category=\(category.rawValue) \(outcome.logDescription)\n"
        if let hint = outcome.diagnosticHint {
            header += "\(hint)\n"
        }
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

    /// The run is over and its end state is about to be written: the slot is
    /// free for the next.
    private func releaseSlot() {
        currentlyRunning = nil
        currentProject = nil
    }

    private func startNextQueued() {
        guard let next = queue.popFirst() else { return }
        let nextID = next.id
        renumberQueue()

        guard let index = projectIndex else {
            // Index not wired — keep the ID visible as queued so we don't
            // silently drop the user's request, and log so a missing
            // setProjectIndex() call shows up.
            Self.logger.error(
                "startNextQueued: no projectIndex for project=\(nextID.uuidString, privacy: .public) — leaving queued"
            )
            queue.pushFront(next)
            renumberQueue()
            return
        }
        guard let project = index.projects.first(where: { $0.id == nextID }) else {
            // Removed from the sidebar while it waited. Put back at the head,
            // it was popped and re-inserted at every turn and nothing behind
            // it ever ran.
            Self.logger.notice(
                "startNextQueued: project=\(nextID.uuidString, privacy: .public) no longer in the sidebar — dropped from the queue"
            )
            state[nextID] = nil
            startNextQueued()
            return
        }
        spawn(project: project, clean: next.clean)
    }

    // MARK: - Queue management

    private func renumberQueue() {
        for (offset, id) in queue.ids.enumerated() {
            state[id] = .queued(position: offset + 1)
        }
    }

    // MARK: - Failure categorisation

    /// The state a run is refused with when it has no key to carry, or nil to
    /// let it start. `chosen` is the provider the researcher picked, if any: the
    /// fallback to Python's default is not a choice, and "Claude isn't set up
    /// yet" said to someone who never picked Claude would be a small lie.
    nonisolated static func providerRefusal(
        _ readiness: BristlenoseShared.APIKeyReadiness, chosen: LLMProvider?
    ) -> PipelineState? {
        guard case .missing = readiness else { return nil }
        return .failed(
            FailureMessage.failure(for: .providerNotSetUp, provider: chosen),
            category: .providerNotSetUp
        )
    }

    /// Regex-based mapping from stderr tail + exit status to a
    /// `PipelineFailureCategory`. Keep heuristics here so display code stays
    /// category-only.
    static func categoriseFailure(
        lines: [String], exitStatus: Int32, projectName: String? = nil,
        provider: LLMProvider? = nil
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
        // No provider the run could use. The setup check prints it in its table
        // ("✗ API key  No Anthropic API key") and exits before the run's
        // lifecycle opens, so no terminus carries a cause. A healthy row names
        // the key instead ("✓ API key  Claude (sk-…)"), so "no … api key" is
        // only ever the failure.
        if matches(
            tail,
            #"no (anthropic|openai|azure openai|google gemini) api key|no azure openai (endpoint|deployment name)|no ai provider configured"#
        ) {
            return .providerNotSetUp
        }
        if matches(tail, #"401|invalid api key|authentication"#) { return .auth }
        // Out of credit (billing) BEFORE the transient rate-limit bucket —
        // Anthropic serves it as a 400 + "credit balance is too low", OpenAI as
        // a 429 with code `insufficient_quota`. Provider-scoped to Claude/ChatGPT
        // (mirrors the Python classifier): Azure bills by subscription quota and
        // Gemini folds billing into RESOURCE_EXHAUSTED, so their `insufficient_
        // quota` stays a transient `.quota`, not a top-up-able credit wall.
        if provider == .claude || provider == .chatGPT {
            if matches(tail, #"credit balance|insufficient_quota|billing_error|exceeded your current quota"#) {
                return .outOfCredit
            }
        }
        if matches(tail, #"rate limit|quota|429"#) { return .quota }
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

    /// Wire format for `started_at`: Python writes
    /// `datetime.now(utc).isoformat()` with `+00:00` swapped for `Z`, so
    /// microseconds are present whenever they are non-zero and absent when they
    /// are not. Both spellings have to parse — the committed smoke fixture uses
    /// the second.
    private static let iso8601WithFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let iso8601Plain = ISO8601DateFormatter()

    nonisolated static func parseEventTimestamp(_ raw: String) -> Date? {
        iso8601WithFraction.date(from: raw) ?? iso8601Plain.date(from: raw)
    }

    /// A terminus event may describe a *previous* run, and must not be allowed
    /// to headline this one.
    ///
    /// `pipeline-events.jsonl` is append-only and is never truncated between
    /// runs, so its tail can hold a `run_failed` from hours ago. An attempt that
    /// is **refused before the lifecycle opens** — `outputExists` is the
    /// everyday one — writes no terminus of its own, so a naive tail read
    /// returns the stale one, and it then outranks the live stdout carrying the
    /// real blocker. Observed 19 Aug 2026: the popover headlined "EOF when
    /// reading a line" from an eleven-hour-old run while "Output directory
    /// already exists" sat below it under *Last output*. The researcher is told
    /// about a failure that is not the one standing in their way.
    ///
    /// `applyEventProgress` already guards this exact trap for the progress
    /// ring, and says so in its comment — but it gates by **run id**, which the
    /// failure path cannot use: a refused attempt never mints one. So this gates
    /// by time instead. A terminus that predates our spawn is not ours.
    ///
    /// Permissive on every unknown — no spawn time, an unparseable stamp, or an
    /// adopted orphan (whose run legitimately began before we attached) all
    /// return `true`. Suppressing a real cause is worse than showing a stale
    /// one; the grace window absorbs sub-second ordering between our `Date()`
    /// and Python's first write.
    nonisolated static func terminusIsCurrentAttempt(
        eventStartedAt: String?, spawnedAt: Date?, attachedFromOrphan: Bool
    ) -> Bool {
        if attachedFromOrphan { return true }
        guard let spawnedAt,
              let raw = eventStartedAt,
              let eventStart = parseEventTimestamp(raw) else { return true }
        return eventStart >= spawnedAt.addingTimeInterval(-terminusGraceSeconds)
    }

    /// Slack between our spawn `Date()` and the run's own `started_at`. Small
    /// enough that the eleven-hour case this exists for can never pass.
    static let terminusGraceSeconds: TimeInterval = 5

    /// Read the structured `cause` from `<project>/bristlenose-output/.bristlenose/
    /// pipeline-events.jsonl` if a `run_failed` terminus is present **and it
    /// belongs to the attempt that just ended**. Returns `(category, message)`,
    /// or `nil` when the events log is missing, the most recent event isn't
    /// `run_failed`, the line can't be decoded, or the terminus predates this
    /// attempt (see `terminusIsCurrentAttempt`).
    private static func deriveFailureFromEvents(
        project: Project, spawnedAt: Date?, attachedFromOrphan: Bool
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
        guard terminusIsCurrentAttempt(
            eventStartedAt: event.startedAt,
            spawnedAt: spawnedAt,
            attachedFromOrphan: attachedFromOrphan
        ) else {
            Self.logger.info(
                """
                ignoring stale run_failed terminus                 started_at=\(event.startedAt, privacy: .public) — it predates this attempt
                """
            )
            return nil
        }
        return (cause.category, cause.message)
    }

    private static func matches(_ haystack: String, _ pattern: String) -> Bool {
        haystack.range(of: pattern, options: .regularExpression) != nil
    }

    // MARK: - Consent

    /// Mirror of `ContentView.hasConsent` — same UserDefaults key the AppStorage
    /// property wraps. Pipeline guard is defence-in-depth; the real gate is
    /// the modal-blocking AIConsentView sheet.
    static var hasAIConsent: Bool {
        UserDefaults.standard.integer(forKey: "aiConsentVersion")
            >= AIConsentView.currentVersion
    }
}

/// Resumes a continuation once, whichever of two racing tasks gets there
/// first.
private final class ResumeOnce<T>: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<T, Never>?
    init(_ continuation: CheckedContinuation<T, Never>) { self.continuation = continuation }
    var resumed: Bool { lock.withLock { continuation == nil } }
    func resume(_ value: T) {
        let pending = lock.withLock { () -> CheckedContinuation<T, Never>? in
            defer { continuation = nil }
            return continuation
        }
        pending?.resume(returning: value)
    }
}
