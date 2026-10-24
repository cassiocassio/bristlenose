import Foundation
import os

/// Reads `pipeline-events.jsonl` (Phase 4a-pre) and derives a `PipelineState`.
///
/// The events log is the single source of truth for run-level outcome data.
/// "Current state" is derived by tail-reading the log. Stage-complete data
/// for `.partial` / `.stopped` cases is read from the manifest at display
/// time, not the events log.
///
/// Read is bounded: the last 64 KB of the file, widened (to at most
/// `tailLimit`) only while it holds no matching line. A run-started event line
/// is small (~200 B); a terminus event with a 4 KB capped `cause.message` is
/// well under 5 KB; but a live run's `run_progress` lines can fill 64 KB in
/// under a minute. See `docs/design-pipeline-resilience.md` §"Phase 4a-pre".
///
/// This file is the Swift mirror of `bristlenose/events.py`; case names
/// (`run_started` / `run_completed` / `run_cancelled` / `run_failed`) are
/// the contract. Don't drift the names.
enum EventLogReader {
    private static let logger = Logger(subsystem: "app.bristlenose", category: "events")

    /// Filename inside `<output>/.bristlenose/`.
    static let filename = "pipeline-events.jsonl"

    /// Filename of the Python-side PID file inside `<output>/.bristlenose/`.
    /// Distinct from Swift's own per-project PID file in App Support.
    static let pidFilename = "run.pid"

    /// Decoded shape of one event line. Most fields are optional because
    /// only `run_started` carries `process`, only terminus events carry
    /// `cause` / `outcome` / `ended_at`, and so on.
    struct Event: Codable, Equatable {
        let event: String
        let kind: String
        let runId: String
        let startedAt: String
        let endedAt: String?
        let outcome: String?
        let cause: Cause?
        /// Schema v5 (May 2026). Present on `run_completed` / `run_failed`
        /// terminus events once the run has begun populating per-stage
        /// outcomes. Schema-additive — older logs decode as `nil` and the
        /// `mapCompleted` / `run_failed` paths fall back to the pre-v5
        /// state derivations. See `tests/fixtures/pipeline-summary-contract.json`.
        let summary: PipelineSummary?

        // Phase 0b `run_progress` fields — present only on progress lines, all
        // optional (schema-additive; lifecycle events decode them as nil). The
        // current-run gate keys off the existing `runId`. These feed the ring
        // (`stageFraction` / `predictedTotalSeconds`) and the deferred subtitle
        // text (`stage` / `sessionsComplete` / `sessionsTotal` /
        // `etaRemainingSeconds`).
        let stage: String?
        let sessionsComplete: Int?
        let sessionsTotal: Int?
        let stageFraction: Double?
        let etaRemainingSeconds: Double?
        let predictedTotalSeconds: Double?
        /// Sessions with a readable transcript so far — a first analysis
        /// delivers them one by one (docs/design-progressive-lenses.md, Phase 1).
        /// Carried on every progress line once non-zero, so the newest line
        /// always has it.
        let sessionsReadable: Int?
        /// The slice of the ring the line's stage owns (R27): its base and
        /// span as shares of the run's expected time, and its expected
        /// seconds. Absent from an older sidecar and from a run with thin
        /// timing history, where the ring keeps its whole-run time fill.
        let stageBase: Double?
        let stageSpan: Double?
        let stageExpectedSeconds: Double?
        /// Token totals on a terminus, present only when the run made an LLM
        /// call that reported usage (`cost.compute_run_cost`): a run that
        /// finished from cache carries neither.
        let inputTokens: Int?
        let outputTokens: Int?

        enum CodingKeys: String, CodingKey {
            case event, kind
            case runId = "run_id"
            case startedAt = "started_at"
            case endedAt = "ended_at"
            case outcome
            case cause
            case summary
            case stage
            case sessionsComplete = "sessions_complete"
            case sessionsTotal = "sessions_total"
            case stageFraction = "stage_fraction"
            case etaRemainingSeconds = "eta_remaining_seconds"
            case predictedTotalSeconds = "predicted_total_seconds"
            case sessionsReadable = "sessions_readable"
            case stageBase = "stage_base"
            case stageSpan = "stage_span"
            case stageExpectedSeconds = "stage_expected_seconds"
            case inputTokens = "input_tokens"
            case outputTokens = "output_tokens"
        }
    }

    struct Cause: Codable, Equatable {
        let category: PipelineFailureCategory
        let message: String?
        let signalName: String?
        /// Set only when the CLI exited non-zero (`run_lifecycle`'s SystemExit
        /// path, the one writer). `message` then holds the English record.
        let exitCode: Int?

        enum CodingKeys: String, CodingKey {
            case category
            case message
            case signalName = "signal_name"
            case exitCode = "exit_code"
        }
    }

    /// Decoded shape of `run.pid`.
    struct PIDFile: Codable {
        let pid: Int32
        let startTime: String
        let runId: String

        enum CodingKeys: String, CodingKey {
            case pid
            case startTime = "start_time"
            case runId = "run_id"
        }
    }

    /// Read the most recent *lifecycle* event (`run_started` / terminus).
    /// Returns `nil` when the file is missing, empty, or has no parseable
    /// lifecycle event. Bounded read. **Skips `run_progress` lines** — those
    /// are in-flight telemetry, not state; a trailing progress line must not
    /// shadow the real terminus or mark a live run as ended (Finding 1). Use
    /// `latestProgress` for the ring.
    static func tailEvent(at url: URL) -> Event? {
        tailMatching(at: url) { $0.event != "run_progress" }
    }

    /// Read the most recent `run_progress` event — the live ring/text signal.
    /// Returns `nil` when no progress line exists yet in the bounded tail.
    static func latestProgress(at url: URL) -> Event? {
        tailMatching(at: url) { $0.event == "run_progress" }
    }

    /// The newest `run_progress` line, if it belongs to the run under way.
    ///
    /// The log is append-only, so the newest progress line can be the previous
    /// run's. Matching it against the newest `run_started` catches that once
    /// the new run has written its start — but a spawned run takes seconds to
    /// get there, and until it does, both lines are the previous run's and
    /// agree. `priorRunId` is the run that was newest on disk when we spawned
    /// (nil when attaching to a run already live): its lines are never this
    /// run's. Without it a re-analyse read the previous run's "8 sessions
    /// readable" and handed the pane from the shoal to a report the new run
    /// had not started (14 Oct 2026).
    static func currentRunProgress(at url: URL, priorRunId: String?) -> Event? {
        guard let event = latestProgress(at: url),
              let current = tailEvent(at: url)?.runId,
              event.runId == current,
              current != priorRunId else { return nil }
        return event
    }

    /// Read from the tail and return the newest decodable event satisfying
    /// `predicate`. Starts with the last 64 KB and widens fourfold, to at most
    /// `tailLimit`, while nothing in the window matches: a running study's log
    /// can end in thousands of `run_progress` lines (up to four a second during
    /// a model download), which pushed its `run_started` out of a fixed 64 KB
    /// window and made a live run read as never started (R22 review). Drops a
    /// chopped first slice.
    private static func tailMatching(
        at url: URL, where predicate: (Event) -> Bool
    ) -> Event? {
        var maxBytes = 65_536
        while true {
            guard let (data, wasTruncated) = readBoundedTail(url: url, maxBytes: maxBytes) else {
                return nil
            }
            switch newestMatching(in: data, wasTruncated: wasTruncated, where: predicate) {
            case .found(let event):
                return event
            case .refused:
                return nil
            case .noMatch:
                guard wasTruncated, maxBytes < tailLimit else { return nil }
                maxBytes *= 4
            }
        }
    }

    /// The widest tail `tailMatching` reads: about ten hours of progress lines.
    static let tailLimit = 64 * 1_048_576

    private enum TailScan {
        case found(Event)
        /// Valid JSON that doesn't fit `Event`: refuse to answer (see below).
        case refused
        case noMatch
    }

    private static func newestMatching(
        in data: Data, wasTruncated: Bool, where predicate: (Event) -> Bool
    ) -> TailScan {
        // JSONL: split on newlines, parse from the tail back.
        let text = String(data: data, encoding: .utf8) ?? ""
        var lines = Array(text.split(separator: "\n", omittingEmptySubsequences: true))
        // If we read from a truncated tail (file > maxBytes), the first slice
        // is almost certainly chopped mid-line. Drop it before iterating —
        // otherwise an accidentally-valid-looking JSON fragment would decode
        // to a wrong event.
        if wasTruncated, !lines.isEmpty {
            lines.removeFirst()
        }
        let decoder = JSONDecoder()
        for line in lines.reversed() {
            // Strip trailing NULs (power-loss padding).
            let cleaned = line.trimmingCharacters(in: CharacterSet(charactersIn: "\0\r"))
            guard !cleaned.isEmpty, let lineData = cleaned.data(using: .utf8) else {
                continue
            }
            if let event = try? decoder.decode(Event.self, from: lineData) {
                // Parseable. Either it's what we're looking for, or it's an
                // event of another kind (`run_progress`, or a forward-compat
                // type from a newer sidecar) and we keep walking back.
                if predicate(event) { return .found(event) }
                continue
            }
            // The decode failed, and the two reasons want opposite handling:
            //
            //   (a) **not valid JSON** — a torn final line from power loss or a
            //       kill mid-write. Skipping it and answering from the line
            //       behind is correct crash recovery, and is pinned by
            //       `tailEventSurvivesPartialTrailingLine`.
            //
            //   (b) **valid JSON that doesn't fit `Event`** — the contract
            //       drifted; this reader's model is out of date. Walking past it
            //       is how a *successful* run got reported as a crash: a
            //       `duration_ms: null` (emitted whenever a stage was fully
            //       cached) made the whole `run_completed` line undecodable, the
            //       loop fell back to that run's `run_started`, a dead PID
            //       turned that into `.failed("Analysis stopped unexpectedly.")`,
            //       and `applyScanResult` then protected the false verdict
            //       across relaunch — all while the report sat there, complete
            //       and correct. See `docs/design-desktop-project-status.md`.
            //
            // So (b) fails **closed**: return nil, which makes `deriveState`
            // return nil, which makes the caller fall back to manifest
            // inference. Refusing to answer is honest; answering about a
            // different event is not.
            if (try? JSONSerialization.jsonObject(with: lineData)) != nil {
                logger.error(
                    """
                    events: a well-formed JSON line does not fit the Event model \
                    — the Python↔Swift contract has drifted. Refusing to derive \
                    state from an older event. line_bytes=\(lineData.count, privacy: .public)
                    """
                )
                return .refused
            }
            // (a) — torn line, keep walking.
        }
        return .noMatch
    }

    /// Map the most recent event + PID-file liveness + manifest stages-complete
    /// onto a `PipelineState`. Returns `nil` when the events log is missing —
    /// caller should fall back to its existing manifest inference.
    static func deriveState(
        eventsURL: URL,
        pidURL: URL,
        stagesComplete: [String]
    ) -> PipelineState? {
        guard FileManager.default.fileExists(atPath: eventsURL.path) else {
            return nil
        }
        guard let event = tailEvent(at: eventsURL) else {
            return nil
        }
        switch event.event {
        case "run_started":
            // In flight if the Python PID file confirms a live owned process.
            // Otherwise the prior run died without writing a terminus — display
            // as failed(unknown). The Python side reconciles on next start.
            //
            // `.failed` and `.failedWithDiagnostic` both route through the same
            // SwiftUI popover surface (`ProjectDiagnosticPopover`).
            // This case renders with the degraded body (no `PipelineSummary`);
            // the visual chrome matches the structured popovers.
            if pythonOwnedRunIsAlive(at: pidURL) {
                return .running
            }
            return .failed(stranded, category: .unknown)
        case "run_completed":
            return mapCompleted(event: event, stagesComplete: stagesComplete)
        case "run_cancelled":
            return .stopped(stagesComplete: stagesComplete, interrupted: endedByLeaving(event.cause))
        case "run_failed":
            // v5 path: a populated `summary` carries per-stage / per-session
            // diagnostics — route to `.failedWithDiagnostic` which renders
            // the per-bucket Grid in the unified popover. Older sidecars
            // without `summary` decode to `.failed`, which renders through
            // the SAME popover surface with the degraded body (no buckets,
            // just the cause string + category). See
            // `ProjectDiagnosticPopover.popoverBodyForCurrentState()`.
            if let pipelineSummary = event.summary,
               pipelineSummary.totalFailureCount > 0 {
                return .failedWithDiagnostic(summary: pipelineSummary)
            }
            let category = event.cause?.category ?? .unknown
            // Python's own sentence when it wrote one; otherwise the category's,
            // which is a good deal more use than the bare "Failed" that stood
            // here — and, either way, resolved by the view rather than frozen
            // into the language in force when the run exited.
            //
            // A CLI exit is the exception: its `message` is our own English
            // record ("CLI exited with code 2"), not someone else's words, so it
            // is said from the code in the app's language, as the browser status
            // page does (`status_page.py`).
            let summary: FailureMessage
            if let code = event.cause?.exitCode {
                summary = .keyed("desktop.pipeline.failure.cliExited", vars: ["code": String(code)])
            } else {
                summary = event.cause?.message.map(FailureMessage.passthrough)
                    ?? .failure(for: category)
            }
            return .failed(summary, category: category)
        default:
            // Unknown event type — likely forward-compat (Phase 4a stage events).
            // Swallow gracefully; not actionable for a human.
            logger.info("unexpected event: \(event.event, privacy: .public)")
            return nil
        }
    }

    private static func mapCompleted(
        event: Event, stagesComplete: [String]
    ) -> PipelineState {
        // `transcribe-only` completes without a render → .partial; allows the
        // UI to offer "Continue (analyse)". `run` and `analyze` produce a
        // full render → .ready.
        if event.kind == "transcribe-only" {
            return .partial(kind: event.kind, stagesComplete: stagesComplete)
        }
        // v5 path: `run_completed` with a summary that carries any session
        // failure → `.completedPartial` (a report was written but degraded).
        // Zero failures (or no summary at all) keeps the existing `.ready`.
        if let summary = event.summary, summary.totalFailureCount > 0 {
            return .completedPartial(summary: summary)
        }
        // For .ready we want a Date — parse `ended_at` if available.
        let date: Date
        if let endedAt = event.endedAt, let parsed = parseISO8601(endedAt) {
            date = parsed
        } else {
            date = Date()
        }
        return .ready(date)
    }

    /// What a `run_started` whose process is gone reads as.
    static let stranded = FailureMessage.keyed("desktop.pipeline.failure.stranded")

    /// Whether a `run_cancelled` ended because the app went, not because the
    /// researcher asked. Stop sends SIGINT, as Ctrl-C does at a terminal, and
    /// Python records the first signal it took. Anything else on a signal cause
    /// is the app leaving: Quit's SIGTERM (`PipelineRunner.quitSignal`), the
    /// run's own parent-death watcher (SIGTERM), a closed terminal (SIGHUP), or
    /// no signal at all when the app had gone (`run_lifecycle._failure_terminus`).
    /// A record with no cause, or one from before 24 Oct 2026 when Quit sent
    /// SIGINT, reads as stopped.
    static func endedByLeaving(_ cause: Cause?) -> Bool {
        guard let cause, cause.category == .userSignal else { return false }
        return cause.signalName != "SIGINT"
    }

    /// Returns `true` iff `<output>/.bristlenose/run.pid` exists, parses,
    /// and its `(pid, start_time)` matches a live process.
    static func pythonOwnedRunIsAlive(at pidURL: URL) -> Bool {
        pythonRunPID(at: pidURL) == .alive
    }

    /// What `run.pid` says about its run, with "can't read it" kept apart from
    /// "it's gone": a watch may end a run only on the second.
    enum PIDVerdict: Equatable { case alive, gone, unreadable }

    /// A run another process owns, judged from disk alone (R22).
    enum ForeignRunVerdict: Equatable {
        /// Its `run_started` is newest and its process is alive.
        case live
        /// A terminus is newest, or `run.pid` names a process that is gone.
        case ended
        /// Neither can be told: no lifecycle line found, or `run.pid` missing
        /// or unreadable. Not an end.
        case unknown
    }

    static func foreignRunVerdict(eventsURL: URL, pidURL: URL) -> ForeignRunVerdict {
        guard let tail = tailEvent(at: eventsURL) else { return .unknown }
        guard tail.event == "run_started" else { return .ended }
        switch pythonRunPID(at: pidURL) {
        case .alive: return .live
        case .gone: return .ended
        case .unreadable: return .unknown
        }
    }

    static func pythonRunPID(at pidURL: URL) -> PIDVerdict {
        guard let data = try? Data(contentsOf: pidURL),
              let payload = try? JSONDecoder().decode(PIDFile.self, from: data) else {
            return .unreadable
        }
        // Signal 0 asks whether the process exists, and only ESRCH says no.
        // App Sandbox answers EPERM for any process outside the app's sandbox
        // (measured 20 Oct 2026 from the sandboxed test host: Dock, Finder),
        // and a CLI run started in Terminal is one. Read as gone, a live CLI
        // run on a sidebar study showed "Analysis stopped unexpectedly" (R22).
        // The start time below still rules out a reused pid.
        guard kill(payload.pid, 0) == 0 || errno == EPERM else { return .gone }
        // Verify start_time matches — defeats PID reuse.
        guard let start = procStartTime(pid: payload.pid) else { return .gone }
        return start == payload.startTime ? .alive : .gone
    }

    /// Returns the process start time as `"<tvsec>.<tvusec>"`, byte-identical
    /// to what Python's `run_lifecycle._ps_start_time` writes on macOS
    /// (`f"{info.pbi_start_tvsec}.{info.pbi_start_tvusec}"`). Must match that
    /// format exactly — the value is compared for equality across the
    /// Swift/Python boundary, never parsed.
    ///
    /// Uses `proc_pidinfo(PROC_PIDTBSDINFO)` (libproc) rather than `/bin/ps`:
    /// the bundled desktop sidecar runs under App Sandbox, which blocks
    /// `Process()` exec of `/bin/ps` at the exec boundary, but permits narrow
    /// libproc syscalls for a known PID. See `docs/design-desktop-python-runtime.md`.
    static func procStartTime(pid: Int32) -> String? {
        var info = proc_bsdinfo()
        let size = Int32(MemoryLayout<proc_bsdinfo>.size)
        let n = proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, size)
        guard n == size else { return nil }
        return "\(info.pbi_start_tvsec).\(info.pbi_start_tvusec)"
    }

    /// The owning uid of `pid`, from the same libproc query. Nil when the
    /// query fails — a dead pid, or one we may not inspect — which the caller
    /// must treat as *unknown*, never as *not ours*. Replaced the
    /// `/bin/ps -o uid=` exec in `PipelineRunner.aliveOwnedRunPID`, which App
    /// Sandbox refuses (measured 12 Oct 2026: `Operation not permitted` from
    /// the sandboxed test host, while this call answered uid 501).
    static func procUID(pid: Int32) -> uid_t? {
        var info = proc_bsdinfo()
        let size = Int32(MemoryLayout<proc_bsdinfo>.size)
        let n = proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, size)
        guard n == size else { return nil }
        return info.pbi_uid
    }

    /// The parent pid of `pid`, from the same libproc query; nil when the query
    /// fails. 1 (launchd) for a run whose app has gone.
    static func procParentPID(pid: Int32) -> pid_t? {
        var info = proc_bsdinfo()
        let size = Int32(MemoryLayout<proc_bsdinfo>.size)
        let n = proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, size)
        guard n == size else { return nil }
        return pid_t(info.pbi_ppid)
    }

    /// Read the last `maxBytes` bytes of `url`. Returns `(data, wasTruncated)`
    /// where `wasTruncated` indicates the file exceeded `maxBytes` and the
    /// caller should drop the first slice (likely chopped mid-line).
    /// Returns `nil` on missing or unreadable file. Mirrors Python's
    /// `_iter_event_lines` recovery posture — caller handles malformed lines.
    private static func readBoundedTail(url: URL, maxBytes: Int) -> (Data, Bool)? {
        guard let handle = try? FileHandle(forReadingFrom: url) else {
            return nil
        }
        defer { try? handle.close() }
        guard let endOffset = try? handle.seekToEnd() else { return nil }
        let truncated = endOffset > UInt64(maxBytes)
        let readFrom: UInt64 = truncated ? endOffset - UInt64(maxBytes) : 0
        guard (try? handle.seek(toOffset: readFrom)) != nil else { return nil }
        guard let data = try? handle.readToEnd() else { return nil }
        return (data, truncated)
    }

    /// Parse a Python-emitted ISO8601 timestamp. Tries with fractional
    /// seconds first (Python's default), falls back to without — Python's
    /// `datetime.isoformat()` omits fractional seconds when `microsecond == 0`.
    static func parseISO8601(_ string: String) -> Date? {
        if let date = iso8601WithFractional.date(from: string) { return date }
        return iso8601Plain.date(from: string)
    }

    private static let iso8601WithFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let iso8601Plain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()
}
